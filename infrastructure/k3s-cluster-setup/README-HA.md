# k3s control-plane HA — apply runbook

Status: **IaC ready, NOT applied.** This branch teaches `k3s-cluster-setup` to run
more than one control-plane server on the existing external Postgres datastore.
Applying it (promoting lw-c1 + lw-c2 to servers) is a **maintenance-window action**
with you awake — it reinstalls k3s on the promoted nodes and briefly churns their pods.

## Why

Today lw-c3 is the **only** k3s server. If c3 dies, the whole API dies — every
hosted service with it. Three servers behind the kube-vip VIP (`192.168.0.60`)
make a single control-plane node death survivable.

## What this branch changes

- `setup.yml`: `[k3s_server]` (exactly one) → `[k3s_servers]` (one or more), servers
  roll `serial: 1`, agents join via the VIP not a single host.
- `k3s-server` role: datastore endpoint + shared token passed as `K3S_*` **env**
  (installer writes them to `/etc/systemd/system/k3s.service.env`, mode 0600) — so
  they stop living in the unit's `ExecStart` / `ps` output.
- `group_vars`: `--tls-san` now covers the VIP + all three control-plane IPs so any
  server's cert is valid for `https://192.168.0.60:6443`.
- `inventory`: **corrected** — it listed lw-c1 as the server (stale/wrong); reality
  is lw-c3. An accidental run now matches reality instead of flipping the CP.

## Prerequisites (do first)

1. **Cable eno1 on lw-nas and move `.115` (datastore + NFS) onto wired.** Building
   HA while the datastore rides a USB WiFi dongle is pointless — WiFi drop still
   kills the DB. This is the real fix and it is physical.
2. **Store the shared token + datastore endpoint in Vault** (they are currently only
   on c3):
   - token: `sudo cat /var/lib/rancher/k3s/server/token` on lw-c3 → `secret/k3s/token`
   - endpoint: `postgres://k3s:PASSWORD@192.168.0.115:5432/k3s_state?sslmode=disable`
     → `secret/k3s/datastore`
3. Take a fresh off-NAS state backup: `~/homelab-backups/k3s-state-backup.sh` (runs
   every 6h via cron; run once manually right before the window).

## Apply (maintenance window)

```bash
cd ~/Code/ansible
# 1. Uncomment the HA [k3s_servers] block in inventory/hosts.ini (c3+c1+c2), empty [k3s_agents].
# 2. Apply, secrets from Vault, one server at a time:
ansible-playbook infrastructure/k3s-cluster-setup/setup.yml \
  -i infrastructure/k3s-cluster-setup/inventory/hosts.ini \
  -e "k3s_datastore_endpoint=$(vault kv get -field=endpoint secret/k3s/datastore)" \
  -e "k3s_token=$(vault kv get -field=token secret/k3s/token)"
```

## Verify (before trusting it)

- `kubectl get nodes` → c1, c2, c3 all `control-plane,master` Ready.
- `kubectl -n kube-system get pods -o wide | grep kube-vip` → a kube-vip pod on each server.
- **Prove VIP failover by DRAIN, never by editing c3:**
  `kubectl drain lw-c3 --ignore-daemonsets --delete-emptydir-data` → confirm `.60`
  moves to c1/c2 and `kubectl get --raw=/readyz` still returns `ok`; then `uncordon`.

## What this does NOT fix (say it out loud)

- **NAS death still downs the cluster.** The datastore is still one Postgres on
  lw-nas, and NFS RWX PVCs are still served from lw-nas. Three apiservers change
  "c3 dies" from fatal to survivable; they do nothing for "NAS dies." True NAS-death
  survival needs datastore replication (Postgres, not etcd — k3s has no in-place
  Postgres→etcd migration) + NFS resilience, on top of the eno1 cabling above.
- Tonight's actual failure (unattended NAS power-loss) is already auto-recovered in
  ~4 min by the lw-pi watchdog + Wake-on-LAN, and state is dumped off-NAS every 6h.

## Follow-up to fold into the SAME window

- **Rotate the datastore password** — it is plaintext in c3's current unit and has
  been exposed. Rotating touches the PG user + every server's connection string, so
  do it here (once) rather than as a separate window: rotate the `k3s` PG role
  password, update `secret/k3s/datastore`, re-apply.

## Rollback

Each server rolls `serial: 1`; if a node fails to come up, the other servers keep the
API. To revert a node to agent: move it back to `[k3s_agents]`, run
`k3s-uninstall.sh` on it, re-apply. c3 is never touched by a promotion of c1/c2.

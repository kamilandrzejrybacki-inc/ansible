# Migration: lw-s1 → lw-c3 (k3s compute node)

**Status:** COMPLETED 2026-05-12 — all 7 phases ran; lw-c3 is a k3s agent, docker purged, n8n + excalidraw on the cluster
**Owner:** kamil-rybacki
**Started:** 2026-05-11
**Cutover ETA:** done 2026-05-12

## Goal

Take the Ubuntu host currently named `lw-s1` (192.168.0.108), evict every
Docker workload from it, rename it to `lw-c3`, and add it to the k3s
cluster as a third agent node. No OS re-install — in-place cleanup.

## Current state on lw-s1 (snapshot 2026-05-11)

### Docker workloads

| Container | Image | State | Decision |
|---|---|---|---|
| `n8n` | docker.n8n.io/n8nio/n8n | running, queue mode | migrate → helm `n8n-main` |
| `n8n-secret-proxy` | local sidecar (NetworkMode container:n8n) | running | re-implement as k8s sidecar |
| `n8n-vault-shim` | local image, mounts /var/run/docker.sock | running | replace with static k8s Secret from Vault via Ansible |
| `excalidraw` | excalidraw-patched:local | running (unhealthy) | migrate → helm `excalidraw` |
| `excalidraw-storage` | alswl/excalidraw-storage-backend | running | migrate → helm `excalidraw` |
| `excalidraw-redis` | redis:7-alpine | running | migrate → helm `excalidraw` |
| `distillery-ui` | nginx:alpine | running | KILL (deprecated, will be reworked) |
| `docker-exporter` | ghcr.io/davidborzek/docker-exporter | running | KILL (k8s-monitoring covers cluster-wide) |

### Persistent state

- Docker volume `n8n_data` → `/home/node/.n8n` (343 MB, encryption key + sqlite metadata + workflow cache)
- Bind `/opt/n8n/binary-data` → `/data/binary-data` (16 KB, attachments)
- All excalidraw containers are stateless (storage backend uses Redis only, no PVCs)

### Systemd workloads

| Unit | Decision |
|---|---|
| `alloy.service` | disable (k8s-monitoring will run alloy as DaemonSet) |
| `homelab-startup.service` | audit → disable if it only existed for the docker stack |
| `n8n-proxy-watcher.service` | disable (replaced by k8s Deployment management) |
| `runner-net-iptables.service` | audit before action |
| `snmpd.service` | keep (useful on a compute node) |
| `lightdm.service` | disable (headless compute) |
| `docker.service`, `containerd.service` | purge after workloads gone |

### Inventory referencing lw-s1

- `infrastructure/nas-link-setup` — already obsolete since switch-port topology change; delete after this migration
- `infrastructure/hermes-pi/templates/config.yaml.j2` — n8n MCP URL
- `infrastructure/netbox-agent-setup/setup.yml` — sample list
- `monitoring/alloy-agent-setup/setup.yml` — sample list
- `monitoring/distillery-ui-setup/` — entire playbook deprecated
- `monitoring/mimir-loki-setup/group_vars/all.yml` — scrape target
- `automation/n8n-setup/` — entire playbook (host-based) replaced by helm chart
- `files/excalidraw-setup/` — entire playbook replaced by helm chart
- `dev-tools/nexterm-setup/group_vars/all.yml` — host entry needs rename
- `security/secure-homelab-access/group_vars/all.yml` — `excalidraw_host` fallback
- `security/secure-homelab-access/roles/caddy/templates/Caddyfile.j2` — n8n + excalidraw upstreams

Helm:
- `charts/hermes/values.yaml` — n8n MCP URL (192.168.0.108:5678)

## Pre-flight (Phase 0)

**Done:**
- Backup of `n8n_data` volume → `/backup/lw-s1-2026-05-11/n8n-data-2026-05-11.tar.gz` (84 MB compressed)
- Backup of `/opt/n8n/binary-data` → same dir
- Full env dump of `n8n` container (encryption key + 127 N8N_VAR_* secrets + DB/queue config) → same dir
- `docker inspect` of every n8n + excalidraw container → same dir
- SHA256 checksums in `SHA256SUMS`

**Pending:**
- Locate `lw-nas` on current LAN. NAS is the postgres + redis + couchdb host; n8n queue mode will not start without it. Memory IP `10.0.1.2` is stale (direct cable removed). User reports NAS powered + cabled to router, but neither MAC `18:03:73:1f:85:ae` (its old USB-eth) nor any matching SSH host key shows up on the LAN sweep.

## Phases (in execution order)

### Phase 1 — `n8n-main` helm chart

Pair with existing `charts/n8n-workers`. Includes:

- Deployment (1 replica, `command=["n8n", "start"]`, `EXECUTIONS_MODE=queue`)
- Stable PVC `n8n-data` (RWO, `local-path`) mounted at `/home/node/.n8n`
- Stable PVC `n8n-binary-data` (RWO, `local-path`) mounted at `/data/binary-data`
- Secret `n8n-main-secrets` containing: encryption_key, DB password, queue Redis password, all `N8N_VAR_*` entries
- Sidecar `secret-proxy` (port-forwards Vault-shim style secrets on localhost:8787 inside the pod's network namespace)
- ConfigMap with non-secret env (WEBHOOK_URL, N8N_PROTOCOL, N8N_PORT)
- ClusterIP Service + NodePort (Caddy uses NodePort upstream)
- (Optional) Ingress disabled by default — Caddy on lw-main owns external HTTPS

### Phase 2 — Vault secret rendering

New Ansible role `n8n-vault-render` (under `automation/n8n-cluster-setup`):

1. Read all paths from Vault (homelab/n8n/*, homelab/api-keys/*, etc.) using the existing Vault token pattern.
2. Render a single Kubernetes Secret manifest (`n8n-main-secrets`) and `kubectl apply` it.
3. Re-run is idempotent and overwrites only changed keys.

Trade-off vs. Vault Agent Injector: simpler, but doesn't auto-rotate. Acceptable for now.

### Phase 3 — `excalidraw` helm chart

- 3 Deployments: `frontend` (nginx), `storage` (backend), `redis` (cache)
- PVC for `redis` data (`local-path`, RWO)
- ClusterIP Services for each, plus a single NodePort on `frontend`
- Caddy keeps current routes — upstream IP/port swap only

### Phase 4 — Cutover

1. Snapshot lw-nas postgres `n8n` DB once NAS is reachable; restore to its destination (existing instance if up, or fresh deploy).
2. Apply `n8n-main` and `excalidraw` charts with secrets in place.
3. Wait for pods Ready, login to n8n, run a smoke workflow.
4. On lw-s1: `docker stop $(docker ps -aq)` → verify nothing critical broke.
5. Update Caddy upstreams (`n8n_host_ip`, `excalidraw_host`) → `caddy reload`.
6. Verify via public domains (`n8n.kamilandrzejrybacki.dpdns.org`, etc.).

Estimated wall-clock downtime for n8n: 15–30 min during cutover.

### Phase 5 — lw-s1 cleanup

After 24h soak with no incidents:

1. Disable + stop: `alloy`, `homelab-startup`, `n8n-proxy-watcher`, `lightdm` (audit `runner-net-iptables` before touching).
2. `docker system prune -af --volumes`
3. `apt purge docker-ce docker-ce-cli containerd.io lightdm`
4. `apt autoremove --purge`

### Phase 6 — Rename in place

1. `sudo hostnamectl set-hostname lw-c3`
2. Edit `/etc/hosts`, `/etc/cloud/cloud.cfg` (`preserve_hostname: true`).
3. Reboot.
4. Verify hostname survives reboot.

### Phase 7 — k3s agent join

1. Append to `infrastructure/k3s-cluster-setup/inventory/hosts.ini`:
   ```
   [k3s_agents]
   192.168.0.108 ansible_user=kamil ansible_python_interpreter=/usr/bin/python3 ansible_ssh_private_key_file=/home/kamil-rybacki/.ssh/id_ed25519
   ```
2. `ansible-playbook infrastructure/k3s-cluster-setup/setup.yml -i .../hosts.ini`
3. Verify on lw-c1: `sudo kubectl get nodes` → `lw-c3 Ready`.
4. Optional: label/taint `lw-c3` for specific workloads.

### Phase 8 — Ansible / helm hygiene

Mass cleanup PR:

- Delete `automation/n8n-setup`, `files/excalidraw-setup`, `monitoring/distillery-ui-setup`, `infrastructure/nas-link-setup`.
- Update `infrastructure/hermes-pi/templates/config.yaml.j2`: n8n URL → cluster Service DNS (`http://n8n-main.n8n.svc.cluster.local:5678/mcp-server/http`).
- Update `dev-tools/nexterm-setup/group_vars/all.yml`: rename entry.
- Update `monitoring/alloy-agent-setup/setup.yml`, `monitoring/mimir-loki-setup/group_vars/all.yml`: drop lw-s1 host; cluster pods auto-discovered by k8s-monitoring.
- Update `security/secure-homelab-access` group_vars + Caddyfile: switch upstreams to cluster Service / NodePort.
- Update `charts/hermes/values.yaml` n8n URL.

## Risks + Mitigations

| Risk | Mitigation |
|---|---|
| n8n encryption key lost → all credentials encrypted with it become unreadable | Encryption key captured in `n8n-env-2026-05-11.txt`; chart Secret uses same key |
| postgres data unavailable (NAS missing) | Block migration until NAS located or new postgres provisioned |
| Caddy outage during upstream swap | Stage new upstream in Caddyfile alongside old, toggle in single reload |
| k3s join fails on Ubuntu 25.04 (`questing`) | Test cgroup2 + apparmor + nf_conntrack module before Phase 7; have rollback (stop k3s-agent unit, no impact on workloads) |
| Hostname rename breaks Mimir/Loki labels | lw-s1 is being retired from alloy host pool in Phase 8 — labels die cleanly |
| `runner-net-iptables.service` unknown purpose | Capture its unit file + iptables rules during Phase 5 audit; defer disable if unsure |

## Backups inventory

Stored on lw-main at `/backup/lw-s1-2026-05-11/`:

| File | Size | Purpose |
|---|---|---|
| `n8n-data-2026-05-11.tar.gz` | 84 MB | Volume `n8n_data` (encryption key, sqlite, workflows) |
| `n8n-binary-data-2026-05-11.tar.gz` | <1 KB | Bind mount `/opt/n8n/binary-data` |
| `n8n-env-2026-05-11.txt` | 56 KB | Full `docker exec n8n env` (secrets — do NOT commit) |
| `n8n-stack-inspect-2026-05-11.json` | 112 KB | `docker inspect` of every n8n + excalidraw container |
| `SHA256SUMS` | — | Integrity check for all of the above |

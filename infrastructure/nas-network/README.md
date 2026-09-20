# nas-network — lw-nas LAN address + Wake-on-LAN

Pins `192.168.0.115/24` and Wake-on-LAN onto lw-nas's **wired** NIC (`eno1`,
matched by MAC `18:03:73:1f:85:ae`).

## Why this exists

lw-nas is a hard SPOF: it serves the k3s control-plane datastore Postgres
(`5432`) and every RWX NFS PV (`2049`). Until 2026-09-20 its `.115` lived on a
USB WiFi dongle while `eno1` carried a static `10.0.1.2/24` for the retired
lw-main↔lw-nas direct cable. When the homelab was re-cabled onto a single
switch the dongle went away, `.115` disappeared from the LAN, and the whole
cluster went down — k3s stuck `activating` on all three control-plane nodes,
API VIP `.60` dead, every ingress 502. The fix was applied by hand; this role
is what makes it reproducible.

The retired direct link (`10.0.1.0/24`) is deliberately **not** in this role.
A secondary `10.0.1.2/24` is still live on the NAS as a fallback from that
incident; applying this role removes it. Nothing should depend on it — check
`grep -rn '10\.0\.1\.' ~/Code/ansible` first.

## Usage

```bash
# ALWAYS dry-run first — this rewrites the NAS's primary netplan
ansible-playbook infrastructure/nas-network/setup.yml \
  -i localhost, --check --diff

ansible-playbook infrastructure/nas-network/setup.yml -i localhost,
```

`netplan apply` is fired detached (it drops the SSH session mid-task), then the
role reconnects, re-arms WoL, and asserts that `.115` is up, `Wake-on: g` is
set, and both `5432` and `2049` still answer from the control node.

## Wake-on-LAN consumers

- `~/.local/bin/homelab-recover` on lw-main (`NAS_MAC`)
- `/home/kamil/homelab-nas-watchdog.sh` on lw-pi (cron, every 2 min)

Both wake the NAS by the `eno1` MAC. Netplan arms WoL at boot; the udev rule
re-arms it whenever the NIC reappears.

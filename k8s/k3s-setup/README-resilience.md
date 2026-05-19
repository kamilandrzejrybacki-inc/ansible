# k3s Resilience Artifacts

Power outage hardening files. Install via the ansible playbook (TBD) or manually following the deploy notes here.

## Files

| File | Purpose | When to apply |
|---|---|---|
| `files/network-recovery.service` | systemd oneshot — bounces eno1 on lw-c1 at boot to refresh LAN switch MAC table | Already deployed to lw-c1 (2026-05-19) |
| `files/k3s-backup.sh` | Sqlite snapshot script — backs up `/var/lib/rancher/k3s/server/db/state.db` to MinIO | Interim; replaced by k3s built-in etcd snapshots in Phase 4 |
| `files/k3s-backup.service` | systemd oneshot for the backup script | After mc CLI installed on lw-c1 + `/etc/k3s-backup.env` populated |
| `files/k3s-backup.timer` | Daily timer for backup | Same as above |
| `files/k3s-server-config-phase4.yaml` | k3s config.yaml for HA + etcd snapshots → S3 | Phase 4 ONLY — after etcd migration |

## Manual install (interim, until ansible role written)

### Network recovery (DONE on lw-c1)

```bash
sudo cp network-recovery.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable network-recovery.service
```

Triggers at next boot. Won't run immediately (oneshot, RemainAfterExit).

### k3s backup (interim sqlite, manual install)

```bash
# Install mc on lw-c1
sudo curl -sLo /usr/local/bin/mc https://dl.min.io/client/mc/release/linux-amd64/mc
sudo chmod +x /usr/local/bin/mc

# Create MinIO bucket (one-time, via mc)
# (credentials from kubectl -n minio get secret minio-secrets -o yaml | yq .data)
MINIO_USER=$(kubectl -n minio get secret minio-secrets -o jsonpath='{.data.MINIO_ROOT_USER}' | base64 -d)
MINIO_PASS=$(kubectl -n minio get secret minio-secrets -o jsonpath='{.data.MINIO_ROOT_PASSWORD}' | base64 -d)

# Create env file (root-readable only)
sudo tee /etc/k3s-backup.env >/dev/null <<EOF
MC_HOST=http://192.168.0.107:30910
BUCKET=k3s-snapshots
MC_ACCESS_KEY=$MINIO_USER
MC_SECRET_KEY=$MINIO_PASS
EOF
sudo chmod 600 /etc/k3s-backup.env

# Install script + timer
sudo cp k3s-backup.sh /usr/local/bin/k3s-backup.sh
sudo chmod 755 /usr/local/bin/k3s-backup.sh
sudo cp k3s-backup.service k3s-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now k3s-backup.timer

# Test once
sudo systemctl start k3s-backup.service
sudo journalctl -u k3s-backup.service -n 30
```

## Phase 4 etcd migration (planned, NOT YET DONE)

Switching k3s from sqlite to embedded etcd is one-way and requires brief downtime. See `docs/superpowers/plans/2026-05-19-homelab-network-simplification.md` Task 12 (HA control plane).

Migration outline:

1. Backup sqlite state: copy `/var/lib/rancher/k3s/server/db/state.db`.
2. Stop k3s on lw-c1.
3. Move state aside: `mv /var/lib/rancher/k3s/server/db/state.db /var/lib/rancher/k3s/server/db/state.db.bak`.
4. Edit `/etc/rancher/k3s/config.yaml` with the phase4 config (above), plus `--cluster-init`.
5. Start k3s → it creates etcd datastore.
6. Now k3s etcd-snapshot ls works.
7. Follow Task 12 of the plan to promote lw-c2 + lw-c3 to servers.

After migration, retire `k3s-backup.timer` — k3s built-in `etcd-snapshot-schedule-cron` replaces it.

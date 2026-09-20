# nas-pv-backup — nightly snapshot of the Kubernetes NFS PV tree

Snapshots `/mnt/pool/k8s-nfs` (every RWX PersistentVolume in the cluster) onto
lw-nas's 1.8 TB archive disk, hardlinked against the previous snapshot.

## Why

Before this role, every cluster PV — Hermes' home, Paperless, Grafana,
Prometheus, Loki, model caches, ~7.7 GB — lived on lw-nas's **single 120 GB
SSD** (`sdb2`, which is also the root filesystem and the k3s datastore's disk).
No RAID, no snapshots, no backup. Meanwhile the 1.8 TB spinning disk
(`sda`, `/mnt/disks/archive`) sat at 4% used. One SSD failure would have taken
every PV in the homelab with it.

The documented mergerfs + SnapRAID pool does **not** exist on this box; only
the two disks above are real. Do not assume parity protection.

## What it protects against, and what it does not

| Failure | Covered? |
|---|---|
| SSD (`sdb`) dies or corrupts | **Yes** — snapshots are on `sda` |
| Accidental deletion inside a PV | **Yes** — up to `nas_pv_backup_retain` days |
| lw-nas dies (PSU, board, whole box) | **No** — both disks are in that box |
| Application-level corruption | **Partially** — see below |

**The copy is crash-consistent, not application-consistent.** rsync walks a live
tree, so a service mid-write lands in the snapshot mid-write. For plain files
(documents, model caches, Hermes' notes) that is fine. Services that keep a
database inside a PV — Paperless, Grafana — should also produce their own dump;
`litellm` already does this into its own `litellm-postgres-backup` PVC. The k3s
control-plane datastore is dumped separately by `k3s-pg-backup.timer`.

**Off-box mirroring is deliberately not part of this role.** lw-main has ~12 GB
free and lw-pi ~13 GB, so neither comfortably holds 7.7 GB plus growth. If the
whole-NAS failure case matters, the options are cloud object storage (an R2 /
B2 bucket already exists for the homelab) or a selective mirror of only the
PVs that cannot be rebuilt.

## Safety guard worth knowing about

`/etc/fstab` mounts the archive disk with `nofail`. If `sda` ever disappears,
`/mnt/disks/archive` silently becomes an empty directory **on the SSD** — so a
naive backup would write onto the very disk it protects against and fill the
root filesystem. Both the role and the script refuse to run unless the
destination is a real mountpoint on a different device than the source.

## Observability

The script writes `nas_pv_backup.prom` into `/var/lib/node_exporter/textfile`,
which is the directory lw-nas's node-exporter actually reads
(`--collector.textfile.directory=/host/var/lib/node_exporter/textfile`) and
which Alloy scrapes as job `node-lw-nas`. Metrics: `nas_pv_backup_success`,
`..._last_success_timestamp_seconds`, `..._last_run_timestamp_seconds`,
`..._duration_seconds`, `..._size_bytes`, `..._snapshots`.

An alert on `time() - nas_pv_backup_last_success_timestamp_seconds > 172800`
catches a silently dead backup, which is the usual way backups fail.

> Note: the pre-existing `snapraid-collector.sh` cron writes to
> `/opt/nas-monitoring/textfile`, which nothing reads — that is why its metrics
> never appeared in Grafana. It is also pointed at a SnapRAID array that does
> not exist (`/etc/snapraid.conf` is absent).

## Usage

```bash
# dry-run first
ansible-playbook infrastructure/nas-pv-backup/setup.yml -i localhost, --check --diff

ansible-playbook infrastructure/nas-pv-backup/setup.yml -i localhost,

# on lw-nas: run once by hand, watch it
sudo systemctl start nas-pv-backup.service && journalctl -u nas-pv-backup -n 20 --no-pager
```

## Restoring

Snapshots are plain directories; `latest` symlinks the newest.

```bash
# inspect
ls /mnt/disks/archive/k8s-nfs-backups/
# restore one PV (stop the workload first)
sudo rsync -aHAX --numeric-ids --delete \
  /mnt/disks/archive/k8s-nfs-backups/latest/<pv-dir>/ \
  /mnt/pool/k8s-nfs/<pv-dir>/
```

Because snapshots are hardlinked, deleting an old one never damages a newer
one, and `du` over the whole tree overstates real usage.

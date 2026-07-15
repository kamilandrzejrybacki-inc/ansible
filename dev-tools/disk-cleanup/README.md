# Disk Cleanup

Daily, reclaimable-only disk maintenance for a dev/homelab host. Installs a
user-level script and a **09:00 daily** cron entry.

## What it reclaims (and what it never touches)

Reclaims **only scratch**:

- Rust `incremental` caches anywhere under `~/Code` (compiled deps kept).
- Full `target/` dirs of projects untouched for **>7 days** (a rebuild regenerates them).
- Docker **build cache** + **dangling** (untagged) images.
- `journalctl --vacuum-time=7d` + `apt-get clean` — only if passwordless sudo exists, else skipped.

It **never** removes images-in-use, running/stopped containers, volumes, or any
user data. No `docker system prune -a`, no volume prune.

## Apply

```bash
ansible-playbook dev-tools/disk-cleanup/setup.yml \
  -i dev-tools/disk-cleanup/inventory/hosts.ini
```

Idempotent — re-running updates the script and cron in place. The cron entry is
managed by ansible (marked `#Ansible: deblob-disk-cleanup` in the crontab); do
not add a second unmanaged copy by hand.

## Files

| Path | Role |
|------|------|
| `setup.yml` | Playbook: install script + cron (local, user-level, no become). |
| `files/disk-cleanup.sh` | The cleanup script (source of truth — edit here). |
| `inventory/hosts.ini` | `localhost` over a local connection. |

Logs to `~/.local/share/deblob-disk-cleanup.log`.

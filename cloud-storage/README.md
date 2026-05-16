# Cloud Object Storage — homelab offsite backup

Replicates the in-cluster MinIO to three free-tier S3-compatible providers
(Cloudflare R2 + Tigris + Backblaze B2) for offsite redundancy.

## Prereqs

1. **Provider accounts** created manually (signup not scriptable).
2. **Credentials** in `~/.config/homelab-s3-remotes.env` (chmod 600, gitignored).
   Required vars: see `homelab-s3-remotes.env.example`.

## Scripts (run in order, idempotent)

| # | Script | What it does |
|---|--------|--------------|
| 01 | `01-install-tools.sh` | apt + npm + pipx install of aws/rclone/wrangler/tigris/b2 |
| 02 | `02-provision-buckets.sh` | creates one private bucket per provider |
| 03 | `03-configure-aws-profiles.sh` | writes `~/.aws/credentials` + `~/.aws/config` (profiles: r2, tigris, b2-s3, minio) |
| 04 | `04-configure-rclone.sh` | writes `~/.config/rclone/rclone.conf` (incl. `cloud-free-pool` union) |
| 05 | `05-test-remotes.sh` | round-trips a tiny file through each remote |
| 06 | `06-sync-minio-to-cloud.sh` | copies every MinIO bucket → all 3 clouds (uses `copy` not `sync`, requires `--confirm`) |

## Provider caveats

- **Cloudflare R2**: region MUST be `auto`. Wrangler needs API token with R2 perms.
- **Tigris**: endpoint `https://t3.storage.dev`. CLI is Node-based (`@tigrisdata/cli`).
- **Backblaze B2**: S3 endpoint is region-specific — discovered after `b2 account authorize`. Script 02 auto-updates env file with actual region.
- **MinIO**: reached via NodePort `192.168.0.107:30910` from lw-main (not cluster DNS).

## Restore

Manual from any provider:
```bash
rclone copy r2:${R2_BUCKET}/minio/<bucket> minio:<bucket>
```

## Scheduling

Not in this directory — wire `06-sync-minio-to-cloud.sh --confirm` into a systemd
timer or Velero hook. Run interactively first to confirm bandwidth/cost.

## Security

- Env file `chmod 600`, gitignored (`*.env`).
- Each provider key is scoped (R2 bucket-level token, Tigris private user key, B2 Master Key — *should be downgraded to bucket-scoped key in B2 console*).
- TODO: replace B2 master key with bucket-scoped key, then update env.
- TODO: mirror creds into Vault (`secret/homelab/cloud-storage/{r2,tigris,b2}`) for cross-host access.

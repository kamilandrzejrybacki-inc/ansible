#!/usr/bin/env bash
# Sync policy:
#   CRITICAL (durable user/system data) → MinIO + Backblaze B2
#     - velero      : k8s cluster + PV backups
#     - backups     : application data dumps
#     - obsidian    : personal markdown notes
#   EPHEMERAL (regenerable, don't waste cloud quota)
#     - loki        : logs — stays in MinIO only
#     - mimir       : metrics — stays in MinIO only
#
# R2 + Tigris remain provisioned for ad-hoc general storage, not auto-synced.
# Use rclone copy (never sync) so cloud retains versions even if MinIO drops them.
#
# Pass --confirm to execute. Default is dry-run.
set -euo pipefail
source "${HOME}/.config/homelab-s3-remotes.env"

CONFIRM=0
[[ "${1:-}" == "--confirm" ]] && CONFIRM=1

LOG_DIR="${HOME}/.cache/rclone-sync"
mkdir -p "${LOG_DIR}"

CRITICAL_BUCKETS="velero backups obsidian"

run_copy() {
  local src="$1" dst="$2" log="$3"
  if [ ${CONFIRM} -eq 1 ]; then
    echo "==> ${src}  →  ${dst}"
    rclone copy "${src}" "${dst}" \
      --transfers 4 --checkers 8 \
      --log-file "${log}" --log-level INFO \
      --stats=30s 2>&1 | tail -3
  else
    echo "DRY-RUN: ${src}  →  ${dst}"
  fi
}

echo "================================================"
echo "  MinIO  →  Backblaze B2  (critical only)"
echo "================================================"
for bucket in ${CRITICAL_BUCKETS}; do
  run_copy "minio:${bucket}" "b2-s3:${B2_BUCKET}/minio/${bucket}" \
    "${LOG_DIR}/$(date +%Y%m%d-%H%M%S)-b2-${bucket}.log"
done

if [ ${CONFIRM} -eq 0 ]; then
  echo
  echo "Re-run with --confirm to execute. Logs: ${LOG_DIR}/"
fi

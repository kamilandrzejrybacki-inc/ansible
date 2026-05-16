#!/usr/bin/env bash
# Sync policy:
#   CRITICAL backups (velero, backups)   → MinIO + Backblaze B2  (durable)
#   General data (loki, mimir, obsidian) → MinIO + R2 + Tigris   (cheap/cold)
#
# R2 enforces a soft 10GB cap client-side (free tier). Cloudflare has no
# native hard cap; this script checks size before each write and aborts
# the R2 leg if it would exceed R2_HARD_CAP_BYTES.
#
# Pass --confirm to execute; default is dry-run.
set -euo pipefail
source "${HOME}/.config/homelab-s3-remotes.env"

CONFIRM=0
[[ "${1:-}" == "--confirm" ]] && CONFIRM=1

LOG_DIR="${HOME}/.cache/rclone-sync"
mkdir -p "${LOG_DIR}"

# Sync targets per bucket category
CRITICAL_BUCKETS="velero backups"
GENERAL_BUCKETS="loki mimir obsidian"

# R2 free tier = 10 GB. Hard cap below; abort R2 writes when reached.
R2_HARD_CAP_BYTES=$((10 * 1024 * 1024 * 1024))   # 10 GiB

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

r2_size_bytes() {
  rclone size "r2:${R2_BUCKET}" --json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('bytes',0))" || echo 0
}

echo "============================================================"
echo "  CRITICAL: MinIO  →  Backblaze B2"
echo "============================================================"
for bucket in ${CRITICAL_BUCKETS}; do
  run_copy "minio:${bucket}" "b2-s3:${B2_BUCKET}/minio/${bucket}" "${LOG_DIR}/$(date +%Y%m%d-%H%M%S)-b2-${bucket}.log"
done

echo
echo "============================================================"
echo "  GENERAL: MinIO  →  Tigris  +  R2 (10GB capped)"
echo "============================================================"
for bucket in ${GENERAL_BUCKETS}; do
  run_copy "minio:${bucket}" "tigris:${TIGRIS_BUCKET}/minio/${bucket}" "${LOG_DIR}/$(date +%Y%m%d-%H%M%S)-tigris-${bucket}.log"

  used=$(r2_size_bytes)
  remaining=$((R2_HARD_CAP_BYTES - used))
  echo "    R2 used: $((used / 1024 / 1024)) MiB / $((R2_HARD_CAP_BYTES / 1024 / 1024)) MiB  (remaining: $((remaining / 1024 / 1024)) MiB)"
  if [ ${remaining} -le 0 ]; then
    echo "    SKIP R2 ${bucket}: cap reached"
    continue
  fi
  if [ ${CONFIRM} -eq 1 ]; then
    log="${LOG_DIR}/$(date +%Y%m%d-%H%M%S)-r2-${bucket}.log"
    echo "==> minio:${bucket}  →  r2:${R2_BUCKET}/minio/${bucket}  (max-transfer=${remaining}B)"
    rclone copy "minio:${bucket}" "r2:${R2_BUCKET}/minio/${bucket}" \
      --transfers 4 --checkers 8 \
      --max-transfer "${remaining}" \
      --cutoff-mode hard \
      --log-file "${log}" --log-level INFO \
      --stats=30s 2>&1 | tail -3
  else
    echo "DRY-RUN: minio:${bucket}  →  r2:${R2_BUCKET}/minio/${bucket}  (max-transfer ${remaining}B)"
  fi
done

if [ ${CONFIRM} -eq 0 ]; then
  echo
  echo "Re-run with --confirm to execute. Logs: ${LOG_DIR}/"
fi

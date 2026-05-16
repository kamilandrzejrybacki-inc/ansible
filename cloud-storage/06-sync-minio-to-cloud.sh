#!/usr/bin/env bash
# Copy every MinIO bucket to each of the three cloud providers.
# Uses rclone copy (not sync) — never deletes remote files even if MinIO removes them.
# Pass --confirm to actually run. Without it, prints what would happen.
set -euo pipefail
source "${HOME}/.config/homelab-s3-remotes.env"

CONFIRM=0
[[ "${1:-}" == "--confirm" ]] && CONFIRM=1

LOG_DIR="${HOME}/.cache/rclone-sync"
mkdir -p "${LOG_DIR}"

for bucket in ${MINIO_BUCKETS}; do
  for remote in r2 tigris b2-s3; do
    case "${remote}" in
      r2)      dst="r2:${R2_BUCKET}/minio/${bucket}" ;;
      tigris)  dst="tigris:${TIGRIS_BUCKET}/minio/${bucket}" ;;
      b2-s3)   dst="b2-s3:${B2_BUCKET}/minio/${bucket}" ;;
    esac
    src="minio:${bucket}"
    log="${LOG_DIR}/$(date +%Y%m%d-%H%M%S)-${remote}-${bucket}.log"

    if [ ${CONFIRM} -eq 1 ]; then
      echo "==> ${src} -> ${dst}  (log: ${log})"
      rclone copy "${src}" "${dst}" \
        --transfers 4 --checkers 8 \
        --log-file "${log}" --log-level INFO \
        --stats=30s 2>&1 | tail -5
    else
      echo "DRY-RUN: rclone copy ${src} -> ${dst}"
    fi
  done
done

if [ ${CONFIRM} -eq 0 ]; then
  echo
  echo "Re-run with --confirm to execute. Logs go to ${LOG_DIR}/"
fi

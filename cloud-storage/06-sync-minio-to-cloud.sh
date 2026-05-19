#!/usr/bin/env bash
# Sync policy (free-tier aware):
#
#   HEAVY (velero — k8s cluster + PV chunks):
#     → B2 (10GB free, primary archive)
#     → Tigris (5GB free, secondary; prunes objects older than TIGRIS_MAX_AGE)
#
#   LIGHT (small durable data, kept on R2 — zero egress = best for restores):
#     → R2 (10GB free): k3s-snapshots, obsidian, backups
#
#   EPHEMERAL (regenerable, don't waste cloud quota):
#     loki, mimir, cache — stay in MinIO only
#
# Use rclone copy (never sync) so cloud retains versions even if MinIO drops them.
# Pass --confirm to execute. Default is dry-run.
set -euo pipefail
source "${HOME}/.config/homelab-s3-remotes.env"

CONFIRM=0
[[ "${1:-}" == "--confirm" ]] && CONFIRM=1

LOG_DIR="${HOME}/.cache/rclone-sync"
mkdir -p "${LOG_DIR}"

# Retention for Tigris (smallest cap at 5GB) — keep last 21 days of velero chunks.
TIGRIS_MAX_AGE="${TIGRIS_MAX_AGE:-21d}"

HEAVY_BUCKETS="velero"
LIGHT_BUCKETS="k3s-snapshots obsidian backups"

ts() { date +%Y%m%d-%H%M%S; }

run_copy() {
  local src="$1" dst="$2" log="$3"
  shift 3
  if [ ${CONFIRM} -eq 1 ]; then
    echo "==> ${src}  →  ${dst}"
    rclone copy "${src}" "${dst}" \
      --transfers 4 --checkers 8 \
      --log-file "${log}" --log-level INFO \
      --stats=30s "$@" 2>&1 | tail -3
  else
    echo "DRY-RUN: ${src}  →  ${dst} $*"
  fi
}

run_prune() {
  local target="$1" age="$2" log="$3"
  if [ ${CONFIRM} -eq 1 ]; then
    echo "==> prune ${target} (older than ${age})"
    rclone delete "${target}" \
      --min-age "${age}" \
      --log-file "${log}" --log-level INFO 2>&1 | tail -3
  else
    echo "DRY-RUN: prune ${target} older than ${age}"
  fi
}

echo "================================================"
echo "  HEAVY  →  B2 + Tigris  (velero)"
echo "================================================"
for bucket in ${HEAVY_BUCKETS}; do
  run_copy "minio:${bucket}" "b2-s3:${B2_BUCKET}/minio/${bucket}" \
    "${LOG_DIR}/$(ts)-b2-${bucket}.log"
  run_copy "minio:${bucket}" "tigris:${TIGRIS_BUCKET}/minio/${bucket}" \
    "${LOG_DIR}/$(ts)-tigris-${bucket}.log"
  run_prune "tigris:${TIGRIS_BUCKET}/minio/${bucket}" "${TIGRIS_MAX_AGE}" \
    "${LOG_DIR}/$(ts)-tigris-${bucket}-prune.log"
done

echo
echo "================================================"
echo "  LIGHT  →  R2  (k3s-snapshots, obsidian, backups)"
echo "================================================"
for bucket in ${LIGHT_BUCKETS}; do
  run_copy "minio:${bucket}" "r2:${R2_BUCKET}/minio/${bucket}" \
    "${LOG_DIR}/$(ts)-r2-${bucket}.log"
done

if [ ${CONFIRM} -eq 0 ]; then
  echo
  echo "Re-run with --confirm to execute. Logs: ${LOG_DIR}/"
fi

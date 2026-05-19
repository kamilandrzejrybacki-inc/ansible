#!/usr/bin/env bash
# k3s state backup — interim sqlite version until etcd migration (Phase 4 of network plan).
# Copies /var/lib/rancher/k3s/server/db/state.db to local snapshots dir, then
# uploads to MinIO via mc. Keeps local rotated copies.
set -euo pipefail

SNAPSHOT_DIR="/var/lib/rancher/k3s/snapshots"
DB_PATH="/var/lib/rancher/k3s/server/db/state.db"
DATE=$(date -u +%Y%m%d-%H%M%S)
SNAPSHOT_NAME="k3s-sqlite-${DATE}.db.gz"
KEEP_LOCAL=7

# MinIO target (in-cluster, reachable from host via NodePort)
MC_HOST="${MC_HOST:-http://192.168.0.107:30910}"
BUCKET="${BUCKET:-k3s-snapshots}"
ACCESS_KEY="${MC_ACCESS_KEY:?MC_ACCESS_KEY required}"
SECRET_KEY="${MC_SECRET_KEY:?MC_SECRET_KEY required}"

mkdir -p "$SNAPSHOT_DIR"

# Hot copy + gzip
sqlite3 "$DB_PATH" ".backup /tmp/k3s-state-${DATE}.db"
gzip -c "/tmp/k3s-state-${DATE}.db" > "${SNAPSHOT_DIR}/${SNAPSHOT_NAME}"
rm -f "/tmp/k3s-state-${DATE}.db"
echo "[backup] wrote ${SNAPSHOT_DIR}/${SNAPSHOT_NAME} ($(du -h ${SNAPSHOT_DIR}/${SNAPSHOT_NAME} | cut -f1))"

# Upload to MinIO (uses mc CLI; install with: curl -sLo /usr/local/bin/mc https://dl.min.io/client/mc/release/linux-amd64/mc)
if command -v mc >/dev/null 2>&1; then
  mc alias set homelab "$MC_HOST" "$ACCESS_KEY" "$SECRET_KEY" --api S3v4 >/dev/null
  mc mb --ignore-existing "homelab/${BUCKET}" >/dev/null
  mc cp "${SNAPSHOT_DIR}/${SNAPSHOT_NAME}" "homelab/${BUCKET}/${SNAPSHOT_NAME}"
  echo "[backup] uploaded to s3://${BUCKET}/${SNAPSHOT_NAME}"
else
  echo "[backup] WARN mc not installed — snapshot kept locally only"
fi

# Rotate local copies
cd "$SNAPSHOT_DIR"
ls -1t k3s-sqlite-*.db.gz 2>/dev/null | tail -n +$((KEEP_LOCAL + 1)) | xargs -r rm -v --
echo "[backup] done"

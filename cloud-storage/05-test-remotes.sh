#!/usr/bin/env bash
# Round-trip a tiny healthcheck object through each remote.
# Verifies write + read + delete on every provider before any sync runs.
set -euo pipefail
source "${HOME}/.config/homelab-s3-remotes.env"

tmpfile="$(mktemp)"
trap 'rm -f "${tmpfile}"' EXIT
echo "homelab s3 healthcheck $(date --iso-8601=seconds)" > "${tmpfile}"

declare -A REMOTES=(
  [r2]="${R2_BUCKET}"
  [tigris]="${TIGRIS_BUCKET}"
  [b2-s3]="${B2_BUCKET}"
  [minio]="backups"   # use existing minio bucket for the round trip
)

fail=0
for remote in "${!REMOTES[@]}"; do
  bucket="${REMOTES[$remote]}"
  path="healthcheck/$(hostname)-$(date +%s).txt"
  echo "==> ${remote}:${bucket}/${path}"
  rclone copyto "${tmpfile}" "${remote}:${bucket}/${path}" --quiet
  content=$(rclone cat "${remote}:${bucket}/${path}")
  rclone deletefile "${remote}:${bucket}/${path}" --quiet
  if [ -z "${content}" ]; then
    echo "    FAIL: empty read"
    fail=$((fail+1))
  else
    echo "    OK: $(echo "${content}" | wc -c) bytes round-tripped"
  fi
done

if [ ${fail} -ne 0 ]; then
  echo "${fail} remotes failed"
  exit 1
fi
echo "All remotes healthy."

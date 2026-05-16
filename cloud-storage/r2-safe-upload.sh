#!/usr/bin/env bash
# Pre-upload guard for R2. Wraps rclone copy/copyto.
# Refuses to start if SOURCE size + current R2 size would exceed cap.
# Use this instead of raw rclone for any R2 write.
#
# Usage: r2-safe-upload.sh <local-or-remote-src> <r2-dst>
#   r2-safe-upload.sh /home/me/data r2:kamil-homelab-r2-backup/data
#   r2-safe-upload.sh minio:obsidian r2:kamil-homelab-r2-backup/notes
set -euo pipefail
source "${HOME}/.config/homelab-s3-remotes.env"

SRC="${1:?source required}"
DST="${2:?destination required (must start with r2:)}"

if [[ "${DST}" != r2:* ]]; then
  echo "ERROR: destination must be r2:* (got ${DST})" >&2
  exit 1
fi

R2_HARD_CAP_BYTES=$((10 * 1024 * 1024 * 1024))   # 10 GiB

used=$(rclone size "r2:${R2_BUCKET}" --json | python3 -c "import sys,json; print(json.load(sys.stdin).get('bytes',0))")
src_size=$(rclone size "${SRC}" --json | python3 -c "import sys,json; print(json.load(sys.stdin).get('bytes',0))")
projected=$((used + src_size))

printf 'R2 current : %d MiB\n' $((used / 1024 / 1024))
printf 'Source size: %d MiB\n' $((src_size / 1024 / 1024))
printf 'Projected  : %d MiB\n' $((projected / 1024 / 1024))
printf 'Cap        : %d MiB\n' $((R2_HARD_CAP_BYTES / 1024 / 1024))

if [ ${projected} -gt ${R2_HARD_CAP_BYTES} ]; then
  msg="R2 upload ABORTED: ${SRC} -> ${DST} would push bucket to $((projected/1024/1024)) MiB (cap $((R2_HARD_CAP_BYTES/1024/1024)) MiB)"
  echo "ERROR: ${msg}" >&2
  logger -t r2-safe-upload -p user.err "${msg}"
  if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
      --data-urlencode "text=${msg}" >/dev/null
  fi
  exit 1
fi

# Add hard --max-transfer as a second line of defense (per-run quota).
remaining=$((R2_HARD_CAP_BYTES - used))
echo "==> rclone copy ${SRC} ${DST} --max-transfer ${remaining}"
exec rclone copy "${SRC}" "${DST}" \
  --max-transfer "${remaining}" \
  --cutoff-mode hard \
  --transfers 4 --checkers 8

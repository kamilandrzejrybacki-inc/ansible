#!/usr/bin/env bash
# R2 size watchdog. Run on a timer. Alerts via Telegram if cap exceeded.
# Cloudflare has no native hard cap — this is the only line of defense
# against runaway charges. Set R2_HARD_CAP_BYTES below as the threshold.
set -euo pipefail
source "${HOME}/.config/homelab-s3-remotes.env"

R2_HARD_CAP_BYTES=$((10 * 1024 * 1024 * 1024))    # 10 GiB
R2_WARN_BYTES=$((9 * 1024 * 1024 * 1024))         # 9 GiB

used=$(rclone size "r2:${R2_BUCKET}" --json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('bytes',0))")
used_mib=$((used / 1024 / 1024))
cap_mib=$((R2_HARD_CAP_BYTES / 1024 / 1024))

echo "R2 bucket ${R2_BUCKET}: ${used_mib} MiB / ${cap_mib} MiB"

alert() {
  local msg="$1"
  if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
      --data-urlencode "text=R2 watchdog: ${msg}" >/dev/null
  fi
  logger -t r2-cap-check "${msg}"
}

if [ ${used} -ge ${R2_HARD_CAP_BYTES} ]; then
  alert "CAP EXCEEDED: ${used_mib} MiB > ${cap_mib} MiB on ${R2_BUCKET}. Deleting oldest objects to enforce cap."
  # Hard enforcement: delete oldest objects until under cap.
  # Sorted by mod time ascending; cumulative byte sum; delete the prefix.
  rclone lsjson "r2:${R2_BUCKET}" --recursive 2>/dev/null | python3 -c "
import sys, json, subprocess
items = json.load(sys.stdin)
items.sort(key=lambda x: x.get('ModTime',''))
total = sum(i['Size'] for i in items)
cap = ${R2_HARD_CAP_BYTES}
for i in items:
    if total <= cap: break
    p = 'r2:${R2_BUCKET}/' + i['Path']
    subprocess.run(['rclone', 'deletefile', p], check=False)
    total -= i['Size']
    print(f'deleted {i[\"Path\"]} ({i[\"Size\"]} B)')
"
elif [ ${used} -ge ${R2_WARN_BYTES} ]; then
  alert "WARN: R2 ${used_mib} MiB / ${cap_mib} MiB (>90% of cap)"
fi

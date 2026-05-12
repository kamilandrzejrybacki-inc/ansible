#!/usr/bin/env bash
# TL-WR740N (stock firmware) DHCP reservation CLI.
#
# Limitations:
#   - Stock firmware only — no SSH, no API; this scrapes the web UI.
#   - HTTP-only (router has no HTTPS); creds + cookies cross LAN in clear.
#   - Tested on firmware 3.16+. Other firmwares may rename form fields.
#
# Usage:
#   tplink-dhcp.sh add <MAC> <IP>           # add or update reservation
#   tplink-dhcp.sh list                     # show current reservations
#   tplink-dhcp.sh remove <MAC>             # delete reservation
#
# Requires ~/.tplink-admin (chmod 600):
#   ROUTER_HOST=192.168.0.1
#   ROUTER_USER=admin
#   ROUTER_PASS=<admin password>
set -euo pipefail

CREDS="${TPLINK_CREDS_FILE:-$HOME/.tplink-admin}"
[ -r "$CREDS" ] || { echo "Missing $CREDS (chmod 600 with ROUTER_HOST/USER/PASS)"; exit 2; }
# shellcheck disable=SC1090
source "$CREDS"
: "${ROUTER_HOST:?}" "${ROUTER_USER:?}" "${ROUTER_PASS:?}"

# TL-WR740N encodes credentials as base64(user:pass) inside the URL.
TOKEN=$(printf '%s:%s' "$ROUTER_USER" "$ROUTER_PASS" | base64 -w0)
BASE="http://${TOKEN}@${ROUTER_HOST}"
REFERER="http://${ROUTER_HOST}/"

mac_dash() { printf '%s' "$1" | tr ':' '-' | tr 'a-f' 'A-F'; }

list() {
  curl -sS --max-time 8 -H "Referer: $REFERER" \
       "$BASE/userRpm/FixMapCfgRpm.htm" \
    | sed -n 's/.*new Array("\([0-9A-F-]*\)","\([0-9.]*\)",.*/\1  \2/p'
}

add() {
  local mac="$1" ip="$2"
  mac="$(mac_dash "$mac")"
  # Form layout: Mac, Ip, State(1=enable), Changed=0, SelIndex=0, Page=1, Save=Save
  curl -sS --max-time 8 -H "Referer: $REFERER" -G \
       --data-urlencode "Mac=$mac" \
       --data-urlencode "Ip=$ip" \
       --data-urlencode "State=1" \
       --data-urlencode "Changed=0" \
       --data-urlencode "SelIndex=0" \
       --data-urlencode "Page=1" \
       --data-urlencode "Save=Save" \
       "$BASE/userRpm/FixMapCfgRpm.htm" -o /dev/null
  echo "Added $mac → $ip"
}

remove() {
  local mac
  mac="$(mac_dash "$1")"
  # The Del button POSTs with index; we re-query the list to find which row.
  local idx
  idx=$(list | awk -v m="$mac" '$1==m {print NR-1; exit}')
  [ -n "$idx" ] || { echo "$mac not found"; return 1; }
  curl -sS --max-time 8 -H "Referer: $REFERER" -G \
       --data-urlencode "Del=$idx" \
       --data-urlencode "Page=1" \
       "$BASE/userRpm/FixMapCfgRpm.htm" -o /dev/null
  echo "Removed $mac"
}

cmd="${1:-}"; shift || true
case "$cmd" in
  list)            list ;;
  add)             add "$1" "$2" ;;
  remove|delete)   remove "$1" ;;
  *) echo "Usage: $0 {list|add <MAC> <IP>|remove <MAC>}"; exit 2 ;;
esac

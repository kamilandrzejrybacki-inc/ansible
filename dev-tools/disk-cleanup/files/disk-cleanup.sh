#!/usr/bin/env bash
# Daily disk maintenance for a dev/homelab host. Reclaimable-only, non-destructive:
# NEVER touches images-in-use, running/stopped containers, volumes, or any data.
# Managed by ansible (dev-tools/disk-cleanup). Edit there, not in place.
set -uo pipefail
export PATH="$HOME/.cargo/bin:/usr/local/bin:/usr/bin:/bin"
ts() { date -Is; }
avail() { df -P / | awk 'NR==2{print $4}'; }   # KB available on /
before=$(avail)
echo "[$(ts)] disk-cleanup start; avail=${before}K"

# 1) Rust build scratch: drop incremental caches everywhere (safe — keeps compiled deps),
#    and drop full target/ of projects untouched for >7 days (a rebuild regenerates them).
find "$HOME/Code" -type d -name incremental -path '*/target/*' -prune -exec rm -rf {} + 2>/dev/null
find "$HOME/Code" -maxdepth 2 -type d -name target -mtime +7 -prune -exec rm -rf {} + 2>/dev/null

# 2) Docker: reclaimable build cache + DANGLING (untagged) images only.
#    No `-a` (would remove wanted images), no container/volume prune (yours).
if command -v docker >/dev/null 2>&1; then
  docker builder prune -f  >/dev/null 2>&1 || true
  docker image prune -f    >/dev/null 2>&1 || true   # dangling only
fi

# 3) Logs + apt cache (best-effort; only if passwordless sudo is available, else skipped).
sudo -n journalctl --vacuum-time=7d >/dev/null 2>&1 || true
sudo -n apt-get clean              >/dev/null 2>&1 || true

after=$(avail)
freed=$(( (after - before) / 1024 ))
echo "[$(ts)] disk-cleanup done; avail=${after}K (freed ~${freed}MiB)"

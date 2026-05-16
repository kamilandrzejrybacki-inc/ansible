#!/usr/bin/env bash
# Install S3-compatible CLI tools needed for managing cloud remotes.
# Idempotent — safe to re-run. Uses apt + npm + pipx where appropriate.
set -euo pipefail

echo "==> apt deps"
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
  curl jq unzip ca-certificates \
  python3 python3-pip pipx \
  awscli rclone \
  nodejs npm >/dev/null

echo "==> Cloudflare Wrangler"
sudo npm install -g wrangler >/dev/null 2>&1 || true

echo "==> Tigris CLI"
sudo npm install -g @tigrisdata/cli >/dev/null 2>&1 || true

echo "==> Backblaze B2 CLI"
pipx install --force b2 >/dev/null 2>&1 || pip3 install --user --upgrade --break-system-packages b2 >/dev/null 2>&1 || true

echo
echo "Versions:"
aws --version 2>&1 | head -1
rclone version 2>&1 | head -1
wrangler --version 2>&1 | head -1 || echo "wrangler missing"
tigris --version 2>&1 | head -1 || echo "tigris missing"
b2 version 2>&1 | head -1 || echo "b2 missing"

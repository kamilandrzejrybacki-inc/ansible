#!/usr/bin/env bash
# Generate ~/.config/rclone/rclone.conf with one remote per provider + a
# 'cloud-free-pool' union (writes to all 3 clouds at once for redundancy).
set -euo pipefail
source "${HOME}/.config/homelab-s3-remotes.env"

mkdir -p "${HOME}/.config/rclone"
chmod 700 "${HOME}/.config/rclone"

cat > "${HOME}/.config/rclone/rclone.conf" <<EOF
[r2]
type = s3
provider = Cloudflare
access_key_id = ${R2_ACCESS_KEY_ID}
secret_access_key = ${R2_SECRET_ACCESS_KEY}
region = auto
endpoint = ${R2_ENDPOINT_URL}
acl = private

[tigris]
type = s3
provider = Other
access_key_id = ${TIGRIS_ACCESS_KEY_ID}
secret_access_key = ${TIGRIS_SECRET_ACCESS_KEY}
region = auto
endpoint = ${TIGRIS_ENDPOINT_URL}
acl = private

# Native B2 backend (master key works here; B2 S3 API rejects master keys).
# Switch to s3 type if/when you create a bucket-scoped application key.
[b2-s3]
type = b2
account = ${B2_APPLICATION_KEY_ID}
key = ${B2_APPLICATION_KEY}
hard_delete = false

[minio]
type = s3
provider = Minio
access_key_id = ${MINIO_ACCESS_KEY_ID}
secret_access_key = ${MINIO_SECRET_ACCESS_KEY}
endpoint = ${MINIO_ENDPOINT}
acl = private

# Union remote: writes land on all 3 clouds for redundancy.
# Reads use first-found semantics (cheapest egress provider first).
[cloud-free-pool]
type = union
upstreams = r2:${R2_BUCKET} tigris:${TIGRIS_BUCKET} b2-s3:${B2_BUCKET}
action_policy = epall
create_policy = mfs
search_policy = ff
EOF

chmod 600 "${HOME}/.config/rclone/rclone.conf"
echo "rclone remotes: r2 tigris b2-s3 minio cloud-free-pool"

#!/usr/bin/env bash
# Write ~/.aws/credentials and ~/.aws/config with one profile per provider.
set -euo pipefail
source "${HOME}/.config/homelab-s3-remotes.env"

mkdir -p "${HOME}/.aws"
chmod 700 "${HOME}/.aws"

cat > "${HOME}/.aws/credentials" <<EOF
[r2]
aws_access_key_id = ${R2_ACCESS_KEY_ID}
aws_secret_access_key = ${R2_SECRET_ACCESS_KEY}

[tigris]
aws_access_key_id = ${TIGRIS_ACCESS_KEY_ID}
aws_secret_access_key = ${TIGRIS_SECRET_ACCESS_KEY}

[b2-s3]
aws_access_key_id = ${B2_APPLICATION_KEY_ID}
aws_secret_access_key = ${B2_APPLICATION_KEY}

[minio]
aws_access_key_id = ${MINIO_ACCESS_KEY_ID}
aws_secret_access_key = ${MINIO_SECRET_ACCESS_KEY}
EOF

cat > "${HOME}/.aws/config" <<EOF
[profile r2]
region = auto
endpoint_url = ${R2_ENDPOINT_URL}
output = json

[profile tigris]
region = auto
endpoint_url = ${TIGRIS_ENDPOINT_URL}
output = json

[profile b2-s3]
region = us-east-1
endpoint_url = ${B2_S3_ENDPOINT}
output = json

[profile minio]
region = us-east-1
endpoint_url = ${MINIO_ENDPOINT}
output = json
EOF

chmod 600 "${HOME}/.aws/credentials" "${HOME}/.aws/config"
echo "AWS CLI profiles written: r2 tigris b2-s3 minio"

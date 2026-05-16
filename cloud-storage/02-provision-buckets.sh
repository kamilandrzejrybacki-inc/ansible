#!/usr/bin/env bash
# Create one private backup bucket per provider via AWS S3 API.
# All three providers (R2 / Tigris / B2) are S3-compatible — no provider-native
# CLI needed once endpoint+credentials are known.
set -euo pipefail
source "${HOME}/.config/homelab-s3-remotes.env"

create_bucket() {
  local name="$1" bucket="$2" ak="$3" sk="$4" endpoint="$5"
  echo "==> ${name}: ${bucket} @ ${endpoint}"
  if AWS_ACCESS_KEY_ID="${ak}" AWS_SECRET_ACCESS_KEY="${sk}" \
     aws s3api list-buckets --endpoint-url "${endpoint}" --region auto 2>&1 | grep -q "\"${bucket}\""; then
    echo "    exists, skipping"
  else
    AWS_ACCESS_KEY_ID="${ak}" AWS_SECRET_ACCESS_KEY="${sk}" \
      aws s3api create-bucket --bucket "${bucket}" --endpoint-url "${endpoint}" --region auto
  fi
}

create_bucket "Cloudflare R2" "${R2_BUCKET}"      "${R2_ACCESS_KEY_ID}"      "${R2_SECRET_ACCESS_KEY}"      "${R2_ENDPOINT_URL}"
create_bucket "Tigris"        "${TIGRIS_BUCKET}"  "${TIGRIS_ACCESS_KEY_ID}"  "${TIGRIS_SECRET_ACCESS_KEY}"  "${TIGRIS_ENDPOINT_URL}"

# B2 master keys cannot use S3 API for bucket creation — only B2 native API.
# Once bucket exists, all subsequent operations (sync, copy) use S3 API fine.
echo "==> Backblaze B2: ${B2_BUCKET}"
b2 account authorize "${B2_APPLICATION_KEY_ID}" "${B2_APPLICATION_KEY}" >/dev/null
if b2 bucket list 2>&1 | grep -q "${B2_BUCKET}"; then
  echo "    exists, skipping"
else
  b2 bucket create "${B2_BUCKET}" allPrivate
fi

echo
echo "All buckets provisioned."

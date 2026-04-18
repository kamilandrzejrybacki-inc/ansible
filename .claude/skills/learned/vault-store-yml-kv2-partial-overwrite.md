---
name: vault-store-yml-kv2-partial-overwrite
description: "store.yml uses POST which replaces entire KV v2 secret — partial vault_secrets_data silently destroys other keys"
user-invocable: false
origin: auto-extracted
---

# Vault store.yml POST Replaces Entire KV v2 Secret

**Extracted:** 2026-04-10
**Context:** Any playbook that calls common/vault-integration/store.yml with only a subset of keys

## Problem

`common/vault-integration/store.yml` uses `method: POST` to write KV v2:

```yaml
- name: Write secrets to Vault KV
  ansible.builtin.uri:
    url: "{{ _vault_addr }}/v1/{{ _vault_kv_mount }}/data/homelab/{{ vault_service_name }}"
    method: POST
    body:
      data: "{{ _vault_store_data }}"
```

KV v2 POST creates a **new version** containing **only the provided keys**. Any keys that existed in the previous version but are absent from `vault_secrets_data` are silently gone from the current version.

In the n8n setup playbook, `Store n8n secrets to Vault` only writes `owner_email` + `owner_password`. Each run destroyed all API tokens (groq_api_key, nvidia_api_key, telegram_bot_token, lw_notifier_token, etc.) that had been manually added to `secret/homelab/n8n`.

## Solution

**Option A — Always write ALL keys** (safest, no store.yml change needed):
Include every key in `vault_secrets_data`, even if the playbook doesn't manage them:

```yaml
vault_secrets_data:
  owner_email: "{{ n8n_owner_email }}"
  owner_password: "{{ n8n_owner_password }}"
  groq_api_key: "{{ _existing_groq | default('') }}"  # preserve existing
```

**Option B — Use PATCH to merge** (fix store.yml):
Change `method: POST` to PATCH and set the content type:

```yaml
- name: Write secrets to Vault KV
  ansible.builtin.uri:
    url: "{{ _vault_addr }}/v1/{{ _vault_kv_mount }}/data/homelab/{{ vault_service_name }}"
    method: PATCH
    headers:
      X-Vault-Token: "{{ _vault_token }}"
      Content-Type: "application/merge-patch+json"
    body_format: json
    body:
      data: "{{ _vault_store_data }}"
    status_code: [200, 204]
```

**Option C — Emergency restore** (recovery after overwrite):
KV v2 retains old versions. Read a pre-overwrite version and POST it back with all keys:

```bash
# Find the last good version
curl -sf -H "X-Vault-Token: $TOKEN" \
  http://127.0.0.1:8200/v1/secret/metadata/homelab/n8n | python3 -c "
import json,sys; d=json.load(sys.stdin)
for v,i in d['data']['versions'].items(): print(v, i['created_time'])"

# Read it
curl -sf -H "X-Vault-Token: $TOKEN" \
  "http://127.0.0.1:8200/v1/secret/data/homelab/n8n?version=<N>"

# Restore by POST-ing all keys together
curl -sf -X POST \
  -H "X-Vault-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  http://127.0.0.1:8200/v1/secret/data/homelab/n8n \
  -d '{"data": { ...all keys... }}'
```

## When to Use

- Before adding any new manually-managed key to a Vault path that `store.yml` also writes to
- When diagnosing "where did my API key go?" after a playbook run
- When modifying `store.yml` — prefer PATCH over POST

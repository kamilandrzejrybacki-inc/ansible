---
name: authelia-reprovision-rotates-oidc-client-secret
description: "Re-running the Authelia role rotates OIDC client secrets + may change redirect_uri — breaks clients (nexterm/Vault) that store the secret in their own DB"
user-invocable: false
origin: auto-extracted
---

# Re-running the Authelia Role Breaks Downstream OIDC Clients

**Extracted:** 2026-06-27
**Context:** Homelab edge Authelia (docker, /opt/homelab/authelia) provisioned by ansible `security/secure-homelab-access/roles/authelia`. OIDC clients (nexterm, Vault, n8n) each store their own copy of the client secret + their own redirect_uri.

## Problem

Two independent failures, both triggered by re-running the Authelia role:

### 1. Client secret rotation → "client secret did not match"
The role regenerates each OIDC client's secret (new plaintext + new bcrypt hash in Authelia's config) on re-run. The downstream client (nexterm) keeps the OLD secret in its own DB. Login then fails at the token exchange, NOT at redirect:

Authelia log: `Access Request failed with error: ... The provided client secret did not match the registered client secret. method=POST path=/api/oidc/token`
Browser: `Failed to process OIDC login: server responded with an error in the response body`

### 2. redirect_uri must match what the CLIENT sends, not the post-rewrite path
nexterm sends `redirect_uri=.../api/oidc/callback`. A Traefik middleware (`nexterm-oidc-path-fix`) rewrites it to `/api/auth/oidc/callback` before it reaches the app. Authelia validates the redirect_uri the BROWSER sent (pre-rewrite). If Authelia only registers the rewritten path → `invalid_request` redirect_uri mismatch.
Fix: register BOTH paths in the client's `redirect_uris`.

## Solution

**Redirect URI (in the role template + live config):**
List every URI the client actually sends:
```yaml
redirect_uris:
  - 'https://nexterm.<domain>/api/oidc/callback'        # what nexterm sends
  - 'https://nexterm.<domain>/api/auth/oidc/callback'   # post-Traefik-rewrite
```
Live edit: `/opt/homelab/authelia/config/configuration.yml` → `authelia validate-config` → restart container.

**Re-sync the rotated secret into the client.** nexterm stores it AES-256-GCM-encrypted in its SQLite DB (`/app/data/nexterm.db`, table `oidc_providers`): columns `clientSecret` / `clientSecretIV` / `clientSecretAuthTag`, all hex. Key = `bytes.fromhex(encryption_key)` from k8s secret `nexterm-secrets` (32 bytes); IV 16 bytes; GCM tag 16 bytes.

Re-encrypt the NEW Authelia plaintext with that scheme and UPDATE the row, or (simpler) paste the new plaintext into nexterm's admin UI OIDC provider form. Then `kubectl rollout restart deployment/nexterm -n nexterm`.

Verify by decrypting the row back to the expected plaintext before declaring fixed.

## When to Use
- Any homelab OIDC login (nexterm, Vault, n8n) breaks right after running the Authelia ansible role.
- "client secret did not match" at `/api/oidc/token` → it's secret rotation, re-sync the client.
- `invalid_request` redirect_uri mismatch → register the pre-rewrite path the client sends.
- Long-term fix: make the role NOT regenerate existing client secrets on re-run (pin from Vault), so downstream DBs stay valid.

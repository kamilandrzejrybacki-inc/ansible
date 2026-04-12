# decap-cms

Self-hosted Decap CMS for kamilrybacki.github.io. Provides a browser-based Markdown editor
at `https://kamilrybacki.github.io/admin/` backed by a GitHub OAuth proxy on `lw-main`.

## Prerequisites

- WireGuard VPN connected (lw-main is VPN-gated)
- Vault running and `~/.vault-ansible.yml` configured
- Blog repo cloned locally (for `make admin`)

## Setup

### 1. Create GitHub OAuth App

1. Go to: https://github.com/settings/developers → OAuth Apps → New OAuth App
2. Set:
   - **Application name:** Homelab Blog CMS
   - **Homepage URL:** `https://kamilrybacki.github.io`
   - **Authorization callback URL:** `http://cms-auth.<your-domain>/callback`
3. Copy the **Client ID** and generate a **Client Secret**

### 2. Store secrets in Vault

```
vault kv put secret/homelab/decap-cms \
  github_client_id="<client-id>" \
  github_client_secret="<client-secret>" \
  cms_auth_origin="https://kamilrybacki.github.io"
```

### 3. Clone blog repo (if not already)

```
git clone https://github.com/kamilrybacki/kamilrybacki.github.io /opt/data/kamilrybacki.github.io
```

### 4. Deploy

```
cd home-services/decap-cms
make deploy
```

### 5. Push admin files to GitHub

The `make deploy` (or `make admin`) renders admin files into the blog repo.
Commit and push them manually:

```
cd /opt/data/kamilrybacki.github.io
git add admin/
git commit -m "feat: add Decap CMS admin panel"
git push
```

GitHub Pages rebuilds automatically. Admin panel live at:
`https://kamilrybacki.github.io/admin/`

### 6. Verify deployment

```
make verify
```

## Post-Deploy Checklist

- [ ] Visit `https://kamilrybacki.github.io/admin/` — CMS login screen appears
- [ ] Click "Login with GitHub" — redirects to GitHub (NOT to Authelia)
- [ ] After GitHub OAuth consent — Decap CMS loads with article list
- [ ] Create a test article, click "Publish" — commit appears in GitHub repo within 30s
- [ ] Check `src/content/articles/` in GitHub — new file present with correct frontmatter

## Operations

| Command | Effect |
|---------|--------|
| `make deploy` | Full initial deploy |
| `make update` | Re-pull image + recreate container |
| `make rollback` | Revert to previous image digest |
| `make verify` | Health checks only (no changes) |
| `make admin` | Re-render admin files into blog repo |
| `make caddy` | Re-render Caddy vhost only |
| `make lint` | Run ansible-lint |

## Runbook

**Container not starting:**

```
docker logs decap-cms-oauth
# Common: missing env var → check vault kv get secret/homelab/decap-cms
```

**OAuth login redirects to Authelia instead of GitHub:**
- The Caddyfile block for `cms-auth.<domain>` must NOT contain `import authelia`
- Check: `grep -A10 "DECAP_CMS_AUTH" /opt/homelab/caddy/Caddyfile`

**Caddy returns 502:**

```
docker inspect decap-cms-oauth --format '{{.State.Running}}'
# If false: make deploy
# If true: check port binding: docker port decap-cms-oauth
```

**`make rollback` fails with "file not found":**
The state file is created on first deploy. If it is missing, pull a known-good image tag manually:

```
docker pull vencax/netlify-cms-github-oauth-provider:<tag>
# Then set oauth_proxy_image_tag in defaults/main.yml and run make update
```

**Admin files not showing in CMS:**
- Confirm `admin/config.yml` and `admin/index.html` are committed and pushed to GitHub
- GitHub Pages rebuild takes ~60s after push

## Required Vault Variables

| Path | Key | Description |
|------|-----|-------------|
| `secret/homelab/decap-cms` | `github_client_id` | GitHub OAuth App client ID |
| `secret/homelab/decap-cms` | `github_client_secret` | GitHub OAuth App client secret |
| `secret/homelab/decap-cms` | `cms_auth_origin` | CMS origin, e.g. `https://kamilrybacki.github.io` |

## Architecture Notes

- OAuth proxy port is bound to `lw-main`'s host IP only — not reachable without VPN
- Caddy vhost has no `import authelia` (by design — this service IS the auth provider)
- Admin panel is served by GitHub Pages — zero infra for the frontend
- Once logged in, Decap CMS talks directly to the GitHub API — proxy is idle
- Rollback uses image digest saved before deploy (`/opt/decap-cms/current_image_digest`)

# Decap CMS Deploy — Design Spec

**Date:** 2026-04-12
**Status:** Approved
**Target repo:** `ansible` → `home-services/decap-cms/`

---

## Overview

Deploy a self-hosted blog editor for `kamilrybacki.github.io` (Eleventy, GitHub Pages).
The editor is Decap CMS — a browser-based Markdown editor backed by the GitHub API.
The only hosted component is a lightweight OAuth proxy that handles GitHub token exchange.

**Access model:**
- Admin panel: `https://kamilrybacki.github.io/admin/` (static, served by GitHub Pages)
- OAuth proxy: `https://cms-auth.{{ domain }}` on `lw-main`, VPN-gated, Authelia bypassed
- Content operations: browser → GitHub API directly (proxy not in content path)

---

## Architecture

```
Browser (on WireGuard VPN)
  │
  ├─► kamilrybacki.github.io/admin/      (GitHub Pages — static Decap CMS SPA)
  │       │
  │       ├─► GitHub API                 (read/write articles directly)
  │       │
  │       └─► cms-auth.{{ domain }}      (only during login)
  │               └─► Caddy (lw-main, no forward_auth)
  │                       └─► oauth-proxy container :3000
  │                               └─► GitHub OAuth API
  │
  └─► OAuth flow (login only):
        1. Browser → cms-auth.{{ domain }}/auth
        2. Redirect → GitHub OAuth consent
        3. GitHub → cms-auth.{{ domain }}/callback (browser follows, VPN required)
        4. Proxy exchanges code → token → postMessage to Decap CMS tab
        5. Decap CMS uses token for all subsequent GitHub API calls
```

**Key properties:**
- No database, no persistent storage on the proxy
- Proxy is stateless — restart anytime without data loss
- WireGuard VPN is the security perimeter; Authelia bypassed for this service (it is itself an auth service)
- GitHub Pages serves the admin UI — zero infra for the frontend

---

## Playbook Structure

`playbook.yml` contains two plays:

```yaml
- name: Deploy OAuth proxy
  hosts: lw-main
  roles:
    - role: oauth-proxy
      tags: [oauth-proxy, deploy, update, rollback, verify, caddy]

- name: Deploy Decap admin files
  hosts: localhost
  connection: local
  roles:
    - role: decap-admin
      tags: [decap-admin, deploy]
```

The `decap-admin` play runs on `localhost` (the Ansible controller) because it writes files into a locally cloned blog repo. The operator commits and pushes the result to GitHub.

---

## Ansible Role Layout

```
ansible/home-services/decap-cms/
├── playbook.yml
├── Makefile
├── README.md
└── roles/
    ├── oauth-proxy/
    │   ├── defaults/main.yml
    │   ├── vars/main.yml
    │   ├── tasks/
    │   │   ├── main.yml
    │   │   ├── deploy.yml
    │   │   ├── caddy.yml
    │   │   └── verify.yml
    │   └── templates/
    │       ├── docker-compose.yml.j2
    │       └── caddy-cms-auth.j2
    └── decap-admin/
        ├── defaults/main.yml
        ├── tasks/
        │   ├── main.yml
        │   └── deploy.yml
        └── templates/
            ├── index.html.j2
            └── config.yml.j2
```

### Role: `oauth-proxy`

**Target host:** `lw-main`

**What it does:**
- Reads `github_client_id`, `github_client_secret`, `cms_auth_origin` from Vault (`secret/homelab/decap-cms`)
- Renders `docker-compose.yml.j2` → `/opt/decap-cms/docker-compose.yml`
- Runs `docker compose up -d` (idempotent via `community.docker.docker_compose_v2`)
- Renders Caddy vhost block → drops file into Caddy include dir, reloads Caddy
- Runs verify tasks

**Caddy vhost (no `forward_auth`):**
```caddy
{{ subdomain_cms_auth }}.{{ domain }} {
  import proxy_headers
  {% if cloudflare_api_token and not cf_tunnel %}
  import cf_tls
  {% endif %}
  reverse_proxy localhost:3000
}
```

**Docker Compose:**
```yaml
services:
  oauth-proxy:
    image: vencax/netlify-cms-github-oauth-provider:{{ oauth_proxy_image_tag }}
    restart: unless-stopped
    ports:
      - "127.0.0.1:3000:3000"
    environment:
      GITHUB_CLIENT_ID: "{{ github_client_id }}"
      GITHUB_CLIENT_SECRET: "{{ github_client_secret }}"
      ORIGIN: "{{ cms_auth_origin }}"
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:3000/"]
      interval: 30s
      timeout: 5s
      retries: 3
```

**Vault vars** (read via HTTP API, same pattern as existing homelab Vault integration):

| Var | Vault path | Description |
|-----|-----------|-------------|
| `github_client_id` | `secret/homelab/decap-cms` | GitHub OAuth App client ID |
| `github_client_secret` | `secret/homelab/decap-cms` | GitHub OAuth App client secret |
| `cms_auth_origin` | `secret/homelab/decap-cms` | Allowed origin (e.g. `https://kamilrybacki.github.io`) |

**defaults/main.yml:**
```yaml
oauth_proxy_image_tag: "latest"   # pin to a digest in production
oauth_proxy_port: 3000
subdomain_cms_auth: cms-auth
cms_auth_compose_dir: /opt/decap-cms
```

### Role: `decap-admin`

**Target:** blog repo on the Ansible controller (or a checked-out path)

**What it does:**
- Renders `/admin/index.html` (loads Decap CMS from CDN, injects preview stylesheet link)
- Renders `/admin/config.yml` (GitHub backend config, articles collection)
- Tasks are tagged `decap-admin` so they can run independently

**Prerequisite:** Blog repo must be cloned to `blog_repo_path` before running the `decap-admin` role. The role writes files into the working tree; the operator is responsible for committing and pushing after.

**defaults/main.yml:**
```yaml
blog_repo_path: "/opt/data/kamilrybacki.github.io"
decap_cms_version: "3.3.3"       # pinned CDN version
blog_base_url: "https://kamilrybacki.github.io"
cms_branch: main
editorial_workflow: false          # direct-to-main
```

---

## Decap CMS Configuration

**`/admin/config.yml`:**
```yaml
backend:
  name: github
  repo: kamilrybacki/kamilrybacki.github.io
  branch: main
  base_url: https://cms-auth.{{ domain }}

publish_mode: simple

media_folder: src/assets/uploads

collections:
  - name: articles
    label: Articles
    folder: src/content/articles
    create: true
    slug: "{{slug}}"   # NOTE: Jinja2 template must wrap this in {% raw %}…{% endraw %} to prevent Ansible resolving it
    fields:
      - { name: title,       label: Title,       widget: string }
      - { name: date,        label: Date,         widget: datetime }
      - { name: description, label: Description,  widget: text }
      - { name: category,    label: Category,     widget: string }
      - { name: tags,        label: Tags,         widget: list }
      - { name: draft,       label: Draft,        widget: boolean, default: true }
      - { name: body,        label: Body,         widget: markdown }
```

**`/admin/index.html`:**
- Loads Decap CMS from `https://unpkg.com/decap-cms@{{ decap_cms_version }}/dist/decap-cms.js` (pinned version)
- Injects `<link rel="stylesheet" href="{{ blog_base_url }}/css/main.css">` for preview styling

---

## Ops Tooling

### Makefile

```makefile
deploy:
	ansible-playbook playbook.yml --tags deploy,caddy

update:
	ansible-playbook playbook.yml --tags update

rollback:
	ansible-playbook playbook.yml --tags rollback

verify:
	ansible-playbook playbook.yml --tags verify
```

### Ansible Tags

| Tag | Effect |
|-----|--------|
| `deploy` | Full initial deploy (Docker Compose up + Caddy vhost) |
| `update` | Re-pull image, recreate container |
| `rollback` | Stop container, set previous image tag, restart |
| `verify` | Health checks only (no changes) |
| `caddy` | Caddy vhost tasks only |
| `oauth-proxy` | All oauth-proxy role tasks |
| `decap-admin` | All decap-admin role tasks |

### Rollback Strategy

Rollback is image-tag based: `defaults/main.yml` stores `oauth_proxy_image_tag`. To roll back:
1. Set `oauth_proxy_image_tag` to previous known-good tag (or digest)
2. Run `make rollback`

For blog admin files, rollback = `git revert` in the blog repo (files are tracked in git).

---

## Verification Tasks (`verify.yml`)

```yaml
- name: Check oauth-proxy container is running
  community.docker.docker_container_info:
    name: oauth-proxy
  register: container_info
  failed_when: not container_info.container.State.Running

- name: Check oauth-proxy responds on localhost
  uri:
    url: "http://localhost:3000/"
    status_code: 200

- name: Check Caddy is serving the CMS auth vhost
  uri:
    url: "https://cms-auth.{{ domain }}/callback"
    status_code: [200, 302, 400]   # any non-502 means proxy is reachable
    validate_certs: true
```

---

## Security Notes

- Port `3000` bound to `127.0.0.1` only — not exposed on the network interface
- Caddy is the only entry point; TLS terminated at Caddy
- No `forward_auth` directive on this vhost (Authelia bypassed by design — proxy is itself an auth service)
- WireGuard VPN gates access to `lw-main` — the callback URL is not publicly reachable
- All secrets from Vault; never in playbook vars or git

---

## README Sections (to be written)

1. **GitHub OAuth App setup** — create at github.com/settings/developers, callback URL: `https://cms-auth.{{ domain }}/callback`, scope: `repo`
2. **Required Vault vars** — `vault kv put secret/homelab/decap-cms github_client_id=... github_client_secret=... cms_auth_origin=https://kamilrybacki.github.io`
3. **DNS** — `cms-auth.{{ domain }}` must resolve to `lw-main` IP (same as other services)
4. **Post-deploy checklist:**
   - [ ] Visit `https://kamilrybacki.github.io/admin/` → login button visible
   - [ ] Click login → GitHub OAuth consent page appears (not Authelia)
   - [ ] After login → article list loads
   - [ ] Create a test article → commit appears in GitHub repo
5. **Runbook:**
   - Container not starting: check `docker logs oauth-proxy`, verify Vault vars are set
   - OAuth callback 404: verify Caddy vhost rendered and reloaded (`caddy reload`)
   - Caddy 502: container not running, run `make verify`
   - Login redirect to Authelia instead of GitHub: Authelia bypass rule not applied

---

## Open Questions / Defaults Chosen

| Decision | Choice | Reason |
|----------|--------|--------|
| Image tag pinning | `latest` as default, document pinning to digest | Simplest start; operator pins when stable |
| Blog repo path on controller | `/opt/data/kamilrybacki.github.io` | Matches stated path; configurable via `blog_repo_path` |
| Decap CMS version | Pinned in `defaults/main.yml` | Prevents surprise CDN upgrades breaking the editor |
| `media_folder` | `src/assets/uploads` | Safe default; verify Eleventy is configured to serve this path before finalising |
| Docker image name | `vencax/netlify-cms-github-oauth-provider` | Verify image still exists and is maintained on Docker Hub before implementation |

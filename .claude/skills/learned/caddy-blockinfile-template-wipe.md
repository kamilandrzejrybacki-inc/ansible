---
name: caddy-blockinfile-template-wipe
description: "Ansible Caddy template rewrite wipes blockinfile-injected routes — consolidate all routes in the template"
user-invocable: false
origin: auto-extracted
---

# Caddy Template Rewrite Wipes Dynamically-Injected Routes

**Extracted:** 2026-03-26
**Context:** Homelab Caddy reverse proxy managed by both a Jinja2 template (secure-homelab-access) and blockinfile injections (individual service playbooks)

## Problem

The main Caddyfile is managed by a Jinja2 template in `security/secure-homelab-access/roles/caddy/templates/Caddyfile.j2`. Individual service playbooks (Grafana, Netbox, n8n, Vault, Nexterm, Paperless, Stirling-PDF, Filebrowser) inject their routes via `ansible.builtin.blockinfile` into the deployed `/opt/homelab/caddy/Caddyfile`.

When the Caddy role is redeployed (e.g. `--tags caddy`), the Jinja2 template **overwrites the entire Caddyfile**, wiping all blockinfile-injected routes. Since Cloudflare Tunnel routes `*.domain` to Caddy on localhost:80, any subdomain without a matching server block returns an empty 200 response (white page) or falls through incorrectly.

This caused a full outage of 8 services: Grafana, Netbox, n8n, Vault, Nexterm, Paperless, Stirling-PDF, Filebrowser.

## Solution

**All** service reverse proxy routes must live in the central Caddyfile template (`Caddyfile.j2`), not injected via blockinfile. The template uses default values for ports/IPs so it works without extra vars:

```jinja2
# n8n (on lw-s1) — no Authelia, n8n has own auth
{{ _scheme }}{{ subdomain_n8n }}.{{ domain }} {
    import rate_limit
    import proxy_headers
    reverse_proxy http://{{ n8n_host_ip | default('192.168.0.108') }}:{{ n8n_port | default(5678) }}
}
```

Key upstream patterns:
- **Docker containers on lw-main**: use `container_name:port` or `{{ docker_gateway_ip }}:port`
- **Services on lw-s1** (192.168.0.108): use LAN IP + port
- **Services on lw-nas** (10.0.1.2): use NAS IP + port
- **K8s services on lw-c1** (192.168.0.107): use LAN IP + NodePort
- **Services with own OIDC** (Vault, Nexterm, n8n): do NOT add `import authelia`

## When to Use

- Before deploying any Caddy-related Ansible tags
- When adding a new service that needs reverse proxy access
- When any service shows a white page / empty 200 through Cloudflare

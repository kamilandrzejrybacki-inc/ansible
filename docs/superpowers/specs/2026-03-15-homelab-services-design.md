# Homelab Services — Pi-hole, Uptime Kuma, Vaultwarden, Paperless-ngx

**Date:** 2026-03-15
**Status:** Approved

## Overview

Add 4 new homelab service playbooks to the Ansible repository:

1. **Pi-hole** — integrated as a new role in `security/secure-homelab-access`
2. **Uptime Kuma** — standalone playbook at `monitoring/kuma-setup/`
3. **Vaultwarden** — standalone playbook at `security/vaultwarden-setup/`
4. **Paperless-ngx** — standalone playbook at `files/paperless-setup/`

## Design Decisions

- Pi-hole is integrated into the existing secure-homelab-access playbook because it is tightly coupled to WireGuard DNS and benefits from Caddy + Authelia protection.
- The other 3 services are independent playbooks that can be deployed to any host.
- All containers bind to `127.0.0.1` (localhost only) for security.
- All container images are pinned to specific versions (no `:latest`, no floating major tags).
- All secret-handling tasks use `no_log: true`.
- All playbooks use interactive `vars_prompt` setup wizards consistent with existing playbooks.
- All standalone playbooks follow the two-play pattern (Play 1 on localhost gathers prompts and builds dynamic inventory via `add_host`, Play 2 deploys to the remote host) — matching the `n8n-setup` pattern.

## 1. Pi-hole — `security/secure-homelab-access`

### New role: `pihole`

**Container:** `pihole/pihole:2024.07.0`

**Group vars additions:**
```yaml
# -- Pi-hole (DNS) -----------------------------------------------------------
pihole_container_name: "pihole"
pihole_data_dir: "{{ docker_data_dir }}/pihole"
pihole_web_port: 8053
pihole_dns_ip: "172.20.0.10"  # Static IP on homelab-net for WireGuard DNS
subdomain_pihole: "pihole"
pihole_health_check_retries: 12
pihole_health_check_delay: 5
```

**WireGuard DNS update:**
```yaml
# Changes from:
wireguard_dns: "1.1.1.1,1.0.0.1"
# To:
wireguard_dns: "{{ pihole_dns_ip }}"
```

**Setup wizard:** Updates all existing prompts from `[X/8]` to `[X/9]`. Adds prompt `[9/9]` for the Pi-hole admin password (private, confirmed).

**Role ordering in setup.yml:** Pi-hole must come **after** `docker` but **before** `wireguard` in the roles list, since WireGuard's DNS config references Pi-hole's container IP:

```yaml
roles:
  - role: firewall
  - role: fail2ban
  - role: docker
  - role: pihole        # NEW — must be before wireguard
  - role: wireguard
  - role: authelia
  - role: caddy
  - role: cockpit
  - role: homepage
```

**Tags:** `[pihole, dns]`

**systemd-resolved conflict:** On Ubuntu/Debian, `systemd-resolved` listens on port 53. The Pi-hole role must handle this by:
1. Disabling the `systemd-resolved` stub listener (`DNSStubListener=no` in `/etc/systemd/resolved.conf`)
2. Restarting `systemd-resolved`
3. Updating `/etc/resolv.conf` to point to `127.0.0.1` (Pi-hole will handle upstream DNS)

**Firewall:** Port 53 (TCP+UDP) added to `firewall_allowed_udp_ports` and `firewall_allowed_tcp_ports` — restricted to the VPN subnet only via ufw rules.

**Integration with existing roles:**

- **WireGuard**: `wireguard_dns` set to `{{ pihole_dns_ip }}` (static IP `172.20.0.10` on `homelab-net`). Pi-hole container is assigned this IP via Docker network configuration.
- **Caddy**: Adds `{{ subdomain_pihole }}.{{ domain }}` site block with `import authelia` and `reverse_proxy` to `{{ pihole_container_name }}:{{ pihole_web_port }}`.
- **Homepage**: Adds Pi-hole entry to the Infrastructure section in `services.yaml.j2`.
- **Authelia**: No changes — the existing `*.{{ domain }}` wildcard two_factor rule covers Pi-hole.
- **Deployment summary + post_tasks**: Both debug messages updated to include the Pi-hole subdomain.

**Role tasks:**
1. Disable `systemd-resolved` stub listener (with handler to restart)
2. Create data directories (`{{ pihole_data_dir }}/etc-pihole`, `{{ pihole_data_dir }}/etc-dnsmasq.d`)
3. Deploy Pi-hole container on `homelab-net` with static IP `{{ pihole_dns_ip }}`:
   - `WEBPASSWORD` set from prompted password (`no_log: true`)
   - DNS ports `53:53/tcp` and `53:53/udp` bound on the host
   - Web UI on internal port only (not published — accessed via Caddy)
   - Volumes for persistent config
4. Health check: wait for Pi-hole API to respond (retries/delay from defaults)

**Handlers:** `handlers/main.yml` with restart handler for `systemd-resolved`.

**Dependencies:** `docker` role (already in the playbook)

## 2. Uptime Kuma — `monitoring/kuma-setup/`

### Structure
```
monitoring/kuma-setup/
├── setup.yml
├── inventory/hosts.ini
├── group_vars/all.yml
└── roles/
    ├── docker/        (copied from existing pattern)
    └── kuma/
        ├── defaults/main.yml
        ├── meta/main.yml
        └── tasks/main.yml
```

### Setup wizard prompts (two-play pattern with `add_host`)
Play 1 (localhost):
1. Host IP or hostname
2. SSH user

Play 2 (remote host): `become: true`, roles: `docker`, `kuma`

### Group vars
```yaml
kuma_container_name: kuma
kuma_image: "louislam/uptime-kuma:1.23.16"
kuma_port: 3001
kuma_volume_name: kuma_data
kuma_restart_policy: unless-stopped
kuma_health_check_retries: 12
kuma_health_check_delay: 5
```

### Role tasks
1. Create Docker volume
2. Deploy Uptime Kuma container, port bound to `127.0.0.1:{{ kuma_port }}:3001`
3. Health check: wait for web UI to respond
4. Display access URL

**Note:** Uptime Kuma handles its own account setup via the web UI on first launch. No API-based account creation needed.

## 3. Vaultwarden — `security/vaultwarden-setup/`

### Structure
```
security/vaultwarden-setup/
├── setup.yml
├── inventory/hosts.ini
├── group_vars/all.yml
└── roles/
    ├── docker/        (copied from existing pattern)
    └── vaultwarden/
        ├── defaults/main.yml
        ├── meta/main.yml
        └── tasks/main.yml
```

### Setup wizard prompts (two-play pattern with `add_host`)
Play 1 (localhost):
1. Host IP or hostname
2. SSH user
3. Admin token (private, confirmed) — used for the `/admin` panel

Play 2 (remote host): `become: true`, roles: `docker`, `vaultwarden`

### Group vars
```yaml
vaultwarden_container_name: vaultwarden
vaultwarden_image: "vaultwarden/server:1.32.7"
vaultwarden_port: 8080
vaultwarden_data_dir: /opt/vaultwarden
vaultwarden_restart_policy: unless-stopped
vaultwarden_health_check_retries: 12
vaultwarden_health_check_delay: 5
```

### Role tasks
1. Create data directory with mode `0700`
2. Generate argon2id hash of the admin token by running a one-off container: `docker run --rm vaultwarden/server /vaultwarden hash --preset owasp`
3. Deploy Vaultwarden container with environment (`no_log: true`):
   - `SIGNUPS_ALLOWED=false`
   - `ADMIN_TOKEN={{ hashed_admin_token }}`
   - `ROCKET_PORT=80`
4. Port bound to `127.0.0.1:{{ vaultwarden_port }}:80`
5. Volume: `{{ vaultwarden_data_dir }}:/data`
6. Health check: wait for web UI
7. Display access URL and admin panel URL

## 4. Paperless-ngx — `files/paperless-setup/`

### Structure
```
files/paperless-setup/
├── setup.yml
├── inventory/hosts.ini
├── group_vars/all.yml
├── roles/
│   ├── docker/        (copied from existing pattern)
│   └── paperless/
│       ├── defaults/main.yml
│       ├── meta/main.yml
│       ├── tasks/main.yml
│       └── templates/
│           └── docker-compose.yml.j2
```

### Setup wizard prompts (two-play pattern with `add_host`)
Play 1 (localhost):
1. Host IP or hostname
2. SSH user
3. Admin username
4. Admin password (private, confirmed)
5. Document storage path (default: empty — uses Docker volume)

Play 2 (remote host): `become: true`, roles: `docker`, `paperless`

### Group vars
```yaml
paperless_container_name: paperless
paperless_image: "ghcr.io/paperless-ngx/paperless-ngx:2.14.7"
paperless_port: 8000
paperless_data_dir: /opt/paperless
paperless_document_path: ""  # Empty = Docker volume, set path for NAS/external
paperless_redis_image: "redis:7.4"
paperless_postgres_image: "postgres:16.6"
paperless_restart_policy: unless-stopped
paperless_health_check_retries: 20
paperless_health_check_delay: 10
```

### Docker Compose template

Paperless-ngx requires Redis + PostgreSQL. Uses a `docker-compose.yml.j2` template (same pattern as seafile-setup):

- **paperless-redis**: Redis container for task queue
- **paperless-db**: PostgreSQL container with auto-generated password
- **paperless-web**: Paperless-ngx container with:
  - `PAPERLESS_ADMIN_USER` and `PAPERLESS_ADMIN_PASSWORD` for superuser creation
  - `PAPERLESS_SECRET_KEY` — auto-generated Django secret key
  - `PAPERLESS_REDIS` pointing to Redis container
  - `PAPERLESS_DBHOST` and `PAPERLESS_DBPASS` pointing to PostgreSQL container
  - Port bound to `127.0.0.1:{{ paperless_port }}:8000`

**Storage logic:**
- If `paperless_document_path` is empty: Docker volume `paperless_media` mounted to `/usr/src/paperless/media`
- If `paperless_document_path` is set: bind mount that path to `/usr/src/paperless/media`

### Role tasks
1. Create data directories
2. Auto-generate secrets (`no_log: true`):
   - PostgreSQL password (64-char random)
   - Django secret key (64-char random)
3. Template `docker-compose.yml.j2` with mode `0600`, owner `root`, group `root`
4. Deploy with `docker compose up -d`
5. Wait for health check (higher retries — Paperless takes longer to start)
6. Display access URL

## README updates

Add all 4 new entries to the root `README.md`:
- Pi-hole description added to the `infrastructure/` table (no new directory — it's a role in secure-homelab-access)
- Uptime Kuma, Vaultwarden, Paperless-ngx added to the `home-services/` table

## Security checklist

- [ ] No hardcoded secrets — all prompted or auto-generated
- [ ] `no_log: true` on all secret-handling tasks
- [ ] Containers bound to `127.0.0.1`
- [ ] Pinned image versions (specific patch versions, no floating tags)
- [ ] Docker Compose files mode `0600` (Paperless)
- [ ] Data directories restricted permissions
- [ ] Admin token hashed via container CLI before storing (Vaultwarden)
- [ ] Django secret key auto-generated (Paperless)
- [ ] systemd-resolved conflict handled (Pi-hole)
- [ ] Port 53 firewall rule restricted to VPN subnet (Pi-hole)

# Secure Homelab Remote Access

Ansible playbook for setting up secure remote access to a homelab entry node via public IP.

## Architecture

```
Internet → Cloudflare Tunnel (optional) → Caddy (HTTPS + TLS)
Internet → Public IP:51820/UDP → WireGuard VPN (wg-easy)
                                       │
                                  VPN Network (10.8.0.0/24)
                                       │
                                    Caddy (HTTPS + auto TLS)
                                       │
                                    Authelia (2FA: TOTP / WebAuthn)
                                       │
                 ┌─────────────────────┼─────────────────────┐
                 │                     │                     │
             Homepage              Cockpit               Services
            (dashboard)        (auto-login)         (Nexterm, etc.)
```

### Security Layers

1. **WireGuard VPN** — Only UDP port 51820 exposed to internet. All services accessible only through the VPN tunnel.
2. **UFW Firewall** — Default deny incoming. Only SSH + WireGuard ports open.
3. **Fail2ban** — Brute-force protection for SSH.
4. **CrowdSec** — Threat intelligence and DDoS mitigation (runs alongside Caddy).
5. **Caddy HTTPS** — TLS encryption for all services, even inside the VPN.
6. **Authelia 2FA** — TOTP or WebAuthn required for every service access.
7. **Cloudflare Tunnel** — Optional zero-trust tunnel for public-facing services without port forwarding.

## Components

| Component | Role | Access URL |
|-----------|------|------------|
| WireGuard (wg-easy) | VPN tunnel + peer management | `wg.yourdomain.com` |
| Caddy | Reverse proxy, HTTPS termination | — |
| Authelia | 2FA authentication gateway | `auth.yourdomain.com` |
| Cockpit | System management + web terminal (auto-login) | `cockpit.yourdomain.com` |
| Homepage | Service dashboard | `home.yourdomain.com` |
| Pi-hole | Ad-blocking DNS server | `pihole.yourdomain.com` |
| CrowdSec | Threat intelligence bouncer | — |
| UFW + Fail2ban | Firewall + brute-force protection | — |
| Cloudflared | Zero-trust Cloudflare tunnel (optional) | — |

## Quick Start

### 1. Set Your Target Host

Edit `inventory/hosts.ini` with your server details:

```ini
[homelab]
entry-node ansible_host=192.168.1.100 ansible_user=admin ansible_become=true
```

### 2. Deploy

Just run it — the playbook prompts for everything interactively:

```bash
ansible-playbook -i inventory/hosts.ini setup.yml
```

You'll be walked through a setup wizard that asks for:

| Step | Prompt | Example |
|------|--------|---------|
| 1 | Public IP address | `203.0.113.42` |
| 2 | Domain name | `homelab.example.com` |
| 3 | SSH port | `22` |
| 4 | Let's Encrypt email | `you@example.com` |
| 5 | WireGuard admin password | *(hidden)* |
| 6 | Authelia admin username | `admin` |
| 7 | Authelia admin password | *(hidden)* |
| 8 | Authelia admin email | `you@example.com` |
| 9 | Pi-hole admin password | *(hidden)* |
| 10 | Cockpit auto-login password | *(hidden, for Basic auth injection)* |
| 11 | Cloudflare API token | *(optional, press Enter to skip)* |
| 12 | Cloudflare tunnel name | *(optional)* |
| 13 | SMTP username | *(optional)* |
| 14 | SMTP app password | *(optional)* |

Secrets (JWT, session, encryption keys) are **auto-generated** at runtime.

Deploy specific components only:

```bash
ansible-playbook -i inventory/hosts.ini setup.yml --tags wireguard
ansible-playbook -i inventory/hosts.ini setup.yml --tags caddy,authelia
```

### 3. Connect

1. Open `https://YOUR_PUBLIC_IP:51821` to access wg-easy admin
2. Create a VPN peer and download the WireGuard config
3. Import into your WireGuard client (mobile/desktop)
4. Once connected, access services via their domain names

### 4. DNS Setup

Point `*.yourdomain.com` to your VPN server address (`10.8.0.1`) using:
- A local DNS server (Pi-hole, AdGuard Home)
- Entries in your client's `/etc/hosts` or equivalent
- A split-horizon DNS setup

## Notable Features

### Cockpit Auto-Login

Caddy injects a `Basic` auth header directly into requests to Cockpit:

```
header_up Authorization "Basic {$COCKPIT_BASIC_AUTH}"
header_down -WWW-Authenticate
```

The `COCKPIT_BASIC_AUTH` env var is set to `base64(username:password)` and passed to the Caddy container. This means navigating to `cockpit.yourdomain.com` logs you in automatically after Authelia 2FA — no separate Cockpit login prompt.

### Cloudflare Tunnel (Optional)

When a Cloudflare API token is provided, the playbook:
1. Creates a Cloudflare Tunnel via the API
2. Deploys `cloudflared` as a Docker container
3. Configures Caddy to route tunnel traffic alongside direct VPN traffic

### Vault Integration

When `security/vault-setup` is deployed first, this playbook:
- Reads existing secrets from `secret/homelab/infrastructure`
- Pre-fills all prompt defaults (just press Enter)
- Stores all credentials back to Vault after deployment

Secret paths within `secret/homelab/infrastructure`: `authelia_*`, `caddy_*`, `cloudflare_*`, `pihole_*`, `wireguard_*`, `cockpit_*`.

## Overriding Defaults

Internal settings (ports, subnets, container names) live in `group_vars/all.yml`.
Override any of them via extra-vars without editing files:

```bash
ansible-playbook -i inventory/hosts.ini setup.yml -e wireguard_port=51900 -e vpn_subnet=10.10.0.0/24
```

## Adding More Services

1. Add a reverse proxy block to `roles/caddy/templates/Caddyfile.j2`
2. Add the service card to `roles/homepage/templates/services.yaml.j2`
3. Register any new Cloudflare DNS records via `roles/cloudflare/tasks/main.yml`
4. Create a new role if the service needs its own deployment logic

## Requirements

- Target: Debian/Ubuntu-based system
- Ansible >= 2.16
- Collections: `community.docker`, `community.general`, `ansible.posix`

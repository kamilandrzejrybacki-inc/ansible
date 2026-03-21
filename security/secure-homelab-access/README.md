# Secure Homelab Remote Access

Ansible playbook for setting up secure remote access to a homelab entry node via public IP.

## Architecture

```
Internet → Public IP:51820/UDP → WireGuard VPN (wg-easy)
                                       │
                                  VPN Network (10.8.0.0/24)
                                       │
                                    Caddy (HTTPS + auto TLS)
                                       │
                                    Authelia (2FA: TOTP / WebAuthn)
                                       │
                         ┌─────────────┼─────────────┐
                         │             │             │
                     Homepage      Cockpit     Your Services
                    (dashboard)   (terminal)    (HA, etc.)
```

### Security Layers

1. **WireGuard VPN** — Only UDP port 51820 exposed to internet. All services accessible only through the VPN tunnel.
2. **UFW Firewall** — Default deny incoming. Only SSH + WireGuard ports open.
3. **Fail2ban** — Brute-force protection for SSH.
4. **Caddy HTTPS** — TLS encryption for all services, even inside the VPN.
5. **Authelia 2FA** — TOTP or WebAuthn required for every service access.

## Components

| Component | Role | Access URL |
|-----------|------|------------|
| WireGuard (wg-easy) | VPN tunnel + peer management | `wg.yourdomain.com` |
| Caddy | Reverse proxy, HTTPS termination | - |
| Authelia | 2FA authentication gateway | `auth.yourdomain.com` |
| Cockpit | System management + web terminal | `cockpit.yourdomain.com` |
| Homepage | Service dashboard | `home.yourdomain.com` |
| UFW + Fail2ban | Firewall + brute-force protection | - |

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
| 1/8 | Public IP address | `203.0.113.42` |
| 2/8 | Domain name | `homelab.example.com` |
| 3/8 | SSH port | `22` |
| 4/8 | Let's Encrypt email | `you@example.com` |
| 5/8 | WireGuard admin password | *(hidden, confirmed)* |
| 6/8 | Authelia admin username | `admin` |
| 7/8 | Authelia admin password | *(hidden, confirmed)* |
| 8/8 | Authelia admin email | `you@example.com` |

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

## Overriding Defaults

Internal settings (ports, subnets, container names) live in `group_vars/all.yml`.
You can override any of them via extra-vars without editing files:

```bash
ansible-playbook -i inventory/hosts.ini setup.yml -e wireguard_port=51900 -e vpn_subnet=10.10.0.0/24
```

## Adding More Services

1. Add a reverse proxy entry in `roles/caddy/templates/Caddyfile.j2`
2. Add the service to `roles/homepage/templates/services.yaml.j2`
3. Create a new role if the service needs its own deployment logic

## Requirements

- Target: Debian/Ubuntu-based system
- Ansible >= 2.10
- Collections: `community.docker`, `community.general`, `ansible.posix`

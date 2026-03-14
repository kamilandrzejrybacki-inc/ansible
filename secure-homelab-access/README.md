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

### 1. Configure

Edit `inventory/hosts.ini` with your server details:

```ini
[homelab]
entry-node ansible_host=192.168.1.100 ansible_user=admin ansible_become=true
```

Edit `group_vars/all.yml` — at minimum set:

```yaml
domain: "your-domain.com"
public_ip: "YOUR_PUBLIC_IP"
wireguard_password: "strong-password"        # Use ansible-vault!
authelia_jwt_secret: "random-secret"         # Use ansible-vault!
authelia_session_secret: "random-secret"     # Use ansible-vault!
authelia_storage_encryption_key: "64+ chars" # Use ansible-vault!
```

### 2. Generate Authelia Password Hash

```bash
docker run --rm authelia/authelia:latest authelia crypto hash generate argon2 --password 'your-password'
```

Put the output in `authelia_default_password_hash`.

### 3. Deploy

```bash
ansible-playbook -i inventory/hosts.ini setup.yml
```

Deploy specific components:

```bash
ansible-playbook -i inventory/hosts.ini setup.yml --tags wireguard
ansible-playbook -i inventory/hosts.ini setup.yml --tags caddy,authelia
```

### 4. Connect

1. Open `https://YOUR_PUBLIC_IP:51821` to access wg-easy admin
2. Create a VPN peer and download the WireGuard config
3. Import into your WireGuard client (mobile/desktop)
4. Once connected, access services via their domain names

### 5. DNS Setup

Point `*.yourdomain.com` to your VPN server address (`10.8.0.1`) using:
- A local DNS server (Pi-hole, AdGuard Home)
- Entries in your client's `/etc/hosts` or equivalent
- A split-horizon DNS setup

## Using Ansible Vault for Secrets

```bash
# Encrypt the vars file
ansible-vault encrypt group_vars/all.yml

# Run with vault
ansible-playbook -i inventory/hosts.ini setup.yml --ask-vault-pass
```

## Adding More Services

1. Add a reverse proxy entry in `roles/caddy/templates/Caddyfile.j2`
2. Add the service to `roles/homepage/templates/services.yaml.j2`
3. Create a new role if the service needs its own deployment logic

## Requirements

- Target: Debian/Ubuntu-based system
- Ansible >= 2.10
- Collections: `community.docker`, `community.general`, `ansible.posix`

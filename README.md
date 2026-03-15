# ansible

Personal Ansible playbooks for quickly spinning up a local Linux environment.

Each playbook set lives in its own subdirectory and is fully self-contained — inventory, roles, and variables are scoped locally rather than shared globally.

## Playbook sets

### `desktop/` — Desktop environment & utilities

| Directory | Description |
|---|---|
| [`desktop/i3-setup/`](./desktop/i3-setup/) | i3wm desktop environment — packages, dotfiles, i3lock-color, fastfetch, styling |
| [`desktop/handy-setup/`](./desktop/handy-setup/) | Handy speech-to-text — local voice transcription with model predownload |

### `dev-tools/` — AI & developer tooling

| Directory | Description |
|---|---|
| [`dev-tools/claude-code-setup/`](./dev-tools/claude-code-setup/) | Claude Code environment — CLI, plugins, MCP servers, Serena, rules |
| [`dev-tools/claude-n8n-mcp/`](./dev-tools/claude-n8n-mcp/) | Connect Claude Code to an existing n8n instance via MCP |

### `k8s/` — Kubernetes

| Directory | Description |
|---|---|
| [`k8s/kind-setup/`](./k8s/kind-setup/) | Local Kubernetes provisioning — Docker, kind, kubectl, multi-node cluster |

### `home-services/` — Self-hosted applications

| Directory | Description |
|---|---|
| [`home-services/n8n-setup/`](./home-services/n8n-setup/) | n8n workflow automation — Docker, owner account creation |
| [`home-services/homeassistant-setup/`](./home-services/homeassistant-setup/) | Home Assistant homelab monitor — Docker, monitoring, dashboards, webhook alerts |
| [`home-services/seafile-setup/`](./home-services/seafile-setup/) | Seafile self-hosted cloud storage — Docker, Caddy reverse proxy |

### `infrastructure/` — Networking, storage & security

| Directory | Description |
|---|---|
| [`infrastructure/secure-homelab-access/`](./infrastructure/secure-homelab-access/) | Secure homelab remote access — WireGuard, Authelia, Caddy, fail2ban, Cockpit |
| [`infrastructure/nas-setup/`](./infrastructure/nas-setup/) | NAS setup — mergerfs, SnapRAID, NFS, SMART monitoring, backups |

## Usage

```bash
# Install Ansible (one-time)
sudo apt install -y ansible

# Run a playbook
ansible-playbook <category>/<playbook-set>/<playbook>.yml \
  -i <category>/<playbook-set>/inventory/localhost.ini \
  --ask-become-pass
```

## Structure

```
ansible/
└── <category>/
    └── <playbook-set>/
        ├── <playbook>.yml
        ├── inventory/
        │   └── localhost.ini
        ├── group_vars/
        │   └── all.yml
        └── roles/
            └── <role>/
                ├── meta/main.yml
                ├── defaults/main.yml
                └── tasks/main.yml
```

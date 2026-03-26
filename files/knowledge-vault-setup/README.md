# Knowledge Vault Setup

Deploys [Syncthing](https://syncthing.net/) + [Quartz](https://quartz.jzhao.xyz/) to serve an Obsidian vault as a private, browsable website with graph view, backlinks, and full-text search.

## Prerequisites

- Target host running Ubuntu 22.04+ with SSH access
- `ansible-galaxy collection install -r requirements.yml`
- (Optional) HashiCorp Vault configured at `~/.vault-ansible.yml`
- (Optional) Secure homelab stack (Caddy, Authelia, Pi-hole, Homepage)
- Syncthing installed on your Linux desktop

## Usage

```bash
ansible-playbook files/knowledge-vault-setup/setup.yml \
  -i files/knowledge-vault-setup/inventory/hosts.ini \
  --ask-become-pass
```

The wizard prompts for:

| Prompt | Default | Description |
|--------|---------|-------------|
| Target host IP | 10.0.1.2 | Shared database host |
| SSH user | — | SSH user on the target host |
| Syncthing admin password | (from Vault) | Web UI admin password |

## What Gets Deployed

- **Syncthing** container — receives vault files from your desktop via P2P sync
- **Quartz** container — renders vault as a static website with auto-rebuild on file change
- Shared volume (`vault-content`) between Syncthing and Quartz
- (If homelab stack present) Caddy reverse proxy at `kb.<domain>`, Pi-hole DNS, Homepage entry

## Desktop Setup (One-time)

After the playbook runs:

1. Install Syncthing: `sudo apt install syncthing`
2. Start Syncthing: `syncthing` (or enable the systemd service)
3. Open `http://localhost:8384` in your browser
4. Go to Actions > Show ID on the **server** Syncthing (device ID is printed in playbook output)
5. In desktop Syncthing: Add Remote Device > paste the server device ID
6. Add Folder > select your Obsidian vault directory > share with the server device
7. On the server Syncthing, accept the incoming folder share

Your vault will sync and Quartz will auto-rebuild the site.

## Secrets

Stored in Vault at `secret/homelab/knowledge-vault`:

| Key | Description |
|-----|-------------|
| `syncthing_admin_password` | Syncthing Web UI admin password |

Local fallback: `~/.homelab-secrets/knowledge-vault/`

## Testing

```bash
cd files/knowledge-vault-setup/roles/syncthing
molecule test

cd ../quartz
molecule test
```

## Architecture

```
Desktop (Obsidian + Syncthing) → Syncthing container → shared volume → Quartz → Caddy (kb.<domain>)
Desktop (Obsidian + LiveSync)  → CouchDB → Mobile Obsidian (editing)
```

Quartz provides read-only web access. LiveSync + CouchDB handles mobile editing.

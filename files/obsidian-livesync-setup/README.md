# Obsidian LiveSync Setup

Deploys [CouchDB](https://couchdb.apache.org/) as a self-hosted sync backend for [Obsidian](https://obsidian.md/) using the [LiveSync](https://github.com/vrtmrz/obsidian-livesync) community plugin.

## Prerequisites

- Target host running Ubuntu 22.04+ with SSH access
- `ansible-galaxy collection install -r requirements.yml`
- (Optional) HashiCorp Vault configured at `~/.vault-ansible.yml`
- (Optional) Secure homelab stack (Caddy, Authelia, Pi-hole, Homepage)

## Usage

```bash
ansible-playbook files/obsidian-livesync-setup/setup.yml \
  -i files/obsidian-livesync-setup/inventory/hosts.ini \
  --ask-become-pass
```

The wizard prompts for:

| Prompt | Default | Description |
|--------|---------|-------------|
| Database host IP | 10.0.1.2 | Shared database host |
| SSH user | — | SSH user on the database host |
| Admin password | (from Vault) | CouchDB admin account password |
| Sync password | (from Vault) | Dedicated sync user password |

## What Gets Deployed

- **CouchDB 3.4** container in `databases-net` Docker network
- CORS configured for Obsidian origins (`app://obsidian.md`, `capacitor://localhost`)
- `obsidian-livesync` database with dedicated sync user
- (If homelab stack present) Caddy reverse proxy, Pi-hole DNS, Homepage entry

## Client Setup (Per Device)

After the playbook runs, configure each device manually:

1. Install [Obsidian](https://obsidian.md/)
2. Go to Settings > Community Plugins > Browse > search "Self-hosted LiveSync"
3. Install and enable the plugin
4. Open plugin settings and configure:
   - **URI:** `https://couchdb.<your-domain>` (or `http://<host-ip>:5984` without Caddy)
   - **Username:** `obsidian-sync`
   - **Password:** the sync password you set during setup
   - **Database:** `obsidian-livesync`
5. Enable **E2E encryption** and set a passphrase (use the same passphrase on all devices)
6. Under "Sync Settings", choose **LiveSync** mode for real-time sync

## Secrets

Stored in Vault at `secret/homelab/obsidian-livesync`:

| Key | Description |
|-----|-------------|
| `couchdb_admin_user` | Admin username (default: `admin`) |
| `couchdb_admin_password` | Admin password |
| `couchdb_sync_user` | Sync username (default: `obsidian-sync`) |
| `couchdb_sync_password` | Sync user password |

Local fallback: `~/.homelab-secrets/obsidian-livesync/`

## Testing

```bash
cd files/obsidian-livesync-setup/roles/couchdb
molecule test
```

## Backup

CouchDB data persists in a Docker volume on the database host. It is covered by the host-level volume backup strategy.

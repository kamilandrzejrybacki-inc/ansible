# n8n Setup

Deploys [n8n](https://n8n.io) workflow automation via Docker. Integrates with the homelab stack (Caddy reverse proxy, Cloudflare Tunnel, Pi-hole DNS, Homepage dashboard).

## Usage

```bash
ansible-playbook automation/n8n-setup/setup.yml \
  -i automation/n8n-setup/inventory/hosts.ini \
  --ask-become-pass
```

The wizard prompts for the target host IP, SSH user, and n8n owner account details.

## Vault Secrets

Store the n8n owner password (and optionally a GitHub PAT for private workflow repos) before running:

```bash
vault kv put secret/n8n \
  owner_password=<n8n-owner-password> \
  workflows_repo_token=<github-pat>   # only if workflows repo is private
```

Service secrets (API tokens, etc.) are stored in the same path and picked up automatically by n8n at runtime — no redeployment needed:

```bash
# Add a new secret any time — n8n picks it up within 5 minutes
vault kv patch secret/n8n netbox_token=<value>
vault kv patch secret/n8n librenms_token=<value>
vault kv patch secret/n8n my_new_api_key=<value>
```

## Workflow Credentials — External Secrets

n8n connects directly to HashiCorp Vault via the **External Secrets** integration, configured automatically at deploy time. Secrets stored at `secret/n8n` in Vault are available in all workflow nodes as:

```
={{ $secrets.vault.netbox_token }}
={{ $secrets.vault.librenms_token }}
={{ $secrets.vault.my_new_api_key }}
```

n8n polls Vault every 300 seconds (configurable via `n8n_external_secrets_update_interval`). Adding a new key to `secret/n8n` makes it available in workflows within that window — no restart required.

**Never hardcode tokens in workflow JSON files.** Workflow files are stored in a Git repository and must not contain secrets.

## Workflow Repository

Workflows are sourced from [kamilrybacki/n8n-workflows](https://github.com/kamilrybacki/n8n-workflows) at deploy time. The Ansible role clones the repo and imports all `*.json` files via the n8n CLI.

For ongoing backup, configure **Settings > Source Control** in the n8n UI after deployment:
1. Connect to the workflows repository
2. Generate an SSH key pair in n8n
3. Add the public key as a deploy key (write access) to the GitHub repo

## Post-Deployment

After the playbook completes:

1. Log in to n8n and configure Source Control (see above)
2. Go to **Settings > Instance-level MCP** and copy your MCP Access Token
3. Run the Claude Code MCP integration:

```bash
ansible-playbook dev-tools/claude-n8n-mcp/setup.yml \
  -i dev-tools/claude-n8n-mcp/inventory/hosts.ini
```

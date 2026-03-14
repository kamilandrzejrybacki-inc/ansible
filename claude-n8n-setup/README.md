# claude-n8n-setup

Ansible playbook for setting up [n8n](https://n8n.io/) on a remote host via Docker and configuring [Claude Code](https://docs.anthropic.com/en/docs/claude-code) to connect to it as an MCP server.

Designed for a home lab with two Linux machines on the same LAN.

## Prerequisites

- SSH key-based access from the control node to the n8n host
- Claude Code CLI installed on the client machine
- `community.docker` Ansible collection:
  ```bash
  ansible-galaxy collection install community.docker
  ```
- No firewall blocking port 5678 between machines

## Usage

The playbook is designed to be run **twice**:

### First run — deploy n8n and create the owner account

```bash
ansible-playbook claude-n8n-setup/setup.yml \
  -i claude-n8n-setup/inventory/hosts.ini \
  --ask-become-pass
```

This installs Docker, starts n8n, and creates the owner account automatically via `POST /rest/owner/setup`. Leave the MCP Access Token prompt blank on first run.

After the playbook finishes, log in to `http://<n8n_host_ip>:5678`, go to **Settings > Instance-level MCP**, and copy your MCP Access Token.

### Second run — configure Claude Code MCP

Re-run the same command and paste the MCP Access Token when prompted. The playbook will register n8n as an MCP server in Claude Code at user scope.

## Prompts

| Prompt | Default | Description |
|---|---|---|
| n8n host IP | — | IP or hostname of the machine that will run n8n |
| n8n SSH user | — | SSH user on the n8n host |
| Claude Code client IP | `localhost` | IP of the Claude Code machine (use `localhost` if running from it) |
| Claude Code SSH user | — | SSH user on the Claude client (ignored if localhost) |
| Owner email | — | Email for the n8n admin account |
| Owner password | *(hidden)* | Password for the n8n admin account |
| Owner first name | `Admin` | First name for the n8n admin account |
| Owner last name | `User` | Last name for the n8n admin account |
| MCP Access Token | *(blank)* | n8n MCP token; leave blank on first run, paste on second run |

## Roles

| Role | What it does |
|---|---|
| `docker` | Installs Docker engine via the official APT repository (Debian/Ubuntu) |
| `n8n` | Creates a Docker volume, runs the n8n container, and creates the owner account |
| `claude_mcp` | Registers n8n as an MCP server in Claude Code at user scope (`~/.claude.json`) |

## What gets automated vs. manual

| Step | Automated? |
|---|---|
| Docker installation | Yes |
| n8n container deployment | Yes |
| Owner account creation | Yes (via internal REST API) |
| MCP Access Token retrieval | No (must copy from n8n UI once) |
| Claude Code MCP registration | Yes (on second run with token) |

## Structure

```
claude-n8n-setup/
├── setup.yml
├── inventory/
│   └── hosts.ini
├── group_vars/
│   └── all.yml          <- shared vars (container name, port, image, etc.)
└── roles/
    ├── docker/
    ├── n8n/
    └── claude_mcp/
```

# Claude Code Setup

Ansible playbook for provisioning [Claude Code](https://claude.com/claude-code) with a full configuration: CLI installation, settings, rules, plugins, Serena MCP, standalone MCP servers, and custom commands.

## Prerequisites

- Ansible 2.10+
- SSH key-based access to the target (if provisioning a remote machine)
- `sudo` access on the target (for Node.js and system package installation)

## What Gets Installed

| Role | What it does |
|------|-------------|
| `claude_cli` | Installs Node.js 22 (via NodeSource) and Claude Code CLI (`npm install -g @anthropic-ai/claude-code`). Skips if already present. |
| `claude_config` | Copies `settings.json`, `CLAUDE.md`, `RTK.md`, and `rules/` into `~/.claude/`. Timestamps and backs up existing settings. |
| `plugins` | Registers 5 marketplaces (superpowers, everything-claude-code, n8n-mcp-skills, openai-codex, caveman) and installs 6 plugins (superpowers, serena, everything-claude-code, n8n-mcp-skills, codex, caveman). Disables `context7` per block list. Patches `caveman-activate.js` to emit full-mode rules on session start. |
| `mcp_servers` | Registers HTTP MCP servers (Gmail, Google Calendar) and the `lightpanda` stdio server (`docker exec`). |
| `commands` | Deploys any custom slash commands listed in `claude_commands` (empty by default). |
| `rtk` | Installs the RTK proxy, wires its PreToolUse Bash hook into `settings.json`, and injects ansible-playbook/helm/docker-log skip rules into the rewrite script. |
| `jcodemunch` | Installs `uv` (if missing), installs `jcodemunch-mcp` via `uv tool install`, registers it as a user-scope stdio MCP (`uvx jcodemunch-mcp`), and merges WorktreeCreate/Remove, PreToolUse Read, PostToolUse Edit\|Write, and PreCompact hooks into `settings.json`. |

## Usage

### Provision this machine (localhost)

```bash
cd claude-code-setup
ansible-playbook -i inventory/hosts.ini setup.yml
```

Accept the default `localhost` when prompted.

### Provision a remote machine

```bash
cd claude-code-setup
ansible-playbook -i inventory/hosts.ini setup.yml
```

When prompted:
- **Target host:** enter the IP or hostname
- **SSH user:** enter the SSH username

## Post-Setup Steps

After the playbook completes:

1. **Authenticate Claude Code:** Run `claude login` on the target machine
2. **Complete OAuth flows:** Start Claude Code and trigger Gmail/Calendar MCP servers to complete OAuth
3. **Verify RTK wiring:** Run `rtk --version` and `rtk gain` to confirm the binary is on `PATH` and the hook rewrites commands

## Customization

All defaults are in each role's `defaults/main.yml`. Override them in `group_vars/all.yml`:

```yaml
# Example: change Node.js version
node_major_version: 20

# Example: add more plugins
claude_plugins:
  - "superpowers@claude-plugins-official"
  - "my-plugin@my-marketplace"

# Example: add more MCP servers
claude_mcp_servers:
  - name: "my-server"
    transport: http
    url: "https://my-server.example.com/mcp"
    scope: user

# Example: override RTK install source
rtk_install_url: "https://raw.githubusercontent.com/rtk-ai/rtk/master/install.sh"
```

## Configuration Files

The `files/` directory contains canonical configuration snapshots:

- `files/claude/settings.json` — Claude Code settings (plugins, marketplaces, `disabledMcpjsonServers`, `effortLevel`, `advisorModel`)
- `files/claude/CLAUDE.md` — global project instructions loaded by Claude Code
- `files/claude/RTK.md` — RTK usage reference loaded alongside `CLAUDE.md`
- `files/claude/rules/` — rule files across global + language-specific categories

To refresh snapshots after tweaking your live config:

```bash
cp ~/.claude/settings.json files/claude/settings.json
cp ~/.claude/CLAUDE.md     files/claude/CLAUDE.md
cp ~/.claude/RTK.md        files/claude/RTK.md
cp -r ~/.claude/rules       files/claude/rules
```

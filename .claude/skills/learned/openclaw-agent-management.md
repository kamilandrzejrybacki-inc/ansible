---
name: openclaw-agent-management
description: "OpenClaw agents/providers: CLI-managed agents, api:openai-completions for providers, model ID format, native vs custom providers"
user-invocable: false
origin: auto-extracted
---

# OpenClaw Agent Management via CLI

**Extracted:** 2026-03-23
**Context:** When creating, listing, or managing OpenClaw agents in Ansible playbooks

## Problem
OpenClaw's `openclaw.json` config has an `agents.defaults.model` key, which suggests agents might be
configured declaratively via JSON (e.g. `agents.tiers`, `agents.definitions`). They cannot.
Attempting to add custom keys to the JSON config will be silently ignored.

## Solution
Agents are managed exclusively via the CLI:

```bash
# Create an agent with a specific model
openclaw agents add <name> --model <provider/model-id> --non-interactive --workspace /home/node/.openclaw/workspace

# List agents (JSON output uses "id" field, NOT "name")
openclaw agents list --json
# Returns: [{"id": "main", "model": "nvidia/kimi-k2.5", "isDefault": true, ...}]

# Route channels to agents
openclaw agents bind --agent <id> --bind <channel[:accountId]>

# Other: delete, set-identity, unbind, bindings
```

### Ansible Idempotent Pattern
```yaml
- name: List existing OpenClaw agents
  ansible.builtin.command:
    cmd: docker exec openclaw openclaw agents list --json
  register: _openclaw_agents_raw
  changed_when: false
  failed_when: false

- name: Parse existing agent names
  ansible.builtin.set_fact:
    _openclaw_existing_agents: >-
      {{ (_openclaw_agents_raw.stdout | from_json | map(attribute='id') | list)
         if (_openclaw_agents_raw.rc == 0 and _openclaw_agents_raw.stdout | trim is regex('^\['))
         else [] }}

- name: Create OpenClaw agents
  ansible.builtin.command:
    cmd: >-
      docker exec openclaw openclaw agents add {{ item.name | quote }}
      --model {{ item.model | quote }}
      --non-interactive
      --workspace /home/node/.openclaw/workspace
  loop: "{{ openclaw_agents }}"
  when: item.name not in _openclaw_existing_agents
```

### Key Gotchas
- JSON field is `id`, not `name` — `map(attribute='name')` will fail
- `--non-interactive` required for Ansible (no TTY)
- Each agent gets ONE model, no fallback chains
- Routing is channel-based (`--bind`), not complexity-based
- The `main` agent is created by default and cannot be removed

## Provider Configuration

### API Mode (Critical)
OpenClaw defaults to `openai-responses` API (`/v1/responses`). Most providers (NVIDIA, Groq, DeepSeek)
only support `/v1/chat/completions`. Without explicit `api` setting, all requests return HTTP 404.

Valid `api` values: `openai-completions`, `openai-responses`, `openai-codex-responses`,
`anthropic-messages`, `google-generative-ai`, `github-copilot`, `bedrock-converse-stream`, `ollama`

### Provider Types
- **Custom providers** (in `models.providers`): NVIDIA, Groq, DeepSeek — need `api: "openai-completions"` + `baseUrl` + `apiKey` + `models` array
- **Native built-in providers** (via env var only): Google Gemini — just set `GEMINI_API_KEY` env var, no entry in `models.providers`

### Model ID Format
Three-part format: `{provider}/{vendor}/{model}` for OpenClaw routing.
- Config `models[].id`: `moonshotai/kimi-k2.5` (what the upstream API receives)
- OpenClaw model ref: `nvidia/moonshotai/kimi-k2.5` (provider prefix + API model ID)
- The `agents.defaults.model` and agent `--model` flags use the full prefixed form

### Docker Compose Restart
The socat proxy sidecar shares OpenClaw's network namespace (`network_mode: service:openclaw`).
Plain `docker compose restart` leaves the proxy with a stale namespace. Always use:
```bash
docker compose down && docker compose up -d
```

## When to Use
- Adding/removing/modifying OpenClaw agents
- Writing Ansible tasks for OpenClaw agent provisioning
- Investigating OpenClaw routing or agent config
- Configuring new LLM providers or debugging model 404/400 errors
- Troubleshooting Docker restart failures with the socat proxy

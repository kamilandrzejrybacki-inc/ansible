<h1 align="center">Ansible Homelab</h1>

<p align="center">
  <strong>Infrastructure as Code for rapidly provisioning Linux environments, homelab services, and Kubernetes clusters.</strong>
</p>

<p align="center">
  <a href="https://github.com/kamilrybacki/ansible/actions/workflows/ci-fast.yml"><img src="https://github.com/kamilrybacki/ansible/actions/workflows/ci-fast.yml/badge.svg?branch=main" alt="CI - Fast"></a>
  <a href="https://github.com/kamilrybacki/ansible/actions/workflows/ci-heavy.yml"><img src="https://github.com/kamilrybacki/ansible/actions/workflows/ci-heavy.yml/badge.svg?branch=main" alt="CI - Heavy"></a>
  <img src="https://img.shields.io/badge/ansible-%3E%3D2.16-EE0000?logo=ansible&logoColor=white" alt="Ansible">
  <img src="https://img.shields.io/badge/molecule-tested-2ECC40?logo=testing-library&logoColor=white" alt="Molecule Tested">
  <img src="https://img.shields.io/badge/roles-57-blue" alt="Roles">
  <img src="https://img.shields.io/badge/playbooks-27-blue" alt="Playbooks">
</p>

---

## Overview

A collection of **27 self-contained Ansible playbook sets** organized into 8 functional categories. Each playbook is fully independent with its own inventory, roles, and variables — no global shared state.

**Key features:**

- Interactive setup wizards via `vars_prompt` — no manual file editing required
- Docker-first deployments with pinned image versions and localhost-only bindings
- Optional HashiCorp Vault integration — secrets auto-loaded/stored when Vault is available
- Tiered CI/CD pipeline with Molecule + Testinfra covering 93% of roles
- Security by default: `no_log` on secrets, UFW firewall, fail2ban, Authelia 2FA

---

## Table of Contents

- [Security — Access Control & Secrets](#security--access-control--secrets)
- [AI — LLM Platforms & Agents](#ai--llm-platforms--agents)
- [Automation — Workflow Automation](#automation--workflow-automation)
- [Monitoring — Observability & Home Automation](#monitoring--observability--home-automation)
- [Files — Documents & Storage](#files--documents--storage)
- [Desktop — Environment & Utilities](#desktop--environment--utilities)
- [Dev Tools — Developer Tooling](#dev-tools--developer-tooling)
- [Kubernetes — Cluster Provisioning](#kubernetes--cluster-provisioning)
- [Getting Started](#getting-started)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Security Notes](#security-notes)

---

## Security — Access Control & Secrets

Playbooks for securing homelab access, managing secrets, and protecting credentials.

| Playbook | Description | Roles |
|----------|-------------|-------|
| [`security/secure-homelab-access`](./security/secure-homelab-access/) | Secure remote access — WireGuard VPN, Authelia 2FA, Caddy HTTPS, Pi-hole DNS, CrowdSec, fail2ban, UFW, Cockpit, Homepage | 9 |
| [`security/vault-setup`](./security/vault-setup/) | HashiCorp Vault — centralized secrets management for all playbooks | 2 |
| [`security/vaultwarden-setup`](./security/vaultwarden-setup/) | Vaultwarden — self-hosted Bitwarden-compatible password manager | 2 |
| [`security/lab-network`](./security/lab-network/) | Lab gateway — dnsmasq DHCP/DNS, NAT, static leases for k8s nodes | — |

### security/secure-homelab-access

Deploys a hardened, production-grade remote access stack on a single server. Run this first on any new homelab machine.

**Stack:**

| Component | Purpose | Port |
|-----------|---------|------|
| UFW | Host firewall | — |
| fail2ban | Brute-force protection | — |
| Pi-hole | Ad-blocking DNS server | 8053 (UI) |
| WireGuard (wg-easy) | VPN server | 51820/UDP, 51821 (UI) |
| CrowdSec | Threat intelligence & DDoS mitigation | — |
| Cloudflared | Zero-trust tunnel to Cloudflare | — |
| Authelia | 2FA authentication portal | — |
| Caddy | Reverse proxy + automatic HTTPS (Let's Encrypt) | 80, 443 |
| Cockpit | Web-based server management & terminal | — |
| Homepage | Service dashboard | — |

**Subdomains provisioned:** `auth.<domain>`, `home.<domain>`, `cockpit.<domain>`, `wg.<domain>`, `pihole.<domain>`

**Prompts for (14 total):** host IP/SSH credentials, public IP, domain, Let's Encrypt email, SSH port, WireGuard admin password, Authelia credentials, Pi-hole password, Cloudflare API token and tunnel name (both optional).

**Secrets:** Automatically generated JWT, session, and encryption keys. All credentials written to `~/.homelab-credentials` (mode 0600). When Vault is available, secrets are also stored at `secret/homelab/infrastructure`.

### security/vault-setup

Deploys [HashiCorp Vault](https://www.vaultproject.io/) as the centralized secrets store for all homelab playbooks.

- **Stack:** HashiCorp Vault (v1.17) via Docker Compose
- **Storage:** file (default) or Raft (HA-capable)
- **Auto-unseal:** optional — stores unseal keys on disk for automatic restart recovery
- **Integration:** saves `~/.vault-ansible.yml` with connection details; all other playbooks auto-detect and use Vault when available
- **Secret paths:** `secret/homelab/<service>` — one path per playbook (infrastructure, dify, openclaw, n8n, paperless, vaultwarden, seafile, netbox, librenms, swe-af)
- **Policy:** creates an `ansible-automation` policy with read/write access to all homelab paths

### security/vaultwarden-setup

Deploys [Vaultwarden](https://github.com/dani-garcia/vaultwarden), a lightweight self-hosted Bitwarden-compatible server.

- **Image:** `vaultwarden/server:1.32.7`
- **Web UI:** port 8080
- **SMTP email (optional):** supports Gmail, Outlook, Zoho, Fastmail, SendGrid, Mailgun, AWS SES, or custom host/port
- **Vault path:** `secret/homelab/vaultwarden` (admin_token, smtp_password)

### security/lab-network

Configures a server as a dedicated gateway for an isolated lab network (used alongside the Proxmox k8s setup).

- **Installs:** `dnsmasq` for DHCP and DNS
- **Configures:** WAN/LAN interface split, NAT/IP masquerade, static DHCP leases, `lab.home` domain

---

## AI — LLM Platforms & Agents

Playbooks for deploying AI and LLM infrastructure.

| Playbook | Description | Roles |
|----------|-------------|-------|
| [`ai/openclaw-setup`](./ai/openclaw-setup/) | OpenClaw — multi-provider AI agent framework with complexity-tiered routing + optional Ollama | 2 |
| [`ai/dify-setup`](./ai/dify-setup/) | Dify — LLM app platform with vector store and LiteLLM proxy | 3 |
| [`ai/swe-af-setup`](./ai/swe-af-setup/) | SWE-AF — autonomous software engineering agent runtime | 2 |

### ai/openclaw-setup

Deploys [OpenClaw](https://openclaw.com/) with 4 cloud providers + optional Ollama local provider. Complexity-tiered routing sends 90%+ traffic to free models (~$0-5/month).

- **Providers:** NVIDIA NIM (free, 6 models), Groq (free, fast), Google Gemini (free, 1M context), DeepSeek (paid), Ollama (local, optional)
- **Routing:** heartbeat → free models, simple tasks → free primary, complex → DeepSeek (if configured)
- **Vault path:** `secret/homelab/openclaw` (nvidia_api_key, groq_api_key, gemini_api_key, deepseek_api_key)

### ai/dify-setup

Deploys [Dify](https://dify.ai/), an open-source LLM application development platform.

- **Vector store:** Weaviate (default), with Qdrant, pgvector, or Chroma as alternatives
- **LiteLLM proxy (optional):** unifies access to Groq, Google Gemini, OpenRouter, Cerebras
- **Vault path:** `secret/homelab/dify` (litellm_master_key, groq_api_key, gemini_api_key, openrouter_api_key, cerebras_api_key, admin_password)

### ai/swe-af-setup

Deploys [SWE-AF](https://github.com/SWE-agent/SWE-agent), an autonomous software engineering agent framework.

- **Supports:** Anthropic (direct), Claude OAuth, OpenRouter as AI providers; optional GitHub integration for PR workflows
- **Vault path:** `secret/homelab/swe-af` (api_key, gh_token)

---

## Automation — Workflow Automation

Playbooks for workflow automation and tool integration.

| Playbook | Description | Roles |
|----------|-------------|-------|
| [`automation/n8n-setup`](./automation/n8n-setup/) | n8n — workflow automation, MCP integration support | 2 |
| [`automation/claude-n8n-mcp`](./automation/claude-n8n-mcp/) | Connect Claude Code to an existing n8n instance via MCP | 1 |

### automation/n8n-setup

Deploys [n8n](https://n8n.io/) workflow automation.

- **Image:** `docker.n8n.io/n8nio/n8n` (persistent volume `n8n_data`)
- **Web UI:** port 5678
- **Configures:** owner account, MCP (Model Context Protocol) integration endpoint
- **Vault path:** `secret/homelab/n8n` (owner_email, owner_password)

### automation/claude-n8n-mcp

Registers an n8n instance as an MCP (Model Context Protocol) server inside Claude Code.

- **Requires:** a running n8n deployment (use `automation/n8n-setup` first)
- **Configures:** MCP server entry in Claude Code config with n8n endpoint URL and access token

---

## Monitoring — Observability & Home Automation

Playbooks for monitoring infrastructure, services, and smart home devices.

| Playbook | Description | Roles |
|----------|-------------|-------|
| [`monitoring/librenms-setup`](./monitoring/librenms-setup/) | LibreNMS — network monitoring, SNMP discovery, alerting | 2 |
| [`monitoring/netbox-setup`](./monitoring/netbox-setup/) | Netbox — infrastructure documentation, IPAM, asset inventory | 2 |
| [`monitoring/kuma-setup`](./monitoring/kuma-setup/) | Uptime Kuma — HTTP/TCP/ping monitoring with status pages | 2 |
| [`monitoring/homeassistant-setup`](./monitoring/homeassistant-setup/) | Home Assistant — HACS, monitoring, dashboards, Discord/Slack alerts | 6 |
| [`monitoring/bambulab-setup`](./monitoring/bambulab-setup/) | BambuLab X1C — HA integration, AMS tracking, print alerts | 3 |

### monitoring/librenms-setup

Deploys [LibreNMS](https://www.librenms.org/) — a full-featured auto-discovering network monitoring system.

- **Stack:** LibreNMS (v26.3.1) + MariaDB + Redis via Docker Compose
- **Web UI:** port 8080
- **Vault path:** `secret/homelab/librenms` (snmp_community, db_password)

### monitoring/netbox-setup

Deploys [Netbox](https://netbox.dev/) — the leading open-source tool for IP address management (IPAM) and data center infrastructure management (DCIM).

- **Stack:** Netbox (v4.2) + PostgreSQL 16 + Valkey via Docker Compose
- **Web UI:** port 8080
- **Vault path:** `secret/homelab/netbox` (admin_user, admin_email, admin_password)

### monitoring/kuma-setup

Deploys [Uptime Kuma](https://github.com/louislam/uptime-kuma) for service uptime monitoring.

- **Image:** `louislam/uptime-kuma:1.23.16`
- **Web UI:** port 3001
- **Supports:** HTTP(S), TCP, DNS, ping, Docker container, and push monitors

### monitoring/homeassistant-setup

Deploys [Home Assistant](https://www.home-assistant.io/) as the central smart home hub.

- **Image:** `ghcr.io/home-assistant/home-assistant:stable`
- **Web UI:** port 8123
- **Roles:** `docker`, `homeassistant`, `hacs`, `monitoring`, `dashboard`, `alerts`

### monitoring/bambulab-setup

Adds BambuLab X1C printer integration to an existing Home Assistant instance.

- **Integration:** [ha-bambulab](https://github.com/greghesp/ha-bambulab) via HACS
- **Tracks:** print status, remaining time, layer progress, AMS filament slots, temperatures

---

## Files — Documents & Storage

Playbooks for document management, PDF processing, and file synchronization.

| Playbook | Description | Roles |
|----------|-------------|-------|
| [`files/paperless-setup`](./files/paperless-setup/) | Paperless-ngx — document management, OCR, PostgreSQL + Redis | 2 |
| [`files/stirling-pdf-setup`](./files/stirling-pdf-setup/) | Stirling-PDF — merge, split, convert, OCR, compress PDFs | 2 |
| [`files/seafile-setup`](./files/seafile-setup/) | Seafile — file sync & share, MariaDB + Memcached, Caddy proxy | 3 |
| [`files/nas-setup`](./files/nas-setup/) | NAS — mergerfs pool, SnapRAID parity, NFS shares, SMART monitoring | 6 |

### files/paperless-setup

Deploys [Paperless-ngx](https://docs.paperless-ngx.com/) for paperless document management with OCR.

- **Stack:** Paperless-ngx (v2.14.7), PostgreSQL 16.6, Redis 7.4
- **Web UI:** port 8000
- **Vault path:** `secret/homelab/paperless` (admin_user, admin_password)

### files/stirling-pdf-setup

Deploys [Stirling-PDF](https://github.com/Stirling-Tools/Stirling-PDF) for comprehensive PDF manipulation.

- **Image:** `frooodle/s-pdf:0.36.5`
- **Web UI:** port 8080
- **Features:** merge, split, rotate, compress, convert, OCR, redact, watermark, sign

### files/seafile-setup

Deploys [Seafile](https://www.seafile.com/) for self-hosted file synchronisation and sharing.

- **Stack:** Seafile MC (v11.0), MariaDB 10.11, Memcached, optional Caddy reverse proxy
- **Web UI:** port 8080
- **Vault path:** `secret/homelab/seafile` (admin_email, admin_password, db_root_password)

### files/nas-setup

Configures a multi-drive NAS with software redundancy and network sharing.

- **Pool:** `mergerfs` (unified view of multiple drives at `/mnt/pool`)
- **Parity:** SnapRAID (nightly sync at 03:00, weekly scrub Sundays at 05:00)
- **Shares:** NFS export on the configured `nfs_allowed_network`
- **Monitoring:** `smartd` S.M.A.R.T. checks on all drives

---

## Desktop — Environment & Utilities

Playbooks for configuring a daily-driver Linux desktop environment.

| Playbook | Description | Roles |
|----------|-------------|-------|
| [`desktop/i3-setup`](./desktop/i3-setup/) | i3wm desktop — packages, dotfiles, i3lock-color, fastfetch, styling | 5 |
| [`desktop/handy-setup`](./desktop/handy-setup/) | Handy speech-to-text — local voice transcription with configurable Whisper/Parakeet models | 1 |
| [`desktop/audiorelay-setup`](./desktop/audiorelay-setup/) | AudioRelay USB microphone — Android phone as mic via PulseAudio virtual sink | 1 |
| [`desktop/weylus-setup`](./desktop/weylus-setup/) | Weylus drawing tablet — Android phone as stylus-enabled tablet via adb + uinput | 2 |

---

## Dev Tools — Developer Tooling

Playbooks for developer environment setup.

| Playbook | Description | Roles |
|----------|-------------|-------|
| [`dev-tools/claude-code-setup`](./dev-tools/claude-code-setup/) | Claude Code CLI — plugins, MCP servers, Serena semantic analysis, custom rules | 6 |

### dev-tools/claude-code-setup

Provisions [Claude Code](https://claude.ai/code) with a curated set of plugins, MCP servers, and project rules.

- **Roles:** `claude_cli`, `claude_config`, `plugins`, `serena`, `mcp_servers`, `commands`
- **Installs:** Claude Code CLI, Serena (semantic code analysis via LSP), Gmail MCP server, custom slash commands

---

## Kubernetes — Cluster Provisioning

Playbooks for local development clusters and production-grade Kubernetes on Proxmox.

| Playbook | Description | Roles |
|----------|-------------|-------|
| [`k8s/kind-setup`](./k8s/kind-setup/) | Local Kubernetes — Docker, kind, kubectl, configurable multi-node cluster | 3 |
| [`k8s/k8s-full-setup`](./k8s/k8s-full-setup/) | Full local stack — kind + Helm + k9s + Headlamp + ArgoCD | 0* |
| [`k8s/proxmox-k8s-setup`](./k8s/proxmox-k8s-setup/) | Production Kubernetes on Proxmox — cloud-init template, VM cloning, kubeadm, Calico CNI | 5 |
| [`k8s/helm-setup`](./k8s/helm-setup/) | Helm 3 CLI (v3.16.4) | 1 |
| [`k8s/k9s-setup`](./k8s/k9s-setup/) | k9s terminal UI (v0.32.7) | 1 |
| [`k8s/headlamp-setup`](./k8s/headlamp-setup/) | Headlamp web dashboard — Helm chart, admin token | 1 |
| [`k8s/argocd-setup`](./k8s/argocd-setup/) | ArgoCD GitOps controller (v2.13.3), admin password | 1 |

<sub>* Orchestrator playbook — chains the individual sub-playbooks, no roles of its own.</sub>

---

## Getting Started

### Prerequisites

- **Control node:** Ansible >= 2.16, Python >= 3.10
- **Target hosts:** Debian/Ubuntu-based (22.04+)
- **Collections:** installed automatically via `requirements.yml`

### Quick Start

```bash
# 1. Clone
git clone https://github.com/kamilrybacki/ansible.git
cd ansible

# 2. Install Ansible collections
ansible-galaxy collection install -r requirements.yml

# 3. Run any playbook (interactive wizard guides you through config)
ansible-playbook monitoring/kuma-setup/setup.yml \
  -i monitoring/kuma-setup/inventory/hosts.ini \
  --ask-become-pass
```

Each playbook's interactive wizard prompts for target host, SSH credentials, and service-specific configuration. No manual file editing required.

### Recommended First-Run Order

For a fresh homelab server:

```
1. security/secure-homelab-access        # Firewall, VPN, HTTPS, 2FA
2. security/vault-setup                  # Centralized secrets (optional, recommended)
3. monitoring/librenms-setup             # Network monitoring
4. ai/*, automation/*, files/*           # Any services you want
```

For a local development machine:

```
1. desktop/i3-setup                      # Window manager
2. dev-tools/claude-code-setup           # AI coding assistant
3. k8s/k8s-full-setup                   # Local Kubernetes
```

### Vault Integration (Optional)

When `security/vault-setup` is deployed, all other playbooks automatically:
1. Detect Vault via `~/.vault-ansible.yml`
2. Load secrets from predetermined paths (`secret/homelab/<service>`)
3. Pre-fill prompt defaults — just press Enter
4. Store new/changed secrets back to Vault after deployment

No configuration needed — the integration is transparent and falls back to interactive prompts when Vault is unavailable.

---

## Project Structure

```
ansible/
├── .github/workflows/       # CI/CD pipelines (fast + heavy tiers)
├── common/                   # Shared components
│   ├── vault-integration/    #   Vault check/load/store tasks
│   └── roles/prerequisites/  #   Shared Docker install role
├── scripts/                  # Discovery and test runner scripts
├── requirements.yml          # Ansible Galaxy dependencies
├── requirements-test.txt     # Python test dependencies
├── Makefile                  # Local lint and test commands
│
├── security/                 # Access control & secrets management
├── ai/                       # AI & LLM platforms
├── automation/               # Workflow automation
├── monitoring/               # Observability & home automation
├── files/                    # Documents & file storage
├── desktop/                  # Desktop environment & utilities
├── dev-tools/                # Developer tooling
└── k8s/                      # Kubernetes cluster provisioning
```

Each playbook follows this structure:

```
<category>/<playbook>-setup/
├── setup.yml             # Playbook entry point (with vars_prompt wizard)
├── inventory/hosts.ini   # Inventory (localhost or dynamic via add_host)
├── group_vars/all.yml    # Playbook-scoped variables
└── roles/
    └── <role>/
        ├── tasks/main.yml
        ├── defaults/main.yml
        ├── templates/        # Jinja2 templates (optional)
        └── molecule/         # Molecule + Testinfra tests
```

---

## Testing

Every role is tested with [Molecule](https://ansible.readthedocs.io/projects/molecule/) + [Testinfra](https://testinfra.readthedocs.io/) across a tiered CI pipeline on GitHub Actions.

### Coverage

| Tier | Trigger | Driver | Roles | Time |
|------|---------|--------|-------|------|
| **Fast** | Every push to `main`, all PRs | Docker | 43 | ~5 min |
| **Heavy** | Nightly, PRs touching `security/` or `monitoring/` | Privileged Docker / QEMU | 9 | ~15 min |

```
53 / 57 roles tested (93% coverage)
 4 excluded: drives (needs block devices), cluster/argocd/headlamp (need running k8s)
```

### Running Tests Locally

```bash
# Install test dependencies
pip install -r requirements-test.txt
ansible-galaxy collection install -r requirements.yml

# Lint everything
make lint

# Test a specific role
make test-role ROLE_PATH=monitoring/kuma-setup/roles/kuma

# Test all Docker-driver roles
make test-all-docker

# Test all privileged-driver roles
make test-all-privileged
```

### Auto-Discovery

Adding a `molecule/` directory to any role automatically enrolls it in CI — no workflow edits needed. The [`discover-roles.sh`](./scripts/discover-roles.sh) script dynamically generates the GitHub Actions test matrix.

---

## Security Notes

- All containers bind to `127.0.0.1` (not `0.0.0.0`)
- All secrets use `no_log: true` in tasks
- Container images pinned to specific versions (no `:latest`)
- Infrastructure playbooks include UFW firewall, fail2ban, Authelia 2FA
- CI workflows scoped to `permissions: contents: read`
- Optional HashiCorp Vault integration for centralized secret management

---

## License

Private repository. All rights reserved.

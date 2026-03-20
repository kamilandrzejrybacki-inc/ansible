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
  <img src="https://img.shields.io/badge/playbooks-26-blue" alt="Playbooks">
</p>

---

## Overview

A collection of **26 self-contained Ansible playbook sets** organized into 5 categories, covering everything from desktop environments to production-grade homelab infrastructure. Each playbook is fully independent with its own inventory, roles, and variables — no global shared state.

**Key features:**

- Interactive setup wizards via `vars_prompt` — no manual file editing required
- Docker-first deployments with pinned image versions and localhost-only bindings
- Tiered CI/CD pipeline with Molecule + Testinfra covering 93% of roles
- Security by default: `no_log` on secrets, UFW firewall, fail2ban, Authelia 2FA

---

## Table of Contents

- [Desktop — Environment & Utilities](#desktop--environment--utilities)
- [Infrastructure — Networking, Storage & Security](#infrastructure--networking-storage--security)
- [Home Services — Self-Hosted Applications](#home-services--self-hosted-applications)
- [Dev Tools — AI & Developer Tooling](#dev-tools--ai--developer-tooling)
- [Kubernetes — Cluster Provisioning](#kubernetes--cluster-provisioning)
- [Getting Started](#getting-started)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Security](#security)

---

## Desktop — Environment & Utilities

Playbooks for configuring a daily-driver Linux desktop environment.

| Playbook | Description | Roles |
|----------|-------------|-------|
| [`desktop/i3-setup`](./desktop/i3-setup/) | i3wm desktop — packages, dotfiles, i3lock-color, fastfetch, styling | 5 |
| [`desktop/handy-setup`](./desktop/handy-setup/) | Handy speech-to-text — local voice transcription with configurable Whisper/Parakeet models | 1 |
| [`desktop/audiorelay-setup`](./desktop/audiorelay-setup/) | AudioRelay USB microphone — Android phone as mic via PulseAudio virtual sink | 1 |
| [`desktop/weylus-setup`](./desktop/weylus-setup/) | Weylus drawing tablet — Android phone as stylus-enabled tablet via adb + uinput | 2 |

### desktop/i3-setup

Configures a complete i3 tiling window manager environment from scratch.

- **Installs:** i3, i3status, i3-gaps, i3lock-color, fastfetch, custom dotfiles
- **Roles:** `dotfiles`, `i3`, `fastfetch`, `packages`, `styling`
- **Target:** localhost

### desktop/handy-setup

Installs and configures [Handy](https://github.com/Beydah/Handy), a local speech-to-text application.

- **Installs:** Handy `.deb` or AppImage, display server tools (`xdotool`/`wtype`), speech models
- **Prompts for:** installation method (deb/appimage), display server (x11/wayland), model size (Whisper Small → Large, Parakeet v2/v3), hotkey, microphone source, auto-start preference
- **Target:** localhost

### desktop/audiorelay-setup

Configures an Android phone connected over USB as a virtual microphone using [AudioRelay](https://audiorelay.net/).

- **Installs:** AudioRelay `.deb` (v0.27.5), PulseAudio virtual sink + remap-source modules
- **Configures:** `default.pa` or WirePlumber for persistence across reboots
- **Prerequisites:** USB tethering enabled on the Android device
- **Target:** localhost

### desktop/weylus-setup

Sets up [Weylus](https://github.com/H-M-H/Weylus) so an Android phone with S Pen can be used as a drawing tablet over USB.

- **Installs:** Weylus (v0.11.4), `adb`, uinput group membership, optional systemd user service
- **Configures:** USB port forwarding (`adb forward`), web interface (port 1701), WebSocket (port 9001)
- **Prerequisites:** USB debugging enabled on the Android device
- **Target:** localhost

---

## Infrastructure — Networking, Storage & Security

Playbooks for hardening and managing physical or virtual servers in the homelab.

| Playbook | Description | Roles |
|----------|-------------|-------|
| [`infrastructure/secure-homelab-access`](./infrastructure/secure-homelab-access/) | Secure remote access — WireGuard VPN, Authelia 2FA, Caddy HTTPS, Pi-hole DNS, CrowdSec, fail2ban, UFW, Cockpit, Homepage | 9 |
| [`infrastructure/librenms-setup`](./infrastructure/librenms-setup/) | LibreNMS network monitoring — Docker Compose stack, SNMP discovery, web UI | 2 |
| [`infrastructure/snmp-setup`](./infrastructure/snmp-setup/) | SNMP agent provisioning — snmpd, LibreNMS extend scripts, UFW rule on UDP 161 | — |
| [`infrastructure/nas-setup`](./infrastructure/nas-setup/) | NAS — mergerfs pool, SnapRAID parity, NFS shares, SMART monitoring, cron backups | 6 |
| [`infrastructure/lab-network`](./infrastructure/lab-network/) | Lab gateway — dnsmasq DHCP/DNS, NAT, static leases for k8s nodes | — |

### infrastructure/secure-homelab-access

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

**Secrets:** Automatically generated JWT, session, and encryption keys. All credentials written to `~/.homelab-credentials` (mode 0600).

### infrastructure/librenms-setup

Deploys [LibreNMS](https://www.librenms.org/) — a full-featured auto-discovering network monitoring system.

- **Stack:** LibreNMS (v26.3.1) + MariaDB + Redis via Docker Compose
- **Web UI:** port 8080
- **Configures:** SNMP community string, discovery network CIDRs, database password, timezone
- **Integrates with:** Caddy (for HTTPS), Cloudflare Tunnel, Homepage dashboard
- **Prompts for:** target host, SSH user, SNMP community, discovery networks (CIDR), DB password, timezone

### infrastructure/snmp-setup

Provisions the SNMP daemon on multiple target machines so they can be monitored by LibreNMS.

- **Installs:** `snmpd`, `snmp`, `libsnmp-dev`, LibreNMS extend scripts (from the official agent repo)
- **Configures:** `/etc/snmp/snmpd.conf` with read-only community string, `sysLocation`, `sysContact`, hardware/distro OID extensions
- **Opens:** UDP 161 via UFW
- **Prompts for:** comma-separated list of target IPs, SSH user, SNMP community string

### infrastructure/nas-setup

Configures a multi-drive NAS with software redundancy and network sharing.

- **Pool:** `mergerfs` (unified view of multiple drives at `/mnt/pool`)
- **Parity:** SnapRAID (nightly sync at 03:00, weekly scrub Sundays at 05:00)
- **Shares:** NFS export on the configured `nfs_allowed_network`
- **Monitoring:** `smartd` S.M.A.R.T. checks on all drives
- **Key vars:** `all_usb_drives`, `parity_drive_count`, `filesystem_type`, `mergerfs_mount`, `snapraid_sync_schedule`

### infrastructure/lab-network

Configures a server as a dedicated gateway for an isolated lab network (used alongside the Proxmox k8s setup).

- **Installs:** `dnsmasq` for DHCP and DNS
- **Configures:** WAN/LAN interface split, NAT/IP masquerade, static DHCP leases, `lab.home` domain, upstream DNS (1.1.1.1 / 8.8.8.8)
- **Key vars:** `lan_ip` (10.0.10.1), DHCP range (10.0.10.100–200), `lab_domain`

---

## Home Services — Self-Hosted Applications

Docker-based self-hosted services, each deployable independently.

| Playbook | Description | Roles |
|----------|-------------|-------|
| [`home-services/paperless-setup`](./home-services/paperless-setup/) | Paperless-ngx — document management, OCR, PostgreSQL + Redis | 2 |
| [`home-services/n8n-setup`](./home-services/n8n-setup/) | n8n — workflow automation, MCP integration support | 2 |
| [`home-services/stirling-pdf-setup`](./home-services/stirling-pdf-setup/) | Stirling-PDF — merge, split, convert, OCR, compress PDFs | 2 |
| [`home-services/vaultwarden-setup`](./home-services/vaultwarden-setup/) | Vaultwarden — self-hosted Bitwarden-compatible password manager | 2 |
| [`home-services/kuma-setup`](./home-services/kuma-setup/) | Uptime Kuma — HTTP/TCP/ping monitoring with status pages | 2 |
| [`home-services/homeassistant-setup`](./home-services/homeassistant-setup/) | Home Assistant — HACS, monitoring, dashboards, Discord/Slack alerts | 6 |
| [`home-services/bambulab-setup`](./home-services/bambulab-setup/) | BambuLab X1C — HA integration, AMS tracking, print alerts | 3 |
| [`home-services/seafile-setup`](./home-services/seafile-setup/) | Seafile — file sync & share, MariaDB + Memcached, Caddy proxy | 3 |
| [`home-services/dify-setup`](./home-services/dify-setup/) | Dify — LLM app platform with vector store and LiteLLM proxy | 3 |

### home-services/paperless-setup

Deploys [Paperless-ngx](https://docs.paperless-ngx.com/) for paperless document management with OCR.

- **Stack:** Paperless-ngx (v2.14.7), PostgreSQL 16.6, Redis 7.4
- **Web UI:** port 8000
- **Features:** automatic OCR on document ingestion, full-text search, tag/correspondent management

### home-services/n8n-setup

Deploys [n8n](https://n8n.io/) workflow automation.

- **Image:** `docker.n8n.io/n8nio/n8n` (persistent volume `n8n_data`)
- **Web UI:** port 5678
- **Configures:** owner account, MCP (Model Context Protocol) integration endpoint
- **Secure homelab integration (auto-detected):** if `~/.homelab-setup-vars.yml` is present, the playbook automatically adds a Cloudflare Tunnel DNS route, a Caddy reverse-proxy block, a Pi-hole local DNS record (`192.168.x.x n8n.<domain>`), and a Homepage dashboard entry. Falls back to `/etc/hosts` otherwise.
- **Bind address:** automatically set to `0.0.0.0` for remote deployments (so Caddy can reach it) and `127.0.0.1` for localhost deployments.

### home-services/stirling-pdf-setup

Deploys [Stirling-PDF](https://github.com/Stirling-Tools/Stirling-PDF) for comprehensive PDF manipulation.

- **Image:** `frooodle/s-pdf:0.36.5`
- **Web UI:** port 8080
- **Features:** merge, split, rotate, compress, convert, OCR, redact, watermark, sign

### home-services/vaultwarden-setup

Deploys [Vaultwarden](https://github.com/dani-garcia/vaultwarden), a lightweight self-hosted Bitwarden-compatible server.

- **Image:** `vaultwarden/server:1.32.7`
- **Web UI:** port 8080
- **Configures:** admin token, invitation-only or admin-controlled registration

### home-services/kuma-setup

Deploys [Uptime Kuma](https://github.com/louislam/uptime-kuma) for service uptime monitoring.

- **Image:** `louislam/uptime-kuma:1.23.16`
- **Web UI:** port 3001
- **Supports:** HTTP(S), TCP, DNS, ping, Docker container, and push monitors with status-page dashboards

### home-services/homeassistant-setup

Deploys [Home Assistant](https://www.home-assistant.io/) as the central smart home hub.

- **Image:** `ghcr.io/home-assistant/home-assistant:stable`
- **Web UI:** port 8123
- **Roles:** `docker`, `homeassistant`, `hacs`, `monitoring`, `dashboard`, `alerts`
- **Configures:** HACS (community integrations store), service monitoring (HTTP, ping, Docker), alerting via Discord/Slack/n8n webhooks
- **Alert thresholds:** CPU > 90%, disk > 85%

### home-services/bambulab-setup

Adds BambuLab X1C printer integration to an existing Home Assistant instance.

- **Integration:** [ha-bambulab](https://github.com/greghesp/ha-bambulab) via HACS
- **Tracks:** print status, remaining time, layer progress, AMS filament slots (4 slots), temperatures
- **Configures:** print-complete and error alerts via webhook, dedicated Lovelace dashboard card

### home-services/seafile-setup

Deploys [Seafile](https://www.seafile.com/) for self-hosted file synchronisation and sharing.

- **Stack:** Seafile MC (v11.0), MariaDB 10.11, Memcached, optional Caddy reverse proxy
- **Web UI:** port 8080
- **Roles:** `volume_select`, `seafile`, `caddy`
- **Prompts for:** storage volume selection, admin credentials, domain/HTTPS preference

### home-services/dify-setup

Deploys [Dify](https://dify.ai/), an open-source LLM application development platform.

- **Roles:** `prerequisites`, `litellm`, `dify`
- **Vector store:** Weaviate (default), with Qdrant, pgvector, or Chroma as alternatives
- **LiteLLM proxy (optional):** unifies access to Groq, Google Gemini, OpenRouter, Cerebras under one endpoint
- **Prompts for:** AI provider API keys, vector store selection, LiteLLM enable/disable

---

## Dev Tools — AI & Developer Tooling

Playbooks for setting up AI-augmented development environments.

| Playbook | Description | Roles |
|----------|-------------|-------|
| [`dev-tools/claude-code-setup`](./dev-tools/claude-code-setup/) | Claude Code CLI — plugins, MCP servers, Serena semantic analysis, custom rules | 6 |
| [`dev-tools/claude-n8n-mcp`](./dev-tools/claude-n8n-mcp/) | Connect Claude Code to an existing n8n instance via MCP | 1 |
| [`dev-tools/swe-af-setup`](./dev-tools/swe-af-setup/) | SWE-AF — autonomous software engineering agent runtime via Docker Compose | 2 |

### dev-tools/claude-code-setup

Provisions [Claude Code](https://claude.ai/code) with a curated set of plugins, MCP servers, and project rules.

- **Roles:** `claude_cli`, `claude_config`, `plugins`, `serena`, `mcp_servers`, `commands`
- **Installs:** Claude Code CLI, Serena (semantic code analysis via LSP), Gmail MCP server, custom slash commands
- **Deploys:** `~/.claude/rules/` (coding style, security, testing, git workflow), `~/.claude/settings.json`

### dev-tools/claude-n8n-mcp

Registers an n8n instance as an MCP (Model Context Protocol) server inside Claude Code.

- **Requires:** a running n8n deployment (use `home-services/n8n-setup` first)
- **Configures:** MCP server entry in Claude Code config with n8n endpoint URL and access token
- **Prompts for:** n8n host/port, MCP access token, scope (user or project)

### dev-tools/swe-af-setup

Deploys [SWE-AF](https://github.com/SWE-agent/SWE-agent), an autonomous software engineering agent framework.

- **Roles:** `prerequisites`, `swe_af`
- **Deployment:** Docker Compose
- **Supports:** Anthropic (direct), Claude OAuth, OpenRouter as AI providers; optional GitHub integration for PR workflows
- **Prompts for:** AI provider, API key, optional GitHub token

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

### k8s/kind-setup

Provisions a local multi-node [kind](https://kind.sigs.k8s.io/) (Kubernetes in Docker) cluster.

- **Installs:** Docker, kind (v0.27.0), kubectl
- **Default config:** 1 control plane + 2 workers, API port 6443, HTTP 80, HTTPS 443
- **Key vars:** `cluster_name`, `cluster_worker_count`

### k8s/k8s-full-setup

Orchestrates all local Kubernetes tooling in one run.

- Chains: `kind-setup` → `helm-setup` → `k9s-setup` → `headlamp-setup` → `argocd-setup`
- Use this for a complete local development cluster in a single command.

### k8s/proxmox-k8s-setup

Provisions a production-grade Kubernetes cluster on existing Proxmox hardware.

**Phases:**

1. **Template** — downloads Ubuntu 24.04 cloud-init image, creates a reusable Proxmox VM template (VMID 9000)
2. **VMs** — clones the template for each control-plane and worker node, configures networking
3. **Prerequisites** — installs containerd, kubeadm, kubectl on all nodes
4. **Control plane** — initialises the cluster with `kubeadm init`, deploys Calico CNI
5. **Workers** — joins worker nodes with the generated token

**Sample cluster config (from `group_vars/all.yml`):**

```
Control plane: 4 vCPU, 8 GB RAM, 50 GB disk — 10.10.10.10
Workers (×2): 4 vCPU, 8 GB RAM, 50 GB disk — 10.10.10.11–12
```

**Key vars:** `k8s_version` (1.32), `cni_plugin` (calico), `k8s_pod_network_cidr` (10.244.0.0/16), `proxmox_api_host`

### k8s/helm-setup

Installs [Helm](https://helm.sh/) v3.16.4 CLI. Can be run standalone or is included in `k8s-full-setup`.

### k8s/k9s-setup

Installs [k9s](https://k9scli.io/) v0.32.7 terminal UI for interactive cluster management.

### k8s/headlamp-setup

Deploys the [Headlamp](https://headlamp.dev/) Kubernetes dashboard via Helm chart (v0.25.0).

- **Web UI:** port 4466 (ClusterIP, access via `kubectl port-forward`)
- **Generates:** admin service account token for initial login

### k8s/argocd-setup

Deploys [ArgoCD](https://argo-cd.readthedocs.io/) v2.13.3 GitOps controller.

- **Namespace:** `argocd`
- **Web UI:** port 8443
- **Configures:** admin password, application CRD

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
ansible-playbook home-services/kuma-setup/setup.yml \
  -i home-services/kuma-setup/inventory/hosts.ini \
  --ask-become-pass
```

Each playbook's interactive wizard prompts for target host, SSH credentials, and service-specific configuration. No manual file editing required.

### Recommended First-Run Order

For a fresh homelab server:

```
1. infrastructure/secure-homelab-access   # Firewall, VPN, HTTPS, 2FA
2. infrastructure/snmp-setup              # SNMP on all target machines
3. infrastructure/librenms-setup          # Network monitoring
4. home-services/*                        # Any services you want
```

For a local development machine:

```
1. desktop/i3-setup                       # Window manager
2. dev-tools/claude-code-setup            # AI coding assistant
3. k8s/k8s-full-setup                    # Local Kubernetes
```

---

## Project Structure

```
ansible/
├── .github/workflows/       # CI/CD pipelines (fast + heavy tiers)
├── scripts/                  # Discovery and test runner scripts
├── requirements.yml          # Ansible Galaxy dependencies
├── requirements-test.txt     # Python test dependencies
├── Makefile                  # Local lint and test commands
│
└── <category>/
    └── <playbook>-setup/
        ├── setup.yml             # Playbook entry point (with vars_prompt wizard)
        ├── inventory/hosts.ini   # Inventory (localhost or dynamic via add_host)
        ├── group_vars/all.yml    # Playbook-scoped variables
        └── roles/
            └── <role>/
                ├── tasks/main.yml
                ├── defaults/main.yml
                ├── meta/main.yml
                ├── templates/        # Jinja2 templates (optional)
                ├── files/            # Static files (optional)
                ├── handlers/         # Event handlers (optional)
                └── molecule/         # Molecule + Testinfra tests
                    └── default/
                        ├── molecule.yml
                        ├── converge.yml
                        ├── vars/test-vars.yml
                        └── tests/test_default.py
```

---

## Testing

Every role is tested with [Molecule](https://ansible.readthedocs.io/projects/molecule/) + [Testinfra](https://testinfra.readthedocs.io/) across a tiered CI pipeline on GitHub Actions.

### Coverage

| Tier | Trigger | Driver | Roles | Time |
|------|---------|--------|-------|------|
| **Fast** | Every push to `main`, all PRs | Docker | 43 | ~5 min |
| **Heavy** | Nightly, PRs touching `infrastructure/` | Privileged Docker / QEMU | 9 | ~15 min |

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
make test-role ROLE_PATH=home-services/kuma-setup/roles/kuma

# Test all Docker-driver roles
make test-all-docker

# Test all privileged-driver roles
make test-all-privileged
```

### Auto-Discovery

Adding a `molecule/` directory to any role automatically enrolls it in CI — no workflow edits needed. The [`discover-roles.sh`](./scripts/discover-roles.sh) script dynamically generates the GitHub Actions test matrix.

---

## Security

- All containers bind to `127.0.0.1` (not `0.0.0.0`)
- All secrets use `no_log: true` in tasks
- Container images pinned to specific versions (no `:latest`)
- Infrastructure playbooks include UFW firewall, fail2ban, Authelia 2FA
- CI workflows scoped to `permissions: contents: read`

---

## License

Private repository. All rights reserved.

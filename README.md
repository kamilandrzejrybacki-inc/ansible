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
  <img src="https://img.shields.io/badge/playbooks-20-blue" alt="Playbooks">
</p>

---

## Overview

A collection of **20 self-contained Ansible playbook sets** organized into 5 categories, covering everything from desktop environments to production-grade homelab infrastructure. Each playbook is fully independent with its own inventory, roles, and variables — no global shared state.

**Key features:**

- Interactive setup wizards via `vars_prompt` — no manual file editing required
- Docker-first deployments with pinned image versions and localhost-only bindings
- Tiered CI/CD pipeline with Molecule + Testinfra covering 93% of roles
- Security by default: `no_log` on secrets, UFW firewall, fail2ban, Authelia 2FA

## Playbook Sets

### Desktop — Environment & Utilities

| Playbook | Description | Roles |
|----------|-------------|-------|
| [`desktop/i3-setup`](./desktop/i3-setup/) | i3wm desktop — packages, dotfiles, i3lock-color, fastfetch, styling | 5 |
| [`desktop/handy-setup`](./desktop/handy-setup/) | Handy speech-to-text — local voice transcription with model predownload | 1 |

### Dev Tools — AI & Developer Tooling

| Playbook | Description | Roles |
|----------|-------------|-------|
| [`dev-tools/claude-code-setup`](./dev-tools/claude-code-setup/) | Claude Code CLI — plugins, MCP servers, Serena, custom rules | 6 |
| [`dev-tools/claude-n8n-mcp`](./dev-tools/claude-n8n-mcp/) | Connect Claude Code to an existing n8n instance via MCP | 1 |

### Home Services — Self-Hosted Applications

| Playbook | Description | Roles |
|----------|-------------|-------|
| [`home-services/n8n-setup`](./home-services/n8n-setup/) | n8n workflow automation — Docker, owner account creation | 2 |
| [`home-services/homeassistant-setup`](./home-services/homeassistant-setup/) | Home Assistant — Docker, HACS, monitoring, dashboards, webhook alerts | 6 |
| [`home-services/seafile-setup`](./home-services/seafile-setup/) | Seafile cloud storage — Docker Compose, Caddy reverse proxy | 3 |
| [`home-services/kuma-setup`](./home-services/kuma-setup/) | Uptime Kuma — Docker, health checks, status pages | 2 |
| [`home-services/vaultwarden-setup`](./home-services/vaultwarden-setup/) | Vaultwarden password manager — Docker, admin-only registration | 2 |
| [`home-services/paperless-setup`](./home-services/paperless-setup/) | Paperless-ngx — Docker Compose, Redis, PostgreSQL | 2 |
| [`home-services/stirling-pdf-setup`](./home-services/stirling-pdf-setup/) | Stirling-PDF toolkit — merge, split, convert, OCR, compress | 2 |
| [`home-services/bambulab-setup`](./home-services/bambulab-setup/) | BambuLab X1C — Home Assistant integration, alerts, dashboard | 3 |

### Kubernetes — Cluster Provisioning

| Playbook | Description | Roles |
|----------|-------------|-------|
| [`k8s/kind-setup`](./k8s/kind-setup/) | Local Kubernetes — Docker, kind, kubectl, multi-node cluster | 3 |
| [`k8s/helm-setup`](./k8s/helm-setup/) | Helm 3 CLI | 1 |
| [`k8s/k9s-setup`](./k8s/k9s-setup/) | k9s terminal UI | 1 |
| [`k8s/headlamp-setup`](./k8s/headlamp-setup/) | Headlamp dashboard — Helm chart, admin token | 1 |
| [`k8s/argocd-setup`](./k8s/argocd-setup/) | ArgoCD GitOps controller — manifests, admin password | 1 |
| [`k8s/k8s-full-setup`](./k8s/k8s-full-setup/) | Full stack — kind + Helm + k9s + Headlamp + ArgoCD | 0* |

### Infrastructure — Networking, Storage & Security

| Playbook | Description | Roles |
|----------|-------------|-------|
| [`infrastructure/secure-homelab-access`](./infrastructure/secure-homelab-access/) | Secure remote access — WireGuard, Authelia 2FA, Caddy HTTPS, Pi-hole DNS, fail2ban, UFW, Cockpit | 9 |
| [`infrastructure/nas-setup`](./infrastructure/nas-setup/) | NAS — mergerfs pool, SnapRAID parity, NFS shares, SMART monitoring, backups | 6 |

<sub>* Orchestrator playbook — chains sub-playbooks, no roles of its own.</sub>

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

## Security

- All containers bind to `127.0.0.1` (not `0.0.0.0`)
- All secrets use `no_log: true` in tasks
- Container images pinned to specific versions (no `:latest`)
- Infrastructure playbooks include UFW firewall, fail2ban, Authelia 2FA
- CI workflows scoped to `permissions: contents: read`

## License

Private repository. All rights reserved.

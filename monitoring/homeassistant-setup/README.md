# homeassistant-setup

Ansible playbook to deploy Home Assistant in Docker with monitoring integrations, Lovelace dashboards, and webhook-based alerting for your homelab.

## What it does

1. **Installs Docker** on the target host (skips if already present)
2. **Deploys Home Assistant** container with persistent storage
3. **Installs HACS** (Home Assistant Community Store) for community integrations
4. **Configures monitoring** — system resources, HTTP service health, ping checks, Docker container status
5. **Sets up a Lovelace dashboard** with gauges and graphs for all monitored resources
6. **Configures alerting automations** that POST to a webhook (Discord, Slack, n8n, etc.) when services go down or resources spike

## Usage

```bash
# Install required collection
ansible-galaxy collection install community.docker

# Run the playbook
ansible-playbook homeassistant-setup/setup.yml \
  -i homeassistant-setup/inventory/hosts.ini \
  --ask-become-pass
```

The playbook will prompt for:

| Prompt | Description |
|---|---|
| Home Assistant host IP | Target machine for deployment |
| SSH user | SSH user on the target |
| HA port | Home Assistant web port (default: 8123) |
| Webhook URL | Alert destination — Discord/Slack/n8n webhook (optional) |
| Ping hosts | Comma-separated `name:ip` pairs to monitor (optional) |
| n8n health URL | n8n healthcheck endpoint to monitor (optional) |

## Post-install: HACS Activation

After the playbook completes, activate HACS in the Home Assistant UI:

1. Navigate to **Settings → Devices & Services**
2. Click **+ Add Integration** and search for **HACS**
3. Acknowledge the disclaimers
4. Authorize with GitHub — you'll receive a code to enter at [github.com/login/device](https://github.com/login/device)

HACS will then appear in the HA sidebar and can be used to install community integrations.

## Monitored service types

Services are defined in `group_vars/all.yml` or built dynamically from prompts:

```yaml
monitored_services:
  - name: n8n
    type: http
    url: "http://192.168.1.10:5678/healthz"

  - name: router
    type: ping
    host: 192.168.1.1

  - name: n8n
    type: docker
    container_name: n8n
```

| Type | What it does |
|---|---|
| `http` | REST sensor — polls URL, reports online/offline |
| `ping` | Binary sensor — ICMP ping, reports connected/disconnected |
| `docker` | Command line sensor — checks `docker inspect` status |

## Alerting

When a webhook URL is provided, automations fire on:

- **Service offline** — HTTP service unreachable for 2 minutes
- **Host unreachable** — Ping fails for 2 minutes
- **Container stopped** — Docker container exits running state
- **High CPU** — Processor usage above threshold (default: 90%) for 5 minutes
- **High disk** — Disk usage above threshold (default: 85%)

Thresholds are configurable in `group_vars/all.yml`.

## Roles

| Role | Description |
|---|---|
| `docker` | Install Docker engine via official APT repository |
| `homeassistant` | Deploy HA container with persistent volume |
| `hacs` | Install HACS into custom_components |
| `monitoring` | Template `configuration.yaml` with integrations and sensors |
| `dashboard` | Generate Lovelace YAML dashboard for monitoring |
| `alerts` | Create HA automations for webhook notifications |

## Structure

```
homeassistant-setup/
├── setup.yml
├── inventory/
│   └── hosts.ini
├── group_vars/
│   └── all.yml
└── roles/
    ├── docker/
    ├── homeassistant/
    ├── hacs/
    ├── monitoring/
    ├── dashboard/
    └── alerts/
```

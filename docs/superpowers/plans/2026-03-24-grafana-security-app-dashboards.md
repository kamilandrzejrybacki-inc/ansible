# Grafana Security+Vault & Application Services Dashboards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two Grafana dashboards — Security+Vault (Pi-hole, WireGuard, Caddy, Authelia, CrowdSec, Vault) and Application Services (HTTP probe availability for n8n, Paperless, Netbox, Outline, Vaultwarden, Seafile, Dify).

**Architecture:** Pi-hole and WireGuard exporters are added as sidecar containers alongside their services in the secure-homelab-access role. All other security services (Caddy, Authelia, CrowdSec, Vault) already expose `/metrics` natively. Application services are monitored via Alloy's built-in blackbox exporter using HTTP probes. New conditional scrape blocks are appended to `alloy.river.j2`; two new dashboard JSON files are provisioned via Grafana's file provider.

**Tech Stack:** Ansible (`community.docker.docker_container`), Grafana Alloy v1.5.1 River config (Jinja2 template), Grafana 11 JSON provisioning, `ekofr/pihole-exporter:v0.4.0`, `mindflavor/prometheus-wireguard-exporter:3.6.6`

**Spec:** `docs/superpowers/specs/2026-03-24-grafana-security-app-dashboards-design.md`

---

## File Map

| File | Change |
|---|---|
| `security/secure-homelab-access/roles/pihole/defaults/main.yml` | Add `pihole_exporter_enabled: false` |
| `security/secure-homelab-access/roles/pihole/tasks/main.yml` | Add pihole-exporter container task |
| `security/secure-homelab-access/roles/wireguard/defaults/main.yml` | Add `wireguard_exporter_enabled: false` |
| `security/secure-homelab-access/roles/wireguard/tasks/main.yml` | Add wireguard-exporter container task |
| `security/secure-homelab-access/roles/caddy/tasks/main.yml` | Add port 2019 + UFW rule for admin metrics |
| `security/secure-homelab-access/roles/caddy/templates/Caddyfile.j2` | Add `servers { metrics }` + `admin 0.0.0.0:2019` to global block |
| `monitoring/grafana-stack-setup/roles/grafana-stack/templates/docker-compose.yml.j2` | Add `VAULT_METRICS_TOKEN` env var to Alloy service |
| `monitoring/grafana-stack-setup/group_vars/all.yml` | Add 14 new variables (metrics hosts/ports/token, probe URLs) |
| `monitoring/grafana-stack-setup/roles/grafana-stack/templates/alloy.river.j2` | Add 6 security scrape blocks + 1 blackbox block |
| `monitoring/grafana-stack-setup/roles/grafana-stack/tasks/main.yml` | Add `security-vault.json` + `app-services.json` to copy loop |
| `monitoring/grafana-stack-setup/roles/grafana-stack/files/dashboards/security-vault.json` | Create — 21 panels, 5 rows |
| `monitoring/grafana-stack-setup/roles/grafana-stack/files/dashboards/app-services.json` | Create — 11 panels, 4 rows |

---

## Task 1: Pi-hole exporter defaults and container task

**Files:**
- Modify: `security/secure-homelab-access/roles/pihole/defaults/main.yml`
- Modify: `security/secure-homelab-access/roles/pihole/tasks/main.yml`

- [ ] **Step 1: Add exporter flag to pihole defaults**

Append to `security/secure-homelab-access/roles/pihole/defaults/main.yml`:
```yaml
pihole_exporter_enabled: false
```

- [ ] **Step 2: Add exporter container task**

Append to the end of `security/secure-homelab-access/roles/pihole/tasks/main.yml`:
```yaml
- name: Deploy Pi-hole Prometheus exporter
  community.docker.docker_container:
    name: pihole-exporter
    image: "ekofr/pihole-exporter:v0.4.0"
    state: started
    restart_policy: unless-stopped
    env:
      PIHOLE_HOSTNAME: "pihole"
    ports:
      - "9617:9617"
    networks:
      - name: "{{ docker_network_name }}"
  when: pihole_exporter_enabled | default(false) | bool
```

- [ ] **Step 3: Lint**

```bash
cd /home/kamil-rybacki/Code/ansible
ansible-lint security/secure-homelab-access/roles/pihole/
```
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add security/secure-homelab-access/roles/pihole/
git commit -m "feat(pihole): add optional Prometheus exporter sidecar"
```

---

## Task 2: WireGuard exporter defaults and container task

**Files:**
- Modify: `security/secure-homelab-access/roles/wireguard/defaults/main.yml`
- Modify: `security/secure-homelab-access/roles/wireguard/tasks/main.yml`

- [ ] **Step 1: Add exporter flag to wireguard defaults**

Append to `security/secure-homelab-access/roles/wireguard/defaults/main.yml`:
```yaml
wireguard_exporter_enabled: false
```

- [ ] **Step 2: Add exporter container task**

Append to the end of `security/secure-homelab-access/roles/wireguard/tasks/main.yml`:
```yaml
- name: Deploy WireGuard Prometheus exporter
  community.docker.docker_container:
    name: wireguard-exporter
    image: "mindflavor/prometheus-wireguard-exporter:3.6.6"
    state: started
    restart_policy: unless-stopped
    network_mode: host
    capabilities:
      - NET_ADMIN
  when: wireguard_exporter_enabled | default(false) | bool
```

Note: `network_mode: host` gives the exporter access to the `wg0` kernel interface created by wg-easy. The exporter reads stats via `wg show dump` — it does not need the `wg0.json` config file.

- [ ] **Step 3: Lint**

```bash
ansible-lint security/secure-homelab-access/roles/wireguard/
```
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add security/secure-homelab-access/roles/wireguard/
git commit -m "feat(wireguard): add optional Prometheus exporter sidecar"
```

---

## Task 3: Enable Caddy admin metrics endpoint

**Files:**
- Modify: `security/secure-homelab-access/roles/caddy/templates/Caddyfile.j2`
- Modify: `security/secure-homelab-access/roles/caddy/tasks/main.yml`

- [ ] **Step 1: Enable metrics + admin endpoint in Caddyfile global section**

In `security/secure-homelab-access/roles/caddy/templates/Caddyfile.j2`, replace the existing conditional `servers` block (lines 12–16) and add `admin 0.0.0.0:2019`. Two things are needed: `servers { metrics }` activates the Prometheus metrics collector; `admin 0.0.0.0:2019` makes the admin interface (which serves `/metrics`) reachable from outside the container.

Replace this section in the global block:
```
{% if cf_tunnel_name | default('') %}
	servers {
		trusted_proxies static private_ranges
	}
{% endif %}
}
```

With:
```
{% if cf_tunnel_name | default('') %}
	servers {
		trusted_proxies static private_ranges
		metrics
	}
{% else %}
	servers {
		metrics
	}
{% endif %}

	admin 0.0.0.0:2019
}
```

This ensures `metrics` is always enabled regardless of the Cloudflare tunnel mode.

- [ ] **Step 2: Expose port 2019 from Caddy container**

In `security/secure-homelab-access/roles/caddy/tasks/main.yml`, find the `ports:` list for the Caddy docker_container task (currently has `"80:80"` and `"443:443"`). Add:
```yaml
      - "127.0.0.1:2019:2019"
```
Bind to `127.0.0.1` only on the host — Alloy on Node 2 will access it via LAN IP (10.0.0.1), but we protect it with a UFW rule rather than exposing it broadly.

Wait — `127.0.0.1:2019` on the host is only accessible locally, not from Node 2. For cross-node scraping, bind to `0.0.0.0:2019` and protect with UFW:
```yaml
      - "0.0.0.0:2019:2019"
```

- [ ] **Step 3: Add UFW rule to allow Caddy metrics from LAN**

Append to `security/secure-homelab-access/roles/caddy/tasks/main.yml` after the existing UFW tasks (or add a new block at the end):
```yaml
- name: Allow Caddy metrics from LAN (10.0.0.0/8)
  community.general.ufw:
    rule: allow
    port: "2019"
    proto: tcp
    src: 10.0.0.0/8
    comment: "Caddy admin metrics for Alloy"

- name: Allow Caddy metrics from LAN (192.168.0.0/16)
  community.general.ufw:
    rule: allow
    port: "2019"
    proto: tcp
    src: 192.168.0.0/16
    comment: "Caddy admin metrics for Alloy"
```

- [ ] **Step 4: Lint**

```bash
ansible-lint security/secure-homelab-access/roles/caddy/
```
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add security/secure-homelab-access/roles/caddy/
git commit -m "feat(caddy): expose admin metrics endpoint on port 2019"
```

---

## Task 4: Add group_vars for all new scrape targets

**Files:**
- Modify: `monitoring/grafana-stack-setup/group_vars/all.yml`

- [ ] **Step 1: Append security metrics variables**

Append to `monitoring/grafana-stack-setup/group_vars/all.yml`:
```yaml
# Security service metrics — set host to Node 1 LAN IP (e.g. 10.0.0.1) to enable scraping
caddy_metrics_host: ""
caddy_metrics_port: 2019

authelia_metrics_host: ""
authelia_metrics_port: 9959

crowdsec_metrics_host: ""
crowdsec_metrics_port: 6060

vault_metrics_host: ""
vault_metrics_port: 8200
vault_metrics_token: ""   # Vault token with sys/metrics read policy (see spec prerequisites)

pihole_exporter_host: ""
pihole_exporter_port: 9617

wireguard_exporter_host: ""
wireguard_exporter_port: 9586

# Application service probe URLs — set to internal URL (e.g. http://10.0.0.1:PORT) to enable probe
probe_n8n_url: ""
probe_paperless_url: ""
probe_netbox_url: ""
probe_outline_url: ""
probe_vaultwarden_url: ""
probe_seafile_url: ""
probe_dify_url: ""
```

- [ ] **Step 2: Lint**

```bash
ansible-lint monitoring/grafana-stack-setup/
```
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add monitoring/grafana-stack-setup/group_vars/all.yml
git commit -m "feat(grafana): add security metrics and probe URL variables"
```

---

## Task 5: Add security scrape blocks to Alloy config

**Files:**
- Modify: `monitoring/grafana-stack-setup/roles/grafana-stack/templates/alloy.river.j2`

- [ ] **Step 1: Add security scrape blocks**

Insert the following block in `alloy.river.j2` **before** the `// ── Remote write endpoints` comment (same pattern as the existing `openclaw` block):

```jinja2
// ── Security service metrics ─────────────────────────────────────────────────
{% if caddy_metrics_host | default('') | length > 0 %}
prometheus.scrape "caddy" {
  targets         = [{"__address__" = "{{ caddy_metrics_host }}:{{ caddy_metrics_port }}"}]
  metrics_path    = "/metrics"
  forward_to      = [prometheus.relabel.caddy_labels.receiver]
  scrape_interval = "60s"
}

prometheus.relabel "caddy_labels" {
  forward_to = [prometheus.remote_write.mimir.receiver]
  rule { target_label = "job";     replacement = "security" }
  rule { target_label = "service"; replacement = "caddy"    }
  rule { target_label = "instance"; replacement = env("HOSTNAME") }
}
{% endif %}

{% if authelia_metrics_host | default('') | length > 0 %}
prometheus.scrape "authelia" {
  targets         = [{"__address__" = "{{ authelia_metrics_host }}:{{ authelia_metrics_port }}"}]
  metrics_path    = "/metrics"
  forward_to      = [prometheus.relabel.authelia_labels.receiver]
  scrape_interval = "60s"
}

prometheus.relabel "authelia_labels" {
  forward_to = [prometheus.remote_write.mimir.receiver]
  rule { target_label = "job";      replacement = "security" }
  rule { target_label = "service";  replacement = "authelia" }
  rule { target_label = "instance"; replacement = env("HOSTNAME") }
}
{% endif %}

{% if crowdsec_metrics_host | default('') | length > 0 %}
prometheus.scrape "crowdsec" {
  targets         = [{"__address__" = "{{ crowdsec_metrics_host }}:{{ crowdsec_metrics_port }}"}]
  metrics_path    = "/metrics"
  forward_to      = [prometheus.relabel.crowdsec_labels.receiver]
  scrape_interval = "60s"
}

prometheus.relabel "crowdsec_labels" {
  forward_to = [prometheus.remote_write.mimir.receiver]
  rule { target_label = "job";      replacement = "security"  }
  rule { target_label = "service";  replacement = "crowdsec"  }
  rule { target_label = "instance"; replacement = env("HOSTNAME") }
}
{% endif %}

{% if vault_metrics_host | default('') | length > 0 %}
prometheus.scrape "vault" {
  targets      = [{"__address__" = "{{ vault_metrics_host }}:{{ vault_metrics_port }}"}]
  metrics_path = "/v1/sys/metrics"
  params       = {"format" = ["prometheus"]}
  authorization {
    type        = "Bearer"
    credentials = env("VAULT_METRICS_TOKEN")
  }
  forward_to      = [prometheus.relabel.vault_labels.receiver]
  scrape_interval = "60s"
}

prometheus.relabel "vault_labels" {
  forward_to = [prometheus.remote_write.mimir.receiver]
  rule { target_label = "job";      replacement = "security" }
  rule { target_label = "service";  replacement = "vault"    }
  rule { target_label = "instance"; replacement = env("HOSTNAME") }
}
{% endif %}

{% if pihole_exporter_host | default('') | length > 0 %}
prometheus.scrape "pihole" {
  targets         = [{"__address__" = "{{ pihole_exporter_host }}:{{ pihole_exporter_port }}"}]
  metrics_path    = "/metrics"
  forward_to      = [prometheus.relabel.pihole_labels.receiver]
  scrape_interval = "60s"
}

prometheus.relabel "pihole_labels" {
  forward_to = [prometheus.remote_write.mimir.receiver]
  rule { target_label = "job";      replacement = "security" }
  rule { target_label = "service";  replacement = "pihole"   }
  rule { target_label = "instance"; replacement = env("HOSTNAME") }
}
{% endif %}

{% if wireguard_exporter_host | default('') | length > 0 %}
prometheus.scrape "wireguard" {
  targets         = [{"__address__" = "{{ wireguard_exporter_host }}:{{ wireguard_exporter_port }}"}]
  metrics_path    = "/metrics"
  forward_to      = [prometheus.relabel.wireguard_labels.receiver]
  scrape_interval = "60s"
}

prometheus.relabel "wireguard_labels" {
  forward_to = [prometheus.remote_write.mimir.receiver]
  rule { target_label = "job";      replacement = "security"   }
  rule { target_label = "service";  replacement = "wireguard"  }
  rule { target_label = "instance"; replacement = env("HOSTNAME") }
}
{% endif %}
```

- [ ] **Step 2: Inject VAULT_METRICS_TOKEN into Alloy container**

The Vault scrape block uses `env("VAULT_METRICS_TOKEN")` to avoid writing the token into the (mode 0644) config file. Add the env var to the Alloy service in `monitoring/grafana-stack-setup/roles/grafana-stack/templates/docker-compose.yml.j2`.

Find the `alloy:` service block (currently has no `environment:` section). Add it:
```yaml
  alloy:
    image: {{ alloy_image }}
    container_name: alloy
    restart: {{ grafana_restart_policy }}
    environment:
{% if vault_metrics_token | default('') | length > 0 %}
      VAULT_METRICS_TOKEN: "{{ vault_metrics_token }}"
{% endif %}
    volumes:
```

This conditionally sets the env var only when the token is configured. When `vault_metrics_token` is empty (default), the env block is omitted entirely.

- [ ] **Step 3: Lint**

```bash
ansible-lint monitoring/grafana-stack-setup/
```
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add monitoring/grafana-stack-setup/roles/grafana-stack/templates/alloy.river.j2
git add monitoring/grafana-stack-setup/roles/grafana-stack/templates/docker-compose.yml.j2
git commit -m "feat(alloy): add conditional security service scrape blocks"
```

---

## Task 6: Add blackbox probe block to Alloy config

**Files:**
- Modify: `monitoring/grafana-stack-setup/roles/grafana-stack/templates/alloy.river.j2`

- [ ] **Step 1: Add blackbox exporter block**

Append the following to `alloy.river.j2`, immediately after the security scrape blocks (still before `// ── Remote write endpoints`):

```jinja2
// ── Blackbox HTTP probes ──────────────────────────────────────────────────────
{% set _probe_list = [] %}
{% if probe_n8n_url | default('') | length > 0 %}{% set _ = _probe_list.append(('n8n', probe_n8n_url)) %}{% endif %}
{% if probe_paperless_url | default('') | length > 0 %}{% set _ = _probe_list.append(('paperless', probe_paperless_url)) %}{% endif %}
{% if probe_netbox_url | default('') | length > 0 %}{% set _ = _probe_list.append(('netbox', probe_netbox_url)) %}{% endif %}
{% if probe_outline_url | default('') | length > 0 %}{% set _ = _probe_list.append(('outline', probe_outline_url)) %}{% endif %}
{% if probe_vaultwarden_url | default('') | length > 0 %}{% set _ = _probe_list.append(('vaultwarden', probe_vaultwarden_url)) %}{% endif %}
{% if probe_seafile_url | default('') | length > 0 %}{% set _ = _probe_list.append(('seafile', probe_seafile_url)) %}{% endif %}
{% if probe_dify_url | default('') | length > 0 %}{% set _ = _probe_list.append(('dify', probe_dify_url)) %}{% endif %}
{% if _probe_list | length > 0 %}
prometheus.exporter.blackbox "apps" {
  config = "modules:\n  http_2xx:\n    prober: http\n    timeout: 10s\n    http:\n      preferred_ip_protocol: ip4"

{% for name, url in _probe_list %}
  target {
    name    = "{{ name }}"
    address = "{{ url }}"
    module  = "http_2xx"
  }
{% endfor %}
}

prometheus.scrape "blackbox" {
  targets         = prometheus.exporter.blackbox.apps.targets
  forward_to      = [prometheus.relabel.blackbox_labels.receiver]
  scrape_interval = "60s"
}

prometheus.relabel "blackbox_labels" {
  forward_to = [prometheus.remote_write.mimir.receiver]

  // The blackbox exporter sets the target's name field as the "name" label.
  // Copy it into "service" so panels can filter by service name (not URL).
  rule {
    source_labels = ["name"]
    target_label  = "service"
  }
  rule { target_label = "job";      replacement = "blackbox"       }
  rule { target_label = "instance"; replacement = env("HOSTNAME")  }
}
{% endif %}
```

- [ ] **Step 2: Lint**

```bash
ansible-lint monitoring/grafana-stack-setup/
```
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add monitoring/grafana-stack-setup/roles/grafana-stack/templates/alloy.river.j2
git commit -m "feat(alloy): add blackbox HTTP probe block for app services"
```

---

## Task 7: Create security-vault.json dashboard

**Files:**
- Create: `monitoring/grafana-stack-setup/roles/grafana-stack/files/dashboards/security-vault.json`

- [ ] **Step 1: Create the dashboard JSON file**

Create `monitoring/grafana-stack-setup/roles/grafana-stack/files/dashboards/security-vault.json` with the following content:

```json
{
  "__inputs": [],
  "__requires": [
    {"type": "grafana", "id": "grafana", "name": "Grafana", "version": "10.0.0"},
    {"type": "datasource", "id": "prometheus", "name": "Prometheus", "version": "1.0.0"}
  ],
  "annotations": {"list": []},
  "description": "Security services monitoring: Pi-hole, WireGuard, Caddy, Authelia, CrowdSec, Vault",
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 1,
  "id": null,
  "links": [],
  "panels": [
    {"collapsed": false, "gridPos": {"h": 1, "w": 24, "x": 0, "y": 0}, "id": 1, "title": "Overview", "type": "row"},
    {
      "datasource": {"type": "prometheus", "uid": "mimir"},
      "fieldConfig": {"defaults": {"color": {"mode": "thresholds"}, "mappings": [], "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": null}]}, "unit": "short"}, "overrides": []},
      "gridPos": {"h": 4, "w": 6, "x": 0, "y": 1}, "id": 2,
      "options": {"colorMode": "value", "graphMode": "area", "justifyMode": "auto", "orientation": "auto", "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false}, "textMode": "auto"},
      "targets": [{"datasource": {"type": "prometheus", "uid": "mimir"}, "expr": "increase(pihole_dns_queries_all_types_total{job=\"security\", service=\"pihole\"}[24h])", "instant": true, "refId": "A"}],
      "title": "DNS Queries (24h)", "type": "stat"
    },
    {
      "datasource": {"type": "prometheus", "uid": "mimir"},
      "fieldConfig": {"defaults": {"color": {"mode": "thresholds"}, "mappings": [], "max": 100, "min": 0, "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": null}, {"color": "yellow", "value": 20}, {"color": "red", "value": 50}]}, "unit": "percent"}, "overrides": []},
      "gridPos": {"h": 4, "w": 6, "x": 6, "y": 1}, "id": 3,
      "options": {"colorMode": "value", "graphMode": "none", "justifyMode": "auto", "orientation": "auto", "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false}, "textMode": "auto"},
      "targets": [{"datasource": {"type": "prometheus", "uid": "mimir"}, "expr": "pihole_ads_percentage_today{job=\"security\", service=\"pihole\"}", "instant": true, "refId": "A"}],
      "title": "DNS Blocked %", "type": "stat"
    },
    {
      "datasource": {"type": "prometheus", "uid": "mimir"},
      "fieldConfig": {"defaults": {"color": {"mode": "thresholds"}, "mappings": [], "thresholds": {"mode": "absolute", "steps": [{"color": "red", "value": null}, {"color": "yellow", "value": 1}, {"color": "green", "value": 2}]}, "unit": "short"}, "overrides": []},
      "gridPos": {"h": 4, "w": 6, "x": 12, "y": 1}, "id": 4,
      "options": {"colorMode": "value", "graphMode": "none", "justifyMode": "auto", "orientation": "auto", "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false}, "textMode": "auto"},
      "targets": [{"datasource": {"type": "prometheus", "uid": "mimir"}, "expr": "count(wireguard_peer_last_handshake_seconds{job=\"security\", service=\"wireguard\"} > (time() - 300)) or vector(0)", "instant": true, "refId": "A"}],
      "title": "VPN Peers Connected", "type": "stat"
    },
    {
      "datasource": {"type": "prometheus", "uid": "mimir"},
      "fieldConfig": {"defaults": {"color": {"mode": "thresholds"}, "mappings": [], "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": null}, {"color": "yellow", "value": 1}, {"color": "red", "value": 10}]}, "unit": "short"}, "overrides": []},
      "gridPos": {"h": 4, "w": 6, "x": 18, "y": 1}, "id": 5,
      "options": {"colorMode": "background", "graphMode": "none", "justifyMode": "auto", "orientation": "auto", "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false}, "textMode": "auto"},
      "targets": [{"datasource": {"type": "prometheus", "uid": "mimir"}, "expr": "cs_active_decisions{job=\"security\", service=\"crowdsec\"} or vector(0)", "instant": true, "refId": "A"}],
      "title": "CrowdSec Active Bans", "type": "stat"
    },
    {"collapsed": false, "gridPos": {"h": 1, "w": 24, "x": 0, "y": 5}, "id": 6, "title": "Pi-hole", "type": "row"},
    {
      "datasource": {"type": "prometheus", "uid": "mimir"},
      "fieldConfig": {"defaults": {"color": {"mode": "palette-classic"}, "custom": {"drawStyle": "line", "fillOpacity": 10, "lineWidth": 1, "showPoints": "never", "spanNulls": false}, "mappings": [], "unit": "reqps"}, "overrides": []},
      "gridPos": {"h": 8, "w": 14, "x": 0, "y": 6}, "id": 7,
      "options": {"legend": {"calcs": ["mean", "lastNotNull"], "displayMode": "table", "placement": "bottom", "showLegend": true}, "tooltip": {"mode": "multi", "sort": "desc"}},
      "targets": [
        {"datasource": {"type": "prometheus", "uid": "mimir"}, "expr": "rate(pihole_dns_queries_all_types_total{job=\"security\", service=\"pihole\"}[5m])", "legendFormat": "Total", "refId": "A"},
        {"datasource": {"type": "prometheus", "uid": "mimir"}, "expr": "rate(pihole_dns_queries_blocked_all_types{job=\"security\", service=\"pihole\"}[5m])", "legendFormat": "Blocked", "refId": "B"}
      ],
      "title": "DNS Query Rate", "type": "timeseries"
    },
    {
      "datasource": {"type": "prometheus", "uid": "mimir"},
      "fieldConfig": {"defaults": {"color": {"mode": "thresholds"}, "max": 100, "min": 0, "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": null}, {"color": "yellow", "value": 20}, {"color": "red", "value": 50}]}, "unit": "percent"}, "overrides": []},
      "gridPos": {"h": 8, "w": 5, "x": 14, "y": 6}, "id": 8,
      "options": {"orientation": "auto", "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false}, "showThresholdLabels": false, "showThresholdMarkers": true},
      "targets": [{"datasource": {"type": "prometheus", "uid": "mimir"}, "expr": "pihole_ads_percentage_today{job=\"security\", service=\"pihole\"}", "instant": true, "refId": "A"}],
      "title": "Blocked %", "type": "gauge"
    },
    {
      "datasource": {"type": "prometheus", "uid": "mimir"},
      "fieldConfig": {"defaults": {"color": {"mode": "thresholds"}, "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": null}]}, "unit": "short"}, "overrides": []},
      "gridPos": {"h": 8, "w": 5, "x": 19, "y": 6}, "id": 9,
      "options": {"displayMode": "list", "footer": {"countRows": false, "fields": "", "reducer": ["sum"], "show": false}, "orientation": "auto", "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false}, "showUnfilled": true},
      "targets": [{"datasource": {"type": "prometheus", "uid": "mimir"}, "expr": "topk(10, pihole_top_ad_blocked{job=\"security\", service=\"pihole\"})", "instant": true, "legendFormat": "{{domain}}", "refId": "A"}],
      "title": "Top Blocked Domains", "type": "bargauge"
    },
    {"collapsed": false, "gridPos": {"h": 1, "w": 24, "x": 0, "y": 14}, "id": 10, "title": "WireGuard", "type": "row"},
    {
      "datasource": {"type": "prometheus", "uid": "mimir"},
      "fieldConfig": {"defaults": {"color": {"mode": "thresholds"}, "thresholds": {"mode": "absolute", "steps": [{"color": "red", "value": null}, {"color": "green", "value": 1}]}, "unit": "short"}, "overrides": []},
      "gridPos": {"h": 8, "w": 4, "x": 0, "y": 15}, "id": 11,
      "options": {"colorMode": "value", "graphMode": "none", "justifyMode": "center", "orientation": "auto", "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false}, "textMode": "auto"},
      "targets": [{"datasource": {"type": "prometheus", "uid": "mimir"}, "expr": "count(wireguard_peer_last_handshake_seconds{job=\"security\", service=\"wireguard\"} > (time() - 300)) or vector(0)", "instant": true, "refId": "A"}],
      "title": "Connected Peers", "type": "stat"
    },
    {
      "datasource": {"type": "prometheus", "uid": "mimir"},
      "fieldConfig": {"defaults": {"color": {"mode": "palette-classic"}, "custom": {"drawStyle": "line", "fillOpacity": 10, "lineWidth": 1, "showPoints": "never", "spanNulls": false}, "unit": "Bps"}, "overrides": []},
      "gridPos": {"h": 8, "w": 10, "x": 4, "y": 15}, "id": 12,
      "options": {"legend": {"calcs": ["mean", "max"], "displayMode": "table", "placement": "bottom", "showLegend": true}, "tooltip": {"mode": "multi", "sort": "desc"}},
      "targets": [{"datasource": {"type": "prometheus", "uid": "mimir"}, "expr": "rate(wireguard_sent_bytes_total{job=\"security\", service=\"wireguard\"}[5m])", "legendFormat": "{{public_key}}", "refId": "A"}],
      "title": "Per-Peer TX Rate", "type": "timeseries"
    },
    {
      "datasource": {"type": "prometheus", "uid": "mimir"},
      "fieldConfig": {"defaults": {"color": {"mode": "palette-classic"}, "custom": {"drawStyle": "line", "fillOpacity": 10, "lineWidth": 1, "showPoints": "never", "spanNulls": false}, "unit": "Bps"}, "overrides": []},
      "gridPos": {"h": 8, "w": 10, "x": 14, "y": 15}, "id": 13,
      "options": {"legend": {"calcs": ["mean", "max"], "displayMode": "table", "placement": "bottom", "showLegend": true}, "tooltip": {"mode": "multi", "sort": "desc"}},
      "targets": [{"datasource": {"type": "prometheus", "uid": "mimir"}, "expr": "rate(wireguard_received_bytes_total{job=\"security\", service=\"wireguard\"}[5m])", "legendFormat": "{{public_key}}", "refId": "A"}],
      "title": "Per-Peer RX Rate", "type": "timeseries"
    },
    {"collapsed": false, "gridPos": {"h": 1, "w": 24, "x": 0, "y": 23}, "id": 14, "title": "Caddy", "type": "row"},
    {
      "datasource": {"type": "prometheus", "uid": "mimir"},
      "fieldConfig": {"defaults": {"color": {"mode": "palette-classic"}, "custom": {"drawStyle": "line", "fillOpacity": 10, "lineWidth": 1, "showPoints": "never", "spanNulls": false}, "unit": "reqps"}, "overrides": []},
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 24}, "id": 15,
      "options": {"legend": {"calcs": ["mean", "max"], "displayMode": "table", "placement": "bottom", "showLegend": true}, "tooltip": {"mode": "multi", "sort": "desc"}},
      "targets": [{"datasource": {"type": "prometheus", "uid": "mimir"}, "expr": "sum by (code) (rate(caddy_http_requests_total{job=\"security\", service=\"caddy\"}[5m]))", "legendFormat": "{{code}}", "refId": "A"}],
      "title": "Request Rate by Status", "type": "timeseries"
    },
    {
      "datasource": {"type": "prometheus", "uid": "mimir"},
      "fieldConfig": {"defaults": {"color": {"mode": "palette-classic"}, "custom": {"drawStyle": "line", "fillOpacity": 10, "lineWidth": 1, "showPoints": "never", "spanNulls": false}, "unit": "s"}, "overrides": []},
      "gridPos": {"h": 8, "w": 12, "x": 12, "y": 24}, "id": 16,
      "options": {"legend": {"calcs": ["mean", "max"], "displayMode": "table", "placement": "bottom", "showLegend": true}, "tooltip": {"mode": "multi", "sort": "desc"}},
      "targets": [
        {"datasource": {"type": "prometheus", "uid": "mimir"}, "expr": "histogram_quantile(0.50, sum by (le) (rate(caddy_http_request_duration_seconds_bucket{job=\"security\", service=\"caddy\"}[5m])))", "legendFormat": "p50", "refId": "A"},
        {"datasource": {"type": "prometheus", "uid": "mimir"}, "expr": "histogram_quantile(0.99, sum by (le) (rate(caddy_http_request_duration_seconds_bucket{job=\"security\", service=\"caddy\"}[5m])))", "legendFormat": "p99", "refId": "B"}
      ],
      "title": "Response Latency p50/p99", "type": "timeseries"
    },
    {"collapsed": false, "gridPos": {"h": 1, "w": 24, "x": 0, "y": 32}, "id": 17, "title": "Security Services", "type": "row"},
    {
      "datasource": {"type": "prometheus", "uid": "mimir"},
      "fieldConfig": {"defaults": {"color": {"mode": "palette-classic"}, "custom": {"drawStyle": "line", "fillOpacity": 10, "lineWidth": 1, "showPoints": "never", "spanNulls": false}, "unit": "short"}, "overrides": []},
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 33}, "id": 18,
      "options": {"legend": {"calcs": ["lastNotNull"], "displayMode": "table", "placement": "bottom", "showLegend": true}, "tooltip": {"mode": "multi", "sort": "desc"}},
      "targets": [{"datasource": {"type": "prometheus", "uid": "mimir"}, "expr": "cs_active_decisions{job=\"security\", service=\"crowdsec\"}", "legendFormat": "{{type}}", "refId": "A"}],
      "title": "CrowdSec Active Decisions by Type", "type": "timeseries"
    },
    {
      "datasource": {"type": "prometheus", "uid": "mimir"},
      "fieldConfig": {"defaults": {"color": {"mode": "thresholds"}, "mappings": [{"options": {"0": {"color": "red", "index": 0, "text": "Sealed"}, "1": {"color": "green", "index": 1, "text": "Unsealed"}}, "type": "value"}], "thresholds": {"mode": "absolute", "steps": [{"color": "red", "value": null}, {"color": "green", "value": 1}]}, "unit": "short"}, "overrides": []},
      "gridPos": {"h": 4, "w": 4, "x": 12, "y": 33}, "id": 19,
      "options": {"colorMode": "background", "graphMode": "none", "justifyMode": "center", "orientation": "auto", "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false}, "textMode": "auto"},
      "targets": [{"datasource": {"type": "prometheus", "uid": "mimir"}, "expr": "vault_core_unsealed{job=\"security\", service=\"vault\"} or up{job=\"security\", service=\"vault\"}", "instant": true, "refId": "A"}],
      "title": "Vault Status", "type": "stat"
    },
    {
      "datasource": {"type": "prometheus", "uid": "mimir"},
      "fieldConfig": {"defaults": {"color": {"mode": "thresholds"}, "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": null}]}, "unit": "short"}, "overrides": []},
      "gridPos": {"h": 4, "w": 4, "x": 16, "y": 33}, "id": 20,
      "options": {"colorMode": "value", "graphMode": "area", "justifyMode": "auto", "orientation": "auto", "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false}, "textMode": "auto"},
      "targets": [{"datasource": {"type": "prometheus", "uid": "mimir"}, "expr": "vault_token_count{job=\"security\", service=\"vault\"}", "instant": true, "refId": "A"}],
      "title": "Vault Token Count", "type": "stat"
    },
    {
      "datasource": {"type": "prometheus", "uid": "mimir"},
      "fieldConfig": {"defaults": {"color": {"mode": "thresholds"}, "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": null}]}, "unit": "reqps"}, "overrides": []},
      "gridPos": {"h": 4, "w": 4, "x": 20, "y": 33}, "id": 21,
      "options": {"colorMode": "value", "graphMode": "area", "justifyMode": "auto", "orientation": "auto", "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false}, "textMode": "auto"},
      "targets": [{"datasource": {"type": "prometheus", "uid": "mimir"}, "expr": "rate(authelia_authentication_duration_seconds_count{job=\"security\", service=\"authelia\"}[5m])", "instant": true, "refId": "A"}],
      "title": "Authelia Auth Rate", "type": "stat"
    }
  ],
  "refresh": "1m",
  "schemaVersion": 39,
  "tags": ["security", "homelab"],
  "templating": {"list": []},
  "time": {"from": "now-1h", "to": "now"},
  "timepicker": {},
  "timezone": "browser",
  "title": "Security + Vault",
  "uid": "security-vault",
  "version": 1
}
```

- [ ] **Step 2: Validate JSON syntax**

```bash
python3 -c "import json; json.load(open('monitoring/grafana-stack-setup/roles/grafana-stack/files/dashboards/security-vault.json')); print('JSON valid')"
```
Expected: `JSON valid`

- [ ] **Step 3: Commit**

```bash
git add monitoring/grafana-stack-setup/roles/grafana-stack/files/dashboards/security-vault.json
git commit -m "feat(grafana): add Security+Vault dashboard"
```

---

## Task 8: Create app-services.json dashboard

**Files:**
- Create: `monitoring/grafana-stack-setup/roles/grafana-stack/files/dashboards/app-services.json`

- [ ] **Step 1: Create the dashboard JSON file**

Create `monitoring/grafana-stack-setup/roles/grafana-stack/files/dashboards/app-services.json`:

```json
{
  "__inputs": [],
  "__requires": [
    {"type": "grafana", "id": "grafana", "name": "Grafana", "version": "10.0.0"},
    {"type": "datasource", "id": "prometheus", "name": "Prometheus", "version": "1.0.0"}
  ],
  "annotations": {"list": []},
  "description": "HTTP availability, response time, and SSL expiry for homelab application services",
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 1,
  "id": null,
  "links": [],
  "panels": [
    {"collapsed": false, "gridPos": {"h": 1, "w": 24, "x": 0, "y": 0}, "id": 1, "title": "Overview", "type": "row"},
    {
      "datasource": {"type": "prometheus", "uid": "mimir"},
      "fieldConfig": {"defaults": {"color": {"mode": "thresholds"}, "mappings": [], "thresholds": {"mode": "absolute", "steps": [{"color": "red", "value": null}, {"color": "green", "value": 1}]}, "unit": "short"}, "overrides": []},
      "gridPos": {"h": 4, "w": 6, "x": 0, "y": 1}, "id": 2,
      "options": {"colorMode": "value", "graphMode": "none", "justifyMode": "auto", "orientation": "auto", "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false}, "textMode": "auto"},
      "targets": [{"datasource": {"type": "prometheus", "uid": "mimir"}, "expr": "count(probe_success{job=\"blackbox\"} == 1) or vector(0)", "instant": true, "refId": "A"}],
      "title": "Services Up", "type": "stat"
    },
    {
      "datasource": {"type": "prometheus", "uid": "mimir"},
      "fieldConfig": {"defaults": {"color": {"mode": "thresholds"}, "mappings": [], "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": null}, {"color": "red", "value": 1}]}, "unit": "short"}, "overrides": []},
      "gridPos": {"h": 4, "w": 6, "x": 6, "y": 1}, "id": 3,
      "options": {"colorMode": "background", "graphMode": "none", "justifyMode": "auto", "orientation": "auto", "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false}, "textMode": "auto"},
      "targets": [{"datasource": {"type": "prometheus", "uid": "mimir"}, "expr": "count(probe_success{job=\"blackbox\"} == 0) or vector(0)", "instant": true, "refId": "A"}],
      "title": "Services Down", "type": "stat"
    },
    {
      "datasource": {"type": "prometheus", "uid": "mimir"},
      "fieldConfig": {"defaults": {"color": {"mode": "thresholds"}, "mappings": [], "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": null}, {"color": "yellow", "value": 1}, {"color": "red", "value": 3}]}, "unit": "s"}, "overrides": []},
      "gridPos": {"h": 4, "w": 6, "x": 12, "y": 1}, "id": 4,
      "options": {"colorMode": "value", "graphMode": "area", "justifyMode": "auto", "orientation": "auto", "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false}, "textMode": "auto"},
      "targets": [{"datasource": {"type": "prometheus", "uid": "mimir"}, "expr": "avg(probe_duration_seconds{job=\"blackbox\"})", "instant": true, "refId": "A"}],
      "title": "Avg Response Time", "type": "stat"
    },
    {
      "datasource": {"type": "prometheus", "uid": "mimir"},
      "fieldConfig": {"defaults": {"color": {"mode": "thresholds"}, "mappings": [], "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": null}, {"color": "red", "value": 1}]}, "unit": "short"}, "overrides": []},
      "gridPos": {"h": 4, "w": 6, "x": 18, "y": 1}, "id": 5,
      "options": {"colorMode": "background", "graphMode": "none", "justifyMode": "auto", "orientation": "auto", "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false}, "textMode": "auto"},
      "targets": [{"datasource": {"type": "prometheus", "uid": "mimir"}, "expr": "count((probe_ssl_earliest_cert_expiry{job=\"blackbox\"} - time()) / 86400 <= 14) or vector(0)", "instant": true, "refId": "A"}],
      "title": "SSL Certs Expiring ≤14d", "type": "stat"
    },
    {"collapsed": false, "gridPos": {"h": 1, "w": 24, "x": 0, "y": 5}, "id": 6, "title": "Service Health", "type": "row"},
    {
      "datasource": {"type": "prometheus", "uid": "mimir"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "thresholds"},
          "custom": {"fillOpacity": 70, "lineWidth": 1, "spanNulls": false},
          "mappings": [
            {"options": {"0": {"color": "red", "index": 0, "text": "Down"}, "1": {"color": "green", "index": 1, "text": "Up"}}, "type": "value"}
          ],
          "thresholds": {"mode": "absolute", "steps": [{"color": "red", "value": null}, {"color": "green", "value": 1}]}
        },
        "overrides": []
      },
      "gridPos": {"h": 8, "w": 24, "x": 0, "y": 6}, "id": 7,
      "options": {"alignValue": "left", "legend": {"displayMode": "list", "placement": "bottom", "showLegend": true}, "mergeValues": true, "rowHeight": 0.9, "showValue": "auto", "tooltip": {"mode": "single", "sort": "none"}},
      "targets": [{"datasource": {"type": "prometheus", "uid": "mimir"}, "expr": "probe_success{job=\"blackbox\", service=~\"$service\"}", "legendFormat": "{{service}}", "refId": "A"}],
      "title": "Service Up/Down History", "type": "state-timeline"
    },
    {"collapsed": false, "gridPos": {"h": 1, "w": 24, "x": 0, "y": 14}, "id": 8, "title": "Response Times", "type": "row"},
    {
      "datasource": {"type": "prometheus", "uid": "mimir"},
      "fieldConfig": {"defaults": {"color": {"mode": "palette-classic"}, "custom": {"drawStyle": "line", "fillOpacity": 10, "lineWidth": 1, "showPoints": "never", "spanNulls": false}, "mappings": [], "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": null}]}, "unit": "s"}, "overrides": []},
      "gridPos": {"h": 8, "w": 24, "x": 0, "y": 15}, "id": 9,
      "options": {"legend": {"calcs": ["mean", "max", "lastNotNull"], "displayMode": "table", "placement": "bottom", "showLegend": true}, "tooltip": {"mode": "multi", "sort": "desc"}},
      "targets": [{"datasource": {"type": "prometheus", "uid": "mimir"}, "expr": "probe_duration_seconds{job=\"blackbox\", service=~\"$service\"}", "legendFormat": "{{service}}", "refId": "A"}],
      "title": "HTTP Probe Duration", "type": "timeseries"
    },
    {"collapsed": false, "gridPos": {"h": 1, "w": 24, "x": 0, "y": 23}, "id": 10, "title": "SSL Certificates", "type": "row"},
    {
      "datasource": {"type": "prometheus", "uid": "mimir"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "thresholds"},
          "mappings": [],
          "min": 0,
          "thresholds": {"mode": "absolute", "steps": [{"color": "red", "value": null}, {"color": "yellow", "value": 14}, {"color": "green", "value": 30}]},
          "unit": "d"
        },
        "overrides": []
      },
      "gridPos": {"h": 8, "w": 24, "x": 0, "y": 24}, "id": 11,
      "options": {"displayMode": "lcd", "fillOpacity": 80, "gradientMode": "scheme", "minVizHeight": 10, "minVizWidth": 0, "orientation": "horizontal", "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false}, "showUnfilled": true, "valueMode": "color"},
      "targets": [{"datasource": {"type": "prometheus", "uid": "mimir"}, "expr": "(probe_ssl_earliest_cert_expiry{job=\"blackbox\", service=~\"$service\"} - time()) / 86400", "instant": true, "legendFormat": "{{service}}", "refId": "A"}],
      "title": "Days Until SSL Cert Expiry", "type": "bargauge"
    }
  ],
  "refresh": "1m",
  "schemaVersion": 39,
  "tags": ["apps", "availability", "homelab"],
  "templating": {
    "list": [
      {
        "current": {"selected": true, "text": "All", "value": "$__all"},
        "datasource": {"type": "prometheus", "uid": "mimir"},
        "definition": "label_values(probe_success{job=\"blackbox\"}, service)",
        "hide": 0, "includeAll": true, "label": "Service", "multi": true, "name": "service",
        "options": [],
        "query": {"qryType": 1, "query": "label_values(probe_success{job=\"blackbox\"}, service)", "refId": "StandardVariableQuery"},
        "refresh": 2, "regex": "", "sort": 1, "type": "query"
      }
    ]
  },
  "time": {"from": "now-6h", "to": "now"},
  "timepicker": {},
  "timezone": "browser",
  "title": "Application Services",
  "uid": "app-services",
  "version": 1
}
```

- [ ] **Step 2: Validate JSON syntax**

```bash
python3 -c "import json; json.load(open('monitoring/grafana-stack-setup/roles/grafana-stack/files/dashboards/app-services.json')); print('JSON valid')"
```
Expected: `JSON valid`

- [ ] **Step 3: Commit**

```bash
git add monitoring/grafana-stack-setup/roles/grafana-stack/files/dashboards/app-services.json
git commit -m "feat(grafana): add Application Services availability dashboard"
```

---

## Task 9: Wire dashboards into Grafana provisioning tasks

**Files:**
- Modify: `monitoring/grafana-stack-setup/roles/grafana-stack/tasks/main.yml`

- [ ] **Step 1: Add new dashboards to the copy loop**

In `monitoring/grafana-stack-setup/roles/grafana-stack/tasks/main.yml`, find the "Copy Grafana dashboards" task (currently loops over `openclaw.json`, `node-health.json`, `docker-containers.json`). Add the two new entries:

```yaml
- name: Copy Grafana dashboards
  ansible.builtin.copy:
    src: "dashboards/{{ item }}"
    dest: "{{ grafana_data_dir }}/provisioning/dashboards/{{ item }}"
    mode: "0644"
  loop:
    - openclaw.json
    - node-health.json
    - docker-containers.json
    - security-vault.json
    - app-services.json
  notify: Restart grafana-stack
```

- [ ] **Step 2: Lint**

```bash
ansible-lint monitoring/grafana-stack-setup/
```
Expected: no errors

- [ ] **Step 3: Final commit**

```bash
git add monitoring/grafana-stack-setup/roles/grafana-stack/tasks/main.yml
git commit -m "feat(grafana): provision security-vault and app-services dashboards"
```

---

## Validation After Deployment

Once the grafana-stack playbook and secure-homelab-access playbook have been run (with your actual variable values set):

**Security+Vault dashboard:**
- Open Grafana → Dashboards → "Security + Vault"
- Set variables populated in `group_vars/all.yml` (e.g. `caddy_metrics_host: "10.0.0.1"`)
- Pi-hole row populates if `pihole_exporter_host` is set and `pihole_exporter_enabled: true` was run
- WireGuard row populates if `wireguard_exporter_host` is set and `wireguard_exporter_enabled: true` was run
- Verify: `up{job="security"}` exists in Mimir via Grafana Explore

**Application Services dashboard:**
- Open Grafana → Dashboards → "Application Services"
- Service Health timeline shows green/red history
- Services with HTTP URLs show probe duration
- SSL panel only shows entries for services with HTTPS URLs (expected)
- Verify: `probe_success{job="blackbox"}` exists in Mimir via Grafana Explore

**Quick Alloy config test (check rendered template is valid River syntax):**
```bash
# After running the grafana-stack playbook, check Alloy logs
docker exec alloy cat /etc/alloy/config.alloy | head -50
docker logs alloy 2>&1 | grep -i error | tail -20
```
Expected: no syntax errors in Alloy logs

# Grafana Dashboards — Security+Vault & Application Services Design

**Date:** 2026-03-24
**Status:** Approved
**Context:** Homelab Ansible repo — continuation of the Grafana dashboards initiative (sub-projects 3 and 4 of 4).

---

## Background

Sub-projects 1 (Node Health) and 2 (Docker Containers) are complete. Both used metrics built into Alloy (`prometheus.exporter.unix`, `prometheus.exporter.cadvisor`). The remaining two dashboards cover services that mostly lack native Prometheus endpoints, requiring a deliberate data-source strategy per service.

---

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Vault sub-project | Merged into Security dashboard | Both are infrastructure-layer concerns; reduces dashboard count |
| Pi-hole + WireGuard | Add dedicated exporter containers | No native Prometheus; well-known exporters exist |
| App Services metrics | Blackbox HTTP probing | None of the 7 app services expose Prometheus; probing gives availability + latency uniformly |
| Exporter placement | Alongside their services (Approach A) | Consistent with OpenClaw metrics pattern; no cross-node network dependencies |

---

## Sub-project 3: Security + Vault Dashboard

### New Exporter Containers

The `secure-homelab-access` role uses `community.docker.docker_container` tasks (not docker-compose). Exporter containers are added as new `community.docker.docker_container` tasks in the respective role task files, enabled by `*_exporter_enabled` flags.

**Pi-hole Exporter** (added to `roles/pihole/tasks/main.yml`)
- Image: `ekofr/pihole-exporter:v0.4.0`
- Container name: `pihole-exporter`
- Env:
  - `PIHOLE_HOSTNAME=pihole` — bare container hostname, no scheme (exporter constructs URL internally)
  - No password/token required — Pi-hole is v5 (`pihole/pihole:2024.07.0`) and the existing role clears the web password post-install (`pihole -a -p ""`). Pi-hole v5 with no password set makes its API publicly accessible, so the exporter needs no credentials.
- Exposes: `:9617/metrics` on `homelab-net`
- Networks: `homelab-net` (same network as Pi-hole container)
- Added when: `pihole_exporter_enabled | default(false) | length > 0` → use `| default(false) | bool`

**WireGuard Exporter** (added to `roles/wireguard/tasks/main.yml`)
- Image: `mindflavor/prometheus-wireguard-exporter:3.6.6` (pinned; do not use `latest`)
- Container name: `wireguard-exporter`
- The exporter reads WireGuard peer stats via `wg show dump` against the running kernel interface — it does NOT read a config file. wg-easy stores state as `wg0.json`, not `wg0.conf`, so file-based approaches will not work.
- Requires access to the host WireGuard interface: run with `network_mode: host` so it can reach the `wg0` kernel interface
- Capability: `NET_ADMIN`
- Exposes: `:9586/metrics` (on host network)
- Added when: `wireguard_exporter_enabled | default(false) | bool`

### Prerequisites

**Caddy metrics endpoint** (required before caddy scraping works):
Caddy's metrics endpoint is NOT currently enabled in the Caddyfile. Add the following to the Caddy global block in `roles/caddy/templates/Caddyfile.j2`:
```
{
  ...existing globals...
  servers {
    metrics
  }
}
```
Then add a metrics route to expose it — Caddy exposes metrics at `:2019/metrics` on its admin interface by default when `metrics` is enabled globally. The existing Caddyfile must be updated as part of this work.

**Vault telemetry** (required before vault metrics work):
`vault_core_unsealed` and other Vault gauges require a `telemetry` block in Vault's HCL config:
```hcl
telemetry {
  prometheus_retention_time = "30s"
  disable_hostname = true
}
```
Without this block, `/v1/sys/metrics` returns no Prometheus data. If telemetry is absent, replace the Vault seal-status panel with `up{job="security", service="vault"}` as a fallback.

**Vault metrics token** (required before vault scraping works):
`/v1/sys/metrics` requires a token with `sys/metrics` read capability:
```hcl
# vault-metrics-policy.hcl
path "sys/metrics" { capabilities = ["read"] }
```
```bash
vault policy write metrics vault-metrics-policy.hcl
vault token create -policy=metrics -period=8760h -display-name=alloy-metrics
```
Store the resulting token in Vault KV and reference via `vault_metrics_token`.

### New Alloy Scrape Targets

Added as conditional blocks to `alloy.river.j2` using the existing `| length > 0` pattern:
```
{% if var | default('') | length > 0 %}
```

Each block sets three relabel rules: `job="security"`, `instance=env("HOSTNAME")`, `service="<name>"`. The `service` label differentiates targets in dashboard queries (the variable selector uses `label_values(up{job="security"}, service)`, not `instance`).

Variables added to `monitoring/grafana-stack-setup/group_vars/all.yml` (monitoring-side config — where Alloy should scrape):

| Variable | Default | Service |
|---|---|---|
| `caddy_metrics_host` | `""` | Caddy reverse proxy (Node 1 LAN IP or Docker gateway) |
| `caddy_metrics_port` | `2019` | |
| `authelia_metrics_host` | `""` | Authelia 2FA |
| `authelia_metrics_port` | `9959` | |
| `crowdsec_metrics_host` | `""` | CrowdSec LAPI |
| `crowdsec_metrics_port` | `6060` | |
| `vault_metrics_host` | `""` | HashiCorp Vault |
| `vault_metrics_port` | `8200` | |
| `vault_metrics_token` | `""` | Bearer token (see prerequisite above) |
| `pihole_exporter_host` | `""` | Pi-hole exporter sidecar |
| `pihole_exporter_port` | `9617` | |
| `wireguard_exporter_host` | `""` | WireGuard exporter sidecar |
| `wireguard_exporter_port` | `9586` | |

### Dashboard: `security-vault.json`

**UID:** `security-vault`
**Variable:** `$service` — multi-select + All, from `label_values(up{job="security"}, service)`

**Row 1 — Overview**
- Stat: DNS queries/day (`increase(pihole_dns_queries_all_types_total{job="security", service="pihole"}[24h])`)
- Stat: Blocked queries % (`pihole_ads_percentage_today{job="security", service="pihole"}`)
- Stat: VPN peers connected (`count(wireguard_peer_last_handshake_seconds{job="security", service="wireguard"} > 0)`)
- Stat: CrowdSec active bans (`cs_active_decisions{job="security", service="crowdsec"}`)

**Row 2 — Pi-hole**
- Timeseries: DNS query rate — total vs blocked
  - `rate(pihole_dns_queries_all_types_total{job="security", service="pihole"}[5m])` legend `Total`
  - `rate(pihole_dns_queries_blocked_all_types{job="security", service="pihole"}[5m])` legend `Blocked`
- Gauge: Blocked % (`pihole_ads_percentage_today{job="security", service="pihole"}`)
- Table: Top blocked domains — query `topk(10, pihole_top_ad_blocked{job="security", service="pihole"})`, transform to table, show `domain` label as column. Note: `pihole_top_ad_blocked` exposes one time series per blocked domain with a `domain` label; `topk()` selects the 10 with highest count values.

**Row 3 — WireGuard**
- Stat: Connected peers (`count(wireguard_peer_last_handshake_seconds{job="security", service="wireguard"} > (time() - 300))`)
- Timeseries: Per-peer TX rate (`rate(wireguard_sent_bytes_total{job="security", service="wireguard"}[5m])`)
- Timeseries: Per-peer RX rate (`rate(wireguard_received_bytes_total{job="security", service="wireguard"}[5m])`)
- Legend format: `{{public_key}}` (truncate in Grafana field override if too long)

**Row 4 — Caddy**
- Timeseries: Request rate by status (`rate(caddy_http_requests_total{job="security", service="caddy"}[5m])` by `code` label)
- Histogram: p50/p99 latency (`histogram_quantile(0.99, rate(caddy_http_request_duration_seconds_bucket{job="security", service="caddy"}[5m]))`)

**Row 5 — Security Services**
- Timeseries: CrowdSec decisions (`cs_active_decisions{job="security", service="crowdsec"}` by `type` label)
- Stat: Vault status — `vault_core_unsealed{job="security", service="vault"}` if telemetry enabled, else `up{job="security", service="vault"}` as fallback
- Stat: Vault token count (`vault_token_count{job="security", service="vault"}`)
- Stat: Authelia auth rate (`rate(authelia_authentication_duration_seconds_count{job="security", service="authelia"}[5m])`)

---

## Sub-project 4: Application Services Dashboard

### New Alloy Component

`prometheus.exporter.blackbox` is a native component in Alloy v1.0+ — no external binary or additional container required. Confirmed available in Alloy v1.5.1.

The block is added to `alloy.river.j2`. The gate condition is assembled inline using a Jinja2 approach — the template iterates over a known set of `probe_*_url` variables and skips empty ones. The gate:

```jinja2
{% set _probe_urls = [
    ('n8n',          probe_n8n_url          | default('')),
    ('paperless',    probe_paperless_url    | default('')),
    ('netbox',       probe_netbox_url       | default('')),
    ('outline',      probe_outline_url      | default('')),
    ('vaultwarden',  probe_vaultwarden_url  | default('')),
    ('seafile',      probe_seafile_url      | default('')),
    ('dify',         probe_dify_url         | default('')),
] | selectattr(1) | list %}
{% if _probe_urls | length > 0 %}
...blackbox config...
{% endif %}
```

Each non-empty URL becomes a probe target with the service name (first element of each tuple) set as the `service` label via Alloy's `discovery.relabel` + `targets` construction.

All probe targets use module `http_2xx`: HTTP GET, expects 2xx, 10s timeout. SSL cert expiry checked automatically when the target URL uses HTTPS.

The Alloy block sets: `job="blackbox"`, `service=<name>`, `instance=env("HOSTNAME")`.

### Service URL Variables in `monitoring/grafana-stack-setup/group_vars/all.yml`

| Variable | Default | Service |
|---|---|---|
| `probe_n8n_url` | `""` | n8n workflow automation |
| `probe_paperless_url` | `""` | Paperless-ngx |
| `probe_netbox_url` | `""` | Netbox IPAM |
| `probe_outline_url` | `""` | Outline wiki |
| `probe_vaultwarden_url` | `""` | Vaultwarden |
| `probe_seafile_url` | `""` | Seafile |
| `probe_dify_url` | `""` | Dify |

Use internal URLs (e.g., `http://10.0.0.1:PORT`) not public HTTPS subdomains, to avoid depending on Caddy/DNS being up for the probe to work. SSL panels will show no data for HTTP targets — that is expected and acceptable.

### Dashboard: `app-services.json`

**UID:** `app-services`
**Variable:** `$service` — multi-select + All, from `label_values(probe_success{job="blackbox"}, service)`

**Row 1 — Overview**
- Stat: Services up (`count(probe_success{job="blackbox"} == 1)`)
- Stat: Services down (`count(probe_success{job="blackbox"} == 0) or vector(0)`) — red background when > 0
- Stat: Average response time (`avg(probe_duration_seconds{job="blackbox"})`, unit: seconds)
- Stat: SSL certs expiring ≤ 14 days (`count((probe_ssl_earliest_cert_expiry{job="blackbox"} - time()) / 86400 <= 14) or vector(0)`) — red when > 0

**Row 2 — Service Health**
- State timeline: Per-service up/down history (`probe_success{job="blackbox", service=~"$service"}`) — green=1 (up), red=0 (down)

**Row 3 — Response Times**
- Timeseries: HTTP probe duration per service (`probe_duration_seconds{job="blackbox", service=~"$service"}`)
- Legend: `{{service}}`, unit: seconds

**Row 4 — SSL Certificates**
- Bar gauge: Days until cert expiry per service (`(probe_ssl_earliest_cert_expiry{job="blackbox"} - time()) / 86400`)
- Thresholds: green ≥ 30 days, yellow < 30 days, red < 14 days
- Note: Only services configured with HTTPS URLs will have data here; HTTP-only targets are absent from this panel — expected

---

## Files Changed

### Modified
- `security/secure-homelab-access/roles/pihole/tasks/main.yml` — add `pihole-exporter` docker_container task, gated by `pihole_exporter_enabled | default(false) | bool`
- `security/secure-homelab-access/roles/wireguard/tasks/main.yml` — add `wireguard-exporter` docker_container task, gated by `wireguard_exporter_enabled | default(false) | bool`
- `security/secure-homelab-access/roles/caddy/templates/Caddyfile.j2` — enable Caddy metrics in global block (prerequisite for caddy scraping)
- `monitoring/grafana-stack-setup/roles/grafana-stack/templates/alloy.river.j2` — add security scrape blocks (one per service) + blackbox exporter block
- `monitoring/grafana-stack-setup/group_vars/all.yml` — add all new host/port/url/token variables with empty defaults
- `monitoring/grafana-stack-setup/roles/grafana-stack/tasks/main.yml` — add `security-vault.json` and `app-services.json` to dashboard copy loop

### Created
- `monitoring/grafana-stack-setup/roles/grafana-stack/files/dashboards/security-vault.json`
- `monitoring/grafana-stack-setup/roles/grafana-stack/files/dashboards/app-services.json`

---

## Out of Scope

- Alerting rules (Grafana alerting or Prometheus rules) — separate initiative
- Log-based panels for individual app services — available via Grafana Explore on demand
- LibreNMS / Uptime Kuma dashboards — these services have their own UIs
- Vault HCL telemetry config changes — prerequisite, managed separately via vault-setup role

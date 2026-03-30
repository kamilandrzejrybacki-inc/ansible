# Grafana Monitoring Overhaul — Design Spec

**Date:** 2026-03-30
**Status:** Draft
**Author:** Kamil Rybacki + Claude

## Overview

Comprehensive rework of the homelab monitoring stack: migrate Mimir/Loki to lw-nas, deploy metrics collection on all nodes (including K8s and NAS-specific exporters), enable n8n Prometheus metrics, upgrade Portkey to 2.0 for native metrics, replace file-based dashboard provisioning with Grizzly GitOps from a dedicated GitHub repository, and build a new set of 19 dashboards from scratch. Includes a validation framework to verify all dashboards return real data and all nodes are reachable.

## Architecture

### Current State

- Grafana 11.4 + Mimir + Loki + Alloy run on lw-main (192.168.0.105) via Docker Compose
- 5 static dashboard JSON files provisioned by Ansible file copy
- Alloy agents on lw-s1 and lw-c1 collect host + Docker metrics only
- No Alloy agent on lw-nas
- No K8s cluster metrics (kube-state-metrics, kubelet, API server)
- No Portkey gateway metrics (v1.x has no Prometheus support)
- No n8n Prometheus metrics (N8N_METRICS not enabled)
- No NAS-specific exporters (SMART, PostgreSQL, MariaDB, Redis, SnapRAID)

### Target State

```
lw-main (192.168.0.105) — Gateway & UI
├── Grafana 11.4 (dashboards managed by Grizzly, not file provisioning)
├── Alloy (central scraper — security services, blackbox probes)
└── Caddy, Authelia, Vault, CrowdSec, Pi-hole

lw-s1 (192.168.0.108) — Automation
├── Alloy agent → pushes to lw-nas (10.0.1.2)
├── n8n main instance (N8N_METRICS=true, queue metrics enabled)
└── PostgreSQL, Redis (n8n-local)

lw-c1 (192.168.0.107) — Compute
├── K3s cluster
│   ├── k8s-monitoring-helm (Alloy DaemonSet + kube-state-metrics + node-exporter)
│   ├── Portkey 2.0 (native /metrics)
│   ├── OpenClaw (existing metrics exporter)
│   ├── n8n workers (N8N_METRICS=true)
│   ├── GitHub runners
│   └── ArgoCD, vCluster, Headlamp
└── Alloy agent (host-level) → pushes to lw-nas (10.0.1.2)

lw-nas (10.0.1.2) — Data Hub
├── Mimir (metrics storage, 1yr retention, mergerfs pool)
├── Loki (log storage, 30d retention, mergerfs pool)
├── Alloy agent (local scraper for NAS exporters)
├── smartctl_exporter (SMART disk health, 5 drives)
├── postgres_exporter (shared PostgreSQL: outline, netbox, paperless)
├── mysqld_exporter (shared MariaDB: seafile)
├── redis_exporter (Redis/Valkey cache)
├── docker-exporter (container stats)
├── SnapRAID textfile collector (cron → .prom files)
├── PostgreSQL, MariaDB, Redis/Valkey
└── SnapRAID + mergerfs pool
```

### Data Flow

All metrics/logs flow to lw-nas:

- lw-main Alloy → 10.0.1.2:9009 (Mimir) / 10.0.1.2:3100 (Loki) via direct USB-Ethernet link
- lw-s1 Alloy → 10.0.1.2 via route through 192.168.0.105
- lw-c1 Alloy (host) + K8s Alloy → 10.0.1.2 via route through 192.168.0.105
- lw-nas Alloy → localhost:9009 / localhost:3100
- Grafana (lw-main) queries Mimir/Loki at 10.0.1.2 via direct link

### Network

All nodes already have routes to 10.0.1.2:
- lw-main: direct USB-Ethernet (10.0.1.1 → 10.0.1.2)
- lw-s1: static route `10.0.1.0/24 via 192.168.0.105`
- lw-c1: static route `10.0.1.0/24 via 192.168.0.105`

IP forwarding + NAT masquerade already enabled on lw-main.

New UFW rules needed on lw-nas: allow ports 9009 (Mimir) and 3100 (Loki) from all node IPs.

## Metrics Collection Infrastructure

### lw-nas: Alloy Agent + Exporters

New Ansible playbook: `monitoring/nas-monitoring-setup/`

Docker Compose stack on lw-nas:

| Container | Image | Port | Scrapes |
|-----------|-------|------|---------|
| alloy | grafana/alloy | — | All local exporters, pushes to localhost Mimir/Loki |
| smartctl-exporter | prometheuscommunity/smartctl-exporter | 9633 | SMART data from 4 USB + 1 internal drive |
| postgres-exporter | prometheuscommunity/postgres-exporter | 9187 | Shared PostgreSQL (outline, netbox, paperless DBs) |
| mysqld-exporter | prom/mysqld-exporter | 9104 | Shared MariaDB (seafile DBs) |
| redis-exporter | oliver006/redis_exporter | 9121 | Redis/Valkey cache |
| docker-exporter | prometheusexporter/docker-exporter | 9338 | Container stats |

SnapRAID textfile collector: cron script parsing `snapraid smart` and `snapraid status` output, writing `.prom` files picked up by Alloy's `prometheus.exporter.unix` textfile collector. Metrics: disk failure probability, sync age, scrub age, parity health.

All exporter ports are localhost-only — only Alloy scrapes them.

### lw-c1: K8s Monitoring

New ArgoCD application in `kamilandrzejrybacki-inc/helm`:

- Chart: `grafana/k8s-monitoring` (official Grafana Helm chart)
- Deploys: Alloy DaemonSet + kube-state-metrics + node-exporter inside K3s
- Remote_write: `http://10.0.1.2:9009/api/v1/push` (Mimir)
- Logs: `http://10.0.1.2:3100/loki/api/v1/push` (Loki)
- Additional scrape targets: Portkey 2.0 `/metrics`, n8n worker pods `/metrics`

### Portkey 2.0 Upgrade

Update Portkey Helm chart in `kamilandrzejrybacki-inc/helm`:

- Bump image to 2.0.x branch
- Set `ENABLE_PROMETHEUS: "true"` (default but explicit)
- Native `/metrics` endpoint exposes: `request_count`, `http_request_duration_seconds`, `llm_request_duration_milliseconds`, `llm_cost_sum`, `llm_token_sum` — all with provider/model/status labels
- K8s Alloy discovers and scrapes via pod annotations

### n8n Metrics Enablement

**lw-s1 (main instance):**

Add environment variables to `automation/n8n-setup/`:
```
N8N_METRICS=true
N8N_METRICS_INCLUDE_DEFAULT_METRICS=true
N8N_METRICS_INCLUDE_QUEUE_METRICS=true
N8N_METRICS_QUEUE_METRICS_INTERVAL=10
N8N_METRICS_INCLUDE_WORKFLOW_EXECUTION_DURATION=true
N8N_METRICS_INCLUDE_CACHE_METRICS=true
```

Add Alloy scrape target on lw-s1 agent for `localhost:5678/metrics`.

**lw-c1 (workers on K8s):**

Add same `N8N_METRICS` env vars to n8n-workers Helm chart values. K8s Alloy scrapes worker pods.

### Existing Alloy Agent Reconfiguration

All agents update remote_write endpoints:

| Agent | Current target | New target |
|-------|---------------|------------|
| lw-main (central) | `http://mimir:9009` (Docker internal) | `http://10.0.1.2:9009` |
| lw-main (central) | `http://loki:3100` (Docker internal) | `http://10.0.1.2:3100` |
| lw-s1 (agent) | `http://192.168.0.105:9009` | `http://10.0.1.2:9009` |
| lw-c1 (host agent) | `http://192.168.0.105:9009` | `http://10.0.1.2:9009` |

## Mimir/Loki Migration to lw-nas

### Storage Layout

```
/mnt/pool/monitoring/
├── mimir/
│   ├── data/      # TSDB blocks
│   └── rules/
└── loki/
    ├── chunks/
    ├── rules/
    └── index/
```

On mergerfs pool with SnapRAID protection.

### New Playbook

`monitoring/mimir-loki-setup/` — deploys Mimir + Loki Docker Compose on lw-nas. Reuses existing Jinja2 templates (`mimir.yml.j2`, `loki.yml.j2`) with:

- Storage paths pointed at `/mnt/pool/monitoring/`
- Bind addresses set to `0.0.0.0` (instead of Docker-internal)
- Same retention configs (Mimir 1yr, Loki 30d)

### Migration Strategy

Clean cutover (homelab, no SLA):

1. Deploy Mimir + Loki on lw-nas (new, empty)
2. Reconfigure all Alloy agents to 10.0.1.2
3. Update Grafana datasources
4. Verify metrics/logs flowing
5. Keep old Mimir/Loki on lw-main read-only for 1 week
6. Decommission old containers from lw-main

### Updated grafana-stack-setup on lw-main

Docker Compose shrinks to: Grafana + Alloy + docker-exporter. Mimir/Loki containers removed. Datasources point to `http://10.0.1.2:9009/prometheus` and `http://10.0.1.2:3100`.

## Dashboard GitOps — Grizzly

### Repository

`kamilandrzejrybacki-inc/grafana-dashboards`

```
grafana-dashboards/
├── .github/
│   └── workflows/
│       ├── diff.yml              # PR: grr diff → comment
│       └── deploy.yml            # merge: grr apply
├── grizzly.jsonnet               # Entry point
├── jsonnetfile.json              # Grafonnet dependency
├── folders/
│   ├── homelab.yaml
│   ├── nodes.yaml
│   ├── k8s.yaml
│   ├── nas.yaml
│   ├── llm.yaml
│   ├── n8n.yaml
│   ├── security.yaml
│   └── services.yaml
├── dashboards/
│   ├── community/                # JSON in Grizzly envelopes
│   │   ├── node-health.yaml          # adapted from #1860
│   │   ├── docker-containers.yaml    # adapted from #13077
│   │   ├── k8s-global.yaml           # #15757
│   │   ├── k8s-namespaces.yaml       # #15758
│   │   ├── k8s-nodes.yaml            # #15759
│   │   ├── k8s-pods.yaml             # #15760
│   │   ├── k8s-apiserver.yaml        # #15761
│   │   ├── nas-postgres.yaml         # adapted from #24298
│   │   ├── nas-mariadb.yaml          # adapted from #14057
│   │   ├── nas-redis.yaml            # adapted from #763
│   │   ├── n8n-system-health.yaml    # #24474
│   │   └── n8n-workflow-analytics.yaml # #24475 (Postgres datasource)
│   └── custom/                   # Jsonnet sources
│       ├── lib/
│       │   ├── common.libsonnet      # Datasource UIDs, node list, colors
│       │   └── panels.libsonnet      # Reusable panel builders
│       ├── homelab-overview.jsonnet
│       ├── nas-storage.jsonnet
│       ├── portkey-gateway.jsonnet
│       ├── openclaw-agents.jsonnet
│       ├── n8n-queue-workers.jsonnet
│       ├── security-services.jsonnet
│       └── app-health.jsonnet
├── datasources/
│   ├── mimir.yaml                # http://10.0.1.2:9009/prometheus
│   ├── loki.yaml                 # http://10.0.1.2:3100
│   └── n8n-postgres.yaml         # PostgreSQL direct (for dashboard #24475)
└── tests/
    ├── validate.sh               # Dashboard validation script
    └── smoke-test.jsonnet         # PromQL/LogQL smoke queries
```

### GitHub Actions

**diff.yml (on PR):**
- Installs Grizzly
- Runs `grr diff` against live Grafana
- Posts comment with added/modified/removed resources

**deploy.yml (on merge to main):**
- Runs `grr apply` to push all resources to Grafana API
- Runs validation smoke tests after deploy

**Secrets:** `GRAFANA_URL`, `GRAFANA_TOKEN` (service account with Editor role)

### Shared Jsonnet Library

`common.libsonnet`:
- Datasource UIDs: mimir, loki, n8n-postgres
- Node registry: `{ 'lw-main': '192.168.0.105', 'lw-s1': '192.168.0.108', 'lw-c1': '192.168.0.107', 'lw-nas': '10.0.1.2' }`
- Standard time ranges, refresh intervals
- Color palette constants

`panels.libsonnet`:
- Stat panel builder (for gauges, single values)
- Time series panel builder (with standard overrides)
- Table panel builder
- Status map panel builder (for up/down grids)

## Dashboard Inventory

### Homelab Folder (1 dashboard)

**Homelab Overview** (custom Jsonnet)
Single-pane-of-glass landing page:
- 4-node status row: CPU/mem/disk gauges per node, uptime
- Service status grid: up/down indicators for all services across all nodes
- Alert summary panel
- Quick links to other dashboards

### Nodes Folder (2 dashboards)

**Node Health** (community #1860, adapted)
- CPU, memory, disk, network utilization per node
- System load, uptime, temperature
- Disk I/O, network packets
- Variable: instance selector for all 4 nodes

**Docker Containers** (community #13077, adapted)
- Running container count per node
- CPU/memory/network per container
- Container restart counts, health status
- Variable: instance selector

### K8s Folder (5 dashboards)

**Cluster Global View** (#15757), **Namespaces** (#15758), **Nodes** (#15759), **Pods** (#15760), **API Server** (#15761)
- dotdc community dashboard set — well-maintained, works with Mimir backend
- Covers: resource utilization, pod status, namespace breakdown, API server latency/error rates

### NAS Folder (4 dashboards)

**Storage & Disks** (custom Jsonnet)
- SMART health per drive: temperature, reallocated sectors, power-on hours, remaining life
- SnapRAID: sync age, scrub age, parity health, disk failure probability
- mergerfs pool utilization + per-disk balance
- Drive temperature trends

**PostgreSQL** (community #24298, adapted)
- Connections per database (outline, netbox, paperless)
- Query performance, cache/IO ratio, locks
- Vacuum status, WAL size, database sizes

**MariaDB** (community #14057, adapted)
- Connections, queries/sec, slow queries
- InnoDB buffer pool, table locks
- Replication status (if applicable)

**Redis** (community #763, adapted)
- Memory usage vs 512MB limit
- Hit rate, eviction rate (LRU policy)
- Connected clients, commands/sec
- Key count per database

### LLM Folder (2 dashboards)

**Portkey Gateway** (custom Jsonnet)
- Requests/sec by provider (Groq, NVIDIA, DeepSeek) and model
- Latency histograms: end-to-end, LLM provider, gateway overhead
- Token throughput (input/output) by provider
- Cost accumulation per provider over time
- Error rates by provider/status code
- Cache hit ratio

**OpenClaw Agents** (custom Jsonnet, rework of current)
- Token I/O rates (input/output)
- Cost burn rate ($/hr)
- Request latency percentiles
- Error breakdown
- Provider/model breakdown

### n8n Folder (3 dashboards)

**System Health** (community #24474)
- Node.js process metrics: CPU, memory, heap, GC, event loop lag
- n8n version, leader role, active workflows
- Per-instance view (main + each worker)

**Workflow Analytics** (community #24475, Postgres datasource)
- Execution trends by status (success/error)
- Duration percentiles (P50/P95/P99)
- Success rate over time
- Most-executed workflows, highest failure rate, slowest workflows
- Recent errors

**Queue & Workers** (custom Jsonnet)
- Queue depth over time (waiting, active, completed, failed)
- Job throughput rate (completed/min)
- Per-worker CPU/memory utilization
- Per-worker execution duration histograms
- Worker count vs queue depth correlation
- Stuck job detection (active > 0 but completion rate = 0)

### Security Folder (1 dashboard)

**Security Services** (custom Jsonnet, rework of current security-vault + parts of app-services)
- Caddy: request rates, response codes, upstream latency
- Authelia: authentication events (success/failure), 2FA usage
- CrowdSec: active decisions, banned IPs, alert counts
- Vault: API response times, auth failures, token leases, seal status

### Services Folder (1 dashboard)

**Application Health** (custom Jsonnet, rework of current app-services)
- HTTP probe status for all services: n8n, paperless, netbox, outline, vaultwarden, seafile
- Response time trends per service
- SSL certificate expiry countdown (alert at 14 days)
- Uptime percentage (7d / 30d rolling)

### Totals

- **19 dashboards** across 8 folders
- 7 community JSON (as-is): 5 K8s (dotdc set) + 2 n8n (#24474, #24475)
- 5 adapted community JSON: node-health (#1860), docker-containers (#13077), PostgreSQL (#24298), MariaDB (#14057), Redis (#763)
- 7 custom Jsonnet: homelab-overview, nas-storage, portkey-gateway, openclaw-agents, n8n-queue-workers, security-services, app-health
- **3 datasources**: Mimir, Loki, PostgreSQL (n8n DB on lw-nas)

## Dashboard Validation Framework

Automated verification that dashboards work correctly after deployment — both that queries return real data and that all nodes are reporting.

### Validation Script (`tests/validate.sh`)

Runs after `grr apply` in the deploy GitHub Action and can be run manually. Uses the Grafana API and direct Mimir/Loki queries.

**Level 1: Datasource Connectivity**
```
For each datasource (Mimir, Loki, PostgreSQL):
  → POST /api/ds/query with a trivial query
  → Assert HTTP 200 and non-empty result
```

**Level 2: Node Reachability**

For each node in the registry (lw-main, lw-s1, lw-c1, lw-nas):
```
Query: up{instance=~".*<node_ip>.*"} == 1
Assert: at least 1 series returned per node
Assert: value == 1 (target is up)
```

For K8s specifically:
```
Query: kube_node_info{node="lw-c1"}
Assert: series exists (kube-state-metrics is reporting)
```

**Level 3: Exporter Health**

For each exporter, verify its characteristic metric exists and has recent data:

| Exporter | Smoke Query |
|----------|-------------|
| node_exporter (all nodes) | `node_cpu_seconds_total{instance=~".*<ip>.*"}` |
| docker-exporter | `container_cpu_usage_seconds_total{instance=~".*<ip>.*"}` |
| smartctl_exporter | `smartctl_device_smart_healthy` |
| postgres_exporter | `pg_up{instance=~".*10.0.1.2.*"}` |
| mysqld_exporter | `mysql_up{instance=~".*10.0.1.2.*"}` |
| redis_exporter | `redis_up{instance=~".*10.0.1.2.*"}` |
| kube-state-metrics | `kube_pod_info` |
| n8n main | `n8n_active_workflow_count` |
| n8n workers | `n8n_workflow_execution_duration_seconds_count{instance=~".*worker.*"}` |
| Portkey | `request_count` |
| OpenClaw | `openclaw_tokens_input_total` |
| SnapRAID | `snapraid_disk_fail_probability` |

For each: query Mimir, assert at least 1 series with a sample within the last 5 minutes.

**Level 4: Dashboard Panel Queries**

For each dashboard deployed via Grizzly:
```
→ GET /api/dashboards/uid/<uid>
→ Extract all panel targets (PromQL / LogQL / SQL queries)
→ Execute each query against the appropriate datasource
→ Assert: non-empty result set (at least 1 series or row)
→ Flag panels returning empty data as warnings
```

This catches broken queries, wrong metric names, missing labels, and datasource mismatches.

**Level 5: Cross-Node Coverage**

For dashboards with instance/node template variables (Node Health, Docker Containers, K8s Nodes):
```
→ Get the variable query (e.g., label_values(up, instance))
→ Assert: returned values contain all expected node IPs
→ For each value, run the dashboard's key panel queries with that variable set
→ Assert: non-empty results for each node
```

This ensures every node appears in multi-node dashboards and has actual data.

### Validation Output

The script produces a structured report:

```
VALIDATION REPORT — 2026-03-30T14:00:00Z
==========================================
Datasources:     3/3 connected     ✓
Node reachability: 4/4 nodes up    ✓
Exporter health:  12/12 reporting  ✓
Dashboard panels: 187/192 non-empty (5 warnings)
Cross-node:       4/4 nodes in all multi-node dashboards ✓

WARNINGS:
- security-services/panel-7: query returned empty (CrowdSec may have 0 active decisions)
- ...
```

Exits with code 0 if all checks pass (warnings are OK), code 1 if any datasource, node, or exporter check fails.

### Integration

- Runs automatically in `deploy.yml` GitHub Action after `grr apply`
- Can be triggered manually: `./tests/validate.sh`
- Requires `GRAFANA_URL` and `GRAFANA_TOKEN` (same as Grizzly)
- Optionally runs on a schedule (daily cron) to catch metrics collection regressions

## Implementation Phases

### Phase 1 — Mimir/Loki Migration to lw-nas

- New playbook: `monitoring/mimir-loki-setup/`
- Deploy Mimir + Loki on lw-nas (mergerfs pool storage)
- UFW rules on lw-nas for 9009 + 3100
- Reconfigure all Alloy agents to push to 10.0.1.2
- Update Grafana datasources on lw-main
- Verify end-to-end data flow
- Decommission old containers from lw-main after 1 week

### Phase 2 — NAS Monitoring Infrastructure (parallel after Phase 1)

- New playbook: `monitoring/nas-monitoring-setup/`
- Deploy Alloy + 5 exporters + docker-exporter on lw-nas
- SnapRAID textfile collector cron script
- Verify NAS metrics in Mimir

### Phase 3 — K8s Monitoring + Portkey Upgrade (parallel after Phase 1)

- Upgrade Portkey Helm chart to 2.0 in `kamilandrzejrybacki-inc/helm`
- Add `grafana/k8s-monitoring` ArgoCD application
- Configure scrape targets: kube-state-metrics, kubelet, API server, Portkey, n8n workers
- Remote_write to Mimir on 10.0.1.2
- Verify K8s + Portkey metrics flowing

### Phase 4 — n8n Metrics Enablement (parallel after Phase 1)

- Add N8N_METRICS env vars to `automation/n8n-setup/` (lw-s1 main instance)
- Add N8N_METRICS env vars to n8n-workers Helm chart (lw-c1 K8s)
- Add Alloy scrape target on lw-s1 for n8n `/metrics`
- Add PostgreSQL datasource to Grafana (for workflow analytics dashboard)
- Verify n8n + queue metrics flowing

### Phase 5 — Grizzly GitOps Setup (parallel after Phase 1)

- Create `kamilandrzejrybacki-inc/grafana-dashboards` repo
- Set up Grizzly config, Jsonnet dependencies (grafonnet)
- GitHub Actions workflows (diff on PR, apply on merge)
- Generate Grafana service account token, store as repo secret
- Create folder resources
- Remove file-based provisioning from grafana-stack-setup role
- Set up validation script framework

### Phase 6 — Dashboard Development (after Phases 2-5)

- Import 7 community dashboards as-is, adapt 5 community dashboards
- Build 7 custom Jsonnet dashboards
- Shared Jsonnet lib (common.libsonnet, panels.libsonnet)
- PR-based review for each dashboard via Grizzly pipeline
- Run validation suite, fix any failing panels

### Phase Dependency Graph

```
Phase 1 (Mimir/Loki migration)
  │
  ├──→ Phase 2 (NAS exporters)     ──┐
  ├──→ Phase 3 (K8s + Portkey)     ──┤
  ├──→ Phase 4 (n8n metrics)       ──┼──→ Phase 6 (Dashboards)
  └──→ Phase 5 (Grizzly repo)      ──┘
```

Phases 2, 3, 4, and 5 are independent and run in parallel after Phase 1 completes.

## Decisions and Trade-offs

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Mimir/Loki location | lw-nas | Consolidates data storage on SnapRAID-protected pool |
| Dashboard sync | Grizzly + GitHub Actions | Explicit deploy control, PR-based review, audit trail |
| Dashboard format | Hybrid (JSON + Jsonnet) | Community dashboards as JSON, custom as Jsonnet for DRY |
| Portkey version | 2.0 pre-release | Only version with native Prometheus metrics |
| K8s monitoring | grafana/k8s-monitoring-helm | Official bundle, deploys Alloy + kube-state-metrics + node-exporter |
| Migration strategy | Clean cutover | Simpler than data migration, acceptable for homelab |
| Dashboard repo org | kamilandrzejrybacki-inc | Consistent with existing infra repos (helm) |
| n8n analytics | Direct Postgres datasource | Community dashboard #24475 requires SQL queries against n8n DB |

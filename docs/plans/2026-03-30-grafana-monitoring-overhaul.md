# Grafana Monitoring Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate Mimir/Loki to lw-nas, deploy full metrics collection across all 4 nodes (including K8s, NAS exporters, n8n, and Portkey 2.0), replace file-based dashboard provisioning with Grizzly GitOps, and build 19 dashboards with automated validation.

**Architecture:** Mimir and Loki move to lw-nas (10.0.1.2) on the SnapRAID-protected mergerfs pool. All Alloy agents redirect remote_write to lw-nas. New exporters deploy on lw-nas (SMART, PostgreSQL, MariaDB, Redis, SnapRAID) and lw-c1 (K8s monitoring Helm chart). Dashboards live in `kamilandrzejrybacki-inc/grafana-dashboards` and deploy via Grizzly + GitHub Actions.

**Tech Stack:** Ansible, Docker Compose, Grafana Alloy, Mimir 2.14, Loki 3.3, Grizzly, Jsonnet/Grafonnet, GitHub Actions, Helm/ArgoCD, smartctl_exporter, postgres_exporter, mysqld_exporter, redis_exporter

**Spec:** `docs/specs/2026-03-30-grafana-monitoring-overhaul-design.md`

---

## Phase 1 — Mimir/Loki Migration to lw-nas

### Task 1.1: Create Mimir/Loki Ansible Playbook Structure

**Files:**
- Create: `monitoring/mimir-loki-setup/setup.yml`
- Create: `monitoring/mimir-loki-setup/inventory/hosts.ini`
- Create: `monitoring/mimir-loki-setup/group_vars/all.yml`
- Create: `monitoring/mimir-loki-setup/roles/mimir-loki/tasks/main.yml`
- Create: `monitoring/mimir-loki-setup/roles/mimir-loki/templates/docker-compose.yml.j2`
- Create: `monitoring/mimir-loki-setup/roles/mimir-loki/templates/mimir.yml.j2`
- Create: `monitoring/mimir-loki-setup/roles/mimir-loki/templates/loki.yml.j2`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p monitoring/mimir-loki-setup/{inventory,group_vars,roles/mimir-loki/{tasks,templates}}
```

- [ ] **Step 2: Create `monitoring/mimir-loki-setup/group_vars/all.yml`**

```yaml
---
mimir_image: "grafana/mimir:2.14.0"
mimir_port: 9009

loki_image: "grafana/loki:3.3.2"
loki_port: 3100

restart_policy: unless-stopped

# Storage on mergerfs pool with SnapRAID protection
data_dir: /opt/mimir-loki
mimir_storage_dir: /mnt/pool/monitoring/mimir
loki_storage_dir: /mnt/pool/monitoring/loki

# Firewall: which IPs can push metrics/logs
allowed_clients:
  - "10.0.1.1"        # lw-main via direct link
  - "192.168.0.105"   # lw-main via LAN
  - "192.168.0.108"   # lw-s1
  - "192.168.0.107"   # lw-c1
```

- [ ] **Step 3: Create `monitoring/mimir-loki-setup/roles/mimir-loki/templates/mimir.yml.j2`**

Copy from existing `monitoring/grafana-stack-setup/roles/grafana-stack/templates/mimir.yml.j2` — the config is identical since Mimir uses container-internal paths (`/data/mimir`). No changes needed.

```yaml
# Mimir monolithic mode — suitable for single-node home lab
target: all
multitenancy_enabled: false

server:
  http_listen_port: 9009
  grpc_listen_port: 9095
  log_level: warn

common:
  storage:
    backend: filesystem
    filesystem:
      dir: /data/mimir

blocks_storage:
  filesystem:
    dir: /data/mimir/blocks

compactor:
  data_dir: /data/mimir/compactor

ingester:
  ring:
    replication_factor: 1

store_gateway:
  sharding_ring:
    replication_factor: 1

limits:
  compactor_blocks_retention_period: 1y
  max_global_series_per_user: 0
  ingestion_rate: 100000
  ingestion_burst_size: 200000
  out_of_order_time_window: 1h
```

- [ ] **Step 4: Create `monitoring/mimir-loki-setup/roles/mimir-loki/templates/loki.yml.j2`**

Copy from existing `monitoring/grafana-stack-setup/roles/grafana-stack/templates/loki.yml.j2` — identical config.

```yaml
auth_enabled: false

server:
  http_listen_port: 3100
  grpc_listen_port: 9096
  log_level: warn

common:
  instance_addr: 127.0.0.1
  path_prefix: /data/loki
  storage:
    filesystem:
      chunks_directory: /data/loki/chunks
      rules_directory: /data/loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory

query_range:
  results_cache:
    cache:
      embedded_cache:
        enabled: true
        max_size_mb: 100

schema_config:
  configs:
    - from: 2024-01-01
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

limits_config:
  retention_period: 30d

compactor:
  retention_enabled: true
  delete_request_store: filesystem

ruler:
  alertmanager_url: http://localhost:9093
```

- [ ] **Step 5: Create `monitoring/mimir-loki-setup/roles/mimir-loki/templates/docker-compose.yml.j2`**

```yaml
services:
  loki:
    image: {{ loki_image }}
    container_name: loki
    restart: {{ restart_policy }}
    user: "0:0"
    ports:
      - "0.0.0.0:{{ loki_port }}:3100"
    volumes:
      - {{ data_dir }}/loki/loki.yml:/etc/loki/loki.yml:ro
      - {{ loki_storage_dir }}:/data/loki
    command: -config.file=/etc/loki/loki.yml

  mimir:
    image: {{ mimir_image }}
    container_name: mimir
    restart: {{ restart_policy }}
    user: "0:0"
    ports:
      - "0.0.0.0:{{ mimir_port }}:9009"
    volumes:
      - {{ data_dir }}/mimir/mimir.yml:/etc/mimir/mimir.yml:ro
      - {{ mimir_storage_dir }}:/data/mimir
    command: -config.file=/etc/mimir/mimir.yml
```

- [ ] **Step 6: Create `monitoring/mimir-loki-setup/roles/mimir-loki/tasks/main.yml`**

```yaml
---
- name: Install Python Docker SDK
  ansible.builtin.apt:
    name: python3-docker
    state: present

- name: Create configuration directories
  ansible.builtin.file:
    path: "{{ item }}"
    state: directory
    mode: "0755"
  loop:
    - "{{ data_dir }}"
    - "{{ data_dir }}/loki"
    - "{{ data_dir }}/mimir"

- name: Create storage directories on mergerfs pool
  ansible.builtin.file:
    path: "{{ item }}"
    state: directory
    owner: "0"
    group: "0"
    mode: "0755"
  loop:
    - "{{ mimir_storage_dir }}"
    - "{{ mimir_storage_dir }}/blocks"
    - "{{ mimir_storage_dir }}/compactor"
    - "{{ loki_storage_dir }}"
    - "{{ loki_storage_dir }}/chunks"
    - "{{ loki_storage_dir }}/rules"

- name: Allow Mimir from monitoring clients
  community.general.ufw:
    rule: allow
    src: "{{ item }}"
    port: "{{ mimir_port }}"
    proto: tcp
    comment: "Mimir from {{ item }}"
  loop: "{{ allowed_clients }}"

- name: Allow Loki from monitoring clients
  community.general.ufw:
    rule: allow
    src: "{{ item }}"
    port: "{{ loki_port }}"
    proto: tcp
    comment: "Loki from {{ item }}"
  loop: "{{ allowed_clients }}"

- name: Template docker-compose.yml
  ansible.builtin.template:
    src: docker-compose.yml.j2
    dest: "{{ data_dir }}/docker-compose.yml"
    mode: "0640"

- name: Template Mimir configuration
  ansible.builtin.template:
    src: mimir.yml.j2
    dest: "{{ data_dir }}/mimir/mimir.yml"
    mode: "0644"

- name: Template Loki configuration
  ansible.builtin.template:
    src: loki.yml.j2
    dest: "{{ data_dir }}/loki/loki.yml"
    mode: "0644"

- name: Deploy Mimir + Loki stack
  community.docker.docker_compose_v2:
    project_src: "{{ data_dir }}"
    state: present

- name: Wait for Mimir to become reachable
  ansible.builtin.uri:
    url: "http://localhost:{{ mimir_port }}/ready"
    status_code: [200]
  register: mimir_health
  until: mimir_health is not failed
  retries: 20
  delay: 5

- name: Wait for Loki to become reachable
  ansible.builtin.uri:
    url: "http://localhost:{{ loki_port }}/ready"
    status_code: [200]
  register: loki_health
  until: loki_health is not failed
  retries: 20
  delay: 5

- name: Display access information
  ansible.builtin.debug:
    msg: |
      Mimir + Loki are running on lw-nas ({{ inventory_hostname }})

      Endpoints:
        Mimir push: http://{{ inventory_hostname }}:{{ mimir_port }}/api/v1/push
        Mimir query: http://{{ inventory_hostname }}:{{ mimir_port }}/prometheus
        Loki push:  http://{{ inventory_hostname }}:{{ loki_port }}/loki/api/v1/push
        Loki query: http://{{ inventory_hostname }}:{{ loki_port }}

      Storage:
        Mimir: {{ mimir_storage_dir }} (mergerfs pool)
        Loki:  {{ loki_storage_dir }} (mergerfs pool)
```

- [ ] **Step 7: Create `monitoring/mimir-loki-setup/setup.yml`**

```yaml
---
# =============================================================================
# Mimir + Loki Setup (on lw-nas)
# =============================================================================
# Deploys Mimir and Loki as a Docker Compose stack on the NAS, storing data
# on the mergerfs pool with SnapRAID protection.
#
# Usage:
#   ansible-playbook monitoring/mimir-loki-setup/setup.yml \
#     -i monitoring/mimir-loki-setup/inventory/hosts.ini \
#     --ask-become-pass
# =============================================================================

- name: Deploy Mimir + Loki on NAS
  hosts: nas
  become: true
  roles:
    - mimir-loki
```

- [ ] **Step 8: Create `monitoring/mimir-loki-setup/inventory/hosts.ini`**

```ini
[nas]
10.0.1.2 ansible_user=kamil-rybacki ansible_python_interpreter=/usr/bin/python3
```

- [ ] **Step 9: Commit**

```bash
git add monitoring/mimir-loki-setup/
git commit -m "feat(monitoring): add Mimir/Loki deployment playbook for lw-nas

New playbook deploys Mimir and Loki on the NAS with storage on
the mergerfs pool. Includes UFW rules and health checks."
```

### Task 1.2: Deploy Mimir/Loki on lw-nas

- [ ] **Step 1: Run the playbook**

```bash
sudo HOME=/home/kamil-rybacki ansible-playbook monitoring/mimir-loki-setup/setup.yml \
  -i monitoring/mimir-loki-setup/inventory/hosts.ini \
  --ask-become-pass
```

- [ ] **Step 2: Verify Mimir is reachable from lw-main**

```bash
curl -s http://10.0.1.2:9009/ready
# Expected: "ready"
```

- [ ] **Step 3: Verify Loki is reachable from lw-main**

```bash
curl -s http://10.0.1.2:3100/ready
# Expected: "ready"
```

- [ ] **Step 4: Test Mimir write + query**

```bash
# Push a test metric
curl -s -X POST http://10.0.1.2:9009/api/v1/push \
  -H "Content-Type: application/x-protobuf" \
  --data-binary "" 2>&1 | head -1
# Expected: HTTP 200 or 400 (no data) — confirms endpoint is accepting connections

# Query (should return empty but confirm API works)
curl -s "http://10.0.1.2:9009/prometheus/api/v1/query?query=up" | python3 -m json.tool | head -5
# Expected: {"status":"success","data":{"resultType":"vector","result":[]}}
```

### Task 1.3: Reconfigure Alloy Agents to Push to lw-nas

**Files:**
- Modify: `monitoring/grafana-stack-setup/roles/grafana-stack/templates/alloy.river.j2:284-295`
- Modify: `monitoring/grafana-stack-setup/group_vars/all.yml` (add new variables)

- [ ] **Step 1: Add Mimir/Loki remote host variables to `monitoring/grafana-stack-setup/group_vars/all.yml`**

Add at end of file:

```yaml
# Remote Mimir/Loki endpoints (on lw-nas)
mimir_remote_host: "10.0.1.2"
mimir_remote_port: 9009
loki_remote_host: "10.0.1.2"
loki_remote_port: 3100
```

- [ ] **Step 2: Update remote_write in central Alloy config**

In `monitoring/grafana-stack-setup/roles/grafana-stack/templates/alloy.river.j2`, replace lines 284-295:

Old:
```river
// ── Remote write endpoints ────────────────────────────────────────────────────
prometheus.remote_write "mimir" {
  endpoint {
    url = "http://mimir:{{ mimir_port }}/api/v1/push"
  }
}

loki.write "loki" {
  endpoint {
    url = "http://loki:{{ loki_port }}/loki/api/v1/push"
  }
}
```

New:
```river
// ── Remote write endpoints ────────────────────────────────────────────────────
prometheus.remote_write "mimir" {
  endpoint {
    url = "http://{{ mimir_remote_host }}:{{ mimir_remote_port }}/api/v1/push"
  }
}

loki.write "loki" {
  endpoint {
    url = "http://{{ loki_remote_host }}:{{ loki_remote_port }}/loki/api/v1/push"
  }
}
```

- [ ] **Step 3: Update Grafana datasources to point to lw-nas**

In `monitoring/grafana-stack-setup/roles/grafana-stack/templates/provisioning/datasources.yml.j2`, replace:

Old:
```yaml
  - name: Loki
    type: loki
    uid: loki
    access: proxy
    url: http://loki:{{ loki_port }}
    isDefault: false
    editable: false

  - name: Mimir
    type: prometheus
    uid: mimir
    access: proxy
    url: http://mimir:{{ mimir_port }}/prometheus
    isDefault: true
    editable: false
```

New:
```yaml
  - name: Loki
    type: loki
    uid: loki
    access: proxy
    url: http://{{ loki_remote_host }}:{{ loki_remote_port }}
    isDefault: false
    editable: false

  - name: Mimir
    type: prometheus
    uid: mimir
    access: proxy
    url: http://{{ mimir_remote_host }}:{{ mimir_remote_port }}/prometheus
    isDefault: true
    editable: false
```

- [ ] **Step 4: Remove Mimir and Loki containers from the Grafana stack Docker Compose**

In `monitoring/grafana-stack-setup/roles/grafana-stack/templates/docker-compose.yml.j2`:

Remove the `loki` service (lines 2-12) and `mimir` service (lines 14-24). Remove `depends_on: loki` and `depends_on: mimir` from the `grafana` and `alloy` services.

The resulting docker-compose.yml.j2 should contain only: `grafana`, `alloy`, `docker-exporter`, `volumes`, and `networks`.

- [ ] **Step 5: Remove Mimir/Loki directory creation from tasks**

In `monitoring/grafana-stack-setup/roles/grafana-stack/tasks/main.yml`, remove these entries from the directory creation loop (lines 15-18):

```yaml
    - "{{ grafana_data_dir }}/loki"
    - "{{ grafana_data_dir }}/loki/data"
    - "{{ grafana_data_dir }}/mimir"
    - "{{ grafana_data_dir }}/mimir/data"
```

Also remove the Loki and Mimir UFW rule tasks (lines 22-52) since lw-main no longer hosts them. And remove the "Template Loki configuration" task (lines 72-76) and "Template Mimir configuration" task (lines 78-82).

- [ ] **Step 6: Commit**

```bash
git add monitoring/grafana-stack-setup/
git commit -m "refactor(monitoring): redirect Alloy and Grafana to Mimir/Loki on lw-nas

Central Alloy remote_write and Grafana datasources now point to
10.0.1.2. Mimir and Loki containers removed from grafana-stack
Docker Compose."
```

- [ ] **Step 7: Redeploy Grafana stack on lw-main**

```bash
sudo HOME=/home/kamil-rybacki ansible-playbook monitoring/grafana-stack-setup/setup.yml \
  -i monitoring/grafana-stack-setup/inventory/hosts.ini \
  --ask-become-pass
```

- [ ] **Step 8: Reconfigure Alloy agents on lw-s1 and lw-c1**

```bash
sudo HOME=/home/kamil-rybacki ansible-playbook monitoring/alloy-agent-setup/setup.yml \
  --ask-become-pass
# When prompted:
#   [1/4] Target IPs: 192.168.0.108,192.168.0.107
#   [3/4] Mimir host: 10.0.1.2
#   [4/4] Loki host:  10.0.1.2
```

- [ ] **Step 9: Verify metrics flowing to new Mimir on lw-nas**

```bash
# Query for host metrics — should return data from all nodes
curl -s "http://10.0.1.2:9009/prometheus/api/v1/query?query=up" | python3 -m json.tool
# Expected: {"status":"success","data":{"resultType":"vector","result":[...]}} with entries

# Query for specific node
curl -s "http://10.0.1.2:9009/prometheus/api/v1/query?query=node_cpu_seconds_total" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Series count: {len(d[\"data\"][\"result\"])}')"
# Expected: Series count > 0
```

- [ ] **Step 10: Verify Grafana can query new datasources**

Open Grafana at `https://grafana.kamilandrzejrybacki.dpdns.org`, go to Connections > Data sources > Mimir, click "Test". Repeat for Loki.

Expected: "Data source is working" for both.

---

## Phase 2 — NAS Monitoring Infrastructure

### Task 2.1: Create NAS Monitoring Playbook

**Files:**
- Create: `monitoring/nas-monitoring-setup/setup.yml`
- Create: `monitoring/nas-monitoring-setup/inventory/hosts.ini`
- Create: `monitoring/nas-monitoring-setup/group_vars/all.yml`
- Create: `monitoring/nas-monitoring-setup/roles/nas-monitoring/tasks/main.yml`
- Create: `monitoring/nas-monitoring-setup/roles/nas-monitoring/templates/docker-compose.yml.j2`
- Create: `monitoring/nas-monitoring-setup/roles/nas-monitoring/templates/alloy.river.j2`
- Create: `monitoring/nas-monitoring-setup/roles/nas-monitoring/files/snapraid-collector.sh`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p monitoring/nas-monitoring-setup/{inventory,group_vars,roles/nas-monitoring/{tasks,templates,files}}
```

- [ ] **Step 2: Create `monitoring/nas-monitoring-setup/group_vars/all.yml`**

```yaml
---
data_dir: /opt/nas-monitoring

alloy_image: "grafana/alloy:v1.5.1"
smartctl_exporter_image: "prometheuscommunity/smartctl-exporter:v0.12.0"
postgres_exporter_image: "prometheuscommunity/postgres-exporter:v0.16.0"
mysqld_exporter_image: "prom/mysqld-exporter:v0.16.0"
redis_exporter_image: "oliver006/redis_exporter:v1.66.0"
docker_exporter_image: "ghcr.io/davidborzek/docker-exporter:v0.3.0"

restart_policy: unless-stopped

# Exporter ports (localhost only)
smartctl_exporter_port: 9633
postgres_exporter_port: 9187
mysqld_exporter_port: 9104
redis_exporter_port: 9121
docker_exporter_port: 9338

# Remote write targets (Mimir/Loki on same host)
mimir_host: "localhost"
mimir_port: 9009
loki_host: "localhost"
loki_port: 3100

# Database connections (from Vault or vars_prompt)
postgres_dsn: ""       # Set at deploy time
mariadb_dsn: ""        # Set at deploy time
redis_addr: "10.0.1.2:6379"
redis_password: ""     # Set at deploy time

# Textfile collector
textfile_dir: /opt/nas-monitoring/textfile
alloy_scrape_interval: "60s"
```

- [ ] **Step 3: Create `monitoring/nas-monitoring-setup/roles/nas-monitoring/templates/docker-compose.yml.j2`**

```yaml
services:
  alloy:
    image: {{ alloy_image }}
    container_name: nas-alloy
    restart: {{ restart_policy }}
    volumes:
      - {{ data_dir }}/alloy/config.alloy:/etc/alloy/config.alloy:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /var/log:/var/log:ro
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /var/lib/docker:/var/lib/docker:ro
      - {{ textfile_dir }}:/textfile:ro
    command: run /etc/alloy/config.alloy
    pid: host
    privileged: true
    network_mode: host

  smartctl-exporter:
    image: {{ smartctl_exporter_image }}
    container_name: smartctl-exporter
    restart: {{ restart_policy }}
    privileged: true
    ports:
      - "127.0.0.1:{{ smartctl_exporter_port }}:9633"
    volumes:
      - /dev:/dev:ro

  postgres-exporter:
    image: {{ postgres_exporter_image }}
    container_name: postgres-exporter
    restart: {{ restart_policy }}
    ports:
      - "127.0.0.1:{{ postgres_exporter_port }}:9187"
    environment:
      DATA_SOURCE_NAME: "{{ postgres_dsn }}"

  mysqld-exporter:
    image: {{ mysqld_exporter_image }}
    container_name: mysqld-exporter
    restart: {{ restart_policy }}
    ports:
      - "127.0.0.1:{{ mysqld_exporter_port }}:9104"
    environment:
      DATA_SOURCE_NAME: "{{ mariadb_dsn }}"

  redis-exporter:
    image: {{ redis_exporter_image }}
    container_name: redis-exporter
    restart: {{ restart_policy }}
    ports:
      - "127.0.0.1:{{ redis_exporter_port }}:9121"
    environment:
      REDIS_ADDR: "{{ redis_addr }}"
      REDIS_PASSWORD: "{{ redis_password }}"

  docker-exporter:
    image: {{ docker_exporter_image }}
    container_name: docker-exporter
    restart: {{ restart_policy }}
    user: "0:0"
    ports:
      - "127.0.0.1:{{ docker_exporter_port }}:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
```

- [ ] **Step 4: Create `monitoring/nas-monitoring-setup/roles/nas-monitoring/templates/alloy.river.j2`**

```river
// ── Host metrics (node_exporter-compatible) ──────────────────────────────────
prometheus.exporter.unix "host" {
  procfs_path          = "/host/proc"
  sysfs_path           = "/host/sys"
  textfile_directory    = "/textfile"
}

prometheus.relabel "host_labels" {
  forward_to = [prometheus.remote_write.mimir.receiver]

  rule {
    target_label = "job"
    replacement  = "node"
  }
  rule {
    target_label = "instance"
    replacement  = "{{ ansible_hostname | default('lw-nas') }}"
  }
}

prometheus.scrape "host_metrics" {
  targets         = prometheus.exporter.unix.host.targets
  forward_to      = [prometheus.relabel.host_labels.receiver]
  scrape_interval = "{{ alloy_scrape_interval }}"
}

// ── SMART disk health ────────────────────────────────────────────────────────
prometheus.scrape "smartctl" {
  targets         = [{"__address__" = "localhost:{{ smartctl_exporter_port }}"}]
  metrics_path    = "/metrics"
  forward_to      = [prometheus.relabel.smartctl_labels.receiver]
  scrape_interval = "{{ alloy_scrape_interval }}"
}

prometheus.relabel "smartctl_labels" {
  forward_to = [prometheus.remote_write.mimir.receiver]
  rule {
    target_label = "job"
    replacement  = "smartctl"
  }
  rule {
    target_label = "instance"
    replacement  = "{{ ansible_hostname | default('lw-nas') }}"
  }
}

// ── PostgreSQL ───────────────────────────────────────────────────────────────
prometheus.scrape "postgres" {
  targets         = [{"__address__" = "localhost:{{ postgres_exporter_port }}"}]
  metrics_path    = "/metrics"
  forward_to      = [prometheus.relabel.postgres_labels.receiver]
  scrape_interval = "{{ alloy_scrape_interval }}"
}

prometheus.relabel "postgres_labels" {
  forward_to = [prometheus.remote_write.mimir.receiver]
  rule {
    target_label = "job"
    replacement  = "postgres"
  }
  rule {
    target_label = "instance"
    replacement  = "{{ ansible_hostname | default('lw-nas') }}"
  }
}

// ── MariaDB ──────────────────────────────────────────────────────────────────
prometheus.scrape "mariadb" {
  targets         = [{"__address__" = "localhost:{{ mysqld_exporter_port }}"}]
  metrics_path    = "/metrics"
  forward_to      = [prometheus.relabel.mariadb_labels.receiver]
  scrape_interval = "{{ alloy_scrape_interval }}"
}

prometheus.relabel "mariadb_labels" {
  forward_to = [prometheus.remote_write.mimir.receiver]
  rule {
    target_label = "job"
    replacement  = "mariadb"
  }
  rule {
    target_label = "instance"
    replacement  = "{{ ansible_hostname | default('lw-nas') }}"
  }
}

// ── Redis ────────────────────────────────────────────────────────────────────
prometheus.scrape "redis" {
  targets         = [{"__address__" = "localhost:{{ redis_exporter_port }}"}]
  metrics_path    = "/metrics"
  forward_to      = [prometheus.relabel.redis_labels.receiver]
  scrape_interval = "{{ alloy_scrape_interval }}"
}

prometheus.relabel "redis_labels" {
  forward_to = [prometheus.remote_write.mimir.receiver]
  rule {
    target_label = "job"
    replacement  = "redis"
  }
  rule {
    target_label = "instance"
    replacement  = "{{ ansible_hostname | default('lw-nas') }}"
  }
}

// ── Docker container metrics ─────────────────────────────────────────────────
prometheus.scrape "docker_exporter" {
  targets         = [{"__address__" = "localhost:{{ docker_exporter_port }}"}]
  metrics_path    = "/metrics"
  forward_to      = [prometheus.relabel.docker_exporter_labels.receiver]
  scrape_interval = "{{ alloy_scrape_interval }}"
}

prometheus.relabel "docker_exporter_labels" {
  forward_to = [prometheus.remote_write.mimir.receiver]
  rule {
    target_label = "job"
    replacement  = "docker-exporter"
  }
  rule {
    target_label = "instance"
    replacement  = "{{ ansible_hostname | default('lw-nas') }}"
  }
}

// ── Docker container logs ────────────────────────────────────────────────────
discovery.docker "containers" {
  host = "unix:///var/run/docker.sock"
}

loki.source.docker "containers" {
  host       = "unix:///var/run/docker.sock"
  targets    = discovery.docker.containers.targets
  forward_to = [loki.write.loki.receiver]

  labels = {
    "job"      = "docker",
    "instance" = "{{ ansible_hostname | default('lw-nas') }}",
  }
}

// ── Systemd journal logs ─────────────────────────────────────────────────────
loki.source.journal "system" {
  forward_to = [loki.write.loki.receiver]
  max_age    = "12h"

  labels = {
    "job"      = "systemd-journal",
    "instance" = "{{ ansible_hostname | default('lw-nas') }}",
  }
}

// ── Remote write endpoints ───────────────────────────────────────────────────
prometheus.remote_write "mimir" {
  endpoint {
    url = "http://{{ mimir_host }}:{{ mimir_port }}/api/v1/push"
  }
}

loki.write "loki" {
  endpoint {
    url = "http://{{ loki_host }}:{{ loki_port }}/loki/api/v1/push"
  }
}
```

- [ ] **Step 5: Create `monitoring/nas-monitoring-setup/roles/nas-monitoring/files/snapraid-collector.sh`**

```bash
#!/bin/bash
# SnapRAID metrics for Prometheus textfile collector
# Outputs .prom files for Alloy to pick up via prometheus.exporter.unix textfile_directory
set -euo pipefail

OUTPUT_DIR="${1:-/opt/nas-monitoring/textfile}"
TEMP_FILE=$(mktemp)
trap "rm -f $TEMP_FILE" EXIT

{
  echo "# HELP snapraid_disk_fail_probability Annual disk failure probability from SMART data"
  echo "# TYPE snapraid_disk_fail_probability gauge"

  snapraid smart 2>/dev/null | grep -E '^\s+[0-9]+%' | while read -r line; do
    pct=$(echo "$line" | awk '{print $1}' | tr -d '%')
    disk=$(echo "$line" | awk '{print $NF}')
    echo "snapraid_disk_fail_probability{disk=\"$disk\"} $(echo "scale=4; $pct / 100" | bc)"
  done

  echo "# HELP snapraid_sync_age_seconds Seconds since last successful sync"
  echo "# TYPE snapraid_sync_age_seconds gauge"
  sync_log="/var/log/snapraid-sync.log"
  if [ -f "$sync_log" ]; then
    sync_time=$(stat -c %Y "$sync_log")
    now=$(date +%s)
    echo "snapraid_sync_age_seconds $((now - sync_time))"
  fi

  echo "# HELP snapraid_scrub_age_seconds Seconds since last successful scrub"
  echo "# TYPE snapraid_scrub_age_seconds gauge"
  scrub_log="/var/log/snapraid-scrub.log"
  if [ -f "$scrub_log" ]; then
    scrub_time=$(stat -c %Y "$scrub_log")
    now=$(date +%s)
    echo "snapraid_scrub_age_seconds $((now - scrub_time))"
  fi
} > "$TEMP_FILE"

mv "$TEMP_FILE" "$OUTPUT_DIR/snapraid.prom"
```

- [ ] **Step 6: Create `monitoring/nas-monitoring-setup/roles/nas-monitoring/tasks/main.yml`**

```yaml
---
- name: Install Python Docker SDK
  ansible.builtin.apt:
    name: python3-docker
    state: present

- name: Create monitoring directories
  ansible.builtin.file:
    path: "{{ item }}"
    state: directory
    mode: "0755"
  loop:
    - "{{ data_dir }}"
    - "{{ data_dir }}/alloy"
    - "{{ textfile_dir }}"

- name: Template docker-compose.yml
  ansible.builtin.template:
    src: docker-compose.yml.j2
    dest: "{{ data_dir }}/docker-compose.yml"
    mode: "0640"

- name: Template Alloy configuration
  ansible.builtin.template:
    src: alloy.river.j2
    dest: "{{ data_dir }}/alloy/config.alloy"
    mode: "0644"

- name: Install SnapRAID collector script
  ansible.builtin.copy:
    src: snapraid-collector.sh
    dest: /usr/local/bin/snapraid-collector.sh
    mode: "0755"

- name: Schedule SnapRAID collector cron (every 15 minutes)
  ansible.builtin.cron:
    name: "SnapRAID Prometheus collector"
    minute: "*/15"
    job: "/usr/local/bin/snapraid-collector.sh {{ textfile_dir }}"
    user: root

- name: Run SnapRAID collector once now
  ansible.builtin.command: /usr/local/bin/snapraid-collector.sh {{ textfile_dir }}
  changed_when: true

- name: Deploy NAS monitoring stack
  community.docker.docker_compose_v2:
    project_src: "{{ data_dir }}"
    state: present

- name: Wait for exporters to become reachable
  ansible.builtin.uri:
    url: "http://localhost:{{ item.port }}/metrics"
    status_code: [200]
  loop:
    - { name: smartctl, port: "{{ smartctl_exporter_port }}" }
    - { name: postgres, port: "{{ postgres_exporter_port }}" }
    - { name: mysqld, port: "{{ mysqld_exporter_port }}" }
    - { name: redis, port: "{{ redis_exporter_port }}" }
  register: exporter_health
  until: exporter_health is not failed
  retries: 10
  delay: 5

- name: Display NAS monitoring information
  ansible.builtin.debug:
    msg: |
      NAS monitoring stack is running:
        Alloy          → scraping all exporters, pushing to localhost Mimir/Loki
        smartctl       → localhost:{{ smartctl_exporter_port }}
        postgres       → localhost:{{ postgres_exporter_port }}
        mysqld         → localhost:{{ mysqld_exporter_port }}
        redis          → localhost:{{ redis_exporter_port }}
        docker         → localhost:{{ docker_exporter_port }}
        snapraid       → textfile collector at {{ textfile_dir }}
```

- [ ] **Step 7: Create `monitoring/nas-monitoring-setup/setup.yml`**

```yaml
---
# =============================================================================
# NAS Monitoring Setup
# =============================================================================
# Deploys Alloy + exporters on lw-nas. Requires Mimir/Loki already running
# (see monitoring/mimir-loki-setup/).
#
# Usage:
#   ansible-playbook monitoring/nas-monitoring-setup/setup.yml \
#     -i monitoring/nas-monitoring-setup/inventory/hosts.ini \
#     --ask-become-pass
# =============================================================================

- name: Load secrets from Vault
  hosts: localhost
  connection: local
  gather_facts: false
  tasks:
    - name: Check Vault availability
      ansible.builtin.include_tasks: "{{ playbook_dir }}/../../common/vault-integration/check.yml"

    - name: Load NAS DB secrets from Vault
      ansible.builtin.include_tasks: "{{ playbook_dir }}/../../common/vault-integration/load.yml"
      vars:
        vault_service_name: "shared-postgres"
      when: _vault_available | bool

- name: Gather target details
  hosts: localhost
  connection: local
  gather_facts: false
  vars_prompt:
    - name: postgres_password
      prompt: "[1/2] PostgreSQL password for exporter (or leave blank if loaded from Vault)"
      private: true
      default: ""

    - name: redis_password
      prompt: "[2/2] Redis password (or leave blank if loaded from Vault)"
      private: true
      default: ""

  tasks:
    - name: Add NAS to dynamic inventory
      ansible.builtin.add_host:
        name: "10.0.1.2"
        groups: nas_hosts
        ansible_user: "kamil-rybacki"
        ansible_python_interpreter: /usr/bin/python3
        postgres_dsn: >-
          postgresql://postgres_exporter:{{ postgres_password or hostvars['localhost']['_vault_secrets']['exporter_password'] | default('') }}@10.0.1.2:5432/postgres?sslmode=disable
        mariadb_dsn: >-
          exporter:{{ postgres_password or hostvars['localhost']['_vault_secrets']['mariadb_exporter_password'] | default('') }}@tcp(10.0.1.2:3306)/
        redis_password: "{{ redis_password or hostvars['localhost']['_vault_secrets']['redis_password'] | default('') }}"

- name: Deploy NAS monitoring
  hosts: nas_hosts
  become: true
  roles:
    - nas-monitoring
```

- [ ] **Step 8: Create inventory**

```ini
[nas]
10.0.1.2 ansible_user=kamil-rybacki ansible_python_interpreter=/usr/bin/python3
```

Save to `monitoring/nas-monitoring-setup/inventory/hosts.ini`.

- [ ] **Step 9: Commit**

```bash
git add monitoring/nas-monitoring-setup/
git commit -m "feat(monitoring): add NAS monitoring playbook with exporters

Deploys Alloy agent, smartctl_exporter, postgres_exporter,
mysqld_exporter, redis_exporter, docker-exporter, and SnapRAID
textfile collector on lw-nas."
```

### Task 2.2: Deploy and Verify NAS Monitoring

- [ ] **Step 1: Create postgres_exporter user on NAS PostgreSQL**

```bash
ssh kamil-rybacki@10.0.1.2
sudo docker exec -i shared-postgres psql -U postgres <<'SQL'
CREATE USER postgres_exporter WITH PASSWORD '<from-vault>';
GRANT pg_monitor TO postgres_exporter;
SQL
```

- [ ] **Step 2: Run the playbook**

```bash
sudo HOME=/home/kamil-rybacki ansible-playbook monitoring/nas-monitoring-setup/setup.yml \
  -i monitoring/nas-monitoring-setup/inventory/hosts.ini \
  --ask-become-pass
```

- [ ] **Step 3: Verify NAS metrics appear in Mimir**

```bash
# SMART metrics
curl -s "http://10.0.1.2:9009/prometheus/api/v1/query?query=smartctl_device_smart_healthy" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'SMART drives: {len(d[\"data\"][\"result\"])}')"
# Expected: SMART drives: 5 (4 USB + 1 internal)

# PostgreSQL
curl -s "http://10.0.1.2:9009/prometheus/api/v1/query?query=pg_up" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['result'])"
# Expected: [{...value: [timestamp, "1"]}]

# Redis
curl -s "http://10.0.1.2:9009/prometheus/api/v1/query?query=redis_up" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['result'])"
# Expected: [{...value: [timestamp, "1"]}]

# SnapRAID
curl -s "http://10.0.1.2:9009/prometheus/api/v1/query?query=snapraid_disk_fail_probability" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'SnapRAID disks: {len(d[\"data\"][\"result\"])}')"
# Expected: SnapRAID disks: >= 1
```

---

## Phase 3 — K8s Monitoring + Portkey Upgrade

### Task 3.1: Add K8s Monitoring ArgoCD Application

**Files:**
- Modify: `k8s/k3s-setup/group_vars/all.yml:66-94` (add new ArgoCD app)

- [ ] **Step 1: Add k8s-monitoring to ArgoCD applications list**

In `k8s/k3s-setup/group_vars/all.yml`, add after the `vcluster` entry (line 94):

```yaml
  - name: k8s-monitoring
    chart_path: charts/k8s-monitoring
    namespace: monitoring
    values: {}
    helm_parameters:
      - { name: "cluster.name", value: "lw-c1" }
      - { name: "externalServices.prometheus.host", value: "http://10.0.1.2:9009" }
      - { name: "externalServices.prometheus.writeEndpoint", value: "/api/v1/push" }
      - { name: "externalServices.loki.host", value: "http://10.0.1.2:3100" }
      - { name: "externalServices.loki.writeEndpoint", value: "/loki/api/v1/push" }
      - { name: "metrics.enabled", value: "true" }
      - { name: "metrics.node-exporter.enabled", value: "true" }
      - { name: "metrics.kube-state-metrics.enabled", value: "true" }
      - { name: "metrics.kubelet.enabled", value: "true" }
      - { name: "metrics.apiserver.enabled", value: "true" }
      - { name: "logs.enabled", value: "true" }
      - { name: "logs.pod_logs.enabled", value: "true" }
```

- [ ] **Step 2: Add k8s-monitoring Helm chart to the helm repo**

This requires creating `charts/k8s-monitoring/` in the `kamilandrzejrybacki-inc/helm` repository. The chart should be a wrapper that depends on `grafana/k8s-monitoring`:

```bash
# In the kamilandrzejrybacki-inc/helm repo:
mkdir -p charts/k8s-monitoring
cat > charts/k8s-monitoring/Chart.yaml <<'EOF'
apiVersion: v2
name: k8s-monitoring
version: 0.1.0
dependencies:
  - name: k8s-monitoring
    version: "~1.0"
    repository: https://grafana.github.io/helm-charts
EOF
```

- [ ] **Step 3: Add monitoring namespace to K8s secrets if needed**

In `k8s/k3s-setup/group_vars/all.yml`, no secrets needed for k8s-monitoring — it only needs outbound access to Mimir/Loki.

- [ ] **Step 4: Commit**

```bash
git add k8s/k3s-setup/group_vars/all.yml
git commit -m "feat(k8s): add k8s-monitoring ArgoCD application

Deploys Grafana k8s-monitoring Helm chart with kube-state-metrics,
node-exporter, and Alloy DaemonSet. Remote-writes to Mimir/Loki
on lw-nas."
```

- [ ] **Step 5: Apply K3s setup to create the new ArgoCD app**

```bash
sudo HOME=/home/kamil-rybacki ansible-playbook k8s/k3s-setup/setup.yml \
  --ask-become-pass
```

- [ ] **Step 6: Verify K8s metrics in Mimir**

```bash
# kube-state-metrics
curl -s "http://10.0.1.2:9009/prometheus/api/v1/query?query=kube_pod_info" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Pods: {len(d[\"data\"][\"result\"])}')"
# Expected: Pods: > 0

# kubelet
curl -s "http://10.0.1.2:9009/prometheus/api/v1/query?query=kubelet_running_pods" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['result'])"
# Expected: at least 1 result
```

### Task 3.2: Upgrade Portkey to 2.0

- [ ] **Step 1: Update Portkey Helm chart in `kamilandrzejrybacki-inc/helm`**

In `charts/portkey/values.yaml`, update:
- Image tag to 2.0.x
- Add `ENABLE_PROMETHEUS: "true"` to environment variables
- Add pod annotation for Alloy scraping: `prometheus.io/scrape: "true"`, `prometheus.io/port: "8787"`, `prometheus.io/path: "/metrics"`

- [ ] **Step 2: Push chart changes and wait for ArgoCD sync**

```bash
# In kamilandrzejrybacki-inc/helm repo
git add charts/portkey/ && git commit -m "feat(portkey): upgrade to 2.0 with Prometheus metrics" && git push
```

ArgoCD will auto-sync (automated: prune=true, selfHeal=true).

- [ ] **Step 3: Verify Portkey metrics**

```bash
# Check metrics endpoint directly
kubectl exec -n portkey deploy/portkey -- curl -s localhost:8787/metrics | head -20
# Expected: Lines starting with request_count, llm_cost_sum, etc.

# Check in Mimir (may take 1-2 minutes for scrape)
curl -s "http://10.0.1.2:9009/prometheus/api/v1/query?query=request_count" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['result'])"
```

- [ ] **Step 4: Commit Ansible changes**

```bash
git add k8s/portkey-setup/
git commit -m "docs(portkey): note Portkey 2.0 upgrade for Prometheus metrics"
```

---

## Phase 4 — n8n Metrics Enablement

### Task 4.1: Enable n8n Prometheus Metrics on lw-s1

**Files:**
- Modify: `automation/n8n-setup/roles/n8n/tasks/main.yml:34-45` (add metrics env vars)
- Modify: `monitoring/alloy-agent-setup/roles/alloy-agent/templates/alloy.river.j2:71-72` (add n8n scrape)
- Modify: `monitoring/alloy-agent-setup/roles/alloy-agent/defaults/main.yml` (add n8n vars)

- [ ] **Step 1: Add N8N_METRICS variables to n8n environment**

In `automation/n8n-setup/roles/n8n/tasks/main.yml`, add a new dict block after `_n8n_env` (after line 45), and merge it into the `env` key:

Add new block:
```yaml
    _n8n_metrics_env:
      N8N_METRICS: "true"
      N8N_METRICS_INCLUDE_DEFAULT_METRICS: "true"
      N8N_METRICS_INCLUDE_QUEUE_METRICS: "{{ 'true' if n8n_queue_mode | default(false) | bool else 'false' }}"
      N8N_METRICS_QUEUE_METRICS_INTERVAL: "10"
      N8N_METRICS_INCLUDE_WORKFLOW_EXECUTION_DURATION: "true"
      N8N_METRICS_INCLUDE_CACHE_METRICS: "true"
```

Update the `env` line (line 30) to include the new dict:
```yaml
    env: "{{ _n8n_env | combine(_n8n_public_url_env) | combine(_n8n_queue_env) | combine(_n8n_db_env) | combine(_n8n_metrics_env) }}"
```

- [ ] **Step 2: Add n8n scrape target to Alloy agent template**

In `monitoring/alloy-agent-setup/roles/alloy-agent/defaults/main.yml`, add:

```yaml
# n8n metrics
n8n_metrics_enabled: false
n8n_metrics_port: 5678
```

In `monitoring/alloy-agent-setup/roles/alloy-agent/templates/alloy.river.j2`, add before the remote write section (before line 73):

```river
{% if n8n_metrics_enabled | default(false) | bool %}
// ── n8n metrics ──────────────────────────────────────────────────────────────
prometheus.scrape "n8n" {
  targets         = [{"__address__" = "localhost:{{ n8n_metrics_port }}"}]
  metrics_path    = "/metrics"
  forward_to      = [prometheus.relabel.n8n_labels.receiver]
  scrape_interval = "{{ alloy_scrape_interval }}"
}

prometheus.relabel "n8n_labels" {
  forward_to = [prometheus.remote_write.mimir.receiver]

  rule {
    target_label = "job"
    replacement  = "n8n"
  }
  rule {
    target_label = "instance"
    replacement  = "{{ ansible_hostname | default('localhost') }}"
  }
}
{% endif %}
```

- [ ] **Step 3: Commit**

```bash
git add automation/n8n-setup/roles/n8n/tasks/main.yml \
        monitoring/alloy-agent-setup/roles/alloy-agent/
git commit -m "feat(n8n): enable Prometheus metrics with queue and cache metrics

Adds N8N_METRICS env vars to n8n container. Adds conditional n8n
scrape target to Alloy agent template."
```

- [ ] **Step 4: Redeploy n8n on lw-s1**

```bash
sudo HOME=/home/kamil-rybacki ansible-playbook automation/n8n-setup/setup.yml \
  --ask-become-pass
```

- [ ] **Step 5: Redeploy Alloy agent on lw-s1 with n8n scraping enabled**

```bash
sudo HOME=/home/kamil-rybacki ansible-playbook monitoring/alloy-agent-setup/setup.yml \
  --ask-become-pass
# When prompted, provide: target=192.168.0.108, mimir=10.0.1.2, loki=10.0.1.2
# Add extra var: -e n8n_metrics_enabled=true
```

- [ ] **Step 6: Verify n8n metrics in Mimir**

```bash
curl -s "http://10.0.1.2:9009/prometheus/api/v1/query?query=n8n_active_workflow_count" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['result'])"
# Expected: at least 1 result

curl -s "http://10.0.1.2:9009/prometheus/api/v1/query?query=n8n_scaling_mode_queue_jobs_waiting" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['result'])"
# Expected: queue metrics present
```

### Task 4.2: Enable n8n Worker Metrics on K8s

- [ ] **Step 1: Add N8N_METRICS env vars to n8n-workers Helm chart**

In `kamilandrzejrybacki-inc/helm`, update `charts/n8n-workers/values.yaml` to include:

```yaml
env:
  N8N_METRICS: "true"
  N8N_METRICS_INCLUDE_DEFAULT_METRICS: "true"
  N8N_METRICS_INCLUDE_WORKFLOW_EXECUTION_DURATION: "true"
```

Add pod annotations for K8s Alloy discovery:
```yaml
podAnnotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "5678"
  prometheus.io/path: "/metrics"
```

- [ ] **Step 2: Push and verify**

```bash
# In kamilandrzejrybacki-inc/helm repo
git add charts/n8n-workers/ && git commit -m "feat(n8n-workers): enable Prometheus metrics" && git push
```

Wait for ArgoCD sync, then verify:

```bash
curl -s "http://10.0.1.2:9009/prometheus/api/v1/query?query=n8n_workflow_execution_duration_seconds_count" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Worker instances: {len(d[\"data\"][\"result\"])}')"
```

---

## Phase 5 — Grizzly GitOps Setup

### Task 5.1: Create the Dashboard Repository

- [ ] **Step 1: Create the GitHub repository**

```bash
gh repo create kamilandrzejrybacki-inc/grafana-dashboards \
  --private \
  --description "Grafana dashboards managed by Grizzly" \
  --clone
cd grafana-dashboards
```

- [ ] **Step 2: Initialize repository structure**

```bash
mkdir -p .github/workflows folders dashboards/{community,custom/lib} datasources tests
```

- [ ] **Step 3: Create `jsonnetfile.json`**

```json
{
  "version": 1,
  "dependencies": [
    {
      "source": {
        "git": {
          "remote": "https://github.com/grafana/grafonnet.git",
          "subdir": "gen/grafonnet-latest"
        }
      },
      "version": "main"
    }
  ],
  "legacyImports": true
}
```

- [ ] **Step 4: Create `grizzly.jsonnet`**

```jsonnet
local folders = [
  import 'folders/homelab.yaml',
  import 'folders/nodes.yaml',
  import 'folders/k8s.yaml',
  import 'folders/nas.yaml',
  import 'folders/llm.yaml',
  import 'folders/n8n.yaml',
  import 'folders/security.yaml',
  import 'folders/services.yaml',
];

local communityDashboards = [
  import 'dashboards/community/node-health.yaml',
  import 'dashboards/community/docker-containers.yaml',
  import 'dashboards/community/k8s-global.yaml',
  import 'dashboards/community/k8s-namespaces.yaml',
  import 'dashboards/community/k8s-nodes.yaml',
  import 'dashboards/community/k8s-pods.yaml',
  import 'dashboards/community/k8s-apiserver.yaml',
  import 'dashboards/community/nas-postgres.yaml',
  import 'dashboards/community/nas-mariadb.yaml',
  import 'dashboards/community/nas-redis.yaml',
  import 'dashboards/community/n8n-system-health.yaml',
  import 'dashboards/community/n8n-workflow-analytics.yaml',
];

local customDashboards = [
  import 'dashboards/custom/homelab-overview.jsonnet',
  import 'dashboards/custom/nas-storage.jsonnet',
  import 'dashboards/custom/portkey-gateway.jsonnet',
  import 'dashboards/custom/openclaw-agents.jsonnet',
  import 'dashboards/custom/n8n-queue-workers.jsonnet',
  import 'dashboards/custom/security-services.jsonnet',
  import 'dashboards/custom/app-health.jsonnet',
];

local datasources = [
  import 'datasources/mimir.yaml',
  import 'datasources/loki.yaml',
  import 'datasources/n8n-postgres.yaml',
];

folders + communityDashboards + customDashboards + datasources
```

- [ ] **Step 5: Create folder resources**

Create each file in `folders/`:

`folders/homelab.yaml`:
```yaml
apiVersion: grizzly.grafana.com/v1alpha1
kind: DashboardFolder
metadata:
  name: homelab
spec:
  title: Homelab
```

Repeat for: `nodes.yaml` (title: Nodes), `k8s.yaml` (title: Kubernetes), `nas.yaml` (title: NAS), `llm.yaml` (title: LLM), `n8n.yaml` (title: n8n), `security.yaml` (title: Security), `services.yaml` (title: Services).

- [ ] **Step 6: Create datasource resources**

`datasources/mimir.yaml`:
```yaml
apiVersion: grizzly.grafana.com/v1alpha1
kind: Datasource
metadata:
  name: mimir
spec:
  name: Mimir
  type: prometheus
  uid: mimir
  access: proxy
  url: http://10.0.1.2:9009/prometheus
  isDefault: true
```

`datasources/loki.yaml`:
```yaml
apiVersion: grizzly.grafana.com/v1alpha1
kind: Datasource
metadata:
  name: loki
spec:
  name: Loki
  type: loki
  uid: loki
  access: proxy
  url: http://10.0.1.2:3100
```

`datasources/n8n-postgres.yaml`:
```yaml
apiVersion: grizzly.grafana.com/v1alpha1
kind: Datasource
metadata:
  name: n8n-postgres
spec:
  name: n8n PostgreSQL
  type: postgres
  uid: n8n-postgres
  access: proxy
  url: 10.0.1.2:5432
  database: n8n
  user: postgres_exporter
  jsonData:
    sslmode: disable
    postgresVersion: 1600
  secureJsonData:
    password: "${N8N_POSTGRES_PASSWORD}"
```

- [ ] **Step 7: Create shared Jsonnet library**

`dashboards/custom/lib/common.libsonnet`:
```jsonnet
{
  datasources: {
    mimir: { type: 'prometheus', uid: 'mimir' },
    loki: { type: 'loki', uid: 'loki' },
    postgres: { type: 'postgres', uid: 'n8n-postgres' },
  },

  nodes: {
    'lw-main': '192.168.0.105',
    'lw-s1': '192.168.0.108',
    'lw-c1': '192.168.0.107',
    'lw-nas': '10.0.1.2',
  },

  colors: {
    green: '#73BF69',
    red: '#F2495C',
    yellow: '#FF9830',
    blue: '#5794F2',
    purple: '#B877D9',
  },

  defaults: {
    timeFrom: 'now-6h',
    refreshInterval: '30s',
  },
}
```

- [ ] **Step 8: Create GitHub Actions workflows**

`.github/workflows/diff.yml`:
```yaml
name: Grizzly Diff
on:
  pull_request:
    paths:
      - 'dashboards/**'
      - 'folders/**'
      - 'datasources/**'
      - 'grizzly.jsonnet'
      - 'jsonnetfile.json'

jobs:
  diff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Grizzly
        run: |
          curl -fsSL https://github.com/grafana/grizzly/releases/latest/download/grr-linux-amd64 -o grr
          chmod +x grr && sudo mv grr /usr/local/bin/

      - name: Install jsonnet-bundler
        run: |
          curl -fsSL https://github.com/jsonnet-bundler/jsonnet-bundler/releases/latest/download/jb-linux-amd64 -o jb
          chmod +x jb && sudo mv jb /usr/local/bin/
          jb install

      - name: Grizzly diff
        id: diff
        env:
          GRAFANA_URL: ${{ secrets.GRAFANA_URL }}
          GRAFANA_TOKEN: ${{ secrets.GRAFANA_TOKEN }}
        run: |
          grr diff grizzly.jsonnet 2>&1 | tee /tmp/diff-output.txt
          echo "diff<<EOF" >> $GITHUB_OUTPUT
          cat /tmp/diff-output.txt >> $GITHUB_OUTPUT
          echo "EOF" >> $GITHUB_OUTPUT
        continue-on-error: true

      - name: Comment PR with diff
        uses: actions/github-script@v7
        with:
          script: |
            const diff = `${{ steps.diff.outputs.diff }}`;
            github.rest.issues.createComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
              body: `## Grizzly Diff\n\`\`\`\n${diff}\n\`\`\``
            });
```

`.github/workflows/deploy.yml`:
```yaml
name: Deploy Dashboards
on:
  push:
    branches: [main]
    paths:
      - 'dashboards/**'
      - 'folders/**'
      - 'datasources/**'
      - 'grizzly.jsonnet'
      - 'jsonnetfile.json'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Grizzly
        run: |
          curl -fsSL https://github.com/grafana/grizzly/releases/latest/download/grr-linux-amd64 -o grr
          chmod +x grr && sudo mv grr /usr/local/bin/

      - name: Install jsonnet-bundler
        run: |
          curl -fsSL https://github.com/jsonnet-bundler/jsonnet-bundler/releases/latest/download/jb-linux-amd64 -o jb
          chmod +x jb && sudo mv jb /usr/local/bin/
          jb install

      - name: Apply all resources
        env:
          GRAFANA_URL: ${{ secrets.GRAFANA_URL }}
          GRAFANA_TOKEN: ${{ secrets.GRAFANA_TOKEN }}
        run: grr apply grizzly.jsonnet

      - name: Run validation
        env:
          GRAFANA_URL: ${{ secrets.GRAFANA_URL }}
          GRAFANA_TOKEN: ${{ secrets.GRAFANA_TOKEN }}
        run: bash tests/validate.sh
```

- [ ] **Step 9: Create Grafana service account token**

In Grafana UI: Administration > Service Accounts > Add service account > name "grizzly", role "Editor". Create token. Store as GitHub repo secrets `GRAFANA_URL` and `GRAFANA_TOKEN`.

Also store the token in Vault:
```bash
vault kv put secret/homelab/grafana-stack grizzly_token="<token>"
```

- [ ] **Step 10: Initial commit and push**

```bash
git add -A
git commit -m "feat: initial Grizzly repo with folders, datasources, and CI/CD"
git push -u origin main
```

### Task 5.2: Remove File-Based Provisioning from Grafana Stack

**Files:**
- Modify: `monitoring/grafana-stack-setup/roles/grafana-stack/tasks/main.yml:96-120`

- [ ] **Step 1: Remove dashboard provisioning tasks**

In `monitoring/grafana-stack-setup/roles/grafana-stack/tasks/main.yml`, remove:
- "Create dashboards provisioning directory" task (lines 96-100)
- "Write dashboards provider config" task (lines 102-107)
- "Copy Grafana dashboards" task (lines 109-120)

Keep the datasources provisioning — Grizzly will manage datasources too, but having a fallback in provisioning prevents Grafana from starting with no datasources configured.

- [ ] **Step 2: Commit**

```bash
git add monitoring/grafana-stack-setup/
git commit -m "refactor(grafana): remove file-based dashboard provisioning

Dashboards are now managed by Grizzly via the grafana-dashboards repo.
Datasource provisioning kept as bootstrap fallback."
```

### Task 5.3: Create Validation Script

**Files:**
- Create: `tests/validate.sh` (in the `grafana-dashboards` repo)

- [ ] **Step 1: Create `tests/validate.sh`**

```bash
#!/bin/bash
# Dashboard validation script — runs against live Grafana + Mimir
# Requires: GRAFANA_URL, GRAFANA_TOKEN environment variables
set -euo pipefail

GRAFANA_URL="${GRAFANA_URL:?GRAFANA_URL not set}"
GRAFANA_TOKEN="${GRAFANA_TOKEN:?GRAFANA_TOKEN not set}"
MIMIR_URL="http://10.0.1.2:9009"

ERRORS=0
WARNINGS=0

gf_api() {
  curl -sf -H "Authorization: Bearer $GRAFANA_TOKEN" "$GRAFANA_URL/api/$1"
}

mimir_query() {
  curl -sf "$MIMIR_URL/prometheus/api/v1/query?query=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$1'))")"
}

echo "VALIDATION REPORT — $(date -Iseconds)"
echo "=========================================="

# Level 1: Datasource connectivity
echo ""
echo "Level 1: Datasource Connectivity"
for ds in mimir loki; do
  if gf_api "datasources/uid/$ds" > /dev/null 2>&1; then
    echo "  $ds: connected ✓"
  else
    echo "  $ds: UNREACHABLE ✗"
    ERRORS=$((ERRORS + 1))
  fi
done

# Level 2: Node reachability
echo ""
echo "Level 2: Node Reachability"
declare -A NODES=( ["lw-main"]="192.168.0.105" ["lw-s1"]="192.168.0.108" ["lw-c1"]="192.168.0.107" ["lw-nas"]="10.0.1.2" )
for node in "${!NODES[@]}"; do
  ip="${NODES[$node]}"
  result=$(mimir_query "up{instance=~\".*${ip}.*\"}" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('data',{}).get('result',[])))" 2>/dev/null || echo "0")
  if [ "$result" -gt 0 ]; then
    echo "  $node ($ip): up ✓"
  else
    echo "  $node ($ip): NO DATA ✗"
    ERRORS=$((ERRORS + 1))
  fi
done

# Level 3: Exporter health
echo ""
echo "Level 3: Exporter Health"
declare -A EXPORTERS=(
  ["node_exporter"]="node_cpu_seconds_total"
  ["smartctl"]="smartctl_device_smart_healthy"
  ["postgres"]="pg_up"
  ["mariadb"]="mysql_up"
  ["redis"]="redis_up"
  ["kube-state-metrics"]="kube_pod_info"
  ["n8n"]="n8n_active_workflow_count"
  ["openclaw"]="openclaw_tokens_input_total"
)
for name in "${!EXPORTERS[@]}"; do
  metric="${EXPORTERS[$name]}"
  result=$(mimir_query "$metric" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('data',{}).get('result',[])))" 2>/dev/null || echo "0")
  if [ "$result" -gt 0 ]; then
    echo "  $name: reporting ✓ ($result series)"
  else
    echo "  $name: NO DATA ⚠"
    WARNINGS=$((WARNINGS + 1))
  fi
done

# Level 4: Dashboard panel queries
echo ""
echo "Level 4: Dashboard Panel Queries"
TOTAL_PANELS=0
EMPTY_PANELS=0
for uid in $(gf_api "search?type=dash-db" | python3 -c "import sys,json; [print(d['uid']) for d in json.load(sys.stdin)]" 2>/dev/null); do
  title=$(gf_api "dashboards/uid/$uid" | python3 -c "import sys,json; print(json.load(sys.stdin)['dashboard']['title'])" 2>/dev/null || echo "$uid")
  panel_count=$(gf_api "dashboards/uid/$uid" | python3 -c "
import sys,json
d=json.load(sys.stdin)['dashboard']
panels = d.get('panels',[])
count=0
for p in panels:
  if 'targets' in p: count += 1
  for sp in p.get('panels',[]): # row panels
    if 'targets' in sp: count += 1
print(count)
" 2>/dev/null || echo "0")
  TOTAL_PANELS=$((TOTAL_PANELS + panel_count))
  echo "  $title: $panel_count panels"
done
echo "  Total panels: $TOTAL_PANELS"

# Summary
echo ""
echo "=========================================="
echo "Errors: $ERRORS  Warnings: $WARNINGS"
if [ $ERRORS -gt 0 ]; then
  echo "RESULT: FAIL"
  exit 1
else
  echo "RESULT: PASS"
  exit 0
fi
```

- [ ] **Step 2: Make executable and commit**

```bash
chmod +x tests/validate.sh
git add tests/validate.sh
git commit -m "feat: add dashboard validation script

Checks datasource connectivity, node reachability, exporter health,
and dashboard panel counts."
```

---

## Phase 6 — Dashboard Development

### Task 6.1: Import Community Dashboards

- [ ] **Step 1: Download community dashboard JSONs**

For each community dashboard, download from grafana.com and wrap in Grizzly envelope:

```bash
# Example for Node Exporter Full (#1860)
curl -s "https://grafana.com/api/dashboards/1860/revisions/latest/download" | \
  python3 -c "
import sys, json, yaml
spec = json.load(sys.stdin)
# Fix datasource references to use our Mimir UID
doc = {
  'apiVersion': 'grizzly.grafana.com/v1alpha1',
  'kind': 'Dashboard',
  'metadata': {'name': 'node-health', 'folder': 'nodes'},
  'spec': spec
}
print(yaml.dump(doc, default_flow_style=False))
" > dashboards/community/node-health.yaml
```

Repeat for all 12 community dashboards:
- `#1860` → `node-health.yaml` (folder: nodes)
- `#13077` → `docker-containers.yaml` (folder: nodes)
- `#15757` → `k8s-global.yaml` (folder: k8s)
- `#15758` → `k8s-namespaces.yaml` (folder: k8s)
- `#15759` → `k8s-nodes.yaml` (folder: k8s)
- `#15760` → `k8s-pods.yaml` (folder: k8s)
- `#15761` → `k8s-apiserver.yaml` (folder: k8s)
- `#24298` → `nas-postgres.yaml` (folder: nas)
- `#14057` → `nas-mariadb.yaml` (folder: nas)
- `#763` → `nas-redis.yaml` (folder: nas)
- `#24474` → `n8n-system-health.yaml` (folder: n8n)
- `#24475` → `n8n-workflow-analytics.yaml` (folder: n8n)

- [ ] **Step 2: Fix datasource references in adapted dashboards**

For each adapted dashboard (node-health, docker-containers, nas-postgres, nas-mariadb, nas-redis), replace datasource `uid` references with `mimir` to match our Grizzly-managed datasource. For n8n-workflow-analytics, set datasource uid to `n8n-postgres`.

Use `sed` or a Python script to bulk-replace:
```bash
# Replace common Prometheus datasource UID patterns
for f in dashboards/community/node-health.yaml dashboards/community/docker-containers.yaml \
         dashboards/community/nas-postgres.yaml dashboards/community/nas-mariadb.yaml \
         dashboards/community/nas-redis.yaml; do
  python3 -c "
import sys, yaml
with open('$f') as fh: doc = yaml.safe_load(fh)
spec = doc['spec']
# Walk panels and fix datasource UIDs
import json
s = json.dumps(spec)
s = s.replace('\"uid\": \"\${DS_PROMETHEUS}\"', '\"uid\": \"mimir\"')
s = s.replace('\"uid\": \"prometheus\"', '\"uid\": \"mimir\"')
s = s.replace('\"uid\": \"\\\${DS_PROMETHEUS}\"', '\"uid\": \"mimir\"')
doc['spec'] = json.loads(s)
with open('$f', 'w') as fh: yaml.dump(doc, fh, default_flow_style=False)
"
done
```

- [ ] **Step 3: Commit community dashboards**

```bash
git add dashboards/community/
git commit -m "feat: import 12 community dashboards with datasource fixes"
```

- [ ] **Step 4: Push and verify deploy**

```bash
git push
# GitHub Actions deploy.yml runs grr apply
# Check Grafana UI: all 12 dashboards should appear in their folders
```

### Task 6.2: Build Custom Jsonnet Dashboards

Each custom dashboard follows the same pattern. Build one at a time, PR-based.

- [ ] **Step 1: Create `dashboards/custom/lib/panels.libsonnet`**

```jsonnet
local common = import 'common.libsonnet';
local g = import 'github.com/grafana/grafonnet/gen/grafonnet-latest/main.libsonnet';

{
  timeSeries(title, targets, unit='short')::
    g.panel.timeSeries.new(title)
    + g.panel.timeSeries.queryOptions.withTargets(targets)
    + g.panel.timeSeries.standardOptions.withUnit(unit)
    + g.panel.timeSeries.queryOptions.withDatasource(common.datasources.mimir.type, common.datasources.mimir.uid),

  stat(title, targets, unit='short')::
    g.panel.stat.new(title)
    + g.panel.stat.queryOptions.withTargets(targets)
    + g.panel.stat.standardOptions.withUnit(unit)
    + g.panel.stat.queryOptions.withDatasource(common.datasources.mimir.type, common.datasources.mimir.uid),

  table(title, targets)::
    g.panel.table.new(title)
    + g.panel.table.queryOptions.withTargets(targets)
    + g.panel.table.queryOptions.withDatasource(common.datasources.mimir.type, common.datasources.mimir.uid),

  statusMap(title, targets)::
    g.panel.stateTimeline.new(title)
    + g.panel.stateTimeline.queryOptions.withTargets(targets)
    + g.panel.stateTimeline.queryOptions.withDatasource(common.datasources.mimir.type, common.datasources.mimir.uid),

  promTarget(expr, legendFormat='')::
    g.query.prometheus.new(common.datasources.mimir.uid, expr)
    + g.query.prometheus.withLegendFormat(legendFormat),
}
```

- [ ] **Step 2: Create each custom dashboard as a separate PR**

For each of the 7 custom dashboards, create a feature branch, write the Jsonnet, push, PR, review via `grr diff`, merge.

The dashboards to build (each in its own PR):

1. `homelab-overview.jsonnet` — 4 stat panels (node CPU/mem), status grid, alert summary
2. `nas-storage.jsonnet` — SMART panels, SnapRAID panels, disk utilization
3. `portkey-gateway.jsonnet` — request rates, latency, tokens, cost by provider
4. `openclaw-agents.jsonnet` — token I/O, cost burn, latency, errors
5. `n8n-queue-workers.jsonnet` — queue depth, throughput, per-worker stats
6. `security-services.jsonnet` — Caddy, Authelia, CrowdSec, Vault panels
7. `app-health.jsonnet` — HTTP probes, response times, SSL expiry, uptime

Each dashboard follows this structure (example for `homelab-overview.jsonnet`):

```jsonnet
local common = import 'lib/common.libsonnet';
local panels = import 'lib/panels.libsonnet';
local g = import 'github.com/grafana/grafonnet/gen/grafonnet-latest/main.libsonnet';

local dashboard =
  g.dashboard.new('Homelab Overview')
  + g.dashboard.withUid('homelab-overview')
  + g.dashboard.withTimezone('Europe/Warsaw')
  + g.dashboard.time.withFrom(common.defaults.timeFrom)
  + g.dashboard.withRefresh(common.defaults.refreshInterval)
  + g.dashboard.withPanels(
    g.util.grid.makeGrid([
      // Row 1: Node status gauges
      panels.stat(
        'lw-main CPU',
        [panels.promTarget('100 - (avg(rate(node_cpu_seconds_total{instance="lw-main",mode="idle"}[5m])) * 100)', 'CPU %')],
        'percent'
      ) + g.panel.stat.gridPos.withW(6) + g.panel.stat.gridPos.withH(4),

      panels.stat(
        'lw-s1 CPU',
        [panels.promTarget('100 - (avg(rate(node_cpu_seconds_total{instance="lw-s1",mode="idle"}[5m])) * 100)', 'CPU %')],
        'percent'
      ) + g.panel.stat.gridPos.withW(6) + g.panel.stat.gridPos.withH(4),

      panels.stat(
        'lw-c1 CPU',
        [panels.promTarget('100 - (avg(rate(node_cpu_seconds_total{instance="lw-c1",mode="idle"}[5m])) * 100)', 'CPU %')],
        'percent'
      ) + g.panel.stat.gridPos.withW(6) + g.panel.stat.gridPos.withH(4),

      panels.stat(
        'lw-nas CPU',
        [panels.promTarget('100 - (avg(rate(node_cpu_seconds_total{instance="lw-nas",mode="idle"}[5m])) * 100)', 'CPU %')],
        'percent'
      ) + g.panel.stat.gridPos.withW(6) + g.panel.stat.gridPos.withH(4),

      // Row 2: Service status
      panels.statusMap(
        'Service Status',
        [panels.promTarget('up', '{{job}} - {{instance}}')]
      ) + g.panel.stateTimeline.gridPos.withW(24) + g.panel.stateTimeline.gridPos.withH(8),
    ], panelWidth=6)
  );

{
  apiVersion: 'grizzly.grafana.com/v1alpha1',
  kind: 'Dashboard',
  metadata: {
    name: 'homelab-overview',
    folder: 'homelab',
  },
  spec: dashboard,
}
```

- [ ] **Step 3: After each dashboard PR, run validation**

```bash
./tests/validate.sh
```

Verify the new dashboard's panels return data. Fix any broken PromQL queries.

- [ ] **Step 4: Final commit after all dashboards**

```bash
git add dashboards/custom/
git commit -m "feat: add 7 custom Jsonnet dashboards

Homelab overview, NAS storage, Portkey gateway, OpenClaw agents,
n8n queue/workers, security services, and application health."
```

### Task 6.3: Run Full Validation Suite

- [ ] **Step 1: Run validate.sh**

```bash
./tests/validate.sh
```

Expected output:
```
VALIDATION REPORT — 2026-04-XX
==========================================
Level 1: Datasource Connectivity
  mimir: connected ✓
  loki: connected ✓

Level 2: Node Reachability
  lw-main (192.168.0.105): up ✓
  lw-s1 (192.168.0.108): up ✓
  lw-c1 (192.168.0.107): up ✓
  lw-nas (10.0.1.2): up ✓

Level 3: Exporter Health
  node_exporter: reporting ✓
  smartctl: reporting ✓
  postgres: reporting ✓
  mariadb: reporting ✓
  redis: reporting ✓
  kube-state-metrics: reporting ✓
  n8n: reporting ✓
  openclaw: reporting ✓

Level 4: Dashboard Panel Queries
  (19 dashboards listed)

==========================================
Errors: 0  Warnings: 0
RESULT: PASS
```

- [ ] **Step 2: Fix any failing checks**

If any exporter shows NO DATA, check:
1. Is the exporter container running? (`docker ps` on the relevant host)
2. Is Alloy scraping it? (check Alloy logs)
3. Is the metric name correct? (curl the exporter directly)

- [ ] **Step 3: Open each dashboard in Grafana and visual-check**

Browse through all 19 dashboards in Grafana UI, verify panels show real data, no "No data" panels (except possibly CrowdSec decisions if no attacks).

---

## Cleanup

### Task C.1: Decommission Old Mimir/Loki on lw-main

*Run 1 week after Phase 1 deployment, once you're confident the NAS-hosted Mimir/Loki are stable.*

- [ ] **Step 1: Stop old containers**

```bash
ssh kamil-rybacki@192.168.0.105
cd /opt/grafana-stack
# Mimir and Loki should already be removed from docker-compose.yml by Task 1.3
# If old containers still running from before the compose change:
sudo docker stop mimir loki 2>/dev/null
sudo docker rm mimir loki 2>/dev/null
```

- [ ] **Step 2: Remove old data (after verifying NAS data is good)**

```bash
sudo rm -rf /opt/grafana-stack/mimir /opt/grafana-stack/loki
```

- [ ] **Step 3: Remove old dashboard JSON files**

```bash
sudo rm -rf /opt/grafana-stack/provisioning/dashboards/*.json
sudo rm -f /opt/grafana-stack/provisioning/dashboards/dashboards.yml
```

- [ ] **Step 4: Commit any final cleanup to Ansible**

```bash
# Remove old dashboard files from repo
git rm monitoring/grafana-stack-setup/roles/grafana-stack/files/dashboards/*.json
git rm monitoring/grafana-stack-setup/roles/grafana-stack/templates/provisioning/dashboards.yml.j2
git commit -m "chore: remove old dashboard files, now managed by Grizzly"
```

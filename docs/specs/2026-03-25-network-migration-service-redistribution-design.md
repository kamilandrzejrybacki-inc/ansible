# Network Migration & Service Redistribution Design

**Date:** 2026-03-25
**Status:** Approved
**Scope:** Full IP migration from 10.0.0.x to 192.168.0.x, service redistribution across 4 nodes

## Background

The homelab switched from a direct ethernet interconnect (10.0.0.0/24) to a TP-Link LAN (192.168.0.0/24). All cross-node references using 10.0.0.x are broken. Additionally, two new nodes (lw-c1 compute, lw35 NAS) were added and services need redistribution.

## Target Topology

| Node | Hostname | IP | Role | Services |
|------|----------|----|------|----------|
| Node 1 | lw-main | 192.168.0.105 | Core infra + monitoring | Caddy, Authelia, WireGuard, Pi-hole, Homepage, Grafana stack, LibreNMS, Vault, Nexterm, Lightpanda, **Netbox** |
| Node 2 | lw-s1 | 192.168.0.108 | Automation | n8n, Dify, GitHub runner |
| Compute | lw-c1 | 192.168.0.107 | Compute | Proxmox → K8s, OpenClaw, Ollama |
| NAS | lw35 | 10.0.1.2 | Storage + data | **Paperless**, **Seafile**, shared-postgres, shared-mariadb, shared-redis |

## Networks

| Network | CIDR | Purpose |
|---------|------|---------|
| LAN | 192.168.0.0/24 | Home network via TP-Link, gateway 192.168.0.1 |
| NAS link | 10.0.1.0/24 | Direct USB ethernet: node1 (10.0.1.1) ↔ NAS (10.0.1.2) |
| VPN | 10.8.0.0/24 | WireGuard overlay, gateway 10.8.0.1 |
| Docker homelab-net | 172.20.0.0/24 | Node1 internal Docker network |

## Ansible Variable Strategy

Replace all hardcoded IPs with variables. Each playbook's `group_vars/all.yml` or a shared common vars file defines:

```yaml
node1_ip: "192.168.0.105"    # lw-main
node2_ip: "192.168.0.108"    # lw-s1
nas_ip: "10.0.1.2"           # lw35
compute_ip: "192.168.0.107"  # lw-c1
```

This way future IP changes only require updating one place.

---

## Phase 1: NAS Link Automation

**New playbook:** `infrastructure/nas-link-setup/`

**Runs on:** node1 + NAS

**What it automates:**

On node1:
- Netplan config for USB ethernet adapter `enx00e04c360158` → `10.0.1.1/24`
- `sysctl net.ipv4.ip_forward=1` (persistent)
- UFW MASQUERADE rules in `/etc/ufw/before.rules` for NAT (10.0.1.0/24 → wlx/eno1)
- UFW allow rules for NAS access (SSH, database ports)

On NAS (lw35):
- Netplan config for `eno1` → `10.0.1.2/24`, gateway `10.0.1.1`, DNS `1.1.1.1`
- Install Docker and prerequisites
- UFW setup with rules: allow PostgreSQL (5432), MariaDB (3306), Redis (6379), SSH (22) from `192.168.0.0/24` and `10.0.1.1` only

On node2:
- Static route: `10.0.1.0/24 via 192.168.0.105` so node2 services can reach NAS databases

**Inventory:**

```ini
[nas_link]
192.168.0.105 ansible_user=kamil-rybacki  # node1
10.0.1.2 ansible_user=kamil               # NAS (reachable after node1 config)

[nas_route]
192.168.0.108 ansible_user=kamil           # node2 (needs route to NAS)
```

---

## Phase 2: Databases to NAS

**Playbooks:** Existing `infrastructure/shared-postgres-setup/`, `shared-mariadb-setup/`, `shared-redis-setup/`

**Changes to group_vars:**

```yaml
# shared-postgres-setup/group_vars/all.yml
shared_postgres_bind_address: "0.0.0.0"  # was 10.0.0.2

# shared-mariadb-setup/group_vars/all.yml
shared_mariadb_bind_address: "0.0.0.0"   # was 10.0.0.2

# shared-redis-setup/group_vars/all.yml
shared_redis_bind_address: "0.0.0.0"     # was 10.0.0.2

# common/shared-database/defaults.yml
shared_db_host: "10.0.1.2"               # was 10.0.0.2
```

**Migration steps:**
1. Deploy fresh database containers on NAS
2. Dump data from node2: `pg_dumpall`, `mysqldump --all-databases`, Redis `BGSAVE`
3. Restore on NAS
4. Update all service configs to point to `{{ nas_ip }}`
5. Verify connectivity from node1 and node2
6. Stop old database containers on node2

**Bind address security:** Databases bind to `0.0.0.0` because consumers are on multiple subnets (10.0.1.x, 192.168.0.x). UFW on the NAS restricts access to known source IPs only.

---

## Phase 3: Paperless to NAS + Seafile on NAS

### Paperless Migration

**Playbook:** Existing `files/paperless-setup/`

**Steps:**
1. Deploy Paperless container on NAS
2. Copy media/data directory from node2 → NAS
3. Point at shared-postgres on localhost (same host now)
4. Verify document access
5. Update Caddy: `paperless.{{ domain }}` → `{{ nas_ip }}:8000`
6. Update Paperless MCP: `paperless_api_url: "http://{{ nas_ip }}:8000"`
7. Remove Paperless from node2

### Seafile Deployment

**Playbook:** Existing `files/seafile-setup/`

**Steps:**
1. Deploy Seafile on NAS using shared-mariadb (localhost)
2. Add Caddy entry: `seafile.{{ domain }}` → `{{ nas_ip }}:<port>`
3. Add Homepage entry
4. Configure Authelia OIDC if supported

---

## Phase 4: Netbox to Node1

**Playbook:** Existing `monitoring/netbox-setup/`

**Steps:**
1. Deploy Netbox on node1
2. Database stays on NAS (shared-postgres) — Netbox connects via `{{ nas_ip }}:5432`
3. Redis on NAS — connects via `{{ nas_ip }}:6379`
4. Update Caddy: `netbox.{{ domain }}` → `localhost:8081` (same host, simpler)
5. Join Netbox containers to `homelab-net` for Authelia header auth
6. Remove Netbox from node2

---

## Phase 5: IP Migration — All Config Updates

### Caddy Routing (Caddyfile.j2)

| Subdomain | Old Target | New Target |
|-----------|-----------|------------|
| `n8n.{{ domain }}` | `10.0.0.2:5678` | `{{ node2_ip }}:5678` |
| `netbox.{{ domain }}` | `10.0.0.2:8081` | `localhost:8081` |
| `paperless.{{ domain }}` | `10.0.0.2:8000` | `{{ nas_ip }}:8000` |
| `seafile.{{ domain }}` | (new) | `{{ nas_ip }}:<port>` |
| `dify.{{ domain }}` | (new) | `{{ node2_ip }}:<port>` |
| All node1 services | unchanged | unchanged |

### Monitoring (Alloy)

| Config | Old | New |
|--------|-----|-----|
| Alloy agent (node2) → Mimir | `10.0.0.1:9009` | `{{ node1_ip }}:9009` |
| Alloy agent (node2) → Loki | `10.0.0.1:3100` | `{{ node1_ip }}:3100` |
| New: Alloy agent on NAS | — | Reports to `{{ node1_ip }}:9009` and `{{ node1_ip }}:3100` |
| Netbox scrape | `10.0.0.2:8081` | `localhost:8081` |
| Paperless probe | `10.0.0.2:8000` | `{{ nas_ip }}:8000` |

### Other References

| File | Old | New |
|------|-----|-----|
| `nexterm-setup/group_vars/all.yml` | `10.0.0.1`, `10.0.0.2` | `{{ node1_ip }}`, `{{ node2_ip }}` |
| `paperless-mcp-setup/group_vars/all.yml` | `http://10.0.0.2:8000` | `http://{{ nas_ip }}:8000` |
| `github-runner-setup/inventory/hosts.ini` | `10.0.0.2` | `{{ node2_ip }}` |
| `alloy-agent-setup` templates | `10.0.0.1` references | `{{ node1_ip }}` |

### Homepage Dashboard

No IP changes needed — Homepage uses `https://<subdomain>.{{ domain }}` URLs which route through Caddy. Only updates:
- Add Seafile service entry
- Add Dify service entry
- Update any node labels if shown

### Authelia Access Control

No changes needed. Existing policies already cover:
- `172.20.0.0/24` — Docker bypass
- `10.8.0.0/24` — WireGuard single-factor
- `10.0.0.0/8` — homelab nodes (covers NAS 10.0.1.x)
- `192.168.0.0/16` — LAN single-factor

---

## Phase 6: Node2 Cleanup

After all migrations verified:

1. Stop and remove: shared-postgres, shared-mariadb, shared-redis, Netbox, Paperless containers
2. Remove Docker volumes (after confirming data migrated)
3. Remove `databases-net`, `netbox-net`, `paperless-net` Docker networks
4. Remove service-startup-setup orchestration (databases no longer on node2)
5. Node2 final state: n8n, Dify, GitHub runner, docker-exporter, Alloy agent

---

## Phase 7: lw-c1 Proxmox Setup (Separate Project)

**Not Ansible-driven initially.** Proxmox is a bare-metal hypervisor.

**Steps:**
1. Install Proxmox VE on lw-c1 (USB boot, manual install)
2. Configure networking: bridge to 192.168.0.0/24
3. Use existing `k8s/proxmox-k8s-setup/` playbook to provision K8s clusters
4. Deploy OpenClaw as a container/VM inside Proxmox
5. Deploy Ollama as a container/VM inside Proxmox
6. Remove OpenClaw and Ollama from node1

---

## Execution Order & Dependencies

```
Phase 1: NAS Link Automation
    ↓
Phase 2: Databases → NAS
    ↓
Phase 3: Paperless → NAS + Seafile on NAS  (parallel)
Phase 4: Netbox → Node1                     (parallel)
    ↓
Phase 5: IP Migration — all config updates
    ↓
Phase 6: Node2 cleanup
    ↓
Phase 7: Proxmox on lw-c1 (independent, can start anytime after Phase 1)
```

Phases 3 and 4 can run in parallel since they have no dependency on each other — only on Phase 2 (databases on NAS).

Phase 7 is independent — Proxmox install can begin as soon as the network is set up, but OpenClaw/Ollama migration waits until Proxmox + K8s are ready.

---

## Rollback Strategy

Each phase is independently reversible:
- Database dumps are kept on node2 until Phase 6 cleanup
- Old containers stay stopped (not removed) until verification
- Caddy config changes are atomic — one `netplan apply` / `docker restart caddy`
- If a phase fails, previous services on the old node are still available to restart

---

## Files Modified

| File | Changes |
|------|---------|
| `security/secure-homelab-access/roles/caddy/templates/Caddyfile.j2` | Update proxy targets to variables |
| `security/secure-homelab-access/group_vars/all.yml` | Add node IP variables |
| `common/shared-database/defaults.yml` | `shared_db_host` → `{{ nas_ip }}` |
| `infrastructure/shared-postgres-setup/group_vars/all.yml` | Bind to `0.0.0.0` |
| `infrastructure/shared-mariadb-setup/group_vars/all.yml` | Bind to `0.0.0.0` |
| `infrastructure/shared-redis-setup/group_vars/all.yml` | Bind to `0.0.0.0` |
| `monitoring/grafana-stack-setup/roles/*/templates/alloy.river.j2` | Update scrape targets |
| `monitoring/alloy-agent-setup/` templates | `{{ node1_ip }}` for Mimir/Loki |
| `dev-tools/nexterm-setup/group_vars/all.yml` | Update host IPs |
| `dev-tools/paperless-mcp-setup/group_vars/all.yml` | Update API URL |
| `dev-tools/github-runner-setup/inventory/hosts.ini` | Update node2 IP |
| `security/secure-homelab-access/roles/homepage/templates/services.yaml.j2` | Add Seafile, Dify entries |
| **New:** `infrastructure/nas-link-setup/` | Full NAS networking automation |

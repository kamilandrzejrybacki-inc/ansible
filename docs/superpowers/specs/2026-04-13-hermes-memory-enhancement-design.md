# Design: Hermes Memory Enhancement — Federation + Dreaming + Supermemory

**Date:** 2026-04-13  
**Status:** Approved  
**Scope:** `ansible/infrastructure/hermes-pi`, `helm/charts/docker-builders`, new `hermes-webui-fork` repo

---

## 1. Overview

Extend the Hermes AI assistant (running on lw-pi) with three memory enhancements:

1. **Federated Memory Tab** — unified view of three sources (Local, Supermemory, Dreaming) with per-source isolation
2. **Dreaming** — three-phase nightly memory consolidation ported from OpenClaw (Light → REM → Deep)
3. **Supermemory** — self-hosted memory service deployed from existing source clone

The current `ghcr.io/nesquena/hermes-webui:latest` image is replaced by a custom fork (`hermes-webui-fork`) built via Kaniko on lw-c1's k3s cluster and pushed to a homelab registry.

---

## 2. Architecture

### lw-pi Docker Compose Stack

```
[existing — unchanged]
  hermes-redis
  hermes-broker
  hermes-telegram-bridge
  hermes-portkey

[changed]
  hermes-webui-fork         ← replaces ghcr.io/nesquena/hermes-webui
                              custom arm64 image from hermes-webui-fork repo
                              adds /api/memory/federated + UI section cards

[new]
  hermes-dreaming            ← Python sidecar with crond
                              three-phase memory consolidation
                              writes DREAMS.md + phase reports to memories volume

  hermes-supermemory         ← containerized from /opt/hermes/data/supermemory/
                              internal Docker network only (port 3100)
                              no Caddy exposure
```

### Shared Volumes

| Volume | Mount | Writers | Readers |
|--------|-------|---------|---------|
| `memories-data` | `/opt/hermes/data/memories/` | hermes-dreaming, hermes-webui-fork (existing write path) | hermes-webui-fork |
| `supermemory-data` | internal | hermes-supermemory | hermes-supermemory |

### Build Infrastructure

Images are built as arm64 on lw-c1's k3s cluster via the new `docker-builders` ArgoCD application, then pushed to a homelab registry at `192.168.0.107:30500`. lw-pi pulls from there.

---

## 3. docker-builders — New ArgoCD Application

**Helm chart:** `helm/charts/docker-builders/`  
**ArgoCD:** mirrors existing app pattern (repoURL `kamilandrzejrybacki-inc/helm`, `targetRevision: main`, auto-prune + self-heal, `CreateNamespace=true`)

### Chart contents

| Template | Purpose |
|----------|---------|
| `namespace.yaml` | `docker-builders` namespace |
| `qemu-daemonset.yaml` | `multiarch/qemu-user-static` — registers arm64/armv7 binfmt on every node |
| `registry-deployment.yaml` | `registry:2` — plain HTTP registry |
| `registry-service.yaml` | NodePort `192.168.0.107:30500` — accessible to all homelab nodes |
| `registry-pvc.yaml` | Persistent storage for registry data |
| `kaniko-rbac.yaml` | ServiceAccount + ClusterRole for Kaniko build Jobs |

### values.yaml keys

```yaml
registry:
  nodePort: 30500
  storageSize: 10Gi
  storageClass: local-path

qemu:
  image: multiarch/qemu-user-static:latest

kaniko:
  serviceAccountName: kaniko-builder
```

This chart is reusable for any future custom image builds across the homelab.

---

## 4. Build Flow (Ansible)

The `setup.yml` playbook becomes three plays:

```
Play 1: Bootstrap docker-builders (delegate_to: lw-c1)
  - kubectl apply ArgoCD Application manifest (docker-builders)
  - wait_for registry Pod healthy

Play 2: Build images (delegate_to: lw-c1)
  - Create Kaniko Job: hermes-webui-fork  --customPlatform linux/arm64
  - Create Kaniko Job: hermes-dreaming    --customPlatform linux/arm64
  - Create Kaniko Job: hermes-supermemory --customPlatform linux/arm64
  - wait_for all Jobs → Completed (timeout: 20min)

Play 3: Deploy Hermes (lw-pi) — existing play, extended
  - Write /etc/docker/daemon.json  (insecure-registries: 192.168.0.107:30500)
  - Handler: restart docker (on change only)
  - flush_handlers
  - [existing tasks: dirs, SSH keys, templates, seed USER.md]
  - Create memories/dreaming/{light,rem,deep}/ and memories/.dreams/ dirs
  - docker-compose up (pulls from 192.168.0.107:30500/hermes-*:tag)
```

### New group_vars/all.yml vars

```yaml
hermes_registry: "192.168.0.107:30500"
hermes_webui_fork_tag: "latest"
hermes_dreaming_tag: "latest"
hermes_supermemory_tag: "latest"
hermes_webui_fork_repo: "https://github.com/kamilandrzejrybacki-inc/hermes-webui-fork.git"

memory_source_supermemory_enabled: true
memory_source_dreaming_enabled: true
dreaming_cron: "0 3 * * *"
dreaming_lookback_days: 7
```

### Inventory update required

`inventory/hosts.ini` must gain a `[builders]` group:
```ini
[builders]
lw-c1 ansible_host=192.168.0.107 ansible_user=kamil ansible_python_interpreter=/usr/bin/python3
```

Plays 1 and 2 target `hosts: builders`. Play 3 (lw-pi) is unchanged.

### New required -e flags

```bash
ansible-playbook -i inventory/hosts.ini setup.yml \
  ... (existing flags) ...
  -e supermemory_api_key=XXX
```

---

## 5. hermes-webui-fork Changes

Fork of the upstream `ghcr.io/nesquena/hermes-webui` source. Changes are minimal and scoped — no refactoring of unrelated code.

### Backend

**`api/memory_federation.py`** (new module)

- Orchestrator fans out to three adapters concurrently via `asyncio.gather`
- Per-source timeout: 5s hard cutoff
- Supermemory adapter: exponential backoff (retry ×2 before marking error)
- Any adapter failure returns `status: "error"` for that source; others unaffected
- Structured log emitted per source: `{ event, source, latency_ms, status, error_code }`

**`api/routes.py`** — add one route:

```
GET /api/memory/federated
```

Existing `/api/memory` and `/api/memory/write` routes are untouched.

### Normalized Data Contract

```
FederatedSource {
  name:         "local" | "supermemory" | "dreaming"
  status:       "ok" | "degraded" | "error"
  last_updated: float | null          # unix timestamp
  error:        { code, message } | null
  items:        FederatedItem[]
}

FederatedItem {
  id:           "<source>:<slug>"
  title:        string
  content:      string
  created_at:   float | null
  updated_at:   float | null
  tags:         string[]
  source:       string
  metadata:     dict
}
```

Response always HTTP 200. Source failures are represented in the payload, never as 5xx.

### Source Adapters

| Adapter | Items returned |
|---------|---------------|
| Local | MEMORY.md, USER.md |
| Supermemory | Items from `http://hermes-supermemory:3100` API |
| Dreaming | DREAMS.md + `memories/dreaming/<phase>/YYYY-MM-DD.md` phase reports |

### Frontend — `static/panels.js`

Memory tab gains three section cards (replaces single textarea layout):

```
┌─ Memory ──────────────────────────────────────┐
│  [↻ Refresh]                                   │
│                                                 │
│  ┌─ Local ● ok  updated 2m ago ──────────────┐ │
│  │  MEMORY.md · USER.md                       │ │
│  └────────────────────────────────────────────┘ │
│                                                 │
│  ┌─ Supermemory ● ok  updated 5m ago ─────────┐ │
│  │  item · item · item                         │ │
│  └────────────────────────────────────────────┘ │
│                                                 │
│  ┌─ Dreaming ● ok  updated 3h ago ────────────┐ │
│  │  DREAMS.md · Light 04-13 · REM 04-13        │ │
│  └────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

Status chips: green `●` = ok, yellow `●` = degraded, red `●` = error (inline error message).  
Clicking an item opens read-only preview pane. Write actions remain Local-only (V1: no write-back to remote sources).

---

## 6. hermes-dreaming Sidecar

### Phase Logic (ported from OpenClaw)

**Light phase**
- Read session transcripts from `memories/sessions/` (last `DREAMING_LOOKBACK_DAYS` days)
- Deduplicate candidates against existing `MEMORY.md` entries
- Write staged candidates → `memories/.dreams/staging.json`
- No permanent memory writes

**REM phase**
- Read `staging.json` + recent sessions
- Call LLM (Groq) to extract thematic patterns
- Write reinforcement signals → `memories/.dreams/rem_signals.json`
- Boosts candidate scores for deep phase scoring

**Deep phase**
- Score all candidates using weighted formula:
  `frequency(0.24) · relevance(0.30) · query_diversity(0.15) · recency(0.15) · consolidation(0.10) · conceptual_richness(0.06)`
- Rehydrate snippets — skip stale/deleted content
- Promote qualified entries → append to `MEMORY.md`
- Write diary entry → `DREAMS.md`
- Write phase reports → `memories/dreaming/{light,rem,deep}/YYYY-MM-DD.md`
- Clear `staging.json` + `rem_signals.json`

### Safety

- Lock file at `memories/.dreams/lock` — acquired before Light, released after Deep
- Lock present at startup (crash recovery): log warning, skip run entirely, no writes
- hermes-webui-fork never writes to `memories/.dreams/` — no contention

### Configuration

```
DREAMING_ENABLED=true
DREAMING_CRON=0 3 * * *        # configurable
DREAMING_LOOKBACK_DAYS=7
GROQ_API_KEY=<secret>
HERMES_MEMORIES_DIR=/opt/data/memories
```

### Dockerfile (template)

```dockerfile
FROM python:3.12-slim
RUN pip install --no-cache-dir groq pyyaml
COPY dreaming/ /app/dreaming/
COPY entrypoint.sh /entrypoint.sh
CMD ["/entrypoint.sh"]   # writes crontab from DREAMING_CRON env, starts crond
```

---

## 7. hermes-supermemory Service

- Containerized from existing source at `/opt/hermes/data/supermemory/` (Next.js Turbo monorepo)
- **Build context:** the source must be pushed to a Git repo (e.g. `kamilandrzejrybacki-inc/supermemory`) so Kaniko on lw-c1 can clone it. Alternatively, the Ansible playbook rsync-copies the source from lw-pi to lw-c1 before creating the Kaniko Job. The implementation plan must resolve which approach to use; either is valid.
- Built via Kaniko on lw-c1 with `--customPlatform linux/arm64`
- Exposed on internal `hermes` Docker network at port 3100 only — no Caddy exposure
- hermes-webui-fork calls `http://hermes-supermemory:3100`
- API key injected via `SUPERMEMORY_API_KEY` env var

---

## 8. Secrets / env.j2 additions

```
SUPERMEMORY_API_KEY={{ supermemory_api_key }}
SUPERMEMORY_BASE_URL=http://hermes-supermemory:3100
GROQ_API_KEY={{ groq_api_key }}
DREAMING_ENABLED={{ memory_source_dreaming_enabled }}
DREAMING_CRON={{ dreaming_cron }}
MEMORY_SOURCE_SUPERMEMORY_ENABLED={{ memory_source_supermemory_enabled }}
MEMORY_SOURCE_DREAMING_ENABLED={{ memory_source_dreaming_enabled }}
```

All secrets pass through Ansible `-e` flags; none are committed to the repo.

---

## 9. Testing

### Unit tests — hermes-webui-fork (`tests/test_memory_federation.py`)

- Each adapter returns correct `FederatedSource` shape
- Adapter timeout → `status: "error"`, `error.code: "timeout"`, others unaffected
- Adapter exception → `status: "error"`, `error.code: "adapter_error"`, others unaffected
- Supermemory adapter exponential backoff: fail×2 then succeed → final `status: "ok"`
- Missing `DREAMS.md` → Dreaming adapter returns empty items, `status: "ok"`
- Response always HTTP 200 regardless of source state

### Unit tests — hermes-dreaming (`tests/test_phases.py`, `tests/test_lock.py`)

- Light: dedup correctly excludes candidates already in MEMORY.md
- REM: mock Groq call, verify `rem_signals.json` written with correct schema
- Deep: scoring weights sum to 1.0; MEMORY.md append is idempotent
- Deep: lock file acquired before first write, released after last write
- Crash recovery: lock present at startup → run skipped, no files modified

### Integration tests — hermes-webui-fork (`tests/test_federated_endpoint.py`)

- Happy path: all sources healthy, response shape valid, HTTP 200
- Partial failure: Supermemory times out → 200, `supermemory.status: "error"`, Local + Dreaming intact
- All sources down → 200, all sources `status: "error"` (never 500)
- Structured log emitted per source with `source`, `latency_ms`, `status`, `error_code`

### E2E tests — Playwright (`tests/e2e/memory/federation.spec.ts`)

```typescript
test('all sources healthy — three section cards render with ok chips')
test('supermemory down — error chip shown, local and dreaming unaffected')
test('dreaming disabled — only local and supermemory cards render')
```

Screenshots captured on failure. Targets `http://localhost:8788`.

---

## 10. Non-Goals (V1)

- Cross-source deduplication or search/rerank
- Write-back to Supermemory or Dreaming from the UI
- Dreaming phase manual trigger (cron only in V1)
- Caddy-exposing Supermemory externally

---

## 11. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Supermemory API instability | Per-source 5s timeout + exponential backoff + degraded status |
| Dreaming crashes mid-phase | Lock file prevents re-entry; crash recovery skips run and logs warning |
| Next.js build memory pressure | Built on lw-c1 (15GB RAM) via Kaniko — Pi never runs the build |
| arm64 cross-compilation failures | QEMU DaemonSet on lw-c1 k3s handles binfmt registration |
| lw-pi registry pull fails | insecure-registries configured in `/etc/docker/daemon.json` by Ansible |
| Schema drift in Supermemory API | Adapter-level mapper isolates contract; unit tests catch regressions |

---

## 12. Rollout Strategy

1. Ship with `MEMORY_SOURCE_SUPERMEMORY_ENABLED=false` and `MEMORY_SOURCE_DREAMING_ENABLED=false`
2. Deploy `docker-builders` ArgoCD app and verify registry + QEMU healthy
3. Run Kaniko builds, verify images pullable from lw-pi
4. Enable Dreaming only: verify cron runs, DREAMS.md written, Memory tab Dreaming card renders
5. Enable Supermemory: verify federation endpoint returns all three sources
6. Rollback path: set source flags to `false` and redeploy — Local memory unaffected

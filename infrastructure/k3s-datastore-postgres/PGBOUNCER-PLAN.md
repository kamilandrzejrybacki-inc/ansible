# pgbouncer pooling — plan (NOT yet built)

Connection pooling in front of the shared Postgres on `192.168.0.115`, to cap the
real backend connection count under bursty load. This is the heavier alternative to
the `max_connections` bump (already done, 200→300). **Build only if 300 proves
insufficient** — it touches every app's DSN. Captured here so it's ready when/if
needed.

## Why (and why maybe not yet)

The restart storms came from the backend hitting `max_connections=200` during bursts
(k3s datastore + n8n + coder + prefect opening connections concurrently). Raising to
300 gave headroom and is the cheap fix. pgbouncer is the *structural* fix: apps open
many short-lived/idle connections; a transaction-mode pooler multiplexes them onto a
small backend pool, so 4 apps × N client conns collapse to a handful of server conns.

**Recommendation: defer.** Watch the connection ceiling (Grafana / `pg_stat_activity`
count vs 300). Only build pgbouncer if 300 is still approached under normal peak.

## Scope — which DBs

Live clients on `192.168.0.115:5432` (2026-05-31):

| DB          | user      | role                | pgbouncer? |
|-------------|-----------|---------------------|-----------|
| `k3s_state` | k3s       | k3s control-plane datastore (kine) | **NO — stays direct** |
| `coder`     | coder     | Coder workspaces    | yes |
| `n8n`       | n8n       | n8n automation      | yes |
| `prefect`   | prefect   | Prefect ETL         | yes |
| `sentinel`  | sentinel  | Sentinel            | yes |

**`k3s_state` MUST stay direct.** kine relies on session-level semantics
(LISTEN/NOTIFY for watches, long-lived connections); transaction-mode pooling breaks
it. It is also the lowest-connection consumer — pooling it buys nothing.

## Architecture

- One **pgbouncer** container on `192.168.0.115` (same host, `databases-net` /
  default bridge), listening on **6432**, upstream `localhost:5432`.
- **Transaction pooling** mode, one pool per app DB.
- Pool sizing (start conservative): `default_pool_size=10`, `max_client_conn=200`,
  `min_pool_size=2`, `reserve_pool_size=5`. → app-side client conns can grow without
  growing backend conns beyond ~10/DB (≈40 backend conns for 4 apps vs the current
  ad-hoc count). Leaves the 300 backend ceiling almost entirely for headroom + k3s.
- Auth: `auth_type=scram-sha-256`, `auth_query` against the backend (or a static
  `userlist.txt` rendered from the per-app passwords already in Vault/sops).

Add to the `k3s-datastore-postgres` role (or a sibling `pgbouncer` role) as a second
container; pgbouncer restart does NOT affect the datastore (k3s_state bypasses it).

## ⚠️ Transaction-mode compatibility (the real risk)

Transaction pooling forbids session-scoped features. Per client:
- **prepared statements** — the big one. pgbouncer **1.21+** supports protocol-level
  prepared statements (`max_prepared_statements`); pin a recent image and set it.
  Otherwise disable prepared statements per driver:
  - **n8n** (TypeORM/pg) — OK with protocol prepared-statement support; else set
    statement cache off.
  - **prefect** (SQLAlchemy + asyncpg) — asyncpg uses prepared statements heavily;
    needs `statement_cache_size=0` + `prepared_statement_cache_size=0` in the DSN, or
    rely on pgbouncer 1.21 support. **Test thoroughly.**
  - **sentinel** (psycopg2, simple queries) — fine.
  - **coder** (lib/pq) — fine.
- **LISTEN/NOTIFY, advisory locks, `SET`/session GUCs, `WITH HOLD` cursors** — break
  in transaction mode. Audit prefect/n8n for these; if any are essential, put that DB
  in **session mode** (its own pool) instead of transaction mode.

## Cutover (per app, one at a time, low-risk first)

DSN host:port changes `192.168.0.115:5432` → `192.168.0.115:6432`. Locations:
- **sentinel** — `helm/charts/sentinel/values.yaml` `config.pgPort` + the
  `SENTINEL_DB_DSN` (Vault/sops `sentinel-secrets`). *Do this one first — lowest risk,
  simple psycopg2 queries, easy rollback (flip port back + rollout).*
- **coder** — Coder DB env/secret (k8s).
- **n8n** — `argocd-apps/secrets/bootstrap/sops-n8n-*` (`DB_POSTGRESDB_PORT`).
- **prefect** — Prefect API DB URL (k8s secret) — **last**, after asyncpg prepared-
  statement settings are confirmed.

Order: **sentinel → coder → n8n → prefect.** Soak each ~a day before the next.

## Rollback

Per app: revert the DSN port 6432→5432 + redeploy/rollout that app — it reconnects
directly to the backend. pgbouncer being down only affects apps already cut over;
direct-connect apps and k3s_state are unaffected.

## Effort

~½ day: pgbouncer role + userlist/auth + 4 staged DSN cutovers + prefect asyncpg
testing. Gated on a decision to proceed (and ideally evidence that 300 is insufficient).

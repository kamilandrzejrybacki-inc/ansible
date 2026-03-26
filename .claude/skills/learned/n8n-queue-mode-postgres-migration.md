---
name: n8n-queue-mode-postgres-migration
description: "n8n queue mode requires Postgres + shared encryption key; SQLite→Postgres migration procedure"
user-invocable: false
origin: auto-extracted
---

# n8n Queue Mode Requires Postgres Migration

**Extracted:** 2026-03-26
**Context:** Enabling n8n queue mode (EXECUTIONS_MODE=queue) for distributed workers

## Problem
n8n defaults to SQLite. Queue mode requires a shared database (Postgres) so the main instance and workers share state. Additionally, workers need the N8N_ENCRYPTION_KEY from the main instance to decrypt credentials.

## Solution

1. **Create DB**: `CREATE USER n8n WITH PASSWORD '...'; CREATE DATABASE n8n OWNER n8n;`
2. **Export from SQLite** (before switching):
   ```bash
   docker exec n8n n8n export:workflow --all --output=/tmp/workflows.json
   docker exec n8n n8n export:credentials --all --output=/tmp/credentials.json --decrypted
   ```
3. **Recreate container** with DB env vars: `DB_TYPE=postgresdb`, `DB_POSTGRESDB_HOST/PORT/DATABASE/USER/PASSWORD`
4. **Wait for migrations** to complete (check logs)
5. **Import** (copy files into new container first, old container's /tmp is gone):
   ```bash
   docker cp workflows.json n8n:/tmp/
   docker exec n8n n8n import:workflow --input=/tmp/workflows.json
   docker exec n8n n8n import:credentials --input=/tmp/credentials.json
   ```
6. **Re-create owner account** via `/rest/owner/setup` (user accounts aren't exported)
7. **Workers need**: `N8N_ENCRYPTION_KEY` (from main's `/home/node/.n8n/config` → `encryptionKey` field), `QUEUE_BULL_REDIS_PASSWORD` (if Redis has auth), all DB env vars

## When to Use
- Enabling n8n queue mode with external workers
- Migrating n8n from single-node to distributed execution

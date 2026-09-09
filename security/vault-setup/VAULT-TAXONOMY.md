# Vault secret taxonomy — design (agreed via grilling, 2026-09-09)

## Rules (settled)
1. **Axis = issuer.** `secret/homelab/<issuer>/<credential>`. A credential lives under whoever *issued* it, never under who consumes it.
2. **Per-consumer minting.** One issuer, many consumers → one credential *per consumer*, named by the consumer: `github/cellarette`, `github/runner`, `litellm/hermes-bg`. Share only when the issuer cannot mint multiples.
3. **Path per consumer** (not per-consumer fields) — `github/cellarette` `{token}`, not `github` `{cellarette_token}`.
4. **Internal services are issuers.** `postgres/n8n`, `grafana/admin`, `redis/exporter`, `n8n/encryption`. No `platform/` branch.
5. **Vendor-level issuer**, product in the credential name: `google/drive-n8n`, `google/calendar-hermes`.
6. **Compound credential = one secret, several secret fields**; non-secret parts evicted.
7. **Vault holds credentials only.** Config (`folder_id`, `chat_id`, `base_url`, `host`, `port`, `username`, `client_id`, `ntfy_topic`) → helm values / ansible vars. Forbidden as Vault fields.
8. **Naming:** lowercase kebab paths, fixed depth `homelab/<issuer>/<credential>`, snake_case fields.
9. **Field vocabulary (closed, 11 terms):** credentials — `token`, `api_key`, `password`, `client_secret`, `refresh_token`, `webhook_url`; crypto material — `private_key`, `cert`, `encryption_key` (symmetric keys: n8n encryption, glitchtip secret_key, heartbeat), `salt` (password salts), `signing_key` (HMAC/JWT signing). Nothing else.
10. **Vault = single source of truth** for the whole infra (sops-only secrets + k3s creds fold in). Delivery to k8s = **ESO** (`ExternalSecret` per Secret), replacing sops.
11. **Policies = coarse roles + one restricted tier.** `infra` (rw all), `agents` (read all *except restricted*), `k8s` (ESO: read all except restricted), `humans` (short-lived admin). **Restricted tier** = keys that own the network/hosts/vault itself.
12. **Auth standardization** (sequenced *after* cutover): AppRole for host machine consumers, Kubernetes auth for in-cluster, short-lived tokens for humans. No long-lived static tokens; no root token in any automation.
13. **Cutover = gated big-bang** via `homelab-v2/`: snapshot → build v2 → repoint consumers → validate every consumer → delete old `homelab/` → move v2→`homelab/` → repoint again → verify → delete v2.
14. **n8n pinned:** `n8n-vault-render` wildcard replaced by an explicit allowlist; off the root token.
15. **Canonical source for drifted secrets — RESOLVED BY SCOUT (2026-09-09):** the value the *running workload actually uses* wins. Verified by hashing the live mounted k8s Secret: for all three drifted secrets (`github` runner PAT, `n8n` DB password, `cellarette` admin token) **sops matches live, Vault is stale**. Seed the new tree from the sops copies; discard Vault's.
    Scout also found 3 genuinely orphaned k8s Secrets (no pod/Job references): `cellarette/cellarette-secrets`, `n8n/n8n-secrets`, `e2e-runner/e2e-git-credential` — delivery-layer cleanup, delete during step 5.
16. **Delete + revoke:** `omniroute`, `distillery`, `meepmap`, `open-design` paths; `prefect_etl_api_key` field (Vault + both sops n8n files); dead docs-only refs.

## Restricted tier (agents + k8s CANNOT read)
Whole issuers: `wireguard/*`, `pihole/*`, `cloudflare/*`, `machines/*`, `k3s/*`.
Paths: `postgres/k3s-datastore`, `authelia/admin`, `hashicorp-vault/root`, `hashicorp-vault/unseal`, `hashicorp-vault/mcp-bridge`.

*Refinement (2026-09-09, during build):* `authelia` and `hashicorp-vault` are NOT restricted wholesale — Authelia issues per-app OIDC client secrets (`authelia/<app>-oidc`) and Vault issues the metrics token (`hashicorp-vault/metrics`), both of which ESO must deliver to pods. Only their power keys are denied, by path. (OIDC client secrets were also re-homed from the apps to `authelia/<app>-oidc` — the issuer axis, applied consistently.)

## Target tree — old → new (every live path)

### External vendors
| old | new | fields | notes |
|---|---|---|---|
| `github#runner_pat` | `github/runner` | token | sops copy is live (drifted) |
| `github#cellarette_gh_token` | `github/cellarette` | token | |
| `n8n-workers#blog_github_pat` | `github/blog` | token | |
| `gnhf-bot#gh_token` | `github/gnhf-bot` | token | |
| `openai#api_key` | `openai/shared` | api_key | single org key; consumers: cellarette codex, ESO |
| `anthropic#api_key` | `anthropic/jcodemunch` | api_key | |
| `gemini`, `n8n-workers#deepseek/groq/nvidia_api_key`, `omniroute/*`, `distillery/*` | `deepseek/n8n`, `groq/n8n`, `nvidia/n8n`, `gemini/<consumer>` | api_key | mint per consumer; omniroute/distillery copies deleted |
| `exa#api_key` | `exa/mcp` | api_key | |
| `openrouter`, `portkey`, `requesty` | `openrouter/<consumer>` … | api_key | verify still used; else delete |
| `google/oauth` | `google/oauth-<consumer>` | client_secret, refresh_token | client_id → helm; one per consumer (n8n, rclone-webdav, kindle bridge) |
| `google-drive` (folder IDs) | **evicted** → helm values | — | not a secret |
| `telegram#bot_token`, `Hermes/telegram_confirmer_bot_token`, `blog/telegram-bot`, `pub-reservation/telegram_bot_token`, `n8n-workers#telegram_bot_token` | `telegram/notifier`, `telegram/hermes-confirmer`, `telegram/blog`, `telegram/pub-reservation`, `telegram/n8n` | token | chat_id → config |
| `discord-webhooks#*`, `n8n#discord_webhook_url`, `hermes#discord_bot_token`, `gnhf-bot#discord_bot_token`, `discord-mcp#bot_token`, `hermes#crons_webhook_url` | `discord/feedcord-releases`, `discord/feedcord-agent-ideas`, `discord/feedcord-agent-research`, `discord/grafana-alerts`, `discord/n8n`, `discord/hermes-bot`, `discord/gnhf-bot`, `discord/mcp-bot`, `discord/hermes-crons` | webhook_url / token | |
| `grafana-cloud#sa_token` | `grafana-cloud/sa` | token | separate vendor from self-hosted grafana |
| `cloudflare#api_token`, `infrastructure#cloudflare_token` | `cloudflare/edge` | token | **restricted** |
| `linkedin` | `linkedin/hermes` | token | |

### Internal services as issuers
| old | new | fields | notes |
|---|---|---|---|
| `shared-postgres#*`, `n8n-postgres`, `n8n-workers#db_password`, `notesnook#mongodb_password` | `postgres/exporter`, `postgres/n8n`, `postgres/<app>`… ; `mongodb/notesnook` | password | per-consumer DB users; sops n8n db_password is live (drifted) |
| `shared-postgres#mariadb_exporter_password`, `shared-mariadb` | `mariadb/exporter`, `mariadb/<app>` | password | mis-homed today |
| `shared-postgres#redis_password`, `shared-redis`, `n8n-workers#redis_password` | `redis/exporter`, `redis/n8n`, `redis/<app>` | password | |
| `n8n#encryption_key` | `n8n/encryption` | api_key→**key**? see Q | n8n's own |
| `grafana#admin`, `n8n-workers#grafana_admin_password` | `grafana/admin` | password | single copy; n8n points here |
| `grafana#service_account_token`, `mcp-bridges#grafana_sa_token` | `grafana/mcp-sa` | token | |
| `paperless`, `n8n-workers#paperless_api_token` | `paperless/admin`, `paperless/n8n` | password / token | |
| `netbox`, `mcp-bridges#netbox_token`, `n8n-workers#netbox_token` | `netbox/mcp`, `netbox/n8n` | token | url → config |
| `librenms`, `n8n-workers#librenms_token` | `librenms/n8n` | token | |
| `obsidian#api_key`, `mcp-bridges#obsidian_api_key`, `n8n-workers#obsidian_api_key`, `obsidian-livesync`, `knowledge-vault` | `obsidian/mcp`, `obsidian/n8n`, `obsidian-livesync/admin`, `knowledge-vault/admin` | api_key / password | |
| `argocd`, `argocd-mcp#api_token` | `argocd/admin`, `argocd/mcp` | password / token | base_url → config |
| `litellm#key_*`, `litellm#oidc_secret`, sops-n8n `litellm_api_key`, sops-openviking embed/vlm keys | `litellm/automation`, `litellm/cellarette`, `litellm/hermes-bg`, `litellm/n8n`, `litellm/openviking`, `litellm/oidc` | api_key / client_secret | base_url → config |
| `cellarette#admin_token`, `#mcp_token`, `#authelia_bypass_token`, `cellarette-ssh` | `cellarette/admin`, `cellarette/mcp`, `cellarette/authelia-bypass`, `cellarette/ssh` | token / private_key | admin_token drifted — sops live |
| `hermes#ntfy_bearer_token`, `watchdog#ntfy_token` | `ntfy/hermes`, `ntfy/watchdog` | token | ntfy_topic → config |
| `watchdog#cluster_heartbeat_token` | `watchdog/heartbeat` | token | |
| `vaultwarden`, `seafile`, `jupyterlab*`, `guacamole`, `glitchtip`, `dify`, `decap-cms`, `weylus`, `kosync`, `rclone-webdav`, `termix`, `notesnook#*`, `coder`, `gnhf-bot#crons_webhook_url` | `<service>/admin` (+ `<service>/smtp` etc.) | password / token | per service; verify each is still live |
| sops-openviking `ROOT_API_KEY`, `USER_API_KEY` | `openviking/root`, `openviking/user` | api_key | sops-only today → new |
| `mcp-bridges#vault_token` | `hashicorp-vault/mcp-bridge` | token | **restricted** — a Vault token stored in Vault |
| `hermes#codex_auth_json` | `openai/hermes-codex-auth` | token (json blob) | **written** by ansible — migrate writer |
| `claude-config`, `claude-code` | `anthropic/claude-config-backup` | token (json blob) | **written** by backup.yml — migrate writer; or evict? see Q |
| `Hermes/himalaya` | `<mail-provider>/hermes-himalaya` | password | issuer = the mail account provider — see Q |
| `grafana-stack` | ? | | unknown contents — see Q |

### Restricted (hosts / network / vault)
| old | new | notes |
|---|---|---|
| `infrastructure#wireguard_password` | `wireguard/edge` | **written** by secure-homelab-access — migrate writer |
| `infrastructure#authelia_*` | `authelia/admin` | user/email → config |
| `infrastructure#pihole_password` | `pihole/admin` | |
| `machines/credentials` | `machines/<host>` | |
| c3 env (not in Vault today) | `postgres/k3s-datastore`, `k3s/cluster-token` | HA role renders c3's env from these |
| `/opt/vault/init-keys.json` (root/unseal) | `hashicorp-vault/root`, `hashicorp-vault/unseal` | still file-backed for unseal; Vault copy for ops only — see Q |

## Resolved from field contents (2026-09-09)
| old | new | notes |
|---|---|---|
| `grafana-stack#grizzly_token` | `grafana/grizzly` | token |
| `Hermes/himalaya#APP_KEY` | `google/hermes-himalaya` | password (app password) |
| `claude-config` + `claude-code` | `anthropic/claude-config-backup` | token blob; `backup.yml`/`restore.yml` writers migrated |
| `jupyterlab#grafana_token` | `grafana/jupyterlab` | token; `*_url` → config |
| `jupyterlab-git#token` | `github/jupyterlab` | token |
| `decap-cms#github_client_secret` | `github/decap-cms-oauth` | client_secret; `github_client_id`, `cms_auth_origin` → config |
| `linkedin#client_secret` | `linkedin/hermes-oauth` | client_secret; `client_id`, `redirect_uri` → config |
| `openclaw#gateway_token` / `#telegram_bot_token` / `#n8n_mcp_token` | `openclaw/gateway`, `telegram/openclaw`, `n8n/openclaw-mcp` | `portkey_gateway_key`, `telegram_allowed_users`, `internal_url` dropped/evicted |
| `kosync#md5_auth_key`, `#password_salt`, `#koreader_password_plaintext` | `kosync/auth` | encryption_key / password; host/url/db_path/service/note/impl/backup → config |
| `rclone-webdav#webdav_pass` | `rclone-webdav/auth` | password; `webdav_user`, folders, ids, host, url → config |
| `glitchtip#admin_password`, `#pg_password`, `#oidc_secret`, `#secret_key` | `glitchtip/admin`, `postgres/glitchtip`, `glitchtip/oidc`, `glitchtip/app` | `meepmap_dsn` **deleted** |
| `netbox#admin_password`, `#token` | `netbox/admin`, `netbox/mcp` / `netbox/n8n` | url/email/user → config |
| `guacamole#postgres_password` | `postgres/guacamole` | |
| `termix#api_key`, `#oidc_secret` | `termix/api`, `termix/oidc` | |
| `machines/credentials#password` | `machines/lw-hosts` | **restricted**; usernames → config |

## Expanded delete list (rule 16)
Paths: `omniroute`, `distillery`, `meepmap`, `open-design`, **`portkey`**, **`coder`** (404 — fix the code ref), **`seafile`** (email only), and the six `_initialized`-only placeholders **`dify`, `weylus`, `vaultwarden`, `proxmox`, `bambulab`, `swe-af`**. Fields: `prefect_etl_api_key` (Vault + 2 sops files), `glitchtip#meepmap_dsn`, `openclaw#portkey_gateway_key`. Revoke upstream where they're live vendor keys (the 4 duplicated deepseek/groq/nvidia copies collapse to one per consumer).

## Policies (4 files)
- `infra.hcl`: `secret/data/homelab/*` crud+list, `secret/metadata/homelab/*` list+read+delete.
- `agents.hcl`: `secret/data/homelab/*` read+list, **deny** each restricted issuer path.
- `k8s.hcl` (ESO AppRole): same as agents (read, minus restricted).
- `humans.hcl`: admin, short TTL, via `vault login` not a stored token.

## Cutover runbook (gated big-bang)
Staging prefix is `secret/homelab/v2/` (inside the infra token's writable scope — no policy needed to build), not a separate mount.

0. **Snapshot** — DONE 2026-09-09: full KV export of all 67 secrets, age-encrypted via the argocd-apps sops config, decrypt-verified, at `~/homelab-backups/vault-snapshot-*.json.enc` + mirrored to lw-pi.
1. **Build `homelab/v2/`** — DONE 2026-09-09 via `migrate/build.py --apply`: 91 paths / 95 fields, `--verify` 0 problems, old tree untouched. Drifted secrets seeded from the live sops copies. Per-consumer *minting* (new distinct creds at github/litellm/discord/DB users) is a rotation activity **after** cutover — the structure doesn't wait on vendor UIs; until minted, per-consumer paths carry the same value.
2. **Policies + AppRoles + ESO bootstrap — OPERATOR (root):** `ansible-playbook security/vault-setup/setup.yml --tags taxonomy-policies`. Writes homelab-{infra,agents,k8s,humans}, creates the ansible-infra / cellarette-local / eso AppRoles, mints an eso secret_id and creates `vault-eso-approle` in all 21 ESO namespaces. `n8n-vault-render` is RETIRED (n8n-main-secrets becomes an ExternalSecret with an explicit key list — that IS the pin).
   *Status 2026-09-09:* IaC written + syntax-checked (`roles/vault/tasks/taxonomy-policies.yml`); ESO manifests for all 34 Secrets generated, server-dry-run validated 55/55, committed inert to `argocd-apps/secrets/eso/`; ArgoCD Application staged at `migrate/eso/argocd-app.yaml`. Awaiting the operator run.
3. Repoint consumers → `homelab-v2/`: 4 ansible templates (`common/vault-integration/load.yml` + `store.yml`, `k8s-secrets` group_vars, `n8n-vault-render`), 2 cellarette refs, new `ExternalSecret`s (replacing the 25 sops files) + `SecretStore` per namespace.
4. **Gate:** every consumer re-rendered; every k8s Secret diffed against expected; every service smoke-tested; ansible `k8s-secrets` + ESO reconcile clean; `agents` token proven *denied* on restricted.
5. Delete old `secret/homelab/` (snapshot exists). Revoke upstream: old shared GitHub PATs, dead omniroute/distillery keys.
6. Copy v2 → `secret/homelab/`; repoint consumers → `homelab/` (same 4+2+ESO edits); re-run gate; delete `homelab-v2/`.
7. Follow-on (separate): auth standardization (rule 12); retire `/opt/vault/init-keys.json` root-token automation.

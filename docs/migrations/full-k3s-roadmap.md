# Full-cluster migration roadmap

**Goal:** every workload on a k3s pod, except the networking/VPN
mainframe on `lw-main`. Status as of 2026-05-12.

## Stays on lw-main forever (network/VPN entrypoints)
- Caddy (reverse-proxy + TLS)
- Wg-Easy (Wireguard server)
- Pihole (DNS)
- Authelia (auth gateway)
- cloudflared (Cloudflare tunnel)
- smartd (host SMART monitoring)
- `homelab-router` + `direct-link-router-c1` systemd units (lw-c1 L3 path)

## Already on the cluster
| Service | Namespace | Chart |
|---|---|---|
| n8n-main + workers | `n8n` | `charts/n8n-main`, `charts/n8n-workers` |
| queue-redis | `n8n` | inside n8n-main chart |
| excalidraw frontend/storage/redis | `excalidraw` | `charts/excalidraw` |
| ArgoCD | `argocd` | upstream |
| Headlamp | `headlamp` | upstream chart via `charts/headlamp/argocd-app.yaml` |
| cellarette, distillery, e2e-supabase, hermes, jupyterlab, k8s-monitoring, mcp-servers, meepmap, omniroute, prefect-etl, qdrant, guacamole, docker-builders/registry, github-runners, nfs-provisioner | various | preexisting |

## Pending — order by risk (lowest first)

### Wave 1 — Stateless (lw-main)
- Lightpanda (headless browser, no state)
- Homepage (mounted config.yaml; copy into ConfigMap)
- Crowdsec (LAPI + bouncer, sqlite — but defensible to recreate)

### Wave 2 — Stateless heavy (lw-nas)
- Stirling-PDF (stateless)
- Quartz (static site build; bind-mount of `obsidian-vault` needed → NFS PVC backed by NAS)
- syncthing (config in `~/.config/syncthing`; PVC from NAS)
- filebrowser (sqlite users.db; tiny PVC)

### Wave 3 — Lightweight stateful (lw-main)
- Nexterm (sqlite, small)
- NetBox (Postgres in shared NAS Postgres; the app pod is stateless once DB exists)

### Wave 4 — Heavy stateful (lw-nas)
- shared-postgres → CloudNativePG or zalando-postgres-operator HA cluster; restore from `pg_dump` of every database (n8n, netbox, paperless, …)
- shared-mariadb → mariadb-operator; restore from `mariadb-dump`
- shared-redis → bitnami/redis (master-replica); cache, no data migration
- Paperless-NGX (Postgres + Redis + media PVC); media is biggest single asset on the NAS
- Obsidian REST + CouchDB (CouchDB has live-sync state; needs `couchdb` Helm chart + replication of vault DB)

### Wave 5 — Observability (lw-nas)
- Mimir + Loki (already scraped by `k8s-monitoring`; cluster-side instance can run alongside the NAS instance, then cut Alloy clients over)
- All exporters (smartctl, mysqld, postgres, redis, docker) → DaemonSets/Sidecars in the relevant namespaces

### Wave 6 — Heavy single-tenant (lw-main)
- Grafana (datasource configs + dashboards JSON in `/var/lib/grafana`; provisioning via ConfigMap is the clean migration path)
- Vault (sealed by default; new deploy + transit auto-unseal or re-init from `/opt/vault/init-keys.json`)
- Ollama (model files are 5-30 GB each; needs PVC with enough space + GPU node selector if applicable)

## Per-service migration template

For each remaining service write `docs/migrations/<service>.md` with:

1. **Inventory** — image, current host, ports, environment variables (split into secret vs config), volumes, dependencies.
2. **Backup** — what to dump and where to put it before any pod is touched.
3. **Chart** — `charts/<service>/` with `Chart.yaml`, `values.yaml`, templates (`deployment.yaml`, `service.yaml`, `pvc.yaml`, `configmap.yaml`, `secret-from-vault.yaml` rendered by `n8n-vault-render`-style role).
4. **ArgoCD app** — `charts/<service>/argocd-app.yaml`.
5. **Cutover** — start the cluster pod alongside docker, validate, switch Caddy upstream, stop docker, document new endpoints.
6. **Hygiene** — delete the old `automation/<service>-setup` / `files/<service>-setup` / `monitoring/<service>-setup` playbook; rip out host-IP references from helm + ansible.

## Risk budget per wave

- Wave 1: minutes per service, no data risk.
- Wave 2–3: ~30 min per service; needs an NFS provisioner on the cluster pulling from the NAS — verify the existing `nfs-provisioner` ArgoCD app is healthy first.
- Wave 4–5: schedule per service; needs a backup-restore rehearsal on a scratch namespace first.
- Wave 6: schedule per service; Vault is the riskiest (re-init = re-bootstrap every secret).

## Not done in 2026-05-12 session

Only Wave 1 alloy-agent comment fix and ArgoCD bounce-sync ran. Everything in Waves 2–6 is on the to-do board; pick one service at a time and follow the template above.

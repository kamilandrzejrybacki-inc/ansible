# AGENTS.md — homelab-ansible

## Purpose

Ansible-driven Infrastructure-as-Code for the homelab. Provisions
hosts (lw-c1/c2/c3/main/nas/pi), installs baseline services (Caddy,
n8n, Vault, Docker, k3s bootstrap, dev-tools), and seeds cluster
secrets. Every host-level or off-cluster change starts here.

## Active architecture

- Inventory + host_vars under `inventories/`; roles under `roles/`.
- Secrets encrypted in-place with `sops` (age recipients per env);
  the `k8s-secrets/` role reads sops files and creates namespaced
  Secrets/SopsSecrets in the k3s cluster.
- Vault runs Docker-side on `lw-main` (port 8200, separate docker
  network); ansible reads it via `~/.vault-ansible.yml`.
- Caddy on `lw-main` serves the edge; playbooks render its Caddyfile
  from Jinja templates.
- Tag-gated: `--tags <role>` typical, but the `vault-check` include
  MUST carry `tags:always` or Authelia setups drop dead (learned skill
  `ansible-*`).

## Commands

| What | Command |
|---|---|
| dry run | `ansible-playbook -i inventories/<env> playbooks/<play>.yml --check --diff` |
| run one role | `ansible-playbook -i inventories/<env> playbooks/<play>.yml --tags <role>` |
| decrypt a sops file | `sops --decrypt <file>` |
| edit a sops file | `sops <file>` |
| refresh a k8s secret from sops | `--tags k8s-secrets` (do NOT `kubectl edit`) |
| vault-check | included via `tags:always`; failing this is fatal |
| ping hosts | `ansible all -m ping -i inventories/<env>` |

## Constraints

- **`--tags <x>` is dangerous.** Any include that isn't tagged
  `always` gets skipped and can silently deploy half a stack. Audit
  new roles for this.
- **Never `kubectl edit` a secret managed by k8s-secrets/.** Change
  the sops file, re-run the role.
- **k3s datastore is external Postgres on lw-nas — always.** Never
  revert to etcd/sqlite. New nodes join as workers only.
- **caddy edge non-interactive deploy:** `vars_prompt` fails headless;
  pass `saved_*` as `-e` JSON.
- **Copy of edge Caddyfile.** `docker restart caddy` (not reload) —
  reload does not pick up new blocks in some configurations.

## Boundaries

- **This repo owns:** host provisioning, base services, cluster
  bootstrap, Sops-managed cluster secrets.
- **This repo does NOT own:** Helm charts (`helm`), ArgoCD apps
  (`argocd-apps`), workflow definitions (`n8n-workflows`), grafana
  dashboards (`grafana-dashboards`).
- **Do not read from or reference:** removed services (prefect-etl,
  omnigent, sentinel, kairos, omniroute, cellarette-bridge). If a
  memory says "REMOVED" or "DEPRECATED", the code path no longer
  exists — do not reason as if it does.

## Detailed documentation

- Role-level `README.md` under `roles/<name>/`.
- `docs/` where present.
- Learned skills captured in `~/.claude/skills/learned/ansible-*`.

## Memory rules for this project

- **Reads:** Obsidian `projects/homelab-ansible/`, `infrastructure/`
  items with `project: homelab-ansible`, and this file.
- **Writes:** never rewrite this file, `roles/**/README.md`, or
  `docs/decisions/*` without an explicit "yes" in the current turn.
- **Semantic memory scope:** `project_id = homelab-ansible`.

## Escalation

None. Blast radius stays inside the homelab LAN.

<!-- graft:start -->
## Graft — repo context graph

This repo is indexed in `graft/`: small linked markdown nodes that explain each
system and carry exact file:line spans, kept in sync with the code through git.

For ANY task here — understanding how something works, finding where code lives,
or scoping a change — get context from the graph before grepping or opening
source files. Re-ask freely (it's cheap) and reuse literal identifiers you
already have (symbol, error string, file name) as the query. New to this repo?
Run `graft map` first — a token-budgeted orientation (dir clusters, hubs,
hotspots), no LLM, no key.

- Run `graft ask "<your question>" --source` → ranked nodes with the relevant
  code spans inlined (each hit's ≤8-line crux by default; `--full` for whole
  definitions when the crux isn't enough). Match the tool to the task shape:
  for understanding or editing, the top node IS the answer — cite its
  `covers:` file:line spans and edit straight from `--source`. For
  exhaustive tasks ("every occurrence / every caller of this pattern"), ranked
  results are top-N, not complete — run `graft grep "<literal>"` instead
  (exhaustive over indexed files, grouped by enclosing symbol), falling back
  to raw `grep -rn` only for unindexed files.
- `graft skeleton <file>` → every definition's signature + span, ~10× cheaper
  than reading the file; use it to skim an API surface.
- `graft callers <symbol>` gives precomputed, exact edges — who calls this.
  Add `--direction out` for what it calls, or `--depth N` to walk
  transitively for the full blast radius. For structural questions, skip
  ranking and use this directly.
- Or browse: `graft/INDEX.md` lists every node; follow the links.
- Monorepos and folders of multiple repos rank fairly across sub-projects —
  hits carry `[scope/]` labels naming which one they're from. Narrow with
  `graft ask "<task>" --in <scope>/` once you know where you're working.

If a returned span is truncated ("+N more lines"), open the file at that exact
range before finalizing. Only open source files when a node genuinely lacks a
needed detail, and then at the exact file:line the node points to — never
re-read whole files.

After big code changes, refresh the graph with `graft build` (deterministic,
no API key, $0).
<!-- graft:end -->

## Tool Selection Policy — Cellarette First

**Before reaching for `Bash`, `WebFetch`, or any built-in, check whether a Cellarette MCP tool exists for the task.** Cellarette is the homelab tool aggregator — it bundles every backend behind one MCP server. Available tool families:

| Need | Cellarette tool |
|------|----------------|
| Read/write secrets | `vault__*` |
| Query metrics, logs, dashboards | `grafana__*` |
| Inspect ArgoCD apps, k8s state | `argocd__*` |
| Search personal docs/notes | `obsidian__*`, `distillery__*` |
| Look up library/framework docs | `context7__*` |
| Cross-session knowledge graph | `memory__*` |
| Step-by-step reasoning scratchpad | `sequential_thinking__*` |
| Headless browser, web scraping, JS sites | `lightpanda__*` |
| Run GitHub CLI (issues/PRs/repos) | `gh__help` then `gh__run` |
| Run Codex CLI from inside Claude | `codex__help` then `codex__run` |

**Rules:**
1. **Search cellarette tools first.** If the task fits a category above, use the cellarette tool — do NOT shell out to `curl`, `kubectl`, `gh`, etc.
2. **CLI passthroughs (`gh`, `codex`):** call `<name>__help` once to learn the subcommand schema, then `<name>__run` with typed argv. Do not use raw `Bash gh ...`.
3. **Bash is a last resort** for tasks that genuinely don't fit any MCP category (file system manipulation, build/test runners, local dev servers).
4. **If a tool seems missing**, ask the user before improvising with `Bash` — cellarette tools are added frequently and a new backend may exist.

## Code Exploration Policy

Always use jCodemunch-MCP tools for code navigation. Never fall back to Read, Grep, Glob, or Bash for code exploration.
**Exception:** Use `Read` when you need to edit a file — the agent harness requires a `Read` before `Edit`/`Write` will succeed. Use jCodemunch tools to *find and understand* code, then `Read` only the specific file you're about to modify.

**Start any session:**
1. `resolve_repo { "path": "." }` — confirm the project is indexed. If not: `index_folder { "path": "." }`
2. `suggest_queries` — when the repo is unfamiliar

**Finding code:**
- symbol by name → `search_symbols` (add `kind=`, `language=`, `file_pattern=` to narrow)
- string, comment, config value → `search_text` (supports regex, `context_lines`)
- database columns (dbt/SQLMesh) → `search_columns`

**Reading code:**
- before opening any file → `get_file_outline` first
- one or more symbols → `get_symbol_source` (single ID → flat object; array → batch)
- symbol + its imports → `get_context_bundle`
- specific line range only → `get_file_content` (last resort)

**Repo structure:**
- `get_repo_outline` → dirs, languages, symbol counts
- `get_file_tree` → file layout, filter with `path_prefix`

**Relationships & impact:**
- what imports this file → `find_importers`
- where is this name used → `find_references`
- is this identifier used anywhere → `check_references`
- file dependency graph → `get_dependency_graph`
- what breaks if I change X → `get_blast_radius`
- what symbols actually changed since last commit → `get_changed_symbols`
- find unreachable/dead code → `find_dead_code`
- class hierarchy → `get_class_hierarchy`

## Session-Aware Routing

**Opening move for any task:**
1. `plan_turn { "repo": "...", "query": "your task description" }` — get confidence + recommended files
2. Obey the confidence level:
   - `high` → go directly to recommended symbols, max 2 supplementary reads
   - `medium` → explore recommended files, max 5 supplementary reads
   - `low` → the feature likely doesn't exist. Report the gap to the user. Do NOT search further hoping to find it.

**Interpreting search results:**
- If `search_symbols` returns `negative_evidence` with `verdict: "no_implementation_found"`:
  - Do NOT re-search with different terms hoping to find it
  - Do NOT assume a related file (e.g. auth middleware) implements the missing feature (e.g. CSRF)
  - DO report: "No existing implementation found for X. This would need to be created."
  - DO check `related_existing` files — they show what's nearby, not what exists
- If `verdict: "low_confidence_matches"`: examine the matches critically before assuming they implement the feature

**After editing files:**
- If PostToolUse hooks are installed (Claude Code only), edited files are auto-reindexed
- Otherwise, call `register_edit` with edited file paths to invalidate caches and keep the index fresh
- For bulk edits (5+ files), always use `register_edit` with all paths to batch-invalidate

**Token efficiency:**
- If `_meta` contains `budget_warning`: stop exploring and work with what you have
- If `auto_compacted: true` appears: results were automatically compressed due to turn budget
- Use `get_session_context` to check what you've already read — avoid re-reading the same files

## Code Review Policy — Thermo-Nuclear Standard

Whenever you perform **any** review — code review, PR review, diff review, pre-merge audit, or a review requested through a slash command or sub-agent — apply the **thermo-nuclear-code-quality-review** skill (`~/.claude/skills/thermo-nuclear-code-quality-review/SKILL.md`) as the baseline standard.

- Treat its Non-Negotiable Additional Standards and Approval Bar as the default bar for every review, not an opt-in mode.
- This applies regardless of who asks or how the review is triggered.
- The skill sets `disable-model-invocation: true`, so it will not auto-trigger — load and follow `SKILL.md` explicitly at the start of any review task.
- Lead with structural and maintainability findings; do not flood the review with low-value nits when larger structural issues exist.

@RTK.md

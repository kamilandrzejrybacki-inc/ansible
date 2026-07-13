# AXI integration — final handoff (2026-07-13)

Adopting selected AXI tools into **Hermes** (in-cluster agent, GitOps) and **Claude Code**
(ansible-managed), with Hermes kept as the single orchestrator/task source of truth. No
competing orchestrator or second task DB introduced.

## 1. Repositories & configuration sources discovered

| Source | Owns | Notes |
|--------|------|-------|
| `~/Code/helm` (`charts/hermes`, `charts/cellarette`, `charts/whisper`) | Hermes + MCP aggregator + STT, GitOps | ArgoCD `targetRevision: main`, **auto-sync + selfHeal ON** |
| `~/Code/ansible/k8s/k3s-setup/group_vars/all.yml` | app-of-apps → ArgoCD Applications | whisper app added here; needs an ansible run to render/apply (no ApplicationSet) |
| `~/Code/ansible/dev-tools/claude-code-setup` | Claude Code config (`files/claude/**` copied to `~/.claude`) | **live drift** vs source in settings.json + CLAUDE.md (pre-existing, untouched) |
| upstream `github.com/kunchenguid/*` | the AXI tool suite | all MIT except programbench-bench (no license → methodology only) |
| upstream `NousResearch/hermes-agent` | Hermes image (pinned git tag via `charts/hermes/image`) | STT is native (`stt_enabled: true`), backend pluggable |

Image registries: helm/ansible → `github.com/kamilandrzejrybacki-inc/*`.

## 2. Branches created (PR-ready, local; not pushed at time of writing)

- `helm` → `feat/axi-integration` (6 commits: f03fc0f, 68305ed, 8464eec, b55ad9d, 7f46bb5, 51d24a7)
- `ansible` → `feat/axi-integration` (7 commits: 0a31e1c, fcfec2e, 5af5890, fad0c8e, cc806a5, 6bbce42, 4b11d68)

## 3. Exact versions installed (all pinned)

| tool | version | how |
|------|---------|-----|
| axi-sdk-js (AXI standard) | `axi-sdk-js-v0.1.8` | skill vendored (no runtime dep) |
| gh-axi | `0.1.27` | npm → `~/.local` (Claude Code) + cellarette install.script |
| no-mistakes | `1.37.0` | `go install …@v1.37.0` → `~/.local/bin` |
| quota-axi | `0.1.5` | npm → `~/.local` + cellarette install.script |
| Speaches (whisper) | `:latest-cpu` (appVersion v0.9.0-rc.3) | new chart |
| faster-whisper model | `Systran/faster-whisper-small` | pre-warmed on pod start |

## 4. Hermes changes (GitOps `charts/hermes` + `charts/cellarette` + `charts/whisper`)

- **AXI skill** delivered read-only via `hermes-skill-axi` ConfigMap → `/opt/hermes-skills/axi`,
  exposed with `skills.external_dirs` (no PVC write, no image rebuild).
- **coding-worker skill** (`hermes-skill-coding-worker`): isolated-workspace → tests →
  no-mistakes gate → PR-only → review-required lifecycle + report contract.
- **gh-axi**: cellarette `gh` passthrough **runtime swapped to gh-axi** (TOON), same hardened
  deny policy remapped + `setup`/`update` denied; new **`hermes-devops` cellarette profile**
  (hermes tools + gh-axi) reusing the existing `GH_TOKEN` — no new credential, no gh/node in
  the Hermes pod.
- **quota-axi**: read-only cellarette passthrough (runtime = `quota-axi-hl` label-normalizer),
  exposed to workspace/hermes/hermes-devops profiles.
- **Voice STT**: new `charts/whisper` (Speaches, OpenAI-compatible, CPU, lw-c1) + 3 Hermes STT
  env vars → auto-selects the `openai` STT provider against the local whisper svc with a dummy
  key. Env-only → **no config.yaml seed-dance**.

## 5. Claude Code changes (ansible `claude-code-setup`)

- Managed skills: `axi`, `gh-axi`, `no-mistakes`, `quota-axi` (in `files/claude/skills/**`,
  delivered by the existing "Copy vendored skills directory" task; also **live-installed**
  additively to `~/.claude/skills/**`).
- Pinned installs in `roles/claude_config` (version defaults + install/verify tasks): gh-axi,
  no-mistakes (go install, skipped if Go absent), quota-axi, `quota-axi-hl` wrapper.
- Project template `files/no-mistakes/.no-mistakes.yaml.template` (no-yolo, sensitive-path
  exclusions, disable_project_settings).
- `dev-tools/axi-eval/` — the controlled-experiment harness.

## 6. Optional components (Phase 5) — DEFERRED (not started)

lavish-axi, chrome-devtools-axi, treehouse, gnhf, acp-mock — none adopted yet. gnhf/treehouse
would stay disabled-by-default / human-launcher-only per spec; acp-mock only if an ACP lane
appears. Explicitly deferred; no blocker.

## 7. Security controls implemented

- **No new GitHub credential** — gh-axi reuses local `gh` auth (Claude Code) / cellarette
  `GH_TOKEN` (Hermes). Cellarette gh deny policy blocks pr create/merge, release, run
  cancel/delete/rerun, secret/variable, raw api, setup/update; audit on; cred-flag guards.
- **quota-axi read-only** — no routing enabled; `quota-axi-hl` only reshapes output; cellarette
  denies `--allow-keychain-prompt`. No tokens in output (leak scan clean).
- **no-mistakes**: no-yolo (auto_fix all 0), PR-only never merges, config read only from trusted
  default branch, telemetry off, sensitive infra excluded.
- **No secrets** committed/logged/leaked (verified in diffs + tool output).
- Hermes RBAC/NetworkPolicy unchanged; no cluster mutation outside GitOps; branches only.

## 8. Commands/tests executed (real results)

- **AXI skill**: validator passes 13/13 on all copies; negative test (strip §11) fails; Hermes
  `iter_skill_index_files` discovered the mount layout.
- **gh-axi**: `--version`=0.1.27; read query→TOON; `pr view 999999999`→structured NOT_FOUND;
  empty state; credential-leak scan clean.
- **no-mistakes**: token-free fakeagent fixture — launches; pass→outcome passed; fail→test
  awaiting_approval + finding; **origin main unchanged both paths**; refuses to validate main.
- **quota-axi**: live — claude(max)+codex(plus) reported read-only, no tokens; Codex WEEKLY
  window mislabel `five_hour` fixed by `quota-axi-hl` (verified codex,weekly,…,604800).
- **whisper**: charts lint/render; warmup endpoint `POST /v1/models/{id}` confirmed in source;
  STT code path honors `STT_OPENAI_BASE_URL` + builds `OpenAI(base_url)`; dummy key confirmed OK.
- **eval harness** (real Claude Code, n=1):
  - gh-vs-gh-axi: **−20.9% output tokens, −23.6% duration**, same success. ✅
  - baseline-vs-axi: **−45.5% turns, −29.9% duration, −6.4% output tokens**, same success. ✅
  - broad-vs-narrow: narrow **+127.9% output tokens / +66.7% turns** — over-restriction backfired
    for that task. ⚠️ (toolset-narrowing is not a universal win.)
  - `input_tokens` metric is noisy (Claude reports uncached-only) — use output_tokens.

## 9. Deployment verification performed

Pre-merge: hermes **idle**; cellarette + hermes ArgoCD apps Synced/Healthy; auto-sync ON.
Post-merge verification steps are in §12 (must be re-checked after the operator go-live).

## 10. Files changed — see the two `feat/axi-integration` branches (`git show --stat <sha>`).

## 11. Remaining blockers

None hard. Soft: whisper needs an ansible run to register (§12); live Hermes coding-worker
*running* the no-mistakes gate needs the binary in the Hermes image + hermes-devops profile
selection (guidance shipped; execution deferred to an idle window). Pre-existing Claude Code
live-vs-source drift (settings.json/CLAUDE.md) should be reconciled before the next full role run.

## 12. Manual actions required from you

1. **Merge + push** both `feat/axi-integration` branches to `main` (approved — see go-live log).
   Pushing helm→main auto-syncs cellarette (gh-axi/quota/hermes-devops) + hermes (STT env/skills;
   restart while idle).
2. **Register + deploy whisper** (vault/become playbook — cannot be automated here):
   `ansible-playbook k8s/k3s-setup/…` to render the app-of-apps so the `whisper` ArgoCD
   Application is created → ArgoCD syncs whisper → postStart downloads the model (~0.5 GB once).
3. **Reproduce Claude Code config** (optional; tools already live): re-run the
   `dev-tools/claude-code-setup` role (reconcile settings.json/CLAUDE.md drift first).
4. **Voice check**: once whisper is Healthy, send a Discord voice message to Hermes.
5. **Post-merge verify**: `argocd app get cellarette/hermes` Healthy; `gh__run` returns TOON;
   `quota-axi-hl` shows codex `weekly`.

## 13. Rollback

- **All changes are on branches** — not merging is the rollback. After merge, `git revert <sha>`
  the specific commit + push; ArgoCD reverts.
- gh-axi swap: revert `charts/cellarette` commit 68305ed (+7f46bb5/b55ad9d for quota) → cellarette
  redeploys with raw gh.
- Hermes skills/STT: revert the `charts/hermes` commits; the ConfigMaps/env disappear on next sync.
  STT env removal → Hermes falls back to its default (no working STT) — harmless (text unaffected).
- whisper: remove the group_vars entry + re-run app-of-apps (ArgoCD prunes the app), or
  `argocd app delete whisper`.
- Claude Code: `npm rm -g` the tools from `~/.local`, remove the skill dirs, revert the role.
- no state directories created except the whisper HF-cache PVC (delete the PVC to reclaim).

## 14. Suggested follow-up benchmark experiments

- Rerun the eval with `--reps 5` (n=1 is directional). Firm up the broad-vs-narrow reversal —
  test whether a *correctly-scoped* narrow toolset (covering the task) beats broad.
- Add a real `normal-vs-nomistakes` arm (needs the gate daemon) to measure the review-gate's
  effect on diff-correctness + human interventions.
- Add a Hermes-side arm (codex model held constant) to compare gh vs gh-axi under the actual
  production model, not just Claude Code.

# axi-eval — did the AXI adoptions actually help?

A small **controlled paired-experiment** harness that measures whether each AXI tool
adoption improves agent behaviour, instead of assuming it. It holds everything constant
(model, task, fixture repo, sandbox, effort) and flips **one** factor between a *control*
arm and a *treatment* arm, then reports the delta.

> Methodology only is borrowed from `kunchenguid/programbench-bench` (hold model constant,
> vary one factor) — that repo ships **no license**, so **no code is copied**. This harness
> is original.

## One command

```bash
./run.sh --smoke                     # offline pipeline check — mock runner, zero token cost
./run.sh                             # real run, all experiments (Claude Code headless)
./run.sh --experiment gh-vs-gh-axi   # one experiment, real
./run.sh --reps 3 --model claude-sonnet-5
```

Outputs, per run, to `results/<UTC-timestamp>/`:
- `results.json` — machine-readable per-arm metrics + per-rep detail.
- `summary.md` — human summary with control→treatment deltas.

Exit code: `0` = no safety violations, `1` = a safety violation was recorded, `2` = usage error.

## Experiments (`experiments.json`)

| id | control | treatment | factor |
|----|---------|-----------|--------|
| `gh-vs-gh-axi` | raw `gh` | `gh-axi` | GitHub CLI wrapper |
| `baseline-vs-axi` | no skill | AXI skill loaded | output-standard skill |
| `broad-vs-narrow` | all tools | task-scoped `allowedTools` | toolset breadth |
| `normal-vs-nomistakes` | direct commit | no-mistakes gate | pre-PR validation |

Each experiment holds the task, fixture, model, and effort constant across its two arms.

## Metrics captured (per arm, averaged over `--reps`)

task success rate · diff-correctness rate · turns · input/output tokens · cost · duration ·
tool/command failures · human-intervention count · **safety-policy violations** (e.g. `main`
advanced without approval, or a denied pattern such as a token surfacing in the run output).

## Runners

- `mock` (default for `--smoke`) — deterministic canned metrics; exercises the whole pipeline
  (fixture build → run → verify → safety scan → aggregate → emit) with **zero token cost**.
  Used to prove the harness works offline. Mock arms don't perform the task, so their
  `verify_cmd`/`expect_contains` checks legitimately fail — that confirms verification is real.
- `claude` — real Claude Code headless (`claude -p --output-format json`), parsing
  `num_turns` / `usage` / `total_cost_usd` / `is_error`. Spends tokens.

## Sandbox / safety

- Every arm runs against a **fresh throwaway git fixture** (built per rep); nothing touches a
  real repo. **No prod credentials.** The `gh-vs-gh-axi` task is read-only against a public repo.
- The harness asserts `origin main` never advances without approval and scans run output for
  denied patterns (tokens, auth headers).
- **Docker network isolation (optional, recommended for real runs):** wrap `./run.sh` in a
  container that allowlists only the model API endpoint + `api.github.com` egress, e.g. a
  tinyproxy domain-whitelist with the task container otherwise `--network`-restricted. Not
  required for `--smoke`.

## Interpreting a result

A treatment "wins" when it lowers tokens/turns/duration/tool-failures **without** hurting
success or diff-correctness and **without** adding safety violations. Percentages are the
control→treatment change; token percentages are the headline for the AXI/gh-axi arms.

## Files

- `eval.py` — the harness (stdlib only; itself AXI-conformant: content-first stdout, exit codes).
- `experiments.json` — the four comparisons (data, not code — add your own arms here).
- `run.sh` — the documented entry point.

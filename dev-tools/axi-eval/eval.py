#!/usr/bin/env python3
"""axi-eval — controlled paired-experiment harness for the AXI tool adoptions.

Measures whether each AXI adoption actually helps, by holding everything constant
(model, task, fixture repo, sandbox, effort) and flipping ONE factor between a
control arm and a treatment arm. Original code — methodology only is borrowed from
programbench-bench (which ships no license); no code is copied.

Experiments (experiments.json):
  gh-vs-gh-axi        raw gh            vs  gh-axi
  baseline-vs-axi     no AXI skill      vs  AXI skill loaded
  broad-vs-narrow     all tools allowed vs  task-scoped allowedTools
  normal-vs-nomistakes direct commit    vs  no-mistakes gate

Per arm it captures: task success, turns, elapsed time, input/output tokens,
tool/command failures, human-intervention count, diff correctness, and
safety-policy violations. Output: results/<ts>/results.json (machine-readable)
plus summary.md (human).

Runners:
  --runner mock    deterministic, zero-cost; validates the whole pipeline (default for --smoke)
  --runner claude  real Claude Code headless (`claude -p --output-format json`); spends tokens

Usage:
  ./run.sh --smoke                     # offline pipeline check (mock runner, 1 rep)
  ./run.sh                             # real run, all experiments (claude runner)
  ./run.sh --experiment gh-vs-gh-axi   # one experiment
  ./eval.py --runner claude --reps 3   # explicit
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))


# --------------------------------------------------------------------------- #
# Runners
# --------------------------------------------------------------------------- #
class RunResult(dict):
    """Normalized agent-run metrics."""


def _mock_run(arm, prompt, cwd, env):
    """Deterministic metrics: the treatment arm is modelled as cheaper/fewer turns
    so the pipeline (compare + summarize) is exercised without spending tokens."""
    treat = bool(arm.get("treatment"))
    base_in, base_out, base_turns = 4200, 1600, 6
    factor = 0.62 if treat else 1.0
    # Leave a deterministic breadcrumb the verify/safety steps can read.
    try:
        with open(os.path.join(cwd, "AGENT_DID"), "w") as fh:
            fh.write(f"arm={arm['id']} treatment={treat}\n")
    except OSError:
        pass
    return RunResult(
        is_error=False,
        num_turns=round(base_turns * factor),
        input_tokens=round(base_in * factor),
        output_tokens=round(base_out * factor),
        cost_usd=round(0.021 * factor, 5),
        duration_ms=round(9000 * factor),
        tool_failures=0 if treat else 1,
        text=f"[mock] completed arm {arm['id']}",
    )


def _claude_run(arm, prompt, cwd, env, model=None, max_turns=25, timeout=900):
    cmd = ["claude", "-p", prompt, "--output-format", "json",
           "--permission-mode", arm.get("permission_mode", "acceptEdits"),
           "--max-turns", str(max_turns)]
    if model:
        cmd += ["--model", model]
    if arm.get("allowed_tools"):
        cmd += ["--allowedTools", *arm["allowed_tools"]]
    if arm.get("disallowed_tools"):
        cmd += ["--disallowedTools", *arm["disallowed_tools"]]
    if arm.get("append_system_prompt"):
        cmd += ["--append-system-prompt", arm["append_system_prompt"]]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True,
                              text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return RunResult(is_error=True, num_turns=0, input_tokens=0, output_tokens=0,
                         cost_usd=0, duration_ms=int((time.time() - t0) * 1000),
                         tool_failures=0, text="TIMEOUT")
    try:
        data = json.loads(proc.stdout)
    except (ValueError, TypeError):
        return RunResult(is_error=True, num_turns=0, input_tokens=0, output_tokens=0,
                         cost_usd=0, duration_ms=int((time.time() - t0) * 1000),
                         tool_failures=0, text=(proc.stdout or proc.stderr)[:400])
    usage = data.get("usage") or {}
    return RunResult(
        is_error=bool(data.get("is_error")),
        num_turns=int(data.get("num_turns") or 0),
        input_tokens=int(usage.get("input_tokens") or 0),
        output_tokens=int(usage.get("output_tokens") or 0),
        cost_usd=float(data.get("total_cost_usd") or 0),
        duration_ms=int(data.get("duration_ms") or (time.time() - t0) * 1000),
        tool_failures=0,
        text=str(data.get("result") or "")[:400],
    )


RUNNERS = {"mock": _mock_run, "claude": _claude_run}


# --------------------------------------------------------------------------- #
# Arm execution
# --------------------------------------------------------------------------- #
def _sh(cmd, cwd, env=None):
    return subprocess.run(cmd, cwd=cwd, env=env, shell=True,
                          capture_output=True, text=True)


def build_fixture(exp, dest):
    """Create the harmless fixture repo for an experiment (git init + seed commands)."""
    os.makedirs(dest, exist_ok=True)
    env = dict(os.environ, GIT_AUTHOR_NAME="axi-eval", GIT_AUTHOR_EMAIL="eval@local",
               GIT_COMMITTER_NAME="axi-eval", GIT_COMMITTER_EMAIL="eval@local")
    _sh("git init -q && git symbolic-ref HEAD refs/heads/main", dest, env)
    for c in exp.get("fixture", []):
        _sh(c, dest, env)
    _sh("git add -A && git commit -q -m fixture --allow-empty", dest, env)
    return env


def run_arm(exp, arm, runner_fn, reps, model, workroot):
    reps_out = []
    for rep in range(reps):
        cwd = os.path.join(workroot, f"{exp['id']}__{arm['id']}__{rep}")
        gitenv = build_fixture(exp, cwd)
        env = dict(gitenv)
        env.update(arm.get("env", {}))
        # arm setup (install/omit a skill, place a tool shim, etc.)
        for c in arm.get("setup", []):
            _sh(c, cwd, env)
        base_main = _sh("git rev-parse main", cwd, env).stdout.strip()

        res = runner_fn(arm, exp["intent"], cwd, env) if runner_fn is _mock_run \
            else runner_fn(arm, exp["intent"], cwd, env, model=model)

        # verify: task success (verify_cmd exit 0) + diff correctness (expect_contains)
        success = not res.get("is_error")
        if success and exp.get("verify_cmd"):
            success = _sh(exp["verify_cmd"], cwd, env).returncode == 0
        diff_ok = True
        for needle_file, needle in exp.get("expect_contains", []):
            p = os.path.join(cwd, needle_file)
            diff_ok = diff_ok and os.path.exists(p) and needle in open(p, errors="ignore").read()

        # safety: origin main must not have moved (no push/merge without approval),
        # and no denied pattern in the run text.
        now_main = _sh("git rev-parse main", cwd, env).stdout.strip()
        violations = []
        if now_main != base_main and not arm.get("allow_main_change"):
            violations.append("main advanced without approval")
        for pat in exp.get("deny_patterns", []):
            if pat in (res.get("text") or ""):
                violations.append(f"denied pattern surfaced: {pat}")

        reps_out.append({
            "rep": rep, "success": bool(success), "diff_correct": bool(diff_ok),
            "num_turns": res.get("num_turns"), "input_tokens": res.get("input_tokens"),
            "output_tokens": res.get("output_tokens"), "cost_usd": res.get("cost_usd"),
            "duration_ms": res.get("duration_ms"), "tool_failures": res.get("tool_failures"),
            "human_interventions": res.get("human_interventions", 0),
            "safety_violations": violations,
        })
    return _aggregate(arm, reps_out)


def _aggregate(arm, reps_out):
    n = len(reps_out) or 1
    def avg(k):
        vals = [r[k] for r in reps_out if isinstance(r.get(k), (int, float))]
        return round(sum(vals) / len(vals), 2) if vals else None
    return {
        "arm": arm["id"], "label": arm.get("label", arm["id"]),
        "treatment": bool(arm.get("treatment")), "reps": n,
        "success_rate": round(sum(r["success"] for r in reps_out) / n, 3),
        "diff_correct_rate": round(sum(r["diff_correct"] for r in reps_out) / n, 3),
        "avg_turns": avg("num_turns"), "avg_input_tokens": avg("input_tokens"),
        "avg_output_tokens": avg("output_tokens"), "avg_cost_usd": avg("cost_usd"),
        "avg_duration_ms": avg("duration_ms"), "avg_tool_failures": avg("tool_failures"),
        "total_safety_violations": sum(len(r["safety_violations"]) for r in reps_out),
        "reps_detail": reps_out,
    }


# --------------------------------------------------------------------------- #
# Compare + emit
# --------------------------------------------------------------------------- #
def _delta(control, treat, key):
    c, t = control.get(key), treat.get(key)
    if not isinstance(c, (int, float)) or not isinstance(t, (int, float)) or c == 0:
        return None
    return round((t - c) / c * 100, 1)


def summarize(results):
    lines = ["# axi-eval summary", ""]
    for exp in results["experiments"]:
        arms = exp["arms"]
        control = next((a for a in arms if not a["treatment"]), arms[0])
        treat = next((a for a in arms if a["treatment"]), arms[-1])
        lines.append(f"## {exp['id']} — {exp['description']}")
        lines.append(f"control=`{control['label']}`  treatment=`{treat['label']}`  (reps={control['reps']})")
        for key, label in [("avg_output_tokens", "output tokens"), ("avg_input_tokens", "input tokens"),
                           ("avg_turns", "turns"), ("avg_duration_ms", "duration"),
                           ("avg_tool_failures", "tool failures")]:
            d = _delta(control, treat, key)
            arrow = "" if d is None else (f" ({d:+.1f}%)")
            lines.append(f"- {label}: {control.get(key)} → {treat.get(key)}{arrow}")
        lines.append(f"- success: {control['success_rate']} → {treat['success_rate']}  "
                     f"| diff-correct: {control['diff_correct_rate']} → {treat['diff_correct_rate']}")
        lines.append(f"- safety violations: control={control['total_safety_violations']} "
                     f"treatment={treat['total_safety_violations']}")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="AXI controlled-experiment harness")
    ap.add_argument("--runner", choices=list(RUNNERS), default="mock")
    ap.add_argument("--experiment", help="run only this experiment id")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--model", default=None, help="model held constant across arms")
    ap.add_argument("--smoke", action="store_true", help="offline pipeline check (forces mock, 1 rep)")
    ap.add_argument("--experiments-file", default=os.path.join(HERE, "experiments.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "results"))
    args = ap.parse_args()
    if args.smoke:
        args.runner, args.reps = "mock", 1

    try:
        experiments = json.load(open(args.experiments_file))["experiments"]
    except (OSError, ValueError, KeyError) as e:
        sys.stdout.write(f"error: cannot load experiments ({e.__class__.__name__})\n")
        sys.stdout.write("help: ./eval.py --experiments-file <path>\n")
        return 2
    if args.experiment:
        experiments = [e for e in experiments if e["id"] == args.experiment]
        if not experiments:
            sys.stdout.write(f"error: no experiment id '{args.experiment}'\n")
            return 2

    runner_fn = RUNNERS[args.runner]
    ts = _sh("date -u +%Y%m%dT%H%M%SZ", HERE).stdout.strip() or "run"
    outdir = os.path.join(args.out, ts)
    os.makedirs(outdir, exist_ok=True)
    workroot = tempfile.mkdtemp(prefix="axi-eval-")

    results = {"runner": args.runner, "reps": args.reps, "model": args.model,
               "experiments": []}
    sys.stderr.write(f"axi-eval: runner={args.runner} reps={args.reps} "
                     f"experiments={len(experiments)} work={workroot}\n")
    for exp in experiments:
        sys.stderr.write(f"  · {exp['id']}\n")
        arm_results = [run_arm(exp, arm, runner_fn, args.reps, args.model, workroot)
                       for arm in exp["arms"]]
        results["experiments"].append({
            "id": exp["id"], "description": exp["description"], "arms": arm_results})

    with open(os.path.join(outdir, "results.json"), "w") as fh:
        json.dump(results, fh, indent=2)
    summary = summarize(results)
    with open(os.path.join(outdir, "summary.md"), "w") as fh:
        fh.write(summary + "\n")
    shutil.rmtree(workroot, ignore_errors=True)

    # AXI-style structured stdout: content first, then where to look.
    sys.stdout.write(summary + "\n")
    sys.stdout.write(f"\nresults: {os.path.join(outdir, 'results.json')}\n")
    sys.stdout.write(f"summary: {os.path.join(outdir, 'summary.md')}\n")
    total_viol = sum(a["total_safety_violations"]
                     for e in results["experiments"] for a in e["arms"])
    return 1 if total_viol else 0


if __name__ == "__main__":
    sys.exit(main())

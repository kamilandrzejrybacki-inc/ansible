#!/usr/bin/env bash
# axi-eval — one documented command to run the AXI controlled experiments.
#
#   ./run.sh --smoke                      # offline pipeline check (mock runner, zero cost)
#   ./run.sh                              # real run, all experiments (claude runner)
#   ./run.sh --experiment gh-vs-gh-axi    # one experiment, real
#   ./run.sh --reps 3 --model claude-sonnet-5
#
# Real runs invoke Claude Code headless (`claude -p`) and spend tokens. Everything runs
# against harmless throwaway git fixtures; no prod credentials are used. If Docker is
# available and you want network isolation, wrap this in a container that allowlists only
# the model API + api.github.com egress (see README).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"

# Default to a real claude run; --smoke forces the mock runner inside eval.py.
if [[ "$*" == *"--smoke"* ]]; then
  exec python3 "$DIR/eval.py" "$@"
fi
exec python3 "$DIR/eval.py" --runner claude "$@"

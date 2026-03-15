#!/usr/bin/env bash
# Runs Molecule tests for all discovered roles of a given driver type.
# Usage: ./scripts/test-all.sh <docker|privileged|qemu>

set -euo pipefail

DRIVER="${1:-docker}"

case "$DRIVER" in
  docker)     SCENARIO="default" ;;
  privileged) SCENARIO="privileged" ;;
  qemu)       SCENARIO="qemu" ;;
  *)
    echo "Usage: $0 <docker|privileged|qemu>" >&2
    exit 1
    ;;
esac

FAILED=()
PASSED=()

while IFS= read -r mol_dir; do
  if [ -d "${mol_dir}/${SCENARIO}" ]; then
    role_path=$(dirname "$mol_dir")
    role_path="${role_path#./}"
    role_name=$(basename "$role_path")
    playbook_name=$(basename "$(dirname "$(dirname "$role_path")")")

    echo "=== Testing ${role_name} (${playbook_name}) ==="
    if (cd "$role_path" && molecule test -s "$SCENARIO"); then
      PASSED+=("${role_name} (${playbook_name})")
    else
      FAILED+=("${role_name} (${playbook_name})")
    fi
    echo ""
  fi
done < <(find . -path "*/roles/*/molecule" -type d | sort)

echo "=== RESULTS ==="
echo "Passed: ${#PASSED[@]}"
echo "Failed: ${#FAILED[@]}"

if [ ${#FAILED[@]} -gt 0 ]; then
  echo ""
  echo "Failed roles:"
  for f in "${FAILED[@]}"; do
    echo "  - $f"
  done
  exit 1
fi

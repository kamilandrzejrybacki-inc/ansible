#!/usr/bin/env bash
# Discovers Ansible roles with Molecule scenarios and outputs a GitHub Actions matrix JSON.
# Usage: ./scripts/discover-roles.sh <docker|privileged|qemu>
#
# Scenario directory naming convention:
#   molecule/default/     -> standard Docker (Tier 1, discovered via "docker")
#   molecule/privileged/  -> privileged Docker (Tier 2, discovered via "privileged")
#   molecule/qemu/        -> QEMU VM (Tier 2, discovered via "qemu")

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

ROLES=()
while IFS= read -r mol_dir; do
  if [ -d "${mol_dir}/${SCENARIO}" ]; then
    role_path=$(dirname "$mol_dir")
    role_path="${role_path#./}"
    role=$(basename "$role_path")
    # Go up: role -> roles -> playbook-setup -> category
    playbook=$(basename "$(dirname "$(dirname "$role_path")")")
    ROLES+=("{\"role_path\":\"${role_path}\",\"role_name\":\"${role} (${playbook})\",\"scenario\":\"${SCENARIO}\"}")
  fi
done < <(find . -path "*/roles/*/molecule" -type d | sort)

if [ ${#ROLES[@]} -eq 0 ]; then
  echo "matrix={\"include\":[]}"
  echo "has_roles=false"
else
  echo "matrix={\"include\":[$(IFS=,; echo "${ROLES[*]}")]}"
  echo "has_roles=true"
fi

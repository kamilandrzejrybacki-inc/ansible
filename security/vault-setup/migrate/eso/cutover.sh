#!/usr/bin/env bash
# cutover.sh — flip ONE namespace from sops-delivered Secrets to ESO, gated.
#
#   cutover.sh <namespace>            full cutover (commits + pushes the sops removal)
#   cutover.sh <namespace> --check    apply SecretStore/ExternalSecrets only, report, no git changes
#
# ESO (creationPolicy Owner) refuses to adopt a Secret owned by a SopsSecret, so the order is:
#   1. apply SecretStore + ExternalSecrets (they sit in SecretSyncedError until sops lets go)
#   2. git rm the namespace's sops files, commit, push; refresh the ArgoCD app so it prunes the
#      SopsSecret CRs -> owned Secrets are garbage-collected
#   3. force-sync the ExternalSecrets -> ESO recreates the Secrets from Vault
#   4. gate: every key's sha256 vs the pre-cutover baseline (~/homelab-backups/k8s-secrets-baseline-*.json).
#      Any value mismatch -> revert the commit, delete the ExternalSecrets, exit 1 (sops reclaims).
set -euo pipefail
NS="${1:?namespace}"; MODE="${2:-}"
ARGO="$HOME/Code/argocd-apps"
ESO_DIR="$ARGO/secrets/eso/$NS"
BASE=$(ls -t "$HOME"/homelab-backups/k8s-secrets-baseline-*.json | head -1)
[ -d "$ESO_DIR" ] || { echo "no ESO manifests for $NS"; exit 2; }

sops_files=$(grep -lE "^\s+namespace: $NS$" "$ARGO"/secrets/bootstrap/sops-*.enc.yaml 2>/dev/null || true)
sops_secrets=$(for f in $sops_files; do awk '/secretTemplates:/{t=1;next} t && /- name:/{print $3}' "$f"; done | sort -u)
eso_secrets=$(grep -h "^    name:" "$ESO_DIR"/es-*.yaml | awk '{print $2}' | sort -u)
for s in $sops_secrets; do
  grep -qx "$s" <<<"$eso_secrets" || { echo "sops delivers $NS/$s but no ExternalSecret covers it — aborting"; exit 2; }
done

wait_for() { # <seconds> <description> <command...>
  local t=$1 d=$2; shift 2
  for _ in $(seq 1 $((t / 3))); do "$@" && return 0; sleep 3; done
  echo "timeout: $d"; return 1
}
es_reason() { kubectl -n "$NS" get externalsecret "$1" -o jsonpath='{.status.conditions[?(@.type=="Ready")].reason}' 2>/dev/null; }

echo "== 1. apply ESO manifests for $NS"
if [ -z "$sops_files" ] && [ "$MODE" != "--check" ]; then
  # ansible-delivered: the unowned Secret must be gone BEFORE the ExternalSecret exists, or ESO's
  # first reconcile fails on it and backs off. Snapshot first so a failed gate can restore it.
  SNAP=$(mktemp -d); chmod 700 "$SNAP"
  for s in $eso_secrets; do
    if kubectl -n "$NS" get secret "$s" >/dev/null 2>&1 && ! kubectl -n "$NS" get secret "$s" -o jsonpath='{.metadata.ownerReferences[0].kind}' | grep -q ExternalSecret; then
      kubectl -n "$NS" get secret "$s" -o json | python3 -c 'import sys,json;d=json.load(sys.stdin);d["metadata"]={k:d["metadata"][k] for k in ("name","namespace","labels") if k in d["metadata"]};print(json.dumps(d))' > "$SNAP/$s.json"
      kubectl -n "$NS" delete secret "$s"
    fi
  done
fi
kubectl apply -f "$ESO_DIR/secretstore.yaml"
wait_for 60 "SecretStore Ready" sh -c "[ \"\$(kubectl -n $NS get secretstore homelab-vault -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}')\" = True ]" \
  || { kubectl -n "$NS" get secretstore homelab-vault -o jsonpath='{.status.conditions}'; echo; exit 3; }
for f in "$ESO_DIR"/es-*.yaml; do kubectl apply -f "$f"; done
es_names=$(kubectl -n "$NS" get externalsecret -o jsonpath='{.items[*].metadata.name}')

if [ "$MODE" = "--check" ]; then
  sleep 5
  for es in $es_names; do echo "   $es: $(es_reason "$es")"; done
  echo "   sops files: ${sops_files:-none}"
  exit 0
fi

echo "== 2. remove sops delivery for $NS"
if [ -n "$sops_files" ]; then
  cd "$ARGO"
  git rm -q $sops_files
  git commit -qm "chore(secrets): $NS delivered by ESO — remove sops files" && git push -q origin main
  kubectl -n argocd annotate application bootstrap-secrets argocd.argoproj.io/refresh=normal --overwrite >/dev/null
  wait_for 300 "SopsSecret CRs pruned" sh -c "[ -z \"\$(kubectl -n $NS get sopssecret -o name 2>/dev/null)\" ]"
  for s in $sops_secrets; do
    wait_for 120 "$s released by sops" sh -c "! kubectl -n $NS get secret $s -o jsonpath='{.metadata.ownerReferences[0].kind}' 2>/dev/null | grep -q SopsSecret"
  done
else
  echo "   no sops files (ansible-delivered or new) — ESO takes over directly"
fi

echo "== 3. force-sync ExternalSecrets"
for es in $es_names; do
  kubectl -n "$NS" annotate externalsecret "$es" force-sync="$(date +%s)" --overwrite >/dev/null
  tgt=$(kubectl -n "$NS" get externalsecret "$es" -o jsonpath='{.spec.target.name}')
  wait_for 180 "$es SecretSynced" sh -c "[ \"\$(kubectl -n $NS get externalsecret $es -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].reason}')\" = SecretSynced ] && kubectl -n $NS get secret $tgt -o jsonpath='{.metadata.ownerReferences[0].kind}' 2>/dev/null | grep -q ExternalSecret" \
    || kubectl -n "$NS" get externalsecret "$es" -o jsonpath='{.status.conditions[0].message}{"\n"}'
done

echo "== 4. GATE vs $(basename "$BASE")"
set +e
# ACCEPT_DIFF="name#key,..." — keys whose baseline value is known-stale (Vault holds the verified-working one).
python3 - "$NS" "$BASE" "${ACCEPT_DIFF:-}" <<'PY'
import sys, json, base64, hashlib, subprocess
ns, basef, accept = sys.argv[1], sys.argv[2], set(filter(None, sys.argv[3].split(",")))
base = json.load(open(basef))
fail = 0
for key, exp in base.items():
    if not key.startswith(ns + "/"): continue
    name = key.split("/", 1)[1]
    out = subprocess.run(["kubectl","-n",ns,"get","secret",name,"-o","json"],capture_output=True,text=True)
    if out.returncode:
        print(f"   {key}: MISSING"); fail += 1; continue
    data = json.loads(out.stdout).get("data") or {}
    now = {k: hashlib.sha256(base64.b64decode(v)).hexdigest()[:16] for k,v in data.items()}
    if exp.get("_missing"):
        print(f"   {key}: created ({len(now)} keys)"); continue
    same = [k for k in exp if k in now and now[k] == exp[k]]
    diff = [k for k in exp if k in now and now[k] != exp[k] and f"{name}#{k}" not in accept]
    accepted = [k for k in exp if k in now and now[k] != exp[k] and f"{name}#{k}" in accept]
    dropped = [k for k in exp if k not in now]
    added = [k for k in now if k not in exp]
    print(f"   {key}: match={len(same)} DIFF={diff or '-'} accepted={accepted or '-'} dropped={dropped or '-'} added={added or '-'}")
    if diff: fail += 1
print("GATE:", "PASS" if fail == 0 else f"FAIL ({fail})")
sys.exit(1 if fail else 0)
PY
rc=$?
set -e
if [ $rc -ne 0 ]; then
  echo "== ROLLBACK: restoring previous delivery for $NS"
  kubectl delete -f "$ESO_DIR" --ignore-not-found
  if [ -n "$sops_files" ]; then
    cd "$ARGO" && git revert --no-edit HEAD >/dev/null && git push -q origin main
    kubectl -n argocd annotate application bootstrap-secrets argocd.argoproj.io/refresh=normal --overwrite >/dev/null
  else
    for f in "${SNAP:-/nonexistent}"/*.json; do [ -f "$f" ] && kubectl create -f "$f"; done
  fi
  exit 1
fi
echo "== $NS cut over to ESO"

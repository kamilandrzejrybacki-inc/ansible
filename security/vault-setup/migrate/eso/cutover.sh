#!/usr/bin/env bash
# cutover.sh — flip ONE namespace from sops/ansible-delivered Secrets to ESO, with a gate.
#
#   cutover.sh <namespace> [--commit]        (default: dry, prints the plan + gate result)
#
# Per namespace, in order:
#   1. apply secrets/eso/<ns>/secretstore.yaml + es-*.yaml (SecretStore must go Ready — needs
#      the vault-eso-approle Secret from the taxonomy-policies run)
#   2. wait for every ExternalSecret in <ns> to report SecretSynced
#   3. GATE: for every target Secret, compare each key's sha256 against the pre-cutover baseline
#      (~/homelab-backups/k8s-secrets-baseline-*.json). Keys the design intentionally drops
#      (e.g. prefect_etl_api_key) are reported, not failed. Any VALUE mismatch fails the gate.
#   4. only with --commit and a passing gate: git rm the superseded sops file(s) for <ns> in
#      argocd-apps (the SopsSecret CR is pruned by ArgoCD; ESO already owns the Secret by then)
#
# Run the lowest-risk namespace first (tauto / silverbullet) to observe ESO's Owner-policy
# behaviour against a sops-owned Secret before touching n8n / cellarette / hermes.
set -euo pipefail
NS="${1:?namespace}"; COMMIT="${2:-}"
ESO_DIR="$HOME/Code/argocd-apps/secrets/eso/$NS"
BASE=$(ls -t "$HOME"/homelab-backups/k8s-secrets-baseline-*.json | head -1)
[ -d "$ESO_DIR" ] || { echo "no ESO manifests for $NS"; exit 2; }

echo "== 1. apply ESO manifests for $NS"
kubectl apply -f "$ESO_DIR/secretstore.yaml"
for i in $(seq 1 20); do
  st=$(kubectl -n "$NS" get secretstore homelab-vault -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true)
  [ "$st" = "True" ] && break; sleep 3
done
[ "$st" = "True" ] || { echo "SecretStore not Ready in $NS (vault-eso-approle missing? AppRole not created?)"; kubectl -n "$NS" get secretstore homelab-vault -o jsonpath='{.status.conditions}'; echo; exit 3; }
echo "   SecretStore Ready"
kubectl apply -f "$ESO_DIR"/es-*.yaml

echo "== 2. wait for SecretSynced"
for es in $(kubectl -n "$NS" get externalsecret -o jsonpath='{.items[*].metadata.name}'); do
  for i in $(seq 1 30); do
    r=$(kubectl -n "$NS" get externalsecret "$es" -o jsonpath='{.status.conditions[?(@.type=="Ready")].reason}' 2>/dev/null || true)
    [ "$r" = "SecretSynced" ] && break; sleep 3
  done
  echo "   $es: ${r:-<no status>}"
  [ "$r" = "SecretSynced" ] || { kubectl -n "$NS" get externalsecret "$es" -o jsonpath='{.status.conditions[0].message}'; echo; }
done

echo "== 3. GATE: compare against baseline $BASE"
python3 - "$NS" "$BASE" <<'PY'
import sys, json, base64, hashlib, subprocess
ns, basef = sys.argv[1], sys.argv[2]
base = json.load(open(basef))
fail = 0
for key, exp in base.items():
    if not key.startswith(ns + "/"): continue
    name = key.split("/", 1)[1]
    out = subprocess.run(["kubectl","-n",ns,"get","secret",name,"-o","json"],capture_output=True,text=True)
    if out.returncode:
        print(f"   {key}: MISSING after cutover"); fail += 1; continue
    data = json.loads(out.stdout).get("data") or {}
    now = {k: hashlib.sha256(base64.b64decode(v)).hexdigest()[:16] for k,v in data.items()}
    if exp.get("_missing"):
        print(f"   {key}: created ({len(now)} keys) — no baseline to compare"); continue
    same = [k for k in exp if k in now and now[k] == exp[k]]
    diff = [k for k in exp if k in now and now[k] != exp[k]]
    dropped = [k for k in exp if k not in now]
    added = [k for k in now if k not in exp]
    print(f"   {key}: match={len(same)} DIFF={diff or '-'} dropped={dropped or '-'} added={added or '-'}")
    if diff: fail += 1
print("GATE:", "PASS" if fail == 0 else f"FAIL ({fail} secret(s) with value mismatches)")
sys.exit(1 if fail else 0)
PY

if [ "$COMMIT" = "--commit" ]; then
  echo "== 4. remove superseded sops files for $NS"
  cd "$HOME/Code/argocd-apps"
  files=$(grep -lE "namespace: $NS\b" secrets/bootstrap/sops-*.enc.yaml 2>/dev/null || true)
  [ -n "$files" ] || { echo "   no sops files for $NS"; exit 0; }
  git rm -q $files && git commit -qm "chore(secrets): $NS delivered by ESO — remove sops files" && git push -q origin main
  echo "   removed: $files"
else
  echo "(dry: pass --commit to remove the sops files after a PASS)"
fi

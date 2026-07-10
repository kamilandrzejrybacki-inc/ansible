#!/usr/bin/env bash
# =============================================================================
# Reproducible Termix host import + Auto-Tmux enablement
# =============================================================================
# Recreates/updates the homelab hosts (hosts.json) under the current Termix
# OIDC user, with Auto-Tmux enabled. Idempotent: overwrite=true, hosts matched
# by ip:port:username.
#
# WHY a script and not pure declarative config: Termix encrypts host data
# per-user with a session-derived key, so imports MUST go through the logged-in
# user's session. This reads the user's active session token server-side (in the
# pod) and calls Termix's own /host/bulk-import — the app does the encryption.
#
# PREREQUISITES:
#   - You are LOGGED INTO Termix (active session) — required for encryption.
#   - kubectl context reaches the cluster; SSH key at ~/.ssh/id_ed25519.
#
# USAGE:
#   ./import.sh                       # uses ~/.ssh/id_ed25519
#   TERMIX_SSH_KEY=/path/to/key ./import.sh
# =============================================================================
set -euo pipefail

NS="${TERMIX_NAMESPACE:-termix}"
KEY_FILE="${TERMIX_SSH_KEY:-$HOME/.ssh/id_ed25519}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST="$SCRIPT_DIR/hosts.json"

[ -f "$KEY_FILE" ] || { echo "SSH key not found: $KEY_FILE" >&2; exit 1; }
[ -f "$MANIFEST" ] || { echo "manifest not found: $MANIFEST" >&2; exit 1; }

POD="$(kubectl -n "$NS" get pod -l app=termix -o jsonpath='{.items[0].metadata.name}')"
[ -n "$POD" ] || { echo "termix pod not found in ns $NS" >&2; exit 1; }
echo "pod: $POD"

# Build payload with the private key injected (never committed).
PAYLOAD="$(mktemp)"; RUNNER="$(mktemp --suffix=.mjs)"
trap 'rm -f "$PAYLOAD" "$RUNNER"' EXIT
python3 - "$MANIFEST" "$KEY_FILE" "$PAYLOAD" <<'PY'
import json, sys
manifest, keyfile, out = sys.argv[1:4]
key = open(keyfile).read().strip()
data = json.load(open(manifest))
for h in data.get("hosts", []):
    if h.get("authType") == "key":
        h["key"] = key
    h.pop("_comment", None)
json.dump({"hosts": data["hosts"]}, open(out, "w"))
PY

cat > "$RUNNER" <<'EOF'
import { initializeDatabase, getDb } from '/app/dist/backend/backend/database/db/index.js';
import { sessions, users } from '/app/dist/backend/backend/database/db/schema.js';
import { readFileSync } from 'fs';
await initializeDatabase();
const db = getDb();
const us = await db.select().from(users);
const user = us.find(u => u.isOidc) || us[0];
if (!user) { console.log('ABORT: no user'); process.exit(3); }
const now = Date.now();
const sess = (await db.select().from(sessions))
  .filter(s => s.userId === user.id && new Date(s.expiresAt).getTime() > now)
  .sort((a,b)=> new Date(b.createdAt) - new Date(a.createdAt))[0];
if (!sess) { console.log('ABORT: no active session for ' + user.username + ' — log into Termix first'); process.exit(4); }
const payload = JSON.parse(readFileSync('/tmp/termix-hosts-payload.json','utf8'));
const r = await fetch('http://127.0.0.1:'+(process.env.PORT||'8080')+'/host/bulk-import', {
  method:'POST', headers:{'Content-Type':'application/json','Authorization':'Bearer '+sess.jwtToken},
  body: JSON.stringify({ hosts: payload.hosts, overwrite: true })
});
console.log('TARGET_USER', user.username);
console.log('IMPORT', r.status, (await r.text()).slice(0,600));
process.exit(0);
EOF

kubectl -n "$NS" cp "$PAYLOAD" "$POD:/tmp/termix-hosts-payload.json"
kubectl -n "$NS" cp "$RUNNER" "$POD:/tmp/termix-import-runner.mjs"
kubectl -n "$NS" exec "$POD" -- node /tmp/termix-import-runner.mjs
kubectl -n "$NS" exec "$POD" -- rm -f /tmp/termix-hosts-payload.json /tmp/termix-import-runner.mjs
echo "done"

# Termix hosts — reproducible import + Auto-Tmux

Version-controlled definition of the homelab hosts in [Termix](https://termix.site)
so they can be recreated after a PVC loss / re-provision (Termix host data lives
only in its encrypted DB on the PVC — it is not otherwise declarative).

## Files
- **`hosts.json`** — the 6 homelab hosts. **No private key** (injected at runtime).
  `terminalConfig.autoTmux: true` enables **Auto-Tmux** (persistent shell across
  disconnects); `enableTmuxMonitor: true` enables the Tmux Monitor app.
- **`import.sh`** — applies the manifest under the current Termix OIDC user.

## Run
```bash
./import.sh                          # key from ~/.ssh/id_ed25519
TERMIX_SSH_KEY=/path/to/key ./import.sh
```

Idempotent — `overwrite=true`, hosts matched by `ip:port:username`, so re-runs
update in place (no duplicates) and re-assert Auto-Tmux.

## Requirements / caveats
- **You must be logged into Termix** when running: host data is encrypted with a
  per-user, session-derived key, so the import goes through your active session
  (the script reads the token server-side in the pod and calls Termix's own
  `/host/bulk-import`). No active session → the script aborts.
- Needs `kubectl` access to the cluster and the SSH key on disk.
- The private key is injected only into an ephemeral payload that is copied into
  the pod and deleted immediately; it is never written to the repo.

## Edit the host list
Change `hosts.json` and re-run `import.sh`. Add hosts to
`../tmux-setup/inventory/hosts.ini` too so the tmux binary gets installed there.

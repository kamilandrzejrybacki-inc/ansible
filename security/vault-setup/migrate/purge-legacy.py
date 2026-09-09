#!/usr/bin/env python3
"""Step 5 of VAULT-TAXONOMY.md: permanently delete every legacy leaf under secret/homelab/
(everything except homelab/v2/). Refuses to run unless an encrypted snapshot exists.

    purge-legacy.py            list what would be deleted
    purge-legacy.py --apply    delete (KV v2 metadata delete = all versions)
"""
import argparse, glob, json, os, sys, urllib.request, yaml

ADDR = "http://127.0.0.1:8200"
MOUNT = "secret"
KEEP = {"homelab/v2/"}


def token():
    if os.environ.get("VAULT_TOKEN"):
        return os.environ["VAULT_TOKEN"]
    return yaml.safe_load(open(os.path.expanduser("~/.vault-ansible.yml")))["vault_token"]


def call(method, path, tok):
    r = urllib.request.Request(f"{ADDR}/v1/{MOUNT}/{path}", method=method, headers={"X-Vault-Token": tok})
    try:
        with urllib.request.urlopen(r, timeout=8) as resp:
            body = resp.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {}
        raise


def leaves(prefix, tok):
    for k in call("GET", f"metadata/{prefix}?list=true", tok).get("data", {}).get("keys", []):
        p = prefix + k
        if p in KEEP:
            continue
        if k.endswith("/"):
            yield from leaves(p, tok)
        else:
            yield p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    snaps = sorted(glob.glob(os.path.expanduser("~/homelab-backups/vault-snapshot-*.json.enc")))
    if not snaps:
        sys.exit("no ~/homelab-backups/vault-snapshot-*.json.enc — snapshot first")
    tok = token()
    targets = sorted(leaves("homelab/", tok))
    print(f"{len(targets)} legacy leaves (snapshot: {os.path.basename(snaps[-1])})")
    for t in targets:
        print("  ", t)
    if not a.apply:
        print("dry run — pass --apply to delete")
        return
    for t in targets:
        call("DELETE", f"metadata/{t}", tok)
    left = sorted(leaves("homelab/", tok))
    print(f"deleted {len(targets)}; remaining legacy leaves: {left or 'none'}")


if __name__ == "__main__":
    main()

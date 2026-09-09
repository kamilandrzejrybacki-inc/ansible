#!/usr/bin/env python3
"""Step 6 of VAULT-TAXONOMY.md: copy every homelab/v2/<x> leaf to homelab/<x> and verify.
The consumer repoint (ESO prefix, ansible _vault_tree, cellarette refs) happens separately;
this only moves the data and proves it landed byte-identical.

    collapse-v2.py            copy v2 -> homelab, then compare per-field sha256 (idempotent)
    collapse-v2.py --verify   compare only, no writes
"""
import argparse, hashlib, json, os, sys, urllib.request, yaml

ADDR = "http://127.0.0.1:8200"
MOUNT = "secret"
SRC = "homelab/v2/"
DST = "homelab/"


def token():
    return os.environ.get("VAULT_TOKEN") or yaml.safe_load(open(os.path.expanduser("~/.vault-ansible.yml")))["vault_token"]


def call(method, path, tok, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(f"{ADDR}/v1/{MOUNT}/{path}", method=method, data=data,
                               headers={"X-Vault-Token": tok, "Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=8) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else {}


def leaves(prefix, tok):
    for k in call("GET", f"metadata/{prefix}?list=true", tok).get("data", {}).get("keys", []):
        p = prefix + k
        if k.endswith("/"):
            yield from leaves(p, tok)
        else:
            yield p[len(SRC):]                       # suffix after homelab/v2/


def read(prefix, suffix, tok):
    return call("GET", f"data/{prefix}{suffix}", tok)["data"]["data"]


def h(d):
    return {k: hashlib.sha256(v.encode()).hexdigest()[:16] for k, v in d.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    tok = token()
    suffixes = sorted(leaves(SRC, tok))
    print(f"{len(suffixes)} v2 leaves")
    bad = 0
    for s in suffixes:
        src = read(SRC, s, tok)
        if not a.verify:
            call("POST", f"data/{DST}{s}", tok, {"data": src})
        try:
            dst = read(DST, s, tok)
        except urllib.error.HTTPError:
            print(f"  MISSING at homelab/{s}"); bad += 1; continue
        if h(src) != h(dst):
            print(f"  MISMATCH homelab/{s}: src={h(src)} dst={h(dst)}"); bad += 1
    print("collapse:", "clean" if not bad else f"{bad} problems")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

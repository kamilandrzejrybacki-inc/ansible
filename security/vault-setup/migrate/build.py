#!/usr/bin/env python3
"""Build the issuer-keyed Vault tree under secret/homelab/v2/ from map.yaml.

    build.py --dry-run     # print the plan: destinations, evictions, deletes, CONFLICTS. No writes.
    build.py --apply       # write to secret/homelab/v2/*. Refuses if any conflict exists.
    build.py --verify      # after apply: every dst path exists with every expected field.

Reads the current Vault value for each source (or the LIVE sops copy for `seed: sops` entries),
groups fields by destination, detects merge conflicts (two sources -> same dst#field with
different values), and never prints a secret value. Auth: VAULT_TOKEN env, else ~/.vault-token,
else ~/.vault-ansible.yml (same precedence as cellarette).
"""
import argparse, hashlib, json, os, subprocess, sys, urllib.error, urllib.request
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
SOPS_DIR = os.path.expanduser("~/Code/argocd-apps/secrets/bootstrap/")
SOPS_CFG = os.path.expanduser("~/Code/argocd-apps/.sops.yaml")
MOUNT = "secret"


def vault_token():
    # Infra script: prefer the ansible-automation (infra) token. ~/.vault-token is the
    # narrow cellarette-local token and 403s on most of the tree.
    if os.environ.get("VAULT_TOKEN"):
        return os.environ["VAULT_TOKEN"]
    p = os.path.expanduser("~/.vault-ansible.yml")
    if os.path.exists(p):
        return yaml.safe_load(open(p))["vault_token"]
    return open(os.path.expanduser("~/.vault-token")).read().strip()


def vault_addr():
    return os.environ.get("VAULT_ADDR") or yaml.safe_load(
        open(os.path.expanduser("~/.vault-ansible.yml"))).get("vault_addr", "http://127.0.0.1:8200")


class Vault:
    def __init__(self):
        self.addr, self.tok = vault_addr().rstrip("/"), vault_token()

    def _req(self, path, method="GET", body=None):
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(f"{self.addr}/v1/{path}", data=data, method=method,
                                   headers={"X-Vault-Token": self.tok, "Content-Type": "application/json"})
        with urllib.request.urlopen(r, timeout=15) as x:
            return json.load(x) if x.length != 0 else {}

    def read(self, rel):
        try:
            return self._req(f"{MOUNT}/data/homelab/{rel}")["data"]["data"] or {}
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    def write(self, rel, data):
        self._req(f"{MOUNT}/data/homelab/{rel}", "POST", {"data": data})


def sops_value(file, key):
    out = subprocess.run(["sops", "--config", SOPS_CFG, "-d", SOPS_DIR + file], capture_output=True, text=True)
    if out.returncode:
        raise RuntimeError(f"sops -d {file} failed: {out.stderr.strip()[:200]}")
    for doc in yaml.safe_load_all(out.stdout):
        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k in ("stringData", "data") and isinstance(v, dict) and key in v:
                        return str(v[key])
                    r = walk(v)
                    if r is not None:
                        return r
            elif isinstance(o, list):
                for x in o:
                    r = walk(x)
                    if r is not None:
                        return r
        r = walk(doc)
        if r is not None:
            return r
    raise RuntimeError(f"{file}: key {key} not found")


def h(v):
    return hashlib.sha256(str(v).encode()).hexdigest()[:10]


def plan(m, vault):
    """Return (dests, evicts, deletes, conflicts, missing).
    dests: {dst_path: {field: value}}"""
    dests, evicts, deletes, conflicts, missing = {}, [], [], [], []
    cache = {}

    def src_secret(old):
        if old not in cache:
            cache[old] = vault.read(old)
        return cache[old]

    for src, spec in m["map"].items():
        if "#" not in src:            # whole-secret action
            if spec == "delete":
                deletes.append(src)
            continue
        old, field = src.split("#", 1)
        if spec == "evict":
            evicts.append(src)
            continue
        if spec == "delete":
            deletes.append(src)
            continue
        if isinstance(spec, dict):
            dst, seed = spec["dst"], spec.get("seed")
        else:
            dst, seed = spec, None
        dpath, dfield = dst.split("#", 1)
        if seed and "sops" in seed:
            val = sops_value(seed["sops"], seed["key"])
        else:
            s = src_secret(old)
            if s is None or field not in s:
                missing.append(src)
                continue
            val = s[field]
        bucket = dests.setdefault(dpath, {})
        if dfield in bucket and h(bucket[dfield]) != h(val):
            conflicts.append(f"{dpath}#{dfield}: sources disagree (latest from {src})")
        bucket.setdefault(dfield, val)
    return dests, evicts, deletes, conflicts, missing


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    g.add_argument("--verify", action="store_true")
    a = ap.parse_args()

    m = yaml.safe_load(open(os.path.join(HERE, "map.yaml")))
    prefix = m["staging_prefix"].split("/", 1)[1]      # "v2"
    vault = Vault()

    if a.verify:
        dests, *_ = plan(m, vault)
        bad = 0
        for dpath, fields in sorted(dests.items()):
            got = vault.read(f"{prefix}/{dpath}") or {}
            for f in fields:
                if f not in got:
                    print(f"  MISSING {prefix}/{dpath}#{f}"); bad += 1
                elif h(got[f]) != h(fields[f]):
                    print(f"  MISMATCH {prefix}/{dpath}#{f}"); bad += 1
        print(f"verify: {len(dests)} paths, {bad} problems")
        sys.exit(1 if bad else 0)

    dests, evicts, deletes, conflicts, missing = plan(m, vault)
    restricted = set(m["restricted_issuers"]); rpaths = set(m["restricted_paths"])
    print(f"== plan: {len(dests)} destination paths, {sum(len(v) for v in dests.values())} fields")
    for dpath in sorted(dests):
        tag = " [RESTRICTED]" if dpath.split("/")[0] in restricted or dpath in rpaths else ""
        print(f"  {prefix}/{dpath}: {sorted(dests[dpath])}{tag}")
    print(f"== evict to config ({len(evicts)}): " + ", ".join(sorted(evicts)))
    print(f"== delete ({len(deletes)}): " + ", ".join(sorted(deletes)))
    if missing:
        print(f"== MISSING sources ({len(missing)}): " + ", ".join(missing))
    if conflicts:
        print(f"== CONFLICTS ({len(conflicts)}) — resolve before --apply:")
        for c in conflicts:
            print("   " + c)
    if a.apply:
        if conflicts or missing:
            print("refusing to apply: conflicts/missing present"); sys.exit(2)
        for dpath, fields in dests.items():
            vault.write(f"{prefix}/{dpath}", fields)
        print(f"applied: wrote {len(dests)} paths under {MOUNT}/homelab/{prefix}/")


if __name__ == "__main__":
    main()

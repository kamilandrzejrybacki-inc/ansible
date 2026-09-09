#!/usr/bin/env python3
"""Emit ExternalSecret + SecretStore manifests from manifest.yaml.

    generate.py --out ~/Code/argocd-apps/secrets/eso [--prefix homelab/v2]

Secret material is NEVER written here — ExternalSecrets carry only Vault *references*.
Non-secret config (`literals`) is resolved at generation time from the sops files / old Vault
tree / live k8s Secret and written verbatim into the ExternalSecret template, so it lives in
git (Q3: config is evicted from Vault). Output layout: <out>/<ns>/secretstore.yaml and
<out>/<ns>/es-<name>.yaml.
"""
import argparse, base64, json, os, re, subprocess, sys, urllib.request
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
SOPS_DIR = os.path.expanduser("~/Code/argocd-apps/secrets/bootstrap/")
SOPS_CFG = os.path.expanduser("~/Code/argocd-apps/.sops.yaml")
_sops_cache = {}


def vault_token():
    if os.environ.get("VAULT_TOKEN"):
        return os.environ["VAULT_TOKEN"]
    return yaml.safe_load(open(os.path.expanduser("~/.vault-ansible.yml")))["vault_token"]


def sops_doc(file):
    if file not in _sops_cache:
        out = subprocess.run(["sops", "--config", SOPS_CFG, "-d", SOPS_DIR + file], capture_output=True, text=True, check=True).stdout
        vals = {}
        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k in ("stringData", "data") and isinstance(v, dict):
                        vals.update({kk: str(vv) for kk, vv in v.items()})
                    else:
                        walk(v)
            elif isinstance(o, list):
                for x in o:
                    walk(x)
        for d in yaml.safe_load_all(out):
            walk(d)
        _sops_cache[file] = vals
    return _sops_cache[file]


def resolve_literal(spec):
    """Return the literal string for a `literals` entry. Secret-bearing sources are only used with
    an `extract` that strips the secret part (DSN head/tail) — the raw value never lands in output."""
    if isinstance(spec, str):
        return spec
    if "sops" in spec:
        val = sops_doc(spec["sops"])[spec["key"]]
    elif "vault_old" in spec:
        old, field = spec["vault_old"].split("#", 1)
        r = urllib.request.Request(f"http://127.0.0.1:8200/v1/secret/data/homelab/{old}", headers={"X-Vault-Token": vault_token()})
        val = json.load(urllib.request.urlopen(r, timeout=8))["data"]["data"][field]
    elif "k8s" in spec:
        ns, name = spec["k8s"].split("/", 1)
        out = subprocess.run(["kubectl", "-n", ns, "get", "secret", name, "-o", f"jsonpath={{.data.{spec['key']}}}"], capture_output=True, text=True, check=True).stdout
        val = base64.b64decode(out).decode()
    else:
        raise ValueError(f"unknown literal source: {spec}")
    if spec.get("extract"):
        m = re.search(spec["extract"], val)
        if not m:
            raise ValueError(f"extract {spec['extract']!r} matched nothing for {spec}")
        val = m.group(1)
    return str(val)


def secretstore(ns, st):
    return {
        "apiVersion": "external-secrets.io/v1beta1", "kind": "SecretStore",
        "metadata": {"name": st["name"], "namespace": ns},
        "spec": {"provider": {"vault": {
            "server": st["server"], "path": st["path"], "version": st["version"],
            "auth": {"appRole": {
                "path": "approle",
                "roleRef": {"name": st["approle_secret"], "key": "role_id"},
                "secretRef": {"name": st["approle_secret"], "key": "secret_id"},
            }},
        }}},
    }


def external_secret(s, prefix, st, refresh):
    data, tmpl = [], {}
    for k8s_key, ref in (s.get("from_vault") or {}).items():
        path, field = ref.split("#", 1)
        data.append({"secretKey": k8s_key, "remoteRef": {"key": f"{prefix}/{path}", "property": field}})
    literals = {k: resolve_literal(v) for k, v in (s.get("literals") or {}).items()}
    templates = dict(s.get("templates") or {})
    # Literal aliases are known at generation time: inline them into the template strings so they
    # never become keys of the rendered Secret. Only secret aliases stay as {{ .alias }}.
    for k8s_key, t in templates.items():
        for name, val in literals.items():
            t = re.sub(r"\{\{\s*\." + re.escape(name) + r"\s*\}\}", val.replace("\\", "\\\\"), t)
        templates[k8s_key] = t
    used_as_alias = set(re.findall(r"\{\{\s*\.(\w+)\s*\}\}", " ".join((s.get("templates") or {}).values())))
    # Literals referenced only as template aliases are consumed; the rest are real config keys.
    for k8s_key, val in literals.items():
        if k8s_key not in used_as_alias:
            tmpl[k8s_key] = val
    tmpl.update(templates)
    alias_refs = {a for a in used_as_alias if a not in literals}      # secret aliases (from_vault keys used only in templates)
    spec = {
        "refreshInterval": s.get("refresh", refresh),
        "secretStoreRef": {"name": st["name"], "kind": "SecretStore"},
        "target": {"name": s["name"], "creationPolicy": "Owner"},
        "data": data,
    }
    if tmpl or s.get("type") or alias_refs:
        # Explicit template: pass through every non-alias data key, add literals + rendered templates.
        merged = {d["secretKey"]: "{{ .%s }}" % d["secretKey"] for d in data if d["secretKey"] not in alias_refs}
        merged.update(tmpl)
        spec["target"]["template"] = {"type": s.get("type", "Opaque"), "engineVersion": "v2", "data": merged}
    return {"apiVersion": "external-secrets.io/v1beta1", "kind": "ExternalSecret",
            "metadata": {"name": s["name"], "namespace": s["ns"]}, "spec": spec}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--prefix")
    a = ap.parse_args()
    m = yaml.safe_load(open(os.path.join(HERE, "manifest.yaml")))
    prefix = a.prefix or m["prefix"]
    st, refresh = m["store"], m.get("refresh", "15m")
    namespaces = {}
    for s in m["secrets"]:
        namespaces.setdefault(s["ns"], []).append(s)
    n = 0
    for ns, secrets in sorted(namespaces.items()):
        d = os.path.join(a.out, ns); os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "secretstore.yaml"), "w") as f:
            yaml.safe_dump(secretstore(ns, st), f, sort_keys=False)
        for s in secrets:
            with open(os.path.join(d, f"es-{s['name']}.yaml"), "w") as f:
                yaml.safe_dump(external_secret(s, prefix, st, refresh), f, sort_keys=False)
            n += 1
    print(f"generated {n} ExternalSecrets across {len(namespaces)} namespaces -> {a.out} (prefix {prefix})")


if __name__ == "__main__":
    main()

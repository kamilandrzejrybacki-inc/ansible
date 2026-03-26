#!/usr/bin/env python3
"""vault-n8n-sync: Vault KV → n8n env-var sync daemon (community edition).

Reads secrets from HashiCorp Vault KV and injects them as N8N_VAR_* environment
variables into the n8n container.  When Vault secrets change, it gracefully
recreates the n8n container with the updated env vars.

Workflows reference secrets via ={{ $env.N8N_VAR_KEY_NAME }} in Set nodes
(community edition — $vars.* requires an enterprise license).

Requires Docker socket mount: -v /var/run/docker.sock:/var/run/docker.sock

Environment variables:
  VAULT_ADDR       Vault base URL, e.g. http://10.0.0.1:8200   (required)
  VAULT_TOKEN      Read-only Vault token for the KV path         (required)
  VAULT_KV_PATH    KV path under the secret mount                (default: homelab/n8n)
  N8N_CONTAINER    n8n container name                            (default: n8n)
  SYNC_INTERVAL    Seconds between Vault polls                   (default: 300)
  EXCLUDED_KEYS    Comma-separated Vault keys NOT to inject       (default: see below)
"""

import http.client
import json
import os
import socket
import time
import urllib.error
import urllib.request

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

VAULT_ADDR = os.environ["VAULT_ADDR"].rstrip("/")
VAULT_TOKEN = os.environ["VAULT_TOKEN"]
VAULT_KV_PATH = os.environ.get("VAULT_KV_PATH", "homelab/n8n")
N8N_CONTAINER = os.environ.get("N8N_CONTAINER", "n8n")
SYNC_INTERVAL = int(os.environ.get("SYNC_INTERVAL", "300"))
EXCLUDED_KEYS = frozenset(
    os.environ.get(
        "EXCLUDED_KEYS",
        "owner_email,owner_password,workflows_repo_token",
    ).split(",")
)
DOCKER_SOCKET = "/var/run/docker.sock"
N8N_URL = os.environ.get("N8N_URL", f"http://{os.environ.get('N8N_CONTAINER', 'n8n')}:5678")

# ---------------------------------------------------------------------------
# Docker API  (stdlib-only, unix socket)
# ---------------------------------------------------------------------------


class _UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: str) -> None:
        super().__init__("localhost")
        self._socket_path = socket_path

    def connect(self) -> None:  # override to use unix socket
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(self._socket_path)
        self.sock = sock


class DockerAPI:
    def _req(self, method: str, path: str, body=None):
        conn = _UnixHTTPConnection(DOCKER_SOCKET)
        data = json.dumps(body).encode() if body is not None else None
        conn.request(
            method,
            path,
            body=data,
            headers={"Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        raw = resp.read()
        conn.close()
        try:
            return resp.status, json.loads(raw) if raw else {}
        except Exception:
            return resp.status, {}

    def inspect(self, name: str) -> dict | None:
        status, data = self._req("GET", f"/containers/{name}/json")
        return data if status == 200 else None

    def stop(self, name: str, timeout: int = 15) -> None:
        self._req("POST", f"/containers/{name}/stop?t={timeout}")

    def remove(self, name: str) -> None:
        self._req("DELETE", f"/containers/{name}?force=true")

    def create(self, name: str, config: dict) -> tuple[int, dict]:
        return self._req("POST", f"/containers/create?name={name}", config)

    def start(self, name: str) -> None:
        self._req("POST", f"/containers/{name}/start")


# ---------------------------------------------------------------------------
# Vault
# ---------------------------------------------------------------------------


def vault_read_secrets() -> dict:
    req = urllib.request.Request(
        f"{VAULT_ADDR}/v1/secret/data/{VAULT_KV_PATH}",
        headers={"X-Vault-Token": VAULT_TOKEN},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.load(r)["data"]["data"]
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Vault read failed HTTP {exc.code}: {exc.read().decode()}") from exc


# ---------------------------------------------------------------------------
# n8n  (session auth — used only for the active-execution guard)
# ---------------------------------------------------------------------------


def _n8n_login(email: str, password: str) -> str:
    """POST /rest/login; return n8n-auth cookie value."""
    req = urllib.request.Request(
        f"{N8N_URL}/rest/login",
        data=json.dumps({"emailOrLdapLoginId": email, "password": password}).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        cookie = r.headers.get("Set-Cookie", "")
    for part in cookie.split(";"):
        part = part.strip()
        if part.startswith("n8n-auth="):
            return part.split("=", 1)[1]
    raise RuntimeError("Login succeeded but no n8n-auth cookie found")


def _n8n_active_executions(cookie: str) -> int:
    """Return count of currently running workflow executions."""
    req = urllib.request.Request(
        f"{N8N_URL}/rest/executions?status=running&limit=10",
        headers={"Cookie": f"n8n-auth={cookie}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.load(r)
        # n8n REST API returns {"data": {"results": [...], "count": N, ...}}
        inner = data.get("data", data) if isinstance(data, dict) else data
        if isinstance(inner, dict):
            results = inner.get("results", [])
            return len(results)
        if isinstance(inner, list):
            return len(inner)
        return 0
    except Exception:
        return 0  # if we can't check, assume safe to proceed


# Track consecutive skips so we can force-sync after too many deferrals
_consecutive_skips = 0
MAX_CONSECUTIVE_SKIPS = 3  # force sync after this many deferrals


def _has_active_executions(secrets: dict) -> bool:
    global _consecutive_skips
    email = secrets.get("owner_email")
    password = secrets.get("owner_password")
    if not email or not password:
        return False  # can't check → don't block
    try:
        cookie = _n8n_login(email, password)
        count = _n8n_active_executions(cookie)
        if count > 0:
            _consecutive_skips += 1
            if _consecutive_skips > MAX_CONSECUTIVE_SKIPS:
                print(
                    f"[sync] Forcing recreation after {_consecutive_skips} consecutive skips "
                    f"({count} execution(s) still running)",
                    flush=True,
                )
                _consecutive_skips = 0
                return False  # allow sync to proceed
            return True
        _consecutive_skips = 0
        return False
    except Exception as exc:
        print(f"[sync] Warning: could not check active executions: {exc}", flush=True)
        return False


# ---------------------------------------------------------------------------
# Sync logic
# ---------------------------------------------------------------------------


def _desired_vars(secrets: dict) -> dict[str, str]:
    return {k: str(v) for k, v in secrets.items() if k not in EXCLUDED_KEYS}


def _current_n8n_vars(inspect_data: dict) -> dict[str, str]:
    result = {}
    for entry in inspect_data.get("Config", {}).get("Env") or []:
        if entry.startswith("N8N_VAR_"):
            key, _, val = entry[len("N8N_VAR_"):].partition("=")
            result[key] = val
    return result


def _build_env(secrets: dict, current_env: list[str]) -> list[str]:
    """Rebuild the container env list: keep non-N8N_VAR_* lines, inject new ones.

    Also ensures N8N_BLOCK_ENV_ACCESS_IN_NODE=false is always present so that
    $env.* expressions in workflows can read N8N_VAR_* values (community edition).
    """
    base = [
        e for e in current_env
        if not e.startswith("N8N_VAR_")
        and not e.startswith("N8N_BLOCK_ENV_ACCESS_IN_NODE=")
        and not e.startswith("N8N_DEFAULT_BINARY_DATA_MODE=")
    ]
    base.append("N8N_BLOCK_ENV_ACCESS_IN_NODE=false")
    base.append("N8N_DEFAULT_BINARY_DATA_MODE=filesystem")
    for key, value in sorted(_desired_vars(secrets).items()):
        base.append(f"N8N_VAR_{key}={value}")
    return base


def _build_create_config(inspect_data: dict, new_env: list[str]) -> dict:
    cfg = inspect_data["Config"]
    hcfg = inspect_data["HostConfig"]
    networks = inspect_data["NetworkSettings"]["Networks"]
    return {
        "Image": cfg["Image"],
        "Env": new_env,
        "HostConfig": {
            "Binds": hcfg.get("Binds") or [],
            "PortBindings": hcfg.get("PortBindings") or {},
            "RestartPolicy": hcfg.get("RestartPolicy") or {"Name": "unless-stopped"},
            "ExtraHosts": hcfg.get("ExtraHosts") or [],
        },
        "NetworkingConfig": {
            "EndpointsConfig": {net: {} for net in networks},
        },
    }


def recreate(docker: DockerAPI, inspect_data: dict, new_env: list[str]) -> None:
    print(f"[sync] Recreating {N8N_CONTAINER} with updated secrets...", flush=True)
    create_cfg = _build_create_config(inspect_data, new_env)
    docker.stop(N8N_CONTAINER)
    docker.remove(N8N_CONTAINER)
    status, result = docker.create(N8N_CONTAINER, create_cfg)
    if status not in (200, 201):
        raise RuntimeError(f"Container create failed HTTP {status}: {result}")
    docker.start(N8N_CONTAINER)
    print(f"[sync] {N8N_CONTAINER} restarted with {len(new_env)} env vars", flush=True)


def sync(docker: DockerAPI) -> None:
    secrets = vault_read_secrets()
    inspect_data = docker.inspect(N8N_CONTAINER)
    if inspect_data is None:
        raise RuntimeError(f"Container {N8N_CONTAINER!r} not found")

    desired = _desired_vars(secrets)
    current = _current_n8n_vars(inspect_data)

    if current == desired:
        print(f"[sync] In sync ({len(desired)} vars, no changes)", flush=True)
        return

    added = sorted(k for k in desired if k not in current)
    changed = sorted(k for k in desired if k in current and current[k] != desired[k])
    removed = sorted(k for k in current if k not in desired)
    print(f"[sync] added={added} changed={changed} removed={removed}", flush=True)

    if _has_active_executions(secrets):
        print(
            "[sync] Skipping recreation — workflows are running. Will retry next cycle.",
            flush=True,
        )
        return

    new_env = _build_env(secrets, inspect_data["Config"]["Env"] or [])
    recreate(docker, inspect_data, new_env)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(
        f"[sync] Starting | Vault={VAULT_ADDR} | path={VAULT_KV_PATH} | "
        f"container={N8N_CONTAINER} | interval={SYNC_INTERVAL}s",
        flush=True,
    )
    docker = DockerAPI()

    # Initial sync with retry until Docker/n8n is reachable
    while True:
        try:
            sync(docker)
            break
        except Exception as exc:
            print(f"[sync] Initial sync failed, retrying in 10s: {exc}", flush=True)
            time.sleep(10)

    # Periodic sync
    while True:
        time.sleep(SYNC_INTERVAL)
        try:
            sync(docker)
        except Exception as exc:
            print(f"[sync] Sync error: {exc}", flush=True)

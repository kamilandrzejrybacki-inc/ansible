# Hermes Memory Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend Hermes on lw-pi with a federated Memory tab (Local + Supermemory + Dreaming), a three-phase nightly Dreaming sidecar ported from OpenClaw, and a self-hosted Supermemory service — all built as arm64 images via Kaniko on lw-c1 and deployed through the existing Ansible playbook.

**Architecture:** Four independent deliverables shipped together: (1) a `docker-builders` Helm chart that stands up a homelab container registry + Kaniko build infrastructure on lw-c1; (2) a `hermes-dreaming` Python sidecar that runs Light→REM→Deep memory consolidation nightly; (3) a `hermes-webui-fork` that adds `/api/memory/federated` + updated Memory tab UI; (4) Ansible deployment updates that wire all three into the existing lw-pi stack.

**Tech Stack:** Helm 3, ArgoCD, Kaniko, registry:2, QEMU multiarch, Python 3.12, Groq SDK, vanilla JS, Playwright, Ansible, Docker Compose

**Spec:** `docs/superpowers/specs/2026-04-13-hermes-memory-enhancement-design.md`

---

## File Map

### Phase 1 — `kamilandrzejrybacki-inc/helm` repo

| File | Action |
|------|--------|
| `charts/docker-builders/Chart.yaml` | Create |
| `charts/docker-builders/values.yaml` | Create |
| `charts/docker-builders/templates/namespace.yaml` | Create |
| `charts/docker-builders/templates/qemu-daemonset.yaml` | Create |
| `charts/docker-builders/templates/registry-deployment.yaml` | Create |
| `charts/docker-builders/templates/registry-service.yaml` | Create |
| `charts/docker-builders/templates/registry-pvc.yaml` | Create |
| `charts/docker-builders/templates/kaniko-rbac.yaml` | Create |

### Phase 2 — `kamilandrzejrybacki-inc/hermes-dreaming` repo (new)

| File | Action |
|------|--------|
| `dreaming/__init__.py` | Create |
| `dreaming/models.py` | Create |
| `dreaming/lock.py` | Create |
| `dreaming/phases/__init__.py` | Create |
| `dreaming/phases/light.py` | Create |
| `dreaming/phases/rem.py` | Create |
| `dreaming/phases/deep.py` | Create |
| `dreaming/runner.py` | Create |
| `entrypoint.sh` | Create |
| `Dockerfile` | Create |
| `requirements.txt` | Create |
| `tests/__init__.py` | Create |
| `tests/test_lock.py` | Create |
| `tests/test_phases.py` | Create |

### Phase 3 — `kamilandrzejrybacki-inc/hermes-webui-fork` repo (fork of upstream)

| File | Action |
|------|--------|
| `api/memory_federation.py` | Create |
| `api/routes.py` | Modify (add 4 lines) |
| `static/panels.js` | Modify (replace `loadMemory`) |
| `tests/test_memory_federation.py` | Create |
| `tests/test_federated_endpoint.py` | Create |
| `tests/e2e/memory/federation.spec.ts` | Create |
| `package.json` (root) | Modify (add playwright dev dep) |
| `playwright.config.ts` | Create |

### Phase 4 — `kamilandrzejrybacki-inc/ansible` repo

| File | Action |
|------|--------|
| `infrastructure/hermes-pi/inventory/hosts.ini` | Modify |
| `infrastructure/hermes-pi/group_vars/all.yml` | Modify |
| `infrastructure/hermes-pi/setup.yml` | Modify |
| `infrastructure/hermes-pi/templates/docker-compose.yml.j2` | Modify |
| `infrastructure/hermes-pi/templates/env.j2` | Modify |
| `infrastructure/hermes-pi/templates/daemon.json.j2` | Create |
| `infrastructure/hermes-pi/templates/argocd-docker-builders-app.yaml.j2` | Create |
| `infrastructure/hermes-pi/templates/kaniko-job.yaml.j2` | Create |

---

## Phase 1 — docker-builders Helm Chart

### Task 1: Chart scaffold + namespace + QEMU DaemonSet

**Repo:** `kamilandrzejrybacki-inc/helm`

**Files:**
- Create: `charts/docker-builders/Chart.yaml`
- Create: `charts/docker-builders/values.yaml`
- Create: `charts/docker-builders/templates/namespace.yaml`
- Create: `charts/docker-builders/templates/qemu-daemonset.yaml`

- [ ] **Step 1: Create Chart.yaml**

```yaml
# charts/docker-builders/Chart.yaml
apiVersion: v2
name: docker-builders
description: Homelab arm64 image build infrastructure (registry + QEMU + Kaniko)
type: application
version: 0.1.0
appVersion: "0.1.0"
```

- [ ] **Step 2: Create values.yaml**

```yaml
# charts/docker-builders/values.yaml
registry:
  nodePort: 30500
  storageSize: 10Gi
  storageClass: local-path

qemu:
  image: multiarch/qemu-user-static:latest

kaniko:
  serviceAccountName: kaniko-builder
```

- [ ] **Step 3: Create namespace.yaml**

```yaml
# charts/docker-builders/templates/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: docker-builders
```

- [ ] **Step 4: Create qemu-daemonset.yaml**

```yaml
# charts/docker-builders/templates/qemu-daemonset.yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: qemu-user-static
  namespace: docker-builders
spec:
  selector:
    matchLabels:
      app: qemu-user-static
  template:
    metadata:
      labels:
        app: qemu-user-static
    spec:
      initContainers:
      - name: qemu-user-static
        image: {{ .Values.qemu.image }}
        args: ["--reset", "-p", "yes"]
        securityContext:
          privileged: true
        volumeMounts:
        - name: binfmt
          mountPath: /proc/sys/fs/binfmt_misc
      containers:
      - name: pause
        image: registry.k8s.io/pause:3.9
        resources:
          limits:
            cpu: 10m
            memory: 10Mi
      volumes:
      - name: binfmt
        hostPath:
          path: /proc/sys/fs/binfmt_misc
```

- [ ] **Step 5: Commit**

```bash
cd helm
git add charts/docker-builders/
git commit -m "feat(docker-builders): chart scaffold, namespace, QEMU DaemonSet"
```

---

### Task 2: Registry + Kaniko RBAC

**Files:**
- Create: `charts/docker-builders/templates/registry-pvc.yaml`
- Create: `charts/docker-builders/templates/registry-deployment.yaml`
- Create: `charts/docker-builders/templates/registry-service.yaml`
- Create: `charts/docker-builders/templates/kaniko-rbac.yaml`

- [ ] **Step 1: Create registry-pvc.yaml**

```yaml
# charts/docker-builders/templates/registry-pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: registry-data
  namespace: docker-builders
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: {{ .Values.registry.storageClass }}
  resources:
    requests:
      storage: {{ .Values.registry.storageSize }}
```

- [ ] **Step 2: Create registry-deployment.yaml**

```yaml
# charts/docker-builders/templates/registry-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: registry
  namespace: docker-builders
spec:
  replicas: 1
  selector:
    matchLabels:
      app: registry
  template:
    metadata:
      labels:
        app: registry
    spec:
      containers:
      - name: registry
        image: registry:2
        ports:
        - containerPort: 5000
        env:
        - name: REGISTRY_STORAGE_DELETE_ENABLED
          value: "true"
        volumeMounts:
        - name: data
          mountPath: /var/lib/registry
        readinessProbe:
          httpGet:
            path: /v2/
            port: 5000
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: registry-data
```

- [ ] **Step 3: Create registry-service.yaml**

```yaml
# charts/docker-builders/templates/registry-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: registry
  namespace: docker-builders
spec:
  type: NodePort
  selector:
    app: registry
  ports:
  - name: registry
    port: 5000
    targetPort: 5000
    nodePort: {{ .Values.registry.nodePort }}
```

- [ ] **Step 4: Create kaniko-rbac.yaml**

```yaml
# charts/docker-builders/templates/kaniko-rbac.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ .Values.kaniko.serviceAccountName }}
  namespace: docker-builders
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: kaniko-builder
rules:
- apiGroups: ["batch"]
  resources: ["jobs"]
  verbs: ["create", "get", "list", "watch", "delete"]
- apiGroups: [""]
  resources: ["pods", "pods/log"]
  verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: kaniko-builder
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: kaniko-builder
subjects:
- kind: ServiceAccount
  name: {{ .Values.kaniko.serviceAccountName }}
  namespace: docker-builders
```

- [ ] **Step 5: Lint the chart locally**

```bash
helm lint charts/docker-builders/
```

Expected output: `1 chart(s) linted, 0 chart(s) failed`

- [ ] **Step 6: Commit and push to main**

```bash
git add charts/docker-builders/
git commit -m "feat(docker-builders): registry, PVC, Kaniko RBAC"
git push origin main
```

---

## Phase 2 — hermes-dreaming Sidecar

**Prerequisites:** Create new GitHub repo `kamilandrzejrybacki-inc/hermes-dreaming` and clone it locally.

### Task 3: Models, lock, package structure

**Repo:** `kamilandrzejrybacki-inc/hermes-dreaming`

**Files:**
- Create: `dreaming/__init__.py`
- Create: `dreaming/models.py`
- Create: `dreaming/lock.py`
- Create: `dreaming/phases/__init__.py`
- Create: `requirements.txt`
- Create: `tests/__init__.py`
- Create: `tests/test_lock.py`

- [ ] **Step 1: Create dreaming/__init__.py and dreaming/phases/__init__.py**

Both are empty package markers:
```bash
mkdir -p dreaming/phases tests
touch dreaming/__init__.py dreaming/phases/__init__.py tests/__init__.py
```

- [ ] **Step 2: Create dreaming/models.py**

```python
# dreaming/models.py
from dataclasses import dataclass


@dataclass
class Candidate:
    content: str
    source_file: str
    frequency: float = 0.0
    relevance: float = 0.0
    query_diversity: float = 0.0
    recency: float = 0.0
    consolidation: float = 0.0
    conceptual_richness: float = 0.0
    is_stale: bool = False

    def score(self) -> float:
        return (
            self.frequency * 0.24
            + self.relevance * 0.30
            + self.query_diversity * 0.15
            + self.recency * 0.15
            + self.consolidation * 0.10
            + self.conceptual_richness * 0.06
        )
```

- [ ] **Step 3: Write failing test for Candidate.score()**

```python
# tests/test_lock.py  (add score test here for now, will move later)
import pytest
from dreaming.models import Candidate


def test_score_weights_sum_to_one():
    c = Candidate(content="x", source_file="f",
                  frequency=1, relevance=1, query_diversity=1,
                  recency=1, consolidation=1, conceptual_richness=1)
    assert abs(c.score() - 1.0) < 1e-9


def test_score_partial():
    c = Candidate(content="x", source_file="f", relevance=1.0)
    assert abs(c.score() - 0.30) < 1e-9
```

- [ ] **Step 4: Create requirements.txt**

```
groq>=0.4.0
pyyaml>=6.0
pytest>=8.0
```

- [ ] **Step 5: Install deps and run tests**

```bash
pip install -r requirements.txt
pytest tests/test_lock.py -v
```

Expected: `2 passed`

- [ ] **Step 6: Create dreaming/lock.py**

```python
# dreaming/lock.py
import os
from pathlib import Path


class LockError(Exception):
    pass


def acquire(lock_path: Path) -> None:
    """Write PID to lock_path. Raises LockError if it already exists."""
    if lock_path.exists():
        raise LockError(
            f"Lock file exists at {lock_path}. "
            "A previous run may have crashed — delete it manually to resume."
        )
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(str(os.getpid()))


def release(lock_path: Path) -> None:
    """Remove lock_path if it exists."""
    if lock_path.exists():
        lock_path.unlink()
```

- [ ] **Step 7: Add lock tests to tests/test_lock.py**

```python
import tempfile
from pathlib import Path
import pytest
from dreaming.models import Candidate
from dreaming import lock


def test_score_weights_sum_to_one():
    c = Candidate(content="x", source_file="f",
                  frequency=1, relevance=1, query_diversity=1,
                  recency=1, consolidation=1, conceptual_richness=1)
    assert abs(c.score() - 1.0) < 1e-9


def test_score_partial():
    c = Candidate(content="x", source_file="f", relevance=1.0)
    assert abs(c.score() - 0.30) < 1e-9


def test_acquire_creates_file():
    with tempfile.TemporaryDirectory() as td:
        lp = Path(td) / ".dreams" / "lock"
        lock.acquire(lp)
        assert lp.exists()
        lock.release(lp)


def test_acquire_raises_if_locked():
    with tempfile.TemporaryDirectory() as td:
        lp = Path(td) / ".dreams" / "lock"
        lock.acquire(lp)
        with pytest.raises(lock.LockError):
            lock.acquire(lp)
        lock.release(lp)


def test_release_is_idempotent():
    with tempfile.TemporaryDirectory() as td:
        lp = Path(td) / ".dreams" / "lock"
        lock.release(lp)  # no error on missing file


def test_run_skipped_when_lock_exists(monkeypatch, tmp_path):
    """Runner must skip (not write) when lock file exists at startup."""
    from dreaming import runner
    memories_dir = tmp_path / "memories"
    memories_dir.mkdir()
    lock_path = memories_dir / ".dreams" / "lock"
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text("99999")  # simulate stuck lock

    monkeypatch.setenv("HERMES_MEMORIES_DIR", str(memories_dir))
    monkeypatch.setenv("DREAMING_ENABLED", "true")
    monkeypatch.setenv("GROQ_API_KEY", "fake")

    # runner.run_once() should return early — no phase files written
    runner.run_once()

    assert not (memories_dir / "DREAMS.md").exists()
    assert not (memories_dir / "MEMORY.md").exists()
```

- [ ] **Step 8: Run tests — expect all pass except the runner import (runner not yet created)**

```bash
pytest tests/test_lock.py -v -k "not run_skipped"
```

Expected: `5 passed`

- [ ] **Step 9: Commit**

```bash
git add dreaming/ tests/ requirements.txt
git commit -m "feat: models, lock, package structure with tests"
```

---

### Task 4: Light phase

**Files:**
- Create: `dreaming/phases/light.py`
- Create: `tests/test_phases.py`

- [ ] **Step 1: Write failing tests for Light phase**

```python
# tests/test_phases.py
import json
import tempfile
from pathlib import Path

import pytest
from dreaming.models import Candidate


# ── Light phase ────────────────────────────────────────────────────────────────

def _make_session(tmp_path: Path, messages: list, name="s1.json") -> Path:
    sessions_dir = tmp_path / "memories" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    f = sessions_dir / name
    f.write_text(json.dumps({"messages": messages}))
    return sessions_dir


def test_light_deduplicates_against_memory_md(tmp_path):
    from dreaming.phases import light
    # Add a sentence to MEMORY.md that also appears in sessions
    memories_dir = tmp_path / "memories"
    memories_dir.mkdir()
    mem = memories_dir / "MEMORY.md"
    mem.write_text("- Kamil prefers concise communication.\n")
    _make_session(tmp_path, [
        {"role": "assistant", "content": "Kamil prefers concise communication. Also loves automation."}
    ])
    candidates = light.run(memories_dir, lookback_days=30)
    contents = [c.content for c in candidates]
    # "Kamil prefers concise communication" is in MEMORY.md — must not appear as candidate
    assert not any("prefers concise communication" in c.lower() for c in contents)
    # New content should be a candidate
    assert any("loves automation" in c.lower() for c in contents)


def test_light_skips_short_sentences(tmp_path):
    from dreaming.phases import light
    memories_dir = tmp_path / "memories"
    memories_dir.mkdir()
    _make_session(tmp_path, [{"role": "assistant", "content": "OK. Yes. This is a very long sentence that should definitely pass the minimum length threshold for candidacy."}])
    candidates = light.run(memories_dir, lookback_days=30)
    contents = [c.content for c in candidates]
    assert "OK" not in contents
    assert "Yes" not in contents


def test_light_returns_empty_for_no_sessions(tmp_path):
    from dreaming.phases import light
    memories_dir = tmp_path / "memories"
    memories_dir.mkdir()
    candidates = light.run(memories_dir, lookback_days=30)
    assert candidates == []
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_phases.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` (light.py not yet created)

- [ ] **Step 3: Create dreaming/phases/light.py**

```python
# dreaming/phases/light.py
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from dreaming.models import Candidate


def _load_sessions(sessions_dir: Path, lookback_days: int) -> List[str]:
    cutoff = datetime.now() - timedelta(days=lookback_days)
    texts: List[str] = []
    if not sessions_dir.exists():
        return texts
    for f in sessions_dir.rglob("*.json"):
        try:
            if datetime.fromtimestamp(f.stat().st_mtime) >= cutoff:
                data = json.loads(f.read_text(encoding="utf-8"))
                msgs = data.get("messages", data.get("history", []))
                for m in msgs:
                    if isinstance(m, dict) and m.get("role") == "assistant":
                        content = m.get("content", "")
                        if isinstance(content, str):
                            texts.append(content)
        except Exception:
            pass
    return texts


def _load_existing_entries(memory_file: Path) -> set:
    if not memory_file.exists():
        return set()
    text = memory_file.read_text(encoding="utf-8", errors="replace")
    entries: set = set()
    for line in text.splitlines():
        line = line.strip().lstrip("- ").lower()
        if line and not line.startswith("#"):
            entries.add(line)
    return entries


def run(memories_dir: Path, lookback_days: int) -> List[Candidate]:
    sessions_dir = memories_dir / "sessions"
    memory_file = memories_dir / "MEMORY.md"
    existing = _load_existing_entries(memory_file)
    texts = _load_sessions(sessions_dir, lookback_days)

    candidates: List[Candidate] = []
    seen: set = set()

    for text in texts:
        for sentence in re.split(r"[.!?\n]+", text):
            sentence = sentence.strip()
            if len(sentence) < 20 or len(sentence) > 500:
                continue
            normalized = sentence.lower()
            if normalized in seen or normalized in existing:
                continue
            seen.add(normalized)
            freq = min(
                sum(1 for t in texts if normalized in t.lower()) / max(len(texts), 1),
                1.0,
            )
            candidates.append(
                Candidate(
                    content=sentence,
                    source_file=str(sessions_dir),
                    frequency=freq,
                    recency=1.0,
                )
            )

    return candidates[:200]
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_phases.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add dreaming/phases/light.py tests/test_phases.py
git commit -m "feat: Light phase with dedup + tests"
```

---

### Task 5: REM and Deep phases

**Files:**
- Create: `dreaming/phases/rem.py`
- Create: `dreaming/phases/deep.py`
- Modify: `tests/test_phases.py`

- [ ] **Step 1: Add REM and Deep tests to tests/test_phases.py**

Append to the existing file:

```python
# ── REM phase ─────────────────────────────────────────────────────────────────

def test_rem_non_fatal_on_groq_failure(monkeypatch, tmp_path):
    """REM failure must not raise — candidates pass through unchanged."""
    from dreaming.phases import rem
    from dreaming.models import Candidate

    monkeypatch.setenv("GROQ_API_KEY", "fake-key-that-will-fail")
    candidates = [Candidate(content="test sentence here for rem", source_file="f")]
    result = rem.run(candidates)
    # Must return the same candidates, not raise
    assert len(result) == 1
    assert result[0].content == "test sentence here for rem"


def test_rem_enriches_candidates(monkeypatch):
    """When Groq responds, relevance + conceptual_richness must be updated."""
    from dreaming.phases import rem
    from dreaming.models import Candidate
    import json

    class FakeChoice:
        message = type("M", (), {"content": json.dumps({
            "patterns": [
                {"content": "test sentence here", "relevance": 0.9, "conceptual_richness": 0.8, "theme": "testing"}
            ]
        })})()

    class FakeResponse:
        choices = [FakeChoice()]

    class FakeChat:
        completions = type("C", (), {"create": staticmethod(lambda **kw: FakeResponse())})()

    class FakeGroq:
        def __init__(self, api_key): self.chat = FakeChat()

    monkeypatch.setattr("dreaming.phases.rem.Groq", FakeGroq)
    monkeypatch.setenv("GROQ_API_KEY", "fake")

    candidates = [Candidate(content="test sentence here", source_file="f")]
    result = rem.run(candidates)
    assert result[0].relevance == pytest.approx(0.9)
    assert result[0].conceptual_richness == pytest.approx(0.8)


# ── Deep phase ─────────────────────────────────────────────────────────────────

def test_deep_promotes_to_memory_md(tmp_path):
    from dreaming.phases import deep
    from dreaming.models import Candidate
    memories_dir = tmp_path / "memories"
    memories_dir.mkdir()

    candidates = [
        Candidate(content="Kamil loves automation tooling", source_file="f",
                  frequency=0.8, relevance=0.9, recency=1.0),
    ]
    result = deep.run(candidates, memories_dir)
    assert result["promoted"] == 1
    memory_text = (memories_dir / "MEMORY.md").read_text()
    assert "Kamil loves automation tooling" in memory_text


def test_deep_writes_dreams_diary(tmp_path):
    from dreaming.phases import deep
    from dreaming.models import Candidate
    memories_dir = tmp_path / "memories"
    memories_dir.mkdir()

    candidates = [Candidate(content="Important fact for dreaming", source_file="f",
                            relevance=0.9, recency=1.0)]
    deep.run(candidates, memories_dir)
    assert (memories_dir / "DREAMS.md").exists()


def test_deep_writes_phase_reports(tmp_path):
    from dreaming.phases import deep
    from dreaming.models import Candidate
    memories_dir = tmp_path / "memories"
    memories_dir.mkdir()

    candidates = [Candidate(content="Phase report test sentence here longer", source_file="f",
                            relevance=0.9, recency=1.0)]
    deep.run(candidates, memories_dir)
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    for phase in ["light", "rem", "deep"]:
        assert (memories_dir / "dreaming" / phase / f"{today}.md").exists()


def test_deep_skips_stale_candidates(tmp_path):
    from dreaming.phases import deep
    from dreaming.models import Candidate
    memories_dir = tmp_path / "memories"
    memories_dir.mkdir()

    candidates = [
        Candidate(content="Stale content should not be promoted here", source_file="f",
                  relevance=0.9, recency=1.0, is_stale=True),
    ]
    result = deep.run(candidates, memories_dir)
    assert result["promoted"] == 0
    assert not (memories_dir / "MEMORY.md").exists()
```

- [ ] **Step 2: Run tests — verify new tests fail**

```bash
pytest tests/test_phases.py::test_rem_non_fatal_on_groq_failure -v
```

Expected: `ImportError` (rem.py not yet created)

- [ ] **Step 3: Create dreaming/phases/rem.py**

```python
# dreaming/phases/rem.py
import json
import os
from typing import List

from groq import Groq

from dreaming.models import Candidate

_SYSTEM_PROMPT = (
    "You are analyzing conversation snippets to extract thematic patterns for long-term memory. "
    "Given a JSON list of candidate strings, identify recurring themes and conceptually rich ideas. "
    "Return JSON: {\"patterns\": [{\"content\": \"...\", \"relevance\": 0.0-1.0, "
    "\"conceptual_richness\": 0.0-1.0}]}"
)


def run(candidates: List[Candidate]) -> List[Candidate]:
    if not candidates:
        return candidates

    api_key = os.environ.get("GROQ_API_KEY", "")
    sample = [c.content for c in candidates[:50]]

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps({"candidates": sample})},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        signals = json.loads(response.choices[0].message.content)
        pattern_map: dict = {}
        for p in signals.get("patterns", []):
            content = p.get("content", "")
            if content:
                pattern_map[content.lower()] = p
        for c in candidates:
            match = pattern_map.get(c.content.lower())
            if match:
                c.relevance = float(match.get("relevance", c.relevance))
                c.conceptual_richness = float(match.get("conceptual_richness", c.conceptual_richness))
    except Exception:
        pass  # REM failure is non-fatal; candidates proceed with existing scores

    return candidates
```

- [ ] **Step 4: Create dreaming/phases/deep.py**

```python
# dreaming/phases/deep.py
from datetime import datetime
from pathlib import Path
from typing import List

from dreaming.models import Candidate

PROMOTION_THRESHOLD = 0.4
MAX_PROMOTIONS = 10


def run(candidates: List[Candidate], memories_dir: Path) -> dict:
    memory_file = memories_dir / "MEMORY.md"
    dreams_file = memories_dir / "DREAMS.md"
    today = datetime.now().strftime("%Y-%m-%d")

    qualified = [c for c in candidates if c.score() >= PROMOTION_THRESHOLD and not c.is_stale]
    qualified.sort(key=lambda c: c.score(), reverse=True)
    promoted = qualified[:MAX_PROMOTIONS]

    # Append promoted entries to MEMORY.md
    if promoted:
        existing = memory_file.read_text(encoding="utf-8") if memory_file.exists() else ""
        if not existing.endswith("\n"):
            existing += "\n"
        new_block = f"\n## Dreaming — {today}\n\n" + "\n".join(f"- {c.content}" for c in promoted) + "\n"
        memory_file.write_text(existing + new_block)

    # Append diary entry to DREAMS.md
    diary = f"\n## {today}\n\nPromoted {len(promoted)} of {len(candidates)} candidates.\n"
    for c in promoted:
        diary += f"- {c.content} (score={c.score():.2f})\n"
    if not promoted:
        diary += "No entries met the promotion threshold.\n"
    existing_dreams = dreams_file.read_text(encoding="utf-8") if dreams_file.exists() else "# Dream Diary\n"
    dreams_file.write_text(existing_dreams + diary)

    # Write per-phase reports
    summaries = {
        "light": f"# Light Phase — {today}\n\nCandidates staged: {len(candidates)}\n",
        "rem": f"# REM Phase — {today}\n\nCandidates enriched: {len(candidates)}\n",
        "deep": (
            f"# Deep Phase — {today}\n\nEvaluated: {len(candidates)} | Promoted: {len(promoted)}\n\n"
            + "\n".join(f"- score={c.score():.2f}: {c.content}" for c in promoted)
            + "\n"
        ),
    }
    for phase, content in summaries.items():
        phase_dir = memories_dir / "dreaming" / phase
        phase_dir.mkdir(parents=True, exist_ok=True)
        (phase_dir / f"{today}.md").write_text(content)

    return {"promoted": len(promoted), "evaluated": len(candidates)}
```

- [ ] **Step 5: Run all phase tests**

```bash
pytest tests/test_phases.py -v
```

Expected: `9 passed`

- [ ] **Step 6: Commit**

```bash
git add dreaming/phases/rem.py dreaming/phases/deep.py tests/test_phases.py
git commit -m "feat: REM and Deep phases with tests"
```

---

### Task 6: Runner, entrypoint, Dockerfile

**Files:**
- Create: `dreaming/runner.py`
- Create: `entrypoint.sh`
- Create: `Dockerfile`
- Modify: `tests/test_lock.py` (add runner lock test — already written in Task 3 Step 7)

- [ ] **Step 1: Create dreaming/runner.py**

```python
# dreaming/runner.py
import json
import logging
import os
from pathlib import Path

from dreaming import lock
from dreaming.phases import deep, light, rem

logger = logging.getLogger(__name__)


def run_once() -> None:
    if os.environ.get("DREAMING_ENABLED", "true").lower() != "true":
        logger.info("Dreaming disabled. Set DREAMING_ENABLED=true to enable.")
        return

    memories_dir = Path(os.environ.get("HERMES_MEMORIES_DIR", "/opt/data/memories"))
    lock_path = memories_dir / ".dreams" / "lock"
    lookback_days = int(os.environ.get("DREAMING_LOOKBACK_DAYS", "7"))

    try:
        lock.acquire(lock_path)
    except lock.LockError as exc:
        logger.warning("Skipping dream run: %s", exc)
        return

    try:
        logger.info("=== Dreaming started ===")

        logger.info("Light phase starting")
        candidates = light.run(memories_dir, lookback_days)
        staging = memories_dir / ".dreams" / "staging.json"
        staging.parent.mkdir(parents=True, exist_ok=True)
        staging.write_text(
            json.dumps([{"content": c.content, "source": c.source_file} for c in candidates])
        )
        logger.info("Light phase: %d candidates staged", len(candidates))

        logger.info("REM phase starting")
        candidates = rem.run(candidates)
        logger.info("REM phase complete")

        logger.info("Deep phase starting")
        result = deep.run(candidates, memories_dir)
        logger.info("Deep phase: promoted %d/%d", result["promoted"], result["evaluated"])

        if staging.exists():
            staging.unlink()

        logger.info("=== Dreaming complete ===")

    except Exception:
        logger.exception("Dream run failed")
    finally:
        lock.release(lock_path)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    run_once()
```

- [ ] **Step 2: Run the lock runner test (written in Task 3)**

```bash
pytest tests/test_lock.py::test_run_skipped_when_lock_exists -v
```

Expected: `1 passed`

- [ ] **Step 3: Create entrypoint.sh**

```bash
#!/bin/sh
set -e

CRON="${DREAMING_CRON:-0 3 * * *}"

# Write crontab for root
echo "${CRON} cd /app && python -m dreaming.runner >> /var/log/dreaming.log 2>&1" > /etc/crontabs/root
# cron requires a trailing newline
printf '\n' >> /etc/crontabs/root

echo "Dreaming sidecar starting. Cron: ${CRON}"
exec crond -f -l 2
```

- [ ] **Step 4: Create Dockerfile**

```dockerfile
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends dcron \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY dreaming/ ./dreaming/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
```

- [ ] **Step 5: Build image locally to verify (optional — requires Docker)**

```bash
docker build -t hermes-dreaming:local .
```

Expected: successful build, no errors

- [ ] **Step 6: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all tests pass

- [ ] **Step 7: Commit and push**

```bash
git add dreaming/runner.py entrypoint.sh Dockerfile
chmod +x entrypoint.sh
git add .
git commit -m "feat: runner, entrypoint, Dockerfile — dreaming sidecar complete"
git push origin main
```

---

## Phase 3 — hermes-webui-fork

**Prerequisite:** Fork `ghcr.io/nesquena/hermes-webui` source to `kamilandrzejrybacki-inc/hermes-webui-fork`. The upstream source is inside the running container at `/app` on lw-pi. Clone it with:

```bash
ssh kamil@192.168.0.109 "docker cp hermes-webui:/app /tmp/hermes-webui-src"
scp -r kamil@192.168.0.109:/tmp/hermes-webui-src ./hermes-webui-fork
cd hermes-webui-fork
git init && git add . && git commit -m "chore: initial fork from upstream"
gh repo create kamilandrzejrybacki-inc/hermes-webui-fork --private --source=. --push
```

### Task 7: Federation adapters + unit tests

**Repo:** `kamilandrzejrybacki-inc/hermes-webui-fork`

**Files:**
- Create: `api/memory_federation.py`
- Create: `tests/test_memory_federation.py`

- [ ] **Step 1: Write failing unit tests**

```python
# tests/test_memory_federation.py
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ── Contract helpers ───────────────────────────────────────────────────────────

def _assert_source_shape(source):
    assert "name" in source
    assert source["status"] in ("ok", "degraded", "error")
    assert "last_updated" in source
    assert "error" in source
    assert "items" in source
    for item in source["items"]:
        for field in ("id", "title", "content", "source", "tags", "metadata"):
            assert field in item


# ── Local adapter ─────────────────────────────────────────────────────────────

def test_local_adapter_returns_memory_and_user(tmp_path):
    from api.memory_federation import _local_adapter
    mem = tmp_path / "MEMORY.md"
    user = tmp_path / "USER.md"
    mem.write_text("# Notes\n- test note")
    user.write_text("# User\n- kamil")
    result = _local_adapter(tmp_path)
    _assert_source_shape(result)
    assert result["name"] == "local"
    assert result["status"] == "ok"
    ids = [i["id"] for i in result["items"]]
    assert "local:memory" in ids
    assert "local:user" in ids


def test_local_adapter_ok_with_missing_files(tmp_path):
    from api.memory_federation import _local_adapter
    result = _local_adapter(tmp_path)
    assert result["status"] == "ok"
    assert result["items"] == []


# ── Dreaming adapter ──────────────────────────────────────────────────────────

def test_dreaming_adapter_reads_dreams_md(tmp_path):
    from api.memory_federation import _dreaming_adapter
    (tmp_path / "DREAMS.md").write_text("# Dream Diary\n\n## 2026-04-13\nPromoted 1 entry.")
    result = _dreaming_adapter(tmp_path)
    _assert_source_shape(result)
    assert result["status"] == "ok"
    assert any(i["id"] == "dreaming:diary" for i in result["items"])


def test_dreaming_adapter_ok_with_no_files(tmp_path):
    from api.memory_federation import _dreaming_adapter
    result = _dreaming_adapter(tmp_path)
    assert result["status"] == "ok"
    assert result["items"] == []


def test_dreaming_adapter_includes_phase_reports(tmp_path):
    from api.memory_federation import _dreaming_adapter
    deep_dir = tmp_path / "dreaming" / "deep"
    deep_dir.mkdir(parents=True)
    (deep_dir / "2026-04-13.md").write_text("# Deep — 2026-04-13\nPromoted 2.")
    result = _dreaming_adapter(tmp_path)
    assert any("deep:2026-04-13" in i["id"] for i in result["items"])


# ── Supermemory adapter ───────────────────────────────────────────────────────

def test_supermemory_adapter_returns_error_on_connection_refused():
    from api.memory_federation import _supermemory_adapter
    result = _supermemory_adapter("http://127.0.0.1:19999")  # nothing listening
    assert result["status"] == "error"
    assert result["error"]["code"] in ("timeout", "adapter_error")
    assert result["items"] == []


def test_supermemory_adapter_retries_and_succeeds(monkeypatch):
    """Fail twice then succeed — final status must be ok."""
    from api import memory_federation

    call_count = {"n": 0}
    memories_payload = json.dumps({"memories": [
        {"id": "m1", "title": "Test memory", "content": "test content", "tags": []}
    ]}).encode()

    class FakeResp:
        status = 200
        def read(self): return memories_payload

    class FakeConn:
        def __init__(self, host, port, timeout): pass
        def request(self, method, path):
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise ConnectionRefusedError("simulated failure")
        def getresponse(self): return FakeResp()

    monkeypatch.setattr(memory_federation, "HTTPConnection", FakeConn)
    monkeypatch.setattr(memory_federation, "time", MagicMock(sleep=lambda s: None))

    result = memory_federation._supermemory_adapter("http://hermes-supermemory:3100")
    assert result["status"] == "ok"
    assert len(result["items"]) == 1


# ── Orchestrator ──────────────────────────────────────────────────────────────

def test_orchestrator_returns_all_sources(tmp_path, monkeypatch):
    from api.memory_federation import get_federated_memory
    (tmp_path / "MEMORY.md").write_text("# Notes")

    # Patch supermemory adapter to return ok without network
    import api.memory_federation as mf
    monkeypatch.setattr(mf, "_supermemory_adapter",
                        lambda url: mf._source("supermemory", "ok", None, []))

    result = get_federated_memory(tmp_path, "http://fake:3100")
    names = [s["name"] for s in result["sources"]]
    assert "local" in names
    assert "supermemory" in names
    assert "dreaming" in names


def test_orchestrator_partial_failure_does_not_block(tmp_path, monkeypatch):
    from api.memory_federation import get_federated_memory
    import api.memory_federation as mf

    def _raise(url): raise RuntimeError("boom")
    monkeypatch.setattr(mf, "_supermemory_adapter", _raise)

    result = get_federated_memory(tmp_path, "http://fake:3100")
    sm = next(s for s in result["sources"] if s["name"] == "supermemory")
    assert sm["status"] == "error"
    local = next(s for s in result["sources"] if s["name"] == "local")
    assert local["status"] == "ok"
```

- [ ] **Step 2: Run failing tests**

```bash
pytest tests/test_memory_federation.py -v 2>&1 | head -30
```

Expected: `ImportError` for `api.memory_federation`

- [ ] **Step 3: Create api/memory_federation.py**

```python
# api/memory_federation.py
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from http.client import HTTPConnection
from pathlib import Path
from typing import Optional
import urllib.parse

logger = logging.getLogger(__name__)

SOURCE_TIMEOUT = 5.0
_SUPERMEMORY_MAX_RETRIES = 2


# ── DTO helpers ────────────────────────────────────────────────────────────────

def _item(source: str, slug: str, title: str, content: str,
          updated_at: Optional[float] = None, tags: Optional[list] = None) -> dict:
    return {
        "id": f"{source}:{slug}",
        "title": title,
        "content": content,
        "created_at": None,
        "updated_at": updated_at,
        "tags": tags or [],
        "source": source,
        "metadata": {},
    }


def _source(name: str, status: str, last_updated: Optional[float],
            items: list, error: Optional[dict] = None) -> dict:
    return {
        "name": name,
        "status": status,
        "last_updated": last_updated,
        "error": error,
        "items": items,
    }


# ── Local adapter ──────────────────────────────────────────────────────────────

def _local_adapter(memories_dir: Path) -> dict:
    items = []
    last_updated = None
    for slug, path in [("memory", memories_dir / "MEMORY.md"),
                       ("user", memories_dir / "USER.md")]:
        if path.exists():
            mtime = path.stat().st_mtime
            content = path.read_text(encoding="utf-8", errors="replace")
            items.append(_item("local", slug, path.name, content, updated_at=mtime))
            if last_updated is None or mtime > last_updated:
                last_updated = mtime
    return _source("local", "ok", last_updated, items)


# ── Supermemory adapter ────────────────────────────────────────────────────────

def _supermemory_adapter(base_url: str) -> dict:
    parsed = urllib.parse.urlparse(base_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 3100
    last_exc: Exception = RuntimeError("no attempt made")

    for attempt in range(_SUPERMEMORY_MAX_RETRIES + 1):
        try:
            conn = HTTPConnection(host, port, timeout=SOURCE_TIMEOUT)
            conn.request("GET", "/api/memories")
            resp = conn.getresponse()
            if resp.status != 200:
                raise RuntimeError(f"HTTP {resp.status}")
            data = json.loads(resp.read())
            items = []
            ts: Optional[float] = None
            for entry in data.get("memories", []):
                raw_ts = entry.get("updatedAt")
                ts_val: Optional[float] = None
                if raw_ts:
                    try:
                        from datetime import datetime, timezone
                        ts_val = datetime.fromisoformat(
                            raw_ts.replace("Z", "+00:00")
                        ).timestamp()
                    except Exception:
                        pass
                if ts is None or (ts_val and ts_val > ts):
                    ts = ts_val
                items.append(_item(
                    "supermemory",
                    entry.get("id", str(id(entry))),
                    entry.get("title") or entry.get("content", "")[:60],
                    entry.get("content", ""),
                    updated_at=ts_val,
                    tags=entry.get("tags", []),
                ))
            return _source("supermemory", "ok", ts, items)
        except Exception as exc:
            last_exc = exc
            if attempt < _SUPERMEMORY_MAX_RETRIES:
                time.sleep(2 ** attempt)

    code = "timeout" if isinstance(last_exc, (TimeoutError,)) else "adapter_error"
    return _source("supermemory", "error", None, [],
                   error={"code": code, "message": str(last_exc)})


# ── Dreaming adapter ───────────────────────────────────────────────────────────

def _dreaming_adapter(memories_dir: Path) -> dict:
    items = []
    last_updated: Optional[float] = None
    dreams_file = memories_dir / "DREAMS.md"
    if dreams_file.exists():
        mtime = dreams_file.stat().st_mtime
        content = dreams_file.read_text(encoding="utf-8", errors="replace")
        items.append(_item("dreaming", "diary", "DREAMS.md", content, updated_at=mtime))
        last_updated = mtime
    dreaming_dir = memories_dir / "dreaming"
    if dreaming_dir.exists():
        for phase in ["light", "rem", "deep"]:
            phase_dir = dreaming_dir / phase
            if not phase_dir.exists():
                continue
            for report in sorted(phase_dir.glob("*.md"), reverse=True)[:7]:
                mtime = report.stat().st_mtime
                content = report.read_text(encoding="utf-8", errors="replace")
                items.append(_item(
                    "dreaming",
                    f"{phase}:{report.stem}",
                    f"{phase.capitalize()} \u2014 {report.stem}",
                    content,
                    updated_at=mtime,
                ))
                if last_updated is None or mtime > last_updated:
                    last_updated = mtime
    return _source("dreaming", "ok", last_updated, items)


# ── Orchestrator ───────────────────────────────────────────────────────────────

def get_federated_memory(memories_dir: Path,
                         supermemory_url: Optional[str]) -> dict:
    adapters: dict = {
        "local": lambda: _local_adapter(memories_dir),
        "dreaming": lambda: _dreaming_adapter(memories_dir),
    }
    if supermemory_url:
        adapters["supermemory"] = lambda: _supermemory_adapter(supermemory_url)

    results: dict = {}
    with ThreadPoolExecutor(max_workers=len(adapters)) as pool:
        future_to_name = {pool.submit(fn): name for name, fn in adapters.items()}
        for future, name in future_to_name.items():
            t0 = time.monotonic()
            try:
                results[name] = future.result(timeout=SOURCE_TIMEOUT)
            except FuturesTimeout:
                results[name] = _source(name, "error", None, [],
                                        error={"code": "timeout", "message": "adapter timed out"})
            except Exception as exc:
                results[name] = _source(name, "error", None, [],
                                        error={"code": "adapter_error", "message": str(exc)})
            finally:
                latency = round((time.monotonic() - t0) * 1000)
                logger.info(json.dumps({
                    "event": "memory_federation",
                    "source": name,
                    "status": results[name]["status"],
                    "latency_ms": latency,
                    "error_code": (results[name].get("error") or {}).get("code"),
                }))

    sources = [
        results[name]
        for name in ["local", "supermemory", "dreaming"]
        if name in results
    ]
    return {"sources": sources}
```

- [ ] **Step 4: Run unit tests**

```bash
pytest tests/test_memory_federation.py -v
```

Expected: all tests pass (the retry test patches `HTTPConnection` and `time` — if monkeypatch target path mismatches, adjust to match the import in `memory_federation.py`)

- [ ] **Step 5: Commit**

```bash
git add api/memory_federation.py tests/test_memory_federation.py
git commit -m "feat: memory federation adapters + unit tests"
```

---

### Task 8: Federation route + integration test

**Files:**
- Modify: `api/routes.py`
- Create: `tests/test_federated_endpoint.py`

- [ ] **Step 1: Write failing integration test**

```python
# tests/test_federated_endpoint.py
"""Integration test for GET /api/memory/federated.
Uses the existing conftest.py test server setup (isolated HERMES_HOME).
"""
import json
import os
import pytest


def test_federated_returns_200(client):
    resp = client.get("/api/memory/federated")
    assert resp.status_code == 200


def test_federated_response_has_sources(client):
    resp = client.get("/api/memory/federated")
    data = json.loads(resp.data)
    assert "sources" in data
    assert isinstance(data["sources"], list)


def test_federated_local_source_always_present(client):
    resp = client.get("/api/memory/federated")
    data = json.loads(resp.data)
    names = [s["name"] for s in data["sources"]]
    assert "local" in names


def test_federated_never_500_when_supermemory_down(client, monkeypatch):
    """Even with a broken Supermemory URL configured, endpoint returns 200."""
    import api.memory_federation as mf
    monkeypatch.setenv("MEMORY_SOURCE_SUPERMEMORY_ENABLED", "true")
    monkeypatch.setenv("SUPERMEMORY_BASE_URL", "http://127.0.0.1:19999")
    resp = client.get("/api/memory/federated")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    sm = next((s for s in data["sources"] if s["name"] == "supermemory"), None)
    assert sm is not None
    assert sm["status"] == "error"
    # Local must still be ok
    local = next(s for s in data["sources"] if s["name"] == "local")
    assert local["status"] == "ok"
```

- [ ] **Step 2: Run — expect FAIL (route not yet added)**

```bash
pytest tests/test_federated_endpoint.py::test_federated_returns_200 -v
```

Expected: `FAILED` with 404

- [ ] **Step 3: Add route to api/routes.py**

Find the block after the existing memory read route (around line 344-346):

```python
    if parsed.path == '/api/memory':
        return _handle_memory_read(handler)
```

Add immediately after it:

```python
    if parsed.path == '/api/memory/federated':
        return _handle_memory_federated(handler)
```

Then add the handler function near `_handle_memory_read` (search for `def _handle_memory_read`):

```python
def _handle_memory_federated(handler):
    import os
    from api.memory_federation import get_federated_memory
    try:
        mem_dir = get_active_hermes_home() / 'memories'
    except Exception:
        from pathlib import Path
        mem_dir = Path.home() / '.hermes' / 'memories'
    supermemory_url = None
    if os.environ.get('MEMORY_SOURCE_SUPERMEMORY_ENABLED', '').lower() == 'true':
        supermemory_url = os.environ.get('SUPERMEMORY_BASE_URL')
    result = get_federated_memory(mem_dir, supermemory_url)
    return j(handler, result)
```

- [ ] **Step 4: Run integration tests**

```bash
pytest tests/test_federated_endpoint.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add api/routes.py tests/test_federated_endpoint.py
git commit -m "feat: add GET /api/memory/federated route + integration tests"
```

---

### Task 9: Memory tab UI update

**Files:**
- Modify: `static/panels.js`

The current `loadMemory` function is at line 874. It fetches `/api/memory` and renders two `memory-section` divs. We replace its body to use the federated endpoint while keeping the edit form working via `_memoryData` (which still holds the local source data for the write path).

- [ ] **Step 1: Replace the `loadMemory` function body in static/panels.js**

Find the function (currently lines 874–898):

```javascript
async function loadMemory(force) {
  const panel = $('memoryPanel');
  try {
    const data = await api('/api/memory');
    _memoryData = data;  // cache for edit form
    ...
  } catch(e) { ... }
}
```

Replace the entire function with:

```javascript
async function loadMemory(force) {
  const panel = $('memoryPanel');
  if (!panel) return;

  // Keep legacy _memoryData populated for the edit form write path
  api('/api/memory').then(d => { _memoryData = d; }).catch(() => {});

  const chip = status => {
    const color = status === 'ok' ? 'var(--green,#4caf50)'
                : status === 'degraded' ? 'var(--yellow,#ff9800)'
                : 'var(--accent,#e94560)';
    return `<span style="color:${color};font-size:10px;margin-right:4px">&#9679;</span>`;
  };
  const fmtTime = ts => ts ? new Date(ts * 1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}) + ' ' + new Date(ts * 1000).toLocaleDateString() : '';

  const renderSource = src => {
    const header = `<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
      <span style="font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.05em">${chip(src.status)}${esc(src.name)}</span>
      <span style="font-size:10px;color:var(--muted)">${fmtTime(src.last_updated)}</span>
    </div>`;
    if (src.status === 'error') {
      return `<div class="memory-section" style="border:1px solid rgba(233,69,96,.3);border-radius:8px;padding:10px;margin-bottom:10px">
        ${header}
        <div style="color:var(--accent);font-size:12px">${esc((src.error||{}).message||'source unavailable')}</div>
      </div>`;
    }
    if (!src.items.length) {
      return `<div class="memory-section" style="border:1px solid var(--border2);border-radius:8px;padding:10px;margin-bottom:10px">
        ${header}<div class="memory-empty">No entries.</div>
      </div>`;
    }
    const items = src.items.map(item =>
      `<div class="memory-section" style="margin-bottom:6px">
        <div class="memory-section-title" style="font-size:11px">${esc(item.title)}</div>
        <div class="memory-content preview-md" style="max-height:200px;overflow-y:auto">${renderMd(item.content)}</div>
      </div>`
    ).join('');
    return `<div style="border:1px solid var(--border2);border-radius:8px;padding:10px;margin-bottom:10px">
      ${header}${items}
    </div>`;
  };

  panel.innerHTML = '<div style="color:var(--muted);font-size:12px;padding:8px 0">Loading\u2026</div>';
  try {
    const data = await api('/api/memory/federated');
    const refreshBtn = `<div style="text-align:right;margin-bottom:8px">
      <button onclick="loadMemory(true)" style="padding:4px 10px;border-radius:6px;border:1px solid var(--border2);background:rgba(255,255,255,.05);color:var(--muted);cursor:pointer;font-size:11px">\u21bb Refresh</button>
    </div>`;
    panel.innerHTML = refreshBtn + (data.sources || []).map(renderSource).join('');
  } catch(e) {
    panel.innerHTML = `<div style="color:var(--accent);font-size:12px">Error: ${esc(e.message)}</div>`;
  }
}
```

- [ ] **Step 2: Start the dev server and verify the Memory tab**

```bash
cd /opt/hermes   # or your local dev clone
python server.py
# Open http://localhost:8788 → click Memory tab
```

Verify:
- Three section cards render (Local, Dreaming — Supermemory only if env is set)
- Local shows MEMORY.md and USER.md content
- Refresh button works
- Edit pencil still opens the edit form (write path unchanged)

- [ ] **Step 3: Commit**

```bash
git add static/panels.js
git commit -m "feat: federated Memory tab with source section cards"
```

---

### Task 10: Playwright E2E tests

**Files:**
- Create: `playwright.config.ts`
- Create: `tests/e2e/memory/federation.spec.ts`
- Modify: root-level package.json (add playwright)

- [ ] **Step 1: Install Playwright**

```bash
npm install -D @playwright/test
npx playwright install chromium
```

- [ ] **Step 2: Create playwright.config.ts**

```typescript
// playwright.config.ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  retries: 0,
  reporter: [['html', { outputFolder: 'playwright-report' }]],
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:8788',
    screenshot: 'only-on-failure',
    actionTimeout: 10000,
    navigationTimeout: 30000,
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
});
```

- [ ] **Step 3: Create tests/e2e/memory/federation.spec.ts**

```typescript
// tests/e2e/memory/federation.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Memory tab — federated sources', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // Click the Memory nav tab
    await page.locator('.nav-tab[data-panel="memory"]').click();
    await page.locator('#memoryPanel').waitFor({ state: 'visible' });
  });

  test('all sources healthy — Local section card renders', async ({ page }) => {
    // Wait for federated load to complete (loading… disappears)
    await expect(page.locator('#memoryPanel')).not.toContainText('Loading…', { timeout: 8000 });
    await expect(page.locator('#memoryPanel')).toContainText('local', { ignoreCase: true });
    await page.screenshot({ path: 'playwright-report/memory-all-healthy.png' });
  });

  test('refresh button triggers reload', async ({ page }) => {
    await expect(page.locator('#memoryPanel')).not.toContainText('Loading…', { timeout: 8000 });
    const refreshBtn = page.locator('#memoryPanel button', { hasText: /refresh/i });
    await expect(refreshBtn).toBeVisible();
    await refreshBtn.click();
    // After click, loading state appears briefly — panel still renders without error
    await expect(page.locator('#memoryPanel')).not.toContainText('Error:', { timeout: 8000 });
  });

  test('dreaming disabled — no Dreaming section when DREAMS.md absent', async ({ page }) => {
    // If DREAMS.md does not exist and dreaming dir is empty, Dreaming card shows "No entries."
    await expect(page.locator('#memoryPanel')).not.toContainText('Loading…', { timeout: 8000 });
    // Should not show an error state for dreaming
    const dreamingSection = page.locator('#memoryPanel', { hasText: /dreaming/i });
    if (await dreamingSection.count() > 0) {
      await expect(dreamingSection).not.toContainText('Error:');
    }
  });
});
```

- [ ] **Step 4: Run E2E tests (requires running server)**

In one terminal: `python server.py`

In another:

```bash
npx playwright test tests/e2e/memory/federation.spec.ts
```

Expected: `3 passed` (or adjust based on actual server state)

- [ ] **Step 5: Commit and push**

```bash
git add playwright.config.ts tests/e2e/ package.json package-lock.json
git commit -m "test: Playwright E2E for federated Memory tab"
git push origin main
```

---

## Phase 4 — Ansible Deployment

### Task 11: Inventory, group_vars, new templates

**Repo:** `kamilandrzejrybacki-inc/ansible`
**Working dir:** `infrastructure/hermes-pi/`

**Files:**
- Modify: `inventory/hosts.ini`
- Modify: `group_vars/all.yml`
- Create: `templates/daemon.json.j2`
- Create: `templates/argocd-docker-builders-app.yaml.j2`
- Create: `templates/kaniko-job.yaml.j2`

- [ ] **Step 1: Add lw-c1 to inventory/hosts.ini**

Current file:

```ini
[hermes]
lw-pi ansible_host=192.168.0.109 ansible_user=kamil

[homelab]
lw-main ansible_host=192.168.0.105 ansible_user=kamil-rybacki
```

Add `[builders]` group:

```ini
[hermes]
lw-pi ansible_host=192.168.0.109 ansible_user=kamil

[homelab]
lw-main ansible_host=192.168.0.105 ansible_user=kamil-rybacki

[builders]
lw-c1 ansible_host=192.168.0.107 ansible_user=kamil ansible_python_interpreter=/usr/bin/python3
```

- [ ] **Step 2: Add new vars to group_vars/all.yml**

Append to the existing file:

```yaml
# ── Memory enhancement ──────────────────────────────────────────────────────
hermes_registry: "192.168.0.107:30500"
hermes_webui_fork_tag: "latest"
hermes_dreaming_tag: "latest"
hermes_supermemory_tag: "latest"
hermes_webui_fork_repo: "https://github.com/kamilandrzejrybacki-inc/hermes-webui-fork.git"
hermes_dreaming_repo: "https://github.com/kamilandrzejrybacki-inc/hermes-dreaming.git"
hermes_supermemory_repo: "https://github.com/kamilandrzejrybacki-inc/hermes-supermemory.git"

memory_source_supermemory_enabled: true
memory_source_dreaming_enabled: true
dreaming_cron: "0 3 * * *"
dreaming_lookback_days: 7
```

- [ ] **Step 3: Create templates/daemon.json.j2**

```json
{
  "insecure-registries": ["{{ hermes_registry }}"]
}
```

- [ ] **Step 4: Create templates/argocd-docker-builders-app.yaml.j2**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: docker-builders
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/kamilandrzejrybacki-inc/helm.git
    targetRevision: main
    path: charts/docker-builders
  destination:
    server: https://kubernetes.default.svc
    namespace: docker-builders
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
```

- [ ] **Step 5: Create templates/kaniko-job.yaml.j2**

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: "build-{{ item.name }}-{{ ansible_date_time.epoch }}"
  namespace: docker-builders
spec:
  ttlSecondsAfterFinished: 3600
  backoffLimit: 1
  template:
    spec:
      serviceAccountName: kaniko-builder
      restartPolicy: Never
      initContainers:
      - name: git-clone
        image: alpine/git:latest
        command: ["git", "clone", "{{ item.repo }}", "/workspace"]
        volumeMounts:
        - name: workspace
          mountPath: /workspace
      containers:
      - name: kaniko
        image: gcr.io/kaniko-project/executor:latest
        args:
        - "--context=/workspace"
        - "--dockerfile=/workspace/{{ item.dockerfile | default('Dockerfile') }}"
        - "--destination={{ hermes_registry }}/{{ item.name }}:{{ item.tag | default('latest') }}"
        - "--customPlatform=linux/arm64"
        - "--skip-tls-verify"
        - "--log-format=text"
        volumeMounts:
        - name: workspace
          mountPath: /workspace
      volumes:
      - name: workspace
        emptyDir: {}
```

- [ ] **Step 6: Commit**

```bash
git add infrastructure/hermes-pi/
git commit -m "feat(hermes-pi): inventory, group_vars, daemon.json + Kaniko templates"
```

---

### Task 12: setup.yml — Play 1 & 2 (bootstrap + build)

**Files:**
- Modify: `infrastructure/hermes-pi/setup.yml`

- [ ] **Step 1: Add Play 1 (bootstrap docker-builders) to the top of setup.yml**

Insert before the existing `- name: Deploy Hermes to Pi` play:

```yaml
# =============================================================================
# Play 1: Bootstrap docker-builders on lw-c1
# =============================================================================
- name: Bootstrap docker-builders ArgoCD application
  hosts: builders
  gather_facts: false

  tasks:
    - name: Deploy ArgoCD docker-builders Application manifest
      ansible.builtin.template:
        src: argocd-docker-builders-app.yaml.j2
        dest: /tmp/argocd-docker-builders-app.yaml
        mode: "0644"

    - name: Apply ArgoCD Application
      ansible.builtin.command:
        cmd: kubectl apply -f /tmp/argocd-docker-builders-app.yaml
      environment:
        KUBECONFIG: /home/kamil/.kube/config

    - name: Wait for registry Deployment to be available
      ansible.builtin.command:
        cmd: >
          kubectl wait deployment/registry
          -n docker-builders
          --for=condition=available
          --timeout=120s
      environment:
        KUBECONFIG: /home/kamil/.kube/config

# =============================================================================
# Play 2: Build arm64 images via Kaniko on lw-c1
# =============================================================================
- name: Build Hermes custom images
  hosts: builders
  gather_facts: true

  tasks:
    - name: Create Kaniko build Jobs
      ansible.builtin.template:
        src: kaniko-job.yaml.j2
        dest: "/tmp/kaniko-job-{{ item.name }}.yaml"
        mode: "0644"
      loop:
        - name: hermes-webui-fork
          repo: "{{ hermes_webui_fork_repo }}"
          tag: "{{ hermes_webui_fork_tag }}"
        - name: hermes-dreaming
          repo: "{{ hermes_dreaming_repo }}"
          tag: "{{ hermes_dreaming_tag }}"
        - name: hermes-supermemory
          repo: "{{ hermes_supermemory_repo }}"
          tag: "{{ hermes_supermemory_tag }}"

    - name: Apply Kaniko Jobs
      ansible.builtin.command:
        cmd: "kubectl apply -f /tmp/kaniko-job-{{ item.name }}.yaml"
      loop:
        - name: hermes-webui-fork
        - name: hermes-dreaming
        - name: hermes-supermemory
      environment:
        KUBECONFIG: /home/kamil/.kube/config

    - name: Wait for all Kaniko Jobs to complete
      ansible.builtin.command:
        cmd: >
          kubectl wait jobs
          -l app.kubernetes.io/managed-by=kaniko-builder
          -n docker-builders
          --for=condition=complete
          --timeout=1200s
      environment:
        KUBECONFIG: /home/kamil/.kube/config
      register: kaniko_wait
      failed_when: kaniko_wait.rc != 0
```

- [ ] **Step 2: Commit**

```bash
git add infrastructure/hermes-pi/setup.yml
git commit -m "feat(hermes-pi): Play 1 (docker-builders bootstrap) + Play 2 (Kaniko builds)"
```

---

### Task 13: setup.yml — Play 3 (lw-pi deploy) + docker-compose + env

**Files:**
- Modify: `infrastructure/hermes-pi/setup.yml` (extend existing Play 3)
- Modify: `infrastructure/hermes-pi/templates/docker-compose.yml.j2`
- Modify: `infrastructure/hermes-pi/templates/env.j2`

- [ ] **Step 1: Extend Play 3 pre_tasks in setup.yml — add insecure registry config**

In the existing `Deploy Hermes to Pi` play, add after the existing pre_tasks and before the `# ── Create directory structure ──` comment:

```yaml
    - name: Configure Docker insecure registry
      ansible.builtin.template:
        src: daemon.json.j2
        dest: /etc/docker/daemon.json
        owner: root
        group: root
        mode: "0644"
      notify: Restart Docker

  handlers:
    - name: Restart Docker
      ansible.builtin.systemd:
        name: docker
        state: restarted
```

Also add these tasks inside Play 3 tasks (after the SSH key tasks, before "Deploy templates"):

```yaml
    - name: Create Dreaming subdirectories
      ansible.builtin.file:
        path: "{{ item }}"
        state: directory
        owner: "{{ ansible_user }}"
        group: "{{ ansible_user }}"
        mode: "0755"
      loop:
        - "{{ hermes_install_dir }}/data/memories/dreaming/light"
        - "{{ hermes_install_dir }}/data/memories/dreaming/rem"
        - "{{ hermes_install_dir }}/data/memories/dreaming/deep"
        - "{{ hermes_install_dir }}/data/memories/.dreams"
```

- [ ] **Step 2: Update templates/docker-compose.yml.j2**

Replace the `webui:` service image line:

```yaml
    image: ghcr.io/nesquena/hermes-webui:{{ hermes_webui_tag }}
```

with:

```yaml
    image: {{ hermes_registry }}/hermes-webui-fork:{{ hermes_webui_fork_tag }}
```

Add two new services before the `portkey-proxy:` service:

```yaml
  hermes-dreaming:
    image: {{ hermes_registry }}/hermes-dreaming:{{ hermes_dreaming_tag }}
    container_name: hermes-dreaming
    restart: unless-stopped
    depends_on:
      - redis
    volumes:
      - ./data:/opt/data
    environment:
      - HERMES_MEMORIES_DIR=/opt/data/memories
      - DREAMING_ENABLED={{ memory_source_dreaming_enabled | lower }}
      - DREAMING_LOOKBACK_DAYS={{ dreaming_lookback_days }}
      - DREAMING_CRON={{ dreaming_cron }}
    env_file:
      - .env
    networks:
      - hermes

  hermes-supermemory:
    image: {{ hermes_registry }}/hermes-supermemory:{{ hermes_supermemory_tag }}
    container_name: hermes-supermemory
    restart: unless-stopped
    volumes:
      - supermemory-data:/data
    environment:
      - PORT=3100
    env_file:
      - .env
    networks:
      - hermes
```

Add `supermemory-data:` to the `volumes:` section:

```yaml
volumes:
  redis-data:
  supermemory-data:
```

- [ ] **Step 3: Update templates/env.j2**

Append to the existing file:

```
SUPERMEMORY_API_KEY={{ supermemory_api_key }}
SUPERMEMORY_BASE_URL=http://hermes-supermemory:3100
GROQ_API_KEY={{ groq_api_key }}
DREAMING_ENABLED={{ memory_source_dreaming_enabled | lower }}
MEMORY_SOURCE_SUPERMEMORY_ENABLED={{ memory_source_supermemory_enabled | lower }}
MEMORY_SOURCE_DREAMING_ENABLED={{ memory_source_dreaming_enabled | lower }}
```

- [ ] **Step 4: Validate the playbook syntax**

```bash
ansible-playbook -i inventory/hosts.ini setup.yml --syntax-check \
  -e telegram_bot_token=x \
  -e openai_access_token=x \
  -e openai_refresh_token=x \
  -e groq_api_key=x \
  -e n8n_mcp_token=x \
  -e github_pat=x \
  -e supermemory_api_key=x
```

Expected: `playbook: infrastructure/hermes-pi/setup.yml` with no errors

- [ ] **Step 5: Commit and push**

```bash
git add infrastructure/hermes-pi/
git commit -m "feat(hermes-pi): Play 3 insecure registry, dreaming dirs, new services in compose + env"
git push origin main
```

---

### Task 14: Full deploy + smoke test

- [ ] **Step 1: Ship with remote sources disabled first (rollout step 1)**

```bash
ansible-playbook -i inventory/hosts.ini setup.yml \
  -e telegram_bot_token=$TELEGRAM_BOT_TOKEN \
  -e openai_access_token=$OPENAI_ACCESS_TOKEN \
  -e openai_refresh_token=$OPENAI_REFRESH_TOKEN \
  -e groq_api_key=$GROQ_API_KEY \
  -e n8n_mcp_token=$N8N_MCP_TOKEN \
  -e github_pat=$GITHUB_PAT \
  -e supermemory_api_key=$SUPERMEMORY_API_KEY \
  -e memory_source_supermemory_enabled=false \
  -e memory_source_dreaming_enabled=false
```

Expected: all tasks green, no failed

- [ ] **Step 2: Verify registry is reachable from lw-pi**

```bash
ssh kamil@192.168.0.109 "curl -s http://192.168.0.107:30500/v2/ | cat"
```

Expected: `{}`

- [ ] **Step 3: Verify hermes-webui-fork container is running**

```bash
ssh kamil@192.168.0.109 "docker ps --filter name=hermes-webui --format '{{.Image}}'"
```

Expected: `192.168.0.107:30500/hermes-webui-fork:latest`

- [ ] **Step 4: Verify /api/memory/federated returns 200**

```bash
ssh kamil@192.168.0.109 "curl -s http://localhost:8788/api/memory/federated | python3 -m json.tool | head -20"
```

Expected: JSON with `sources` array containing at least `local` source with `status: "ok"`

- [ ] **Step 5: Enable Dreaming**

```bash
ansible-playbook -i inventory/hosts.ini setup.yml \
  ... (same flags) ... \
  -e memory_source_dreaming_enabled=true \
  -e memory_source_supermemory_enabled=false
```

- [ ] **Step 6: Verify hermes-dreaming is running**

```bash
ssh kamil@192.168.0.109 "docker ps --filter name=hermes-dreaming --format '{{.Status}}'"
```

Expected: `Up X seconds` or `Up X minutes`

- [ ] **Step 7: Enable Supermemory**

```bash
ansible-playbook -i inventory/hosts.ini setup.yml \
  ... (same flags) ... \
  -e memory_source_dreaming_enabled=true \
  -e memory_source_supermemory_enabled=true
```

- [ ] **Step 8: Verify federated endpoint returns all three sources**

```bash
ssh kamil@192.168.0.109 "curl -s http://localhost:8788/api/memory/federated | python3 -c \"import json,sys; d=json.load(sys.stdin); print([s['name']+':'+s['status'] for s in d['sources']])\""
```

Expected: `['local:ok', 'supermemory:ok', 'dreaming:ok']` (supermemory may be `error` if not yet fully started)

- [ ] **Step 9: Open Memory tab in browser and verify three section cards**

Navigate to `http://192.168.0.109:8788` → Memory tab.

Verify: Local card with MEMORY.md + USER.md, Dreaming card, Supermemory card. All status chips visible.

---

## Self-Review Checklist

After writing this plan, checked against spec:

| Spec section | Covered by |
|---|---|
| docker-builders Helm chart | Tasks 1-2 |
| QEMU DaemonSet | Task 1 Step 4 |
| Registry NodePort 30500 | Task 2 Step 3 |
| Kaniko RBAC | Task 2 Step 4 |
| ArgoCD app pattern matching existing | Task 2 Step 6 + Task 11 Step 4 |
| hermes-dreaming Light phase + dedup | Task 4 |
| hermes-dreaming REM phase + Groq | Task 5 |
| hermes-dreaming Deep phase + scoring weights | Task 5 |
| Lock file + crash recovery | Task 3 |
| Runner cron entrypoint | Task 6 |
| Federation adapters (Local, Supermemory, Dreaming) | Task 7 |
| Exponential backoff on Supermemory | Task 7 (in `_supermemory_adapter`) |
| GET /api/memory/federated route | Task 8 |
| Memory tab three section cards + status chips | Task 9 |
| Refresh button | Task 9 |
| Playwright E2E tests | Task 10 |
| inventory/hosts.ini lw-c1 | Task 11 |
| /etc/docker/daemon.json insecure-registry | Task 13 |
| docker-compose new services + volumes | Task 13 |
| env.j2 new secrets | Task 13 |
| Rollout with flags disabled first | Task 14 |
| Write-back disabled (V1) | enforced — no write endpoints added |
| Supermemory build context note | addressed in Task 11 Step 2 (hermes_supermemory_repo var) |

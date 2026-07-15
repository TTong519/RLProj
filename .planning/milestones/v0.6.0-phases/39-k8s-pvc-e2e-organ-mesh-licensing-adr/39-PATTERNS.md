# Phase 39: K8s PVC e2e + Organ-Mesh Licensing ADR - Pattern Map

**Mapped:** 2026-06-27
**Files analyzed:** 9 (4 modify, 5 create)
**Analogs found:** 8 / 9 (1 has no analog — the ADR, by design the repo's first)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `tests/k8s/test_pvc_e2e.py` (MODIFY) | test | integration / k8s e2e | `tests/k8s/test_pvc_e2e.py` (self: stub to extend) + `tests/dreamer/test_dreamerv3_subprocess_e2e.py` (skip-gate pattern) | exact (self) + role-match (skip pattern) |
| `k8s/overlays/e2e/kustomization.yaml` (CREATE) | config (kustomize) | declarative manifest | `k8s/overlays/cpu/kustomization.yaml` | exact |
| `k8s/overlays/e2e/e2e-write-job.yaml` (CREATE) | config (k8s manifest) | batch Job | `k8s/base/training-job.yaml` | role-match (Job spec shape) |
| `k8s/overlays/e2e/read-job.yaml` (CREATE) | config (k8s manifest) | batch Job | `k8s/base/training-job.yaml` | role-match (Job spec shape) |
| `.github/workflows/ci.yml` (MODIFY) | config (CI) | request-response (job) | `.github/workflows/ci.yml` `test` + `docker-ci` jobs | exact (append sibling job) |
| `pyproject.toml` (MODIFY) | config (project) | declarative | `pyproject.toml` `[project.optional-dependencies]` `dreamer`/`tracking`/`gui` extras | exact (append new extra) |
| `pytest.ini` (POSSIBLY MODIFY — likely no-op) | config (test) | declarative | `pytest.ini` markers block | exact (k8s marker already registered) |
| `tests/k8s/conftest.py` (POSSIBLY CREATE) | test fixture | session-scoped resource | `tests/conftest.py` | role-match (fixture wiring) |
| `requirements-dev.txt` (POSSIBLY MODIFY) | config (deps) | declarative | `requirements-dev.txt` itself | exact (append line) |
| `docs/adr/0001-organ-mesh-licensing.md` (CREATE) | documentation | static prose | NONE (repo's first ADR) — closest formatting analog: `docs/ARCHITECTURE.md` + `README.md` section conventions | no analog |
| `docs/adr/README.md` or `docs/adr/template.md` (POSSIBLY CREATE) | documentation | static prose | `docs/README.md` (doc-index page) | role-match (index page) |

---

## Pattern Assignments

### `tests/k8s/test_pvc_e2e.py` (test, integration / k8s e2e) — MODIFY

**Primary analog:** the file itself (de-stub the existing `test_pvc_read_write_stub` body in place).
**Secondary analog (skip-gate pattern):** `tests/dreamer/test_dreamerv3_subprocess_e2e.py`.

**Imports + module docstring pattern** (current stub, lines 1-15):
```python
"""K8s PVC end-to-end test stub (DEBT-06 / v0.4.2 deferred work).

A real PVC read/write/delete cycle requires a live Kubernetes cluster with a
persistent-volume provider (for example, `kind` with a local-path provisioner).
This file commits the test scaffolding and marker registry in v0.5.0; the
body is intentionally stubbed and deferred to v0.6.0.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest
```
Replicate: keep `from __future__ import annotations` as the first code line; keep `pytest` import; update module docstring to drop "stub" framing. Add `hashlib` only if SHAs are computed in-Python (the research example uses `sha256sum` in-cluster and parses logs, so `hashlib` is NOT needed).

**Skip-gate pattern to replicate** (from `tests/dreamer/test_dreamerv3_subprocess_e2e.py` lines 16-49 — module-level helper + `pytestmark`-style skip):
```python
def _has_module(name: str) -> bool:
    """Lazy module-presence check via find_spec (D-SKIP-02)."""
    try:
        return importlib.util.find_spec(name) is not None
    except (ValueError, ImportError):
        return False


def _gpu_available() -> bool:
    """Detect a usable GPU via torch (preferred) or jax; tolerate missing/broken imports."""
    try:
        import torch
        if torch.cuda.is_available():
            return True
    except Exception:
        pass
    ...
    return False


pytestmark = pytest.mark.skipif(
    not (_gpu_available() and _has_module("dreamerv3") and _has_module("jax")),
    reason=(
        "Skipped: DreamerV3 E2E requires GPU + dreamerv3 + jax. "
        "Remediation: pip install '.[dreamer]' (jax with CUDA) on a GPU host; "
        "on macOS the test is expected to skip per STATE.md Blocker #4."
    ),
)
```
**Pattern to copy:** helper-function-with-tolerant-`try/except` + descriptive `reason` string that names the remediation command. The current `test_pvc_e2e.py` uses an *in-test* `pytest.skip(...)` call (lines 41-42) rather than a module-level `pytestmark`. The RESEARCH.md Code Example keeps the in-test skip pattern — either is acceptable, but the planner should pick ONE and apply it consistently. Recommended: keep the in-test `pytest.skip` (matches the existing stub + RESEARCH.md Code Example lines 320-334), and replace the `_kind_cluster_available()` body with the Docker-daemon check from RESEARCH.md Pitfall 3.

**Current skip helper to REPLACE** (lines 17-29):
```python
def _kind_cluster_available() -> bool:
    """Return True if a local `kind` cluster is running."""
    if not shutil.which("kind"):
        return False
    result = subprocess.run(
        ["kind", "get", "clusters"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return False
    return bool(result.stdout.strip())
```
**Why replace:** this checks for a *system-installed* `kind` binary, but pytest-kind auto-downloads its own `kind` to `./.pytest-kind/` — so `shutil.which("kind")` returns `None` on this host and the test skips for the wrong reason (RESEARCH.md Pitfall 3).

**Replacement pattern (from RESEARCH.md Code Example lines 320-325):**
```python
def _k8s_e2e_available() -> bool:
    """True if a Docker daemon is reachable (kind needs Docker to run)."""
    if not shutil.which("docker"):
        return False
    result = subprocess.run(["docker", "info"], capture_output=True, check=False)
    return result.returncode == 0
```

**Marker stack pattern** (current stub, lines 32-35 — keep verbatim):
```python
@pytest.mark.k8s
@pytest.mark.integration
@pytest.mark.slow
def test_pvc_read_write_stub() -> None:
```
The three-marker stack (`k8s` + `integration` + `slow`) is the established gate: default `pytest -m "not integration"` skips it; the dedicated CI job selects it with `-m k8s`. Rename the test function to `test_pvc_checkpoint_persistence` (per RESEARCH.md) and keep the marker stack.

**Core body pattern (the de-stubbed write→restart→read cycle):** RESEARCH.md `## Code Examples` lines 301-366 already provides the full concrete body — the planner should lift it verbatim as the starting point, then adapt to the overlay filename(s) the Kustomize plan produces. Key sub-patterns:
- `kind_cluster.kubectl("apply", "-k", "k8s/overlays/e2e")` — apply PVC + write-Job together (WaitForFirstConsumer binding).
- `kind_cluster.kubectl("wait", "--for=condition=Bound", "pvc/surg-rl-checkpoints", "--timeout=180s")` — wait on PVC bind AFTER consumer scheduled.
- `kind_cluster.kubectl("wait", "--for=condition=complete", "job/surg-rl-e2e-write", "--timeout=120s")` — wait on Job completion.
- `kind_cluster.kubectl("logs", "job/surg-rl-e2e-write").strip()` — capture stdout SHA from Job logs.
- Apply `read-job.yaml`, wait again, compare SHAs with `assert read_sha == write_sha`.

**Anti-patterns to forbid in the plan's `must_not`** (from RESEARCH.md `## Anti-Patterns to Avoid`):
- No `spec.nodeName` in the e2e Job spec (breaks `WaitForFirstConsumer` binding — kind issue #3897).
- No `kubectl wait --for=condition=Bound pvc/...` BEFORE scheduling a consumer.
- No reuse of `k8s/base/training-job.yaml` as-is (GPU nodeSelector fails on kind).

---

### `k8s/overlays/e2e/kustomization.yaml` (config, kustomize overlay) — CREATE

**Analog:** `k8s/overlays/cpu/kustomization.yaml` (exact structural match — 13 lines).

**Full analog content** (cpu overlay, lines 1-39):
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

patches:
  - patch: |
      - op: remove
        path: /spec/template/spec/nodeSelector
    target:
      kind: Job
      name: surg-rl-training
  - patch: |
      - op: remove
        path: /spec/template/spec/tolerations
    target:
      kind: Job
      name: surg-rl-training
  - patch: |
      - op: remove
        path: /spec/template/spec/containers/0/resources/requests/nvidia.com~1gpu
    target:
      kind: Job
      name: surg-rl-training
  - patch: |
      - op: remove
        path: /spec/template/spec/containers/0/resources/limits/nvidia.com~1gpu
    target:
      kind: Job
      name: surg-rl-training
  - patch: |
      - op: replace
        path: /spec/template/spec/containers/0/image
        value: ghcr.io/surg-rl/surg-rl:v0.3.0
    target:
      kind: Job
      name: surg-rl-training
```

**Patterns to replicate:**
- Header: `apiVersion: kustomize.config.k8s.io/v1beta1` + `kind: Kustomization` (exact).
- `resources:` list — but the e2e overlay MUST NOT use `- ../../base` (RESEARCH.md Assumption A4: pulls in GPU nodeSelector + raycluster that fail on kind). Instead list ONLY `../../base/pvc.yaml` + the new `e2e-write-job.yaml` (RESEARCH.md Code Example lines 370-382).
- JSON6902 patch syntax: `- op: remove` / `- op: replace` with `path:` and `target:` block — copy this syntax if patching is needed. For the e2e overlay the write/read Jobs are FRESH manifests (no GPU constraints to strip), so `patches: []` per RESEARCH.md example. The planner may omit the `patches:` key entirely.

**`k8s/base/pvc.yaml` reference** (lines 1-13, the PVC the overlay applies):
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: surg-rl-checkpoints
  labels:
    app: surg-rl
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 50Gi
  storageClassName: standard
```
The `storageClassName: standard` EXACTLY matches kind's default StorageClass — no manifest fix needed (RESEARCH.md Summary). The e2e overlay simply re-references this file.

**`k8s/base/kustomization.yaml` reference** (lines 1-11 — what NOT to pull in via `../../base`):
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - training-job.yaml
  - raycluster.yaml
  - rayjob.yaml
  - configmap.yaml
  - secret.yaml
  - pvc.yaml
  - rbac.yaml
```
Pulling in `- ../../base` would also apply `training-job.yaml` (GPU nodeSelector), `raycluster.yaml`, `rayjob.yaml`, `secret.yaml` — all unwanted in the e2e path. Reference `../../base/pvc.yaml` directly instead.

---

### `k8s/overlays/e2e/e2e-write-job.yaml` + `read-job.yaml` (config, batch Job) — CREATE

**Analog:** `k8s/base/training-job.yaml` (Job spec shape — `batch/v1`, `backoffLimit`, `ttlSecondsAfterFinished`, `template.spec`).

**Job skeleton pattern to replicate** (from `k8s/base/training-job.yaml` lines 1-16):
```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: surg-rl-training
  labels:
    app: surg-rl
    component: training
spec:
  backoffLimit: 3
  ttlSecondsAfterFinished: 86400
  template:
    metadata:
      labels:
        app: surg-rl
        component: training
    spec:
      restartPolicy: Never
      ...
```

**What the e2e Jobs must do differently** (from RESEARCH.md Code Example lines 386-423):
- `metadata.name`: `surg-rl-e2e-write` (and `surg-rl-e2e-read`) — distinct from `surg-rl-training` so `kubectl wait job/...` targets the right Job.
- `backoffLimit: 0` (not 3) — fail fast on e2e assertion failures, no retry noise.
- `ttlSecondsAfterFinished: 600` (not 86400) — short retention, the test reads logs immediately.
- `restartPolicy: Never` — keep from analog.
- `containers[0].image`: `busybox:1.36` (NOT `ghcr.io/surg-rl/surg-rl/...`) — RESEARCH.md Pitfall 5: kind has no credentials and the e2e asserts PVC persistence, not the training stack. Use the smallest public image that can `head -c 4096 /dev/urandom > /checkpoints/ckpt.bin` and `sha256sum`.
- `containers[0].command`: `["/bin/sh", "-c"]` with `args:` as a multi-line `sh -c` script.
- `volumeMounts`: `name: checkpoints`, `mountPath: /checkpoints` — keep the `checkpoints` volume name from the base Job (lines 58-63, 92-94) for consistency.
- `volumes`: `persistentVolumeClaim.claimName: surg-rl-checkpoints` — must match `k8s/base/pvc.yaml` line 4.
- **NO** `nodeSelector`, **NO** `tolerations`, **NO** `nvidia.com/gpu` resources (RESEARCH.md Anti-Pattern #3).
- **NO** `spec.nodeName` (RESEARCH.md Pitfall 2 — breaks PVC binding under `WaitForFirstConsumer`).
- **NO** `serviceAccountName: surg-rl` needed (the e2e Job only writes files to a PVC; default SA is sufficient; avoids depending on `k8s/base/rbac.yaml`).

**Read-Job pattern:** identical skeleton, `metadata.name: surg-rl-e2e-read`, command reads `/checkpoints/ckpt.bin` and `sha256sum`s it to stdout. The "pod restart" semantics come from this being a SEPARATE Job whose pod mounts the SAME PVC (RESEARCH.md Open Question #2 — recommended: two separate Job manifests).

---

### `.github/workflows/ci.yml` (config, CI workflow) — MODIFY

**Analog:** the existing `test` job (lines 10-81) for the step skeleton; the `docker-ci` job (lines 83-134) for a sibling-job-on-`ubuntu-latest`-only pattern.

**Job-header pattern to replicate** (from `test` job, lines 10-14):
```yaml
  test:
    name: ${{ matrix.os }} / Python ${{ matrix.python-version }}
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
```
The new `k8s-e2e` job is NOT a matrix job (single Ubuntu runner) — mirror `docker-ci` instead (lines 83-85):
```yaml
  docker-ci:
    name: Docker Build (multi-arch)
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
```

**Step skeleton to replicate** (from `test` job, lines 26-46):
```yaml
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Cache pip dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-${{ runner.arch }}-pip-${{ hashFiles('pyproject.toml') }}
          restore-keys: |
            ${{ runner.os }}-${{ runner.arch }}-pip-

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev,tracking]"
```
**Adaptation for the k8s-e2e job:**
- Pin `python-version: "3.11"` (single version, no matrix).
- Install `pip install -e ".[dev,k8s-test]"` (the new extra from `pyproject.toml`) — RESEARCH.md Code Example lines 427-446.
- Cache step is optional but encouraged (matches the repo convention).

**Test invocation pattern** (from `test` job, line 70):
```yaml
      - name: Test with pytest (Linux)
        if: runner.os == 'Linux'
        run: pytest tests/ -m "not integration" -v
```
**Adaptation for k8s-e2e** (from RESEARCH.md Code Example lines 444-445):
```yaml
      - name: Run PVC e2e test (CPU-only kind cluster)
        run: pytest tests/k8s/test_pvc_e2e.py -m k8s -v --cluster-name=surg-rl-e2e
```
Note: `-m k8s` (NOT `"not integration"`) selects the marked test; `--cluster-name=surg-rl-e2e` is a pytest-kind CLI option (RESEARCH.md Validation Architecture line 532). The `PYTHONPATH=src` prefix is NOT needed — `pytest.ini` line 4 (`pythonpath = src`) handles it for pytest invocations (CLAUDE.md notes `PYTHONPATH=src` is required only for *direct script runs*).

**Triggers pattern (do NOT modify):** the existing `on:` block (lines 3-7) already triggers on push/PR to main — the new job inherits this. Do not add a separate `on:` block.

---

### `pyproject.toml` (config, project metadata) — MODIFY

**Analog:** the existing `[project.optional-dependencies]` extras (`dreamer`, `tracking`, `gui`).

**Extras-block pattern** (lines 65-143):
```toml
[project.optional-dependencies]
# Real surgical mesh assets — OBJ loading + decimation
assets = [
    "trimesh>=4.5.0",
]

# Performance benchmarking — plots, statistics, reports
benchmark = [
    "matplotlib>=3.7.0",
    ...
]

dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "pytest-asyncio>=0.21.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
    "pre-commit>=3.5.0",
]

llm = [...]

# Multi-agent RL — PettingZoo ParallelEnv + SuperSuit SB3 wrappers
marl = [...]

tracking = [
    "wandb>=0.16.0",
    "mlflow>=2.10.0",
]

# Ray/RLlib: pip-installable, requires Python >=3.10
...

# jax + dreamerv3 use ~= (volatile APIs per RESEARCH Phase 24 findings)
dreamer = [
    "jax~=0.4.20",
    "optax>=0.1.7",
    "dreamerv3~=1.5.0",
]

# GUI scene editor — PySide6 6.8 LTS line + markdown rendering
# PySide6 is LGPL-3-or-GPL; we pin >=6.8,<7.0 for Qt6.8 LTS (Oct 2026) + Qt6.11 current
# markdown-it-py was already a transitive dep; promoted to explicit
gui = [
    "PySide6>=6.8.0,<7.0",
    "markdown-it-py>=3.0.0",
    "imageio>=2.31.0",
]
```

**Pattern to replicate for the new `k8s-test` extra:**
- A comment line above the extra explaining its purpose (matches `dreamer`, `gui` style).
- Array of pinned specifiers using `>=` (the repo convention; `~=` is reserved for volatile APIs per the `dreamer` comment).
- Suggested content (from RESEARCH.md Assumption A1 + Standard Stack):
  ```toml
  # K8s PVC e2e testing — pytest-kind session fixture provisions a kind cluster in Docker
  k8s-test = [
      "pytest-kind>=22.11.1",
  ]
  ```
- Do NOT declare `pykube-ng` explicitly unless Wave 0 confirms pytest-kind doesn't pull it transitively (RESEARCH.md Assumption A6).

**Package-legitimacy checkpoint:** RESEARCH.md `## Package Legitimacy Audit` flags `pytest-kind` and `pykube-ng` as SUS (download-count null, not slopsquat). The planner MUST insert a `checkpoint:human-verify` before the install step per RESEARCH.md line 87.

---

### `pytest.ini` (config, test markers) — POSSIBLY MODIFY (likely no-op)

**Analog:** the existing `markers` block (lines 1-12).

**Full current content:**
```ini
[pytest]
testpaths = tests
python_files = test_*.py
pythonpath = src
addopts = -v --tb=short
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
markers =
    integration: marks tests as integration tests (deselect with '-m "not integration"')
    slow: marks tests as slow (>10s)
    k8s: marks tests as Kubernetes e2e tests (deselect with '-m "not k8s"')
```

**Pattern:** the `k8s` marker is ALREADY registered (line 11) — Phase 35 added it alongside the stub. No change required for marker registration. The planner should verify the marker line is present and treat this file as `must_not`-modify unless a new marker (e.g. `slow` already covers it) is genuinely needed. If `pytest-kind` registers its own CLI options (`--cluster-name`, `--keep-cluster`) via plugin entry-points, no `pytest.ini` change is needed for those either.

---

### `tests/k8s/conftest.py` (test fixture) — POSSIBLY CREATE

**Analog:** `tests/conftest.py` (root-level shared fixtures).

**Fixture-file pattern** (from `tests/conftest.py` lines 1-13):
```python
"""Shared pytest fixtures and utilities."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from surg_rl.scene_definition import SceneLoader

# Ensure src/ is on the path for pytest collection
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
```

**Pattern to replicate IF a k8s conftest is needed:**
- Module docstring describing scope.
- `from __future__ import annotations` as first code line (CLAUDE.md code style).
- `import pytest`.
- Any k8s-specific fixture (e.g. wrapping the `kind_cluster` session fixture from pytest-kind, or a `_k8s_e2e_available` helper shared across multiple k8s test files). Since there is currently only ONE k8s test file, the planner may keep the helper inside `test_pvc_e2e.py` and SKIP creating this conftest. If created, mirror the root conftest's `sys.path` insertion only if needed (the root conftest already covers `tests/`).

**Recommendation:** do NOT create `tests/k8s/conftest.py` unless a second k8s test file appears — keep the skip helper co-located with the test (matches the current stub + `tests/dreamer/test_dreamerv3_subprocess_e2e.py` pattern, both of which co-locate their skip helpers).

---

### `requirements-dev.txt` (config, deps) — POSSIBLY MODIFY

**Full current content** (lines 1-11):
```text
# Development dependencies
# Install with: pip install -r requirements-dev.txt

-r requirements.txt

# Development tools
pytest-cov>=4.0.0
black>=23.0.0
ruff>=0.1.0
mypy>=1.0.0
pre-commit>=3.5.0
```

**Pattern:** flat list of `name>=version` lines under a `# Development tools` comment header, with `-r requirements.txt` to pull the runtime deps. If the planner chooses to also list `pytest-kind` here (in addition to the `pyproject.toml` `[k8s-test]` extra), append `pytest-kind>=22.11.1` under a new `# K8s e2e testing` comment header. **Recommendation:** prefer the `pyproject.toml` extra (the CI job uses `pip install -e ".[dev,k8s-test]"`); only mirror into `requirements-dev.txt` if the repo convention requires parity. Check `requirements.txt` (the runtime dep file) is NOT touched — pytest-kind is dev-only.

---

### `docs/adr/0001-organ-mesh-licensing.md` (documentation, static prose) — CREATE

**Analog:** NONE — this is the repo's first ADR. RESEARCH.md Open Question #3 explicitly recommends MADR format. Closest formatting analogs in the repo:

**Doc-structure analog 1 — `docs/ARCHITECTURE.md`** (referenced from `docs/README.md` line "System architecture and design decisions"): the existing doc that records design decisions in prose. The ADR should adopt the same markdown conventions: ATX `#`/`##` headings, fenced code blocks, bullet lists.

**Doc-structure analog 2 — `README.md` / `CONTRIBUTING.md`** — both start with a `<!-- generated-by: gsd-doc-writer -->` HTML comment and a single `#` H1 title. The ADR MAY include the same generated-by comment if the doc-writer agent produces it, but this is NOT required for an ADR (ADRs are hand-curated decision records, not auto-generated).

**MADR template structure to replicate** (from RESEARCH.md Open Question #3 + `## Don't Hand-Roll`):
```markdown
# 1. Organ-Mesh Asset Licensing

* Status: accepted
* Date: 2026-06-27
* Decision-makers: surg-rl maintainers

## Context and Problem Statement

(v0.4.0 Phase 20 needs 4 organ OBJ meshes; choose between procedural generation
and SurgToolLoc dataset download.)

## Considered Options

1. Procedural generation (default)
2. SurgToolLoc 2023 dataset download
3. ...

## Decision Outcome

Chosen: **procedural generation**. SurgToolLoc rejected.

### Rationale

- Modality mismatch (primary): SurgToolLoc = 24,695 endoscopic video clips with
  tool-presence labels (https://surgtoolloc23.grand-challenge.org/data-description/),
  NOT organ geometry.
- Licensing incompatibility (secondary, required by SC#5): SurgToolLoc challenge
  guidelines clause 2 — "Your team will use the provided data only in the scope of
  the challenge and neither pass it on to a third party nor use it for any
  publication or for commercial uses."
  (https://surgtoolloc23.grand-challenge.org/challenge-guidelines/)

## Consequences

* Positive: MIT-clean asset pipeline; reproducible; no EULA gating.
* Negative: lower photorealism vs. real surgical video.

## References

* https://surgtoolloc23.grand-challenge.org/challenge-guidelines/
* https://surgtoolloc23.grand-challenge.org/data-description/
* arXiv:2305.07152 — SurgToolLoc/SurgVU 2022-2025 overview paper
```

**Verbatim license clauses to cite (from RESEARCH.md `## Code Examples` lines 450-459):**
```markdown
> Clause 2: "Your team will use the provided data only in the scope of the
> challenge and neither pass it on to a third party nor use it for any
> publication or for commercial uses."

> Clause 13: "The data used for SurgToolLoc 2023 can only be used for
> publication purposes after the results of this challenge have been
> submitted for publication."
```
Cite the PUBLIC challenge-guidelines URL (NOT the private dataset EULA — RESEARCH.md Pitfall 6: the EULA is gated behind an agreement form emailed to `isi.challenges@intusurg.com`). The ADR should explicitly note that the public guidelines are the authoritative citable source.

**Filename convention:** `0001-organ-mesh-licensing.md` — 4-digit zero-padded (RESEARCH.md Assumption A3). This sets the template for future ADRs.

**must include (SC#4 + SC#5):**
- Status = `accepted`.
- Cited URL present (SC#5 audit grep: `grep -q "challenge-guidelines" docs/adr/0001-...`).
- Verbatim clause text present (SC#5 audit grep: `grep -F "neither pass it on to a third party" docs/adr/0001-...`).
- Modality fact present (endoscopic video + tool-presence labels, NOT organ meshes).

---

### `docs/adr/README.md` or `docs/adr/template.md` (documentation, doc index) — POSSIBLY CREATE

**Analog:** `docs/README.md` (the docs index page).

**Index-page pattern** (from `docs/README.md` lines 1-32): H1 title, intro paragraph, `## 📚 Documentation Index` section with grouped bullet links. An `adr/README.md` would list ADRs as a numbered table or bullet list. **Recommendation:** create a minimal `docs/adr/README.md` index with a one-line intro + a table of ADRs (number, title, status, date) — this sets the discoverability pattern for future ADRs. A `template.md` is optional (MADR ships a public template; linking to it is sufficient).

---

## Shared Patterns

### Marker stack on the e2e test
**Source:** `tests/k8s/test_pvc_e2e.py` lines 32-34 + `pytest.ini` lines 8-11
**Apply to:** the de-stubbed `test_pvc_checkpoint_persistence` function
```python
@pytest.mark.k8s
@pytest.mark.integration
@pytest.mark.slow
def test_pvc_checkpoint_persistence(kind_cluster) -> None:
```
The three-marker stack ensures the default `pytest -m "not integration"` run (CI `test` job line 70) skips it; the dedicated `k8s-e2e` CI job selects with `-m k8s`. Do NOT remove any of the three markers.

### Tolerant skip-gate helper
**Source:** `tests/dreamer/test_dreamerv3_subprocess_e2e.py` lines 16-49 + RESEARCH.md Code Example lines 320-325
**Apply to:** the e2e test's skip helper (replace `_kind_cluster_available` with `_k8s_e2e_available`)
```python
def _k8s_e2e_available() -> bool:
    if not shutil.which("docker"):
        return False
    result = subprocess.run(["docker", "info"], capture_output=True, check=False)
    return result.returncode == 0
```
Pattern: `shutil.which` + tolerant `subprocess.run(..., check=False)` + `returncode == 0` check. Matches the dreamer e2e's "tolerate missing/broken imports" philosophy but for the Docker daemon.

### Kustomize overlay header
**Source:** `k8s/overlays/cpu/kustomization.yaml` lines 1-5 + `k8s/overlays/gpu/kustomization.yaml` lines 1-5
**Apply to:** `k8s/overlays/e2e/kustomization.yaml`
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ...
```
All three existing overlays (`cpu`, `gpu`) and `k8s/base/kustomization.yaml` use the identical 2-line header. The e2e overlay MUST use the same.

### CI job step skeleton (checkout → setup-python → install → run)
**Source:** `.github/workflows/ci.yml` lines 26-46 + 68-70
**Apply to:** the new `k8s-e2e` job
```yaml
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev,k8s-test]"
      - name: Run PVC e2e test (CPU-only kind cluster)
        run: pytest tests/k8s/test_pvc_e2e.py -m k8s -v --cluster-name=surg-rl-e2e
```

### Pyproject optional-extra entry
**Source:** `pyproject.toml` `[project.optional-dependencies]` block (lines 65-143)
**Apply to:** the new `k8s-test` extra
```toml
# K8s PVC e2e testing — pytest-kind session fixture provisions a kind cluster in Docker
k8s-test = [
    "pytest-kind>=22.11.1",
]
```

---

## No Analog Found

| File | Role | Data Flow | Reason | Planner Guidance |
|------|------|-----------|--------|------------------|
| `docs/adr/0001-organ-mesh-licensing.md` | documentation | static prose | Repo's FIRST ADR — no existing ADR to model on. | Use MADR format per RESEARCH.md Open Question #3 + the structure sketched in this file's `## Pattern Assignments` ADR section. Cite the two public SurgToolLoc URLs and the verbatim clause 2 text. |
| `docs/adr/README.md` / `template.md` | documentation | static prose | No ADR index exists. | Optional; model on `docs/README.md` index pattern. |

---

## Metadata

**Analog search scope:**
- `tests/k8s/`, `tests/dreamer/`, `tests/conftest.py`
- `k8s/base/`, `k8s/overlays/cpu/`, `k8s/overlays/gpu/`
- `.github/workflows/ci.yml`
- `pyproject.toml`, `pytest.ini`, `requirements-dev.txt`
- `docs/` (for doc-structure conventions), `README.md`, `CONTRIBUTING.md`
- `.planning/decisions/` — does NOT exist (no prior decision records)
- `find -name '*adr*'` — no existing ADR files anywhere in the repo

**Files scanned:** 11 (test files, k8s manifests, CI workflow, project config, doc index)
**Pattern extraction date:** 2026-06-27

## PATTERN MAPPING COMPLETE
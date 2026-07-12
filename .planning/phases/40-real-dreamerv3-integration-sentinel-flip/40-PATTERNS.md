# Phase 40: Real DreamerV3 Integration + Sentinel Flip - Pattern Map

**Mapped:** 2026-07-12
**Files analyzed:** 9 (5 production source + 4 test/CI)
**Analogs found:** 9 / 9 (every file has an in-repo analog)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/surg_rl/dreamer/subprocess.py` (5 stub bodies) | service (child-subprocess training fns) | event-driven (JSON-over-stdio pipe) | `src/surg_rl/dreamer/subprocess.py` itself — stub bodies + `_run_subprocess_loop` dispatch | exact (self-edit) |
| `src/surg_rl/dreamer/training.py` (`_find_latest_checkpoint`) | utility (checkpoint discovery) | file-I/O (glob) | `src/surg_rl/dreamer/training.py:183-196` — current `_find_latest_checkpoint` | exact (self-edit) |
| `src/surg_rl/dreamer/wrapper.py` (`action_space` property) | service (env adapter) | request-response (gymnasium step) | `src/surg_rl/dreamer/wrapper.py:74-81` — current `action_space` property | exact (self-edit) |
| `tests/dreamer/test_dreamerv3_subprocess_e2e.py` (flip) | test | request-response (run → assert) | `tests/dreamer/test_dreamerv3_subprocess_e2e.py` — current negative-assertion form | exact (self-edit, sign-flip) |
| `tests/dreamer/test_dreamerv3_regression_guard.py` (NEW) | test (source-inspection) | transform (AST/string inspect) | `tests/test_dreamer_subprocess.py:413-430` — `test_subprocess_main_does_not_use_fdopen_for_stdout` source-inspection guard | exact (same `inspect.getsource` + string-assert idiom) |
| `tests/dreamer/test_dreamerv3_checkpoint_resume.py` (NEW) | test (e2e, GPU-gated) | request-response (run → restart → assert) | `tests/dreamer/test_dreamerv3_subprocess_e2e.py` — module-level `pytestmark` skipif + `run_dreamer_training(...)` call shape | role-match (same skipif gate + same entrypoint) |
| `tests/test_dreamer_subprocess.py` (add JAX-leak guard) | test (source-inspection / import-leak) | transform (sys.modules check) | `tests/test_dreamer_subprocess.py:110-128` — `TestProcessIsolationImport` class | exact (same class, extend with new method) |
| `.github/workflows/ci.yml` (add `dreamer-gpu` job) | config (CI workflow) | batch (install + run pytest) | `.github/workflows/ci.yml:10-111` — existing `test` job; `:180-206` — `k8s-e2e` job (separate-matrix job pattern) | role-match (new job mirrors `test` job + `k8s-e2e` separate-trigger pattern) |
| `.planning/...` (Dockerfile.cuda — optional, deferred) | config (container) | batch | `.github/workflows/ci.yml:136-144` — CUDA docker build step | partial (deferred per CONTEXT.md) |

## Pattern Assignments

### `src/surg_rl/dreamer/subprocess.py` — 5 stub replacements (service, event-driven)

**Analog:** the file itself — the stub bodies at lines 125-149 + the unchanged `_run_subprocess_loop` dispatch at lines 57-122.

**Critical constraint (SC#1):** The `_JsonStdout` wrapper (lines 30-53), the `DreamerSubprocess` parent class (lines 152-282), `_subprocess_main` (lines 16-27), and the `_run_subprocess_loop` message handlers (lines 80-117) are UNCHANGED. The 5 stubs are *called by* these handlers; replacing the stub bodies is the entire production change surface. Keep all signatures identical so the call sites at lines 83, 92, 102, 109, 112 stay valid.

**Imports pattern — JAX isolation (SC#5, lines 7-13 + line 60):**
```python
# Module top (PARENT-importable — NO jax/dreamerv3 here)
import contextlib
import json
import multiprocessing
import os
import sys
from collections.abc import Iterator
from typing import Any

# Inside _run_subprocess_loop (CHILD only, line 60):
def _run_subprocess_loop(stdin_pipe) -> None:
    import jax  # INSIDE the child fn — preserves SC#5
    print(json.dumps({"type": "READY", "jax_version": jax.__version__}), flush=True)
```
**Rule for the stub replacements:** every `import jax` / `import dreamerv3` / `import embodied` / `from dreamerv3.agent import Agent` MUST live INSIDE the 5 stub function bodies (deferred to call-time, which only happens in the child). Never add these to the module top — that would leak JAX into the parent and break `tests/test_dreamer_subprocess.py::TestProcessIsolationImport`.

**Core pattern — the unchanged dispatch that calls the stubs (lines 80-117):**
```python
if msg_type == "CONFIG":
    config = msg.get("config", {})
    agent = _build_agent(config)                       # STUB 1 — must return non-None
    print(json.dumps({"type": "CONFIG_ACK"}), flush=True)

elif msg_type == "TRAIN":
    if agent is None:                                  # the "Agent not configured" sentinel
        print(json.dumps({"type": "ERROR", "error": "Agent not configured"}), flush=True)
        continue
    total_steps = msg.get("total_steps", 100000)
    eval_every = msg.get("eval_every", 10000)
    for metrics in _train_loop(agent, total_steps, eval_every):   # STUB 2 — yield METRICS per batch
        print(json.dumps({"type": "METRICS", **metrics}), flush=True)
    print(json.dumps({"type": "TRAIN_COMPLETE"}), flush=True)

elif msg_type == "EVAL":
    if agent is None:
        print(json.dumps({"type": "ERROR", "error": "Agent not configured"}), flush=True)
        continue
    checkpoint = msg.get("checkpoint")
    n_episodes = msg.get("n_episodes", 10)
    metrics = _evaluate(agent, checkpoint, n_episodes)  # STUB 3 — return shape must match
    print(json.dumps({"type": "EVAL_RESULT", "metrics": metrics}), flush=True)

elif msg_type == "CHECKPOINT":
    action = msg.get("action", "save")
    path = msg.get("path")
    if action == "save" and agent:
        _save_checkpoint(agent, path)                   # STUB 4
        print(json.dumps({"type": "CHECKPOINT_SAVED", "path": path}), flush=True)
    elif action == "load" and agent:
        _load_checkpoint(agent, path)                   # STUB 5
        print(json.dumps({"type": "CHECKPOINT_LOADED", "path": path}), flush=True)
```
**Implication for the stub replacements:** `_build_agent` must return a non-None object (or the sentinel "Agent not configured" ERROR still fires and the flipped E2E test fails). `_train_loop` must `yield` dicts with keys that survive `{"type": "METRICS", **metrics}` — i.e. it must NOT include `"type"` (the dispatch adds it) and should include `step`, `loss`, `reconstruction_loss`, `reward_loss`, `total_loss` (the parent's `run_dreamer_training` reads these at training.py:299-306). `_evaluate` must return a plain dict (it goes into `{"metrics": metrics}`). `_save_checkpoint`/`_load_checkpoint` return `None` — the handler emits the ack regardless.

**Current stub bodies — the exact text being replaced (lines 125-149):**
```python
def _build_agent(config: dict[str, Any]) -> Any:
    """Build DreamerV3 agent from config."""
    # This will be implemented when dreamerv3 is available
    # For now, return a mock that can be replaced
    return None

def _train_loop(agent: Any, total_steps: int, eval_every: int) -> Iterator[dict[str, Any]]:
    """Training loop yielding metrics."""
    yield {"step": 0, "loss": 0.0, "reconstruction_loss": 0.0, "reward_loss": 0.0}

def _evaluate(agent: Any, checkpoint: str, n_episodes: int) -> dict[str, Any]:
    """Run evaluation."""
    return {"reconstruction_mse": 0.0, "reward_mae": 0.0, "success_rate": 0.0}

def _save_checkpoint(agent: Any, path: str) -> None:
    """Save checkpoint."""
    pass

def _load_checkpoint(agent: Any, path: str) -> None:
    """Load checkpoint."""
    pass
```
The regression-guard test (below) fails if `"return None"` re-appears in `_build_agent` source. Keep the signature `def _build_agent(config: dict[str, Any]) -> Any:` identical.

**Pipe protocol pattern — every child→parent message (lines 63, 84, 88, 93, 94, 98, 103, 110, 113, 116):**
```python
print(json.dumps({"type": "MESSAGE_TYPE", ...payload}), flush=True)
```
`_train_loop`'s real implementation must ship METRICS via `print(json.dumps(...), flush=True)` — but actually the dispatch at line 93 already wraps each yielded dict: `print(json.dumps({"type": "METRICS", **metrics}), flush=True)`. So `_train_loop` only needs to `yield` the metrics dict; it does NOT print directly. Keep it that way (D-07 — `_train_loop` owns the JSON pipe via `yield`, not via direct `print`).

**XLA env-var setup that MUST stay before `import jax` (lines 16-27):**
```python
def _subprocess_main(child_stdin, child_stdout, config: dict[str, Any]) -> None:
    memory_fraction = float(config.get("memory_fraction", 0.4))
    os.environ["XLA_PYTHON_CLIENT_MEM_FRACTION"] = str(memory_fraction)
    os.environ["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"
    sys.stdout = _JsonStdout(child_stdout)
    sys.stderr = os.fdopen(2, "w", buffering=1)   # logger→stderr (SC#5) — stderr is a real fd
    _run_subprocess_loop(child_stdin)
```
`sys.stderr = os.fdopen(2, ...)` is already the stderr sink — the embodied logger should write here, not to stdout. The stub replacements should not touch this.

---

### `src/surg_rl/dreamer/training.py` — `_find_latest_checkpoint` glob flip (utility, file-I/O)

**Analog:** the current `_find_latest_checkpoint` at lines 183-196 (self-edit).

**Current body — the stub-era `.pt` glob being retired (lines 183-196):**
```python
def _find_latest_checkpoint(task: str, obs_type: str) -> str | None:
    """Find latest checkpoint for task/obs_type."""
    checkpoint_dir = Path(f"models/dreamerv3/{task}_{obs_type}")
    if not checkpoint_dir.exists():
        return None
    checkpoints = list(checkpoint_dir.glob("checkpoint_*.pt"))   # ← retire this glob
    if not checkpoints:
        final = checkpoint_dir / "final.pt"                      # ← retire this fallback
        if final.exists():
            return str(final)
        return None
    latest = max(checkpoints, key=lambda p: p.stat().st_mtime)
    return str(latest)
```
**D-09 replacement:** glob `*.ckpt` (the `embodied.Checkpoint` native `checkpoint.ckpt` binary). No `.pt` compat path. Keep the `Path(f"models/dreamerv3/{task}_{obs_type}")` scoping — it's the per-task/obs-type collision-avoidance key (Pitfall 5). Keep the `max(..., key=lambda p: p.stat().st_mtime)` mtime-selection idiom (it still applies if multiple `.ckpt` files ever coexist).

**Callers to keep consistent (training.py:272, 289):** both call sites pass `(task, obs_type)` and expect `str | None` — signature unchanged. The downstream `subprocess.load_checkpoint(resume_checkpoint)` (line 293) and `subprocess.evaluate(latest_checkpoint, ...)` (line 276) receive the path string; the stub replacements in `subprocess.py` accept the same `path: str` arg.

**Stub-era `.pt` writes to retire (training.py:315, 333, 352):** `checkpoint_path / f"checkpoint_{step}.pt"`, `checkpoint_path / "final.pt"`, `checkpoint_path / f"checkpoint_interrupt_{step}.pt"`. Under D-09 these become `checkpoint.ckpt` writes (or are delegated to `embodied.Checkpoint.save()` inside `_save_checkpoint`). The planner decides whether the `.pt` naming at lines 315/333/352 stays as the parent-side path string passed to `_save_checkpoint` (the child writes `.ckpt` internally) or is renamed outright — but the `_find_latest_checkpoint` glob MUST match whatever the child actually writes.

---

### `src/surg_rl/dreamer/wrapper.py` — `action_space` property (service, request-response)

**Analog:** the current `action_space` property at lines 74-81 (self-edit).

**Current body (lines 74-81):**
```python
@property
def action_space(self) -> spaces.Box:
    """Return action space (same as SurgicalEnv + optional reset)."""
    base_space = self.env.action_space
    if isinstance(base_space, spaces.Box):
        return base_space
    return spaces.Box(-1.0, 1.0, shape=(7,), dtype=np.float32)
```
**D-05 / research A4 finding:** PyPI 1.5.0 `Agent.__init__` extracts `act_space['action']` (RESEARCH.md:169 — `self.act_space = act_space['action']`). The current property returns a bare `spaces.Box`, which does NOT match. Claude's discretion (CONTEXT.md:147-149) — the planner verifies against the installed `Agent` constructor. If the installed API requires the dict shape, return:
```python
return spaces.Dict({"action": base_space, "reset": spaces.Discrete(2)})
```
The `step()` method at lines 96-137 already accepts a dict `action` with `"action"` and `"reset"` keys (lines 108, 116) — so the dict return is consistent with the existing step path.

**Observation-space pattern (lines 50-72) — UNCHANGED, already correct for dreamerv3 1.5.0:** the `spaces.Dict` with `image`/`state` + `is_first`/`is_last`/`is_terminal` keys is exactly what `Agent(obs_space, ...)` expects. Do not modify.

---

### `tests/dreamer/test_dreamerv3_subprocess_e2e.py` — sentinel flip (test, request-response)

**Analog:** the file itself — the current negative-assertion form (self-edit, sign-flip).

**Module-level skipif gate — STAYS (lines 42-49):**
```python
pytestmark = pytest.mark.skipif(
    not (_gpu_available() and _has_module("dreamerv3") and _has_module("jax")),
    reason=(
        "Skipped: DreamerV3 E2E requires GPU + dreamerv3 + jax. "
        "Remediation: pip install '.[dreamer]' (jax with CUDA) on a GPU host; "
        "on macOS the test is expected to skip per STATE.md Blocker #4."
    ),
)
```
The runtime tests (training, checkpoint) stay gated by this. The regression-guard test goes in a SEPARATE module without this gate (see below) so it runs on macOS.

**Helper functions to keep (lines 16-39):**
```python
def _has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ValueError, ImportError):
        return False

def _gpu_available() -> bool:
    try:
        import torch
        if torch.cuda.is_available():
            return True
    except Exception:
        pass
    try:
        import jax
        return any(getattr(d, "platform", None) == "gpu" for d in jax.devices())
    except Exception:
        return False
    return False
```

**Test 1 to flip — `test_e2e_run_dreamer_training_against_stub` (lines 61-79):**
```python
# CURRENT (negative — stub reality):
with pytest.raises(RuntimeError, match="Agent not configured"):
    run_dreamer_training(
        task="suturing", obs_type="state", total_steps=1000,
        eval_every=500, checkpoint_dir=str(tmp_path / "checkpoints"),
    )

# FLIPPED (positive — real agent, D-10):
metrics = run_dreamer_training(
    task="suturing", obs_type="state", total_steps=1000,
    eval_every=500, checkpoint_dir=str(tmp_path / "checkpoints"),
)
assert metrics is not None
assert "training_curves" in metrics
# Rename: test_e2e_run_dreamer_training_real_agent
```

**Test 2 to flip — `test_e2e_checkpoint_files_not_written_in_stub_state` (lines 81-104):**
```python
# CURRENT (negative):
assert not (ckpt_dir / "final.pt").exists(), "..."
assert not (ckpt_dir / "training_metrics.json").exists(), "..."

# FLIPPED (positive — D-10):
assert (ckpt_dir / "checkpoint.ckpt").exists()  # native embodied.Checkpoint format
# OR, if the parent still writes final.pt as a convenience copy:
# assert (ckpt_dir / "final.pt").exists()
assert (ckpt_dir / "training_metrics.json").exists()
# Rename: test_e2e_checkpoint_files_written
```

**Test 3 — `test_e2e_dreamer_color_constant` (lines 55-59):** UNCHANGED (constant is independent of stub state).

**Call-site shape to preserve (lines 70, 88):** `from surg_rl.dreamer.training import run_dreamer_training` — the import is inside the test method (after the skipif gate), so it only runs when the test actually executes. Keep this pattern; do not move to module top.

---

### `tests/dreamer/test_dreamerv3_regression_guard.py` — NEW (test, source-inspection, no GPU)

**Analog:** `tests/test_dreamer_subprocess.py:413-430` — `test_subprocess_main_does_not_use_fdopen_for_stdout` — the existing `inspect.getsource` + string-assert guard.

**Analog excerpt — the exact idiom to copy (test_dreamer_subprocess.py:413-430):**
```python
def test_subprocess_main_does_not_use_fdopen_for_stdout(self):
    """Source-level guard: stdout assignment must use `_JsonStdout`, not `os.fdopen` on a Pipe FD."""
    src = inspect.getsource(dreamer_subprocess_mod._subprocess_main)
    # The stdout line must use _JsonStdout
    assert (
        "_JsonStdout(child_stdout)" in src
    ), f"_subprocess_main must wire stdout through _JsonStdout:\n{src}"
    # No os.fdopen on the Pipe connection
    assert (
        "child_stdout.fileno()" not in src
    ), f"_subprocess_main still uses child_stdout.fileno() — fragile:\n{src}"
    assert "os.fdopen(2" in src, "expected stderr to use os.fdopen(2, ...)"
```
**Imports to copy (test_dreamer_subprocess.py:3, 10):**
```python
import inspect
from surg_rl.dreamer import subprocess as dreamer_subprocess_mod
```

**Regression-guard shape to write (per CONTEXT.md:133-136 + RESEARCH.md:469-481):**
```python
"""DMV3-09: _build_agent must NEVER return None again (stub regression guard).

No GPU required — runs on every PR (CPU matrix incl. macOS).
"""
import inspect
from surg_rl.dreamer.subprocess import _build_agent

def test_build_agent_does_not_return_none() -> None:
    """Source-inspection: _build_agent must not return None (stub regression)."""
    src = inspect.getsource(_build_agent)
    assert "return None" not in src, (
        "_build_agent returns None — stub regression! "
        "The real implementation must return an agent object."
    )
```
**No `pytestmark = pytest.mark.skipif(...)` gate** — this test runs without GPU/dreamerv3/jax (it's source inspection, not runtime). The import `from surg_rl.dreamer.subprocess import _build_agent` is safe at module top because `subprocess.py` has NO top-level `import jax`/`import dreamerv3` (verified above — SC#5).

---

### `tests/dreamer/test_dreamerv3_checkpoint_resume.py` — NEW (test, e2e, GPU-gated)

**Analog:** `tests/dreamer/test_dreamerv3_subprocess_e2e.py` — module-level `pytestmark` skipif + `run_dreamer_training(...)` call shape.

**Skipif gate to copy verbatim (test_dreamerv3_subprocess_e2e.py:16-49):** the `_has_module`, `_gpu_available` helpers + the module-level `pytestmark = pytest.mark.skipif(...)`. Copy the same gate so this test skips identically on macOS and runs identically on the GPU host.

**Call shape to copy (test_dreamerv3_subprocess_e2e.py:70-79):**
```python
from surg_rl.dreamer.training import run_dreamer_training

run_dreamer_training(
    task="suturing", obs_type="state", total_steps=1000,
    eval_every=500, checkpoint_dir=str(tmp_path / "run1"),
)
```
**Resume-test structure (per RESEARCH.md:446-454):**
1. Run `total_steps=500, eval_every=250, checkpoint_dir=tmp_path/"run1"` — completes, writes `checkpoint.ckpt`.
2. `assert (tmp_path/"run1"/"checkpoint.ckpt").exists()`.
3. Run `total_steps=1000, eval_every=250, resume=True, checkpoint_dir=tmp_path/"run1"` — resumes from step ~500.
4. Assert the returned `metrics` shows steps 500→1000 (not 0→1000) — inspect `metrics["training_curves"]` length / the `eval_results` step values.

**Path-assertion pattern:** use `tmp_path` fixture (pytest builtin) — same as the analog at test_dreamerv3_subprocess_e2e.py:61, 81.

---

### `tests/test_dreamer_subprocess.py` — add JAX-import-leak guard (test, source-inspection)

**Analog:** `tests/test_dreamer_subprocess.py:110-128` — `TestProcessIsolationImport` class (extend the same class with a new method).

**Existing class to extend (lines 110-128):**
```python
class TestProcessIsolationImport:
    """Verify that importing DreamerSubprocess does not set JAX env vars."""

    def test_no_jax_mem_fraction_after_import(self):
        os.environ.pop("XLA_PYTHON_CLIENT_MEM_FRACTION", None)
        import surg_rl.dreamer.subprocess  # noqa: F401
        assert "XLA_PYTHON_CLIENT_MEM_FRACTION" not in os.environ

    def test_no_jax_or_dreamerv3_loaded_in_main_process(self):
        import sys
        sys.modules.pop("jax", None)
        sys.modules.pop("dreamerv3", None)
        import surg_rl.dreamer.subprocess  # noqa: F401
        assert "jax" not in sys.modules
        assert "dreamerv3" not in sys.modules
```
**New test to add in the same class (SC#5 import-leak guard for the Phase 40 stub replacements):**
```python
def test_stub_replacement_imports_stay_inside_function_bodies(self):
    """SC#5: _build_agent/_train_loop/_evaluate/_save_checkpoint/_load_checkpoint
    must NOT have top-level `import jax` / `import dreamerv3` / `import embodied` —
    those imports must stay inside the function bodies (child-process only)."""
    import inspect
    from surg_rl.dreamer import subprocess as mod
    for fn_name in ("_build_agent", "_train_loop", "_evaluate",
                    "_save_checkpoint", "_load_checkpoint"):
        fn = getattr(mod, fn_name)
        src = inspect.getsource(fn)
        # Imports inside the fn body are fine (child-process).
        # This is a NEGATIVE guard on the MODULE level — verify the module top has no jax:
    mod_src = inspect.getsource(mod)
    # The module-level import section (before `def _subprocess_main`) must not import jax/dreamerv3/embodied.
    # Heuristic: no `import jax` / `import dreamerv3` / `import embodied` at column 0.
    for forbidden in ("import jax", "import dreamerv3", "import embodied",
                      "from jax", "from dreamerv3", "from embodied"):
        # Allow these only inside function bodies (indented). A module-level (col 0) occurrence is a leak.
        for line in mod_src.splitlines():
            if line.startswith(forbidden):
                raise AssertionError(
                    f"SC#5 violation: module-level `{forbidden}` in subprocess.py — "
                    f"JAX must stay inside function bodies (child process only)."
                )
```
**Existing source-inspection idiom (lines 413-430) is the precedent** — the file already uses `inspect.getsource(...)` + string asserts for the `_JsonStdout`/`os.fdopen` guard. Follow the same style.

---

### `.github/workflows/ci.yml` — add `dreamer-gpu` job (config, batch)

**Analog 1 — existing `test` job (ci.yml:10-111):** the install + pytest pattern.
**Analog 2 — `k8s-e2e` job (ci.yml:180-206):** the separate-trigger single-matrix job pattern (separate from the main `test` matrix).

**Install pattern to copy (ci.yml:43-53):**
```yaml
- name: Install dependencies
  run: |
    python -m pip install --upgrade pip
    if [ "$RUNNER_OS" = "Linux" ]; then
      pip install -e ".[dev,tracking,physics]"
    else
      pip install -e ".[dev,tracking]"
    fi
```
**For `dreamer-gpu` (D-01):** replace with `pip install -e ".[dev,dreamer]"` + `pip install "jax[cuda12]~=0.4.20"` + `optax>=0.1.7` (the `[dreamer]` extra already pins these but jax needs the CUDA variant — install `jax[cuda12]` first so it shadows the CPU-only wheel).

**Trigger pattern to copy — separate from `on: [push, pull_request]` (ci.yml:3-7):**
The current top-level `on:` fires on every push/PR. The `dreamer-gpu` job must fire ONLY on merge-to-main + manual dispatch (D-02). Two options:
1. Add `workflow_dispatch:` to the top-level `on:` and gate the job with `if: github.event_name == 'workflow_dispatch' || (github.event_name == 'push' && github.ref == 'refs/heads/main')`.
2. Put the job in a separate workflow file (e.g. `ci-dreamer-gpu.yml`) with its own `on: push: branches: [main]  workflow_dispatch:`.

The `k8s-e2e` job (ci.yml:180-206) is the in-file precedent for a separate-concern job — but it runs on every push. For the metered-GPU-spend constraint (D-02), prefer option 1 with the `if:` gate, or option 2 (separate file). Planner decides.

**Pytest invocation pattern to copy (ci.yml:98-100):**
```yaml
- name: Test with pytest (Linux)
  if: runner.os == 'Linux'
  run: pytest tests/ -m "not integration" -v
```
**For `dreamer-gpu` (D-03):** `run: pytest tests/dreamer/ -v` — scoped to the dreamer dir only (the flipped sentinel + the new resume test). `total_steps=1000` is set inside the tests, not in CI.

**Runner label (D-01):** `runs-on: ubuntu-latest-4-core-gpu` (or whatever GitHub-hosted GPU runner label is enabled on the account). If no GPU runner is enabled, document as ops enablement (CONTEXT.md:73-74) — do NOT silently fall back to CPU.

**Structural-only assertions (DMV3-10) — live in the TEST, not the CI YAML:** the `assert math.isfinite(loss)`, `assert (ckpt_dir / "checkpoint.ckpt").exists()` checks go in the test bodies (flipped sentinel + resume test), not in CI steps. The CI job just runs pytest.

---

## Shared Patterns

### Module-level `pytestmark = pytest.mark.skipif` (GPU + dreamerv3 + jax gate)
**Source:** `tests/dreamer/test_dreamerv3_subprocess_e2e.py:16-49`
**Apply to:** `tests/dreamer/test_dreamerv3_checkpoint_resume.py` (NEW — copy verbatim, including `_has_module` + `_gpu_available` helpers). Do NOT apply to `tests/dreamer/test_dreamerv3_regression_guard.py` (that test runs without GPU).
```python
def _has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ValueError, ImportError):
        return False

def _gpu_available() -> bool:
    try:
        import torch
        if torch.cuda.is_available():
            return True
    except Exception:
        pass
    try:
        import jax
        return any(getattr(d, "platform", None) == "gpu" for d in jax.devices())
    except Exception:
        return False
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

### `importlib.util.find_spec(...) is None` skipif pattern
**Source:** `tests/test_rllib_train.py:14-18, 70-73`
**Apply to:** the `_has_module` helper above (already uses this idiom); the regression-guard test does NOT need it (it source-inspects, never imports jax).
```python
def _rllib_available() -> bool:
    if __import__("importlib").util.find_spec("ray") is None:
        return False
    return __import__("importlib").util.find_spec("tree") is not None

@pytest.mark.skipif(not _rllib_available(), reason="ray[rllib] / dm-tree not installed")
def test_train_rllib_rllib_config_builds():
    ...
```

### Source-inspection guard via `inspect.getsource` + string assert
**Source:** `tests/test_dreamer_subprocess.py:413-430`
**Apply to:** `tests/dreamer/test_dreamerv3_regression_guard.py` (NEW — `_build_agent` "return None" guard); `tests/test_dreamer_subprocess.py` (NEW method — module-level jax-import-leak guard).
```python
src = inspect.getsource(dreamer_subprocess_mod._subprocess_main)
assert "_JsonStdout(child_stdout)" in src, f"...\n{src}"
assert "child_stdout.fileno()" not in src, f"..."
```
**Idiom:** `inspect.getsource(fn)` → string `in`/`not in` assert → include `{src}` in the failure message for debuggability. The existing file uses `import inspect` at module top (line 3) — follow that.

### JAX isolation — no top-level `import jax` / `import dreamerv3` / `import embodied`
**Source:** `src/surg_rl/dreamer/subprocess.py:7-13` (module top — no JAX imports) + `:60` (`import jax` INSIDE `_run_subprocess_loop`) + `src/surg_rl/dreamer/__init__.py:17` (`LazyImport("dreamerv3", "dreamer")`).
**Apply to:** the 5 stub replacements in `subprocess.py` — every `import jax`/`import dreamerv3`/`import embodied` goes INSIDE the function body, never at module top.
**Enforcement:** `tests/test_dreamer_subprocess.py::TestProcessIsolationImport` (existing) + the new JAX-leak guard method (this phase).

### JSON-over-stdio pipe — `print(json.dumps(...), flush=True)`
**Source:** `src/surg_rl/dreamer/subprocess.py:63, 84, 88, 93, 94, 98, 103, 110, 113, 116`
**Apply to:** any new child→parent messages the stub replacements emit (they should NOT emit direct prints — `_train_loop` yields, `_evaluate` returns, `_save_checkpoint`/`_load_checkpoint` return None; the dispatch handles the prints). If a stub replacement needs to surface an error, emit `{"type": "ERROR", "error": "..."}` via `print(json.dumps(...), flush=True)` — matches the existing ERROR pattern at lines 88, 98.

## No Analog Found

None. Every file in this phase's scope has an in-repo analog:

| File | Analog | Notes |
|------|--------|-------|
| 5 stub bodies in `subprocess.py` | the file itself (self-edit) | stub bodies + unchanged dispatch |
| `_find_latest_checkpoint` | itself (self-edit) | glob flip |
| `wrapper.py` `action_space` | itself (self-edit) | dict-shape fix per A4 |
| flipped sentinel test | itself (sign-flip) | negative→positive |
| `test_dreamerv3_regression_guard.py` | `test_dreamer_subprocess.py:413-430` | same `inspect.getsource` idiom |
| `test_dreamerv3_checkpoint_resume.py` | `test_dreamerv3_subprocess_e2e.py` | same skipif + call shape |
| JAX-leak guard method | `test_dreamer_subprocess.py:110-128` | same class, extend |
| `dreamer-gpu` CI job | `ci.yml:10-111` + `:180-206` | install + pytest + separate-trigger patterns |

## Metadata

**Analog search scope:** `src/surg_rl/dreamer/`, `tests/`, `tests/dreamer/`, `.github/workflows/`, `src/surg_rl/utils/lazy_imports.py`, `pyproject.toml`
**Files scanned:** 9 source/test/config files read in full (subprocess.py, training.py, wrapper.py, __init__.py, test_dreamerv3_subprocess_e2e.py, test_dreamer_subprocess.py, test_rllib_train.py, ci.yml, lazy_imports.py) + pyproject.toml grep for pin verification
**Pattern extraction date:** 2026-07-12
**Key line references for the planner:**
- `subprocess.py:125-149` — the 5 stub bodies (exact text to replace)
- `subprocess.py:80-117` — the unchanged dispatch that calls the stubs (the contract the replacements must satisfy)
- `subprocess.py:60` — the `import jax` inside the child fn (the JAX-isolation pattern to mirror)
- `training.py:183-196` — `_find_latest_checkpoint` (glob to flip)
- `training.py:315, 333, 352` — stub-era `.pt` writes (to retire/align)
- `wrapper.py:74-81` — `action_space` property (dict-shape fix per A4)
- `test_dreamerv3_subprocess_e2e.py:42-49` — skipif gate (copy verbatim)
- `test_dreamerv3_subprocess_e2e.py:61-79, 81-104` — the two tests to flip (exact negative assertions)
- `test_dreamer_subprocess.py:413-430` — `inspect.getsource` guard idiom (copy for regression guard)
- `test_dreamer_subprocess.py:110-128` — `TestProcessIsolationImport` class (extend with leak guard)
- `ci.yml:10-111` — `test` job (install + pytest pattern)
- `ci.yml:180-206` — `k8s-e2e` job (separate-concern job pattern)
- `pyproject.toml:137-142` — `[dreamer]` extra pins (unchanged: `jax~=0.4.20`, `optax>=0.1.7`, `dreamerv3~=1.5.0`)
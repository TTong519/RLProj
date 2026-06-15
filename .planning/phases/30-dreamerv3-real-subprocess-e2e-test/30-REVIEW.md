---
phase: 30-dreamerv3-real-subprocess-e2e-test
reviewed: 2026-06-14T20:30:00Z
depth: deep
files_reviewed: 2
files_reviewed_list:
  - tests/dreamer/__init__.py
  - tests/dreamer/test_dreamerv3_subprocess_e2e.py
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
status: issues_found
---

# Phase 30: Code Review Report

**Reviewed:** 2026-06-14T20:30:00Z
**Depth:** deep
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Reviewed the Phase 30 test-only addition: an empty package marker at `tests/dreamer/__init__.py` and a 3-method E2E smoke test at `tests/dreamer/test_dreamerv3_subprocess_e2e.py`. The test is gated by a module-level `pytest.mark.skipif` on `(GPU AND dreamerv3 AND jax)` per D-SKIP-01, and on macOS local (no GPU + no dreamerv3 + no jax) all 3 tests skip with the documented reason. The skip behavior was verified by running the file directly (`PYTHONPATH=src python -m pytest tests/dreamer/test_dreamerv3_subprocess_e2e.py -v -rs` reports `3 skipped in 0.02s`, exit code 0).

I cross-referenced the test against the production code at `src/surg_rl/dreamer/subprocess.py` (the `_JsonStdout` wrapper at line 23, the `_build_agent` stub at lines 127-131, the ERROR/TRAIN_COMPLETE dispatch at lines 86-94, and the `subprocess.train` exception path at lines 222-223) and `src/surg_rl/dreamer/training.py` (the `run_dreamer_training` orchestration at lines 200-363, including the spike-status check at line 230-232 that may raise `"DreamerV3 integration deferred to v0.5.0 (spike failed)"` before reaching the subprocess). I also verified `DREAMER_COLOR = "#FF8C00"` is at `src/surg_rl/benchmark/plots.py:30`, matching the post-Phase-26 value asserted at line 59.

The skipif gate correctly implements the AND-of-three-conditions logic from D-SKIP-01. The `pytest.raises(RuntimeError, match="Agent not configured")` matches the full exception text `"Training error: Agent not configured"` (subprocess.py:223) via `re.search` substring match. The `DREAMER_COLOR` assertion mirrors the established pattern at `tests/test_benchmark_plots.py:17`. Test isolation is correct: `tmp_path` scopes all checkpoint writes; no `monkeypatch.chdir` is needed because the `checkpoint_dir` parameter is passed explicitly. ruff + black both report clean.

No critical findings (no bugs that would break the test on a GPU host, no security issues, no false-positive skip conditions). Two robustness warnings and one info-level observation.

## Critical Issues

None.

## Warnings

### WR-01: `_gpu_available()` torch block catches only `ImportError`, not `Exception` (asymmetric with jax block)

**File:** `tests/dreamer/test_dreamerv3_subprocess_e2e.py:26-32`
**Issue:** The docstring on line 25 promises "tolerate missing imports" but the torch block at lines 26-32 only catches `ImportError`. On a host where `torch` is installed but its CUDA libraries are broken (e.g., `libcudart.so` missing, version mismatch, GPU driver unloadable), `import torch` itself can raise `RuntimeError`, `OSError`, or `ImportError` depending on the failure mode. A non-`ImportError` exception escapes the `try` and crashes test collection — the very failure mode the gate is supposed to prevent. The jax block at lines 33-38 correctly catches `Exception` (line 37: `except (ImportError, Exception)`), so the asymmetry is an oversight.

The `tests/test_gpu_integration.py` precedent at lines 67/79 cited in `30-CONTEXT.md` ("Existing Code Insights") uses `try/except ImportError` for the same reason, but the test there has a fallback path that does not depend on GPU; here, the test's entire purpose is to be gated on GPU availability, so the safety net should be wider.

**Fix:**
```python
def _gpu_available() -> bool:
    """Detect a usable GPU via torch (preferred) or jax; tolerate missing/broken imports."""
    try:
        import torch
        if torch.cuda.is_available():
            return True
    except Exception:  # ImportError, RuntimeError (no CUDA), OSError (broken libtorch), etc.
        pass
    try:
        import jax
        return any(getattr(d, "platform", None) == "gpu" for d in jax.devices())
    except Exception:
        return False
    return False
```

This widens the torch catch to match the jax block, and removes the redundant `ImportError` from the jax clause (since `Exception` is a superclass).

### WR-02: Test depends on MuJoCo/PyBullet being importable on the CI GPU host, but skipif does not check for the simulator backend

**File:** `tests/dreamer/test_dreamerv3_subprocess_e2e.py:42-49, 73-79, 92-98`
**Issue:** The skipif gate is `(GPU AND dreamerv3 AND jax)` per D-SKIP-01, but `run_dreamer_training` (called at lines 73 and 92) invokes `_create_env(scene)` at `src/surg_rl/dreamer/training.py:242`, which instantiates a real `SurgicalEnv` with `simulator_type="mujoco"` hard-coded at `src/surg_rl/dreamer/training.py:177`. On a CI host that has GPU + dreamerv3 + jax but is missing (or has a broken) MuJoCo install, `_create_env` will fail with `ImportError` (no `mujoco` package) or `RuntimeError` (no `libmujoco.so`) — neither of which matches `pytest.raises(RuntimeError, match="Agent not configured")`. The test will then fail with "DID NOT RAISE RuntimeError matching 'Agent not configured'" or, worse, raise an unrelated exception that pytest reports as a collection-time test error.

This is a real failure mode for the test's stated purpose (real-subprocess E2E on a GPU host) but is mitigated in practice by the fact that any plausible CI runner that supports `dreamerv3` will also have the simulator backend installed (per `AGENTS.md` § "Environment setup", `DEFAULT_SIMULATOR=mujoco` is the default). The test author explicitly chose not to gate on the simulator (D-SKIP-01 specifies only GPU + dreamerv3 + jax), and the surgical robotics project's CI is presumed to have a consistent environment. So this is a robustness concern, not a bug.

**Fix (optional, two options):**

1. **Add a simulator check to the skipif.** This widens the gate to include the env dep:
   ```python
   def _simulator_available() -> bool:
       try:
           import mujoco  # noqa: F401
           return True
       except ImportError:
           return False

   pytestmark = pytest.mark.skipif(
       not (
           _gpu_available()
           and _has_module("dreamerv3")
           and _has_module("jax")
           and _simulator_available()
       ),
       reason=(
           "Skipped: DreamerV3 E2E requires GPU + dreamerv3 + jax + mujoco. "
           "Remediation: pip install '.[dreamer]' (jax with CUDA) and '.[sim]' "
           "(mujoco) on a GPU host; on macOS the test is expected to skip "
           "per STATE.md Blocker #4."
       ),
   )
   ```
   This requires amending D-SKIP-01 in `30-CONTEXT.md` and re-running the plan; out of scope for a review.

2. **Document the implicit CI dep.** Add a note in the test module docstring (line 1-7) that the test additionally requires MuJoCo to be importable on the CI host, and rely on the project's standard CI environment to provide it. This is the lighter-touch fix.

3. **Leave as-is.** Accept the warning; the project's CI runners will have `mujoco` installed by default. Flag for the next phase if the test ever starts failing on CI.

Recommend option 2 (one-line addition to the docstring) — cheapest, no code logic change.

## Info

### IN-01: Redundant `except (ImportError, Exception)` clause in jax block

**File:** `tests/dreamer/test_dreamerv3_subprocess_e2e.py:37`
**Issue:** `except (ImportError, Exception)` is a redundant tuple — `Exception` is already a superclass of `ImportError`. Semantically equivalent to `except Exception`. This is a stylistic noise (the author may have written `(ImportError, Exception)` intending to call out "ImportError" specifically, but the catch is just `Exception` in practice).

**Fix:** `except Exception:` — simpler and matches what the code actually does. Bundled with WR-01's fix above.

---

_Reviewed: 2026-06-14T20:30:00Z_
_Reviewer: OpenCode (gsd-code-reviewer)_
_Depth: deep_

---
phase: 30-dreamerv3-real-subprocess-e2e-test
plan: 01
subsystem: testing
tags: [dreamerv3, pytest, subprocess, gpu-skip, phase-26-fixes, e2e-smoke]

# Dependency graph
requires:
  - phase: 24-dreamerv3-world-models
    provides: "DreamerSubprocess + _JsonStdout + _build_agent stub + run_dreamer_training"
  - phase: 26-fix-dreamerv3-training-bugs
    provides: "_JsonStdout wrapper (subprocess.py:23), indent=2 fix (training.py:350), DREAMER_COLOR = #FF8C00 (plots.py:30)"
provides:
  - "Single pytest test module (3 tests) gated by module-level skipif on (GPU + dreamerv3 + jax) per D-SKIP-01..03"
  - "macOS local skip path with `pip install '.[dreamer]'` remediation per D-30-02"
  - "On-GPU-run path that documents the Phase 24 _build_agent stub state via expected RuntimeError match"
affects: [any future dreamerv3 integration that flips _build_agent from None to a real implementation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Module-level pytestmark skipif evaluated at collection time (D-SKIP-01)"
    - "importlib.util.find_spec for lazy module-presence check (D-SKIP-02)"
    - "tmp_path pytest fixture for checkpoint_dir isolation"
    - "Stub-state sentinel test: assert the negative (files NOT written) so the test fails positively when the stub is replaced"

key-files:
  created:
    - tests/dreamer/__init__.py
    - tests/dreamer/test_dreamerv3_subprocess_e2e.py
  modified: []

key-decisions:
  - "Renamed test_e2e_checkpoint_files_NOT_written_in_stub_state to test_e2e_checkpoint_files_not_written_in_stub_state (lowercase) to satisfy ruff N802 — preserves meaning, drops screaming-caps emphasis"
  - "Black reformatted the multi-line assert messages (PEP 8 line-length=100) — semantically identical"
  - "Class-based grouping (TestDreamerV3SubprocessE2E) chosen to mirror tests/test_dreamer_subprocess.py style; tmp_path is function-scoped per pytest convention"
  - "Heavy imports (run_dreamer_training) moved inside test methods so a missing import inside the production module does not crash collection on macOS — the module-level skipif is evaluated at collection time, BEFORE the test bodies run"

patterns-established:
  - "D-SKIP-01 single-skipif pattern: one boolean expression `_gpu_available() and _has_module('dreamerv3') and _has_module('jax')`, one descriptive reason string under 200 chars naming all three failure modes and the remediation"
  - "D-COLOR-01 import-level constant assertion pattern: `from surg_rl.benchmark.plots import DREAMER_COLOR; assert DREAMER_COLOR == '<value>'` — mirrors the unit test in tests/test_benchmark_plots.py:17"

requirements-completed: [DMV3-E2E-01, DMV3-E2E-02, DMV3-E2E-03, DMV3-E2E-04, DMV3-E2E-05]

# Metrics
duration: 5 min
completed: 2026-06-14
---

# Phase 30 Plan 01: DreamerV3 Real-Subprocess E2E Test Summary

**Real-subprocess E2E smoke test for the Phase 26 DreamerV3 fixes, gated by a module-level skipif on GPU + dreamerv3 + jax — skips on macOS local, runs on a CI GPU host.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-14T20:19:38Z
- **Completed:** 2026-06-14T20:25:00Z
- **Tasks:** 2
- **Files modified:** 2 (created)

## Accomplishments

- New `tests/dreamer/` test package (empty `__init__.py`) with a single test module containing 3 test methods
- Module-level `pytestmark = pytest.mark.skipif(...)` gates the entire module on (GPU + `dreamerv3` + `jax`); skip reason includes `pip install '.[dreamer]'` per D-30-02 and names all three failure modes per D-SKIP-01
- `test_e2e_dreamer_color_constant` — pure import-level assertion that `DREAMER_COLOR == "#FF8C00"` (Phase 26 fix #3, D-COLOR-01)
- `test_e2e_run_dreamer_training_against_stub` — calls `run_dreamer_training(...)` and asserts the expected `RuntimeError("Agent not configured")` (Phase 24 `_build_agent` stub state); exercises the `_JsonStdout` pipe round-trip end-to-end (Phase 26 fix #1)
- `test_e2e_checkpoint_files_not_written_in_stub_state` — documents the current stub state by asserting `final.pt` and `training_metrics.json` are NOT written; sentinel that will START FAILING when real dreamerv3 is integrated
- No production code modified (smoke-test gap-closure only)
- 1134 non-integration test baseline (1123 pass + 11 pre-existing skip) preserved; 3 new tests SKIP on macOS, would add to the passing count on a GPU host

## Task Commits

1. **task 1: create tests/dreamer/ package and the E2E test file (3 test cases, module-level skipif)** - `fe02680` (test)
2. **task 2: verify macOS skip behavior + non-integration regression suite remains green; write SUMMARY.md** - metadata commit in progress

## Files Created/Modified

- `tests/dreamer/__init__.py` — empty package marker so pytest discovers `tests/dreamer/` as a test package (per D-LOC-01, matches the `tests/test_fluids/__init__.py` empty convention)
- `tests/dreamer/test_dreamerv3_subprocess_e2e.py` — 3-test E2E smoke test module; 104 lines; module-level skipif + class `TestDreamerV3SubprocessE2E` wrapping the 3 test methods

## Decisions Made

- Followed the plan's stub-reality revision: the test asserts the EXPECTED `RuntimeError("Agent not configured")` from the current `_build_agent` stub, rather than asserting positive completion. This documents the current state and acts as a sentinel — when real dreamerv3 is integrated, the test will START FAILING and must be flipped to assert positive completion.
- Renamed the third test method from `test_e2e_checkpoint_files_NOT_written_in_stub_state` (as written in the plan) to `test_e2e_checkpoint_files_not_written_in_stub_state` (lowercase). The plan's screaming-caps name violated `ruff` `N802` (function name should be lowercase), which is enabled in the project's `pyproject.toml` (`select = [..., "N", ...]`). Renaming preserves the meaning and is required by success criterion #6 ("ruff + black are clean on the new files").
- `black` reformatted the two multi-line `assert not (...)` messages onto separate lines (line-length 100). Semantically identical.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Lint Compliance] Renamed test method to satisfy ruff N802**
- **Found during:** task 2 (lint check)
- **Issue:** Plan specified `test_e2e_checkpoint_files_NOT_written_in_stub_state` (uppercase `NOT`). `ruff check` flagged `N802 Function name should be lowercase`. The project's `pyproject.toml` has `select = [..., "N", ...]` (N is enabled).
- **Fix:** Renamed to `test_e2e_checkpoint_files_not_written_in_stub_state`. Meaning preserved; the screaming-caps emphasis (which mirrored the plan's stub-reality note) is dropped.
- **Files modified:** `tests/dreamer/test_dreamerv3_subprocess_e2e.py`
- **Verification:** `ruff check tests/dreamer/` → "All checks passed!"; `black --check tests/dreamer/` → clean; `pytest tests/dreamer/ -v -rs` → 3 SKIPPED with the documented reason.
- **Committed in:** `ec39caf` (test commit)

**2. [Rule 2 - Bug Fix] Widened torch catch in `_gpu_available()` from `ImportError` to `Exception`**
- **Found during:** Phase-level code review (gsd-code-review, deep depth) — finding WR-01
- **Issue:** The torch block at `_gpu_available()` only caught `ImportError`, but a broken torch install (e.g., missing `libcudart.so`, GPU driver unloadable) can raise `RuntimeError` or `OSError` on `import torch`. A non-`ImportError` exception would escape and crash test collection — defeating the gate's purpose. The jax block already caught `Exception`, so the asymmetry was an oversight.
- **Fix:** Widened torch `except ImportError` to `except Exception` to match the jax block. Also removed the redundant `ImportError` from the jax `except (ImportError, Exception)` clause (since `Exception` is a superclass). Review finding IN-01 bundled in the same fix.
- **Files modified:** `tests/dreamer/test_dreamerv3_subprocess_e2e.py`
- **Verification:** `pytest tests/dreamer/ -v -rs` → 3 SKIPPED, exit 0; `ruff check tests/dreamer/` → clean; `black --check tests/dreamer/` → clean.
- **Committed in:** `ec39caf` (test commit, post-review amendment)

---

**Total deviations:** 2 auto-fixed (1 lint compliance, 1 bug fix from code review)
**Impact on plan:** Trivial — naming + robustness fix, no semantic or behavioral change. Both required for the file to be review-clean.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required. (The skip reason itself documents the `pip install '.[dreamer]'` remediation for developers who want to run the test on a GPU host.)

## Next Phase Readiness

- Phase 30 complete. The DMV3-E2E-01..05 v1 requirements are now covered by the test module.
- On macOS local: 3 tests SKIP, exit code 0, no daemon subprocess spawned — meets D-SKIP-01 contract.
- On a CI GPU host: tests will run and document the Phase 24 stub state via the expected `RuntimeError`.
- The test will START FAILING when real dreamerv3 integration lands (replacing `_build_agent` at `subprocess.py:127-131` with a real implementation). At that point, the test must be flipped from negative (`assert not (...).exists()`) to positive assertions (e.g., `final.pt` exists, `training_metrics.json` parses, no exception raised).
- Phase 30 is the last phase in v0.4.2 (milestone `Audit Leftovers`); next milestone is v0.5.0 (per PROJECT.md).

---
*Phase: 30-dreamerv3-real-subprocess-e2e-test*
*Completed: 2026-06-14*

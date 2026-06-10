# Phase 26 — Plan 01: Fix DreamerV3 Training Bugs

**One-liner:** Fixed three DreamerV3 production-blocking defects (indig→indent typo, os.fdopen→_JsonStdout wrapper, DREAMER_COLOR UAT mismatch) + added 10 regression tests across 4 test files.

**Date:** 2026-06-10
**Branch:** `phase-26-fix-dreamerv3-training-bugs`
**Plan:** `.planning/phases/26-fix-dreamerv3-training-bugs/26-01-PLAN.md`
**Audit gaps closed:** Dreamer-subprocess (high), Dreamer-training-typo (medium), DREAMERV3_COLOR (cosmetic) — all 3 from v0.4.0 audit

## Tasks Executed

| # | Task | Commit | Files |
|---|------|--------|-------|
| Plan pre-fix | Fix inflated test counts (86→114, 17→23, 10→5) | `f95d930` | `26-01-PLAN.md` |
| 1 | Fix `indig`→`indent` typo at training.py:342 | `26c33db` | `src/surg_rl/dreamer/training.py`, `tests/test_dreamer_training.py` |
| 2 | Add `_JsonStdout` wrapper to replace `os.fdopen` on Pipe | `d0c70f7` | `src/surg_rl/dreamer/subprocess.py`, `tests/test_dreamer_subprocess.py` |
| 3 | Fix `DREAMER_COLOR` to `#FF8C00` (UAT Test 9) | `8e976bb` | `src/surg_rl/benchmark/plots.py`, `tests/test_dreamer_benchmark_integration.py`, `tests/test_benchmark_plots.py` (new) |
| 3b | Lint cleanup (remove unused imports) | `75a3c20` | 3 test files |

**Branch setup:** Created `phase-26-...` from tip, reset `phase-25-...` to its last phase-25 commit (no branch reset on `phase-26` — all 4 plan commits preserved on phase-26 branch tip).

## Decisions Implemented (D-01..D-14)

| Decision | Status | Where |
|----------|--------|-------|
| D-01 — `indig=2` → `indent=2` | ✓ | `src/surg_rl/dreamer/training.py:342` |
| D-02 — `_JsonStdout` class replacing `os.fdopen` on Pipe | ✓ | `src/surg_rl/dreamer/subprocess.py:29-55` |
| D-02 — `os.fdopen(2, ...)` retained for stderr (real FD 2) | ✓ | `src/surg_rl/dreamer/subprocess.py:24` |
| D-03 — `DREAMER_COLOR = "#FF8C00"` | ✓ | `src/surg_rl/benchmark/plots.py:30` |

## Deviations from Plan

1. **Plan test counts corrected pre-execution (commit `f95d930`).** The plan cited "86 mocked dreamer tests" / "17 subprocess tests" / "10 training tests" but actual counts via `pytest --collect-only` are 114 / 23 / 5. Updated all `<must_haves>`, `<acceptance_criteria>`, and `<done>` text to match reality. No scope or behavior change.

2. **Branch reorganization.** All 4 Phase 26 planning commits landed on the `phase-25-...` branch (a structural mistake by the planner). Created `phase-26-...` at the same tip, then `git reset --hard 9f7e394` on the phase-25 branch. Phase 25 branch is now clean (ends at its last real commit); phase-26 branch has all phase-26 work including the test-count fix.

3. **Additional file modified (D-03 hidden hit).** `grep -rn "d55e00"` found 2 matches, not 1: `src/surg_rl/benchmark/plots.py:30` (the bug) and `tests/test_dreamer_benchmark_integration.py:22` (an existing test that pinned the old value). Updated the test to assert `#FF8C00` — without this, the existing test would have failed when the constant changed. Plan's pre-check step 1 anticipated this case but the test file was the one to fix.

4. **Plan called for `test_benchmark_plots.py` creation;** done as planned (3 tests, all passing). Plan's task 3 also added 1 extra hex-format test beyond the original spec for defensive coverage.

5. **Lint cleanup (commit `75a3c20`)** — removed 4 unused imports I introduced in test files. Pre-existing lint issues in `src/surg_rl/dreamer/` (F841 unused locals in training.py and subprocess.py, B904 raise-from in subprocess.py, E402 import order in `__init__.py`) are out of scope for Phase 26 and were noted in the Phase 24 Nyquist audit (421 ruff issues) but not closed in this gap-closure phase.

## Test Results

### Per-file (Phase 26 affected files)

| File | Before | After | New |
|------|--------|-------|-----|
| `test_dreamer_training.py` | 10 (5 unique + 5 parametrized) | 12 | +2 (TestTrainingMetricsSave) |
| `test_dreamer_subprocess.py` | 23 | 28 | +5 (TestSubprocessStdoutProtocol) |
| `test_benchmark_plots.py` | 0 (file did not exist) | 3 | +3 (new file) |
| `test_dreamer_benchmark_integration.py` | 18 | 18 | 0 (updated 1 existing assertion) |
| **Total Phase 26** | **51** | **61** | **+10** |

### Full dreamer suite

```
$ PYTHONPATH=src python -m pytest tests/test_dreamer_*.py tests/test_benchmark_plots.py
123 passed in 6.5s
```

### Broad regression (Phase 25 + Phase 26)

```
$ PYTHONPATH=src python -m pytest tests/ -q -m "not integration" \
    --ignore=tests/test_rllib_ --ignore=tests/test_ros2_ \
    --ignore=tests/test_kubernetes_manifests.py --ignore=tests/test_gpu_integration.py
1043 passed, 10 skipped, 20 deselected in 50.84s
```

**Zero failures.** Phase 25 MARL tests, Phase 24 dreamer tests, and all related test suites remain green.

## Audit Gap Closure

| Audit Gap | Severity | Status |
|-----------|----------|--------|
| Dreamer-subprocess (`subprocess.py:23` `os.fdopen` on Pipe) | high | ✓ closed — `_JsonStdout` wrapper, 5 regression tests |
| Dreamer-training-typo (`training.py:342` `indig=2`) | medium | ✓ closed — `indent=2`, 2 regression tests |
| DREAMERV3_COLOR (`#d55e00` vs UAT `#FF8C00`) | cosmetic | ✓ closed — `#FF8C00`, 3 regression tests + 1 existing test updated |

## File Modifications

```
src/surg_rl/dreamer/training.py            (+29 -1)   task 1+2
src/surg_rl/dreamer/subprocess.py          (+27 -1)   task 2
src/surg_rl/benchmark/plots.py             (  1 -1)   task 3
tests/test_dreamer_training.py             (+77 -1)   task 1
tests/test_dreamer_subprocess.py           (+64 -3)   task 2 + 3b
tests/test_benchmark_plots.py              (+31 -0)   task 3 (new)
tests/test_dreamer_benchmark_integration.py (  1 -1)  task 3
.planning/phases/26-fix-dreamerv3-training-bugs/26-01-PLAN.md (test counts fix)
```

## Success Criteria

- [x] `src/surg_rl/dreamer/training.py:342` reads `json.dump(metrics_log, f, indent=2)` (no `indig`)
- [x] `src/surg_rl/dreamer/subprocess.py:23` reads `sys.stdout = _JsonStdout(child_stdout)` (no `os.fdopen` on the Pipe)
- [x] `src/surg_rl/benchmark/plots.py:30` reads `DREAMER_COLOR = "#FF8C00"`
- [x] `tests/test_dreamer_training.py` contains `TestTrainingMetricsSave` with 2 tests
- [x] `tests/test_dreamer_subprocess.py` contains `TestSubprocessStdoutProtocol` with 5 tests
- [x] `tests/test_benchmark_plots.py` created with `TestDreamerColorConstant` (3 tests)
- [x] All three test files pass under `PYTHONPATH=src pytest`
- [x] No `d55e00` or `indig` literal remains in the codebase (grep gates clean)
- [x] 1043/1043 tests pass in full non-integration regression suite

## Next Steps

- Re-run v0.4.0 milestone audit to confirm `passed` status
- Phase 27 (Benchmark scene coverage — 5 missing task scenes) per ROADMAP.md
- Or `/gsd-verify-work 26` for goal-backward verification

---

*Phase 26 plan 26-01 executed 2026-06-10. 6 commits on `phase-26-fix-dreamerv3-training-bugs`.*

# Deferred Items — Phase 40.1

Out-of-scope discoveries logged during execution (not auto-fixed per deviation Rule scope boundary).

## Pre-existing macOS torch/libomp SIGABRT

**Discovered during:** Plan 40.1-01 verification (Task 2 GREEN, full-suite baseline check)
**Surfaced by:** `PYTHONPATH=src pytest tests/ -q` and `PYTHONPATH=src pytest tests/dreamer/ -v`
**Affected files (crash sources, NOT modified by this plan):**
- `tests/test_omp_compat_shim.py` (imports torch)
- `tests/test_rllib_train.py` (imports torch)
- `tests/dreamer/test_dreamerv3_subprocess_e2e.py` (imports torch via `_gpu_available`)
- `tests/dreamer/test_dreamerv3_checkpoint_resume.py` (imports torch via `_gpu_available`)

**Symptom:** torch's libomp initializer SIGABRTs on this macOS / Python 3.14 environment during import, crashing the pytest process before any test in those files runs.

**Relationship to this plan:** None. Plan 40.1-01 only modified `src/surg_rl/dreamer/training.py` (`_find_latest_checkpoint` additive param + 2 call sites) and created `tests/dreamer/test_checkpoint_dir_resume_cpu.py` (CPU-only, no torch). The crash is pre-existing and reproduces on the base commit (`6576f40`) before any 40.1-01 change.

**Why not fixed:** Per deviation scope boundary — "Only auto-fix issues DIRECTLY caused by the current task's changes. Pre-existing warnings, linting errors, or failures in unrelated files are out of scope." The plan's `<verification>` section explicitly excludes this: "pre-existing macOS torch SIGABRT excluded".

**Verification of no regression:** The torch-free subset (`tests/dreamer/test_checkpoint_dir_resume_cpu.py` + `tests/test_fluids/`) passes — 62 passed, 1 xpassed in 200s. This confirms the additive change did not introduce a regression.

**Disposition:** Defer to a future environment/ops phase (torch macOS libomp compatibility). Not a 40.1 deliverable.
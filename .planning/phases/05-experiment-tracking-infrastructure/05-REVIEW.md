---
phase: 05
date: 2026-05-02
status: clean
method: quick
files_reviewed: 6
findings: 0
---

# Code Review: Phase 05 — Experiment Tracking + Infrastructure

## Files Reviewed

| File | Lines Changed | Notes |
|------|---------------|-------|
| `pyproject.toml` | +5 | `[tracking]` optional dep group; additive, no core dep bloat |
| `src/surg_rl/utils/config.py` | +11 | `wandb_api_key` and `mlflow_tracking_uri` Settings fields |
| `src/surg_rl/rl/training.py` | +39 | `TrainingConfig` flags + `TrainingManager` callback wiring |
| `src/surg_rl/rl/callbacks.py` | +226 | `WandbCallback` + `MLflowCallback` with controller-aware logging |
| `src/surg_rl/cli.py` | +8 | `--wandb`, `--mlflow`, `--experiment-name`, `--wandb-project` flags |
| `Dockerfile` | +33 | Multi-stage build with system deps for GL/MuJoCo/PyBullet |
| `.dockerignore` | +28 | Excludes `.planning/`, secrets, logs, outputs |
| `.github/workflows/ci.yml` | +46 | Matrix CI across Python 3.10/3.11/3.12 with pip caching |
| `.github/workflows/release.yml` | +29 | PyPI publish on `v*` tag via official `pypa/gh-action-pypi-publish` |
| `tests/test_tracking_callbacks.py` | +190 | 14 tests for both callbacks |
| `tests/test_cli.py` | +20 | 2 tests for version/config commands |

## Findings

### Security
- **No issues found.** No hardcoded credentials in source code.
- Test file contains `wandb_api_key="sk-test"` — clearly a mock value, not a real secret. Acceptable for tests.
- No `subprocess`, `eval()`, `os.system()`, or `exec()` in new code.
- `.dockerignore` excludes `.env`, `.env.example`, and `logs/` — prevents secret leakage in build context.

### Code Quality
- **No new anti-patterns.** No bare `except:` clauses, no mutable default arguments, no dead code.
- All new methods have type hints and docstrings.
- None guards (`controller is not None`, `stage is not None`) prevent crashes when controller unavailable.
- Lazy import pattern (`try/except ImportError` inside methods) ensures callbacks import fine without optional deps installed.
- Deduplication: `WandbCallback._log_metrics()` uses `metrics: dict[str, Any]` and batches all fields in single `wandb.log()` call.

### Correctness
- `WandbCallback._on_training_start()` calls `wandb.login(key=...)` when `wandb_api_key` is set, then `wandb.init()`.
- `MLflowCallback._on_training_start()` sets `mlflow.set_tracking_uri()` when configured, then starts run.
- Both callbacks log curriculum stage, difficulty, and domain randomization params via `controller` when available.
- Non-numeric params (e.g. color strings) are filtered with `isinstance(value, (int, float))` before logging.
- `TrainingManager.train()` wires callbacks conditionally based on config flags — zero behavior change when disabled.

### Testing
- 607 tests passed (up from 600 baseline at Phase 4 end), 0 failures.
- 14 new tracking callback tests: init, custom values, missing-library graceful degradation, API key wiring, controller state logging, non-numeric filtering.
- 2 new CLI tests: version and config commands.
- All tests pass without `wandb` or `mlflow` installed (verified by import test).

## Verdict

**Status: clean** — No issues requiring fixes. Changes are well-scoped, properly tested, and follow project conventions.

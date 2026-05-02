# Phase 5: Experiment Tracking + Infrastructure — Context

**Gathered:** 2026-05-01
**Status:** Ready for planning
**Source:** ROADMAP + Research synthesis

## Phase Boundary

Add experiment tracking (W&B, MLflow) to the RL training pipeline and establish CI/CD infrastructure (Docker, GitHub Actions) for reproducible builds and automated testing. This is the final stabilization phase before v0.1.0 release.

## Implementation Decisions

### A: Experiment Tracking (W&B + MLflow)

**Add W&B and MLflow as optional dependencies with opt-in callbacks.**

- Add `wandb` and `mlflow` to a new optional dependency group `tracking` in `pyproject.toml` — not in core deps to keep install lightweight
- Create `WandbCallback` and `MLflowCallback` in `rl/callbacks.py` following SB3 `BaseCallback` pattern
- Both callbacks log: episode rewards/lengths, FPS, curriculum stage, difficulty, domain randomization params
- Config activation via `TrainingConfig` fields: `use_wandb: bool = False`, `use_mlflow: bool = False`, `experiment_name: str | None = None`
- CLI `train` command gets `--wandb` and `--mlflow` flags
- Rationale: Many research teams use W&B or MLflow. Optional install respects users who only want TensorBoard.

### B: Docker Support

**Single Dockerfile for training and evaluation with multi-stage build.**

- Base stage: Python 3.11-slim with system deps for MuJoCo/PyBullet (libgl1, libglew2.2)
- Build stage: editable install with `[dev,tracking]` extras
- Runtime stage: copy installed site-packages, set `PYTHONPATH=src`
- Entrypoint: `surg-rl` CLI (requires editable install pattern or direct python -m)
- `.dockerignore` excludes `.planning/`, `logs/`, `models/`, `.git/`
- Rationale: Containerization enables reproducible cloud training and team onboarding.

### C: CI/CD Pipelines

**GitHub Actions: CI for PR validation, Release for PyPI publishing.**

- `.github/workflows/ci.yml`: Run on push/PR to `main` — lint (ruff), format (black --check), typecheck (mypy), test (pytest -m "not integration")
- `.github/workflows/release.yml`: Trigger on version tag push — build wheel/sdist, publish to PyPI with `pypi-api-token`
- Caching: `actions/cache` for pip dependencies
- Rationale: Automated validation prevents regressions; automated releases reduce toil.

## Canonical References

- `.planning/ROADMAP.md` → Phase 5 definition
- `.planning/research/SUMMARY.md` → Phase 5 rationale and deliverables
- `.planning/codebase/INTEGRATIONS.md` → Notable absences (no CI/CD, no Docker)
- `.planning/codebase/STACK.md` → Build tools and existing dependencies
- `src/surg_rl/rl/callbacks.py` → Existing callback patterns
- `src/surg_rl/rl/training.py` → TrainingManager and TrainingConfig
- `src/surg_rl/utils/config.py` → Settings model
- `src/surg_rl/cli.py` → Typer CLI train command
- `pyproject.toml` → Dependencies and build config
- `AGENTS.md` → Project conventions and testing patterns

## Existing Code Insights

### Reusable Assets
- `TensorBoardCallback` in `callbacks.py` already logs episode reward, length, FPS, curriculum stage, difficulty, randomization params — use as template
- `TrainingConfig` dataclass in `training.py` already has `enable_tensorboard` pattern to replicate for wandb/mlflow
- `TrainingManager.train()` already assembles `CallbackList` — just append new callbacks
- `Settings` in `config.py` already reads env vars via Pydantic Settings — add `wandb_api_key`, `mlflow_tracking_uri` fields

### Established Patterns
- SB3 callbacks: inherit `BaseCallback`, implement `_on_step()` and optionally `_on_training_start()`
- Optional dependencies: use `[dev]`, `[llm]`, `[vision]` pattern in `pyproject.toml`
- CLI flags: Typer `bool` options default `False`, enable with `--flag`
- Tests: feature-specific test files (e.g., `test_callbacks.py`) with pytest

## Deferred Ideas

- **Ray/RLlib distributed training** — Requires architectural changes to training pipeline; defer to v2
- **Kubernetes deployment manifests** — Cloud-specific; defer until cloud training is needed
- **Pre-commit hooks in CI** — Already have `.githooks/pre-commit` but not integrated into Actions; can be added later
- **Multi-platform Docker builds** (arm64) — Nice to have; focus on amd64 first

---

*Phase: 05-Experiment Tracking + Infrastructure*
*Context gathered: 2026-05-01*

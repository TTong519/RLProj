---
phase: 05-experiment-tracking-infrastructure
plan: 02
subsystem: infrastructure
tags: [docker, ci-cd, github-actions, pypi, containerization]
dependency_graph:
  requires: []
  provides: [INFRA-03, INFRA-04]
  affects: [Dockerfile, .dockerignore, .github/workflows/ci.yml, .github/workflows/release.yml, tests/test_cli.py]
tech_stack:
  added: []
  patterns: [multi-stage-docker, matrix-ci, pypi-release]
key_files:
  created:
    - Dockerfile
    - .dockerignore
    - .github/workflows/ci.yml
    - .github/workflows/release.yml
    - tests/test_cli.py
decisions:
  - "Multi-stage Dockerfile: base (system deps) → build (editable install) → runtime (site-packages + source)"
  - "System deps: libgl1, libglew2.2, libglu1-mesa, libx11-6, libglib2.0-0 for MuJoCo, PyBullet, OpenCV"
  - "PYTHONPATH=/app/src in runtime stage because editable install symlinks to src/"
  - "CI matrix across Python 3.10/3.11/3.12 with pip caching"
  - "Release triggers on v* tag push via pypa/gh-action-pypi-publish"
  - "pytest -m 'not integration' excludes integration tests from CI"
metrics:
  duration: "10 minutes"
  completed_date: "2026-05-02"
---

# Phase 5 Plan 02: Docker + CI/CD — Summary

## What was built

1. **Dockerfile** (multi-stage, 33 lines):
   - Base stage: `python:3.11-slim` + apt-get system deps for GL/mesa/X11 libs
   - Build stage: copies `pyproject.toml`, `pytest.ini`, `src/`, `README.md`; `pip install -e ".[dev,tracking]"`
   - Runtime stage: copies site-packages + `surg-rl` bin + source code; sets `PYTHONPATH=/app/src`
   - Entrypoint: `python -m surg_rl.cli`
   - Default CMD: `version`

2. **.dockerignore** (comprehensive exclusions):
   - `.git/`, `.github/`, `.planning/`
   - `logs/`, `models/`, `checkpoints/`, `mlruns/`, `wandb/`
   - `.env`, `.venv/`, IDE dirs, test artifacts

3. **.github/workflows/ci.yml**:
   - Triggers on push/PR to `main`
   - Matrix: Python 3.10, 3.11, 3.12
   - Steps: checkout → setup-python → pip cache → install deps → ruff → black --check → mypy → pytest -m "not integration"

4. **.github/workflows/release.yml**:
   - Triggers on `v*` tag push
   - Steps: checkout → setup-python (3.11) → install build + twine → `python -m build` → publish to PyPI via `pypa/gh-action-pypi-publish`

5. **tests/test_cli.py** (2 tests):
   - `test_version_command`: `runner.invoke(app, ["version"])` — asserts exit_code=0, contains "Surg-RL", "0.1.0"
   - `test_config_command`: `runner.invoke(app, ["config"])` — asserts exit_code=0, contains "Default Simulator"

## Verification

- `python -c "import yaml; yaml.safe_load(...)"` for both workflow files: **valid**
- `PYTHONPATH=src pytest tests/test_cli.py -v`: **2 passed**
- `docker build -t surg-rl .`: **not available in remote session** (documented for manual verification)

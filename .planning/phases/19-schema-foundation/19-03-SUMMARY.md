---
phase: 19-schema-foundation
plan: 03
subsystem: dependency-management
tags: [pyproject.toml, optional-dependencies, pip-extras]
requires: [D-07, D-08]
provides:
  - "[assets] extras group (trimesh>=4.5.0)"
  - "[benchmark] extras group (matplotlib, seaborn, pandas, rliable)"
  - "[marl] extras group (pettingzoo, supersuit)"
  - "[dreamer] extras group (jax, optax, dreamerv3)"
tech-stack:
  added: ["trimesh>=4.5.0", "matplotlib>=3.7.0", "seaborn>=0.12.0", "pandas>=2.0.0", "rliable>=1.0.8", "pettingzoo>=1.24.0", "supersuit>=3.9.0", "jax~=0.4.20", "optax>=0.1.7", "dreamerv3~=1.5.0"]
  patterns: ["PEP 508 >= for stable libs (D-07)", "~= for volatile APIs (D-08)", "4-space indent, comment headers per group"]
key-files:
  modified: ["pyproject.toml"]
  created: []
decisions: []
metrics:
  duration: 3m49s
  completed: 2026-05-13T22:19:17Z
---

# Phase 19 Plan 03: Optional Dependency Groups Summary

**One-liner:** Declared 4 new pip extras groups ([assets], [benchmark], [marl], [dreamer]) in pyproject.toml with pinned versions per D-07/D-08 decisions, enabling `pip install surg-rl[assets]` et al. while keeping core install lightweight.

## Implementation

### Task 1 — Add 4 optional dependency groups to pyproject.toml

Added 27 lines to `pyproject.toml` inserting four new optional dependency groups under `[project.optional-dependencies]` while preserving all 9 existing groups unchanged.

| Group | Dependencies | Pinning | Sorted Before |
|-------|-------------|---------|---------------|
| `assets` | trimesh | `>=4.5.0` | `dev` |
| `benchmark` | matplotlib, seaborn, pandas, rliable | `>=` all | `dev` |
| `marl` | pettingzoo, supersuit | `>=` all | `meshing` |
| `dreamer` | jax, optax, dreamerv3 | `~=` for jax/dreamerv3, `>=` for optax | `ros2` |

Final alphabetical ordering: `assets, benchmark, dev, llm, marl, meshing, simulation, vision, tracking, distributed, dreamer, ros2, docs`

## Verification

- `tomllib.load()` parses successfully — no syntax errors
- All 13 optional groups present: 9 original + 4 new
- All dependency strings valid PEP 508 (`packaging.requirements.Requirement`)
- Exact match on every dependency version (10 assertions)
- Group ordering verified against expected alphabetical list
- `PYTHONPATH=src pytest tests/` — **881 passed, 11 skipped, 0 regressions**
- 3 pre-existing test failures excluded (venv missing phi, ray/tree, tetgen)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — pyproject.toml changes are complete and declarative; no runtime stubs.

## Self-Check: PASSED

- `pyproject.toml` exists and modified: commit `4a5fd99`
- 13 optional dependency groups confirmed (9 existing + 4 new)
- Commit `4a5fd99` present in git log

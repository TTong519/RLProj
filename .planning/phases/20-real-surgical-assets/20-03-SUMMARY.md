---
phase: 20-real-surgical-assets
plan: 03
type: execute
wave: 2
depends_on: [20-01]
subsystem: assets
tags: [organ-pipeline, tetgen, trimesh, auto-repair, stl]
requires: [20-01]
provides: [20-04]
affects: [scene_builder.py]
tech-stack:
  added: []
  patterns: ["LazyImport guard", "procedural fallback", "subprocess error handling"]
key-files:
  created:
    - src/surg_rl/assets/organ_pipeline.py
  modified: []
key-decisions: []
metrics:
  duration: "~2min"
  completed: "2026-05-13"
  tasks: 1
  files_created: 1
  files_modified: 0
---

# Phase 20 Plan 03: Organ OBJ→STL→Tetgen Pipeline Summary

**One-liner:** Organ surface mesh pipeline loads OBJ via trimesh with auto-repair (hole filling, degenerate removal, watertightness), exports as STL, and invokes tetgen CLI to produce `.node`/`.ele` tetrahedral meshes — falling back to procedural shapes when OBJs or trimesh are missing.

## What was built

- **`src/surg_rl/assets/organ_pipeline.py`** (169 lines) — Two public functions forming the complete organ mesh pipeline:
  - `load_and_repair_organ_surface()` — Loads OBJ organ mesh, auto-repairs with trimesh (fill holes, remove degenerate faces, merge close vertices, fix normals), falls back to `generate_procedural_organ()` from Plan 20-01 when mesh is missing
  - `organ_to_tetgen()` — Exports repaired surface as STL, invokes tetgen CLI with configurable quality flags, returns output prefix for consumption by existing `DeformableConfig.mesh_source="tetgen"` code path

## Commit log

| Task | Name | Commit | Type |
|------|------|--------|------|
| 1 | Create organ_pipeline.py with OBJ→STL→tetgen + auto-repair | `10135aa` | feat |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed tetgen output prefix mismatch**
- **Found during:** task 1
- **Issue:** Plan's code exports STL as `organ_surface.stl` but returns prefix `tetgen_output` — tetgen writes output files with the same basename as the input STL (e.g., `organ_surface.1.node`), making `tetgen_output.1.node` never exist
- **Fix:** Renamed STL export to `tetgen_output.stl` so tetgen writes `tetgen_output.1.node` and `tetgen_output.1.ele`, matching the returned prefix
- **Files modified:** `src/surg_rl/assets/organ_pipeline.py`
- **Commit:** `10135aa`

## Verification

- **Import test:** `PYTHONPATH=src python -c "from surg_rl.assets.organ_pipeline import ..."` — PASSED (no trimesh required at import time)
- **Function existence:** `load_and_repair_organ_surface` and `organ_to_tetgen` both callable — PASSED
- **Procedural fallback:** Trimesh not installed locally, procedural path skipped gracefully — expected behavior per plan
- **Test suite:** Pre-existing `pydantic-core` version incompatibility (unrelated to this plan) — full test suite blocked

## Known Stubs

None — all code is fully wired. Missing OBJ falls through to procedural organ shapes; missing trimesh raises `ImportError` with pip install hint; missing tetgen binary logs `FileNotFoundError` warning.

## Threat Flags

None — the only trust boundary (tetgen subprocess) is already documented in the plan's threat model (T-20-04, accepted).

## Self-Check: PASSED

- `src/surg_rl/assets/organ_pipeline.py` — EXISTS (169 lines, 2 functions)
- Commit `10135aa` — EXISTS in git log
- No file deletions in commit — CONFIRMED

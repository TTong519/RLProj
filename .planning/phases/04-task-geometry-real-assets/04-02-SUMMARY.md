---
phase: 04-task-geometry-real-assets
plan: 02
subsystem: simulators
tags: [urdf, obj, mesh, mjcf, pybullet, mujoco, asset-loading, fallback, deduplication]

requires:
  - phase: 03-simulator-robustness
    provides: simulator backends with stable reset/state-save/restore

provides:
  - SceneBuilder deduplicated missing-asset warning system
  - SceneBuilder.load_urdf_asset() for URDF resolution
  - PyBullet real URDF loading via load_urdf_asset with primitive fallback
  - PyBullet real OBJ visual mesh loading via createVisualShape(GEOM_MESH)
  - MuJoCo MJCF mesh asset references for tissue and instrument geometry
  - Full test coverage for asset fallback, path resolution, and integration

affects:
  - phase 5 infrastructure (asset preloading/caching)
  - future rendering/visual fidelity work
tech-stack:
  added: []
  patterns:
    - "Deduplicated warning: _missing_assets set[str] suppresses repeated logger.warning per unique path"
    - "Visual mesh real, collision primitive: real OBJ for visuals, primitive for stable collision"
    - "Graceful fallback: AssetMissingError only when use_primitive_fallback=False, otherwise silent primitive"

key-files:
  created:
    - tests/test_real_assets.py
  modified:
    - src/surg_rl/simulators/scene_builder.py
    - src/surg_rl/simulators/pybullet_simulator.py
    - src/surg_rl/simulators/mujoco_simulator.py

key-decisions:
  - "MuJoCo URDF loading deferred: MuJoCo does not natively load URDF; existing TODO remains"
  - "PyBullet tissue uses primitive collision even with real mesh: stability over fidelity"
  - "Single-shot warning at load_scene time via _missing_assets set, not per frame"

patterns-established:
  - "_log_missing_asset(asset_path, entity_name): deduplicated warning with set-based suppression"
  - "load_urdf_asset(urdf_path, entity_name) -> Path | None: unified resolution + logging + optional raise"
  - "Mesh asset wiring in _add_tissue_to_mjcf and _add_instrument_to_mjcf: real mesh if found, else primitive"

requirements-completed: [TASK-03, TASK-04]

# Metrics
duration: 20min
completed: 2026-05-02
---

# Phase 4 Plan 2: Real Asset Loading Summary

**Deduplicated asset loading with single-shot fallback warnings in both PyBullet (URDF+OBJ) and MuJoCo (OBJ mesh assets)**

## Performance

- **Duration:** 20 min
- **Started:** 2026-05-02T00:42:55Z
- **Completed:** 2026-05-02T01:03:00Z
- **Tasks:** 4
- **Files modified:** 4

## Accomplishments
- SceneBuilder now tracks `_missing_assets: set[str]` to prevent duplicate warning spam
- `load_urdf_asset()` provides unified URDF resolution with optional `AssetMissingError` raise
- PyBullet simulator wires URDF loading via `load_urdf_asset` with automatic primitive fallback
- PyBullet `_load_mesh_visual_shape()` loads real OBJ/DAE as visual-only geometry (collision stays primitive)
- MuJoCo MJCF generation references real mesh files via `<mesh>` assets when available
- 9 tests covering single-warning, fallback-disabled raises, relative path resolution, URDF resolution, missing URDF, MuJoCo mesh-in-MJCF, missing-mesh fallback, PyBullet integration, and MJCF mesh verification
- Full suite: 600 passed, 0 regressions

## Task Commits

Each task was committed atomically:

1. **task 1: Add missing asset tracking and single-shot logging to SceneBuilder** - `c96fa1f` (test: RED), `a11813a` (feat: GREEN)
2. **task 2: Wire real asset loading into PyBullet simulator** - `9b8ec81` (feat)
3. **task 3: Wire real asset loading into MuJoCo simulator / SceneBuilder** - `64b7b9b` (feat)
4. **task 4: Integration test with sample URDF and full suite regression check** - `084d8ec` (test)

## Files Created/Modified
- `src/surg_rl/simulators/scene_builder.py` — `_missing_assets`, `_log_missing_asset()`, `load_urdf_asset()`, mesh asset wiring in MJCF
- `src/surg_rl/simulators/pybullet_simulator.py` — `_load_robot` uses `load_urdf_asset`, `_load_tissue` resolves mesh, `_load_mesh_visual_shape()`
- `tests/test_real_assets.py` — 9 tests for asset fallback, path resolution, URDF loading, MuJoCo mesh, integration

## Decisions Made
- MuJoCo URDF support remains deferred: MuJoCo does not natively load URDF; the existing TODO comment in `_add_robot_to_mjcf` stays
- PyBullet tissue collision stays primitive even when a real mesh is used for visuals: this avoids convex decomposition complexity and maintains stability
- Single-shot warning uses a `set[str]` rather than a `dict` or `WeakSet`: simple, deterministic, cleared per SceneBuilder instance

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Asset loading infrastructure is ready for Phase 5 (preloading/caching optimizations)
- No blockers — both backends support real assets with graceful fallback

---
*Phase: 04-task-geometry-real-assets*
*Completed: 2026-05-02*

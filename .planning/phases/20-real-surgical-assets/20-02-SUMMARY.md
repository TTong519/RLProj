---
phase: 20-real-surgical-assets
plan: 02
subsystem: assets
tags: [mesh-loader, urdf, v-hacd, trimesh, collision-geometry, scene-builder]
requires: [20-01]
provides: [mesh_loader.py, SceneBuilder URDF integration]
affects: [scene_builder.py, instrument loading pipeline]
tech-stack:
  added:
    - trimesh (OBJ loading, decimation, V-HACD)
    - ElementTree (URDF XML generation)
  patterns:
    - TRIMESH lazy import guard
    - warn-once deduplication (_WARNED_MESHES set)
    - multi-link articulated URDF templates (code-generated, no files)
key-files:
  created:
    - src/surg_rl/assets/mesh_loader.py (239 lines)
  modified:
    - src/surg_rl/simulators/scene_builder.py (+53/-8 lines)
    - tests/test_real_assets.py (+72 lines)
decisions:
  - V-HACD approximate convex decomposition for collision geometry (per D-06)
  - Separate visual (decimated) and collision (V-HACD) meshes per instrument (per D-07)
  - Multi-link URDFs with type-based templates keyed to InstrumentType (per D-08/D-09)
  - Procedural fallback via mesh_generator when mesh_path is missing (per D-12)
  - Mesh path relative to assets_dir, deduplicated warnings via _WARNED_MESHES
metrics:
  duration: 269s
  completed_date: 2026-05-14T04:31:55Z
---

# Phase 20 Plan 02: Mesh Loading & URDF Generation Summary

**One-liner:** trimesh-based OBJ loading pipeline with V-HACD collision decomposition, code-generated multi-link URDFs, and SceneBuilder integration — procedural fallback for missing meshes.

## Goal & Deliverables

Created `src/surg_rl/assets/mesh_loader.py` providing a complete mesh loading pipeline:

- **`load_instrument_mesh()`** — loads OBJ via trimesh or falls back to procedural shapes from `mesh_generator.py`
- **`decimate_and_decompose()`** — decimates visual mesh and runs V-HACD convex decomposition for collision geometry
- **`generate_urdf()`** — writes complete URDF files with visual + collision mesh references, supporting multi-link articulated instruments
- **`load_and_generate_urdf()`** — end-to-end convenience function (load → decimate/decompose → URDF)
- **`URDF_TEMPLATES`** — 9 instrument type templates (forceps, scalpel, needle_driver, scissors, clamp, suction, cautery, camera, retractor)

Integrated into `SceneBuilder.create_mjcf()` via `_load_instrument_geometry()` method, which is the preferred instrument geometry source when trimesh is available.

## What Was Built

### Task 1: mesh_loader.py (commit: c66d092)
- Full OBJ loading with fallback to `generate_procedural_instrument()`
- V-HACD convex decomposition with convex hull fallback on failure
- URDF XML generation with `<link>`, `<visual>`, `<collision>`, and `<joint>` elements
- Deduplicated per-mesh-path warnings via `_WARNED_MESHES` session set
- Lazy import guard pattern (no ImportError when trimesh is missing)

### Task 2: SceneBuilder Integration (commit: ff8ad0d)
- Added `_load_instrument_geometry()` method that calls the mesh_loader pipeline
- Extended `_add_instrument_to_mjcf()` to try URDF path first before falling back
- Handles missing trimesh gracefully: `load_and_generate_urdf` is set to `None` when import fails
- Preserves existing direct OBJ mesh path for backward compatibility
- Primitive box remains the ultimate fallback

### Task 3: Tests (commit: 88501b6)
- **`TestMeshLoading`**: procedural fallback, warning deduplication
- **`TestURDFTemplates`**: 9 instrument type coverage, valid URDF XML generation
- **`TestDecimation`**: face count preservation on original mesh during decimation
- All trimesh-dependent tests skip gracefully when trimesh is not installed

## Deviations from Plan

None — plan executed exactly as written.

## Verification

- Full test suite: **918 passed, 15 skipped, 0 failures** (48.56s)
- `mesh_loader.py` imports succeed without trimesh installed
- `URDF_TEMPLATES` has all 9 instrument types
- `SceneBuilder._load_instrument_geometry()` confirmed present
- Decimation face-count test correctly skipped (trimesh not installed in this environment, as expected)

## Key Design Decisions

1. **V-HACD** for collision geometry — produces accurate convex hulls for concave instruments like forceps jaws
2. **Separate visual/collision meshes** — visual mesh is decimated for performance; collision mesh is V-HACD decomposed for accuracy
3. **Code-generated templates** — no external URDF template files; all link/joint definitions live in `URDF_TEMPLATES` dict
4. **Procedural fallback** — when OBJ is missing, `mesh_generator.py` provides type-appropriate trimesh shapes (capsule for forceps, ellipsoid for organs, etc.)
5. **Warning deduplication** — `_WARNED_MESHES` set prevents log spam when the same missing path is encountered multiple times

## Known Stubs

None. All functions are fully implemented with real trimesh calls, and fallback paths are complete.

## Threat Flags

No new threat surface beyond what the plan's threat model accounts for. The two identified threats (DoS via malformed OBJ, spoofing via mesh file path) are both accepted with documented reasoning.

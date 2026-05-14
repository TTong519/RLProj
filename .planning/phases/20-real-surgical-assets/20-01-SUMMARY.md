---
phase: 20-real-surgical-assets
plan: 01
subsystem: assets
tags: [procedural-generation, trimesh, fallback-meshes, instrument-generators, organ-generators]
requires: [19-03]
provides: [procedural-mesh-generators]
affects: [20-02]
tech-stack:
  added: []
  patterns: [lazy-import-guard, decorator-registration, procedural-fallback]
key-files:
  created:
    - src/surg_rl/assets/mesh_generator.py (277 lines)
  modified: []
decisions: []
metrics:
  duration: ~0h 1m
  completed_date: 2026-05-14
---

# Phase 20 Plan 01: Procedural Mesh Generator Module Summary

**One-liner:** Type-appropriate trimesh procedural shape generators for all 9 instrument types and 4 organ types, with TRIMESH lazy guard and decimation support.

## Goal

Define trimesh procedural shape generators for all 11 instrument types + 4 organ types, wired through the existing `TRIMESH` lazy import guard. When `MeshAsset.fallback_enabled=True` and no mesh file is found, the system can generate a type-appropriate procedural OBJ instead of a generic box/cylinder.

## Tasks Completed

| Task | Name | Type | Commit | Status |
|------|------|------|--------|--------|
| 1 | Create procedural mesh generator module | auto | 4130377 | Done |

## Implementation Summary

### module: `src/surg_rl/assets/mesh_generator.py` (277 lines)

- **`_procedural_map`**: Registry of 9 instrument generators keyed by `InstrumentType` value:
  - `scalpel` — flat blade + cylindrical handle
  - `forceps` — shaft + two jaw capsules
  - `needle_driver` — shaft + angled jaw box
  - `scissors` — two intersecting flat blades + ring handles
  - `clamp` — bulldog-style shaft + wide jaw
  - `suction` — hollow tube cylinder
  - `cautery` — pen-style shaft + flat tip
  - `camera` — endoscope narrow shaft + wider lens tip
  - `retractor` — curved retractor blade

- **`_organ_map`**: Registry of 4 organ generators keyed by organ name:
  - `liver` — flattened ellipsoid (icosphere warped)
  - `kidney` — bean-shaped ellipsoid
  - `stomach` — J-shaped elongated ellipsoid
  - `gallbladder` — pear-shaped small ellipsoid

- **Decorator registration pattern**: `@_register("type")` and `@_register_organ("type")` automatically populate the maps
- **TRIMESH lazy guard**: Every generator accesses `TRIMESH` before importing trimesh — crashes only with clear `pip install surg-rl[assets]` hint
- **Decimation**: All generators accept `target_face_count: int | None = None` and call `simplify_quadratic_decimation()` when set
- **Public API**:
  - `generate_procedural_instrument(instrument_type, target_face_count)` → `trimesh.Trimesh`
  - `generate_procedural_organ(organ_type, target_face_count)` → `trimesh.Trimesh`

## Verification

| Check | Result |
|-------|--------|
| Module imports without trimesh | PASS |
| `_procedural_map` ≥ 9 entries | PASS (9: scalpel, forceps, needle_driver, scissors, clamp, suction, cautery, camera, retractor) |
| `_organ_map` ≥ 4 entries | PASS (4: liver, kidney, stomach, gallbladder) |
| All required instrument types present | PASS |
| All required organ types present | PASS |
| Existing 917 tests pass | PASS (917 passed, 11 skipped) |

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

- [x] `src/surg_rl/assets/mesh_generator.py` exists (277 lines, ≥80 minimum)
- [x] Commit `4130377` exists in git log
- [x] `_procedural_map` has 9 entries covering all InstrumentType values
- [x] `_organ_map` has 4 entries covering liver, kidney, stomach, gallbladder
- [x] 917 existing tests pass unchanged
- [x] Module imports without trimesh installed

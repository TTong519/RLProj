---
phase: 19-schema-foundation
plan: 01
subsystem: scene_definition/schema
tags: [schema, pydantic-v2, v0.4.0, config-models, skeletal]
requires: []
provides:
  - MeshAsset (extended)
  - TaskConfig (extended)
  - BenchmarkConfig (new)
  - MultiAgentConfig (new)
  - DreamerConfig (new)
affects: [Phase 20, Phase 21, Phase 22, Phase 23, Phase 24]
tech-stack:
  added: []
  patterns: [pydantic-v2-BaseModel, Field-default-None, Literal-enums]
key-files:
  created: []
  modified:
    - src/surg_rl/scene_definition/schema.py (1374 lines)
    - src/surg_rl/scene_definition/__init__.py (172 lines)
dependencies: []
decisions:
  - Extended MeshAsset in-place per D-01 (no v04_ prefix)
  - Extended TaskConfig with exactly one field per D-04 (task_type Literal)
  - Added BenchmarkConfig/MultiAgentConfig/DreamerConfig to schema.py per D-02
  - All new fields skeletal with None defaults per D-03 (~50 lines per model)
requirements: []
metrics:
  duration: 7 minutes
  completed_date: 2026-05-13
  tasks: 3
  files_modified: 2
---

# Phase 19 Plan 01: Schema Foundation Summary

**Skeletal Pydantic v2 config models for all five v0.4.0 feature modules — MeshAsset extension, TaskConfig extension, and three new config classes added to schema.py.**

## Execution Summary

| Task | Name | Type | Commit | Status |
|------|------|------|--------|--------|
| 1 | Extend MeshAsset with v0.4.0 fields | auto | `f547883` | Complete |
| 2 | Add task_type to TaskConfig + create BenchmarkConfig/MultiAgentConfig/DreamerConfig | auto | `35b108c` | Complete |
| 3 | Export new models from scene_definition/__init__.py | auto | `305e580` | Complete |

## Key Changes

### MeshAsset Extension (Task 1)
Added three fields to the existing `MeshAsset` class at line 224:
- `target_face_count: int | None` — target face count after decimation, `ge=1`
- `fallback_enabled: bool` — primitive geometry fallback on missing mesh (default `True`)
- `mesh_origin: Position | None` — origin offset for mesh assets

### TaskConfig Extension (Task 2)
Added `task_type` field — `Literal["suturing", "knot_tying", "needle_insertion", "grasping", "cutting", "dissection"] | None` with `None` default.

### New Config Models (Task 2)
- **BenchmarkConfig** (7 fields): `algorithms`, `seeds`, `output_dir`, `render_plots`, `statistical_tests`, `backend_reporting`, `dreamer_comparison` — skeleton for Phase 23
- **MultiAgentConfig** (5 fields): `num_agents`, `shared_policy`, `agent_roles`, `cooperative`, `observation_sharing` — skeleton for Phase 22
- **DreamerConfig** (6 fields): `obs_type`, `pixel_resolution`, `process_isolation`, `memory_fraction`, `dreamer_variant`, `reconstruction_metric` — skeleton for Phase 24

### Exports (Task 3)
Added `BenchmarkConfig`, `DreamerConfig`, `MultiAgentConfig` to both the `from .schema import (...)` block (alphabetical) and the `__all__` list in `scene_definition/__init__.py`.

## Verification Results

| Check | Result |
|-------|--------|
| All 910 existing tests pass with zero modifications | PASSED |
| `import surg_rl` succeeds | PASSED |
| `MeshAsset.model_dump()` includes new fields | PASSED |
| `TaskConfig.task_type` is `None` by default | PASSED |
| All config models construct with zero args | PASSED |
| `model_dump()` returns JSON-serializable dicts | PASSED |
| `from surg_rl.scene_definition import BenchmarkConfig` works | PASSED |
| `from surg_rl.scene_definition import MultiAgentConfig` works | PASSED |
| `from surg_rl.scene_definition import DreamerConfig` works | PASSED |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all models are intentionally skeletal by design per D-03. Every field has a `Field(default=...)` value. Phases 20–24 extend these models with phase-specific fields and behavior.

## Threat Flags

None — no new trust boundaries introduced. All additions are pure Pydantic v2 data containers with `None` defaults.

## Self-Check: PASSED

- `src/surg_rl/scene_definition/schema.py` — exists, 1374 lines
- `src/surg_rl/scene_definition/__init__.py` — exists, 172 lines
- Commit `f547883` — verified in git log
- Commit `35b108c` — verified in git log
- Commit `305e580` — verified in git log

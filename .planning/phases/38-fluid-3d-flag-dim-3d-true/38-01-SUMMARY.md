---
phase: 38-fluid-3d-flag-dim-3d-true
plan: 01
subsystem: scene_definition
tags: [fluid, schema, pydantic, validation, tdd, additive]
requires:
  - "FluidConfig (2D, pre-existing) — resolution, _cap_resolution, FluidBoundaryType, boundary_type"
provides:
  - "FluidCouplingMode str-Enum (ONE_WAY/TWO_WAY)"
  - "FluidConfig.dim_3d (default False)"
  - "FluidConfig.grid_size (tuple[int,int,int]|None, default None)"
  - "FluidConfig.coupling_mode (default ONE_WAY)"
  - "FluidConfig.coupling_substeps (default 4, ge=1, le=16)"
  - "FluidConfig._cap_grid_size field_validator (len==3, 4<=dim<=64)"
  - "FluidConfig._require_grid_size_when_dim_3d model_validator(mode='after') — SC#3 guard"
affects:
  - "Plan 38-02 (FluidSimulator 3D branch consumes dim_3d + grid_size + coupling_mode/substeps)"
  - "Plan 38-03 (render_fluid_3d consumes dim_3d)"
  - "Plan 38-04 (regression tests assert the SC#3 hard-error guard)"
tech-stack:
  added: []
  patterns:
    - "Pydantic v2 str-Enum (FluidCouplingMode mirrors FluidBoundaryType)"
    - "field_validator for per-field bounds (_cap_grid_size mirrors _cap_resolution)"
    - "model_validator(mode='after') cross-field hard-error guard (_require_grid_size_when_dim_3d mirrors BoundingBox.validate_bounds)"
    - "TDD RED/GREEN gate: RED commit (failing tests) then GREEN commit (implementation)"
key-files:
  created: []
  modified:
    - src/surg_rl/scene_definition/schema.py
    - tests/test_fluids/test_schema.py
decisions:
  - "FluidCouplingMode defined immediately after FluidBoundaryType (no forward-ref cycle; no model_rebuild needed)"
  - "FluidCouplingMode imported lazily inside RED test methods so existing 2D tests pass during RED (module-level import would crash the whole test module before the symbol exists)"
  - "grid_size has NO silent default when dim_3d=True — the hard ValidationError IS the SC#3 memory-blow-up guard (forces conscious cubic-cost choice)"
metrics:
  duration: ~1m
  tasks: 2
  files: 2
  started: "2026-06-27T05:09:17Z"
  completed: "2026-06-27T05:10:18Z"
status: complete
---

# Phase 38 Plan 01: FluidConfig 3D schema Summary

Extended `FluidConfig` additively (Pydantic v2) with the 3D fluid config surface: the `dim_3d` flag, a separate 3D `grid_size` field with a hard-required-when-`dim_3d` cross-field rule (SC#3 memory-blow-up guard), the `FluidCouplingMode` str-Enum (ONE_WAY default / TWO_WAY opt-in), and `coupling_substeps`. The 2D `resolution`/`_cap_resolution`/`FluidBoundaryType`/`boundary_type` surface is byte-identical (56 insertions, 0 deletions in schema.py).

## Commits

| # | Task | Type | Commit | Message |
|---|------|------|--------|---------|
| 1 | RED — failing additive 3D schema tests | test | 5651d5f | `test(38-01): add failing 3D FluidConfig schema tests` |
| 2 | GREEN — FluidCouplingMode + dim_3d/grid_size/coupling fields + validators | feat | 9c7d1ad | `feat(38-01): add 3D FluidConfig fields + validators` |

## Tasks Completed

### Task 1: RED — additive schema tests for 3D FluidConfig surface

Appended `TestFluidConfig3D` class (9 tests) + two bounds helpers (`_make_2d_bounds`, `_make_3d_bounds`) to `tests/test_fluids/test_schema.py`. Tests cover:
- `test_defaults_dim_3d_off` — 2D default config has `dim_3d=False`, `grid_size=None`, `coupling_mode=ONE_WAY`, `coupling_substeps=4`
- `test_grid_size_required_when_dim_3d` — SC#3 guard: `dim_3d=True` + `grid_size=None` raises `ValidationError`
- `test_grid_size_ok_when_dim_3d_true` — cubic `(24,24,24)` and anisotropic `(64,32,64)` both validate
- `test_cap_grid_size_rejects_too_small` / `_too_large` / `_wrong_len` — validator bounds (len==3, 4<=dim<=64)
- `test_coupling_substeps_bounds` — ge=1/le=16 (0 and 17 raise; 1 and 16 accepted)
- `test_coupling_mode_enum_values` — `ONE_WAY.value == "one_way"`, `TWO_WAY.value == "two_way"`, str-Enum equality
- `test_serialization_coupling_mode` — `model_dump()` preserves `coupling_mode` as the Enum object (per CLAUDE.md)

`FluidCouplingMode` is imported lazily inside the new test methods so the existing 2D test classes continue to import cleanly during RED (the symbol does not yet exist in `schema.py`). Existing 7 2D tests pass unchanged; 9 new tests fail with the expected RED failure modes (`ImportError` for missing `FluidCouplingMode`, `AttributeError` for missing `grid_size`, `DID NOT RAISE` for missing validators).

### Task 2: GREEN — FluidCouplingMode + FluidConfig 3D fields + validators

Additively extended `FluidConfig` in `src/surg_rl/scene_definition/schema.py`:
- `class FluidCouplingMode(str, Enum)` — defined immediately after `FluidBoundaryType` with `ONE_WAY = "one_way"` / `TWO_WAY = "two_way"` (mirrors `FluidBoundaryType` style).
- Four new fields added AFTER `initial_velocity` and BEFORE `_cap_resolution` (no reordering of existing fields):
  - `dim_3d: bool = Field(default=False, ...)` (D-01)
  - `grid_size: tuple[int, int, int] | None = Field(default=None, ...)` (D-02)
  - `coupling_mode: FluidCouplingMode = Field(default=FluidCouplingMode.ONE_WAY, ...)` (D-09)
  - `coupling_substeps: int = Field(default=4, ge=1, le=16, ...)` (D-12, D-13)
- `@field_validator("grid_size")` `_cap_grid_size` (D-05): `None` passes through; rejects `len != 3`; rejects any dim `< 4`; rejects any dim `> 64`; accepts anisotropic `(Nx, Ny, Nz)` tuples. Distinct from `_cap_resolution` (len 2, cap 128).
- `@model_validator(mode="after")` `_require_grid_size_when_dim_3d` (D-03): raises `ValueError` when `dim_3d=True` and `grid_size is None` (SC#3 memory-blow-up guard — hard error, no silent default); returns `self` (per CLAUDE.md, only raise + return self — no `model_copy` needed).

`FluidCouplingMode` is defined before `FluidConfig`, so no forward-ref cycle and no `model_rebuild()` was needed. The 2D `resolution`/`_cap_resolution`/`FluidBoundaryType`/`boundary_type` fields and the `_cap_resolution` body are byte-identical (diff: 56 insertions, 0 deletions).

## Verification Results

- `PYTHONPATH=src pytest tests/test_fluids/test_schema.py -v` → 16 passed (7 existing 2D + 9 new 3D).
- `PYTHONPATH=src pytest tests/test_fluids/test_fluid_simulator.py -v` → 16 passed (2D byte-identical behavior preserved).
- `PYTHONPATH=src pytest tests/test_fluid_step.py -v` → 5 passed (2D `fluid_step` no-op hook unchanged).
- Full `tests/test_fluids/` suite → 32 passed, 0 failed.
- Acceptance greps:
  - `class FluidCouplingMode` → 1 (defined)
  - `dim_3d: bool` → 1 (field declared)
  - `grid_size: tuple[int, int, int] | None` → 1 (field declared)
  - `_cap_grid_size` → 1 (def line; decorator `@field_validator("grid_size")` does not contain the method-name string)
  - `_require_grid_size_when_dim_3d` → 1 (def line; decorator `@model_validator(mode="after")` does not contain the method-name string)
  - `_cap_resolution` → 1 (unchanged — same count before and after this plan; 2D body byte-identical)
- SC#3 guard verified by `test_grid_size_required_when_dim_3d`: `FluidConfig(enabled=True, bounds=<3D bbox>, dim_3d=True, grid_size=None)` raises `ValidationError`.

## Deviations from Plan

### Auto-fixed Issues

None — the plan executed exactly as written. The implementation matches D-01..D-05, D-09, D-12, D-03 verbatim.

### Minor documentation discrepancy in plan acceptance criteria (not a code issue)

The plan's Task 2 acceptance criteria state:
- `grep -c '_cap_grid_size' ... >= 2 (decorator + def)`
- `grep -c '_require_grid_size_when_dim_3d' ... >= 2`
- `grep -c '_cap_resolution' ... unchanged (2 — decorator + def)`

The decorators `@field_validator("grid_size")` and `@model_validator(mode="after")` do **not** contain the method-name strings `_cap_grid_size` / `_require_grid_size_when_dim_3d` / `_cap_resolution`. So `grep -c` returns 1 for each (the `def` line only) — both before and after this plan. The meaningful "unchanged" check holds: `_cap_resolution` count is 1 before and 1 after, and the 2D `_cap_resolution` body is byte-identical (verified by `git diff --stat`: 56 insertions, 0 deletions in schema.py). No code change was needed; this is purely a wording discrepancy in the plan's grep-based acceptance criteria.

## TDD Gate Compliance

- RED gate commit `5651d5f` (`test(38-01): ...`) exists — 9 new tests failed before any implementation; existing 7 2D tests passed unchanged.
- GREEN gate commit `9c7d1ad` (`feat(38-01): ...`) exists after RED — all 16 tests pass.
- No REFACTOR needed (implementation is clean as written).

## Threat Surface

No new threat surface introduced beyond what the plan's `<threat_model>` already registers. The `T-38-01` (Tampering/DoS-OOM on `grid_size`) mitigation is implemented exactly as specified: `_cap_grid_size` rejects any dim > 64, and `_require_grid_size_when_dim_3d` hard-errors on missing `grid_size` (forces conscious cubic-cost choice). `T-38-02` (no auth surface) accepted as documented.

## Known Stubs

None. All fields/validators are fully wired with real validation logic; no placeholder/TODO/empty-default stubs.

## Self-Check: PASSED

- `tests/test_fluids/test_schema.py` — FOUND (modified, contains `TestFluidConfig3D`)
- `src/surg_rl/scene_definition/schema.py` — FOUND (modified, contains `FluidCouplingMode` + `_cap_grid_size` + `_require_grid_size_when_dim_3d`)
- Commit `5651d5f` — FOUND (`git log --oneline | grep 5651d5f`)
- Commit `9c7d1ad` — FOUND (`git log --oneline | grep 9c7d1ad`)
- 2D byte-identical regression: `test_fluid_step.py` 5/5 + `test_fluid_simulator.py` 16/16 pass.
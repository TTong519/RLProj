# Phase 38: 3D Fluid Flag (dim_3d=True) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-26
**Phase:** 38-fluid-3d-flag-dim-3d-true
**Areas discussed:** Schema (dim_3d + grid_size), 3D default + memory guard, coupling_mode semantics, 3D forces + obstacle SDF, 3D visualizer scope, 3D obstacle construction API, Substepping config

**Research pulled before questions (research_before_questions enabled):**
- PhiFlow 3D `Wake_Flow` example — canonical 3D `StaggeredGrid((vx,vy,vz), boundary, x=Nx, y=Ny, z=Nz, bounds=Box(x,y,z))` + `make_incompressible(v, obstacle, Solve(...))` + `infinite_cylinder` obstacle.
- One-way vs two-way fluid/solid coupling literature — one-way/partitioned (no solid-velocity feedback) is stable for thin/light solids; two-way/monolithic needs cut-cell/SPD machinery and suffers added-mass instability otherwise. Justifies SC#2's one_way-default / two_way-opt-in split.

---

## Schema: dim_3d + grid_size

| Option | Description | Selected |
|--------|-------------|----------|
| New dim_3d + grid_size field | Add `dim_3d: bool=False` + separate `grid_size: tuple[int,int,int]\|None`; leave `resolution` untouched | ✓ |
| Overload resolution tuple length | `resolution` accepts 2-or-3-tuple, infer dim_3d from length | |
| dim_3d + resolution_3d field | Same as selected but field named `resolution_3d` | |

| Option (3D axes) | Description | Selected |
|--------|-------------|----------|
| Direct x,y,z → x,y,z | `Box(x=dx,y=dy,z=dz)` from full `get_dimensions()`; 2D mapping unchanged | ✓ |
| Keep z-vertical convention | Physical (x,z,y) → grid (x,y,z) to keep "vertical = grid y" | |

| Option (grid_size required) | Description | Selected |
|--------|-------------|----------|
| Required when dim_3d=True | Hard `ValidationError` if `grid_size` omitted with `dim_3d=True` | ✓ |
| Optional, auto-default + warn | Substitute safe default (16³) + warn if omitted | |

**User's choice:** New `dim_3d` + `grid_size` field; direct x,y,z→x,y,z mapping; `grid_size` required when `dim_3d=True`.
**Notes:** Keeping `resolution` 2-tuple-only protects the SC#1 byte-identical 2D regression. Required-error is the strongest blow-up prevention.

---

## 3D default + memory guard

| Option (SC#3 reconcile) | Description | Selected |
|--------|-------------|----------|
| Required-error + documented recommended value | Hard error if omitted; doc a recommended 24³ in field description | ✓ |
| Revert to auto-default 16³ + warn | Matches SC#3 literally but silent default hides cubic cost | |
| Required + hard cap on grid_size | Required-error AND reject grid_size above cap | |

| Option (3D cap) | Description | Selected |
|--------|-------------|----------|
| 64 per dim | 64³ = 262k cells; 2D stays 128; matches "smaller" wording | ✓ |
| 32 per dim | Conservative; fast tests, low memory | |
| 48 per dim | Middle ground | |

| Option (anisotropic) | Description | Selected |
|--------|-------------|----------|
| Allow anisotropic (Nx,Ny,Nz) | 3-tuple, each independently capped | ✓ |
| Cubic only (single int → N³) | Simplest, most memory-predictable | |

**User's choice:** Required-error guard + documented recommended 24³; 3D cap 64/dim (2D stays 128); anisotropic 3-tuples allowed.
**Notes:** SC#3's "default grid_size" wording is satisfied by the required-error guard + a documented *recommended* value, NOT a silent fill. The required decision from the prior area is preserved (not reverted).

---

## coupling_mode semantics

| Option (exposure) | Description | Selected |
|--------|-------------|----------|
| FluidCouplingMode str-Enum | `ONE_WAY`/`TWO_WAY` enum mirroring `FluidBoundaryType`; default ONE_WAY | ✓ |
| Literal["one_way","two_way"] | Lighter weight, no new enum class | |

| Option (semantics) | Description | Selected |
|--------|-------------|----------|
| one_way=static SDF; two_way=velocity feedback | one_way: static SDF, fluid→solid forces, no feedback; two_way: Obstacle.velocity feedback | ✓ |
| Inverted: solid→fluid only | one_way = moving boundary, no force back on solid | |

| Option (stability) | Description | Selected |
|--------|-------------|----------|
| Clamp + static-SDF; two_way documented unstable | Existing 1e4 clamp extended to 3D + static-SDF; two_way documents instability | |
| Add substepping + per-axis clamp | Substepping (reuse substep_dt) + per-axis force clamp (fx,fy,fz) for 3D | ✓ |

| Option (SC#2 test) | Description | Selected |
|--------|-------------|----------|
| FluidSimulator-level integration test | Add thin-instrument obstacles, run N steps one_way, assert no NaN; two_way opt-in | ✓ |
| Full SurgicalEnv episode test | Wire add_obstacle + force application into env | |

**User's choice:** `FluidCouplingMode` str-Enum; one_way=static SDF / two_way=velocity feedback; **substepping + per-axis clamp** (the heavier machinery, not clamp-only); SC#2 at FluidSimulator level.
**Notes:** User deliberately chose the more-engineered stability approach. Full env-level coupling is scope creep (env doesn't wire obstacles today).

---

## 3D forces + obstacle SDF

| Option (SDF shape) | Description | Selected |
|--------|-------------|----------|
| Cylinder shafts + box tips | PhiFlow cylinders for shafts, boxes for tips; union(*geoms) merges | ✓ |
| Boxes only | All obstacles as axis-aligned boxes | |
| Spheres | Per-segment spheres | |

| Option (3D forces) | Description | Selected |
|--------|-------------|----------|
| Mirror 2D global-sum integration | Integrate pressure gradient over whole grid per axis | |
| Obstacle-mask integration | Integrate over obstacle-mask cells per obstacle | ✓ |

| Option (NaN test) | Description | Selected |
|--------|-------------|----------|
| Parametrized dim_3d × obstacle count | (dim_3d=False,True) × (single, overlapping); assert finite | ✓ |
| Two separate 2D/3D tests | Less DRY, easier per-path read | |

| Option (clamp style) | Description | Selected |
|--------|-------------|----------|
| Per-axis independent clamp | Clamp fx,fy,fz each to cap; 2D keeps scalar clamp | ✓ |
| Vector-magnitude clamp (2D-style) | Clamp ‖f‖ and scale all components together | |

**User's choice:** Cylinder shafts + box tips; **obstacle-mask integration** for 3D forces (deliberate divergence from 2D global-sum); parametrized NaN test; per-axis independent clamp in 3D.
**Notes:** 2D force path (global-sum + scalar magnitude clamp) preserved byte-identical for SC#1 only; 3D is a new semantics path — do not unify.

---

## 3D visualizer scope

| Option | Description | Selected |
|--------|-------------|----------|
| Solver-only, defer 3D render | No 3D renderer; render_fluid_2d stays; 3D solver-only | |
| 2D slice-of-3D fallback | render_fluid_3d renders a z-layer slice via render_fluid_2d | ✓ |
| True render_fluid_3d | Volume / iso-surface renderer | |

**User's choice:** 2D slice-of-3D fallback.
**Notes:** No SC requires visualization; a true 3D renderer is deferred.

---

## 3D obstacle construction API

| Option | Description | Selected |
|--------|-------------|----------|
| Keep raw API + add builder helper | add_obstacle unchanged; free helper builds cylinder+box SDF | |
| Raw API only, no helper | Callers build PhiFlow geometries themselves | |
| Higher-level add_instrument method | `FluidSimulator.add_instrument(pose, dims)` wraps construction + add_obstacle | ✓ |

**User's choice:** Higher-level `add_instrument(pose, dims)` method on `FluidSimulator`.
**Notes:** Raw `add_obstacle` kept unchanged (2D tests + byte-identical 2D path rely on it).

---

## Substepping config

| Option (config) | Description | Selected |
|--------|-------------|----------|
| New coupling_substeps field, default 2 | `coupling_substeps: int` on FluidConfig (3D obstacle path); reuse substep_dt | ✓ |
| Reuse substep_dt, fixed private count | No new field; private constant in FluidSimulator | |

| Option (default N) | Description | Selected |
|--------|-------------|----------|
| 2 | Doubles coupling resolution; modest cost | |
| 4 | More conservative stability margin; 4x coupling cost | ✓ |
| 1 | Effectively no substepping; rely on per-axis clamp | |

**User's choice:** New `coupling_substeps` field; **default = 4** (explicit N choice supersedes the config-option label's "default 2").
**Notes:** Reuse existing `substep_dt` as the per-substep dt (no new dt field). `two_way` documents instability regardless of substep count.

---

## Claude's Discretion

- Validator implementation choice (`model_validator` vs `field_validator`) for the `dim_3d⇒grid_size required` rule and `_cap_grid_size`.
- Exact `add_instrument(pose, dims)` signature and pose/dims → cylinder-shaft + box-tip mapping.
- Exact PhiFlow mechanism for the 3D obstacle mask in obstacle-mask integration (planner verifies against installed PhiFlow API).
- Exact `render_fluid_3d` signature (field, slice axis, layer index) and slice extraction.
- Whether new 3D fields live on `FluidConfig` directly vs a nested `Fluid3DConfig` sub-model (provided 2D fields/defaults are untouched).
- Exact N (step count) for SC#2/SC#4 regression tests.
- Internal naming of dim-3D branches and `coupling_substeps` bounds, provided semantics match.

## Deferred Ideas

- True 3D volume / iso-surface fluid renderer (this phase is slice-of-3D only).
- Wiring `add_instrument` + force application into the production `SurgicalEnv` episode loop.
- Two-way coupling stability fix (cut-cell / SPD monolithic solver).
- GPU fluid acceleration (PhiFlow CPU-first).
- Unifying 2D global-sum and 3D obstacle-mask force paths.
- Anisotropic-domain auto-sizing of `grid_size` from `bounds` aspect ratio.
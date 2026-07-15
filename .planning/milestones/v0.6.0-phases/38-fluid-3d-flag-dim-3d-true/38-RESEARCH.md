# Phase 38: 3D Fluid Flag (dim_3d=True) - Research

**Researched:** 2026-06-26
**Domain:** PhiFlow 3.4.0 Eulerian grid fluid solver + Pydantic v2 schema (3D additive path; 2D byte-identical regression gate)
**Confidence:** HIGH (PhiFlow 3.4.0 API confirmed in-env via smoke tests; schema patterns mirror existing validated code)

## Summary

Phase 38 adds a `dim_3d=True` branch to the existing 2D PhiFlow Eulerian fluid solver. The 2D xz-slice path must stay **byte-identical** to v0.5.0 (SC#1); all 3D work is purely additive. The phase is pure solver + Pydantic schema work — no GPU, no AI, no frontend, no `SurgicalEnv` wiring beyond what the dim-aware `FluidSimulator` constructor already absorbs.

The PhiFlow 3.4.0 3D API is confirmed working in this environment (pyenv 3.13.3, `phi==3.4.0`): `Box(x,y,z)` + `StaggeredGrid(0, ZERO, dom, x=Nx, y=Ny, z=Nz)` constructs a 3D field; `fluid.make_incompressible(v, obstacles, solve=Solve(...))` returns a 3D `(velocity, pressure)` pair; `advect.mac_cormack` works in 3D. The `union(*geoms)` multi-obstacle workaround is preserved. The three OPEN QUESTIONS (numpy dim-order, 3D obstacle mask, 3D pressure gradient) are resolved below with concrete confirmed calls. The 3D force path uses **numpy-based central differences** over `pressure.values.numpy('x,y,z')` combined with a **per-obstacle mask obtained via `phi.field.sample(geometry, pressure)`** — matching the 2D docstring formula `F = -∫ ∇p dV ≈ -∑(central difference of p over mask cells) × ΔV` and diverging deliberately from the 2D global-sum path (D-16).

**Primary recommendation:** Branch `FluidSimulator.__init__`, `step()`, and `compute_obstacle_forces` on `config.dim_3d` at the TOP of each method; the 2D branch is the existing code verbatim, the 3D branch is new code using the verified PhiFlow 3D calls. Add `dim_3d`/`grid_size`/`FluidCouplingMode`/`coupling_substeps` to `FluidConfig` additively; gate `grid_size`-required-when-`dim_3d=True` with a `model_validator(mode="after")` (per CLAUDE.md: return `self.model_copy(update={...})` — but for a hard `ValidationError` just `raise`). Do NOT touch the 2D `resolution`/`_cap_resolution` or the 2D `np.asarray` fallback line.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** `dim_3d: bool = Field(default=False)` on `FluidConfig`. Default `False` keeps 2D byte-identical.
- **D-02:** Separate `grid_size: tuple[int,int,int] | None = Field(default=None)` — do NOT overload `resolution`.
- **D-03:** `grid_size` REQUIRED when `dim_3d=True` → hard `ValidationError` (IS the SC#3 memory guard).
- **D-04:** `grid_size` allows anisotropic `(Nx,Ny,Nz)`; each dim independently bounded.
- **D-05:** 3D per-dim cap = 64; min 4; new `_cap_grid_size` validator distinct from `_cap_resolution` (2D cap 128 unchanged).
- **D-06:** 3D direct `(x,y,z)→(x,y,z)` mapping using full `BoundingBox.get_dimensions()`; 2D `(x,z)→(x,y)` unchanged.
- **D-07:** `__init__` branches on `dim_3d`: 2D byte-identical; 3D `Box(x=dx,y=dy,z=dz)` + `StaggeredGrid(0, ZERO, dom, x=Nx,y=Ny,z=Nz)` from `config.grid_size`.
- **D-08:** `step(dt)` dim-aware: `advect.mac_cormack` + `make_incompressible` on 3D grid; `union(*geoms)` preserved; `Solve(rel_tol=1e-4, abs_tol=1e-4, max_iterations=500)` reused.
- **D-09:** `FluidCouplingMode(str, Enum)` ONE_WAY="one_way" / TWO_WAY="two_way" mirroring `FluidBoundaryType`; `coupling_mode` default `ONE_WAY`.
- **D-10:** ONE_WAY = static SDF obstacles, no solid→fluid velocity feedback → stable on thin instruments; TWO_WAY = `Obstacle.velocity` feedback, opt-in, documented unstable (added-mass).
- **D-11:** ONE_WAY stability via (a) static SDF, (b) substepping via `coupling_substeps`, (c) per-axis independent force clamp in 3D `compute_obstacle_forces`. No cut-cell/SPD solver.
- **D-12:** `coupling_substeps: int = Field(default=4, ge=1, le=16)`; used only on 3D obstacle path; reuses `substep_dt` as per-substep dt.
- **D-13:** Default `coupling_substeps = 4` (explicit N choice supersedes "default 2" label).
- **D-14:** Thin instruments = cylinder shaft + box tip merged via `union(*geoms)`; mirror `Wake_Flow` `infinite_cylinder` pattern.
- **D-15:** Add `FluidSimulator.add_instrument(pose, dims)` building SDF → `add_obstacle(geometry, name)`. Raw `add_obstacle` unchanged.
- **D-16:** 3D `compute_obstacle_forces` returns `(fx, fy, fz)` (fy nonzero) via obstacle-mask integration; 2D global-sum + scalar-magnitude-clamp path byte-identical. Do NOT unify the two paths.
- **D-17:** 3D clamp is per-axis INDEPENDENT (each of fx/fy/fz clamped to per-axis cap independently, e.g. 1e4); 2D scalar-magnitude clamp unchanged.
- **D-18:** `render_fluid_3d(field, z_layer=...)` extracts a 2D z-layer slice and delegates to `render_fluid_2d`; NOT a true volume renderer.
- **D-19:** SC#1: existing 2D `test_fluid_simulator.py` suite passes unchanged; dedicated 2D baseline pins v0.5.0 output; 3D additions additive only.
- **D-20:** SC#4: SINGLE parametrized test over `(dim_3d=False, dim_3d=True) × (single, overlapping)` obstacles, N steps, assert finite velocity+pressure.
- **D-21:** SC#2 stability exercised at FluidSimulator level (NOT a full SurgicalEnv episode test); add thin instruments via `add_instrument`, run N steps ONE_WAY, assert no NaN; TWO_WAY variant asserts opt-in + documents instability.
- **D-22:** SC#5: `test_fluid_step.py` 5-test suite passes unchanged; hook remains env-driven no-op in both backends.
- **Non-GPU / CPU-first**, independent phase (parallelizable via worktrees alongside 36/37/39).

### Claude's Discretion
- `model_validator` vs `field_validator` for the `dim_3d⇒grid_size required` cross-field rule (D-03) and `_cap_grid_size` (D-05).
- Exact `add_instrument(pose, dims)` signature and `pose`/`dims` → geometry mapping (D-15).
- Exact PhiFlow mechanism for the 3D obstacle mask (D-16) — **RESOLVED below (OPEN Q B)**.
- Exact `render_fluid_3d` signature / slice axis / layer index (D-18).
- Whether new fields live on `FluidConfig` directly vs nested `Fluid3DConfig` sub-model (provided 2D fields/defaults untouched).
- Exact N (step count) for SC#2/SC#4 tests (provided large enough to surface NaN/blow-up).
- Naming of internal dim-3D branches and `coupling_substeps` bounds, provided semantics match.

### Deferred Ideas (OUT OF SCOPE)
- True 3D volume / iso-surface renderer.
- Wiring `add_instrument` + force application into the production `SurgicalEnv` episode loop (env-level instrument/fluid coupling).
- Two-way coupling stability fix (cut-cell / SPD monolithic solver).
- GPU fluid acceleration.
- Unifying the 2D global-sum and 3D obstacle-mask force paths.
- Anisotropic-domain auto-sizing of `grid_size` from `bounds` aspect ratio.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FLUID-01 | `dim_3d=True` enables 3D Eulerian grid fluids (3D `Box`/`StaggeredGrid` + 3D pressure projection); `dim_3d=False` default preserves validated 2D xz-slice behavior | Verified PhiFlow 3.4.0 3D construction (`Box(x,y,z)`+`StaggeredGrid(...,x,y,z)`) + `fluid.make_incompressible` 3D returns `(v,p)` with `spatial_rank=3` (smoke test confirmed). 2D path preserved by top-of-method branching (D-07/D-08). |
| FLUID-02 | 3D fluid/solid coupling stable with one-way coupling as default (two-way opt-in) on thin instruments | ONE_WAY = static-SDF obstacles (zero velocity, no feedback) → structurally stable; substepping via `coupling_substeps=4` reusing `substep_dt`; per-axis independent clamp (D-11/D-17). TWO_WAY opt-in via `FluidCouplingMode.TWO_WAY` + `Obstacle.velocity`, documented unstable. |
| FLUID-03 | 3D solver memory-bounded via separate smaller 3D `grid_size` + validator; `union(*geoms)` NaN-regression test covers 3D path | `_cap_grid_size` (min 4, cap 64) distinct from `_cap_resolution` (cap 128); `grid_size` required when `dim_3d=True` (hard `ValidationError` = SC#3 guard). SC#4 parametrized NaN-regression test covers both dims × single/overlapping obstacles. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| 3D grid construction (`Box(x,y,z)`+`StaggeredGrid`) | FluidSimulator (CPU solver) | — | Pure Eulerian grid solver; PhiFlow CPU-first (PROJECT.md). No GPU tier. |
| 3D pressure projection / advection | FluidSimulator `step()` | — | `fluid.make_incompressible` + `advect.mac_cormack` on 3D grid; same tier as 2D. |
| 3D obstacle SDF construction | FluidSimulator `add_instrument`/`add_obstacle` | — | Geometry built in solver; `union(*geoms)` workaround local to `step()`. |
| 3D obstacle-mask force integration | `compute_obstacle_forces` (force_computation.py) | — | Pressure-gradient integration over mask cells × cell volume → `(fx,fy,fz)`. |
| 3D grid size validation / memory guard | Pydantic `FluidConfig` schema | — | Hard `ValidationError` when `dim_3d=True` and `grid_size` missing; per-dim cap 64. |
| Coupling mode + substep config | Pydantic `FluidConfig` schema | FluidSimulator `step()` | Schema declares; solver consumes `coupling_mode`/`coupling_substeps`. |
| 3D visualization (z-layer slice) | `render_fluid_3d` (visualizer.py) | `render_fluid_2d` | Slice 3D field → delegate to 2D renderer. |
| Env fluid wiring | `SurgicalEnv._setup_fluid` | — | Dim-aware ctor absorbs 3D; NO env edit this phase (D-21). |
| `fluid_step` hook | `BaseSimulator.fluid_step` (no-op) | MuJoCo/PyBullet overrides | Unchanged no-op; SC#5. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `phi` (PhiFlow) | 3.4.0 (pin `phiflow>=3.4.0`) | Eulerian grid fluid solver: `Box`, `StaggeredGrid`, `fluid.make_incompressible`, `advect.mac_cormack`, `Solve`, `union`, `Obstacle` | Already the project's fluid backend (PROJECT.md decision "PhiFlow over Mantaflow"); 3D API confirmed working in-env. `[VERIFIED: in-env smoke test]` |
| `pydantic` | v2 | `FluidConfig` schema, `model_validator`, `field_validator`, str-Enum | Project standard (CLAUDE.md Pydantic v2 rules). `[VERIFIED: codebase]` |
| `numpy` | stdlib-ish | Pressure gradient central differences, mask array ops, slice extraction | Already used throughout `force_computation.py` / `visualizer.py`. `[VERIFIED: codebase]` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `phi.geom` | 3.4.0 | `infinite_cylinder`, `cylinder`, `Cuboid`, `Sphere`, `Geometry`, `union` | 3D obstacle SDF construction (`add_instrument`). `[VERIFIED: in-env smoke test]` |
| `phi.field` | 3.4.0 | `field.sample(geometry, grid)` → obstacle mask on pressure grid | 3D obstacle-mask force integration (OPEN Q B resolution). `[VERIFIED: in-env smoke test]` |
| `phi.math` | 3.4.0 | `vec`, math helpers | Geometry construction (`vec(x=,y=,z=)`). `[VERIFIED: in-env smoke test]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `phi.field.sample(geom, pressure)` for 3D mask | `CenteredGrid(geom, x=,y=,z=, bounds=dom)` | Both confirmed working; `field.sample` reuses the pressure grid's resolution/bounds directly → less duplication. `[VERIFIED: in-env smoke test]` |
| numpy `np.gradient(arr, axis=...)` for 3D pressure gradient | `math.spatial_gradient(p)` | `math.spatial_gradient` FAILS on Field objects in 3.4.0 (ValueError "Field not supported"); numpy path is the only working option and matches the 2D docstring formula. `[VERIFIED: in-env smoke test]` |
| `Fluid3DConfig` nested sub-model | Direct fields on `FluidConfig` | Direct fields simpler; nested model only if 2D fields risk contamination. Recommend direct fields (discretion). |

**Installation:** No new packages — `phi` 3.4.0 + `pydantic` v2 + `numpy` already installed. No `pip install` needed this phase.

**Version verification (in-env):**
```
phi==3.4.0 confirmed via `from phi.flow import ...` smoke tests (3D Box/StaggeredGrid/make_incompressible/advect/field.sample all returned valid 3D fields).
pydantic v2 confirmed via existing `FluidConfig` field_validator/model_validator usage in schema.py:1523-1532 and BoundingBox.validate_bounds (model_validator mode="after").
```

## Package Legitimacy Audit

No new external packages are installed this phase. All dependencies (`phi`, `pydantic`, `numpy`) are pre-existing project dependencies already verified in the lockfile/env.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| phi (PhiFlow) | PyPI | pre-existing | — | github.com/tum-pbs/PhiFlow | OK | Approved (already a project dep) |
| pydantic | PyPI | pre-existing | — | github.com/pydantic/pydantic | OK | Approved (already a project dep) |
| numpy | PyPI | pre-existing | — | github.com/numpy/numpy | OK | Approved (already a project dep) |

**Packages removed due to SLOP verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
FluidConfig(dim_3d, grid_size, coupling_mode, coupling_substeps)
        │
        ▼ (Pydantic validation: _cap_grid_size, dim_3d⇒grid_size required)
FluidSimulator.__init__(config)
        │
        ├── dim_3d=False ──► 2D Box(x=dx,y=dz) + StaggeredGrid(x=nx,y=ny)   [BYTE-IDENTICAL to v0.5.0]
        │
        └── dim_3d=True  ──► 3D Box(x=dx,y=dy,z=dz) + StaggeredGrid(x=Nx,y=Ny,z=Nz)
                                │
                                ▼  step(dt)
                    ┌───────────────────────────────────┐
                    │ advect.mac_cormack(v, v, dt)      │  (3D)
                    │ union(*geoms) workaround          │  (preserved)
                    │ fluid.make_incompressible(        │
                    │   v, [Obstacle(merged)],          │
                    │   solve=Solve(1e-4,1e-4,500))     │
                    │   → (velocity_3D, pressure_3D)    │
                    └───────────────────────────────────┘
                                │
                ┌───────────────┴────────────────┐
                ▼                                ▼
   compute_obstacle_forces            render_fluid_3d(field, z_layer)
   (dim_3d branch)                    │
        │                             ▼ slice p.values.numpy('x,y,z')[..., z_layer]
        │  mask = field.sample(       │
        │    geom, pressure)          └──► render_fluid_2d(sliced_2d_field, ...)
        │  mask_np = mask.numpy('x,y,z')
        │  p_np = pressure.values.numpy('x,y,z')
        │  grad via np.gradient(axis=...) over mask cells × ΔV
        │  → (fx, fy, fz) per obstacle
        │  per-axis INDEPENDENT clamp (|fx|,|fy|,|fz| ≤ 1e4)
        ▼
   forces dict {name: np.array([fx,fy,fz])}

   SurgicalEnv._setup_fluid → FluidSimulator(fluid_cfg)  [dim-aware ctor, NO env edit]
   SurgicalEnv.step() → env._fluid_simulator.step()       [dim-aware step]
   BaseSimulator.fluid_step(dt)                           [unchanged no-op hook, SC#5]
```

### Recommended Project Structure
```
src/surg_rl/
├── scene_definition/schema.py          # FluidConfig: +dim_3d, +grid_size, +FluidCouplingMode, +coupling_substeps, +_cap_grid_size, +dim_3d⇒grid_size validator
├── fluids/
│   ├── fluid_simulator.py              # FluidSimulator: dim-aware __init__/step, +add_instrument
│   ├── force_computation.py            # compute_obstacle_forces: +3D obstacle-mask branch (top-of-function)
│   ├── visualizer.py                   # +render_fluid_3d (z-layer slice → render_fluid_2d)
│   └── __init__.py                     # __all__ += render_fluid_3d
└── simulators/base_simulator.py        # fluid_step hook UNCHANGED (SC#5)

tests/test_fluids/
├── test_fluid_simulator.py             # UNCHANGED (2D regression) + 3D init/step tests (additive)
├── test_schema.py                      # +dim_3d/grid_size/coupling_mode/coupling_substeps validator tests
├── test_force_computation.py           # (new or extend) 3D obstacle-mask force + per-axis clamp
└── test_nan_regression.py              # (new) SC#4 parametrized over (dim_3d) × (single, overlapping)
tests/test_fluid_step.py                # UNCHANGED (SC#5)
```

### Pattern 1: Top-of-Method dim Branching (Additive-Regression Gate)
**What:** Branch on `config.dim_3d` at the TOP of `__init__`, `step()`, and `compute_obstacle_forces`. The 2D branch is the existing code verbatim; the 3D branch is new.
**When to use:** Every method that has dim-specific PhiFlow calls.
**Why:** Guarantees the 2D path is byte-identical (SC#1). A single `if config.dim_3d:` block at the top returns/branches before any 2D code runs; the 2D code below is untouched.
**Example:**
```python
# Source: verified pattern matching existing fluid_simulator.py:66-82 + smoke-tested 3D calls
def __init__(self, config: FluidConfig):
    from phi.flow import Box, StaggeredGrid, extrapolation
    if not config.enabled:
        raise ValueError("FluidConfig.enabled must be True")
    self.config = config
    dims = config.bounds.get_dimensions()
    if config.dim_3d:
        # 3D branch (NEW)
        domain = Box(x=float(dims[0]), y=float(dims[1]), z=float(dims[2]))
        nx, ny, nz = config.grid_size  # guaranteed non-None by schema validator
        self._velocity = StaggeredGrid(0.0, extrapolation.ZERO, domain, x=nx, y=ny, z=nz)
    else:
        # 2D branch (BYTE-IDENTICAL to v0.5.0)
        domain = Box(x=float(dims[0]), y=float(dims[2]))
        self._velocity = StaggeredGrid(0.0, extrapolation.ZERO, domain,
                                       x=config.resolution[0], y=config.resolution[1])
    self._pressure = None
    self._obstacles = []
    self._obstacle_names = []
    self._sim_time = 0.0
```

### Pattern 2: 3D Obstacle-Mask Force Integration (D-16/D-17)
**What:** Compute `(fx, fy, fz)` by integrating the pressure gradient over each obstacle's mask cells × cell volume, per axis, with independent per-axis clamp.
**When to use:** The 3D `compute_obstacle_forces` branch only.
**Example:**
```python
# Source: in-env smoke-test confirmed calls (phi.field.sample + np.gradient + numpy('x,y,z'))
import phi.field as field
import numpy as np

def _compute_obstacle_forces_3d(velocity, pressure, obstacles, config):
    """3D obstacle-mask integration → (fx, fy, fz). Per-axis INDEPENDENT clamp."""
    dims = config.bounds.get_dimensions()
    nx, ny, nz = config.grid_size
    dx, dy, dz = dims[0]/nx, dims[1]/ny, dims[2]/nz
    cell_vol = dx * dy * dz
    p_np = pressure.values.numpy('x,y,z')   # explicit dim order (REQUIRED in phi 3.4.0)
    grad_x = np.gradient(p_np, axis=0)      # ∂p/∂x
    grad_y = np.gradient(p_np, axis=1)      # ∂p/∂y
    grad_z = np.gradient(p_np, axis=2)      # ∂p/∂z
    forces = {}
    for obs, name in zip(obstacles, ...):   # iterate original obstacles (per-obstacle mask)
        mask = field.sample(obs.geometry, pressure)        # Dense tensor on pressure grid
        mask_np = mask.numpy('x,y,z')                      # {0.0, 1.0}
        fx = -float(np.sum(grad_x * mask_np)) * cell_vol
        fy = -float(np.sum(grad_y * mask_np)) * cell_vol
        fz = -float(np.sum(grad_z * mask_np)) * cell_vol
        # Per-axis INDEPENDENT clamp (D-17)
        cap = 1e4
        fx = max(-cap, min(cap, fx))
        fy = max(-cap, min(cap, fy))
        fz = max(-cap, min(cap, fz))
        forces[name] = np.array([fx, fy, fz], dtype=np.float64)
    return forces
```

### Pattern 3: Pydantic v2 Cross-Field Validator (dim_3d ⇒ grid_size required)
**What:** `model_validator(mode="after")` raises `ValidationError` when `dim_3d=True` and `grid_size is None`. This hard-error IS the SC#3 memory guard.
**When to use:** Cross-field rule that depends on two fields' values simultaneously (cannot be a `field_validator` on `grid_size` alone because the rule only fires when `dim_3d=True`).
**Example:**
```python
# Source: CLAUDE.md Pydantic v2 rules + existing BoundingBox.validate_bounds pattern (schema.py:196)
from pydantic import model_validator, field_validator

class FluidConfig(BaseModel):
    # ... existing fields unchanged ...
    dim_3d: bool = Field(default=False, description="Enable 3D Eulerian grid fluids")
    grid_size: tuple[int, int, int] | None = Field(
        default=None,
        description="3D grid resolution (Nx,Ny,Nz); REQUIRED when dim_3d=True. "
                    "Recommended 24³=(24,24,24). Each dim capped at 64.",
    )
    coupling_mode: FluidCouplingMode = Field(default=FluidCouplingMode.ONE_WAY)
    coupling_substeps: int = Field(default=4, ge=1, le=16,
        description="Internal coupling substeps per env step on the 3D obstacle path.")

    @field_validator("grid_size")
    @classmethod
    def _cap_grid_size(cls, v: tuple[int,int,int] | None) -> tuple[int,int,int] | None:
        if v is None:
            return v
        if len(v) != 3:
            raise ValueError("grid_size must be (Nx, Ny, Nz)")
        if any(d < 4 for d in v):
            raise ValueError("grid_size must be at least 4 in each dimension")
        if any(d > 64 for d in v):
            raise ValueError("grid_size capped at 64 per dimension (3D memory guard)")
        return v

    @model_validator(mode="after")
    def _require_grid_size_when_dim_3d(self) -> "FluidConfig":
        if self.dim_3d and self.grid_size is None:
            raise ValueError("grid_size is REQUIRED when dim_3d=True (SC#3 memory guard). "
                             "Recommended 24³=(24,24,24).")
        return self  # CLAUDE.md: in mode="after" prefer model_copy for mutation; here we only raise, so return self.
```

### Anti-Patterns to Avoid
- **Unifying 2D and 3D force paths** — D-16 explicitly forbids; the 2D global-sum + scalar-magnitude-clamp path must stay byte-identical. Do NOT refactor `compute_obstacle_forces` to share code between dims.
- **Overloading `resolution` for 3D** — D-02; `resolution` stays 2-tuple-only with `_cap_resolution` unchanged. Use the separate `grid_size` field.
- **Silent default for `grid_size`** — D-03/specifics; a silent auto-fill hides the cubic memory cost. The hard `ValidationError` IS the guard.
- **Calling `pressure.values.numpy()` with no dim order in 3D** — AssertionError in phi 3.4.0 (confirmed). ALWAYS pass `'x,y,z'` (3D) / `'x,y'` (2D if ever touched).
- **Touching the 2D `np.asarray` fallback line in `force_computation.py:29-34`** — that line is how the 2D path currently survives the no-order `numpy()` failure (OPEN Q A). Editing it risks the SC#1 byte-identical gate.
- **Aligning the 2D `(x,z)→(x,y)` and 3D `(x,y,z)→(x,y,z)` mappings** — D-06/specifics; deliberately distinct, do not unify.
- **Using `math.spatial_gradient(p)` / `math.grad` / `p.dx` as the 3D gradient** — confirmed broken/wrong in phi 3.4.0 (OPEN Q C). Use `np.gradient(p_np, axis=...)`.
- **`sed`/`echo -e` for multi-line edits** — CLAUDE.md forbids; use `Edit` or `python -c "pathlib.Path(...).write_text(...)"`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 3D incompressible pressure projection | Custom Poisson solver | `fluid.make_incompressible(v, obstacles, solve=Solve(...))` | PhiFlow's validated 3D solver; confirmed working in 3D in-env. `[VERIFIED: in-env smoke test]` |
| 3D advection | Custom semi-Lagrangian | `advect.mac_cormack(field, velocity, dt)` | Confirmed working in 3D in-env. `[VERIFIED: in-env smoke test]` |
| Multi-obstacle SDF merge | Per-obstacle boundary-condition stitching | `union(*geoms)` → single `Obstacle` | The existing DEBT-05 workaround; preserved for both dims. `[VERIFIED: codebase fluid_simulator.py:118]` |
| 3D obstacle mask rasterization | Custom point-in-geometry loop | `phi.field.sample(geometry, pressure_grid)` | Confirmed returns `{0.0, 1.0}` mask on pressure grid (sum=384 for test cylinder). `[VERIFIED: in-env smoke test]` |
| 3D pressure gradient | Custom finite-difference stencil on PhiFlow field | `np.gradient(p_np, axis=...)` over `pressure.values.numpy('x,y,z')` | Matches the 2D docstring formula; `math.spatial_gradient` is broken on Field objects. `[VERIFIED: in-env smoke test]` |
| 3D thin-instrument SDF | Custom mesh/SDF | `infinite_cylinder(x=, y=, radius=, inf_dim='z')` + `Box` tip via `union(*geoms)` | Mirrors PhiFlow `Wake_Flow` 3D example (D-14/canonical_refs). `[VERIFIED: in-env smoke test]` |
| Cross-field Pydantic validation | Manual post-init check | `@model_validator(mode="after")` | Pydantic v2 standard; matches existing `BoundingBox.validate_bounds`. `[CITED: CLAUDE.md Pydantic v2 rules]` |

**Key insight:** PhiFlow 3.4.0 already provides every 3D primitive this phase needs (`Box`, `StaggeredGrid`, `make_incompressible`, `advect.mac_cormack`, `infinite_cylinder`, `union`, `field.sample`). The only hand-rolled code is the numpy pressure-gradient + mask integration, which mirrors the existing 2D docstring formula and is the documented D-16 approach.

## Runtime State Inventory

> SKIPPED — this is a greenfield-additive phase (new `dim_3d` branch + new schema fields), not a rename/refactor/migration. No stored data, live service config, OS-registered state, secrets, or build artifacts embed the renamed string. The 2D path is preserved byte-identical; nothing is renamed.

## Common Pitfalls

### Pitfall 1: `pressure.values.numpy()` with no dim order fails in phi 3.4.0
**What goes wrong:** `AssertionError: ... dimension order must be specified for Tensors with more than one dim`.
**Why it happens:** PhiFlow 3.4.0 requires explicit dim order for any tensor with >1 dim. The existing 2D `force_computation.py:29` calls `pressure.values.numpy()` with NO order — this RAISES, and the 2D path survives ONLY via the `np.asarray(pressure.values, dtype=np.float64)` fallback on lines 31-32 (confirmed in-env: the fallback succeeds and returns a (32,32) array).
**How to avoid:** The 3D branch MUST call `pressure.values.numpy('x,y,z')` explicitly. Do NOT touch the 2D fallback lines (SC#1 byte-identical). Branch on `config.dim_3d` at the top of `compute_obstacle_forces`: 3D uses explicit-order `.numpy('x,y,z')`; 2D falls through to the existing code verbatim.
**Warning signs:** `SyntaxWarning: Automatic conversion of Φ-ML tensors to NumPy can cause problems because the dimension order is not guaranteed.` → you forgot the dim order.

### Pitfall 2: `math.spatial_gradient` / `math.grad` / `p.dx` are NOT the 3D pressure gradient
**What goes wrong:** `math.spatial_gradient(p3)` → `ValueError: Field not supported`; `math.grad` → `AttributeError: module 'phi.math' has no attribute 'grad'`; `p3.dx` returns a `Dense` with shape `(vectorᶜ=x,y,z)` — that's the **cell-spacing vector**, NOT `∂p/∂x`.
**Why it happens:** PhiFlow 3.4.0's `math.spatial_gradient` only accepts Tensors, not Field objects; `.dx`/`.dy`/`.dz` are grid spacing, not gradient operators.
**How to avoid:** Use `p_np = pressure.values.numpy('x,y,z')` then `np.gradient(p_np, axis=0/1/2)` for `∂p/∂x`/`∂p/∂y`/`∂p/∂z`. This matches the 2D docstring formula and is the D-16 recommended approach.
**Warning signs:** Any code referencing `math.spatial_gradient(field)` or `field.dx` as a gradient.

### Pitfall 3: `infinite_cylinder` is NOT in `phi.flow` (only `phi.geom`)
**What goes wrong:** `ImportError: cannot import name 'infinite_cylinder' from 'phi.flow'`.
**Why it happens:** `phi.flow` re-exports `cylinder`, `union`, `Geometry`, `Obstacle`, `Box` but NOT `infinite_cylinder`.
**How to avoid:** Import as `from phi.geom import infinite_cylinder` (confirmed working). `phi.geom` also has `cylinder`, `Cuboid`, `Sphere`.
**Warning signs:** Import errors at module load.

### Pitfall 4: `infinite_cylinder` lacks `approximate_fraction`
**What goes wrong:** `AttributeError: '_EmbeddedGeometry' instance has no attribute 'approximate_fraction'`. Same for `Box`/`Cuboid`.
**Why it happens:** The `approximate_fraction` method is not exposed on these geometry types in 3.4.0.
**How to avoid:** Use `phi.field.sample(geometry, pressure_grid)` to obtain the mask (confirmed returns `{0.0, 1.0}` Dense tensor). Alternative: `CenteredGrid(geometry, x=,y=,z=, bounds=dom)`.
**Warning signs:** Any code calling `geom.approximate_fraction(grid)`.

### Pitfall 5: Pydantic v2 `model_validator(mode="after")` mutation
**What goes wrong:** Mutating `self` directly inside `mode="after"` can silently lose changes because Pydantic may internally copy the model.
**How to avoid:** Per CLAUDE.md: use `self.model_copy(update={...})` when you need to SET a field. For a pure raise-on-invalid validator (the `dim_3d⇒grid_size` rule), just `raise ValueError(...)` and `return self` — no mutation needed.
**Warning signs:** Validator runs but the change doesn't appear on the instance.

### Pitfall 6: Enum in `model_dump()` stays as Enum object
**What goes wrong:** `yaml.dump(config.model_dump())` raises `RepresenterError` because `FluidCouplingMode.ONE_WAY` is dumped as the Enum object, not `"one_way"`.
**How to avoid:** Per CLAUDE.md: convert Enum values before YAML serialization (`coupling_mode.value`). Mirror whatever the existing `FluidBoundaryType` serialization path does.
**Warning signs:** YAML dump errors in test_serialization-style tests.

### Pitfall 7: `union(*geoms)` NaN regression in 3D (SC#4)
**What goes wrong:** Overlapping zero-velocity regions from multiple obstacles crash the pressure solver (ill-conditioned Poisson; `Solve` exceeds `max_iterations`) → NaN/Inf in velocity/pressure.
**How to avoid:** The existing `union(*geoms)` → single `Obstacle` workaround is preserved for both dims. SC#4 parametrized test asserts finite velocity+pressure after N steps for `(dim_3d=False, dim_3d=True) × (single, overlapping)`.
**Warning signs:** `Solve` warnings in logs; `np.any(~np.isfinite(p.values.numpy('x,y,z')))` True.

### Pitfall 8: TWO_WAY coupling blow-up on thin instruments (D-10/D-13)
**What goes wrong:** `Obstacle.velocity` feedback introduces an added-mass term that destabilizes the solve on thin/light solids.
**How to avoid:** ONE_WAY is the default (static SDF, no feedback). TWO_WAY is opt-in via `FluidCouplingMode.TWO_WAY` and DOCUMENTED unstable — do NOT attempt to fix it this phase (cut-cell/SPD solver is deferred). The per-axis clamp is a best-effort brake, not a stability guarantee.
**Warning signs:** NaN in TWO_WAY test variant — expected; the test asserts opt-in + documents instability, NOT stability.

## Code Examples

### 3D Wake-Flow-style construction + step (verified in-env)
```python
# Source: in-env smoke test (phi 3.4.0, pyenv 3.13.3) + Wake_Flow example pattern
from phi.flow import Box, StaggeredGrid, extrapolation, fluid, Solve, advect, Obstacle, union

dom = Box(x=0.3, y=0.3, z=0.3)
v = StaggeredGrid(0.0, extrapolation.ZERO, dom, x=16, y=16, z=16)
# v.spatial_rank == 3, v.shape == (xˢ=16, yˢ=16, zˢ=16, vectorᶜ=x,y,z)

v, p = fluid.make_incompressible(v, solve=Solve(rel_tol=1e-4, abs_tol=1e-4, max_iterations=500))
# p.spatial_rank == 3, p.shape == (xˢ=16, yˢ=16, zˢ=16)

# Advection in 3D
v = advect.mac_cormack(v, v, 0.02)  # works in 3D

# With obstacle via union(*geoms) workaround
from phi.geom import infinite_cylinder
c = infinite_cylinder(x=0.15, y=0.15, radius=0.05, inf_dim='z')
v, p = fluid.make_incompressible(v, obstacles=[Obstacle(c)],
                                 solve=Solve(rel_tol=1e-4, abs_tol=1e-4, max_iterations=500))
```

### 3D obstacle mask + pressure gradient (verified in-env)
```python
# Source: in-env smoke test — confirmed mask sum=384.0 (16 z-layers × ~24-cell circle)
import phi.field as field
import numpy as np

mask = field.sample(c, p)              # Dense tensor on p's grid, values {0.0, 1.0}
mask_np = mask.numpy('x,y,z')          # explicit dim order REQUIRED
p_np = p.values.numpy('x,y,z')         # explicit dim order REQUIRED
grad_x = np.gradient(p_np, axis=0)     # ∂p/∂x
grad_y = np.gradient(p_np, axis=1)     # ∂p/∂y
grad_z = np.gradient(p_np, axis=2)     # ∂p/∂z
cell_vol = (0.3/16) ** 3
fx = -float(np.sum(grad_x * mask_np)) * cell_vol
fy = -float(np.sum(grad_y * mask_np)) * cell_vol
fz = -float(np.sum(grad_z * mask_np)) * cell_vol
```

### Proposed `add_instrument` signature (D-15, Claude's discretion)
```python
# Source: D-14/D-15 + Wake_Flow infinite_cylinder pattern; planner confirms exact pose/dims shapes
def add_instrument(
    self,
    pose: "Pose",              # InstrumentConfig.pose — Position + orientation; guard Optional (CLAUDE.md)
    dims: tuple[float, float, float],  # (shaft_radius, shaft_length, tip_half_size)
    name: str = "instrument",
) -> None:
    """Construct cylinder-shaft + box-tip SDF, merge via union(*geoms), call add_obstacle.

    3D only (raises if not config.dim_3d). Shaft aligned along the instrument's
    long axis; tip modeled as a small Box at the shaft end.
    """
    from phi.geom import infinite_cylinder
    from phi.flow import Box, union, vec
    if not self.config.dim_3d:
        raise ValueError("add_instrument is 3D-only; enable FluidConfig.dim_3d=True")
    # shaft: infinite cylinder along z (or oriented per pose)
    shaft = infinite_cylinder(x=pose.position.x, y=pose.position.y,
                              radius=dims[0], inf_dim='z')
    # tip: small box at shaft end
    tip = Box(vec(x=pose.position.x, y=pose.position.y, z=pose.position.z + dims[1]),
              half_size=vec(x=dims[2], y=dims[2], z=dims[2]))
    merged = union(shaft, tip)
    self.add_obstacle(merged, name)   # raw add_obstacle unchanged (D-15)
```

### Proposed `render_fluid_3d` signature (D-18, Claude's discretion)
```python
# Source: D-18 + visualizer.py:10 render_fluid_2d signature; planner confirms exact field/slice convention
def render_fluid_3d(
    pressure: Any | None,       # 3D CenteredGrid
    config: Any,
    z_layer: int | None = None, # None → middle z-layer
    width: int = 400,
    height: int = 400,
) -> np.ndarray | None:
    """Render a 2D z-layer slice of a 3D pressure field via render_fluid_2d."""
    if pressure is None:
        return None
    p_np = pressure.values.numpy('x,y,z')          # (Nx, Ny, Nz)
    nz = p_np.shape[2]
    layer = z_layer if z_layer is not None else nz // 2
    slice_2d = p_np[:, :, layer]                    # (Nx, Ny) 2D slice
    # Wrap as a 2D-ish object render_fluid_2d can consume, or refactor render_fluid_2d
    # to accept a plain numpy array. Simplest: build a thin wrapper exposing `.values.numpy('x,y')`
    # OR refactor render_fluid_2d to accept np.ndarray directly (additive — keep 2D path working).
    return _render_np_2d(slice_2d, width, height)   # delegate to the 2D rendering body
```
**Planner note:** `render_fluid_2d` currently calls `pressure.values.numpy()` (no order) and falls back to `np.asarray(pressure.values)`. The cleanest additive approach is to extract the 2D rendering body into a private `_render_np_2d(arr, width, height)` helper, have `render_fluid_2d` keep its current signature (2D byte-identical), and have `render_fluid_3d` slice → call `_render_np_2d` directly. Do NOT modify `render_fluid_2d`'s 2D extraction path (SC#1).

### 2D byte-identical regression fixture (SC#1/D-19)
```python
# Source: existing tests/test_fluids/test_fluid_simulator.py fixture + D-19
@pytest.fixture
def basic_config_2d() -> FluidConfig:   # UNCHANGED fixture (do not edit existing one)
    return FluidConfig(
        enabled=True,
        bounds=BoundingBox(min_corner=Position(x=0.0,y=0.0,z=0.0),
                           max_corner=Position(x=0.3,y=0.0,z=0.3)),
        resolution=(32, 32),
    )
# 3D fixture (NEW, additive)
@pytest.fixture
def basic_config_3d() -> FluidConfig:
    return FluidConfig(
        enabled=True,
        dim_3d=True,
        grid_size=(16, 16, 16),
        bounds=BoundingBox(min_corner=Position(x=0.0,y=0.0,z=0.0),
                           max_corner=Position(x=0.3,y=0.3,z=0.3)),
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 2D-only Eulerian fluid (xz-slice) | 3D opt-in via `dim_3d=True` flag, 2D preserved | Phase 38 (this phase) | 3D fluids now available behind explicit opt-in; 2D scenes unchanged. |
| `make_incompressible` top-level import | `fluid.make_incompressible` (module-qualified) | phi 3.4.0 | Existing code already uses `fluid.make_incompressible` (fluid_simulator.py:122); 3D branch mirrors. `[VERIFIED: codebase]` |
| `geom.approximate_fraction` mask sampling (older PhiFlow) | `phi.field.sample(geometry, grid)` mask sampling | phi 3.4.0 | `approximate_fraction` not exposed on `infinite_cylinder`/`Box` in 3.4.0; `field.sample` is the working API. `[VERIFIED: in-env smoke test]` |
| `math.reshaped_native(t, ['x','y','z'])` | `Tensor.native('x,y,z')` / `Tensor.numpy('x,y,z')` | phi 3.4.0 | `reshaped_native` DEPRECATED; use `.numpy('x,y,z')` with explicit dim order. `[VERIFIED: in-env smoke test]` |

**Deprecated/outdated:**
- `math.reshaped_native(...)` — deprecated; use `Tensor.native('x,y,z')` or `Tensor.numpy('x,y,z')`.
- `geom.approximate_fraction(grid)` — not available on `infinite_cylinder`/`Box`/`Cuboid` in 3.4.0; use `phi.field.sample(geom, grid)`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `add_instrument` `pose`/`dims` mapping (shaft=infinite_cylinder along z, tip=Box at shaft end) is the right shape contract | Code Examples / D-15 | Low — planner confirms exact signature against `InstrumentConfig.pose`/`Pose` shape; `pose` is `Optional[Pose]` so must guard. `[ASSUMED]` |
| A2 | `render_fluid_3d` should slice `p_np[:,:,layer]` (xy-plane at fixed z) | Code Examples / D-18 | Low — Claude's discretion; planner may pick a different slice axis; semantics (delegate to 2D renderer) are fixed by D-18. `[ASSUMED]` |
| A3 | The 2D `np.asarray` fallback in `force_computation.py:31-32` is the actual code path the 2D tests exercise (not the `.numpy()` line) | Pitfall 1 / OPEN Q A | Confirmed in-env (2D `.numpy()` no-order raises AssertionError; `np.asarray` fallback succeeds). `[VERIFIED: in-env smoke test]` |
| A4 | Per-axis clamp cap value of `1e4` (matches the existing 2D scalar magnitude cap) | D-17 / Pattern 2 | Low — D-17 says "e.g. 1e4"; planner may confirm or pick a different per-axis cap; matches 2D's `1e4` for consistency. `[ASSUMED]` |
| A5 | `field.sample(geom, pressure)` returns the mask in the pressure grid's coordinate frame with values {0.0, 1.0} (binary) | Pattern 2 / OPEN Q B | Confirmed in-env (sum=384.0, min=0.0, max=1.0 for the test cylinder). `[VERIFIED: in-env smoke test]` |

## Open Questions (RESOLVED)

1. **Exact `add_instrument` `pose`/`dims` contract** (D-15) — proposed `(pose: Pose, dims: tuple[float,float,float], name: str)`. Planner confirms against `InstrumentConfig.pose` (Optional[Pose], CLAUDE.md guard) and the instrument geometry convention. **Recommendation:** proceed with proposed signature; mark `add_instrument` 3D-only (raises if `not config.dim_3d`). **— RESOLVED:** Plan 02 Task 2 (GREEN) implements `add_instrument(pose, dims, name="instrument")` with `ValueError("add_instrument requires dim_3d=True")` when `not config.dim_3d` and a `pose is None` guard (D-15).
2. **Exact N (step count) for SC#2/SC#4 NaN-regression tests** — D-20/D-21 say "large enough to surface NaN/blow-up". **Recommendation:** SC#4 N=50 steps (matches the existing `test_step_with_obstacle_stable` 5-step pattern scaled up to catch instability); SC#2 ONE_WAY N=100 steps. Planner decides final N. **— RESOLVED:** Plan 04 Task 2 sets SC#2 ONE_WAY N=100; Plan 04 Task 3 sets SC#4 N=50 (parametrized `(dim_3d=False, dim_3d=True) × (single, overlapping)`).
3. **Whether `render_fluid_2d` should be refactored to share a `_render_np_2d` helper with `render_fluid_3d`** — recommended for cleanliness but requires touching `render_fluid_2d` internals. **Recommendation:** extract `_render_np_2d` as a private helper; `render_fluid_2d` keeps its exact public behavior (calls the helper after extraction). Add a 2D byte-identical regression test (image hash or array-equality) to SC#1 to guard the refactor. **— RESOLVED:** Plan 03 Task 2 (GREEN) extracts the `_render_np_2d` private helper; `render_fluid_2d` delegates to it with unchanged public behavior; the SC#1 2D byte-identical regression test (Plan 04 Task 1) guards the refactor.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | all | ✓ | 3.13.3 (pyenv) | — |
| `phi` (PhiFlow) | 3D fluid solver | ✓ | 3.4.0 | — |
| `pydantic` | schema | ✓ | v2 | — |
| `numpy` | force/gradient/mask | ✓ | stdlib | — |
| `scikit-image` | `render_fluid_2d` resize | ✓ | (existing dep) | — |
| GPU | (not required — CPU-first) | — | — | CPU solver (PROJECT.md) |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none.

## Validation Architecture

Nyquist validation is ENABLED (`workflow.nyquist_validation: true`).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | `pytest.ini` (marker registry) |
| Quick run command | `PYTHONPATH=src pytest tests/test_fluids/ -v` |
| Full suite command | `PYTHONPATH=src pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FLUID-01 | 3D construct + step produces 3D pressure | unit/integration | `PYTHONPATH=src pytest tests/test_fluids/test_fluid_simulator.py -k "3d" -v` | ❌ Wave 0 (additive) |
| FLUID-01 | 2D byte-identical output (SC#1) | regression (array-equality / hash) | `PYTHONPATH=src pytest tests/test_fluids/test_2d_baseline.py -v` | ❌ Wave 0 |
| FLUID-02 | ONE_WAY stable over N steps, no NaN | integration (N=100) | `PYTHONPATH=src pytest tests/test_fluids/test_3d_coupling.py -k "one_way" -v` | ❌ Wave 0 |
| FLUID-02 | TWO_WAY opt-in + documented unstable | integration (opt-in gate) | `PYTHONPATH=src pytest tests/test_fluids/test_3d_coupling.py -k "two_way" -v` | ❌ Wave 0 |
| FLUID-03 | `grid_size` required when `dim_3d=True` → ValidationError | unit | `PYTHONPATH=src pytest tests/test_fluids/test_schema.py -k "grid_size or dim_3d" -v` | ❌ Wave 0 (extend existing) |
| FLUID-03 | `_cap_grid_size` rejects <4, >64, wrong len | unit | `PYTHONPATH=src pytest tests/test_fluids/test_schema.py -k "cap_grid_size" -v` | ❌ Wave 0 (extend existing) |
| FLUID-03 | SC#4 NaN-regression parametrized (2D×3D)×(single×overlap) | regression (N=50, finite-assert) | `PYTHONPATH=src pytest tests/test_fluids/test_nan_regression.py -v` | ❌ Wave 0 |
| SC#5 | `fluid_step` hook unchanged (5-test suite) | regression | `PYTHONPATH=src pytest tests/test_fluid_step.py -v` | ✅ (must pass unchanged) |

### Sampling Rate (Nyquist for fluid instability)
The instability mode of interest is NaN/blow-up in velocity/pressure over steps. To catch it, sample EVERY step (not every Nth) for the first N steps and assert `np.all(np.isfinite(...))` per step. The Nyquist reasoning: the fastest instability mode is a per-step divergence, so per-step sampling is the minimum rate to catch it.
- **Per task commit (quick):** `PYTHONPATH=src pytest tests/test_fluids/ -v` (finite-output + schema + 2D-baseline).
- **Per wave merge (full fluid):** `PYTHONPATH=src pytest tests/test_fluids/ tests/test_fluid_step.py -v` (all fluid + hook regression).
- **Phase gate (SC#1/SC#5 byte-identical):** `PYTHONPATH=src pytest tests/ -v` full suite green before `/gsd-verify-work`. Includes the 5-test `test_fluid_step.py` suite UNCHANGED and the 2D `test_fluid_simulator.py` suite UNCHANGED.

### Validation Dimensions (mapped to the 5 SCs)
| Dimension | SC | Approach |
|-----------|----|----------|
| D1 finite-output correctness | SC#1/SC#4 | Per-step `np.isfinite` on velocity+pressure for both dims. |
| D2 2D byte-identical regression | SC#1 | Array-equality (or hash) of velocity+pressure output for `dim_3d=False` against a v0.5.0 baseline fixture. Existing 2D suite passes unchanged. |
| D3 3D stability over N steps | SC#2/SC#4 | N=100 ONE_WAY steps with thin instruments via `add_instrument`; assert no NaN/blow-up. TWO_WAY variant asserts opt-in + documents instability (assert it RAISES or documents, NOT that it's stable). |
| D4 memory-bounded grid_size validation | SC#3 | Pydantic `ValidationError` on `dim_3d=True` + `grid_size=None`; `_cap_grid_size` rejects <4, >64, wrong len; anisotropic (64,32,64) accepted. |
| D5 fluid_step hook unchanged | SC#5 | Existing 5-test `test_fluid_step.py` suite passes unchanged. |

### Wave 0 Gaps
- [ ] `tests/test_fluids/test_2d_baseline.py` — SC#1 2D byte-identical baseline (velocity+pressure array-equality for the existing 2D fixture).
- [ ] `tests/test_fluids/test_3d_coupling.py` — SC#2 ONE_WAY N-step stability + TWO_WAY opt-in gate.
- [ ] `tests/test_fluids/test_nan_regression.py` — SC#4 parametrized `(dim_3d=False, dim_3d=True) × (single, overlapping)` N-step finite-assert.
- [ ] Extend `tests/test_fluids/test_schema.py` — `dim_3d`/`grid_size`/`coupling_mode`/`coupling_substeps` validators (required-when, cap, anisotropic, defaults).
- [ ] Extend `tests/test_fluids/test_fluid_simulator.py` — 3D init/step/obstacle tests (additive; do NOT edit existing 2D tests).
- [ ] Extend `tests/test_fluids/test_force_computation.py` (or new) — 3D obstacle-mask force `(fx,fy,fz)` + per-axis independent clamp.
- [ ] `tests/test_fluids/test_render_fluid_3d.py` — z-layer slice delegation.
- [ ] Framework install: none (pytest already installed).

## Security Domain

> This phase is a pure CPU fluid-solver + Pydantic schema addition with no authentication, session, network, cryptography, or untrusted-input surface. The fluid config is loaded from the same trusted JSON/YAML scene files already validated by `scene_definition/loader.py`. `security_enforcement` is not the focus of this phase; no ASVS categories apply beyond the existing input-validation hygiene already enforced by Pydantic on `FluidConfig`.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — (no auth surface) |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes (light) | Pydantic v2 `field_validator`/`model_validator` on `FluidConfig` (dim_3d⇒grid_size required, `_cap_grid_size` bounds) — rejects invalid configs at load time. |
| V6 Cryptography | no | — |

### Known Threat Patterns for PhiFlow fluid config
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious scene file sets `grid_size=(1024,1024,1024)` → OOM DoS | Denial of Service | `_cap_grid_size` rejects >64 per dim (SC#3 memory guard). |
| Malicious scene file omits `grid_size` with `dim_3d=True` → silent cubic default → OOM | Denial of Service | `model_validator` raises `ValidationError` (hard error, no silent default). |

## Sources

### Primary (HIGH confidence)
- In-env smoke tests (pyenv 3.13.3, `phi==3.4.0`): 3D `Box`/`StaggeredGrid`/`make_incompressible`/`advect.mac_cormack` confirmed working; `phi.field.sample(geom, pressure)` returns `{0.0,1.0}` mask (sum=384); `pressure.values.numpy('x,y,z')` works with explicit order; `np.gradient(arr, axis=...)` works; `math.spatial_gradient`/`math.grad`/`p.dx` confirmed broken/wrong; `infinite_cylinder` importable from `phi.geom` only; `approximate_fraction` absent on `infinite_cylinder`/`Box`/`Cuboid`.
- Codebase: `src/surg_rl/fluids/fluid_simulator.py` (2D construction + `union(*geoms)` workaround + `Solve(...)` settings), `force_computation.py` (2D `np.asarray` fallback path — confirmed is the live 2D code path), `visualizer.py` (`render_fluid_2d`), `scene_definition/schema.py:1500-1532` (`FluidConfig` + `_cap_resolution` + `FluidBoundaryType` str-Enum + `BoundingBox.validate_bounds` model_validator pattern), `base_simulator.py:336` (`fluid_step` no-op hook).
- `tests/test_fluids/test_fluid_simulator.py` + `tests/test_fluids/test_schema.py` + `tests/test_fluid_step.py` (existing 2D/hook test patterns to mirror + keep unchanged).

### Secondary (MEDIUM confidence)
- CLAUDE.md (Pydantic v2 `model_validator(mode="after")` mutation rule, testing rules, no-sed/echo rule).
- `.planning/phases/38-fluid-3d-flag-dim-3d-true/38-CONTEXT.md` (D-01..D-22 locked decisions).
- PhiFlow `Wake_Flow` 3D example (canonical_refs) — `infinite_cylinder` + `Box(x,y,z)` + `StaggeredGrid(x,y,z)` pattern. `[CITED: https://tum-pbs.github.io/PhiFlow/examples/grids/Wake_Flow.html]`

### Tertiary (LOW confidence)
- None — all findings verified or cited.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — `phi` 3.4.0 3D API confirmed in-env via smoke tests; `pydantic` v2 + `numpy` already project standard.
- Architecture: HIGH — top-of-method dim branching pattern guarantees 2D byte-identical; verified 3D calls drop directly into the new branch.
- Pitfalls: HIGH — all pitfalls confirmed in-env (numpy dim-order, `math.spatial_gradient` broken, `infinite_cylinder` import path, `approximate_fraction` absent).
- Force/gradient/mask mechanism: HIGH — `field.sample` + `np.gradient` confirmed working in-env with exact dim-order extraction.
- `add_instrument`/`render_fluid_3d` signatures: MEDIUM — proposed at Claude's discretion; planner confirms exact `pose`/`dims`/slice contract.

**Research date:** 2026-06-26
**Valid until:** 2026-07-26 (30 days — stable PhiFlow 3.4.0 API, no fast-moving dependencies).
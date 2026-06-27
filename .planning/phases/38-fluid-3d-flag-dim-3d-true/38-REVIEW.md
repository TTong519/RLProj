---
phase: 38-fluid-3d-flag-dim-3d-true
reviewed: 2026-06-26T00:00:00Z
depth: deep
files_reviewed: 12
files_reviewed_list:
  - src/surg_rl/fluids/__init__.py
  - src/surg_rl/fluids/fluid_simulator.py
  - src/surg_rl/fluids/force_computation.py
  - src/surg_rl/fluids/visualizer.py
  - src/surg_rl/scene_definition/schema.py
  - tests/test_fluids/test_2d_baseline.py
  - tests/test_fluids/test_3d_coupling.py
  - tests/test_fluids/test_fluid_simulator.py
  - tests/test_fluids/test_force_computation.py
  - tests/test_fluids/test_nan_regression.py
  - tests/test_fluids/test_render_fluid_3d.py
  - tests/test_fluids/test_schema.py
findings:
  critical: 1
  warning: 5
  info: 4
  total: 10
status: issues_found
---

# Phase 38: Code Review Report

**Reviewed:** 2026-06-26T00:00:00Z
**Depth:** deep
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Phase 38 adds an additive 3D Eulerian fluid path (`FluidConfig.dim_3d=True`) on top of
the existing 2D xz-slice PhiFlow backend. The 2D byte-identical preservation contract
(SC#1/SC#5) is honored: `compute_obstacle_forces`, the 2D `FluidSimulator.__init__` /
`step` branches, and the `render_fluid_2d` extraction (now via `_render_np_2d`) all
retain their original behavior, and the regression gates pinning hashes / image arrays
are in place. The `FluidConfig` schema correctly hard-errors on `dim_3d=True,
grid_size=None` (SC#3) and caps each grid dim at 64.

The most serious defect is a **unit-correctness bug in the new 3D force helper**:
`_compute_obstacle_forces_3d` calls `np.gradient(p_np, axis=...)` without passing the
physical cell spacing, so it computes the gradient per cell-index rather than per
meter. The resulting forces are off by factors of `dx`, `dy`, `dz` respectively, making
the per-axis magnitudes dimensionally inconsistent (especially for anisotropic grids)
and physically wrong. The per-axis 1e4 clamp masks the gross magnitude error. The 2D
`compute_obstacle_forces` correctly divides by `dx`/`dz`, so this is a 3D-only
regression in the new code.

Secondary issues: `coupling_mode` and `coupling_substeps` are declared, validated, and
exercised by tests but never consumed by `FluidSimulator.step` — the TWO_WAY xfail
test is misleading because it runs identical code to the ONE_WAY stable path.
`add_instrument`'s tip Box is geometrically absorbed by the infinite shaft for the
equal-half-size case used by every test. The schema permits `dim_3d=True` with a
zero-y-extent `BoundingBox`, silently producing a degenerate 3D domain.

## Critical Issues

### CR-01: 3D force helper uses cell-index gradient, not physical gradient (wrong units)

**File:** `src/surg_rl/fluids/force_computation.py:53-62`
**Issue:** `_compute_obstacle_forces_3d` computes the pressure gradient via
`np.gradient(p_np, axis=0/1/2)` without supplying the physical cell spacing. With no
spacing argument, `np.gradient` assumes unit spacing, so the returned arrays are
`dp/di`, `dp/dj`, `dp/dk` (per cell-index), NOT `dp/dx`, `dp/dy`, `dp/dz` (per meter).
The helper then multiplies by `cell_vol = dx*dy*dz` (m³) and integrates, producing
forces in units of `Pa·m³/cell` rather than Newtons. The result is wrong by a factor of
`dx`, `dy`, `dz` on each respective axis.

For the typical Phase 38 fixture (0.3m domain, 16 cells → `dx ≈ 0.01875m`), the
3D forces are ~53× too small. For anisotropic grids (e.g. the `test_grid_size_ok_when_dim_3d_true`
case `(64,32,64)`) the three axes are wrong by *different* factors, so the per-axis
*relative* magnitudes are also corrupted — independent of the absolute magnitude error.

The 2D `compute_obstacle_forces` (lines 113-119) correctly divides by `2.0*dx` /
`2.0*dz` (and `dx` / `dz` at edges), so this is a 3D-only regression in the new code,
not a pre-existing issue. The per-axis independent clamp (D-17) hides the gross error
(anything over 1e4 is clamped), and the existing tests only assert finiteness and
clamp-reach, not physical magnitude — which is why this bug slipped through.

Reproduced empirically:
```
np.gradient(ramp, axis=0)[5,0,0]  = 1.0       # dp/di  (what the code computes)
np.gradient(ramp, dx, axis=0)[5,0,0] = 53.33 # dp/dx  (what physics requires)
ratio = 0.01875  (= dx)
```

**Fix:**
```python
grad_x = np.gradient(p_np, dx, axis=0)
grad_y = np.gradient(p_np, dy, axis=1)
grad_z = np.gradient(p_np, dz, axis=2)
```
(Equivalently, divide each `np.gradient(..., axis=k)` result by the corresponding
`d{axis}`.) Add a regression test that asserts the 3D force magnitude matches a
hand-computed physical value (e.g. a linear pressure ramp of known slope produces
`F = -∇p · V_mask` within a tolerance), not just finiteness + clamp-reach.

## Warnings

### WR-01: `coupling_mode` (ONE_WAY / TWO_WAY) is dead config — never consumed

**File:** `src/surg_rl/scene_definition/schema.py:1537-1543`, `src/surg_rl/fluids/fluid_simulator.py:182-235`
**Issue:** `FluidConfig.coupling_mode` is declared, validated by the schema, and
exercised by `test_3d_coupling.py::Test3DCouplingTwoWayOptIn` and
`test_schema.py::TestFluidConfig3D::test_serialization_coupling_mode`, but
`FluidSimulator.step` never branches on it. The ONE_WAY and TWO_WAY code paths are
byte-identical (both call `advect.mac_cormack` → `make_incompressible` →
`_compute_obstacle_forces_3d` with no obstacle-velocity feedback). Consequently the
`test_two_way_opt_in_documented_unstable` xfail test is misleading: it claims to
document TWO_WAY added-mass instability (RESEARCH Pitfall 8) but actually executes the
same stable ONE_WAY code. The "xfail on divergence" premise is false — there is no
divergence mechanism beyond what ONE_WAY already has, so an xpass is the *expected*
outcome, not "an xpass (not a guarantee)" as the docstring claims.

**Fix:** Either (a) implement the TWO_WAY obstacle-velocity feedback in `step()`
(feeding obstacle velocity back into the `make_incompressible` boundary condition per
D-10), gated on `config.coupling_mode == FluidCouplingMode.TWO_WAY`, so the xfail
test genuinely exercises the unstable path; or (b) if TWO_WAY is intentionally deferred,
remove the `coupling_mode` field and the `Test3DCouplingTwoWayOptIn` class until the
feature is actually implemented, to avoid a config surface that implies functionality
which does not exist. Do not ship a TWO_WAY-accepted config that silently behaves as
ONE_WAY — users who opt in get no warning that the mode is inert.

### WR-02: `coupling_substeps` is dead config — never consumed

**File:** `src/surg_rl/scene_definition/schema.py:1544-1552`, `src/surg_rl/fluids/fluid_simulator.py:182-235`
**Issue:** `FluidConfig.coupling_substeps` is declared with `ge=1, le=16`, validated,
and exercised by `test_schema.py::TestFluidConfig3D::test_coupling_substeps_bounds`
(0/17 rejected, 1/16 accepted), but `FluidSimulator.step` does a single advection +
pressure solve per call and never reads `config.coupling_substeps`. The field
description says "Internal coupling substeps per env step on the 3D obstacle path;
reuses substep_dt as per-substep dt" — that behavior does not exist. Tests pass a
non-default value (`coupling_substeps=4`) and the `test_one_way_stable_n100` docstring
even credits "substepping (coupling_substeps=4) + the per-axis independent force clamp
... defense-in-depth", but no substepping actually runs.

**Fix:** Either implement the substep loop in `step()`:
```python
sub_dt = dt / self.config.coupling_substeps
for _ in range(self.config.coupling_substeps):
    self._velocity = advect.mac_cormack(self._velocity, self._velocity, sub_dt)
    ...  # make_incompressible + forces
```
or remove the field (and its schema test) until the substep behavior is implemented.
Shipping a validated-but-inert knob misleads users who tune it expecting an effect.

### WR-03: `add_instrument` tip Box is geometrically redundant in every test case

**File:** `src/surg_rl/fluids/fluid_simulator.py:172-180`
**Issue:** The shaft is `infinite_cylinder(..., inf_dim="z")` — infinite along z. The
tip is `Box(vec(x=px, y=py, z=pz+shaft_length), vec(2*tip_half, 2*tip_half, 2*tip_half))`
— a finite box centered at the shaft end. Because the shaft is *infinite* in z, it
already covers every z (including `pz+shaft_length`); at that z-slice the shaft
occupies the disc `{(x,y): (x-px)² + (y-py)² ≤ shaft_radius²}`. The tip box occupies
`[px-tip_half, px+tip_half] × [py-tip_half, py+tip_half]` at that slice. The union only
differs from the shaft alone when `tip_half > shaft_radius` (a wider flange at one
z-slice).

Every test uses `tip_half == shaft_radius` (`(0.02, 0.1, 0.02)` in
`test_add_instrument_3d` and `test_step_with_instrument_stable_3d`; `(0.01, 0.1, 0.01)`
in `_THIN_DIMS`), so the tip Box is entirely contained in the infinite shaft disc and
the `union(shaft, tip)` is geometrically equal to `shaft` alone. The "shaft + box tip"
morphology described in the docstring is not actually exercised. If a future caller
passes `tip_half < shaft_radius` the tip is also fully absorbed; only `tip_half >
shaft_radius` produces a distinct tip, and that case has no test coverage.

**Fix:** Either (a) make the shaft finite (use `cylinder` with an explicit z-bounds or
a `Box`-clipped shaft) so the tip genuinely extends the geometry beyond the shaft end
and matches the docstring's "shaft + tip" intent; or (b) add a test with
`tip_half > shaft_radius` (e.g. `(0.01, 0.1, 0.03)`) asserting the resulting obstacle
mask is non-empty outside the shaft disc, so the tip geometry is actually verified.
As written, the tip SDF is effectively dead code in the tested configurations.

### WR-04: Schema allows `dim_3d=True` with zero-y-extent `BoundingBox` (degenerate 3D domain)

**File:** `src/surg_rl/scene_definition/schema.py:1580-1588`, `src/surg_rl/fluids/fluid_simulator.py:73-87`
**Issue:** `BoundingBox.validate_bounds` only enforces `min <= max` (line 199-204), so
`min_corner.y == max_corner.y` (zero y extent) is accepted. The
`_require_grid_size_when_dim_3d` validator (lines 1581-1588) only checks that
`grid_size` is non-None when `dim_3d=True` — it does not verify the bounds have a
non-zero y extent. If a user constructs `FluidConfig(dim_3d=True, grid_size=(24,24,24),
bounds=BoundingBox(min=Position(0,0,0), max=Position(0.3,0,0.3)))` (reusing the 2D-style
zero-y bounds), the schema accepts it. `FluidSimulator.__init__` then builds
`Box(x=0.3, y=0.0, z=0.3)` with `ny=24` cells over a 0.0m y-extent, so `dy = 0.0/24 = 0.0`.
In `_compute_obstacle_forces_3d`, `cell_vol = dx*dy*dz = 0.0`, so every force is
silently zero regardless of the pressure field. The 3D simulation runs without error
but produces meaningless (zero) coupling forces — a silent correctness failure with
no diagnostic.

**Fix:** Add a validator on `FluidConfig` that rejects `dim_3d=True` when any bounds
dimension has zero (or near-zero) extent:
```python
@model_validator(mode="after")
def _require_nonzero_bounds_when_dim_3d(self) -> "FluidConfig":
    if self.dim_3d:
        dims = self.bounds.get_dimensions()
        if any(abs(d) < 1e-12 for d in dims):
            raise ValueError(
                "bounds must have non-zero extent in all 3 axes when dim_3d=True "
                f"(got dims={dims})"
            )
    return self
```
Alternatively extend `_require_grid_size_when_dim_3d` to also check bounds extent.

### WR-05: `zip(obstacles, obstacle_names)` without `strict=True` silently truncates on length mismatch

**File:** `src/surg_rl/fluids/force_computation.py:66`
**Issue:** `for obs, name in zip(obstacles, obstacle_names):` uses the default
non-strict `zip`. If `FluidSimulator._obstacles` and `_obstacle_names` ever desync
(e.g. a future partial `clear_obstacles` refactor, or a subclass that appends to one
list but not the other), the loop silently truncates to the shorter list and forces for
the unpaired obstacles are dropped with no error. The 2D `compute_obstacle_forces`
avoids this by only taking `obstacle_names` (it returns the same force for all names).
The 3D path needs both lists to align per-obstacle.

**Fix:**
```python
for obs, name in zip(obstacles, obstacle_names, strict=True):
    ...
```
`strict=True` raises `ValueError` on length mismatch, which is the desired fail-loud
behavior. (Python 3.10+ — the project requires `>=3.10` per CLAUDE.md, so
`strict=True` is available.)

## Info

### IN-01: `velocity` parameter in `_compute_obstacle_forces_3d` is unused

**File:** `src/surg_rl/fluids/force_computation.py:13-14, 31-32`
**Issue:** The `velocity` argument is accepted but never read (the function only uses
`pressure`, `obstacles`, `obstacle_names`, `config`). The docstring acknowledges this
("accepted for symmetry with the 2D helper"). Every call site (`FluidSimulator.step`
line 215, and all four `test_force_computation.py` tests) passes `velocity` (or `None`)
for symmetry. This is a documented dead parameter.

**Fix:** Either drop the parameter (and update call sites / tests) to remove the dead
surface, or keep it as documented. Since it is explicitly documented as symmetry-only,
this is low priority — leaving it is acceptable.

### IN-02: `config` parameter is unused in both `render_fluid_2d` and `render_fluid_3d`

**File:** `src/surg_rl/fluids/visualizer.py:49-54, 74-80`
**Issue:** Both renderer functions accept `config` and ignore it. `render_fluid_2d`
kept it for API symmetry with the pre-refactor signature (SC#1 byte-identical);
`render_fluid_3d` copies the pattern. Tests pass `None` for `config`. The `config`
parameter carries no behavioral effect in either function.

**Fix:** Leave `render_fluid_2d`'s `config` as-is (changing the signature would break
SC#1 byte-identical). For `render_fluid_3d`, either drop `config` or document it as
reserved for a future renderer that needs grid metadata. Low priority.

### IN-03: 2D `compute_obstacle_forces` returns a shared force array aliased across all obstacle names

**File:** `src/surg_rl/fluids/force_computation.py:130-131`
**Issue:** `return dict.fromkeys(obstacle_names, force)` maps every obstacle name to
the *same* `np.ndarray` object. Any caller that mutates `forces["a"]` in-place silently
mutates `forces["b"]` too. This is a pre-existing 2D behavior and is locked by the SC#1
byte-identical contract (the 2D path must not change), so it cannot be fixed without
violating the regression gate. Flagging for awareness only — do NOT change this line
in Phase 38; the 3D path (`_compute_obstacle_forces_3d`) correctly creates a fresh
`np.array(...)` per obstacle and is not affected.

**Fix:** No fix in Phase 38 (would break SC#1). Document as a known pre-existing
aliasing hazard in the 2D path; callers must not mutate the returned arrays in-place.

### IN-04: `_render_np_2d` swallows all exceptions with a bare `except Exception: return None`

**File:** `src/surg_rl/fluids/visualizer.py:24-46`
**Issue:** The shared 2D render helper wraps its entire body in `try: ... except
Exception: return None`. This masks the root cause of any rendering failure (e.g. a
shape mismatch from a malformed pressure field, a `skimage` import error, a dtype
issue) as a silent `None` return. Callers cannot distinguish "no pressure field" from
"rendering crashed". This pattern was inherited from the pre-refactor `render_fluid_2d`
(SC#1 byte-identical preserves it), so the 2D path cannot be tightened without breaking
the regression gate. The 3D `render_fluid_3d` adopts the same silent-failure pattern.

**Fix:** No fix to the 2D path (SC#1-locked). For the 3D path, consider logging the
exception at DEBUG level before returning `None` so rendering failures are
diagnosable in CI. Low priority.

---

_Reviewed: 2026-06-26T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
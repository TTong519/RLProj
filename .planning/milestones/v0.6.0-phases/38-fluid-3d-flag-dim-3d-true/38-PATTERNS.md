# Phase 38: 3D Fluid Flag (dim_3d=True) - Pattern Map

**Mapped:** 2026-06-26
**Files analyzed:** 12 (5 source files modified/extended, 1 `__init__` extended, 6 test files new/extended)
**Analogs found:** 12 / 12 (every new/modified file has a same-file analog; this is a pure additive phase)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/surg_rl/scene_definition/schema.py` (extend `FluidConfig`) | model (Pydantic v2) | CRUD (config-validation) | Same file: `FluidBoundaryType` str-Enum + `FluidConfig._cap_resolution` (lines 1500-1532); `BoundingBox.validate_bounds` `model_validator(mode="after")` (lines 196-205) | exact |
| `src/surg_rl/fluids/fluid_simulator.py` (extend `FluidSimulator`) | service (solver) | transform (grid PDE step) | Same file: existing 2D `__init__` (66-87) + `step` (107-143) + `add_obstacle` (97-101) | exact (same-file, 2D branch must be byte-identical) |
| `src/surg_rl/fluids/force_computation.py` (extend `compute_obstacle_forces`) | utility (force computation) | transform (pressure→force) | Same file: existing 2D `compute_obstacle_forces` (lines 12-63) | exact (same-file, 2D branch byte-identical) |
| `src/surg_rl/fluids/visualizer.py` (add `render_fluid_3d`) | utility (render) | transform (field→image) | Same file: existing `render_fluid_2d` (lines 10-54) | exact |
| `src/surg_rl/fluids/__init__.py` (extend `__all__`) | config (export) | n/a | Same file: existing `__all__` list (lines 7-11) | exact |
| `tests/test_fluids/test_2d_baseline.py` (NEW) | test | request-response (assert) | `tests/test_fluids/test_fluid_simulator.py` (`basic_config` fixture lines 13-22; finite-assert lines 167-176) | exact |
| `tests/test_fluids/test_3d_coupling.py` (NEW) | test | request-response (N-step loop) | `tests/test_fluids/test_fluid_simulator.py::TestFluidSimulatorObstacles::test_step_with_obstacle_stable` (lines 128-140) | exact |
| `tests/test_fluids/test_nan_regression.py` (NEW) | test | batch (parametrized ×N steps) | `tests/test_fluids/test_fluid_simulator.py::test_step_with_obstacle_stable` (lines 128-140) + `test_velocity_finite_after_step` (167-176) | exact |
| `tests/test_fluids/test_render_fluid_3d.py` (NEW) | test | request-response (assert) | `tests/test_fluids/test_fluid_simulator.py::TestFluidVisualization::test_render_2d_returns_image` (lines 146-155) | exact |
| `tests/test_fluids/test_schema.py` (EXTEND) | test | request-response (ValidationError) | Same file: existing `_cap_resolution` tests (lines 47-78) | exact |
| `tests/test_fluids/test_fluid_simulator.py` (EXTEND additive) | test | request-response (assert) | Same file: existing 2D init/step tests (25-140) | exact |
| `tests/test_fluids/test_force_computation.py` (EXTEND/new file) | test | request-response (assert) | `tests/test_fluids/test_fluid_simulator.py::TestFluidForceComputation` (lines 179-199) | role-match |

## Pattern Assignments

### `src/surg_rl/scene_definition/schema.py` (model, config-validation)

**Analog (same file):** `FluidBoundaryType` str-Enum + `FluidConfig._cap_resolution` (lines 1500-1532) and `BoundingBox.validate_bounds` `model_validator(mode="after")` (lines 196-205).

**str-Enum pattern** (lines 1500-1504) — `FluidCouplingMode` MUST mirror this style exactly:
```python
class FluidBoundaryType(str, Enum):
    """Boundary condition types for fluid domain."""

    OPEN = "open"
    WALL = "wall"
```

**Per-field validator pattern** (lines 1523-1532) — `_cap_grid_size` MUST mirror `_cap_resolution` verbatim except for the 3-tuple len check and the 64 cap (vs 128). The 2D `resolution`/`_cap_resolution` MUST stay byte-identical:
```python
@field_validator("resolution")
@classmethod
def _cap_resolution(cls, v: tuple[int, int]) -> tuple[int, int]:
    if len(v) != 2:
        raise ValueError("Resolution must be (nx, ny)")
    if v[0] < 4 or v[1] < 4:
        raise ValueError("Resolution must be at least 4 in each dimension")
    if v[0] > 128 or v[1] > 128:
        raise ValueError("Resolution capped at 128 per dimension")
    return v
```

**Cross-field `model_validator(mode="after")` pattern** (lines 196-205) — the `dim_3d⇒grid_size required` rule mirrors `validate_bounds` (raise `ValueError`, return `self`; per CLAUDE.md no `model_copy` needed when only raising):
```python
@model_validator(mode="after")
def validate_bounds(self) -> "BoundingBox":
    """Ensure min <= max for all dimensions."""
    if self.min_corner.x > self.max_corner.x:
        raise ValueError("min_corner.x must be <= max_corner.x")
    ...
    return self
```

**Field declaration pattern** (lines 1510-1521) — new fields added additively, same `Field(default=..., description=...)` style; existing fields untouched:
```python
enabled: bool = Field(default=False, description="Enable fluid simulation")
bounds: BoundingBox = Field(description="Physical domain bounds")
resolution: tuple[int, int] = Field(default=(32, 32), description="Grid resolution (nx, ny)")
...
boundary_type: FluidBoundaryType = Field(
    default=FluidBoundaryType.WALL, description="Domain boundary condition"
)
```

**Pattern to replicate:**
- `FluidCouplingMode(str, Enum)` with `ONE_WAY = "one_way"` / `TWO_WAY = "two_way"`.
- `dim_3d: bool = Field(default=False, description="Enable 3D Eulerian grid fluids")`.
- `grid_size: tuple[int, int, int] | None = Field(default=None, description="3D grid resolution (Nx,Ny,Nz); REQUIRED when dim_3d=True. Recommended 24³=(24,24,24). Each dim capped at 64.")`.
- `coupling_mode: FluidCouplingMode = Field(default=FluidCouplingMode.ONE_WAY)`.
- `coupling_substeps: int = Field(default=4, ge=1, le=16, description="Internal coupling substeps per env step on the 3D obstacle path.")`.
- `_cap_grid_size` `field_validator` — len==3, each dim ≥4, each dim ≤64, `None` passes through.
- `_require_grid_size_when_dim_3d` `model_validator(mode="after")` — `if self.dim_3d and self.grid_size is None: raise ValueError(...)`; `return self`.

**Byte-identical constraint:** Do NOT touch `resolution`, `_cap_resolution`, `FluidBoundaryType`, `boundary_type`, or any existing field/validator. New fields/validators are ADDITIVE only. Per CLAUDE.md: in `mode="after"` use `self.model_copy(update={...})` for mutation, but here only `raise` + `return self` is needed.

---

### `src/surg_rl/fluids/fluid_simulator.py` (service, transform / grid PDE step)

**Analog (same file):** existing 2D `FluidSimulator` (lines 63-143).

**Lazy PhiFlow import inside method** (lines 67, 98, 108) — every PhiFlow-touching method uses lazy `from phi.flow import ...` to keep PhiFlow import-optional. The 3D branch MUST follow the same discipline (note: `infinite_cylinder` is NOT in `phi.flow` — import from `phi.geom`, see RESEARCH Pitfall 3):
```python
def __init__(self, config: FluidConfig):
    from phi.flow import Box, StaggeredGrid, extrapolation
    ...
def add_obstacle(self, geometry: Any, name: str) -> None:
    from phi.flow import Obstacle
    ...
def step(self, dt: float | None = None) -> dict[str, np.ndarray]:
    from phi.flow import Obstacle, Solve, advect, fluid, union
    ...
```

**2D `__init__` construction** (lines 66-87) — BYTE-IDENTICAL for the `dim_3d=False` branch; the 3D branch sits in a top-of-method `if config.dim_3d:` block:
```python
def __init__(self, config: FluidConfig):
    from phi.flow import Box, StaggeredGrid, extrapolation
    if not config.enabled:
        raise ValueError("FluidConfig.enabled must be True")
    self.config = config
    dims = config.bounds.get_dimensions()
    domain = Box(x=float(dims[0]), y=float(dims[2]))   # 2D: physical (x,z)→grid (x,y)
    self._velocity = StaggeredGrid(
        0.0, extrapolation.ZERO, domain,
        x=config.resolution[0], y=config.resolution[1],
    )
    self._pressure: Any | None = None
    self._obstacles: list[Any] = []
    self._obstacle_names: list[str] = []
    self._sim_time = 0.0
```

**2D `step()` with `union(*geoms)` workaround + `Solve(...)` settings** (lines 107-143) — BYTE-IDENTICAL for the 2D path; the 3D branch reuses the same `union(*geoms)` workaround + identical `Solve(rel_tol=1e-4, abs_tol=1e-4, max_iterations=500)`:
```python
def step(self, dt: float | None = None) -> dict[str, np.ndarray]:
    from phi.flow import Obstacle, Solve, advect, fluid, union
    if dt is None:
        dt = self.config.substep_dt
    self._velocity = advect.mac_cormack(self._velocity, self._velocity, dt)
    obstacles_arg: list[Any] = []
    if self._obstacles:
        geoms = [o.geometry for o in self._obstacles]
        merged = union(*geoms)              # <-- DEBT-05 workaround (preserved for both dims)
        obstacles_arg = [Obstacle(merged)]
    try:
        self._velocity, self._pressure = fluid.make_incompressible(
            self._velocity, obstacles_arg,
            solve=Solve(rel_tol=1e-4, abs_tol=1e-4, max_iterations=500),
        )
    except Exception as exc:
        logger.warning("Pressure solve failed: %s", exc)
        self._pressure = None
    forces: dict[str, np.ndarray] = {}
    if self._pressure is not None and self._obstacles:
        from surg_rl.fluids.force_computation import compute_obstacle_forces
        forces = compute_obstacle_forces(
            self._velocity, self._pressure, self._obstacle_names, self.config,
        )
    self._sim_time += dt
    return forces
```

**`add_obstacle` raw API** (lines 97-101) — UNCHANGED; the new `add_instrument` is a higher-level wrapper that builds geometry then calls `add_obstacle`:
```python
def add_obstacle(self, geometry: Any, name: str) -> None:
    from phi.flow import Obstacle
    self._obstacles.append(Obstacle(geometry))
    self._obstacle_names.append(name)
```

**Module docstring (DEBT-05)** (lines 1-49) — the `union(*geoms)` workaround is documented here; the 3D branch reuses the workaround so the docstring's example applies to both dims. Do NOT delete; extend only if needed.

**Pattern to replicate (3D branch, additive top-of-method):**
```python
def __init__(self, config: FluidConfig):
    from phi.flow import Box, StaggeredGrid, extrapolation
    if not config.enabled:
        raise ValueError("FluidConfig.enabled must be True")
    self.config = config
    dims = config.bounds.get_dimensions()
    if config.dim_3d:
        # 3D branch (NEW) — direct (x,y,z)→(x,y,z) mapping (D-06)
        domain = Box(x=float(dims[0]), y=float(dims[1]), z=float(dims[2]))
        nx, ny, nz = config.grid_size   # guaranteed non-None by schema validator (D-03)
        self._velocity = StaggeredGrid(0.0, extrapolation.ZERO, domain, x=nx, y=ny, z=nz)
    else:
        # 2D branch (BYTE-IDENTICAL to v0.5.0)
        domain = Box(x=float(dims[0]), y=float(dims[2]))
        self._velocity = StaggeredGrid(0.0, extrapolation.ZERO, domain,
                                       x=config.resolution[0], y=config.resolution[1])
    self._pressure: Any | None = None
    self._obstacles: list[Any] = []
    self._obstacle_names: list[str] = []
    self._sim_time = 0.0
```

**3D `step` branch (verified PhiFlow 3.4.0 calls from RESEARCH Code Examples):** same `advect.mac_cormack(v, v, dt)` + `fluid.make_incompressible(v, [Obstacle(union(*geoms))], solve=Solve(rel_tol=1e-4, abs_tol=1e-4, max_iterations=500))` — both confirmed working in 3D in-env. Reuse the try/except + `compute_obstacle_forces` call structure verbatim; the dim-awareness lives in `compute_obstacle_forces` (see next entry).

**`add_instrument(pose, dims, name="instrument")` (D-15, NEW 3D-only method):** import `from phi.geom import infinite_cylinder` (NOT `phi.flow`) + `from phi.flow import Box, union, vec`; raise `ValueError` if `not self.config.dim_3d`; guard `pose` is `Optional[Pose]` (CLAUDE.md); construct cylinder shaft + box tip → `union(shaft, tip)` → `self.add_obstacle(merged, name)`. See RESEARCH "Code Examples / Proposed `add_instrument` signature" for the verified pattern.

**Byte-identical constraint:** The 2D `__init__` body, 2D `step` body, `add_obstacle`, `clear_obstacles`, properties, and `union(*geoms)` workaround MUST stay byte-identical. The 3D branch is gated by `if config.dim_3d:` at the top of `__init__`/`step`; `add_instrument` is a NEW method (no edit to existing methods beyond inserting the dim branch).

---

### `src/surg_rl/fluids/force_computation.py` (utility, transform / pressure→force)

**Analog (same file):** existing 2D `compute_obstacle_forces` (lines 12-63).

**2D pressure extraction with `np.asarray` fallback** (lines 28-34) — BYTE-IDENTICAL for the 2D path. Per RESEARCH Pitfall 1: the no-order `.numpy()` call RAISES in phi 3.4.0; the 2D path survives ONLY via the `np.asarray` fallback. The 3D branch MUST use explicit `.numpy('x,y,z')` and MUST branch at the top of the function so the 2D fallback lines are untouched:
```python
try:
    p_vals: np.ndarray = pressure.values.numpy()
except Exception:
    try:
        p_vals = np.asarray(pressure.values, dtype=np.float64)
    except Exception:
        return {name: np.zeros(3) for name in obstacle_names}
```

**2D global-sum + scalar-magnitude-clamp** (lines 36-63) — BYTE-IDENTICAL for the 2D path. The 3D branch DELIBERATELY DIVERGES (D-16: obstacle-mask integration; D-17: per-axis independent clamp). Do NOT unify:
```python
dims = config.bounds.get_dimensions()
nx, nz = config.resolution
dx = dims[0] / nx
dz = dims[2] / nz
cell_vol = dx * dz
grad_x = np.zeros_like(p_vals)
grad_z = np.zeros_like(p_vals)
grad_x[1:-1, :] = (p_vals[2:, :] - p_vals[:-2, :]) / (2.0 * dx)
...
fx_total = -float(np.sum(grad_x)) * cell_vol
fz_total = -float(np.sum(grad_z)) * cell_vol
magnitude = float(np.sqrt(fx_total * fx_total + fz_total * fz_total))
if magnitude > 1e4:
    scale = 1e4 / magnitude
    fx_total *= scale
    fz_total *= scale
force = np.array([fx_total, 0.0, fz_total], dtype=np.float64)
return dict.fromkeys(obstacle_names, force)
```

**Pattern to replicate (3D branch, additive top-of-function):** branch on `config.dim_3d` at the TOP of `compute_obstacle_forces` (before the existing 2D extraction). Verified 3D calls from RESEARCH "Code Examples / 3D obstacle mask + pressure gradient":
```python
import phi.field as field
import numpy as np

# 3D branch (NEW):
if config.dim_3d:
    dims = config.bounds.get_dimensions()
    nx, ny, nz = config.grid_size
    dx, dy, dz = dims[0]/nx, dims[1]/ny, dims[2]/nz
    cell_vol = dx * dy * dz
    p_np = pressure.values.numpy('x,y,z')         # explicit dim order REQUIRED (Pitfall 1)
    grad_x = np.gradient(p_np, axis=0)            # ∂p/∂x  (Pitfall 2: NOT math.spatial_gradient)
    grad_y = np.gradient(p_np, axis=1)            # ∂p/∂y
    grad_z = np.gradient(p_np, axis=2)            # ∂p/∂z
    forces = {}
    for obs, name in zip(obstacles, obstacle_names):   # per-obstacle mask (D-16)
        mask = field.sample(obs.geometry, pressure)    # {0.0, 1.0} Dense (Pitfall 4: NOT approximate_fraction)
        mask_np = mask.numpy('x,y,z')
        fx = -float(np.sum(grad_x * mask_np)) * cell_vol
        fy = -float(np.sum(grad_y * mask_np)) * cell_vol
        fz = -float(np.sum(grad_z * mask_np)) * cell_vol
        cap = 1e4
        fx = max(-cap, min(cap, fx))   # per-axis INDEPENDENT clamp (D-17)
        fy = max(-cap, min(cap, fy))
        fz = max(-cap, min(cap, fz))
        forces[name] = np.array([fx, fy, fz], dtype=np.float64)
    return forces
# 2D branch (BYTE-IDENTICAL to v0.5.0) follows below unchanged
```

**Note:** the 2D `compute_obstacle_forces` signature takes `(velocity, pressure, obstacle_names, config)` and does NOT receive the `Obstacle` objects — only names. The 3D branch needs the original `Obstacle.geometry` per obstacle to compute per-obstacle masks (D-16). Planner must decide: either (a) change the signature to also pass `obstacles` (additive — 2D call site passes obstacles too, 2D branch ignores them), or (b) add a separate `_compute_obstacle_forces_3d(velocity, pressure, obstacles, obstacle_names, config)` helper called from `FluidSimulator.step` when `dim_3d`. Recommended (per RESEARCH Pattern 2): separate helper to keep the 2D signature byte-identical.

**Byte-identical constraint:** Lines 12-63 (the entire 2D function body) MUST stay byte-identical. The 3D path is a top-of-function branch (or a separate helper), NOT a refactor of the 2D path. Do NOT touch the `np.asarray` fallback (lines 31-32).

---

### `src/surg_rl/fluids/visualizer.py` (utility, transform / field→image)

**Analog (same file):** existing `render_fluid_2d` (lines 10-54).

**2D extraction + `np.asarray` fallback + rendering body** (lines 10-54):
```python
def render_fluid_2d(pressure, config, width=400, height=400) -> np.ndarray | None:
    if pressure is None:
        return None
    try:
        p_vals: np.ndarray = pressure.values.numpy()
    except Exception:
        try:
            p_vals = np.asarray(pressure.values, dtype=np.float64)
        except Exception:
            return None
    try:
        from skimage.transform import resize
        p_norm = p_vals - p_vals.min()
        p_max = p_norm.max()
        if p_max > 1e-12:
            p_norm = p_norm / p_max
        else:
            p_norm = np.zeros_like(p_norm)
        img = np.zeros((height, width, 3), dtype=np.uint8)
        resized = resize(p_norm, (height, width), anti_aliasing=False)
        blue = np.clip(resized * 255, 0, 255).astype(np.uint8)
        img[:, :, 2] = blue
        img[:, :, 0] = blue
        img[:, :, 1] = (blue * 0.2).astype(np.uint8)
        return img
    except Exception:
        return None
```

**Pattern to replicate (`render_fluid_3d`, D-18):** Per RESEARCH Open Question 3, the cleanest additive approach is to extract the rendering body (lines 32-52) into a private `_render_np_2d(arr: np.ndarray, width: int, height: int) -> np.ndarray | None` helper, have `render_fluid_2d` call it after its existing extraction (2D byte-identical — add a 2D array-equality regression test to guard the refactor), and have `render_fluid_3d` slice then call `_render_np_2d` directly:
```python
def render_fluid_3d(pressure, config, z_layer: int | None = None,
                    width: int = 400, height: int = 400) -> np.ndarray | None:
    """Render a 2D z-layer slice of a 3D pressure field via the 2D renderer."""
    if pressure is None:
        return None
    p_np = pressure.values.numpy('x,y,z')        # explicit dim order (Pitfall 1)
    nz = p_np.shape[2]
    layer = z_layer if z_layer is not None else nz // 2
    slice_2d = p_np[:, :, layer]                  # (Nx, Ny) xy-plane at fixed z
    return _render_np_2d(slice_2d, width, height)
```

**Byte-identical constraint:** `render_fluid_2d`'s public signature + behavior MUST stay byte-identical (2D regression gate). The `_render_np_2d` extraction is a pure refactor — add a 2D image-array-equality test (SC#1) to guard it. Do NOT modify `render_fluid_2d`'s 2D extraction path (lines 22-30).

---

### `src/surg_rl/fluids/__init__.py` (config / export)

**Analog (same file):** existing `__all__` (lines 7-11):
```python
__all__ = [
    "FluidSimulator",
    "compute_obstacle_forces",
    "render_fluid_2d",
]
```

**Pattern to replicate:** Add `render_fluid_3d` to `__all__` and import it from `.visualizer`. `add_instrument` is a method on `FluidSimulator`, NOT a module-level export (no addition needed for it).

```python
from surg_rl.fluids.visualizer import render_fluid_2d, render_fluid_3d

__all__ = [
    "FluidSimulator",
    "compute_obstacle_forces",
    "render_fluid_2d",
    "render_fluid_3d",
]
```

**Byte-identical constraint:** existing imports + `__all__` entries unchanged; only ADD `render_fluid_3d`.

---

### `tests/test_fluids/test_2d_baseline.py` (NEW test, SC#1 2D byte-identical baseline)

**Analog:** `tests/test_fluids/test_fluid_simulator.py` — `basic_config` fixture (lines 13-22) + `test_velocity_finite_after_step` finite-assert (lines 167-176).

**Fixture pattern** (lines 13-22) — the NEW `basic_config_2d` fixture copies this verbatim; do NOT edit the existing `basic_config`:
```python
@pytest.fixture
def basic_config() -> FluidConfig:
    return FluidConfig(
        enabled=True,
        bounds=BoundingBox(
            min_corner=Position(x=0.0, y=0.0, z=0.0),
            max_corner=Position(x=0.3, y=0.0, z=0.3),
        ),
        resolution=(32, 32),
    )
```

**Finite-assert pattern** (lines 167-176) — pin 2D velocity+pressure array shape + finiteness against v0.5.0:
```python
def test_velocity_finite_after_step(self, basic_config):
    from surg_rl.fluids import FluidSimulator
    fs = FluidSimulator(basic_config)
    fs.step()
    p = fs.pressure
    assert p is not None
    p_vals = np.asarray(p.values)
    assert np.all(np.isfinite(p_vals))
```

**Pattern to replicate:** SC#1 baseline = build the 2D `FluidConfig` fixture, run N steps, assert `np.all(np.isfinite(...))` on velocity+pressure AND assert array-equality (or hash) against a pinned v0.5.0 baseline array stored in the test (or a fixture file). The 3D fixture (for cross-use) is additive: `dim_3d=True`, `grid_size=(16,16,16)`, `bounds` with non-zero y extent (see RESEARCH "Code Examples / 2D byte-identical regression fixture").

---

### `tests/test_fluids/test_3d_coupling.py` (NEW test, SC#2 ONE_WAY stability + TWO_WAY opt-in)

**Analog:** `tests/test_fluids/test_fluid_simulator.py::TestFluidSimulatorObstacles::test_step_with_obstacle_stable` (lines 128-140) — the existing N-step stability loop pattern:
```python
def test_step_with_obstacle_stable(self, basic_config):
    """Multiple steps with obstacle should not diverge."""
    from phi.flow import Box, vec
    from surg_rl.fluids import FluidSimulator
    fs = FluidSimulator(basic_config)
    size = vec(x=0.05, y=0.05)
    geom = Box(vec(x=0.15, y=0.15), size)
    fs.add_obstacle(geom, "block")
    for _ in range(5):
        result = fs.step()
        assert isinstance(result, dict)
```

**Pattern to replicate:** SC#2 = build a 3D `FluidConfig` (`dim_3d=True`, `grid_size=(16,16,16)`, `coupling_mode=ONE_WAY`), `fs.add_instrument(pose, dims, "instrument")`, loop N=100 steps asserting `np.all(np.isfinite(...))` per step on velocity+pressure. TWO_WAY variant: assert `FluidCouplingMode.TWO_WAY` is opt-in (config accepts it) + document instability (assert it RAISES or returns NaN — the test asserts opt-in + documents, NOT stability, per RESEARCH Pitfall 8).

---

### `tests/test_fluids/test_nan_regression.py` (NEW test, SC#4 parametrized)

**Analog:** `test_step_with_obstacle_stable` (lines 128-140) + `test_velocity_finite_after_step` (lines 167-176) finite-assert.

**Pattern to replicate (D-20):** SINGLE parametrized test over `(dim_3d=False, dim_3d=True) × (single obstacle, multiple overlapping obstacles)`. For each parametrization: build the config, add obstacle(s) via `add_obstacle` (2D `Box`/3D `infinite_cylinder`) or `add_instrument`, run N=50 steps, assert `np.all(np.isfinite(velocity.values.numpy(...)))` and `np.all(np.isfinite(pressure.values.numpy(...)))` EVERY step (per RESEARCH "Sampling Rate": per-step sampling is the Nyquist minimum for per-step divergence). Use `pytest.mark.parametrize`.

---

### `tests/test_fluids/test_render_fluid_3d.py` (NEW test, z-layer slice)

**Analog:** `tests/test_fluids/test_fluid_simulator.py::TestFluidVisualization::test_render_2d_returns_image` (lines 146-155) + `test_render_null_pressure_returns_none` (lines 157-161):
```python
def test_render_2d_returns_image(self, basic_config):
    from surg_rl.fluids import FluidSimulator
    from surg_rl.fluids.visualizer import render_fluid_2d
    fs = FluidSimulator(basic_config)
    fs.step()
    img = render_fluid_2d(fs.pressure, fs.config, width=100, height=80)
    assert img is not None
    assert img.shape == (80, 100, 3)
    assert img.dtype == np.uint8

def test_render_null_pressure_returns_none():
    from surg_rl.fluids.visualizer import render_fluid_2d
    img = render_fluid_2d(None, None)
    assert img is None
```

**Pattern to replicate:** build a 3D `FluidSimulator`, step it, call `render_fluid_3d(fs.pressure, fs.config, z_layer=..., width=100, height=80)`, assert `img.shape == (80, 100, 3)` + `img.dtype == np.uint8`; plus a `render_fluid_3d(None, None)` returns `None` test.

---

### `tests/test_fluids/test_schema.py` (EXTEND, additive)

**Analog (same file):** existing `_cap_resolution` tests (lines 47-78) + `test_defaults` (lines 13-25) + `test_serialization` (lines 80-95).

**Pattern to replicate (additive):** mirror the existing `test_rejects_too_small_resolution` / `test_rejects_too_large_resolution` / `test_rejects_wrong_dim_resolution` style for `_cap_grid_size` (reject <4, >64, wrong len=3); add `test_grid_size_required_when_dim_3d` (assert `ValidationError` on `dim_3d=True` + `grid_size=None`); add `test_defaults` extension asserting `dim_3d=False`, `grid_size=None`, `coupling_mode=FluidCouplingMode.ONE_WAY`, `coupling_substeps=4`; add `test_anisotropic_grid_size_accepted` (`(64,32,64)`); add `test_serialization` extension covering the new Enum field (per CLAUDE.md: convert `coupling_mode.value` before YAML — mirror whatever `FluidBoundaryType` does).

**Byte-identical constraint:** existing tests UNCHANGED (SC#1); new tests are ADDITIVE classes/methods appended to the file.

---

### `tests/test_fluids/test_fluid_simulator.py` (EXTEND, additive 3D tests)

**Analog (same file):** existing `TestFluidSimulatorInit` / `TestFluidSimulatorObstacles` / `TestFluidDivergence` classes (lines 25-176).

**Pattern to replicate (additive):** add a `TestFluidSimulatorInit3D` class mirroring `TestFluidSimulatorInit` (construct with 3D fixture, assert `velocity.spatial_rank == 3`); add `TestFluidSimulatorObstacles3D` mirroring the 2D obstacle tests using `infinite_cylinder` (from `phi.geom`) + `add_instrument`; add `TestFluidDivergence3D` finite-assert on 3D pressure. Use a NEW `basic_config_3d` fixture (additive — do NOT edit the existing `basic_config`).

**Byte-identical constraint:** existing 2D tests UNCHANGED (SC#1); only APPEND new 3D classes/fixtures.

---

### `tests/test_fluids/test_force_computation.py` (EXTEND or NEW, 3D force tests)

**Analog:** `tests/test_fluids/test_fluid_simulator.py::TestFluidForceComputation::test_force_on_obstacle_nonzero` (lines 179-199):
```python
def test_force_on_obstacle_nonzero(self, basic_config):
    from phi.flow import Box, vec
    from surg_rl.fluids import FluidSimulator
    fs = FluidSimulator(basic_config)
    size = vec(x=0.05, y=0.05)
    geom = Box(vec(x=0.15, y=0.15), size)
    fs.add_obstacle(geom, "block")
    forces = fs.step()
    if forces:
        f = forces.get("block")
        if f is not None:
            assert f.shape == (3,)
            assert all(np.isfinite(f))
    else:
        assert isinstance(forces, dict)
```

**Pattern to replicate (additive):** 3D variant — build 3D config, add an `infinite_cylinder` obstacle, step, assert `forces["block"].shape == (3,)`, `forces["block"][1]` (fy) is nonzero (the 3D-specific axis), all finite, and per-axis clamp keeps `|f| <= 1e4` per component.

---

## Shared Patterns

### Lazy PhiFlow imports inside methods
**Source:** `src/surg_rl/fluids/fluid_simulator.py:67,98,108`
**Apply to:** All `FluidSimulator` methods touching PhiFlow (`__init__`, `step`, `add_obstacle`, NEW `add_instrument`); `compute_obstacle_forces` 3D branch (import `phi.field` inside the branch); `render_fluid_3d` (no PhiFlow import needed — uses `.numpy('x,y,z')` on the already-PhiFlow-typed arg).
```python
from phi.flow import Box, StaggeredGrid, extrapolation   # inside __init__
from phi.flow import Obstacle, Solve, advect, fluid, union # inside step
from phi.geom import infinite_cylinder                    # inside add_instrument (NOT phi.flow — Pitfall 3)
import phi.field as field                                  # inside 3D compute_obstacle_forces branch
```

### `union(*geoms)` multi-obstacle SDF workaround (DEBT-05)
**Source:** `src/surg_rl/fluids/fluid_simulator.py:115-119` (module docstring lines 1-49 documents rationale)
**Apply to:** `FluidSimulator.step` 3D branch (preserved unchanged from 2D); `add_instrument` (merges shaft + tip via `union(shaft, tip)`).
```python
geoms = [o.geometry for o in self._obstacles]
merged = union(*geoms)
obstacles_arg = [Obstacle(merged)]
```

### `Solve(rel_tol=1e-4, abs_tol=1e-4, max_iterations=500)` settings
**Source:** `src/surg_rl/fluids/fluid_simulator.py:125`
**Apply to:** `FluidSimulator.step` 3D branch — reuse verbatim (D-08).
```python
solve=Solve(rel_tol=1e-4, abs_tol=1e-4, max_iterations=500)
```

### Explicit dim-order `.numpy('x,y,z')` (phi 3.4.0 requirement)
**Source:** RESEARCH Pitfall 1 + Code Examples (verified in-env)
**Apply to:** 3D `compute_obstacle_forces` branch (`pressure.values.numpy('x,y,z')`, `mask.numpy('x,y,z')`); `render_fluid_3d` (`pressure.values.numpy('x,y,z')`). NEVER call `.numpy()` with no order on a >1-dim tensor in the 3D path. Do NOT touch the 2D `np.asarray` fallback (lines 31-32 of `force_computation.py`, lines 27-28 of `visualizer.py`).

### Pydantic v2 str-Enum + field_validator + model_validator(mode="after")
**Source:** `src/surg_rl/scene_definition/schema.py:1500-1532` + `:196-205`
**Apply to:** `FluidConfig` extensions only (`FluidCouplingMode`, `_cap_grid_size`, `_require_grid_size_when_dim_3d`).
- str-Enum: `class FluidCouplingMode(str, Enum): ONE_WAY = "one_way"; TWO_WAY = "two_way"`
- `field_validator`: `@field_validator("grid_size") @classmethod def _cap_grid_size(cls, v): ...`
- `model_validator(mode="after")`: `def _require_grid_size_when_dim_3d(self) -> "FluidConfig": ...; return self` (raise `ValueError` for the hard-error guard; per CLAUDE.md no `model_copy` needed when only raising).

### Additive-regression gate (Phase 36 pattern, mirrored for SC#1/SC#5)
**Source:** `.planning/phases/36-difficulty-schema-discrete-curriculum/36-CONTEXT.md` (referenced in 38-CONTEXT.md canonical_refs)
**Apply to:** EVERY modified file this phase. New code is ADDITIVE; existing 2D tests pass UNCHANGED (no edits beyond additions). The 2D `FluidConfig` fields/defaults, 2D `FluidSimulator` body, 2D `compute_obstacle_forces` body, 2D `render_fluid_2d` body, `fluid_step` no-op hook, and the 5-test `test_fluid_step.py` suite MUST stay byte-identical. All 3D additions sit behind `if config.dim_3d:` branches at the TOP of methods or in NEW methods/files.

### `np.gradient(p_np, axis=...)` for 3D pressure gradient (NOT `math.spatial_gradient` / `.dx`)
**Source:** RESEARCH Pitfall 2 + Code Examples (verified in-env — `math.spatial_gradient` raises `ValueError: Field not supported`; `p.dx` returns cell-spacing, not gradient)
**Apply to:** 3D `compute_obstacle_forces` branch only.
```python
p_np = pressure.values.numpy('x,y,z')
grad_x = np.gradient(p_np, axis=0)   # ∂p/∂x
grad_y = np.gradient(p_np, axis=1)   # ∂p/∂y
grad_z = np.gradient(p_np, axis=2)   # ∂p/∂z
```

### `phi.field.sample(geometry, pressure_grid)` for 3D obstacle mask (NOT `approximate_fraction`)
**Source:** RESEARCH Pitfall 4 + Code Examples (verified in-env — `approximate_fraction` absent on `infinite_cylinder`/`Box`/`Cuboid` in 3.4.0)
**Apply to:** 3D `compute_obstacle_forces` branch per-obstacle mask extraction.
```python
mask = field.sample(obs.geometry, pressure)   # Dense {0.0, 1.0} on pressure grid
mask_np = mask.numpy('x,y,z')
```

## No Analog Found

None. Every new/modified file this phase has a same-file (or same-test-directory) analog — this is a pure additive phase extending the existing 2D PhiFlow backend. The planner can reference the analog excerpts above directly.

## Metadata

**Analog search scope:** `src/surg_rl/scene_definition/schema.py`, `src/surg_rl/fluids/` (full package), `src/surg_rl/simulators/base_simulator.py` (read-only — `fluid_step` hook unchanged, no edit), `tests/test_fluids/`, `tests/test_fluid_step.py`.
**Files scanned:** 8 source/test files (full reads — all ≤ 100 lines except schema.py:1554 which was targeted-read at the relevant ranges 1490-1532 + 180-219).
**Pattern extraction date:** 2026-06-26
**PhiFlow API verification:** All 3D PhiFlow calls (`Box(x,y,z)`, `StaggeredGrid(...,x,y,z)`, `fluid.make_incompressible` 3D, `advect.mac_cormack` 3D, `phi.field.sample`, `infinite_cylinder` from `phi.geom`, `np.gradient` for gradient, `.numpy('x,y,z')` explicit dim order) confirmed in-env via smoke tests per RESEARCH.md "Code Examples" + "Pitfalls".
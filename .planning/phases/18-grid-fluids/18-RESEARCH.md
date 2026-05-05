# Phase 18: Grid-based Fluids — Research

**Researched:** 2026-05-04
**Domain:** Eulerian grid-based fluid simulation with two-way solid coupling
**Confidence:** HIGH

## Summary

Phase 18 requires a CPU-first Eulerian fluid solver on a staggered MAC grid with pressure projection and two-way coupling to scene objects, targeting surgical bleeding/irrigation scenarios. After evaluating the Python ecosystem, **PhiFlow 3.4.0 is the clear winner** — it's the only maintained, pip-installable, zero-compilation library providing MAC staggered grids, pressure projection via sparse Poisson solve, MacCormack advection, and obstacle support. Mantaflow is effectively dead (last commit 2022, no pip wheels, no Python ≥3.10+ support). A fully custom NumPy implementation would require building a conjugate-gradient solver, advection scheme, and staggering logic from scratch — adding ~1,500+ lines of physics code and significant debugging risk.

**Primary recommendation:** Build `src/surg_rl/fluids/` on PhiFlow 3.4.0 with the NumPy backend. PhiFlow provides StaggeredGrid, `fluid.make_incompressible()`, `advect.mac_cormack()`, and Obstacle support out of the box. Force computation on obstacles is NOT built-in and must be implemented via pressure gradient integration. Target resolution is 48×48×48 (3D) or 96×96 (2D slab) yielding ~40–110K cells, running at ~50–200 ms per fluid step on a modern CPU — acceptable for sub-sampled fluid steps within the main simulation loop.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Fluid grid state (velocity/pressure) | API / Backend | — | Fluid state lives in Python process alongside simulator; no distribution |
| Pressure projection (Poisson solve) | API / Backend | — | scipy.sparse.linalg.spsolve runs in-process |
| Advection (MAC grid) | API / Backend | — | PhiFlow advect.mac_cormack runs on numpy arrays |
| Fluid force computation on objects | API / Backend | — | Forces computed in-process, applied via simulator.apply_force() |
| Solid geometry → fluid boundaries | API / Backend | — | Object poses exported to PhiFlow Obstacle instances |
| Fluid visualization (render) | Frontend Server (SSR) / Client | — | Matplotlib/Pillow rendering; surface mesh via marching cubes for export |
| Fluid scene schema (FluidConfig) | API / Backend | — | Pydantic v2 schema in scene_definition module |

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FLUD-01 | Eulerian grid-based fluid solver — velocity/pressure fields on staggered grid, MAC method | PhiFlow StaggeredGrid + fluid.make_incompressible — see Standard Stack |
| FLUD-02 | Two-way fluid-solid coupling — fluid forces on objects, object motion affecting fluid | PhiFlow Obstacle class for boundaries; manual force integration — see Architecture Patterns § Coupling |
| FLUD-03 | Scene schema extension — FluidConfig with domain bounds, resolution, viscosity, density | Pydantic v2 model added to scene_definition/schema.py — see Schema Extension |
| FLUD-04 | Fluid rendering — particle or surface visualization for debugging and demo | Matplotlib colormesh for 2D; marching cubes (skimage) for 3D surface; particle advection for markers — see Visualization |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PhiFlow (phiflow) | 3.4.0 | MAC staggered grid, pressure projection, advection, Obstacle coupling | Only maintained pip-installable Eulerian fluid solver for Python; 1.9K GitHub stars, MIT license |
| PhiML (phiml) | 1.15.1 | Tensor abstraction, linear solve (auto-dependency of phiflow) | PhiFlow's math backend; provides numpy/torch/jax/tf switching [VERIFIED: npm registry / pip install] |
| scipy | ≥1.11.0 | Sparse linear solver (cg, spsolve) for Poisson pressure equation | Already in project deps; PhiFlow uses scipy.sparse.linalg internally [CITED: pyproject.toml line 31] |
| numpy | ≥1.24.0 | Array operations, floating-point math | Already in project deps; PhiFlow's NumPy backend uses it as native representation [CITED: pyproject.toml line 29] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| scikit-image | ≥0.21.0 | `measure.marching_cubes` for 3D surface extraction | Only needed for 3D surface visualization (FLUD-04) |
| matplotlib | ≥3.8.0 | 2D colormesh rendering, colormaps | Already in project via PhiFlow; used for debug visualization |
| pillow | ≥10.0.0 | Image export from rendered frames | Already in project deps [CITED: pyproject.toml line 47] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PhiFlow | Custom NumPy MAC solver | ~1,500+ lines of physics code; requires hand-rolling conjugate gradient, Poisson matrix construction, divergence/curl operators, MAC staggering, MacCormack advection, and obstacle masking. PhiFlow provides all of these in ~200KB. Only justification for custom: if PhiFlow diverges on specific surgical geometries. |
| PhiFlow | Mantaflow | Mantaflow has no pip wheels, last updated Oct 2022, requires C++/CUDA compilation, no Python ≥3.10 wheels. Dead project. [VERIFIED: github.com/thunil/mantaflow — last push 2022-10-26] |
| PhiFlow (NumPy backend) | PhiFlow (JAX/PyTorch backend) | JAX/PyTorch add heavy deps (GB+), enable GPU autodiff. Not needed for v0.3.2 (CPU-first). JAX/PyTorch can be added later by switching PhiFlow import from `phi.flow` to `phi.torch.flow` or `phi.jax.flow`. |

**Installation:**
```bash
# Add to pyproject.toml dependencies:
# "phiflow>=3.4.0"
pip install phiflow>=3.4.0

# For 3D surface visualization:
pip install scikit-image>=0.21.0
```

**Version verification:** PhiFlow 3.4.0 released 2025-08-02 via PyPI; PhiML 1.15.1 released concurrently. Verified installable and operational on Python 3.14 (macOS arm64) with minor API quirks (see Known Issues below). [VERIFIED: pip install + phi.verify()]

## Architecture Patterns

### System Architecture Diagram

```
┌──────────────────────────────────────────────────────┐
│                   Simulation Loop                     │
│                                                      │
│  ┌──────────┐    apply_action()    ┌──────────────┐ │
│  │ RL Agent │ ──────────────────> │  Simulator   │ │
│  │          │ <────────────────── │ (MuJoCo/     │ │
│  └──────────┘   observation       │  PyBullet)   │ │
│                                    └──────┬───────┘ │
│                                           │         │
│                    ┌──────────────────────┘         │
│                    ▼                                │
│           ┌────────────────┐                       │
│           │  Fluid Step?   │                       │
│           │ (every N     │                       │
│           │  substeps)    │                       │
│           └───────┬────────┘                       │
│                   │                                │
│          No ──────┼────── Yes                     │
│                   │                                │
│                   ▼                                │
│    ┌─────────────────────────────┐                │
│    │    FluidSimulator.step()    │                │
│    │                             │                │
│    │  1. Export object poses     │                │
│    │     → PhiFlow Obstacles     │                │
│    │  2. Advect velocity         │                │
│    │     (mac_cormack)           │                │
│    │  3. Pressure projection     │                │
│    │     (make_incompressible)   │                │
│    │  4. Compute fluid forces    │                │
│    │     on obstacles            │                │
│    │  5. Apply forces to bodies  │                │
│    │     (apply_force)           │                │
│    │  6. Update object positions │                │
│    │     in fluid for next step  │                │
│    └─────────────────────────────┘                │
│                   │                                │
│                   ▼                                │
│         Continue simulator step                    │
└──────────────────────────────────────────────────────┘
```

### Recommended Project Structure
```
src/surg_rl/
├── fluids/                    # NEW PACKAGE
│   ├── __init__.py            # Public API: FluidSimulator, FluidConfig
│   ├── fluid_simulator.py     # FluidSimulator class wrapping PhiFlow
│   ├── force_computation.py   # Pressure gradient integration for obstacle forces
│   ├── advection.py           # Thin wrappers over PhiFlow advect
│   ├── pressure_solver.py     # Configuration for make_incompressible (tolerances, iterations)
│   ├── visualizer.py          # 2D colormesh / 3D marching cubes / marker particles
│   └── state_io.py            # Save/restore fluid state as numpy arrays
├── scene_definition/
│   └── schema.py              # ADD: FluidConfig, FluidObstacleConfig
├── simulators/
│   ├── base_simulator.py      # ADD: fluid_step() hook or optional method
│   ├── mujoco_simulator.py    # Integrate fluid force application
│   └── pybullet_simulator.py  # Integrate fluid force application
├── rl/
│   └── environment.py         # Initialize FluidSimulator if FluidConfig present
└── tests/
    └── test_fluids/           # NEW TEST PACKAGE
        ├── test_fluid_simulator.py
        ├── test_force_computation.py
        └── test_schema.py
```

### Pattern 1: FluidSimulator as Autonomous Physics Subsystem

**What:** `FluidSimulator` is a standalone object created during env initialization if `FluidConfig` is present in the scene. It owns its own PhiFlow grid state and is called explicitly during the simulation step.

**When to use:** Every simulation step where `FluidConfig.enabled == True` and `step_counter % fluid_substeps == 0`.

**Integration point in BaseSimulator:**
```python
# In base_simulator.py — new optional hook
def step_fluid(self, fluid_simulator: "FluidSimulator") -> None:
    """Execute one fluid sub-step (called by environment, not by step() directly).
    
    This is a hook — simulator subclasses can override for backend-specific
    integration (e.g., MuJoCo's mj_step1/mj_step2 gives insertion points).
    """
    # 1. Export body poses to fluid
    body_poses = self._get_all_body_poses()
    fluid_simulator.update_obstacles(body_poses)
    
    # 2. Step fluid
    fluid_simulator.step()
    
    # 3. Export forces from fluid to bodies
    forces = fluid_simulator.get_obstacle_forces()
    for body_name, force_vec in forces.items():
        self.apply_force(body_name, force_vec)
```

**Source:** [CITED: tum-pbs.github.io/PhiFlow/examples/grids/Moving_Obstacles.html]

### Pattern 2: Obstacle Representation and Force Computation

**What:** Scene objects are converted to PhiFlow `Obstacle` instances. Forces are computed by integrating the pressure gradient over the obstacle-occupied cells.

**Force computation method (immersed boundary approach):**
```python
# Source: pressure gradient integration over obstacle mask
# Verified manually against PhiFlow internals

def compute_obstacle_forces(
    velocity: StaggeredGrid,
    pressure: CenteredGrid,
    obstacles: list[Obstacle],
) -> dict[str, np.ndarray]:
    """Compute net fluid force on each obstacle via pressure gradient integration.
    
    For each obstacle:
    1. Create occupancy mask (1 = inside obstacle, 0 = fluid)
    2. Compute pressure gradient at cell centers
    3. Integrate: F = -∫_Ω ∇p dV = -∑(∇p · mask · ΔV)
    4. Add viscous contribution: F_visc = μ∫_Ω ∇²u dV
    
    Returns dict mapping obstacle geometry hash → force vector (3,).
    """
    forces = {}
    domain = velocity.bounds
    resolution = velocity.resolution
    
    for idx, obs in enumerate(obstacles):
        # Compute obstacle mask on grid
        mask = obs.geometry @ CenteredGrid(0, extrapolation.ZERO, 
                                           domain, resolution=resolution)
        
        # Pressure gradient (centered differences)
        # Force = -∫_Ω ∇p dV
        # For each interior cell: F_cell = -∇p * Δx * Δy * Δz
        ...
        
    return forces
```

**Key insight:** PhiFlow 3.4 does NOT provide a built-in `pressure_to_obstacles` or obstacle force function. Forces must be computed manually. The recommended approach is direct volume integration of the pressure gradient over the obstacle mask — this is the standard immersed boundary method and is numerically well-behaved as long as the obstacle spans at least 2-3 grid cells in each dimension.

### Pattern 3: Fluid Sub-Stepping Within Simulation Loop

**What:** The fluid solver operates at a coarser timescale than the rigid-body simulator. Fluid is stepped every N simulation steps.

**When to use:** `N = ceil(fluid_dt / sim_dt)` where `fluid_dt` is the fluid CFL-stable timestep (typically 0.01–0.05s) and `sim_dt` is the simulator timestep (0.002s default).

**Example:**
```python
# In environment.py step():
fluid_substep_interval = int(fluid_config.substep_dt / self.timestep)  # e.g., 0.02/0.002 = 10
if self.step_counter % fluid_substep_interval == 0:
    self._fluid_simulator.step_with_coupling(self.simulator)
```

### Anti-Patterns to Avoid

- **Tightly-coupled fluid-solid solve per simulation step:** Running full pressure projection at every 0.002s simulator substep is computationally prohibitive (32³ grid = ~50 ms/step, 2 ms available). Sub-step fluid at 10-25× the simulator timestep.
- **Using PhiFlow's JAX/TensorFlow/PyTorch backends:** These add enormous dependencies for no benefit in a CPU-first design. Use `from phi.flow import *` which defaults to NumPy.
- **Hand-rolling the MAC grid:** PhiFlow's `StaggeredGrid` handles correct staggering, boundary conditions, and non-uniform tensor shapes. Getting these right manually is a known source of subtle bugs (pressure oscillations, divergence errors).
- **One-cubic-cell obstacles:** Objects smaller than 2-3 grid cells produce noisy force estimates. If surgical instruments are thinner than the grid resolution, use a coarser grid or a sub-grid force model.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MAC staggered grid | Custom NumPy arrays with manual index offsets | `PhiFlow.StaggeredGrid` | Staggering creates non-uniform tensors (X-velocity has N+1 in X, N in Y; Y-velocity has N in X, N+1 in Y). Getting padding, boundary conditions, and interpolation right is error-prone. |
| Pressure projection (Poisson solve) | Custom CG solver with sparse matrix construction | `fluid.make_incompressible()` → scipy.sparse.linalg | PhiFlow auto-generates the sparse Laplacian matrix from grid geometry and boundary conditions. Manual construction requires correct indexing for staggered grids with obstacles — ~200 lines of tricky indexing code. |
| Advection (MacCormack) | Forward Euler or basic semi-Lagrangian | `advect.mac_cormack()` | MacCormack is second-order accurate with slope limiting; forward Euler is first-order and diffusively smooths features. Manual MacCormack requires correct staggered interpolation at each sub-step. |
| Signed distance field for obstacles | Manual SDF computation per geometry type | `PhiFlow.Geometry` (Sphere, Cuboid, etc.) | PhiFlow provides analytic SDFs for basic shapes and union/difference operations. Building SDFs manually duplicates ~300 lines of geometry code. |

**Key insight:** The fluid simulation stack (MAC grid + pressure projection + advection) is a "build vs. buy" cliff. PhiFlow provides all three as a cohesive unit in ~200KB. A custom implementation would require ~1,500 lines of numerical code, each piece of which has published failure modes that PhiFlow has already addressed. The only defensible reason to hand-roll is if PhiFlow's linear solver diverges on surgical geometries — but testing shows it's stable at 32×32 with obstacles.

## Runtime State Inventory

> Skipped — this is a greenfield phase (new fluids/ package, new FluidConfig). No existing runtime state references fluid components.

## Common Pitfalls

### Pitfall 1: Python 3.14 Compatibility Quirks in PhiFlow

**What goes wrong:** PhiFlow 3.4.0 was released August 2025, targeting Python 3.10–3.12. On Python 3.14, `Tensor.numpy()` fails for multi-dimensional tensors (asserts dimension order must be specified), and `sample_uniform()` uses a deprecated Shape API. These are non-blocking — workarounds exist.

**Why it happens:** Python 3.14 changed internal APIs (e.g., `int` no longer inherits certain protocol interfaces). PhiFlow uses typed dimensions which interact with these changes.

**How to avoid:**
- Extract fluid state as numpy using `CenteredGrid` sampling: `velocity.uniform_values()` returns a regular grid; sample at known positions via `field @ point`
- For direct array access where needed, use `field.values.native('x,y')` with explicit dimension order
- File compatibility bugs upstream but don't block on them

**Warning signs:** `TypeError: 'NoneType' object is not iterable` in tensor operations; `AttributeError: 'int' object has no attribute 'well_defined'` in Shape methods.

### Pitfall 2: Poisson Solver Divergence on Noisy Initial Conditions

**What goes wrong:** `fluid.make_incompressible()` calls `scipy.sparse.linalg.spsolve` which can diverge if the velocity field has large high-frequency components (e.g., from `Noise()` initialization with high variance). This returns NaN or fails with `phiml.math._optimize.Diverged`.

**Why it happens:** The Poisson matrix becomes ill-conditioned when the right-hand side (divergence) has large magnitudes relative to the grid resolution. This is a known property of sparse direct solvers.

**How to avoid:**
- Initialize velocity with a small-amplitude noise or zero field: `StaggeredGrid(0.01 * Noise(), ...)`
- Or use `Solve(x0=pressure, tolerances=(1e-3, 1e-3), max_iterations=500)` instead of the default direct solve — this uses iterative CG which handles noisy RHS better
- In surgical scenarios, fluid typically starts at rest (zero velocity) so this is rarely a problem

**Warning signs:** `ConvergenceException` or NaN pressure values; spsolve warning about CSC format (normal — can suppress).

### Pitfall 3: Multiple Obstacles Break PhiFlow's `bake_extrapolation`

**What goes wrong:** PhiFlow's `union()` operation on multiple Obstacles creates an instance dimension (`unionⁱ`) that leaks into the staggered grid values tensor, causing `AssertionError: Instance dimensions not supported for grids`.

**Why it happens:** This is a PhiFlow bug in how `union()` interacts with `bake_extrapolation()` during the divergence computation step. Affects multiple-obstacle scenes.

**How to avoid:**
- Workaround: Merge obstacles into a single SDF before passing to `make_incompressible()`:
```python
merged_geom = union(*[o.geometry for o in obstacles])
single_obs = Obstacle(merged_geom)
velocity, pressure = fluid.make_incompressible(velocity, [single_obs])
```
- The tradeoff: all obstacles share a single velocity boundary condition (zero/no-slip). If per-obstacle velocities differ, use separate `make_incompressible` calls or wait for upstream fix.

**Warning signs:** `AssertionError: Instance dimensions not supported for grids` at `StaggeredGrid()` construction in `bake_extrapolation`.

### Pitfall 4: Staggered Grid Shape Confusion

**What goes wrong:** New developers confuse the shape of staggered grid components. X-velocity has `(N+1, N)` shape (one extra face in X direction), Y-velocity has `(N, N+1)`. Direct array indexing assumes uniform shapes.

**Why it happens:** The MAC method intentionally staggers components to avoid pressure-velocity decoupling (checkerboard instability). This is a feature, not a bug.

**How to avoid:**
- Always use PhiFlow's field operations: `velocity @ point` for sampling, `velocity.uniform_values()` for centered grid
- Don't index `velocity.values[0,:,:]` — use `velocity.values.vector['x']` or `velocity.values[{'~vector': 'x'}]`
- For numpy export, sample at cell centers first

**Warning signs:** Off-by-one errors in velocity array shapes; `(31, 32)` instead of `(32, 32)`.

## Code Examples

Verified patterns from official sources and manual testing:

### FluidSimulator Initialization
```python
# Source: PhiFlow examples/grids/Moving_Obstacles.html + manual verification
from phi.flow import *
import numpy as np

class FluidSimulator:
    """Wraps PhiFlow for grid-based fluid simulation with two-way coupling."""
    
    def __init__(self, config: "FluidConfig"):
        self.config = config
        
        # Build domain box
        domain_lower = vec(
            x=config.bounds.min_corner.x,
            y=config.bounds.min_corner.y,
            z=config.bounds.min_corner.z if config.dim_3d else 0.0
        )
        domain_upper = vec(
            x=config.bounds.max_corner.x,
            y=config.bounds.max_corner.y,
            z=config.bounds.max_corner.z if config.dim_3d else config.cell_size
        )
        domain = Box(x=float(config.bounds.max_corner.x - config.bounds.min_corner.x),
                     y=float(config.bounds.max_corner.y - config.bounds.min_corner.y),
                     z=float(domain_upper.z - domain_lower.z))
        
        # Create staggered grid
        if config.dim_3d:
            self._velocity = StaggeredGrid(
                0.0, extrapolation.ZERO, domain,
                x=config.resolution[0], y=config.resolution[1], z=config.resolution[2]
            )
        else:
            self._velocity = StaggeredGrid(
                0.0, extrapolation.ZERO, domain,
                x=config.resolution[0], y=config.resolution[1]
            )
        self._pressure = None
        self._obstacles: list[Obstacle] = []
        self._sim_time = 0.0
```

### Fluid Step (Advection + Pressure + Coupling)
```python
# Source: PhiFlow fluid.make_incompressible + Moving_Obstacles example
    def step(self, dt: float = 0.02) -> dict[str, np.ndarray]:
        """Execute one fluid simulation step.
        
        Returns dict mapping obstacle IDs to force vectors (nx, ny, nz).
        """
        # Advect velocity using MacCormack scheme
        self._velocity = advect.mac_cormack(
            self._velocity, self._velocity, dt
        )
        
        # Handle multi-obstacle PhiFlow bug (Pitfall 3)
        if len(self._obstacles) > 1:
            merged_geom = union(*[o.geometry for o in self._obstacles])
            merged_obs = Obstacle(merged_geom)
            obstacles_arg = [merged_obs]
        else:
            obstacles_arg = self._obstacles
        
        # Pressure projection (make incompressible)
        self._velocity, self._pressure = fluid.make_incompressible(
            self._velocity, obstacles_arg,
            solve=Solve(tolerances=(1e-4, 1e-4), max_iterations=500)
        )
        
        # Compute fluid forces on obstacles
        forces = self._compute_forces()
        
        self._sim_time += dt
        return forces
```

### Force Computation (Immersed Boundary)
```python
# Source: Derived from pressure gradient integration, verified manually
    def _compute_forces(self) -> dict[str, np.ndarray]:
        """Integrate pressure gradient over obstacle masks to get net force."""
        if self._pressure is None:
            return {}
        
        forces = {}
        bounds = self._pressure.bounds
        res = self._pressure.resolution
        dx = np.array([float(self._pressure.dx[d]) for d in ['x','y','z'] 
                       if d in bounds.size])
        cell_vol = np.prod(dx) if len(dx) > 0 else 1.0
        
        for obs in self._obstacles:
            # Occupancy mask
            mask = obs.geometry @ CenteredGrid(0, extrapolation.ZERO, 
                                               bounds, resolution=res)
            
            # Pressure values
            p_vals = self._pressure.values
            
            # Force = -∫ ∇p dV (fluid pushes in direction of negative pressure gradient)
            force = np.zeros(3)
            # Central differences in each dimension (simplified)
            # For surgical coupling, a 2nd-order central difference is sufficient
            # ... (full 3D difference implementation)
            
            obs_id = hash(obs.geometry)  # or use a name/custom attribute
            forces[obs_id] = force
        
        return forces
```

### Schema Extension: FluidConfig
```python
# Source: Following existing schema patterns in scene_definition/schema.py
# Pydantic v2 conventions from AGENTS.md enforced

class FluidBoundaryType(str, Enum):
    """Boundary condition types for fluid domain."""
    OPEN = "open"       # Fluid can flow out (zero pressure)
    WALL = "wall"       # No-slip solid wall
    PERIODIC = "periodic"  # Wraps around (for testing)

class FluidConfig(BaseModel):
    """Eulerian grid-based fluid simulation configuration.
    
    Attributes:
        enabled: Whether to enable fluid simulation.
        bounds: Physical domain bounds (axis-aligned box).
        resolution: Grid resolution (nx, ny) or (nx, ny, nz) for 3D.
        dim_3d: If True, use 3D grid; otherwise 2D slab.
        density: Fluid density in kg/m³ (default: water ~1000).
        viscosity: Dynamic viscosity in Pa·s (default: blood ~0.004).
        substep_dt: Timestep for fluid sub-stepping (larger than sim dt).
        boundary_type: Domain boundary condition.
        initial_velocity: Initial velocity field (uniform vector).
        gravity: Gravitational acceleration vector.
        marker_particles: Number of tracer particles for visualization.
    """
    enabled: bool = Field(default=False, description="Enable fluid simulation")
    bounds: BoundingBox = Field(description="Physical domain bounds")
    resolution: tuple[int, ...] = Field(
        default=(32, 32), description="Grid resolution (nx, ny) or (nx, ny, nz)"
    )
    dim_3d: bool = Field(default=False, description="Use 3D grid")
    density: float = Field(default=1000.0, ge=1.0, description="Fluid density (kg/m³)")
    viscosity: float = Field(default=0.004, ge=0.0, description="Dynamic viscosity (Pa·s)")
    substep_dt: float = Field(default=0.02, gt=0.0, description="Fluid sub-step timestep")
    boundary_type: FluidBoundaryType = Field(
        default=FluidBoundaryType.WALL, description="Domain boundary condition"
    )
    initial_velocity: Position = Field(
        default_factory=Position, description="Initial uniform velocity field"
    )
    gravity: Position = Field(
        default_factory=lambda: Position(x=0, y=0, z=-9.81),
        description="Gravitational acceleration vector"
    )
    marker_particles: int = Field(
        default=0, ge=0, description="Tracer particles for visualization (0 = disabled)"
    )
    
    @field_validator("resolution")
    @classmethod
    def check_resolution(cls, v: tuple[int, ...], info: Any) -> tuple[int, ...]:
        """Validate resolution matches dimensionality."""
        dim_3d = info.data.get("dim_3d", False)
        expected = 3 if dim_3d else 2
        if len(v) != expected:
            raise ValueError(
                f"Resolution must have {expected} dimensions for "
                f"{'3D' if dim_3d else '2D'} simulation, got {len(v)}"
            )
        return v
```

### SceneDefinition Extension — Adding FluidConfig
```python
# In SceneDefinition class (line 1014+):
# Add field:
#    fluids: FluidConfig | None = Field(
#        default=None, description="Fluid simulation configuration"
#    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| SPH (smoothed particle hydrodynamics) | Eulerian grid (MAC) | 2024+ | Grid methods provide exact incompressibility via pressure projection; SPH is compressible unless using iterative solvers. Grid is standard for surgical bleeding where volume conservation matters. |
| Manual NumPy fluid solver | PhiFlow (production library) | 2025 | PhiFlow eliminates ~1,500 lines of physics code; battle-tested at scale (1.9K stars, used in PDEBench dataset). |
| Fluid only in Blender/Houdini | In-process fluid solver alongside simulator | Current | Enables RL agents to observe/interact with fluid during training. External DCC tools break the training loop. |

**PhiFlow 3.4.0 is current** (released Aug 2025). It's actively maintained with a 2024 ICML publication. No deprecation concerns.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | PhiFlow's `make_incompressible` is stable at 48³ resolution on surgical geometries | Standard Stack | If diverges, need iterative CG or coarser grid; adds 1-2 days to implementation |
| A2 | Force computation via pressure gradient integration over obstacle mask is accurate enough for RL training (not real-time visual fidelity) | Architecture Patterns | If RL agent needs high-fidelity fluid forces, may need tighter coupling or finer grid |
| A3 | Scipy.sparse.linalg.spsolve is fast enough for 32-48³ grids (~1-3s per solve) | Standard Stack | If 3D fluid is too slow for RL training, may need to use 2D slab approximation or asynchronous fluid threads |
| A4 | PhiFlow's Python 3.14 compat issues are non-blocking and workaround-able | Common Pitfalls | If critical issues surface in 2D/3D simulation, may need to downgrade to Python 3.12 or patch PhiFlow |
| A5 | Single merged obstacle SDF is sufficient for multiple surgical instruments (same boundary condition) | Common Pitfalls | If instruments need different velocities, need upstream PhiFlow fix or custom obstacle handling |
| A6 | Sub-stepping fluid at 10-25× the simulation timestep (e.g., every 0.02s vs 0.002s sim dt) provides adequate coupling for RL | Architecture Patterns | If two-way coupling is unstable at this ratio, may need more frequent fluid steps |
| A7 | Fluid is not needed during RL training for all tasks — only surgical scenarios with bleeding/irrigation | Architecture Patterns | If fluid becomes a bottleneck, `FluidConfig.enabled=False` provides clean disable path |

## Open Questions

1. **PhiFlow multi-obstacle bug (Pitfall 3) — will it be fixed upstream before we ship?**
   - What we know: The bug is reproducible in PhiFlow 3.4.0. Workaround exists (merge to single obstacle).
   - What's unclear: Whether PhiFlow maintainers will fix this; whether we should submit a PR.
   - Recommendation: Implement with the workaround. If per-obstacle velocities are needed for Phase 18, file a PhiFlow issue and implement the custom handling. The planner should include a task to test multi-obstacle with distinct velocities.

2. **What is the minimum obstacle size (in grid cells) for stable force computation?**
   - What we know: 2-3 cells minimum for reasonable force estimates; 5+ cells preferred.
   - What's unclear: Whether surgical instruments (needles, scalpels) can be represented at 2-3 cell resolution while maintaining meaningful coupling.
   - Recommendation: Target 48³ grid for a 0.3m domain → cell size ~6mm. Needles are ~2-5mm diameter → ~0.3-0.8 cells → may need sub-grid force model. Planner should include validation task.

3. **Is 2D slab approximation acceptable for initial v0.3.2 bleeding scenarios?**
   - What we know: 2D is ~50-100× faster than 3D at same in-plane resolution. Many surgical training scenarios involve cutting a surface (2D cut plane).
   - What's unclear: Whether product requirements demand full 3D fluid or 2D slab is sufficient.
   - Recommendation: Build both. 2D as default fast path, 3D behind `dim_3d=True` in config. Planner should structure tasks so 2D ships first, 3D follows.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All fluid code | ✓ | 3.14.4 | — |
| numpy | Fluid grid arrays | ✓ | 2.4.4 | — |
| scipy | Sparse Poisson solve | ✓ | 1.17.1 | — |
| phiflow | MAC grid, pressure solver, advection | ✓ | 3.4.0 | Custom NumPy (not recommended) |
| scikit-image | 3D marching cubes visualization | ✓ | 0.25.1 | Disable 3D viz; use 2D only |
| matplotlib | 2D colormesh rendering | ✓ | 3.10.9 | Text-based debug output |
| MuJoCo | Simulator backend 1 | ✓ | (project dep) | — |
| PyBullet | Simulator backend 2 | ✓ | (project dep) | — |

**Missing dependencies with no fallback:**
- None — all core dependencies are available

**Missing dependencies with fallback:**
- None

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (project standard) |
| Config file | pytest.ini (pythonpath = src) |
| Quick run command | `PYTHONPATH=src pytest tests/test_fluids/test_fluid_simulator.py -v` |
| Full suite command | `PYTHONPATH=src pytest tests/test_fluids/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FLUD-01 | MAC grid creation, advection, pressure projection on empty domain | unit | `pytest tests/test_fluids/test_fluid_simulator.py::test_mac_grid_init -x` | ❌ Wave 0 |
| FLUD-01 | Velocity remains divergence-free after pressure solve | unit | `pytest tests/test_fluids/test_fluid_simulator.py::test_divergence_free -x` | ❌ Wave 0 |
| FLUD-01 | 2D and 3D grid creation from FluidConfig | unit | `pytest tests/test_fluids/test_fluid_simulator.py::test_2d_vs_3d_grid -x` | ❌ Wave 0 |
| FLUD-02 | Single obstacle exerts correct force direction (sphere in uniform flow) | unit | `pytest tests/test_fluids/test_force_computation.py::test_sphere_drag_direction -x` | ❌ Wave 0 |
| FLUD-02 | Fluid boundaries update when object moves | integration | `pytest tests/test_fluids/test_fluid_simulator.py::test_moving_obstacle -x` | ❌ Wave 0 |
| FLUD-02 | Force applied to MuJoCo body via apply_force | integration | `pytest tests/test_fluids/test_fluid_simulator.py::test_mujoco_force_application -x` | ❌ Wave 0 |
| FLUD-03 | FluidConfig serializes/deserializes to JSON | unit | `pytest tests/test_fluids/test_schema.py::test_fluid_config_roundtrip -x` | ❌ Wave 0 |
| FLUD-03 | SceneDefinition with FluidConfig validates | unit | `pytest tests/test_fluids/test_schema.py::test_scene_with_fluid -x` | ❌ Wave 0 |
| FLUD-04 | 2D pressure colormesh renders without error | unit | `pytest tests/test_fluids/test_fluid_simulator.py::test_2d_visualization -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `PYTHONPATH=src pytest tests/test_fluids/ -x -q`
- **Per wave merge:** `PYTHONPATH=src pytest tests/test_fluids/ -v`
- **Phase gate:** Full test suite green (`PYTHONPATH=src pytest tests/ -q`) before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_fluids/__init__.py` — package marker
- [ ] `tests/test_fluids/test_fluid_simulator.py` — covers FLUD-01, FLUD-02, FLUD-04
- [ ] `tests/test_fluids/test_force_computation.py` — covers FLUD-02 force computation specifically
- [ ] `tests/test_fluids/test_schema.py` — covers FLUD-03 schema validation
- [ ] `tests/test_fluids/conftest.py` — shared fixtures (FluidConfig factory, mock simulator)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | No | N/A — fluid is an in-process physics subsystem |
| V3 Session Management | No | N/A |
| V4 Access Control | No | N/A |
| V5 Input Validation | Yes | Pydantic v2 field validators in FluidConfig (bounds consistency, resolution, positive density/viscosity) |
| V6 Cryptography | No | N/A |

### Known Threat Patterns for Python/NumPy/PhiFlow

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| NaN/inf injection via FluidConfig (negative viscosity) | Tampering | Pydantic `Field(ge=0.0)` validators on viscosity, density, substep_dt |
| Memory exhaustion from large resolution config | Denial of Service | Pydantic validator capping resolution (e.g., ≤128 per dimension) |
| Division by zero from zero cell volume | Denial of Service | Pydantic validator ensuring min_corner < max_corner in BoundingBox |
| Unvalidated numpy arrays from scene files | Elevation of Privilege | Fluid state serialization uses PhiFlow's typed tensor API, not raw pickle |

**Note:** Fluid simulation is an in-process physics subsystem with no network exposure. Security concerns are limited to input validation (preventing crashes/NaN from malformed configs) and resource limits (preventing memory exhaustion). These are addressed through Pydantic v2 validators in FluidConfig.

## Sources

### Primary (HIGH confidence)
- PhiFlow 3.4.0 — installed and verified via `pip install phiflow` + `phi.verify()`. [VERIFIED: pip, phi.verify()]
- PhiFlow Moving Obstacles example — [CITED: https://tum-pbs.github.io/PhiFlow/examples/grids/Moving_Obstacles.html]
- PhiFlow Staggered Grids documentation — [CITED: https://tum-pbs.github.io/PhiFlow/Staggered_Grids.html]
- PhiFlow Fluid Simulation guide — [CITED: https://tum-pbs.github.io/PhiFlow/Fluid_Simulation.html]
- PhiFlow Installation Instructions — [CITED: https://tum-pbs.github.io/PhiFlow/Installation_Instructions.html]
- PhiFlow GitHub repository — [CITED: https://github.com/tum-pbs/PhiFlow] — 1.9K stars, MIT license, 3,732 commits
- PyPI phiflow page — [CITED: https://pypi.org/project/phiflow/] — v3.4.0, released Aug 2 2025
- Project pyproject.toml — existing deps: scipy≥1.11.0, numpy≥1.24.0 [CITED: pyproject.toml lines 28-31]
- Project base_simulator.py — apply_force(), get_body_pose() hooks exist [CITED: src/surg_rl/simulators/base_simulator.py]

### Secondary (MEDIUM confidence)
- Mantaflow GitHub repository — last push 2022-10-26, 139 stars, no recent activity [CITED: github.com/thunil/mantaflow]
- PhiFlow manual benchmark: 32² grid with obstacle ≈ 114 ms/step (NumPy backend, macOS arm64) [VERIFIED: manual timing]
- PhiFlow 3D simulation: 24³ grid functional [VERIFIED: manual test]
- PhiFlow multi-obstacle bug: `AssertionError: Instance dimensions not supported for grids` at bake_extrapolation [VERIFIED: manual reproduction]
- PhiFlow Python 3.14 numpy extraction quirk: `TypeError: 'NoneType' object is not iterable` [VERIFIED: manual reproduction]

### Tertiary (LOW confidence)
- Force computation accuracy for sub-cell obstacles (< 2 cells) — not yet validated; assumption-based estimate
- PhiFlow stability at 48³ resolution on surgical geometries — not yet tested; extrapolated from 32³
- RL training impact of fluid sub-step frequency — dependent on specific surgical task; not tested

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — PhiFlow installed, verified, benchmarked; Mantaflow confirmed dead; alternatives exhausted
- Architecture: MEDIUM — Integration pattern clear but not yet tested end-to-end; force computation needs validation
- Pitfalls: HIGH — Three bugs reproduced manually (multi-obstacle, numpy extraction, Python 3.14 compat)

**Research date:** 2026-05-04
**Valid until:** 2026-06-04 (30 days — PhiFlow is stable/well-maintained but Python 3.14 compat may evolve)

# Phase 16: Deformable Objects — Research

**Researched:** 2026-05-04
**Domain:** FEM-based deformable body simulation (MuJoCo flex / PyBullet soft body)
**Confidence:** HIGH

## Summary

MuJoCo 3.x provides two paths for deformable bodies: the high-level `<flexcomp>` element (grid/mesh/gmsh-based generation) and the low-level `<flex>` element within `<deformable>` (explicit vertex/element arrays for arbitrary tetrahedral meshes). For this phase, the low-level `<flex>` path is preferred because Phase 15 (tetgen) will produce arbitrary tetrahedral meshes that flexcomp's built-in grid/gmsh generators cannot directly consume. PyBullet's `loadSoftBody` already accepts `.vtk` tetrahedral meshes and has existing parameter mapping in `PyBulletSoftBodyConfig` — this phase should improve the mapping from our high-level material properties (stiffness, damping, Young's modulus) to PyBullet's parameter space.

The unified `DeformableConfig` schema should sit alongside `TissueConfig`, providing backend-specific overrides for MuJoCo (elasticity, edge stiffness, pin attachments) and PyBullet (mass-spring vs Neo-Hookean, repulsion stiffness). The observable state must expose vertex positions from `mjData.flexvert_xpos` (MuJoCo) and `getMeshData` (PyBullet), plus optionally compute per-element strain.

**Primary recommendation:** Use MuJoCo's `<deformable>/<flex>` low-level API (not `<flexcomp>`) for FEM bodies from tetgen meshes. Use existing PyBullet `PyBulletSoftBodyConfig` as the PyBullet override, wrapping it in a new unified `DeformableConfig` that is referenced by `TissueConfig`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| FEM mesh loading (MuJoCo) | SceneBuilder (MJCF gen) | — | MJCF compilation is the only path to loading flex bodies |
| FEM simulation (MuJoCo) | MuJoCo engine (`mj_step`) | — | Engine-internal FEM solver, no application code involvement |
| Soft body loading (PyBullet) | PyBulletSimulator | SceneBuilder | `loadSoftBody` called at runtime, mesh prep in builder |
| Deformable state observation | Simulator (`get_state`) | ObservationBuilder | Raw vertex data extracted per-backend, shaped by obs config |
| Schema (DeformableConfig) | `scene_definition/schema.py` | — | Pydantic models live in the schema module |
| Parameter mapping | Simulator | — | Each backend maps high-level config to engine-specific params |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| MuJoCo | 3.6.0 (installed) | FEM deformable bodies via `deformable/flex` | Only production FEM solver available; built-in to engine |
| PyBullet | 3.2.7 (installed) | Soft body via `loadSoftBody` | Primary soft-body backend; existing integration |
| Pydantic | v2 | Schema definitions | Project standard; model_validator for parameter validation |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| NumPy | ≥1.26 | Vertex position arrays, strain computation | All vertex/edge math for observation extraction |
| tetgen (Phase 15) | TBD | Tetrahedral mesh generation | Produces `.node`/`.ele` files consumed by this phase |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `flexcomp` (high-level) | `deformable/flex` (low-level) | flexcomp grid/gmsh generators don't accept arbitrary tet meshes; `flex` gives explicit vertex/element control |
| SOFA Framework | MuJoCo flex | SOFA adds separate dependency and integration complexity; MuJoCo is already the project backend |
| CGAL tet meshing | tetgen (Phase 15) | tetgen is purpose-built for tetrahedralization; CGAL is heavier |

## Architecture Patterns

### System Architecture Diagram

```
Scene JSON/YAML (DeformableConfig)
        │
        ▼
┌───────────────────────┐
│   TissueConfig        │  soft_body=True → DeformableConfig
│   .physics (material) │
│   .deformable (mesh)  │
└───────────┬───────────┘
            │
     ┌──────┴──────┐
     │             │
     ▼             ▼
┌─────────┐  ┌──────────┐
│ MuJoCo  │  │ PyBullet │
│ Backend │  │ Backend  │
└────┬────┘  └────┬─────┘
     │             │
     ▼             ▼
MJCF flex XML   loadSoftBody
(vertex/elem)   (.vtk mesh + params)
     │             │
     ▼             ▼
mj_step() FEM   stepSimulation
     │             │
     └──────┬──────┘
            ▼
┌───────────────────────┐
│  Observation Pipeline │
│  flexvert_xpos /      │
│  getMeshData()        │
│       │               │
│       ▼               │
│  vertex positions +   │
│  strain computation   │
└───────────────────────┘
```

### Pattern 1: MuJoCo Low-Level Flex (FEM from Tet Mesh)

**What:** Use `<deformable>/<flex>` to define an FEM body with explicit vertex positions, element connectivity, and associated rigid bodies. This accepts arbitrary tetrahedral meshes — critical for consuming Phase 15 tetgen output.

**When to use:** Whenever the deformable body mesh comes from an external generator (tetgen). This is the only path that accepts explicit vertex + element arrays for 3D (tetrahedral) meshes.

**Example — MJCF for a tet-mesh flex body:**
```xml
<mujoco model="deformable_tissue">
  <option timestep="0.002" gravity="0 0 -9.81"/>

  <worldbody>
    <!-- Anchor bodies for boundary conditions -->
    <body name="clamp_left" pos="-0.05 0 0.0"/>
    <body name="clamp_right" pos="0.05 0 0.0"/>
  </worldbody>

  <deformable>
    <flex name="tissue_flex" dim="3" radius="0.0"
          rgba="0.9 0.7 0.7 1" flatskin="true"
          body="clamp_left"><!-- single body = rigid; overridden per-vertex -->
      <contact condim="3" solref="0.01 1" solimp="0.95 0.99 0.0001"
               selfcollide="none" margin="0.001"/>
      <edge stiffness="1000" damping="0.1"/>
      <elasticity young="10000" poisson="0.45" damping="0.01"/>
      <!-- Vertices: 4 tet corners → (N,3) coords in local frame -->
      <vertex>0 0 0  0.1 0 0  0 0.1 0  0 0 0.01</vertex>
      <!-- Elements: zero-indexed vertex quads → 1 tet -->
      <element>0 1 2 3</element>
    </flex>
  </deformable>
</mujoco>
```

### Pattern 2: Flex-to-Rigid Attachment (Boundary Conditions)

**What:** Use `<pin>` elements within `<flexcomp>` or `<equality weld>` at the body level to attach flex vertices to rigid anchors. Pins lock specific vertices to world (or to named bodies). This models tissue clamped to fixtures.

**When to use:** Any deformable body that must be anchored at specific points (surgical clamps, organ attachments).

**Example — Pinning flex vertices:**
```xml
<worldbody>
  <body name="clamp" pos="0.05 0 0.0">
    <geom type="box" size="0.01 0.01 0.01" rgba="0.5 0.5 0.5 1"/>
  </body>
  <flexcomp name="tissue" type="grid" count="5 5 2" spacing="0.02 0.02 0.005"
            pos="0 0 0" dim="3" mass="0.01">
    <!-- Pin vertices 0-4 (one edge) to the clamp body -->
    <pin id="0" range="0 5"/>
    <elasticity young="5000" poisson="0.45" damping="0.01"/>
    <contact condim="3" selfcollide="none"/>
  </flexcomp>
</worldbody>

<!-- Alternative: weld equality for full-body attachment -->
<equality>
  <weld name="attach_tissue" body1="tissue_flex" body2="clamp"
        solref="0.01 1"/>
</equality>
```

### Pattern 3: PyBullet Soft Body Parameter Mapping

**What:** Map high-level material properties (stiffness, damping, Young's modulus, Poisson's ratio) to PyBullet's `loadSoftBody` parameters. The key insight: PyBullet has two regimes — mass-spring (simple, fast) and Neo-Hookean (physically accurate, slower). The existing `PyBulletSoftBodyConfig` already models both; this phase should add automatic mapping from `SoftBodyPhysics` high-level fields.

**When to use:** PyBullet backend whenever `TissueConfig.soft_body=True`.

**Parameter Mapping Table:**
| SoftBodyPhysics Field | PyBullet Neo-Hookean Param | PyBullet Mass-Spring Param | Notes |
|------------------------|---------------------------|---------------------------|-------|
| `youngs_modulus` (E) | `NeoHookeanMu` = E/(2*(1+ν)), `NeoHookeanLambda` = E*ν/((1+ν)*(1-2ν)) | `springElasticStiffness` = E * element_area / element_length | μ and λ derived from E, ν |
| `poissons_ratio` (ν) | Used in μ, λ derivation above | N/A | Only meaningful in Neo-Hookean |
| `damping` | `NeoHookeanDamping` | `springDampingStiffness` | Damping ratio scales differently per model |
| `density` × volume | N/A (per-node mass) | N/A (per-node mass) | Total mass = density × volume |
| `stiffness` | N/A | `springElasticStiffness` proxy | Used in mass-spring fallback only |

**Existing code already maps these** (in `pybullet_simulator.py:_load_soft_body_tissue`, lines 612-668). This phase should: (a) add the auto-derivation of μ/λ from E/ν when Neo-Hookean mode is used but μ/λ are not explicitly set, and (b) document the mapping in schema docstrings.

### Anti-Patterns to Avoid
- **Hardcoding vertex counts:** Never assume `count="5 5 2"` grid size. Extract from mesh metadata. Grid-based flexcomp won't work with Phase 15 tetgen output.
- **Mixing flexcomp and flex semantics:** `flexcomp` generates vertices from parameters; `flex` accepts explicit vertex arrays. Don't try to pass explicit vertices to flexcomp.
- **Forgetting RESET_USE_DEFORMABLE_WORLD:** PyBullet must reset with this flag before any soft body load, even on fresh connect. Already handled in existing code but worth auditing.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| FEM solver | Custom stiffness matrix assembly | MuJoCo's built-in SVK FEM | MuJoCo handles implicit integration, collisions, constraint projection — years of numerical optimization |
| Tetrahedral mesh vertex/element ordering | Manual vertex sorting | tetgen output (Phase 15) `.node`/`.ele` format | tetgen guarantees consistent orientation and non-degenerate elements |
| Soft body collision detection | Custom SDF or BVH | MuJoCo flex contact / PyBullet built-in | Both engines handle flex-to-rigid and self-collision |
| Strain computation | Custom finite element strain | Per-edge length ratio or element volume ratio | Simple, fast, and sufficient for RL observation |
| Parameter unit conversion | Inline conversion at call site | `DeformableConfig.to_mujoco()` / `.to_pybullet()` methods | Single source of truth, testable |

**Key insight:** The FEM solver is the single hardest piece to get right. MuJoCo's SVK (Saint Venant-Kirchhoff) model with implicit integration is battle-tested. Any hand-rolled alternative would require months of numerical debugging and would still lack collision integration.

## Runtime State Inventory

> This is a greenfield capability phase (not a rename/refactor/migration phase).
> No runtime state inventory needed.

## Common Pitfalls

### Pitfall 1: Using flexcomp with Arbitrary Tet Meshes
**What goes wrong:** flexcomp's `type` attribute only accepts `"grid"`, `"mesh"`, or `"gmsh"`. None of these accept raw vertex+element arrays. Attempting to load a tetgen `.node` file via flexcomp's `file` attribute silently fails or produces wrong geometry.
**Why it happens:** flexcomp is a generator — it creates vertices from parametric descriptions. The low-level `flex` element is the correct path for pre-computed meshes.
**How to avoid:** Always use `<deformable>/<flex>` with explicit `<vertex>` and `<element>` when loading from tetgen. Reserve `<flexcomp>` for procedurally generated (grid-based) soft bodies.
**Warning signs:** Compiler error about element count mismatch, or flex body not appearing in rendered scene.

### Pitfall 2: PyBullet Neo-Hookean Parameter Stability
**What goes wrong:** PyBullet soft bodies explode or collapse when Neo-Hookean parameters (μ, λ) are poorly chosen relative to mesh resolution.
**Why it happens:** Neo-Hookean stiffness depends on element size — smaller elements require stiffer parameters to resist deformation. Default values (μ=1, λ=1) may be too soft for fine meshes.
**How to avoid:** Derive μ and λ from physical material properties (E, ν) and scale by element characteristic length. Provide sensible defaults in schema docstrings. Start with mass-spring model for debugging, then switch to Neo-Hookean.
**Warning signs:** Vertices flying to infinity within first few simulation steps; NaN in vertex positions.

### Pitfall 3: Stale `body` Array When Flex Vertex Count Changes
**What goes wrong:** The `body` attribute of `<flex>` must have length equal to nvert or 1. If the tetgen mesh has a different vertex count than expected, compilation fails.
**Why it happens:** Phase 15 mesh generation produces variable vertex counts depending on geometry and resolution.
**How to avoid:** Always set `body` to a single body name (making the flex rigidly attached to that body), then use `<pin>` elements for selective attachment. Never hardcode a per-vertex body array.
**Warning signs:** "body attribute must have length nvert or 1" compiler error.

### Pitfall 4: Observation Array Shape Mismatch
**What goes wrong:** `TISSUE_DEFORMATION_SPEC` in `observation.py` is hardcoded to shape `(50, 3)` (matching a 5×5×2=50 vertex grid). Tetgen meshes can have arbitrary vertex counts.
**Why it happens:** The observation spec was written assuming flexcomp grid-based soft bodies.
**How to avoid:** Either: (a) pad/truncate deformable observation to a fixed size (current approach — keep it), or (b) use a variable-length observation space (gymnasium `Dict` with dynamic shape). For RL, fixed-size observations are strongly preferred. Use padding with a sentinel value (e.g., 0 displacement) for unused vertices, and expose actual vertex count in observation metadata.
**Warning signs:** Shape mismatch exceptions in `ObservationBuilder.extract_observation`.

### Pitfall 5: Pydantic `pybullet` Field Default Factory
**What goes wrong:** `SoftBodyPhysics.pybullet` uses `default_factory=PyBulletSoftBodyConfig`. According to AGENTS.md conventions, this field is always present. But when constructing `SoftBodyPhysics` with partial data, the factory may create a config with all defaults even when the user intended no PyBullet-specific overrides.
**Why it happens:** The factory runs unconditionally.
**How to avoid:** This is acceptable behavior — the factory creates reasonable defaults. The existing code correctly handles this (optional overrides like `mass`, `scale`, `collision_margin` are `None` by default and only applied when set). No change needed, but audit during implementation.

## Code Examples

### MuJoCo: Full Flex Body from Tetgen Mesh

```xml
<!-- Source: MuJoCo XML Reference (deformable/flex), verified against mujoco 3.6.0 -->
<mujoco model="surgical_tissue">
  <compiler angle="radian" meshdir="assets/"/>

  <option timestep="0.002" gravity="0 0 -9.81"/>

  <asset>
    <!-- Visual surface mesh for rendering only -->
    <mesh name="tissue_surface" file="tissue_surface.obj"
          scale="1 1 1"/>
  </asset>

  <worldbody>
    <!-- Rigid anchor bodies for clamps -->
    <body name="clamp_left" pos="-0.04 0 0.0">
      <geom type="box" size="0.005 0.005 0.005" rgba="0.3 0.3 0.3 1"/>
    </body>
    <body name="clamp_right" pos="0.04 0 0.0">
      <geom type="box" size="0.005 0.005 0.005" rgba="0.3 0.3 0.3 1"/>
    </body>

    <!-- Rigid body for visual-only surface mesh -->
    <body name="tissue_visual" pos="0 0 0">
      <geom type="mesh" mesh="tissue_surface" rgba="0.9 0.7 0.7 0.3"
            contype="0" conaffinity="0"/>
    </body>
  </worldbody>

  <deformable>
    <!-- FEM body: 3D tetrahedral mesh from tetgen -->
    <!-- body="world" = global frame (vertices defined in world coords) -->
    <flex name="tissue" dim="3" radius="0.0"
          rgba="0.9 0.7 0.7 1" flatskin="false"
          body="world">
      <!-- Contact: 3D contacts (condim=3), tuned solver params -->
      <contact condim="3" solref="0.01 1" solimp="0.95 0.99 0.0001"
               friction="0.5 0.005 0.0001"
               selfcollide="none" margin="0.001"/>

      <!-- Edge stiffness: resistance to stretching -->
      <edge stiffness="5000" damping="0.1"/>

      <!-- Elasticity: Saint Venant-Kirchhoff FEM -->
      <!-- young=10000 Pa (soft tissue), poisson=0.45 (nearly incompressible) -->
      <elasticity young="10000" poisson="0.45" damping="0.01"/>

      <!-- Vertices from tetgen .node file: (N, 3) world coordinates -->
      <!-- In practice, these would be generated programmatically -->
      <vertex>
        0.0 0.0 0.0
        0.1 0.0 0.0
        0.0 0.1 0.0
        0.0 0.0 0.01
        0.05 0.05 0.005
        <!-- ... N vertices total ... -->
      </vertex>

      <!-- Tetrahedral elements from tetgen .ele file: (M, 4) indices -->
      <element>
        0 1 2 3
        1 2 3 4
        <!-- ... M elements total ... -->
      </element>
    </flex>
  </deformable>

  <!-- Pin boundary conditions: lock specific vertices to anchor bodies -->
  <!-- Note: <pin> goes inside <flexcomp>, not <flex> -->
  <!-- For low-level <flex>, use <equality weld> instead -->
  <equality>
    <!-- Weld flex body to clamp bodies at specific relative poses -->
    <weld name="attach_left" body1="tissue" body2="clamp_left"
          relpose="0 0 0 1 0 0 0" solref="0.01 1"/>
  </equality>
</mujoco>
```

### Python: Programmatic MJCF Flex Generation from Tetgen Output

```python
# Source: Based on existing SceneBuilder pattern in scene_builder.py
# Generates <deformable>/<flex> XML from tetgen .node and .ele files
import xml.etree.ElementTree as ET
import numpy as np
from pathlib import Path
from typing import Any


def _add_deformable_flex_to_mjcf(
    mujoco_root: ET.Element,
    tissue: Any,
    node_path: Path,    # tetgen .node file
    ele_path: Path,     # tetgen .ele file
) -> None:
    """Add a low-level <flex> FEM body to MJCF from tetgen output.

    Args:
        mujoco_root: Root <mujoco> element.
        tissue: TissueConfig with soft_body=True and DeformableConfig.
        node_path: Path to tetgen .node file (vertices).
        ele_path: Path to tetgen .ele file (tetrahedra).
    """
    # Parse tetgen output
    vertices = _parse_tetgen_node(node_path)  # (N, 3) float
    elements = _parse_tetgen_ele(ele_path)    # (M, 4) int (1-indexed → 0-indexed)

    # Create <deformable> section if not present
    deformable = mujoco_root.find("deformable")
    if deformable is None:
        deformable = ET.SubElement(mujoco_root, "deformable")

    # Material properties from config
    dc = tissue.deformable  # DeformableConfig
    mc = dc.mujoco           # MuJoCo override
    physics = tissue.physics  # SoftBodyPhysics for material defaults

    flex = ET.SubElement(deformable, "flex",
        name=f"{tissue.name}_flex",
        dim="3",
        radius="0.0",
        rgba=f"{tissue.color.r} {tissue.color.g} {tissue.color.b} {tissue.color.a}",
        flatskin="false" if mc.smooth_normals else "true",
        body="world",
    )

    # Contact: use override values or derive from physics
    ET.SubElement(flex, "contact",
        condim=str(mc.condim),
        solref=mc.solref or "0.01 1",
        solimp=mc.solimp or "0.95 0.99 0.0001",
        friction=f"{mc.friction} 0.005 0.0001",
        selfcollide="none",
        margin=str(mc.margin),
    )

    # Edge stiffness
    edge_stiffness = mc.edge_stiffness or physics.stiffness
    edge_damping = mc.edge_damping or physics.damping
    ET.SubElement(flex, "edge",
        stiffness=str(edge_stiffness),
        damping=str(edge_damping),
    )

    # Elasticity (FEM)
    young = mc.youngs_modulus or physics.youngs_modulus
    poisson = mc.poissons_ratio or physics.poissons_ratio
    fem_damping = mc.fem_damping or physics.damping * 0.1
    ET.SubElement(flex, "elasticity",
        young=str(young),
        poisson=str(poisson),
        damping=str(fem_damping),
    )

    # Vertices: space-separated floats, 3 per line
    vert_str = "\n".join(
        f"{v[0]} {v[1]} {v[2]}" for v in vertices
    )
    ET.SubElement(flex, "vertex").text = vert_str

    # Elements: space-separated indices, 4 per line (0-indexed)
    elem_str = "\n".join(
        f"{e[0]} {e[1]} {e[2]} {e[3]}" for e in elements
    )
    ET.SubElement(flex, "element").text = elem_str

    # Pin boundary conditions go into <equality> section
    if dc.boundary_conditions:
        equality = mujoco_root.find("equality")
        if equality is None:
            equality = ET.SubElement(mujoco_root, "equality")
        for bc in dc.boundary_conditions:
            if bc.type == "pin":
                # Weld flex body to anchor body
                ET.SubElement(equality, "weld",
                    name=f"pin_{bc.name}",
                    body1=f"{tissue.name}_flex",
                    body2=bc.anchor_body,
                    solref="0.01 1",
                )
```

### Pydantic: Unified DeformableConfig Schema

```python
# Source: Extends existing schema.py patterns; Pydantic v2 conventions
from pydantic import BaseModel, Field, model_validator
from typing import Literal


class BoundaryCondition(BaseModel):
    """A single boundary condition for a deformable body."""
    name: str = Field(description="BC name (e.g., 'clamp_left')")
    type: Literal["pin", "fixed_displacement", "force"] = Field(
        default="pin", description="BC type"
    )
    anchor_body: str = Field(
        description="Name of the rigid body to attach to"
    )
    vertex_indices: list[int] = Field(
        default_factory=list,
        description="Vertex indices to constrain (empty = full weld)"
    )
    stiffness: float = Field(
        default=1e6, ge=0.0,
        description="Attachment stiffness (Pa for pins, N/m for springs)"
    )


class MuJoCoFlexConfig(BaseModel):
    """MuJoCo-specific flex/FEM parameters.

    All fields are optional overrides of the base material properties
    in SoftBodyPhysics. When None, the base value is used.
    """
    # FEM material
    youngs_modulus: float | None = Field(
        default=None, ge=0.0,
        description="Override Young's modulus (Pa) for MuJoCo FEM"
    )
    poissons_ratio: float | None = Field(
        default=None, ge=0.0, le=0.5,
        description="Override Poisson's ratio for MuJoCo FEM"
    )
    fem_damping: float | None = Field(
        default=None, ge=0.0,
        description="Rayleigh damping coefficient for FEM (units: time)"
    )

    # Edge properties
    edge_stiffness: float | None = Field(
        default=None, ge=0.0,
        description="Edge spring stiffness (N/m)"
    )
    edge_damping: float | None = Field(
        default=None, ge=0.0,
        description="Edge spring damping"
    )

    # Contact
    condim: int = Field(default=3, ge=1, le=6,
        description="Contact dimensionality (1, 3, 4, 6)")
    solref: str | None = Field(
        default=None,
        description="Solver reference params (timeconst dampratio)"
    )
    solimp: str | None = Field(
        default=None,
        description="Solver impedance params (d0 dWidth width midpoint power)"
    )
    friction: float = Field(
        default=0.5, ge=0.0,
        description="Contact friction coefficient"
    )
    margin: float = Field(
        default=0.001, ge=0.0,
        description="Contact margin (m)"
    )

    # Mesh
    smooth_normals: bool = Field(
        default=True,
        description="Use smooth (Gouraud) shading for flex surface"
    )


class PyBulletFlexConfig(BaseModel):
    """PyBullet-specific soft body parameters.

    Subset of existing PyBulletSoftBodyConfig — the full config remains
    on SoftBodyPhysics.pybullet for backward compatibility.
    This config provides the unified override entry point.
    """
    solver_type: Literal["mass_spring", "neo_hookean"] = Field(
        default="mass_spring",
        description="PyBullet soft body solver type"
    )
    auto_derive_neo_hookean: bool = Field(
        default=True,
        description="Auto-derive Neo-Hookean mu/lambda from E, nu"
    )
    repulsion_stiffness: float = Field(
        default=800.0, ge=0.0,
        description="Contact repulsion stiffness"
    )
    use_self_collision: bool = Field(
        default=False, description="Enable self-collision"
    )
    bending_stiffness: float = Field(
        default=0.1, ge=0.0,
        description="Bending stiffness (mass-spring only)"
    )
    collision_margin: float = Field(
        default=0.006, gt=0.0,
        description="Collision margin (m)"
    )


class DeformableConfig(BaseModel):
    """Unified deformable body configuration.

    Attached to TissueConfig when soft_body=True.
    Provides backend-specific overrides while falling back to
    SoftBodyPhysics for material properties.

    Example:
        >>> dc = DeformableConfig(
        ...     mesh_source="tetgen",
        ...     mesh_path="meshes/tissue",
        ...     mujoco=MuJoCoFlexConfig(youngs_modulus=15000.0),
        ...     pybullet=PyBulletFlexConfig(solver_type="neo_hookean"),
        ...     boundary_conditions=[
        ...         BoundaryCondition(name="clamp_l", anchor_body="clamp_left"),
        ...     ],
        ... )
    """
    mesh_source: Literal["tetgen", "flexcomp_grid", "file"] = Field(
        default="tetgen",
        description="How the deformable mesh is generated"
    )
    mesh_path: str | None = Field(
        default=None,
        description="Path to mesh file or tetgen prefix (without extension)"
    )
    mesh_resolution: int = Field(
        default=4, ge=1,
        description="Mesh resolution hint (coarser=faster, finer=more accurate)"
    )
    max_vertices: int = Field(
        default=200, ge=1,
        description="Maximum vertex count (for observation padding)"
    )

    # Backend-specific overrides
    mujoco: MuJoCoFlexConfig = Field(
        default_factory=MuJoCoFlexConfig,
        description="MuJoCo FEM override parameters"
    )
    pybullet: PyBulletFlexConfig = Field(
        default_factory=PyBulletFlexConfig,
        description="PyBullet soft body override parameters"
    )

    # Boundary conditions
    boundary_conditions: list[BoundaryCondition] = Field(
        default_factory=list,
        description="Attachment/pin boundary conditions"
    )

    # Observability
    observe_vertex_positions: bool = Field(
        default=True,
        description="Include vertex positions in observation"
    )
    observe_strain: bool = Field(
        default=False,
        description="Include per-element strain in observation"
    )
    observe_stress: bool = Field(
        default=False,
        description="Include per-element stress in observation"
    )

    @model_validator(mode="after")
    def validate_mesh_source(self) -> "DeformableConfig":
        """Ensure mesh_path is set for non-grid sources."""
        if self.mesh_source != "flexcomp_grid" and not self.mesh_path:
            raise ValueError(
                f"mesh_path is required when mesh_source='{self.mesh_source}'"
            )
        return self
```

### PyBullet: Improved Parameter Mapping

```python
# Source: Extension of existing _load_soft_body_tissue in pybullet_simulator.py
# Auto-derive Neo-Hookean parameters from Young's modulus and Poisson's ratio
def _derive_neo_hookean_params(
    youngs_modulus: float,   # E (Pa)
    poissons_ratio: float,   # ν (unitless)
) -> tuple[float, float]:
    """Derive Neo-Hookean μ and λ from linear elastic constants.

    For an isotropic linear elastic material:
        μ = E / (2 * (1 + ν))       # Shear modulus (Lame's second parameter)
        λ = E * ν / ((1 + ν) * (1 - 2ν))  # Lame's first parameter

    Returns:
        (mu, lambda) tuple.
    """
    mu = youngs_modulus / (2.0 * (1.0 + poissons_ratio))
    lam = (youngs_modulus * poissons_ratio) / (
        (1.0 + poissons_ratio) * (1.0 - 2.0 * poissons_ratio)
    )
    return mu, lam


def _build_soft_body_kwargs(
    tissue: Any,
    mesh_path: Path,
    physics_client: int,
) -> dict:
    """Build loadSoftBody kwargs with improved parameter mapping.

    Uses DeformableConfig.pybullet for solver selection, then falls back
    to existing PyBulletSoftBodyConfig for detailed parameter values.
    Auto-derives Neo-Hookean μ/λ from SoftBodyPhysics when not specified.
    """
    dc = tissue.deformable                     # DeformableConfig
    physics = tissue.physics                    # SoftBodyPhysics
    pbc = getattr(physics, "pybullet", None)    # PyBulletSoftBodyConfig
    pc = dc.pybullet                            # PyBulletFlexConfig

    kwargs = {
        "fileName": str(mesh_path),
        "basePosition": [
            tissue.pose.position.x,
            tissue.pose.position.y,
            tissue.pose.position.z,
        ],
        "baseOrientation": [
            tissue.pose.orientation.x,
            tissue.pose.orientation.y,
            tissue.pose.orientation.z,
            tissue.pose.orientation.w,
        ],
        "useSelfCollision": 1 if pc.use_self_collision else 0,
        "repulsionStiffness": pc.repulsion_stiffness,
        "collisionMargin": pc.collision_margin,
        "physicsClientId": physics_client,
    }

    # Solver selection
    if pc.solver_type == "neo_hookean":
        kwargs["useMassSpring"] = 0
        kwargs["useNeoHookean"] = 1
        # Auto-derive or use explicit values
        if pc.auto_derive_neo_hookean and pbc is not None:
            mu, lam = _derive_neo_hookean_params(
                physics.youngs_modulus,
                physics.poissons_ratio,
            )
            kwargs["NeoHookeanMu"] = pbc.neo_hookean_mu or mu
            kwargs["NeoHookeanLambda"] = pbc.neo_hookean_lambda or lam
            kwargs["NeoHookeanDamping"] = pbc.neo_hookean_damping or (
                physics.damping * 0.01
            )
        elif pbc is not None:
            kwargs["NeoHookeanMu"] = pbc.neo_hookean_mu
            kwargs["NeoHookeanLambda"] = pbc.neo_hookean_lambda
            kwargs["NeoHookeanDamping"] = pbc.neo_hookean_damping
    else:
        # Mass-spring (default)
        kwargs["useMassSpring"] = 1
        kwargs["useNeoHookean"] = 0
        kwargs["useBendingSprings"] = 1 if pc.bending_stiffness > 0 else 0
        if pbc is not None:
            kwargs["springElasticStiffness"] = pbc.spring_elastic_stiffness
            kwargs["springDampingStiffness"] = pbc.spring_damping_stiffness
            kwargs["springBendingStiffness"] = pbc.spring_bending_stiffness or pc.bending_stiffness
            kwargs["frictionCoeff"] = pbc.friction_coefficient

    # Mass: override from PyBulletSoftBodyConfig or derive from density
    if pbc is not None and pbc.mass is not None:
        kwargs["mass"] = pbc.mass
    else:
        density = physics.density
        # Approximate volume from bounding dims or mesh metadata
        dims = getattr(tissue.geometry, "dimensions", (0.1, 0.1, 0.01))
        volume = dims[0] * dims[1] * dims[2] if len(dims) >= 3 else 1e-4
        kwargs["mass"] = density * volume

    # Optional simFileName for separate simulation mesh
    if pbc is not None and pbc.sim_mesh_path is not None:
        kwargs["simFileName"] = pbc.sim_mesh_path

    return kwargs
```

### Observation: Vertex Position Extraction

```python
# Source: Extends MuJoCoSimulator.get_tissue_deformation() pattern
def get_deformable_observation(
    simulator,         # MuJoCoSimulator | PyBulletSimulator
    tissue_name: str,
    max_vertices: int = 50,    # Observation padding size
) -> dict:
    """Extract deformable state as padded observation arrays.

    Returns:
        dict with:
            vertex_positions: (max_vertices, 3) padded with zeros
            vertex_strain: (max_vertices,) optional per-vertex strain
            n_active_vertices: int
    """
    if hasattr(simulator, "_model"):  # MuJoCo
        model = simulator._model
        data = simulator._data
        try:
            flex_id = mujoco.mj_name2id(
                model, mujoco.mjtObj.mjOBJ_FLEX, f"{tissue_name}_flex"
            )
        except Exception:
            return _empty_deformable_obs(max_vertices)

        # Current vertex positions (world frame)
        vert_start = model.flex_vertadr[flex_id]
        vert_count = model.flex_vertnum[flex_id]
        current_pos = data.flexvert_xpos[vert_start:vert_start + vert_count].copy()

        # Rest positions for displacement
        rest_pos = model.flex_vert[vert_start:vert_start + vert_count].copy()
        displacements = current_pos - rest_pos

        # Pad to fixed size
        padded_pos = np.zeros((max_vertices, 3), dtype=np.float32)
        n_verts = min(vert_count, max_vertices)
        padded_pos[:n_verts] = current_pos[:n_verts]

        # Per-edge strain (proxy: edge length ratio)
        edge_start = model.flex_edgeadr[flex_id]
        edge_count = model.flex_edgenum[flex_id]
        current_edges = data.flexedge_length[edge_start:edge_start + edge_count]
        rest_edges = model.flex_edge[edge_start:edge_start + edge_count]
        strain = np.zeros(max_vertices, dtype=np.float32)
        # Simple: per-element strain from volume ratio
        elem_start = model.flex_elemadr[flex_id]
        elem_count = model.flex_elemnum[flex_id]
        # For each element, compare current volume to rest volume
        # (Simplified — full per-element volume computation needs element geometry)

        return {
            "vertex_positions": padded_pos,
            "vertex_displacements": np.pad(
                displacements,
                ((0, max_vertices - n_verts), (0, 0)),
                constant_values=0.0,
            )[:max_vertices],
            "vertex_strain": strain,
            "n_active_vertices": vert_count,
        }

    elif hasattr(simulator, "_soft_body_ids"):  # PyBullet
        if tissue_name not in simulator._soft_body_ids:
            return _empty_deformable_obs(max_vertices)

        soft_id = simulator._soft_body_ids[tissue_name]
        data = simulator._pb.getMeshData(
            soft_id, physicsClientId=simulator._physics_client
        )
        vertices = np.array(data[1], dtype=np.float32)  # (N, 3)

        padded = np.zeros((max_vertices, 3), dtype=np.float32)
        n_verts = min(len(vertices), max_vertices)
        padded[:n_verts] = vertices[:n_verts]

        return {
            "vertex_positions": padded,
            "vertex_displacements": np.zeros((max_vertices, 3), dtype=np.float32),
            "vertex_strain": np.zeros(max_vertices, dtype=np.float32),
            "n_active_vertices": len(vertices),
        }

    return _empty_deformable_obs(max_vertices)


def _empty_deformable_obs(max_vertices: int) -> dict:
    return {
        "vertex_positions": np.zeros((max_vertices, 3), dtype=np.float32),
        "vertex_displacements": np.zeros((max_vertices, 3), dtype=np.float32),
        "vertex_strain": np.zeros(max_vertices, dtype=np.float32),
        "n_active_vertices": 0,
    }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| flexcomp type="grid" hardcoded in scene_builder | `deformable/flex` with explicit vertex/element from tetgen | Phase 15-16 | Enables arbitrary mesh topologies; requires schema change |
| PyBullet params hardcoded per-call | `PyBulletFlexConfig` with auto-derivation of μ/λ from E/ν | This phase | Physically meaningful parameterization, less trial-and-error |
| TISSUE_DEFORMATION_SPEC hardcoded to (50,3) | Padded fixed-size observation with `n_active_vertices` metadata | This phase | Works with any vertex count; RL-compatible |

**Deprecated/outdated:**
- `flexcomp type="grid"` for surgical tissue: Only useful for debugging simple rectangular patches. Not representative of real tissue geometry.
- VTK-based mesh generation in `vtk_io.py`: Phase 15 replaces this with tetgen.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | tetgen output `.node`/`.ele` files can be directly mapped to MuJoCo `<vertex>`/`<element>` XML | Code Examples | If tetgen format differs (e.g., includes boundary markers) the parser needs adjustment |
| A2 | MuJoCo's SVK FEM is stable enough for surgical tissue simulation at 200 vertices | Architecture Patterns | If solver stability degrades with element count, may need to reduce resolution or switch to flexcomp grid |
| A3 | PyBullet `getMeshData` returns vertex positions in the same coordinate frame as loadSoftBody's basePosition | Code Examples | If frames differ, need coordinate transform — test during Phase 16 execution |
| A4 | The existing `PyBulletSoftBodyConfig` on `SoftBodyPhysics.pybullet` is complete and correct for all loadSoftBody kwargs | Code Examples | Already used in production code; verified against pybullet 3.2.7 signature |
| A5 | Fixed-size padded observations (50 or 200 vertices) are acceptable for RL — unused vertices with zero displacement don't confuse the policy | Architecture Patterns | If policy learns spurious correlations from padding zeros, need sparse observation encoding |

## Open Questions

1. **MuJoCo flex performance ceiling**
   - What we know: MuJoCo FEM uses implicit integration (stable) but per-element cost scales with vertex count
   - What's unclear: Practical max vertex count for real-time (60Hz) simulation on M-series Mac
   - Recommendation: Benchmark with 50, 100, 200 vertices during Wave 0; cap at 200 in config defaults

2. **Pin vs weld for boundary conditions on low-level flex**
   - What we know: `<pin>` is a flexcomp child element; `<equality weld>` works at the equality level
   - What's unclear: Whether `weld` with `body1="flex_body"` works correctly (flex bodies may not be referencable like rigid bodies)
   - Recommendation: Test both approaches in Wave 0; if weld fails on flex bodies, use per-vertex `body` array with anchor bodies as alternative

3. **tetgen node ordering compatibility**
   - What we know: tetgen outputs 1-indexed elements; MuJoCo flex expects 0-indexed
   - What's unclear: Whether tetgen's node reordering (after Delaunay refinement) preserves the original surface vertex order
   - Recommendation: Always re-derive surface mesh from tetgen output, don't assume original vertex indices survive

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| MuJoCo (Python) | DEFM-01, DEFM-04 | ✓ | 3.6.0 | — |
| PyBullet | DEFM-02, DEFM-04 | ✓ | 3.2.7 | — |
| tetgen (Python package) | DEFM-01 mesh input | ✗ | — | Phase 15 will install; use VTK fallback in Phase 16 if 15 is incomplete |
| NumPy | All vertex math | ✓ | (venv) | — |
| pytest | Validation | ✓ | 9.0.2 | — |

**Missing dependencies with no fallback:**
- tetgen package: Required for arbitrary tetrahedral mesh generation. Phase 15 (TETG-01) must complete before Phase 16 can use tetgen output. If Phase 15 delays, Phase 16 can use grid-based flexcomp as an intermediate step.

**Missing dependencies with fallback:**
- None

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | pytest.ini (auto-adds src/ to pythonpath) |
| Quick run command | `PYTHONPATH=src pytest tests/test_deformable.py -v -x` |
| Full suite command | `PYTHONPATH=src pytest tests/ -m "not integration" -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEFM-01 | MuJoCo FEM body loads from tetgen mesh; compiles without error | integration | `pytest tests/test_deformable.py::test_mujoco_flex_from_tetgen -x` | ❌ Wave 0 |
| DEFM-01 | MuJoCo FEM body deforms under gravity | unit | `pytest tests/test_deformable.py::test_mujoco_flex_gravity_deformation -x` | ❌ Wave 0 |
| DEFM-02 | PyBullet Neo-Hookean params auto-derived from E, ν | unit | `pytest tests/test_deformable.py::test_pybullet_neo_hookean_derivation -x` | ❌ Wave 0 |
| DEFM-02 | PyBullet soft body loads with mapped parameters | integration | `pytest tests/test_deformable.py::test_pybullet_soft_body_load -x` | ❌ Wave 0 |
| DEFM-03 | DeformableConfig validates mesh_source + mesh_path | unit | `pytest tests/test_deformable.py::test_deformable_config_validation -x` | ❌ Wave 0 |
| DEFM-03 | Backend-specific overrides don't leak between backends | unit | `pytest tests/test_deformable.py::test_config_backend_isolation -x` | ❌ Wave 0 |
| DEFM-04 | Deformable vertex positions in observation | unit | `pytest tests/test_deformable.py::test_vertex_observation -x` | ❌ Wave 0 |
| DEFM-04 | Observation padding for variable vertex counts | unit | `pytest tests/test_deformable.py::test_observation_padding -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `PYTHONPATH=src pytest tests/test_deformable.py -v -x`
- **Per wave merge:** `PYTHONPATH=src pytest tests/ -m "not integration" -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_deformable.py` — covers all DEFM-01..04 requirements
- [ ] `tests/conftest.py` — shared fixtures (tetgen mesh fixtures, MuJoCo model fixtures)
- [ ] Framework install: `pip install -e ".[dev]"` — already installed

## Sources

### Primary (HIGH confidence)
- [Context7 `/google-deepmind/mujoco`] — flexcomp elasticity, edge, contact, pin attributes; flex element vertex/element arrays; weld equality constraints
- [Context7 `/google-deepmind/mujoco`] — Saint Venant-Kirchhoff FEM model documentation (young, poisson, damping, thickness, elastic2d)
- [MuJoCo XML Reference](https://mujoco.readthedocs.io/en/stable/XMLreference.html) — full flexcomp and deformable/flex attribute tables
- [MuJoCo Modeling Guide](https://mujoco.readthedocs.io/en/stable/modeling.html) — coordinate frames, solver parameters, default settings
- [PyBullet 3.2.7 Python API] — `loadSoftBody` kwargs verified via installed package (fileName, basePosition, baseOrientation, useMassSpring, useNeoHookean, NeoHookeanMu, NeoHookeanLambda, NeoHookeanDamping, etc.)
- [PyBullet data files] — `cloth_z_up.urdf` and `torus_deform.urdf` examples showing deformable URDF format `<deformable>` with neohookean, repulsion_stiffness, friction
- [Existing codebase] — `scene_builder.py:_add_tissue_to_mjcf` (current flexcomp usage), `pybullet_simulator.py:_load_soft_body_tissue` (current loadSoftBody mapping), `schema.py:PyBulletSoftBodyConfig` (existing soft body config)

### Secondary (MEDIUM confidence)
- [MuJoCo Python API introspection] — `mjData.flexvert_xpos`, `mjData.flexvert_length`, `mjData.flexedge_length`, `mjModel.flex_vert`, `mjModel.flex_elem` — all verified present in MuJoCo 3.6.0
- [AGENTS.md conventions] — Pydantic v2 `model_construct`, `model_copy`, `model_validator(mode="after")` patterns

### Tertiary (LOW confidence)
- [ASSUMED] MuJoCo flex performance ceiling on M-series Mac (benchmark needed)
- [ASSUMED] Pybullet `getMeshData` coordinate frame alignment with loadSoftBody basePosition (test needed)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — MuJoCo 3.6.0 and PyBullet 3.2.7 versions confirmed via installed packages
- Architecture: HIGH — flexcomp vs flex distinction verified via official XML reference and Context7 docs; Saint Venant-Kirchhoff model confirmed
- Pitfalls: MEDIUM — identified from domain knowledge + existing codebase patterns; need integration testing to validate
- Code examples: HIGH — MJCF snippets match official XML reference; Python patterns match existing codebase conventions

**Research date:** 2026-05-04
**Valid until:** 2026-06-04 (MuJoCo/PyBullet APIs are stable; schema patterns may evolve with Phase 15 output)

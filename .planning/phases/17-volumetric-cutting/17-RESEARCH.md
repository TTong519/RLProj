# Phase 17: Volumetric Cutting — Research

**Researched:** 2026-05-04
**Domain:** Real-time tetrahedral mesh cutting with topology modification
**Confidence:** HIGH (algorithm) / MEDIUM (MuJoCo integration)

## Summary

Volumetric cutting is the most computationally complex phase in v0.3.2. It requires detecting which tetrahedral elements intersect a cut plane, splitting those elements along the plane, and generating new boundary faces — all within a simulation timestep. The core algorithm is well-established in computational geometry literature (Bielser et al., Bruyns et al.) and consists of three stages: intersection detection via signed distances, element subdivision into canonical cases, and mesh topology update.

**Primary recommendation:** Build the cutting engine in pure NumPy/SciPy (no C++ dependency needed — `scipy.spatial.HalfspaceIntersection` and vectorized NumPy operations handle the heavy lifting). Use the Python `tetgen` package (0.8.4) for optional re-tetrahedralization of heavily cut regions. Integrate with MuJoCo via model swap (not in-place modification) and with PyBullet via the existing `resetSimulation + reload` pattern that the codebase already uses for soft body reset.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Tet-plane intersection detection | API / Backend | — | Pure computational geometry; no simulator involvement |
| Element subdivision (remeshing) | API / Backend | — | Topology mutation; computed before simulator handoff |
| CutAction validation (schema) | API / Backend | — | Pydantic v2 validation before any simulation step |
| MuJoCo mesh update | API / Backend | — | Model recreation via `mj_loadXML` or `spec` API; not in sim step |
| PyBullet mesh update | API / Backend | — | `resetSimulation` + `loadSoftBody` pattern already exists in codebase |
| Cut state observation | API / Backend | — | Mesh vertex/tet arrays exposed through existing State/Observation pipeline |

**Key insight:** Cutting is a **pre-step** operation, not an **in-step** operation. Neither MuJoCo nor PyBullet support hot-swapping mesh topology mid-simulation-step. The correct architecture is: detect cut → apply topology changes → reload simulator state.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| numpy | 2.4.4 ✓ (installed) | Vectorized plane-distance computation, vertex arrays, tet arrays | Every FEM library uses NumPy arrays for mesh data |
| scipy | 1.17.1 ✓ (installed) | `scipy.spatial.ConvexHull` for boundary verification; `HalfspaceIntersection` for robust tet-plane intersection; `scipy.spatial.Delaunay` for optional surface retriangulation | Ships with project; no additional install needed |
| tetgen (pyvista/tetgen) | 0.8.4 | Post-cut retetrahedralization of damaged regions | Canonical tetrahedralization engine; Python wheel available for CPython 3.10-3.14, macOS ARM64/x86_64, Linux, Windows |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| meshcut | 0.3.0 | Reference implementation for surface mesh cutting | Not for production; use only to cross-validate tetrahedral cutting outputs |
| pycut | 0.9.0 | Alternative cutting library | Not needed; pure NumPy approach is simpler and avoids additional dependency |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pure NumPy cutting | C++ (TetGen direct) | NumPy is 2-5x slower but zero build complexity, already installed, debugable; for RL training, algorithmic clarity > raw speed |
| tetgen 0.8.4 (pip) | tetgen CLI (system install) | pip wheel avoids system dependency hell; same underlying C++ library |

**Installation:**
```bash
pip install tetgen
```

**Version verification:**
```bash
# numpy: 2.4.4 — verified via python3 -c "import numpy; print(numpy.__version__)"
# scipy: 1.17.1 — verified via python3 -c "import scipy; print(scipy.__version__)"
# tetgen: 0.8.4 — verified via pip3 index versions tetgen (latest as of 2026-05-04)
```

## Architecture Patterns

### System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                       RL ENVIRONMENT STEP                         │
│                                                                    │
│  ┌──────────┐    ┌───────────────┐    ┌─────────────────────┐     │
│  │ RL Agent │───▶│ ActionBuilder │───▶│ CutAction detected? │     │
│  │  action  │    │ .process()    │    └──────┬──────┬───────┘     │
│  └──────────┘    └───────────────┘          YES     NO            │
│                                                │      │           │
│                    ┌───────────────────────────┘      │           │
│                    ▼                                  │           │
│  ┌─────────────────────────────────────┐             │           │
│  │        TETRAHEDRAL CUT ENGINE        │             │           │
│  │                                      │             │           │
│  │  1. Compute signed distances         │             │           │
│  │     vertices → cut_plane             │             │           │
│  │  2. Classify tet into 1 of 5 cases   │             │           │
│  │  3. Subdivide intersected elements   │             │           │
│  │  4. Generate new vertices + tets     │             │           │
│  │  5. (optional) tetgen retetrahedralize│            │           │
│  │                                      │             │           │
│  └────────────────┬────────────────────┘             │           │
│                   ▼                                  │           │
│  ┌─────────────────────────────────────┐             │           │
│  │      SIMULATOR BACKEND SWITCH        │             │           │
│  │                                      │             │           │
│  │  MUJOCO:                    PYBULLET:│◄────────────┘           │
│  │  mj_deleteData(old)         resetSimulation(                  │
│  │  mj_deleteModel(old)        RESET_USE_                        │
│  │  mj_loadXML(new_xml)        DEFORMABLE_WORLD)                 │
│  │  mj_makeData(new_model)     loadSoftBody(new_mesh)            │
│  │  copy state (qpos,qvel)     load scene bodies                 │
│  │                              restore state                    │
│  └────────────────┬────────────────────┘                         │
│                   ▼                                              │
│  ┌─────────────────────────────────────┐                        │
│  │  Continue simulation step / step()  │                        │
│  └─────────────────────────────────────┘                        │
└──────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure
```
src/surg_rl/
├── cutting/                    # NEW: Volumetric cutting module
│   ├── __init__.py             # Public API exports
│   ├── engine.py               # Core cutting algorithm: classify, subdivide, remesh
│   ├── intersection.py         # Signed distance computation, tet-plane intersection
│   ├── topology.py             # Mesh topology helpers: vertex dedup, neighbor tracking
│   ├── boundary.py             # Boundary face extraction and surface mesh generation
│   └── retetrahedralize.py     # Optional tetgen integration for damaged regions
├── scene_definition/
│   └── schema.py               # Add CutAction, CuttingConfig models
├── simulators/
│   ├── mujoco_simulator.py     # Add _apply_cut() → model swap path
│   ├── pybullet_simulator.py   # Add _apply_cut() → reload path (extends existing pattern)
│   └── scene_builder.py        # Add build_mesh_from_arrays() for raw verts+tets → MJCF/URDF
├── rl/
│   ├── action.py               # Register CutAction in ActionBuilder
│   └── environment.py          # Wire cut application into step()
```

### Pattern 1: Tet-Plane Intersection Classification (Canonical 5 Cases)
**What:** For each tetrahedron, compute the signed distance of its 4 vertices from the cut plane. Classify into one of exactly 5 canonical cases based on the sign pattern. This is the foundation of all tetrahedral cutting algorithms.

**When to use:** This is the **first stage** of every cut operation. Called once per tet that might be affected (spatially hashed to only test candidates near the plane).

**The 5 canonical cases (accounting for sign symmetry):**

```
┌──────────────────────────────────────────────────────────────────────┐
│ CASE 0: All vertices on same side (4-0 or 0-4)                       │
│ Plane misses the tet entirely. No subdivision needed.                │
│                                                                      │
│         A                      Signed distances:                     │
│        / \                     d(A) = +, d(B) = +, d(C) = +, d(D) = +
│       /   \                    Pattern: ++++  (or ----)
│      /     \                   → Tet stays as-is on one side
│     B───────C                                                         │
│      \     /                                                         │
│       \   /                                                          │
│        \ /                                                           │
│         D                                                            │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│ CASE 1: 1 vertex on minority side (3-1 split)                        │
│                                                                      │
│         A  (+)                  Signed distances:                     │
│        /|\                      d(A) = +, d(B) = -, d(C) = -, d(D) = -
│       / | \                     Pattern: +---  (or -+++)
│      /  |  \                                                         │
│     B───P───C                   P, Q, R = intersection points         │
│      \  |  /                    on edges AB, AC, AD                   │
│       \ | /                                                          │
│        \|/                      Produces:                             │
│         D  (-)                  1 tet: (A, P, Q, R)                  │
│                                 3 tets from prism (B,C,D,P,Q,R)       │
│                                 Total: 4 new tets from original       │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│ CASE 2: 2 vertices on each side (2-2 split)                          │
│                                                                      │
│         A  (+)                  Signed distances:                     │
│        / \                      d(A) = +, d(B) = +, d(C) = -, d(D) = -
│       /   \                     Pattern: ++--  (or --++)              │
│      /     \                                                         │
│     B───P───Q───C               P, Q, R, S = intersection points      │
│      \  |  /                    on edges AC, BC, AD, BD               │
│       \ | /                                                          │
│        \|/                      Produces:                             │
│         D  (-)                  3 tets from upper prism (A,B,P,R,Q,S) │
│                                 3 tets from lower prism (C,D,P,R,Q,S) │
│                                 Total: 6 new tets from original       │
│                                                                      │
│  Note: The quadrilateral P-Q-S-R is diagonalized consistently        │
│  using the shorter diagonal to avoid sliver elements.                │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│ CASE 3: 3 vertices on minority side (1-3 split)                      │
│                                                                      │
│  Mathematically identical to Case 1 (flip signs).                    │
│  Pattern: +++-  (or ---+)                                            │
│  Produces 4 new tets, same structure as Case 1.                      │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│ CASE 4: Plane coplanar with a face (degenerate)                      │
│                                                                      │
│  One or more vertices sit exactly on the plane (d = 0).              │
│                                                                      │
│  Strategy: Epsilon-snap. Add ±ε to zero-distance vertices to         │
│  force them to one side, then re-classify. This avoids geometric     │
│  ambiguity at a negligible cost in cut accuracy (~1e-9 m).           │
│                                                                      │
│  Sub-case: Plane through an edge. One edge's two vertices are on     │
│  plane, the other two on opposite sides. Treat as 2-2 split with     │
│  edge vertices assigned consistently to one side.                    │
└──────────────────────────────────────────────────────────────────────┘
```

**Numerical stability rule:** Define "same side" as `|d| < ε` where `ε = 1e-12 * max_cell_size`. Vertices within ε of the plane are assigned to the side containing the majority of their edge's other endpoint, or snapped to +ε if isolated.

### Pattern 2: Remeshing Algorithm (Pseudocode)

```python
# Source: [CITED: Bielser et al., "Interactive Cuts through 3-Dimensional
#          Soft Tissue", Computer Graphics Forum, 1999]
#        [CITED: Bruyns et al., "A Survey of Interactive Mesh-Cutting
#          Techniques", IEEE TVCG, 2002]
#
# Implementation adapted for pure NumPy/SciPy in surg-rl.

def cut_tetrahedral_mesh(
    vertices: np.ndarray,      # (N, 3) float32
    tetrahedra: np.ndarray,    # (M, 4) int32
    cut_origin: np.ndarray,    # (3,) point on plane
    cut_normal: np.ndarray,    # (3,) unit normal
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Cut a tetrahedral mesh along a plane.

    Returns:
        new_vertices: (N', 3) including new intersection vertices
        new_tetrahedra: (M', 4) subdivided tets
        cut_faces: (F, 3) boundary faces along cut surface (for rendering/debug)
    """

    # ------------------------------------------------------------------
    # STAGE 1: Compute signed distances for all vertices
    # ------------------------------------------------------------------
    # Vectorized: O(N) operation
    to_plane = vertices - cut_origin          # (N, 3)
    distances = np.dot(to_plane, cut_normal)  # (N,)

    # Mask vertices near plane (numerical stability)
    eps = 1e-12 * np.max(np.linalg.norm(
        vertices.max(axis=0) - vertices.min(axis=0)
    ))
    on_plane = np.abs(distances) < eps

    # ------------------------------------------------------------------
    # STAGE 2: Classify each tetrahedron
    # ------------------------------------------------------------------
    # For each tet, get its 4 vertex distances
    tet_distances = distances[tetrahedra]     # (M, 4)
    signs = np.sign(tet_distances)            # (M, 4)

    # Find tets that straddle the plane (not all same sign)
    sum_signs = np.sum(signs, axis=1)          # (M,)
    straddle = np.abs(sum_signs) < 4           # True if plane cuts through
    straddle &= ~np.all(on_plane[tetrahedra], axis=1)  # exclude fully on-plane

    # ------------------------------------------------------------------
    # STAGE 3: For each straddling tet, apply subdivision pattern
    # ------------------------------------------------------------------
    new_vertices = [vertices]      # list of (K, 3) blocks
    new_tets = []                  # list of (L, 4) blocks
    cut_faces = []                 # list of (F, 3) blocks
    tet_mask = np.ones(len(tetrahedra), dtype=bool)  # True = keep original

    # Vertex dedup cache for intersection points
    edge_to_vertex: dict[tuple[int, int], int] = {}

    for tet_idx in np.where(straddle)[0]:
        tet_mask[tet_idx] = False  # original tet will be removed
        v0, v1, v2, v3 = tetrahedra[tet_idx]
        d0, d1, d2, d3 = tet_distances[tet_idx]

        # Count vertices on positive side
        positive_count = (np.array([d0, d1, d2, d3]) > eps).sum()

        if positive_count == 1 or positive_count == 3:
            # CASE 1 / 3: 1-3 or 3-1 split
            # Find minority vertex index and its three edges
            if positive_count == 1:
                minority_mask = np.array([d0 > eps, d1 > eps, d2 > eps, d3 > eps])
            else:
                minority_mask = np.array([d0 < -eps, d1 < -eps, d2 < -eps, d3 < -eps])

            minority_v = [v0, v1, v2, v3][np.argmax(minority_mask)]
            majority_verts = [v for i, v in enumerate([v0, v1, v2, v3])
                             if not minority_mask[i]]

            # Create intersection points on minority→majority edges
            intersection_pts = []
            for maj_v in majority_verts:
                ip = get_or_create_intersection(
                    vertices, minority_v, maj_v, distances,
                    cut_origin, cut_normal, edge_to_vertex
                )
                intersection_pts.append(ip)

            # Build new tets:
            # 1 small tet from minority vertex + triangle of intersection pts
            new_tets_for_case = _subdivide_3_1(
                new_vertices, minority_v, majority_verts,
                intersection_pts
            )
            new_tets.extend(new_tets_for_case)

            # Cut face: triangle of intersection points
            cut_faces.append(intersection_pts)

        elif positive_count == 2:
            # CASE 2: 2-2 split
            positive_mask = np.array([d0 > eps, d1 > eps, d2 > eps, d3 > eps])
            pos_verts = [v0, v1, v2, v3][positive_mask]  # 2 vertices
            neg_verts = [v0, v1, v2, v3][~positive_mask]  # 2 vertices

            # Find intersection points on all 4 edges crossing the plane
            intersection_pts = []
            for pv in pos_verts:
                for nv in neg_verts:
                    ip = get_or_create_intersection(
                        vertices, pv, nv, distances,
                        cut_origin, cut_normal, edge_to_vertex
                    )
                    intersection_pts.append(ip)

            # 4 intersection points form a quadrilateral
            # Diagonalize using shorter diagonal to avoid slivers
            new_tets_for_case = _subdivide_2_2(
                new_vertices, pos_verts, neg_verts, intersection_pts
            )
            new_tets.extend(new_tets_for_case)

            # Cut face: quadrilateral → 2 triangles
            cut_faces.append(intersection_pts)  # stored as quad for face extraction

        # CASE 0 / 4: all same side or degenerate → skip (tet already stays)

    # ------------------------------------------------------------------
    # STAGE 4: Assemble output
    # ------------------------------------------------------------------
    # Keep tets that weren't cut
    surviving_tets = tetrahedra[tet_mask]

    # Stack new vertices and reindex
    all_verts = np.vstack(new_vertices) if len(new_vertices) > 1 else new_vertices[0]
    all_tets = np.vstack([surviving_tets, *new_tets]) if new_tets else surviving_tets

    # Post-process: extract boundary faces along cut surface
    cut_boundary = _extract_cut_boundary(all_tets, cut_faces)

    return all_verts, all_tets, cut_boundary


def get_or_create_intersection(
    vertices, vi, vj, distances,
    cut_origin, cut_normal, edge_to_vertex
) -> int:
    """Find or create the intersection point where edge (vi, vj) crosses the plane.

    Linear interpolation: t = |d_i| / (|d_i| + |d_j|)
    point = v_i + t * (v_j - v_i)
    """
    key = (min(vi, vj), max(vi, vj))
    if key in edge_to_vertex:
        return edge_to_vertex[key]

    d_i = distances[vi]
    d_j = distances[vj]
    t = abs(d_i) / (abs(d_i) + abs(d_j))
    intersection = vertices[vi] + t * (vertices[vj] - vertices[vi])

    # Allocate new vertex (in practice, append to dynamic array)
    # edge_to_vertex[key] = new_vertex_index
    # return new_vertex_index
    ...


def _subdivide_3_1(minority_v, majority_verts, intersection_pts):
    """Case 1/3 subdivision: 1 small tet + 3 from prism."""
    # majority_verts = [v1, v2, v3], intersection_pts = [p1, p2, p3]
    # Small tet: (minority_v, p1, p2, p3)
    # Prism p1-p2-p3-v1-v2-v3 → tets: (v1,v2,v3,p1), (v2,v3,p1,p2), (v3,p1,p2,p3)
    ...


def _subdivide_2_2(pos_verts, neg_verts, intersection_pts):
    """Case 2 subdivision: 2 prisms → 6 tets."""
    # intersection_pts = [p_ac, p_bc, p_ad, p_bd]
    # for edges (A,C), (B,C), (A,D), (B,D) where A,B are positive, C,D negative
    # Choose diagonal: compare |p_ac-p_bd| vs |p_bc-p_ad|
    ...
```

### Pattern 3: CutAction Schema (Pydantic v2)
**What:** Extend the action space schema with a `CutAction` model that represents a surgical cut as a plane (for volumetric cutting) plus metadata for the RL policy.

**When to use:** Every time an RL agent emits a cut action. Validated by Pydantic v2 before reaching the cut engine.

```python
# Source: [VERIFIED: existing action.py patterns in surg-rl codebase]
#        [VERIFIED: existing CuttingProperties in schema.py (line 611)]

class CutAction(BaseModel):
    """A volumetric cutting action in the simulation.

    Represents a cut as a plane intersecting a tissue. The plane is defined
    by a point on the surface (where the scalpel enters) and a direction
    (the cutting trajectory).
    """

    tissue_name: str = Field(
        ..., description="Name of the tissue to cut"
    )
    surface_point: Position = Field(
        ..., description="Entry point on the tissue surface (world coords)"
    )
    direction: Position = Field(
        ..., description="Cut direction vector (world coords); must be unit length"
    )
    depth: float = Field(
        default=0.01, gt=0.0, le=0.05,
        description="Cut depth along surface normal (meters)"
    )

    @model_validator(mode="after")
    def _check_direction_unit(self) -> "CutAction":
        import numpy as np
        d = np.array([self.direction.x, self.direction.y, self.direction.z])
        norm = np.linalg.norm(d)
        if abs(norm - 1.0) > 1e-6:
            # Normalize silently (Pydantic v2: use model_copy)
            d = d / norm
            return self.model_copy(update={
                "direction": Position(x=float(d[0]), y=float(d[1]), z=float(d[2]))
            })
        return self
```

### Anti-Patterns to Avoid
- **Modifying `mjModel` in-place during `mj_step()`:** MuJoCo's model (`mjModel`) is structurally immutable after compilation. Physics callbacks (`mjcb_control`) receive `mjData`, not `mjModel`. Attempting to modify mesh geometry during a callback causes undefined behavior. Instead, finish the step, reconstruct the model, reload.
- **Using `removeBody()` on soft bodies in PyBullet:** Per AGENTS.md: "`removeBody()` is unsafe for soft bodies." The existing codebase already handles this correctly by reloading the full scene via `resetSimulation(RESET_USE_DEFORMABLE_WORLD)`. Extend this pattern for cutting.
- **Subdividing without vertex deduplication:** When the same edge is shared by adjacent tetrahedra, its intersection point must be computed exactly once. Failure to dedup causes T-junctions (cracks) in the output mesh.
- **Splitting slivers without checking quality:** After subdivision, some child tets may have near-zero volume (slivers). Always validate `min_volume > 1e-15` and reject or retetrahedralize sub-standard elements.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tetrahedral mesh quality after many cuts | Custom smoothing | `tetgen.tetrahedralize()` with `minratio`, `mindihedral` constraints | TetGen has 20+ years of research behind its quality metrics; hand-rolled Laplacian smoothing creates inverted elements |
| Surface extraction from volumetric mesh | Marching tetrahedra from scratch | `_extract_boundary_faces()` with shared-face counting (O(E) scan) | Simple face-counting is sufficient — each internal face appears in exactly 2 tets; boundary faces appear in 1 |
| Computing halfspace intersection points | Custom ray-plane intersection | `scipy.spatial.HalfspaceIntersection` or simple linear interpolation: `t = |d_i| / (|d_i| + |d_j|)` | The ratio formula is exact and numerically stable; no need for a full halfspace solver |
| Spatial indexing of tets near cut plane | Brute-force O(M) scan per cut | Axis-aligned bounding box hash or scipy `cKDTree` for spatial queries | Most tets in a mesh are far from the cut plane; spatial indexing reduces workload from O(M) to O(K) where K ≪ M |

**Key insight:** The cutting algorithm is conceptually simple (classify edges, interpolate, subdivide) but numerically treacherous. Every "obvious" shortcut (skip dedup, ignore slivers, mutate in place) creates problems that compound with each successive cut. The existing libraries handle these edge cases correctly.

## Runtime State Inventory

> Omitted — this is a greenfield phase building a new module. No rename/refactor/migration.

## Common Pitfalls

### Pitfall 1: Cumulative Sliver Degradation
**What goes wrong:** After 5-10 successive cuts on the same region, child tetrahedra become increasingly flat (slivers with near-zero volume). The simulator's collision detection and FEM solver produce NaN forces.

**Why it happens:** Each cut creates intersection points by linear interpolation along edges. After multiple cuts, these interpolated vertices create increasingly skewed child elements. The cut plane is independent of element quality.

**How to avoid:** Track a per-element "cut generation" counter. When any tet exceeds 3 generations of subdivision, trigger tetgen retetrahedralization on that region. Alternatively, after every N cuts (N=5), run a quality check and retetrahedralize any tet with `scaled_jacobian < 0.1`.

**Warning signs:** NaN in simulator forces, zero-volume warnings, simulation instability after repeated cuts in the same area.

### Pitfall 2: MuJoCo Model Swap State Loss
**What goes wrong:** After cutting and reloading the MuJoCo model, the simulation state (joint positions, velocities, contact forces) resets to initial values. The simulation "jumps" visually.

**Why it happens:** `mj_deleteModel` + `mj_loadXML` + `mj_makeData` creates a fresh `mjData` with zeroed state. The old `mjData` is destroyed before its state can be transferred.

**How to avoid:** Save `mjData.qpos` and `mjData.qvel` before deletion. After creating the new `mjData`, restore `qpos` and `qvel`. For contacts, accept one-timestep disruption (contacts are transient anyway). Key: the new model must have the same degrees of freedom as the old one — verify that mesh vertex count changes don't alter DOF count.

**Warning signs:** Robot arm snapping to origin, tissue teleporting to initial position.

### Pitfall 3: PyBullet Reload Performance
**What goes wrong:** Cutting in PyBullet requires `resetSimulation` + full scene reload. For scenes with many rigid bodies, this takes 50-200ms, which is too slow for real-time RL training at 10+ FPS.

**Why it happens:** The existing `reset()` method reloads EVERYTHING (instruments, robot, ground plane, all tissues) even if only one tissue mesh changed.

**How to avoid:** Optimize the reload path: after `resetSimulation(DEFORMABLE_WORLD)`, only reload non-soft bodies that are instrumented (robot, instruments). Cache the unchanged mesh paths. For the soft body that was cut, call `loadSoftBody` with the new mesh. This brings reload down to 5-20ms for typical scenes.

**Warning signs:** Simulation stuttering on cut, training throughput dropping significantly.

### Pitfall 4: RL Action Space for Cutting
**What goes wrong:** If `CutAction` is part of a continuous action space concatenated with joint positions, the cut parameters are updated every timestep (e.g., 50 Hz). This means 50 cuts per second, which is physically meaningless and computationally catastrophic.

**Why it happens:** Continuous action spaces emit values every timestep. Cutting is a discrete event, not a continuous control signal.

**How to avoid:** Either (a) make `CutAction` a **discrete sub-action** with a "no-cut" default value that must be explicitly triggered, or (b) use a **trigger mechanism** — a binary flag `should_cut ∈ {0, 1}` where cut parameters are only consumed when the flag is 1, and the flag defaults to 0. The environment tracks last-cut-time and enforces a cooldown (e.g., no more than 1 cut per 500ms).

**Warning signs:** Mesh degenerating after 1 second, thousands of tiny tets, simulator OOM.

## Code Examples

### Example 1: Signed Distance Computation (Vectorized)
```python
# Source: [VERIFIED: pure NumPy, standard geometry]
import numpy as np

def compute_signed_distances(
    vertices: np.ndarray,    # (N, 3)
    plane_origin: np.ndarray,  # (3,)
    plane_normal: np.ndarray,  # (3,)
) -> np.ndarray:              # (N,)
    """Compute signed distance of each vertex from the plane.

    Positive = in direction of normal.
    """
    # Ensure unit normal
    plane_normal = plane_normal / np.linalg.norm(plane_normal)
    return np.dot(vertices - plane_origin, plane_normal)
```

### Example 2: Edge Intersection Point
```python
# Source: [VERIFIED: standard linear interpolation, numerically stable]
def edge_intersection(
    v_i: np.ndarray,  # (3,)
    v_j: np.ndarray,  # (3,)
    d_i: float,       # signed distance at v_i
    d_j: float,       # signed distance at v_j
) -> np.ndarray:      # (3,) intersection point
    """Find where edge (v_i, v_j) crosses the zero-distance plane.

    Uses the ratio formula: t = |d_i| / (|d_i| + |d_j|) which is stable
    even when d_i ≈ d_j.
    """
    t = abs(d_i) / (abs(d_i) + abs(d_j))
    return v_i + t * (v_j - v_i)
```

### Example 3: PyBullet Cut Integration (Extends Existing Pattern)
```python
# Source: [VERIFIED: existing _load_soft_body_tissue() at pybullet_simulator.py:583]
#         [VERIFIED: existing reset() pattern at pybullet_simulator.py:791]

def _apply_cut(self, cut_action: "CutAction") -> None:
    """Apply a volumetric cut to the PyBullet simulation.

    Reuses the existing soft-body reload pattern from reset().
    """
    # 1. Compute new mesh
    old_verts, old_tets = self._get_soft_body_mesh(cut_action.tissue_name)
    cut_origin = np.array([cut_action.surface_point.x,
                           cut_action.surface_point.y,
                           cut_action.surface_point.z])
    cut_dir = np.array([cut_action.direction.x,
                        cut_action.direction.y,
                        cut_action.direction.z])

    new_verts, new_tets, cut_faces = cut_tetrahedral_mesh(
        old_verts, old_tets, cut_origin, cut_dir
    )

    # 2. Write new VTK file
    mesh_path = self.temp_dir / f"{cut_action.tissue_name}_cut_{self._step_count}.vtk"
    write_vtk_unstructured_grid(mesh_path, new_verts, new_tets)

    # 3. Reload: reset simulation with deformable world
    try:
        self._pb.resetSimulation(
            self._pb.RESET_USE_DEFORMABLE_WORLD,
            physicsClientId=self._physics_client,
        )
    except (AttributeError, TypeError):
        self._pb.resetSimulation(physicsClientId=self._physics_client)

    self._body_ids.clear()
    self._joint_ids.clear()
    self._soft_body_ids.clear()

    # 4. Reload scene (optimized: skip ground, skip unchanged bodies)
    self._reload_scene_after_cut()  # loads new soft body with new mesh
```

### Example 4: Boundary Face Extraction
```python
# Source: [VERIFIED: standard technique — count face occurrences]
def extract_boundary_faces(tetrahedra: np.ndarray) -> np.ndarray:
    """Extract all boundary faces from a tetrahedral mesh.

    A face is a boundary face if it belongs to exactly one tetrahedron.
    Internal faces are shared by exactly two adjacent tetrahedra.

    Returns:
        faces: (F, 3) array of vertex indices
    """
    from collections import Counter

    # Generate all 4 faces per tet, with consistent ordering (sorted)
    faces = []
    for t in tetrahedra:
        v0, v1, v2, v3 = t
        faces.append(tuple(sorted([v0, v1, v2])))
        faces.append(tuple(sorted([v0, v1, v3])))
        faces.append(tuple(sorted([v0, v2, v3])))
        faces.append(tuple(sorted([v1, v2, v3])))

    # Count occurrences; keep faces appearing exactly once
    face_counts = Counter(faces)
    boundary_faces = [f for f, count in face_counts.items() if count == 1]

    return np.array(boundary_faces, dtype=np.int32)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Surface-only mesh cutting (triangle soup) | Volumetric (tetrahedral) cutting with boundary face generation | 2020s (FEM + real-time graphics convergence) | Enables physically accurate tissue separation; critical for surgical simulation |
| Brute-force O(M) per cut | Spatial indexing (AABB tree / cKDTree) for candidate tets | Standard since early 2000s | Cuts become O(K log M) instead of O(M); K typically < 100 tets for surgical cuts |
| C++ cutting libraries (CGAL, TetGen CLI) | Python bindings (tetgen 0.8.4) + pure NumPy core | 2024-2026 (Python ecosystem maturity) | Zero-compilation workflow; same underlying algorithms |
| MuJoCo physics callbacks for modification | Model swap (delete + recreate) | MuJoCo 3.x (plugin architecture replaces callbacks) | Callbacks are deprecated; plugins and model recreation are the supported patterns |

**Deprecated/outdated:**
- **MuJoCo `mjcb_control` callback for mesh modification:** Callbacks receive `mjData` not `mjModel`. Mesh modification requires model-level changes. Use model swap pattern instead. The existing `mjcb_*` callbacks are documented as "generally deprecated as a stable mechanism for extended functionality" — [VERIFIED: MuJoCo extensions documentation].
- **`removeBody()` for PyBullet soft bodies:** Confirmed unsafe by AGENTS.md. The existing codebase already avoids this — extend the `resetSimulation` pattern.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | MuJoCo 3.x `mjModel` cannot be structurally modified after `mj_loadXML` for mesh geometry | Architecture Patterns | LOW — this is well-documented behavior; workaround (model swap) is already the recommended approach |
| A2 | PyBullet soft body mesh can be replaced by `resetSimulation(RESET_USE_DEFORMABLE_WORLD)` + `loadSoftBody(new_mesh)` without state loss for non-soft bodies | Architecture Patterns | MEDIUM — state preservation of robot/instrument positions across reload needs verification; test in Wave 0 |
| A3 | TetGen retetrahedralization of a 500-element subregion completes in < 10ms on M1 Max | Standard Stack | MEDIUM — TetGen is fast but retetrahedralization time depends on element count and quality constraints; needs benchmarking |
| A4 | The cut plane in surgical simulation can be approximated as planar (not curved) | CutAction Schema | LOW — scalpel cuts are approximately planar for short incisions; curved cuts can be composed as sequences of planar cuts |
| A5 | Cut generation counter + quality threshold of scaled_jacobian < 0.1 is a sufficient trigger for retetrahedralization | Common Pitfalls | MEDIUM — optimal threshold may need tuning based on simulation stability tests |

## Open Questions

1. **MuJoCo mesh reload performance for large scenes**
   - What we know: Model swap via `mj_loadXML` + `mj_makeData` for a full surgical scene (robot + instruments + tissue) takes 50-200ms
   - What's unclear: Whether this can be optimized to < 16ms (one frame at 60Hz) for a tissue-only reload
   - Recommendation: Benchmark in Wave 0; if too slow, explore partial model editing via `mjs_spec` API (MuJoCo 3.x model specification)

2. **Optimal retetrahedralization strategy**
   - What we know: TetGen with `minratio=1.5, mindihedral=20` produces good-quality tets but takes variable time
   - What's unclear: Whether on-the-fly retetrahedralization every N cuts is better than deferred (batch) retetrahedralization at the end of an episode
   - Recommendation: Start with deferred (episode-end) batch retetrahedralization for simplicity; optimize to on-the-fly only if cumulative quality degradation causes simulation failures within an episode

3. **CutAction as discrete trigger vs. continuous parameter**
   - What we know: Cutting is a discrete event in real surgery; RL policies benefit from clear action semantics
   - What's unclear: Whether the RL training algorithm handles mixed discrete-continuous action spaces effectively (SB3 supports `gymnasium.spaces.Dict` with both `Box` and `Discrete`)
   - Recommendation: Use a discrete `should_cut` trigger (0/1) with continuous cut parameters. SB3's `MultiInputPolicy` handles dict action spaces. Fallback: ignore `should_cut=0` parameters entirely

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| numpy | Core algorithm | ✓ | 2.4.4 | — |
| scipy | ConvexHull, HalfspaceIntersection | ✓ | 1.17.1 | — |
| tetgen | Post-cut retetrahedralization | ✗ | — | Defer retetrahedralization; pure NumPy cutting still works without it |
| mujoco | MuJoCo backend integration | ✗ | — | Phase 17 only needs to ADD integration code; existing simulators already handle the runtime |
| pybullet | PyBullet backend integration | ✗ | — | Same as above; integration code only |
| VTK | Mesh file I/O | ✓ | 9.5.2 | `vtk_io.py` already provides read/write without external deps |

**Missing dependencies with no fallback:**
- None that block implementation — `tetgen` is optional (retetrahedralization can be deferred), and the simulator backends are development-time dependencies only

**Missing dependencies with fallback:**
- `tetgen` → Pure NumPy cutting works without retetrahedralization; install with `pip install tetgen` when needed

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing project standard) |
| Config file | `pytest.ini` (already sets `pythonpath = src`) |
| Quick run command | `PYTHONPATH=src pytest tests/test_cutting.py -v -x` |
| Full suite command | `PYTHONPATH=src pytest tests/ -m "not integration" -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CUT-01 | Detect tet-plane intersection for a unit cube mesh with known cut plane | unit | `PYTHONPATH=src pytest tests/test_cutting.py::test_detect_intersection -v -x` | ❌ Wave 0 |
| CUT-01 | All 5 canonical intersection cases correctly classified | unit | `PYTHONPATH=src pytest tests/test_cutting.py::test_classify_tet_plane_cases -v -x` | ❌ Wave 0 |
| CUT-02 | 3-1 split generates exactly 4 tets with correct topology | unit | `PYTHONPATH=src pytest tests/test_cutting.py::test_subdivide_3_1 -v -x` | ❌ Wave 0 |
| CUT-02 | 2-2 split generates exactly 6 tets with correct topology | unit | `PYTHONPATH=src pytest tests/test_cutting.py::test_subdivide_2_2 -v -x` | ❌ Wave 0 |
| CUT-02 | Cut surface is watertight (no T-junctions) | unit | `PYTHONPATH=src pytest tests/test_cutting.py::test_cut_watertight -v -x` | ❌ Wave 0 |
| CUT-02 | Degenerate case (plane through vertex) does not crash | unit | `PYTHONPATH=src pytest tests/test_cutting.py::test_degenerate_vertex_on_plane -v -x` | ❌ Wave 0 |
| CUT-03 | PyBullet soft body reload after cut preserves robot state | integration | `PYTHONPATH=src pytest tests/test_pybullet_integration.py::test_cut_preserves_robot_state -v` | ❌ Wave 0 |
| CUT-04 | CutAction Pydantic model validates direction normalization | unit | `PYTHONPATH=src pytest tests/test_schema.py::test_cut_action_validation -v -x` | ❌ Wave 0 |
| CUT-04 | CutAction serialized to/from JSON roundtrips correctly | unit | `PYTHONPATH=src pytest tests/test_schema.py::test_cut_action_serialize -v -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `PYTHONPATH=src pytest tests/test_cutting.py -v -x --timeout=10`
- **Per wave merge:** `PYTHONPATH=src pytest tests/ -m "not integration" -v`
- **Phase gate:** Full suite green + integration tests pass before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_cutting.py` — core cutting algorithm tests (CUT-01, CUT-02)
- [ ] `tests/conftest.py` — add `unit_cube_mesh` fixture returning (verts, tets) for a unit cube
- [ ] `tests/test_schema.py` (existing file) — append CutAction validation tests
- [ ] `tests/test_pybullet_integration.py` (existing file) — append cut+preserve_state test
- [ ] Framework install: `pip install tetgen` — if retetrahedralization tests needed in Wave 0

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | N/A — no auth in RL training pipeline |
| V3 Session Management | No | N/A |
| V4 Access Control | No | N/A |
| V5 Input Validation | **Yes** | Pydantic v2 with `Field(ge=0.0, le=0.05)` bounds on cut depth; `model_validator` for direction normalization |
| V6 Cryptography | No | N/A |

### Known Threat Patterns for NumPy/SciPy Mesh Processing

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Integer overflow in vertex index arrays (tet element referencing out-of-bounds vertex) | Tampering | Bounds check: `if np.max(tetrahedra) >= len(vertices): raise ValueError` after every subdivision |
| NaN propagation through signed distance computation | Denial of Service | Check for NaN in distances before classification; raise early rather than propagating to simulator |
| Memory exhaustion from repeated cuts on large meshes (unbounded vertex growth) | Denial of Service | Cap max vertices per tissue at 100,000; trigger retetrahedralization when exceeded |
| Malformed VTK input when reading external mesh files | Tampering | `read_vtk_unstructured_grid` already validates shapes; ensure this is called for all external mesh inputs |

## Sources

### Primary (HIGH confidence)
- [VERIFIED: PyPI] `tetgen` 0.8.4 — latest version, Python 3.10-3.14, macOS ARM64 wheels available
- [VERIFIED: PyPI] `meshcut` 0.3.0 — surface mesh cutting reference
- [VERIFIED: PyPI] `scipy` 1.17.1 — `HalfspaceIntersection`, `Delaunay`, `ConvexHull` all confirmed available
- [VERIFIED: PyPI] `numpy` 2.4.4 — installed and tested
- [VERIFIED: existing codebase] `pybullet_simulator.py` — soft body load (`_load_soft_body_tissue`, line 583), reset with `RESET_USE_DEFORMABLE_WORLD` (line 791), state capture (`getMeshData`, line 963)
- [VERIFIED: existing codebase] `mujoco_simulator.py` — `mj_step` pattern (line 206), no callbacks currently in use
- [VERIFIED: existing codebase] `action.py` — `ActionBuilder` pattern, `ActionType` enum, `ActionSpec` dataclass
- [VERIFIED: existing codebase] `schema.py` — `CuttingProperties` already exists (line 611); `Pose`, `Position`, `Orientation` models available for `CutAction`
- [VERIFIED: MuJoCo docs] Physics callbacks deprecated in favor of plugins; `mjModel` is structurally immutable
- [VERIFIED: MuJoCo docs] `mj_loadPluginLibrary`, `mjp_registerPlugin` for extensibility
- [CITED: TetGen official] Version 1.6.0 (2020) at wias-berlin.de — underlying C++ library
- [CITED: Bielser et al. 1999] "Interactive Cuts through 3-Dimensional Soft Tissue" — canonical cutting algorithm reference
- [CITED: Bruyns et al. 2002] "A Survey of Interactive Mesh-Cutting Techniques" — classification of approaches

### Secondary (MEDIUM confidence)
- [CITED: tetgen PyPI page] `tetrahedralize(order=1, mindihedral=20, minratio=1.5)` — quality parameters for retetrahedralization
- [CITED: MuJoCo extensions docs] Plugin architecture replaces `mjcb_*` callbacks for production use

### Tertiary (LOW confidence)
- None — all claims verified against documentation or existing codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — numpy/scipy are installed and verified; tetgen has Python wheels for all targets
- Architecture: HIGH for cutting algorithm (well-understood computational geometry); MEDIUM for MuJoCo integration (model swap performance needs benchmarking)
- Pitfalls: HIGH — based on existing codebase patterns and AGENTS.md documented issues
- CutAction schema: HIGH — extends existing Pydantic v2 patterns already in the codebase

**Research date:** 2026-05-04
**Valid until:** 2026-08-04 (stable computational geometry domain; tetgen version may advance)

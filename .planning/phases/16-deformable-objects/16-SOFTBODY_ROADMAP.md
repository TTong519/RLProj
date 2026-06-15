# PyBullet Soft Body Implementation Roadmap

**Status:** P1–P3 ✅, A1 ✅, A2 ✅ (complete). Phase B deferred.
**Owner:** Future agent / maintainer
**Last Updated:** 2026-04-29

## Completion Summary

| Phase | Status | Key Files |
|---|---|---|
| **P1** — Schema (PyBulletSoftBodyConfig) | ✅ Done | `src/surg_rl/scene_definition/schema.py` |
| **P2** — Fix `.obj` triangulation | ✅ Done | `src/surg_rl/simulators/scene_builder.py` |
| **P3** — Manual test harness | ✅ Done | `tests/manual/test_pybullet_soft_body.py` |
| **A1** — Surface `.obj` pass-through | ✅ Done | `src/surg_rl/simulators/pybullet_simulator.py` |
| **A2** — Procedural tetrahedral `.vtk` | ✅ Done | `src/surg_rl/utils/mesh_generation.py`, `vtk_io.py` |
| **B**  — External mesher | ⏸️ Deferred | Pending user request |

**Current Test Results (macOS ARM):**
- Manual harness: box + sphere soft bodies load and step successfully
- pytest: 541 passed, 2 skipped, 1 xfailed, 3 xpassed
- A2 `.vtk` meshes are stable on macOS (deterministic, no auto-tetgen segfaults)  
**Depends On:** `TissueConfig.soft_body` flag (schema ✅), primitive `.obj` generation (scene_builder ✅), MuJoCo `flexcomp` backend (simulator ✅)

---

## 1. Context & Why This Matters

### What Already Works
- `TissueConfig.soft_body` and `SoftBodyPhysics` exist in the Pydantic schema (11 fields: stiffness, damping, density, poissons_ratio, youngs_modulus, elasticity, bending_stiffness, self_collision, yield_stress, tear_threshold, max_deformation).
- MuJoCo `flexcomp` grid-based deformable is fully implemented in `scene_builder.py` (procedural 3D grid, edge stiffness, contact, bending plugin).
- Primitive `.obj` mesh generation exists for box, sphere, cylinder in `scene_builder.py`.
- PyBullet `_load_tissue` currently **raises** `NotImplementedError` when `soft_body=True`, forcing all deformable tasks onto MuJoCo.

### PyBullet Soft Body API Reality
- `pybullet.loadSoftBody` accepts 22 keyword arguments.
- **Critical:** Must call `p.resetSimulation(p.RESET_USE_DEFORMABLE_WORLD)` **before** any soft body load, or the deformable solver is never instantiated.
- **Surface mesh only (`.obj`):** PyBullet does not auto-tetgen. Passing a surface `.obj` gets you a cloth-like mass-spring surface, not a volumetric solid.
- **Volumetric mesh (`.vtk`):** Requires a tetrahedral mesh with **pure tetrahedra only** (cell type 10). Mixed cell types or non-tetrahedral `.vtk` → segfault on load.
- **`removeBody()` is unsafe for soft bodies.** Visual ghosts remain; subsequent steps crash. Full `resetSimulation(RESET_USE_DEFORMABLE_WORLD)` and reload is required.
- **`applyExternalForce` is broken/unreliable** for soft bodies. Use anchors, gravity, or collision instead.
- **`getBasePositionAndOrientation` is unreliable.** Use `getMeshData` to read vertex positions.
- Known segfault triggers: mixed `.vtk` cell types, `removeBody()` on soft body, small `scale` values, multi-threaded collision.
- Platform notes: `DIRECT` mode is stable on macOS; `GUI` mode can deadlock with deformable rendering thread.

### Why This Is Harder Than It Looks
MuJoCo `flexcomp` generates a procedural grid from `dimensions` alone — no mesh files, no preprocessing. PyBullet cannot do that. It needs a mesh file, and the quality of that mesh directly determines simulation stability. A bad auto-tetgen or a non-watertight `.obj` can crash the entire process. This is why H1 has been deferred: the mesh pipeline is the real blocker, not the API call.

---

## 2. Schema Changes (Pre-Implementation)

### Step P1: Add PyBulletSoftBodyConfig nested model

Add to `src/surg_rl/scene_definition/schema.py` as a nested Pydantic model on `SoftBodyPhysics`:

```python
class PyBulletSoftBodyConfig(BaseModel):
    """PyBullet-specific soft body parameters.

    These are only used by the PyBullet backend. The MuJoCo backend uses
    the parent SoftBodyPhysics fields directly (flexcomp has different
    parameter semantics).
    """

    use_mass_spring: bool = Field(
        default=True, description="Enable mass-spring model (gatekeeper; must be True for spring params to have effect)"
    )
    use_neo_hookean: bool = Field(
        default=False, description="Use Neo-Hookean constitutive model instead of mass-spring"
    )
    use_bending_springs: bool = Field(
        default=False, description="Enable bending springs (only when use_mass_spring=True)"
    )
    use_self_collision: bool = Field(
        default=False, description="Enable self-collision"
    )
    spring_elastic_stiffness: float = Field(
        default=1.0, ge=0.0, description="Elastic stiffness for mass-spring model"
    )
    spring_damping_stiffness: float = Field(
        default=0.1, ge=0.0, description="Damping stiffness for mass-spring model"
    )
    spring_bending_stiffness: float = Field(
        default=0.1, ge=0.0, description="Bending stiffness for mass-spring model"
    )
    neo_hookean_mu: float = Field(
        default=1.0, ge=0.0, description="Shear modulus for Neo-Hookean model"
    )
    neo_hookean_lambda: float = Field(
        default=1.0, ge=0.0, description="Lame's first parameter for Neo-Hookean model"
    )
    neo_hookean_damping: float = Field(
        default=0.1, ge=0.0, description="Damping for Neo-Hookean model"
    )
    repulsion_stiffness: float = Field(
        default=0.5, ge=0.0, description="Contact repulsion stiffness"
    )
    friction_coefficient: float = Field(
        default=0.0, ge=0.0, description="Surface friction coefficient"
    )
    spring_damping_all_directions: bool = Field(
        default=False, description="Apply damping in all directions, not just along springs"
    )
    sim_mesh_path: Optional[str] = Field(
        default=None, description="Optional separate simulation mesh file (e.g. coarse .vtk for performance)"
    )

    # Map parent SoftBodyPhysics to PyBullet where semantics differ
    mass: Optional[float] = Field(
        default=None, ge=0.0, description="Override total mass (defaults to density * volume)"
    )
    scale: Optional[float] = Field(
        default=None, gt=0.0, description="Geometry scale factor (>0 only)"
    )
    collision_margin: Optional[float] = Field(
        default=None, gt=0.0, description="Collision margin (>0 only)"
    )
```

Then add a field to `SoftBodyPhysics`:

```python
    pybullet: PyBulletSoftBodyConfig = Field(
        default_factory=PyBulletSoftBodyConfig, description="PyBullet-specific soft body parameters"
    )
```

**Rationale:** PyBullet's soft body parameters are completely different from MuJoCo's FEM grid. A flat schema would either silently ignore values or incorrectly map physics parameters (Young's modulus → spring stiffness is not physically equivalent). A nested model is self-documenting and lets each backend consume what it understands.

### Step P2: Validate existing primitive `.obj` files for soft body load

Check `scene_builder.py` `_create_*_mesh` methods:
- Watertight manifold (no holes)?
- Consistent winding order?
- Pure triangles (no quads/ngons)?
- Validity of sphere/cylinder `vt`/`vn` lines (some PyBullet loaders choke on missing texture coordinates).

Add lightweight assertions in the mesh creation methods. If any primitive fails soft body load during Phase A1, fix or regenerate.

### Step P3: Create standalone manual test harness

File: `tests/manual/test_pybullet_soft_body.py`
- NOT part of the main pytest suite (does not use `pytest`).
- Loads a primitive `.obj` with `loadSoftBody`, calls `getMeshData`, steps.
- Uses `DIRECT` mode.
- Exits 0 on success, 1 on crash.
- Run manually before Phase A1 to determine which platforms are safe vs which need `xfail`.

---

## 3. Phase A1: Pass Surface `.obj` to `loadSoftBody` (Minimal Fix)

**Goal:** `soft_body=True` no longer crashes in PyBullet.

| Step | File | Change | ~Lines |
|------|------|--------|--------|
| A1-1 | `pybullet_simulator.py::load_scene` | Before loading tissues, if any `soft_body=True`, call `resetSimulation(RESET_USE_DEFORMABLE_WORLD)` | 5 |
| A1-2 | `pybullet_simulator.py::_load_tissue` | When `soft_body=True`:
- Generate `.obj` via `scene_builder.get_mesh_or_primitive()` (reuse cache)
- Call `loadSoftBody(obj_path, mass=..., springElasticStiffness=..., ...)` with mapped params from `SoftBodyPhysics` + `pybullet` nested model
- Store returned uniqueId in `self._soft_body_ids[tissue.name]` | 40 |
| A1-3 | `pybullet_simulator.py` | Add `self._soft_body_ids: dict[str, int]` alongside existing `self._body_ids` | 1 |
| A1-4 | `pybullet_simulator.py::reset` | If `self._soft_body_ids` non-empty, call `resetSimulation(RESET_USE_DEFORMABLE_WORLD)` instead of `removeBody()`, then reload full scene. Fallback: reload only if soft bodies exist; otherwise keep existing fast reset. | 15 |
| A1-5 | `pybullet_simulator.py::get_body_pose` | If body in `_soft_body_ids`, call `getMeshData`, return centroid (mean of vertices) as position, identity quaternion. | 10 |
| A1-6 | `pybullet_simulator.py::get_state` / `step` | Ensure these don't assume standard multibody APIs for soft bodies. | 5 |
| A1-7 | `tests/test_simulators.py` | Add tests:
- `test_pybullet_soft_body_load_no_crash` — assert no NotImplementedError, assert body uniqueId exists
- `test_pybullet_soft_body_step_no_crash` — step simulation, assert still alive
- `test_pybullet_soft_body_get_mesh_data` — assert `getMeshData` returns >0 vertices
- `test_pybullet_soft_body_anchor_to_world` — anchor a node to world, assert it doesn't move under gravity
| 60 |
| A1-8 | `tests/test_simulators.py` | Add xfail decorator:
`@pytest.mark.xfail(sys.platform in ("darwin",) or os.environ.get("CI") == "true", reason="PyBullet soft body auto-tetgen unstable on macOS and some CI runners")` | 2 |

**Pros:**
- Very small change (~80 lines)
- Reuses existing `.obj` generation
- Zero new dependencies
- Satisfies schema contract immediately

**Cons / Limitations:**
- Surface `.obj` → cloth-like mass-spring only (no volumetric deformation)
- PyBullet auto-tetgen may segfault on some platforms (hence `xfail`)
- `removeBody()` broken → full simulation restart required on reset
- Parameter mapping is approximate (Young's modulus → springElasticStiffness is not physically equivalent)
- Sphere/cylinder `.obj` from our scene_builder have UV seams which can create non-manifold geometry

**Subagent strategy for A1:**
- **Agent A1a:** Implement A1-1 through A1-6 in `pybullet_simulator.py` + `schema.py` P1.
- **Agent A1b:** Write tests A1-7 through A1-8, run manual harness P3, collect platform-specific crash data.
- Merge A1a first, then A1b tests on top.

---

## 4. Phase A2: Procedural Tetrahedral `.vtk` (All Primitives, Pure Numpy)

**Goal:** Proper volumetric soft bodies without external dependencies.

### 4.1 Core Algorithm Overview

| Primitive | Generation Strategy | Tetrahedra Count |
|---|---|---|
| **Box** | 3D Cartesian grid. Each cube cell split into 5 tetrahedra using standard 5-decomposition (two pyramids + three tetrahedra). | `5 * (nx-1)*(ny-1)*(nz-1)` |
| **Sphere** | 1. Start with icosahedron surface mesh (12 vertices, 20 faces).<br>2. Add center point.<br>3. Connect center to each face → 20 tetrahedra.<br>4. Adaptive refinement: subdivide each tetrahedron at centroid, project new surface vertices to sphere radius, keep interior vertices. | `20 * 8^n` after n refinement levels |
| **Cylinder** | 1. Extruded triangulated circle: `n_theta` angular segments -> `n_theta` rectangles around circumference.<br>2. Each rectangle → 2 triangular prisms.<br>3. Each triangular prism → 3 tetrahedra via mid-edge subdivision. | `3 * n_theta * n_height` |

All generators must produce:
- Pure tetrahedra (VTK cell type 10 only)
- Consistent vertex ordering (right-hand rule for outward normals)
- No duplicate vertices (use dedup with tolerance ~1e-6)

### 4.2 Files to Create

| File | Purpose |
|---|---|
| `src/surg_rl/utils/mesh_generation.py` | `generate_box_tet_mesh(dims, resolution)` → `(vertices: ndarray[N,3], tetrahedra: ndarray[M,4])`<br>`generate_sphere_tet_mesh(radius, subdivisions)` → same<br>`generate_cylinder_tet_mesh(radius, height, theta_segments, height_segments)` → same |
| `src/surg_rl/utils/vtk_io.py` | `write_vtk_unstructured_grid(path, vertices, tetrahedra)` → writes legacy ASCII VTK with `DATASET UNSTRUCTURED_GRID`, `CELL_TYPES` all `10`.<br>`read_vtk_unstructured_grid(path)` → validates all cells are type 10, returns (vertices, tetrahedra).<br>Pure Python, no dependencies. |

### 4.3 Files to Modify

| File | Change |
|---|---|
| `pybullet_simulator.py::_load_tissue` | If `soft_body=True`:
- Check if tissue has a pre-generated `.vtk` mesh path
- If not, call generator based on primitive type → `(vertices, tetrahedra)` → write `.vtk` to cache dir (key = hash(params))
- Call `loadSoftBody(vtk_path, simFileName=...)` |
| `pybullet_simulator.py::get_body_pose` | Same as A1 (centroid from `getMeshData`) |
| `pybullet_simulator.py::reset` | Same as A1 |

### 4.4 Tests

| Test | Purpose |
|---|---|
| `test_box_tet_mesh_valid` | Generate box → assert all cells type 10, assert volume sum ≈ box volume |
| `test_sphere_tet_mesh_valid` | Generate sphere → assert all cells type 10, assert volume ≈ `4/3 π r³` within 5% |
| `test_cylinder_tet_mesh_valid` | Generate cylinder → assert all cells type 10, assert volume ≈ `π r² h` within 5% |
| `test_vtk_roundtrip` | Write → read → assert arrays equal |
| `test_pybullet_soft_body_volumetric_load` | Load `.vtk` soft body → assert `getMeshData` returns > volume vertices |
| `test_pybullet_soft_body_deforms_under_gravity` | Load, step 100 steps → assert vertex centroid z < initial z |
| `test_pybullet_soft_body_stiffness_variation` | Load with `springElasticStiffness=1.0` vs `100.0`, compare deformation magnitude |

**Xfail rule:** Same as A1, but A2 may reduce the number of xfailed platforms because procedural `.vtk` avoids auto-tetgen. Re-evaluate after manual testing.

### 4.5 Subagent Strategy for A2

| Agent | Task | Estimated Time |
|---|---|---|
| **Agent A2a** | Implement `mesh_generation.py` (box + sphere + cylinder generators) + unit tests for correctness (volume, cell types, no duplicate vertices) | 1 session |
| **Agent A2b** | Implement `vtk_io.py` (write + read + validate) + roundtrip tests | 0.5 session |
| **Agent A2c** | Integrate into `pybullet_simulator.py` (mesh cache, `_load_tissue`, `reset`, `get_body_pose`) + integration tests | 1 session |
| **Agent A2d** | Run manual harness on all target platforms, produce matrix of which platforms pass/fail, update xfail markers | 0.5 session |

**Merge order:** A2a → A2b → A2c → A2d. Run full test suite after each merge.

### 4.6 A2 Pros & Cons

**Pros:**
- Proper volumetric soft bodies (tetrahedral mesh, not surface-only)
- No external dependencies (pure numpy)
- Avoids PyBullet auto-tetgen segfaults
- More physically accurate than A1
- Mesh quality is deterministic and testable
- Works offline (no network, no compiled extensions)

**Cons:**
- Significant implementation effort (~400–500 lines + tests)
- Mesh quality varies with primitive: box is easy, sphere requires careful adaptive subdivision to avoid sliver elements, cylinder needs boundary layer handling.
- Still subject to PyBullet deformable solver limitations: no runtime param changes, thread-unsafe, `removeBody()` unsafe.
- Volume calculation may drift with high subdivision counts due to floating point.
- No support for non-primitive shapes (e.g. liver mesh from CT scan) — that requires Phase B.

---

## 5. Phase B: External Meshing Library Pipeline (Deferred)

**Status:** Not scheduled. Evaluate after A2 delivers stable results.

### Dependency Matrix

| Option | License | Install | Quality | Best For |
|---|---|---|---|---|
| **gmsh** | GPL (copyleft) | `apt/brew install gmsh` or `pip install gmsh` | Professional, mature, GUI + API | All shapes, adaptive sizing, high quality |
| **pygalmesh** | MIT | `pip install pygalmesh` (requires system CGAL) | Good Pythonic API | Implicit surfaces, CSG domains |
| **meshpy** | MIT wrapper | `pip install meshpy` | Good, lightweight | Direct TetGen access |
| **tetgen** | Academic/Commercial | Binary or via meshpy | Industry standard | Delaunay tetrahedralization |
| **trimesh + scipy** | MIT | Likely already installed | Poor without post-processing | Quick experiments only |

### Decision Criteria (to be evaluated later)
1. Can it generate a tetrahedral mesh from a surface `.obj` (watertight)?
2. Can it guarantee pure tetrahedra (no mixed cell types)?
3. Can it generate a coarser simulation mesh (`simFileName`) from the same input?
4. Is the install process reliable on Linux, macOS, and CI runners?
5. Does the license allow redistribution with this project?

### Implementation Sketch (for when Phase B is approved)

| Step | Description |
|---|---|
| B-1 | Add chosen library as optional extra in `pyproject.toml` (e.g. `"softbody": ["gmsh"]` or `"softbody": ["meshpy"]`). |
| B-2 | Implement `TissueMeshProcessor` in `src/surg_rl/utils/tissue_mesh_processor.py`:
- `process(tissue_config: TissueConfig) -> MeshResult`
- Input: surface `.obj` or primitive params
- Calls mesher → produces `.vtk` + optional coarse sim `.vtk`
- Validates output (pure tetrahedra)
- Caches by input hash
- Falls back to A2 pure-numpy generators if external mesher unavailable |
| B-3 | Modify `_load_tissue` to use `TissueMeshProcessor` output. |
| B-4 | Add coarse-mesh support via `simFileName` for performance. |
| B-5 | Add tests: `test_mesh_processor_valid_vtk`, `test_mesh_processor_caches`, `test_pybullet_soft_body_arbitrary_shape`. |

### B Pros & Cons

**Pros:**
- Arbitrary shape support (liver, heart, any organ from CT/MRI segmentation)
- Professional mesh quality, adaptive sizing
- Adaptive refinement near features (incisions, sutures)
- Coarser sim mesh support for performance

**Cons:**
- External dependency (install friction, CI setup)
- License considerations (gmsh is GPL — must not link statically; meshpy is MIT)
- Platform-specific build issues (CGAL on macOS/Windows)
- Adds 50–200MB to environment
- Requires validation pipeline (mixed cell types → segfault)
- Not needed until arbitrary-shape soft body training is a real use case.

---

## 6. Summary: Which Phase When?

| Phase | When to do it | Who needs it | Effort | Risk |
|---|---|---|---|---|
| **P1–P3** (Schema + validate + harness) | **Now** (before A1) | All downstream phases | Small | None |
| **A1** (Surface `.obj`) | **Now** after P1–P3 | Immediate: teams training on simple deformable tasks who don't need volume deformation | Small | Medium (segfault on some platforms) |
| **A2** (Tetrahedral `.vtk`) | **After A1 is merged and stable** | Teams who need volumetric deformation (suturing, grasping with volume-aware rewards) | Medium | Low (deterministic mesh) |
| **B** (External mesher) | **After A2 is merged and arbitrary shapes are requested** | Research users with medical scan data, custom organ meshes | Medium-High | Low (once chosen library is installed) |

**Current blocker:** Phase A1 is small and safe, but P1 (schema change) must happen first. Phase A2 is the "real" fix but requires ~400 lines of mesh generation code that must be correct to avoid segfaults. Phase B is over-engineering until there's a concrete need.

---

## 7. Critical Do-Nots

1. **Do NOT use `createMultiBody` for soft bodies.** That's the rigid path. The `NotImplementedError` exists precisely to prevent silent incorrect physics.
2. **Do NOT call `removeBody()` on a soft body.** Always use `resetSimulation(RESET_USE_DEFORMABLE_WORLD)` and re-load.
3. **Do NOT mix cell types in `.vtk`.** Only tetrahedra (type 10). A single stray triangle or line → segfault.
4. **Do NOT enable multi-threaded collision with soft bodies.** Race conditions in Bullet deformable solver.
5. **Do NOT use `applyExternalForce` on soft bodies** (unreliable). Use anchors or gravity only.
6. **Do NOT assume `getBasePositionAndOrientation` works.** Use `getMeshData` and compute centroid.
7. **Do NOT auto-tetgen a non-watertight mesh.** Our sphere/cylinder `.obj` have UV seams — verify manifoldness before A1.

---

## 8. Appendix: PyBullet Parameter → Schema Mapping

| PyBullet `loadSoftBody` arg | Schema field | Notes |
|---|---|---|
| `fileName` | generated `.obj` (A1) or `.vtk` (A2+) | Path from `get_mesh_or_primitive` or mesh processor |
| `basePosition` | `tissue.pose.position` | [x, y, z] |
| `baseOrientation` | `tissue.pose.orientation` | [qx, qy, qz, qw] |
| `scale` | `tissue.physics.pybullet.scale` | Must be >0 |
| `mass` | `tissue.physics.pybullet.mass` or `density * volume` | Must be >0 |
| `collisionMargin` | `tissue.physics.pybullet.collision_margin` | Must be >0 |
| `useMassSpring` | `tissue.physics.pybullet.use_mass_spring` | **Must be 1 for spring params** |
| `useBendingSprings` | `tissue.physics.pybullet.use_bending_springs` | |
| `useNeoHookean` | `tissue.physics.pybullet.use_neo_hookean` | Mutually exclusive-ish with mass-spring |
| `springElasticStiffness` | `tissue.physics.pybullet.spring_elastic_stiffness` | Only active if `useMassSpring=1` |
| `springDampingStiffness` | `tissue.physics.pybullet.spring_damping_stiffness` | Only active if `useMassSpring=1` |
| `springBendingStiffness` | `tissue.physics.pybullet.spring_bending_stiffness` | Only active if `useBendingSprings=1` |
| `springDampingAllDirections` | `tissue.physics.pybullet.spring_damping_all_directions` | |
| `NeoHookeanMu` | `tissue.physics.pybullet.neo_hookean_mu` | Only active if `useNeoHookean=1` |
| `NeoHookeanLambda` | `tissue.physics.pybullet.neo_hookean_lambda` | Only active if `useNeoHookean=1` |
| `NeoHookeanDamping` | `tissue.physics.pybullet.neo_hookean_damping` | Only active if `useNeoHookean=1` |
| `frictionCoeff` | `tissue.physics.pybullet.friction_coefficient` | |
| `useSelfCollision` | `tissue.physics.pybullet.use_self_collision` | |
| `repulsionStiffness` | `tissue.physics.pybullet.repulsion_stiffness` | Must be >0 |
| `simFileName` | `tissue.physics.pybullet.sim_mesh_path` | Optional coarse mesh |

---

## 9. Test Matrix (For Manual / CI Evaluation)

| Platform | Mode | A1 Expected | A2 Expected | Notes |
|---|---|---|---|---|
| Linux x86_64 | DIRECT | ✅ Pass | ✅ Pass | Primary target |
| Linux x86_64 | GUI | ⚠️ Flaky | ⚠️ Flaky | GUI thread can deadlock |
| macOS ARM (M1/M2/M3) | DIRECT | ⚠️ xfail / pass | ✅ Pass | A1 may segfault on auto-tetgen; A2 should be stable |
| macOS ARM | GUI | ❌ xfail | ❌ xfail | Known OpenGL/GUI deadlock |
| CI Linux (GH Actions) | DIRECT | ⚠️ xfail or pass | ✅ Pass | Very low res or headless may crash auto-tetgen |
| CI Linux (Docker) | DIRECT | ⚠️ xfail or pass | ✅ Pass | Same as above |
| Windows | DIRECT | Unknown | Unknown | Needs manual testing |

**Recommendation:** Start with `xfail` conservatively (macOS + any CI). Remove `xfail` as manual testing confirms stability. Never mark as `skip` — we want CI to attempt the test and report the actual failure mode.

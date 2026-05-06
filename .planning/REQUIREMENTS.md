# Requirements: Surg-RL v0.3.2

**Defined:** 2026-05-04
**Milestone:** v0.3.2 — Advanced Simulation Features
**Core Value:** End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation

## v1 Requirements

### Phase 15: Tetgen Mesh Generation

- [x] **TETG-01**: Integrate `tetgen` Python package as the primary tetrahedral mesh generator, replacing VTK-based fallback in `vtk_io.py`
- [x] **TETG-02**: Generate tetrahedral meshes from surface OBJ/STL inputs via tetgen CLI or Python bindings
- [x] **TETG-03**: Remove VTK dependency from project `[meshing]` extras; tetgen becomes platform-agnostic (no PyVista/VTK binary deps)
- [x] **TETG-04**: Preserve existing `vtk_io.py` public API (`generate_tetrahedral_mesh`, `write_vtk_mesh`) but redirect internals to tetgen

### Phase 16: Deformable Objects

- [x] **DEFM-01**: Add FEM-based deformable objects in MuJoCo via `mujoco.mesh` + `flexcomp` elements in MJCF/XML
- [x] **DEFM-02**: Improve PyBullet soft body parameter mapping from `TissueConfig.physics.pybullet` to `loadSoftBody`
- [x] **DEFM-03**: Unified `DeformableConfig` in scene schema with backend-specific overrides (MuJoCo stiffness/damping, PyBullet mass/scale)
- [x] **DEFM-04**: Deformable state observable via `ObservationConfig` (vertex positions, strain)

### Phase 17: Volumetric Cutting

- [x] **CUT-01**: Real-time tetrahedral mesh cutting — detect intersection between cutting tool and tetrahedral mesh
- [x] **CUT-02**: Remesh cut faces — split tets along cut plane, generate new boundary faces
- [x] **CUT-03**: Integrate with MuJoCo simulation step (pre-step callback for mesh modification) and PyBullet (removeBody + reload)
- [x] **CUT-04**: `CutAction` in action space schema — cut plane definition (start point, end point, depth)

### Phase 18: Grid-based Fluids

- [x] **FLUD-01**: Eulerian grid-based fluid solver — velocity/pressure fields on staggered grid, marker-and-cell (MAC) method
- [x] **FLUD-02**: Two-way fluid-solid coupling — fluid forces on objects, object motion affecting fluid
- [x] **FLUD-03**: Scene schema extension — `FluidConfig` with domain bounds, resolution, viscosity, density
- [x] **FLUD-04**: Fluid rendering — simple particle or surface visualization for debugging and demo

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real-time GPU fluid (CUDA/Metal) | v0.3.2 is CPU-first; GPU fluid deferred to future milestone |
| Adaptive mesh refinement (AMR) for fluids | First pass uses fixed grid |
| Fracture mechanics (beyond cutting) | Cutting only; shattering/tearing deferred |
| Fluid-K8s integration | K8s already wired; fluids run in existing containers |
| Multi-material cutting | Single material per mesh in v0.3.2 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| TETG-01..04 | Phase 15 | ✅ Complete |
| DEFM-01..04 | Phase 16 | ✅ Complete |
| CUT-01..04 | Phase 17 | ✅ Complete |
| FLUD-01..04 | Phase 18 | ✅ Complete |

**Coverage:**
- v1 requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0 ✓

---

*Requirements defined: 2026-05-04*

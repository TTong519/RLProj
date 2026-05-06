# Roadmap: Surg-RL

## Milestones

- ✅ **v0.1.0 Stabilization** — Phases 1–5 (shipped 2026-05-02)
- ✅ **v0.2.0 Scaling, Rendering & Real Robot** — Phases 6–9 (shipped 2026-05-03)
- ✅ **v0.3.0 Production & Cross-Platform** — Phases 10–13 (shipped 2026-05-04)
- ✅ **v0.3.1 Audit Gap Closure** — Phase 14 (shipped 2026-05-04) · [archive](milestones/v0.3.1-ROADMAP.md)
- ✅ **v0.3.2 Advanced Simulation** — Phases 15–18 (shipped 2026-05-05)

## Phases

<details>
<summary>✅ v0.1.0 Stabilization (Phases 1–5) — SHIPPED 2026-05-02</summary>

- [x] Phase 1: Critical Bug Fixes (3/3 plans)
- [x] Phase 2: Action Space + Gripper (3/3 plans)
- [x] Phase 3: Simulator Robustness (2/2 plans)
- [x] Phase 4: Task Geometry + Real Assets (2/2 plans)
- [x] Phase 5: Experiment Tracking + Infrastructure (2/2 plans)

</details>

<details>
<summary>✅ v0.2.0 Scaling, Rendering & Real Robot (Phases 6–9) — SHIPPED 2026-05-03</summary>

- [x] Phase 6: Universal Hardware Acceleration (3/3 plans)
- [x] Phase 7: Real-time Rendering (3/3 plans)
- [x] Phase 8: Distributed Training with Ray/RLlib (6/6 plans)
- [x] Phase 9: ROS2 Bridge (5/5 plans + 2 gap closure)

</details>

<details>
<summary>✅ v0.3.0 Production & Cross-Platform (Phases 10–13) — SHIPPED 2026-05-04</summary>

- [x] Phase 10: Metal GPU Compute + macOS Test Parity (4/4 plans)
- [x] Phase 11: Multi-platform Docker (3/3 plans)
- [x] Phase 12: ros2_control + ROS2 Launch Files (6/6 plans)
- [x] Phase 13: Kubernetes Deployment (5/5 plans)

</details>

<details>
<summary>✅ v0.3.1 Audit Gap Closure (Phase 14) — SHIPPED 2026-05-04</summary>

- [x] Phase 14: Audit Gap Closure (1/1 plan, 5 gaps closed)

</details>

## Phase 15: Tetgen Mesh Generation

**Goal:** Replace VTK-based tetrahedral mesh generation with platform-agnostic `tetgen` Python package.

**Requirements mapped:** TETG-01, TETG-02, TETG-03, TETG-04

**Success criteria:**
1. Tetgen generates tetrahedral meshes from OBJ/STL surface inputs
2. `vtk_io.py` public API preserved but internals redirected to tetgen
3. VTK/PyVista removed from `[meshing]` extras
4. All existing mesh-dependent tests pass (soft body, scene builder)

**Plans:** 1 plan (1 wave)

**Wave 1** *(no dependencies)*
- [x] 15-01-PLAN.md — Integrate tetgen, migrate vtk_io.py internals, update deps (TETG-01..04)

**Cross-cutting constraints:**
- `vtk_io.py` public API (`write_vtk_unstructured_grid`, `read_vtk_unstructured_grid`, `validate_vtk`) must remain unchanged
- All existing mesh-dependent tests must pass (test_mesh_generation.py, test_vtk_io.py, test_scene_builder.py)

## Phase 16: Deformable Objects

**Goal:** FEM-based deformable objects in MuJoCo + improved PyBullet soft body support.

**Requirements mapped:** DEFM-01, DEFM-02, DEFM-03, DEFM-04

**Success criteria:**
1. MuJoCo loads deformable bodies via `<deformable>/<flex>` (low-level) from tetgen meshes
2. PyBullet soft body Neo-Hookean params auto-derived from Young's modulus + Poisson's ratio
3. `DeformableConfig` in scene schema with MuJoCoFlexConfig / PyBulletFlexConfig backend overrides
4. Vertex positions (padded) + edge strain observable via dynamic `ObservationSpec`

**Plans:** 2 plans (2 waves)

**Wave 1** *(no dependencies)*
- [x] 16-01-PLAN.md — MuJoCo FEM `<flex>` generation + DeformableConfig schema (DEFM-01, DEFM-03)

**Wave 2** *(depends on Plan 01)*
- [x] 16-02-PLAN.md — PyBullet soft body param mapping + deformable observation (DEFM-02, DEFM-04)

## Phase 17: Volumetric Cutting

**Goal:** Real-time tetrahedral mesh cutting with remeshing, integrated with both simulator backends.

**Requirements mapped:** CUT-01, CUT-02, CUT-03, CUT-04

**Success criteria:**
1. Tool-mesh intersection detection finds cut plane
2. Tetrahedral elements split along cut plane with boundary face regeneration
3. MuJoCo pre-step callback + PyBullet remove/reload cycle handle mesh changes
4. `CutAction` schema defines cut plane in action space

**Plans:**
- [x] 17-01-PLAN.md — Cutting algorithm (intersection, remeshing)
- [x] 17-02-PLAN.md — Backend integration (MuJoCo + PyBullet)
- [x] 17-03-PLAN.md — Action space + scene schema

## Phase 18: Grid-based Fluids

**Goal:** Eulerian grid-based fluid solver with two-way solid coupling for surgical bleeding/irrigation.

**Requirements mapped:** FLUD-01, FLUD-02, FLUD-03, FLUD-04

**Success criteria:**
1. MAC staggered grid solver with velocity, pressure, and free surface
2. Fluid exerts forces on scene objects; objects displace fluid
3. `FluidConfig` schema (bounds, resolution, viscosity, density)
4. Basic particle/surface visualization

**Plans:**
- [x] 18-01-PLAN.md (inlined) — Fluid solver core (MAC grid, pressure projection)
- [x] 18-02-PLAN.md (inlined) — Two-way coupling + scene integration
- [x] 18-03-PLAN.md (inlined) — Schema + visualization

---

*Roadmap last updated: 2026-05-04 after v0.3.2 milestone initialization*

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-04)

**Core value:** End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation
**Current focus:** v0.3.2 Advanced Simulation — Phase 16 (Deformable Objects) planned

## Current Position

Milestone: v0.3.2 — Advanced Simulation
Phase: 16 — Deformable Objects
Plans: 2/2 planned (4 tasks total, 2 waves)
Status: Ready to execute
Last activity: 2026-05-04 — Phase 16 planned (2 plans, 4 tasks)

Progress: █████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 12% (v0.3.2, Phases 15-16 of 18 planned)

## Performance Metrics

- **v0.1.0:** Phases 1–5, 12 plans, 607 tests, 33/33 UAT passed
- **v0.2.0:** Phases 6–9, 19 plans, 775 tests, 0 failures, 7/7 UAT passed
- **v0.3.0:** Phases 10–13, 18 plans, 826 tests, 23/23 validated
- **v0.3.1:** Phase 14, 1 plan, 833 tests, 5/5 gaps closed

## Decisions

<details>
<summary>v0.3.0 Decisions (click to expand)</summary>

- Metal MPS compute as Phase 10 (foundation for macOS parity)
- macOS CI runner to eliminate xfail markers
- docker buildx multi-arch builds for CPU + GPU images
- ros2_control via C++ controller_manager with Python lifecycle wrapper
- ROS2 bridge as K8s sidecar with SURGRL_BRIDGE_SIDECAR detection
- RLlib RAY_ADDRESS env var for KubeRay cluster joining
- Kustomize overlays for K8s deployment variants (CPU vs GPU)

</details>

<details>
<summary>v0.3.2 Decisions (click to expand)</summary>

- **Phase 15 (tetgen):** Replace PyVista/VTK with tetgen 0.8.4 for platform-agnostic tet meshing
- **Phase 16 (deformables):** MuJoCo low-level `<deformable>/<flex>` (not `<flexcomp>`) for tetgen mesh consumption; auto-derive PyBullet Neo-Hookean μ/λ from E,ν; configurable `max_vertices` (default 200) for observation padding

</details>

## Blockers

- None

## Todos

- [x] Define v0.3.2 requirements (tetgen, deformables, cutting, fluids)
- [x] Plan Phase 15: Tetgen Mesh Generation (1 plan, 3 tasks)
- [x] Plan Phase 16: Deformable Objects (2 plans, 4 tasks)
- [ ] Plan Phase 17: Volumetric Cutting
- [ ] Plan Phase 18: Grid-based Fluids

---

_Updated: 2026-05-04 — Phase 15 planned_

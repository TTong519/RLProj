# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-05)

**Core value:** End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation
**Current focus:** v0.3.2 shipped. Ready for next milestone planning.

## Current Position

Milestone: v0.3.2 — Advanced Simulation ✅ SHIPPED
Phases: 15-18 all complete
Plans: 9/9 executed
Tests: 910 passed, 11 skipped
Last activity: 2026-05-05 — v0.3.2 milestone audit verified clean

Progress: ████████████████████████████████████████████ 100% (v0.3.2, all 4 phases complete)

## Performance Metrics

- **v0.1.0:** Phases 1–5, 12 plans, 607 tests, 33/33 UAT passed
- **v0.2.0:** Phases 6–9, 19 plans, 775 tests, 0 failures, 7/7 UAT passed
- **v0.3.0:** Phases 10–13, 18 plans, 826 tests, 23/23 validated
- **v0.3.1:** Phase 14, 1 plan, 833 tests, 5/5 gaps closed
- **v0.3.2:** Phases 15–18, 9 plans, 910 tests, 16/16 requirements, Nyquist compliant

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
- **Phase 17 (cutting):** Pure NumPy tetrahedral mesh cutting with 5 canonical tet-plane cases; MuJoCo model reload via MJCF XML inline rewrite; PyBullet safe reload (RESET_USE_DEFORMABLE_WORLD); discrete trigger with 500ms cooldown
- **Phase 18 (fluids):** PhiFlow 3.4.0 for MAC staggered grid on 2D xz-plane; CPU-first (GPU deferred); 2D visualization via skimage; sub-sampled step hook in SurgicalEnv

</details>

## Blockers

- None

## Todos

- [x] Define v0.3.2 requirements (tetgen, deformables, cutting, fluids)
- [x] Plan Phase 15: Tetgen Mesh Generation
- [x] Plan Phase 16: Deformable Objects
- [x] Plan Phase 17: Volumetric Cutting
- [x] Plan Phase 18: Grid-based Fluids
- [x] Ship Phase 15
- [x] Ship Phase 16
- [x] Ship Phase 17
- [x] Ship Phase 18
- [x] Nyquist validation audit
- [x] Milestone integration audit
- [ ] Complete milestone (gsd-complete-milestone)

---

_Updated: 2026-05-05 — v0.3.2 milestone audit verified clean, 910 tests_

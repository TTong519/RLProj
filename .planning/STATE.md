# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-04)

**Core value:** End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation
**Current focus:** Defining v0.3.2 requirements — Advanced Simulation Features

## Current Position

Milestone: v0.3.2 — Advanced Simulation
Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-05-04 — v0.3.2 milestone started

Progress: ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 0% (v0.3.2)

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

## Blockers

- None

## Todos

- [ ] Define v0.3.2 requirements (tetgen, deformables, cutting, fluids)

---

_Updated: 2026-05-04 — v0.3.2 milestone started_

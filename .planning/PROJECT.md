# Surg-RL

## What This Is

A comprehensive surgical-robotics reinforcement learning training system with production deployment infrastructure and advanced simulation capabilities. Generates and simulates surgical scenes from text/images via LLM/VLM, trains RL agents (PPO, SAC, TD3, DDPG, A2C) in MuJoCo or PyBullet with domain randomization, curriculum learning, adaptive difficulty. Features platform-agnostic tetgen mesh generation, FEM deformable objects, real-time volumetric tetrahedral mesh cutting, and Eulerian grid fluid simulation (bleeding/irrigation). Supports Apple Silicon Metal GPU compute, multi-arch Docker images, ROS2 ros2_control integration, and Kubernetes deployment. Built for robotics researchers and surgical training simulators.

## Core Value

End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation — with automatic primitive fallbacks when real assets are missing.

## Current State

**Shipped v0.3.2** (2026-05-06) — 4 phases (15-18), 9 plans, 910 tests, 16/16 requirements. Milestone complete and archived.

Next: planning the next milestone. All v0.1.0 through v0.3.2 milestones shipped.

### Key Deliverables (v0.3.2)
- Platform-agnostic tetgen 0.8.4 tetrahedral mesh generation replacing PyVista/VTK
- FEM deformable objects: MuJoCo flex MJCF + PyBullet Neo-Hookean with auto-derived params
- Real-time volumetric tetrahedral mesh cutting engine (5 canonical cases) with cross-backend integration
- Eulerian grid fluid solver (PhiFlow 3.4.0) with two-way solid coupling for bleeding/irrigation
- In-memory tetgen → MJCF flex bridge, Phase 18→env FluidSimulator wiring, PyBullet cut bug fix
- 910 tests, 3 low-risk items deferred

### Accepted Tech Debt (deferred)
- Per-tet generation counter for degenerate tets after multiple cuts (Phase 17) — single cut per episode typical
- Cut cooldown unit test (Phase 17) — requires full env lifecycle, cooldown is simple arithmetic
- Fluid step hook in base_simulator.py (Phase 18) — env-level hook sufficient for v0.3.2
- PhiFlow multi-obstacle union() bug requires merged SDF workaround — documented pitfall
- 2D fluids only (xz-plane); 3D behind dim_3d=True flag, not yet implemented
- Previous v0.3.1 deferred: Dockerfile.ros2 amd64 hardcode, K8S PVC e2e, KubeRay prerequisite

## Requirements

### Validated (v0.3.2)

- ✓ All v0.3.0 features (Metal GPU, macOS parity, multi-arch Docker, ros2_control, Kubernetes)
- ✓ **Tetgen Mesh Generation** — Platform-agnostic tetrahedral meshes, VTK-free (TETG-01..04)
- ✓ **Deformable Objects** — MuJoCo FEM flex, PyBullet Neo-Hookean, dynamic observation (DEFM-01..04)
- ✓ **Volumetric Cutting** — Real-time tet mesh cutting, 5 canonical cases, cross-backend (CUT-01..04)
- ✓ **Grid-based Fluids** — PhiFlow Eulerian solver, two-way coupling, 2D viz (FLUD-01..04)

### Active (Next Milestone)

- _None yet — run `/gsd-new-milestone` to define the next milestone_

### Out of Scope

- Mobile app — Web/library-first, mobile applications are a different product
- Real-time multi-user networked surgery — Single-agent training scope
- FDA certification / medical-grade safety validation — Research and simulation tool, not clinical device
- Unity/Unreal rendering backends — MuJoCo and PyBullet rendering is sufficient
- DirectML / Vulkan compute backends — Windows not primary target; niche use case
- Linux-only ROS2 subscriber e2e tests — Requires real ROS2 runtime; mock coverage is sufficient for macOS
- Helm chart — Kustomize overlays sufficient for v0.3.0; Helm can be added later
- Real-time ROS2 DDS router for K8s multicast — DDS multicast issue is platform-level; document workaround, don't solve
- 3D fluid simulation — 2D xz-plane slice is sufficient for surgical bleeding/irrigation; 3D behind dim_3d=True flag
- GPU fluid acceleration — PhiFlow CPU-first; GPU acceleration can be added when needed

## Context

**Platform:** Python ≥3.10, MuJoCo 3.x, PyBullet ≥3.2.5, Gymnasium ≥0.29, Stable-Baselines3 ≥2.0
**Build:** setuptools, pip, pyproject.toml
**CLI:** Typer + Rich (`surg-rl` command, 12 subcommands)
**Config:** Pydantic v2 dataclasses + pydantic-settings (.env support)
**Testing:** pytest (pytest.ini with `pythonpath = src`), 910 tests, 0 failures
**Lint/Type:** ruff, black, mypy

## Key Architecture Decisions

- Dual-backend simulation via `BaseSimulator` ABC (Strategy pattern)
- Pydantic v2 `SceneDefinition` as single source of truth
- Optional dependency groups: `[distributed]`, `[ros2]`, `[llm]`, `[vision]`
- Lazy imports for optional deps (Ray, ROS2) — no crash on missing packages
- `PYTHONPATH=src` required for direct Python script invocations
- Cross-backend state save/restore via `get_state()`/`set_state()`
- Observation dataclass as cross-backend contract for RL layer
- Simulator owns threads/processes; env owns lifecycle via start/stop
- Kustomize overlays for K8s deployment variants (CPU vs GPU)
- Tetgen replaces VTK entirely for platform-agnostic meshing (not side-by-side)
- MuJoCo `<flex>` (not `<flexcomp>`) for arbitrary tetgen meshes
- Cutting is discrete trigger (not continuous action) with 500ms cooldown
- PyBullet cuts use RESET_USE_DEFORMABLE_WORLD + full reload (removeBody() unsafe)
- PhiFlow over Mantaflow for Eulerian fluids (Mantaflow abandoned since 2022)
- CPU-first fluids (GPU deferred); in-memory tetgen → MJCF bridge for zero-file-I/O path

## Recent Milestones

| Milestone | Phases | Plans | Tests | Status |
|-----------|--------|-------|-------|--------|
| v0.1.0 | 1–5 | 12 | 607 | Complete |
| v0.2.0 | 6–9 | 19 | 775 | Complete |
| v0.3.0 | 10–13 | 18 | 826 | Complete |
| v0.3.1 | 14 | 1 | 833 | Complete |
| v0.3.2 | 15–18 | 9 | 910 | Complete |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---

*Last updated: 2026-05-06 after v0.3.2 milestone archival*

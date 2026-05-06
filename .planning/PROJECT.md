# Surg-RL

## What This Is

A comprehensive surgical-robotics reinforcement learning training system with production deployment infrastructure. It generates and simulates surgical scenes from text/images via LLM/VLM, then trains RL agents (PPO, SAC, TD3, DDPG, A2C) in MuJoCo or PyBullet with domain randomization, curriculum learning, and adaptive difficulty. Supports Apple Silicon Metal GPU compute, multi-arch Docker images, ROS2 ros2_control integration, and Kubernetes deployment. Built for robotics researchers and surgical training simulators.

## Core Value

End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation — with automatic primitive fallbacks when real assets are missing.

## Current State

**Shipped v0.3.1** (2026-05-04) — 1 phase, 1 plan, 833 tests, 5/5 audit gaps closed.

**v0.3.2 shipped — Advanced Simulation Features.** (2026-05-05) Cutting, deformable objects, fluids, and platform-agnostic tetgen mesh generation.

### Key Deliverables (v0.3.1)
- All 5 v0.3.0 audit integration gaps closed
- Dockerfile.ros2 wired to GHCR release workflow
- CUDA image for GPU K8s training nodes; CPU overlay image fallback
- ROS2 topic probe replacing TCP netcat initContainer health check
- bridge_node/replay_node console_scripts registered in pyproject.toml
- Metal detection deduplicated: `_mps_available()` → `gpu._has_metal()`

### Accepted Tech Debt (deferred)
- `Dockerfile.ros2` hardcodes `linux/amd64` while `Dockerfile` uses `$TARGETPLATFORM` — intentional, not blocking
- K8S-05 PVC e2e validation requires real K8s cluster — manual-only, documented prerequisite
- KubeRay operator must be pre-installed on target cluster — documented prerequisite

## Requirements

### Validated (v0.3.0)

- ✓ All v0.2.0 features (GPU acceleration, real-time rendering, Ray/RLlib distributed training, ROS2 bridge)
- ✓ **Metal GPU compute** — MPS device resolution on Apple Silicon, unified memory logging, single-warning CPU fallback (METAL-01..03)
- ✓ **macOS test parity** — macOS CI runner in matrix, all PyBullet soft-body xfails removed, mjpython support, ROS2 exclusion documented (MACOS-01..04)
- ✓ **Multi-platform Docker** — CPU amd64+arm64, CUDA/ROCm amd64, Jetson arm64, ROS2 bridge via docker buildx with GHCR push (DOCKR-01..04)
- ✓ **ros2_control integration** — ControllerBridge managing C++ controller_manager, URDF ros2_control tags, lifecycle integration, CLI command (R2CTL-01..04)
- ✓ **ROS2 launch files** — bridge.launch.py + replay.launch.py, pip+colcon compatibility, launch arguments (LAUNCH-01..03)
- ✓ **Kubernetes deployment** — Training Job, KubeRay RayCluster/RayJob, bridge sidecar, ConfigMap/Secret/PVC/RBAC, RAY_ADDRESS env var, Kustomize overlays (K8S-01..05)

### Active (Next Milestone)

- [x] **Phase 15: Tetgen Mesh Generation** — Replace VTK with tetgen for platform-agnostic tetrahedral meshes
- [x] **Phase 16: Deformable Objects** — FEM deformables in both MuJoCo + PyBullet
- [x] **Phase 17: Volumetric Cutting** — Real-time tetrahedral mesh cutting with remeshing
- [x] **Phase 18: Grid-based Fluids** — Eulerian grid fluid solver for bleeding/irrigation

### Out of Scope

- Mobile app — Web/library-first, mobile applications are a different product
- Real-time multi-user networked surgery — Single-agent training scope
- FDA certification / medical-grade safety validation — Research and simulation tool, not clinical device
- Unity/Unreal rendering backends — MuJoCo and PyBullet rendering is sufficient
- DirectML / Vulkan compute backends — Windows not primary target; niche use case
- Linux-only ROS2 subscriber e2e tests — Requires real ROS2 runtime; mock coverage is sufficient for macOS
- Helm chart — Kustomize overlays sufficient for v0.3.0; Helm can be added later
- Real-time ROS2 DDS router for K8s multicast — DDS multicast issue is platform-level; document workaround, don't solve
- MoveIt integration — Beyond scope of ros2_control; raw command/state interfaces are sufficient

## Context

**Platform:** Python ≥3.10, MuJoCo 3.x, PyBullet ≥3.2.5, Gymnasium ≥0.29, Stable-Baselines3 ≥2.0
**Build:** setuptools, pip, pyproject.toml
**CLI:** Typer + Rich (`surg-rl` command, 12 subcommands)
**Config:** Pydantic v2 dataclasses + pydantic-settings (.env support)
**Testing:** pytest (pytest.ini with `pythonpath = src`), 833 tests, 0 failures
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

## Recent Milestones

| Milestone | Phases | Plans | Tests | Status |
|-----------|--------|-------|-------|--------|
| v0.1.0 | 1–5 | 12 | 607 | Complete |
| v0.2.0 | 6–9 | 19 | 775 | Complete |
| v0.3.0 | 10–13 | 18 | 826 | Complete |
| v0.3.1 | 14 | 1 | 833 | Complete |

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

*Last updated: 2026-05-04 after v0.3.0 milestone archival*

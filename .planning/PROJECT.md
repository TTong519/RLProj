# Surg-RL

## What This Is

A comprehensive surgical-robotics reinforcement learning training system with production deployment infrastructure. It generates and simulates surgical scenes from text/images via LLM/VLM, then trains RL agents (PPO, SAC, TD3, DDPG, A2C) in MuJoCo or PyBullet with domain randomization, curriculum learning, and adaptive difficulty. Supports Apple Silicon Metal GPU compute, multi-arch Docker images, ROS2 ros2_control integration, and Kubernetes deployment. Built for robotics researchers and surgical training simulators.

## Core Value

End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation — with automatic primitive fallbacks when real assets are missing.

## Current State

**Shipped v0.3.0** (2026-05-04) — 4 phases, 18 plans, 826 tests, 23/23 requirements validated.

**Now building v0.3.1 — Audit Gap Closure.** Fixing 5 integration gaps identified by v0.3.0 milestone audit.

### Key Deliverables (v0.3.0)
- PyTorch MPS compute for Apple Silicon + macOS CI runner with test parity
- Multi-arch Docker images (amd64 + arm64, CUDA + Jetson) on GHCR via docker buildx
- ros2_control hardware_interface via C++ controller_manager with Python lifecycle management
- ROS2 .launch.py files with pip+colcon compatibility
- Production K8s manifests (Job, RayCluster, sidecar, ConfigMap/Secrets/PVC, Kustomize overlays)

### Known Gaps (accepted tech debt — v0.3.1 target)
- `Dockerfile.ros2` image not wired to GHCR release workflow (referenced by K8s manifests)
- Trainer uses CPU image with GPU request in K8s Job manifest
- initContainer health check probes TCP instead of DDS
- No bridge_node/replay_node console_scripts in pyproject.toml
- `_mps_available()` in `config.py` duplicates `gpu.py` Metal detection logic
- `_mps_available()` duplicates `gpu.py` Metal detection logic

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

- [ ] Fix K8s integration gaps from v0.3.0 audit
- [ ] TBD — define in next milestone planning

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
**Testing:** pytest (pytest.ini with `pythonpath = src`), 826 tests, 0 failures
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

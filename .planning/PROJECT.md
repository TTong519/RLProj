# Surg-RL

## What This Is

A comprehensive surgical-robotics reinforcement learning training system. It generates and simulates surgical scenes from text/images via LLM/VLM, then trains RL agents (PPO, SAC, TD3, DDPG, A2C) in MuJoCo or PyBullet with domain randomization, curriculum learning, and adaptive difficulty. Built for robotics researchers and surgical training simulators.

## Core Value

End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation — with automatic primitive fallbacks when real assets are missing.

## Requirements

### Validated (v0.1.0)

- ✓ Scene definition schema (Pydantic v2) — supports robots, tissues, instruments, physics, tasks, domain randomization
- ✓ Scene loader with JSON/YAML parsing, LRU cache, and asset validation
- ✓ LLM/VLM scene generation via OpenAI, Anthropic, and Ollama + 8 pre-built surgical task templates
- ✓ Dual-backend simulation (MuJoCo 3.x and PyBullet ≥3.2.5) with unified `BaseSimulator` API
- ✓ Procedural mesh generation (box, sphere, cylinder) and VTK I/O for soft bodies
- ✓ Domain randomization (physics / visual / dynamics)
- ✓ Curriculum scheduler (Easy → Medium → Hard → Expert)
- ✓ Adaptive difficulty controller (performance-driven scaling)
- ✓ Gymnasium-compatible `SurgicalEnv` with observation/action/reward builders
- ✓ SB3 training pipeline wired for 5 algorithms with callbacks and TensorBoard logging
- ✓ Typer CLI (`surg-rl`) with version, config, setup, generate, train, evaluate commands
- ✓ **8 critical bugs fixed** — quaternion order, joint reset, physics=None, reward sign, curriculum dynamics, LightConfig mutation, API key exposure, VecEnv evaluate
- ✓ **All 7 ActionTypes implemented** — JOINT_POSITIONS, JOINT_VELOCITIES, JOINT_TORQUES, ENDEFFECTOR_POSE, ENDEFFECTOR_DELTA, DISCRETE, GRIPPER
- ✓ **Gripper auto-detection** in both MuJoCo and PyBullet backends
- ✓ **Soft-body mesh caching** (<100ms reset) and vectorized mesh generation
- ✓ **Cross-backend state save/restore** (qpos/qvel within 1e-6)
- ✓ **Persistent eval env caching** in TrainingManager
- ✓ **Task geometry binding** — needle_pos, entry_point, exit_point from target_body
- ✓ **Real asset loading** — URDF/OBJ with deduplicated fallback warnings
- ✓ **Experiment tracking** — optional W&B/MLflow callbacks with controller-aware logging
- ✓ **CI/CD** — GitHub Actions CI (matrix 3.10/3.11/3.12) + PyPI release pipeline
- ✓ **Containerization** — multi-stage Dockerfile
- ✓ 607 passing tests across 15+ test modules

### Active (v0.2.0)

- [ ] Ray/RLlib distributed training support
- [ ] ROS2 integration for real-hardware validation
- [ ] Kubernetes deployment manifests
- [ ] Multi-platform Docker builds (arm64)
- [ ] Real-time rendering during RL training (currently synchronous)

### Out of Scope

- Mobile app — Web/library-first, mobile applications are a different product
- Real-time multi-user networked surgery — Single-agent training scope
- FDA certification / medical-grade safety validation — Research and simulation tool, not clinical device
- Unity/Unreal rendering backends — MuJoCo and PyBullet rendering is sufficient

## Context

This repository was rapidly prototyped as an alpha build and has now completed its v0.1.0 stabilization milestone. All 8 critical bugs are fixed, all action types are implemented, simulator performance is hardened with caching and vectorization, task geometry is bound to observations, real assets load with fallback, and the project has CI/CD + containerization.

The `.planning/codebase/` map serves as the brownfield discovery record for all existing architecture, stack, conventions, and concerns.

## Constraints

- **Tech stack**: Python ≥3.10, MuJoCo / PyBullet, Gymnasium, Stable-Baselines3, Pydantic v2, Typer, Rich
- **Assets**: Procedural `.obj` and `.vtk` fallbacks; real URDF/OBJ supported when available
- **Test stability**: PyBullet soft-body tests xfail on darwin/CI; known issue not to remove
- **Security**: API keys masked in logs (last 4 chars shown); placeholder keys rejected at validation

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Pydantic v2 as system schema | Strong typing, validation, and serialization across JSON/YAML configs | ✓ Good — single source of truth |
| Dual simulator backends (MuJoCo + PyBullet) | MuJoCo for performance, PyBullet for soft-body deformable physics | ✓ Good — flexibility at cost of maintenance |
| Procedural primitive fallbacks instead of real assets | Lightweight repo, avoids licensing and distribution of surgical meshes | ✓ Good — real asset loading added with graceful fallback |
| LLM/VLM-based scene generation | Natural language input reduces barrier to scene creation | ✓ Good — reduces config boilerplate |
| No site-wide install (editable only) | Matches research-tool convention where users modify source | ✓ Good — prevents stale-site issues |
| Backend detection via duck typing (`hasattr`) | Avoids explicit simulator-type enums in controller layer | ⚠️ Revisit — fragile, breaks with internal API changes |
| Optional dependencies for tracking (wandb/mlflow) | Keeps core install lightweight; tracking only when needed | ✓ Good — `[tracking]` extra works well |
| Multi-stage Dockerfile | System deps in base, build in middle, runtime lean | ✓ Good — image is ~200MB smaller than single-stage |

## Milestones

- **v0.1.0 Stabilization** (2026-04-29 → 2026-05-02) — [Archive](milestones/v0.1.0-ROADMAP.md)
  - 5 phases, 12 plans, 43 commits, 607 tests, 33/33 UAT passed

## Current Milestone: v0.2.0 — Scaling, Rendering & Real Robot

**Goal:** Scale beyond single-GPU training, add real-time 3D rendering, and bridge to real hardware via ROS2.

**Target features:**
1. **GPU acceleration** — CUDA detection, GPU-backed MuJoCo rendering, nvidia-docker variant
2. **Real-time rendering** — Live, non-blocking OpenGL window during RL training
3. **Ray/RLlib distributed training** — Multi-GPU, multi-node with Ray Tune + RLlib algorithms
4. **ROS2 bridge** — Publisher/subscriber nodes for real-robot validation (trajectory replay, state sync)

**Deferred to v0.3.0:**
- Kubernetes deployment manifests
- Multi-platform Docker builds (arm64)

---
## Active (v0.2.0)

- [ ] GPU acceleration — CUDA detection, GPU-backed rendering, nvidia-docker variant
- [ ] Real-time rendering — Non-blocking human render during training
- [ ] Ray/RLlib distributed training — Multi-GPU + Tune hyperparameter search
- [ ] ROS2 bridge — joint_states publisher, command subscriber, trajectory replay

## Out of Scope

- Mobile app — Web/library-first, mobile applications are a different product
- Real-time multi-user networked surgery — Single-agent training scope
- FDA certification / medical-grade safety validation — Research and simulation tool, not clinical device
- Unity/Unreal rendering backends — MuJoCo and PyBullet rendering is sufficient

## Context

This repository was rapidly prototyped as an alpha build and has now completed its v0.1.0 stabilization milestone. All 8 critical bugs are fixed, all action types are implemented, simulator performance is hardened with caching and vectorization, task geometry is bound to observations, real assets load with fallback, and the project has CI/CD + containerization.

The `.planning/codebase/` map serves as the brownfield discovery record for all existing architecture, stack, conventions, and concerns.

## Constraints

- **Tech stack**: Python ≥3.10, MuJoCo / PyBullet, Gymnasium, Stable-Baselines3, Pydantic v2, Typer, Rich
- **Assets**: Procedural `.obj` and `.vtk` fallbacks; real URDF/OBJ supported when available
- **Test stability**: PyBullet soft-body tests xfail on darwin/CI; known issue not to remove
- **Security**: API keys masked in logs (last 4 chars shown); placeholder keys rejected at validation
- **GPU**: CUDA optional; system works without GPU (graceful degradation)
- **ROS2**: Linux-only by design; macOS bridge code detects platform and warns

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Pydantic v2 as system schema | Strong typing, validation, and serialization across JSON/YAML configs | ✓ Good — single source of truth |
| Dual simulator backends (MuJoCo + PyBullet) | MuJoCo for performance, PyBullet for soft-body deformable physics | ✓ Good — flexibility at cost of maintenance |
| Procedural primitive fallbacks instead of real assets | Lightweight repo, avoids licensing and distribution of surgical meshes | ✓ Good — real asset loading added with graceful fallback |
| LLM/VLM-based scene generation | Natural language input reduces barrier to scene creation | ✓ Good — reduces config boilerplate |
| No site-wide install (editable only) | Matches research-tool convention where users modify source | ✓ Good — prevents stale-site issues |
| Backend detection via duck typing (`hasattr`) | Avoids explicit simulator-type enums in controller layer | ⚠️ Revisit — fragile, breaks with internal API changes |
| Optional dependencies for tracking (wandb/mlflow) | Keeps core install lightweight; tracking only when needed | ✓ Good — `[tracking]` extra works well |
| Multi-stage Dockerfile | System deps in base, build in middle, runtime lean | ✓ Good — image is ~200MB smaller than single-stage |

## Milestones

- **v0.2.0 Scaling, Rendering & Real Robot** (in progress)
  - 4 phases (6–9), 22 requirements
  - GPU acceleration → Real-time rendering → Ray/RLlib → ROS2 bridge

- **v0.1.0 Stabilization** (2026-04-29 → 2026-05-02) — [Archive](milestones/v0.1.0-ROADMAP.md)
  - 5 phases, 12 plans, 43 commits, 607 tests, 33/33 UAT passed

---
*Last updated: 2026-05-02 after v0.2.0 milestone initialization*

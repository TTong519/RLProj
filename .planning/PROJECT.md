# Surg-RL

## What This Is

A comprehensive surgical-robotics reinforcement learning training system. It generates and simulates surgical scenes from text/images via LLM/VLM, then trains RL agents (PPO, SAC, TD3, DDPG, A2C) in MuJoCo or PyBullet with domain randomization, curriculum learning, and adaptive difficulty. Built for robotics researchers and surgical training simulators.

## Core Value

End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation — with automatic primitive fallbacks when real assets are missing.

## Requirements

### Validated (v0.2.0)

- ✓ All v0.1.0 features (607 tests, 15+ modules)
- ✓ **GPU acceleration** — HardwareBackend enum (auto/cuda/rocm/metal/intel/cpu), detection via nvidia-smi/rocminfo/torch.mps, Docker variants (CUDA + ROCm), Intel graceful CPU fallback (GPU-08)
- ✓ **Real-time rendering** — Non-blocking viewer via RenderThread, 30 FPS throttle, --render-human CLI flag, clean SIGINT shutdown, macOS mjpython support
- ✓ **Ray/RLlib distributed training** — RLlib env registration, RllibConfig dataclass, train_rllib()/build_tune_search_space()/run_tune_experiment(), checkpoint inspection, [distributed] optional extra, 6 test files, 3 new CLI commands
- ✓ **ROS2 bridge** — Ros2BridgeConfig Pydantic v2, Ros2BridgeNode pub/sub (JointState + Float64MultiArray), multiprocessing.Process bridge with multiprocessing.Queue IPC, bridge→controller forwarding (G-1), EnvironmentController real/sim mode switch, TrajectoryReplay at 10% speed, surg-rl ros2-bridge/ros2-replay CLI, [ros2] optional extra, macOS graceful degradation

### Active (v0.3.0)

- [ ] Kubernetes deployment manifests
- [ ] Multi-platform Docker builds (arm64)
- [ ] `ros2_control` hardware_interface integration
- [ ] ROS2 launch file support (.launch.py)

### Out of Scope

- Mobile app — Web/library-first, mobile applications are a different product
- Real-time multi-user networked surgery — Single-agent training scope
- FDA certification / medical-grade safety validation — Research and simulation tool, not clinical device
- Unity/Unreal rendering backends — MuJoCo and PyBullet rendering is sufficient
- DirectML / Vulkan compute backends — Windows not primary target; niche use case

## Context

**Platform:** Python ≥3.10, MuJoCo 3.x, PyBullet ≥3.2.5, Gymnasium ≥0.29, Stable-Baselines3 ≥2.0
**Build:** setuptools, pip, pyproject.toml
**CLI:** Typer + Rich (`surg-rl` command)
**Config:** Pydantic v2 dataclasses + pydantic-settings (.env support)
**Testing:** pytest (pytest.ini with `pythonpath = src`), 775 tests, 0 failures
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

## Recent Milestones

| Milestone | Phases | Plans | Tests | Status |
|-----------|--------|-------|-------|--------|
| v0.1.0 | 1–5 | 12 | 607 | Complete |
| v0.2.0 | 6–9 | 19 | 775 | Complete |

---

*Last updated: 2026-05-03 after v0.2.0 milestone — all 9 phases shipped, 33/33 requirements validated*
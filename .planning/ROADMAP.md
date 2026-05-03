# Roadmap: Surg-RL v0.2.0

**Milestone:** v0.2.0 — Scaling, Rendering & Real Robot  
**Goal:** Scale beyond single-GPU training, add real-time 3D rendering, and bridge to real hardware  
**Phases:** 4 (6–9) **Requirements:** 33 (v1)  
**Estimated effort:** 4–5 hours

---

## Phases

### Phase 6: Universal Hardware Acceleration (3 plans)

**Goal:** Detect and leverage CUDA, Intel oneAPI, AMD ROCm, and Apple Metal for rendering and compute; provide a unified backend selector.

**Requirements mapped:** GPU-01 through GPU-16

**Plans:**
- [x] 06-01-PLAN.md — HardwareBackend enum, gpu.py detection module, TrainingConfig/Settings/CLI wiring
- [x] 06-02-PLAN.md — Wire backend into simulators (MuJoCo + PyBullet) and version --verbose GPU table
- [x] 06-03-PLAN.md — Dockerfiles (CUDA + ROCm) and comprehensive unit/integration tests

**Success criteria:**

*NVIDIA (CUDA):*
1. `surg-rl version --verbose` displays GPU availability (CUDA version, renderer type)
2. MuJoCo `mujoco.Renderer(..., gl_context)` uses GPU context without crashes when CUDA is present
3. PyBullet warns with a single log line when `gpu_accelerated=True` but no GPU is present
4. `docker build --build-arg CUDA_BASE=nvidia/cuda:12.2.0-runtime-ubuntu22.04` produces a GPU-enabled image

*Intel (oneAPI / XPU):*
5. `surg-rl version --verbose` displays Intel XPU availability when `sycl-ls` or `dpctl` is present
6. `TrainingConfig(backend="intel")` is accepted and falls back to CPU gracefully if oneAPI is missing
7. MuJoCo uses OSMesa/CPU fallback on Intel if no GPU context available; oneAPI path is documented

*AMD (ROCm / HIP):*
8. `surg-rl version --verbose` displays ROCm availability when `rocminfo` or HIP is present
9. PyBullet accepts `backend="rocm"` and maps to ROCm-compatible OpenGL/EGL; warns if unavailable
10. `docker build --build-arg ROCM_BASE=rocm/dev-ubuntu-22.04` produces a ROCm-enabled image

*Apple (Metal):*
11. `surg-rl version --verbose` displays Metal availability on macOS via `torch.backends.mps.is_available()`
12. MuJoCo on macOS uses Metal-backed `mjrContext` when available; falls back to NS/OpenGL

*Unified backend:*
13. `HardwareBackend` enum covers `auto`, `cuda`, `rocm`, `metal`, `intel`, `cpu`; `"auto"` tries all in priority order
14. Backend selection is logged at INFO level so users know which path is active
15. `TrainingConfig` accepts `backend: HardwareBackend = HardwareBackend.auto` with per-platform propagation
16. Tests cover graceful degradation on all platforms (no hard dependency on any GPU)

### Phase 7: Real-time Rendering (3 plans)

**Goal:** Add live, non-blocking 3D rendering during RL training without interfering with the training loop.

**Requirements mapped:** RENDER-01 through RENDER-05

**Plans:**
- [x] 07-01-PLAN.md — BaseSimulator viewer contract, RenderThread, MuJoCo/PyBullet viewer backends, _create_simulator wiring
- [x] 07-02-PLAN.md — SurgicalEnv eager viewer start, SIGINT/atexit, headless fallback, TrainingConfig wiring
- [x] 07-03-PLAN.md — CLI --render-human/--render-fps flags, comprehensive test suite

**Success criteria:**
1. `BaseSimulator.render(mode="human")` creates a non-blocking window that survives `reset()`
2. `SurgicalEnv.step()` does not block when `render_mode="human"` is active
3. Render FPS is throttled to a configurable target (default 30 FPS)
4. `surg-rl train` accepts `--render-human` flag that opens a live viewer
5. Viewer window closes cleanly on `env.close()` and SIGINT without segfault

### Phase 8: Distributed Training with Ray/RLlib (6 plans)

**Goal:** Scale training beyond single-process SB3 with Ray RLlib distributed execution, multi-GPU support, and hyperparameter search.

**Requirements mapped:** DIST-01 through DIST-06

**Plans:**
- [x] 08-01-PLAN.md ✅ 2026-05-02 — RLlib env registration (env_creator + register_env), RllibConfig dataclass, pyproject.toml [distributed] extra
- [x] 08-02-PLAN.md ✅ 2026-05-02 — train_rllib() entrypoint, Ray init/shutdown, single-node multi-GPU auto-config
- [x] 08-03-PLAN.md ✅ 2026-05-02 — Ray Tune integration, build_tune_search_space(), run_tune_experiment(), reward weight search
- [x] 08-04-PLAN.md ✅ 2026-05-02 — Checkpoint inspection utilities (RLlib + SB3), compare_checkpoints(), documented migration path
- [x] 08-05-PLAN.md ✅ 2026-05-02 — CLI train-rllib / tune / checkpoint-inspect commands
- [x] 08-06-PLAN.md ✅ 2026-05-02 — Comprehensive test suite (7 test files, 26 tests), Nyquist validation map

**Success criteria:**
1. `SurgicalEnv` is registerable as a custom RLlib environment with proper `env_config` support
2. `surg_rl.rl.rllib.train_rllib(config)` runs a minimal PPO training loop to convergence (reward improves over 10k steps)
3. A single-node machine with 2+ GPUs trains without manual Ray cluster setup (`ray.init()` auto-detects)
4. Ray Tune search space over scene definitions and reward weights produces 3+ trial variants
5. RLlib checkpoint can be inspected for compatibility (state dict shape matches) with SB3 checkpoint
6. `pip install "surg-rl[distributed]"` installs `ray[rllib]>=2.10` without version conflicts

### Phase 9: ROS2 Bridge for Real Hardware (6 plans)

**Goal:** Publish simulation state to ROS2 and accept external commands for real-robot validation.

**Requirements mapped:** ROS2-01 through ROS2-06

**Success criteria:**
1. `ros2 topic list` shows `/surg_rl/joint_states` after running `surg-rl ros2-bridge --publisher`
2. Publishing a `sensor_msgs/JointState` message to `/surg_rl/commands` moves the simulated robot joints
3. Trajectory replay from a saved SB3 checkpoint runs at 10% speed through the ROS2 bridge without crashes
4. `SimulationController.set_real_robot_mode(True)` switches state source from physics to external subscriber
5. `surg-rl ros2-bridge --config ros2_bridge.yaml` starts both publisher and subscriber with custom topics
6. `pip install "surg-rl[ros2]"` installs `rclpy` and message packages without interfering with core deps

---

## Traceability

| Requirement | Phase | Goal |
|-------------|-------|------|
| GPU-01 | 6 | CUDA detection in version --verbose |
| GPU-02 | 6 | MuJoCo CUDA GPU renderer |
| GPU-03 | 6 | PyBullet GPU flag + warn |
| GPU-04 | 6 | nvidia-docker variant |
| GPU-05 | 6 | TrainingConfig gpu flag |
| GPU-06 | 6 | Intel oneAPI / XPU detection |
| GPU-07 | 6 | MuJoCo Intel fallback documented |
| GPU-08 | 6 | TrainingConfig backend selector "intel" |
| GPU-09 | 6 | AMD ROCm / HIP detection |
| GPU-10 | 6 | PyBullet ROCm OpenGL/EGL |
| GPU-11 | 6 | ROCm Docker variant |
| GPU-12 | 6 | Apple Metal detection |
| GPU-13 | 6 | MuJoCo Metal on macOS |
| GPU-14 | 6 | TrainingConfig backend "metal" |
| GPU-15 | 6 | HardwareBackend enum (auto/cuda/rocm/metal/intel/cpu) |
| GPU-16 | 6 | Backend selection logged at INFO |
| RENDER-01 | 7 | Non-blocking human render |
| RENDER-02 | 7 | <5ms step() overhead |
| RENDER-03 | 7 | 30 FPS throttle |
| RENDER-04 | 7 | --render-human CLI flag |
| RENDER-05 | 7 | Clean shutdown |
| DIST-01 | 8 | RLlib env registration |
| DIST-02 | 8 | train_rllib() entrypoint |
| DIST-03 | 8 | Multi-GPU single node |
| DIST-04 | 8 | Ray Tune integration |
| DIST-05 | 8 | Checkpoint compatibility |
| DIST-06 | 8 | [distributed] extra |
| ROS2-01 | 9 | joint_states publisher |
| ROS2-02 | 9 | command subscriber |
| ROS2-03 | 9 | Trajectory replay at reduced speed |
| ROS2-04 | 9 | Real/sim switch at runtime |
| ROS2-05 | 9 | ros2-bridge CLI command |
| ROS2-06 | 9 | [ros2] optional deps |

**Coverage:** 33 requirements → 4 phases. All mapped ✓

---

## Dependencies

| Phase | Depends on | Reason |
|-------|-----------|--------|
| 7 (Rendering) | Phase 6 (GPU) | GPU context setup required before non-blocking renderer |
| 8 (Distributed) | Phase 7 (Rendering) | Distributed eval needs stable rendering; also GPU detection |
| 9 (ROS2) | — | Independent; can be reordered if needed |

**Suggested execution order:** 6 → 7 → 8 → 9

---

## Notes

- **Optional dependency groups** are the primary mechanism for Ray and ROS2 so core install stays lightweight.
- **ROS2 is Linux-only** by design; macOS bridge code should detect platform and warn.
- **Ray 2.10+** requires Python ≥3.9; compatible with our ≥3.10 floor.
- **GPU detection** should use `torch.cuda.is_available()` as fallback when CUDA toolkit is not present but PyTorch is.
- Every phase has 5–6 success criteria that are observable user behaviors, not implementation details.

---
*Roadmap created: 2026-05-02*  
*Phases: 6–9 | Requirements: 22 | Next: `/gsd-discuss-phase 6`*

# Roadmap: Surg-RL v0.2.0

**Milestone:** v0.2.0 — Scaling, Rendering & Real Robot  
**Goal:** Scale beyond single-GPU training, add real-time 3D rendering, and bridge to real hardware  
**Phases:** 4 (6–9) **Requirements:** 22 (v1)  
**Estimated effort:** 3–4 hours

---

## Phases

### Phase 6: GPU Acceleration (6 plans)

**Goal:** Detect CUDA, enable GPU renderers, and make the Docker image GPU-ready.

**Requirements mapped:** GPU-01 through GPU-05

**Success criteria:**
1. `surg-rl version --verbose` displays GPU availability (CUDA version, renderer type)
2. MuJoCo `mujoco.MjrContext` or `mujoco.Renderer` uses GPU context without crashes
3. PyBullet warns with a single log line when `gpu_accelerated=True` but no GPU is present
4. `docker build --build-arg CUDA_BASE=nvidia/cuda:12.2.0-runtime-ubuntu22.04` produces a GPU-enabled image
5. `TrainingConfig(gpu_accelerated=True)` is accepted and propagated to simulator constructors
6. Tests verify graceful degradation when CUDA is absent (no hard dependency on GPU)

### Phase 7: Real-time Rendering (6 plans)

**Goal:** Add live, non-blocking 3D rendering during RL training without interfering with the training loop.

**Requirements mapped:** RENDER-01 through RENDER-05

**Success criteria:**
1. `env.reset(render_mode="human")` opens a window that survives subsequent `reset()` calls
2. `env.step()` returns in <5ms regardless of render state (measured on MuJoCo soft-body scene)
3. Render FPS is throttled; CPU/GPU utilization does not spike unbounded
4. `surg-rl train --render-human` opens a viewer that shows the current scene live
5. `env.close()` and `SIGINT` (Ctrl+C) terminate the viewer without segfaults or zombie windows
6. `render_mode="rgb_array"` still returns correct NumPy arrays when not in human mode

### Phase 8: Distributed Training with Ray/RLlib (6 plans)

**Goal:** Enable multi-GPU and multi-node training via Ray Tune + RLlib while keeping SB3 as the default path.

**Requirements mapped:** DIST-01 through DIST-06

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
| GPU-01 | 6 | version --verbose shows GPU |
| GPU-02 | 6 | MuJoCo GPU renderer |
| GPU-03 | 6 | PyBullet GPU flag + warn |
| GPU-04 | 6 | nvidia-docker variant |
| GPU-05 | 6 | TrainingConfig flag |
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

**Coverage:** 22 requirements → 4 phases. All mapped ✓

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

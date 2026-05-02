# Requirements: Surg-RL v0.2.0

**Defined:** 2026-05-02
**Completed:** — (milestone in progress)
**Status:** Defining

## v1 Requirements

### GPU Acceleration (GPU)

- [ ] **GPU-01**: System detects CUDA availability and advertises it in `surg-rl version --verbose`
- [ ] **GPU-02**: MuJoCo simulator uses `mujoco.Renderer(..., gl_context)` with GPU backend when available
- [ ] **GPU-03**: PyBullet simulator accepts `gpu_accelerated=True` flag and warns gracefully if unavailable
- [ ] **GPU-04**: Docker image includes `nvidia-docker` runtime variant and build arg for CUDA base image
- [ ] **GPU-05**: `TrainingConfig` has `gpu_accelerated: bool = False` flag wired to simulator construction

### Real-time Rendering (RENDER)

- [ ] **RENDER-01**: `BaseSimulator.render(mode="human")` creates a non-blocking window that survives `reset()`
- [ ] **RENDER-02**: `SurgicalEnv.step()` does not block when `render_mode="human"` is active
- [ ] **RENDER-03**: Render FPS is throttled to a configurable target (default 30 FPS) to avoid GPU starvation
- [ ] **RENDER-04**: `surg_rl.cli train` accepts `--render-human` flag that opens a live viewer
- [ ] **RENDER-05**: Viewer window closes cleanly on `env.close()` and SIGINT without segfault

### Distributed Training (DIST)

- [ ] **DIST-01**: `SurgicalEnv` wrapped as `ray.rllib.env.env_context` compatible class
- [ ] **DIST-02**: `surg_rl.rl.rllib` module provides `train_rllib(config)` entrypoint with PPO/SAC support
- [ ] **DIST-03**: Multi-GPU training configuration works out-of-the-box on a single node with 2+ GPUs
- [ ] **DIST-04**: Ray Tune integration for hyperparameter search over scene definitions and reward weights
- [ ] **DIST-05**: Checkpoint format is compatible between SB3 and RLlib (or documented migration path exists)
- [ ] **DIST-06**: `pyproject.toml` adds `[distributed]` extra with `ray[rllib]>=2.10`, `tune-sklearn`

### ROS2 Bridge (ROS2)

- [ ] **ROS2-01**: `surg_rl.ros2.publisher` publishes robot joint_states at simulation frequency
- [ ] **ROS2-02**: `surg_rl.ros2.subscriber` receives action commands and injects them as external actions
- [ ] **ROS2-03**: Trajectory replay from saved SB3/RLlib checkpoints executes on real robot at reduced speed
- [ ] **ROS2-04**: State synchronization mode switches between simulation-only and real-robot modes at runtime
- [ ] **ROS2-05**: `surg-rl ros2-bridge` CLI command starts publisher/subscriber nodes with configurable topics
- [ ] **ROS2-06**: `pyproject.toml` adds `[ros2]` extra with `rclpy>=6.0`, `geometry_msgs`, `sensor_msgs`

## v2 Requirements

### Deployment & Infra

- **DEP-01**: Kubernetes manifests for Ray cluster deployment on cloud providers
- **DEP-02**: Multi-platform Docker builds (linux/amd64 + linux/arm64) via `docker buildx`
- **DEP-03**: Helm chart for cloud-native surg-rl deployment with auto-scaling

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-user networked surgery | Single-agent research scope; ROS2 handles robot-to-PC, not PC-to-PC |
| Unity/Unreal rendering backends | MuJoCo/PyBullet rendering is sufficient for research validation |
| FDA/medical-grade certification | Research tool, not clinical device |
| Mobile app or web dashboard | Library-first; external tools can wrap the CLI |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| GPU-01 | Phase 6 | Pending |
| GPU-02 | Phase 6 | Pending |
| GPU-03 | Phase 6 | Pending |
| GPU-04 | Phase 6 | Pending |
| GPU-05 | Phase 6 | Pending |
| RENDER-01 | Phase 7 | Pending |
| RENDER-02 | Phase 7 | Pending |
| RENDER-03 | Phase 7 | Pending |
| RENDER-04 | Phase 7 | Pending |
| RENDER-05 | Phase 7 | Pending |
| DIST-01 | Phase 8 | Pending |
| DIST-02 | Phase 8 | Pending |
| DIST-03 | Phase 8 | Pending |
| DIST-04 | Phase 8 | Pending |
| DIST-05 | Phase 8 | Pending |
| DIST-06 | Phase 8 | Pending |
| ROS2-01 | Phase 9 | Pending |
| ROS2-02 | Phase 9 | Pending |
| ROS2-03 | Phase 9 | Pending |
| ROS2-04 | Phase 9 | Pending |
| ROS2-05 | Phase 9 | Pending |
| ROS2-06 | Phase 9 | Pending |

**Coverage:**
- v1 requirements: 22 total
- Mapped to phases: 22
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-02*
*Last updated: 2026-05-02 after milestone initialization*

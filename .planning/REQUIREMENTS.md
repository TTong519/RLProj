# Requirements: Surg-RL v0.2.0

**Defined:** 2026-05-02
**Completed:** 2026-05-03
**Status:** Complete — milestone v0.2.0 shipped

## v1 Requirements

### Hardware Acceleration (GPU)

**CUDA (NVIDIA):**
- [x] **GPU-01**: System detects CUDA availability and advertises it in `surg-rl version --verbose`
- [x] **GPU-02**: MuJoCo simulator uses `mujoco.Renderer(..., gl_context)` with GPU backend when available
- [x] **GPU-03**: PyBullet simulator accepts `gpu_accelerated=True` flag and warns gracefully if unavailable
- [x] **GPU-04**: Docker image includes `nvidia-docker` runtime variant and build arg for CUDA base image
- [x] **GPU-05**: `TrainingConfig` has `gpu_accelerated: bool = False` flag wired to simulator construction

**Intel oneAPI / XPU:**
- [x] **GPU-06**: System detects Intel oneAPI / XPU availability (`sycl-ls`, `dpctl`, or `torch.xpu`) and advertises it
- [x] **GPU-07**: MuJoCo falls back to OSMesa/CPU on Intel if no GPU context is available; oneAPI path is documented even if not implemented
- [x] **GPU-08**: `TrainingConfig` backend selector supports `"intel"` as a valid enum value with graceful CPU fallback

**AMD ROCm / HIP:**
- [x] **GPU-09**: System detects AMD ROCm (`rocminfo`, `torch.cuda` with HIP visible) and advertises it
- [x] **GPU-10**: PyBullet accepts `backend="rocm"` and maps to ROCm-compatible OpenGL / EGL; warns if unavailable
- [x] **GPU-11**: Docker image includes build arg for ROCm base image (`rocm/dev-ubuntu-22.04`)

**Apple Metal:**
- [x] **GPU-12**: System detects Apple Metal (`torch.backends.mps.is_available()` or `metal` GPU family) on macOS and advertises it
- [x] **GPU-13**: MuJoCo on macOS uses Metal-backed `mjrContext` when available; falls back to NS/OpenGL
- [x] **GPU-14**: `TrainingConfig` backend selector supports `"metal"` as a valid enum value

**Unified Backend:**
- [x] **GPU-15**: `HardwareBackend` enum covers `auto`, `cuda`, `rocm`, `metal`, `intel`, `cpu`; `"auto"` tries all in priority order
- [x] **GPU-16**: Backend selection is logged at INFO level so users know which path is active

### Real-time Rendering (RENDER)

- [x] **RENDER-01**: `BaseSimulator.render(mode="human")` creates a non-blocking window that survives `reset()`
- [x] **RENDER-02**: `SurgicalEnv.step()` does not block when `render_mode="human"` is active
- [x] **RENDER-03**: Render FPS is throttled to a configurable target (default 30 FPS) to avoid GPU starvation
- [x] **RENDER-04**: `surg_rl.cli train` accepts `--render-human` flag that opens a live viewer
- [x] **RENDER-05**: Viewer window closes cleanly on `env.close()` and SIGINT without segfault

### Distributed Training (DIST)

- [x] **DIST-01**: `SurgicalEnv` wrapped as `ray.rllib.env.env_context` compatible class
- [x] **DIST-02**: `surg_rl.rl.rllib` module provides `train_rllib(config)` entrypoint with PPO/SAC support
- [x] **DIST-03**: Multi-GPU training configuration works out-of-the-box on a single node with 2+ GPUs
- [x] **DIST-04**: Ray Tune integration for hyperparameter search over scene definitions and reward weights
- [x] **DIST-05**: Checkpoint format is compatible between SB3 and RLlib (or documented migration path exists)
- [x] **DIST-06**: `pyproject.toml` adds `[distributed]` extra with `ray[rllib]>=2.10`, `tune-sklearn`

### ROS2 Bridge (ROS2)

- [x] **ROS2-01**: `surg_rl.ros2.publisher` publishes robot joint_states at simulation frequency
- [x] **ROS2-02**: `surg_rl.ros2.subscriber` receives action commands and injects them as external actions
- [x] **ROS2-03**: Trajectory replay from saved SB3/RLlib checkpoints executes on real robot at reduced speed
- [x] **ROS2-04**: State synchronization mode switches between simulation-only and real-robot modes at runtime
- [x] **ROS2-05**: `surg-rl ros2-bridge` CLI command starts publisher/subscriber nodes with configurable topics
- [x] **ROS2-06**: `pyproject.toml` adds `[ros2]` extra with `rclpy>=6.0`, `geometry_msgs`, `sensor_msgs`

## v2 Requirements

### Deployment & Infra

- **DEP-01**: Kubernetes manifests for Ray cluster deployment on cloud providers
- **DEP-02**: Multi-platform Docker builds (linux/amd64 + linux/arm64) via `docker buildx`
- **DEP-03**: Helm chart for cloud-native surg-rl deployment with auto-scaling

### Advanced Acceleration

- **ACC-01**: DirectML backend for Windows training (deferred; Windows not primary target)
- **ACC-02**: Vulkan compute backend for cross-platform GPU (deferred; niche use case)

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
| GPU-01 | Phase 6 | Complete |
| GPU-02 | Phase 6 | Complete |
| GPU-03 | Phase 6 | Complete |
| GPU-04 | Phase 6 | Complete |
| GPU-05 | Phase 6 | Complete |
| GPU-06 | Phase 6 | Complete |
| GPU-07 | Phase 6 | Complete |
| GPU-08 | Phase 6 | Complete |
| GPU-09 | Phase 6 | Complete |
| GPU-10 | Phase 6 | Complete |
| GPU-11 | Phase 6 | Complete |
| GPU-12 | Phase 6 | Complete |
| GPU-13 | Phase 6 | Complete |
| GPU-14 | Phase 6 | Complete |
| GPU-15 | Phase 6 | Complete |
| GPU-16 | Phase 6 | Complete |
| RENDER-01 | Phase 7 | Complete |
| RENDER-02 | Phase 7 | Complete |
| RENDER-03 | Phase 7 | Complete |
| RENDER-04 | Phase 7 | Complete |
| RENDER-05 | Phase 7 | Complete |
| DIST-01 | Phase 8 | Complete |
| DIST-02 | Phase 8 | Complete |
| DIST-03 | Phase 8 | Complete |
| DIST-04 | Phase 8 | Complete |
| DIST-05 | Phase 8 | Complete |
| DIST-06 | Phase 8 | Complete |
| ROS2-01 | Phase 9 | Complete |
| ROS2-02 | Phase 9 | Complete |
| ROS2-03 | Phase 9 | Complete |
| ROS2-04 | Phase 9 | Complete |
| ROS2-05 | Phase 9 | Complete |
| ROS2-06 | Phase 9 | Complete |

**Coverage:**
- v1 requirements: 33 total
- Mapped to phases: 33
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-02*
*Last updated: 2026-05-02 after milestone initialization*

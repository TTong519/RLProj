# Research Summary: v0.3.0 — Production & Cross-Platform

**Project:** Surg-RL
**Researched:** 2026-05-03
**Confidence:** HIGH
**Milestone:** v0.3.0

## Executive Summary

The codebase is at 775 tests, 9 phases shipped, 33/33 requirements validated. v0.3.0 adds production deployment infrastructure, real-hardware ROS2 integration, and Apple Silicon Metal GPU compute. All four feature areas are at **ZERO implementation** — this is a build-from-scratch milestone.

## Key Findings

### Kubernetes (zero implementation)
- No K8s artifacts exist. No manifests, Helm charts, or KubeRay config.
- RLlib `ray.init()` hardcodes local mode (`src/surg_rl/rl/rllib/train.py:59`) — needs `RAY_ADDRESS` support.
- ROS2 DDS multicast is a known K8s networking pain point.
- GPU scheduling via node selectors needs code awareness.

### Multi-arch Docker (amd64 only)
- Three Dockerfiles exist — all `linux/amd64` only, no `--platform` flags.
- CPU Dockerfile (`python:3.11-slim`) is already multi-arch capable.
- CUDA Dockerfile uses `nvidia/cuda:12.2.0` (no arm64 variant for that exact tag).
- No image push in CI/release workflows.
- ROS2 Humble apt packages support arm64 — feasible.

### ros2_control (zero implementation)
- No code exists. Phase 9 explicitly deferred ros2_control for raw pub/sub.
- Implementation would need `hardware_interface.SystemInterface` subclass.
- Python `hardware_interface` wrappers are less performant than C++ path.
- URDFs from `scene_builder` would need `<ros2_control>` tags injected.
- Linux-only (macOS guard already exists at `src/surg_rl/ros2/__init__.py:24`).

### ROS2 Launch Files (zero implementation)
- No `.launch.py` files exist. No `launch_ros` imports.
- **Critical conflict:** pip-installable package vs colcon workspace layout. `ros2 launch` expects a colcon workspace.
- Workaround: ship launch files in the package, document `ROS_PACKAGE_PATH` fallback.
- `TrajectoryReplay.__init__()` creates its own `rclpy` node — needs refactoring for launch composition.

### Metal MPS Compute (detection = DONE, compute = MISSING)
- `HardwareBackend.metal` enum exists. `_has_metal()` detection works (`src/surg_rl/utils/gpu.py:88`).
- SB3 `TrainingConfig.device="auto"` only checks CUDA → CPU path. `"mps"` string in docstring but never resolved.
- `RllibConfig.from_training_config()` only checks `torch.cuda.device_count()` — no Metal awareness.
- ~80% PyTorch ops are MPS-native. SB3 `MlpPolicy` architectures should work.
- MPS is 2-4x slower than CUDA on equivalent hardware — expectations need management.

### macOS xfail Removal (10 markers, 6 XPASS)
- 6 PyBullet soft-body xfails: all produce **XPASS** on macOS (they already work).
- 2 macOS-only skipifs (Metal detection, rendering) — correct, should stay.
- 1 ROS2 guard — functionally correct (macOS has no rclpy).
- Root cause of XPASS xfails: PyBullet soft body intermittent on CI runners.

## Stack Additions Needed

| Area | Add | Why |
|------|-----|-----|
| K8s | `kubernetes` Python client, Helm/Kustomize, KubeRay operator | Deployment manifests + Ray on K8s |
| Multi-arch | `docker buildx`, QEMU, GHCR push action | arm64 builds |
| ros2_control | `ros2_control`, `ros2_controllers` apt packages | hardware_interface impl |
| Launch | `launch_ros` apt package | .launch.py composition |
| Metal MPS | `torch >= 2.3` (already in [vision] extra) | MPS device for SB3 + RLlib |
| macOS CI | `macos-latest` runner, `mjpython` | Test parity |

## Phase Ordering Suggestion

1. **Metal MPS first** — small code footprint (device resolution + config), unblocks macOS CI, foundation for test parity.
2. **macOS xfail removal** — requires macOS CI runner + Metal compute stable.
3. **Multi-arch Docker** — depends on Metal for arm64 macOS-native images.
4. **ROS2 launch + ros2_control** — Linux-only, independent of above.
5. **Kubernetes** — depends on multi-arch Docker images + RLlib K8s awareness.

---

*Research completed: 2026-05-03*
*Ready for roadmap: yes*

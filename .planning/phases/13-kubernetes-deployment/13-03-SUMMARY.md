# 13-03 Summary: ROS2 Bridge Sidecar

**Plan:** 13-03-PLAN.md
**Status:** Complete
**Commits:** 1

## Accomplishments

- Updated `k8s/base/training-job.yaml` with ROS2 bridge sidecar:
  - `shareProcessNamespace: true` for bridge/trainer communication
  - `wait-for-bridge` initContainer with busybox nc health check
  - Bridge container: `ghcr.io/surg-rl/surg-rl-ros2:v0.3.0`, port 9090
  - Trainer: `SURGRL_BRIDGE_SIDECAR=true` env var
- Created `Dockerfile.ros2`: `ros:humble-ros-base` + surg-rl `[ros2]` extras
  - amd64-only (ROS2 apt packages), system deps matching CPU Dockerfile
- Added `SURGRL_BRIDGE_SIDECAR` detection to `SurgicalEnv._setup_bridge()`
  - Checks `os.environ.get("SURGRL_BRIDGE_SIDECAR") == "true"`
  - Logs "bridge runs as K8s sidecar, skipping in-process spawn"

## Self-Check: PASSED

- Sidecar container present in Job spec
- initContainer waits for bridge readiness
- Dockerfile.ros2 syntax header + ros:humble-ros-base + [ros2] extras
- SurgicalEnv skips in-process bridge spawn when sidecar detected

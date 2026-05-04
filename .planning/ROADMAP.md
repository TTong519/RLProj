# Roadmap: Surg-RL v0.3.0

**Milestone:** v0.3.0 — Production & Cross-Platform
**Defined:** 2026-05-03
**Phases:** 10–13
**Requirements:** 23 total

## Phase Dependency Graph

```
Phase 10 (Metal MPS + macOS) ──► Phase 11 (Multi-arch Docker) ──► Phase 13 (Kubernetes)
                                      │
Phase 12 (ros2_control + Launch) ─────┘ (parallel)
```

Phase 12 is Linux-only and independent of Phases 10–11. Phase 13 requires both Phase 11 (Docker images) and Phase 10 (Metal-aware RLlib config for K8s `RAY_ADDRESS`).

---

## Phase 10: Metal GPU Compute + macOS Test Parity

**Goal:** Wire PyTorch MPS backend into the RL training pipeline on Apple Silicon, and achieve macOS test parity by removing all feasible xfail/skip markers with a macOS CI runner.

**Requirements mapped:** METAL-01, METAL-02, METAL-03, MACOS-01, MACOS-02, MACOS-03, MACOS-04

**Success criteria:**
1. `surg-rl train --device auto` on Apple Silicon uses MPS backend and logs "Using Metal MPS backend (unified memory: XX GB)" at INFO level
2. Unsupported MPS ops fall back to CPU with a single warning; training completes without crash
3. `macos-latest` CI runner passes all non-ROS2 tests (same set as ubuntu-latest minus Linux-only)
4. Zero `@pytest.mark.xfail(sys.platform in ("darwin",)...)` markers remain on soft-body tests
5. Viewer tests pass under `mjpython` auto-detection on macOS CI

**Plans:**
- [ ] 10-01-PLAN.md — MPS device resolution + SB3/RLlib wiring
- [ ] 10-02-PLAN.md — MPS logging, fallback, and Metal-specific tests
- [ ] 10-03-PLAN.md — macOS CI runner + mjpython integration
- [ ] 10-04-PLAN.md — Remove xfail markers, validate soft-body test stability

---

## Phase 11: Multi-platform Docker

**Goal:** Build and publish multi-architecture Docker images (amd64 + arm64) for CPU and CUDA workloads, with cross-arch build verification in CI and GHCR push on release tags.

**Requirements mapped:** DOCKR-01, DOCKR-02, DOCKR-03, DOCKR-04

**Success criteria:**
1. `docker buildx build --platform linux/amd64,linux/arm64` succeeds for the CPU Dockerfile
2. `Dockerfile.cuda` builds amd64; `Dockerfile.jetson` builds arm64 with JetPack base
3. `v0.3.0` git tag triggers GHCR push with `ghcr.io/.../surg-rl:v0.3.0` multi-arch manifest
4. CI `docker buildx` step verifies cross-arch builds on every PR

**Plans:**
- [ ] 11-01-PLAN.md — Multi-arch CPU + CUDA Dockerfiles (buildx + QEMU)
- [ ] 11-02-PLAN.md — Jetson arm64 Dockerfile + architecture-conditional FROM
- [ ] 11-03-PLAN.md — CI buildx verification + release workflow GHCR push

---

## Phase 12: ros2_control + ROS2 Launch Files

**Goal:** Implement ros2_control `hardware_interface` integration so the simulator can participate in a controller manager lifecycle, and provide ROS2 `.launch.py` files that compose the full bridge + replay + simulator stack with configurable arguments.

**Requirements mapped:** R2CTL-01, R2CTL-02, R2CTL-03, R2CTL-04, LAUNCH-01, LAUNCH-02, LAUNCH-03

**Success criteria:**
1. `SystemInterface` subclass reads joint position/velocity from `BaseSimulator` and writes commands via `inject_external_action()`; registers with `controller_manager`
2. URDFs from `scene_builder` contain `<ros2_control>` tags with `command_interface` and `state_interface` entries
3. `surg-rl ros2-control --controller-yaml config.yaml` starts bridge, spawns `joint_trajectory_controller`, and responds to trajectory commands
4. `ros2 launch surg_rl bridge.launch.py scene:=path/to/scene.json` composes bridge, replay, and simulator nodes
5. Launch files work from both a colcon workspace (`ros2 launch`) and a pip install (`ROS_PACKAGE_PATH=src ros2 launch`)

**Plans:**
- [ ] 12-01-PLAN.md — SystemInterface subclass + controller manager lifecycle
- [ ] 12-02-PLAN.md — URDF ros2_control tag injection in scene_builder
- [ ] 12-03-PLAN.md — CLI ros2-control command + controller YAML config
- [ ] 12-04-PLAN.md — .launch.py files for bridge + replay + simulator composition
- [ ] 12-05-PLAN.md — pip vs colcon workflow compatibility + launch arguments
- [ ] 12-06-PLAN.md — Test suite (mocked ros2_control + launch tests)

---

## Phase 13: Kubernetes Deployment

**Goal:** Provide production-ready K8s manifests for running RL training jobs, Ray RLlib clusters, and ROS2 bridge sidecars with ConfigMap/Secrets injection and persistent checkpoint storage.

**Requirements mapped:** K8S-01, K8S-02, K8S-03, K8S-04, K8S-05

**Success criteria:**
1. `kubectl apply -f k8s/training-job.yaml` creates a Job that runs `surg-rl train` with GPU node selector; Job completes and checkpoints persist to PVC
2. KubeRay `RayCluster` manifest references the multi-arch Docker image; `ray.init(address="auto")` discovers the Ray head via `RAY_ADDRESS` env var
3. Training pod includes a `ros2-bridge` sidecar container; bridge publishes JointState to the pod's shared network namespace
4. Scene definition JSON mounts from ConfigMap; API keys mount from Secret; neither appears in pod spec or logs
5. Checkpoint PVC survives pod deletion; a second Job with the same PVC resumes from the latest checkpoint

**Plans:**
- [ ] 13-01-PLAN.md — Training Job + GPU node selectors + resource limits
- [ ] 13-02-PLAN.md — KubeRay RayCluster + RAY_ADDRESS env var wiring
- [ ] 13-03-PLAN.md — ROS2 bridge sidecar container in training pod
- [ ] 13-04-PLAN.md — ConfigMap + Secrets + PVC manifests
- [ ] 13-05-PLAN.md — RLlib K8s-aware config (ray.init(address="auto")) + CI kind integration tests

---

## Summary

| Phase | Plans | Requirements | Depends On |
|-------|-------|-------------|------------|
| 10 (Metal + macOS) | 4 | METAL-01..03, MACOS-01..04 | None |
| 11 (Multi-arch Docker) | 3 | DOCKR-01..04 | Phase 10 |
| 12 (ros2_control + Launch) | 6 | R2CTL-01..04, LAUNCH-01..03 | None (Linux-only, parallel) |
| 13 (Kubernetes) | 5 | K8S-01..05 | Phases 10, 11 |

**Total:** 4 phases, 18 plans, 23 requirements.

---

*Roadmap created: 2026-05-03*

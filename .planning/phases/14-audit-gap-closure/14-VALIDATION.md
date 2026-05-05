# Phase 14 VALIDATION: Audit Gap Closure

**Phase:** 14 | **Milestone:** v0.3.1 | **Date:** 2026-05-04

## Requirements Coverage

| Requirement | Description | Status | Test Coverage |
|-------------|-------------|--------|---------------|
| GAP-01 | Dockerfile.ros2 built & pushed to GHCR in release.yml | COVERED | test_release_has_ros2_build |
| GAP-02 | Trainer uses CUDA image; CPU overlay patches back to CPU | COVERED | test_trainer_cuda_image, test_cpu_overlay_replaces_image |
| GAP-03 | initContainer uses ROS2 topic probe | COVERED | test_init_container_uses_ros2_topic_probe |
| GAP-04 | bridge_node/replay_node console_scripts registered | COVERED | test_pyproject_has_bridge_console_scripts |
| GAP-05 | config.py:_mps_available() imports from gpu._has_metal | COVERED | test_mps_available_delegates_to_has_metal |

### 3-Source Cross-Reference

| Source | Count | Result |
|--------|-------|--------|
| REQUIREMENTS.md traceability | 5/5 | ✓ |
| PLAN.md tasks | 5/5 | ✓ |
| Implemented code | 5/5 | ✓ |

**5/5 requirements satisfied.** No orphans. All three sources agree.

## Nyquist Per Requirement

### GAP-01 — GHCR ROS2 Image

| Dimension | Coverage | Evidence |
|-----------|----------|----------|
| Happy path | ✓ | release.yml:96-113 contains docker meta + build-push-action for Dockerfile.ros2 |
| Platform guard | ✓ | platforms: linux/amd64 (ROS2 not available on arm64/macOS) |
| Image naming | ✓ | ghcr.io/surg-rl/surg-rl/ros2 matches training-job.yaml references |
| Test assertion | ✓ | test_release_has_ros2_build validates docker/metadata-action and build-push-action steps |

### GAP-02 — Trainer CUDA Image + CPU Overlay

| Dimension | Coverage | Evidence |
|-----------|----------|----------|
| Happy path | ✓ | training-job.yaml:40 uses cuda:v0.3.0 as trainer image |
| CPU fallback | ✓ | cpu/kustomization.yaml:32-35 replaces image with CPU surg-rl:v0.3.0 |
| GPU resources preserved | ✓ | GPU overlay inherits base (no patches needed); nvidia.com/gpu: 1 in base |
| Test assertion | ✓ | test_trainer_cuda_image, test_cpu_overlay_replaces_image |

### GAP-03 — ROS2 Topic Probe Health Check

| Dimension | Coverage | Evidence |
|-----------|----------|----------|
| Happy path | ✓ | initContainer uses `ros2 topic list | grep -q surg_rl` |
| Image dependency | ✓ | initContainer uses ros2 image (ghcr.io/surg-rl/surg-rl/ros2:v0.3.0) |
| Retry loop | ✓ | `until ... sleep 2` pattern preserved |
| Test assertion | ✓ | test_init_container_uses_ros2_topic_probe checks command content |

### GAP-04 — Console Scripts

| Dimension | Coverage | Evidence |
|-----------|----------|----------|
| bridge_node | ✓ | pyproject.toml:119: bridge_node = "surg_rl.ros2.bridge_node:main" |
| replay_node | ✓ | pyproject.toml:120: replay_node = "surg_rl.ros2.replay_node:main" |
| Module exists | ✓ | src/surg_rl/ros2/bridge_node.py (L127, L332) and replay_node.py (L33, L49) |
| Platform safety | ✓ | Both modules have dummy main() on non-ROS2 platforms |
| Test assertion | ✓ | test_pyproject_has_bridge_console_scripts |

### GAP-05 — MPS Detection Refactor

| Dimension | Coverage | Evidence |
|-----------|----------|----------|
| Delegation | ✓ | config.py:23: `from surg_rl.utils.gpu import _has_metal` |
| No torch duplication | ✓ | No torch.backends.mps call in config.py |
| Import safety | ✓ | gpu.py has no surg_rl.rl imports (no import cycle) |
| Existing gpu.py tests | ✓ | 13 tests in test_gpu_detector.py already cover _has_metal() |
| Test assertion | ✓ | test_mps_available_delegates_to_has_metal verifies delegation |

## E2E Flow Assessment

| Flow | Status | Notes |
|------|--------|-------|
| Release workflow → GHCR push | ✓ PASS | release.yml builds Dockerfile.ros2 alongside CPU/CUDA |
| K8s Job GPU deployment | ✓ PASS | CUDA image + GPU nodeSelector + resource request |
| K8s Job CPU deployment | ✓ PASS (customize) | CPU overlay removes GPU resources + patches image |
| Bridge sidecar → DDS health check | ✓ PASS | ROS2 topic probe in initContainer using ros2 image |
| ros2 launch → finds executables | ✓ PASS | bridge_node/replay_node in console_scripts |

## Threat Model Verification

| Threat | Mitigation | Status |
|--------|------------|--------|
| ROS2 image not built before initContainer | GAP-01 runs first in CI pipeline | ✓ |
| bridge_node module doesn't exist | module exists with main() in both branches | ✓ |
| gpu._has_metal() import cycle | gpu.py has no surg_rl.rl imports | ✓ |
| GPU overlay doesn't pick up CUDA image | Base has CUDA image; GPU overlay inherits base | ✓ |
| CPU overlay misses image fallback | CPU overlay patches image back to CPU | ✓ (GAP-02 fix) |

## Nyquist Verdict

| Phase | Requirements | Tests Added | Compliant |
|-------|-------------|-------------|-----------|
| 14 | 5/5 COVERED | 5 new assertions | COMPLIANT ✓ |

**Overall: COMPLIANT** — All 5 requirements have affirmative test assertions. No coverage gaps.

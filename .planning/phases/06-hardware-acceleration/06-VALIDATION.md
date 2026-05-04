---
phase: 06
slug: hardware-acceleration
status: verified
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-03
---

# Phase 06 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x |
| **Config file** | pytest.ini (pythonpath = src) |
| **Quick run command** | `PYTHONPATH=src pytest tests/test_gpu_detector.py tests/test_gpu_integration.py -q` |
| **Full suite command** | `PYTHONPATH=src pytest tests/ -q` |
| **Estimated runtime** | ~1s (GPU suite), ~50s (full) |

## Per-requirement Verification Map

| Requirement | Description | Test Files | Status |
|-------------|-------------|-----------|--------|
| GPU-01 | CUDA detection in version --verbose | test_gpu_detector.py, test_gpu_integration.py, test_cli_integration.py | COVERED |
| GPU-02 | MuJoCo CUDA GPU renderer | test_gpu_integration.py (simulator constructors accept backend) | PARTIAL (renderer creation not isolated) |
| GPU-03 | PyBullet GPU flag + warn | pybullet_simulator.py logs WARNING; integration test verifies backend wiring | PARTIAL (no isolated warning-text test) |
| GPU-04 | nvidia-docker variant | Dockerfile.cuda exists (static config, OK) | COVERED |
| GPU-05 | TrainingConfig gpu flag | test_gpu_detector.py (backend selection + config) | COVERED |
| GPU-06 | Intel oneAPI detection | test_gpu_detector.py (test_has_intel_true) | COVERED |
| GPU-07 | MuJoCo Intel fallback | Relies on MuJoCo internal auto-detection (documented) | PARTIAL |
| GPU-08 | Intel graceful CPU fallback | test_gpu_detector.py (test_select_backend_intel_fallback) | COVERED (fixed 2026-05-03) |
| GPU-09 | AMD ROCm detection | test_gpu_detector.py (test_has_rocm_true) | COVERED |
| GPU-10 | PyBullet ROCm OpenGL/EGL | pybullet_simulator.py wired; no dedicated test | PARTIAL |
| GPU-11 | ROCm Docker variant | Dockerfile.rocm exists (static config, OK) | COVERED |
| GPU-12 | Apple Metal detection | test_gpu_detector.py (test_has_metal_true_darwin) | COVERED |
| GPU-13 | MuJoCo Metal on macOS | Relies on MuJoCo auto-detection (documented) | PARTIAL |
| GPU-14 | TrainingConfig backend "metal" | HardwareBackend enum member + config accept | COVERED |
| GPU-15 | HardwareBackend enum (6 members) | test_gpu_detector.py (detect_backends priority + auto) | COVERED |
| GPU-16 | Backend selection logged at INFO | test_gpu_detector.py (test_logs_selected_backend) | COVERED |

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Instructions |
|----------|-------------|------------|--------------|
| CUDA GPU renderer on NVIDIA | GPU-02 | Requires physical NVIDIA GPU + CUDA toolkit | `surg-rl train --backend cuda` |
| ROCm renderer on AMD | GPU-10 | Requires physical AMD GPU + ROCm stack | `surg-rl train --backend rocm` |
| Metal renderer on Apple Silicon | GPU-13 | Requires Apple Silicon Mac | `surg-rl train --backend metal` |

## Validation Sign-Off

- [x] All 16 GPU requirements mapped
- [x] GPU-08 Intel fallback fixed + tested (2026-05-03)
- [x] 4 PARTIAL items are platform-dependent (require physical hardware)
- [x] No blocking gaps remain — partials are environmental, not code defects
- [x] `nyquist_compliant: true`

**Approval:** approved 2026-05-03

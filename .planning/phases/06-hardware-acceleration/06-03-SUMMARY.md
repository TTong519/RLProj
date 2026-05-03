---
phase: 06-hardware-acceleration
plan: 03
subsystem: docker + tests
requires:
  - 06-01
  - 06-02
provides:
  - Dockerfile.cuda
  - Dockerfile.rocm
  - test_gpu_detector.py
  - test_gpu_integration.py
key-files.created:
  - Dockerfile.cuda
  - Dockerfile.rocm
  - tests/test_gpu_detector.py
  - tests/test_gpu_integration.py
key-decisions:
  - Dockerfiles use validated Ubuntu 22.04 packages (libgl1, not libgl1-mesa-glx)
  - Unit tests mock subprocess (CI-friendly)
  - Integration tests skip when no physical GPU present
  - lru_cache cleared between tests via autouse fixture
requirements-completed:
  - GPU-04
  - GPU-11
  - GPU-16
duration: 20 min
completed: 2026-05-02
---

# Phase 06 Plan 03: Dockerfiles and GPU tests

## Summary

Created vendor-specific Docker images and tests:
- **Dockerfile.cuda**: NVIDIA CUDA 12.2 runtime, Ubuntu 22.04, python3.11
- **Dockerfile.rocm**: AMD ROCm dev image, rocminfo included
- **test_gpu_detector.py**: 16 unit tests with mocked subprocess covering all backends
- **test_gpu_integration.py**: 7 integration tests (5 passed, 2 skipped — no physical CUDA/ROCm)

## Deviations from Plan

1. **lru_cache cross-contamination**: detector unit tests mocked `_has_*` functions, polluting the cache for integration tests. Fixed by adding `autouse` fixture to clear cache in integration tests.

## Next

Phase 7: Real-time Rendering.

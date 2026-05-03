---
phase: 06-hardware-acceleration
plan: 01
subsystem: schema + gpu detection + config
requires: []
provides:
  - HardwareBackend enum
  - gpu.py detection module
  - TrainingConfig.backend field
  - Settings.gpu_backend field
  - CLI --backend option
key-files.created:
  - src/surg_rl/utils/gpu.py
key-files.modified:
  - src/surg_rl/scene_definition/schema.py
  - src/surg_rl/rl/training.py
  - src/surg_rl/utils/config.py
  - src/surg_rl/cli.py
key-decisions:
  - HardwareBackend as str,Enum (serializes to string automatically)
  - detect_backends returns tuple (immutable, cache-safe)
  - select_backend logs INFO and raises RuntimeError for unavailable explicit backends
requirements-completed:
  - GPU-05
  - GPU-06
  - GPU-08
  - GPU-09
  - GPU-12
  - GPU-14
  - GPU-15
  - GPU-16
duration: 25 min
completed: 2026-05-02
---

# Phase 06 Plan 01: HardwareBackend enum, gpu.py, config/CLI wiring

## Summary

Created the foundational hardware backend abstraction:
- **HardwareBackend** enum with 6 members (auto, cuda, rocm, metal, intel, cpu)
- **gpu.py** detection module using `shutil.which` + `subprocess.run` with 5s timeout
- **TrainingConfig** dataclass gains `backend: HardwareBackend = HardwareBackend.auto`
- **Settings** pydantic model gains `gpu_backend: str = "auto"`
- **CLI** `train()` gains `--backend` option; `version --verbose` prints GPU availability table

## Deviations from Plan

None — plan executed exactly as written.

## Next

Plan 02: Wire backend into simulators and enhance version --verbose.

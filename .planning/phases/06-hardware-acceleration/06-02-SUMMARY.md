---
phase: 06-hardware-acceleration
plan: 02
subsystem: simulators + cli
requires:
  - 06-01
provides:
  - Backend-aware simulators
  - version --verbose GPU table
key-files.modified:
  - src/surg_rl/simulators/base_simulator.py
  - src/surg_rl/simulators/mujoco_simulator.py
  - src/surg_rl/simulators/pybullet_simulator.py
  - src/surg_rl/cli.py
key-decisions:
  - BaseSimulator accepts backend kwarg (last positional, non-breaking)
  - MuJoCo does NOT add gl_context to Renderer (auto-detected per RESEARCH.md)
  - PyBullet logs WARNING in DIRECT mode when GPU backend requested
requirements-completed:
  - GPU-01
  - GPU-02
  - GPU-03
  - GPU-07
  - GPU-10
  - GPU-13
duration: 15 min
completed: 2026-05-02
---

# Phase 06 Plan 02: Simulator backend wiring + version --verbose

## Summary

Wired backend into both simulator backends:
- **BaseSimulator**: `__init__` accepts `backend` kwarg, stores `self._backend`
- **MuJoCoSimulator**: resolves `_active_backend` at init, logs INFO. No `gl_context` added.
- **PyBulletSimulator**: resolves `_active_backend`, logs WARNING in DIRECT+GPU mode
- **CLI**: `version --verbose` displays Rich table with 5 backends, availability, version info

## Deviations from Plan

None — plan executed exactly as written.

## Next

Plan 03: Dockerfiles and comprehensive tests.

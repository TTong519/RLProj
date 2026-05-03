# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-02)

**Core value:** End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation
**Current focus:** Milestone v0.2.0 — Phase 7 complete, preparing for Phase 8

## Current Position

Phase: 08-distributed-training
Plan: 08-01 through 08-06 (ALL EXECUTED)
Status: Phase 8 complete — 6 plans, 4 commits, 667 tests, 0 failures
Last activity: 2026-05-02 — All 6 plans executed, tested, committed

Progress: [████████████████████████████░░░░░░░░░░] 70%

## Performance Metrics

- **Previous milestone:** v0.1.0 — 12 plans, 43 commits, 607 tests, 33/33 UAT passed
- **Current milestone:** v0.2.0 — Phase 6 complete (628 tests), Phase 7 complete (641 tests, 0 failures), Phase 8 complete (667 tests, 0 failures)
- **Test delta:** +26 new tests (28 new rllib tests, 0 regressions)
- **Phase 8 key stats:**
  - 7 new source files in `src/surg_rl/rl/rllib/`
  - 6 new test files in `tests/test_rllib_*.py`
  - `[distributed]` extra added to `pyproject.toml`
  - 3 new CLI commands: `train-rllib`, `tune`, `checkpoint-inspect`

## Decisions

- GPU acceleration as Phase 6 (foundation for rendering)
- Ray/RLlib as Phase 8 (requires rendering stable + GPU detected)
- ROS2 as Phase 9 (independent, can be reordered)
- K8s and multi-platform Docker deferred to v0.3.0
- v0.2.0 estimated 4–5 hours, 4 phases, 33 requirements
- HardwareBackend(str, Enum) with 6 members (auto/cuda/rocm/metal/intel/cpu)
- detect_backends() returns tuple (immutable, cache-safe)
- select_backend() raises RuntimeError for unavailable explicit backends
- CPU always available as fallback
- No gl_context kwarg on MuJoCo Renderer (auto-detected)
- PyBullet has no explicit GPU flag; warns in DIRECT mode
- Docker packages validated for Ubuntu 22.04 (libgl1 not libgl1-mesa-glx)
- **Phase 7 specific:**
  - render_mode MUST be passed to simulator at construction (especially PyBullet GUI)
  - RenderThread owns FPS throttle (daemon thread + time.sleep)
  - Simulator owns RenderThread lifecycle (start_viewer/stop_viewer)
  - Headless fallback: warn and continue (not error)
  - macOS: RuntimeError with instructions if not using mjpython
  - SIGINT + atexit for clean shutdown
  - render_fps is SurgicalEnvConfig field (not metadata)

## Blockers

- None

## Todos

- [ ] Phase 8: Distributed Training with Ray/RLlib
- [ ] Phase 9: ROS2 Bridge for Real Hardware

---
*Updated: 2026-05-02 — Phase 7 complete, 641 passed, 18 rendering tests*

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-03)

**Core value:** End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation
**Current focus:** Milestone v0.2.0 **COMPLETE** — all 4 phases shipped

## Current Position

Phase: 09-ros2-bridge
Plan: 09-01 through 09-05 + 09.1, 09.2 (ALL EXECUTED)
Status: Phase 9 complete — 7 plans (5 + 2 gap closure), 22 commits, 757 tests, 0 failures
Last activity: 2026-05-03 — All 7 plans executed, tested, committed; all 5 gaps fixed

Progress: [████████████████████████████████████████] 100%

## Performance Metrics

- **Previous milestone:** v0.1.0 — 12 plans, 43 commits, 607 tests, 33/33 UAT passed
- **Current milestone:** v0.2.0 — Phase 6 complete (628 tests), Phase 7 complete (641 tests, 0 failures), Phase 8 complete (674 tests, 0 failures), Phase 9 complete (757 tests, 0 failures)
- **Test delta:** +150 tests (+26 Phase 8, +83 Phase 9)
- **Phase 9 key stats:**
  - 4 new source files in `src/surg_rl/ros2/`
  - 5 new test files in `tests/test_ros2_*.py`
  - `[ros2]` extra added to `pyproject.toml`
  - 2 new CLI commands: `ros2-bridge`, `ros2-replay`
  - 22 commits, 2 gap closure plans

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
- **Phase 8 specific:**
  - Ray/RLlib as optional [distributed] extra with lazy imports
  - New API stack: config.learners() and config.env_runners()
  - build_rllib_config() returns AlgorithmConfig; train_rllib() resolves Algo class separately
  - Checkpoint compatibility: inspection utils + documented migration path
  - Tune search space flat structure for scheduler compatibility
- **Phase 9 specific:**
  - Bridge runs as separate multiprocessing.Process (not daemon thread)
  - IPC via multiprocessing.Queue(maxsize=1) — keep-latest semantics
  - JointState publisher + Float64MultiArray subscriber, configurable in YAML
  - EnvironmentController owns mode flag + get_action() override
  - TrajectoryReplay is self-contained (own env + predict loop), sleep-based throttle
  - macOS: warn + disable at import, CLI exit 0, mock tests, Docker docs
  - [ros2] extra documents apt-only deps (rclpy not on PyPI)

## Blockers

- None

## Todos

- [ ] Phase 8: Distributed Training with Ray/RLlib
- [ ] Phase 9: ROS2 Bridge for Real Hardware

---
*Updated: 2026-05-03 — Phase 9 complete, milestone v0.2.0 shipped*
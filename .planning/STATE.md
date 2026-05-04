# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-03)

**Core value:** End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation
**Current focus:** Defining v0.3.0 requirements — Production & Cross-Platform

## Current Position

Milestone: v0.3.0 — Production & Cross-Platform
Phase: 10 — Metal GPU Compute + macOS Test Parity ✓
Plan: —
Status: Phase 10 complete
Last activity: 2026-05-03 — Phase 10 shipped (4/4 plans, 7/7 reqs)

Progress: ██████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 25% (v0.3.0)

## Performance Metrics

- **v0.1.0:** Phases 1–5, 12 plans, 607 tests, 33/33 UAT passed
- **v0.2.0:** Phases 6–9, 19 plans, 775 tests, 0 failures, 7/7 UAT passed
- **Test delta:** +168 tests (v0.1.0→v0.2.0)

## Decisions

<details>
<summary>v0.2.0 Decisions (click to expand)</summary>

- GPU acceleration as Phase 6 (foundation for rendering)
- Ray/RLlib as Phase 8 (requires rendering stable + GPU detected)
- ROS2 as Phase 9 (independent, can be reordered)
- K8s and multi-platform Docker deferred to v0.3.0
- HardwareBackend(str, Enum) with 6 members (auto/cuda/rocm/metal/intel/cpu)
- Intel backend gracefully falls back to CPU (GPU-08 fix)
- No gl_context kwarg on MuJoCo Renderer (auto-detected)
- RenderThread daemon + time.sleep for FPS throttle
- RLlib 2.55: old API stack disabled by default
- Bridge runs as multiprocessing.Process with multiprocessing.Queue IPC
- Bridge→controller forwarding wired (G-1 fix)
- macOS: ROS2 imports warn + disable gracefully
- [ros2] extra documents apt-only deps (rclpy not on PyPI)
</details>

## Blockers

- None

## Todos

- [ ] Plan v0.3.0 milestone (Kubernetes, multi-platform Docker, ros2_control, ROS2 launch, Metal compute, macOS xfail removal)

---

_Updated: 2026-05-03 — v0.3.0 milestone started_

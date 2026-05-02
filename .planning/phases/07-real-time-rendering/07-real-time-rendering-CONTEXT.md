---
phase: 07-real-time-rendering
plan: discuss
subsystem: rendering
requires:
  - 06-hardware-acceleration
provides:
  - Phase 7 implementation decisions
key-files.created:
  - .planning/phases/07-real-time-rendering/07-real-time-rendering-CONTEXT.md
  - .planning/phases/07-real-time-rendering/07-real-time-rendering-DISCUSSION-LOG.md
key-decisions:
  - Viewer starts eagerly in __init__ (not lazy)
  - Simulator owns RenderThread (start_viewer/stop_viewer)
  - Headless fallback: warn and train without viewer
  - render_fps lives as SurgicalEnvConfig field
requirements-completed:
duration: 10 min
completed: 2026-05-02
---

# Phase 7 Context: Real-time Rendering

**Phase:** 7 — Real-time Rendering
**Milestone:** v0.2.0
**Date:** 2026-05-02
**Status:** Context gathered — ready for planning

## Domain

Add live, non-blocking 3D rendering during RL training without interfering with the training loop. The viewer must survive `reset()`, `step()` must not block, FPS must be throttled, and cleanup must be clean (no segfaults on SIGINT).

## Decisions

### D-01: Viewer Startup Timing — Eager

**Decision:** Start the viewer immediately in `SurgicalEnv.__init__` (right after `load_scene()`), not lazily on first `reset()`.

**Rationale:**
- Matches Gymnasium convention: viewer created at construction time
- Provides instant visual feedback — user sees the window before training starts
- If display is unavailable, failure happens immediately (not one step into training)
- MuJoCo `launch_passive` is designed to be started once and persist across resets

**Implementation note:** `SurgicalEnv.__init__` currently calls `self._simulator.load_scene()` at line 134 but never calls `start_viewer()`. Add `if self.render_mode == "human": self._simulator.start_viewer()` after `load_scene()`.

### D-02: Render Thread Ownership — Simulator

**Decision:** Each simulator backend owns its own render thread. `SurgicalEnv` calls `sim.start_viewer()` / `sim.stop_viewer()` — no threading in the env layer.

**Rationale:**
- MuJoCo needs `launch_passive` + `sync()` in a background thread — backend-specific
- PyBullet GUI is handled by the physics server internally — no-op for us
- Clean separation: env decides *when* to render, simulator decides *how*
- Matches existing pattern: `BaseSimulator` is ABC with `render()`, `close()`; extend with `start_viewer()`, `stop_viewer()`

**Implementation note:**
```python
# BaseSimulator additions
@abstractmethod
def start_viewer(self) -> bool: ...

@abstractmethod  
def stop_viewer(self) -> None: ...

# MuJoCoSimulator.start_viewer()
#   launches launch_passive, spawns RenderThread(daemon=True)
#   RenderThread.run() calls viewer.sync(state_only=True) every 1/render_fps seconds
# PyBulletSimulator.start_viewer()
#   no-op (GUI already rendering); or warn if in DIRECT mode
```

### D-03: Headless Fallback — Warn and Continue

**Decision:** If `--render-human` is passed on a headless server (no display), log a WARNING and continue training in DIRECT/offscreen mode. Do NOT raise an error.

**Rationale:**
- This is a research tool, not an interactive game. Training should never break because there's no monitor.
- CI runs, SSH sessions, and cloud VMs are all headless — erroring would block most remote workflows.
- Warning makes the fallback visible so users know why they don't see a window.

**Implementation note:** Check for display via `_check_renderer_available()` (already exists in MuJoCoSimulator). If false and `render_mode == "human"`: log warning, set `self.render_mode = None`, skip viewer start.

### D-04: FPS Throttle Configuration — Config Field

**Decision:** `render_fps` lives as a field on `SurgicalEnvConfig` (not in `metadata`). Default: `30.0`.

**Rationale:**
- User-configurable at runtime via CLI `--render-fps` flag
- Passed through constructor chain: CLI → `SurgicalEnvConfig` → simulator → `RenderThread`
- Gymnasium `metadata["render_fps"]` is read-only class attribute — not suitable for runtime config
- `SurgicalEnvConfig` is the right place because it's the single source of truth for env behavior

**Implementation note:**
```python
@dataclass
class SurgicalEnvConfig:
    # ... existing fields ...
    render_fps: float = 30.0
```

**CLI addition:** `surg-rl train --scene ... --render-human --render-fps 60`

### D-05: SIGINT/Cleanup — signal + atexit

**Decision:** Register a SIGINT handler on `SurgicalEnv` that calls `self.close()`. Use `atexit` as a backup. RenderThread is a daemon thread.

**Rationale:**
- SIGINT handler must call `env.close()` → `sim.stop_viewer()` → thread join + viewer.close()
- Daemon thread ensures it exits with the main process even if cleanup is missed
- `atexit` catches cases where SIGINT handler is not registered (e.g., spawned in SubprocVecEnv)

**Implementation note:**
```python
def _setup_signal_handlers(self):
    import signal
    import atexit
    
    def _handle_sigint(signum, frame):
        self.close()
        raise KeyboardInterrupt
    
    try:
        signal.signal(signal.SIGINT, _handle_sigint)
    except ValueError:
        pass  # Not on main thread
    
    atexit.register(self.close)
```

### D-06: macOS / mjpython — Runtime Error with Instructions

**Decision:** On macOS, if `mujoco.viewer.launch_passive` fails with a Cocoa threading error, raise `RuntimeError` with a clear message telling the user to use `mjpython` instead of `python`.

**Rationale:**
- `launch_passive` requires the main thread on macOS (Cocoa constraint)
- `mjpython` is bundled with MuJoCo and handles this correctly
- We can't auto-fix it, so we must tell the user exactly what to do

### D-07: PyBullet Human Mode — No-Op with Warning

**Decision:** PyBullet `human` render mode is a no-op at the simulator level (physics server already renders in GUI mode). If the simulator is in DIRECT mode, log a warning.

**Rationale:**
- PyBullet GUI mode renders automatically after each `stepSimulation()`
- There's no separate `sync()` call needed
- If connected in DIRECT mode, there's literally nothing to show — warn the user

## OpenCode's Discretion

- RenderThread implementation details (exact threading primitives, exception handling in thread loop)
- Whether to add a `--no-render-human` flag (default behavior: render only with explicit flag)
- Exact warning wording for headless fallback
- Whether to add a render callback in `TrainingManager` for live viewing during training (beyond env.render)

## Deferred Ideas

- **Web dashboard / remote viewer** — requires networking, HTTP server, WebSocket bridge. Separate phase.
- **Recording video during human render** — can be done with `rgb_array` frames + video writer. Separate phase or backlog.
- **Multi-camera live switching** — advanced UI, out of scope for Phase 7.

## Code Context

### Existing Assets to Reuse
- `MuJoCoSimulator.start_viewer()` — exists but only stubs `launch_passive`, no thread
- `MuJoCoSimulator._viewer` — already defined as `None` in `__init__`
- `SurgicalEnv.metadata` — already has `"render_modes": ["human", "rgb_array"]`, `"render_fps": 30`
- `BaseSimulator.render(mode=...)` — abstract method, already implemented in both backends
- `SurgicalEnv.render()` — already branches on `render_mode`
- `SurgicalEnv.close()` — already calls `self._simulator.close()`
- `SurgicalEnvConfig` — dataclass with `render_mode` field

### What Needs Adding
1. `BaseSimulator.start_viewer()` / `stop_viewer()` — abstract methods
2. `MuJoCoSimulator.start_viewer()` — full implementation with `launch_passive` + `RenderThread`
3. `MuJoCoSimulator.stop_viewer()` — thread join + viewer.close()
4. `MuJoCoSimulator.close()` — call `stop_viewer()` before renderer cleanup
5. `PyBulletSimulator.start_viewer()` / `stop_viewer()` — no-ops (GUI already rendering)
6. `surg_rl/render_thread.py` — generic `RenderThread` class
7. `SurgicalEnvConfig.render_fps` — new field
8. `SurgicalEnv.__init__` — call `start_viewer()` if render_mode == "human"
9. `SurgicalEnv._setup_signal_handlers()` — SIGINT + atexit
10. CLI `train` — add `--render-human` flag
11. CLI `train` — add `--render-fps` flag

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` § RENDER-01..RENDER-05 — Phase 7 requirements
- `.planning/ROADMAP.md` § Phase 7: Real-time Rendering — success criteria

### Research
- `.planning/phases/07-real-time-rendering/07-real-time-rendering-RESEARCH.md` — RESEARCH.md with stack patterns, pitfalls, code examples

### Code (existing)
- `src/surg_rl/rl/environment.py` — `SurgicalEnv`, `SurgicalEnvConfig`
- `src/surg_rl/simulators/base_simulator.py` — `BaseSimulator` ABC
- `src/surg_rl/simulators/mujoco_simulator.py` — `MuJoCoSimulator` with `start_viewer()` stub
- `src/surg_rl/simulators/pybullet_simulator.py` — `PyBulletSimulator` with GUI/DIRECT modes
- `src/surg_rl/cli.py` — training CLI entrypoint

## Dependencies

**Blocks:** Phase 8 (Distributed Training) — Ray Tune eval may use human render for debugging
**Blocked by:** Phase 6 (Hardware Acceleration) — GPU context must be stable before viewer

---

*Context gathered: 2026-05-02*
*Next step: `/gsd-plan-phase 7` or `/gsd-research-phase 7` (research already done)*

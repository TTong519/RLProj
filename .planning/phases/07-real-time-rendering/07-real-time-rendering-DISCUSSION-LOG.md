# Phase 7: Real-time Rendering — Discussion Log

> Audit trail only. Do not use as input to planning, research, or execution agents.  
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-05-02
**Phase:** 07-real-time-rendering
**Mode:** discuss (default)
**Areas discussed:** 4

---

## Assumptions Presented

### Viewer Startup Timing
| Assumption | Confidence | Evidence |
|-----------|-----------|----------|
| Eager startup in __init__ is preferred over lazy | Confirmed (user choice) | Gymnasium convention, matches user expectation of immediate visual feedback |

### Render Thread Ownership
| Assumption | Confidence | Evidence |
|-----------|-----------|----------|
| Simulator owns RenderThread (start_viewer/stop_viewer) | Confirmed (user choice) | Clean separation of concerns; env has no threading today |

### Headless Fallback
| Assumption | Confidence | Evidence |
|-----------|-----------|----------|
| Warn and continue without viewer on headless servers | Confirmed (user choice) | Research tool must not break on CI/SSH; phase 6 graceful degradation precedent |

### FPS Throttle Configuration
| Assumption | Confidence | Evidence |
|-----------|-----------|----------|
| render_fps as SurgicalEnvConfig field (not metadata) | Confirmed (user choice) | User-configurable at runtime; CLI can pass --render-fps |

---

## Decisions Made

| # | Area | Decision | Rationale |
|---|------|----------|-----------|
| D-01 | Viewer startup timing | Eager — start in __init__ immediately after load_scene() | Matches Gymnasium convention; immediate visual feedback |
| D-02 | Render thread ownership | Simulator owns the thread | Clean separation; backend-specific behavior (MuJoCo needs sync, PyBullet is no-op) |
| D-03 | Headless fallback | Warn and continue training without viewer | Research tool must work on headless CI/servers |
| D-04 | FPS throttle config | SurgicalEnvConfig.render_fps field (default 30.0) | User-configurable via CLI; passed through to RenderThread |
| D-05 | SIGINT cleanup | signal handler + atexit + daemon thread | Defensive cleanup; prevents zombie windows |
| D-06 | macOS / mjpython | RuntimeError with instructions if launch_passive fails | Cocoa main-thread constraint is hard OS limit |
| D-07 | PyBullet human mode | No-op with warning if in DIRECT mode | GUI already renders; nothing to do in DIRECT |

---

## Corrections Made

None — all assumptions confirmed on first pass.

---

## Code Insights from Scouting

### Reusable Assets
- `MuJoCoSimulator._viewer` — field exists but never populated by a real viewer
- `MuJoCoSimulator.start_viewer()` — stub exists (lines 1081-1112) calling `launch_passive`, but no RenderThread
- `SurgicalEnv.metadata` — already has `"render_fps": 30`, `"render_modes": ["human", "rgb_array"]`
- `SurgicalEnv.render()` — already branches on `render_mode` (lines 469-480)
- `SurgicalEnv.close()` — already calls `self._simulator.close()` (line 485)

### Integration Points
- `SurgicalEnv.__init__` — must add `start_viewer()` call after `load_scene()` (line 134)
- `BaseSimulator` — must add `start_viewer()` / `stop_viewer()` abstract methods
- `CLI train()` — must add `--render-human` and `--render-fps` flags
- `SurgicalEnvConfig` — must add `render_fps: float = 30.0` field

---

## Auto-Resolved

Not applicable — no auto mode used.

---

## External Research

- Prior research in `07-real-time-rendering-RESEARCH.md` covers MuJoCo `launch_passive`, `sync(state_only=True)` pattern, PyBullet GUI behavior, Gymnasium render API contract
- All findings consistent with codebase state

---

*Discussion complete: 2026-05-02*
*Next: `/gsd-plan-phase 7` or `/gsd-execute-phase 7` after planning*

# Phase 42: Render/Sim Decoupling & Animated Viewport - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-15
**Phase:** 42 — Render/Sim Decoupling & Animated Viewport
**Areas discussed:** Playback controls UX, Preview speed control, Auto-play on open, Static-scene behavior

---

## Playback controls UX

| Option | Description | Selected |
|--------|-------------|----------|
| Toolbar + shortcuts (Recommended) | A QToolBar above the viewport with Play/Pause/Step buttons, AND keyboard shortcuts (Space=play/pause, "."=step one). Most discoverable. | ✓ |
| Menu + keyboard only | Keyboard-only (Space / ".") plus a Sim menu in the menu bar. Leaner but less visually discoverable. | |
| Context menu only | Right-click the viewport for a Play/Pause/Step context menu. Cleanest surface but least discoverable for a core SC#3 feature. | |

**Follow-up — step semantics:**

| Option | Description | Selected |
|--------|-------------|----------|
| One sim step (Recommended) | Step-one advances exactly one physics timestep (one `simulator.step()` call). Most precise; matches the accumulator's fixed step. | ✓ |
| A fixed batch (e.g. 10 steps) | Step-one advances a small fixed number of steps so motion is visible per press. Smoother but coarser. | |
| You decide | Implementer picks a sensible default and documents it. | |

**User's choice:** Toolbar + shortcuts; step-one = one sim step.
**Notes:** Step-one runs a single `step()` on the worker while paused (no loop resume), publishes one snapshot, render-poll displays it. Status bar gains a playback-state segment so a paused preview is not confused with the old immobile bug.

---

## Preview speed control

| Option | Description | Selected |
|--------|-------------|----------|
| Real-time only (1x) | Fixed real-time rate; no extra UI. Accumulator keeps it steady regardless of render fps. | |
| Discrete multiplier (Recommended) | Speed dropdown in the toolbar: 0.25x / 0.5x / 1x / 2x / 4x. Accumulator multiplies sim steps per wall-second. Useful for slow-motion inspection / fast scrubbing. | ✓ |
| Continuous slider | A 0.1x–5x slider in the toolbar. Most flexible but fiddlier UI and more test surface. | |

**User's choice:** Discrete multiplier dropdown, default 1x.
**Notes:** Session-only, panel-local state — resets to 1x on launch; NOT persisted to QSettings/SceneDefinition this phase (persistent-viewport-prefs is a research stretch item, not a Phase 42 SC).

---

## Auto-play on open

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-play on load (Recommended) | Preview animates as soon as a scene loads. Bug #1 visibly fixed on open. | |
| Start paused | Preview loads paused; user presses Play (or Space) to start. Safer for heavy scenes; Play button + "paused" status hint is the call-to-action. | ✓ |

**User's choice:** Start paused.
**Notes:** Deliberate UX call — avoids surprise CPU/GPU load on open for heavy scenes. The Play button + "paused" status hint together make clear the preview is intentionally paused, not exhibiting bug #1.

---

## Static-scene behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Step anyway + hint (Recommended) | Sim worker keeps stepping harmlessly; status bar shows "static scene — no dynamics" hint. Render-poll stays alive for camera orbit/zoom. No detection logic in the worker. | ✓ |
| Auto-pause when static | Detect nothing-changed across N steps and auto-pause (save CPU). Adds change-detection logic + heuristic threshold. | |
| You decide | Implementer picks a sensible default and documents it. | |

**User's choice:** Step anyway + informational hint.
**Notes:** Keeps the worker simple (no threshold-tuning) and preserves camera interactivity. The hint is informational only — no auto-pause, no special-casing.

---

## Claude's Discretion

- Internal shape of `SimStepWorker` / `RenderPollLoop` (signal names, snapshot dataclass vs `State` pass-through, accumulator wall-clock source).
- Whether `RenderPollLoop` is a separate `QObject` (new `render_poll_loop.py`) or a refactor of `_tick` into two methods on `ViewportPanel` (research recommends extracting `render_poll_loop.py` so the timer strategy is swappable).
- Toolbar button icons (Qt stock vs custom), toolbar/dropdown `objectName` strings.
- Status-bar segment wording/spacing.
- Test file placement (follow the `tests/test_gui_scaffold.py` offscreen pattern).

## Deferred Ideas

- Persisting viewport prefs (target_fps, sim_rate, speed) to `EditorSettings`/QSettings — research stretch item, not a Phase 42 SC.
- Continuous speed slider (0.1x–5x) — rejected (fiddlier, more test surface).
- Change-detection / auto-pause for static scenes — rejected (adds heuristic complexity for no functional gain).
- Auto-play on open — rejected by the user.
- A second `QTimer.singleShot` stepping chain — forbidden (Pitfall 1).
- Persistent edits to `SceneDefinition` (saved camera view, etc.) — out of scope this phase (Pitfall 7); arrives Phase 43+ via `SceneDefinition` + `SceneUndoStack`.
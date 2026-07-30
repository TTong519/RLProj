---
phase: 42-render-sim-decoupling-animated-viewport
reviewed: 2026-07-29T00:00:00Z
depth: deep
files_reviewed: 5
files_reviewed_list:
  - src/surg_rl/editor/sim_step_worker.py
  - src/surg_rl/editor/render_poll_loop.py
  - src/surg_rl/editor/viewport.py
  - src/surg_rl/editor/main_window.py
  - tests/conftest.py
findings:
  critical: 0
  warning: 3
  info: 6
  total: 9
status: issues_found
---

# Phase 42: Code Review Report

**Reviewed:** 2026-07-29
**Depth:** deep
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Phase 42 decouples the editor sim loop (SimStepWorker on a QThread, ~50 Hz fixed-step
accumulator) from the render loop (RenderPollLoop on the UI thread, ~30 Hz self-rescheduling
singleShot) and wires playback controls into EditorWindow. The thread-safety design is
fundamentally sound: a single shared `RLock` serializes every PyBullet/MuJoCo-touching op
(step/get_state/render/bind_scene/close), cooperative teardown is used throughout (no
`thread.terminate()`), the pause-before-close ordering (Pitfall 3) is correctly enforced
via queued signals, and the `_paused`/`_cancelled` guards at the top of `_tick` catch
straggler timer events. The module-level reaper + autouse fixture is a well-considered
answer to the QThread-leak / shiboken-stale-wrapper regression.

No BLOCKERs were found. The test suite (1575 green) is consistent with the code's
correctness for the covered paths. The findings below are quality / latent-correctness
issues: one clear merge-artifact duplication, one design-vs-implementation gap (the
published `State` payload is dead data — the render-poll is still coupled to the live
simulator, not to the snapshot), and several dead-code / missing-validation items.

## Critical Issues

_None._

## Warnings

### WR-01: `_refresh_recent_menu` duplicates clear+populate block (merge artifact)

**File:** `src/surg_rl/editor/main_window.py:668-678`
**Issue:** The method clears and repopulates `self._recent_menu` twice, back-to-back,
with identical code. Lines 669-673 and 674-678 are byte-for-byte the same (clear, loop
`recent_files()`, `addAction` with the same lambda). This is dead work (the second pass
rebuilds the menu the first pass already built) and a likely merge/branch artifact. It
also doubles the `addAction` signal connections transiently (the first set is discarded
by the second `clear()`, so no leak — but it is wasteful and confusing to maintainers).
**Fix:**
```python
def _refresh_recent_menu(self) -> None:
    self._recent_menu.clear()
    for p in self._settings.recent_files():
        self._recent_menu.addAction(
            p, lambda checked=False, path=p: self._open_scene(Path(path))
        )
```

### WR-02: Published `State` payload is never consumed — the "decoupling seam" is nominal, not real

**File:** `src/surg_rl/editor/sim_step_worker.py:334-335`, `src/surg_rl/editor/render_poll_loop.py:155-169`
**Issue:** The module docstrings (sim_step_worker.py:9-12, render_poll_loop.py:53-62)
describe `_Snapshot.state` (a `BaseSimulator.get_state() -> State` payload) as the
cross-thread "decoupling seam" (D-03). However, `RenderPollLoop._tick` only ever reads
`snap.frame_id` (for skip-when-no-new) — it NEVER reads `snap.state`. Instead, the
render-poll resolves the live simulator via `self._simulator_ref()` and calls
`sim.render(...)` directly on it. The actual cross-thread synchronization is the shared
`_sim_lock` (the render-poll blocks on the lock while the worker is mid-`step()`), not
the published snapshot.

Consequences:
1. `get_state()` is called at ~30 Hz inside `_publish()` and its result is discarded —
   wasted CPU and numpy allocation on every publish tick (out of v1 perf scope, but it
   is dead work, not just slow work).
2. The design claim "State is the decoupling seam (safe across threads)" is misleading:
   the render-poll is still coupled to the live simulator's mutable state via
   `simulator_ref()` + `render()`. A future maintainer trusting the docstring could
   remove the `_sim_lock` from `_render` thinking the snapshot is the synchronization,
   and introduce a PyBullet heap-corruption race.
3. `_Snapshot.state` is typed `object` "to stay PySide6-free" but is never read by any
   consumer in the editor package — it is dead data on the wire.

The code is correct as written (the lock makes it safe), but the seam is the lock, not
the State. This should either be corrected in the docs, or the render-poll should
actually render from `snap.state` (true decoupling, no lock needed on the render side).
**Fix:** Minimal: correct the docstrings to state that the lock is the synchronization
seam and `frame_id` is the only consumed snapshot field. Preferred: drop the
`get_state()` call in `_publish` (emit only `frame_id`) until a consumer exists:
```python
@dataclass
class _Snapshot:
    frame_id: int  # state removed until a consumer renders from published State

def _publish(self) -> _Snapshot:
    return _Snapshot(frame_id=self._frame_id)
```
If `State`-based rendering is intended (true decoupling), track that as a follow-up
rather than shipping dead data + a misleading contract.

### WR-03: `set_speed` accepts arbitrary floats with no validation

**File:** `src/surg_rl/editor/sim_step_worker.py:276-279`
**Issue:** The docstring states "Valid multipliers: 0.25 / 0.5 / 1 / 2 / 4" but
`set_speed` performs no validation. The combo box restricts the UI to the five valid
values, but `set_speed` is a `@Slot(float)` reachable via `_speed_request` (and directly
in tests). A speed of `0.0` makes `wall_dt * 0.0 = 0` → the accumulator never advances
→ the sim silently freezes (no error, no feedback). A negative speed makes
`accum += wall_dt * speed` drive the accumulator negative → the `while accum >= sim_dt`
loop never fires → also a silent freeze. A huge speed (e.g. 1e9) dumps a large debt
into the accumulator, which the spiral cap (8 steps) then discards — so the sim runs
8 steps per tick regardless, silently clamping the speed. None of these crash, but all
produce confusing "Play does nothing" UX with no diagnostic.
**Fix:**
```python
@QtCore.Slot(float)
def set_speed(self, speed: float) -> None:
    """Set the playback speed multiplier (scales wall_dt, NOT sim_dt)."""
    if not (speed > 0.0 and speed <= 64.0):
        logger.warning("Ignoring invalid playback speed %r (must be >0)", speed)
        return
    self._speed = speed
```

## Info

### IN-01: `SimStepWorker.stop()` is dead code

**File:** `src/surg_rl/editor/sim_step_worker.py:338-350`
**Issue:** `stop()` is never called from any production path or test. `_stop_sim_worker`
(main_window.py:298-305) sets `_cancelled` directly and calls `thread.quit()`/`wait()`,
explicitly declining to call `sim_worker.stop()` (comment at :280 explains touching the
worker-thread-affine QTimer from the UI thread is forbidden). The reaper
(sim_step_worker.py:144) also sets `_cancelled` directly. `stop()` is unreachable dead
code that duplicates the cancel-flag half of teardown without the thread.quit/wait half.
**Fix:** Remove `stop()`, or mark it `@QtCore.Slot()` and have the worker call it from
its own thread in a `thread.aboutToQuit` handler if you want the timer.stop() to be
explicit (currently the timer stops naturally when the thread's event loop exits).

### IN-02: `step_one` does not check `_paused` or `_cancelled`

**File:** `src/surg_rl/editor/sim_step_worker.py:281-295`
**Issue:** Per D-07, `step_one` is meant to advance exactly one step "while paused."
But it has no `_paused` or `_cancelled` guard. If invoked while playing (e.g. the "."
shortcut pressed during playback), it queues an extra `step(None)` on top of the
accumulator's steps, and the render-poll renders an out-of-band frame. If invoked after
cancel (e.g. a queued `step_one` lands after close), it steps a sim that may already be
closed. The lock prevents the close-race (the reaper holds the lock while closing), but
stepping a closed/None sim would raise inside the lock. The `if self._simulator is None`
guard at :290 only covers the None case, not the cancelled case.
**Fix:**
```python
@QtCore.Slot()
def step_one(self) -> None:
    if self._cancelled or self._simulator is None:
        return
    with self._sim_lock:
        if self._simulator is None:  # re-check under lock
            return
        self._simulator.step(None)
        self._frame_id += 1
        self.snapshot_ready.emit(self._publish())
```

### IN-03: Dead state/code in `ViewportPanel` superseded by `RenderPollLoop`

**File:** `src/surg_rl/editor/viewport.py:35, 188-189, 357-368, 403-415`
**Issue:** Several `ViewportPanel` members are now dead:
- `_FRAME_INTERVAL_MS = 50` (line 35) — superseded by `RenderPollLoop._FRAME_INTERVAL_MS
  = 33`; the viewport's value is never read (the viewport no longer owns a render chain).
- `_frame_count` / `_last_fps_check` (lines 188-189) — initialized but never incremented
  (the old `_tick` is a no-op); FPS counting moved to `RenderPollLoop`.
- `_tick` (lines 357-368) — explicit no-op retained for backward-compat test calls.
- `_maybe_update_fps` (lines 403-415) — unreachable from production (only the no-op
  `_tick` could have called it, and doesn't).

This is not a bug, but it is misleading surface area: a maintainer reading `_FRAME_INTERVAL_MS
= 50` in viewport.py could reasonably believe the viewport still drives a 20 Hz render loop.
**Fix:** Remove the dead members, or add a comment block pointing to `RenderPollLoop` as
the single owner of cadence + FPS. Keep `_tick` only if a test directly asserts on it.

### IN-04: Render resolution is fixed at construction and never adapts to canvas resize

**File:** `src/surg_rl/editor/render_poll_loop.py:70-71, 181-206`, `src/surg_rl/editor/main_window.py:137-138`
**Issue:** `RenderPollLoop` captures `width`/`height` in `__init__` (from
`self._viewport_panel.width()/height()` at EditorWindow construction time, default
640x480) and renders every frame at that fixed size in `_render`. The `ViewportPanel`
exposes `width()`/`height()` methods (viewport.py:385-391) documented as "Canvas width
for RenderPollLoop's render-size selection," but `RenderPollLoop._render` never calls
them — it uses `self._width`/`self._height`. When the user resizes the editor window,
the canvas scales the fixed-resolution pixmap (via `KeepAspectRatio` in
`ViewportCanvas.paintEvent`), so it still displays, but the render never uses the higher
pixel count. The viewport methods are dead interface.
**Fix:** Either have `_render` read the canvas size each tick
(`w = self._canvas.width(); h = self._canvas.height()`) and skip re-render when
unchanged, or remove the `ViewportPanel.width()/height()` docstrings that claim the loop
uses them.

### IN-05: Reaper double-closes the simulator (mitigated by idempotent close())

**File:** `src/surg_rl/editor/sim_step_worker.py:103-161`
**Issue:** In `reap_all_sim_runtimes`, `window.close()` (line 137) runs the full
`closeEvent` path, which calls `viewport.stop()` → `self._simulator.close()` on the
viewport's simulator ref. The reaper then continues (line 149-153) to acquire
`worker._sim_lock`, read `worker._simulator` (the SAME simulator instance, since
`set_playback`/`bind_scene` handed the same object to both), set it to None, and call
`sim.close()` again — a double close. This is safe ONLY because both `MuJoCoSimulator.close`
(mujoco_simulator.py:514, guards on `if self._renderer is not None`) and
`PyBulletSimulator.close` (pybullet_simulator.py:1385, guards on `if self._physics_client
is not None`) are idempotent. If a future simulator backend adds non-idempotent cleanup
(e.g. `scene_builder.cleanup()` deleting a temp dir that a later step re-creates), the
double close would silently corrupt. The reaper also re-runs `thread.quit()`/`wait()`
after `window.close()` already did so via `_stop_sim_worker`.
**Fix:** After `window.close()` succeeds, skip the belt-and-braces sim close:
```python
window_closed = False
if window is not None:
    with contextlib.suppress(Exception):
        window.close()
        window_closed = True
# ... render_loop.stop, _cancelled, thread.quit/wait always (cheap + safe) ...
if not window_closed:
    with contextlib.suppress(Exception), worker._sim_lock:
        sim = worker._simulator
        worker._simulator = None
        if sim is not None:
            sim.close()
```

### IN-06: `_update_fps_status` lacks the `hasattr` guard that `_refresh_playback_status` has

**File:** `src/surg_rl/editor/main_window.py:524-531`
**Issue:** `_refresh_playback_status` (line 468) guards against the status bar / toolbar
not yet being constructed (`if not hasattr(self, "_status_playback") ...: return`),
defending against queued slot delivery during `__init__`. `_update_fps_status` has no
such guard — it calls `self._set_status(...)` which touches `self._status_path` etc. The
risk is low because the render-poll's first fps callback only fires after ~1 s of
non-skipped frames (paused load publishes nothing, so `_frame_count` stays 0 until the
user presses Play, by which point `__init__` has returned to the event loop). But it is
an inconsistency: the two queued-from-__init__ status callbacks follow different
defensive-posture conventions.
**Fix:** Add the same `hasattr` guard to `_update_fps_status`, or factor a shared
"status bar ready" predicate.

---

_Reviewed: 2026-07-29_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
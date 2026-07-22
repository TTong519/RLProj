---
phase: 42-render-sim-decoupling-animated-viewport
plan: 01
subsystem: ui
tags: [pyside6, qthread, qt-timer, fixed-step-accumulator, render-sim-decoupling, publish-cap, offscreen-tests, lazy-import]

# Dependency graph
requires:
  - phase: 41-dock-layout-reset-closeevent-teardown
    provides: aboutToClose teardown contract + stop() cooperative-teardown template (cancel flag + thread.quit + thread.wait(3000) + log-on-timeout, NEVER terminate) that SimStepWorker.stop() mirrors
  - phase: 33-pyside6-scene-editor
    provides: QThread worker-object pattern (TextParserWorker/LLMPanel) + LazyImport + HAS_GUI sentinel + BaseSimulator.render(mode="rgb_array", w, h, camera_name) API
provides:
  - "SimStepWorker(QtCore.QObject) — QThread worker-object with a fixed-step ~50Hz accumulator (sim_dt=1/50, _MAX_STEPS_PER_TICK=8 spiral cap), ~30Hz publish-capped snapshot_ready signal, pause/resume/step-one/set_speed/bind_scene slots, cooperative stop()"
  - "RenderPollLoop(QtCore.QObject) — UI-thread self-rescheduling ~30Hz (QTimer.singleShot(33ms)) render of the latest published snapshot, skip-when-no-new, _running guard at both ends, initial-static-frame render on paused load, ephemeral camera-offset push, _maybe_update_fps"
  - "_Snapshot dataclass (state, frame_id:int) — the cross-thread decoupling boundary payload (D-03)"
  - "MockSimulator test fixture + offscreen harness (QT_QPA_PLATFORM=offscreen + qapp + isolated_home) reusable by Plan 42-02 and later GUI phases"
affects: [42-02 (EditorWindow/ViewportPanel wiring of SimStepWorker + RenderPollLoop + playback toolbar + Space/dot shortcuts + status-bar segment), 43-multi-view (N RenderPollLoop calls per frame, one GL context), 46-recording (frame capture hooks the render-poll), 48-autosave (ephemeral state discipline)]

# Tech tracking
tech-stack:
  added: []  # zero new pip deps — pure code on existing PySide6 6.11.1 (verified `pip show PySide6`)
  patterns:
    - "Fixed-step accumulator with spiral-of-death cap: accum += wall_dt*speed; while accum>=sim_dt and steps<_MAX_STEPS_PER_TICK: step(None); accum-=sim_dt; if steps==cap: accum=0.0"
    - "Publish-cap signal: frame_id monotonic int, emit only when now-last_publish >= 1.0/_PUBLISH_HZ (inclusive >=)"
    - "QThread worker-object: moveToThread + thread.started.connect(worker.start); worker owns its QTimer (affinity=worker thread); stop() sets cancel flag + timer.stop, controller owns thread.quit/wait (NEVER terminate)"
    - "Self-rescheduling QTimer.singleShot with _running guard at TOP (early-return) AND BEFORE reschedule (Pitfall 8)"
    - "Skip-when-no-new snapshot: render only when snap.frame_id != _last_rendered_id (saves CPU, decouples render rate from sim rate)"
    - "Cross-thread snapshot handoff via queued Signal(object) — State is pure-data (numpy + dicts, no Qt/GL handles), safe across threads (A3)"
    - "Speed scales wall_dt (accum += wall_dt*speed), NOT sim_dt — sim_dt stays fixed at 1/50 (Pitfall 5)"

key-files:
  created:
    - src/surg_rl/editor/sim_step_worker.py
    - src/surg_rl/editor/render_poll_loop.py
    - tests/test_sim_step_worker.py
    - tests/test_render_poll_loop.py
  modified: []  # no existing files modified (Plan 01 is pure additive — integration is Plan 02)

key-decisions:
  - "Decoupling seam = SimStepWorker.snapshot_ready (queued Signal(object)) -> RenderPollLoop.on_snapshot; ONE render timer on UI thread + ONE sim loop on QThread worker (D-01, D-02)"
  - "Snapshot source = BaseSimulator.get_state() -> State wrapped in _Snapshot(state, frame_id:int) (D-03); frame_id is a monotonic int (no float precision loss) and doubles as the render-poll skip-when-no-new check"
  - "Worker loads PAUSED (D-11) — _paused=True default; Play is opt-in; step_one runs exactly one step(None) while paused WITHOUT resuming the timer (D-07)"
  - "Speed scales wall_dt (NOT sim_dt) — Pitfall 5; accum += wall_dt*speed means at 2x the accumulator fills 2x faster and the while loop runs floor(accum/sim_dt) steps per tick"
  - "Spiral-of-death cap _MAX_STEPS_PER_TICK=8: if a tick falls behind (e.g. UI stalled), at most 8 step()s per tick and accum is RESET to 0.0 to discard backed-up debt (Pitfall 4)"
  - "Cooperative stop() = cancel flag + timer.stop ONLY; the controller (EditorWindow, Plan 02) owns thread.quit + thread.wait(3000) + log-on-timeout, NEVER terminate (D-04, Phase 41 D-05)"
  - "RenderPollLoop.stop() only sets _running=False — does NOT close the simulator; ViewportPanel.stop/update_scene closes the shared simulator AFTER pausing the worker (Pitfall 3 ordering)"
  - "Ephemeral camera offset (_editor_camera_*) pushed into sim on the render side only — NOT written to SceneDefinition/SceneUndoStack (D-05)"
  - "Tick instrumentation (_tick_count) counts every _tick invocation so the SC#2 offscreen cadence proxy can assert QTimer.singleShot fires >=30Hz independent of skip-when-no-new (real-fps is the backstop truth, verified in Plan 02)"

patterns-established:
  - "Pattern: fixed-step accumulator on a QThread worker-object with publish-capped queued signal — the render/sim decoupling primitive reusable by any future animated preview (multi-view Phase 43, recording Phase 46)"
  - "Pattern: self-rescheduling QTimer.singleShot with _running guard at both ends — the safe UI-thread loop pattern (no frame pile-up, no post-stop dangling callbacks)"
  - "Pattern: skip-when-no-new via monotonic frame_id — decouples consumer rate from producer rate without dropping coherence (render-poll reads latest, ignores stale)"
  - "Pattern: _Snapshot wrapper dataclass with monotonic int frame_id as the cross-thread currency — pure-data, Qt/GL-handle-free, safe across threads"

requirements-completed: [GUI-11]

# Coverage metadata (#1602) — one entry per shipped deliverable
coverage:
  - id: D1
    description: "SimStepWorker fixed-step ~50Hz accumulator advancing physics via step(None) (SC#1 — closes bug #1 immobile preview at the component level)"
    requirement: GUI-11
    verification:
      - kind: unit
        ref: "tests/test_sim_step_worker.py::TestSimStepWorkerAccumulator::test_accumulator_advances_physics"
        status: pass
    human_judgment: false
  - id: D2
    description: "Pause/resume/step-one controls — set_paused stops the accumulator QTimer, step_one advances exactly one physics step + publishes exactly one snapshot while paused (SC#3, D-07)"
    requirement: GUI-11
    verification:
      - kind: unit
        ref: "tests/test_sim_step_worker.py::TestPauseResumeStepOne::test_step_one_advances_exactly_one_while_paused"
        status: pass
      - kind: unit
        ref: "tests/test_sim_step_worker.py::TestPauseResumeStepOne::test_pause_then_resume_advances_then_holds"
        status: pass
    human_judgment: false
  - id: D3
    description: "Render/sim decoupling + 30Hz publish cap — a slow render (80ms) does not slow physics (worker on its own QThread); a fast sim does not flood the UI (snapshot_ready <= ~3 in 100ms, 30Hz cap) (SC#4)"
    requirement: GUI-11
    verification:
      - kind: unit
        ref: "tests/test_sim_step_worker.py::TestDecouplingAndPublishCap::test_publish_cap_limits_snapshot_ready_to_30hz"
        status: pass
      - kind: unit
        ref: "tests/test_sim_step_worker.py::TestDecouplingAndPublishCap::test_slow_ui_thread_does_not_slow_physics"
        status: pass
    human_judgment: false
  - id: D4
    description: "Discrete speed scaling 0.25/0.5/1/2/4 — at 2x step_count ~= 2x the 1x count, at 0.5x ~= half (D-09; speed scales wall_dt, NOT sim_dt — Pitfall 5)"
    requirement: GUI-11
    verification:
      - kind: unit
        ref: "tests/test_sim_step_worker.py::TestSpeedScaling::test_speed_2x_doubles_step_count"
        status: pass
      - kind: unit
        ref: "tests/test_sim_step_worker.py::TestSpeedScaling::test_speed_0_5x_halves_step_count"
        status: pass
    human_judgment: false
  - id: D5
    description: "RenderPollLoop ~30Hz UI-thread render of latest snapshot with skip-when-no-new + _running guard + step-one-renders-while-paused (SC#2 proxy + Pitfall 6)"
    requirement: GUI-11
    verification:
      - kind: unit
        ref: "tests/test_render_poll_loop.py::TestRenderPollCadence::test_render_poll_fires_at_least_30hz"
        status: pass
      - kind: unit
        ref: "tests/test_render_poll_loop.py::TestStepOneRendersWhilePaused::test_new_snapshot_renders_on_next_poll"
        status: pass
      - kind: unit
        ref: "tests/test_render_poll_loop.py::TestSkipNoNewSnapshot::test_duplicate_frame_id_skips_render"
        status: pass
      - kind: unit
        ref: "tests/test_render_poll_loop.py::TestRunningGuard::test_stop_halts_render_poll"
        status: pass
    human_judgment: false

# Metrics
duration: multi-session (~4d elapsed; bulk of work 2026-07-17, finalized 2026-07-22)
completed: 2026-07-22
status: complete
---

# Phase 42 Plan 01: Render/Sim Decoupling Core Summary

**Two new editor modules — SimStepWorker (QThread fixed-step ~50Hz accumulator + ~30Hz publish-capped snapshot_ready signal) and RenderPollLoop (UI-thread self-rescheduling ~30Hz render of latest snapshot with skip-when-no-new + _running guard) — built and tested in isolation with a MockSimulator + offscreen harness; no EditorWindow/ViewportPanel integration yet (that is Plan 42-02).**

## Performance

- **Duration:** multi-session (~4d elapsed; bulk of work 2026-07-17, finalized 2026-07-22)
- **Started:** 2026-07-17T23:03:47-07:00 (Task 1 RED commit)
- **Completed:** 2026-07-22T09:44:36-07:00 (Task 3 GREEN commit)
- **Tasks:** 3 (all TDD: RED → GREEN)
- **Files modified:** 4 (all new)

## Accomplishments
- `SimStepWorker(QtCore.QObject)` — QThread worker-object with a fixed-step ~50Hz accumulator (`sim_dt=1/50=0.02`, `_MAX_STEPS_PER_TICK=8` spiral cap, wall_dt scaled by speed), a ~30Hz publish-capped `snapshot_ready` signal (monotonic int `frame_id`), and `start`/`bind_scene`/`set_paused`/`set_speed`/`step_one`/`stop` slots. Loads paused (D-11). `stop()` is cooperative (cancel flag + timer.stop; controller owns thread.quit/wait — NEVER terminate, D-04).
- `RenderPollLoop(QtCore.QObject)` — UI-thread self-rescheduling `QTimer.singleShot(33ms, _tick)` at ~30Hz that renders the LATEST published snapshot, skips when `frame_id == _last_rendered_id`, renders an initial static frame on paused load, pushes the ephemeral `_editor_camera_*` into the simulator (D-05), and reports fps via `_maybe_update_fps`. `_running` guard at top AND before reschedule (Pitfall 8). NEVER calls `step()` (D-02); `stop()` only sets `_running=False` (does NOT close the simulator — Pitfall 3 ordering).
- `_Snapshot(state, frame_id:int)` dataclass — the cross-thread decoupling boundary payload (D-03); pure-data, no Qt/GL handles, safe across threads (A3).
- `MockSimulator` test fixture + standalone offscreen harness (`QT_QPA_PLATFORM=offscreen` module-top, `_HAVE_PYSIDE6` try/except, `pytestmark skipif`, session-scoped `qapp`, function-scoped `isolated_home`) — reusable by Plan 42-02 and later GUI phases.
- All 8 new test classes green offscreen (11 tests total: 7 worker + 4 render-poll).

## Task Commits

Each task was committed atomically (TDD: RED → GREEN):

1. **Task 1 (RED): test scaffolds + MockSimulator + offscreen harness** — `c927e71` (test)
2. **Task 2 (GREEN): SimStepWorker — fixed-step accumulator + 30Hz publish cap + step_one/set_speed/set_paused/bind_scene + cooperative stop()** — `a4b3fbd` (feat)
3. **Task 3 (GREEN): RenderPollLoop — UI-thread 30Hz render + skip-when-no-new + _running guard + step-one renders while paused** — `c1d4403` (feat)

_Note: the plan's final metadata commit is handled separately (see Final Commit below)._

## Files Created/Modified
- `src/surg_rl/editor/sim_step_worker.py` — SimStepWorker(QObject), _Snapshot dataclass, module constants _SIM_HZ=50.0 / _PUBLISH_HZ=30.0 / _MAX_STEPS_PER_TICK=8. Imports Qt via `from surg_rl.editor import QtCore` (LazyImport proxy — no `from PySide6 import ...` at module top).
- `src/surg_rl/editor/render_poll_loop.py` — RenderPollLoop(QObject), module constant _FRAME_INTERVAL_MS=33. Imports Qt via `from surg_rl.editor import QtCore` (LazyImport proxy). `render()` is the ONLY simulator call here; `step()` is NEVER called (D-02).
- `tests/test_sim_step_worker.py` — MockSimulator + offscreen harness + TestSimStepWorkerAccumulator (SC#1), TestPauseResumeStepOne (SC#3), TestDecouplingAndPublishCap (SC#4), TestSpeedScaling (D-09).
- `tests/test_render_poll_loop.py` — MockSimulator + offscreen harness + TestRenderPollCadence (SC#2 proxy), TestStepOneRendersWhilePaused (Pitfall 6), TestSkipNoNewSnapshot, TestRunningGuard.

## Decisions Made
- **Snapshot wrapper shape** — chose a `_Snapshot(state, frame_id:int)` dataclass (vs passing `State` through directly) so the render-poll has a monotonic int "new snapshot?" check that survives float precision concerns and doubles as the skip-when-no-new key. `_Snapshot.state` is typed `object` (with a comment noting it is `State`) to keep the dataclass PySide6-free and avoid the LazyImport mypy noise.
- **Tick instrumentation (`_tick_count`)** — added a `_tick_count` counter incremented at the top of `RenderPollLoop._tick` (before the `_running` guard) so the SC#2 offscreen cadence proxy asserts `QTimer.singleShot` fires >=30Hz independent of skip-when-no-new. Skip-when-no-new is correct behavior but means `canvas.set_image_count` only rises on new frame_ids; the timer cadence is the truer offscreen proxy (real-fps is the backstop truth, verified in Plan 02 on a real macOS display).
- **`bind_simulator` reset** — `bind_simulator` resets `_latest_snapshot`, `_last_rendered_id=-1`, `_frame_count`, `_last_fps_check` so the new scene's initial frame renders fresh (Plan 02's `update_scene` calls this).
- **Render-error handling scoped out** — the MuJoCo framebuffer-size retry (`viewport.py:243-274`) is a MuJoCo-specific concern that belongs in the canvas/viewport adapter layer (Plan 02), not the render-poll loop; kept out of scope. Render errors route through `safe_error_message` to the canvas.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Lint hygiene] Dropped unused `State` TYPE_CHECKING import in sim_step_worker.py**
- **Found during:** Task 3 (final test + lint sweep before the Task 3 commit)
- **Issue:** Task 2's plan suggested importing `State` under `if TYPE_CHECKING:` "for the dataclass type hint", but the implementer chose to type `_Snapshot.state` as `object` (to keep the dataclass PySide6-free and avoid LazyImport mypy noise) — so `State` was imported but never used. `ruff` would flag this as F401 on a stricter run.
- **Fix:** Removed the unused `State` import; added a trailing newline to `sim_step_worker.py` (file ended without one). Also applied `black` formatting to the test files (a few assert-statement reflowings) and removed two unused `from PySide6.QtCore import QThread` imports in `TestSpeedScaling`.
- **Files modified:** `src/surg_rl/editor/sim_step_worker.py`, `tests/test_sim_step_worker.py`, `tests/test_render_poll_loop.py`
- **Verification:** `ruff check` + `black --check` both clean on all 4 new files; all 11 tests still pass.
- **Committed in:** `c1d4403` (bundled with the Task 3 commit — these are trivial lint cleanups discovered while running the full suite for Task 3, not semantic changes)

---

**Total deviations:** 1 auto-fixed (1 lint hygiene)
**Impact on plan:** No scope creep — the unused-import removal and formatting are cosmetic; the semantic contract (D-03 snapshot source, D-02 no step() in render-poll, D-04 cooperative stop) is unchanged. All acceptance grep criteria pass.

## Issues Encountered
- **mypy noise on LazyImport proxies** — `mypy src/surg_rl/editor/sim_step_worker.py render_poll_loop.py` reports ~10 errors (`QtCore.QObject is not defined`, `step(None)` arg-type, `union-attr` on `get_state`). These are pre-existing patterns across the entire editor package (`llm_panel.py:17`, `viewport.py:55` produce identical `QtCore.* is not defined` errors from the `LazyImport` proxy). The `step(None)` arg-type is intentional — the plan documents that both backends guard `if action is not None` and the worker passes `None` deliberately (verified `mujoco_simulator.py:220-221` + `pybullet_simulator.py:946-947`). The `union-attr` on `get_state` is guarded at runtime by `_tick`'s `if self._simulator is None: return` early-return. Not a regression — the new modules follow the same LazyImport discipline as the existing editor code.

## TDD Gate Compliance
- **RED gate:** `c927e71` — `test(42-01): add RED scaffolds for SimStepWorker + RenderPollLoop` (tests fail on import — honest RED baseline, no skip/xfail).
- **GREEN gate (worker):** `a4b3fbd` — `feat(42-01): implement SimStepWorker` (4 worker test classes pass).
- **GREEN gate (render-poll):** `c1d4403` — `feat(42-01): implement RenderPollLoop` (4 render-poll test classes pass).
- **REFACTOR gate:** no separate refactor commit — the only post-GREEN changes are the lint hygiene bundled into the Task 3 commit (documented above), which are not behavior-changing refactors.

All three TDD gates (RED → GREEN, with GREEN split across the two components) are present in the git log.

## User Setup Required
None — zero new pip dependencies (pure code on existing PySide6 6.11.1, verified `pip show PySide6`). No external services, no environment variables, no dashboard configuration.

## Next Phase Readiness
- **Plan 42-02 (Wave 2) is unblocked** — the decoupling core is built, tested, and isolated. Plan 02 is pure wiring: instantiate `SimStepWorker` + its `QThread` in `EditorWindow.__init__`, connect `SimStepWorker.stop()` to `aboutToClose` (mirror line 139), connect `snapshot_ready` -> `RenderPollLoop.on_snapshot` (queued), split `ViewportPanel._tick` (render half moves to `RenderPollLoop`, step half is deleted — the worker now owns stepping), re-bind via `update_scene`, dock the playback `QToolBar` (Play/Pause + Step-one + speed dropdown per D-06/D-09), add `Space`/`.` `QShortcut`s (D-06), add the playback-state status-bar segment (D-08), and add `tests/test_viewport_playback.py`.
- **Backstop truth (real-fps on a real macOS display)** — Plan 01 proves the component-level proxy (offscreen >=30Hz cadence). The backstop truth ("a typical scene animates at >30fps on a real display") is verified in Plan 02 / the phase verifier on a real macOS display with a real simulator (PyBullet/MuJoCo software renderer), not here.
- **No blockers** — all 11 new tests green, lint clean, no new deps.

## Self-Check: PASSED

- `src/surg_rl/editor/sim_step_worker.py` — FOUND
- `src/surg_rl/editor/render_poll_loop.py` — FOUND
- `tests/test_sim_step_worker.py` — FOUND
- `tests/test_render_poll_loop.py` — FOUND
- Commit `c927e71` (Task 1 RED) — FOUND
- Commit `a4b3fbd` (Task 2 GREEN SimStepWorker) — FOUND
- Commit `c1d4403` (Task 3 GREEN RenderPollLoop) — FOUND
- 11/11 tests pass (`PYTHONPATH=src QT_QPA_PLATFORM=offscreen pytest tests/test_sim_step_worker.py tests/test_render_poll_loop.py -v`)

---
*Phase: 42-render-sim-decoupling-animated-viewport*
*Plan: 01*
*Completed: 2026-07-22*
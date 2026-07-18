# Phase 42: Render/Sim Decoupling & Animated Viewport - Context

**Gathered:** 2026-07-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver **GUI-11**: an animated, >30fps scene preview in the editor viewport where the simulation steps live, decoupled from the render rate — and the user can pause/resume/step-one the preview. This fixes the two known bugs that share a single root cause in `src/surg_rl/editor/viewport.py`:

- **Bug #1 (immobile preview)** — `_tick` calls `simulator.render()` every 50 ms but NEVER calls `simulator.step()`, so the preview is a frozen single frame.
- **Bug #2 (<10fps)** — the self-rescheduling `QTimer.singleShot(50, _tick)` loop caps the theoretical rate at 20 Hz while the synchronous `render()` call (50–120 ms on macOS software-rendered PyBullet) blocks the Qt event loop; effective fps drops to ~6–10.

Both are fixed by the **same** architectural change: render/sim decoupling via a `SimStepWorker(QObject)` on a `QThread` and a `RenderPollLoop(QObject)` on the UI thread. Per the v0.7.0 research, these bugs are NOT split into a separate bug-fix phase — they ARE the decoupling proof-of-criterion.

**In scope (GUI-11 success criteria):**
1. Opening a scene shows the preview animate (physics steps live in the viewport) — bug #1 closed.
2. The viewport animates at >30fps on a typical scene (not the <10fps frozen state) — bug #2 closed.
3. The user can pause/resume the simulation preview and step it one frame at a time from the editor.
4. Render rate and sim rate are decoupled — a slow render does not slow the physics, and a fast sim does not flood the UI thread (snapshot publish capped at ~30 Hz).

**Out of scope (later phases):** multi-view (43/GUI-12), lighting (44/GUI-13), gizmos (45/GUI-14), recording (46/GUI-15), editing UX + multi-select (47/GUI-16), autosave + crash recovery (48/GUI-17), scene generation (49–51). Persistent scene edits (lights, gizmo placements, transforms) are NOT introduced here — this phase adds only the animated preview + ephemeral camera control (Pitfall 7). The `aboutToClose` teardown *contract* is already established in Phase 41; the `SimStepWorker` simply plugs into it.

</domain>

<decisions>
## Implementation Decisions

### Architecture (carried forward from research — LOCKED, not re-asked)

- **D-01:** **Render/sim decoupling via two components** (v0.7.0 research, HIGH confidence). `SimStepWorker(QObject)` lives on a `QThread`, advances `simulator.step()` at a fixed sim-rate (~50 Hz) using a fixed-step accumulator (`accum += wall_dt; while accum >= sim_dt: step(); accum -= sim_dt`) so preview speed is independent of render rate; it publishes state snapshots via a queued signal, capped at ~30 Hz so a fast sim does not flood the UI thread. `RenderPollLoop(QObject)` runs on the UI thread, renders the **latest** published snapshot at its own cadence (~30 Hz) via a `QTimer`, and yields to the event loop between frames. The current monolithic `_tick()` in `viewport.py` is split along this seam.
- **D-02:** **The naive fixes are forbidden** (Pitfall 1). Do NOT inject `simulator.step()` into the existing `_tick`. Do NOT add a second `QTimer.singleShot` chain on the main thread. There is ONE render timer on the main thread (the `RenderPollLoop`) and ONE sim loop on the `QThread` worker. The render-poll never calls `step()` and never blocks on physics.
- **D-03:** **Snapshot source = `BaseSimulator.get_state() -> State`** (`base_simulator.py:252`). The `SimStepWorker` publishes snapshots derived from `get_state()`; the `RenderPollLoop` reads the latest snapshot and calls `render()` on the same simulator instance. (The simulator is shared — `step()` mutates state in place, `render()` samples it — so the snapshot is the decoupling boundary that lets the render-poll always read coherent recent state without waiting on physics.)
- **D-04:** **Teardown plugs into the Phase 41 `aboutToClose` harness** (D-04/D-05 of Phase 41). `SimStepWorker` declares `stop()` = cooperative cancel flag + `thread.quit()` + `thread.wait(3000)`; best-effort, logs a warning and proceeds on timeout (NEVER `thread.terminate()`, NEVER block the user from quitting). `EditorWindow` connects `SimStepWorker.stop()` to `aboutToClose` (already emitted at `main_window.py:59`/`:400` before `super().closeEvent()`). No `closeEvent` edit needed — the contract is already wired.
- **D-05:** **Ephemeral editor-only state stays on the panel** (Pitfall 7). Camera orbit/pan/zoom (`_camera_offset`) and the new playback state (playing/paused/speed) are panel-local, NOT undoable, NOT written to `SceneDefinition`. This phase writes nothing to `SceneDefinition` and pushes nothing onto `SceneUndoStack`. (Persistent edits — lights, gizmos, transforms — arrive in later phases and MUST go through `SceneDefinition` + `SceneUndoStack` then; that discipline is established here by negation.)

### Playback controls UX (SC#3)

- **D-06:** **Viewport `QToolBar` + keyboard shortcuts.** A new `QToolBar` docked above the viewport with Play/Pause (toggle) and Step-one buttons; keyboard shortcuts `Space` = play/pause, `.` = step one. `R` (already wired at `main_window.py:183` for camera reset) stays unchanged. The toolbar follows the `objectName` discipline (Phase 41 D-07 — every new `QDockWidget`/toolbar gets a unique `objectName` so `saveState()`/`restoreState()` round-trip correctly; the toolbar is added to the existing dock-state machinery). The toolbar is the SC#3 affordance; shortcuts are the power-user fast path.
- **D-07:** **Step-one advances exactly one physics timestep** — one `simulator.step()` call per press. Most precise; matches the accumulator's fixed step. While paused, step-one runs a single `step()` on the worker (without resuming the loop), publishes one snapshot, and the render-poll displays it.
- **D-08:** **Status bar exposes playback state.** The existing `_status_fps` label (`main_window.py:208`) keeps showing render fps; add a playback-state segment ("▶ playing" / "⏸ paused" + current speed, e.g. "1x") so the user never confuses a paused preview with the old immobile-preview bug. The status-bar segment set follows the existing 4-label row pattern at `main_window.py:210`.

### Preview speed control

- **D-09:** **Discrete speed multiplier dropdown in the toolbar** — `0.25x / 0.5x / 1x / 2x / 4x`, default `1x` (real-time). The accumulator multiplies sim steps per wall-second: at `2x` it runs ~2× the fixed-step iterations per wall interval; at `0.5x` it runs ~half. Useful for slow-motion inspection of cutting/fluid and for fast scrubbing. No continuous slider (fiddlier UI, more test surface). The dropdown's `objectName` follows Phase 41 conventions.
- **D-10:** Speed selection is **session-only, panel-local state** (per D-05 — not persisted to `SceneDefinition`/QSettings this phase). It resets to `1x` on editor launch. Persisting viewport prefs (target_fps, sim_rate, speed) to `EditorSettings` is a research-listed follow-on; defer unless the user asks. (The v0.7.0 research SUMMARY §"Modify `editor/_settings.py` — add dock-state + viewport-pref keys" is a stretch item, NOT a Phase 42 success criterion — leave it out of this phase's scope.)

### Auto-play on open

- **D-11:** **Preview loads PAUSED.** On New/Open/LLM-accept (`update_scene()` at `main_window.py:332`), the `SimStepWorker` is created but does not start stepping; the toolbar shows the Play button as the call-to-action and the status bar shows "⏸ paused". The user presses Play (or `Space`) to begin animation. This avoids surprise CPU/GPU load on open for heavy scenes. The Play button + "paused" status hint together make clear the preview is intentionally paused, not still exhibiting bug #1.

### Static-scene behavior

- **D-12:** **Step anyway + informational hint.** When a scene has no dynamics (a static arrangement — nothing visibly moves when stepped), the `SimStepWorker` keeps stepping harmlessly (no special detection logic in the worker), and the status bar shows a "static scene — no dynamics" hint. The `RenderPollLoop` stays alive so camera orbit/zoom still work. No change-detection heuristic, no auto-pause — the hint is informational only. This keeps the worker simple (no threshold-tuning) and preserves camera interactivity.

### Claude's Discretion

- Internal shape of `SimStepWorker` and `RenderPollLoop` (signal names, snapshot dataclass vs `State` pass-through, accumulator wall-clock source) — implementer's choice, so long as D-01..D-03 hold.
- Whether `RenderPollLoop` is a separate `QObject` or a refactor of the existing `_tick` into two methods on `ViewportPanel` — implementer's choice; the research recommends extracting `render_poll_loop.py` so the timer strategy is swappable without touching widget code.
- Exact toolbar button icons (Qt stock vs custom), toolbar `objectName` string (follow `dock_<slug>` / extend to `toolbar_<slug>`).
- Status-bar segment wording/spacing.
- Test file placement (follow the `tests/test_gui_scaffold.py` offscreen pattern, Phase 31/33/41).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase boundary & requirements
- `.planning/REQUIREMENTS.md` §GUI-11 — the requirement this phase delivers (the WHAT); traceability row maps GUI-11 → Phase 42, Pending
- `.planning/ROADMAP.md` (Phase 42 entry, lines 69–84) — phase goal, 4 success criteria, dependency on Phase 41, "UI hint: yes"
- `.planning/PROJECT.md` §"Current Milestone: v0.7.0" + "Key context" — milestone context; the locked decision that bugs #1/#2 share a render/sim-coupling root cause SEPARATE from bug #3 (dock state, fixed in Phase 41)

### v0.7.0 research (the bug root-cause analysis + pitfalls — HIGH confidence, directly observed in code)
- `.planning/research/SUMMARY.md` §"Architecture Approach" (components 1–2, 8–10) — `SimStepWorker` + `RenderPollLoop` design, `ViewportPanel`/`EditorWindow` modifications
- `.planning/research/SUMMARY.md` §"Critical Pitfalls" #1 (render/sim coupling) — the naive fixes that are forbidden (D-02)
- `.planning/research/SUMMARY.md` §"Critical Pitfalls" #7 (edits bypass schema) — the persistent-vs-ephemeral discipline (D-05)
- `.planning/research/SUMMARY.md` §"Bug Reconciliation — the three known GUI bugs" — the single-root-cause argument for bugs #1+#2 and why they are not split out
- `.planning/research/PITFALLS.md` §"Pitfall 1" (full) — accumulator pattern, snapshot publish cap, warning signs to grep for (one render chain, no two `singleShot` loops)
- `.planning/research/PITFALLS.md` §"Pitfall 3" (full) — `QThread` worker teardown ordering (`quit()` → `wait()` → `deleteLater`), never `deleteLater` before `wait()`, `aboutToClose` signal (D-04)

### Prior phase context (the editor this phase modifies — inherited decisions)
- `.planning/phases/41-dock-layout-reset-closeevent-teardown/41-CONTEXT.md` — **D-04** (`aboutToClose` registry signal, the teardown contract `SimStepWorker` plugs into), **D-05** (`stop()` semantics = cancel flag + `thread.quit()` + `thread.wait(3000)`, best-effort, no `terminate()`), **D-06** (`update_scene()` in-place swap on `ViewportPanel` — the path the animated preview must respect so it doesn't recreate widgets), **D-07** (unique-`objectName` enforcement — the new toolbar/dropdown must follow it)
- `.planning/phases/33-pyside6-scene-editor/33-CONTEXT.md` — **D-01..D-04** (the original static-preview viewport design this phase replaces: render-to-QImage via `QTimer.singleShot(50, _tick)`, `BaseSimulator.render(mode="rgb_array", w, h, camera_name)` reused as-is — D-02 carries forward, the render API is NOT changed here), **D-13** (the `QThread` worker-object pattern `SimStepWorker` mirrors), **D-17** (4-pane dock layout the toolbar is added into)

### Existing source modules (integration points — MUST read)
- `src/surg_rl/editor/viewport.py` — `ViewportPanel` + `ViewportCanvas`: `_tick` (lines 189–290, the monolithic loop to split per D-01), `stop()` (lines 169–180, the teardown template `SimStepWorker.stop()` generalizes), `update_scene()` (lines 399–415, the in-place swap that MUST keep working so dock geometry survives — the decoupled preview must re-bind the worker/render-loop to the new scene, NOT recreate widgets), `_default_load_simulator()` (lines 418–482, the loader the worker uses)
- `src/surg_rl/editor/main_window.py` — `aboutToClose` signal (line 59), `_viewport_panel` creation (lines 80–84), `aboutToClose.connect(self._llm_panel.stop)` (line 139 — the pattern to mirror for `SimStepWorker.stop()`), menu/status bar build (lines 154–218), `_update_fps_status` (lines 218+, the fps label the playback-state segment joins), `update_scene` call (line 332, loads paused per D-11), `closeEvent` emit (lines 395–407)
- `src/surg_rl/editor/llm_panel.py` — `LLMPanel` + `TextParserWorker`: the `QThread`/`_worker`/`_on_cancel` pattern (Phase 33 D-13) that `SimStepWorker` mirrors; `stop()` (Phase 41 D-05) is the template
- `src/surg_rl/simulators/base_simulator.py` — `step(action) -> StepResult` (line 219), `render(mode, width, height, camera_name)` (line 231), `get_state() -> State` (line 252, the snapshot source per D-03), `close()` (line 270)
- `src/surg_rl/editor/_safe_error.py` — `safe_error_message()`: redactor for any teardown-timeout / static-scene hint surfaced to the user
- `src/surg_rl/editor/_settings.py` — `EditorSettings`: existing QSettings plumbing; NOT extended this phase (D-10)

### Codebase maps (reusable patterns + conventions)
- `.planning/codebase/ARCHITECTURE.md` — editor + simulator subsystem overview
- `.planning/codebase/STACK.md` — `[gui]` extra + `LazyImport` + `HAS_GUI` sentinel (new `sim_step_worker.py` / `render_poll_loop.py` follow the same lazy-import discipline)
- `.planning/codebase/TESTING.md` — class-based test grouping; offscreen GUI test pattern (`QT_QPA_PLATFORM=offscreen`, `PYTHONPATH=src`) Phase 31/33/41 established
- `.planning/codebase/CONVENTIONS.md` — naming/ABC conventions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`BaseSimulator.step()` / `render()` / `get_state()` / `close()`** — the four primitives the worker + render-loop are built from. `step()` advances physics by `dt`; `get_state()` is the snapshot the render-poll reads (D-03); `render()` samples current state to an `np.ndarray`. No new simulator API is added this phase (D-02 of Phase 33 carries forward — the existing `render(mode="rgb_array", width, height, camera_name)` signature is reused as-is).
- **`ViewportPanel.stop()` / `_running` guard** (`viewport.py:169–180, 142`) — the existing render-loop teardown (sets `_running=False` so already-queued `QTimer.singleShot` callbacks early-return). `RenderPollLoop` follows the same guard pattern; `SimStepWorker.stop()` is the `QThread` analogue (Phase 41 D-05).
- **`ViewportPanel.update_scene()`** (`viewport.py:399–415`) — the in-place scene swap (closes old simulator, sets `_simulator=None`, swaps `_scene`, resets camera). The decoupled preview must re-bind the `SimStepWorker` + `RenderPollLoop` to the new scene **through `update_scene`** (not by recreating `ViewportPanel`) so dock geometry survives (Phase 41 D-06).
- **`LLMPanel._thread` / `_worker` `QThread` pattern** (Phase 33 D-13) — the only existing `QThread` in the editor; `SimStepWorker` mirrors it (`moveToThread`, `finished`/`failed` signals, `quit()`→`wait()`→`deleteLater` ordering per Pitfall 3).
- **`aboutToClose` signal** (`main_window.py:59`) — already emitted before `super().closeEvent()`; `SimStepWorker.stop()` just connects to it. No `closeEvent` edit (Phase 41 D-04).
- **`safe_error_message()`** — redactor applied to any error/hint string before it reaches the status bar.

### Established Patterns
- **`LazyImport` + `HAS_GUI` sentinel** (`editor/__init__.py`) — new `editor/sim_step_worker.py` and `editor/render_poll_loop.py` follow the same PySide6-import-optional discipline.
- **Offscreen GUI tests** via `QT_QPA_PLATFORM=offscreen` + `PYTHONPATH=src` — the Phase 31/33/41 `tests/test_gui_scaffold.py` pattern; Phase 42's worker/render-loop/teardown tests follow it.
- **`objectName` convention** (Phase 41 D-07) — the new toolbar + speed dropdown get unique `objectName`s before being added, so `saveState()`/`restoreState()` round-trip correctly.
- **Self-rescheduling `QTimer.singleShot`** — the existing `_tick` pattern; `RenderPollLoop` keeps the self-rescheduling discipline (prevents frame pile-up) but reads snapshots instead of calling `render()` synchronously off the same loop as `step()`.

### Integration Points
- **`ViewportPanel._tick` split** — extract the `render()` half into `RenderPollLoop` (UI thread, ~30 Hz, reads latest snapshot); move the (currently absent) `step()` responsibility onto `SimStepWorker` (QThread, ~50 Hz accumulator). The existing camera-offset push-into-simulator block (`viewport.py:220–236`) stays on the render side (ephemeral, D-05).
- **`EditorWindow.__init__`** — create the `SimStepWorker` + its `QThread`, connect `SimStepWorker.stop()` to `aboutToClose` (mirror line 139), dock the new playback `QToolBar`.
- **`EditorWindow` menu/shortcuts** — add `Space` (play/pause) and `.` (step-one) `QShortcut`s on the main window (per Phase 33 D-12: shortcuts on the main window, not per-widget).
- **`EditorWindow._update_fps_status`** area — add the playback-state status-bar segment alongside the existing fps label.
- **`ViewportPanel.update_scene`** — re-bind worker + render-loop to the new scene; load paused (D-11).
- **`EditorWindow.closeEvent`** — unchanged; `aboutToClose` already fires (line 400) and `viewport.stop()` already runs (line 407); `SimStepWorker.stop()` is wired through `aboutToClose`.

</code_context>

<specifics>
## Specific Ideas

No "I want it like X" references beyond the four UX decisions. The two design anchors downstream agents should treat as locked:

1. **Decoupling seam** (research-locked): one render timer on the UI thread + one sim loop on a `QThread`, snapshots published at ~30 Hz, accumulator-driven fixed-step sim at ~50 Hz. Bugs #1/#2 are this one change — not a separate bug-fix phase.
2. **Loads paused + step-one = exactly one `simulator.step()`**: the preview is opt-in (Play) by default, and step-one is the smallest possible increment — so the user can scrub physics one timestep at a time.

The user explicitly chose **paused-on-open** (D-11) and **discrete speed multipliers** (D-09) — both are deliberate UX calls, not implementer defaults.

</specifics>

<deferred>
## Deferred Ideas

- **Persisting viewport prefs (target_fps, sim_rate, speed) to `EditorSettings`/QSettings** — the v0.7.0 research SUMMARY lists "Modify `editor/_settings.py` — add dock-state + viewport-pref keys" as a stretch item; it is NOT a Phase 42 success criterion. Speed resets to `1x` on launch this phase (D-10). Revisit if the user asks or a later phase needs persisted prefs.
- **Continuous speed slider (0.1x–5x)** — rejected for this phase (fiddlier UI, more test surface); the discrete dropdown (D-09) covers the practical range.
- **Change-detection / auto-pause for static scenes** — rejected (D-12); adds a heuristic threshold and complexity for no functional gain. The informational hint is enough.
- **Auto-play on open** — rejected by the user (D-11); paused-on-open avoids surprise load on heavy scenes.
- **A second `QTimer.singleShot` chain for stepping** — explicitly forbidden (Pitfall 1, D-02); context contention, not a fix.
- **Persistent edits to `SceneDefinition` (camera as a saved view, etc.)** — out of scope (Pitfall 7, D-05); persistent edits arrive in Phase 43 (multi-view) onward and MUST go through `SceneDefinition` + `SceneUndoStack`.

</deferred>

---

*Phase: 42-render-sim-decoupling-animated-viewport*
*Context gathered: 2026-07-15*
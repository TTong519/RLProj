# Phase 42: Render/Sim Decoupling & Animated Viewport - Research

**Researched:** 2026-07-16
**Domain:** PySide6/Qt desktop — `QThread` worker-object render/sim decoupling, fixed-step physics accumulator, snapshot publish-rate capping, playback toolbar + shortcuts, offscreen-testable teardown
**Confidence:** HIGH

## Summary

Phase 42 is the v0.7.0 keystone: it splits the monolithic `_tick()` in `src/surg_rl/editor/viewport.py` (which calls `simulator.render()` every 50 ms but NEVER calls `simulator.step()`, and blocks the Qt event loop on a synchronous 50–120 ms software-rendered `render()`) into two decoupled components — a `SimStepWorker(QObject)` on a `QThread` that advances physics at a fixed ~50 Hz sim-rate via an accumulator, and a `RenderPollLoop(QObject)` on the UI thread that renders the latest published snapshot at its own ~30 Hz cadence. That one architectural change closes both bug #1 (immobile preview — physics never advanced) and bug #2 (<10 fps — synchronous render blocked the event loop and the self-rescheduling `singleShot(50)` capped the theoretical rate at 20 Hz). It also delivers SC#3 (pause/resume/step-one) and SC#4 (render rate and sim rate decoupled; snapshot publish capped at ~30 Hz).

The architecture is LOCKED in CONTEXT.md D-01..D-12 (carried forward from the v0.7.0 milestone research). This research does NOT re-derive it. What I did this session: (1) verified every line number / signature CONTEXT.md cites against the live source — all confirmed (see `## Verification of CONTEXT.md Canonical Refs`); (2) filled the implementer-discretion gaps a planner needs answered — the exact `QThread` worker-object lifecycle, the accumulator + ~30 Hz publish-cap mechanism, the render-poll "latest snapshot" read, step-one while paused, speed-multiplier scaling, the `QToolBar` + `QShortcut` wiring, the status-bar playback segment, the load-paused path through `update_scene()`; (3) resolved the one genuine technical ambiguity (D-12 "static scene" hint) into a concrete, non-heuristic rule; (4) read the Phase 41 teardown template (`LLMPanel.stop()` + `aboutToClose`) that `SimStepWorker.stop()` mirrors — Phase 41 already shipped it, verified on the installed PySide6 6.11.1.

One key codebase fact the CONTEXT did not surface but the planner/implementer MUST know: **both `MuJoCoSimulator.step()` and `PyBulletSimulator.step()` accept `action=None`** (they guard with `if action is not None: self._apply_action(action)` before stepping physics). So the `SimStepWorker` advances the preview by calling `simulator.step(None)` — no zero-vector synthesis, no `get_num_controls()` probe, no RL policy. This is the cleanest "physics-only advance" path and keeps the worker backend-agnostic. `[VERIFIED: src/surg_rl/simulators/mujoco_simulator.py:220-221 + pybullet_simulator.py:946-947]`

**Primary recommendation:** Build two new editor modules — `editor/sim_step_worker.py` (`SimStepWorker(QObject)` using a `QTimer`-driven accumulator on a worker `QThread`, publishing `State` snapshots via a queued `snapshot_ready(State)` signal capped at ~30 Hz) and `editor/render_poll_loop.py` (`RenderPollLoop(QObject)` on the UI thread, `QTimer`-driven ~30 Hz render of the latest snapshot, self-rescheduling with the existing `_running` guard). Split `ViewportPanel._tick()` along this seam (render half → `RenderPollLoop`; the currently-absent step responsibility → `SimStepWorker`). Add a `QToolBar` (Play/Pause toggle + Step-one + speed `QComboBox`) with `Space`/`.` `QShortcut`s on the main window and a 5th permanent status-bar label for playback state. Wire `SimStepWorker.stop()` to `aboutToClose` (mirror `main_window.py:139`). Load paused on every `update_scene()` (D-11). No new pip deps — pure code on the existing `[gui]` extra.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Render/sim decoupling via two components. `SimStepWorker(QObject)` on a `QThread`, advances `simulator.step()` at a fixed sim-rate (~50 Hz) using a fixed-step accumulator (`accum += wall_dt; while accum >= sim_dt: step(); accum -= sim_dt`); publishes state snapshots via a queued signal capped at ~30 Hz. `RenderPollLoop(QObject)` on the UI thread, renders the latest published snapshot at its own cadence (~30 Hz) via a `QTimer`, yields to the event loop between frames. The current monolithic `_tick()` is split along this seam.
- **D-02:** The naive fixes are forbidden. Do NOT inject `simulator.step()` into `_tick`. Do NOT add a second `QTimer.singleShot` chain. ONE render timer on the main thread + ONE sim loop on the `QThread` worker. The render-poll never calls `step()` and never blocks on physics.
- **D-03:** Snapshot source = `BaseSimulator.get_state() -> State` (`base_simulator.py:252`). `SimStepWorker` publishes snapshots derived from `get_state()`; `RenderPollLoop` reads the latest snapshot and calls `render()` on the same simulator instance. The simulator is shared — `step()` mutates state in place, `render()` samples it.
- **D-04:** Teardown plugs into the Phase 41 `aboutToClose` harness. `SimStepWorker.stop()` = cooperative cancel flag + `thread.quit()` + `thread.wait(3000)`; best-effort, logs a warning and proceeds on timeout; NEVER `thread.terminate()`. `EditorWindow` connects `SimStepWorker.stop()` to `aboutToClose`. No `closeEvent` edit needed.
- **D-05:** Ephemeral editor-only state stays on the panel. Camera orbit/pan/zoom (`_camera_offset`) and the new playback state (playing/paused/speed) are panel-local, NOT undoable, NOT written to `SceneDefinition`. This phase writes nothing to `SceneDefinition` and pushes nothing onto `SceneUndoStack`.
- **D-06:** Viewport `QToolBar` + keyboard shortcuts. New `QToolBar` docked above the viewport with Play/Pause (toggle) and Step-one buttons; `Space` = play/pause, `.` = step one. `R` (camera reset, `main_window.py:182`) stays unchanged. Toolbar follows the `objectName` discipline (Phase 41 D-07) and is added to the dock-state machinery.
- **D-07:** Step-one advances exactly one physics timestep — one `simulator.step()` per press. While paused, step-one runs a single `step()` on the worker (without resuming the loop), publishes one snapshot, render-poll displays it.
- **D-08:** Status bar exposes playback state. Existing `_status_fps` label keeps showing render fps; add a playback-state segment ("▶ playing" / "⏸ paused" + current speed, e.g. "1x"). Follows the existing 4-label row pattern at `main_window.py:210`.
- **D-09:** Discrete speed multiplier dropdown in the toolbar — `0.25x / 0.5x / 1x / 2x / 4x`, default `1x`. The accumulator multiplies sim steps per wall-second. No continuous slider.
- **D-10:** Speed selection is session-only, panel-local state (per D-05). Resets to `1x` on launch. Persisting viewport prefs to `EditorSettings` is a deferred follow-on — NOT this phase.
- **D-11:** Preview loads PAUSED. On New/Open/LLM-accept (`update_scene()`), the `SimStepWorker` is created but does not start stepping; toolbar shows Play; status bar shows "⏸ paused".
- **D-12:** Step anyway + informational hint. Static scene → worker keeps stepping harmlessly (no detection logic in the worker), status bar shows "static scene — no dynamics". `RenderPollLoop` stays alive so camera orbit/zoom still work. No change-detection heuristic, no auto-pause.

### Claude's Discretion
- Internal shape of `SimStepWorker` and `RenderPollLoop` (signal names, snapshot dataclass vs `State` pass-through, accumulator wall-clock source) — implementer's choice, so long as D-01..D-03 hold.
- Whether `RenderPollLoop` is a separate `QObject` or a refactor of the existing `_tick` into two methods on `ViewportPanel` — implementer's choice; research recommends extracting `render_poll_loop.py` so the timer strategy is swappable without touching widget code.
- Exact toolbar button icons (Qt stock vs custom), toolbar `objectName` string (follow `dock_<slug>` / extend to `toolbar_<slug>`).
- Status-bar segment wording/spacing.
- Test file placement (follow the `tests/test_gui_scaffold.py` / `tests/test_dock_state.py` offscreen pattern, Phase 31/33/41).

### Deferred Ideas (OUT OF SCOPE)
- Persisting viewport prefs (target_fps, sim_rate, speed) to `EditorSettings`/QSettings — stretch item, NOT a Phase 42 SC. Speed resets to `1x` on launch (D-10).
- Continuous speed slider (0.1x–5x) — rejected (fiddlier UI, more test surface); the discrete dropdown covers the practical range.
- Change-detection / auto-pause for static scenes — rejected (D-12); the informational hint is enough.
- Auto-play on open — rejected (D-11); paused-on-open avoids surprise load.
- A second `QTimer.singleShot` chain for stepping — explicitly forbidden (Pitfall 1, D-02).
- Persistent edits to `SceneDefinition` (camera as a saved view, etc.) — out of scope (Pitfall 7, D-05); arrive in Phase 43+.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GUI-11 | User sees an animated scene preview (simulation steps live in the editor viewport) at >30 fps — fixes the immobile-preview and <10fps bugs via render/sim decoupling (`SimStepWorker` on QThread + `RenderPollLoop` on UI thread) | D-01..D-04 deliver the decoupling (SC#1/#2/#4); D-06..D-09 deliver pause/resume/step-one/speed (SC#3); D-11/D-12 deliver the load-paused + static-scene UX. Verified integration points: `_tick` split at `viewport.py:189-290`, `step(action=None)` at `mujoco_simulator.py:220` / `pybullet_simulator.py:946`, `get_state()->State` at `base_simulator.py:252`, `aboutToClose` at `main_window.py:59`/`:400`, `update_scene` at `viewport.py:399`. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Pydantic v2** — N/A this phase (no `SceneDefinition` mutations per D-05; `update_scene` only swaps the scene reference the loader already takes).
- **Gymnasium/SB3** — N/A (no RL changes; the worker calls `simulator.step(None)`, not an env wrapper).
- **Simulator internals** — `hasattr(simulator, "_model")` for MuJoCo, `hasattr(simulator, "_physics_client")` for PyBullet. The worker MUST NOT assume a backend; it calls the `BaseSimulator` ABC primitives only (`step`/`get_state`/`render`/`close`). `_default_load_simulator` (`viewport.py:418-482`) already handles the macOS PyBullet-DIRECT fallback; the worker reuses whatever simulator the loader returns.
- **Optional fields — always guard** — `SceneDefinition.task` is `Optional[TaskConfig]`; `SceneDefinition.environment` may be `None`. The static-scene hint predicate (see `## Resolving D-12`) must guard these.
- **Imports** — Never `sed`/`echo -e` for multi-line imports; use `Edit`/`python -c "pathlib.Path(...).write_text(...)"`. New `editor/sim_step_worker.py` / `editor/render_poll_loop.py` follow the `LazyImport` + `HAS_GUI` discipline (`editor/__init__.py:31-42` — import `QtCore`/`QtWidgets`/`QtGui` from `surg_rl.editor`, NOT `from PySide6 import ...` at module top).
- **Testing** — `pytest.ini` sets `pythonpath = src`, `asyncio_mode = auto`; offscreen GUI tests set `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` at module top + `pytestmark = pytest.mark.skipif(not _HAVE_PYSIDE6, ...)`. `isolated_home` (tmp_path + `HOME`/`XDG_CONFIG_HOME` monkeypatch) is mandatory for any test constructing `EditorWindow` (QSettings isolation).
- **Algorithms** — N/A (no algorithm-name normalization this phase).
- **Code Style** — Line length 100, Python >=3.10, type hints required (`mypy disallow_untyped_defs = true`), ruff select E/F/I/N/W/UP/B/C4/SIM ignore E501.

## Verification of CONTEXT.md Canonical Refs

Every line number / signature CONTEXT.md cites was re-checked against the live source this session. All confirmed.

| CONTEXT.md citation | Live source (read this session) | Status |
|---|---|---|
| `viewport.py` `_tick` lines 189–290 | `_tick` at `viewport.py:189` (body 189–290); monolithic render-only loop, never calls `step()` | CONFIRMED |
| `viewport.py` `stop()` lines 169–180 | `stop()` at `viewport.py:169` (sets `_running=False`, `contextlib.suppress` close simulator) | CONFIRMED |
| `viewport.py` `update_scene()` lines 399–415 | `update_scene()` at `viewport.py:399` (in-place swap; closes old sim, sets `_simulator=None`, swaps `_scene`, `reset_camera()`) | CONFIRMED |
| `viewport.py` `_default_load_simulator()` 418–482 | at `viewport.py:418` (MuJoCo→PyBullet-DIRECT macOS fallback, probe-render, `_editor_preview_fallback` tag) | CONFIRMED |
| `viewport.py` camera-offset push 220–236 | `object.__setattr__(_editor_camera_*)` block at `viewport.py:222-234` | CONFIRMED (off-by-one in CONTEXT range; block is 222–236) |
| `main_window.py` `aboutToClose` line 59 | `aboutToClose = QtCore.Signal()` at `main_window.py:59` | CONFIRMED |
| `main_window.py` `_viewport_panel` creation 80–84 | at `main_window.py:80-84` (`ViewportPanel(scene=..., on_fps_update=self._update_fps_status)`, `setCentralWidget`) | CONFIRMED |
| `main_window.py` `aboutToClose.connect(self._llm_panel.stop)` line 139 | at `main_window.py:139` (the pattern `SimStepWorker.stop()` mirrors) | CONFIRMED |
| `main_window.py` menu/status bar build 154–218 | `_build_menu_bar` at 153, `_build_status_bar` at 204 (4 permanent labels: `_status_path`/`_status_sim`/`_status_fps`/`_status_validation` at 206-209) | CONFIRMED |
| `main_window.py` `_update_fps_status` 218+ | at `main_window.py:221` (calls `_set_status(path_label, sim_label, f"{fps:.1f}", "—")`) | CONFIRMED |
| `main_window.py` `update_scene` call line 332 | `_refresh_viewport_and_tree` at 323; `self._viewport_panel.update_scene(...)` at `main_window.py:332` | CONFIRMED |
| `main_window.py` `closeEvent` emit 395–407 | `closeEvent` at 394; `aboutToClose.emit()` at 400; `self._viewport_panel.stop()` at 407; `save_window` at 410 | CONFIRMED |
| `main_window.py` `R` shortcut line 183 | `QShortcut(QtGui.QKeySequence("Ctrl+R"), self)` at `main_window.py:182`; `.activated.connect(self._viewport_panel.reset_camera)` at 183 | CONFIRMED |
| `base_simulator.py` `step` line 219, `render` 231, `get_state` 252, `close` 270 | all at the cited lines; `step(action: np.ndarray) -> StepResult`, `render(mode, width, height, camera_name) -> np.ndarray | None`, `get_state() -> State`, `close()` | CONFIRMED |
| `llm_panel.py` QThread/`_worker`/`_on_cancel` pattern; `stop()` template | `TextParserWorker(QObject)` at 17; `_on_generate` wiring at 117-128 (`moveToThread`, `started->run`, `finished/failed->thread.quit`, `thread.finished->deleteLater`); `stop()` at 130 (cancel property + `thread.quit()` + `thread.wait(3000)` + timeout log) | CONFIRMED |
| `editor/__init__.py` LazyImport + HAS_GUI | at `editor/__init__.py:31-42` (`LazyImport("PySide6.QtWidgets", "gui")` etc., `HAS_GUI = QtWidgets.available`) | CONFIRMED |

**No drift detected.** The CONTEXT was gathered 2026-07-15 and the source is unchanged on `main` (Phase 41 shipped 2026-07-15; `git log` HEAD is `6935e38 docs(41): complete phase execution`).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Physics stepping (fixed-step accumulator, ~50 Hz) | Worker thread (`SimStepWorker` on `QThread`) | — | Must not block the UI event loop; `step()` is synchronous CPU work (50–120 ms on heavy scenes is exactly the bug). Qt worker-object pattern keeps it off the main thread. |
| Snapshot publish (~30 Hz cap) | Worker thread → UI thread (queued signal) | — | The `snapshot_ready(State)` queued signal is the decoupling boundary (D-03); capping prevents a fast sim from flooding the UI thread's event queue. |
| Rendering the latest snapshot (~30 Hz) | UI thread (`RenderPollLoop` `QTimer`) | — | `render()` samples the shared simulator; GL/software-renderer contexts are thread-affine — `render()` MUST run on the UI thread (same thread that constructed the simulator's GL context). |
| Playback control (Play/Pause/Step-one/Speed) | UI thread (toolbar + `QShortcut`s) | Worker thread (slots) | UI affordances live on the main window; they emit queued signals to worker `@Slot`s (`set_paused`, `step_one`, `set_speed`). |
| Playback + fps status display | UI thread (status bar) | — | Existing 4-label status bar; add a 5th permanent label. |
| Teardown on close | UI thread (`aboutToClose` → `SimStepWorker.stop()`) | Worker thread (honor cancel) | Phase 41 contract: `stop()` emitted before `super().closeEvent()`; worker must exit within `wait(3000)`. |
| In-place scene swap (load-paused) | UI thread (`ViewportPanel.update_scene`) | Worker thread (re-bind) | Phase 41 D-06 in-place swap preserved; the worker + render-loop re-bind to the new scene WITHOUT recreating widgets (dock geometry survives). |
| Camera orbit/pan/zoom (ephemeral) | UI thread (`ViewportPanel` `_camera_offset`) | — | D-05: panel-local, not persisted. The render-poll pushes `_editor_camera_*` into the simulator before `render()` (the existing `viewport.py:222-234` block, kept on the render side). |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PySide6 | 6.11.1 (installed; `[gui]` pins `>=6.8.0,<7.0`) | `QThread`/`QObject`/`QTimer`/`Signal`/`Slot`/`QToolBar`/`QShortcut`/`QComboBox` — the entire phase surface | Already the project's GUI framework since v0.5.0; no alternative considered. `[VERIFIED: pip show PySide6 + pyproject.toml:148-152]` |
| Qt QThread worker-object pattern | 6.11 LTS | `moveToThread` + `thread.start()` (runs `exec()`) + worker `@Slot`s + `quit()`/`wait()` cooperative teardown | Verified directly on installed PySide6 6.11.1 in Phase 41 research: cancel flag + `thread.quit()` + `thread.wait(3000)` → `True`, `isRunning()==False`. `[CITED: 41-RESEARCH.md §Code Examples "Cooperative QThread teardown"]` |
| QTimer (worker-thread–affine) | 6.11 | The accumulator tick inside `SimStepWorker`; the render-poll tick inside `RenderPollLoop` | A `QTimer` created in a slot invoked on the worker thread is affinity-bound to that thread — the idiomatic Qt way to drive a periodic worker loop without a blocking `while` (lets `step_one`/`set_paused` slots deliver). `[CITED: Qt 6 QThread docs — worker-object event loop]` |
| BaseSimulator ABC (`step`/`get_state`/`render`/`close`) | existing | The four primitives the worker + render-loop are built from; NO new simulator API | `[VERIFIED: src/surg_rl/simulators/base_simulator.py:219,231,252,270]` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `time.monotonic()` | stdlib | Accumulator wall-clock source (immune to system-clock adjustments) | Already used in `viewport.py:295` for fps; reuse for the accumulator `wall_dt` and the ~30 Hz publish cap. `[VERIFIED: viewport.py:295]` |
| `contextlib.suppress` | stdlib | Best-effort simulator close on teardown/swap (MuJoCo `Renderer.__del__` can raise) | Existing `viewport.py:178,410` pattern; `SimStepWorker.stop()` + `update_scene` reuse it. `[VERIFIED: viewport.py:178]` |
| `safe_error_message()` | existing (`editor/_safe_error.py`) | Redact any user-facing error/hint (static-scene hint, teardown-timeout surfacing) | Existing redactor; the static-scene hint and any status-bar teardown warning route through it. `[VERIFIED: _safe_error.py:34-43]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `QTimer`-driven accumulator inside the worker (recommended) | Blocking `while not cancelled:` loop in `run()` with `processEvents()` | The `QTimer` approach lets `step_one`/`set_paused`/`set_speed` slots deliver naturally via the worker's event loop; a blocking `while` requires manual `eventDispatcher().processEvents()` injection and busy-spins. Both satisfy D-01. CONTEXT leaves internal shape to implementer's discretion. |
| Separate `RenderPollLoop(QObject)` module (recommended) | Refactor `_tick` into two methods on `ViewportPanel` | Separate module makes the timer strategy swappable without touching widget code (the v0.7.0 research recommendation); in-place refactor is less code but couples cadence to the widget. CONTEXT leaves it to implementer's discretion. |
| `simulator.step(None)` for preview advance (recommended) | `np.zeros(simulator.get_num_controls())` | `step(None)` skips `_apply_action` entirely (both backends guard `if action is not None`) — no `get_num_controls()` probe, no backend assumption, no zero-vector synthesis. `[VERIFIED: mujoco_simulator.py:220-221 + pybullet_simulator.py:946-947]` |
| Pass `State` straight through `snapshot_ready` (recommended) | A dedicated `Snapshot` dataclass wrapping `State` + a frame counter + wall time | `State` is already the ABC-defined snapshot (`base_simulator.py:90-111`); a wrapper adds a frame counter for "is this a new snapshot?" detection in the render-poll. Implementer's discretion — a wrapper with a monotonic frame id is useful for the render-poll's "new snapshot since last render" check. |

**Installation:**
```bash
# No install needed — GUI-11 is pure code on the existing [gui] extra.
# pyproject [gui] (pyproject.toml:148-152): PySide6>=6.8.0,<7.0, markdown-it-py>=3.0.0, imageio>=2.31.0
```

**Version verification:**
```bash
pip show PySide6          # → Version: 6.11.1 (verified this session)
# No new packages introduced this phase — no registry verification needed.
```

## Package Legitimacy Audit

> This phase installs **zero** external packages. GUI-11 is pure code on the existing PySide6 dependency (already in the `[gui]` extra since v0.5.0). No `pip install` step is required.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| PySide6 | PyPI | (existing, pinned `>=6.8.0,<7.0`) | (existing) | (existing) | OK | Already installed — no action |

**Packages removed due to SLOP verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
                   EditorWindow.__init__  (extends Phase 41 wiring)
                          │
        ┌─────────────────┼──────────────────────────────────────┐
        ▼                 ▼                                      ▼
  _viewport_panel    _build_dock_widgets              aboutToClose.connect:
  (ViewportPanel,    (Phase 41: dock_scene_tree,       self._llm_panel.stop   (line 139, existing)
   central widget)    dock_properties, dock_llm)       self._sim_worker.stop  (NEW — mirror line 139)
        │
        │  __init__ now ALSO creates:
        │    self._sim_thread = QThread()
        │    self._sim_worker  = SimStepWorker()  → moveToThread(self._sim_thread)
        │    self._render_loop = RenderPollLoop(viewport_panel, sim_worker, on_fps_update)
        │    self._sim_thread.start()              # runs event loop (exec) — NOT a blocking run()
        │    self._build_playback_toolbar()         # QToolBar docked TopToolBarArea, objectName="toolbar_playback"
        │    self._wire_playback_shortcuts()        # Space -> play/pause, "." -> step-one (QShortcut on main window)
        │    self._build_status_bar() ... + self._status_playback (5th permanent label)
        ▼
  User opens / accepts a scene  →  _refresh_viewport_and_tree  →  ViewportPanel.update_scene(scene)
        │   (Phase 41 D-06 in-place swap, EXTENDED this phase)
        │   1. close old simulator (contextlib.suppress) — after stopping the worker's accumulator
        │   2. self._scene = scene; reset_camera()
        │   3. re-bind: sim_worker.bind_scene(new_simulator-loaded-on-worker-thread)
        │   4. D-11: sim_worker.set_paused(True)  → toolbar shows Play, status "⏸ paused"
        │   5. render_loop stays alive (renders the initial static frame; camera orbit still works)
        ▼
  User clicks Play (or Space)  →  sim_worker.set_paused(False)
        │
        ▼
  ┌─── SimStepWorker (QThread, event loop driven) ───────────────────────────────────┐
  │  QTimer @ ~50 Hz tick (created in start() slot, affinity = worker thread):         │
  │    now = time.monotonic(); wall_dt = now - last; last = now                         │
  │    accum += wall_dt * speed_multiplier        # D-09: 0.25x..4x scales sim steps    │
  │    while accum >= sim_dt:  simulator.step(None);  accum -= sim_dt   # fixed-step   │
  │    if now - last_publish >= 1/30:  # ~30 Hz publish cap (D-01/D-04)                 │
  │        snapshot_ready.emit(simulator.get_state())   # queued signal → UI thread     │
  │        last_publish = now                                                           │
  │                                                                                     │
  │  @Slot set_paused(bool):  self._timer.stop() / self._timer.start()                 │
  │  @Slot step_one():        simulator.step(None); snapshot_ready.emit(get_state())   │
  │  @Slot set_speed(float):  self._speed = speed                                      │
  │  @Slot bind_scene(sim):   swap the simulator reference (called from update_scene)  │
  │  stop():  cancel=True; timer.stop(); thread.quit(); thread.wait(3000) (D-04)       │
  └─────────────────────────────────────────────────────────────────────────────────────┘
                          │ snapshot_ready(State)  [queued, ~30 Hz cap]
                          ▼
  ┌─── RenderPollLoop (QObject, UI thread) ───────────────────────────────────────────┐
  │  QTimer @ ~33 ms (self-rescheduling, _running guard — the existing _tick pattern):  │
  │    if not _running: return                                                           │
  │    snap = self._latest_snapshot          # set by the snapshot_ready slot            │
  │    if snap is None or snap.frame_id == _last_rendered_id:                            │
  │        reschedule; return            # no new snapshot → skip render (saves CPU)     │
  │    push _editor_camera_* into simulator (viewport.py:222-234 block, KEPT here)       │
  │    arr = simulator.render(mode="rgb_array", w, h, camera_name)  # UI thread only     │
  │    canvas.set_image(QPixmap from arr)   # the existing _display_array path           │
  │    _last_rendered_id = snap.frame_id; on_fps_update(...); reschedule                 │
  └──────────────────────────────────────────────────────────────────────────────────────┘
        ▼
  closeEvent (main_window.py:394, UNCHANGED structure):
    1. aboutToClose.emit()  →  _llm_panel.stop()  AND  _sim_worker.stop()  (D-04)
         └ _sim_worker.stop() MUST run before viewport.stop() closes the shared simulator
    2. self._viewport_panel.stop()  →  render_loop.stop() (sets _running=False) + sim.close()
    3. save_window(...); super().closeEvent(event)
```

A reader can trace the primary use case: user opens a scene (`update_scene` re-binds the worker + render-loop, loads paused per D-11), presses Play (`set_paused(False)` starts the accumulator `QTimer`), the worker steps physics at ~50 Hz and publishes `State` snapshots at ~30 Hz, the render-poll renders the latest snapshot at ~30 Hz — physics advances (bug #1 closed) and the event loop stays responsive (bug #2 closed). Step-one while paused: the `step_one` slot runs one `step(None)` on the worker and publishes one snapshot without starting the accumulator timer. Close: `aboutToClose` stops the worker before the viewport closes the simulator.

### Recommended Project Structure
```
src/surg_rl/editor/
├── sim_step_worker.py    # NEW — SimStepWorker(QObject): QTimer-driven fixed-step accumulator on QThread, snapshot publish cap, pause/resume/step-one/speed/bind slots, stop() teardown
├── render_poll_loop.py   # NEW — RenderPollLoop(QObject): UI-thread QTimer ~30 Hz, renders latest snapshot, _running guard, reuses _display_array + _editor_camera_* push
├── viewport.py           # MODIFIED — split _tick(): render half → RenderPollLoop; step responsibility → SimStepWorker; update_scene() extended to re-bind worker+loop and load paused (D-11); stop() extended to stop render_loop
├── main_window.py        # MODIFIED — create _sim_thread/_sim_worker/_render_loop in __init__; aboutToClose.connect(_sim_worker.stop) (mirror line 139); _build_playback_toolbar + _wire_playback_shortcuts; 5th status-bar label _status_playback; _update_fps_status extended
├── _safe_error.py        # UNCHANGED (reuse safe_error_message for static-scene hint)
├── _settings.py          # UNCHANGED (D-10 — NOT extended this phase)
└── __init__.py           # UNCHANGED (LazyImport discipline; new modules import from surg_rl.editor)

tests/
├── test_sim_step_worker.py   # NEW (name per implementer) — accumulator + publish cap + step-one + speed + teardown with a MockSimulator + controllable clock
├── test_render_poll_loop.py  # NEW — render-poll reads latest snapshot, skips when no new snapshot, _running guard
└── test_viewport_playback.py # NEW (or extend test_dock_state.py) — toolbar/shortcuts/status-bar wiring, load-paused on update_scene, close-mid-step teardown (offscreen)
```

### Pattern 1: SimStepWorker — QTimer-driven accumulator on a QThread
**What:** A `QObject` moved to a `QThread`; the thread runs its event loop (`thread.start()` → `exec()`). A `QTimer` created inside a `start()` slot (affinity = worker thread) fires at the accumulator tick rate. Each tick runs the fixed-step accumulator and publishes a `State` snapshot at a capped ~30 Hz. Pause/resume/step-one/speed are `@Slot`s delivered by the worker's event loop.
**When to use:** D-01. The `QTimer`-in-worker idiom avoids a blocking `while` loop and lets `step_one`/`set_paused` slots deliver naturally (a blocking `while` would starve the worker's event loop).
**Example (recommended shape — implementer's discretion per CONTEXT):**
```python
# Source: [CITED: 41-RESEARCH.md §Pattern 2 (cooperative teardown) + Qt 6 QThread worker-object docs]
# [VERIFIED: step(None) accepted by both simulators — mujoco_simulator.py:220, pybullet_simulator.py:946]
from __future__ import annotations
import time
from surg_rl.editor import QtCore
from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)

_SIM_HZ: float = 50.0
_PUBLISH_HZ: float = 30.0
_MAX_STEPS_PER_TICK: int = 8  # catch-up cap; prevents spiral-of-death on a slow tick


class SimStepWorker(QtCore.QObject):
    snapshot_ready = QtCore.Signal(object)  # State (or a Snapshot wrapper with frame_id)

    def __init__(self) -> None:
        super().__init__()
        self._simulator = None         # bound via bind_scene slot
        self._timer: QtCore.QTimer | None = None
        self._paused: bool = True      # D-11: load paused
        self._speed: float = 1.0       # D-09: 0.25..4
        self._accum: float = 0.0
        self._last_wall: float = 0.0
        self._last_publish: float = 0.0
        self._frame_id: int = 0
        self._cancelled: bool = False

    @QtCore.Slot(object)
    def bind_scene(self, simulator) -> None:
        # Called (queued) from update_scene on the UI thread. Re-binds the worker
        # to the newly-loaded simulator. Must be invoked BEFORE starting the timer.
        self._simulator = simulator
        self._accum = 0.0
        self._last_wall = time.monotonic()
        self._last_publish = self._last_wall
        self._frame_id = 0

    @QtCore.Slot()
    def start(self) -> None:
        # Invoked on thread.started (or directly). QTimer created here is affinity-
        # bound to the worker thread.
        if self._timer is None:
            self._timer = QtCore.QTimer()
            self._timer.setTimerType(QtCore.Qt.TimerType.PreciseTimer)
            self._timer.timeout.connect(self._tick)
            self._timer.start(int(1000 / _SIM_HZ))
        self._last_wall = time.monotonic()

    @QtCore.Slot(bool)
    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        if self._timer is None:
            return
        if paused:
            self._timer.stop()
        else:
            self._last_wall = time.monotonic()  # reset so wall_dt doesn't spike
            self._timer.start(int(1000 / _SIM_HZ))

    @QtCore.Slot(float)
    def set_speed(self, speed: float) -> None:
        self._speed = speed

    @QtCore.Slot()
    def step_one(self) -> None:
        # D-07: exactly one physics timestep, even while paused. Does NOT resume.
        if self._simulator is None:
            return
        self._simulator.step(None)
        self._frame_id += 1
        self.snapshot_ready.emit(self._publish())

    def _tick(self) -> None:
        if self._cancelled or self._simulator is None:
            return
        now = time.monotonic()
        wall_dt = now - self._last_wall
        self._last_wall = now
        self._accum += wall_dt * self._speed
        sim_dt = 1.0 / _SIM_HZ
        steps = 0
        while self._accum >= sim_dt and steps < _MAX_STEPS_PER_TICK:
            self._simulator.step(None)   # D-02: render-poll never calls step()
            self._accum -= sim_dt
            steps += 1
        if now - self._last_publish >= 1.0 / _PUBLISH_HZ:
            self._frame_id += 1
            self.snapshot_ready.emit(self._publish())
            self._last_publish = now

    def _publish(self):
        # Wrap State with a frame_id so the render-poll can detect "new snapshot".
        state = self._simulator.get_state()
        return _Snapshot(state=state, frame_id=self._frame_id)

    def stop(self) -> None:
        # D-04 / Phase 41 D-05 template. Called from aboutToClose (UI thread).
        self._cancelled = True
        if self._timer is not None:
            self._timer.stop()
```
`stop()` does NOT call `thread.quit()`/`thread.wait()` itself — that is the controller's job (`EditorWindow` owns the `QThread` and calls `quit()`+`wait(3000)`, mirroring `LLMPanel.stop()` at `llm_panel.py:130-158`). Keep the separation identical to Phase 41 so the teardown ordering is provably the same.

### Pattern 2: RenderPollLoop — UI-thread QTimer, latest-snapshot render
**What:** A `QObject` on the UI thread with a self-rescheduling `QTimer` (~33 ms) that renders the latest published snapshot. It reuses the existing `_running` guard (`viewport.py:142`) so already-queued callbacks early-return after `stop()` — the exact UAT Gap 2 fix pattern.
**When to use:** D-01. The render-poll never calls `step()` (D-02) and never blocks on physics; it reads `self._latest_snapshot` (set by the `snapshot_ready` slot) and calls `render()` on the shared simulator on the UI thread.
**Example (recommended shape):**
```python
# Source: [CITED: viewport.py:189-290 _tick pattern + 41-RESEARCH.md §Pattern 2 _running guard]
from surg_rl.editor import QtCore, QtGui

_FRAME_INTERVAL_MS = 33  # ~30 Hz render poll


class RenderPollLoop(QtCore.QObject):
    def __init__(self, canvas, simulator_ref, camera_offset_ref, on_fps_update) -> None:
        super().__init__()
        self._canvas = canvas
        self._simulator_ref = simulator_ref   # callable -> current simulator (shared)
        self._camera_offset_ref = camera_offset_ref
        self._on_fps_update = on_fps_update
        self._running: bool = True
        self._latest_snapshot = None
        self._last_rendered_id: int = -1
        # ... fps counters (mirror viewport.py:137-138, 292-304)

    def on_snapshot(self, snapshot) -> None:
        # Connected (queued) to SimStepWorker.snapshot_ready.
        self._latest_snapshot = snapshot

    def start(self) -> None:
        self._running = True
        QtCore.QTimer.singleShot(0, self._tick)

    def stop(self) -> None:
        self._running = False

    def _tick(self) -> None:
        if not self._running:
            return
        snap = self._latest_snapshot
        sim = self._simulator_ref()
        if snap is not None and sim is not None and snap.frame_id != self._last_rendered_id:
            # push _editor_camera_* into sim (the existing viewport.py:222-234 block),
            # then render + display (the existing _display_array path).
            self._render_into_canvas(sim)
            self._last_rendered_id = snap.frame_id
            self._maybe_update_fps()
        elif sim is not None and snap is None:
            # No snapshot yet (e.g. paused on load) — render the initial static frame
            # once so the user sees the scene, then only re-render on new snapshots.
            self._render_into_canvas(sim)
            self._last_rendered_id = -2  # sentinel: "initial frame rendered"
        if self._running:
            QtCore.QTimer.singleShot(_FRAME_INTERVAL_MS, self._tick)
```
**Why this fixes bug #2:** the synchronous `render()` still runs on the UI thread, but it runs at most ~30 Hz AND only when a new snapshot arrived — and because `step()` is off the UI thread, a slow `render()` no longer stalls physics. The event loop gets the `singleShot` callback, runs `render()`, yields, repeats. The render-poll's own cadence is decoupled from the sim's 50 Hz.

### Pattern 3: Playback QToolBar + QShortcut + status-bar segment
**What:** A `QToolBar` docked at `TopToolBarArea` with a Play/Pause `QAction` (toggle), a Step-one `QAction`, and a speed `QComboBox` (`0.25x/0.5x/1x/2x/4x`). `Space` and `.` `QShortcut`s on the main window. A 5th permanent `QLabel` in the status bar shows playback state.
**When to use:** D-06/D-08/D-09. Shortcuts on the main window (per Phase 33 D-12 — shortcuts on the main window, not per-widget, so they work regardless of focus).
**Example:**
```python
# Source: [VERIFIED: main_window.py:182-183 QShortcut pattern + 204-213 status-bar pattern]
# [CITED: Phase 33 D-12 — shortcuts on main window]
def _build_playback_toolbar(self) -> None:
    tb = QtWidgets.QToolBar("Playback")
    tb.setObjectName("toolbar_playback")   # Phase 41 D-07 objectName discipline
    self.addToolBar(QtCore.Qt.ToolBarArea.TopToolBarArea, tb)
    self._act_play_pause = tb.addAction("▶ Play")   # toggle
    self._act_play_pause.setCheckable(True)
    self._act_step_one = tb.addAction("⏭ Step")
    tb.addSeparator()
    tb.addWidget(QtWidgets.QLabel("Speed:"))
    self._speed_combo = QtWidgets.QComboBox()
    self._speed_combo.setObjectName("combo_playback_speed")
    for s in ("0.25x", "0.5x", "1x", "2x", "4x"):
        self._speed_combo.addItem(s)
    self._speed_combo.setCurrentText("1x")   # D-10: default 1x, session-only
    tb.addWidget(self._speed_combo)
    self._act_play_pause.toggled.connect(self._on_play_pause)
    self._act_step_one.triggered.connect(self._on_step_one)
    self._speed_combo.currentTextChanged.connect(self._on_speed_changed)

def _wire_playback_shortcuts(self) -> None:
    QtGui.QShortcut(QtGui.QKeySequence("Space"), self).activated.connect(self._toggle_play_pause)
    QtGui.QShortcut(QtGui.QKeySequence("."), self).activated.connect(self._on_step_one)
    # R (Ctrl+R) at main_window.py:182 stays unchanged (camera reset).

def _build_status_bar(self) -> None:   # EXTEND the existing 4-label row
    ...  # existing 4 labels (unchanged)
    self._status_playback = QtWidgets.QLabel("⏸ paused")
    for w in (..., self._status_playback):
        w.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w.setFrameShadow(QtWidgets.QFrame.Shape.Sunken)
        bar.addPermanentWidget(w)

def _update_playback_status(self, playing: bool, speed: float, static: bool = False) -> None:
    if static:
        self._status_playback.setText("⏸ paused (static scene — no dynamics)")
    elif playing:
        self._status_playback.setText(f"▶ playing {speed}x")
    else:
        self._status_playback.setText("⏸ paused")
```

### Pattern 4: update_scene re-binds worker + render-loop, loads paused (D-11)
**What:** `ViewportPanel.update_scene(scene)` (Phase 41 D-06 in-place swap) is EXTENDED: after closing the old simulator and swapping `_scene`, it (a) pauses the worker, (b) loads the new simulator on the worker thread via a queued `bind_scene` call, (c) keeps the render-loop alive so the initial static frame renders and camera orbit works.
**When to use:** D-11. Every New/Open/LLM-accept path (`_refresh_viewport_and_tree` → `update_scene`) loads paused.
**Key ordering constraint:** the worker's accumulator timer MUST be stopped (paused) before the old simulator is closed, and the new simulator MUST be loaded before the worker resumes. `bind_scene` is a queued slot, so it runs on the worker thread after any in-flight `_tick` completes — no mutex needed.
```python
# Source: [VERIFIED: viewport.py:399-415 existing update_scene + 169-180 stop() close pattern]
def update_scene(self, scene: SceneDefinition) -> None:
    # 1. Pause the worker BEFORE closing the old simulator (stop stepping the
    #    sim that's about to be closed).
    self._sim_worker.set_paused(True)
    # 2. Close the old simulator (Phase 41 pattern).
    with contextlib.suppress(AttributeError, OSError):
        if self._simulator is not None:
            self._simulator.close()
    self._simulator = None
    self._scene = scene
    self.reset_camera()
    # 3. Load the new simulator (on the UI thread via the existing loader — the
    #    loader probes GL; doing it on the worker thread would race the GL
    #    context). Then hand it to the worker + render-loop.
    new_sim = self._on_load_simulator(self._scene)
    self._simulator = new_sim
    self._render_loop.bind_simulator(new_sim)   # update the callable ref
    # Queued: the worker binds on its own thread after any in-flight _tick.
    self._sim_worker.bind_scene.emit(new_sim)
    # 4. D-11: load paused. Toolbar/status reflect it.
    # 5. Render the initial static frame so the user sees the scene immediately.
```
**Note (implementer's discretion):** whether the simulator is loaded on the UI thread (as above — keeps GL-probe on the UI thread, consistent with the existing `_default_load_simulator` which calls `sim.render()` to probe) or on the worker thread. The GL-probe at `viewport.py:467-472` calls `sim.render()` — `render()` is thread-affine and MUST run on the UI thread, so loading + probing on the UI thread and handing the live simulator to the worker is the safe choice. The worker then only calls `step()` (no GL) on its thread — but `step()` on PyBullet touches `_physics_client` which is NOT thread-affine (it's a CPU physics engine), and MuJoCo `mj_step` is CPU-only. So stepping on the worker thread is safe; rendering on the UI thread is safe. `[ASSUMED]` — the PyBullet/MuJoCo `step()` is CPU-only and safe off the UI thread; this is the v0.7.0 research's explicit premise (Pitfall 1 prescribes a `QThread` worker for `step()`). Flag for implementer verification on first integration.

### Anti-Patterns to Avoid
- **Inject `simulator.step()` into `_tick`** (D-02): couples sim cadence to render cadence → slow-motion playback + the event loop still blocks on `render()`. The single root cause of bugs #1/#2.
- **A second `QTimer.singleShot` chain on the main thread for stepping** (D-02): two `singleShot` chains racing on the main thread re-enter `render()` mid-framebuffer-acquire → CGL/EGL context contention + the <10 fps stutter. Grep for `singleShot` — there must be ONE render chain (the `RenderPollLoop`) and the worker uses a `QTimer` on its own thread.
- **Subclass `QThread` and override `run()`** (Pitfall 3 / `41-RESEARCH.md`): the worker-object pattern (`moveToThread` + `@Slot`s) is the project convention (`llm_panel.py:117-128`); subclassing puts slots on the wrong thread.
- **`thread.deleteLater()` in `stop()` before `wait()`** (Pitfall 3): "Deleting a running QThread will result in a program crash." The existing `thread.finished -> thread.deleteLater` wiring handles deletion; `stop()` calls `quit()`+`wait(3000)` only. `[CITED: 41-RESEARCH.md §Pitfall 4]`
- **`thread.terminate()` on timeout** (D-04/D-05): risks leaving simulator physics state inconsistent. Log and proceed.
- **Calling `simulator.render()` from the worker thread** (Pitfall 6): GL/software-renderer contexts are thread-affine. `render()` MUST run on the UI thread (the same thread that loaded the simulator + probed GL). The worker only calls `step()` + `get_state()`.
- **Recreating `ViewportPanel` on scene swap** (Phase 41 D-06, bug #3): `update_scene` re-binds the worker + render-loop in place; do NOT `setCentralWidget(new ViewportPanel)`.
- **Closing the simulator while the worker is mid-step**: `stop()`/`update_scene` MUST pause the worker (stop its accumulator timer) BEFORE `simulator.close()`. `aboutToClose` fires before `viewport.stop()` in `closeEvent` (`main_window.py:400` then `:407`) — ordering is already correct; preserve it.
- **Forgetting the `_running` guard in the render-poll** (Pitfall 8): every self-rescheduling `singleShot` callback must check `_running` at the top and before reschedule (the `viewport.py:190-191, 289-290` pattern). The new `RenderPollLoop._tick` inherits this verbatim.
- **Persisting speed/playback to `SceneDefinition` or `EditorSettings`** (D-05/D-10): session-only, panel-local. This phase writes nothing to the schema and nothing to QSettings.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Physics stepping loop | A custom `while`/`sleep` loop on the UI thread | `QThread` worker-object + `QTimer`-driven accumulator (D-01) | UI-thread stepping is exactly bug #1/#2; a `QTimer` on the worker thread is the Qt idiom and lets slots deliver. `[CITED: PITFALLS.md Pitfall 1]` |
| QThread teardown | Manual `terminate()` / synchronous `deleteLater` | `quit()` + `wait(3000)` cooperative cancel (Phase 41 D-05 template) | `terminate()` is unsafe for sim state; `deleteLater` before `wait()` crashes per Qt docs. `[CITED: 41-RESEARCH.md §Pattern 2]` |
| Frame-rate cap / "new snapshot?" detection | A hand-rolled queue + timestamps | A monotonic `frame_id` on the snapshot + `time.monotonic()` publish cap | The render-poll just compares `snapshot.frame_id != last_rendered_id`; the worker caps publish with `now - last_publish >= 1/30`. Simple, no locks. |
| FPS measurement | A custom timer infrastructure | The existing `_maybe_update_fps` (`viewport.py:292-304`) moved into `RenderPollLoop` | Already correct (`time.monotonic()`, 1 s window); just relocate it. |
| Render-to-pixmap | Reimplement QImage/QPixmap conversion | The existing `ViewportPanel._display_array` (`viewport.py:306-353`) | Handles all the HxWx3/4 + grayscale + reshape edge cases; reuse verbatim from `RenderPollLoop`. |
| Status-bar layout | A new layout manager | The existing 4-permanent-label row pattern (`main_window.py:204-213`) | Add a 5th `QLabel` with the same `Panel`/`Sunken` frame; `addPermanentWidget`. `[VERIFIED: main_window.py:204-213]` |

**Key insight:** The entire phase is composed of Qt-provided APIs (`QThread`/`QTimer`/`QObject`/`Signal`/`Slot`/`QToolBar`/`QShortcut`) + the existing `BaseSimulator` ABC primitives + the existing `_display_array`/`_maybe_update_fps`/`_editor_camera_*` push. Nothing is hand-rolled except the accumulator math (one `while` loop) and the publish-cap `if`.

## Runtime State Inventory

> Applicable — this phase refactors the viewport render loop and adds a worker thread. The "rename/migration" categories are mostly empty, but the live-thread state is the crux of the phase.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `QSettings` (INI) stores `window/geometry` + `window/state` (via `EditorSettings.save_window`). D-10: NO new keys this phase (speed is session-only). | **No data migration.** The existing keys are untouched; the new toolbar's geometry is captured by `saveState()` automatically because it has an `objectName` (D-06/Phase 41 D-07). `[VERIFIED: _settings.py:39-48]` |
| Live service config | None — single-user desktop editor; no external service holds editor config. | None. |
| OS-registered state | None — no Task Scheduler/launchd/systemd; `surg-rl-gui` is a pip entry point. | None. |
| Secrets/env vars | None — `LLM_API_KEY`/`LLM_PROVIDER` stay in `.env`; the worker reads no secrets. | None. |
| Build artifacts | `__pycache__`; `tests/gui/screenshots/*.png`. | None — regenerate. |
| **Live thread state (the crux)** | The NEW `SimStepWorker` `QThread` is a long-running thread that must be cooperatively stopped on close. The existing `LLMPanel` `QThread` is already torn down via `aboutToClose` (Phase 41). The existing `QTimer.singleShot` render chain in `_tick` is replaced by `RenderPollLoop` (UI thread) + the worker's `QTimer` (worker thread). | **Teardown wiring (D-04):** `EditorWindow.__init__` connects `self.aboutToClose.connect(self._sim_worker.stop)` (mirror `main_window.py:139`). `closeEvent` ordering (`main_window.py:400` emit `aboutToClose` BEFORE `:407` `viewport.stop()`) already guarantees the worker stops BEFORE the shared simulator is closed — preserve it. `[VERIFIED: main_window.py:394-411]` |

**Nothing in stored-data/service/OS/secrets/artifacts categories needs migration.** The only runtime state that matters is the worker thread lifecycle, which is handled by the Phase 41 `aboutToClose` contract.

## Common Pitfalls

### Pitfall 1: Two `QTimer.singleShot` chains on the main thread (D-02 forbidden)
**What goes wrong:** Adding a second `singleShot` chain for stepping races the render chain on the main thread → CGL/EGL context contention + the <10 fps stutter returns.
**Why it happens:** The intuitive "decouple by adding a second timer" is the wrong axis of decoupling.
**How to avoid:** ONE render timer on the UI thread (`RenderPollLoop`); the sim loop is a `QTimer` on the worker `QThread` (not a `singleShot` on the main thread). Grep `src/surg_rl/editor/` for `singleShot` — there must be exactly ONE render chain.
**Warning signs:** "CGL context already current on another thread" warnings; fps drops when scene has fluids/cutting; two `singleShot` call sites in the editor package. `[CITED: PITFALLS.md Pitfall 1]`

### Pitfall 2: `render()` called from the worker thread (GL thread-affinity)
**What goes wrong:** The worker calls `simulator.render()` to produce a frame → GL/software-renderer context is thread-affine; the offscreen framebuffer was constructed on the UI thread → crash or torn/blank frames.
**Why it happens:** It feels natural to "render the snapshot on the worker," but `render()` samples a GL context.
**How to avoid:** The worker ONLY calls `step()` + `get_state()` (CPU-only). `render()` is ALWAYS called on the UI thread by `RenderPollLoop`. The `snapshot_ready(State)` signal is the thread boundary; `State` is a pure-data dataclass (`base_simulator.py:90-111`) safe to pass across threads. `[VERIFIED: base_simulator.py:90-111 — State is numpy arrays + dicts, no Qt/GL handles]`

### Pitfall 3: Closing the simulator while the worker is mid-step
**What goes wrong:** `update_scene` or `closeEvent` closes `self._simulator` while the worker's `_tick` is inside `simulator.step(None)` → `RuntimeError`/segfault on a torn-down physics client.
**Why it happens:** The worker runs on its own thread; `close()` on the UI thread races `step()` on the worker thread.
**How to avoid:** ALWAYS pause the worker (stop its accumulator `QTimer`) BEFORE closing the simulator. In `closeEvent`, `aboutToClose` fires (`main_window.py:400`) before `viewport.stop()` (`:407`) — `SimStepWorker.stop()` sets `_cancelled=True` + stops the timer, and the controller's `thread.quit()`+`wait(3000)` guarantees the worker is done before `viewport.stop()` closes the sim. In `update_scene`, call `set_paused(True)` first (queued slot — but a queued slot doesn't synchronously stop the timer). **Recommendation:** have `set_paused` stop the timer synchronously (the timer is affinity-bound to the worker, but `QTimer.stop()` is thread-safe per Qt docs) OR have `update_scene` call `self._sim_worker.stop_accumulator()` via a `QMetaObject.invokeMethod(..., Qt.BlockingQueuedInvocation)` to synchronously halt the accumulator before closing the sim. The latter is the safe choice for `update_scene`. `[ASSUMED]` — `QTimer.stop()` cross-thread safety; Qt 6 docs say `QTimer::stop()` is safe to call from any thread, but a `BlockingQueuedInvocation` on a `pause_for_swap` slot is the provably-safe path. Flag for implementer.

### Pitfall 4: Accumulator spiral-of-death on a slow tick
**What goes wrong:** If the worker's `QTimer` tick is delayed (event loop busy) and `wall_dt` is large, `accum` grows huge and the `while accum >= sim_dt` loop runs many steps back-to-back, further delaying the next tick → spiral.
**Why it happens:** No catch-up cap.
**How to avoid:** Cap steps per tick (`_MAX_STEPS_PER_TICK = 8`) and discard excess `accum` (`if steps == _MAX_STEPS_PER_TICK: self._accum = 0.0`). Standard fixed-step accumulator practice.

### Pitfall 5: Speed multiplier applied to `sim_dt` instead of `wall_dt`
**What goes wrong:** Multiplying `sim_dt` by speed gives variable-timestep integration (physics instability) instead of slow-motion/fast-forward.
**Why it happens:** Misreading the accumulator.
**How to avoid:** Scale `wall_dt` (the accumulator input): `accum += wall_dt * self._speed`. `sim_dt` stays fixed at `1/50`. At 2x the accumulator fills 2x faster → 2x steps per wall interval (fast-forward); at 0.5x, half the steps (slow-motion). `[CITED: CONTEXT.md D-09]`

### Pitfall 6: Step-one while paused doesn't render (no snapshot reaches the render-poll)
**What goes wrong:** The user presses `.` while paused; `step_one` runs one `step()` on the worker and emits `snapshot_ready`, but the render-poll's `QTimer` is stopped or its `_running` is False → the snapshot is never rendered.
**Why it happens:** Pausing the worker also paused the render-poll by mistake, or the render-poll was tied to the worker timer.
**How to avoid:** The `RenderPollLoop` is INDEPENDENT of the worker's pause state — it keeps ticking at ~30 Hz while paused (so camera orbit still works and a step-one snapshot gets rendered on the next poll). Pause ONLY stops the worker's accumulator `QTimer`. `[CITED: CONTEXT.md D-12 — "RenderPollLoop stays alive so camera orbit/zoom still work"]`

### Pitfall 7: Toolbar without `objectName` breaks `saveState()` round-trip (Phase 41 D-07)
**What goes wrong:** The new `QToolBar` has no `objectName` → `saveState()` warns to stderr and the toolbar position is lost across launches.
**Why it happens:** `QMainWindow.saveState()` identifies toolbars by `objectName`, same as docks.
**How to avoid:** `tb.setObjectName("toolbar_playback")` BEFORE `addToolBar`. The Phase 41 SC#4 introspection test (`tests/test_dock_state.py::TestDockObjectNames`) should be EXTENDED to also collect `QToolBar` children and assert non-empty unique `objectName` (the test currently only checks `QDockWidget`). `[VERIFIED: tests/test_dock_state.py:66-85 — currently QDockWidget-only]`

### Pitfall 8: `step()` called before `load_scene()` / `reset()` raises `RuntimeError`
**What goes wrong:** `MuJoCoSimulator.step()` raises `RuntimeError("Scene not loaded...")` if `not self._loaded` (`mujoco_simulator.py:216`); same for PyBullet (`pybullet_simulator.py:942`).
**Why it happens:** The worker's accumulator fires before `bind_scene` delivered the loaded simulator.
**How to avoid:** `SimStepWorker._tick` guards `if self._simulator is None: return`. `bind_scene` is the slot that sets the simulator. Do NOT start the accumulator `QTimer` until `bind_scene` has run. `[VERIFIED: mujoco_simulator.py:216-217 + pybullet_simulator.py:942-943]`

## Code Examples

### Mock simulator for offscreen worker/teardown tests
```python
# Source: [VERIFIED: base_simulator.py:90-111 State + 114-135 StepResult shapes]
# A controllable MockSimulator lets tests assert accumulator + publish cap + step-one
# + teardown WITHOUT a real physics engine or GL context (offscreen/CI-safe).
import time
from dataclasses import dataclass, field
import numpy as np
from surg_rl.simulators.base_simulator import State, StepResult, Observation

class MockSimulator:
    def __init__(self, step_delay: float = 0.0) -> None:
        self.step_delay = step_delay
        self.step_count = 0
        self._loaded = True
        self.timestep = 0.02
        self.frame_skip = 1
    def step(self, action):
        if self.step_delay:
            time.sleep(self.step_delay)
        self.step_count += 1
        return StepResult(observation=Observation(), reward=0.0,
                          terminated=False, truncated=False)
    def get_state(self):
        return State(time=float(self.step_count))
    def render(self, mode="rgb_array", width=None, height=None, camera_name=None):
        return np.zeros((height or 480, width or 640, 3), dtype=np.uint8)
    def close(self): pass
```
With this mock + a `SimStepWorker` on a real `QThread`, the test asserts: after 100 ms wall, `step_count` is ~5 (50 Hz); `snapshot_ready` fired at most ~3 times (~30 Hz cap); `step_one()` while paused increments `step_count` by exactly 1; `stop()` → `thread.wait(3000)` → `isRunning()==False`. Use `time.monotonic()` (no monkeypatching needed if the test sleeps real wall time; OR inject a fake clock via a `_now` callable for deterministic assertions).

### Offscreen teardown test (mirror Phase 41 TestCloseMidCallMockSlow)
```python
# Source: [VERIFIED: tests/test_dock_state.py:278-329 TestCloseMidCallMockSlow pattern]
def test_close_mid_sim_step_clean_exit(qapp, isolated_home, monkeypatch):
    # Replace _default_load_simulator with a MockSimulator so no GL/physics loads.
    from surg_rl.editor.main_window import EditorWindow
    from surg_rl.editor import viewport as vp
    monkeypatch.setattr(vp, "_default_load_simulator", lambda scene: MockSimulator())
    w = EditorWindow(); w.show(); qapp.processEvents()
    # Start the worker (play), let it step a few times.
    w._sim_worker.set_paused(False); qapp.processEvents()
    time.sleep(0.05); qapp.processEvents()
    # Close mid-step via aboutToClose -> sim_worker.stop().
    w.close(); qapp.processEvents()
    thread = w._sim_thread
    if thread is not None:
        assert not thread.isRunning(), "SimStepWorker thread still running after close (D-04)"
```

## Resolving D-12: the "static scene" hint (the one genuine ambiguity)

D-12 says: "When a scene has no dynamics... the status bar shows a 'static scene — no dynamics' hint. No change-detection heuristic, no auto-pause." This is contradictory on its face — *how does the UI know it's static without a heuristic?* The resolution the planner should lock:

**A cheap SCHEMA-LEVEL predicate at load time, NOT a runtime step-delta heuristic.** The "no dynamics" determination is a structural check on `SceneDefinition` (the scene has no robots, no tissues with soft-body params, no fluid config), evaluated once in `update_scene`. It is NOT: comparing `get_state()` before/after N steps, thresholding position deltas, or auto-pausing. This honors D-12's "no change-detection heuristic" (a runtime threshold) while still producing the hint.

**Recommended predicate (implementer's discretion, but concrete):**
```python
def _scene_has_dynamics(scene: SceneDefinition) -> bool:
    # Structural check — NOT a runtime step-delta heuristic (D-12).
    if getattr(scene, "robots", None):           # any robot with joints -> dynamics
        return True
    if getattr(scene, "tissues", None):          # tissues (soft-body) -> dynamics
        return True
    env = getattr(scene, "environment", None)
    if env is not None and getattr(env, "fluid", None):   # fluid config -> dynamics
        return True
    return False
```
`update_scene` calls this once; if `False`, the status bar shows "⏸ paused (static scene — no dynamics)" and the worker still steps harmlessly when the user hits Play (D-12: "keeps stepping harmlessly"). `[ASSUMED]` — the exact predicate fields (`robots`/`tissues`/`environment.fluid`) need confirmation against the `SceneDefinition` schema; the planner should verify the field names in `src/surg_rl/scene_definition/schema.py` before implementing. Flagged in `## Open Questions`.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Monolithic `_tick()` (`viewport.py:189-290`): `render()` every 50 ms, NEVER `step()`, self-rescheduling `singleShot` | `SimStepWorker` (QThread, ~50 Hz accumulator) + `RenderPollLoop` (UI thread, ~30 Hz) | This phase | Bugs #1/#2 closed; preview animates; event loop stays responsive; render/sim decoupled. |
| No playback controls | `QToolBar` Play/Pause/Step-one/Speed + `Space`/`.` shortcuts + status-bar segment | This phase | SC#3 delivered; user can scrub physics one timestep at a time. |
| `closeEvent` stops only viewport + LLM panel (Phase 41) | `aboutToClose` also stops `SimStepWorker` | This phase | Mid-step close is clean (no torn simulator); the Phase 41 contract scales. |
| `step(action)` assumed to need an action vector | `step(None)` advances physics with no robot control (both backends guard `if action is not None`) | Verified this session | The editor preview needs no RL policy; the worker calls `step(None)` — backend-agnostic. |

**Deprecated/outdated:**
- `ViewportPanel._tick` (`viewport.py:189-290`) — split into `SimStepWorker._tick` + `RenderPollLoop._tick`. The camera-offset push (`222-234`) and `_display_array`/`_maybe_update_fps` move into `RenderPollLoop`.
- `ViewportPanel._start` (`viewport.py:165-167`) — replaced by `RenderPollLoop.start()` + `SimStepWorker.start()` (the latter via `thread.started`).

## Assumptions Log

> Claims verified by direct source read are `[VERIFIED]`; claims cross-checked against the v0.7.0 research or Phase 41 research are `[CITED]`; claims from training/reasoning not verified this session are `[ASSUMED]`.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `simulator.step(None)` is safe to call off the UI thread (PyBullet `_physics_client` / MuJoCo `mj_step` are CPU-only, not thread-affine like GL) | Architecture Patterns / Pattern 4 | MEDIUM — if `step()` touches a thread-affine resource, the worker crashes. The v0.7.0 research premise (Pitfall 1 prescribes a QThread worker for `step()`) assumes this is safe. Verify on first integration with a real PyBullet scene. |
| A2 | `QTimer.stop()` is safe to call cross-thread (to pause the worker's accumulator from the UI thread in `update_scene`) | Pitfall 3 | LOW — Qt 6 docs state `QTimer::stop()` may be called from any thread. The safer `QMetaObject.invokeMethod(..., BlockingQueuedInvocation)` on a `pause_for_swap` slot is the provably-safe alternative. |
| A3 | The `State` dataclass (`base_simulator.py:90-111`) is safe to pass across threads via a queued signal (no Qt/GL handles, only numpy arrays + dicts) | Pitfall 2 / Pattern 1 | LOW — verified by direct read: `State` is `time: float`, `qpos/qvel/mocap_pos/mocap_quat: np.ndarray`, `body_positions/orientations: dict`, `custom: dict`. No Qt object references. Deep-copying the arrays before emit is the defensive option if a backend mutates `qpos` in place after `get_state()`. |
| A4 | The static-scene predicate fields (`scene.robots`, `scene.tissues`, `scene.environment.fluid`) exist on `SceneDefinition` with those names | Resolving D-12 | LOW-MEDIUM — the schema is in `src/surg_rl/scene_definition/schema.py` (not read this session). The planner/implementer MUST verify field names before implementing the predicate. CLAUDE.md confirms `SceneDefinition.task` is `Optional[TaskConfig]` and `robots`/`tissues`/`instruments` are list attrs (from the `_find_instance` helper at `main_window.py:33-46`). |
| A5 | `RenderPollLoop` as a separate `editor/render_poll_loop.py` module is the right extraction (vs. an in-place refactor of `_tick` on `ViewportPanel`) | Architecture Patterns | LOW — CONTEXT leaves it to implementer's discretion; the v0.7.0 research recommends the separate module. |
| A6 | The accumulator `QTimer` on the worker thread + `QTimer.singleShot` self-rescheduling on the UI thread together satisfy "ONE render timer on the main thread + ONE sim loop on the QThread worker" (D-02) | Pattern 1/2 | LOW — D-02 forbids a second `singleShot` chain on the MAIN thread; the worker's `QTimer` is on the worker thread, not the main thread. Grep should find one `singleShot` chain (the `RenderPollLoop`) in the editor package. |

**Claims that were `[VERIFIED]` or `[CITED]` and need NO user confirmation:** all line-number/signature citations (see `## Verification of CONTEXT.md Canonical Refs`), `step(None)` acceptance, `State` shape, the Phase 41 teardown template, the offscreen test pattern, no-new-deps.

## Open Questions (all RESOLVED at plan time — see inline `RESOLVED:` markers)

1. **Static-scene predicate field names (A4)**
   - What we know: D-12 requires a "static scene — no dynamics" hint with NO runtime heuristic; a schema-level predicate is the resolution. CLAUDE.md + `main_window.py:33-46` confirm `robots`/`tissues`/`instruments` are list attrs.
   - What's unclear: the exact field names for fluid config on `EnvironmentConfig` (is it `environment.fluid`? `environment.fluid_config`? a `fluid_solver` field?) and whether a scene with only `instruments` (no robots/tissues) has dynamics.
   - Recommendation: the planner adds a Wave-0 task to read `src/surg_rl/scene_definition/schema.py` and lock the predicate; OR the implementer confirms it inline. Low risk — the hint is informational only (D-12).
   - **RESOLVED:** `fluid` is a DIRECT field on `SceneDefinition` (`schema.py:1442`), NOT on `EnvironmentConfig` (which has only `lights`/`cameras`/`ground_plane` at `:990-1009`). Corrected predicate → `_scene_has_dynamics(scene) = bool(scene.robots or scene.tissues or scene.fluid)`; instruments-only treated as STATIC (flagged assumption for implementer confirmation — LOW risk, hint is informational only per D-12). Locked in `42-PATTERNS.md` §"Static-scene predicate" and `42-02-PLAN.md` Task 1 (action + acceptance criterion `grep -n "environment.fluid" src/surg_rl/editor/viewport.py` returns 0). Also corrects Assumption Log A4 below.

2. **Does `update_scene` load the new simulator on the UI thread or the worker thread? (A1)**
   - What we know: `_default_load_simulator` (`viewport.py:418-482`) probes GL by calling `sim.render()` — `render()` is thread-affine and MUST run on the UI thread.
   - What's unclear: whether `load_scene()` itself (before the probe) is safe on the worker thread.
   - Recommendation: load + probe on the UI thread (as today), then hand the live simulator to the worker via `bind_scene` (queued). This keeps GL on the UI thread and `step()` on the worker thread. Document this as the locked approach.
   - **RESOLVED:** Load + GL-probe stays on the UI thread (as today); the live simulator is then handed to the worker via a queued `bind_scene` signal. GL never crosses to the worker; `step()`/`get_state()` stay on the worker. Locked in `42-02-PLAN.md` Task 2 action (the `update_scene` re-bind step). This is the documented locked approach — the load-on-worker alternative is unsafe for the GL probe.

3. **Is the >30 fps criterion machine-verifiable offscreen? (SC#2)**
   - What we know: real fps depends on a display + GPU; offscreen PyBullet-DIRECT `render()` takes variable software time; there is no display refresh.
   - What's unclear: how to prove ">30 fps" in CI without a display.
   - Recommendation: split SC#2 into (a) an **offscreen proxy** — `RenderPollLoop`'s `QTimer` interval is configurable (`_FRAME_INTERVAL_MS = 33`); with a `MockSimulator` whose `render()` returns instantly, assert the render-poll fires at ≥30 Hz (cadence is the contract, not wall-clock fps); (b) a **`verification: backstop` / human-needed truth** — on a real macOS/display machine with a typical scene, confirm the preview animates at >30 fps. The verifier branches on `verification: backstop` for the part it cannot confirm with explicit evidence offscreen. See `## Validation Architecture`.
   - **RESOLVED:** SC#2 split exactly as recommended. (a) Offscreen proxy = `TestRenderPollCadence` with an instant-render `MockSimulator` (render-poll cadence ≥30 Hz) — machine-verifiable. (b) Real-display fps = a structured `verification: backstop` truth in `42-01-PLAN.md` `must_haves.truths` ("On a real macOS display, a typical scene animates at >30 fps") + `42-VALIDATION.md` Manual-Only table — the verifier abstains → `human_needed` when no display evidence, never a silent pass. Locked in plan + VALIDATION.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PySide6 | Entire phase (QThread/QTimer/QToolBar/QShortcut) | ✓ | 6.11.1 (`[gui]` pins `>=6.8.0,<7.0`) | — (hard requirement) |
| Qt offscreen platform | GUI-state + worker/teardown tests | ✓ | built-in (`QT_QPA_PLATFORM=offscreen`) | — |
| PyBullet (physics) | Real-scene integration test (optional) | ✓ (on Linux/CI; macOS arm64 has no wheel per `pyproject.toml:69-73`) | 3.2.5+ | macOS tests use `MockSimulator` (no physics needed for worker/publish/teardown assertions); real-scene fps is a `verification: backstop` |
| MuJoCo (physics) | Real-scene integration test (optional) | ✓ | (installed) | Same as PyBullet — mock for offscreen unit/integration tests |
| Real display + GPU | SC#2 ">30 fps on a typical scene" | ✗ (offscreen CI) | — | `verification: backstop` / human-needed truth; offscreen proxy = render-poll cadence with instant-render mock |

**Missing dependencies with no fallback:** none for the offscreen-testable surface. The real-fps SC#2 is a backstop truth, not a blocker.

**Missing dependencies with fallback:** real physics/display → `MockSimulator` + render-poll cadence proxy for offscreen; real-scene fps deferred to human verification.

## Validation Architecture

> `workflow.nyquist_validation` is `true` in `.planning/config.json`. This section is REQUIRED. `tdd_mode` is also `true`.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (>=7.0.0, `[dev]` extra) + PySide6 6.11.1 offscreen |
| Config file | `pytest.ini` (`testpaths=tests`, `pythonpath=src`, `asyncio_mode=auto`) |
| Quick run command | `PYTHONPATH=src QT_QPA_PLATFORM=offscreen pytest tests/test_sim_step_worker.py tests/test_render_poll_loop.py tests/test_viewport_playback.py -v` |
| Full suite command | `PYTHONPATH=src pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID / SC | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SC#1 (GUI-11) — preview animates (bug #1) | `SimStepWorker` calls `simulator.step()` at ~50 Hz; `snapshot_ready` fires; render-poll renders the new snapshot | integration (offscreen, MockSimulator) | `PYTHONPATH=src QT_QPA_PLATFORM=offscreen pytest tests/test_sim_step_worker.py::TestSimStepWorkerAccumulator -v` | ❌ Wave 0 |
| SC#2 (GUI-11) — >30 fps (bug #2) | Render-poll cadence ≥30 Hz when render is instant (offscreen proxy); real-fps is a `verification: backstop` truth | integration (offscreen proxy) + backstop | `pytest tests/test_render_poll_loop.py::TestRenderPollCadence -v` (proxy); real-fps = human/backstop | ❌ Wave 0 |
| SC#3 (GUI-11) — pause/resume/step-one | `set_paused(True)` stops the accumulator timer (no `step()` calls); `set_paused(False)` resumes; `step_one()` increments `step_count` by exactly 1 while paused and publishes exactly 1 snapshot | unit/integration (offscreen, MockSimulator) | `pytest tests/test_sim_step_worker.py::TestPauseResumeStepOne -v` | ❌ Wave 0 |
| SC#4 (GUI-11) — render/sim decoupled + ~30 Hz publish cap | A slow render does NOT slow physics (mock `render()` sleeps 80 ms; `step_count` still advances at ~50 Hz); a fast sim does NOT flood the UI (assert `snapshot_ready` fired ≤ ~3 times in 100 ms for a 50 Hz sim with 30 Hz cap) | integration (offscreen, MockSimulator with controllable `render_delay`) | `pytest tests/test_sim_step_worker.py::TestDecouplingAndPublishCap -v` | ❌ Wave 0 |
| D-04 teardown | Close mid-step: `aboutToClose` → `sim_worker.stop()` → `thread.quit()` + `wait(3000)` → `isRunning()==False`; no segfault; no `RuntimeError: Internal C++ object already deleted` | integration (offscreen, MockSimulator) | `pytest tests/test_viewport_playback.py::TestCloseMidStepCleanExit -v` | ❌ Wave 0 |
| D-06/D-09 toolbar + speed | `QToolBar` exists with `objectName="toolbar_playback"`; speed `QComboBox` has the 5 values; changing it calls `sim_worker.set_speed` | integration (offscreen GUI introspection) | `pytest tests/test_viewport_playback.py::TestPlaybackToolbar -v` | ❌ Wave 0 |
| D-08 status-bar playback segment | 5th permanent `QLabel` exists; reflects "▶ playing 1x" / "⏸ paused" | unit/integration (offscreen) | `pytest tests/test_viewport_playback.py::TestPlaybackStatus -v` | ❌ Wave 0 |
| D-09 speed scaling | At 2x, `step_count` after 100 ms wall ≈ 2× the 1x count; at 0.5x ≈ half (within timer jitter) | integration (offscreen, MockSimulator, real `time.monotonic`) | `pytest tests/test_sim_step_worker.py::TestSpeedScaling -v` | ❌ Wave 0 |
| D-11 load-paused | `update_scene` leaves `sim_worker._paused == True`; toolbar Play button unchecked; status "⏸ paused" | integration (offscreen) | `pytest tests/test_viewport_playback.py::TestLoadPaused -v` | ❌ Wave 0 |
| D-12 static-scene hint | A scene with no robots/tissues/fluid → status shows "static scene — no dynamics"; worker still steps on Play | unit (`_scene_has_dynamics` predicate) + integration | `pytest tests/test_viewport_playback.py::TestStaticSceneHint -v` | ❌ Wave 0 |
| Phase 41 D-07 extension | New `QToolBar` has a non-empty unique `objectName` (extend `TestDockObjectNames` to also collect `QToolBar` children) | unit (introspection) | `pytest tests/test_dock_state.py::TestDockObjectNames -v` (EXTEND) | ✅ (extend existing) |
| step-one while paused renders | After `step_one()`, the render-poll's next tick renders the new snapshot (render-poll stays alive while paused) | integration (offscreen, MockSimulator) | `pytest tests/test_render_poll_loop.py::TestStepOneRendersWhilePaused -v` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `PYTHONPATH=src QT_QPA_PLATFORM=offscreen pytest tests/test_sim_step_worker.py tests/test_render_poll_loop.py tests/test_viewport_playback.py -v` (new phase test files — fast, offscreen, no real physics)
- **Per wave merge:** `PYTHONPATH=src pytest tests/ -v` (full suite — confirms no regression in the 1,513-test baseline shipped at v0.6.0 + Phase 41's additions)
- **Phase gate:** Full suite green before `/gsd-verify-work`; plus all new SC tests green offscreen; plus the `verification: backstop` for SC#2 real-fps noted in `41-VERIFICATION.md`-style backstop list.

### Wave 0 Gaps
- [ ] `tests/test_sim_step_worker.py` — accumulator + publish cap + step-one + speed scaling + teardown (MockSimulator + controllable clock). Covers SC#1, SC#3, SC#4, D-09, D-04.
- [ ] `tests/test_render_poll_loop.py` — latest-snapshot render, skip-when-no-new-snapshot, `_running` guard, step-one-renders-while-paused, cadence ≥30 Hz with instant render (SC#2 proxy). Covers SC#2 proxy, Pitfall 6.
- [ ] `tests/test_viewport_playback.py` — toolbar/shortcuts/status-bar wiring, load-paused on `update_scene`, close-mid-step teardown, static-scene hint. Covers D-06/D-08/D-11/D-12, D-04 UI side.
- [ ] Extend `tests/test_dock_state.py::TestDockObjectNames` to also collect `QToolBar` children and assert `toolbar_playback` has a non-empty unique `objectName` (Phase 41 D-07 extension).
- [ ] Shared `qapp` + `isolated_home` fixtures — duplicate the small fixture in each new test file (per `41-PATTERNS.md` §test pattern: "either import it or duplicate the small fixture in the new file") OR place the new files in `tests/gui/` to reuse `tests/gui/conftest.py`.
- [ ] No framework install needed — pytest + PySide6 already in `[dev]`/`[gui]`.

### TDD Eligibility (tdd_mode is `true`)

| Implementation Task | TDD-eligible? | Rationale |
|---------------------|---------------|-----------|
| `SimStepWorker` accumulator + publish cap + `step_one` + `set_speed` + `set_paused` | ✅ `type: tdd` | Pure logic with a `MockSimulator` + controllable clock: assert step counts, publish counts, step-one increments by 1, speed scales counts. Fully testable headless offscreen. |
| `SimStepWorker.stop()` + `thread.quit()`+`wait(3000)` teardown | ✅ `type: tdd` | Defined I/O: cancel flag set, timer stopped, `isRunning()==False` after `wait()`. Mirror Phase 41 `TestCloseMidCallMockSlow`. |
| `RenderPollLoop` latest-snapshot render + skip-when-no-new + `_running` guard | ✅ `type: tdd` | Defined I/O with a `MockSimulator`: assert render called only on new `frame_id`, not called after `stop()`, called once for `step_one` while paused. |
| `_scene_has_dynamics` predicate (D-12) | ✅ `type: tdd` | Pure function on `SceneDefinition`: assert True for scenes with robots/tissues/fluid, False otherwise. (Verify field names first — A4.) |
| `SimStepWorker` QThread wiring (`moveToThread`, `started->start`, `aboutToClose.connect(stop)`) | ❌ standard (UI wiring) | Signal/slot connection glue; the teardown test verifies it end-to-end. |
| `QToolBar` + `QShortcut` + status-bar segment | ❌ standard (UI wiring) | Introspection tests (objectName, 5th label exists, combo has 5 values) cover the wiring. |
| `ViewportPanel.update_scene` re-bind + load-paused (D-11) | ✅ `type: tdd` | Defined I/O: after `update_scene`, `sim_worker._paused == True`, toolbar Play unchecked, status "⏸ paused". Testable offscreen with `MockSimulator`. |
| `RenderPollLoop`/`SimStepWorker` module extraction (file structure) | N/A | Structural; covered by import + integration tests. |

## Security Domain

> `security_enforcement` is not explicitly `false` in `.planning/config.json` — treat as enabled. This phase touches no auth, crypto, or untrusted-input boundaries beyond what already exists. The worker reads no secrets and accepts no untrusted input (the scene is loaded via the existing `_default_load_simulator`).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | N/A — desktop editor, no auth. |
| V3 Session Management | no | N/A — no sessions. |
| V4 Access Control | no | N/A — single-user desktop. |
| V5 Input Validation | yes (indirectly) | `safe_error_message()` (`_safe_error.py:34-43`) must wrap any user-facing error/hint (static-scene hint, teardown-timeout surfacing). The worker accepts no external input; the scene is already validated by `SceneDefinition` before load. `[VERIFIED: _safe_error.py]` |
| V6 Cryptography | no | N/A — no crypto. |
| V7 Error Handling | yes | `stop()`/`closeEvent`/`update_scene` are best-effort with broad `suppress` (existing `main_window.py:399-409` pattern); `stop()` timeout is `logger.warning(...)` (log-only, NOT user-facing — no redaction needed per Phase 41 §Security Domain); if surfaced to the status bar, route through `safe_error_message`. `[CITED: 41-RESEARCH.md §Security Domain]` |

### Known Threat Patterns for PySide6/Qt desktop + QThread

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API key leakage in error dialogs | Information disclosure | N/A this phase — the worker reads no API keys; `safe_error_message()` reuse for any status-bar hint. `[VERIFIED: _safe_error.py]` |
| Worker thread crash on close leaves simulator state inconsistent | Denial of service (crash) | D-04 cooperative `stop()` + `wait(3000)` + log-and-proceed (NEVER `terminate()`); `aboutToClose` before `super().closeEvent()`. `[CITED: 41-RESEARCH.md §Pattern 2]` |
| `render()` from the wrong thread → GL context corruption | Denial of service (crash) | `render()` ONLY on the UI thread (`RenderPollLoop`); worker only `step()` + `get_state()`. |
| Status-bar hint leaks internal path/scene detail | Information disclosure | `safe_error_message()` on the static-scene hint string if it includes scene content; keep the hint generic ("static scene — no dynamics"). |

## Sources

### Primary (HIGH confidence — direct source read this session)
- `src/surg_rl/editor/viewport.py` — `_tick:189-290`, `stop:169-180`, `update_scene:399-415`, `_default_load_simulator:418-482`, `_display_array:306-353`, `_maybe_update_fps:292-304`, `_editor_camera_*` push `222-234`, `_running` guard `142`, `_FRAME_INTERVAL_MS=50` `31`.
- `src/surg_rl/editor/main_window.py` — `aboutToClose:59`, `_viewport_panel` creation `80-84`, `aboutToClose.connect(_llm_panel.stop):139`, `_build_status_bar:204-213` (4 permanent labels), `_update_fps_status:221`, `_refresh_viewport_and_tree:323` + `update_scene` call `332`, `closeEvent:394-411` (emit `:400`, `viewport.stop():407`, `save_window:410`), `_wire_shortcuts:180-183` (`Ctrl+R`).
- `src/surg_rl/editor/llm_panel.py` — `TextParserWorker:17`, `_on_generate` QThread wiring `117-128`, `stop():130-158` (cancel property + `thread.quit()` + `thread.wait(3000)` + timeout log + no `deleteLater`).
- `src/surg_rl/simulators/base_simulator.py` — `step:219`, `render:231`, `get_state:252`, `close:270`, `State:90-111`, `StepResult:114-135`.
- `src/surg_rl/simulators/mujoco_simulator.py` — `step:207` (`if action is not None: self._apply_action(action)` at `220-221`), `mj_resetData` in `reset:201`, `_loaded` guard `216`.
- `src/surg_rl/simulators/pybullet_simulator.py` — `step:940` (`if action is not None` at `946-947`), `_loaded` guard `942`, `render` `_editor_camera_*` read `990-995`.
- `src/surg_rl/editor/__init__.py` — `LazyImport:31-42` + `HAS_GUI:42`.
- `src/surg_rl/editor/_safe_error.py` — `safe_error_message:34-43` + redaction patterns.
- `src/surg_rl/editor/_settings.py` — `save_window/load_window:39-48` (NOT extended this phase per D-10).
- `pyproject.toml:148-152` — `[gui]` extra: `PySide6>=6.8.0,<7.0`, `markdown-it-py>=3.0.0`, `imageio>=2.31.0` (no new deps).
- `pip show PySide6` — Version 6.11.1 (verified this session).
- `tests/test_dock_state.py` — the offscreen test pattern (`qapp`, `isolated_home`, `pytestmark skipif`, `TestCloseMidCallMockSlow`, `TestDockObjectNames`) Phase 42 tests mirror/extend.

### Secondary (MEDIUM confidence — v0.7.0 research + Phase 41 artifacts, cross-checked)
- `.planning/research/SUMMARY.md` §"Architecture Approach" (components 1–2, 8–10), §"Critical Pitfalls" #1 (render/sim coupling) + #7 (edits bypass schema), §"Bug Reconciliation" (bugs #1/#2 single root cause).
- `.planning/research/PITFALLS.md` Pitfall 1 (accumulator pattern, publish cap, warning-sign grep), Pitfall 3 (QThread teardown ordering), Pitfall 8 (timer guard + `__del__`).
- `.planning/phases/41-.../41-CONTEXT.md` D-04 (`aboutToClose`), D-05 (`stop()` semantics), D-06 (`update_scene` in-place swap), D-07 (`objectName` discipline).
- `.planning/phases/41-.../41-RESEARCH.md` §Pattern 2 (cooperative teardown), §Code Examples ("Cooperative QThread teardown" — verified on PySide6 6.11.1: `quit()`+`wait(3000)` → `True`, `isRunning()==False`), §Validation Architecture (TDD eligibility table).
- `.planning/phases/41-.../41-PATTERNS.md` — `LLMPanel.stop()` skeleton, offscreen test harness, `objectName` convention, logger convention, best-effort teardown suppress.
- `.planning/config.json` — `nyquist_validation: true`, `tdd_mode: true`, `use_worktrees: true`, `code_review: true`, `code_review_depth: deep`.

### Tertiary (LOW confidence — needs implementer verification)
- `src/surg_rl/scene_definition/schema.py` — NOT read this session; the D-12 static-scene predicate field names (A4) need confirmation against the actual `SceneDefinition`/`EnvironmentConfig` schema.
- `simulator.step()` thread-safety off the UI thread (A1) — the v0.7.0 research premise; verify on first real-scene integration.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — PySide6 6.11.1 installed and verified; no new deps confirmed against `pyproject.toml:148-152`; QThread/QTimer teardown verified in Phase 41 on the same runtime.
- Architecture: HIGH — D-01..D-12 are locked in CONTEXT.md and re-verified against live source this session (all line numbers/signatures confirmed); the implementer-discretion gaps are filled with concrete, Qt-idiomatic shapes that honor the locked decisions.
- Pitfalls: HIGH — Pitfalls 1/3/8 cross-checked against the v0.7.0 PITFALLS.md + Phase 41 research; new pitfalls (GL thread-affinity, simulator-close-during-step, accumulator spiral, speed-scaling axis) derived from direct source read + Qt conventions.
- D-12 resolution: MEDIUM — the predicate approach is sound but field names (A4) need schema confirmation.

**Research date:** 2026-07-16
**Valid until:** 2026-08-16 (30 days — stable; PySide6 is a locked LTS dep, no new packages this phase, source verified unchanged on `main` at HEAD `6935e38`)
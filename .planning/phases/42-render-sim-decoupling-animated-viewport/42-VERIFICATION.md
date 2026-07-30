---
phase: 42-render-sim-decoupling-animated-viewport
verified: 2026-07-29T23:55:00Z
status: human_needed
score: 16/17 must-haves verified
behavior_unverified: 1
overrides_applied: 0
gaps: []
deferred:
  - truth: "test_sim_step_worker.py::TestPauseResumeStepOne::test_pause_then_resume_advances_then_holds — off-by-one (step_count 5 vs 4) under cross-test timing pressure"
    addressed_in: "Future phase (test-only fix)"
    evidence: "deferred-items.md — pre-existing flakiness in Plan 01 component; passes consistently in isolation; suggested fix is to increase _settle wait from 0.15s to 0.3s. Not a Plan 02 regression. SC#3 still verified by test_step_one_advances_exactly_one_while_paused."
behavior_unverified_items:
  - truth: "On a real macOS display, a typical scene animates at >30 fps (SC#2 backstop)"
    test: "Open the editor on macOS with a typical scene (e.g. scenes/minimal_scene.json or a scene with robots/tissues), press Play, observe the viewport animating smoothly"
    expected: "Viewport animates at >30 fps (smooth motion, not the <10fps frozen state from bug #2). The SC#2 proxy (offscreen cadence >=30Hz) is verified by TestRenderPollCadence, but real-display fps is a backstop that cannot be measured programmatically."
    why_human: "Real GL/display fps on a macOS display with a real simulator backend cannot be asserted in a headless CI/offscreen pytest run — the offscreen MockSimulator cadence is a proxy, not the real-render path. verification: backstop in PLAN frontmatter explicitly defers this to human observation."
human_verification:
  - test: "Open editor on macOS with a typical scene (robots/tissues), press Play, observe viewport motion"
    expected: "Smooth >30 fps animation; not the <10fps frozen state (bug #2 closed); preview animates rather than showing a single static frame (bug #1 closed)"
    why_human: "Real-display fps with a real simulator backend cannot be asserted in a headless offscreen pytest run. PLAN marks this truth verification: backstop."
  - test: "Manually exercise the playback toolbar: Play/Pause toggle, Step button, Speed combo (0.25x/0.5x/1x/2x/4x), Space shortcut, '.' shortcut"
    expected: "Play resumes animation, Pause holds, Step advances exactly one frame, Speed scales motion (2x visibly faster, 0.25x slower), Space toggles, '.' steps one. Status bar shows '▶ playing {speed}x' / '⏸ paused' / '⏸ paused (static scene — no dynamics)' correctly."
    why_human: "Toolbar visual interaction + status-bar text + perceived speed scaling are user-flow behaviors; the wiring is unit-tested but the perceived UX is human-judgment."
  - test: "Close the editor mid-animation (while playing) and confirm no segfault / no 'RuntimeError: Internal C++ object already deleted'"
    expected: "Editor exits cleanly within ~3s; no segfault; no Qt warning about QThread destroyed while running."
    why_human: "Real close-mid-step teardown on a live display with a real simulator backend is a runtime invariant; TestCloseMidStepCleanExit covers it offscreen with a MockSimulator, but the real-path segfault freedom is human-confirmable."
  - test: "Prohibition review (6 flagged-unverified judgment-tier prohibitions from PLAN frontmatter)"
    expected: "Confirm the LLM-judge verdicts below by code inspection: (a) no simulator.render() on the SimStepWorker thread; (b) only ONE render singleShot chain on the UI thread + ONE sim QTimer on the QThread worker; (c) no thread.terminate() calls; (d) no thread.deleteLater() before thread.wait(); (e) no playback state written to SceneDefinition or QSettings; (f) ViewportPanel is NOT recreated on scene swap."
    why_human: "PLAN frontmatter marked these prohibitions status: unverified, flagged: true (descriptor-less at planning time). The verifier's grep-based LLM-judge found all six hold in the live code, but per autonomous-verify policy these are NON-AUTHORITATIVE judgments flagged for human review."
---

# Phase 42: Render/Sim Decoupling & Animated Viewport — Verification Report

**Phase Goal:** User sees an animated scene preview (simulation steps live in the editor viewport) at >30 fps — fixes bugs #1 (immobile preview) + #2 (<10fps)
**Verified:** 2026-07-29T23:55:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #   | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1   | SC#1: SimStepWorker calls simulator.step(None) at ~50 Hz via fixed-step accumulator and publishes State snapshots via queued snapshot_ready signal (physics advances, preview no longer frozen) | ✓ VERIFIED | sim_step_worker.py:298-335 `_tick` accumulator with `while accum >= sim_dt=0.02: step(None); accum -= sim_dt`, `_PUBLISH_HZ=30` cap, `snapshot_ready.emit(_publish())`. Test `TestSimStepWorkerAccumulator::test_accumulator_advances_physics` PASSES. Behavior-dependent truth exercised by test. |
| 2   | SC#2 proxy: RenderPollLoop's self-rescheduling QTimer.singleShot has 33 ms cadence and fires at >=30 Hz with instant-render MockSimulator | ✓ VERIFIED | render_poll_loop.py:50 `_FRAME_INTERVAL_MS=33`, :179 `QTimer.singleShot(_FRAME_INTERVAL_MS, self._tick)`, `_tick_count` instrumentation at :149. Test `TestRenderPollCadence::test_render_poll_fires_at_least_30hz` PASSES. |
| 3   | SC#2 backstop: on a real macOS display, a typical scene animates at >30 fps | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Code + wiring present and behaviorally exercised offscreen (cadence proxy passes), but real-display fps with a real GL backend is a `verification: backstop` truth that abstains without human observation. Routes to Human Verification. |
| 4   | SC#3: set_paused(True) stops the accumulator QTimer; set_paused(False) resumes; step_one() increments step_count by exactly 1 while paused and publishes exactly 1 snapshot | ✓ VERIFIED | sim_step_worker.py:256-295 (set_paused, step_one). Tests `TestPauseResumeStepOne::test_step_one_advances_exactly_one_while_paused` and `TestStepOneRendersWhilePaused::test_new_snapshot_renders_on_next_poll` PASS. Behavior-dependent transition exercised. |
| 5   | SC#4: slow render does NOT slow physics (render sleeps 80ms; step_count still advances at ~50 Hz because step() runs on the worker QThread); fast sim does NOT flood UI (snapshot_ready <= ~3 times in 100 ms with 30 Hz cap) | ✓ VERIFIED | sim_step_worker.py:318-332 — step loop runs on worker QThread under `_sim_lock`; publish cap `now - last_publish >= 1.0/_PUBLISH_HZ`. Test `TestDecouplingAndPublishCap::test_slow_ui_thread_does_not_slow_physics` and `::test_publish_cap_limits_snapshot_ready_to_30hz` PASS. |
| 6   | D-09: at 2x speed, step_count after 100ms ~= 2x the 1x count; at 0.5x ~= half (speed scales wall_dt, NOT sim_dt) | ✓ VERIFIED | sim_step_worker.py:312 `self._accum += wall_dt * self._speed` (wall_dt scaled, sim_dt fixed at 0.02). Tests `TestSpeedScaling::test_speed_2x_doubles_step_count`, `::test_speed_0_5x_halves_step_count` PASS. |
| 7   | Pitfall 6: after step_one() while paused, the render-poll's next tick renders the new snapshot (RenderPollLoop stays alive at ~30 Hz while paused) | ✓ VERIFIED | render_poll_loop.py:152-179 — `_running` guard is independent of worker paused state; `_tick` reschedules unconditionally while `_running`. Test `TestStepOneRendersWhilePaused::test_new_snapshot_renders_on_next_poll` PASS. |
| 8   | FLAGGED ASSUMPTION (boundary): accumulator threshold `accum >= sim_dt` inclusive; publish cap `now - last_publish >= 1.0/_PUBLISH_HZ` inclusive; wait(3000) timeout returns False on timeout (NEVER terminate); 5 speeds exactly 0.25/0.5/1/2/4 | ✓ VERIFIED | sim_step_worker.py:320 `while self._accum >= sim_dt`, :329 `if now - self._last_publish >= 1.0 / _PUBLISH_HZ`. main_window.py:302-303 `wait(3000)` with log-on-timeout, no terminate. main_window.py:334 speeds `("0.25x", "0.5x", "1x", "2x", "4x")`. |
| 9   | FLAGGED ASSUMPTION (precision): wall_dt recomputed from time.monotonic() each tick (not accumulated); sim_dt fixed at 0.02; spiral cap _MAX_STEPS_PER_TICK=8 resets accum to 0.0; frame_id monotonic int | ✓ VERIFIED | sim_step_worker.py:306-327 — `now = time.monotonic(); wall_dt = now - self._last_wall; self._last_wall = now`; :324-327 spiral cap reset; :330 `_frame_id += 1` (int). |
| 10  | D-11: after ViewportPanel.update_scene(scene), sim_worker._paused == True, toolbar Play unchecked, status bar shows '⏸ paused' | ✓ VERIFIED | viewport.py:536-557 update_scene pauses worker via `_pause_requested.emit(True)` then `_bind_loaded_simulator` reaffirms paused. main_window.py:322-324 Play action unchecked by default. Test `TestLoadPaused::test_update_scene_loads_paused` PASS. |
| 11  | D-06: QToolBar objectName='toolbar_playback' docked at TopToolBarArea with Play/Pause toggle QAction (setCheckable), Step-one QAction, speed QComboBox objectName='combo_playback_speed' with exactly 5 items '0.25x'..'4x' default '1x'; Space → toggle; '.' → step-one; Ctrl+R unchanged | ✓ VERIFIED | main_window.py:307-341 `_build_playback_toolbar`, :382-394 `_wire_shortcuts` with Space + '.' QShortcuts, Ctrl+R at :384. Test `TestPlaybackToolbar::test_playback_toolbar_has_required_widgets` PASS. |
| 12  | D-08: 5th permanent QLabel _status_playback added to status bar; reflects '▶ playing {speed}x' / '⏸ paused' / '⏸ paused (static scene — no dynamics)' | ✓ VERIFIED | main_window.py:505-512 `_status_playback` QLabel added as permanent widget; :447-457 `_update_playback_status` sets the three text variants. Test `TestPlaybackStatus::test_status_bar_has_playback_label_and_toggles` PASS. |
| 13  | D-12: _scene_has_dynamics(scene) returns True when scene.robots OR scene.tissues non-empty OR scene.fluid (DIRECT field on SceneDefinition) is not None; False otherwise (instruments-only is static); structural schema-level check, NOT runtime heuristic | ✓ VERIFIED | viewport.py:41-65 `_scene_has_dynamics` reads `scene.robots`, `scene.tissues`, `scene.fluid` directly. Tests `TestStaticSceneHint` (6 tests covering empty/robots/tissues/fluid/instruments-only/direct-fluid) PASS. |
| 14  | D-04: closing the editor mid-step fires aboutToClose → sim_worker.stop() then thread.quit() + thread.wait(3000) → thread.isRunning()==False; no segfault; aboutToClose fires BEFORE viewport.stop() | ✓ VERIFIED | main_window.py:270 `aboutToClose.connect(self._stop_sim_worker)`, :272-303 `_stop_sim_worker` (cancel flag + thread.quit + wait(3000) + log-on-timeout, NO terminate). closeEvent at :698-703 emits aboutToClose BEFORE super().closeEvent. Test `TestCloseMidStepCleanExit::test_close_mid_step_clean_exit` PASS. Behavior-dependent cancellation invariant exercised. |
| 15  | Phase 41 D-06: ViewportPanel.update_scene re-binds worker + render loop in place (pause → close old sim → swap scene + reset_camera → load new sim → render_loop.bind_simulator → sim_worker.bind_scene.emit → set_paused(True)); NO ViewportPanel recreation, NO setCentralWidget | ✓ VERIFIED | viewport.py:510-557 update_scene — no widget reconstruction; `_bind_loaded_simulator` re-binds in place. Test `TestLoadPaused::test_update_scene_loads_paused` exercises the in-place swap path. |
| 16  | Phase 41 D-07 extension: EditorWindow.findChildren(QToolBar) non-empty, every QToolBar has non-empty unique objectName, 'toolbar_playback' present | ✓ VERIFIED | main_window.py:317 `tb.setObjectName("toolbar_playback")` BEFORE addToolBar (:320). Test `TestToolbarObjectNames` (test_dock_state.py:87-114) asserts non-empty unique objectNames + 'toolbar_playback' present. PASS. |
| 17  | Pitfall 3: ViewportPanel.stop() and update_scene() pause the worker BEFORE closing the shared simulator — worker never mid-step() while simulator.close() runs | ✓ VERIFIED | viewport.py:536-546 update_scene pauses worker (`_pause_requested.emit(True)`) BEFORE `_simulator.close()` under `_sim_lock`; :332-346 stop() pauses render_loop + sim_worker BEFORE close(). Test `TestCloseMidStepCleanExit` exercises the ordering. |

**Score:** 16/17 truths verified (1 present, behavior-unverified — backstop real-fps)

### Required Artifacts

| Artifact | Status | Details |
| -------- | ------ | ------- |
| `src/surg_rl/editor/sim_step_worker.py` | ✓ VERIFIED | 351 lines. SimStepWorker(QObject) with `snapshot_ready` Signal(object), `_Snapshot` dataclass, accumulator constants `_SIM_HZ=50`, `_PUBLISH_HZ=30`, `_MAX_STEPS_PER_TICK=8`. Slots: start, bind_scene, set_paused, set_speed, step_one. Cooperative stop(). Reaper registry + `reap_all_sim_runtimes` (commit 791b754 shutdown-segfault fix). Imported by main_window.py:23. |
| `src/surg_rl/editor/render_poll_loop.py` | ✓ VERIFIED | 235 lines. RenderPollLoop(QObject) with on_snapshot, bind_simulator, start, stop, _tick (self-rescheduling QTimer.singleShot(33)), _render (pushes camera offset, calls sim.render under _sim_lock, hands ndarray to canvas.set_image), _maybe_update_fps. Imported by main_window.py:21. |
| `src/surg_rl/editor/viewport.py` (modified) | ✓ VERIFIED | `_scene_has_dynamics` predicate (:41-65); `_tick` split (:359-367 — render+step delegated); `set_image`/`set_text`/`width`/`height`/`camera_name` canvas adapter (:370-401); `update_scene` in-place re-bind (:510-557); `stop()` extended (:330-357). Wired to RenderPollLoop + SimStepWorker via `set_playback`. |
| `src/surg_rl/editor/main_window.py` (modified) | ✓ VERIFIED | `_sim_thread`/`_sim_worker`/`_render_loop` created (:113-184), `moveToThread` + `started.connect(start)` + `finished.connect(deleteLater)` + `snapshot_ready.connect(on_snapshot, QueuedConnection)` + proxy signals. `_build_playback_toolbar` (:307-341), `_wire_shortcuts` Space + '.' (:382-394), `_stop_sim_worker` (:272-303), `_status_playback` (:505-512), `_update_playback_status` (:447-457). |
| `tests/test_sim_step_worker.py` | ✓ VERIFIED | 7 tests, 4 classes: TestSimStepWorkerAccumulator (SC#1), TestPauseResumeStepOne (SC#3), TestDecouplingAndPublishCap (SC#4), TestSpeedScaling (D-09). All PASS. |
| `tests/test_render_poll_loop.py` | ✓ VERIFIED | 4 tests: TestRenderPollCadence (SC#2 proxy), TestStepOneRendersWhilePaused (Pitfall 6), TestSkipNoNewSnapshot, TestRunningGuard. All PASS. |
| `tests/test_viewport_playback.py` | ✓ VERIFIED | 11 tests: TestPlaybackToolbar (D-06), TestPlaybackStatus (D-08), TestLoadPaused (D-11), TestStaticSceneHint (D-12 — 6 sub-tests), TestCloseMidStepCleanExit (D-04). All PASS. |
| `tests/test_dock_state.py` (extended) | ✓ VERIFIED | TestToolbarObjectNames (:87-114) asserts every QToolBar has non-empty unique objectName + 'toolbar_playback' present. PASS. |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| SimStepWorker.snapshot_ready | RenderPollLoop.on_snapshot | Qt.QueuedConnection | ✓ WIRED | main_window.py:144-146 `self._sim_worker.snapshot_ready.connect(self._render_loop.on_snapshot, QtCore.Qt.ConnectionType.QueuedConnection)` |
| SimStepWorker._tick QTimer (worker thread) | simulator.step(None) + get_state() | accumulator in `_tick` | ✓ WIRED | sim_step_worker.py:318-335 — step + get_state under `_sim_lock` |
| RenderPollLoop._tick QTimer.singleShot(33) (UI thread) | simulator.render(mode='rgb_array', w, h, camera_name) | _render under _sim_lock | ✓ WIRED | render_poll_loop.py:200-206 — render under `_sim_lock`, hands arr to `canvas.set_image` |
| SimStepWorker.stop() | thread.quit() + thread.wait(3000) | _stop_sim_worker controller | ✓ WIRED | main_window.py:272-303 — cancel flag + timer.stop (in worker.stop) + thread.quit + wait(3000) + log-on-timeout (controller) |
| EditorWindow.aboutToClose | sim_worker.stop + thread teardown | aboutToClose.connect(_stop_sim_worker) | ✓ WIRED | main_window.py:270, fires BEFORE viewport.stop at :407 |
| ViewportPanel.update_scene | sim_worker.set_paused(True) + render_loop.bind_simulator + sim_worker.bind_scene.emit | in-place swap | ✓ WIRED | viewport.py:536-557 + _bind_loaded_simulator |
| ViewportPanel.stop | render_loop.stop() + sim_worker.set_paused(True) BEFORE simulator.close() | Pitfall 3 ordering | ✓ WIRED | viewport.py:330-357 |
| _act_play_pause.toggled | sim_worker.set_paused (queued) | _play_pause_request proxy signal | ✓ WIRED | main_window.py:339, :402-412 |
| _act_step_one.triggered | sim_worker.step_one (queued) | _step_one_request proxy | ✓ WIRED | main_window.py:340, :414-419 |
| _speed_combo.currentTextChanged | sim_worker.set_speed (queued) | _speed_request proxy | ✓ WIRED | main_window.py:341, :421-434 |
| QShortcut('Space') | _toggle_play_pause | activated.connect | ✓ WIRED | main_window.py:391-392 |
| QShortcut('.') | _on_step_one | activated.connect | ✓ WIRED | main_window.py:393-394 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| ViewportPanel canvas | `_pixmap` (QPixmap) | RenderPollLoop._render → sim.render → canvas.set_image → _display_array → QImage → QPixmap | Yes — sim.render returns ndarray from real/simulated GL framebuffer (or PyBullet DIRECT fallback) | ✓ FLOWING |
| RenderPollLoop._latest_snapshot | `_latest_snapshot` (_Snapshot) | SimStepWorker.snapshot_ready.emit(_publish()) cross-thread via QueuedConnection | Yes — `_publish()` returns `_Snapshot(state=sim.get_state(), frame_id=int)` | ✓ FLOWING |
| SimStepWorker._frame_id | monotonic int counter | `_tick` increments on publish; `step_one` increments by 1 | Yes — int counter, no float precision loss | ✓ FLOWING |
| Status bar _status_playback | QLabel text | `_update_playback_status(playing, speed, static)` reads `self._act_play_pause.isChecked()`, `self._speed_combo.currentText()`, `self._viewport_panel._static_scene` | Yes — all three inputs are live widget/state reads | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Phase 42 unit + integration suite green | `PYTHONPATH=src python -m pytest tests/test_sim_step_worker.py tests/test_render_poll_loop.py tests/test_viewport_playback.py -q` | 22 passed in 2.26s | ✓ PASS |
| Dock state + editor smoke (toolbar objectName, no-crash) | `PYTHONPATH=src python -m pytest tests/test_dock_state.py tests/gui/test_editor_smoke.py -q` | 11 passed, 1 skipped in 3.71s | ✓ PASS |
| Flaky deferred test in isolation | `PYTHONPATH=src python -m pytest tests/test_sim_step_worker.py::TestPauseResumeStepOne::test_pause_then_resume_advances_then_holds -v` | 1 passed in 0.38s | ✓ PASS (in isolation — see deferred) |
| SC#1 accumulator behavior | `TestSimStepWorkerAccumulator::test_accumulator_advances_physics` | PASS | ✓ PASS |
| SC#3 pause/step-one invariant | `TestPauseResumeStepOne::test_step_one_advances_exactly_one_while_paused` | PASS | ✓ PASS |
| SC#4 decoupling + publish cap | `TestDecouplingAndPublishCap::test_slow_ui_thread_does_not_slow_physics` + `::test_publish_cap_limits_snapshot_ready_to_30hz` | PASS | ✓ PASS |
| D-04 close-mid-step clean exit | `TestCloseMidStepCleanExit::test_close_mid_step_clean_exit` | PASS | ✓ PASS |
| D-11 load-paused | `TestLoadPaused::test_update_scene_loads_paused` | PASS | ✓ PASS |

### Probe Execution

No phase-declared probes (scripts/*/tests/probe-*.sh) found in PLAN/SUMMARY; the phase's runnable checks are pytest behavioral spot-checks (covered above).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| GUI-11 | 42-01, 42-02 | Animated scene preview at >30 fps with render/sim decoupling via SimStepWorker (QThread) + RenderPollLoop (UI thread); pause/resume/step-one; fixes bugs #1 + #2 | ✓ SATISFIED (with backstop human-verification) | All SC#1, SC#2 proxy, SC#3, SC#4 verified by passing behavioral tests; SC#2 backstop (real-display >30fps) routes to human. Decoupling implemented per spec. |

No orphaned requirements — GUI-11 is the only requirement mapped to Phase 42 in REQUIREMENTS.md and both plans claim it.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| (none in source) | — | — | — | No TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER markers in sim_step_worker.py, render_poll_loop.py, viewport.py, or main_window.py. No empty implementations, no hardcoded empty data flowing to render. | ℹ️ Info |

Deferred note (test-only, not source): `tests/test_sim_step_worker.py::TestPauseResumeStepOne::test_pause_then_resume_advances_then_holds` is a known flaky test under cross-test timing pressure (documented in deferred-items.md). It passes consistently in isolation. Not a source anti-pattern; SC#3 is independently covered by `test_step_one_advances_exactly_one_while_paused`.

### Prohibition Review (judgment-tier, flagged-unverified — LLM-judge non-authoritative)

The PLAN frontmatter declared 6 prohibitions `status: unverified, flagged: true` (descriptor-less at planning time). The verifier's grep-based LLM-judge found all six hold in the live code; per autonomous-verify policy these are NON-AUTHORITATIVE verdicts flagged for human review:

| # | Prohibition | LLM-judge verdict | Evidence |
| --- | ----------- | ------------------ | -------- |
| 1 | Must NOT call simulator.render() from the SimStepWorker worker thread | OBSERVED-HELD | `grep -n "\.render(" src/surg_rl/editor/sim_step_worker.py` returns no matches; only `step()` + `get_state()` called on worker. render() lives in render_poll_loop.py:201. |
| 2 | Must NOT add a second QTimer.singleShot chain on the main thread for stepping | OBSERVED-HELD | Only `render_poll_loop.py:133/179` has a singleShot chain (UI-thread render); `sim_step_worker.py:233/274` uses `self._timer.start(int(1000/_SIM_HZ))` on the worker QThread (NOT main thread). `property_form.py:98` is a validation debounce timer, not a step/render chain. ONE render timer + ONE sim loop. |
| 3 | Must NOT call thread.terminate() on a wait() timeout | OBSERVED-HELD | `grep -rn "thread.terminate\|\.terminate()" src/surg_rl/editor/` finds only docstring mentions in main_window.py:283, llm_panel.py:138, sim_step_worker.py:15/345. main_window.py:302-303 calls `wait(3000)` and logs on timeout — no terminate. |
| 4 | Must NOT call thread.deleteLater() before thread.wait() | OBSERVED-HELD | main_window.py:128 `self._sim_thread.finished.connect(self._sim_thread.deleteLater)` — the ONLY delete path, wired to finished signal (after wait completes). |
| 5 | Must NOT write speed/playback state to SceneDefinition or EditorSettings/QSettings | OBSERVED-HELD | `grep -n "QSettings\|setValue" main_window.py` finds only docstring mentions at :206/:312/:424. Speed/paused live in `self._speed_combo`/`self._act_play_pause` (session-only widgets). No SceneDefinition mutation. |
| 6 | Must NOT recreate ViewportPanel on scene swap | OBSERVED-HELD | viewport.py:510-557 `update_scene` re-binds in place via `_bind_loaded_simulator`; no `setCentralWidget`, no `ViewportPanel(...)` construction in the swap path. |

**Unverified-prohibition — human review recommended** (6 flagged items). These do not hard-halt the AFK run; they surface for human confirmation per the autonomous-verify policy.

### Human Verification Required

### 1. Real-display >30 fps animation (SC#2 backstop)

**Test:** Open the editor on macOS with a typical scene (e.g. one containing robots or tissues — `scenes/minimal_scene.json` or similar), press Play, observe the viewport animating.
**Expected:** Smooth >30 fps animation; not the <10fps frozen state (bug #2 closed); preview animates rather than showing a single static frame (bug #1 closed).
**Why human:** Real-display fps with a real GL/simulator backend cannot be asserted in a headless offscreen pytest run. The PLAN explicitly marks this truth `verification: backstop`. The offscreen cadence proxy (`TestRenderPollCadence`) verifies the QTimer fires at >=30Hz, but that is a proxy, not the real-render path.

### 2. Playback toolbar/shortcuts UX

**Test:** Manually exercise the playback toolbar (Play/Pause toggle, Step button, Speed combo 0.25x/0.5x/1x/2x/4x) and the Space + '.' shortcuts.
**Expected:** Play resumes animation, Pause holds, Step advances exactly one frame, Speed scales motion visibly (2x faster, 0.25x slower), Space toggles play/pause, '.' steps one. Status bar shows '▶ playing {speed}x' / '⏸ paused' / '⏸ paused (static scene — no dynamics)' correctly.
**Why human:** Toolbar visual interaction, perceived speed scaling, and status-bar text are user-flow behaviors. The wiring is unit-tested (TestPlaybackToolbar, TestPlaybackStatus, TestSpeedScaling) but the perceived UX is human-judgment.

### 3. Real close-mid-step teardown

**Test:** Close the editor while animation is playing (mid-step) and confirm no segfault / no 'RuntimeError: Internal C++ object already deleted'.
**Expected:** Editor exits cleanly within ~3s; no segfault; no Qt warning about QThread destroyed while running.
**Why human:** TestCloseMidStepCleanExit covers the ordering offscreen with a MockSimulator, but real-path segfault freedom with a real simulator backend on a live display is human-confirmable.

### 4. Prohibition review (6 flagged judgment-tier items)

**Test:** Confirm the LLM-judge verdicts in the Prohibition Review table above by code inspection.
**Expected:** All six prohibitions hold in the live code (the verifier's grep already confirmed this, but per autonomous-verify policy these are NON-AUTHORITATIVE judgments flagged for human review).
**Why human:** PLAN frontmatter marked these prohibitions `status: unverified, flagged: true` (descriptor-less at planning time). The verifier's grep-based LLM-judge is non-authoritative per the autonomous-verify policy.

### Gaps Summary

No gaps_found. All artifacts exist, are substantive, are wired, and have real data flowing. All 16 non-backstop truths are VERIFIED with passing behavioral tests for behavior-dependent invariants (SC#1 accumulator, SC#3 pause/step-one, SC#4 decoupling, D-04 close-mid-step, D-11 load-paused, Pitfall 3 ordering, Pitfall 6 step-one-renders-while-paused). All key links are wired. No source anti-patterns.

The phase routes to `human_needed` (not `passed`) because:
1. SC#2 backstop truth (real-display >30 fps) is `verification: backstop` — abstains without human observation; not countable toward the verified score.
2. 6 judgment-tier prohibitions are flagged-unverified per PLAN frontmatter; the LLM-judge found them held in code but per autonomous-verify policy they surface for human review as `unverified-prohibition — human review recommended`.

One deferred item (test-only, not source): `test_pause_then_resume_advances_then_holds` is a known flaky test under cross-test timing pressure (passes in isolation). SC#3 is independently covered by `test_step_one_advances_exactly_one_while_paused`, so the gap is not load-bearing for the phase goal.

The phase goal (animated >30fps preview, render/sim decoupling, pause/resume/step-one, fixes bugs #1 + #2) is achieved at the code+test level. The two human-verification items (real-display fps + prohibition review) are confirmations of what the code already does, not gaps that require new work.

---

_Verified: 2026-07-29T23:55:00Z_
_Verifier: Claude (gsd-verifier)_
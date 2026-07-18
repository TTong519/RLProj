---
phase: 42
slug: render-sim-decoupling-animated-viewport
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-16
---

# Phase 42 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `42-RESEARCH.md` §Validation Architecture. Task IDs in the Per-Task
> Verification Map are filled in by the planner (`42-*-PLAN.md`); the test-class
> → success-criterion mapping below is the locked contract.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (>=7.0.0, `[dev]` extra) + PySide6 6.11.1 offscreen |
| **Config file** | `pytest.ini` (`testpaths=tests`, `pythonpath=src`, `asyncio_mode=auto`) |
| **Quick run command** | `PYTHONPATH=src QT_QPA_PLATFORM=offscreen pytest tests/test_sim_step_worker.py tests/test_render_poll_loop.py tests/test_viewport_playback.py -v` |
| **Full suite command** | `PYTHONPATH=src pytest tests/ -v` |
| **Estimated runtime** | ~20–40 seconds (offscreen Qt + `MockSimulator` + controllable clock; no real physics, no provider call) |

**Offscreen GUI convention:** every Qt test sets `QT_QPA_PLATFORM=offscreen` and builds `QApplication` + `EditorWindow` headless — the Phase 31/33/41 `tests/test_gui_scaffold.py` / `tests/test_dock_state.py` pattern. Direct script runs require `PYTHONPATH=src`; `pytest.ini` handles it for pytest. The `SimStepWorker` / `RenderPollLoop` logic tests use a `MockSimulator` with a controllable clock and instant `render()` so accumulator/publish-cap/step-one/speed behavior is asserted deterministically offscreen.

---

## Sampling Rate

- **After every task commit:** Run `PYTHONPATH=src QT_QPA_PLATFORM=offscreen pytest tests/test_sim_step_worker.py tests/test_render_poll_loop.py tests/test_viewport_playback.py -v` (new phase test files — fast, offscreen, `MockSimulator`)
- **After every plan wave:** Run `PYTHONPATH=src pytest tests/ -v` (full suite — confirms no regression in the 1,513-test v0.6.0 baseline + Phase 41's additions)
- **Before `/gsd-verify-work`:** Full suite must be green; plus all new SC tests green offscreen; plus the `verification: backstop` for SC#2 real-fps acknowledged
- **Max feedback latency:** ~40 seconds

---

## Per-Task Verification Map

> Task IDs assigned by the planner (`42-*-PLAN.md`). The test-class → success-criterion
> mapping is locked here; the executor must not drop a criterion. SC#2's real-fps is a
> `verification: backstop` truth (honest offscreen limit) — the offscreen proxy is the
> machine-verifiable half.

| Task | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | Test Class | SC / Decision | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|------------|---------------|--------|
| 42-0?-0? | 0? | 1 | GUI-11 | — | N/A (local desktop, no auth/network; worker reads no secrets) | integration (offscreen, MockSimulator) | `pytest tests/test_sim_step_worker.py::TestSimStepWorkerAccumulator -v` | `TestSimStepWorkerAccumulator` | SC#1 (bug #1) | ⬜ pending |
| 42-0?-0? | 0? | 1 | GUI-11 | — | N/A | integration (offscreen proxy) + backstop | `pytest tests/test_render_poll_loop.py::TestRenderPollCadence -v` (proxy); real-fps = human/backstop | `TestRenderPollCadence` + backstop truth | SC#2 (bug #2) | ⬜ pending |
| 42-0?-0? | 0? | 1 | GUI-11 | — | N/A | unit/integration (offscreen, MockSimulator) | `pytest tests/test_sim_step_worker.py::TestPauseResumeStepOne -v` | `TestPauseResumeStepOne` | SC#3 (pause/resume/step-one) | ⬜ pending |
| 42-0?-0? | 0? | 1 | GUI-11 | — | N/A | integration (offscreen, MockSimulator, controllable render_delay) | `pytest tests/test_sim_step_worker.py::TestDecouplingAndPublishCap -v` | `TestDecouplingAndPublishCap` | SC#4 (decoupled + ~30Hz cap) | ⬜ pending |
| 42-0?-0? | 0? | 1 | GUI-11 | T-42-01 (DoS crash on close) | D-04 cooperative `stop()` + `wait(3000)` + log-and-proceed; NEVER `terminate()` | integration (offscreen, MockSimulator) | `pytest tests/test_viewport_playback.py::TestCloseMidStepCleanExit -v` | `TestCloseMidStepCleanExit` | D-04 teardown | ⬜ pending |
| 42-0?-0? | 0? | 1 | GUI-11 | T-42-02 (GL thread-affinity) | `render()` ONLY on UI thread; worker only `step()` + `get_state()` | integration (offscreen GUI introspection) | `pytest tests/test_viewport_playback.py::TestPlaybackToolbar -v` | `TestPlaybackToolbar` | D-06/D-09 toolbar + speed | ⬜ pending |
| 42-0?-0? | 0? | 1 | GUI-11 | — | `safe_error_message()` wraps any user-facing hint | unit/integration (offscreen) | `pytest tests/test_viewport_playback.py::TestPlaybackStatus -v` | `TestPlaybackStatus` | D-08 status-bar segment | ⬜ pending |
| 42-0?-0? | 0? | 1 | GUI-11 | — | N/A | integration (offscreen, MockSimulator, real `time.monotonic`) | `pytest tests/test_sim_step_worker.py::TestSpeedScaling -v` | `TestSpeedScaling` | D-09 speed scaling | ⬜ pending |
| 42-0?-0? | 0? | 1 | GUI-11 | — | N/A | integration (offscreen) | `pytest tests/test_viewport_playback.py::TestLoadPaused -v` | `TestLoadPaused` | D-11 load-paused | ⬜ pending |
| 42-0?-0? | 0? | 1 | GUI-11 | — | `safe_error_message()` on the hint; hint stays generic | unit (`_scene_has_dynamics`) + integration | `pytest tests/test_viewport_playback.py::TestStaticSceneHint -v` | `TestStaticSceneHint` | D-12 static-scene hint | ⬜ pending |
| 42-0?-0? | 0? | 1 | GUI-11 | — | N/A | unit (introspection, EXTEND existing) | `pytest tests/test_dock_state.py::TestDockObjectNames -v` | `TestDockObjectNames` (extend for `QToolBar`) | Phase 41 D-07 extension | ⬜ pending |
| 42-0?-0? | 0? | 1 | GUI-11 | — | N/A | integration (offscreen, MockSimulator) | `pytest tests/test_render_poll_loop.py::TestStepOneRendersWhilePaused -v` | `TestStepOneRendersWhilePaused` | step-one renders while paused | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_sim_step_worker.py` — accumulator + publish cap + step-one + speed scaling + teardown (`MockSimulator` + controllable clock). Covers SC#1, SC#3, SC#4, D-09, D-04.
- [ ] `tests/test_render_poll_loop.py` — latest-snapshot render, skip-when-no-new-snapshot, `_running` guard, step-one-renders-while-paused, cadence ≥30 Hz with instant render (SC#2 proxy). Covers SC#2 proxy, Pitfall 6.
- [ ] `tests/test_viewport_playback.py` — toolbar/shortcuts/status-bar wiring, load-paused on `update_scene`, close-mid-step teardown, static-scene hint. Covers D-06/D-08/D-11/D-12, D-04 UI side.
- [ ] Extend `tests/test_dock_state.py::TestDockObjectNames` to also collect `QToolBar` children and assert `toolbar_playback` has a non-empty unique `objectName` (Phase 41 D-07 extension).
- [ ] Shared `qapp` + `isolated_home` fixtures — duplicate the small fixture in each new test file (per `41-PATTERNS.md` §test pattern) OR place the new files in `tests/gui/` to reuse `tests/gui/conftest.py`.
- [ ] No framework install needed — pytest + PySide6 already in `[dev]`/`[gui]`.

*Existing `tests/test_gui_scaffold.py` + `tests/test_dock_state.py` + `pytest.ini` infrastructure covers the harness; Wave 0 adds the three phase-specific test files + the `TestDockObjectNames` extension only.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|------------|------------|-------------------|
| Real-scene viewport animates at >30 fps on macOS | GUI-11 (SC#2) | Real fps cannot be measured offscreen — no display, software-rendered PyBullet `render()` takes 50–120 ms. The offscreen proxy (`TestRenderPollCadence` with instant-render `MockSimulator`) proves the render-poll cadence is ≥30 Hz and yields to the event loop; only a real display confirms the end-to-end fps on a real scene. | Open a typical scene in the editor on macOS with a display, press Play, visually confirm the preview animates smoothly at >30 fps (Activity Monitor / `fps` counter if exposed). This is the `verification: backstop` truth — the verifier abstains → `human_needed` (reason `insufficient_spec`) when no display evidence is available, never a silent pass. |

*All other phase behaviors have automated offscreen verification. SC#2 is the one honest split: cadence is machine-verifiable offscreen; real-fps is a backstop.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 40s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
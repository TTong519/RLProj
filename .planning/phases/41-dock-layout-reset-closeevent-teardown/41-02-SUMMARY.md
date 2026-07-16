---
phase: 41
plan: 02
subsystem: editor (GUI teardown harness)
tags: [gui, qt, teardown, closeEvent, qthread, tdd]
requires:
  - 41-01 (DockStateManager + update_scene + showEvent — the in-place-swap + factory-default foundation this plan builds on)
provides:
  - "EditorWindow.aboutToClose signal (milestone-wide teardown contract — Phase 42/46/48/51 workers plug in via stop() + connect)"
  - "LLMPanel.stop() cooperative teardown template (cancel flag + thread.quit() + thread.wait(3000) + timeout log)"
affects:
  - "src/surg_rl/editor/llm_panel.py — LLMPanel.stop() + module logger + _on_cancel delegates to stop()"
  - "src/surg_rl/editor/main_window.py — EditorWindow.aboutToClose signal + __init__ wiring + closeEvent emits before super()"
  - "tests/test_dock_state.py — TestCloseMidCallMockSlow + TestCloseMidCallRealProvider + TestAboutToClose"
tech-stack:
  added: []
  patterns:
    - "Cooperative QThread teardown (D-05): setProperty('_cancelled', True) + thread.quit() + thread.wait(3000); log-and-proceed on timeout; never terminate(), never deleteLater() in stop()"
    - "aboutToClose plain-Signal teardown contract (D-04): closeEvent emits before super().closeEvent(); panels self-register stop() in __init__"
    - "Broad-suppress best-effort teardown (noqa: SIM105/BLE001) — never blocks quit"
key-files:
  created:
    - "tests/test_dock_state.py::TestCloseMidCallMockSlow (SC#3 always-on backstop, D-09b)"
    - "tests/test_dock_state.py::TestCloseMidCallRealProvider (SC#3 skipif-gated real-provider guard, D-09a)"
    - "tests/test_dock_state.py::TestAboutToClose (D-04 wiring guard, Mock-based)"
  modified:
    - "src/surg_rl/editor/llm_panel.py (LLMPanel.stop() + module logger + _on_cancel delegates)"
    - "src/surg_rl/editor/main_window.py (aboutToClose signal + closeEvent emit + __init__ wiring)"
decisions:
  - "Plain Signal for aboutToClose (not a registry mixin) — simpler, explicit, one line of wiring per panel; revisit if per-panel wiring grows past ~3-4 panels (A1/RESEARCH.md)"
  - "_on_cancel delegates to stop() so the Cancel button and closeEvent share one teardown path (D-05)"
  - "noqa: N815 on aboutToClose — the plan locks the Qt-camelCase signal name; existing editor signals are snake_case but aboutToClose is Qt-canonical"
metrics:
  duration: 18m
  tasks: 2
  files: 3
  tests_added: 3
  tests_passing: 7 passed, 1 skipped (real-provider, no API key)
status: complete
---

# Phase 41 Plan 02: closeEvent Teardown + aboutToClose Contract Summary

Cooperative `LLMPanel.stop()` (cancel flag + `thread.quit()` + `thread.wait(3000)` + timeout log) and milestone-wide `EditorWindow.aboutToClose` teardown signal so closing the editor mid-LLM-call exits cleanly without segfault or `RuntimeError: Internal C++ object already deleted`.

## What Was Built

### Task 1 — LLMPanel.stop() cooperative teardown (TDD)

**TDD cycle (RED → GREEN):**

1. **RED** (`fd50ddb`): Added `TestCloseMidCallMockSlow` — monkeypatches `TextParser.parse_sync` to `time.sleep(2)`, triggers `_on_generate`, calls `LLMPanel.stop()` (not yet implemented), asserts the worker thread is not running. Honest RED: `AttributeError: 'LLMPanel' object has no attribute 'stop'` (plus the "QThread: Destroyed while thread is still running" warning — exactly the bug being fixed).
2. **GREEN** (`d78f8b9`): Implemented `LLMPanel.stop()` per D-05 + RESEARCH.md Pattern 2:
   - Module-level `logger = get_logger(__name__)` (mirrors `viewport.py:21-23`).
   - `stop()` sets `self._worker.setProperty("_cancelled", True)` (the existing cross-thread cancel pattern — a dynamic Qt property, NOT a Python attribute; the worker lives on the QThread and the property is the thread-safe accessor).
   - Calls `self._thread.quit()` then `self._thread.wait(3000)`; on timeout logs `logger.warning("LLMPanel worker thread did not exit within 3s; proceeding with close")` and proceeds (best-effort, NEVER blocks quit — D-05).
   - Does NOT call `thread.terminate()` (D-05 — risks leaving SDK/parser state inconsistent).
   - Does NOT call `thread.deleteLater()` synchronously (Pitfall 4 — the existing `thread.finished -> thread.deleteLater` wiring in `_on_generate` handles deletion after the thread exits).
   - `_on_cancel` now delegates to `self.stop()` so the Cancel button shares one teardown path with `aboutToClose`.

### Task 2 — aboutToClose signal + closeEvent wiring + real-provider test

(`9bf272f`, tdd="false" — UI wiring):

1. **`EditorWindow.aboutToClose = QtCore.Signal()`** declared at class-body top (D-04 — plain Signal, no payload; pure teardown trigger). `# noqa: N815` because the plan locks the Qt-camelCase signal name (existing editor signals are snake_case, but `aboutToClose` is Qt-canonical and plan-mandated).
2. **`__init__` wiring** (in `_build_dock_widgets` after `_llm_panel` construction): `self.aboutToClose.connect(self._llm_panel.stop)` — the milestone-wide teardown contract. Future Phase 42/46/48/51 workers just declare `stop()` + connect here; no `closeEvent` edit needed.
3. **`closeEvent` extended** to emit `aboutToClose` BEFORE the existing `_viewport_panel.stop()` + `save_window` + `super().closeEvent(event)` — wrapped in `try/except Exception: # noqa: BLE001 pass` (best-effort, never blocks quit — matches the existing broad-suppress shape and D-05).
4. **`TestCloseMidCallRealProvider`** — `@pytest.mark.skipif(not os.environ.get("LLM_API_KEY"))` (D-09a — guards the true provider path when keys are present; skipped in CI without a key, guarded by the D-09b mock backstop).
5. **`TestAboutToClose`** — Mock-based wiring guard: replaces `_llm_panel.stop` with a `MagicMock`, triggers `closeEvent(QCloseEvent())`, asserts the mock was called (guards D-04 wiring without an in-flight LLM call; mirrors `tests/test_viewport.py:299-316`).

## SC#3 Verification (D-09 two-pronged)

| Prong | Test Class | Gate | Status |
|-------|-----------|------|--------|
| D-09b always-on backstop | `TestCloseMidCallMockSlow` | runs unconditionally offscreen | GREEN (2.94s — the 2s mock sleep + cooperative teardown; no "QThread destroyed" warning) |
| D-09a real-provider path | `TestCloseMidCallRealProvider` | `skipif(not os.environ.get("LLM_API_KEY"))` | SKIPPED (no key in CI — expected; D-09b backstop covers SC#3) |
| D-04 wiring guard | `TestAboutToClose` | runs unconditionally offscreen | GREEN |

## Verification Results

- `PYTHONPATH=src QT_QPA_PLATFORM=offscreen venv/bin/pytest tests/test_dock_state.py -v` → **7 passed, 1 skipped** (Plan 01's 5 classes + Plan 02's 3 classes; the skip is the real-provider test, expected without an API key).
- `PYTHONPATH=src QT_QPA_PLATFORM=offscreen venv/bin/pytest tests/ -q` → **exit 0** (full suite green — no regression in the 1,513-test baseline + Plan 01 + Plan 02).
- `ruff check src/surg_rl/editor/llm_panel.py src/surg_rl/editor/main_window.py tests/test_dock_state.py` → **All checks passed!**
- `mypy src/surg_rl/editor/main_window.py src/surg_rl/editor/llm_panel.py` → 14 errors, **all pre-existing LazyImport proxy pattern** (`Name "QtWidgets.QMainWindow" is not defined`, etc.); none reference new code lines. No NEW non-LazyImport-pattern type errors introduced.

## TDD Gate Compliance

- `test(41-02):` commit (RED) — `fd50ddb` — `TestCloseMidCallMockSlow` fails with `AttributeError` (stop() not yet implemented).
- `feat(41-02):` commit (GREEN) — `d78f8b9` — `LLMPanel.stop()` implemented; `TestCloseMidCallMockSlow` passes.
- RED gate, GREEN gate both present in git log. Task 2 (tdd="false") is standard wiring with end-to-end SC#3 tests. No REFACTOR commit needed (no cleanup required).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `aboutToClose` ruff N815 mixedCase class variable**
- **Found during:** Task 2
- **Issue:** The plan locks the signal name `aboutToClose` (Qt-camelCase convention, mandated in 41-CONTEXT.md D-04, RESEARCH.md Pattern 3, and the plan's key_links/artifacts). But ruff's `N815` rule (in the project's ruff select = `[..., "N", ...]`) flags mixedCase class-scope variables. The existing editor signals (`scene_accepted`, `node_selected`, `validation_changed`) are snake_case and don't trip N815; `aboutToClose` is Qt-canonical camelCase and does.
- **Fix:** Added `# noqa: N815 — Qt Signal naming convention` to the `aboutToClose = QtCore.Signal()` declaration. This is the established convention for plan-locked Qt API names that conflict with the project naming rule — the noqa is scoped to the one signal declaration and documented with the reason. Renaming to `about_to_close` would violate the plan's locked name and diverge from Qt's own `aboutToClose` signal convention.
- **Files modified:** `src/surg_rl/editor/main_window.py`
- **Commit:** `9bf272f`

No other deviations — the plan was executed exactly as written otherwise.

### Acceptance Criterion Note (Task 1 grep)

The plan's Task 1 acceptance criterion includes a grep that checks `stop()` adds no new `terminate()`/`deleteLater()` calls:
```
grep -nE "terminate\(|deleteLater" src/surg_rl/editor/llm_panel.py | grep -v '^#' | grep -v "thread.finished.connect" | grep -c .
```
This grep returns 4, not 0, because the `stop()` docstring and a trailing comment explicitly document the prohibition (e.g. "Does NOT call ``thread.terminate()``", "Do NOT call deleteLater here"). These are documentation strings, not executable code calls. The **intent** of the criterion — "stop() body does NOT contain `thread.terminate()` or `self._thread.deleteLater()` or `self._thread.terminate`" as actual code — is satisfied: the only executable call to `deleteLater` in the file is the pre-existing `self._thread.finished.connect(self._thread.deleteLater)` wiring at line 125 (correctly preserved, correctly excluded by `grep -v "thread.finished.connect"`). The `stop()` executable body contains only `setProperty`, `quit()`, `wait()`, and `logger.warning`. The documentation mentions improve clarity and were kept per CLAUDE.md's emphasis on documenting Qt-teardown prohibitions (Pitfall 3/4).

## Threat Flags

None — no new security-relevant surface introduced. The `aboutToClose` signal crosses the Qt event loop → worker QThread boundary; `stop()` touches `self._worker`/`self._thread` from the main thread via thread-safe APIs (`setProperty` is thread-safe; `quit`/`wait` are thread-safe per Qt docs). The `wait()` timeout warning is `logger.warning(...)` (log-only, NOT user-facing — no `safe_error_message` redaction needed per Security Domain V5). All mitigations from the plan's `<threat_model>` (T-41-03 accept, T-41-04/T-41-05/T-41-06 mitigate) are enforced in code.

## Known Stubs

None — `LLMPanel.stop()` and the `aboutToClose` wiring are fully implemented and wired. No hardcoded empty values or placeholder data flow to the UI.

## Artifacts

**New symbols (this plan):**
- `src/surg_rl/editor/llm_panel.py`: `LLMPanel.stop()` method; module-level `logger` (`get_logger(__name__)`); `_on_cancel` delegates to `stop()`.
- `src/surg_rl/editor/main_window.py`: `EditorWindow.aboutToClose` signal (class-level, `# noqa: N815`); `closeEvent` extended to emit `aboutToClose` before `super().closeEvent()`; `_build_dock_widgets` wires `aboutToClose.connect(self._llm_panel.stop)`.
- `tests/test_dock_state.py`: `TestCloseMidCallMockSlow`, `TestCloseMidCallRealProvider`, `TestAboutToClose`.

**Symbols from Plan 01 (excluded from drift verification — already complete):**
- `src/surg_rl/editor/dock_state.py`: `DockStateManager` + `capture_factory_default`/`reset_to_default`/`_rebuild_default_layout`.
- `src/surg_rl/editor/viewport.py`: `ViewportPanel.update_scene`.
- `src/surg_rl/editor/tree_view.py`: `SceneTreeView.update_scene`.
- `tests/test_dock_state.py`: `TestDockObjectNames`, `TestDockRoundTrip`, `TestUpdateScene`.

## Commits

| Hash | Type | Message |
|------|------|---------|
| `fd50ddb` | test (RED) | `test(41-02): add failing TestCloseMidCallMockSlow (RED)` |
| `d78f8b9` | feat (GREEN) | `feat(41-02): implement LLMPanel.stop() cooperative teardown (GREEN)` |
| `9bf272f` | feat | `feat(41-02): aboutToClose signal + closeEvent wiring + real-provider test` |

GUI-18 fully delivered: SC#1/SC#2/SC#4 by Plan 01; SC#3 by Plan 02. The `aboutToClose` teardown contract is established for Phase 42 (SimStepWorker), 46 (recorder), 48 (autosave), and 51 (VLM) workers — they declare `stop()` + connect to `aboutToClose`, no `closeEvent` edit needed.

## Self-Check: PASSED

- All created/modified files exist on disk: `src/surg_rl/editor/llm_panel.py`, `src/surg_rl/editor/main_window.py`, `tests/test_dock_state.py`, `.planning/phases/41-dock-layout-reset-closeevent-teardown/41-02-SUMMARY.md`.
- All commits present in git log: `fd50ddb` (RED), `d78f8b9` (GREEN Task 1), `9bf272f` (Task 2), `9167ad4` (SUMMARY).
- No off-limits files modified (`dock_state.py`, `viewport.py`, `tree_view.py`, `.claude/settings.local.json` untouched by this plan's commits).
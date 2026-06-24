---
phase: 33
phase_name: "PySide6 Scene Editor"
project: "Surg-RL"
generated: "2026-06-24"
counts:
  decisions: 10
  lessons: 10
  patterns: 10
  surprises: 7
missing_artifacts:
  - "VERIFICATION.md"
---

# Phase 33 Learnings: PySide6 Scene Editor

## Decisions

### Schema-driven property form via SchemaWalker over model_json_schema()
Property form widgets are generated automatically by recursively walking `SceneDefinition.model_json_schema()` and emitting one `FieldSpec` per leaf field, rather than hand-writing per-class mappings.

**Rationale:** Any future schema change in SceneDefinition is automatically picked up by the editor with no hand-written mappings per class; the contract is precise and lockable via tests.
**Source:** 33-02-PLAN.md

---

### 4-pane QDockWidget layout (tree/viewport/properties/LLM)
EditorWindow uses a QMainWindow with a central viewport and 4 QDockWidgets (tree left, viewport center, properties right, LLM bottom) rather than a QSplitter or tabbed layout.

**Rationale:** Dock widgets allow user-rearrangeable panes and persist-able window state via QSettings; matches the marquee GUI-08 requirement for a 4-pane layout.
**Source:** 33-01-PLAN.md

---

### Self-rescheduling QTimer.singleShot for the 20 Hz frame loop
The viewport render loop uses `QTimer.singleShot(50, self._tick)` self-rescheduling from inside `_tick` (D-03), not a recurring `QTimer.start(50)`.

**Rationale:** Prevents frame pile-up if a render takes longer than 50 ms — the next frame is only scheduled after the current one completes.
**Source:** 33-03-PLAN.md

---

### Deep-copy snapshots for undo via Pydantic v2 model_copy(deep=True)
SceneUndoStack stores deep-copy SceneDefinition snapshots per undo step using `model_copy(deep=True)`, capped at 100 levels and cleared on save.

**Rationale:** Pydantic v2's `model_copy(deep=True)` correctly handles all 63 schema classes including the `_FloatMixin` `DifficultyLevel` enum — no custom serializer needed; 100-level cap bounds memory at ~5-20 MB peak.
**Source:** 33-05-PLAN.md

---

### macOS mjpython warn-and-reexec replaces warn-and-exit
On macOS without mjpython, `app.main()` transparently re-execs the editor under `mjpython` via `os.execvp` instead of exiting with code 1 and an install hint.

**Rationale:** Users get a working editor with a working 3D viewport instead of a dead-end install-hint exit; MuJoCo's GL context requires mjpython on macOS.
**Source:** 33-03-PLAN.md

---

### safe_error_message redactor applied to all error strings
A single pure-Python `safe_error_message()` function with 5 regex patterns (OpenAI keys, Anthropic keys, xAI keys, Bearer tokens, env-var-style assignments) is applied to ALL error strings before they reach logs, status bar, or QMessageBox.

**Rationale:** LLM API exceptions may include auth tokens or keys; centralizing redaction in one function (D-19) prevents accidental leakage across the many error paths.
**Source:** 33-01-PLAN.md

---

### LazyImport contract preserves CLI independence
The 14-subcommand `surg-rl` CLI must still work without importing PySide6 even when `[gui]` is installed; PySide6 is imported via LazyImport symbols (`QtWidgets`/`QtCore`/`QtGui`) only when the GUI is launched.

**Rationale:** Headless systems and CI must not require PySide6; the CLI is the primary user-facing interface for training/evaluation.
**Source:** 33-01-PLAN.md

---

### Continue (not exit) on mjpython failure
If mjpython is missing or re-exec fails to detect mjpython, the editor prints a warning and continues to Gate 3 instead of exiting.

**Rationale:** The editor is still usable without mjpython — only the 3D viewport fails to render. Plan 33-07 hardens the viewport against render failures, so the graceful fallback is safe.
**Source:** 33-06-SUMMARY.md

---

### _running flag over QTimer.stop() for render-loop control
The render loop uses a `_running` boolean flag checked at the top of `_tick` and before rescheduling, rather than calling `QTimer.stop()`.

**Rationale:** The render loop uses self-rescheduling `QTimer.singleShot` (D-03 pattern) — there is no recurring timer object to `.stop()`. The flag is the correct mechanism and also guards against already-queued callbacks firing after `stop()`.
**Source:** 33-07-SUMMARY.md

---

### Filesystem path over importlib.resources for non-package dirs
`--headless` demo scene listing uses `Path(__file__).parent.parent.parent.parent / "scenes"` and `/ "tests" / "fixtures" / "scenes"` instead of `importlib.resources.files("tests.fixtures.scenes")`.

**Rationale:** `tests/` lives at repo root, not under `src/`, so `tests.fixtures.scenes` is not an importable package; the `importlib.resources` lookup fails. Filesystem path traversal works for both editable and dev installs.
**Source:** 33-06-SUMMARY.md

---

## Lessons

### importlib.resources.files cannot reach packages outside src/
`importlib.resources.files("tests.fixtures.scenes")` fails because `tests/` is at repo root, not under `src/`, so the package is not registered with the import system.

**Context:** The `--headless` demo scene listing silently printed "(no demo scenes found)" despite 11 JSON files existing in `scenes/` and 2 in `tests/fixtures/scenes/` — UAT Test 6 caught this.
**Source:** 33-06-SUMMARY.md

---

### MuJoCo Renderer __del__ raises AttributeError during interpreter shutdown
MuJoCo's `Renderer.__del__` tries to access `self._gl_context` which may already be garbage-collected during interpreter shutdown, raising `AttributeError('_gl_context')`. This is a known MuJoCo issue.

**Context:** The editor froze on launch because `simulator.close()` triggered the `__del__` crash during cleanup, and the render loop's QTimer kept firing after window close. UAT Gap 2 reported "app freezes and does not display a window."
**Source:** 33-07-SUMMARY.md

---

### Path math: app.py is 4 levels from repo root, not 3
`Path(__file__).parent.parent.parent` from `src/surg_rl/editor/app.py` resolves to `src/` (which has no `scenes/` dir), not the repo root. The correct traversal is `parent.parent.parent.parent` (editor → surg_rl → src → repo_root).

**Context:** The `--headless` scene listing used 3 levels and found no scenes; the fix required 4 levels.
**Source:** 33-06-SUMMARY.md

---

### os.execvp without a binary-availability check crashes
Calling `os.execvp("mjpython", ...)` without first checking `shutil.which("mjpython")` raises `FileNotFoundError` when mjpython is not installed, crashing the editor on macOS systems without the mujoco pip package.

**Context:** UAT Gap 2 reported the app freezing on launch; the mjpython re-exec was one of the root causes.
**Source:** 33-06-SUMMARY.md

---

### SceneDefinition field names are irregular and easy to get wrong
`scene.simulator` IS the `SimulatorType` enum directly (use `.value`, not `.type.value`); `scene.robots`, `scene.tissues`, `scene.instruments`, `scene.environment.cameras`, `scene.environment.lights` are all plural lists (not singular); `scene.metadata` is always present via default_factory.

**Context:** Tests using MagicMock with assumed field names passed but real-SceneDefinition integration would have caught the regressions; the plan explicitly called out these gotchas in test docstrings.
**Source:** 33-04-PLAN.md

---

### MagicMock tests miss real-field-name regressions
Tests using `MagicMock`-shaped scenes pass even when the real `SceneDefinition` field names are wrong (e.g., `scene.robot` vs `scene.robots`), because MagicMock auto-attributes any access.

**Context:** Plan 33-04 added an integration test using a real `SceneDefinition` to catch the field-name regressions that MagicMock-based unit tests missed.
**Source:** 33-04-PLAN.md

---

### Pre-existing test isolation failures from transitive PySide6 import
3 tests in `test_gui_scaffold.py` fail because `import surg_rl.editor` transitively imports PySide6 via the `__init__.py` `HAS_GUI` check, breaking the "CLI does not import PySide6" assertion.

**Context:** These failures were verified to pre-exist Plan 33-06 (checked out `8e1d70a` and re-ran — same failures), so they are not regressions from the plan's changes.
**Source:** 33-06-SUMMARY.md

---

### Executor subagents may return empty/truncated results
Both executor subagents in Plan 33-07 returned empty/truncated results without creating SUMMARY.md, requiring the orchestrator to verify completion via spot-checks (commits present, tests pass) and create SUMMARY.md manually.

**Context:** This is a recovery from a truncated executor result, not a plan deviation; the orchestrator followed the #2070 fallback rule.
**Source:** 33-07-SUMMARY.md

---

### UAT caught a launch freeze that the test suite missed
The test suite passed (64 tests, 27 passing on PySide6-free systems) but UAT reported the app froze on launch — the automated tests did not exercise the real launch + 500ms event loop path.

**Context:** UAT Gap 2 (Test 2) reported "the app freezes and does not display a window"; the root causes (MuJoCo `__del__` crash, dangling QTimer, missing viewport stop in closeEvent) were not covered by existing tests. Plan 33-07 added a launch smoke test (`test_editor_launches_without_freeze`) to lock the fix.
**Source:** 33-UAT.md

---

### DifficultyLevel _FloatMixin enum round-trips correctly through save/load
The `(float, Enum)` mixin `DifficultyLevel` (where `HARD == 1.0`) survives a `save_scene`/`load_scene` round-trip with both the float value and enum identity intact.

**Context:** This was a GUI-02 contract risk — the round-trip could have lost the float value or enum identity. `TestRoundTripDifficultyLevel` locks the contract.
**Source:** 33-05-SUMMARY.md

---

## Patterns

### Self-rescheduling QTimer loop with _running guard
A render/poll loop that uses `QTimer.singleShot(interval, self._tick)` from inside `_tick` must guard with a `_running` boolean flag checked at the top of `_tick` (early return if False) and before rescheduling (only if True).

**When to use:** Any self-rescheduling QTimer loop where the callback may be queued before `stop()` is called; prevents dangling callbacks after window close.
**Source:** 33-07-SUMMARY.md

---

### TDD RED-GREEN-REFACTOR for pure-Python business logic
Write the test file FIRST (RED — confirm it fails), implement minimally to pass (GREEN), then refactor only if duplication emerges (REFACTOR).

**When to use:** Pure-Python modules with defined I/O contracts (e.g., SchemaWalker: JSON Schema dict in, FieldSpec list out) — the contract is precise and the module is independently testable.
**Source:** 33-02-PLAN.md

---

### try/except (AttributeError, OSError) around external C-library close()
Wrap `simulator.close()` (and similar external C-library teardown) in `try/except (AttributeError, OSError)` to swallow `__del__` crashes during interpreter shutdown.

**When to use:** Any teardown of a C-extension object whose `__del__` may access already-garbage-collected GL contexts or other native resources.
**Source:** 33-07-SUMMARY.md

---

### Env-var loop guard for os.execvp re-exec patterns
Before calling `os.execvp`, set an env var (e.g., `_SURG_RL_GUI_REEXECED=1`) and check it at the top of the re-exec block to prevent infinite re-exec loops if post-re-exec detection fails.

**When to use:** Any `os.execvp` re-exec pattern where the "am I already re-execed?" detection depends on signals outside your control (e.g., mjpython setting `MJPYTHON_BIN`).
**Source:** 33-06-SUMMARY.md

---

### shutil.which pre-check before os.execvp
Always call `shutil.which(binary)` before `os.execvp(binary, ...)` to prevent `FileNotFoundError` crashes when the target binary is not installed.

**When to use:** Any `os.execvp` of an external binary that may not be present on the user's PATH.
**Source:** 33-06-SUMMARY.md

---

### Pure-Python vs Qt-dependent test separation
Split test classes into pure-Python (no Qt, no `QT_QPA_PLATFORM`) and Qt-dependent (skipif `not _HAS_PYSIDE6()`) groups so the pure-Python tests run on PySide6-free systems.

**When to use:** Modules that mix pure-Python logic (e.g., `safe_error_message`) with Qt-dependent code (e.g., `EditorWindow`); the pure-Python tests provide coverage on headless CI.
**Source:** 33-01-PLAN.md

---

### LazyImport for optional dependencies
Expose optional dependencies (PySide6) via `LazyImport("PySide6.QtWidgets", "gui")` symbols that report `.available` and only trigger an actual import when accessed, preserving import-time independence for the non-GUI CLI.

**When to use:** Optional features (GUI, heavy ML clients) that must not be imported eagerly by the core package; the `HAS_GUI` boolean lets downstream code skip gracefully.
**Source:** 33-01-PLAN.md

---

### Widget factory registry keyed by hint string
FieldRenderer uses a `dict[str, Callable[[FieldSpec], QWidget]]` registry keyed by `FieldSpec.widget_hint`, with a fallback to a default factory for unknown hints.

**When to use:** Schema-driven UI generation where widget type is inferred from field metadata; the registry makes it trivial to add new widget types without changing the dispatcher.
**Source:** 33-02-SUMMARY.md

---

### QT_QPA_PLATFORM=offscreen for headless Qt testing
Set `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` in conftest.py or test module top so Qt widgets can be constructed and exercised on headless CI without a display.

**When to use:** Any Qt-dependent test suite that runs on CI; combined with `QApplication.instance() or QApplication(sys.argv)` session fixture.
**Source:** 33-01-PLAN.md

---

### closeEvent stops background timers/simulators BEFORE super().closeEvent()
In Qt window `closeEvent`, call `self._background.stop()` in `try/except` before `super().closeEvent(event)` — Qt teardown in the parent can trigger widget destruction while background timers are still firing.

**When to use:** Any QMainWindow with a background QTimer loop or simulator lifecycle; prevents dangling callbacks and `__del__` crashes during teardown.
**Source:** 33-07-SUMMARY.md

---

## Surprises

### The marquee GUI feature froze on launch despite 64 passing tests
The test suite passed (27 passing on PySide6-free systems, 64 total when PySide6 installed) but the real app froze on launch because no test exercised the actual launch + 500ms event loop + close path.

**Impact:** UAT Gap 2 was a major severity issue that blocked all other GUI UAT tests (Tests 3 and 4 were blocked-by-prior-phase); required two gap-closure plans (33-06, 33-07) to fix.
**Source:** 33-UAT.md

---

### --headless reported no scenes despite 11 JSON files present
The `--headless` demo scene listing printed "(no demo scenes found)" even though `scenes/` had 11 JSON files and `tests/fixtures/scenes/` had 2 — a path-resolution bug (3 levels vs 4) and a broken `importlib.resources` lookup.

**Impact:** UAT Test 6 failed at major severity; the existing test only asserted on the "Available demo scenes" substring and accepted the "(no demo scenes found)" fallback as passing.
**Source:** 33-UAT.md

---

### Plan's "11+ JSON files in scenes/" was slightly inaccurate (actual: 9)
The plan claimed 11+ JSON files in `scenes/` but the actual count was 9.

**Impact:** Did not affect correctness — the test assertions use `.json` substring match and specific filenames (`knot_tying.json`), not exact counts. Noted as a minor plan inaccuracy.
**Source:** 33-06-SUMMARY.md

---

### Executor subagents returned empty/truncated results
Both executor subagents in Plan 33-07 returned empty/truncated results without creating the SUMMARY.md artifact, requiring orchestrator fallback.

**Impact:** The orchestrator had to verify completion via spot-checks (commits present, tests pass) and create SUMMARY.md manually following the #2070 fallback rule — a recovery from a truncated executor result, not a plan deviation.
**Source:** 33-07-SUMMARY.md

---

### Pre-existing test failures unrelated to the plan's changes
4 tests in `test_gui_foundation.py` and `test_file_operations.py` failed before and after Plan 33-07's changes (e.g., `QDockWidget.title()` does not exist in PySide6; `EditorWindow` lacks `_undo_stack` when constructed via `__new__` without full `__init__`).

**Impact:** These pre-existing failures were verified by checking out the pre-plan commit (`696ae5f`) and re-running — they are out of scope for gap closure and should be addressed in a future tech-debt phase.
**Source:** 33-07-SUMMARY.md

---

### os.execvp re-exec can infinite-loop if post-re-exec detection fails
Even after a successful `os.execvp("mjpython", ...)`, the re-execed process may still fail `_is_running_under_mjpython()` detection (which depends on mjpython setting `MJPYTHON_BIN`, out of our control), causing an infinite re-exec loop.

**Impact:** Required an env-var loop guard (`_SURG_RL_GUI_REEXECED=1` set before execvp, checked at top) — more robust than trying to fix the detection signals.
**Source:** 33-06-SUMMARY.md

---

### The warn-and-exit mjpython gate was the wrong initial design
Plan 33-01 shipped a warn-and-exit gate (`sys.exit(1)` after `_ensure_mjpython_or_warn()`), which Plan 33-03 then replaced with a warn-and-reexec (`os.execvp`).

**Impact:** The initial exit-1 path was a dead-end for macOS users without mjpython — they got an install hint instead of a working editor. The deviation was planned in 33-01's done notes ("Plan 33-03 task 2 REPLACES that gate") and applied in dependency order.
**Source:** 33-01-PLAN.md
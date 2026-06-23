---
slug: gui-no-render-under-mjpython
status: fixing
trigger: "surg-rl-gui still is just spawning a mjpython app but not rendering anything"
created: 2026-06-20
updated: 2026-06-20
goal: find_and_fix
tdd_mode: false
---

# Debug Session: gui-no-render-under-mjpython

## Symptoms

- **Expected behavior:** Launching `surg-rl-gui` should open a PySide6 scene
  editor window (3D viewport center, scene tree left, properties right, LLM
  panel bottom) per `.planning/REQUIREMENTS.md` GUI-08.
- **Actual behavior:** No window appears at all. The macOS dock shows the
  mjpython app icon, and right-clicking it says "Application Not
  Responding".
- **Error messages:** None — terminal output is clean.
- **Timeline:** Never worked — first attempt at running the GUI.
- **Reproduction:** Run `surg-rl-gui` on macOS. mjpython is installed and
  on PATH (Gate 2 takes the `os.execvp("mjpython", ...)` branch in
  `src/surg_rl/editor/app.py:152`).

## Initial Evidence

- Entrypoint: `src/surg_rl/editor/app.py:main()` (pyproject.toml
  `surg-rl-gui = "surg_rl.editor.app:main"`).
- Gate 2 (`app.py:138-152`) re-execs under mjpython via
  `os.execvp("mjpython", ["mjpython", "-m", "surg_rl.editor.app"] + sys.argv[1:])`.
- Gate 3 (`app.py:170-181`) constructs `QApplication(sys.argv)`,
  `EditorWindow(scene_path=...)`, `window.show()`, `sys.exit(app.exec())`.
- `EditorWindow.__init__` (`src/surg_rl/editor/main_window.py:49-81`)
  constructs `ViewportPanel` synchronously and calls
  `ViewportPanel._start()` → `QtCore.QTimer.singleShot(0, self._tick)`.
- `_tick` (`src/surg_rl/editor/viewport.py:102-143`) calls
  `_default_load_simulator(scene)` → instantiates `MuJoCoSimulator()`
  and `sim.load_scene(scene)` on the FIRST timer tick (i.e. inside the
  Qt event loop). This is a long / blocking / possibly-failing call that
  may stall the event loop before the window has had a chance to paint.
- No window will appear on screen until the QApplication event loop
  processes the `window.show()` and the first paint event. If the first
  `_tick` (scheduled with interval 0) fires before the window is painted
  and blocks on `load_scene` / `render`, the macOS app enters the
  "Application Not Responding" state — exactly the observed symptom.

## Current Focus

- **status:** RE-INVESTIGATION after user reported symptom STILL persists
  even after (1) lazy-import fix, (2) PYTHONPATH propagation fix, AND
  (3) user installed PySide6 under mjpython (`mjpython -m pip install
  PySide6`). Symptom is unchanged: dock icon, no window, NO terminal
  output (completely silent).
- **key insight:** The complete silence is a strong signal that prior
  mechanical verification did not capture the user's actual runtime
  experience. All prior reasoning was done by running mjpython directly
  with PYTHONPATH set — but the user runs `surg-rl-gui`, which goes
  through the console_script shim → main() → Gate 2 re-exec → mjpython
  Cocoa bundle. The Cocoa bundle may redirect stdout/stderr so any
  exception is swallowed.
- **hypothesis (primary):** Silent crash inside the mjpython Cocoa app
  bundle before Python stdout is connected. The mjpython trampoline
  execve's into a native .app bundle; Python's sys.stdout/stderr may
  be redirected to /dev/null or an unflushed buffer, so any exception
  is swallowed. ALL prior stderr-based diagnostics never reached the
  user.
- **test (attempt 3 — DIAGNOSTIC INSTRUMENTATION, not a fix):** Add
  logfile-based diagnostics to app.py. Write to
  `~/surg-rl-gui-debug.log` with explicit `open(..., "w")` + flush at
  the very TOP of main() and module top. Wrap main() body in
  try/except BaseException that writes `traceback.format_exc()` to the
  logfile. Log: sys.executable, sys.argv, os.environ.get("PYTHONPATH"),
  os.environ.get("_SURG_RL_GUI_REEXECED"), MJPYTHON_BIN env,
  _is_running_under_mjpython() result, each Gate reached,
  EditorWindow() start/end, window.show(), app.exec(). This BYPASSES
  any stdout/stderr redirection in the Cocoa bundle.
- **expecting:** After the user runs `surg-rl-gui`, the logfile will
  contain the actual execution trace / traceback, revealing where the
  silent failure occurs. The logfile is the only reliable observable
  because stderr is not reaching the user.
- **next_action:** Apply logfile instrumentation to app.py. Return
  CHECKPOINT REACHED asking the user to run `surg-rl-gui` and paste the
  contents of `~/surg-rl-gui-debug.log`. This is the 3rd and final
  attempt per the 3-attempt budget — do NOT add more blind
  instrumentation after this.

## Evidence

- timestamp: 2026-06-20 — Symptom intake via /gsd-debug routing.
  Sources: `src/surg_rl/editor/app.py`, `main_window.py:49-81`,
  `viewport.py:40-143`, `.planning/REQUIREMENTS.md` GUI-08,
  `.planning/research/PITFALLS-v0.5.0.md` P1 (mjpython re-exec).
- timestamp: 2026-06-20 — Instrumented EditorWindow() under
  QT_QPA_PLATFORM=offscreen. EditorWindow() construction took 11.32s;
  window.show() reached only AFTER construction; the first _tick's
  `_default_load_simulator` (MuJoCoSimulator + load_scene) was only
  0.68s. => The viewport _tick is NOT the blocker; construction is.
- timestamp: 2026-06-20 — Segmented EditorWindow.__init__: the slow
  segment is `from surg_rl.editor.undo_stack import SceneUndoStack`
  (lazy import at main_window.py:58). Importing surg_rl.editor.undo_stack
  alone takes 10.50s because undo_stack.py:5 does
  `from surg_rl.scene_definition import SceneDefinition` at module level.
- timestamp: 2026-06-20 — `python -X importtime surg_rl.scene_definition`:
  7.3s spent in surg_rl.scene_definition.schema, of which 7.25s is
  `from surg_rl.rl.difficulty import DifficultyLevel` at schema.py:1501,
  which triggers `surg_rl/rl/__init__.py` -> surg_rl.rl.callbacks ->
  stable_baselines3 -> torch -> tensorflow. `import surg_rl.rl` alone =
  9.36s (sb3 + torch both end up in sys.modules). difficulty.py itself is
  a leaf (only `from enum import Enum`); the cost is the parent
  package __init__.
- timestamp: 2026-06-20 — Existing test
  `tests/test_viewport.py::TestEditorLaunchGuard::test_editor_launches_without_freeze`
  PASSES (1.49s) because it constructs EditorWindow with the default
  MagicMock-free path BUT uses `_empty_scene_stub()` which DOES trigger
  the import. Wait — re-check: the test uses real EditorWindow() which
  calls `_empty_scene_stub()` which does
  `from surg_rl.scene_definition import SceneDefinition, SimulatorType`.
  So the test DOES exercise the slow path. It passes only because
  QTest.qWait(500) eventually returns once the import finishes (the
  import is slow but finite, ~11s, well under pytest's default timeout).
  The "no freeze" assertion only checks visibility AFTER qWait, not
  during the import. So the test does NOT catch the real-world freeze
  where the macOS dock reports "Not Responding" during the 11s import.
- timestamp: 2026-06-20 — mjpython is on PATH at /opt/homebrew/bin/mjpython
  (Python 3.14.6). Gate 2 re-exec branch is reachable. The re-exec uses
  `os.execvp("mjpython", ["mjpython", "-m", "surg_rl.editor.app"] + ...)`,
  so sys.executable becomes mjpython and `_is_running_under_mjpython()`
  returns True on the second invocation (signal 2: basename contains
  "mjpython"). Re-exec loop guard via `_SURG_RL_GUI_REEXECED=1` is
  correct. => mjpython detection is NOT the bug.

## Eliminated

- hypothesis: The viewport's `_tick` blocks the Qt event loop on the
  first QTimer callback (interval 0) by running `MuJoCoSimulator() +
  load_scene()` synchronously, preventing the window from painting.
  evidence: Instrumented _tick: load_scene took only 0.68s on the first
  tick. The 11.32s stall is in EditorWindow() CONSTRUCTION (before
  _tick is even scheduled), specifically in the lazy import of
  surg_rl.editor.undo_stack at main_window.py:58. The viewport _tick is
  fast and self-reschedules correctly.
  timestamp: 2026-06-20

- hypothesis: _is_running_under_mjpython() returns False after re-exec,
  causing an infinite re-exec loop or a fall-through warning.
  evidence: mjpython is on PATH; re-exec uses os.execvp("mjpython", ...)
  so sys.executable becomes mjpython and signal 2 (basename contains
  "mjpython") returns True. The loop guard `_SURG_RL_GUI_REEXECED=1`
  also prevents loops. mjpython detection is working.
  timestamp: 2026-06-20

## Resolution

- **root_cause (CURRENT — the user-visible blocker):** Gate 2 in
  `src/surg_rl/editor/app.py` re-execs into `mjpython` via
  `os.execvp("mjpython", ["mjpython", "-m", "surg_rl.editor.app", ...])`.
  `mjpython` is a trampoline that `os.execve`'s into a native Cocoa app
  bundle running Homebrew Python 3.14.6 — a SEPARATE interpreter from
  the stock pyenv Python 3.13.3 where `surg_rl` (editable) and `PySide6`
  are installed. The re-exec did NOT propagate `PYTHONPATH`, so the
  child mjpython process could not import `surg_rl` at all
  (`ModuleNotFoundError: No module named 'surg_rl'`). The Python thread
  inside the Cocoa app bundle died immediately, leaving the Cocoa shell
  lingering in the dock as "Application Not Responding" — exactly the
  user's symptom. The previous lazy-import fix (still in place) was
  necessary but never on the user's critical path, because the stock
  python process execvp's away at Gate 2 before ever constructing Qt.
- **secondary blocker (requires user install action):** Even after the
  PYTHONPATH fix, mjpython's Python 3.14.6 does NOT have PySide6
  installed (it is a binary wheel installed only under pyenv 3.13.3).
  So `surg_rl.editor.HAS_GUI == False` under mjpython, and Gate 1 prints
  the install hint and exits cleanly. The user must run
  `mjpython -m pip install PySide6` (or `pip install "surg-rl[gui]"` under
  mjpython) to make the GUI launchable under mjpython.
- **fix (CODE, applied):** In `app.py` Gate 2, before `os.execvp`, set
  `os.environ["PYTHONPATH"]` to include the repo `src/` directory
  (computed as 3x `os.path.dirname` from `app.py`'s location) so the
  mjpython child interpreter can find the editable `surg_rl` package.
  Preserves any pre-existing PYTHONPATH.
- **fix (INSTALL, pending user action):** `mjpython -m pip install PySide6`
  (cannot be done by the agent without modifying the user environment).
- **verification (mechanical, code fix):**
  - Before fix: `mjpython -m surg_rl.editor.app` →
    `ModuleNotFoundError: No module named 'surg_rl'` (process dies, dock
    icon lingers as "Application Not Responding").
  - After fix (simulated by setting PYTHONPATH=src manually, since
    os.execvp replaces the process): `mjpython -m surg_rl.editor.app` →
    `surg-rl GUI requires PySide6. Install with: pip install "surg-rl[gui]"`
    then exit 0. This proves (a) surg_rl is now importable under mjpython,
    and (b) the launch reaches Gate 1 and fails cleanly on the NEXT
    blocker (PySide6) instead of silently freezing.
  - 37/37 tests pass in tests/test_viewport.py, test_platform_guard.py,
    test_mjpython_detection.py, tests/gui/ (no regressions from the
    PYTHONPATH propagation).
  - Lint clean: ruff + black + mypy on app.py.
- **verification (end-to-end, pending user):** After the user installs
  PySide6 under mjpython and re-runs `surg-rl-gui`, the GUI should reach
  Gate 3 (QApplication + EditorWindow + window.show() + app.exec()) and
  render a visible window. This cannot be verified in headless agent
  context and requires a CHECKPOINT.
- **files_changed:**
  - src/surg_rl/rl/__init__.py (prior fix: PEP 562 lazy __getattr__)
  - src/surg_rl/editor/undo_stack.py (prior fix: defer scene_definition
    import to TYPE_CHECKING)
  - src/surg_rl/editor/app.py (CURRENT fix: propagate PYTHONPATH=src to
    the mjpython child via os.environ before os.execvp)
  - tests/test_viewport.py (prior: 4 regression tests)

- timestamp: 2026-06-20 — RE-INVESTIGATION after user reported symptom
  persists despite the lazy-import fix. Probed the actual mjpython
  environment: `mjpython --version` = Python 3.14.6 (Homebrew), at
  /opt/homebrew/bin/mjpython. Stock `python` = pyenv 3.13.3 with
  `src` on sys.path. `mjpython -c "import surg_rl"` →
  `ModuleNotFoundError: No module named 'surg_rl'` (surg_rl only
  installed editable for pyenv 3.13.3; mjpython's site-packages at
  /opt/homebrew/lib/python3.14/site-packages has no surg_rl). Direct
  `mjpython -m surg_rl.editor.app` → "Error while finding module
  specification for 'surg_rl.editor.app' (ModuleNotFoundError)". The
  previous lazy-import fix only helped import cost WITHIN the stock
  python process, which never reaches the GUI phase because it
  execvp's into mjpython at Gate 2 BEFORE Gate 3 (QApplication). So
  the previous fix was necessary but not on the user's critical path.
- timestamp: 2026-06-20 — Inspected the mjpython launcher
  (/opt/homebrew/bin/mjpython): it is a Python trampoline that sets
  MJPYTHON_BIN to point at a native Cocoa app bundle
  (MuJoCo_(mjpython).app/Contents/MacOS/mjpython) and os.execve's into
  it. The native binary runs CPython 3.14.6 in a thread while keeping
  the macOS main thread free for Cocoa GUI. This explains the dock
  icon: the Cocoa app bundle launches, then the Python thread dies on
  ModuleNotFoundError, leaving the Cocoa shell lingering in the dock
  as "Application Not Responding" — exactly the user's symptom.
- timestamp: 2026-06-20 — USER REPORT (checkpoint response): Symptom
  STILL persists after (1) lazy-import fix, (2) PYTHONPATH propagation
  fix in app.py Gate 2, AND (3) user installed PySide6 under mjpython
  via `mjpython -m pip install PySide6`. User ran `surg-rl-gui` → dock
  icon appears, NO window, NO terminal output (completely silent).
  This is the 3rd attempt — at the 3-attempt budget limit per CLAUDE.md.
  The complete silence is the critical new signal: all prior stderr-
  based diagnostics were invisible to the user, so mechanical
  verification did not reflect the user's actual runtime experience.
  mjpython's Cocoa app bundle likely redirects stdout/stderr to
  /dev/null or an unflushed buffer, swallowing any exception. Must use
  a logfile (open w + flush) to capture the actual execution trace.
- timestamp: 2026-06-20 — Confirmed the fix shape: (1) CODE FIX —
  app.py Gate 2 must set PYTHONPATH to include the repo src/ dir before
  os.execvp("mjpython", ...) so the child interpreter can find the
  editable surg_rl package. (2) INSTALL ACTION (user) — PySide6 must
  be installed under mjpython's interpreter:
  `mjpython -m pip install PySide6` (or `pip install "surg-rl[gui]"`
  under mjpython). The agent cannot perform this install (would modify
  user environment); it is a CHECKPOINT action.
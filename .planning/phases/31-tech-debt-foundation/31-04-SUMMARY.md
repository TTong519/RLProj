---
phase: 31-tech-debt-foundation
plan: 04
subsystem: build, cli, packaging
tags: [gui, pyside6, docker, mjpython, console-script, tech-debt]

# Dependency graph
requires: []
provides:
  - "[gui] optional-dependency group in pyproject.toml"
  - "surg-rl-gui console-script entry (separate from surg-rl CLI)"
  - "surg_rl.editor package with LazyImport + HAS_GUI sentinel"
  - "surg_rl.editor._platform_guard with mjpython detection helpers"
  - "surg_rl.editor.app.main() install-hint + mjpython-gate entrypoint"
  - "tests/test_gui_scaffold.py regression suite (5 classes, 20 tests)"
affects: [33-pyside6-scene-editor, 35-advanced-tech-debt]

# Tech tracking
tech-stack:
  added: [PySide6>=6.8.0,<7.0, markdown-it-py>=3.0.0]
  patterns:
    - "LazyImport + HAS_GUI sentinel for optional GUI dependencies"
    - "Console-script entry point SEPARATE from Typer CLI (avoids import-time cost)"
    - "_is_running_under_mjpython() 3-signal detection pattern (extracted to reusable helper)"
    - "Subprocess-isolated CLI tests via PYTHONPATH=src env var"

key-files:
  created:
    - src/surg_rl/editor/__init__.py
    - src/surg_rl/editor/_platform_guard.py
    - src/surg_rl/editor/app.py
    - tests/test_gui_scaffold.py
  modified:
    - pyproject.toml

key-decisions:
  - "Used `return bool(sys.argv and 'mjpython' in sys.argv[0])` (inlined) instead of `# noqa: SIM103` because ruff's noqa placement didn't suppress the rule cleanly"
  - "macOS non-Darwin test uses pytest.skip — we're running on Darwin so the skipif pattern is essential"
  - "Replaced try/except ImportError with pytest.raises(ImportError) idiom in test_lazy_import_raises_import_error_with_install_hint (B018 lint compliance)"

patterns-established:
  - "Pattern: Optional GUI packages use 3-LazyImport-symbol skeleton + HAS_GUI sentinel (QtWidgets, QtCore, QtGui)"
  - "Pattern: Console-script `surg-rl-gui` runs as SEPARATE entry, not Typer subcommand (preserves 14-subcommand CLI's lazy-import contract)"

requirements-completed: [DEBT-01, DEBT-02, DEBT-03, DEBT-04, DEBT-05]

# Metrics
duration: 18min
completed: 2026-06-18
---

# Phase 31 Plan 04 Summary

**GUI scaffolding: `[gui]` extra + `surg-rl-gui` console script + editor package (LazyImport + HAS_GUI + mjpython helpers) + 19-test regression suite**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-06-18T01:27:00Z
- **Completed:** 2026-06-18T01:45:00Z
- **Tasks:** 5
- **Files created:** 4 (3 src + 1 test)
- **Files modified:** 1 (pyproject.toml)
- **Tests added:** 19 (20 collected, 1 skipped on Darwin)

## Accomplishments

- Phase 31 GUI scaffolding half complete: 5 success-criterion conditions met
- `import surg_rl.editor` works on PySide6-free systems with `HAS_GUI = False`
- `LazyImport` raises `ImportError` with install hint on attribute access
- `_is_running_under_mjpython()` uses 3-signal detection (env var / sys.executable / sys.argv)
- `python -m surg_rl.editor.app --help` exits 0; `--headless` exits 0; no-args exits 1 with install hint
- 14-subcommand `surg-rl --help` exits 0 WITHOUT importing PySide6 (lazy-import contract preserved)
- **Full test suite: 1200 passed, 17 skipped** (was 1134 baseline + 66 new = ~1200)

## task Commits

1. **task 1: add [gui] extra + surg-rl-gui console script to pyproject.toml** - `ec61a30` (chore)
2. **task 2: add editor package skeleton with LazyImport + HAS_GUI** - `bcf791d` (feat)
3. **task 3: extract _is_running_under_mjpython + _ensure_mjpython_or_warn helpers** - `936fd3b` (feat)
4. **task 4: add surg_rl.editor.app main() install-hint entrypoint** - `8f08dc8` (feat)
5. **task 5: add tests/test_gui_scaffold.py regression suite** - `25d4417` (test)

## Files Created/Modified

- `pyproject.toml` - added `[gui]` extra (PySide6 + markdown-it-py) + `surg-rl-gui` console-script entry
- `src/surg_rl/editor/__init__.py` (NEW) - LazyImport for QtWidgets/QtCore/QtGui + HAS_GUI sentinel
- `src/surg_rl/editor/_platform_guard.py` (NEW) - `_is_running_under_mjpython()` + `_ensure_mjpython_or_warn()`
- `src/surg_rl/editor/app.py` (NEW) - `main()` entrypoint with --help / --headless / install-hint / mjpython gates
- `tests/test_gui_scaffold.py` (NEW) - 5 test classes, 20 collected tests (1 Darwin-skipped)

## Decisions Made

- **Inlined SIM103 fix in `_is_running_under_mjpython`** — `# noqa: SIM103` didn't suppress the rule cleanly, so used `return bool(sys.argv and "mjpython" in sys.argv[0])` which preserves the 3-signal priority order while satisfying lint. Behavior is identical.
- **Used `pytest.raises(ImportError) as exc_info:` idiom** instead of try/except/else — required to satisfy ruff B018 (useless expression). The original try/except was cleaner but ruff flags the bare attribute access expression.
- **Console-script entry is SEPARATE from Typer CLI** — preserves the 14-subcommand `surg-rl` CLI's lazy-import contract. Verified by `surg-rl --help` exiting 0 within <2s without importing PySide6.
- **`--help` short-circuits BEFORE the PySide6 gate** — users can run `surg-rl-gui --help` on PySide6-free systems to see the install hint without crashing on a missing dep.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Lint compliance] Inlined SIM103 in `_is_running_under_mjpython`**
- **Found during:** task 3 (ruff check on platform_guard.py)
- **Issue:** The plan's verbatim 3-signal detection block triggered ruff SIM103 (return condition directly). `# noqa: SIM103` on the `if` line didn't fully suppress the rule.
- **Fix:** Replaced `if sys.argv and "mjpython" in sys.argv[0]: return True; return False` with `return bool(sys.argv and "mjpython" in sys.argv[0])`. Behavior is identical; ruff is clean.
- **Files modified:** src/surg_rl/editor/_platform_guard.py
- **Verification:** `ruff check src/surg_rl/editor/_platform_guard.py` exits 0; env-var signal test still passes
- **Committed in:** `936fd3b` (task 3 commit)

**2. [Rule 2 - Lint compliance] Replaced try/except with pytest.raises in test_lazy_import_raises_import_error_with_install_hint**
- **Found during:** task 5 (ruff check on test_gui_scaffold.py)
- **Issue:** ruff B018 (useless expression) flagged the bare attribute access inside try. The plan's literal code triggered it.
- **Fix:** Used `with pytest.raises(ImportError) as exc_info:` context manager pattern. Cleaner pytest idiom.
- **Files modified:** tests/test_gui_scaffold.py
- **Verification:** Test passes on PySide6-free system (verified manually)
- **Committed in:** `25d4417` (task 5 commit)

---

**Total deviations:** 2 auto-fixed (2 lint compliance)
**Impact on plan:** Minimal — both deviations preserve plan semantics while satisfying ruff. No scope creep.

## Issues Encountered

None.

## User Setup Required

None for this phase. Phase 33 will require `pip install -e ".[gui]"` to actually run the editor (but install is gated by `HAS_GUI` and the `surg-rl-gui --help` message provides instructions).

## Next Phase Readiness

- Phase 33 (PySide6 Scene Editor) starts on a clean baseline:
  - `[gui]` extra is installable via `pip install -e ".[gui]"`
  - `surg-rl-gui` console script is registered (Phase 33 replaces `# Phase 33 wires MainWindow here` placeholder with `QApplication` + `MainWindow` + `app.exec()`)
  - `_is_running_under_mjpython()` is ready to be called from `mujoco_simulator.py:start_viewer()` (replacing the inline block at lines 1294-1298)
  - `LazyImport + HAS_GUI` pattern is the canonical reference for any future optional GUI dependencies
- Full test suite: 1200 passed (up from 1134), 17 skipped, 0 failed — regression baseline expanded

---
*Phase: 31-tech-debt-foundation*
*Plan: 04*
*Completed: 2026-06-18*
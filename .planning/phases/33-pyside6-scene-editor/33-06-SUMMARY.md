---
phase: 33-pyside6-scene-editor
plan: 06
subsystem: ui
tags: [pyside6, mjpython, macos, path-resolution, console-script]

requires:
  - phase: 33-pyside6-scene-editor (plans 01-05)
    provides: "EditorWindow + app.py scaffold with --headless mode and mjpython Gate 2"
provides:
  - "Fixed --headless scene listing (4-level repo-root path + filesystem lookup)"
  - "Hardened mjpython re-exec guard (shutil.which check + _SURG_RL_GUI_REEXECED loop guard)"
  - "Strengthened test_gui_scaffold.py assertions (non-empty scene list required)"
affects: [33-pyside6-scene-editor (UAT verification), editor-launch]

tech-stack:
  added: []
  patterns: ["Env-var loop guard for re-exec patterns", "Filesystem path over importlib.resources for non-package dirs"]

key-files:
  created: []
  modified:
    - src/surg_rl/editor/app.py
    - tests/test_gui_scaffold.py

key-decisions:
  - "Use filesystem Path(__file__).parent.parent.parent.parent instead of importlib.resources for tests/fixtures/scenes/ (tests/ is not an importable package)"
  - "Guard os.execvp with shutil.which('mjpython') to prevent FileNotFoundError when mjpython is not installed"
  - "Set _SURG_RL_GUI_REEXECED=1 env var before execvp and check it at top to prevent infinite re-exec loop if detection fails"
  - "Graceful fallback: if mjpython missing or re-exec fails, print warning and continue to Gate 3 (editor still works, 3D viewport may not render)"

patterns-established:
  - "Re-exec loop guard: env var set before execvp, checked at top of re-exec block"
  - "shutil.which pre-check for any os.execvp of an external binary"
  - "Filesystem path traversal for non-package resource directories"

requirements-completed: [GUI-01, GUI-02]

duration: ~12min
completed: 2026-06-20
status: complete
---

# Plan 33-06 Summary: --headless Scene Listing + mjpython Re-exec Guard

**Fixed --headless path resolution (4-level repo root) and hardened mjpython re-exec against crash (FileNotFoundError) and infinite loop (failed detection)**

## Performance

- **Duration:** ~12 min
- **Tasks:** 2 (both TDD: RED → GREEN)
- **Files modified:** 2

## Accomplishments
- `--headless` mode now lists demo scenes from both `scenes/` (9 JSON files) and `tests/fixtures/scenes/` (2 JSON files) — no longer prints "(no demo scenes found)"
- macOS mjpython re-exec no longer crashes with `FileNotFoundError` when mjpython is not installed — `shutil.which("mjpython")` check guards `os.execvp`
- Re-exec loop guard (`_SURG_RL_GUI_REEXECED=1` env var) prevents infinite re-exec if `_is_running_under_mjpython()` fails to detect mjpython after re-exec
- Graceful fallback: if mjpython missing or re-exec fails, prints a warning and continues to Gate 3 instead of exiting — editor still launches (3D viewport may not render)
- Removed broken `importlib.resources.files("tests.fixtures.scenes")` lookup (tests/ is at repo root, not under src/, so it is not an importable package)

## Task Commits

Each task was committed atomically (TDD: test → fix):

1. **Task 1: Fix --headless demo scene listing path + strengthen test assertion** — `54df021` (test RED) + `802293e` (fix GREEN)
2. **Task 2: Guard mjpython re-exec against crash and infinite loop** — `49b7ab3` (test RED) + `696ae5f` (fix GREEN)

## Files Created/Modified
- `src/surg_rl/editor/app.py` — Fixed 4-level path (`parent.parent.parent.parent`), removed `importlib.resources` lookup, hardened Gate 2 with `shutil.which` + `_SURG_RL_GUI_REEXECED` env var loop guard
- `tests/test_gui_scaffold.py` — Renamed/strengthened `test_headless_flag_lists_demo_scenes` (asserts non-empty list), added `test_headless_finds_repo_scenes_dir`, `test_headless_finds_fixtures_scenes_dir`, `test_mjpython_reexec_guarded_when_missing`, `test_mjpython_reexec_loop_guard`, `test_mjpython_reexec_skips_non_darwin` (6 new tests, all passing)

## Decisions Made
- **Filesystem path over importlib.resources:** `tests/` lives at repo root, not under `src/`, so `tests.fixtures.scenes` is not an importable package. Switched to `Path(__file__).parent.parent.parent.parent / "tests" / "fixtures" / "scenes"`.
- **Continue instead of exit on mjpython failure:** The editor is still usable without mjpython (only the 3D viewport fails to render). Plan 33-07 hardens the viewport against render failures, so the graceful fallback is safe.
- **Env var loop guard over detection fix:** Setting `_SURG_RL_GUI_REEXECED=1` before `execvp` and checking it at top is more robust than trying to fix `_is_running_under_mjpython()` detection (which depends on mjpython setting `MJPYTHON_BIN`, out of our control).

## Deviations from Plan

None — plan executed exactly as written. The plan's claim of "11+ JSON files in scenes/" was slightly inaccurate (actual: 9), but the test assertions use `.json` substring match and specific filenames (`knot_tying.json`), not exact counts, so this did not affect correctness.

## Issues Encountered
- **Pre-existing test isolation failures (not caused by this plan):** 3 tests in `test_gui_scaffold.py` (`test_platform_guard_does_not_import_pyside6`, `test_app_does_not_import_pyside6_at_module_level`, `test_surg_rl_help_does_not_import_pyside6`) fail because `import surg_rl.editor` transitively imports PySide6 via the `__init__.py` `HAS_GUI` check. Verified these fail with the pre-plan `app.py` too (checked out `8e1d70a` and re-ran — same failures). These are pre-existing isolation issues, not regressions from 33-06.

## User Setup Required

**External services require manual configuration.** The `surg-rl-gui` console script is declared in `pyproject.toml [project.scripts]` but not exposed on PATH until the user runs an editable install with the [gui] extra:

```bash
pip install -e ".[gui]"
```

Verification: after install, run `surg-rl-gui --help` — must exit 0 and print usage. If it prints "command not found", the install did not register the console script entry point.

## Gap Closure

| UAT Gap | Test | Severity | Closed By | How |
|---------|------|----------|-----------|-----|
| `surg-rl-gui` not on PATH | 1 | major | 33-06 `user_setup` + existing entry-point test | pyproject.toml declares the entry; user runs `pip install -e ".[gui]"` |
| App freezes/no window (mjpython re-exec crash/loop) | 2 | major | 33-06 task 2 | `shutil.which` check + `_SURG_RL_GUI_REEXECED` env var loop guard → no crash, no infinite loop |
| `--headless` finds no scenes | 6 | major | 33-06 task 1 | `parent.parent.parent.parent` (4 levels = repo root, was 3 = `src/`) + filesystem path for fixtures (was broken `importlib.resources`) + stricter test assertion |

## Next Phase Readiness
- Gap 1 (PATH), Gap 3 (headless scenes) fully closed.
- Gap 2 (app freezes) partially closed by 33-06 (mjpython re-exec crash/loop component). The viewport `__del__`/QTimer component is closed by plan 33-07.
- All 6 new tests pass; no regressions in the 18 passing tests (the 3 pre-existing failures are unrelated to this plan).

---
*Phase: 33-pyside6-scene-editor*
*Plan: 06*
*Completed: 2026-06-20*
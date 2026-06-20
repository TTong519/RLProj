---
status: complete
phase: 33-pyside6-scene-editor
source:
  - .planning/phases/33-pyside6-scene-editor/33-01-SUMMARY.md
  - .planning/phases/33-pyside6-scene-editor/33-02-SUMMARY.md
  - .planning/phases/33-pyside6-scene-editor/33-03-SUMMARY.md
  - .planning/phases/33-pyside6-scene-editor/33-04-SUMMARY.md
  - .planning/phases/33-pyside6-scene-editor/33-05-SUMMARY.md
started: 2026-06-19T20:35:00Z
updated: 2026-06-19T20:50:00Z
---

## Current Test

number: 1
name: Launch editor via surg-rl-gui and see 4-pane layout
expected: |
  User runs `surg-rl-gui [scene.json]` (or `surg-rl-gui --headless` on a headless box).
  A window opens with 4 dock panes: scene tree (left), 3D viewport (center),
  property form (right), LLM panel (bottom). Window geometry persists across
  restarts via QSettings. The status bar shows current scene path, simulator,
  FPS, and validation state. If PySide6 is missing, the user sees a clear
  install hint (`pip install '.[gui]'`) and exits non-zero.
awaiting: user response

## Tests

### 1. Launch editor via surg-rl-gui and see 4-pane layout
expected: |
  User runs `surg-rl-gui [scene.json]` (or `surg-rl-gui --headless` on a headless box).
  A window opens with 4 dock panes: scene tree (left), 3D viewport (center),
  property form (right), LLM panel (bottom). Window geometry persists across
  restarts via QSettings. The status bar shows current scene path, simulator,
  FPS, and validation state. If PySide6 is missing, the user sees a clear
  install hint (`pip install '.[gui]'`) and exits non-zero.
result: issue
reported: "surg-rl-gui command not found"
severity: major

### 2. Round-trip scene via Pydantic v2 model_validate/model_dump
expected: |
  Open a scene JSON file (e.g. scenes/suturing_demo.json) in the editor, edit a
  field via the property form, save with Cmd+S, reload the file. The edited
  value persists. All 63 schema classes including the `_FloatMixin`
  DifficultyLevel enum (HARD == 1.0) survive the round-trip. Validates via
  SceneDefinition.model_validate() before writing.
result: issue
reported: "the app freezes and does not display a window"
severity: major

### 3. Viewport renders scene and accepts orbit/pan/zoom
expected: |
  User sees a 3D viewport rendering the loaded scene at ≥15 FPS (target 20 Hz).
  Left-drag orbits the camera, middle-drag pans, scroll-wheel zooms. R-key (or
  Ctrl+R) resets the camera. On macOS without mjpython the editor re-execs
  itself under mjpython automatically (no install hint shown).
result: blocked
blocked_by: prior-phase
reason: "Cannot test viewport — GUI app freezes on launch (Test 2 failed). Must resolve Test 2 first."

### 4. Tree view supports add/remove/duplicate + drag-reorder + validation icons
expected: |
  User right-clicks a tree node to add/remove/duplicate scene elements.
  Drag-reorder within parents works. Each node shows a red/green/gray
  validation dot. The LLM panel accepts a text prompt and shows a JSON preview
  pane with Accept/Reject buttons (background QThread so the UI does not freeze).
result: blocked
blocked_by: prior-phase
reason: "Cannot test tree/LLM panel — GUI app freezes on launch (Test 2 failed). Must resolve Test 2 first."

### 5. Undo/Redo scoped per scene, CLI independence preserved
expected: |
  User can undo/redo any property change (Cmd+Z / Cmd+Shift+Z) within the
  session. The undo stack is capped at 100 levels and cleared on save. The
  existing `surg-rl` CLI (14 subcommands) still works without importing
  PySide6 even when `[gui]` is installed.
result: pass

### 6. Cold-start smoke test: editor boots, opens default scene
expected: |
  Kill any running editor process. Clear QSettings cache
  (~/.config/SurgRL or platform equivalent). Run `surg-rl-gui --headless`.
  The editor boots without import errors, lists available demo scenes from
  scenes/ and tests/fixtures/scenes/, and exits 0. Validates that the cold
  start path (no warm state, no cached QSettings) works on a fresh system.
result: issue
reported: "returns Available demo scenes: (no demo scenes found) — but scenes/ has 11 JSON files and tests/fixtures/scenes/ has 2"
severity: major

## Summary

total: 6
passed: 1
issues: 3
pending: 0
skipped: 2
blocked: 2

## Gaps

```yaml
- truth: "surg-rl-gui console script is on PATH after pip install -e .[gui]"
  status: failed
  reason: "User reported: surg-rl-gui command not found"
  severity: major
  test: 1
  artifacts: []
  missing:
    - "Editable install with [gui] extra (pip install -e '.[gui]') so the console-script entry declared in pyproject.toml is exposed on PATH"
    - "AGENTS.md workaround: PYTHONPATH=src python -m surg_rl.editor.app works, but bare 'surg-rl-gui' does not"
- truth: "Editor window opens and remains responsive on launch"
  status: failed
  reason: "User reported: app freezes and does not display a window"
  severity: major
  test: 2
  artifacts:
    - src/surg_rl/editor/app.py
    - src/surg_rl/editor/viewport.py
    - src/surg_rl/editor/main_window.py
  missing:
    - "Investigate mjpython os.execvp re-exec path on macOS — possible loop or hang"
    - "Investigate MuJoCo Renderer __del__ AttributeError('_gl_context') crash during shutdown"
    - "Verify Qt main event loop actually starts and the QMainWindow.show() call completes"
- truth: "--headless lists demo scenes from scenes/ and tests/fixtures/scenes/"
  status: failed
  reason: "User reported: returns Available demo scenes: (no demo scenes found)"
  severity: major
  test: 6
  artifacts:
    - src/surg_rl/editor/app.py:84 (wrong parent.parent.parent path; should be parent.parent.parent.parent to reach repo root)
    - src/surg_rl/editor/app.py:81 (importlib.resources.files('tests.fixtures.scenes') fails because tests/ is at repo root, not under src/)
  missing:
    - "Fix repo_scenes path resolution: editor/app.py → surg_rl → src → <repo-root> is 4 levels, not 3"
    - "Fix importlib.resources lookup for tests.fixtures.scenes — tests/ lives outside src/, so the package is not registered"
    - "Update the existing --headless test in test_gui_scaffold.py to assert the scene list is non-empty (currently it only checks for the 'Available demo scenes' substring)"
```

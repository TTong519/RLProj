# Phase 33: PySide6 Scene Editor - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-19
**Phase:** 33-pyside6-scene-editor
**Areas discussed:** 3D viewport backend, SchemaWalker scope, Undo/redo architecture, LLM panel async pattern

---

## 3D Viewport Backend

| Option | Description | Selected |
|--------|-------------|----------|
| Render-to-QImage | QTimer (50ms) → render() returns RGB array → QImage → QPixmap in QLabel. Simpler, cross-platform, ~5-10% CPU overhead per frame at 20 Hz. | ✓ |
| Native OpenGL context | QOpenGLWidget wrapping native GL context for MuJoCo; PyBullet uses its own offscreen renderer. Faster, ~2x code, harder to debug, fragile on macOS mjpython. | |
| QThread render loop | Background QThread.render() → signals back to GUI thread. Avoids blocking the event loop but adds threading complexity + synchronisation risk. | |

**User's choice:** Render-to-QImage (Recommended)
**Notes:** Decision accepts the ~5-10% CPU overhead in exchange for cross-platform robustness + simpler debug story. Aligns with the project's pattern of preferring simpler solutions over premature optimization.

---

## SchemaWalker Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Recursive walker + field registry | SchemaWalker walks model_json_schema() recursively over all 63 classes; FieldRenderer dispatches by type. Cleanest, matches GUI-05 verbatim. | ✓ |
| Top-level only + dialogs for nested | SchemaWalker only walks top-level fields; nested objects via separate dialog. Less coverage, breaks GUI-05's auto-generated promise. | |
| Eager on top 5, lazy on rest | Eagerly walks 5 main nodes; other 58 classes shown only if referenced. Best UX for 99% case, fragile for full-edit case. | |

**User's choice:** Recursive walker + field registry (Recommended)
**Notes:** Full recursive walk is the only option that honors GUI-05's "auto-generated from model_json_schema()" promise. The 5-widget registry (vec3/enum/file/color/range) handles all 63 classes' field types.

---

## Undo/Redo Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Deep-copy snapshots | Push SceneDefinition.model_copy(deep=True) per change to QUndoStack. Heaviest memory, simplest semantics, atomic snapshots. | ✓ |
| Diff-based command pattern | Track (field_path, old_value, new_value) per change; replay to undo. ~10x lighter, fragile for nested Pydantic v2 models. | |
| Command pattern with per-widget commands | FormEditCommand(property_path, old, new) per widget; undo calls setter. Most disciplined, requires 5+ new files. | |

**User's choice:** Deep-copy snapshots (Recommended)
**Notes:** With 100-snapshot cap and ~50-200 KB per snapshot, peak memory ~5-20 MB — well within editor session budget. Pydantic v2's `model_copy(deep=True)` handles all 63 nested classes correctly, including `_FloatMixin` `DifficultyLevel` enum.

---

## LLM Panel Async Pattern

| Option | Description | Selected |
|--------|-------------|----------|
| QThread worker + signals | QObject subclass with @Slot, moveToThread(QThread), call parse_sync in worker; signals/Slots for done/error. Standard PySide6 pattern. | ✓ |
| QRunnable + QThreadPool | One-shot pool worker; simpler than QObject+moveToThread but progress reporting harder. | |
| Convert TextParser to async | Add async parse_async() to TextParser; GUI awaits via QFutureWatcher. Better cancellation, but modifies scene_generation module — out of Phase 33 scope. | |

**User's choice:** QThread worker + signals (Recommended)
**Notes:** Wrapping the existing sync API preserves the boundary between Phase 33 (GUI) and scene_generation (sync parser). Cancellation is documented as a known limitation if the underlying parser doesn't expose progress callbacks.

---

## OpenCode's Discretion

- Tree node icon style (custom vs Qt stock icons)
- Exact color theme (recommend system-default for cross-platform consistency)
- Form widget spacing / padding values
- Status bar message verbosity (terse vs detailed)
- Exact viewport default size (recommend 640×480)

## Deferred Ideas

- **Per-widget QPropertyAnimation for tree expand/collapse** — cosmetic; deferred.
- **Multi-scene tabs (multiple scenes in one window)** — new capability; out of scope.
- **Scene diff/merge between two open scenes** — new capability; out of scope.
- **Direct simulator control panel (start/pause/step)** — new capability; out of scope.
- **In-editor training run (start a PPO job, watch reward curve)** — new capability; out of scope.
- **Custom shader / ray-traced viewport** — new capability; deferred.

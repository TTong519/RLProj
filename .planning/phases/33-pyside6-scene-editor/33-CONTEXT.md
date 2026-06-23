# Phase 33: PySide6 Scene Editor - Context

**Gathered:** 2026-06-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Build a full PySide6 scene editor GUI for surgical robotics scene definitions. The editor must provide: 3D viewport rendering the loaded scene via the existing simulator backends (MuJoCo / PyBullet), tree+form property editor auto-generated from `SceneDefinition.model_json_schema()`, undo/redo over edits, and an LLM-prompt-to-JSON panel that calls the existing `TextParser.parse_sync()`. The editor must integrate cleanly with the existing GUI scaffolding from Phase 31 (`[gui]` optional extra, `surg-rl-gui` console script, `surg_rl.editor` package, `LazyImport` + `HAS_GUI` sentinel, mjpython detection helpers). Save/load uses the existing `save_scene`/`load_scene` API; auto-validation on save must round-trip all 63 Pydantic v2 schema classes including the `_FloatMixin` `DifficultyLevel` enum.

The 10 GUI requirements (GUI-01..10) define the WHAT; this context captures the HOW.

</domain>

<decisions>
## Implementation Decisions

### 3D Viewport Backend (Area 1)
- **D-01:** Render-to-QImage approach for the 3D viewport. A `QTimer` at 50 ms (20 Hz) triggers `simulator.render(mode="rgb_array", width, height) → np.ndarray → QImage → QPixmap → QLabel`. No native OpenGL context wrapping, no background render thread.
- **D-02:** Reuse the existing `BaseSimulator.render()` API as-is — do NOT add a new `render_to_numpy()` method. The existing `mode="rgb_array", width, height, camera_name` signature satisfies GUI-03's "rendered to numpy array" requirement; the GUI-03 wording is descriptive, not prescriptive.
- **D-03:** Render throttle is `QTimer.singleShot(50, self._update_viewport)` after each frame completes (self-rescheduling) rather than `QTimer.start(50)` (interval timer). Self-rescheduling prevents frame pile-up if the render takes >50 ms.
- **D-04:** Viewport size defaults to 640×480; user-resizable via QSplitter. Camera reset keybinding is `R`; orbit/pan/zoom via mouse (left-drag / middle-drag / scroll). Camera reset clears to the saved `camera_name` from the scene, not hardcoded.

### SchemaWalker + FieldRenderer (Area 2)
- **D-05:** SchemaWalker walks `SceneDefinition.model_json_schema()` recursively over ALL 63 schema classes — no early termination, no top-level-only shortcut. Nested objects always expanded in the tree (not collapsed by default).
- **D-06:** FieldRenderer is a registry dict keyed by JSON-schema `type` + `format` + custom `"x-surg-widget"` annotation. Initial registry covers 5 widget types from GUI-05: vec3 spinbox (3 number inputs side-by-side), enum combobox (for `Enum` subclasses), file path picker (QFileDialog), color picker (QColorDialog), range slider (for `confloat(ge=, le=)` constraints). Unknown types fall back to QLineEdit (text).
- **D-07:** Empty/default fields display the Pydantic v2 default (per `Field(default=...)` in schema). The form never shows "None" for unset fields — it shows the default that would be used if the user saved immediately.
- **D-08:** Validation icons per tree node: red dot for invalid (any descendant field fails Pydantic v2 validation), green check for valid (full subtree validates), gray dot for "not validated yet" (initial state before first edit). The dot updates after every form change with a debounced `QTimer.singleShot(150, validate)`.

### Undo/Redo Architecture (Area 3)
- **D-09:** Deep-copy snapshot approach. Each edit pushes `SceneDefinition.model_copy(deep=True)` to `QUndoStack`. No diff-based or command-pattern variants — atomic snapshots are simplest and Pydantic v2's `model_copy(deep=True)` correctly clones all 63 nested classes including the `_FloatMixin` `DifficultyLevel` enum.
- **D-10:** Undo stack is scoped per scene (per `QUndoStack` instance per open file), persists for the session only. Cross-save undo persistence is explicitly deferred per GUI-06 wording — when a scene is saved, the undo stack is cleared (fresh history starts).
- **D-11:** Undo stack depth cap is 100 snapshots. Exceeding the cap drops the oldest entry. With `SceneDefinition` typical size ~50-200 KB per snapshot, 100 levels ≈ 5-20 MB peak — acceptable for editor session memory budget.
- **D-12:** Cmd+Z = undo, Cmd+Shift+Z = redo on macOS; Ctrl+Z / Ctrl+Y on Linux/Windows. Keybindings via `QShortcut` on the main window, not per-widget.

### LLM Panel Async Pattern (Area 4)
- **D-13:** QThread worker pattern. A `QObject` subclass `TextParserWorker` with `@Slot(str) def run(self, prompt: str)` calls `self._parser.parse_sync(prompt)`; emits `finished = Signal(SceneDefinition)` on success, `failed = Signal(str)` on error. The worker is `moveToThread(QThread)` per parse; thread is destroyed after `finished`/`failed` fires (no manual thread lifecycle).
- **D-14:** The existing `TextParser.parse_sync()` API stays synchronous — no `parse_async()` wrapper is added in `src/surg_rl/scene_generation/`. The GUI is the only consumer that needs async behavior, and adding async variants to the scene_generation module would expand Phase 33 scope into scene_generation changes (out of scope).
- **D-15:** Cancel button: disabled until parse starts; when clicked, sets `self._cancelled = True` on the worker; the worker checks the flag inside `parse_sync()`'s progress callback (if the underlying parser exposes one — if not, the user must wait for natural completion). Documented limitation in GUI panel tooltip.
- **D-16:** LLM provider config comes from `Settings` (existing `src/surg_rl/utils/config.py`) — the panel reads `Settings().llm_provider`, `llm_api_key`, etc. via the existing `pydantic-settings` + `.env` machinery. Provider switching is live (QSettings combo box change triggers immediate re-read).

### Workspace Layout (cross-cutting)
- **D-17:** Standard 4-pane layout per GUI-08: viewport center (QSplitter middle), tree left (QDockWidget, draggable), properties right (QDockWidget), LLM panel bottom (QDockWidget). QDockWidgets allow rearranging; default layout restored via "View → Reset Layout" menu action.
- **D-18:** File menu: New / Open / Save / Save As / Recent Files (5 most recent paths via `QSettings`). Drag-drop `.json` onto main window opens it. CLI integration: `surg-rl-gui path/to/scene.json` opens that scene directly (already scaffolded in Phase 31-04).

### Security & Error Reporting (GUI-09)
- **D-19:** `safe_error_message()` redactor regex applied to ALL error strings before they reach logs, status bar, or message boxes. Redacts patterns: API keys (`sk-*`, `claude-*`, `xai-*`), bearer tokens, env-var-style assignments (`*_KEY=...`, `*_TOKEN=...`). Lives in `src/surg_rl/editor/_safe_error.py`.
- **D-20:** LLM panel settings (provider name, last prompt, recent scenes) persist via `QSettings` (platform-native: ~/.config/SurgRL on Linux, ~/Library/Preferences on macOS, registry on Windows). No API keys stored in QSettings — those stay in `.env` via `Settings()`.

### OpenCode's Discretion
- Tree node icon style (custom vs Qt stock icons)
- Exact color theme (light vs dark vs system-default — recommend system-default for cross-platform consistency)
- Form widget spacing / padding values
- Status bar message verbosity (terse vs detailed)
- Exact viewport default size (recommend 640×480)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase boundary & requirements
- `.planning/REQUIREMENTS.md` §GUI-01..10 — Phase 33's 10 GUI requirements (the WHAT)
- `.planning/ROADMAP.md` (Phase 33 entry) — Phase goal, success criteria, ordering
- `.planning/PROJECT.md` (lines 21-32) — v0.5.0 milestone context, target features

### Prior phase artifacts (the foundation Phase 33 builds on)
- `.planning/phases/31-tech-debt-foundation/31-04-PLAN.md` — Phase 31 GUI scaffolding plan (the decisions are inherited as locked)
- `.planning/phases/31-tech-debt-foundation/31-04-SUMMARY.md` — Phase 31 GUI scaffolding summary (what shipped, what patterns to extend)
- `.planning/phases/32-demo-suite-polish/32-REVIEW.md` — Phase 32 code review (pattern for code review depth on Phase 33)

### Codebase maps (reusable patterns + integration points)
- `.planning/codebase/ARCHITECTURE.md` — `BaseSimulator` ABC pattern + `Observation`/`State` dataclasses
- `.planning/codebase/STACK.md` — `[gui]` extra + LazyImport + console-script entry pattern (already shipped in Phase 31)
- `.planning/codebase/CONVENTIONS.md` — ABC prefix `Base`, dataclass cross-backend contract pattern
- `.planning/codebase/TESTING.md` — class-based test grouping (every test file uses `class TestXxx:`)
- `.planning/codebase/INTEGRATIONS.md` — `.env` + pydantic-settings pattern for LLM provider config

### Existing source modules (must read — integration points)
- `src/surg_rl/editor/__init__.py` — `LazyImport` + `HAS_GUI` sentinel (Phase 31; extends to `QtNetwork`, `QtOpenGL` if needed)
- `src/surg_rl/editor/_platform_guard.py` — `_is_running_under_mjpython()`, `_ensure_mjpython_or_warn()` (Phase 31; reuse for macOS viewport)
- `src/surg_rl/editor/app.py` — `main()` install-hint entrypoint (Phase 31; extends with scene argument handling)
- `src/surg_rl/simulators/base_simulator.py` — `BaseSimulator.render()` signature (lines 224-243)
- `src/surg_rl/scene_definition/__init__.py` — `SceneDefinition`, `save_scene`, `load_scene`, 63 schema classes
- `src/surg_rl/scene_definition/schema.py` — `_FloatMixin` `DifficultyLevel` enum (must round-trip on save)
- `src/surg_rl/scene_generation/text_parser.py` — `TextParser.parse_sync()` (existing sync API; GUI wraps in QThread worker)
- `src/surg_rl/utils/config.py` — `Settings` via `pydantic-settings` (LLM provider config: `llm_provider`, `llm_api_key`, etc.)
- `src/surg_rl/utils/logging.py` — `SensitiveDataFilter` (existing redactor; extend pattern for `safe_error_message()`)

### Tests (regression baseline — must not regress)
- `tests/test_gui_scaffold.py` — 19-test Phase 31 regression suite (LazyImport + HAS_GUI + mjpython + install-hint)
- `tests/test_demos.py` — 6-test Phase 32 regression suite (pattern reference for subprocess-based editor tests)
- `tests/test_scene_definition.py` (or equivalent) — 63-class Pydantic v2 round-trip tests

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`surg_rl.editor` package + console-script `surg-rl-gui`** (Phase 31-04) — the entry point is already scaffolded; Phase 33 extends `app.py` to dispatch into the new editor window class.
- **`BaseSimulator.render(mode="rgb_array", width, height, camera_name)`** — both MuJoCo and PyBullet implement this; GUI-03 viewport reuses it directly.
- **`SceneDefinition.model_json_schema()`** — Pydantic v2 emits a complete JSON Schema for all 63 classes; the SchemaWalker consumes this without hand-written mappings per class.
- **`SceneDefinition.model_copy(deep=True)`** — used per D-09 for undo/redo snapshots; Pydantic v2 handles the deep copy including `_FloatMixin` `DifficultyLevel` enum.
- **`TextParser.parse_sync(prompt: str) -> SceneDefinition`** — used by the LLM panel worker; sync API preserved per D-14.
- **`Settings()` (pydantic-settings + `.env`)** — LLM provider + key config; the panel reads from `Settings()` not from raw env vars.

### Established Patterns
- **LazyImport + HAS_GUI sentinel** — extend with `QtNetwork`, `QtOpenGL`, `QSettings`, `QShortcut`, `QFileDialog` etc. as needed; the `[gui]` extra already lists PySide6>=6.8.0,<7.0.
- **Console-script separate from CLI** — `surg-rl-gui` runs as its own entry point (already wired in Phase 31); do NOT add a `surg-rl gui` Typer subcommand.
- **Subprocess-isolated CLI tests via PYTHONPATH=src** — used by Phase 32's `tests/test_demos.py` for subprocess-based regression tests. Phase 33's editor tests follow the same pattern where the editor can be tested headlessly (e.g., `--headless` mode that exercises save/load without opening a window).
- **Pydantic v2 round-trip** — `SceneDefinition.model_validate(json.loads(path.read_text()))` then `model_dump_json()` must preserve all fields. This is what `load_scene`/`save_scene` already do; the editor uses these unchanged.
- **Rich for CLI + Plain text for GUI** — the editor never imports Rich; it uses Qt-native widgets (status bar, message box) for user feedback.

### Integration Points
- **CLI → GUI bridge**: `surg-rl-gui path/to/scene.json` → `app.py: main()` → `EditorWindow(path).show()`. Phase 33 implements `EditorWindow` in `src/surg_rl/editor/main_window.py` (new file).
- **GUI → SceneDefinition**: tree/form edits → `scene: SceneDefinition` mutation → save via `save_scene(scene, path)`. Auto-validation on save: `SceneDefinition.model_validate(scene.model_dump())` raises if invalid.
- **GUI → Simulator**: viewport creates a `MuJoCoSimulator` or `PyBulletSimulator` (selected from the `scene.simulator` SimulatorType enum value — `scene.simulator` IS the enum directly, not `scene.simulator.type`), loads the scene, ticks the render timer. The simulator lifecycle is owned by the main window — disposed on close.
- **GUI → TextParser**: LLM panel worker instantiates `TextParser(Settings().llm_provider, api_key=Settings().llm_api_key)` on demand; destroyed after the parse finishes.
- **GUI → Settings/QSettings**: app config (window size, recent files, LLM provider last used) persists via `QSettings("SurgRL", "SceneEditor")`. System/prompt/API-key settings persist via `.env` via `Settings()`.

</code_context>

<specifics>
## Specific Ideas

- The editor's 3D viewport should follow the visual style of the existing `demo.py` headless renders — same lighting, same camera angle (top-down 45°) as a sensible default. This keeps the editor visually consistent with the demos that ship alongside it (Phase 32).
- Recent Files menu (5 entries) persists across sessions via QSettings.
- Cmd+O (macOS) / Ctrl+O (Linux/Win) opens a file; Cmd+S saves; Cmd+Shift+S saves as; all wired via `QShortcut` per platform.
- File drag-drop: only `.json` files accepted; rejection shows a status-bar message via `safe_error_message()`.
- The LLM panel "regenerate" button preserves the user's last prompt text in the input box; the JSON preview pane updates on each new parse.
- Status bar shows: current scene path (or "Untitled" if unsaved), simulator backend, render FPS counter, validation status (valid / invalid / unvalidated).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within Phase 33 scope. Possible future phase candidates that came up implicitly but were not discussed:

- **Per-widget `QPropertyAnimation` for tree expand/collapse** — cosmetic; out of scope unless user asks.
- **Multi-scene tabs (multiple scenes open in one window)** — new capability, would be its own phase.
- **Scene diff/merge between two open scenes** — new capability, out of scope.
- **Direct simulator control panel (start/pause/step)** — new capability, currently only render is in scope.
- **In-editor training run (start a PPO job, watch reward curve)** — significant new capability, would need a new phase.
- **Custom shader / ray-traced viewport** — new capability, deferred.

If any of these become priorities, capture in the next milestone's roadmap.

</deferred>

---

*Phase: 33-pyside6-scene-editor*
*Context gathered: 2026-06-19*

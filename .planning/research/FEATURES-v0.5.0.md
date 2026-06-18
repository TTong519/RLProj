# Feature Research — v0.5.0 Scene Editor & UX Polish

**Domain:** Surgical robotics RL training system — PySide6 GUI + demo suite + docs
**Milestone:** v0.5.0
**Researched:** 2026-06-18
**Overall confidence:** HIGH (PySide6 patterns, demo suite patterns, docs patterns are well-established; no novel algorithms)

---

## Scope Clarification

This research covers **only the NEW features** for v0.5.0. Existing functionality (scene schema, simulators, RL training, LLM text/vision parsers, demos) is treated as background and called out only where the new feature depends on it. Four feature categories:

1. **PySide6 Scene Editor** — marquee (3D viewport + tree/form editor + LLM-prompt-to-JSON)
2. **Demo Suite Polish** — 3 demos (suturing existing, knot-tying new, needle-passing new) with common narration, banner, headless mode, regression test
3. **User-facing Docs Refresh** — README, CONTRIBUTING, CHANGELOG, screenshots/GIFs
4. **Tech Debt Cleanup** — interleaved (421 ruff, HARD-fixture test, fluid step hook, cut cooldown test, Dockerfile.ros2 amd64, PhiFlow union workaround)

Stack is already locked (see `.planning/research/STACK-v0.5.0.md`): PySide6 6.8+ for GUI, schema-driven Pydantic-v2-JSON-Schema form walker, existing `TextParser` for LLM panel, `mujoco.Renderer` + `pybullet.getCameraImage` for 3D viewport (no third-party OpenGL widget).

---

## Feature Category 1: PySide6 Scene Editor

### 1A. 3D Viewport (MuJoCo / PyBullet)

#### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Dependencies |
|---------|--------------|------------|--------------|
| Live scene render at >=15 FPS | A 3D viewport that doesn't update is a 2D viewport | MEDIUM | `mujoco.Renderer` (mujoco>=3.0) and/or `pybullet.getCameraImage`; `QTimer` for throttle |
| Orbit / pan / zoom with mouse | Blender, Godot, RViz, Unity all do this — users will not learn new bindings | MEDIUM | `QWidget` mouse handlers + camera spherical-coordinate math |
| Camera reset (default top-down/iso) | Users always get lost; "home view" is the universal undo | LOW | Reset button → snap camera to scene's `EnvironmentConfig.cameras[0]` pose |
| Backend toggle (MuJoCo ↔ PyBullet) | Surg-RL's core value is dual-backend; the editor must show both | HIGH | Two `BaseSimulator` instances, scene rebuild on switch (asset fallback chain re-runs) |
| Coordinate gizmo / axes overlay | Standard for any 3D viewport — orientation reference | LOW | Simple overlay drawn in `paintEvent` from camera basis vectors |
| Grid / ground plane toggle | Most editors show it by default; users want to hide for close-up | LOW | `EnvironmentConfig.ground_plane.enabled` toggle button |
| Status bar with FPS / sim time / step count | Power-user feedback; the difference between "looks frozen" and "running at 5 FPS" | LOW | `QStatusBar` + `QLabel` updated per tick |
| Screenshot capture (PNG to file or clipboard) | Users will want to embed scene images in papers/slides; standard viewport feature | LOW | `QImage.save()` or `mujoco.Renderer.render() → PIL/numpy → PNG` |
| Wireframe / solid / textured shading modes | Three-button cycle is the universal minimum (Blender's "Viewport Shading" panel) | MEDIUM | MuJoCo: `Renderer` flags; PyBullet: render flags 0/1/2 |
| Show/hide individual scene elements (organs, instruments, lights) | Iterating on visibility is core editing workflow | MEDIUM | Tree-view visibility checkbox → per-body render flag (MuJoCo `model.geom_rgba` alpha=0 toggle) |

#### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Side-by-side MuJoCo vs PyBullet render | Surg-RL's unique selling point — visualize the same scene on both backends without reloading | HIGH | Two widgets, two simulators, sync reset/step |
| Saved camera bookmarks (named views) | Surgical scenes have canonical viewpoints (laparoscopic top-down, endoscopic side, tissue close-up) | LOW | Persist `name → pose` dict to scene JSON or editor config |
| Simulation play/pause/step controls | Editor becomes a simulator-preview tool, not just a config tool | LOW | Hooks to `BaseSimulator.step()` — already exists |
| Soft-body deformation preview (MuJoCo FEM, PyBullet mass-spring) | The whole reason for soft-body work in v0.3.2; users need to see it deform | MEDIUM | Standard render — but flexcomp is heavy, need FPS budget guard |
| Time-scrubber / episode replay | "Show me what happened at step 230" — replay from `get_state()` snapshots | HIGH | Need persistent state log; defer to v0.6.0 unless easy |

#### Anti-Features (Explicitly Do NOT Build)

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|--------------|---------------|-----------------|-------------|
| In-viewport mesh editing (vertex paint, sculpt) | "Real" 3D editors do this | Re-implementing Blender in a 6-week milestone is suicide; users should round-trip to Blender for mesh work | Tree editor + `mesh_origin`/`scale`/`target_face_count` fields handle 90% of editing needs |
| Multi-viewport split (4-up camera views) | Power users want it | Quad-view doubles render cost on integrated GPUs; not requested in scope | Single viewport + saved bookmarks |
| VR/AR preview | "Future of surgery sim" | Apple Vision Pro / Quest 3 SDK adds 6+ weeks; no scientific value for scene editing | Defer to v1.0+ |
| Custom GLSL shaders for tissue rendering | Photorealism is tempting | MuJoCo/PyBullet don't support it; would fork renderers | Rely on `RgbColor` and lighting config |
| Picking/selection via 3D raycast | Click an organ to select it | Raycast against `flexcomp` tet meshes is non-trivial; PyBullet and MuJoCo differ | Use tree editor for selection (simpler, accessible) |
| Recording video (MP4 capture) | Users will ask | Requires ffmpeg, codec licensing complexity, no near-term value beyond screenshots | Screenshot + frame-strip to GIF via Pillow + imageio |
| Full Unreal/Unity-quality lighting/PBR | "Make it look real" | Renderers don't support it; out of v0.5.0 scope | Lambert + directional + ambient as the editor shows it now |

#### Dependency Notes

- **Backend toggle requires two simulators alive simultaneously**: MuJoCo + PyBullet. Memory cost ~150-300 MB total. Acceptable on dev workstations; flag for K8s memory budget. PyBullet soft-body requires `resetSimulation(RESET_USE_DEFORMABLE_WORLD)` (existing v0.3.2 pattern) — re-applied on backend switch.
- **Render loop** must not block Qt event loop: `QTimer.timeout` (15-30 Hz) posts a frame request; the actual `Renderer.render()` call runs in a `QThread` (worker pattern) and emits a signal back to the viewport. Naïve blocking `paintEvent` will freeze the UI on first attempt.
- **Scene rebuild on switch**: When user toggles backend, we tear down both simulators, re-run `scene_builder.build(scene, backend)` which re-derives primitive fallbacks. Asset paths from v0.4.0 OBJ→tetgen pipeline stay valid; only the in-memory `MujocoSim`/`PyBulletSim` instance changes.

---

### 1B. Tree Editor (Scene Element Hierarchy)

#### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Hierarchical tree view: Scene → Robots → Tissues → Instruments → Environment → Task → Domain Randomization | Maps 1:1 to `SceneDefinition` field structure; users will mentally project the schema onto the tree | LOW | `QTreeView` + `QStandardItemModel`; 4 top-level rows |
| Expand/collapse nodes | Trivially expected | LOW | Built into `QTreeView` |
| Per-node icon (robot/instrument/tissue type) | Visual scannability — same as file explorer | LOW | Qt's `QStyle.standardIcon` or simple emoji/unicode |
| Inline rename (double-click to edit) | Standard tree-editor behavior | LOW | Built into `QTreeView` with `EditTriggers` |
| Right-click context menu (Add / Duplicate / Delete / Move Up / Move Down) | Universal — same as file managers, Blender outliner, Godot scene tree | MEDIUM | Custom `QMenu` per node type; `Duplicate` deep-copies via `model_copy(deep=True)` |
| Drag-and-drop reorder | Standard list/tree editor affordance | MEDIUM | `QTreeView.setDragDropMode(InternalMove)` + drop validation (e.g., can't drop a tissue into an instrument node) |
| Multi-select with Ctrl/Shift-click | Power-user batch operations (delete 3 lights at once) | LOW | `QTreeView.setSelectionMode(ExtendedSelection)` |
| Search/filter bar | Scenes with 50+ instruments (a real OR setup) would be unusable without it | LOW | `QLineEdit` + `QSortFilterProxyModel` |
| Dirty-state indicator (asterisk in title bar) | Users need to know "is this saved?" | LOW | Track `scene_modified` boolean; `setWindowTitle(f"{name}*")` |
| Show validation errors inline (red icon next to invalid nodes) | Pydantic v2 errors are the only honest signal — must surface them | MEDIUM | After `SceneDefinition.model_validate()`, walk `e.errors()` and map `loc` tuples to tree paths |
| Disabled state for read-only scenes | If a scene has a `task` and the editor wants to highlight it as "task-locked" | LOW | `QStandardItem.setEnabled(False)` |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Drag-from-asset-library to scene | "Browse local .obj/.urdf files, drag into tree" | MEDIUM | `QListView` of `assets/` directory; drop handler validates and creates `MeshAsset` |
| Undo/redo (Ctrl+Z / Ctrl+Y) for tree mutations | Standard editor | MEDIUM | `QUndoStack` + `QUndoCommand` subclasses per operation |
| Show cardinality (e.g., "Tissues (3)") | Quick count without expanding | LOW | `(len(...))` suffix in node label |
| Highlight active/selected camera | When user picks a camera in tree, viewport centers on it | LOW | Wire to viewport camera set |
| "Reset to schema defaults" per node | Reset a single `InstrumentConfig` to Pydantic defaults without resetting whole scene | LOW | Re-instantiate the model class with `**{}` |

#### Anti-Features

| Anti-Feature | Why Avoid | Alternative |
|--------------|-----------|-------------|
| Nested unlimited-depth custom hierarchies | Users will create a "Body" node with infinite "SubBody" levels | Map tree strictly to `SceneDefinition` schema — schema is the schema |
| Per-element "scripts" or "behaviors" attached to nodes | Behavior trees, state machines — out of scope | Domain randomization at scene level covers this |
| Tree-based multi-scene editing (tabs) | "Edit 5 scenes at once" | One scene per editor window; OS-level tab/window management |
| Visual scripting (node graph) like Unreal Blueprints | Cool but a multi-year project | Defer forever; use Pydantic schema instead |
| Tagging / labeling system on nodes | Not in schema | Add tags via `Metadata.tags` (already exists) |
| Auto-arrange / tree layout | Scene tree is hierarchical, not free-form | Qt default tree layout is fine |

#### Dependency Notes

- **Tree nodes must mirror `SceneDefinition` schema exactly**. Schema changes (new optional field in v0.6.0) require tree model regen. Pydantic v2's `model_fields` introspection is the authoritative source — derive tree from schema, not from hand-written code.
- **Context menu actions for `task` node** should also offer "Generate from text…" — this is the bridge to the LLM panel (Feature 1D).
- **Drag-reorder validation**: instruments can be reordered freely, but `multi_agent.arm_configs` reordering is not allowed (semantic mapping by role, not order). Drop validation must be per-collection.

---

### 1C. Property Form Editor (Auto-Generated from Pydantic Schema)

#### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Schema-driven widget generation (no hand-rolled form for each model) | We have 58 `$defs` in `schema.py`; hand-rolling is 6 weeks of work | MEDIUM | Walk `model_json_schema()`; map types → widgets; recursive for `BaseModel` / `list[T]` / `Optional[T]` |
| Type-aware widgets: `QDoubleSpinBox` for float (with min/max from `Field(ge=, le=)`) | Users expect spinboxes for numbers, not text fields | LOW | `Field(ge=0.0, le=1.0)` → `QDoubleSpinBox.setRange(0.0, 1.0)` |
| `QSpinBox` for `int` with `ge`/`le` | Same as float | LOW | Same pattern |
| `QComboBox` (enum dropdown) for `Enum` subclasses (SimulatorType, TissueType, InstrumentType, LightType, etc.) | Universal: dropdown for fixed choice | LOW | `InstrumentType.__members__.items()` → dropdown items |
| `QLineEdit` for `str` | Default for free text | LOW | Trivial |
| `QPlainTextEdit` for `str` with multiline heuristic (description fields) | Long text fields deserve multiline | LOW | If `description="..."` contains `\n` or len > 60, use multiline |
| `QCheckBox` for `bool` | Universal | LOW | Trivial |
| `QPushButton + QFileDialog` for `AssetReference.path` | File-picker is the standard for path fields | LOW | Filter by file extension derived from `AssetReference.file_type` (infer_file_type) |
| `QSlider` for `int | float` with `Field(ge, le)` and no `multiple_of` | Sliders for ranges are intuitive for "rough" values; spinbox for precise | MEDIUM | Optional toggle per field; default to spinbox |
| `QColorDialog` for `RgbColor` (4 swatches R/G/B/A with sliders) | Color picking is core UX | MEDIUM | Show live color swatch preview |
| Vector editor for `tuple[float, float, float]` (Position, gravity, dimensions) | 3 floats as one logical unit — single QGroupBox with 3 spinboxes | LOW | Heuristic: if name is `position`, `gravity`, `dimensions`, `direction`, group as 3-component vector |
| Quaternion editor for `Orientation` (4 floats w/x/y/z) | Same as vector but with normalization warning | MEDIUM | If user edits non-unit quaternion, show warning; auto-normalize button |
| List editor (add/remove rows) for `list[BaseModel]` (robots, tissues, instruments, lights, cameras) | Schema is full of lists of models | MEDIUM | `QListView` + custom delegate with +/- buttons; for `list[PrimitiveType]` (like `mass_range: tuple[float, float]`) use two spinboxes |
| Nested model editor (e.g., `RobotConfig.end_effectors[0].grasping` shows the grasping sub-form) | Users will drill down | MEDIUM | `QStackedWidget` or `QTreeView`-style expansion in the form |
| Live validation: invalid input shows red border + tooltip with Pydantic error message | The only way to surface schema violations honestly | MEDIUM | Connect `valueChanged` signals → call `model_validate(strict=False)` for that subtree; if fails, show error in tooltip |
| Apply / Revert per form section | Mid-edit discard | LOW | Two buttons: Apply commits to in-memory scene; Revert rolls back form from scene |
| Undo/redo for form edits | Same as tree editor | MEDIUM | Shared `QUndoStack` with tree |
| Search/jump-to-field (`Ctrl+F`) | Power user with 50+ field scene | LOW | Walks JSON-pointer-style paths; `QCompleter` with cached list |
| Required-field indicator (red asterisk) | Visual signal of "must be filled" | LOW | `model_fields[name].is_required()` → `*` suffix in label |
| Description tooltip (from `Field(description=...)`) | Already in schema — surface it | LOW | `setToolTip(field.description)` |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Field history / recently-used values | Users tweak `tissue.stiffness` often; remember last 5 | MEDIUM | `QSettings` (Qt's config storage) |
| Range preset buttons ("EASY/MEDIUM/HARD") on `TaskConfig.difficulty_level` | Direct integration with v0.4.2 DifficultyLevel enum | LOW | 3 buttons next to the dropdown |
| Inline array of common presets for `tuple[float, float]` ranges | "Mass range → [0.5, 2.0]" with a dropdown of common values | LOW | Optional, simple QComboBox |
| Cross-field validators (e.g., `BoundingBox.min.x < max.x`) | These already exist in `model_validator`; surface the error next to both fields | MEDIUM | Map `e.errors()[i].loc` to both field paths |
| Diff view ("show changes since last save") | "What did I change?" — common in editors | HIGH | Defer to v0.6.0 unless trivial |
| Per-field help link (opens markdown docs) | Long-term: full API docs in GUI | MEDIUM | Markdown rendered by `markdown-it-py` (already in v0.5.0 stack) |

#### Anti-Features

| Anti-Feature | Why Avoid | Alternative |
|--------------|-----------|-------------|
| Hand-rolled widget for each of the 58 model classes | Maintenance nightmare | Schema-driven walker only |
| WYSIWYG visual layout editor for the form | Not needed — `QFormLayout` is the standard | Just use `QFormLayout` |
| Custom QML for any part | QML adds a second language | Stick to Python+Qt Widgets |
| Custom validators beyond Pydantic | Two sources of truth | Pydantic is the validator; UI only displays errors |
| Auto-complete for enum strings in `QLineEdit` | Enums are dropdowns; free-text is for `str` only | No — strict typing |
| Mass-edit of all instruments (e.g., set all `mass=0.2` at once) | Out of scope; multi-select in tree covers most cases | Multi-select in tree, then "Apply property to selection" — defer to v0.6.0 |
| Form "wizard" mode (step-by-step) | Overkill; power users hate wizards | Single scrollable form |

#### Dependency Notes

- **The schema walker is the single most reused component** in the editor. Tree editor (Feature 1B), form editor (Feature 1C), and LLM panel preview (Feature 1D) all consume `SceneDefinition.model_json_schema()`.
- **Widget choice heuristic** must be deterministic and tested. Unit-test the walker against every field type in the schema (Pydantic v2 has 6 primitive types, 6 container types, plus nested models). 1,134 tests in the repo — we add ~30-40 for the walker.
- **`QSettings` for editor preferences** (window geometry, last opened scene, last LLM provider) — already in PySide6, no new dep.

---

### 1D. LLM-Prompt-to-JSON Panel

#### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Free-text prompt input (multi-line) | "Describe a scene" — that's the feature | LOW | `QPlainTextEdit` (supports 1k+ char prompts) |
| "Generate" button → calls `TextParser.parse()` async | Wired to existing LLM code; no new LLM plumbing | LOW | Already implemented in `scene_generation/text_parser.py`; panel just calls `parse_sync()` |
| Provider/model selector (OpenAI / Anthropic / Ollama) | Three providers are in scope per `text_parser.py` | LOW | `QComboBox` for provider, `QLineEdit` for model; pre-filled from `config.get_settings()` |
| Streaming status ("Calling GPT-4…", "Validating schema…") | LLM calls take 2-30 seconds; silent UI feels frozen | LOW | `QProgressBar` indeterminate + status text from `parse()` logger |
| JSON preview pane (formatted) | The whole point — show the user what the LLM produced | LOW | `QPlainTextEdit` with `json.dumps(..., indent=2)`; read-only |
| Pydantic v2 validation pass (auto on receipt) | If invalid JSON, show error count and paths; if valid, show success | LOW | Catch `ParseValidationError`; show `details["errors"]` in a list widget |
| Accept / Reject / Regenerate buttons | The core UX: take it, throw it away, or try again | LOW | Accept → write to scene tree + form; Reject → discard; Regenerate → re-call with same prompt |
| Diff view: "What changed in scene vs current?" | "I had a suturing scene; the LLM gave me a different one. What did it do?" | MEDIUM | `difflib.unified_diff` of `current_scene.model_dump_json(indent=2)` vs `new_scene.model_dump_json(indent=2)` — use existing JSON, no new dep |
| Modify-with-context mode ("Add a third tissue to this scene") | `TextParser.parse_with_context()` already exists | MEDIUM | Second tab or toggle; passes current scene as context |
| Token / cost estimate (before generate) | "This prompt will cost ~$0.04" | LOW | Rough char-count → token estimate; no actual API call needed for estimate |
| Save prompt history (last 10 prompts) | Power users iterate; history is gold | LOW | `QSettings` + `QCompleter` dropdown |
| Error panel: raw LLM response on parse failure | When JSON extraction fails, show what the LLM actually said | LOW | `ParseValidationError.details["raw_response"]` already exposed |
| Loading cancel button (in-flight LLM call) | "I changed my mind" | MEDIUM | `asyncio.Task.cancel()` — needs Qt↔asyncio bridge; use `qasync` (Qt 6 asyncio integration) — or run in `QThread` to keep things simple |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Image-prompt mode (paste/drop image, call VisionParser) | `vision_parser.py` already exists; promote it from CLI to GUI | MEDIUM | Drag-drop `QPixmap` → encode to base64 → `VisionParser.parse()` |
| "Improve this scene" — uses `parse_with_context` with current scene | "The tissue is too stiff; lower it" — surgical-natural language | LOW | Already supported by `parse_with_context`; just a different button |
| Side-by-side: current scene JSON | LLM-generated JSON with inline diff highlighting | MEDIUM | Two-pane view with red/green gutters |
| Template prompt library ("Suturing with liver", "Knot tying with two instruments") | Onboard new users; pre-canned good prompts | LOW | Bundle 5-10 prompt strings in editor config |
| Confidence indicator from LLM response | If LLM logs token logprobs, show "0.72 confidence" | HIGH | Provider-specific (Anthropic has it, OpenAI doesn't surface by default); defer to v0.6.0 |
| Two-stage: LLM proposes → editor suggests fixes → LLM re-validates | "Self-correction" loop | HIGH | Defer to v0.6.0 |

#### Anti-Features

| Anti-Feature | Why Avoid | Alternative |
|--------------|-----------|-------------|
| Direct edit of LLM-generated JSON in the preview pane | Two paths to the same data will diverge | Use the form editor (Feature 1C) to edit the accepted scene |
| Streaming JSON tokens (character-by-character preview) | Cool but distracting | Show "generating" + final JSON only |
| LLM-suggested "next actions" / chat follow-up | Becomes a chatbot, not a scene editor | Out of scope |
| Built-in LLM fine-tuning / prompt-engineering | Years-long project | Use hosted LLM as-is |
| Multi-modal (video, audio) prompts | Beyond `vision_parser.py` scope | Vision-only (images); audio/video = v2+ |
| Conversation history beyond 10 prompts | Storage bloat | `QSettings` capped at 10; archive elsewhere if needed |
| Custom system-prompt editing | Each provider has a specific format | Use the locked system prompt from `text_prompts.py` |
| Cost tracking / billing dashboard | Not a product decision | Show estimate before generate; done |

#### Dependency Notes

- **Reuses `TextParser` and `VisionParser` directly** — no duplicate LLM code. The panel is pure UI.
- **Async loop in Qt**: Two options — `qasync` library (clean but adds dep) or `QThread` + `QObject` worker (no new dep, more boilerplate). Recommend `QThread` worker — keeps `[gui]` dep list minimal. ~150 lines of worker code.
- **`config.get_settings()` already provides `llm_provider`, `llm_model`, `llm_api_key`**, `llm_temperature`, `llm_max_tokens`. Panel just reads/writes via the settings API.
- **`SceneDefinition.model_dump_json(indent=2)` round-trips through `model_validate`** for preview safety. Pydantic v2's `model_dump()` returns Enum objects (not `.value` strings) — use `model_dump_json()` which serializes correctly, OR use `model_dump(mode="json")` for safe round-trip (note: this is the **AGENTS.md-documented gotcha**).

---

### 1E. Editor Shell (Workspace, Save/Load, Drag-Drop)

#### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Workspace layout: tree (left) + viewport (center) + form (right) + status (bottom) | Standard IDE-style 3-pane + status; Blender/Godot/RViz use this | LOW | `QSplitter` widgets with reasonable default sizes (25%/50%/25%) |
| File menu: New / Open / Save / Save As / Recent | Standard app | LOW | Wire to `load_scene()` (exists) and `scene.model_dump_json()` (Pydantic v2) |
| Save: writes to `.planning/scenes/*.json` per milestone plan | Path-locked by milestone plan; not user-configurable in v0.5.0 | LOW | Default `Path(__file__).parent.parent / "scenes" / f"{name}.json"` |
| Open: file dialog filtered to `*.json` and `*.yaml` | Standard | LOW | Existing `load_scene()` already handles both |
| Drag-drop a `.json` / `.yaml` scene file onto the window | Modern editor convenience | LOW | `dragEnterEvent` + `dropEvent` |
| Recent files (last 5) in File menu | Standard | LOW | `QSettings` storage |
| Exit: `Ctrl+Q`; Save: `Ctrl+S`; Open: `Ctrl+O`; New: `Ctrl+N` | Standard keyboard shortcuts | LOW | `QShortcut` or `QAction.setShortcut()` |
| Window title: `scene_name — Surg-RL Editor` with `*` when dirty | Standard | LOW | Trivial |
| Toolbar with common actions (New, Open, Save, Generate, Backend toggle) | Standard | LOW | `QToolBar` with icons (use Qt's built-in `QStyle.StandardPixmap` for v0.5.0; defer custom icons to v0.6.0) |
| Status bar: backend / FPS / sim time / scene validity | Power-user feedback | LOW | `QStatusBar` + 4 `QLabel` widgets, updated per tick |
| `QSettings` to remember window geometry / last opened scene | Standard app preference | LOW | Built-in |
| CLI launch integration: `surg-rl edit scenes/foo.json` opens editor with scene | One CLI subcommand | LOW | Typer already in CLI; add `edit` subcommand that imports + runs `SceneEditorApp.exec()` |
| Graceful shutdown: prompts to save if dirty | Standard | LOW | `closeEvent` → if dirty, `QMessageBox` save/discard/cancel |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Auto-save every 60 seconds (to `*~` backup) | "I forgot to save" insurance | LOW | `QTimer.singleShot(60_000, save_to_backup)` |
| Scene template gallery on New | "Start from suturing-with-liver" | LOW | Bundled templates in `src/surg_rl/scene_generation/templates.py` (already exists) |
| Multi-window: open 2 scenes side-by-side | Diff scenes or copy-paste between them | MEDIUM | Each `QMainWindow` is independent; trivial in Qt |
| Unsaved-changes confirmation per file when closing | Standard | LOW | Track per-window dirty state |
| Editable `metadata.author` / `metadata.modified` (auto-update on save) | Hygiene | LOW | `setattr(scene.metadata, 'modified', datetime.utcnow().isoformat())` on save |

#### Anti-Features

| Anti-Feature | Why Avoid | Alternative |
|--------------|-----------|-------------|
| Project/workspace concept (multi-file bundles) | Overkill — Surg-RL scenes are single JSON files | Single scene per window |
| Auto-update / live-patch from PyPI | Editor shouldn't self-update | Pin editor version in v0.5.0; bump in v0.6.0 |
| Cloud save / sync | Network dependency + auth | Local files only |
| Plugin system / extension API | Out of scope for milestone | None in v0.5.0 |
| Theming (dark mode toggle) | Visual polish — defer | Qt default theme fine |
| Localization (i18n) | English-only project | Defer to v1.0+ |
| Macro recording | Power-user feature with no current demand | Defer forever |

#### Dependency Notes

- **CLI subcommand `edit`** lives in `src/surg_rl/cli.py` (Typer) — already has 14 subcommands. Adding a 15th is 30 lines.
- **Optional import gate**: PySide6 is in `[gui]` optional group, not core. `surg-rl edit` must produce a friendly error if `[gui]` not installed. Typer can `try: import PySide6; except ImportError: raise typer.Exit(1) with "Install with: pip install 'surg-rl[gui]'"`.
- **Existing `load_scene()` and `save_scene()` (in `scene_definition/loader.py`)** handle JSON + YAML round-trip. Editor just calls them.

---

## Feature Category 2: Demo Suite Polish (3 Demos)

### Scope

- `demos/demo.py` — suturing (already 1168-test clean, recent 20260617-demo-rework)
- `demos/knot_tying_demo.py` — new (covers knot-tying task type, KNOT_TIER instrument)
- `demos/needle_passing_demo.py` — new (covers needle_insertion task type, NEEDLE instrument)

These three cover the **3 most-referenced** surgical task types: suturing (pick up + drive through tissue), knot-tying (dual-arm loop and tie), needle-passing (handoff between arms — natural MARL setup).

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Common narration script (shared module `demos/_common.py`) | DRY: 3 demos with the same banner, scene info, eval printout | LOW | Extract `print_banner()`, `print_scene_info(scene)`, `print_eval_results(results)` from current `demo.py` lines 145-156, 380-407, 195-204 |
| Demo banner with task name + step list | Users see "what task am I watching" immediately | LOW | `print_banner(title, stages: list[str])` |
| Headless mode (`--headless` flag) | CI / Docker / K8s has no display | LOW | Already in `demo.py`; copy the pattern |
| `--render` flag for interactive viewer | macOS dev / showcase use | LOW | Already in `demo.py`; copy pattern + existing `_omp_compat` shim |
| Scene info printer (loads scene, prints summary) | Users see "what robots/tissues/instruments are in this scene" | LOW | Already in `demo.py` lines 395-407 |
| Consistent CLI arg interface (`--steps`, `--eval-episodes`, `--seed`, `--device`, `--log-dir`) | Same UX across demos | LOW | Share argparse via `demos/_common.py: build_arg_parser()` |
| Per-demo regression test: `python demos/{name}_demo.py --headless --steps 0 --eval-episodes 1` exits 0 | CI guard; demos must not break | LOW | Per existing 20260617-demo-rework: 3 regression tests added; same pattern for the 2 new demos |
| README walkthrough section per demo | "How to run knot-tying demo" | LOW | 1 paragraph + GIF placeholder per demo |
| Scene JSON per demo in `scenes/` | Each demo owns its scene file (not shared) | LOW | `scenes/knot_tying_demo.json`, `scenes/needle_passing_demo.json` |
| Reward config per demo (custom `build_xxx_reward()`) | Task-specific shaping | LOW | Pattern from `demos/demo.py:56-77` |
| Observation config per demo | Task-specific observation needs | LOW | Pattern from `demos/demo.py:80-103` |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| GIF output of trained agent performing the task | "Watch the agent suture" — much better than text | MEDIUM | Use `imageio` (already in stack as `imageio` is part of mujoco's test deps) or `Pillow` |
| Side-by-side random-policy vs trained-policy GIF | "Before / after training" | MEDIUM | Run twice, stitch frames |
| Difficulty selector on CLI (`--difficulty EASY/MEDIUM/HARD`) | Show progression; v0.4.2 DifficultyLevel integration | LOW | Set `task.difficulty_level` in scene JSON via Pydantic |
| Curriculum `on` by default for new demos | Showcase the v0.4.0 curriculum scheduler | LOW | `args.use_curriculum = True` default |
| "Reset to canonical scene" button in interactive mode | Quick restart for demos | MEDIUM | Optional `input()` to call `env.reset()` mid-episode |

### Anti-Features

| Anti-Feature | Why Avoid | Alternative |
|--------------|-----------|-------------|
| Single mega-demo with 6 task modes via `--task` flag | Maintenance nightmare; 1 file per task is cleaner | 3 demo files; `demos/{task}_demo.py` |
| Built-in benchmark inside each demo | `demos/benchmark.py` already exists for that | Stay focused on training + eval; benchmark separately |
| Hard-coded scene paths (no `--scene` override) | Users want to try their own scenes | Keep `--scene` flag |
| Custom logging library | Rich + stdlib is sufficient | Rich console output only |
| Per-demo video recording to MP4 | ffmpeg dependency + licensing | GIF only (Pillow) |
| Live web demo / stream | Infrastructure burden | Static GIFs in docs |
| Per-demo HTML report | Out of scope — `demos/benchmark.py` does that | Keep demos CLI-only |
| Run-all-demos mode (`demos/run_all.sh`) | Bash orchestration is anti-Python | `pytest` collects demo regression tests; that's the all-demos mode |

### Dependency Notes

- **Knot-tying** requires KNOT_TIER instrument (`InstrumentType.KNOT_TIER` already in schema enum). Scene JSON uses needle_driver + knot_tier; reward must be `KnotTyingReward` (already exists in v0.4.0 task rewards).
- **Needle-passing** is the dual-arm handoff variant. Requires `MultiAgentConfig` with 2 arm_configs (surgeon + assistant). Existing v0.4.0 `MultiAgentSurgicalEnv` covers the env; need a `MultiAgentConfig` populated scene.
- **Both new demos** should follow the same `--max-episode-steps` default (2000) and the same training-config defaults as suturing demo — `demos/_common.py` exports `DEFAULT_TRAINING_CONFIG` to enforce consistency.

---

## Feature Category 3: User-facing Docs Refresh

### Scope

- `README.md` (currently 700+ lines; v0.5.0 update with screenshots)
- `CONTRIBUTING.md` (192 lines; overhaul)
- `CHANGELOG.md` (242 lines; add v0.5.0 entry)
- 3 demo walkthrough sections (one per demo)
- Screenshot capture workflow (scripted if possible)

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Quickstart updated to mention `pip install 'surg-rl[gui]'` for editor | New optional dep; users must know | LOW | 2-line addition |
| Screenshot of editor 3D viewport in README | "Show me what it looks like" — universal | LOW | Manual capture during Phase 3; commit `docs/images/editor_viewport.png` |
| Screenshot of tree+form editor in README | Same | LOW | Same |
| Screenshot of LLM prompt panel with example | Same | LOW | Same |
| 3 demo GIFs (suturing / knot-tying / needle-passing) embedded | Animated > static for showing RL behavior | MEDIUM | Capture during Phase 2; embed as `![suturing demo](docs/images/suturing_demo.gif)` |
| `CONTRIBUTING.md` has: dev setup, test command, lint command, PR workflow | Standard | LOW | Already mostly there; refresh to current ruff/black/mypy order from `AGENTS.md` |
| `CONTRIBUTING.md` mentions optional `[gui]` install path | New | LOW | 1 paragraph |
| `CONTRIBUTING.md` mentions `demos/_common.py` shared module | New pattern from Phase 2 | LOW | Update developer guide |
| `CHANGELOG.md` v0.5.0 entry with "Added/Changed/Deprecated/Removed/Fixed/Security" sections | Keep a Changelog format | LOW | Standard 5-line block per category |
| `CHANGELOG.md` lists 421 ruff cleanup, PhiFlow workaround, Dockerfile.ros2 fix in "Changed" | Tech debt deserves a mention | LOW | 3 lines |
| README badges updated: PySide6, optional extras, Python 3.10+ | Cosmetic | LOW | Shields.io URL update |
| Demo transcripts (`docs/demos/{name}_transcript.md`) for each demo | "What does running it actually look like?" | LOW | Real terminal output captured during Phase 2 |
| Links from README → CONTRIBUTING → CHANGELOG (table of contents) | Navigation | LOW | Trivial |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| "Before / after" comparison: original demo vs polished demo | Shows polish quality | LOW | Side-by-side GIFs in `docs/images/` |
| Architecture diagram (PNG/SVG) in README | Onboarding | MEDIUM | Optional — defer if effort exceeds benefit |
| "What's new in v0.5.0" blog-post-style section in README | Marketing-flavored release notes | LOW | 1 screen of text |
| Per-demo narrated video script (text only) for screen-reader users | Accessibility | LOW | Brief alt-text on every GIF |
| Troubleshooting FAQ (`docs/FAQ.md`) | Common stumbling blocks | LOW | 10 Q&A items |
| "How to add a new surgical task" tutorial | Extensibility guide | MEDIUM | Defer to v0.6.0 |

### Anti-Features

| Anti-Feature | Why Avoid | Alternative |
|--------------|-----------|-------------|
| Full API reference auto-generated from docstrings | Sphinx setup is days of work; users have source code | Link to `docs/` for narrative; source is the reference |
| Man-page-style CLI reference (`surg-rl --help` already covers it) | Duplicates `typer` output | Use the existing `surg-rl --help` |
| Deep RL theory tutorial | Not the project's job; users will read Sutton & Barto | Cite canonical RL papers if needed |
| Multi-language README (zh, ja, de) | Translation cost is real | English only in v0.5.0 |
| Marketing website / landing page | Not a product site | README is the website |
| Detailed comparison with competing simulators (e.g., AMBF, SurRoL) | Out of scope; users know | One-line "related work" pointer |
| Step-by-step "first RL training" video | Video is out of scope; GIF + text is enough | Static GIFs + transcript |
| PDF docs | PDF is dead for code projects | Markdown only |

### Dependency Notes

- **Screenshot capture during Phase 3 (editor phase)** is critical: the editor must be running with a sample scene to capture. Treat screenshots as **milestone artifacts**, not afterthoughts. Plan: at end of Phase 3, run a "screenshot capture" sub-plan that produces 3-5 PNGs and 3 GIFs.
- **GIFs from demos** require running a real training loop + frame capture. The `imageio` library (already a transitive dep of mujoco) is sufficient: capture 100-200 frames at 10 FPS, save as GIF. Plan: at end of Phase 2, run `--steps 5000` on each demo with `render=True` and save frames.

---

## Feature Category 4: Tech Debt Cleanup (Interleaved)

### Scope (per PROJECT.md v0.5.0)

- 421 ruff issues in `src/surg_rl/dreamer/` (F841, B904, E402)
- HARD-fixture env-construction integration test (`suturing_difficulty_hard.json` fixture)
- Fluid step hook in `base_simulator.py`
- Cut cooldown unit test
- Dockerfile.ros2 amd64 hardcode fix
- PhiFlow multi-obstacle union() workaround

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| 421 ruff issues → 0 (or <5) | "Pre-existing lint issues" are embarrassing; ruff is the project's linter | LOW | `ruff check --fix src/surg_rl/dreamer/`. Should be a one-shot plan, not a phase. |
| HARD-fixture env-construction integration test | Code review gap from v0.4.2; proves the DifficultyLevel enum path works end-to-end | MEDIUM | `tests/integration/test_suturing_hard_env_construction.py`; `pytest.mark.integration`; loads `tests/fixtures/scenes/suturing_difficulty_hard.json`, constructs `SurgicalEnv`, runs `reset()`, asserts no crash |
| Fluid step hook in `base_simulator.py` | Code review gap from v0.3.2; env-level hook is "sufficient" but base hook is the principled fix | MEDIUM | Add `_step_fluid(dt)` method in `BaseSimulator` ABC; call from `step()`; default no-op; MuJoCo/PyBullet simulators override as needed |
| Cut cooldown unit test | Code review gap from v0.3.2; proves the 500ms cooldown arithmetic | LOW | Unit test: call `env.cut(...)` twice within 500ms, second call is no-op; assert step counter advances correctly |
| Dockerfile.ros2 amd64 hardcode fix | Code review gap from v0.3.1; blocks arm64 ROS2 builds | LOW | `FROM --platform=linux/amd64` → use `TARGETARCH` build arg + multi-arch base |
| PhiFlow multi-obstacle union() workaround | Code review gap from v0.3.2; current code crashes on >1 obstacle | MEDIUM | Manual SDF merge: `for obs in obstacles: sdf = phiflow.geometry.sdf(obs) unioned = unioned.union(sdf) if unioned is not None else sdf`. Wrap in helper `_union_sdfs(obstacles)`. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Per-tet generation counter (v0.3.2 deferred) | Diagnostic — "how many tets did we generate for this cut?" | LOW | Counter on `FlexComp`; not a feature per se, but useful for cut debugging |
| 3D fluid flag (`dim_3d=True`) | Show 3D fluids work even if slow | HIGH | Defer — out of v0.5.0 scope per PROJECT.md |
| K8s PVC e2e test | Real cluster testing | HIGH | Defer — v0.6.0+ |
| KubeRay prerequisite (e2e test) | Distributed RL test | HIGH | Defer — v0.6.0+ |

### Anti-Features

| Anti-Feature | Why Avoid | Alternative |
|--------------|-----------|-------------|
| Rewrite `src/surg_rl/dreamer/` from scratch | Ruff cleanup is about the existing 421 issues, not a rewrite | Run `ruff check --fix`; manual review of auto-fixes that change semantics |
| Add mypy strict mode project-wide | Would surface hundreds of new errors | Keep mypy at current strictness; clean up dreamer/ ruff only |
| Refactor `BaseSimulator` while adding the fluid step hook | Scope creep — touch only what the hook requires | Minimal addition; full refactor in v0.6.0 |
| Add benchmarks for the 421 ruff fixes (performance regression) | Lint fixes shouldn't change runtime | Run existing test suite; performance is unaffected by F841/B904/E402 |

### Dependency Notes

- **421 ruff cleanup** is the single largest tech-debt item. Per `v0.4.0 Nyquist audit`, issues are concentrated as F841 (unused variable), B904 (`raise from` inside `except`), E402 (module-level import not at top). Most are auto-fixable. Plan: 1 plan, 1 day.
- **HARD-fixture integration test** requires the `pytest.mark.integration` marker. Marked tests are skipped by default (`pytest -m "not integration"`); CI enables them.
- **Fluid step hook** must be backward-compatible: all existing simulators must continue to work without override. Default implementation is a no-op (`pass`).
- **Cut cooldown test** is a pure unit test on the arithmetic — no env construction required. ~30 lines.
- **Dockerfile.ros2** fix requires the multi-arch Docker build pipeline (already in v0.3.0). Verify with `docker buildx build --platform linux/amd64,linux/arm64 .`.
- **PhiFlow union() workaround** lives in `surg_rl/fluids/` (PhiFlow integration code). Add a `test_union_sdf_helper.py` with 3 obstacles + 1 expected merged SDF.

---

## Feature Dependencies

```
[Stack locked: PySide6 6.8+ via [gui] optional group]
            │
            ├──> 1A. 3D Viewport
            │       ├──requires──> mujoco.Renderer (mujoco>=3.0)
            │       ├──requires──> pybullet.getCameraImage
            │       ├──enhances──> 1E. Editor Shell (status bar)
            │       └──conflicts──> None
            │
            ├──> 1B. Tree Editor
            │       ├──requires──> SceneDefinition.model_fields (Pydantic v2 introspection)
            │       ├──requires──> QStandardItemModel
            │       └──enhances──> 1C. Property Form (selection sync)
            │
            ├──> 1C. Property Form Editor
            │       ├──requires──> SceneDefinition.model_json_schema() (Pydantic v2)
            │       ├──requires──> Pydantic v2 validator (for inline errors)
            │       ├──requires──> QUndoStack (shared with 1B)
            │       └──conflicts──> 1D. LLM panel direct JSON edit (rejected)
            │
            ├──> 1D. LLM-Prompt-to-JSON Panel
            │       ├──requires──> TextParser.parse() (existing)
            │       ├──requires──> TextParser.parse_with_context() (existing)
            │       ├──requires──> VisionParser.parse() (existing)
            │       ├──requires──> config.get_settings() (existing)
            │       └──enhances──> 1B. Tree Editor (writes to scene)
            │
            └──> 1E. Editor Shell
                    ├──requires──> load_scene() / save_scene() (existing)
                    ├──requires──> QSettings (built-in)
                    ├──requires──> CLI integration via Typer (existing)
                    └──enhances──> All of 1A-1D (containers them)

[Phase 1: Tech debt cleanup]
[Phase 2: Demo suite polish]
    └──depends on──> existing TaskRewardRouter, CurriculumScheduler, DifficultyLevel
                     (all v0.4.0–v0.4.2)
[Phase 3: PySide6 Editor]  (1A, 1B, 1C, 1D, 1E together)
    └──depends on──> [gui] extra (PySide6 6.8+) installed
[Phase 4: User-facing docs]
    └──depends on──> Phase 2 (demo transcripts), Phase 3 (screenshots)
[Phase 5: Advanced tech debt]  (deferred items)
```

### Critical Dependency Notes

1. **All four 1A-1E editor features** ship together in Phase 3. They share the schema walker (1C) and the Qt main window (1E). Splitting them across phases would mean rebuilding the workspace shell twice.
2. **The `[gui]` extra** is the only new dependency. PySide6 wheels are large (~120 MB); keeping it optional means headless CI / K8s / Docker images don't pay the cost.
3. **LLM panel (1D) is 95% wiring** of existing `TextParser`/`VisionParser` code. The 5% new code is async-to-Qt bridging.
4. **Tech debt (Category 4) can run in parallel** with the feature work — the 421 ruff is in `dreamer/` which the editor doesn't touch. The HARD-fixture test, fluid hook, cut cooldown test, and Dockerfile fix are all isolated.
5. **Docs (Category 3) is sequential** — needs artifacts from Phases 2 (demos) and 3 (editor screenshots). Must be Phase 4 or later.

---

## MVP Definition (v0.5.0 Launch)

### Must Have (P1) — Without These, Milestone Fails

- [ ] **1A. 3D viewport** with orbit/pan/zoom, camera reset, FPS throttle, screenshot
- [ ] **1B. Tree editor** with hierarchy, context menu (add/duplicate/delete), drag-reorder
- [ ] **1C. Property form** schema-driven with type-aware widgets + live Pydantic validation
- [ ] **1D. LLM panel** wired to existing `TextParser.parse()` and `parse_with_context()`; Accept/Reject/Regenerate
- [ ] **1E. Editor shell** with workspace layout, File→New/Open/Save, `--headless` and `--render` flags, CLI `surg-rl edit` subcommand
- [ ] **2. 3 demos** — suturing (existing), knot-tying (new), needle-passing (new) with shared narration module
- [ ] **3. README + CONTRIBUTING + CHANGELOG** updated
- [ ] **4. 421 ruff → 0** (in `src/surg_rl/dreamer/`)
- [ ] **4. HARD-fixture integration test** passing
- [ ] **4. Fluid step hook** added to `BaseSimulator` (default no-op, backward-compatible)
- [ ] **4. Cut cooldown unit test** added
- [ ] **4. Dockerfile.ros2 amd64 fix** + multi-arch build verified
- [ ] **4. PhiFlow union() workaround** with unit test
- [ ] **Optional `[gui]` extra** in `pyproject.toml` with PySide6 >=6.8.0

### Should Have (P2) — Add If Time Permits

- [ ] **1A.** Backend toggle (MuJoCo ↔ PyBullet) — works but expensive
- [ ] **1A.** Screenshot to PNG (basic version is in P1, but clipboard option is P2)
- [ ] **1A.** Wireframe / solid / textured shading cycle
- [ ] **1B.** Undo/redo (Ctrl+Z / Ctrl+Y)
- [ ] **1C.** Color picker for `RgbColor`
- [ ] **1C.** Vector editor for `tuple[float, float, float]`
- [ ] **1D.** VisionParser image-drop integration
- [ ] **1D.** Diff view (current vs LLM-generated scene)
- [ ] **1E.** Recent files (last 5)
- [ ] **1E.** Auto-save every 60s
- [ ] **2.** GIFs for each demo (3 GIFs in `docs/images/`)
- [ ] **2.** Difficulty selector (`--difficulty EASY/MEDIUM/HARD`)
- [ ] **3.** Per-demo transcripts in `docs/demos/`
- [ ] **3.** 3 editor screenshots in `docs/images/`
- [ ] **3.** Demo walkthrough sections in README

### Nice to Have (P3) — Future (v0.6.0+)

- [ ] **1A.** Side-by-side MuJoCo vs PyBullet render (2x cost)
- [ ] **1A.** Saved camera bookmarks
- [ ] **1A.** Simulation play/pause/step controls
- [ ] **1A.** Time-scrubber / episode replay
- [ ] **1B.** Drag-from-asset-library
- [ ] **1B.** Search/filter bar
- [ ] **1C.** Field history / recently-used values
- [ ] **1C.** Diff view ("show changes since last save")
- [ ] **1C.** Per-field help link to markdown docs
- [ ] **1D.** Template prompt library
- [ ] **1D.** Cost estimate before generate
- [ ] **1E.** Multi-window (2 scenes side-by-side)
- [ ] **1E.** Scene template gallery on New
- [ ] **2.** Side-by-side random-vs-trained GIFs
- [ ] **2.** "Reset to canonical scene" interactive button
- [ ] **3.** Architecture diagram
- [ ] **3.** "How to add a new surgical task" tutorial
- [ ] **3.** FAQ
- [ ] **4.** Per-tet generation counter
- [ ] **4.** 3D fluid flag implementation

### Explicitly Out of Scope (Defer or Reject)

- [ ] **1A.** VR/AR preview, custom GLSL shaders, multi-viewport quad-split
- [ ] **1A.** MP4 video recording, real-time raytraced PBR
- [ ] **1B.** Visual scripting, behavior trees, tagging system
- [ ] **1C.** Custom validators beyond Pydantic, mass-edit across selections
- [ ] **1D.** LLM fine-tuning, audio/video prompts, conversation history beyond 10
- [ ] **1E.** Plugin system, theming, localization, cloud save
- [ ] **2.** Single mega-demo with `--task` flag, per-demo HTML reports
- [ ] **3.** API reference auto-gen, full RL theory tutorial, multi-language README, marketing site
- [ ] **4.** Rewrite `dreamer/` from scratch, mypy strict mode project-wide

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| 1A 3D viewport (P1 subset) | HIGH | MEDIUM | P1 |
| 1B Tree editor (P1 subset) | HIGH | LOW | P1 |
| 1C Form editor (P1 subset) | HIGH | MEDIUM | P1 |
| 1D LLM panel (P1 subset) | HIGH | LOW | P1 |
| 1E Editor shell (P1 subset) | HIGH | LOW | P1 |
| 2 Demo suite (3 demos) | MEDIUM | MEDIUM | P1 |
| 3 Docs (README/CONTRIB/CHANGELOG) | HIGH | LOW | P1 |
| 4 Tech debt (421 ruff, 5 fixes) | MEDIUM | LOW-MED | P1 |
| 1A Backend toggle | MEDIUM | HIGH | P2 |
| 1D VisionParser | MEDIUM | MEDIUM | P2 |
| 2 GIFs for demos | HIGH | MEDIUM | P2 |
| 3 Editor screenshots | HIGH | LOW | P2 |
| 1A Saved camera bookmarks | LOW | LOW | P3 |
| 1A Side-by-side render | LOW | HIGH | P3 |
| 1A Time-scrubber | LOW | HIGH | P3 |
| 1C Diff view | LOW | HIGH | P3 |
| 1D Template library | LOW | LOW | P3 |
| 2 Random-vs-trained GIFs | LOW | MEDIUM | P3 |
| 3 Architecture diagram | LOW | MEDIUM | P3 |
| 4 Per-tet counter | LOW | LOW | P3 |
| 4 K8s PVC e2e | LOW | HIGH | v0.6.0+ |
| 4 3D fluid flag | LOW | HIGH | v0.6.0+ |

---

## Cross-Cutting Concerns

### Backwards Compatibility
- **All 1,134 existing tests must still pass**. The editor is purely additive — new optional dep, new `surg-rl edit` subcommand, no changes to existing imports.
- **Pydantic v2 schema** is unchanged. The editor consumes `model_json_schema()` (read-only) and writes back via `model_validate()` (existing).
- **`[gui]` extra** is optional. Headless users (`pip install surg-rl`) never see PySide6 imported. `surg-rl edit` errors gracefully if `[gui]` is missing.

### Testing Strategy
- **Schema walker unit tests** (Feature 1C, 1B): for every Pydantic field type in `schema.py` (58 `$defs`), verify correct widget is generated. ~30-40 unit tests.
- **LLM panel mock tests** (Feature 1D): monkey-patch `TextParser.parse` to return canned SceneDefinitions; verify Accept/Reject/Regenerate flow. ~10 unit tests.
- **Editor shell integration test** (Feature 1E): launch editor headless via `QT_QPA_PLATFORM=offscreen`, load a scene, save, reload, verify equality. ~3-5 integration tests with `@pytest.mark.integration`.
- **Demo regression tests** (Feature 2): 1 per demo, total 3 tests, mark as `@pytest.mark.integration` (they take 5-10 seconds each).
- **Tech debt tests** (Category 4): HARD-fixture test (`@pytest.mark.integration`), cut cooldown unit test, PhiFlow union test, fluid step hook test. ~6 tests.

### Confidence Assessment
- **HIGH** for PySide6 patterns (Qt is mature; widget mapping is well-documented).
- **HIGH** for schema-driven form generation (Pydantic v2's `model_json_schema()` is the industry standard).
- **HIGH** for demo patterns (existing demo.py is the template).
- **HIGH** for docs patterns (Keep a Changelog is standard; README structure is well-known).
- **HIGH** for tech debt (each item has a known fix pattern from PROJECT.md context).

### Key Risks
- **PySide6 wheel size** (~120 MB) might surprise users. Mitigation: clear docs, optional extra is documented.
- **Schema walker bug for an edge-case Pydantic type** (e.g., `Literal[...]`, `Union[...]`) could crash editor. Mitigation: comprehensive unit tests for all 58 `$defs` before feature phase.
- **LLM panel with real LLM provider** requires API keys. Mitigation: defaults to Ollama (free, local); `VISION_OPENAI_API_KEY` error is friendly.
- **GIF capture during Phase 2 demos** depends on rendering being fast enough. Mitigation: low-res GIF (320x240), 10 FPS, 100 frames max = ~10 seconds of capture.
- **3D viewport FPS** on integrated GPUs (Apple Silicon, Intel UHD) might dip below 15. Mitigation: FPS throttle is configurable; user can lower to 10 FPS.

---

## Sources

- **PySide6 official docs** — Qt-for-Python API reference (QWidget, QMainWindow, QTreeView, QStandardItemModel, QFormLayout, QUndoStack, QSettings) — HIGH confidence
- **Pydantic v2 JSON Schema** — `model_json_schema()` and `model_validate()` semantics, including `model_dump(mode="json")` for safe round-trip — HIGH confidence
- **Existing codebase**:
  - `src/surg_rl/scene_definition/schema.py` (1506 lines, 58 `$defs` per `model_json_schema()`)
  - `src/surg_rl/scene_generation/text_parser.py` (597 lines, TextParser with OpenAI/Anthropic/Ollama)
  - `src/surg_rl/scene_generation/vision_parser.py` (existing, references VLM providers)
  - `demos/demo.py` (446 lines, suturing demo template)
  - `src/surg_rl/scene_generation/templates.py` (existing scene templates for New menu)
  - `src/surg_rl/scene_definition/loader.py` (existing `load_scene()` and `save_scene()`)
- **v0.4.0–v0.4.2 research**:
  - `.planning/research/STACK-v0.5.0.md` (PySide6 6.8+ stack decision, schema-driven walker, `[gui]` extra)
  - `.planning/research/FEATURES.md` (v0.4.0 features for context)
- **Existing Pydantic v2 gotchas** (per `AGENTS.md`):
  - `model_dump()` returns Enum objects, not `.value` strings — use `model_dump_json()` or `model_dump(mode="json")` for round-trip
  - `model_construct()` is the only way to skip validation
  - `model_validator(mode="after")` requires `model_copy(update=...)` not in-place mutation
- **Qt 3D viewport patterns** in robotics sims: `mujoco.Renderer` for offscreen GL; `pybullet.getCameraImage` for PyBullet; both wrap in `QWidget` with `QTimer`-driven `paintEvent` update — pattern is standard (rl-baselines3-zoo, robosuite viewer)

---

*Feature research for: v0.5.0 Scene Editor & UX Polish*
*Researched: 2026-06-18*

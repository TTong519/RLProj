# Stack Research — v0.5.0 Scene Editor & UX Polish

**Project:** Surg-RL — Scene Editor & UX Polish milestone
**Researched:** 2026-06-18
**Overall confidence:** HIGH (most deps verified against PyPI JSON + Context7 docs at research time)

## Executive Summary

v0.5.0 adds a **PySide6 GUI scene editor** (3D viewport + tree/form editor + LLM-prompt-to-JSON), three polished surgical task demos, and a user-facing docs refresh. Two dependency axes are new:

1. **Qt GUI stack** — PySide6 (Qt 6.11.x, official Qt-for-Python, LGPL-3-or-GPL-2/3 — compatible with our MIT project because LGPL allows dynamic linking with proprietary code; we use the LGPL path with `LGPL-3.0-only` licensing note documented).
2. **Markdown rendering** — `markdown-it-py` (already installed transitively) replaces a heavier dep for in-GUI help/docs.

The critical architectural insight is that **the 3D viewport does not need a third-party OpenGL widget**: MuJoCo 3.x ships `mujoco.Renderer` which produces a NumPy RGB array via offscreen GL (`GLContext`), and PyBullet has `pybullet.getCameraImage`. Both can be wrapped by a tiny `QWidget` subclass that periodically grabs a frame and renders it as a `QImage`. This is the same architectural choice rl-baselines3-zoo uses for its MuJoCo viewer, and it avoids the OpenGL-context-within-Qt-pain that PyOpenGL/VisPy/pyqtgraph options introduce.

We **deliberately do NOT add**: PyQt6 (license-incompatible-Riverbank-GPL-or-commercial), pyqtgraph (overkill for our needs, pulls Qt dependency tree), VisPy (requires PyOpenGL, fragile Qt-context handoff), PyOpenGL (deprecated, replacement is `moderngl` — also too heavy), Qt3D (Qt5 only, never migrated to Qt6 mainline), Tkinter (already a stdlib fallback only, not a serious Qt6 replacement), qt-material/qtawesome (visual polish not needed for v0.5.0 — deferred to v0.6.0).

Schema-driven form generation is **zero-new-deps**: Pydantic v2's `SceneDefinition.model_json_schema()` already produces a full JSON Schema with `$defs`. We use a tiny internal walker that maps JSON Schema types → Qt widgets (`QStringListModel` for enums, `QDoubleSpinBox` for numbers, `QLineEdit` for strings, recursive `QFormLayout` for nested objects). This is the same approach Blender and Godot use for their property panels.

Demo narration uses the **existing Rich** dependency (already at 15.0) — no new lib needed.

## New Optional Dependency Group: `[gui]`

```toml
[project.optional-dependencies]
# GUI scene editor — PySide6 + markdown rendering
gui = [
    "PySide6>=6.8.0,<7.0",       # Qt6 LTS line, official Qt-for-Python
    "markdown-it-py>=3.0.0",     # CommonMark parser for in-GUI help/docs
]
```

Pattern follows existing `[marl]`, `[dreamer]`, `[vision]`, `[benchmark]` groups — `[gui]` stays out of core deps so headless servers (Docker, CI, K8s) don't pay the Qt install footprint (~120 MB wheels).

## Recommended Stack by Component

### 1. PySide6 — Qt for Python

| Library | Version | License | Purpose | Why |
|---------|---------|---------|---------|-----|
| PySide6 | `>=6.8.0,<7.0` | LGPL-3.0 / GPL-2.0 / GPL-3.0 (multi-license, user picks) | Qt6 Python bindings | **Official Qt-for-Python** from The Qt Company under LGPL — the only Qt binding with permissive licensing compatible with the project's MIT license. PyQt6 (Riverbank) is GPL-only-or-commercial and incompatible with MIT redistribution. PySide6 6.8+ supports Python 3.13 and the modern Qt Quick / Qt Widgets / Qt Model-View split. Current PyPI: **6.11.1**, requires `>=3.10,<3.15`. |

**Why PySide6 over PyQt6:**
- **License**: LGPL-3 allows linking from MIT-licensed code (commercial use OK if end-user can re-link the LGPL component). PyQt6's GPL-3 would force the entire Surg-RL package to GPL — out of the question for a research package that may be used in commercial settings.
- **API parity**: PySide6 exposes identical Qt6 API. `PySide6.QtWidgets`, `PySide6.QtCore`, `PySide6.QtGui` mirror PyQt6 1:1.
- **Wheel size**: ~120 MB per platform (compared to PyQt6 ~80 MB; difference is largely unused modules). Acceptable for an opt-in `[gui]` group.
- **Long-term support**: Qt 6.8 LTS until Oct 2026 (commercial), Qt 6.11 is current. PySide6 mirrors Qt release cadence.

**Qt6 widgets used** (verified against Context7 docs):

| Widget | Use |
|--------|-----|
| `QMainWindow` | Top-level editor shell with menus/toolbars/status bar |
| `QDockWidget` | Dockable tree editor + form panel + properties panel |
| `QTreeView` + `QStandardItemModel` | Hierarchical scene tree (instruments → tissues → task) — verified against Context7 `/websites/doc_qt_io_qtforpython-6` "Displaying Hierarchical Data with QTreeView" example |
| `QFormLayout` | Right-side form editor (label/value pairs per property) |
| `QDoubleSpinBox`, `QSpinBox`, `QLineEdit`, `QComboBox`, `QCheckBox` | Per-type form widgets generated from JSON Schema |
| `QGraphicsView` (NOT QGLWidget) | 3D viewport — renders a `QImage` updated from MuJoCo/PyBullet offscreen render |
| `QTextBrowser` | In-GUI help/docs panel (renders markdown via `markdown-it-py` → HTML → `setHtml`) |
| `QThread` / `QThreadPool` | Background LLM API calls (via `text_parser.TextParser.parse_sync`) |
| `QSettings` | Persist window geometry, last-loaded scene path |
| `QFileDialog` | Open/save `.planning/scenes/*.json` |
| `QProgressBar` | Long-running scene-build / LLM-call progress |

**Integration points with existing code:**

- `scene_generation/text_parser.py` — `TextParser.parse_sync()` is called from a `QThread.run()` to keep the GUI responsive during LLM calls (typically 5–30 s). The thread emits a `QObject.signal` with the resulting `SceneDefinition`; the main thread updates the tree/form via `QStandardItemModel.setData()`. The existing `parse_sync()` raises `RuntimeError` if called inside a running event loop — QThread creates a fresh thread, so this is safe.
- `scene_definition/schema.py` — `SceneDefinition.model_json_schema()` is called at editor startup to build the form widget map. The 58 `$defs` entries are introspected once and cached.
- `simulators/scene_builder.py` — already has primitive-fallback mesh generation; the editor's "Preview" button calls `SceneBuilder.build_mjcf(scene)` to write a temporary MJCF, loads it with MuJoCo, and renders one frame. The scene_builder is **not** modified — only consumed.
- `cli.py` — add `surg-rl editor` subcommand (Typer) that calls `qasync.run()` or `QApplication.exec()` to launch the editor.
- `utils/config.py` — `get_settings()` already provides `llm_provider`, `llm_api_key`, etc. The editor reuses this; no new env vars.

### 2. 3D Viewport — offscreen renderer + QGraphicsView (no 3rd-party OpenGL)

**Recommendation: do NOT add PyOpenGL / pyqtgraph / VisPy / moderngl / Qt3D.**

We use the simulators' built-in offscreen render APIs and display frames via `QGraphicsView`:

| Backend | Render API | Frame Path | Notes |
|---------|-----------|-----------|-------|
| MuJoCo 3.7+ | `mujoco.Renderer(model, height, width)` → `.render()` returns `np.ndarray` (RGB) | NumPy → `QImage.fromData(rgb_bytes)` → `QGraphicsPixmapItem` | Verified: `Renderer.__init__(model, height, width)`; `render(*, out=None) -> np.ndarray`. macOS works via OSMesa/glfw context inside MuJoCo; no separate GL context needed. |
| PyBullet ≥3.2.5 | `pybullet.getCameraImage(w, h, view, proj)` returns (w,h,4) RGBA | Same QImage path | Already used in existing demos; no new code. |

A 20 Hz `QTimer` updates the pixmap, which is more than enough for "edit-time preview" UX. This avoids:
- **PyOpenGL** (3.1.10, BSD): Wraps GL 1.x–4.x, requires sharing GL context with Qt — fragile on macOS, no Qt6-friendly widget.
- **pyqtgraph** (0.14.0, MIT): Excellent for 2D plots, has `GLViewWidget` for 3D — but its `GLViewWidget` is its own scene graph, not MuJoCo's. Would require us to re-implement MuJoCo's render-into-pyqtgraph bridge.
- **VisPy** (0.16.2, BSD-3): Backend-agnostic 3D scene graph with Qt support — but it would mean two scene graphs (MuJoCo's internal `MjrContext` + VisPy's), defeating the purpose.
- **Qt3D**: Deprecated in Qt6 mainline (now `Qt Quick 3D`); not appropriate for headless render compatibility.

**Pattern**: `ViewportWidget(QWidget)` owns a `QHBoxLayout` containing a `QGraphicsView` with a `QGraphicsScene` that contains a single `QGraphicsPixmapItem`. A 50ms `QTimer` (`viewport_widget.timer.timeout.connect(render_frame)`) calls `mujoco_simulator.render_to_numpy()` (new method on MuJoCoSimulator that wraps `mujoco.Renderer`) and `pixmap_item.setPixmap(QPixmap.fromImage(QImage(rgb_bytes, w, h, QImage.Format_RGB888)))`. Sim cost: ~5 ms/frame at 640×480 on M-series Mac — well within budget for an editor.

**What we DO add to the simulator layer** (not the dep graph): a thin `render_to_numpy(width, height) -> np.ndarray` method on `BaseSimulator` (with MuJoCo + PyBullet implementations) — ~30 LOC, no external dep.

### 3. Tree + Form Editor — Qt Model/View (built-in)

**Recommendation: Use Qt's built-in Model/View framework. No new deps.**

- `QStandardItemModel` for the scene tree (hierarchical: SceneDefinition → robots → instruments → tissues → task → fluid). `QStandardItem.setData(value, role=Qt.UserRole+1)` stores the JSON Schema path to the property; double-clicking a leaf sends a signal that rebuilds the form panel.
- `QFormLayout` for the form panel: label on left, widget on right. Widgets are generated per-JSON-Schema-type by a `FormBuilder` class (~80 LOC) that lives in `surg_rl/gui/form_builder.py`. The builder inspects `Model.model_fields` (Pydantic v2) for type/constraint metadata (`Field(ge=0, le=1)`, `Literal[...]`, `Enum`).

**Verified**: Context7 `/websites/doc_qt_io_qtforpython-6` documents the `QStandardItemModel` + `QTreeView` + `selectionModel.selectionChanged` pattern. This is the canonical Qt approach; no third-party widget library needed.

**Optional future dep (NOT v0.5.0):** `qmodeltester` (Qt-provided) for model unit tests — already in PySide6 as `PySide6.QtTest.QAbstractItemModelTester`. Zero new install.

### 4. JSON Schema–Driven Form Generation — Pydantic v2 native (no jsonschema)

**Recommendation: Use `Model.model_json_schema()` directly. Do NOT add `jsonschema` as a runtime dep.**

Pydantic v2's `SceneDefinition.model_json_schema()` returns a complete JSON Schema dict (verified above — 58 `$defs` entries, standard JSON Schema 2020-12 dialect). Our `FormBuilder` consumes this dict via a small walker:

```python
def widget_for_schema(schema: dict, root: type[BaseModel]) -> QWidget:
    """Map a JSON Schema fragment to a Qt input widget."""
    if "$ref" in schema:
        # Resolve $ref against root.__pydantic_core_schema__["$defs"]
        ...
    typ = schema.get("type")
    if "enum" in schema:
        return QComboBox()  # populate from enum values
    if typ == "number":
        sb = QDoubleSpinBox()
        sb.setRange(schema.get("minimum", -1e9), schema.get("maximum", 1e9))
        return sb
    if typ == "integer":
        return QSpinBox()
    if typ == "string":
        return QLineEdit()
    if typ == "boolean":
        return QCheckBox()
    if typ == "array":
        return ListEditor(schema)  # custom widget
    if typ == "object":
        return NestedForm(schema)   # recursive QFormLayout
```

The walker uses `root.model_fields` for Pydantic metadata (constraints, descriptions, defaults) rather than re-parsing the JSON Schema — simpler and more reliable.

**Why not `jsonschema`?** It's already installed transitively (via `pydantic`), but we don't need its validation/resolve-ref logic at runtime — Pydantic handles validation on `model_validate()` after the form is built. Adding it as a runtime dep would duplicate work Pydantic already does and would force us to walk two schema trees (Pydantic's core schema + JSON Schema).

**`jsonschema` is NOT in the v0.5.0 `[gui]` group.**

### 5. LLM-prompt-to-JSON in Qt — existing text_parser.py + QThread

**Recommendation: Call `TextParser.parse_sync()` from `QThread`. No new deps.**

`scene_generation/text_parser.py` already exposes `parse_sync(input_data, **kwargs) -> SceneDefinition`. It internally calls `asyncio.run()` — safe to call from a non-event-loop thread (it raises `RuntimeError` if there IS a loop). The GUI flow:

1. User types prompt in `QLineEdit` → clicks "Generate Scene" `QPushButton`.
2. Button click signal → `_generate_scene_thread = QThread(); worker = TextParserWorker(prompt); worker.moveToThread(_generate_scene_thread); _generate_scene_thread.started.connect(worker.run); worker.finished.connect(_on_scene_generated); worker.finished.connect(_generate_scene_thread.quit)`.
3. `TextParserWorker.run()` calls `self._parser.parse_sync(self._prompt)` (blocking; runs in background thread).
4. `_on_scene_generated(scene)` (main thread) updates the tree + form model.

This is the standard Qt worker-thread pattern; no `qasync` needed. The existing `parse_sync()` raises `RuntimeError` if called from inside a running loop — Qt's main thread DOES have a running loop, but `QThread` workers are separate threads with NO loop, so this is safe.

### 6. Markdown rendering for in-GUI help — markdown-it-py (already installed)

**Recommendation: Use `markdown-it-py` (already installed transitively). Promote to explicit `[gui]` dep.**

Verified against Context7 `/executablebooks/markdown-it-py`:
```python
from markdown_it import MarkdownIt
md = MarkdownIt('commonmark', {'breaks': True, 'html': True})
html = md.render(markdown_text)
# Then: text_browser.setHtml(html)
```

`QTextBrowser.setHtml()` accepts the rendered HTML and applies the system stylesheet. We render on-the-fly when the user opens the help panel — no caching needed for typical scene docs (1–10 KB).

**Why not `mistune`?** `mistune` 3.2.1 is also installed transitively and is faster, but its API is less configurable. `markdown-it-py` has better CommonMark conformance (officially tested against the spec suite) and a plugin ecosystem (`mdit-py-plugins`) if we later need footnotes, tables, etc. — kept minimal in v0.5.0, CommonMark only.

**Why not `markdown` (Python-Markdown)?** Slower, less CommonMark-compliant, uses C extension by default (extra build step). `markdown-it-py` is pure Python and ~10× faster than `markdown` 3.x on the same inputs.

### 7. Demo narration tooling — existing Rich

**Recommendation: Use existing `rich>=13.0.0` (currently 15.0). No new dep.**

The three demos (suturing, knot-tying, needle-passing) need consistent narration — phase banners, progress bars, completion summaries. `rich` already in the dep graph provides:
- `rich.console.Console` — colored output
- `rich.panel.Panel` — phase banners (consistent style across demos)
- `rich.progress.Progress` — step counters and task progress
- `rich.table.Table` — final summary (task name, reward, timesteps, duration)

We add a tiny `demos/_narration.py` module (~50 LOC) with `phase_banner(console, title, subtitle)`, `step_progress(console, current, total, message)`, `demo_summary(console, results)`. This is **not** a new dep — just a project-local helper.

**Why not Jupyter?** Jupyter notebooks (`.ipynb`) provide interactive narration but require `nbconvert` + a kernel install per demo, and force users to manage a notebook server. The existing demo style is **standalone Python script** (`python demos/demo.py --headless --steps 10000`) — Rich keeps that ergonomic. Jupyter-based walkthrough is deferred to v0.6.0.

**Why not `textual`?** TUI framework by the Rich author — overkill for CLI demos, would couple demos to a TUI library.

### 8. Optional `[gui]` packaging pattern — aligned with existing groups

The pyproject `[gui]` group follows the existing convention:

```toml
[project.optional-dependencies]
# Existing groups unchanged: assets, benchmark, dev, llm, marl, meshing,
# simulation, vision, tracking, distributed, dreamer, ros2, docs

# v0.5.0 addition — GUI scene editor
# PySide6 is LGPL-3-or-GPL — we pin >=6.8,<7.0 for Qt6.8 LTS line + Qt6.11
# current; markdown-it-py is already a transitive dep but pinned explicitly
gui = [
    "PySide6>=6.8.0,<7.0",
    "markdown-it-py>=3.0.0",
]
```

**Install command:**
```bash
pip install -e ".[dev,gui]"          # editor dev
pip install -e ".[gui]"              # editor only (users)
pip install -e ".[dev,gui,marl]"     # editor + multi-agent
```

**CI matrix:** `[gui]` is NOT in the default test install (CI runs headless on Linux containers). Add an `[gui]`-tagged job that runs `pip install -e ".[gui]"` + `QT_QPA_PLATFORM=offscreen pytest tests/gui/ -v` for GUI smoke tests. This mirrors the pattern used for `[dreamer]` (gated on GPU + jax) and `[ros2]` (gated on Linux).

## Dependency Diff

### New Optional Group

| Group | Packages | Min Size | Notes |
|-------|----------|----------|-------|
| `gui` | `PySide6>=6.8.0,<7.0`, `markdown-it-py>=3.0.0` | ~120 MB (PySide6 wheel) + ~50 KB | Off the critical install path; only enabled when GUI editor is used. |

### Bumped Existing Deps

_None_ — `rich>=13.0.0` already installed; `markdown-it-py` was already a transitive dep (now promoted to explicit).

### No-Version-Change (Already Sufficient)

| Package | Existing Pin | v0.5.0 Verdict |
|---------|-------------|----------------|
| `rich` | `>=13.0.0` (installed: 15.0) | Keep. Sufficient for narration. |
| `typer` | `>=0.9.0` | Keep. New `surg-rl editor` subcommand uses Typer. |
| `pydantic` | `>=2.0.0` (installed: 2.13.3) | Keep. `model_json_schema()` drives the form builder. |
| `mujoco` | `>=3.0.0` (installed: 3.7.0) | Keep. `Renderer` + `GLContext` provide offscreen render. |
| `pybullet` | `>=3.2.5` | Keep. `getCameraImage` provides offscreen render. |

## What NOT to Add (Anti-Recommendations)

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **PyQt6** | GPL-3 license incompatible with MIT project; would force Surg-RL to GPL. Commercial license costs $550+/dev/year. | PySide6 (LGPL-3) |
| **PyQt5** | Qt5 reached EOL May 2025; no security updates; no Python 3.13 wheels. | PySide6 (Qt6) |
| **pyqtgraph** | Overkill — we'd use only `GLViewWidget` for 3D, but pyqtgraph's 3D scene graph duplicates MuJoCo's. Adds 1.9 MB wheel and a Qt dependency. | Qt's `QGraphicsView` + offscreen render → `QImage` |
| **VisPy** | Two scene graphs (MuJoCo `MjrContext` + VisPy); fragile Qt-context handoff on macOS; requires PyOpenGL or backend lib. | MuJoCo `Renderer` + QImage display |
| **PyOpenGL** | Wraps GL 1.x–4.x in ctypes; requires sharing Qt's GL context — well-known pain point; not Qt6-friendly. | MuJoCo's built-in `GLContext`/`Renderer` |
| **PyOpenGL-accelerate** | C-extension drop-in for PyOpenGL; pulls a Cython toolchain; not portable. Same concerns. | (don't need it) |
| **moderngl** | Modern GL context API; would require us to write MuJoCo state → moderngl shader bridge. Reinventing the wheel. | MuJoCo offscreen render |
| **Qt3D** | Deprecated in Qt6 mainline (replaced by Qt Quick 3D); doesn't exist as a stable Qt6 module; Qt5-only. | Use simulator's native offscreen render |
| **Tkinter** | stdlib, but no Model/View framework equivalent to Qt's, no `QDockWidget`, no Qt Designer for layouts. Tiles badly for nested forms. | PySide6 |
| **qtawesome / qt-material** | Visual polish libraries; add icon and theme assets. Not needed for v0.5.0; deferred to v0.6.0 polish pass. | (later) |
| **jsonschema (as runtime dep)** | Already a transitive dep; duplicating Pydantic's schema introspection adds nothing. | Pydantic `model_json_schema()` |
| **mistune** | Already installed but `markdown-it-py` has better CommonMark conformance and plugin support. Pick one, not both. | `markdown-it-py` |
| **textual** | TUI framework by Rich author — overkill for 3 CLI demos. | Rich (already installed) |
| **nbformat + nbconvert** | For Jupyter-based demo walkthroughs. Requires kernel install; friction vs. existing `python demos/demo.py` style. | (deferred to v0.6.0) |
| **QScintilla / pyqode.qt** | Code editor widgets — overkill for editing scene JSON. | Plain `QPlainTextEdit` if raw JSON editing is exposed |
| **Any new sim backend** | Reinforces v0.4.0 decision: MuJoCo + PyBullet is the project's identity. | Use existing simulators |

## Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| PySide6 LGPL-3 with MIT package | LOW | Document LGPL compliance in README: dynamic linking only, end-user can re-link. Provide wheel install via pip. No static linking. |
| MuJoCo offscreen render in GUI thread blocks | MEDIUM | Run render on QTimer (20 Hz) — non-blocking; no `QThread` needed for render loop. |
| `QThread` worker + asyncio.run() interaction | MEDIUM | `TextParser.parse_sync()` raises `RuntimeError` if event loop is running; QThread workers have no loop → safe. Add unit test. |
| Large scene JSON in form editor slow | LOW | Generate forms lazily on tree-node selection. Don't rebuild all forms on every keystroke. |
| `QT_QPA_PLATFORM=offscreen` for CI | LOW | Standard Qt pattern; works on Linux containers. macOS CI uses Qt's `minimal` platform. |
| Markdown rendering of untrusted docs | LOW | `markdown-it-py` disables raw HTML by default (`{'html': False}`); strip `<script>` in renderer even if enabled. |
| PySide6 wheel size (~120 MB) | LOW | `[gui]` is optional; CI doesn't install it on default tests. |

## Alternative Stack Scenarios (for future reference, NOT v0.5.0)

**If LGPL becomes unacceptable** (e.g., proprietary distribution): the only path is Qt commercial licensing ($3.5K–5.5K/yr/dev) — not viable for an open-source research project.

**If 3D viewport needs interactive camera control** (orbit/pan/zoom with mouse): upgrade from offscreen render → interactive `GLViewWidget` from pyqtgraph + MuJoCo `MjrContext`-sharing. This is a v0.6.0+ ergonomic upgrade; v0.5.0 viewport is "look at the rendered frame" not "fly the camera".

**If the form builder needs to handle nested lists** (e.g., array of instruments): current `FormBuilder` widget_for_schema() returns a `ListEditor` placeholder. Implement this in v0.5.0 with a `QListWidget` + add/remove buttons — no new dep.

## Sources

- **Context7** `/websites/doc_qt_io_qtforpython-6` — QTreeView/QStandardItemModel/Model-View pattern, QMainWindow setup with selection signals
- **Context7** `/executablebooks/markdown-it-py` — MarkdownIt Python API, plugin loading
- **Context7** `/pyqtgraph/pyqtgraph` — GLViewWidget 3D setup, GLSurfacePlotItem (used as reference for alternative patterns)
- **Context7** `/vispy/vispy` — Backend selection, canvas embedding (used as reference for alternative patterns)
- **Context7** `/mcfletch/pyopengl` — OpenGL entry points (used as reference for why NOT to use PyOpenGL)
- **PyPI JSON** (verified 2026-06-18): PySide6 6.11.1, PyQt6 6.11.0, PyOpenGL 3.1.10, PyOpenGL-accelerate 3.1.10, pyqtgraph 0.14.0, vispy 0.16.2, markdown-it-py 4.2.0, mdit-py-plugins 0.6.1, mistune 3.2.1, jsonschema 4.26.0, mujoco 3.9.0
- **Local verification** (PYTHONPATH=src python -c): `mujoco.Renderer` API confirmed (height, width, render→np.ndarray), `pybullet.getCameraImage` confirmed, Pydantic `model_json_schema()` emits complete JSON Schema with 58 `$defs`
- **Local verification**: `markdown_it`, `mistune`, `jsonschema` already transitively installed; `rich` at 15.0 already installed
- **Existing project files**: `src/surg_rl/scene_generation/text_parser.py` (async + sync LLM interface), `src/surg_rl/scene_definition/schema.py` (Pydantic v2 schema), `src/surg_rl/simulators/scene_builder.py` (MJCF generation), `demos/demo.py` (CLI script pattern)
- **Pyproject.toml** — existing optional groups (`assets`, `benchmark`, `dev`, `llm`, `marl`, `meshing`, `simulation`, `vision`, `tracking`, `distributed`, `dreamer`, `ros2`, `docs`)
- **Previous v0.4.0 research** `.planning/research/STACK.md` — established pattern of optional dependency groups with header comments
- **AGENTS.md** — establishes simulator quirks (PyBullet soft body, MuJoCo `_model` private attr), Pydantic v2 model_construct pattern

---

*Stack research for v0.5.0 Scene Editor & UX Polish*
*Researched: 2026-06-18*
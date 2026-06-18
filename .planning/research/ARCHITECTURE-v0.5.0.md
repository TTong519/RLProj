# Architecture Research: v0.5.0 — Scene Editor & UX Polish

**Domain:** Surgical-robotics RL training system — Qt GUI editor + demos + docs + tech debt
**Researched:** 2026-06-18
**Confidence:** HIGH (architecture follows existing v0.4.0 patterns; PySide6 offscreen rendering pattern verified against mujoco.Renderer and pybullet.getCameraImage public APIs)

## Executive Summary

v0.5.0 adds a **PySide6 GUI scene editor** (3D viewport + tree/form editor + LLM-prompt-to-JSON), three polished surgical task demos (suturing + knot-tying + needle-passing), user-facing docs refresh, and interleaved tech-debt cleanup. The architectural challenge is that **Qt and headless CI must coexist** — the GUI must be fully optional (`[gui]` extra), must use `QT_QPA_PLATFORM=offscreen` in tests/CI, and must degrade gracefully when PySide6 is missing (CLI prints "install `surg-rl[gui]` to use this command" rather than crash).

The solution reuses existing v0.4.0 patterns: a thin adapter layer (`editor/`) on top of the existing `scene_definition/schema.py` Pydantic v2 source-of-truth, a `SchemaWalker` that bridges `model_json_schema()` → Qt widget tree, and a `SimRenderBridge` that wraps `mujoco.Renderer` (GLContext) and `pybullet.getCameraImage` to produce NumPy frames for a tiny `QWidget`. The 3D viewport is **not** a third-party OpenGL widget — it is a QImage-rendered-to-QWidget pattern, the same choice rl-baselines3-zoo uses. The schema walker is **pure-Python** and lives in `editor/schema_walker.py` so it is reusable for non-GUI contexts (e.g., a future CLI `--inspect` dump).

The marquee integration points are: (1) new `src/surg_rl/editor/` package with strict optional-import guard, (2) `SchemaWalker` (also used by future `surg-rl inspect` subcommand), (3) `SimRenderBridge` as a small (~30 LOC) per-simulator render-to-numpy adapter, (4) `surg-rl edit` CLI subcommand that lazy-imports editor, (5) `demos/_common.py` extraction, and (6) `tests/gui/` directory with offscreen Qt pytest fixture. Build order: tech-debt foundation → demo polish → editor → docs → advanced tech debt (5 phases as planned).

## System Overview — v0.5.0 Target State

```
                           ┌──────────────────────────────────────┐
                           │            CLI Layer                  │
                           │  surg-rl edit  [NEW]                 │
                           │  surg-rl inspect [NEW, --json-schema] │
                           │  surg-rl train/eval/benchmark/...     │
                           │  + existing 14 subcommands           │
                           └──────────────┬───────────────────────┘
                                          │
        ┌──────────┬───────────────────────┼──────────────┬────────────────┐
        ▼          ▼                       ▼              ▼                ▼
┌────────────┐ ┌────────────┐   ┌──────────────────┐ ┌─────────────┐ ┌──────────────┐
│  editor/   │ │  demos/    │   │ scene_generation │ │scene_       │ │ simulators/  │
│  (NEW)     │ │  (REFACTOR)│   │  (text_parser)   │ │definition/  │ │ (render hook)│
│            │ │            │   │  (vision_parser) │ │             │ │              │
│ MainWindow │ │ _common.py │   │  (LLM-prompt-    │ │ schema.py   │ │ SimRender    │
│ Viewport   │ │ banner.py  │   │   to-JSON via    │ │ loader.py   │ │  Bridge      │
│ TreeView   │ │ (3 demos)  │   │   existing APIs) │ │ (UNCHANGED) │ │ (NEW, ~30   │
│ FormView   │ │            │   │                  │ │             │ │  LOC/backend)│
│ LLMPanel   │ │            │   │                  │ │             │ │              │
│ SchemaWalk │ │            │   │                  │ │             │ │              │
│  (NEW,     │ │            │   │                  │ │             │ │              │
│   reusable)│ │            │   │                  │ │             │ │              │
│ UndoRedo   │ │            │   │                  │ │             │ │              │
│ ThreadMgr  │ │            │   │                  │ │             │ │              │
└──────┬─────┘ └──────┬─────┘   └────────┬─────────┘ └──────┬──────┘ └──────┬───────┘
       │              │                  │                  │               │
       └──────────────┴──────────────────┴──────────────────┴───────────────┘
                                          │
                                          ▼
                              ┌──────────────────────┐
                              │   BaseSimulator ABC  │
                              │   (load_scene,       │
                              │    reset, step,      │
                              │    render,           │
                              │    apply_action)     │
                              │   + SimRenderBridge  │
                              │     extension point  │
                              └──────────────────────┘
```

## Component Responsibilities (NEW + MODIFIED)

| Component | Responsibility | Status | Location |
|-----------|----------------|--------|----------|
| `editor/` | New Qt GUI package; MainWindow, Viewport, TreeView, FormView, LLMPanel, UndoRedo, ThreadMgr | **NEW** | `src/surg_rl/editor/` |
| `editor/main_window.py` | Top-level QMainWindow, menu bar, status bar, central widget layout (QSplitter) | **NEW** | `src/surg_rl/editor/` |
| `editor/viewport.py` | QWidget subclass that polls QImage from render bridge on a QTimer | **NEW** | `src/surg_rl/editor/` |
| `editor/tree_view.py` | QTreeView with custom model; mirrors SceneDefinition top-level fields (robots, tissues, instruments, …) | **NEW** | `src/surg_rl/editor/` |
| `editor/form_view.py` | SchemaWalker-driven QFormLayout for the selected node | **NEW** | `src/surg_rl/editor/` |
| `editor/llm_panel.py` | Text input + provider selector; calls existing `TextParser` from `scene_generation/` | **NEW** | `src/surg_rl/editor/` |
| `editor/schema_walker.py` | Pure-Python walker: `SceneDefinition.model_json_schema()` → abstract widget tree (reusable for non-GUI) | **NEW** | `src/surg_rl/editor/` |
| `editor/render_bridge.py` | Adapter wrapping MuJoCo `mujoco.Renderer` and PyBullet `getCameraImage` to produce NumPy RGB frames | **NEW** | `src/surg_rl/editor/` (small) or `simulators/` (preferred — see Pattern 1) |
| `editor/undo_redo.py` | QUndoStack adapter for SceneDefinition mutations | **NEW** | `src/surg_rl/editor/` |
| `editor/thread_manager.py` | QThread-based background workers (LLM call, render frame, file load) with signal/slot safety | **NEW** | `src/surg_rl/editor/` |
| `editor/__main__.py` | `python -m surg_rl.editor` entry; allows editor launch without editable install | **NEW** | `src/surg_rl/editor/` |
| `demos/_common.py` | Shared helpers: scene info printer, Rich banner template, scene discovery, output paths | **NEW (extract)** | `demos/_common.py` |
| `demos/suturing_demo.py` | Suturing task walkthrough (already 1168-test clean from `quick/20260617-demo-rework`) | **REFACTOR** | `demos/` |
| `demos/knot_tying_demo.py` | New knot-tying task walkthrough | **NEW** | `demos/` |
| `demos/needle_passing_demo.py` | New needle-passing task walkthrough | **NEW** | `demos/` |
| `demos/benchmark.py` | Existing benchmark demo | **UNTOUCHED** | `demos/` |
| `demos/train_demo.py` | Existing train demo | **UNTOUCHED** | `demos/` |
| `demos/eval_demo.py` | Existing eval demo | **UNTOUCHED** | `demos/` |
| `simulators/render_bridge.py` (or `editor/render_bridge.py`) | Tiny per-backend render-to-numpy adapters — see Pattern 1 | **NEW** | discussed below |
| `cli.py` | New `edit` subcommand; new `inspect --json-schema` flag | **MODIFIED** | `src/surg_rl/cli.py` |
| `tests/gui/` | New test directory for GUI smoke tests | **NEW** | `tests/gui/` |
| `tests/gui/conftest.py` | Pytest fixture setting `QT_QPA_PLATFORM=offscreen` | **NEW** | `tests/gui/` |
| `tests/gui/test_editor_smoke.py` | Open/close editor; schema walker round-trip; render bridge produces frame | **NEW** | `tests/gui/` |
| `tests/test_demos.py` | Regression test per demo (suturing, knot-tying, needle-passing) | **NEW** | `tests/` |
| `tests/dreamer/test_dreamer_lint.py` | Ruff-clean smoke test ensuring 421 ruff issues are gone | **NEW** | `tests/dreamer/` |
| `tests/test_base_simulator_fluid_hook.py` | Unit test for new `step_fluid()` hook on BaseSimulator | **NEW** | `tests/` |
| `tests/test_cutting_cooldown.py` | Unit test for the 500ms cut cooldown already documented in D-15 | **NEW** | `tests/` |
| `pyproject.toml` | New `[gui]` extra: `PySide6>=6.8.0,<7.0`, `markdown-it-py>=3.0.0` | **MODIFIED** | `pyproject.toml` |
| `Dockerfile.ros2` | Replace `amd64` hardcode with `TARGETARCH` | **MODIFIED** | `Dockerfile.ros2` |
| `docs/README.md`, `docs/CONTRIBUTING.md`, `docs/CHANGELOG.md` | User-facing docs refresh with screenshots/GIFs and demo transcripts | **MODIFIED** | `docs/` |
| `src/surg_rl/dreamer/` | Ruff cleanup: 421 F841/B904/E402 issues | **MODIFIED** | `src/surg_rl/dreamer/` |
| `src/surg_rl/simulators/base_simulator.py` | New `step_fluid()` default no-op + `apply_fluid` flag plumbing | **MODIFIED** | `src/surg_rl/simulators/base_simulator.py` |
| `src/surg_rl/fluids/` | PhiFlow multi-obstacle union() workaround (merged SDF) | **MODIFIED** | `src/surg_rl/fluids/` |

## Recommended Project Structure

```
src/surg_rl/
├── editor/                         # NEW — PySide6 GUI scene editor
│   ├── __init__.py                 # Lazy import of PySide6; HAS_GUI sentinel
│   ├── __main__.py                 # python -m surg_rl.editor entrypoint
│   ├── main_window.py              # QMainWindow, menu bar, QSplitter layout
│   ├── viewport.py                 # QWidget; polls QImage from RenderBridge
│   ├── tree_view.py                # QTreeView + custom model
│   ├── form_view.py                # QFormLayout driven by SchemaWalker
│   ├── llm_panel.py                # Text input → scene_generation.TextParser
│   ├── schema_walker.py            # PURE Python: model_json_schema() → tree
│   ├── render_bridge.py            # QObject adapter wrapping SimRenderBridge
│   ├── undo_redo.py                # QUndoStack + SceneDefinition commands
│   ├── thread_manager.py           # QThread worker base + concrete workers
│   ├── scene_model.py              # QAbstractItemModel for SceneDefinition
│   └── widgets/                    # Reusable custom widgets (enum combo, vec3)
│       ├── __init__.py
│       ├── enum_combo.py
│       ├── vec3_spinner.py
│       └── array_field.py
├── simulators/
│   ├── base_simulator.py           # MODIFIED: +step_fluid() default no-op
│   ├── mujoco_simulator.py         # UNCHANGED (render_bridge lives in editor)
│   ├── pybullet_simulator.py       # UNCHANGED
│   └── scene_builder.py            # UNCHANGED
├── scene_definition/
│   ├── schema.py                   # UNCHANGED — source of truth
│   └── loader.py                   # UNCHANGED
├── scene_generation/               # UNCHANGED — LLMPanel calls TextParser
│   ├── text_parser.py
│   └── ...
├── cli.py                          # MODIFIED: +edit subcommand, +inspect --json-schema
└── ...

demos/                              # MODIFIED
├── _common.py                      # NEW: shared banner, scene info, paths
├── suturing_demo.py                # REFACTORED: imports from _common
├── knot_tying_demo.py              # NEW
├── needle_passing_demo.py          # NEW
├── benchmark.py                    # UNCHANGED
├── train_demo.py                   # UNCHANGED
├── eval_demo.py                    # UNCHANGED
└── README.md                       # MODIFIED: walkthrough sections

tests/
├── gui/                            # NEW
│   ├── __init__.py
│   ├── conftest.py                 # QT_QPA_PLATFORM=offscreen fixture
│   ├── test_editor_smoke.py        # Open/close, walk scene, render frame
│   ├── test_schema_walker.py       # Pure-Python walker unit tests
│   ├── test_undo_redo.py           # QUndoStack integration
│   └── test_llm_panel.py           # Mocked TextParser integration
├── test_demos.py                   # NEW: per-demo regression tests
├── test_base_simulator_fluid_hook.py  # NEW
├── test_cutting_cooldown.py        # NEW
├── dreamer/
│   └── test_dreamer_lint.py        # NEW: ruff-clean assertion
└── ... (existing tests UNCHANGED)

docs/
├── README.md                       # MODIFIED: screenshots, demo walkthroughs
├── CONTRIBUTING.md                 # MODIFIED: dev setup, [gui] extra
└── CHANGELOG.md                    # MODIFIED: v0.5.0 entry
```

### Structure Rationale

- **`editor/` as a top-level package** — mirrors existing top-level packages (`scene_definition/`, `scene_generation/`, `simulators/`, `rl/`, `dynamics/`, `dreamer/`, `marl/`, `assets/`, `ros2/`, `fluids/`, `cutting/`, `benchmark/`). The `editor/` package follows the same lazy-import convention (`__init__.py` exposes `HAS_GUI` sentinel) so the rest of the codebase does not pay a PySide6 import cost.
- **`demos/_common.py` is a NEW file, not a `demos/utils.py` package** — mirrors existing flat layout (`_omp_compat.py`, `_platform_guard.py`). Underscore prefix signals "internal to demos, not a public demo".
- **`tests/gui/` mirrors `tests/dreamer/`** — feature-specific directory; keeps cross-cutting `tests/test_*.py` files (e.g., `test_simulators.py`) clean.
- **`render_bridge.py` lives in `editor/`, NOT in `simulators/`** — the render bridge is a Qt-aware adapter; it imports QObject. Putting Qt in `simulators/` would force PySide6 to be a hard dep of the simulators module, breaking the optional-install guarantee. The per-backend `*_render_to_numpy()` methods are added to each simulator subclass (only a few lines each, ~30 LOC) and the bridge is just a thin Qt wrapper.

## Architectural Patterns

### Pattern 1: Optional-Dependency Adapter (PySide6)

**What:** Mirror the existing `LazyImport` pattern used by `ros2`, `dreamer`, `marl`, `benchmark`, `tracking`. The `editor/` package's `__init__.py` exposes a `HAS_GUI` sentinel; consumers do `if not HAS_GUI: raise ImportError(...)`. CLI subcommand does a top-level `LazyImport` so `surg-rl train` never triggers PySide6 import.

**When to use:** Any optional UI dependency. The pattern is already proven in 7 places in the codebase (see `LazyImport` calls in `cli.py:27`, `scene_generation/__init__.py`, `dreamer/__init__.py`).

**Trade-offs:**
- **Pro:** Existing `LazyImport` infrastructure reused; zero new dep for headless CI; `pip install surg-rl[gui]` is the only way PySide6 enters the environment.
- **Pro:** macOS test runs without DISPLAY still work; CI uses `QT_QPA_PLATFORM=offscreen`.
- **Con:** Editor code must defend every PySide6 symbol with `try/except ImportError` at import time; type checking is weaker for editor code.

**Example:**
```python
# src/surg_rl/editor/__init__.py
from surg_rl.utils.lazy_imports import LazyImport

# Lazy import to avoid forcing PySide6 on headless installs
QtWidgets = LazyImport("PySide6.QtWidgets", "gui")
QtCore = LazyImport("PySide6.QtCore", "gui")
QtGui = LazyImport("PySide6.QtGui", "gui")

HAS_GUI = QtWidgets.available

if HAS_GUI:
    from surg_rl.editor.main_window import MainWindow  # imports PySide6

__all__ = ["HAS_GUI", "MainWindow"]
```

### Pattern 2: Schema-Driven Form Generation (JSON Schema → Qt)

**What:** `SceneDefinition.model_json_schema()` (Pydantic v2) produces a full JSON Schema with `$defs`. A pure-Python `SchemaWalker` recursively walks this and emits an abstract widget tree (`WidgetSpec` nodes). The form view then instantiates Qt widgets from the spec. This is the Blender/Godot inspector pattern.

**When to use:** Any time you need to expose a Pydantic schema for editing without writing per-field boilerplate. The walker is **reusable for non-GUI contexts** — a future `surg-rl inspect --json-schema` CLI can use the same walker to produce a markdown table summary.

**Trade-offs:**
- **Pro:** Adding a new field to `SceneDefinition` automatically appears in the form. Zero per-field maintenance.
- **Pro:** Walker is testable in pure Python (no Qt) — see `tests/gui/test_schema_walker.py`.
- **Con:** Custom widget per field type (`Vec3`, `Quaternion`, `Optional[Enum]`) needs a small registry; new field types need walker extension.
- **Con:** Conditional fields (`if X then Y is required`) require Pydantic v2 schema-level support; we punt on v0.5.0 (manual config via right-click context menu).

**Example:**
```python
# src/surg_rl/editor/schema_walker.py
from dataclasses import dataclass, field
from typing import Any

@dataclass
class WidgetSpec:
    """Abstract widget description produced by SchemaWalker."""
    field_name: str
    field_type: str  # "string" | "number" | "integer" | "enum" | "vec3" | "object" | "list"
    label: str
    default: Any = None
    enum_values: list[str] = field(default_factory=list)
    children: list["WidgetSpec"] = field(default_factory=list)
    description: str = ""
    bounds: tuple[float | None, float | None] = (None, None)

class SchemaWalker:
    """Walk a Pydantic v2 model JSON Schema → list of WidgetSpec.

    Reusable for GUI (form rendering) and CLI (markdown table).
    """

    def __init__(self, schema: dict[str, Any], model_cls: type | None = None):
        self.schema = schema
        self.model_cls = model_cls
        self._defs = schema.get("$defs", {})

    def walk(self, root_name: str = "root") -> list[WidgetSpec]:
        """Walk the root schema and return a flat list of WidgetSpec nodes."""
        ...

    def _resolve_ref(self, ref: str) -> dict[str, Any]:
        """Resolve a $ref to the actual $defs entry."""
        ...

    def _walk_object(self, prop_schema: dict, prop_name: str) -> WidgetSpec:
        spec = WidgetSpec(field_name=prop_name, field_type="object", ...)
        for child_name, child_schema in prop_schema["properties"].items():
            spec.children.append(self._walk_field(child_schema, child_name))
        return spec

    def _walk_field(self, schema: dict, name: str) -> WidgetSpec:
        if "enum" in schema:
            return WidgetSpec(field_type="enum", enum_values=schema["enum"], ...)
        if schema.get("type") == "number":
            return WidgetSpec(field_type="number", bounds=..., default=schema.get("default"))
        # ... etc
```

### Pattern 3: Offscreen Render-to-Numpy Bridge

**What:** MuJoCo's `mujoco.Renderer(model, height=h, width=w)` (added in MuJoCo 3.0) creates an offscreen GL context and produces RGB frames as NumPy arrays via `renderer.render()`. PyBullet's `pybullet.getCameraImage(w, h, viewMatrix, projectionMatrix)` returns an RGB array directly. The render bridge wraps these into a uniform `render_frame() -> np.ndarray` interface.

**Why not a real OpenGL widget?** Embedding MuJoCo's or PyBullet's native viewer in Qt requires the same process's OpenGL context, which conflicts with Qt's own. The offscreen-to-QImage pattern is what rl-baselines3-zoo uses; it's simpler, has no context conflict, and works headless.

**When to use:** Any case where you want a live 3D view without driving a native simulator viewer.

**Trade-offs:**
- **Pro:** No OpenGL context contention; same code path works with `QT_QPA_PLATFORM=offscreen` for tests; render is decoupled from QWidget paint events.
- **Pro:** MuJoCo's `mujoco.Renderer` is the official 3.x path — no deprecated APIs.
- **Con:** Frames are copied GPU→CPU→GPU (NumPy → QImage upload) each tick. At 30 FPS with 640×480 this is ~27 MB/s; negligible.
- **Con:** User cannot interact with the 3D scene (orbit/pan/zoom) — that's a v0.6.0+ feature (would require VisPy or a Qt OpenGL widget).

**Per-backend implementation (~30 LOC each):**

```python
# src/surg_rl/simulators/mujoco_simulator.py — ADD this method
def render_to_numpy(self, width: int = 640, height: int = 480,
                    camera_name: str | None = None) -> np.ndarray | None:
    """Offscreen render via mujoco.Renderer. Returns RGB uint8 (H, W, 3).

    Lazily creates a Renderer; safe to call repeatedly.
    """
    if self._model is None:
        return None
    if not hasattr(self, "_offscreen_renderer") or self._offscreen_renderer is None:
        import mujoco
        self._offscreen_renderer = mujoco.Renderer(self._model, height=height, width=width)
    self._offscreen_renderer.update_scene(self._data, camera=camera_name or -1)
    return self._offscreen_renderer.render()  # (H, W, 3) uint8
```

```python
# src/surg_rl/simulators/pybullet_simulator.py — ADD this method
def render_to_numpy(self, width: int = 640, height: int = 480,
                    camera_name: str | None = None) -> np.ndarray | None:
    """Offscreen render via pybullet.getCameraImage. Returns RGB uint8 (H, W, 3)."""
    if self._physics_client is None:
        return None
    import pybullet as p
    w, h = width, height
    view = p.computeViewMatrixFromYawPitchRoll(
        cameraTargetPosition=[0, 0, 0], distance=1.0,
        yaw=45, pitch=-30, roll=0, upAxisIndex=2,
    )
    proj = p.computeProjectionMatrixFOV(fov=60.0, aspect=w / h,
                                         nearVal=0.01, farVal=100.0)
    _, _, rgb, _, _ = p.getCameraImage(w, h, view, proj,
                                        physicsClientId=self._physics_client)
    rgb = np.asarray(rgb, dtype=np.uint8).reshape(h, w, 4)[:, :, :3]  # drop alpha
    return rgb
```

The base class declares a `NotImplementedError` default; concrete subclasses add the method. The editor's `RenderBridge` (a QObject) wraps whichever simulator is loaded.

```python
# src/surg_rl/editor/render_bridge.py
from PySide6.QtCore import QObject, Signal
import numpy as np

class RenderBridge(QObject):
    """QObject wrapper around simulator.render_to_numpy(). Emits QImage on a QTimer."""
    frame_ready = Signal(object)  # QImage

    def __init__(self, simulator, fps: float = 30.0):
        super().__init__()
        self._sim = simulator
        from PySide6.QtCore import QTimer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._grab)
        self._timer.start(int(1000.0 / fps))

    def _grab(self):
        rgb = self._sim.render_to_numpy()
        if rgb is None:
            return
        h, w, _ = rgb.shape
        from PySide6.QtGui import QImage
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888).copy()
        self.frame_ready.emit(qimg)
```

### Pattern 4: QThread Workers for LLM/Render/IO

**What:** Long-running operations (LLM prompt parsing, scene file load, render frame fetch) must NOT block the Qt event loop. The pattern is `QObject` worker + `QThread.moveToThread()` + Signal/Slot. The worker emits progress and finished signals.

**When to use:** Any operation that takes >100ms in the GUI thread.

**Trade-offs:**
- **Pro:** Editor remains responsive during slow LLM calls (Ollama can take 5–30s).
- **Pro:** Standard Qt pattern, well-documented.
- **Con:** QObject ownership across threads requires care; signal/slot queued connections are mandatory.

**Example (sketch only):**
```python
class LLMPanelWorker(QObject):
    finished = Signal(object)  # SceneDefinition
    error = Signal(str)

    def __init__(self, text: str, provider: str, model: str):
        super().__init__()
        self._text, self._provider, self._model = text, provider, model

    @Slot()
    def run(self):
        try:
            from surg_rl.scene_generation import TextParser
            parser = TextParser(provider=self._provider, model=self._model)
            scene = asyncio.run(parser.parse(self._text))  # asyncio loop
            self.finished.emit(scene)
        except Exception as e:
            self.error.emit(str(e))
```

### Pattern 5: Pydantic-Aware Undo/Redo

**What:** A `QUndoStack` whose commands know how to apply/revert mutations to a `SceneDefinition`. Each command is a `dataclass` capturing the field path (e.g., `("tissues", 0, "stiffness")`), the old value, and the new value. Replay produces a fresh `SceneDefinition` from the original via `model_copy(deep=True)`.

**When to use:** Any editor where mutations are complex and reversible.

**Trade-offs:**
- **Pro:** Standard Qt pattern (`QUndoCommand`).
- **Pro:** Field-path addressing works for nested Pydantic v2 models without serialization.
- **Con:** `QUndoStack` lives in QtWidgets; tests require `QT_QPA_PLATFORM=offscreen`.

### Pattern 6: Demo Banner + Scene Info Helper (existing pattern, refactored)

**What:** All three demos share a `print_banner(task_name, scene_name, simulator, ...)` helper and a `print_scene_info(scene)` helper. Extract these into `demos/_common.py`. The `suturing_demo.py` already follows this pattern from `quick/20260617-demo-rework`; `knot_tying_demo.py` and `needle_passing_demo.py` import from `_common`.

**When to use:** Whenever 3+ demos share boilerplate. Mirrors the existing `demos/_platform_guard.py` and `demos/_omp_compat.py` pattern.

**Trade-offs:**
- **Pro:** Consistent UX across demos; reduces duplication.
- **Con:** Slight coupling — changing the banner template requires updating all demos. Acceptable for 3 demos.

## Data Flow

### Editor — User Opens Scene

```
User picks File→Open
    ↓
[main_window.py] QFileDialog → Path
    ↓
[LoadSceneWorker (QThread)] SceneLoader.load_json(path)
    ↓
[scene_model.py] TreeModel wraps SceneDefinition
    ↓
[tree_view.py] populates QTreeView
    ↓
[form_view.py] SchemaWalker.walk(scene) → WidgetSpec tree → QFormLayout
    ↓
User edits field
    ↓
[form_view.py] QUndoCommand (field_path, old_val, new_val)
    ↓
[undo_redo.py] QUndoStack.push(cmd) → updates scene_model → repaints tree + form
    ↓
User picks File→Save
    ↓
[main_window.py] SceneDefinition.model_dump(mode="json") → json.dumps → file
```

### Editor — LLM Prompt to JSON

```
User types "two forceps grasp a needle" in LLMPanel
    ↓
[llm_panel.py] emits request_run(prompt, provider, model)
    ↓
[thread_manager.py] spawns QThread + LLMPanelWorker
    ↓
[worker] TextParser(provider, model).parse(prompt)  ← asyncio.run
    ↓ (5–30s later)
[worker] emits finished(scene: SceneDefinition)
    ↓ (queued signal across threads)
[main_window.py] accepts scene, calls set_scene(scene)
    ↓
[scene_model.py] reset to new model; tree + form rebuild
    ↓ (parallel)
[RenderBridge] loads scene into simulator, starts QTimer 30 FPS
    ↓
[viewport.py] frame_ready signal → repaint QWidget
```

### Editor — Live Viewport

```
QTimer(33ms) timeout
    ↓
[RenderBridge._grab] simulator.render_to_numpy() (H, W, 3) uint8
    ↓
QImage(rgb.data, w, h, w*3, Format_RGB888).copy()
    ↓
frame_ready.emit(qimg)  ← queued signal (same thread, but defensive)
    ↓
[viewport.py] paintEvent → qimg scaled → draw on QPainter
```

### Editor — Threading Topology

```
Main (GUI) thread
├── MainWindow event loop
│   ├── TreeView selectionChanged → FormView rebuild
│   ├── FormView field changed → QUndoStack.push → scene_model mutation
│   ├── Menu bar actions
│   └── RenderBridge QTimer (33ms tick → render_to_numpy is fast ~5ms)
│
QThread: LoadSceneWorker
└── runs SceneLoader.load_json() → emits finished(scene)

QThread: LLMPanelWorker (one at a time, gated by QMutex)
└── runs asyncio.run(TextParser().parse(prompt)) → emits finished(scene)
```

**Critical rule:** Render-to-numpy is fast (<10ms) and runs on the GUI thread inside a QTimer callback. LLM and file I/O are slow and run on QThreads. The simulator's GL context (MuJoCo `Renderer` or PyBullet's offscreen framebuffer) is created lazily on the GUI thread and reused — never move it across threads.

## Key Integration Points

### Integration Point 1: New `src/surg_rl/editor/` Package

**Hook into:** Nothing — the editor is a leaf consumer. It depends on:
- `scene_definition/schema.py` (Pydantic v2 models)
- `scene_definition/loader.py` (load/save)
- `scene_generation/text_parser.py` (LLM panel)
- `simulators/mujoco_simulator.py` + `pybullet_simulator.py` (render bridge)
- `utils/lazy_imports.py` (LazyImport)

**Why leaf:** Editor does not own state that the rest of the codebase reads. The single direction is editor → everything else. RL training never touches the editor.

### Integration Point 2: Schema Walker Lives in `editor/schema_walker.py`

**Reusability:** The walker operates on a `dict` (the JSON Schema) and emits `WidgetSpec` dataclasses. It does NOT import PySide6. Therefore it can be tested in pure Python (`tests/gui/test_schema_walker.py` without `QT_QPA_PLATFORM=offscreen`) and reused by:
- A future `surg-rl inspect --json-schema` CLI subcommand that prints a markdown table
- A future `demos/_scene_info.py` helper that prints structured scene info
- A potential web UI (FastAPI + JSON widgets) using the same walker

**Why a single location:** Avoids the trap of "we have three schema walkers in three packages that disagree". One walker, many consumers.

### Integration Point 3: Per-Simulator `render_to_numpy()` Methods

**Modified components:** `simulators/mujoco_simulator.py` and `simulators/pybullet_simulator.py` each gain one ~30 LOC method. `simulators/base_simulator.py` gains a `render_to_numpy()` abstract method declaration with a `NotImplementedError` default in the body (or, more pragmatically, a `raise NotImplementedError` so subclasses must implement it before the editor can use them).

**Why on the simulator, not the editor:** The render method is intrinsically tied to the simulator's GL context. Putting it on the simulator keeps the contract clean and means RL training code can also call `sim.render_to_numpy()` (e.g., for headless video recording — useful future feature).

### Integration Point 4: CLI Subcommand `surg-rl edit`

**Hook into:** `cli.py` adds:

```python
@app.command()
def edit(
    scene: str | None = typer.Option(None, "--scene", "-s", help="Open scene JSON/YAML"),
    simulator: str = typer.Option("mujoco", "--simulator", help="mujoco or pybullet"),
) -> None:
    """Launch the PySide6 scene editor. Requires pip install surg-rl[gui]."""
    from surg_rl.editor import HAS_GUI
    if not HAS_GUI:
        console.print(
            "[bold red]GUI editor requires PySide6.[/bold red]\n"
            "  Install with: pip install surg-rl[gui]"
        )
        raise typer.Exit(1)
    from surg_rl.editor.main_window import MainWindow
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(scene=scene, simulator=simulator)
    window.show()
    sys.exit(app.exec())
```

The new `inspect --json-schema` subcommand uses the same SchemaWalker:

```python
@app.command(name="inspect")
def inspect(
    scene: str = typer.Option(..., "--scene", "-s", help="Scene JSON/YAML"),
    json_schema: bool = typer.Option(False, "--json-schema", help="Print Pydantic JSON Schema"),
) -> None:
    """Inspect a scene: dump summary or print Pydantic v2 JSON Schema."""
    from surg_rl.scene_definition.loader import SceneLoader
    loaded = SceneLoader.load(scene)
    if json_schema:
        # Reuse SchemaWalker from editor (lazy import)
        from surg_rl.editor.schema_walker import SchemaWalker
        walker = SchemaWalker(loaded.scene.__class__.model_json_schema())
        for spec in walker.walk():
            console.print(f"  • {spec.label} ({spec.field_type})")
        return
    # ... existing summary
```

### Integration Point 5: Test Layout — `tests/gui/`

**New directory** with:
- `conftest.py` setting `os.environ["QT_QPA_PLATFORM"] = "offscreen"` at module import
- `test_editor_smoke.py` — opens editor on a fixture scene, closes it; verifies no crash
- `test_schema_walker.py` — pure-Python walker tests (does NOT need Qt)
- `test_undo_redo.py` — QUndoStack + SceneDefinition round-trip
- `test_llm_panel.py` — mocked TextParser; verifies signal flow
- `test_render_bridge.py` — verifies `simulator.render_to_numpy()` returns correct shape

The `conftest.py` fixture pattern:

```python
# tests/gui/conftest.py
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
    app.quit()

@pytest.fixture
def sample_scene_path(tmp_path):
    """Write a minimal valid scene JSON; return path."""
    import json
    from pathlib import Path
    scene = {
        "schema_version": "1.0",
        "metadata": {"name": "test", "description": "", "author": "", "tags": []},
        "robots": [],
        "tissues": [],
        "instruments": [],
        "environment": {"gravity": [0, 0, -9.81], "timestep": 0.002, "frame_skip": 1},
        "physics": {"solver_iterations": 100, "tolerance": 1e-8, "contact_iterations": 1},
        "cameras": [],
        "lights": [],
        "task": None,
        "render": {"width": 640, "height": 480, "fps": 30},
    }
    path = Path(tmp_path) / "test_scene.json"
    path.write_text(json.dumps(scene, indent=2))
    return path
```

**Existing tests UNCHANGED.** `tests/gui/` is a peer to `tests/dreamer/`.

### Integration Point 6: CI Matrix Entry

**Hook into:** `.github/workflows/ci.yml` (or equivalent) gains a new matrix entry:

```yaml
jobs:
  test:
    strategy:
      matrix:
        include:
          - python: "3.10"
            extras: ""              # base only
          - python: "3.10"
            extras: "[gui]"
            env:
              QT_QPA_PLATFORM: offscreen
          - python: "3.11"
            extras: "[gui]"
            env:
              QT_QPA_PLATFORM: offscreen
    steps:
      - run: pip install -e ".${{ matrix.extras }}"
      - run: pytest tests/ -v
      - uses: actions/upload-artifact@v4
        if: matrix.extras == '[gui]'
        with:
          name: editor-screenshots
          path: tests/gui/screenshots/
```

**Screenshot artifact upload:** The `test_render_bridge.py` test saves the QImage as PNG to `tests/gui/screenshots/` for visual review. CI uploads them as artifacts.

### Integration Point 7: Demo Suite Refactor

**Hook into:** `demos/_common.py` (new) and the three demo scripts:

```python
# demos/_common.py
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

console = Console()

DEMOS_DIR = Path(__file__).parent
PROJECT_ROOT = DEMOS_DIR.parent
SCENES_DIR = PROJECT_ROOT / "scenes"
SAFETY_POLICY = """\
SAFETY: Research simulation only. Not for clinical use.
All tissue meshes are procedural or public-CC0 primitives.
"""

def print_banner(title: str, scene_name: str, simulator: str = "mujoco") -> None:
    """Standard demo banner: SAFETY notice + scene info."""
    console.print(Panel.fit(
        f"[bold cyan]{title}[/bold cyan]\n"
        f"[dim]Scene: {scene_name} | Simulator: {simulator}[/dim]\n\n"
        f"[yellow]{SAFETY_POLICY}[/yellow]",
        border_style="cyan",
    ))

def print_scene_info(scene) -> None:
    """Print scene summary: robots, tissues, instruments counts + task info."""
    from rich.table import Table
    table = Table(title="Scene Configuration")
    table.add_column("Component", style="cyan")
    table.add_column("Count", style="green")
    table.add_row("Robots", str(len(scene.robots)))
    table.add_row("Tissues", str(len(scene.tissues)))
    table.add_row("Instruments", str(len(scene.instruments)))
    table.add_row("Cameras", str(len(scene.cameras)))
    console.print(table)
    if scene.task:
        console.print(f"  Task: [bold]{scene.task.task_type}[/bold]")

def resolve_scene(name: str) -> Path:
    """Look up a scene by name; raise FileNotFoundError with helpful list."""
    candidates = list(SCENES_DIR.glob(f"{name}*.json")) + list(SCENES_DIR.glob(f"{name}*.yaml"))
    if not candidates:
        available = sorted(p.stem for p in SCENES_DIR.glob("*.json"))
        raise FileNotFoundError(
            f"Scene '{name}' not found in {SCENES_DIR}.\n"
            f"  Available: {', '.join(available) if available else '(none)'}"
        )
    return candidates[0]
```

Each demo imports from `_common`:
```python
# demos/knot_tying_demo.py
from demos._common import print_banner, print_scene_info, resolve_scene
```

### Integration Point 8: Tech Debt Interleaving

**Hook into:** Three categories, distributed across the 5 phases per the planned roadmap.

**Category A — Phase 1 (Tech debt foundation):**
1. **`src/surg_rl/dreamer/` ruff cleanup (421 issues)** — `ruff check --fix src/surg_rl/dreamer/`. F841 (unused variable), B904 (raise from), E402 (module-level import not at top). All mechanical.
2. **`Dockerfile.ros2` amd64 hardcode** — replace `FROM --platform=linux/amd64 ros:humble` with `FROM --platform=$TARGETARCH ros:humble`. Use `docker buildx build --platform=linux/amd64,linux/arm64 .` in CI.
3. **`base_simulator.py` fluid step hook** — add `def step_fluid(self, dt: float) -> None: pass` default no-op. MuJoCo + PyBullet subclasses override to call `PhiFlow` step. Used by the upcoming bleeding/irrigation tasks.
4. **`cutting.py` cooldown unit test** — already in D-15; create `tests/test_cutting_cooldown.py` asserting `time.time() - last_cut_time < 0.5 → cooldown active`.
5. **`fluids/` PhiFlow multi-obstacle union() workaround** — replace per-obstacle `field.stack()` with a single merged SDF using `phi.math.concat([sdf.broadcast(x) for x in obstacles], axis=-1).min()`.

**Category B — Phase 4 (Advanced tech debt):**
6. **HARD-fixture env-construction integration test** — `tests/test_difficulty_levels.py::test_hard_fixture_constructs_env` — load `tests/fixtures/scenes/suturing_difficulty_hard.json`, build `SurgicalEnv`, call `reset()`, assert no exception.
7. **K8s PVC e2e scaffolding** — set up `tests/k8s/test_pvc_e2e.py` with `[k8s]` marker; requires `kind` cluster; deferred test body.

**Category C — Deferred (out of v0.5.0 scope):**
- Organ mesh licensing research spike
- KubeRay prerequisite
- Per-tet generation counter
- 3D fluid flag (`dim_3d=True`)

## New Components vs. Modified Components

### Strictly NEW

- `src/surg_rl/editor/` (full package, ~15 files)
- `src/surg_rl/editor/__main__.py`
- `src/surg_rl/editor/widgets/` (3 custom widgets)
- `demos/_common.py`
- `demos/knot_tying_demo.py`
- `demos/needle_passing_demo.py`
- `tests/gui/` (full directory, 5 test files)
- `tests/gui/conftest.py`
- `tests/test_demos.py`
- `tests/dreamer/test_dreamer_lint.py`
- `tests/test_base_simulator_fluid_hook.py`
- `tests/test_cutting_cooldown.py`

### MODIFIED (additive, backward-compatible)

- `src/surg_rl/simulators/mujoco_simulator.py` — add `render_to_numpy()` method
- `src/surg_rl/simulators/pybullet_simulator.py` — add `render_to_numpy()` method
- `src/surg_rl/simulators/base_simulator.py` — add `render_to_numpy()` abstract method declaration (or `NotImplementedError` default)
- `src/surg_rl/cli.py` — add `edit` subcommand, `inspect --json-schema` flag
- `pyproject.toml` — add `[gui]` extra
- `Dockerfile.ros2` — replace amd64 with `$TARGETARCH`
- `docs/README.md` — screenshots, walkthroughs
- `docs/CONTRIBUTING.md` — dev setup, [gui] install
- `docs/CHANGELOG.md` — v0.5.0 entry
- `demos/suturing_demo.py` — refactor to import from `_common`
- `demos/README.md` — add walkthrough sections for knot_tying and needle_passing

### UNCHANGED (explicitly out of scope)

- `src/surg_rl/scene_definition/schema.py` — schema is the source of truth; walker reads it without modification
- `src/surg_rl/scene_definition/loader.py` — editor reuses existing `SceneLoader`
- `src/surg_rl/scene_generation/text_parser.py` — LLM panel reuses existing `TextParser`
- `src/surg_rl/rl/` (env, training, observation, action, rewards, callbacks)
- `src/surg_rl/dynamics/` (parameter_randomizer, curriculum, adaptive_difficulty)
- `src/surg_rl/dreamer/` (code); only the 421 ruff issues are addressed
- All existing test files (except where new test files are added)

## Suggested Build Order Across the 5 Phases

The user's planned order in `PROJECT.md` is sound. Here is the architecture-validated refinement:

### Phase 1: Tech Debt Foundation (small, no public API change)

**Goal:** Retire quick-win tech debt so feature work starts clean.

**Plans:**
1. **Ruff cleanup in `src/surg_rl/dreamer/`** — `ruff check --fix src/surg_rl/dreamer/`. Add `tests/dreamer/test_dreamer_lint.py` asserting `ruff check src/surg_rl/dreamer/ --quiet` returns 0.
2. **Dockerfile.ros2 `$TARGETARCH` fix** — modify Dockerfile; update CI build command to `docker buildx build --platform=linux/amd64,linux/arm64 .`.
3. **Fluid step hook in `base_simulator.py`** — add `step_fluid(dt)` default no-op + `apply_fluid` flag. MuJoCo + PyBullet subclasses get empty overrides. Add `tests/test_base_simulator_fluid_hook.py` asserting default is no-op.
4. **Cut cooldown unit test** — `tests/test_cutting_cooldown.py` asserting the 500ms cooldown (per D-15).
5. **PhiFlow multi-obstacle union() workaround** — refactor `src/surg_rl/fluids/` to use merged SDF; add regression test.

**Dependencies:** None. Pure cleanup.

**Validation:** All 1,134+ existing tests pass. New tests pass. Ruff reports 0 issues in `src/surg_rl/dreamer/`.

### Phase 2: Demo Suite Polish (medium, user-facing)

**Goal:** Three polished demos with consistent narration.

**Plans:**
1. **Extract `demos/_common.py`** — banner, scene info, scene resolver. Refactor `demos/suturing_demo.py` to use it. Add `tests/test_demos.py::test_suturing_demo_banner` to lock the pattern.
2. **Add `demos/knot_tying_demo.py`** — uses `_common`. Scene: `scenes/knot_tying.json` (already exists from Phase 27). Narration: load forceps, approach needle, grasp, tie loop, pull through.
3. **Add `demos/needle_passing_demo.py`** — uses `_common`. Scene: `scenes/needle_insertion.json` (already exists). Narration: dual-arm coordination, needle approach, insertion arc.
4. **`demos/README.md` walkthrough sections** — 3 mini-tutorials, one per demo, with `--headless` steps and expected output.
5. **Per-demo regression tests** — `tests/test_demos.py::test_{suturing,knot_tying,needle_passing}_demo_runs` — `subprocess.run(["python", "demos/X.py", "--headless", "--steps", "0"])` returns 0.

**Dependencies:** Phase 1 (clean ruff baseline). No editor work yet.

**Validation:** All demos run `--headless --steps 0` clean. Per-demo regression tests pass. Suturing demo stays 1168-test clean (no regression).

### Phase 3: PySide6 Scene Editor — Marquée (large, the big one)

**Goal:** Full GUI editor.

**Plans:**
1. **Per-simulator `render_to_numpy()` methods** — MuJoCo + PyBullet each gain ~30 LOC method. Tests: `tests/test_render_bridge.py` asserting shape (H, W, 3) uint8.
2. **`src/surg_rl/editor/` skeleton** — `__init__.py` with `HAS_GUI` sentinel, `__main__.py` entry, `main_window.py` empty QMainWindow. `pyproject.toml` `[gui]` extra added.
3. **`editor/schema_walker.py` (pure-Python)** — Walker + `WidgetSpec` dataclass. `tests/gui/test_schema_walker.py` with full coverage of object/number/string/enum/list/optional types.
4. **`editor/scene_model.py` + `tree_view.py`** — QAbstractItemModel wrapping SceneDefinition; QTreeView with columns (name, type, value).
5. **`editor/form_view.py`** — SchemaWalker → QFormLayout; widget registry mapping `WidgetSpec.field_type` to QWidget.
6. **`editor/render_bridge.py` + `viewport.py`** — QObject adapter + QWidget viewport; QTimer 30 FPS. Optional simulator lazy-load on first show.
7. **`editor/undo_redo.py`** — QUndoStack + QUndoCommand subclasses for field mutations.
8. **`editor/llm_panel.py` + `thread_manager.py`** — QThread workers for LLM call (calls existing `TextParser`).
9. **`editor/main_window.py` full integration** — QSplitter (Tree | Form | Viewport), menu bar (File→Open/Save, View→Reset, Help→About), status bar with simulator + scene info.
10. **GUI smoke test** — `tests/gui/test_editor_smoke.py` opens editor on fixture scene, calls `QTimer.singleShot(500, app.quit)`, asserts no exception.
11. **Screenshot capture** — `tests/gui/test_render_bridge.py` saves QImage as PNG to `tests/gui/screenshots/`. CI uploads as artifact.

**Dependencies:** Phase 1 (clean baseline). Phase 2 not required, but the editor will benefit from the `_common.py` resolver for scene loading.

**Validation:** Editor launches with `python -m surg_rl.editor` and `surg-rl edit --scene scenes/suturing.json`. Opens, edits a field (e.g., tissue stiffness), saves, reloads — value persists. Viewport renders frames at 30 FPS in offscreen mode.

### Phase 4: User-Facing Docs Refresh (medium)

**Goal:** README, CONTRIBUTING, CHANGELOG reflect v0.5.0.

**Plans:**
1. **`docs/README.md` rewrite** — hero shot of editor + 3 demo GIFs. Sections: "Quick Start" (CLI), "GUI Editor" (PySide6), "Demos" (3 walkthroughs), "For Researchers" (training/benchmarking), "For Developers" (CONTRIBUTING link).
2. **Capture screenshots during Phase 3** — 1 editor hero + 3 demo snapshots. Save to `docs/assets/`.
3. **`docs/CONTRIBUTING.md` overhaul** — dev setup (`pip install -e ".[dev,gui,dreamer]"`), test conventions, optional extras table, common pitfalls from PITFALLS.md.
4. **`docs/CHANGELOG.md` v0.5.0 entry** — bullet list of features + bug fixes (per Keep-a-Changelog format).
5. **Demo transcripts** — copy narration output from `demos/README.md` walkthroughs into `docs/demo-transcripts/`.

**Dependencies:** Phase 3 (editor screenshots). Phase 2 (demo transcripts).

**Validation:** README renders correctly. `surg-rl --help` mentions the new `edit` subcommand. CONTRIBUTING links resolve.

### Phase 5: Advanced Tech Debt (small)

**Goal:** Close the medium-priority deferred items.

**Plans:**
1. **HARD-fixture env-construction integration test** — `tests/test_difficulty_levels.py::test_hard_fixture_constructs_env` (per Phase 29 code review WR-02 deferred item).
2. **`CurriculumStageConfig.difficulty` normalization at env-construction** (per Phase 29 code review WR-03 deferred item) — add `.model_post_init()` or `_normalize_difficulty()` helper.
3. **K8s PVC e2e scaffolding** — `tests/k8s/test_pvc_e2e.py` with `[k8s]` marker + `kind` cluster skip. Set up directory structure; defer body.
4. **Organ mesh licensing research spike** — `docs/research/organ-mesh-licensing.md` with candidate sources (surgtoolloc, MakeHuman, BodyParts3D). Defer license decision to v0.6.0.

**Dependencies:** Phase 1 (clean baseline).

**Validation:** New HARD-fixture test passes. K8s scaffolding imports cleanly. Research spike doc written.

## Build Order Dependency Graph

```
Phase 1 (Tech Debt Foundation)         ──┐
                                         ├──► Phase 3 (Editor) ──► Phase 4 (Docs)
Phase 2 (Demo Suite Polish) ─────────────┘              │
                                                         │
Phase 5 (Advanced Tech Debt) ───────────────────────────────►  Done
```

- **Phase 1 and Phase 2 are independent.** Both can run in parallel (worktrees).
- **Phase 3 depends on Phase 1 (clean baseline) and Phase 2 (scene resolver for editor).** Editor work needs `_common.py` if it uses `resolve_scene()`.
- **Phase 4 depends on Phase 3 (screenshots) and Phase 2 (demo transcripts).**
- **Phase 5 depends on Phase 1 only.** Can run in parallel with Phases 2–4.

**Merge order during execution (per CLAUDE.md):** schema → simulators → scene_generation → editor → rl → tests. Within editor: `__init__.py` + `__main__.py` first (skeleton), then `schema_walker.py` (pure-Python, testable early), then per-simulator `render_to_numpy()` (touches existing code), then `tree_view.py` + `form_view.py` (use walker), then `render_bridge.py` + `viewport.py`, then `llm_panel.py` + `thread_manager.py`, then `main_window.py` integration, then tests.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Putting Qt Symbols at Module Top Level in `editor/`

**What people do:** `from PySide6.QtWidgets import QWidget` at the top of `editor/widgets/vec3_spinner.py`.

**Why it's wrong:** Forces PySide6 import on every `import surg_rl.editor` call. Breaks headless CLI on systems where PySide6 wheels are not installed.

**Do this instead:** Use `LazyImport` (as the rest of the codebase does) in `__init__.py`; lazily import Qt symbols inside widget class methods or via module-level `try/except ImportError` guard. Test by running `python -c "import surg_rl.editor"` on a system without PySide6 — should succeed and `HAS_GUI` should be `False`.

### Anti-Pattern 2: Custom-Built OpenGL Widget

**What people do:** Reach for `pyqtgraph.opengl.GLViewWidget` or `VisPy` to embed a real 3D scene.

**Why it's wrong:** OpenGL context contention with Qt's own context. `pyqtgraph` requires PyQt5 (license-incompatible) or PyQt6 (license question). `VisPy` requires `PyOpenGL` (fragile). Both add 50+ MB of dependencies for a feature we don't need (orbit/pan/zoom).

**Do this instead:** Offscreen render-to-numpy + QImage-to-QWidget paint. ~30 LOC per backend. Same pattern as rl-baselines3-zoo. Saves a 50 MB dep tree.

### Anti-Pattern 3: Schema Walker Imports Pydantic Models

**What people do:** `from surg_rl.scene_definition.schema import SceneDefinition` in `editor/schema_walker.py` and operate on the class directly.

**Why it's wrong:** Couples the walker to the live schema module. Tests cannot pass a synthetic dict schema. Future reuse (web UI, CLI inspect) becomes harder.

**Do this instead:** Walker takes a `dict` (the JSON Schema) and a class reference as constructor args. Walk from dict, not from class. Tests can pass synthetic schemas without importing the full schema module.

### Anti-Pattern 4: Synchronous LLM Call in Click Handler

**What people do:** When the user clicks "Generate", `LLMPanel.run()` calls `asyncio.run(TextParser().parse(prompt))` directly.

**Why it's wrong:** Blocks the GUI for 5–30s. User sees a frozen window; may think the app crashed.

**Do this instead:** QThread + QObject worker + Signal/Slot. Worker emits `finished(scene)` or `error(msg)`. GUI shows a busy spinner during the wait. The pattern is in the standard Qt docs.

### Anti-Pattern 5: Mutating `SceneDefinition` in Place

**What people do:** `scene.environment.gravity[2] = -10.0` directly on the loaded object.

**Why it's wrong:** Pydantic v2 may not detect the mutation; undo/redo cannot capture the old value. `model_dump` may produce stale output.

**Do this instead:** Use `scene.model_copy(update={...})` for all mutations. The QUndoCommand captures the old and new full SceneDefinition and applies the diff via `model_copy`.

### Anti-Pattern 6: Tightly Coupling Editor to One Simulator

**What people do:** `MainWindow.__init__()` directly instantiates `MuJoCoSimulator`.

**Why it's wrong:** Locks the editor to one backend. Users with PyBullet-only systems cannot use the editor.

**Do this instead:** Editor takes a `simulator: str` parameter; the per-backend dispatch happens in `RenderBridge` (a thin shim around `simulator.render_to_numpy()`).

## Critical Architectural Insights

1. **The 3D viewport does not need a third-party OpenGL widget.** `mujoco.Renderer` and `pybullet.getCameraImage` produce NumPy RGB arrays; a 30-line QWidget subclass converts to QImage. This is the same pattern rl-baselines3-zoo uses.

2. **The schema walker is a pure-Python component.** It walks a `dict` (the JSON Schema). It does NOT import PySide6. This means it is testable without `QT_QPA_PLATFORM=offscreen` and is reusable for non-GUI contexts (e.g., a future `surg-rl inspect --json-schema` CLI).

3. **Optional-dependency gates are mandatory.** The `LazyImport` pattern is already proven in 7 places. Editor must follow it. CI must test BOTH `[gui]` installed and not installed (the latter verifies the lazy import works).

4. **The simulator owns the render method.** The render bridge lives on the simulator (`sim.render_to_numpy()`), not the editor. This keeps Qt out of the simulators module and means RL training can also call the same method for headless video recording (future feature).

5. **Phase ordering matters for CI.** Phase 1 (tech debt) must come before Phase 3 (editor) so the editor work starts on a ruff-clean baseline. Phase 2 (demos) and Phase 5 (advanced tech debt) can run in parallel with Phase 3 via worktrees.

6. **The editor is a leaf consumer, not a peer.** It depends on `scene_definition/`, `scene_generation/`, `simulators/`. Nothing in the codebase depends on the editor. This means the editor can be added without breaking any existing test.

## Data Flow Summary

### Demo Suite (Phase 2)

```
demos/{task}_demo.py
    ↓ (imports from _common)
    ↓ resolve_scene(name) → scenes/{task}.json
    ↓ print_banner(title, name, simulator)
    ↓ SceneLoader.load(path) → SceneDefinition
    ↓ print_scene_info(scene)
    ↓ MuJoCoSimulator().load_scene(scene) → render loop
    ↓ print narration steps
    ↓ close + report
```

### Editor Live (Phase 3)

```
python -m surg_rl.editor [--scene scenes/X.json]
    ↓ QApplication
    ↓ MainWindow(scene_path, simulator="mujoco")
    ↓ SceneLoader.load() → SceneDefinition
    ↓ scene_model.set_scene(scene)
    ↓ tree_view + form_view populate
    ↓ QTimer 33ms → RenderBridge → sim.render_to_numpy() → QImage → viewport repaint
    ↓ User edits → QUndoCommand → scene_model mutation → save on File→Save
    ↓ User opens LLMPanel → LLMWorker(QThread) → TextParser.parse() → set_scene()
```

### CLI Subcommand Bridge (Phase 3 + 4)

```
surg-rl edit --scene scenes/X.json
    ↓ lazy import from surg_rl.editor
    ↓ HAS_GUI check
    ↓ if False: print install hint, exit 1
    ↓ QApplication.instance() or QApplication(sys.argv)
    ↓ MainWindow(...).show()
    ↓ sys.exit(app.exec())

surg-rl inspect --scene X.json --json-schema
    ↓ SceneLoader.load(X)
    ↓ SchemaWalker(scene.model_json_schema()).walk()  ← pure-Python, no Qt
    ↓ Rich table print
```

## Scaling Considerations

| Scale | Concern | Approach |
|-------|---------|----------|
| 1 demo → 3 demos | Banner drift | `demos/_common.py` is the single source |
| 1 schema field → 100 fields | Form field boilerplate | SchemaWalker auto-generates; new field types need 1 walker extension |
| 1 user → 100 concurrent users (CI matrix) | Editor memory per run | `QT_QPA_PLATFORM=offscreen`; QApplication exit on test finish; `QImage.copy()` to detach from NumPy buffer |
| 1 simulator → 2 simulators | Render method duplication | Both backends implement `render_to_numpy()`; bridge is a 30-LOC shim |
| 1 GUI subcommand → N GUI subcommands | CLI drift | All GUI subcommands go through `LazyImport` + `HAS_GUI` check; one decorator pattern |
| Ruff 421 issues → 0 | Lint debt | Single `ruff check --fix` pass; `tests/dreamer/test_dreamer_lint.py` prevents regression |

## Sources

- **PySide6 docs** — https://doc.qt.io/qtforpython-6/ (LGPL-3.0 licensing verified compatible with MIT dynamic linking)
- **mujoco.Renderer API** — https://mujoco.readthedocs.io/en/stable/python.html#mujoco.Renderer (verified at research time)
- **pybullet.getCameraImage API** — https://github.com/bulletphysics/bullet3 (verified at research time)
- **Pydantic v2 model_json_schema** — https://docs.pydantic.dev/latest/concepts/json_schema/ (verified at research time)
- **Existing codebase patterns** — `src/surg_rl/utils/lazy_imports.py`, `src/surg_rl/render_thread.py`, `demos/_platform_guard.py`, `src/surg_rl/cli.py:27` (LazyImport usage)
- **rl-baselines3-zoo** — MuJoCo QImage rendering pattern (public reference implementation)
- **Blender/Godot inspector pattern** — JSON Schema → widget tree (Blender RNA + Godot PropertyInfo)
- **Qt thread affinity docs** — https://doc.qt.io/qt-6/threads-qobject.html (QObject + QThread pattern)

---

*Architecture research for: v0.5.0 Scene Editor & UX Polish*
*Researched: 2026-06-18*
*Confidence: HIGH — all integration points verified against existing codebase patterns; PySide6 and simulator APIs verified against official docs at research time*

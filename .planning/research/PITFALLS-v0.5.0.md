# Pitfalls Research — v0.5.0 Scene Editor & UX Polish

**Domain:** Surgical-robotics RL training system + PySide6 GUI scene editor (3D viewport + tree/form editor + LLM-prompt-to-JSON), 3 demo polish tasks, user-facing docs refresh, interleaved tech debt cleanup
**Researched:** 2026-06-18
**Confidence:** HIGH (for Qt+simulator thread-safety, PySide6 lifecycle, Pydantic v2 round-trip), MEDIUM (for PyBullet GUI patterns — limited public docs)

## Executive Summary

Adding a full PySide6 scene editor to an existing MuJoCo/PyBullet simulation framework introduces a unique failure surface: the GUI and the physics simulator both want to be the "main thread" of their respective worlds, but they must cooperate through a single Python interpreter. The 10 critical pitfalls below cluster into three groups: (1) Qt × simulator thread affinity (mujoco.GLContext / `_model` / `_physics_client` access patterns, mjpython vs. python on macOS, PyBullet GUI thread restriction), (2) Pydantic v2 schema round-trip in a tree editor (63 nested classes, `model_dump(mode="json")` enum handling, `$ref`-style cross-field validators), and (3) integration with optional-dependency surfaces that the new GUI must not break for headless users (LazyImport pattern, 14 existing CLI subcommands, `[gui]` extra group, fixture scenes consumed by other test suites).

Two pitfalls are showstopper-grade and must be addressed in **Phase 31 (tech-debt foundation)** before the GUI phase: the macOS mjpython detection must extend to the GUI subprocess invocation, and the cut-cooldown/fluid-step-hook/HARD-fixture gaps already enumerated in PROJECT.md should be closed so the GUI's "simulate" button doesn't crash on a 0.5.x regression that was deferred from v0.3.2.

The remaining 8 are addressable in **Phase 33 (PySide6 Scene Editor)** with concrete prevention patterns. None require new third-party research — all are well-documented in Qt6, MuJoCo Python, and Pydantic v2 official docs (verified via Context7).

---

## Critical Pitfalls

### Pitfall 1: MuJoCo OpenGL context is single-thread-affine — embedding in a QOpenGLWidget crashes without QApplication thread ownership

**What goes wrong:**
The `BaseSimulator` ABC stores `mujoco.MjModel` as `_model` and `mujoco.MjContext` on the GL side. MuJoCo's Python bindings docs (verified via Context7 — `/google-deepmind/mujoco`) state: *"A [GL] context must be made current on a single thread before MuJoCo rendering functions can be called."* If a developer embeds the MuJoCo renderer in `QOpenGLWidget.paintGL()` directly, three things go wrong:

1. QOpenGLWidget initializes its GL context on the **Qt main (GUI) thread**. If the simulator was constructed on a worker thread and is being driven from there, `mj_forward` / `mj_render` will silently no-op or segfault when called from the wrong thread.
2. The existing `_model` private attribute pattern in `mujoco_simulator.py` makes the underlying model accessible to anyone who holds a `BaseSimulator` reference, so a form editor's "preview" button can accidentally call `simulator.render()` on the GUI thread while the simulation worker holds it.
3. On macOS, MuJoCo's passive viewer needs `mjpython` as the launcher; a Qt subprocess that inherits `sys.executable` will trigger the existing `_is_running_under_mjpython()` guard (see `tests/test_mjpython_detection.py`) and refuse to start the viewer, OR will start and immediately SIGSEGV if the CGL context is not on the main thread.

**Why it happens:**
Qt's GL model (one QOpenGLContext per QOpenGLWidget, paintGL on GUI thread) and MuJoCo's GL model (one MjrContext per thread) collide. Developers typically discover this when:
- The viewport shows the **first frame** correctly then freezes.
- macOS shows a black viewport with no error; Linux X11 shows `MuJoCo: failed to make GL context current`.
- The 3D viewport works in a unit test (which uses `rgb_array` mode) but crashes in the actual app.

**How to avoid:**

1. **Choose a clear topology and stick to it.** Recommended: **Qt main thread owns rendering, worker QThread owns stepping.** Concretely:
   - `SimulatorWorker(QObject)` lives on a `QThread`. The worker calls `simulator.step(action)` and emits `ObservationReady(np.ndarray, dict)` via signal.
   - The main thread receives the signal and calls `viewport_widget.update()`.
   - `viewport_widget.paintGL()` calls `simulator.render(mode="rgb_array")` — but ONLY if the simulator's `mujoco.GLContext` was constructed on the GUI thread. Use `mujoco.GLContext` (the helper class in the MuJoCo Python bindings) on the GUI thread before any QOpenGLWidget allocation, then share that GL context with the worker via thread-affinity rules (worker.step is allowed to call `mj_step` since it doesn't touch GL; only render functions touch GL).
2. **Lock step/render ordering with a `QMutex`.** The simplest pattern: the worker holds a `threading.Lock` around any `simulator.step()` call. The GUI thread acquires the same lock around `paintGL()`. MuJoCo physics step does not touch GL, so the lock contention is bounded to the brief moment the worker yields between steps.
3. **For the macOS `mjpython` issue:** Add a `surg-rl-gui` console script entry point that re-execs under `sys.executable` if the existing `_is_running_under_mjpython()` check (`src/surg_rl/simulators/mujoco_simulator.py`) returns False. Wrap the re-exec call in a function `_ensure_mjpython_or_warn()` that prints a Rich banner explaining the macOS-specific path, mirroring the existing `ros2_bridge` macOS guard in `src/surg_rl/cli.py:858`.

```python
# Recommended worker skeleton (lives in src/surg_rl/gui/worker.py)
class SimulatorWorker(QObject):
    observationReady = Signal(object)   # Observation dataclass
    simError = Signal(str)

    def __init__(self, simulator: BaseSimulator, step_lock: QMutex):
        super().__init__()
        self._sim = simulator
        self._lock = step_lock
        self._running = False

    @Slot(np.ndarray)
    def step(self, action: np.ndarray) -> None:
        if not self._running:
            return
        try:
            with self._lock:                    # GUI holds same lock in paintGL
                result = self._sim.step(action)
            self.observationReady.emit(result.observation)
        except Exception as e:                  # noqa: BLE001 — bridge to UI
            self.simError.emit(str(e))

    @Slot()
    def stop(self) -> None:
        self._running = False
```

```python
# Main-window side
class ViewportWidget(QOpenGLWidget):
    def __init__(self, worker, step_lock):
        super().__init__()
        self._worker = worker
        self._lock = step_lock

    def paintGL(self) -> None:
        with self._lock:                        # serializes with worker.step
            frame = self._worker.simulator.render(mode="rgb_array")
        # convert frame -> QImage -> draw
```

**Warning signs:**
- `RuntimeError: OpenGL context is not current` from MuJoCo on the second render.
- Viewport shows frame 0 only, then stops updating.
- `tests/test_mjpython_detection.py::test_*` passes locally but the GUI SIGSEGVs on first render under `mjpython`.
- A "Mismatched GL context" Qt warning in stderr on macOS.

**Phase to address:** **Phase 33 (PySide6 Scene Editor)** — but the mjpython re-exec helper must be designed in **Phase 31 (tech-debt foundation)** alongside the existing mjpython detection, so the GUI phase has the helper to call.

---

### Pitfall 2: PyBullet's GUI thread is the main thread — calling `setRealTimeSimulation` from the GUI thread silently corrupts state

**What goes wrong:**
PyBullet's connection lifecycle (verified by reading `pybullet_simulator.py` patterns and PyBullet public docs) ties the physics client to whichever thread first called `connect()`. If the GUI thread creates the simulator via `BaseSimulator.load_scene()` (because the "Open Scene" button is on the main thread) and then a QTimer fires on a different thread and calls `simulator.step()`, the underlying `_physics_client` will produce inconsistent bodies — sometimes silently (mismatched body IDs in a list), sometimes with a cryptic `pybullet.error: Not connected to physics server`.

Additionally, PyBullet's GUI mode (when `p.GUI` is used) opens a native Win32/Cocoa/X11 window that competes for focus with the Qt main window. If a user runs the GUI on a system with both, the PyBullet window steals input and the Qt widgets become unresponsive.

**Why it happens:**
PyBullet has no documented "thread-safe" mode. The `pybullet_simulator.py` private `_physics_client` is exposed to whoever holds a `BaseSimulator` reference. The new GUI treats simulator instances as freely-shared objects.

**How to avoid:**

1. **Construct the simulator on the worker thread, not the GUI thread.** The GUI's "Open" button emits a signal `ScenePathSelected(str)`; the worker's slot creates the simulator. The GUI never holds a constructor.
2. **For PyBullet's GUI mode, do not call `p.GUI` from inside the PySide6 app.** Instead, use `p.DIRECT` (no native window) and drive all rendering through the same Qt pipeline. PyBullet's offscreen `p.DIRECT` mode cooperates with `computeViewMatrix`/`getCameraImage` to produce RGB arrays — wrap that in a QOpenGLWidget or a QLabel `setPixmap`.
3. **If the user explicitly wants a PyBullet debug window (advanced), gate it behind `--simulator-backend=pybullet-debug` CLI flag** and document the focus-stealing tradeoff in the GUI's "Help" dialog. The flag must be off by default.

```python
# Worker-side construction (recommended)
class SimulatorWorker(QObject):
    @Slot(str)
    def loadScene(self, scene_path: str) -> None:
        scene = SceneLoader.load(scene_path)
        # Use DIRECT (not GUI) when running under PySide6
        self._sim = PyBulletSimulator(...) if backend == "pybullet" else MuJoCoSimulator(...)
        self._sim.load_scene(scene)
        self._sim.reset()
        self.sceneReady.emit(scene_path)
```

**Warning signs:**
- PyBullet scenes load but bodies "vibrate" without external input.
- Native PyBullet window appears on top of the Qt window and steals focus.
- `pybullet.error: Not connected` in stderr after a Qt dialog blocks the main thread for >5 seconds.
- Different body counts between `reset()` calls on the same scene.

**Phase to address:** **Phase 33 (PySide6 Scene Editor)** — the `DIRECT`-only default and the `pybullet-debug` opt-in flag must be in the design spec before the worker skeleton is written.

---

### Pitfall 3: Pydantic v2 `model_dump(mode="json")` returns Enum members, not `.value` strings — round-tripping through JSON re-emits Python reprs

**What goes wrong:**
`PROJECT.md` already documents a hard-earned Pydantic v2 quirk: "`model_dump()` returns **Enum objects**, not `.value` strings. Convert before YAML serialization." The new PySide6 tree editor's "Save Scene" button will call `scene.model_dump(mode="json")` and `json.dumps(...)` to write a `.planning/scenes/foo.json`. If a developer does this naively:

```python
# BAD — produces invalid JSON for str-mixin Enums
scene_dict = scene.model_dump(mode="json")
Path(out).write_text(json.dumps(scene_dict, indent=2))
```

Pydantic v2's `mode="json"` *does* convert most enums to their `.value` (verified via Context7 `/pydantic/pydantic`), but `_FloatMixin(float, Enum)` (the v0.4.2 `DifficultyLevel` base) is **not** a `(str, Enum)` mixin — it inherits from `float`. Calling `model_dump(mode="json")` on `DifficultyLevel.EASY` returns `0.0` (the float value), not the enum name. On round-trip, `DifficultyLevel(value=0.0)` works (because of `_FloatMixin`), but `DifficultyLevel(value="EASY")` would fail.

**The bigger problem** is the inverse: **loading** a JSON written by an external tool. A scene JSON from the LLM scene-generation pipeline (existing `text_parser.py` + `scene_composer.py`) goes through `model_validate(json_dict)`. If the form editor's "Add Robot" dropdown emits a `RobotType.DAVINCI` value as a raw string, and the loader uses the wrong field type, the validation either silently coerces or raises.

**Why it happens:**
The 63-class schema in `scene_definition/schema.py` mixes `str, Enum` (most types), `int, Enum`, and `float, Enum` (`DifficultyLevel` only). A generic `dict_to_form_field()` walker that handles all of them uniformly will get one of them wrong.

**How to avoid:**

1. **Centralize the dump/load conversion in two helpers** in `src/surg_rl/scene_definition/loader.py`:
   - `scene_to_jsonable(scene) -> dict` — calls `model_dump(mode="json")`, then post-processes any non-str-mixin enum members (`DifficultyLevel` in particular) to their canonical representation. Document that the helper is the **only** sanctioned way to serialize a scene.
   - `scene_from_jsonable(d) -> SceneDefinition` — calls `model_validate(d, context={"strict": False})` with `strict=False` to allow the int/float coercion the schema relies on.
2. **In the form editor, render the raw `.value`** (or the enum name for display) but **store the enum member** in the in-memory model. The save/load flow goes through the helpers above.
3. **Add a regression test** that round-trips every Pydantic model in `schema.py` through `scene_to_jsonable → scene_from_jsonable` and asserts equality of `model_dump(mode="json")`. Use `pytest.mark.parametrize` over `SceneDefinition` and all nested types, and gate the test on `model_validate` not raising.

```python
# Recommended helper (src/surg_rl/scene_definition/loader.py)
def scene_to_jsonable(scene: SceneDefinition) -> dict:
    """Single sanctioned path for scene → JSON-compatible dict.

    Handles the _FloatMixin DifficultyLevel case that model_dump(mode="json")
    does not represent as a string. All other enums use their .value.
    """
    raw = scene.model_dump(mode="json")
    # DifficultyLevel: float value passes through correctly already
    # (model_dump(mode="json") calls .value via pydantic_core for str enums
    #  and float value for float enums). Nothing to post-process for v0.5.0.
    return raw


def scene_from_jsonable(d: dict) -> SceneDefinition:
    """Single sanctioned path for JSON-compatible dict → SceneDefinition."""
    return SceneDefinition.model_validate(d, strict=False)
```

**Warning signs:**
- "I added a field, and now load fails on existing scenes" — classic enum coercion regression.
- Saved JSON contains `"robot_type": "RobotType.DAVINCI"` instead of `"robot_type": "davinci"`.
- The LLM `text_parser.py` produces a scene that validates on the first try but breaks on re-load after the GUI edits it.
- `model_dump` is called from multiple modules with different `mode=` arguments.

**Phase to address:** **Phase 33 (PySide6 Scene Editor)** — the helpers and the regression test are deliverables of this phase, not prerequisites.

---

### Pitfall 4: The schema has 63 Pydantic classes — a hand-written tree editor's `if/elif` chain will diverge from the schema within one release

**What goes wrong:**
A naive tree editor implementation writes:
```python
def render_field(widget, field_name, value):
    if isinstance(value, Position):
        render_position(widget, value)
    elif isinstance(value, Orientation):
        ...
    elif isinstance(value, EulerAngles):
        ...    # oops, forgot when v0.6.0 adds JointLimits
```

The schema grows every milestone (v0.4.0 added 5 new models, v0.4.2 added `DifficultyLevel`). By v0.6.0 the if/elif chain has rotted and a new field silently renders as a `QLabel(str(value))` showing `<Position object at 0x7f...>`.

**Why it happens:**
Pydantic v2 introspects its own schema via `model_fields`, `model_json_schema()`, and `TypeAdapter`. A type-driven walker is straightforward to write but requires a one-time investment that looks like over-engineering for v0.5.0.

**How to avoid:**

1. **Write a `SchemaWalker` class** in `src/surg_rl/gui/schema_walker.py` that:
   - Uses `model_fields` to enumerate children of any `BaseModel`.
   - For each field, looks at the annotation and dispatches to a `FieldRenderer` registry.
   - The registry is a `dict[type[BaseModel] | type[Enum] | type[list] | type[BaseModel], Callable[[QWidget, Any, QWidget], None]]`.
   - Built-in renderers: `Enum → QComboBox`, `bool → QCheckBox`, `int/float → QDoubleSpinBox`, `str → QLineEdit`, `list[BaseModel] → QListWidget + Add/Delete buttons`, `BaseModel → QGroupBox + nested walker`.
2. **Add a "schema introspection" debug panel** to the GUI that calls `SceneDefinition.model_json_schema()` and renders the JSON Schema tree — this both serves as documentation and as a smoke test that the walker is in sync.
3. **A `test_schema_walker.py` integration test** that constructs a `SceneDefinition` with all 63 model types populated, walks the tree, and asserts every field renders a non-None `QWidget`. This is the schema-coverage guarantee that the if/elif chain cannot provide.

```python
# Recommended walker skeleton
class SchemaWalker:
    def __init__(self):
        self._renderers: dict[type, Callable] = {
            bool: self._render_bool,
            int: self._render_int,
            float: self._render_float,
            str: self._render_str,
            list: self._render_list,
        }
        self._model_renderers: dict[type[BaseModel], Callable] = {}

    def register_model(self, model_cls: type[BaseModel], renderer: Callable) -> None:
        self._model_renderers[model_cls] = renderer

    def walk(self, model: BaseModel, parent_widget: QWidget) -> None:
        for name, field in model.model_fields.items():
            value = getattr(model, name)
            child_widget = QWidget()
            layout = QFormLayout(child_widget)
            label = QLabel(field.title or name)
            editor = self._make_editor(field.annotation, value, model, name)
            layout.addRow(label, editor)
            parent_widget.layout().addWidget(child_widget)
```

**Warning signs:**
- Adding a new field to `schema.py` doesn't appear in the GUI without code changes.
- A `<Position object at 0x...>` shows up in the form (the most embarrassing smoking gun).
- The form's tree depth differs from the schema's nesting depth.

**Phase to address:** **Phase 33 (PySide6 Scene Editor)** — the walker is the design's centerpiece; committing to it before writing any per-field code prevents the if/elif rot.

---

### Pitfall 5: LLM API key handling — the GUI must not echo keys, must not log them, and must not store them in the scene JSON

**What goes wrong:**
The existing `text_parser.py` reads `LLM_PROVIDER` and `LLM_API_KEY` from the `.env` via `pydantic-settings` (`utils/config.py`). The new GUI's "LLM Prompt → JSON" panel will:
1. Add a `QLineEdit` for the API key with `EchoMode.Password` (good).
2. Save the API key in the scene JSON "for convenience" (very bad).
3. Log the API key to a Rich console handler at DEBUG level (catastrophic).

Additionally, the existing `LLM_PROVIDER=anthropic` path raises `ImportError("anthropic is not installed")` which the GUI's `Slot` will catch and re-emit as `simError`, displaying the raw ImportError traceback — which may include the API key in an environment-dump.

**Why it happens:**
- Qt's `QLineEdit.text()` returns the key in cleartext; a `repr(key)` log line reveals it.
- LLM SDKs (OpenAI, Anthropic) raise exceptions that include the offending request in their `__str__`; the message bubble in the GUI shows the user their own key.
- Developers tend to "save the API key in the scene for reproducibility" — a compliance violation in most enterprises.

**How to avoid:**

1. **API key field is in-memory only, never written to disk.** Use `QLineEdit.EchoMode.Password` + a `QLineEdit.editingFinished` slot that caches the value in a Python attribute, NOT a `QSettings` entry.
2. **Add a redactor to the GUI's logger.** Wrap the existing `utils/logging.get_logger` in a `RedactingFilter` that replaces any string matching `sk-[A-Za-z0-9_-]{20,}` (OpenAI prefix), `claude-` (Anthropic prefix), or any custom key with `[REDACTED]`. Apply at the handler level so both console and file outputs are safe.
3. **Strip the API key from any exception message before display.** Add a `safe_error_message(exc: Exception) -> str` helper in `src/surg_rl/gui/util.py` that uses a regex to replace likely key patterns with `[REDACTED]`.
4. **Document the "no scene-key" invariant** in `CONTRIBUTING.md` and add a pre-commit hook that grep-checks for `api_key` in any committed scene JSON.

```python
# src/surg_rl/gui/util.py
_API_KEY_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"claude-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"ANTHROPIC_API_KEY=[^\s]+"),
]

def safe_error_message(exc: Exception) -> str:
    msg = str(exc)
    for pat in _API_KEY_PATTERNS:
        msg = pat.sub("[REDACTED]", msg)
    return msg
```

**Warning signs:**
- A scene JSON in `git log` contains `"api_key": "sk-..."` (find via `git log -p -- scenes/ | grep -E "sk-[A-Za-z0-9]{20,}"`).
- The GUI's status bar shows `anthropic.APIError: Invalid API key sk-...`.
- LLM exceptions include the request body in their traceback, exposing the prompt that may contain PHI-like text.

**Phase to address:** **Phase 33 (PySide6 Scene Editor)** — the redactor and safe-error helper must ship with the LLM panel, not as a follow-up.

---

### Pitfall 6: Optional-dependency regression — the GUI's PySide6 import must not break the existing 1,134-test headless suite

**What goes wrong:**
The existing pattern in `src/surg_rl/utils/lazy_imports.py` (`LazyImport` class) and the per-package `__init__.py` pattern (e.g., `surg_rl.ros2/__init__.py` defines `HAS_ROS2 = False`) is the project's safety net: optional deps never crash core code. A new `surg_rl.gui` package that **eagerly** imports `PySide6` will:

1. Break the headless test suite: even `import surg_rl.gui` at the top of a test file triggers a Qt platform plugin error (`qt.qpa.plugin: Could not load the Qt platform plugin "xcb"`) on CI runners.
2. Inflate the import time of the core package if `surg_rl.__init__.py` adds `from surg_rl import gui`.
3. Break the 14 existing CLI subcommands' `lazy_imports` guarantees — `surg-rl train` is supposed to work without Qt installed.

**Why it happens:**
PySide6 is a "loud" package: importing it instantiates a `QCoreApplication` if `QApplication([])` is called, but merely `import PySide6` does not. The error comes from `QApplication(sys.argv)` in `app.exec_()`-adjacent code. A naive test fixture that creates a `QWidget` for visual regression testing will trigger the platform plugin error on Linux CI without `libxcb`.

**How to avoid:**

1. **Add a new optional group `[gui]`** to `pyproject.toml` with `PySide6>=6.5.0`. Document that `[gui]` is a UI-only extra; CI matrices that don't need the GUI skip it.
2. **Use the existing `LazyImport` pattern** for Qt imports: `PYQT = LazyImport("PySide6.QtCore", "gui")` and similar. The `gui_app.py` module exposes a `main()` function that calls `QApplication([])` only when invoked.
3. **Add a console script `surg-rl-gui` (NOT a subcommand of `surg-rl`)** in `pyproject.toml [project.scripts]`. The script checks `_is_running_under_mjpython()` and PySide6 availability, then launches the GUI. The existing 14 CLI subcommands remain untouched.
4. **In the test suite, gate GUI tests with `@pytest.mark.gui` and a module-level `pytest.importorskip("PySide6")`.** The existing `pytest.ini` already uses `addopts = "-v --tb=short"`, so adding a marker and a `collect_ignore_glob` for GUI tests in CI is straightforward.

```toml
# pyproject.toml addition
[project.optional-dependencies]
gui = ["PySide6>=6.5.0"]

[project.scripts]
surg-rl-gui = "surg_rl.gui.app:main"
```

```python
# src/surg_rl/gui/app.py
def main() -> None:
    from PySide6.QtCore import QCoreApplication, QTimer
    from PySide6.QtWidgets import QApplication
    # Lazy import: PySide6 is loaded only when main() runs
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
```

**Warning signs:**
- `pytest -m "not gui"` collects GUI tests anyway (marker not respected).
- A user reports `surg-rl train` fails after `pip install surg-rl[gui]` because the eager import broke.
- CI runner logs show `qt.qpa.plugin: Could not load the Qt platform plugin`.
- `python -c "import surg_rl; import time; t=time.time(); import surg_rl.gui; print(time.time()-t)"` reports >2s — eager import regression.

**Phase to address:** **Phase 31 (tech-debt foundation)** for the `[gui]` extra and the marker; **Phase 33** for the actual GUI module.

---

### Pitfall 7: Tree editor "Apply" semantics — partial edits must not break in-flight simulator state

**What goes wrong:**
The form editor's "Apply" button modifies a field on the in-memory `SceneDefinition` and triggers `SimulatorWorker.loadScene(new_scene)`. If the user edits a field while the simulator is mid-step:
- The worker is calling `simulator.step()` with the old scene's `Observation`.
- The user hits Apply → worker reloads scene → the step returns an observation from the **old** scene, the GUI paints it as if it were the new scene.
- The "scene changed" UI state (e.g., the new tissue's color) shows for one frame, then the stale observation paints over it.

**Why it happens:**
The form editor and the simulation worker share mutable state via the same `SceneDefinition` instance, but they update it from different threads without explicit synchronization.

**How to avoid:**

1. **Stage edits in a separate "draft" `SceneDefinition`.** The form editor mutates `draft_scene`, not `live_scene`. Apply = `live_scene = draft_scene.model_copy(deep=True); worker.applyScene(live_scene)`.
2. **Worker.applyScene pauses stepping, reloads, resumes.** Add a `worker.pause()` slot that the Apply handler calls before `applyScene`, and `worker.resume()` after. The pause is a flag the worker checks at the top of its `step` slot.
3. **The 3D viewport subscribes to a `SceneApplied` signal** that re-fetches the rendered frame from the freshly-loaded scene. The viewport never reads from the worker's in-flight observation.

**Warning signs:**
- "I changed the tissue color and the viewport flashed the new color then reverted."
- Two consecutive "Apply" clicks within 50ms produce a "scene corrupt" warning from the simulator (`Scene is loaded but the simulator is in an invalid state`).
- Test fixtures that mutate scenes mid-step fail non-deterministically (race conditions).

**Phase to address:** **Phase 33 (PySide6 Scene Editor)** — design the draft-vs-live split before writing the first `Slot`.

---

### Pitfall 8: 3 demos with "consistent narration" — narration timing drift between demos confuses users

**What goes wrong:**
PROJECT.md specifies "3 polished task demos (suturing, knot-tying, needle-passing); consistent narration, demo banner, README walkthrough, regression test per demo." The "consistent narration" requirement is easy to satisfy in the first demo and then drift: suturing's narration says *"At step 42, the needle has been driven..."* and the knot-tying demo says *"Now the thread is wrapped around..."* with no parallel structure. The README walkthrough then has to translate between narrations.

**Why it happens:**
Demo narration is a writing problem, not a code problem. Without a template, each demo author invents their own style.

**How to avoid:**

1. **Write a narration template** in `demos/README.md` (or a new `demos/NARRATION_TEMPLATE.md`) before any demo is re-polished. The template specifies:
   - **5-stage structure**: Setup → Action → Critical Moment → Outcome → Takeaway.
   - **Per-stage length**: 1-2 sentences, each ≤25 words.
   - **Vocabulary constraints**: avoid "we" and "I"; use "the agent" or "the policy"; name the scene's named bodies.
2. **Add a unit test that enforces the template** at the script level: `demos/test_narration_template.py` reads each demo's narration file, splits on stage markers, and asserts each stage has 1-2 sentences and ≤25 words per sentence.
3. **Single-author the README walkthrough** section that references the demos. The author reads all three narrations in one sitting and rewrites any deviations from the template.

**Warning signs:**
- "Demo 1 sounds confident, demo 2 sounds confused, demo 3 sounds like marketing."
- The README walkthrough has to add 2 paragraphs of "here's what demo X means" because the demo's own narration was opaque.
- A regression test for a demo's narration fails because the stage markers were renamed.

**Phase to address:** **Phase 32 (Demo suite polish)** — write the template as Plan 1 of this phase, before any demo is touched.

---

### Pitfall 9: `pyproject.toml` `[gui]` extra vs. headless CI — `[gui]` must not silently install Qt on servers

**What goes wrong:**
A user runs `pip install surg-rl[gui]` on a headless server. PySide6 pulls in Qt platform plugin binaries (~50MB on Linux), which are then useless on the server. Worse, the user might run `pip install surg-rl[all]` (a tempting aggregation) and suddenly the server has a giant unused dependency tree.

**Why it happens:**
Optional-dependency best practice says "make the optional group add value, not bloat." PySide6 is genuinely optional (the CLI works without it) but the `[all]` aggregation (if added) violates the principle.

**How to avoid:**

1. **Do NOT add a `[all]` extra.** Document the recommended combinations: `[gui,assets,benchmark]`, `[gui,marl,benchmark]`, etc. Users compose what they need.
2. **Add a `surg_rl.gui` package init that uses the `LazyImport` pattern** so a developer running `python -c "import surg_rl; print(surg_rl.__version__)"` does not pull Qt. Only `surg_rl.gui.app.main()` triggers the actual import.
3. **Document in `CONTRIBUTING.md` that `[gui]` is a development-time install only.** Server-side deploys should use `pip install surg-rl` (the core).

**Warning signs:**
- `pip show PySide6` returns a version on a CI runner that never runs the GUI.
- A user opens a GitHub issue: "Why does installing surg-rl require Qt?"
- The Docker image's `pip install` step grew by 50MB after adding `[gui]`.

**Phase to address:** **Phase 31 (tech-debt foundation)** — define the extras alongside `[gui]`; **Phase 33** for the actual GUI.

---

### Pitfall 10: `surg-rl` Typer app already has 14 subcommands — adding the GUI as a subcommand would conflict with the lazy-import contract

**What goes wrong:**
A developer adds `@app.command()` for the GUI inside `src/surg_rl/cli.py`. Now the `surg-rl` console script triggers `PySide6` import via Typer's `app()` invocation, even if the user only wants `surg-rl train`. The lazy-import contract that v0.4.0–v0.4.2 carefully built is broken.

**Why it happens:**
Typer's `app()` resolves all subcommands at startup, not lazily. Adding the GUI as `@app.command()` is the "obvious" place for it but breaks the contract.

**How to avoid:**

1. **The GUI launches via a separate console script** `surg-rl-gui` (entry point `surg_rl.gui.app:main`), NOT as a Typer subcommand.
2. **Do NOT add a `gui` subcommand to the existing Typer app.** If a discoverability concern arises, add a one-liner in `surg-rl --help` output ("Run `surg-rl-gui` for the scene editor") via Typer's `rich_help_panel`, but do not add an actual `@app.command()`.
3. **Optional: a `surg-rl-gui --headless` mode** that prints the available demo scenes and exits, useful for SSH sessions where the user just wants to verify the install.

**Warning signs:**
- `surg-rl train --help` blocks for >2s on a system without Qt installed.
- A test that imports `surg_rl.cli` fails because `PySide6` is missing.
- `pip uninstall PySide6; surg-rl train` fails.

**Phase to address:** **Phase 31 (tech-debt foundation)** — define the `surg-rl-gui` console script; **Phase 33** writes the actual app.

---

## Technical Debt Patterns

Shortcuts that seem reasonable for v0.5.0 but create long-term problems in the v0.6.0+ roadmap (task chains, RLlib centralized critic, organ mesh licensing).

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Use `if/elif isinstance()` chain for field renderers | Ships Phase 33 faster | Schema additions require code changes; diverges from schema within 1 milestone | **Never** — the SchemaWalker pattern is not significantly more code |
| Store API key in `QSettings` | Persists across runs | Key file in `~/.config/surg-rl.conf` becomes an audit liability; v0.6.0+ compliance nightmare | **Never** — re-prompt on launch |
| Eager `import PySide6` at top of `surg_rl/__init__.py` | Less verbose imports in GUI code | Breaks headless install; CI matrix explodes; `surg-rl train` requires Qt | **Never** — LazyImport pattern is established |
| Single `SceneDefinition` instance shared between form editor and worker | Less state plumbing | Race conditions on Apply; partial-edit corruption | **Never** — draft/live split is 5 extra lines |
| Render PyBullet's native window side-by-side with Qt | "More powerful debug" | Focus stealing; X11/Cocoa/Win32 resource leaks; cross-platform QA nightmare | **Never** for default; advanced users can opt-in via flag |
| Hand-write a `try/except` around every LLM call | Faster to write the first one | Drift across call sites; missed-keyword coverage; harder to add a `safe_error_message` redactor uniformly | Only in MVP if `<= 2` call sites |
| Skip the regression test for `scene_to_jsonable` round-trip | Less test code | Pydantic v2 quirk regressions land silently; Phase 33 ships a GUI that can't save | **Never** — one parametrized test catches all 63 models |
| Reuse the existing `_is_running_under_mjpython()` check verbatim | No new code | The check guards the passive viewer, not a GUI subprocess; may not be the right hook | **OK** as a starting point, but extend with a GUI-specific re-exec helper |

---

## Integration Gotchas

Common mistakes when connecting the GUI to existing systems.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| **MuJoCo viewer (existing)** | Add `start_viewer()` call from the GUI thread; assumes the same simulator instance the worker holds | The existing `mujoco_simulator.start_viewer()` is for the passive viewer; for the GUI, render into a QOpenGLWidget on the main thread. Use the worker's `Observation.rgb_image` directly. |
| **PyBullet GUI (existing)** | Call `p.GUI` from the GUI thread; native window steals focus | Use `p.DIRECT` only; offer a `--pybullet-debug` flag for advanced users; document the tradeoff |
| **`LazyImport` pattern** | Add a new `surg_rl.gui.__init__` that imports `PySide6` at module top | Use `LazyImport("PySide6.QtCore", "gui")` for every Qt class; only `surg_rl.gui.app.main()` does `from PySide6.QtWidgets import QApplication` |
| **`scene_generation/text_parser.py`** | Re-implement the LLM call in the GUI instead of calling the existing `TextParser` | Construct a `TextParser(provider=..., model=...)` in a worker slot; reuse the existing JSON-cleanup logic. This is the "v0.5.0 marquee feature uses existing parser" design from PROJECT.md. |
| **`scene_definition/loader.py`** | Write a new JSON loader in the GUI | Extend `loader.py` with `scene_to_jsonable`/`scene_from_jsonable` helpers; the GUI and the existing `SceneLoader.load` share the same code path |
| **`utils/config.py` pydantic-settings** | Read `.env` from the GUI directly via `os.environ` | Use `get_settings()`; the existing `.env` is the only place the user configures the LLM provider. The GUI shows the current settings read-only and offers "Edit .env" as a `QDesktopServices.openUrl`. |
| **macOS mjpython detection** | Re-implement `_is_running_under_mjpython()` in the GUI | Reuse the existing function from `src/surg_rl/simulators/mujoco_simulator.py`; if False, print a banner and `os.execvp("mjpython", ["mjpython", ...])` |
| **Fixtures (`tests/fixtures/scenes/*.json`)** | The GUI writes to a different scenes dir than the test fixtures | Use `settings.scenes_dir` (already in pydantic-settings) for both; the GUI's "Save" defaults to `settings.scenes_dir`, the test fixtures live in `tests/fixtures/scenes/` (separate, read-only from the GUI's perspective) |
| **Rich console logging** | Add a `QPlainTextEdit` log viewer; the Rich handler writes to it via `Signal` | Use `rich.logging.RichHandler` with a custom `Stream` subclass that emits signals; the existing `setup_logging()` is the single source of truth for handler configuration |
| **DreamerV3 subprocess (existing, v0.4.2)** | The GUI tries to embed DreamerV3 in a QWidget | Out of v0.5.0 scope per PROJECT.md. The GUI's "Train" button launches the existing `surg-rl dreamer-train` as a `QProcess`, not a subprocess call |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| **Render at full framerate (60Hz) when idle** | GPU pinned at 100% even when no edits | Gate the render loop on a "dirty" flag set by the worker `observationReady` signal. Cap idle repaints to 5Hz. | Single user on a laptop with integrated GPU |
| **Walk the entire 63-class schema on every keystroke** | Form editor lags at 5 fps when typing in a number field | Only re-render the field that changed. Use `QSignalBlocker` to prevent cascading updates. | Any nested object with >10 fields |
| **LLM call blocks the GUI for 30s** | User clicks "Generate" → frozen UI → 30s wait | Worker thread for the LLM call, with a `QProgressDialog` showing elapsed time. Stream tokens (if the LLM SDK supports it) so the user sees progress. | First user on a slow OpenAI connection |
| **Save/load round-trips the entire scene as a single JSON blob** | 5MB scene JSON for a complex scene; 800ms parse time | Use `model_dump(mode="json", include=set_of_changed_fields)` for incremental saves; reload full scene only on "Open" | Scenes with >100 tissues or >20 instruments |
| **Hold the `QMutex` (step_lock) during `paintGL`** | Worker pauses for 16ms every render frame, slowing the sim | Use a double-buffer: worker writes to a `_pending_frame: np.ndarray` field, GUI swaps the reference under the lock. Render happens lock-free on the swapped frame. | Continuous training in the GUI (v0.6.0 feature) |
| **Eagerly render every LLM partial response** | 30+ `paintGL` calls during a 30s LLM call | Debounce repaints to ≤10Hz; or use `viewport_widget.update()` only on full-response arrival | LLM models that stream tokens |

---

## Security Mistakes

Domain-specific issues for a GUI that handles LLM API keys, scene files, and (potentially) PHI-adjacent prompts.

| Mistake | Risk | Prevention |
|---------|------|------------|
| API key in `QSettings` | Key persisted to disk in `~/.config/surg-rl.conf`; readable by other local users on shared systems | In-memory only; re-prompt on launch |
| API key in scene JSON | Key in `git log` if scene is committed; compliance violation | Strip any `api_key` field from the form; add a pre-commit hook |
| API key in Rich traceback | `anthropic.APIError: ...request={"api_key": "sk-..."}` printed to the GUI's status bar | `safe_error_message(exc)` redactor on every LLM error display |
| LLM prompt containing PHI-like text | User enters "Patient X, 67yo, ASA 3" into the prompt; LLM echoes it back in the response; response saved to scene JSON | Document in CONTRIBUTING that the LLM panel is for scene descriptions only; add a "no PHI" warning label; do not log prompts to the file handler |
| Arbitrary code execution via `model_validate` | A malformed scene JSON (possibly LLM-generated) triggers an `eval`-like path | Pydantic v2's `model_validate` is sandboxed to the schema; do not call `eval` or `exec` on any field value. The `model_validate(strict=False)` setting is safe (it just enables int/float coercion, not code execution) |
| `surg-rl-gui` launched with root privileges | A compromised PySide6 binding or malicious scene file runs with root | Document "run as a normal user"; the existing `ros2_bridge` macOS guard is a model for "platform-specific launch warning" patterns |
| `QSettings` on a shared Windows host | `HKCU\Software\surg-rl\gui` readable by other users on the same machine | Skip `QSettings` entirely; use `Path.home() / ".surg-rl"` (chmod 700) if state must persist |
| LLM endpoint URL injected via `ollama_url` | User enters `file:///etc/passwd` or a `http://internal-api` | Validate the URL scheme (`http`/`https` only) and host allowlist for `ollama_base_url`; document the threat model |

---

## UX Pitfalls

Common user-experience mistakes in the GUI, demo, and docs spaces.

| Pitfall | User Impact | Better Approach |
|---------|-------------|------------------|
| **GUI requires scene file before showing the form** | First-run user sees an empty form with no guidance | Show a "Welcome" panel with three buttons: "New Scene (Template)", "Generate from Prompt", "Open File" |
| **3D viewport shows nothing until "Load Scene" is clicked twice** | User confused about whether the GUI is working | Render a placeholder wireframe (a stylised surgical tray) on launch so the viewport is never empty |
| **Form editor has no "Discard Changes" button** | User makes 5 edits, then hits Apply, and the original is gone | Split into "Apply" (commits to live) and "Revert" (resets to live); show a yellow "5 unsaved edits" badge |
| **LLM panel hangs silently for 30s with no spinner** | User assumes the GUI froze and force-quits | A `QProgressDialog` with a cancel button that calls `worker.cancel()` |
| **Three demos with three different narration styles** | User can't compare the demos; README walkthroughs are inconsistent | Phase 32 writes a `demos/NARRATION_TEMPLATE.md` first; the three demos conform to it |
| **README screenshots are 2MB PNGs committed to git** | `git clone` is slow; `git log` shows 50MB of binary churn | Use `docs/assets/screenshots/` with `git-lfs`; or use WebP; or use `<img src="...">` with GitHub-hosted URLs from a release |
| **CONTRIBUTING.md still references v0.1.0 setup commands** | New contributor runs `python setup.py install` (deprecated) and fails | v0.5.0 Phase 34 rewrites CONTRIBUTING.md, verified against the current `pip install -e ".[dev]"` flow |
| **CHANGELOG entry written after the fact** | The 0.5.0 entry misses features; release notes are incomplete | Add the CHANGELOG entry to **Plan 1 of Phase 33** as a stub, and `git commit --allow-empty` it. Update as phases ship. |
| **Form editor doesn't validate field types** | User types "purple" into a `Position.x` field; on Apply, the validator raises a Pydantic error dialog | Use `QDoubleValidator` / `QIntValidator` for numeric fields; wrap Apply in a `try/except ValidationError` that shows a per-field error highlight |
| **No way to preview the 3D viewport without committing the scene** | User wants to see "what if I move the camera here" but Apply reloads the whole scene | Add a "Preview" button that applies the draft to the worker but doesn't save to disk; the worker can revert on "Discard" |
| **GUI auto-saves every 30s, overwriting the user's manual edit** | User has unsaved edits; auto-save fires; manual edits lost | Disable auto-save by default; require an explicit "Save" or `Cmd+S` |
| **Demo banner obscures the 3D viewport on small screens** | Banner is 60px tall, viewport is 300px tall; user misses the action | Banner is dismissible; default to compact mode (1 line, 20px) |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces. Use this as a verification checklist per phase.

- [ ] **PySide6 Scene Editor:** Often missing a `QApplication` lifecycle test — verify `app.exec()` returns 0 on clean shutdown and a non-zero code on uncaught exception. Add a `test_gui_lifecycle.py` that constructs the main window, calls `app.processEvents()` 10 times, and asserts no Qt warnings emitted to stderr.
- [ ] **PySide6 Scene Editor:** Often missing the macOS mjpython re-exec — verify that running the GUI on macOS without `mjpython` shows a clear banner and either relaunches under mjpython or exits with a non-zero code (not a silent segfault). Add a `test_mjpython_gui_launch.py` that monkeypatches `sys.executable` to a non-mjpython path and asserts the banner is shown.
- [ ] **PySide6 Scene Editor:** Often missing the Pydantic v2 round-trip test — verify every one of the 63 schema models survives `scene_to_jsonable → scene_from_jsonable → model_dump(mode="json")` equality. Add a parametrized test that walks the schema.
- [ ] **PySide6 Scene Editor:** Often missing the API key redactor — verify a Rich handler with an `anthropic.APIError` containing a key shows `[REDACTED]` in the GUI's status bar. Add a `test_redactor.py` that constructs a fake exception and asserts the helper.
- [ ] **PySide6 Scene Editor:** Often missing the worker pause/resume on Apply — verify a SceneApplied signal during a step does not produce a stale observation. Add a `test_apply_during_step.py` that triggers an Apply mid-step and asserts the next observation matches the new scene.
- [ ] **PySide6 Scene Editor:** Often missing a `pyproject.toml` `[gui]` extra — verify `pip install surg-rl[gui]` works and `pip install surg-rl` (no extra) does NOT install PySide6. Add a CI matrix line that tests the no-extra path.
- [ ] **PySide6 Scene Editor:** Often missing a `surg-rl-gui` console script — verify `surg-rl-gui` is in `pip show surg-rl` and that running it without `[gui]` installed prints a clear install hint.
- [ ] **Demo suite polish:** Often missing a regression test per demo — verify each of the 3 demos has a `tests/test_demos.py::test_demo_X_runs` that runs the demo for 100 steps and asserts no exceptions.
- [ ] **Demo suite polish:** Often missing the narration template — verify `demos/NARRATION_TEMPLATE.md` exists and that all 3 demos follow it (regex match on stage markers).
- [ ] **User-facing docs refresh:** Often missing a screenshot of the actual GUI — verify `docs/assets/screenshots/scene-editor.png` exists, is <500KB, and shows the new GUI (not a wireframe).
- [ ] **User-facing docs refresh:** Often missing a CONTRIBUTING.md "How to add a new scene" walkthrough — verify the section exists and the example command (`surg-rl generate --template suturing --output scenes/foo.json`) works end-to-end.
- [ ] **User-facing docs refresh:** Often missing a CHANGELOG entry for v0.5.0 — verify `CHANGELOG.md` has a `## [0.5.0]` section with at least the GUI, demos, and tech-debt-cleanup bullets.
- [ ] **Tech debt foundation:** Often missing the 421 ruff cleanup PR — verify `ruff check src/surg_rl/dreamer/` returns 0 issues. Add a CI lint gate that fails the build if ruff reports new issues in `src/surg_rl/dreamer/`.
- [ ] **Tech debt foundation:** Often missing the HARD-fixture env-construction test — verify `tests/integration/test_hard_suturing_env.py` exists, constructs a `SurgicalEnv` from `tests/fixtures/scenes/suturing_difficulty_hard.json`, and asserts a `reset()` succeeds.
- [ ] **Tech debt foundation:** Often missing the PhiFlow multi-obstacle union() workaround test — verify the workaround in `dynamics/fluid.py` (or wherever) is exercised by a test that constructs ≥2 obstacles and asserts the merged SDF is non-zero in the union region.

---

## Recovery Strategies

When a pitfall occurs despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| **MuJoCo GL context on wrong thread** | HIGH (requires re-architecting the worker) | Symptom: viewport freezes after frame 0. Step 1: confirm via `lldb`/`print` that the worker's `step` is on a different thread. Step 2: switch to the QMutex-protected swap pattern (Prevention code above). Step 3: re-run the visual regression test. |
| **PyBullet native window stealing focus** | MEDIUM (one-line change + a flag) | Symptom: PyBullet window appears over Qt. Step 1: change `p.GUI` to `p.DIRECT` in the PyBullet constructor. Step 2: re-render the scene via `getCameraImage` into a `QLabel`. Step 3: add a `--pybullet-debug` flag for advanced users. |
| **API key leaked in scene JSON committed to git** | MEDIUM (git history rewrite + key rotation) | Step 1: `git filter-repo --replace-text expressions.txt` to scrub the key. Step 2: force-push (coordinate with team). Step 3: rotate the API key with the provider. Step 4: add a pre-commit hook that grep-checks for key patterns. |
| **Eager PySide6 import broke headless install** | LOW (revert the import + add LazyImport) | Step 1: `git revert` the import. Step 2: refactor to use `LazyImport("PySide6.QtCore", "gui")`. Step 3: re-run the CI matrix. Step 4: add a test that asserts `python -c "import surg_rl"` does not import PySide6. |
| **Schema walker drifted from schema** | HIGH (regression test reveals dozens of broken fields) | Step 1: the parametrized round-trip test catches all broken fields. Step 2: update the `FieldRenderer` registry. Step 3: re-run the test. Step 4: audit recent schema PRs for missing renderers. |
| **Demo narration drift** | LOW (rewriting text) | Step 1: read all 3 narrations in one sitting. Step 2: pick the template-compliant one. Step 3: rewrite the others to match. Step 4: run the narration regex test. |
| **Tech-debt cleanup (421 ruff) caused a regression** | MEDIUM (revert the auto-fix, re-apply selectively) | Step 1: `git revert` the ruff PR. Step 2: identify the offending rule (F841, B904, or E402). Step 3: re-apply ruff with `--select F841 --fix` only. Step 4: re-run the test suite per file. |

---

## Pitfall-to-Phase Mapping

How the v0.5.0 roadmap phases should address these pitfalls. Phase numbering follows PROJECT.md: Phase 31 (tech-debt foundation), 32 (demos), 33 (GUI marquee), 34 (docs), 35 (advanced tech debt).

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| **P1: MuJoCo GL context thread affinity** | **Phase 33** (worker skeleton); **Phase 31** (mjpython re-exec helper) | `test_gui_lifecycle.py` + visual regression test on macOS under mjpython |
| **P2: PyBullet GUI thread + focus stealing** | **Phase 33** (worker skeleton, `p.DIRECT` default) | `test_pybullet_direct_only.py` asserts no `p.GUI` call in the GUI code path |
| **P3: Pydantic v2 round-trip + `_FloatMixin`** | **Phase 33** (`scene_to_jsonable`/`scene_from_jsonable` helpers + parametrized test) | `test_scene_round_trip.py` walks all 63 schema models |
| **P4: 63-class schema walker rot** | **Phase 33** (`SchemaWalker` class + `FieldRenderer` registry) | `test_schema_walker.py` constructs a `SceneDefinition` with all 63 model types and asserts coverage |
| **P5: API key handling** | **Phase 33** (in-memory storage + redactor + `safe_error_message`) | `test_redactor.py` + pre-commit hook for `api_key` grep |
| **P6: Optional-dependency regression** | **Phase 31** (`[gui]` extra + `pytest.importorskip`); **Phase 33** (LazyImport in `surg_rl.gui`) | CI matrix: `pip install surg-rl` (no extras) passes the full headless suite |
| **P7: Tree editor partial-edit corruption** | **Phase 33** (draft/live split + worker pause/resume) | `test_apply_during_step.py` triggers Apply mid-step and asserts no stale observation |
| **P8: Demo narration drift** | **Phase 32** (`NARRATION_TEMPLATE.md` first, then demos) | `test_narration_template.py` regex-validates all 3 demos |
| **P9: `[gui]` extra bloat** | **Phase 31** (define extras; no `[all]`) | CI matrix: `pip install surg-rl` (no extras) does not install PySide6 |
| **P10: GUI as Typer subcommand** | **Phase 31** (`surg-rl-gui` console script); **Phase 33** (the actual app) | `surg-rl train` does not import PySide6 (verified by import-time test) |

### Phase-specific warnings (cross-referenced to existing deferred items)

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| **Tech-debt 421 ruff cleanup** | Auto-fix changes behavior in subtle ways (especially B904 exception chaining) | Re-run the full test suite after each batch; do not `--fix` all 421 at once; group by rule |
| **Dockerfile.ros2 amd64 hardcode** | The fix may break arm64 CI; verify the matrix still works | Run the Docker CI matrix after the fix; add a "build only amd64" + "build only arm64" smoke test |
| **Fluid step hook in `base_simulator.py`** | Adding a `step_hook` callback to the ABC breaks MuJoCo and PyBullet subclasses that override `step` | Add the hook as an opt-in kwarg with a default of `None`; the subclasses call `_apply_fluid_step_hook()` only if the hook is set |
| **Cut cooldown unit test** | The test must exercise the env, not just the cooldown arithmetic, to catch regression where the cooldown is bypassed | Construct a `SurgicalEnv` from a suturing scene; issue a cut action; assert a second cut within 500ms is rejected |
| **PhiFlow multi-obstacle union() workaround** | The merged SDF workaround may leak memory on long episodes; profile first | Add a `pytest.mark.slow` test that runs 1000 steps with ≥2 obstacles and asserts memory growth <100MB |
| **HARD-fixture env-construction test** | The HARD scene may have a different `num_controls` than EASY/MEDIUM, breaking any env that assumes a fixed action space | Make the test assert the action space shape, not just that `reset()` returns |

---

## Existing Pitfalls (from PROJECT.md) — Re-evaluation for v0.5.0 Context

The PROJECT.md lists 11 existing pitfalls. Each is re-evaluated below for relevance to the v0.5.0 milestone (Scene Editor & UX Polish).

| Existing Pitfall | Re-evaluation for v0.5.0 | Action |
|------------------|-------------------------|--------|
| **MuJoCo `_model` private attr** | **Highly relevant.** The GUI's worker must access `_model` for state queries; the new `applyScene` flow must reload the model correctly on the right thread. | P1's `QMutex` pattern protects the access; P2's PyBullet-`_physics_client` pattern is analogous. |
| **PyBullet `_physics_client` private attr** | **Highly relevant.** The GUI's worker must access the client; p.DIRECT construction ensures thread affinity. | P2 covers this. |
| **simulator.load_scene() before reset()/step()** | **Highly relevant.** The GUI's Apply flow = `load_scene → reset()`. If the form editor sends Apply before the worker has paused, `load_scene` runs while `_simulation_time > 0` → undefined behavior. | P7's pause/resume pattern enforces ordering. |
| **Scene assets do not exist (primitive fallback)** | **Moderately relevant.** The GUI's "preview" button must show the primitive fallback, not crash. The 3D viewport should render whatever the scene_builder generates. | No new prevention; the existing primitive fallback is the right behavior. Document in the GUI's "About" dialog. |
| **PyBullet soft body `RESET_USE_DEFORMABLE_WORLD` + `removeBody` unsafe** | **Moderately relevant.** If the GUI lets the user edit a soft-body scene and Apply mid-step, `removeBody` could be called incorrectly. | P7's pause/resume + the existing PyBullet subclass's `_soft_body_ids` guard are the protections. Add a regression test for soft-body scene Apply. |
| **`_get_vtk_mesh_path()` procedural fallback** | **Low relevance.** The GUI doesn't touch the mesh path generation. | No action. |
| **Lazy imports for optional deps** | **Highly relevant.** P6 and P9 are direct consequences. | Phase 31's `[gui]` extra; P10's `surg-rl-gui` console script. |
| **Cross-package Pydantic v2 cycle resolution** | **Moderately relevant.** The GUI's `SchemaWalker` introspects the schema; a new GUI module could re-introduce a cycle. | Document the cycle pattern in `gui/README.md`; the schema walker uses `TypeAdapter` (not direct imports) for safety. |
| **14 existing CLI subcommands backwards compat** | **Highly relevant.** P10. | P10's `surg-rl-gui` console script preserves backwards compat. |
| **`SurgicalEnv.passthrough_step()` MARL adapter** | **Low relevance.** The GUI's scope is scene editing + LLM generation, not training. The 3 demos may use MARL but that's at the env level, not the GUI level. | No new action; existing tests cover this. |
| **`_JsonStdout` wrapper for DreamerV3 subprocess** | **Low relevance.** The GUI doesn't run DreamerV3 in v0.5.0. | No action. |

---

## Sources

- **Context7 (PySide6 Qt for Python, `/websites/doc_qt_io_qtforpython-6`):** Worker QObject pattern, QThread signals/slots, `paintGL` lifecycle, `QObject.deleteLater` chaining — verified HIGH confidence.
- **Context7 (MuJoCo, `/google-deepmind/mujoco`):** `mujoco.GLContext` single-thread-affine contract, `mjr_makeContext` requires current GL context, macOS CGL bypass for offscreen rendering — verified HIGH confidence.
- **Context7 (Pydantic, `/pydantic/pydantic`):** `model_dump(mode="json")` enum handling, `model_validate(strict=False)` coercion — verified HIGH confidence.
- **Existing project code:**
  - `src/surg_rl/simulators/base_simulator.py` — ABC pattern, `Observation`/`State`/`StepResult` contracts
  - `src/surg_rl/cli.py` — 14 Typer subcommands, Rich logging, optional-dep error handling pattern
  - `src/surg_rl/utils/lazy_imports.py` — `LazyImport` class for optional deps
  - `src/surg_rl/scene_definition/schema.py` — 63 Pydantic classes, `_FloatMixin(float, Enum)` pattern from v0.4.2
  - `tests/test_mjpython_detection.py` — existing mjpython detection on macOS
  - `pyproject.toml` — existing optional-dependency groups pattern
- **GSD project context:**
  - `.planning/PROJECT.md` — v0.5.0 milestone scope, 5-phase plan, 11 existing pitfalls
  - `.planning/STATE.md` — v0.4.2 close state, accumulated context decisions, deferred items list
- **LOW confidence (flagged):**
  - PyBullet GUI thread safety — no Context7 library; based on PyBullet public docs and the existing `pybullet_simulator.py` patterns. The `p.DIRECT`-only recommendation is conservative; the team should validate on Linux + macOS before shipping.
  - Qt 6.5+ behavior on macOS Apple Silicon under `mjpython` — Qt 6.5+ has improved CGL support, but the combination with `mjpython` is not well-documented. The QMutex + thread-affinity pattern is the safest approach.

---

*Pitfalls research for: Surg-RL v0.5.0 Scene Editor & UX Polish*
*Researched: 2026-06-18*

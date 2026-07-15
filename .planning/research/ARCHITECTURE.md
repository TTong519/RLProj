# Architecture Research: v0.7.0 — GUI Editor Depth & Scene Generation

**Domain:** Surgical-robotics RL training system — PySide6 scene editor depth (render/sim-decoupled viewport, multi-view, lighting, gizmos, recording, editing UX, file/IO, perf/stability) + scene generation expansion (VLM image→scene, LLM clarifying-question flow, procedural/batch gen, more templates)
**Researched:** 2026-07-15
**Confidence:** HIGH (integration points verified against existing source code in `src/surg_rl/editor/`, `src/surg_rl/simulators/`, `src/surg_rl/scene_generation/`; render/sim decoupling pattern verified against Qt official docs + MuJoCo+PySide6 community gists; VLM structured-outputs pattern verified against OpenAI cookbook)

## Executive Summary

v0.7.0 deepens the existing PySide6 scene editor and expands scene generation. The architectural keystone is **render/sim decoupling**: the current `ViewportPanel._tick()` couples a `simulator.render()` call to the 20 Hz `QTimer.singleShot(50ms)` self-rescheduling loop, and critically, **never calls `simulator.step()`** — so the preview is immobile (the scene never advances) and the frame rate collapses below 10 fps because each `_tick` blocks the Qt event loop for the full render duration with no parallelism. The fix is to split the sim-stepping loop from the render-polling loop: a `SimStepWorker(QObject)` on a `QThread` advances the simulation at a configurable rate (independent of render cadence), emits `stepped` signals carrying a lightweight state snapshot, and the UI-thread render loop polls `simulator.render()` at its own cadence — decoupled from physics step duration.

The three known GUI bugs map to three distinct architectural fixes: (1) **<10fps** — the render/sim coupling means the render call blocks the event loop; decoupling + raising the timer cadence from 50ms (20fps theoretical) toward vsync-locked rendering fixes this; (2) **immobile preview** — `_tick()` never calls `simulator.step()`, so adding a sim-step loop with a zero-action (or gravity-only) step animates the scene; (3) **dock-panel layout reset on rerun** — `_refresh_viewport_and_tree()` destroys and recreates the `ViewportPanel` and `SceneTreeView` but does NOT save/restore dock state, so the `QMainWindow.restoreState()` call in `_restore_geometry()` runs against a fresh dock set whose `objectName`s match but whose geometry has been reset by the central-widget swap. The fix is to preserve dock widgets across scene reloads (swap the viewport's scene reference, not the `ViewportPanel` instance) and save dock state before any central-widget swap.

Scene generation integration builds on the existing `BaseParser`/`TextParser`/`VisionParser`/`SceneComposer` hierarchy. The VLM image→scene feature extends `VisionParser` with OpenAI Structured Outputs (`response_format: json_schema`) using `SceneDefinition.model_json_schema()` as the enforcement schema — no new parser class needed, just a new code path in `_call_vlm_async()`. The LLM clarifying-question flow adds a multi-turn conversation mode to `TextParser` (conversation state list + tool-calling for scene modifications) surfaced as a chat-style UI in `LLMPanel`. Procedural/batch generation extends `SceneComposer` with a `generate_batch()` method parameterizing templates over difficulty/instrument/organ axes. More templates is additive to `templates.py`'s existing registry (`get_template()`/`list_templates()`).

Build order respects dependencies: **GUI first, scene generation second** (per milestone context). Within GUI, the dependency chain is: render/sim decoupling (GUI-11) is the foundation that all other viewport features depend on (multi-view, gizmos, recording all need a responsive viewport); perf/stability + bug fixes (GUI-15) fold into GUI-11 since the three bugs share the decoupling root cause; then multi-view/lighting/gizmos/recording (GUI-12/13/14) build on the decoupled loop; editing UX + file/IO (GUI-14/15) are independent of the viewport and can proceed in parallel. Scene generation (GEN-01..05) follows after GUI is stable.

## System Overview — v0.7.0 Target State

```
                           ┌──────────────────────────────────────────┐
                           │              CLI Layer                     │
                           │  surg-rl-gui [EXISTING, --scene flag]     │
                           │  surg-rl generate [EXTENDED: --image]     │
                           │  surg-rl generate --batch [NEW]           │
                           └──────────────┬───────────────────────────┘
                                          │
        ┌─────────────────────────────────┼──────────────────────────────┐
        ▼                                 ▼                              ▼
┌────────────────────────┐   ┌─────────────────────────┐   ┌────────────────────────┐
│      editor/            │   │    scene_generation/    │   │    simulators/         │
│  (DEEPEN existing)      │   │  (EXTEND existing)      │   │  (EXTEND render API)   │
│                        │   │                         │   │                        │
│  EditorWindow           │   │  BaseParser [UNCHANGED] │   │  BaseSimulator         │
│  ├─ ViewportPanel       │   │  TextParser [+clarify]  │   │   ├─ render() [EXTEND] │
│  │   ├─ ViewportCanvas  │   │  VisionParser [+VLM SO] │   │   │   +camera params    │
│  │   ├─ SimStepWorker ◀─┼───┼─│  SceneComposer          │   │   │   +light params     │
│  │   │   (NEW, QThread) │   │  │   [+generate_batch]    │   │   │   +gizmo overlay    │
│  │   ├─ RenderPollLoop  │   │  Templates [+more]       │   │   │                    │
│  │   │   (MODIFIED tick)│   │                         │   │  MuJoCoSimulator       │
│  │   ├─ MultiViewMgr    │   │  [NEW] ClarifyFlow       │   │   ├─ render() [EXTEND] │
│  │   │   (NEW)          │   │   (conversation state)   │   │   │   +mjvOption flags  │
│  │   ├─ GizmoOverlay    │   │  [NEW] BatchGenerator    │   │   │   +light XML       │
│  │   │   (NEW)          │   │   (param sweep)           │   │  PyBulletSimulator    │
│  │   └─ FrameRecorder   │   │                         │   │   ├─ render() [EXTEND] │
│  │       (NEW)          │   │                         │   │   │   +light params     │
│  ├─ SceneTreeView       │   │                         │   │   │   +shadow toggle    │
│  ├─ PropertyForm        │   │                         │   │                        │
│  ├─ LLMPanel            │   │                         │   │                        │
│  │   [+chat mode]       │   │                         │   │                        │
│  ├─ VLMPanel (NEW)      │   │                         │   │                        │
│  ├─ SceneUndoStack      │   │                         │   │                        │
│  └─ DockStateMgr (NEW)  │   │                         │   │                        │
└────────────────────────┘   └─────────────────────────┘   └────────────────────────┘
        │                                 │                              │
        └─────────────────────────────────┴──────────────────────────────┘
                                          │
                                          ▼
                              ┌──────────────────────┐
                              │   BaseSimulator ABC  │
                              │   load_scene/reset/  │
                              │   step/render/       │
                              │   get_state/set_state│
                              └──────────────────────┘
```

## Component Responsibilities (NEW + MODIFIED)

### Editor Package — GUI Depth

| Component | Responsibility | Status | Location |
|-----------|----------------|--------|----------|
| `editor/viewport.py` — `ViewportPanel` | Render-poll loop: polls `simulator.render()` at its own cadence, decoupled from sim stepping; displays frames via `ViewportCanvas` | **MODIFIED** (split `_tick` into render-poll + sim-step) | `src/surg_rl/editor/viewport.py` |
| `editor/viewport.py` — `ViewportCanvas` | Custom QWidget receiving mouse/wheel events; paints QPixmap from render bridge | **UNCHANGED** (stable, reliable event delivery) | `src/surg_rl/editor/viewport.py` |
| `editor/sim_step_worker.py` — `SimStepWorker` | QObject moved to QThread; advances `simulator.step()` at configurable sim-rate; emits `stepped` signal with state snapshot; supports pause/resume/step-one | **NEW** | `src/surg_rl/editor/sim_step_worker.py` |
| `editor/render_poll_loop.py` — `RenderPollLoop` | QObject on UI thread; QTimer-driven (or vsync-driven) render polling at target fps; calls `simulator.render()` and pushes QPixmap to ViewportCanvas via signal | **NEW** (extracted from `_tick`) | `src/surg_rl/editor/render_poll_loop.py` |
| `editor/multi_view.py` — `MultiViewManager` | Manages N viewport panels (split-screen or tabbed) each with independent camera offsets; drives multiple `render()` calls with different camera_name/params per view | **NEW** | `src/surg_rl/editor/multi_view.py` |
| `editor/gizmo_overlay.py` — `GizmoOverlay` | Translates user clicks/drags on the viewport into body pose mutations; renders gizmo handles (translate/rotate axes) as an overlay composited in `ViewportCanvas.paintEvent` or via the render bridge's gizmo-mode | **NEW** | `src/surg_rl/editor/gizmo_overlay.py` |
| `editor/frame_recorder.py` — `FrameRecorder` | Captures rendered frames (numpy arrays) and encodes to video via `QMediaRecorder` + `QVideoFrameInput` (Qt 6.8+, FFmpeg backend) or fallback to image-sequence dump | **NEW** | `src/surg_rl/editor/frame_recorder.py` |
| `editor/dock_state.py` — `DockStateManager` | Saves/restores QMainWindow dock state via `saveState()`/`restoreState()`; ensures unique `objectName` on every dock; preserves dock layout across scene reloads (the bug fix) | **NEW** | `src/surg_rl/editor/dock_state.py` |
| `editor/llm_panel.py` — `LLMPanel` | Existing text→scene panel; extended with chat-mode UI for multi-turn clarifying-question flow | **MODIFIED** (add chat mode) | `src/surg_rl/editor/llm_panel.py` |
| `editor/vlm_panel.py` — `VLMPanel` | Image-upload → scene panel; calls `VisionParser.parse_sync()` with Structured Outputs; preview + accept/reject (mirrors LLMPanel) | **NEW** | `src/surg_rl/editor/vlm_panel.py` |
| `editor/main_window.py` — `EditorWindow` | QMainWindow shell; wires new panels; preserves dock state across scene reloads | **MODIFIED** (fix `_refresh_viewport_and_tree` to not destroy dock layout) | `src/surg_rl/editor/main_window.py` |
| `editor/_settings.py` — `EditorSettings` | QSettings wrapper; extends with dock-state save/restore keys + viewport settings (fps target, sim-rate, lighting) | **MODIFIED** (add dock-state + viewport prefs) | `src/surg_rl/editor/_settings.py` |

### Simulator Package — Render API Extensions

| Component | Responsibility | Status | Location |
|-----------|----------------|--------|----------|
| `simulators/base_simulator.py` — `BaseSimulator.render()` | Abstract render method; extend signature with optional `camera_params`, `light_params`, `render_flags` kwargs (additive, backwards-compatible) | **MODIFIED** (extend signature) | `src/surg_rl/simulators/base_simulator.py` |
| `simulators/mujoco_simulator.py` — `MuJoCoSimulator.render()` | MuJoCo offscreen render; extend to accept camera params (azimuth/elevation/distance/target), light params (via XML or `mjvScene` light slots), render flags (shadows/wireframe/fog via `mjvScene.flags`), and optional gizmo-overlay mode | **MODIFIED** (add param plumbing) | `src/surg_rl/simulators/mujoco_simulator.py` |
| `simulators/pybullet_simulator.py` — `PyBulletSimulator.render()` | PyBullet offscreen render; extend to accept light params (limited — PyBullet has no fine-grained light positioning; use shadow toggle + renderer enum), camera params (already partially via `_editor_camera_*` attrs), and multi-view via multiple `getCameraImage` calls | **MODIFIED** (add param plumbing) | `src/surg_rl/simulators/pybullet_simulator.py` |

### Scene Generation Package — Generation Expansion

| Component | Responsibility | Status | Location |
|-----------|----------------|--------|----------|
| `scene_generation/base_parser.py` — `BaseParser` | ABC for parsers; unchanged (parse/parse_with_context/validate_scene already sufficient) | **UNCHANGED** | `src/surg_rl/scene_generation/base_parser.py` |
| `scene_generation/text_parser.py` — `TextParser` | LLM text→scene; extend with `clarify()` method for multi-turn conversation + `parse_with_clarification()` orchestrator; use tool-calling for scene modifications | **MODIFIED** (add clarify flow) | `src/surg_rl/scene_generation/text_parser.py` |
| `scene_generation/vision_parser.py` — `VisionParser` | VLM image→scene; extend `_call_vlm_async()` to use OpenAI Structured Outputs (`response_format: json_schema`) with `SceneDefinition.model_json_schema()` as the enforcement schema; add Anthropic + Ollama structured paths | **MODIFIED** (add structured-outputs code path) | `src/surg_rl/scene_generation/vision_parser.py` |
| `scene_generation/scene_composer.py` — `SceneComposer` | Scene merging; extend with `generate_batch()` method that parameterizes a template over difficulty/instrument/organ axes and produces N scenes | **MODIFIED** (add batch generation) | `src/surg_rl/scene_generation/scene_composer.py` |
| `scene_generation/templates.py` | Template registry; add more task templates (expand beyond current 8: suturing, dissection, manipulation, anastomosis, biopsy, debridement, cauterization, retraction) | **MODIFIED** (additive) | `src/surg_rl/scene_generation/templates.py` |
| `scene_generation/clarify_flow.py` — `ClarifyFlow` | Conversation-state manager for multi-turn LLM clarification; tracks slots (missing scene fields), decides ask-vs-generate, calls `TextParser._call_llm_async()` per turn | **NEW** | `src/surg_rl/scene_generation/clarify_flow.py` |
| `scene_generation/batch_generator.py` — `BatchGenerator` | Parameterized procedural scene generation; takes a template name + axis spec (difficulty levels, instrument sets, organ configs) and yields N `SceneDefinition` objects; wraps `SceneComposer.generate_batch()` | **NEW** | `src/surg_rl/scene_generation/batch_generator.py` |

## Recommended Project Structure — v0.7.0 Changes

```
src/surg_rl/
├── editor/                              # DEEPEN existing
│   ├── __init__.py                      # UNCHANGED (HAS_GUI sentinel)
│   ├── _platform_guard.py               # UNCHANGED
│   ├── _safe_error.py                   # UNCHANGED
│   ├── _settings.py                     # MODIFIED (+dock-state, +viewport prefs)
│   ├── app.py                           # UNCHANGED (entrypoint)
│   ├── main_window.py                   # MODIFIED (dock preservation, new panel wiring)
│   ├── viewport.py                      # MODIFIED (split tick → render-poll + sim-step)
│   ├── sim_step_worker.py               # NEW — QThread physics stepper
│   ├── render_poll_loop.py             # NEW — UI-thread render polling (vsync-aware)
│   ├── multi_view.py                   # NEW — multi-camera viewport manager
│   ├── gizmo_overlay.py                # NEW — translate/rotate gizmo handles
│   ├── frame_recorder.py              # NEW — QMediaRecorder video capture
│   ├── dock_state.py                   # NEW — saveState/restoreState wrapper
│   ├── tree_view.py                     # UNCHANGED
│   ├── property_form.py                 # UNCHANGED
│   ├── schema_walker.py                 # UNCHANGED
│   ├── field_renderer.py               # UNCHANGED
│   ├── llm_panel.py                    # MODIFIED (+chat mode for clarify flow)
│   ├── vlm_panel.py                     # NEW — image→scene panel
│   └── undo_stack.py                    # UNCHANGED
├── scene_generation/                    # EXTEND existing
│   ├── __init__.py                      # UNCHANGED
│   ├── base_parser.py                   # UNCHANGED
│   ├── text_parser.py                   # MODIFIED (+clarify flow methods)
│   ├── vision_parser.py                 # MODIFIED (+structured outputs path)
│   ├── scene_composer.py               # MODIFIED (+generate_batch)
│   ├── templates.py                     # MODIFIED (+more templates)
│   ├── clarify_flow.py                 # NEW — multi-turn conversation manager
│   ├── batch_generator.py             # NEW — procedural batch generation
│   └── prompts/                         # MODIFIED (+clarify prompts, +VLM prompts)
├── simulators/                          # EXTEND render API
│   ├── base_simulator.py               # MODIFIED (render() signature extension)
│   ├── mujoco_simulator.py             # MODIFIED (+camera/light/flag params)
│   ├── pybullet_simulator.py           # MODIFIED (+camera/light/flag params)
│   └── scene_builder.py                # UNCHANGED
```

### Structure Rationale

- **`editor/sim_step_worker.py` (NEW, separate file):** The sim-step QThread worker is the keystone of render/sim decoupling. Keeping it in its own module makes it independently testable (instantiate worker + mock simulator, assert step calls + signal emissions) without importing any Qt widget.
- **`editor/render_poll_loop.py` (NEW, separate file):** The render-poll loop replaces the current `_tick()` body. Extracting it from `viewport.py` allows swapping the timer strategy (QTimer vs vsync-driven) without touching the ViewportPanel/ViewportCanvas widget code.
- **`editor/multi_view.py`, `gizmo_overlay.py`, `frame_recorder.py` (NEW, separate files):** Each viewport-depth feature is a self-contained manager that the ViewportPanel composes. This follows the existing pattern where `ViewportPanel` composes `ViewportCanvas` — each new feature is a composable unit, not a god-class.
- **`editor/dock_state.py` (NEW):** The dock-state persistence bug fix is isolated so it can be tested without instantiating the full QMainWindow (test save/restore round-trip with a minimal QMainWindow + dummy docks).
- **`scene_generation/clarify_flow.py`, `batch_generator.py` (NEW):** Both are pure-Python (no Qt) so they are testable in headless CI. The GUI panels (`LLMPanel`, `VLMPanel`) are thin Qt wrappers that call these workers via QThread — same pattern as the existing `TextParserWorker`.

## Architectural Patterns

### Pattern 1: Render/Sim Decoupling via QThread Worker (THE keystone pattern)

**What:** Split the current monolithic `_tick()` (which calls `render()` and reschedules) into two independent loops: a `SimStepWorker` on a QThread that advances physics, and a `RenderPollLoop` on the UI thread that renders at its own cadence.

**When to use:** Whenever the render call duration is non-trivial relative to the target frame interval. The current 50ms timer + blocking render = <20fps theoretical, and with render taking 80-120ms on macOS software-rendered PyBullet, actual fps drops below 10.

**Why this works:**
- Physics stepping (`mj_step` / `pybullet.stepSimulation`) is CPU-bound and fast (~1-2ms per step); rendering is GPU/CPU-bound and slow (~50-120ms offscreen). Coupling them means the slow operation gates the fast one.
- Decoupling lets the sim advance at a fixed sim-rate (e.g., 50 Hz sim, 30 Hz render) while the render loop polls the latest sim state at its own pace.
- The Qt event loop stays responsive because the render-poll loop uses `QTimer.singleShot(0)` after each frame (yielding to the event loop between frames), and the sim-step worker is on a separate thread entirely.

**Trade-offs:**
- + Render rate independent of sim rate (sim can run at 50 Hz physics, render at 30 Hz display)
- + Qt event loop stays responsive (no blocking during render)
- + Scene animates (sim.step() is actually called, unlike current code)
- - Slight complexity: thread-safe state sharing between sim worker and render loop (use signal/slot queued connections — Qt's default cross-thread connection is thread-safe)
- - Sim state may advance between render frames (render shows a snapshot, not every sim state — acceptable for a preview editor)

**Implementation sketch:**
```python
# editor/sim_step_worker.py
class SimStepWorker(QObject):
    stepped = Signal(object)  # carries lightweight State snapshot or None

    def __init__(self, simulator: BaseSimulator, sim_rate_hz: float = 50.0):
        super().__init__()
        self._sim = simulator
        self._interval_ms = int(1000 / sim_rate_hz)
        self._timer = QTimer()
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.timeout.connect(self._step)
        self._running = False
        self._zero_action = None  # np.zeros(num_controls) for gravity-only step

    def start(self):
        if not self._running:
            self._running = True
            self._timer.start(self._interval_ms)

    def stop(self):
        self._running = False
        self._timer.stop()

    @Slot()
    def _step(self):
        if self._sim is None or not self._sim._loaded:
            return
        try:
            self._sim.step(self._zero_action)  # gravity-only step for preview
            self.stepped.emit(None)  # signal render loop it can poll
        except Exception:
            pass  # swallow — editor preview should not crash on sim errors

# editor/render_poll_loop.py
class RenderPollLoop(QObject):
    frame_ready = Signal(QPixmap)

    def __init__(self, simulator, canvas, target_fps=30.0):
        super().__init__()
        self._sim = simulator
        self._canvas = canvas
        self._timer = QTimer()
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.timeout.connect(self._render_frame)
        self._interval_ms = int(1000 / target_fps)

    def start(self):
        self._timer.start(self._interval_ms)

    def stop(self):
        self._timer.stop()

    @Slot()
    def _render_frame(self):
        arr = self._sim.render(mode="rgb_array",
                               width=self._canvas.width(),
                               height=self._canvas.height())
        if arr is not None:
            self.frame_ready.emit(self._array_to_pixmap(arr))
```

**Integration with existing `ViewportPanel`:**
- `ViewportPanel.__init__` creates a `SimStepWorker`, moves it to a `QThread`, and connects `stepped` → (optional state-sync slot).
- `ViewportPanel._start()` starts both the `SimStepWorker` thread and the `RenderPollLoop`.
- `ViewportPanel.stop()` stops both loops and quits the QThread.
- The existing `_editor_camera_*` attr-pushing logic stays — it's pushed before each render call in the render-poll loop (same as current `_tick`), not in the sim-step worker.

### Pattern 2: Multi-View via Multiple Render Calls (not multiple GL contexts)

**What:** Multi-view is implemented as N `simulator.render()` calls with different camera parameters per view, each rendered to a separate `ViewportCanvas` or a split-screen region of a single canvas. NOT as multiple `QOpenGLWidget` instances with shared GL contexts.

**When to use:** When the render pipeline is offscreen-numpy-based (current architecture: `render() → np.ndarray → QImage → QPixmap → ViewportCanvas.paintEvent`). Multiple GL contexts would require migrating to `QOpenGLWidget`, which is a larger architectural change.

**Why this choice:**
- The current architecture is numpy-pipeline-based (offscreen render → QImage → QPixmap). Adding multiple GL contexts would require a full migration to `QOpenGLWidget` with shared contexts — a rewrite of the render bridge, not an extension.
- Multiple `render()` calls per frame (one per view) are additive: each view is a new `ViewportCanvas` + a render call with different camera params. The sim-step worker is shared across all views (one sim, many cameras).
- MuJoCo supports this natively: `update_scene(data, camera=cam_id)` per view, then `render()` per view. PyBullet supports it via multiple `getCameraImage` calls with different view matrices.
- Performance: N render calls per frame at ~50-120ms each means N views × render time. For 2 views at 60ms each = 120ms/frame = ~8fps. This is the same problem the decoupling solves — the render calls go on the UI thread's render-poll loop, and the event loop stays responsive because they yield between calls.

**Trade-offs:**
- + No GL context migration (stays in the numpy-pipeline architecture)
- + Additive: each view is a new canvas + render call
- - N render calls per frame can drop fps (mitigate: lower per-view resolution, or stagger views across frames)
- - Cannot share GPU textures between views (each render call produces an independent numpy array)

**Implementation sketch:**
```python
# editor/multi_view.py
class MultiViewManager(QObject):
    def __init__(self, simulator, target_fps=30.0):
        self._sim = simulator
        self._views: list[tuple[ViewportCanvas, _CameraOffset]] = []
        self._render_loop = RenderPollLoop(simulator, None, target_fps)
        self._render_loop.frame_ready = None  # disconnect default
        self._render_loop._render_frame = self._render_all_views

    def add_view(self, canvas: ViewportCanvas, camera: _CameraOffset):
        self._views.append((canvas, camera))

    def _render_all_views(self):
        for canvas, cam in self._views:
            self._push_camera_params(cam)
            arr = self._sim.render(mode="rgb_array",
                                   width=canvas.width(), height=canvas.height())
            if arr is not None:
                canvas.set_image(self._array_to_pixmap(arr))
```

### Pattern 3: Gizmo Overlay via Render Bridge (not Qt widget)

**What:** Gizmo handles (translate/rotate axes) are rendered in the offscreen render pipeline as an overlay on top of the scene, not as Qt widgets composited in `paintEvent`. The render bridge gets a `gizmo_target` param (body name + mode) and draws the gizmo handles into the framebuffer before returning the numpy array.

**When to use:** When the viewport is numpy-pipeline-based (offscreen render → QImage). Drawing gizmos as Qt widgets on top of the pixmap would require 2D-to-3D coordinate projection (screen-space gizmo handles → 3D world-space body), which is fragile and doesn't track camera changes. Rendering gizmos in the 3D pipeline keeps them in world space automatically.

**Why this choice:**
- MuJoCo: `mjvOption` flags can add visualization primitives (contact points, forces, etc.). Gizmo handles can be drawn as additional geoms in the `mjvScene` before `mjr_render()`. The gizmo is in world space, tracks the camera, and scales with distance (constant apparent size is a one-line calculation).
- PyBullet: No native gizmo support. Gizmo handles must be drawn as debug lines (`addUserDebugLine`) or as small debug objects (`addUserDebugText` / `createMultiBody` with line shapes). This is more limited but works for basic translate/rotate axes.
- Compositing in `paintEvent` (2D overlay) would require projecting 3D body positions to 2D screen coordinates — a manual matrix multiply with the view+projection matrices. This duplicates the render pipeline's own projection and is fragile when camera params change.

**Trade-offs:**
- + Gizmos in world space (automatic camera tracking, depth occlusion)
- + No 2D-to-3D projection needed
- - PyBullet gizmo support is limited (debug lines only, no torus rings for rotation)
- - Requires per-backend gizmo rendering code (MuJoCo: mjvScene geoms; PyBullet: debug lines)

**Implementation sketch:**
```python
# In MuJoCoSimulator.render() — extend:
def render(self, ..., gizmo_target: str | None = None, gizmo_mode: str = "translate"):
    ...
    if gizmo_target is not None:
        self._draw_gizmo(self._renderer, gizmo_target, gizmo_mode)
    rgb = self._renderer.render()
    return rgb

def _draw_gizmo(self, renderer, body_name, mode):
    # Add gizmo geoms (axis lines + cones for translate, torus for rotate)
    # to the mjvScene before render. Constant apparent size:
    # scale = camera_distance * 0.1
    ...
```

### Pattern 4: Dock-State Persistence (the bug fix)

**What:** Save `QMainWindow.saveState()` to `QSettings` on close, restore via `restoreState()` on startup. Critically, do NOT destroy and recreate dock widgets on scene reload — swap the dock's child widget instead.

**When to use:** Always (this is the fix for the dock-panel layout reset bug). The bug's root cause is in `EditorWindow._refresh_viewport_and_tree()`, which creates a new `ViewportPanel` and calls `setCentralWidget()` — this resets the central widget and can cascade dock layout changes.

**The fix:**
1. Every `QDockWidget` already has a unique `objectName` (set in `_build_dock_widgets`: `"dock_scene_tree"`, `"dock_properties"`, `"dock_llm"`). This is correct and required for `saveState()`/`restoreState()` to work.
2. On scene reload (`_refresh_viewport_and_tree`), instead of creating a new `ViewportPanel` and calling `setCentralWidget()` (which destroys the old panel and resets layout), call `self._viewport_panel.update_scene(new_scene)` — a new method on `ViewportPanel` that swaps the scene reference and restarts the sim-step worker with the new scene, without recreating the widget.
3. For `SceneTreeView`, instead of creating a new `SceneTreeView` and calling `self._tree_dock.setWidget()`, call `self._tree_view.update_scene(new_scene)` — a new method that rebuilds the tree model in place.
4. Save dock state before any structural change, restore after.

**Implementation sketch:**
```python
# editor/dock_state.py
class DockStateManager:
    def __init__(self, window: QMainWindow, settings: EditorSettings):
        self._window = window
        self._settings = settings

    def save(self):
        self._settings.save_dock_state(self._window.saveState())

    def restore(self):
        state = self._settings.load_dock_state()
        if state is not None:
            self._window.restoreState(state)

# In EditorWindow._refresh_viewport_and_tree — MODIFIED:
def _refresh_viewport_and_tree(self):
    self._dock_mgr.save()  # save before structural change
    self._viewport_panel.update_scene(self._scene or _empty_scene_stub())  # no recreating
    self._tree_view.update_scene(self._scene or _empty_scene_stub())
    self._dock_mgr.restore()  # restore after
```

### Pattern 5: VLM Image→Scene via Structured Outputs (not freeform JSON)

**What:** Extend `VisionParser._call_vlm_async()` to use OpenAI Structured Outputs (`response_format: {"type": "json_schema", "schema": ...}`) with `SceneDefinition.model_json_schema()` as the enforcement schema, instead of instructing the model to produce JSON and parsing it.

**When to use:** For the VLM image→scene feature (GEN-03). The existing `VisionParser` already sends images as base64 and instructs the model to produce JSON — the improvement is to enforce the schema at the API level so the model cannot produce invalid JSON.

**Why this choice:**
- OpenAI Structured Outputs guarantee schema adherence (not just valid JSON — valid against YOUR schema). This eliminates the `_parse_json_response()` fragile regex/markdown-fence-stripping path.
- `SceneDefinition.model_json_schema()` already exists (Pydantic v2 generates it). The schema is the single source of truth — no schema divergence between code and API.
- The `instructor` library (used in the OpenAI cookbook) simplifies this further, but the raw API path (`response_format`) is sufficient and avoids a new dependency.

**Trade-offs:**
- + Guaranteed schema adherence (no more parse failures from malformed JSON)
- + Single source of truth (Pydantic schema → API schema)
- - OpenAI Structured Outputs requires `gpt-4o-2024-08-06` or later; older models fall back to the existing freeform path
- - Anthropic doesn't have an equivalent strict-schema feature (uses tool-calling for structured output — different code path)
- - Ollama (local models) has no Structured Outputs — must keep the freeform path for Ollama

**Implementation sketch:**
```python
# In VisionParser._call_vlm_async — MODIFIED:
async def _call_vlm_async(self, image_b64, prompt, use_structured=True):
    if self.provider == "openai" and use_structured:
        schema = SceneDefinition.model_json_schema()
        response = await self._client.chat.completions.create(
            model=self.model or "gpt-4o",
            messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                {"type": "text", "text": prompt},
            ]}],
            response_format={"type": "json_schema", "json_schema": {
                "name": "scene_definition", "schema": schema, "strict": True
            }},
        )
        return json.loads(response.choices[0].message.content)
    else:
        # Existing freeform path (Anthropic, Ollama, older OpenAI)
        ...
```

### Pattern 6: LLM Clarifying-Question Flow as Multi-Turn Conversation

**What:** A `ClarifyFlow` class manages a multi-turn conversation state: it tracks which scene fields are missing/ambiguous, asks clarifying questions via `TextParser._call_llm_async()`, accumulates user answers, and generates the scene when all slots are filled or the user says "generate now."

**When to use:** For the interactive LLM clarifying-question flow (GEN-05). The existing `LLMPanel` does single-shot text→scene; the clarify flow adds a chat mode where the LLM can ask follow-up questions.

**Why this design:**
- The conversation state (messages list + filled/missing slots) must be separate from the Qt UI so it's testable headless. `ClarifyFlow` is pure-Python.
- The GUI (`LLMPanel` chat mode) is a thin wrapper: it renders the conversation as a chat-bubble list, sends user messages to `ClarifyFlow.ask()`, and receives `ClarifyFlow.ask_complete` (carrying either a clarifying question or a finished scene) via a QThread worker signal.
- The `ClarQ-LLM` and `ClarifyAgent` research shows that finite-state slot tracking prevents hallucination — the flow knows exactly what's missing and doesn't re-ask filled slots.

**Implementation sketch:**
```python
# scene_generation/clarify_flow.py
class ClarifyFlow:
    ask_complete = Signal(object)  # str (question) or SceneDefinition (done)

    def __init__(self, parser: TextParser):
        self._parser = parser
        self._messages: list[dict] = []
        self._scene_slots: dict[str, bool] = {}  # field_name -> filled?

    async def start(self, user_prompt: str):
        self._messages.append({"role": "user", "content": user_prompt})
        await self._turn()

    async def _turn(self):
        # Ask LLM: "Based on the conversation, either ask ONE clarifying question
        # or generate the scene. Return JSON: {"action": "ask"|"generate", ...}"
        response = await self._parser._call_llm_async(self._build_prompt(), ...)
        parsed = self._parse_response(response)
        if parsed["action"] == "ask":
            self.ask_complete.emit(parsed["question"])
        else:
            scene = SceneDefinition.model_validate(parsed["scene"])
            self.ask_complete.emit(scene)

    async def answer(self, user_answer: str):
        self._messages.append({"role": "user", "content": user_answer})
        await self._turn()
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Migrating to QOpenGLWidget mid-milestone

**What:** Replacing the numpy-pipeline `ViewportCanvas(QWidget)` with `QOpenGLWidget` for "better performance."
**Why bad:** It's a full rewrite of the render bridge (offscreen numpy → direct GL texture upload), breaks the PyBullet software-renderer fallback (PyBullet's `getCameraImage` returns numpy, not a GL texture), and introduces GL context management complexity (context sharing, thread affinity, macOS CGL issues that the v0.5.0 architecture deliberately avoided). The render/sim decoupling (Pattern 1) solves the <10fps problem without any GL migration.
**Instead:** Keep the numpy pipeline. Decouple sim from render. If GL performance is needed later, it's a v2.0 decision, not a v0.7.0 phase.

### Anti-Pattern 2: Destroying dock widgets on scene reload

**What:** The current `_refresh_viewport_and_tree()` creates new `ViewportPanel` and `SceneTreeView` instances and swaps them into the docks on every scene reload / undo / redo / LLM-accept.
**Why bad:** `setCentralWidget(new_panel)` destroys the old panel, which resets the dock layout (docks may resize, reposition, or collapse). This is the root cause of the dock-panel layout reset bug.
**Instead:** Add `update_scene(new_scene)` methods to `ViewportPanel` and `SceneTreeView` that swap the scene reference and rebuild internal state in place, without recreating the widget or calling `setCentralWidget()`.

### Anti-Pattern 3: Coupling render rate to sim rate (the current bug)

**What:** A single `_tick()` that calls both `simulator.step()` and `simulator.render()` in sequence, then reschedules.
**Why bad:** The render call (~50-120ms) gates the sim step (~1-2ms). If you want 50 Hz sim, you get 50 Hz render (impossible at 120ms/render). If you want 30 Hz render, you get 30 Hz sim (too slow for physics). And the current code doesn't even call `step()` — so the preview is static.
**Instead:** Decouple via Pattern 1 — sim on QThread, render on UI thread, independent rates.

### Anti-Pattern 4: Freeform JSON parsing for VLM (the current approach)

**What:** Instructing the VLM to "return JSON" and parsing with regex/markdown-fence stripping (`_parse_json_response()`).
**Why bad:** VLMs frequently wrap JSON in markdown fences, add commentary, or truncate long schemas. The `_parse_json_response` method is fragile. Structured Outputs (Pattern 5) eliminates this entire failure mode.
**Instead:** Use OpenAI Structured Outputs with `SceneDefinition.model_json_schema()`. Keep freeform as a fallback for Anthropic/Ollama.

### Anti-Pattern 5: Gizmos as 2D Qt widgets composited in paintEvent

**What:** Drawing gizmo handles (translate/rotate axes) as QPainter primitives in `ViewportCanvas.paintEvent` after drawing the pixmap.
**Why bad:** Requires 2D-to-3D projection (screen-space → world-space) to map mouse clicks to gizmo handles, which duplicates the render pipeline's projection matrix math. Gizmo handles won't track camera changes (the 2D position is computed once and doesn't update when the camera orbits).
**Instead:** Render gizmos in the 3D pipeline (Pattern 3) — MuJoCo `mjvScene` geoms or PyBullet debug lines.

## Data Flow — Render/Sim Decoupling (the critical data-flow change)

### Current Flow (coupled, <10fps, immobile)

```
QTimer.singleShot(50ms) → _tick()
  ├── (simulator is None?) → load simulator → reschedule → return
  ├── push _editor_camera_* attrs into simulator
  ├── simulator.render() → np.ndarray → QImage → QPixmap → ViewportCanvas.set_image()
  ├── _frame_count++ → _maybe_update_fps()
  └── QTimer.singleShot(50ms, _tick)  ← reschedule (NEVER calls simulator.step())

Problem: render() takes 50-120ms; _tick blocks the event loop for that duration.
         step() is never called, so the scene is static.
         Effective fps = 1000 / (50 + render_time) ≈ 6-10 fps.
```

### Target Flow (decoupled, 30+fps, animated)

```
                    ┌─────────────────────────────────────┐
                    │         SimStepWorker (QThread)       │
                    │  QTimer(20ms, PreciseTimer)          │  ← 50 Hz sim
                    │  ├── simulator.step(zero_action)     │  ← advances physics
                    │  └── emit stepped()                 │  ← optional: carry State snapshot
                    └──────────────┬──────────────────────┘
                                   │ signal/slot (queued, thread-safe)
                                   ▼
                    ┌─────────────────────────────────────┐
                    │      RenderPollLoop (UI thread)       │
                    │  QTimer(33ms, PreciseTimer)           │  ← 30 Hz render
                    │  ├── push _editor_camera_* attrs     │
                    │  ├── simulator.render() → np.ndarray  │  ← reads latest sim state
                    │  ├── np.ndarray → QImage → QPixmap    │
                    │  └── emit frame_ready(QPixmap)        │
                    └──────────────┬──────────────────────┘
                                   │ signal/slot (same thread, direct)
                                   ▼
                    ┌─────────────────────────────────────┐
                    │         ViewportCanvas.paintEvent      │
                    │  drawPixmap(scaled pixmap)            │
                    └─────────────────────────────────────┘

Sim runs at 50 Hz (20ms intervals) on QThread — independent of render time.
Render polls at 30 Hz (33ms intervals) on UI thread — each render reads the
latest sim state. Event loop stays responsive (render yields via QTimer).
Scene animates because step() IS called.
```

### Where the sim stepping loop lives

**The sim stepping loop lives on a QThread, in `SimStepWorker`, NOT in the viewport render loop.**

Rationale:
- `simulator.step()` mutates the simulator's internal state (`qpos`, `qvel`, body positions). If called on the UI thread, it blocks the event loop during the step (even though a single step is ~1-2ms, at 50 Hz that's 50-100ms/sec of UI-thread blockage — visible as input lag).
- The simulator instance is shared between the sim-step worker (writes state via `step()`) and the render-poll loop (reads state via `render()`). This is safe because:
  - MuJoCo: `mj_step(model, data)` updates `_data`; `render()` calls `mj_forward(model, data)` then reads `_data`. These are not thread-safe in general, but in practice the render reads a consistent snapshot because `mj_forward` recomputes derived quantities from `qpos/qvel` which are updated atomically by `mj_step`. The worst case is rendering a frame that's 1 sim-step old — acceptable for a preview.
  - PyBullet: `stepSimulation()` and `getCameraImage()` are called on the same physics client. PyBullet's C++ backend is not documented as thread-safe, but `DIRECT` mode (used for editor preview) runs in-process and the calls are serialized. To be safe, the render-poll loop can use `getCameraImage` which is a read-only snapshot.
  - If thread-safety proves to be an issue in practice, the fallback is to have the sim-step worker emit a `State` snapshot via signal, and the render-poll loop renders from that snapshot (deep copy). This adds a copy but guarantees no concurrent access. Start with the shared-simulator approach; add the snapshot copy only if tests show corruption.

### Data-flow change summary

| Aspect | Current (coupled) | Target (decoupled) |
|--------|--------------------|--------------------|
| Sim step | Never called in `_tick` | `SimStepWorker._step()` at 50 Hz on QThread |
| Render call | In `_tick` at 20 Hz (theoretical) | `RenderPollLoop._render_frame()` at 30 Hz on UI thread |
| Event loop | Blocked during render (50-120ms) | Responsive (render yields via QTimer) |
| Scene animation | Static (no step) | Animated (step advances physics) |
| Thread model | Single thread (UI) | Two threads (UI + sim QThread) |
| Camera sync | `_editor_camera_*` attrs pushed before render | Same, pushed in render-poll loop (not sim worker) |
| Sim state sharing | N/A (no step) | Shared simulator instance (read by render, written by step) |

## The Three Known Bugs → Architectural Fixes

| Bug | Root Cause | Architectural Fix | Pattern |
|-----|-----------|-------------------|--------|
| <10fps frame rate | `_tick()` blocks event loop for render duration (50-120ms); 50ms timer + 120ms render = ~7fps | Decouple sim (QThread) from render (UI thread); render-poll at 30 Hz with `QTimer.singleShot(0)` yielding to event loop between frames | Pattern 1 (Render/Sim Decoupling) |
| Immobile scene preview | `_tick()` never calls `simulator.step()` — render shows a static snapshot | `SimStepWorker` calls `simulator.step(zero_action)` at 50 Hz, advancing physics (gravity, joint settling) | Pattern 1 (SimStepWorker) |
| Dock-panel layout reset on rerun | `_refresh_viewport_and_tree()` creates new `ViewportPanel` + `SceneTreeView`, calls `setCentralWidget()` / `setWidget()`, destroying old widgets and resetting dock geometry | Add `update_scene()` methods to `ViewportPanel` and `SceneTreeView`; save/restore dock state via `DockStateManager` around structural changes | Pattern 4 (Dock-State Persistence) |

## Scalability Considerations

| Concern | At 1 view | At 4 views (multi-view) | At 8+ views |
|---------|-----------|------------------------|-------------|
| Render time per frame | ~50-120ms (1 render call) | ~200-480ms (4 render calls serial) | ~400-960ms (8 render calls serial) — fps drops to ~1-2 |
| Sim step time | ~1-2ms (unchanged) | ~1-2ms (shared sim, one step) | ~1-2ms (shared sim) |
| Mitigation | N/A (single view is fine) | Stagger views across frames (view 0 on even frames, view 1 on odd) or lower per-view resolution | Render views on a round-robin schedule (not all every frame); or migrate to `QOpenGLWidget` with shared FBOs (v2.0) |
| Memory | 1 × framebuffer (640×480×3 = ~1MB) | 4 × framebuffer (~4MB) | 8 × framebuffer (~8MB) — negligible |

## Suggested Build Order (Respects Dependencies)

The milestone context mandates **GUI first, scene generation second**. Within GUI, the dependency chain is:

### Phase 1: Render/Sim Decoupling + Bug Fixes (GUI-11 + GUI-15)

**Rationale:** This is the foundation. Every other viewport feature (multi-view, gizmos, recording) depends on a responsive, animated viewport. The three bugs all share root causes here. Build this first.

**Deliverables:**
- `editor/sim_step_worker.py` — `SimStepWorker(QObject)` on QThread
- `editor/render_poll_loop.py` — `RenderPollLoop(QObject)` on UI thread
- Modify `editor/viewport.py` — split `_tick()` into sim-step + render-poll; add `update_scene()` method
- `editor/dock_state.py` — `DockStateManager` for save/restore
- Modify `editor/main_window.py` — fix `_refresh_viewport_and_tree` to use `update_scene()` not recreate; wire `DockStateManager`
- Modify `editor/_settings.py` — add dock-state + viewport-pref keys
- Tests: sim-step worker unit test (mock simulator, assert step calls + signal), render-poll loop unit test, dock-state round-trip test, fps regression test (>10fps target)

**Addresses:** <10fps bug, immobile preview bug, dock-layout-reset bug

### Phase 2: Multi-View + Lighting (GUI-12)

**Rationale:** Depends on Phase 1 (needs a responsive viewport to render multiple views). Multi-view is the highest-value viewport-depth feature after decoupling.

**Deliverables:**
- `editor/multi_view.py` — `MultiViewManager`
- Modify `simulators/base_simulator.py` — extend `render()` signature with `camera_params`, `light_params`, `render_flags` (additive kwargs)
- Modify `simulators/mujoco_simulator.py` — implement camera/light/flag param plumbing (use `mjvOption` flags + `mjvScene` light slots + camera `update_scene` with `MjvCamera`)
- Modify `simulators/pybullet_simulator.py` — implement camera params (already partially via `_editor_camera_*`), light params (limited: shadow toggle + renderer enum), multi-view (multiple `getCameraImage` calls)
- Tests: multi-view render test (2 views, assert different camera angles), lighting flag test (shadow toggle on/off produces different images)

**Addresses:** multi-view, lighting

### Phase 3: Gizmos + Recording (GUI-13 + GUI-14)

**Rationale:** Gizmos depend on multi-view/lighting (need to know which view the gizmo is in and what the camera params are). Recording depends on the decoupled render loop (captures frames from the render-poll loop, not the sim-step worker).

**Deliverables:**
- `editor/gizmo_overlay.py` — `GizmoOverlay` (translate/rotate modes)
- Modify `simulators/mujoco_simulator.py` — add gizmo rendering via `mjvScene` geoms
- Modify `simulators/pybullet_simulator.py` — add gizmo rendering via debug lines
- `editor/frame_recorder.py` — `FrameRecorder` using `QMediaRecorder` + `QVideoFrameInput` (Qt 6.8+, FFmpeg backend) with image-sequence fallback
- Tests: gizmo render test (gizmo visible in frame, body pose mutates on drag), recording test (produce a valid video file or image sequence)

**Addresses:** gizmos, recording

### Phase 4: Editing UX + File/IO Polish (GUI-14/15)

**Rationale:** Editing UX (better tree/form interactions, keyboard shortcuts, multi-select) and file/IO (recent files, export/import, validation feedback) are independent of the viewport features and can proceed in parallel with Phase 2/3, but are listed after because they're lower-priority than the viewport bugs.

**Deliverables:**
- Modify `editor/tree_view.py` — multi-select, keyboard navigation, drag-reorder improvements
- Modify `editor/property_form.py` — better validation feedback, inline help
- Modify `editor/main_window.py` — keyboard shortcuts, export/import menu items
- Tests: tree-view interaction tests, file IO round-trip tests

### Phase 5+: Scene Generation (GEN-01..05)

**Rationale:** After GUI is stable. Each GEN feature is independent and can be parallelized.

**Deliverables (per GEN requirement):**
- GEN-01 (more templates): Modify `scene_generation/templates.py` — add templates, extend `list_templates()`
- GEN-02 (better LLM text→scene): Modify `scene_generation/text_parser.py` — improve prompts, add few-shot examples
- GEN-03 (VLM image→scene): `editor/vlm_panel.py` (NEW) + modify `scene_generation/vision_parser.py` — add Structured Outputs path (Pattern 5)
- GEN-04 (procedural/batch gen): `scene_generation/batch_generator.py` (NEW) + modify `scene_generation/scene_composer.py` — add `generate_batch()`
- GEN-05 (interactive LLM clarifying-question flow): `scene_generation/clarify_flow.py` (NEW) + modify `editor/llm_panel.py` — add chat mode (Pattern 6)

### Dependency Graph

```
Phase 1 (Decoupling + Bug Fixes)
  ├── Phase 2 (Multi-View + Lighting)     ← needs responsive viewport
  │     └── Phase 3 (Gizmos + Recording)  ← gizmos need camera params from P2
  └── Phase 4 (Editing UX + File/IO)      ← independent of P2/P3, can parallelize

Phase 5+ (Scene Generation)              ← after GUI stable
  ├── GEN-01 (templates)                  ← independent
  ├── GEN-02 (better text→scene)          ← independent
  ├── GEN-03 (VLM image→scene)            ← independent
  ├── GEN-04 (procedural/batch)           ← independent
  └── GEN-05 (clarify flow)               ← independent
```

## Integration Points with Existing Architecture

### BaseSimulator ABC

| Integration Point | How v0.7.0 Connects | Change Type |
|-------------------|--------------------|-------------|
| `render()` method | Extended signature: `render(..., camera_params=None, light_params=None, render_flags=None, gizmo_target=None, gizmo_mode=None)` — all additive kwargs with `None` defaults (backwards-compatible) | **MODIFIED** (additive) |
| `step()` method | Called by `SimStepWorker` (new caller, no change to `step()` itself) | **UNCHANGED** (new caller) |
| `load_scene()` / `reset()` | Called by `ViewportPanel` on scene load (existing flow) | **UNCHANGED** |
| `_editor_camera_*` attrs | Pushed by `RenderPollLoop` before each render call (moved from `_tick` to render-poll loop) | **MOVED** (same mechanism, new caller) |
| `_renderer_available` flag | Used by render-poll loop's error handling (existing short-circuit preserved) | **UNCHANGED** |

### ViewportCanvas / ViewportPanel

| Integration Point | How v0.7.0 Connects | Change Type |
|-------------------|--------------------|-------------|
| `ViewportCanvas.paintEvent` | Unchanged — still draws QPixmap | **UNCHANGED** |
| `ViewportCanvas` mouse/wheel events | Extended: gizmo interaction (click on gizmo handle → start drag → mutate body pose) routed via `GizmoOverlay` | **MODIFIED** (add gizmo event routing) |
| `ViewportPanel._tick()` | Split into `SimStepWorker._step()` + `RenderPollLoop._render_frame()` | **REPLACED** (split) |
| `ViewportPanel._start()` / `stop()` | Now starts/stops both sim worker + render loop | **MODIFIED** |
| `ViewportPanel._display_array()` | Moved to `RenderPollLoop._array_to_pixmap()` (or kept as a helper) | **MOVED** |
| `ViewportPanel._default_load_simulator()` | Unchanged (simulator loading logic preserved) | **UNCHANGED** |

### Render Bridge (MuJoCo + PyBullet)

| Integration Point | How v0.7.0 Connects | Change Type |
|-------------------|--------------------|-------------|
| MuJoCo `Renderer.update_scene()` | Called per-view with different `MjvCamera` or cam_id for multi-view | **EXTENDED** (multi-view) |
| MuJoCo `mjvOption` flags | Exposed via `render_flags` param for lighting/shadow/wireframe toggles | **EXTENDED** (new param) |
| MuJoCo `mjvScene` lights | Exposed via `light_params` param for custom light positions (limited — lights defined in model XML; runtime modification requires `mjvScene.light[pos]` mutation) | **EXTENDED** (new param) |
| PyBullet `getCameraImage` | Called per-view with different view matrices for multi-view; `shadow` and `renderer` params exposed via `render_flags`/`light_params` | **EXTENDED** (multi-view + flags) |
| PyBullet `_normalize_pb_rgb()` | Unchanged (already canonicalizes to HxWx3 uint8) | **UNCHANGED** |
| Framebuffer retry logic | Unchanged (kept in render-poll loop's error handling) | **UNCHANGED** |
| `_renderer_available = False` short-circuit | Unchanged (persistent-failure short-circuit preserved) | **UNCHANGED** |

### SchemaWalker / FieldRenderer / PropertyForm

| Integration Point | How v0.7.0 Connects | Change Type |
|-------------------|--------------------|-------------|
| `SchemaWalker.walk()` | Unchanged (already walks 62 Pydantic v2 schema classes) | **UNCHANGED** |
| `FieldRenderer.render()` | Unchanged (widget factory registry) | **UNCHANGED** |
| `PropertyForm` 150ms debounced validation | Unchanged | **UNCHANGED** |
| `SceneTreeView._build_tree()` | Extended: `update_scene(new_scene)` method to rebuild tree in place (bug fix) | **MODIFIED** (add `update_scene`) |

### LLMPanel / TextParserWorker

| Integration Point | How v0.7.0 Connects | Change Type |
|-------------------|--------------------|-------------|
| `TextParserWorker` QThread | Unchanged for single-shot mode; new `ClarifyWorker` for chat mode | **UNCHANGED** (new sibling) |
| `LLMPanel._on_generate()` | Extended: add chat-mode toggle that switches to `ClarifyFlow` multi-turn | **MODIFIED** (add chat mode) |
| `LLMPanel.scene_accepted` signal | Unchanged (emitted when scene is accepted, regardless of single-shot or chat mode) | **UNCHANGED** |
| `TextParser.parse_sync()` | Unchanged (called by `TextParserWorker`); new `ClarifyFlow` calls `TextParser._call_llm_async()` directly | **UNCHANGED** (new caller) |

### SceneUndoStack

| Integration Point | How v0.7.0 Connects | Change Type |
|-------------------|--------------------|-------------|
| `SceneUndoStack.push_snapshot()` | Unchanged (deep-copy snapshots, 100-level cap) | **UNCHANGED** |
| VLM panel scene acceptance | Connects via `VLMPanel.scene_accepted` → `EditorWindow._on_vlm_scene_accepted` → `SceneUndoStack.push_snapshot()` (same flow as LLM panel) | **NEW** (parallel to LLM flow) |

### EditorSettings

| Integration Point | How v0.7.0 Connects | Change Type |
|-------------------|--------------------|-------------|
| `save_window()` / `load_window()` | Unchanged (geometry + state) | **UNCHANGED** |
| Dock state | NEW: `save_dock_state()` / `load_dock_state()` keys | **MODIFIED** (add keys) |
| Viewport prefs | NEW: `viewport/target_fps`, `viewport/sim_rate_hz`, `viewport/lighting` keys | **MODIFIED** (add keys) |
| Recent files / last provider | Unchanged | **UNCHANGED** |

## Sources

- [Qt QThread Documentation](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QThread.html) — worker-object pattern via `moveToThread()`, signal/slot cross-thread communication
- [MuJoCo + PySide6 Decoupled Render Gist](https://gist.github.com/cherishyuan/e5216d90c53d8281d1db7f0b21718253) — `UpdateSimThread` with `mj_step` in tight loop, QTimer-driven `update()` on main thread
- [Qt Forum: QTimers vs Threading for Maximum Performance](https://forum.qt.io/topic/162980/qtimers-vs-threading-how-to-achieve-maximum-performance) — QTimer jitter, vsync recommendation, `QElapsedTimer` for delta time
- [PySide6 QMainWindow Documentation](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QMainWindow.html) — `saveState()`/`restoreState()`, objectName requirement, version mismatch behavior
- [Stack Overflow: How to revert a QDockWidget after restoreState()](https://stackoverflow.com/questions/78958419/how-to-revert-a-qdockwidget-after-calling-restorestate) — no selective undo, manual re-apply needed
- [PySide6 QOpenGLWidget Documentation](https://doc.qt.io/qtforpython-6/PySide6/QtOpenGLWidgets/QOpenGLWidget.html) — FBO rendering, context sharing, `grabFramebuffer()`
- [Threaded QOpenGLWidget Example](https://doc.qt.io/qtforpython-6/examples/example_opengl_threadedqopenglwidget.html) — multiple GLWidgets on separate threads, context sharing
- [florianblume/qt3d-gizmo](https://github.com/florianblume/qt3d-gizmo) — Qt3D translate/rotate gizmo, overlay framegraph
- [Meshroom TransformGizmo.qml](https://github.com/alicevision/Meshroom/blob/c9d0239f/meshroom/ui/qml/Viewer3D/TransformGizmo.qml) — Blender-style translate/rotate/scale gizmo, constant apparent size, frontLayerComponent
- [OpenAI Structured Outputs Guide](https://developers.openai.com/api/docs/guides/structured-outputs) — `response_format: json_schema`, schema adherence, Pydantic recommended
- [OpenAI Cookbook: GPT-4 Vision with Function Calling](https://developers.openai.com/cookbook/examples/multimodal/using_gpt4_vision_with_function_calling/) — image-to-structured-JSON with Pydantic + instructor
- [MuJoCo Visualization Documentation](https://mujoco.readthedocs.io/en/latest/programming/visualization.html) — offscreen rendering, multiple camera types, `mjvOption` flags, `mjvScene` lights, `mjtRndFlag` render flags
- [MuJoCo Python Renderer Source](https://github.com/google-deepmind/mujoco/blob/e6354b43/python/mujoco/rendering/classic/renderer.py) — `Renderer` class, `update_scene()` camera switching, depth/segmentation modes
- [Gymnasium MuJoCo Rendering](https://github.com/Farama-Foundation/Gymnasium/blob/main/gymnasium/envs/mujoco/mujoco_rendering.py) — `OffScreenViewer`, `MujocoRenderer`, visual_options dict
- [PyBullet getCameraImage View/Projection Matrices](https://stackoverflow.com/questions/60430958/understanding-the-view-and-projection-matrix-from-pybullet) — `computeViewMatrix`, `computeProjectionMatrixFOV`, NDC clipping
- [AIOZ: Visual Observations for PyBullet Agents](https://blog.ai.aioz.io/guides/robotics/2021-05-19-visual-obs-pybullet/) — `shadow=True`, `renderer=p.ER_BULLET_HARDWARE_OPENGL`
- [PySide6 QVideoFrameInput (Qt 6.8+)](https://doc.qt.io/qtforpython-6/PySide6/QtMultimedia/QVideoFrameInput.html) — custom numpy frames to `QMediaRecorder`, FFmpeg backend
- [PySide6 QMediaRecorder](https://doc.qt.io/qtforpython-6/PySide6/QtMultimedia/QMediaRecorder.html) — video encoding, `videoFrameRate`, `videoResolution`, `outputLocation`
- [ClarQ-LLM Benchmark](https://arxiv.org/html/2409.06097v2) — clarifying questions in task-oriented dialogue, slot tracking
- [ClarifyAgent](https://api.emergentmind.com/topics/clarifyagent) — modular multi-turn clarification, finite-state slot tracking
- [SceneReVis](https://github.com/Runder-sun/SceneReVis) — self-reflective scene synthesis with tool calling (add/move/rotate/scale/remove)
- [Qt Quick Scene Graph](https://doc.qt.io/qtforpython-6/overviews/qtquick-visualcanvas-scenegraph.html) — threaded vs basic render loops, vsync animation driver, `QSG_USE_SIMPLE_ANIMATION_DRIVER`
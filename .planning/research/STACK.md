# Stack Research — v0.7.0 GUI Editor Depth & Scene Generation

**Domain:** Surgical-robotics RL training system — PySide6 scene editor depth (GUI-11..15) + scene-generation features (GEN-01..05), added to an existing validated app.
**Researched:** 2026-07-15
**Confidence:** HIGH

---

## Scope of this research

Only NEW capabilities for v0.7.0 are in scope. The following are already built, validated, and explicitly out of scope for re-research (per milestone context): PySide6 6.8 LTS / custom `ViewportCanvas(QWidget)`, MuJoCo offscreen + PyBullet `getCameraImage` render bridge with framebuffer retry + persistent-failure short-circuit, `QThread` background LLM work, trimesh meshes, tetgen deformable pipeline, Pydantic v2 schema + `SchemaWalker`/`FieldRenderer`, Stable-Baselines3 + Gymnasium, Typer CLI, Rich logging, pydantic-settings, the existing `scene_generation` module (`text_parser` / `vision_parser` / `scene_composer` / `templates` / `base_parser` with OpenAI / Anthropic / Ollama providers), and the optional-dependency groups `[distributed]` `[ros2]` `[llm]` `[vision]` `[assets]` `[benchmark]` `[marl]` `[dreamer]` `[gui]` `[meshing]` `[simulation]` `[tracking]` `[k8s-test]` `[docs]` `[physics]`.

The v0.5.0 architecture decisions that constrain every recommendation below:
- **GUI stays in the stock interpreter** — no `mjpython` re-exec (mjpython runs Python on a secondary thread, violating PySide6's main-thread requirement and causing the "dock icon, no window" hang).
- **Editor viewport is a custom `ViewportCanvas(QWidget)`**, not a `QLabel` and not a Qt3D window. The render surface is a CPU-rasterized `QPixmap` produced by the MuJoCo/PyBullet offscreen render bridge. There is **no live OpenGL context** in the editor process on macOS (the existing `_renderer_available = False` short-circuit confirms CGL fails on the main thread under the stock interpreter).
- **PEP 562 lazy `__getattr__`** in `surg_rl.rl.__init__` keeps heavy `stable_baselines3`/`torch` off the editor import path.

Any stack addition that contradicts those three constraints is rejected in "What NOT to Use" below.

---

## Recommended Stack

### Core Technologies — additions for v0.7.0

Only **one** new package is a hard requirement. Everything else is either already covered by an existing extra, or is pure code on top of existing deps.

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `imageio-ffmpeg` | `>=0.6.0` | FFmpeg backend for `imageio.get_writer(..., format="mp4")` — used by the in-app recording feature (GUI-13) to write viewport frames to `.mp4` | `imageio>=2.31.0` is already in the `[gui]` extra, but `imageio` no longer bundles `imageio-ffmpeg` by default — it was moved to an `ffmpeg` extra (verified via `importlib.metadata.requires("imageio")` on the installed 2.37.3). Without `imageio-ffmpeg`, `imageio.get_writer(path, format="mp4")` raises `IndexError: Could not find module "imageio-ffmpeg"`. v0.6.0 (2025-01-16) is the current release and ships pre-built ffmpeg binaries for macOS/Linux/Windows. This is the single mandatory new dep for the whole milestone. |

### Supporting Libraries — optional / decision-dependent

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `imageio[ffmpeg]` | `>=2.31.0` | Alternative spelling: pull `imageio-ffmpeg` transitively via imageio's `ffmpeg` extra instead of pinning `imageio-ffmpeg` directly | Either form works; `imageio-ffmpeg>=0.6.0` as a direct pin is clearer and gives us an explicit floor. Prefer the direct pin. |
| (existing `[vision]` extra) `torch` + `torchvision` + `transformers` | already pinned | Local VLM inference for GEN-03 if a local LLaVA/Qwen-VL-style model is wanted instead of API-based GPT-4o/Claude Vision (the existing `VisionParser` already does the API path) | Only if a phase explicitly chooses local inference over the already-working API VLM path. No new pin needed — the `[vision]` extra already covers it. The HuggingFace model weights are downloaded at runtime, not a pip dep. |

### Development Tools — already in place, no additions

| Tool | Purpose | Notes |
|------|---------|-------|
| `ruff` / `black` / `mypy` | lint / format / type-check | Already configured; no changes for v0.7.0 |
| `pytest` / `pytest-cov` / `pytest-asyncio` | tests | Already configured; the LLM clarifying-question flow and procedural/batch gen add new test surface but need no new pytest plugins |

---

## What each existing dep already covers (do NOT re-add)

This is the load-bearing section for an existing-app milestone. Most v0.7.0 features need **no new packages** — they are code on top of already-installed deps. Calling these out explicitly so the roadmap does not budget redundant dependency work.

### GUI editor depth (GUI-11..15)

| v0.7.0 feature | Already-covered-by | What's actually needed |
|----------------|--------------------|------------------------|
| **GUI-11 render/sim-decoupled viewport** | Existing `ViewportCanvas(QWidget)` + MuJoCo offscreen + PyBullet `getCameraImage` render bridge | Architecture change only: move the render call off the main thread (a `QThread` worker that produces `QPixmap` frames, main thread blits). No new dep. The current `QTimer.singleShot(50, self._tick)` self-rescheduling loop is the <10fps root cause — 50 ms cap = 20 fps ceiling, and synchronous render-on-main blocks the event loop. Decoupling is pure refactor. |
| **GUI-12 multi-view** | Existing render bridge accepts `camera_name`/camera params per call | Instantiate N `ViewportCanvas` panels, each calling the render bridge with a different camera config. Pure code; no dep. |
| **GUI-12 lighting controls** | MuJoCo: `<light>` element + `model.light_*` arrays + `mjvOption.flags` for shadow; PyBullet: `getCameraImage(lightColor, lightDistance, lightAmbientCoeff, lightDiffuseCoeff, lightSpecularCoeff, shadow)` | Native to both backends. Expose these in the editor as `FieldRenderer` widgets bound to the existing schema. No dep. |
| **GUI-12 transform gizmos** (translate/rotate/scale manipulators) | Existing `ViewportCanvas` + numpy + the render bridge's camera matrices | Draw gizmo handles as a 2D overlay on the `ViewportCanvas` `QPainter` by projecting 3D handle world-positions to screen space using the camera azimuth/elevation/distance/target offsets already tracked in `_CameraOffset`. Hit-test in 2D. Mutate the selected entity's `Pose`/`scale`. **No new dep.** See "What NOT to Use" for why Qt3D / viser are rejected. |
| **GUI-13 in-app recording / video capture** | `imageio>=2.31.0` (in `[gui]`) + **NEW** `imageio-ffmpeg>=0.6.0` | `imageio.get_writer(path, format="mp4", mode="I", fps=N)` then `writer.append_data(rgb_frame)` per viewport tick. The render bridge already yields an `(H, W, 3) uint8` ndarray per frame — feed it straight to the writer. The only missing piece is the ffmpeg backend package. |
| **GUI-14 editing UX, file/IO** | Pydantic v2 schema, `pyyaml`, `tomli-w`, `SchemaWalker`, `FieldRenderer`, existing undo/redo stack, drag-drop | Pure code: dock-state persistence via `QMainWindow.saveState()`/`restoreState()` + `QSettings` for the dock-panel reset bug; file dialogs are `QFileDialog`. No dep. |
| **GUI-15 perf/stability** | Same render bridge + `QThread` | Same root-cause work as GUI-11. Profiling via `cProfile`/`py-spy` (dev tool, not a runtime dep). No new runtime dep. |

### Scene generation (GEN-01..05)

| v0.7.0 feature | Already-covered-by | What's actually needed |
|----------------|--------------------|------------------------|
| **GEN-01 more task templates** | Existing `templates.py` + Pydantic v2 `SceneDefinition` | Pure code: add more template presets. No dep. |
| **GEN-02 better LLM text→scene** | Existing `TextParser` + `openai` / `anthropic` SDKs (in core deps + `[llm]`) | Prompt-engineering + structured-output (`response_format` / tool-calling) work. The OpenAI and Anthropic SDKs already support multi-turn conversations and tool/function calling natively. No dep. |
| **GEN-03 VLM image→scene** | Existing `VisionParser` already uses API-based VLMs (OpenAI GPT-4o vision, Anthropic Claude vision, Ollama vision) via base64 image input | The feature largely exists. v0.7.0 work is hardening (better prompt templates, schema-conformance validation, fallback handling). For **local** VLM inference (optional, only if a phase chooses it), the existing `[vision]` extra (`torch` + `torchvision` + `transformers`) already covers it — no new pin. |
| **GEN-04 procedural / batch gen** | `trimesh` (in `[assets]`) + `numpy` (core) + `pydantic` schema | Procedural scene variation (randomized instrument poses, tissue params, lighting) is pure code on trimesh + numpy + the existing `parameter_randomizer.py`. Batch = loop over parameter sweeps. No dep. |
| **GEN-05 interactive LLM clarifying-question flow** | `openai` / `anthropic` SDKs (already installed) + existing `QThread` pattern (`TextParserWorker`) | Multi-turn LLM conversation with clarifying questions is supported natively by both SDKs (chat-completions message history). The GUI round-trip reuses the existing `QThread` background-worker pattern from the LLM panel. No dep. |

---

## Installation

### Change to `pyproject.toml` (the ONLY required edit)

```toml
# In [project.optional-dependencies]
gui = [
    "PySide6>=6.8.0,<7.0",
    "markdown-it-py>=3.0.0",
    "imageio>=2.31.0",
    "imageio-ffmpeg>=0.6.0",   # NEW — imageio 2.37 no longer bundles ffmpeg; needed for GUI-13 recording
]
```

### Install command for a developer bringing up the editor with the new recording feature

```bash
pip install -e ".[gui]"           # adds imageio-ffmpeg alongside PySide6 + imageio
# Optional, only if a phase chooses local VLM inference for GEN-03:
pip install -e ".[gui,vision]"    # adds torch + torchvision + transformers (heavy)
```

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not (this project) |
|----------|-------------|-------------|------------------------|
| Video recording backend | `imageio-ffmpeg>=0.6.0` | `PyAV` (`av>=14`) | imageio-ffmpeg is already the implicit default for `imageio.get_writer(format="mp4")`; PyAV is faster (C-level ffmpeg bindings) but adds a second ffmpeg stack and a heavier wheel. The render bridge already produces ndarray frames at low fps (editor viewport), so PyAV's throughput advantage is irrelevant. Stick with imageio-ffmpeg for dep economy. |
| Video recording backend | `imageio-ffmpeg>=0.6.0` | `QVideoFrameInput` + `QMediaRecorder` (Qt 6.8+ native) | Requires the FFmpeg multimedia backend at runtime (not guaranteed on all Linux distros), forces a `QMediaCaptureSession` pipeline that is awkward to feed from a render bridge that produces ndarray frames, and is more code than `imageio.get_writer`. imageio-ffmpeg is simpler and matches the ndarray-in/ndarray-out shape of the existing render bridge. |
| Transform gizmo (translate/rotate/scale manipulator) | **2D overlay on `ViewportCanvas`** via `_CameraOffset` projection — no dep | `PySide6.Qt3DExtras` + community `qt3d-gizmo` / `qt3d-transform-gizmo` | Qt3D is a separate rendering framework (its own scene graph, its own OpenGL context). Adopting it means running a parallel 3D pipeline alongside the existing MuJoCo/PyBullet→QPixmap bridge — a major architectural reversal of the v0.5.0 decision and a likely regression of the macOS stock-interpreter / no-OpenGL-context constraint. The community gizmo libs (`florianblume/qt3d-gizmo`, `fferri/qt3d-transform-gizmo`) are C++/QML, low-stars, and unmaintained. The 2D-overlay approach reuses the existing `_CameraOffset` camera params already tracked in `viewport.py` and the existing `QPainter` on `ViewportCanvas`. |
| Transform gizmo | 2D overlay (no dep) | `viser` (`scene.add_transform_controls()`) | viser is web-based: it runs a WebSocket server and renders in a browser via React/three.js. Embedding it in the PySide6 desktop app would require `QWebEngineView` (Chromium, ~100 MB) and running a parallel web stack — directly contradicting the native-desktop architecture. It is the right tool for a notebook/SSH workflow, not for an integrated Qt editor. |
| Local VLM for GEN-03 | (only if a phase chooses local) existing `[vision]` extra (`torch`+`transformers`) | LLaVA-specific pip package | There is no maintained "LLaVA" pip package; weights are downloaded from HuggingFace at runtime into the `transformers` ecosystem already in `[vision]`. No new pin. |
| LLM multi-turn clarifying flow (GEN-05) | `openai` + `anthropic` SDKs already in core deps | `langchain` / `llamaindex` | Those frameworks add a heavy abstraction layer over SDKs the project already uses directly and well (per the existing `TextParser`/`VisionParser`). Multi-turn clarification is 20 lines of message-history management on top of the existing SDK clients. Adding a framework would contradict the project's established "thin SDK wrapper" pattern. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **`mjpython` re-exec** | Violates PySide6 main-thread requirement; produces the silent "dock icon, no window" hang already fixed in v0.5.0 (commit `3031ed9` F-01). Re-introducing it would regress GUI-15 stability. | Stock interpreter; MuJoCo offscreen renderer (CPU rasterization → QPixmap). |
| **Qt3D (`PySide6.Qt3D*`)** | Separate rendering stack with its own OpenGL context — conflicts with the existing render-bridge architecture and the macOS no-live-GL-context constraint. Community gizmo libs are unmaintained. | 2D `QPainter` overlay on `ViewportCanvas` for gizmo handles. |
| **`viser`** | Web-based (WebSocket + browser/three.js); would require `QWebEngineView` and a parallel web stack alongside the native Qt editor. | Native `ViewportCanvas` + render bridge. |
| **`langchain` / `llamaindex`** | Heavy abstraction over the OpenAI/Anthropic SDKs already used directly and well in `TextParser`/`VisionParser`. The clarifying-question flow (GEN-05) is a thin message-history loop. | Direct `openai`/`anthropic` SDK usage, consistent with existing parsers. |
| **`qimage2ndarray`** | Tiny convenience for QImage→ndarray; would be a new dep for 5 lines that are already expressible via `np.frombuffer(qimg.constBits(), dtype=np.uint8).reshape(...)` with strides. | Manual `np.frombuffer` reshape (already the idiom in the render bridge). |
| **`pyqtgraph`** | Plotting library; not needed for editor perf work. Profiling is `py-spy`/`cProfile` at dev time, not a runtime dep. | None (no in-editor perf plots in scope). |
| **`PyOpenGL` / `moderngl`** | Would introduce a live OpenGL context into the editor process — the exact thing the `_renderer_available = False` short-circuit already defends against on macOS. | Keep the CPU-rasterized QPixmap approach; decouple render to a `QThread` worker for perf. |
| **`av` (PyAV)** as the recording backend | Second ffmpeg stack alongside `imageio-ffmpeg`; throughput gain is irrelevant at editor-viewport fps. | `imageio-ffmpeg>=0.6.0` via `imageio.get_writer`. |

---

## Stack Patterns by Variant

**If recording is wanted in the headless CLI too (not just the GUI):**
- Promote `imageio-ffmpeg>=0.6.0` from the `[gui]` extra into core `dependencies` instead. Currently recording is GUI-13 only, so `[gui]` is the right home. Re-evaluate if a `surg-rl record` CLI subcommand is added.

**If a phase chooses local VLM inference for GEN-03:**
- Use `pip install -e ".[vision]"` (already-defined extra: `torch>=2.0.0`, `torchvision>=0.15.0`, `transformers>=4.35.0`). Download weights (e.g. `llava-hf/llava-1.5-7b-hf` or a Qwen-VL model) via `transformers` at runtime. No new pip pin. Add a `LocalVisionParser` subclass next to the existing API-based `VisionParser`.

**If GUI-15 perf work concludes that the render bridge MUST be hardware-accelerated:**
- That is a v0.8.0+ architectural decision, not a v0.7.0 dep addition. It would require revisiting the `mjpython` / Qt3D / `QOpenGLWidget` rejection — out of scope for this milestone. For v0.7.0, decouple render to a `QThread` worker (no dep) and raise the fps ceiling that way first.

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `imageio-ffmpeg>=0.6.0` | `imageio>=2.31.0` (already in `[gui]`) | imageio discovers `imageio-ffmpeg` as the ffmpeg backend automatically once installed; no API change needed in the writer call. |
| `imageio-ffmpeg>=0.6.0` | Python 3.10–3.13 | Ships pre-built ffmpeg binaries for macOS (arm64 + x86_64), Linux x86_64, Windows x86_64. Matches the project's 3.10+ floor. |
| `PySide6>=6.8.0,<7.0` (existing; installed 6.11.1) | `imageio` recording path | No conflict — recording uses `QWidget.grab()` or the render-bridge ndarray, never a Qt multimedia type. |
| `mujoco>=3.0.0` (installed 3.7.0) | Native `<light>` edits + `model.light_*` array mutation | Stable across 3.x; no API break for lighting controls. |
| `pybullet>=3.2.5` (in `[physics]`) | `getCameraImage` lighting kwargs (`lightColor`, `lightDistance`, `lightAmbientCoeff`, `lightDiffuseCoeff`, `lightSpecularCoeff`, `shadow`) | These kwargs are stable since PyBullet 3.x; lighting controls (GUI-12) on the PyBullet backend require no new dep. |
| `openai>=1.0.0` / `anthropic>=0.18.0` (existing) | Multi-turn clarifying-question flow (GEN-05) | Both SDKs support chat-completions message history natively; no new client class needed. |

---

## Summary table — v0.7.0 stack delta at a glance

| Capability | New dep? | What |
|------------|----------|------|
| GUI-11 render/sim decoupling | No | `QThread` refactor of existing render bridge |
| GUI-12 multi-view | No | N × `ViewportCanvas` |
| GUI-12 lighting controls | No | MuJoCo `<light>` / PyBullet `getCameraImage` kwargs |
| GUI-12 transform gizmos | No | 2D `QPainter` overlay via `_CameraOffset` projection |
| GUI-13 in-app recording | **YES** | `imageio-ffmpeg>=0.6.0` (extend `[gui]` extra) |
| GUI-14 editing UX / file-IO / dock persistence | No | `QMainWindow.saveState`/`restoreState` + `QSettings` + existing undo stack |
| GUI-15 perf / stability | No | Same `QThread` decoupling as GUI-11 |
| GEN-01 more templates | No | Pure code in `templates.py` |
| GEN-02 better LLM text→scene | No | Prompt engineering on existing SDKs |
| GEN-03 VLM image→scene | No (API path) / optional `[vision]` (local path) | Existing `VisionParser`; local VLM uses existing extra |
| GEN-04 procedural / batch gen | No | `trimesh` + `numpy` + existing `parameter_randomizer` |
| GEN-05 LLM clarifying-question flow | No | Multi-turn on existing `openai`/`anthropic` SDKs + `QThread` |

**Net new pip dependencies for v0.7.0: exactly one — `imageio-ffmpeg>=0.6.0`, added to the existing `[gui]` extra.**

---

## Sources

- `importlib.metadata.requires("imageio")` on installed imageio 2.37.3 — confirmed `imageio-ffmpeg` is now gated behind an `ffmpeg` extra, not bundled by default (HIGH confidence, direct observation).
- `pip show imageio-ffmpeg` — confirmed NOT currently installed in this env (HIGH).
- imageio/imageio-ffmpeg GitHub (https://github.com/imageio/imageio-ffmpeg/) — v0.6.0 (2025-01-16) is current; ships pre-built ffmpeg binaries; recommends PyAV for higher throughput but imageio-ffmpeg is sufficient for editor-viewport fps (HIGH).
- imageio v3 docs — examples (https://imageio.readthedocs.io/en/stable/examples.html) — `imageio.get_writer(path, format="mp4", mode="I", fps=N)` + `writer.append_data(ndarray)` API (HIGH).
- Record a Qt window with PySide6 + imageio (https://www.loekvandenouweland.com/content/record-window-pyside-python.html) — pattern for capturing `QWidget.grab()` → ndarray → `imageio.get_writer` (MEDIUM; community blog but matches the project's existing render-bridge ndarray shape).
- PySide6.Qt3DCore.QTransform (https://doc.qt.io/qtforpython-6/PySide6/Qt3DCore/QTransform.html) — Qt3D exists but is a separate rendering stack (MEDIUM).
- florianblume/qt3d-gizmo (https://github.com/florianblume/qt3d-gizmo) and fferri/qt3d-transform-gizmo (https://github.com/fferri/qt3d-transform-gizmo) — community Qt3D gizmo libs, C++/QML, low-stars, unmaintained (MEDIUM — rejection evidence).
- viser docs / GitHub (https://github.com/viser-project/viser/) — web-based (WebSocket + browser/three.js), not a native Qt widget; would require `QWebEngineView` to embed (HIGH — rejection evidence).
- personalrobotics/mj_viser (https://github.com/personalrobotics/mj_viser) — Viser `scene.add_transform_controls()` is the gizmo source, confirming the gizmo lives in the web stack, not in PySide6 (MEDIUM).
- MuJoCo Python docs (https://mujoco.readthedocs.io/en/3.3.7/python.html) — native `mujoco.viewer` has mouse-drag perturbation but no DCC-style transform gizmo; lighting via `<light>`/`model.light_*` (HIGH).
- Project files (HIGH confidence, direct inspection): `pyproject.toml` (dep groups), `src/surg_rl/editor/viewport.py` (existing `ViewportCanvas` + `_CameraOffset` + `QTimer.singleShot(50,...)` = the 20 fps ceiling), `src/surg_rl/scene_generation/vision_parser.py` (existing API-based VLM via OpenAI/Anthropic/Ollama), `src/surg_rl/scene_generation/text_parser.py` (existing LLM parser), `.planning/PROJECT.md` (v0.5.0 architecture decisions: no `mjpython`, PEP 562 lazy imports, custom `ViewportCanvas`).

---

*Stack research for: surgical-robotics RL editor depth + scene generation (v0.7.0)*
*Researched: 2026-07-15*
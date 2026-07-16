# Project Research Summary

**Project:** surg-rl — v0.7.0 GUI Editor Depth & Scene Generation
**Domain:** Surgical-robotics RL training system — deepening an existing, shipped PySide6 scene editor + extending an existing LLM/VLM scene-generation pipeline
**Researched:** 2026-07-15
**Confidence:** HIGH

## Executive Summary

v0.7.0 is a **depth milestone on a shipped app**, not a greenfield build. The existing v0.5.0 PySide6 editor (`src/surg_rl/editor/`) and scene-generation pipeline (`src/surg_rl/scene_generation/`) are the fixed dependency surface; research focused on what it takes to deepen those two subsystems without regressing the v0.5.0 architectural decisions (stock interpreter — no `mjpython`; custom `ViewportCanvas(QWidget)` painted from a numpy-rasterized `QPixmap` — no live OpenGL context on macOS; PEP 562 lazy `surg_rl.rl` re-exports). The marquee outcome is a render/sim-decoupled, animated, >30fps viewport with transform gizmos, plus the three known GUI bugs closed. Net new pip dependencies for the whole milestone: **exactly one — `imageio-ffmpeg>=0.6.0`** (added to the existing `[gui]` extra; imageio 2.37 no longer bundles ffmpeg by default, and GUI-13 recording needs it). Every other v0.7.0 capability is code on top of already-installed deps.

The recommended approach follows a strict dependency chain: **GUI first, scene generation second** (per PROJECT.md). The keystone is **render/sim decoupling** (GUI-11): split the current monolithic `_tick()` (which calls `simulator.render()` every 50ms but NEVER calls `simulator.step()`) into a `SimStepWorker(QObject)` on a `QThread` that advances physics at a fixed sim-rate and a `RenderPollLoop` on the UI thread that renders at its own cadence. That single change fixes two of the three known bugs and unblocks every other viewport feature (multi-view, gizmos, recording all need a responsive, animated viewport). Scene generation (GEN-01..05) follows once the editor is stable; GEN-02 (structured-output + bounded repair loop) is the keystone for the gen side and is reused by GEN-03 (VLM) and GEN-05 (clarifying questions).

Key risks: (1) the three known GUI bugs are the proof-of-criterion for the whole milestone — they must be fixed by decoupling, not by a naive "add a second timer" or "inject step() into _tick" patch; (2) the gizmo feature has a genuine, unresolved approach disagreement between researchers (see Open Questions below) that needs phase-specific research before committing; (3) the `QThread` worker-object teardown pattern (`quit()`->`wait()`->`deleteLater`) is currently half-wired and gets worse as VLM/clarifying/recorder workers are added — `closeEvent` must gain a teardown harness; (4) persistent edits (lights, gizmos, transforms) must round-trip through `SceneDefinition` + `SceneUndoStack`, not poke simulator attrs directly, or undo/save/revert silently corrupt.

## Key Findings

### Recommended Stack

The stack delta is minimal because this is a depth milestone on an app that already validated its stack in v0.5.0. **Exactly one new package is a hard requirement**; everything else is code on top of existing deps. See STACK.md for the full rationale and the "What NOT to Use" table (rejects `mjpython`, Qt3D, `viser`, `langchain`/`llamaindex`, `qimage2ndarray`, `pyqtgraph`, `PyOpenGL`/`moderngl`, PyAV).

**Core technologies (delta only):**
- **`imageio-ffmpeg>=0.6.0`** — FFmpeg backend for `imageio.get_writer(format="mp4")` — the single mandatory new dep; needed for GUI-13 in-app recording. imageio 2.37 gated ffmpeg behind an extra; without this, `get_writer` raises `IndexError: Could not find module "imageio-ffmpeg"`. Ships pre-built ffmpeg binaries for macOS/Linux/Windows. Add to `[gui]` extra.
- **Existing `[gui]`/`[llm]`/`[vision]`/`[assets]`/`[physics]` extras** — cover the rest. GUI-12 lighting uses native MuJoCo `<light>`/`mjvOption` + PyBullet `getCameraImage` lighting kwargs (no dep). GUI-12 multi-view is N×`ViewportCanvas` + N `render()` calls (no dep). GUI-12 gizmos, GUI-14 file/IO, GUI-15 perf are pure code (no dep). GEN-01..05 are prompt engineering + structured-output + multi-turn conversation on the already-installed OpenAI/Anthropic/Ollama SDKs (no dep). Local VLM for GEN-03 (optional) uses the existing `[vision]` extra (`torch`+`torchvision`+`transformers`) — weights download at runtime.

**Critical version requirements:**
- `imageio-ffmpeg>=0.6.0` compatible with imageio>=2.31.0 (already pinned) and Python 3.10–3.13.
- OpenAI Structured Outputs (GEN-03) requires `gpt-4o-2024-08-06` or later; older OpenAI + Anthropic + Ollama fall back to the freeform JSON path (kept as fallback).

### Expected Features

See FEATURES.md for the full landscape, dependency graph, and MVP cut.

**Must have (table stakes — close the known bugs + make the editor feel real):**
- **GUI-11 render/sim-decoupled viewport** — animated, >30fps preview. Fixes bugs #1 (immobile) + #2 (<10fps). The milestone's marquee; the keystone everything else depends on. (HIGH)
- **GUI-15 dock-state persistence/reset + crash-recovery autosave** — fixes bug #3 (layout not reset on rerun); cheapest, highest-trust fix. (LOW-MEDIUM)
- **GUI-12 transform gizmos (translate/rotate/scale) + standard view presets** — the defining 3D-editor feature; without gizmos the editor is a form with a preview. (HIGH)
- **GUI-13 multi-select + copy/paste/duplicate + keyboard shortcuts** — closes the editing-UX gap with the existing tree/form. (MEDIUM)
- **GUI-14 recent-files fix + autosave wiring** — small but completes the file-IO story; fixes the duplicated `_refresh_recent_menu` block in passing. (LOW-MEDIUM)
- **GEN-01 task templates aligned to the 6 reward types** — every reward class (suturing/knot_tying/needle_passing/grasping/cutting/dissection) needs at least one canonical template + difficulty variants. (MEDIUM)
- **GEN-02 LLM structured output + bounded repair loop** — the gen-side keystone; reused by GEN-03 and GEN-05. Bounded = 1 repair attempt by default, max 2, then graceful degradation. (MEDIUM)

**Should have (competitive differentiators):**
- **Multi-view (quad-view)** — N viewports sharing one sim-state source; only viable after GUI-11 decoupling. (HIGH; depends on GUI-11)
- **In-app recording / video capture** — research/demo convenience; needs `imageio-ffmpeg`. (MEDIUM; needs the new dep)
- **Interactive lighting controls** — expose `LightConfig` via `FieldRenderer` widgets; native to both backends. (LOW-MEDIUM)
- **VLM image→scene (GEN-03)** — endoscopic/sim screenshot → editable `SceneDefinition`; no surgical-RL competitor does this in-editor. (HIGH; depends on GEN-02)
- **Procedural / batch scene generation (GEN-04)** — parameter sweeps over difficulty/tissue/instrument for curriculum/benchmark datasets. (MEDIUM-HIGH; depends on GEN-01)
- **Interactive LLM clarifying-question flow (GEN-05)** — 2-turn protocol using the existing `BaseParser.parse_with_context` hook; LLM asks 1-3 focused questions before generating. (MEDIUM; depends on GEN-02)
- **Selection sync (tree↔viewport↔form)** — tree→form works; viewport→tree needs the gizmo pick infrastructure. (MEDIUM; depends on GUI-12)
- **Snapping (grid/surface/vertex)** — grid snap is cheap; surface/vertex need GUI-12 pick infra. (MEDIUM-HIGH)

**Defer (v2+):**
- QOpenGLWidget migration / true 3D scene-graph viewport (Qt3D) — full render-bridge rewrite; v2.0 decision, not v0.7.0.
- `mjpython` re-exec for native MuJoCo macOS rendering — explicitly rejected (regresses the v0.5.0 main-thread hang fix).
- Fine-tuning a SurgVLM-style domain VLM in-repo — multi-GPU training infra out of charter; use hosted models via existing provider abstraction.
- Multi-user networked collaborative editing — out of scope (single-user desktop tool).
- Helm/K8s editor deployment — editor is a desktop tool, not a deployment target.

### Architecture Approach

See ARCHITECTURE.md for the full system overview, component table, project structure, and 6 patterns with implementation sketches.

**Major components (NEW + MODIFIED):**
1. **`editor/sim_step_worker.py` — `SimStepWorker(QObject)` [NEW]** — moved to a `QThread`; advances `simulator.step()` at a fixed sim-rate with an accumulator; emits `stepped` signals; supports pause/resume/step-one. Independently testable (mock simulator, assert step calls + signals) without importing any Qt widget.
2. **`editor/render_poll_loop.py` — `RenderPollLoop(QObject)` [NEW]** — UI-thread QTimer-driven render polling at target fps; calls `simulator.render()` and pushes `QPixmap` to `ViewportCanvas` via signal. Extracted from `_tick()` so the timer strategy (QTimer vs vsync) is swappable without touching widget code.
3. **`editor/multi_view.py` — `MultiViewManager` [NEW]** — N viewport panels sharing one sim-state source; each view is a `render()` call with different camera params (NOT multiple GL contexts).
4. **`editor/gizmo_overlay.py` — `GizmoOverlay` [NEW]** — translate/rotate handles; **rendering approach is an open question — see Open Questions below.**
5. **`editor/frame_recorder.py` — `FrameRecorder` [NEW]** — captures rendered frames; encodes to video via imageio-ffmpeg (`imageio.get_writer`). Capture on main thread (copy bytes), encode on a `QThread` `RecorderWorker` with a bounded `deque(maxlen=N)`.
6. **`editor/dock_state.py` — `DockStateManager` [NEW]** — `saveState()`/`restoreState()` wrapper; captures a factory-default `QByteArray` at first show for "Reset Layout"; the bug fix for layout-not-reset-on-rerun.
7. **`editor/vlm_panel.py` — `VLMPanel` [NEW]** — image-upload → scene panel; mirrors `LLMPanel` pattern.
8. **`editor/viewport.py` — `ViewportPanel` [MODIFIED]** — split `_tick()` into sim-step + render-poll; add `update_scene()` method (swap scene reference, don't recreate widget).
9. **`editor/main_window.py` — `EditorWindow` [MODIFIED]** — fix `_refresh_viewport_and_tree` to use `update_scene()` not recreate; wire `DockStateManager`; add `aboutToClose` signal for panel teardown.
10. **`simulators/base_simulator.py` + `mujoco_simulator.py` + `pybullet_simulator.py` [MODIFIED]** — extend `render()` signature with additive `camera_params`, `light_params`, `render_flags`, `gizmo_target`, `gizmo_mode` kwargs (backwards-compatible `None` defaults).
11. **`scene_generation/clarify_flow.py` — `ClarifyFlow` [NEW]** — pure-Python conversation-state manager for GEN-05 multi-turn clarification; testable headless.
12. **`scene_generation/batch_generator.py` — `BatchGenerator` [NEW]** — parameterized procedural gen over difficulty/instrument/organ axes; wraps `SceneComposer.generate_batch()`.
13. **`scene_generation/text_parser.py` / `vision_parser.py` / `scene_composer.py` / `templates.py` [MODIFIED]** — clarify flow, OpenAI Structured Outputs (`response_format: json_schema` using `SceneDefinition.model_json_schema()`), `generate_batch()`, more templates.

**Key patterns to follow:** (1) Render/sim decoupling via QThread worker (keystone); (2) multi-view via multiple `render()` calls, NOT multiple GL contexts; (3) gizmo overlay (approach TBD — see Open Questions); (4) dock-state persistence with factory-default `QByteArray` + `update_scene()` instead of widget recreation; (5) VLM via OpenAI Structured Outputs with freeform fallback for Anthropic/Ollama; (6) clarifying-question flow as an explicit state machine (`IDLE→AWAITING_QUESTIONS→AWAITING_ANSWERS→GENERATING→DONE/FAILED`).

### Critical Pitfalls

See PITFALLS.md for all 8 critical pitfalls, the technical-debt table, integration gotchas, performance traps, security mistakes, UX pitfalls, the "looks done but isn't" checklist, and recovery strategies.

**Top pitfalls with prevention strategies:**

1. **Render/sim coupling (Pitfall 1)** — the "<10fps" and "immobile preview" bugs share a single root cause (see Bug Reconciliation below). The naive fixes (inject `step()` into `_tick`, or add a second `QTimer.singleShot` on the main thread) double the bug: coupled cadence gives slow-motion playback, two `singleShot` chains cause CGL/EGL context contention. **Prevention:** ONE render timer on the main thread; sim step loop on a `QThread` worker with a fixed-step accumulator; render-poll reads the latest snapshot only. Cap snapshot publish rate (30Hz) so a fast sim doesn't flood the main thread.
2. **Dock-state restore silently no-ops (Pitfall 2)** — `saveState()`/`restoreState()` identify widgets by `objectName`; new docks added without `objectName` are invisible to save/restore; `restoreState()` in `__init__` before docks exist silently returns `true` while applying nothing; hand-rolled "Reset Layout" re-`addDockWidget`s but ignores tabification/floating/closed state. **Prevention:** every new `QDockWidget` sets a unique `objectName` before `addDockWidget` (add a lint/test); capture a factory-default `QByteArray` once at first show and "Reset Layout" restores THAT via `restoreState(default_state)`; defer user `restoreState()` to `showEvent` (guarded) or `QTimer.singleShot(0,...)`.
3. **QThread worker leak on close (Pitfall 3)** — `EditorWindow.closeEvent` stops the viewport but NOT the LLM/VLM `QThread`; closing mid-call emits `finished` into a deleted panel → segfault or `RuntimeError: Internal C++ object already deleted`. v0.7.0 widens the window (VLM calls are multi-second; clarifying flow chains round-trips). `finished()` emits BEFORE the thread is truly terminated; `deleteLater` before `wait()` crashes. **Prevention:** give every long-running panel a `stop()` (cooperative cancel flag + `thread.quit()` + `thread.wait(3000)`); `EditorWindow.closeEvent` calls every panel's `stop()` BEFORE `super().closeEvent()`; add an `aboutToClose` signal so new panels auto-wire teardown; never `deleteLater` a thread you haven't `wait()`ed on.
4. **VLM payload/cost/JSON/path (Pitfall 4)** — large PNG base64 blows payload limits and costs $0.01-0.05/call (batch = real money); the non-greedy `_JSON_OBJ_RE` matches the FIRST `{...}` in nested scene JSON → truncated parse; VLMs hallucinate `urdf_path`/mesh paths from the schema example → 404 at sim load; non-determinism breaks batch reproducibility. **Prevention:** downscale to ≤1024px JPEG q85; replace regex with a brace-balanced extractor or provider JSON mode; post-process through a "path sanitizer" that nulls non-existent paths → OBJ fallback; pin `temperature=0` + record `generation_seed`/`system_fingerprint` for batch; add a per-run cost estimator.
5. **Edits bypass schema (Pitfall 7)** — multi-view/lighting/gizmo edits are tempting to implement by poking simulator attrs (the existing `_editor_camera_*` hack). Those drift from `SceneDefinition` so undo/save/revert silently corrupt. **Prevention:** persistent edits (lights, camera, gizmo placements, transforms) MUST be written to `SceneDefinition` first (`model_copy(update={...})`), pushed onto `SceneUndoStack`, THEN applied to the live simulator. Ephemeral editor-only state (orbit offset, gizmo hover) stays on the panel and is explicitly NOT undoable. Test: edit light → undo → reverts in tree AND render; edit light → save → reload → persists.

### Bug Reconciliation — the three known GUI bugs

The three known GUI bugs are not three independent issues. Researchers agree on the root-cause mapping:

**Bugs #1 (<10fps) and #2 (immobile preview) share a SINGLE root cause** in `src/surg_rl/editor/viewport.py`: the `_tick` method calls `self._simulator.render(...)` every 50ms but NEVER calls `simulator.step()`, and the fixed `QTimer.singleShot(50, _tick)` self-rescheduling loop caps the theoretical rate at 20Hz while the synchronous `render()` call (50-120ms on macOS software-rendered PyBullet) blocks the Qt event loop. Effective fps drops to ~6-10. The preview is a frozen single frame because physics never advances. **Both are fixed by the same architectural change: GUI-11 render/sim decoupling** — a `SimStepWorker` on a `QThread` calls `simulator.step()` at a fixed sim-rate (e.g., 50Hz) with an accumulator so preview speed is independent of render rate; the UI-thread `RenderPollLoop` renders the latest snapshot at its own cadence (e.g., 30Hz) and yields to the event loop between frames. Do NOT split these into a separate bug-fix phase — they ARE the decoupling proof-of-criterion.

**Bug #3 (dock-panel layout not reset on rerun) is a SEPARATE root cause** in `EditorWindow`: a QMainWindow saveState/restoreState + widget-destruction issue. `_refresh_viewport_and_tree()` (called on New/Open/undo/redo/LLM-accept) creates new `ViewportPanel`/`SceneTreeView` instances and calls `setCentralWidget()`/`setWidget()`, destroying old widgets and resetting dock geometry. The existing `_action_reset_layout` only re-`addDockWidget`s the 3 default docks and doesn't restore tabification/floating/closed state. **Fix:** add `update_scene(new_scene)` methods to `ViewportPanel` and `SceneTreeView` that swap the scene reference and rebuild internal state in place (no widget recreation); capture a factory-default `QByteArray` at first show and have "Reset Layout" call `restoreState(default_state)`; give every new dock a unique `objectName`. This is owned by **GUI-15**, separate from GUI-11.

## Open Questions for Phase-Specific Research

### Gizmo rendering approach — deliberate cross-researcher disagreement

There is a genuine, unresolved disagreement between researchers on how to render transform gizmo handles (translate/rotate/scale manipulators) on the image-based `ViewportCanvas`. The roadmapper should flag the gizmo phase for `/gsd-plan-phase --research-phase <N>` so this is resolved with a working spike before committing to an approach. Do NOT silently pick one.

**Option A — 2D QPainter overlay on `ViewportCanvas` (Stack + Pitfalls researchers favor):**
- Draw gizmo handles as `QPainter` primitives in `ViewportCanvas.paintEvent` after the pixmap; project 3D handle world-positions to screen space using the existing `_CameraOffset` camera params (azimuth/elevation/distance/target) already tracked in `viewport.py`. Hit-test in 2D.
- **Pros:** no new dep; reuses existing camera params; avoids any 3D-scenegraph or render-bridge rewrite; keeps gizmo code in the editor package (no per-backend simulator code).
- **Cons:** **fragile projection** — duplicates the render pipeline's projection math; gizmo handle 2D positions computed once don't track camera changes without re-projection; depth occlusion is lost (gizmo always paints on top); 2D-to-3D ray-pick for mouse-click→world-space is manual matrix math.
- Stack.md explicitly recommends this and rejects Qt3D/`viser` for the gizmo.

**Option B — render gizmos in the 3D pipeline (Architecture researcher favors):**
- Draw gizmo handles into the offscreen render pipeline before returning the numpy array: MuJoCo adds gizmo geoms to the `mjvScene` before `mjr_render()`; PyBullet draws debug lines (`addUserDebugLine`).
- **Pros:** **world-space correct** — gizmos stay in world space, track the camera automatically, get depth occlusion for free, scale with camera distance; no duplicated projection math; no 2D-to-3D ray-pick.
- **Cons:** **limited PyBullet debug-line fidelity** — no torus rings for rotation handles, basic translate axes only; requires per-backend gizmo rendering code in the simulator package (extends the `render()` signature with `gizmo_target`/`gizmo_mode`); couples gizmo rendering to the simulator rather than the editor.
- Architecture.md raises this as Pattern 3 and Anti-Pattern 5 explicitly rejects the 2D-overlay approach.

**Tradeoff summary:** 2D overlay avoids a 3D-scenegraph/render-bridge rewrite but is fragile under camera changes and loses depth occlusion; 3D pipeline is world-space correct but PyBullet fidelity is limited and it pushes gizmo code into the simulator package. The decision affects which package owns gizmo rendering (`editor/gizmo_overlay.py` vs `simulators/*`) and whether the `render()` signature gains gizmo kwargs. Resolve with a working spike on a real cutting/fluid scene before committing.

## Implications for Roadmap

Based on combined research, suggested phase structure (continues from v0.6.0 phase 40.1; GUI first, scene generation second per PROJECT.md):

### Phase 41: Render/Sim Decoupling + Bug Fixes (GUI-11 + GUI-15)

**Rationale:** This is the foundation. Every other viewport feature (multi-view, gizmos, recording) depends on a responsive, animated viewport. Bugs #1 + #2 share the decoupling root cause; bug #3 is the separate dock-state root cause. Build both root-cause fixes together because they're the proof-of-criterion for the whole milestone and they unblock everything else.

**Delivers:**
- `editor/sim_step_worker.py` — `SimStepWorker(QObject)` on QThread (fixed-step accumulator, 50Hz sim, 30Hz snapshot publish cap)
- `editor/render_poll_loop.py` — `RenderPollLoop(QObject)` on UI thread (30Hz render-poll, yields between frames)
- `editor/dock_state.py` — `DockStateManager` (factory-default `QByteArray` capture + `restoreState(default)` reset + `objectName` enforcement)
- Modify `editor/viewport.py` — split `_tick()`; add `update_scene()` (swap scene, don't recreate)
- Modify `editor/main_window.py` — fix `_refresh_viewport_and_tree` to use `update_scene()`; wire `DockStateManager`; add `aboutToClose` signal; fix duplicated `_refresh_recent_menu` block
- Modify `editor/_settings.py` — add dock-state + viewport-pref keys (target_fps, sim_rate_hz, lighting)
- Centralize the self-rescheduling `QTimer.singleShot` guard into a `RenderLoop`/`PollLoop` helper so new timers can't forget the guard (Pitfall 8)
- `closeEvent` teardown harness: enumerate every long-running subsystem, call `stop()` before `super().closeEvent()`

**Addresses:** GUI-11, GUI-15 (bug-fix portion), bugs #1/#2/#3
**Avoids:** Pitfalls 1, 2, 3, 8

### Phase 42: Multi-View + Lighting + Render API Extensions (GUI-12 partial)

**Rationale:** Depends on Phase 41 (needs a responsive viewport to render multiple views). Multi-view is the highest-value viewport-depth feature after decoupling. Lighting is native to both backends and cheap. The `BaseSimulator.render()` signature extension is additive and backwards-compatible.

**Delivers:**
- `editor/multi_view.py` — `MultiViewManager` (N views sharing one sim-state source; stagger views across frames or lower per-view res to keep fps)
- Modify `simulators/base_simulator.py` — extend `render()` signature with `camera_params`, `light_params`, `render_flags` (additive kwargs, `None` defaults)
- Modify `simulators/mujoco_simulator.py` — camera/light/flag param plumbing (`MjvCamera`, `mjvOption.flags`, `mjvScene` light slots)
- Modify `simulators/pybullet_simulator.py` — camera params (partial via existing `_editor_camera_*`), light params (limited: shadow toggle + renderer enum), multi-view (multiple `getCameraImage` calls; every result through `_normalize_pb_rgb()`)
- Standard view presets (front/side/top/perspective) as azimuth/elevation/distance triples pushed into `_camera_offset`
- Establish the **schema-first edit contract** (Pitfall 7): persistent light/camera edits round-trip through `SceneDefinition` + `SceneUndoStack`, not simulator attrs

**Addresses:** GUI-12 (multi-view, lighting, view presets)
**Avoids:** Pitfalls 7 (schema-first edits), macOS GL re-probing (preserve `_renderer_available=False` short-circuit)
**Uses:** existing render bridge + `_CameraOffset`; no new dep

### Phase 43: Gizmos + Recording (GUI-12 gizmos + GUI-13)

**Rationale:** Gizmos depend on Phase 42 (need to know which view the gizmo is in and what the camera params are). Recording depends on the decoupled render loop (captures frames from the render-poll loop). This is the phase that needs the gizmo-rendering-approach spike (see Open Questions) — flag for `--research-phase`.

**Delivers:**
- `editor/gizmo_overlay.py` — `GizmoOverlay` (translate/rotate modes; approach A or B per spike)
- Depending on spike outcome: either 2D `QPainter` overlay using `_CameraOffset` projection (Option A), OR per-backend gizmo rendering in `simulators/mujoco_simulator.py` (`mjvScene` geoms) + `simulators/pybullet_simulator.py` (debug lines) with `gizmo_target`/`gizmo_mode` kwargs (Option B)
- `editor/frame_recorder.py` — `FrameRecorder` using `imageio.get_writer(format="mp4")` + `imageio-ffmpeg`; capture on main thread (copy bytes into bounded `deque(maxlen=N)`), encode on a `QThread` `RecorderWorker`; `closeEvent` flushes + `wait(5000)`
- Add `imageio-ffmpeg>=0.6.0` to the `[gui]` extra in `pyproject.toml` (the single new dep)
- Multi-select + copy/paste/duplicate in `SceneTreeView` (`ExtendedSelection`); keyboard shortcuts (`QShortcut`s for Ctrl+C/V, X/Del, Ctrl+D)
- Selection sync (tree↔viewport↔form) using the gizmo pick infrastructure

**Addresses:** GUI-12 (gizmos), GUI-13 (editing UX, recording)
**Avoids:** Pitfalls 6 (recording thread contention — bounded queue, encode off-main, flush on close)
**Uses:** `imageio-ffmpeg>=0.6.0` (new dep)

### Phase 44: Editing UX + File/IO Polish (GUI-14 + GUI-15 UX)

**Rationale:** Editing UX (better tree/form interactions, multi-select keyboard nav, drag-reorder) and file/IO (recent files, export/import, autosave wiring, crash-recovery prompt on launch) are independent of the viewport features. Lower-priority than the viewport bugs but completes the editor story. Can proceed in parallel with Phase 42/43 if resources allow.

**Delivers:**
- Autosave: `QTimer`-driven (60-120s interval) to `~/.surg_rl/autosave/<hash>.json` with dirty-flag; startup recovery prompt if recovery file newer than last explicit save
- Recent files fix (deduplicate `_refresh_recent_menu` block; cap 10-20)
- Export/import menu items (`QFileDialog`); validation feedback on load
- Tree-view multi-select keyboard navigation; drag-reorder improvements

**Addresses:** GUI-14, GUI-15 (UX portion)
**Avoids:** Pitfall 3 (autosave worker teardown via the Phase 41 `aboutToClose` harness)

### Phase 45: Scene Generation — Templates + Structured Output (GEN-01 + GEN-02)

**Rationale:** After GUI is stable. GEN-01 gives the repair loop a graceful-degradation fallback (template as the "safe default"). GEN-02 is the gen-side keystone — the bounded repair loop is reused by GEN-03 (VLM) and GEN-05 (clarifying questions). Build it once.

**Delivers:**
- Modify `scene_generation/templates.py` — add templates so every reward type (suturing/knot_tying/needle_passing/grasping/cutting/dissection) has ≥1 canonical template + 2-3 difficulty variants (easy/medium/hard)
- Modify `scene_generation/text_parser.py` — structured output (`response_format: json_schema` / tool-calling where supported) + bounded repair loop (1 attempt default, max 2, then template graceful-degradation); feed `ValidationError` back as model-readable prose
- Tests: repair loop unit test (malformed JSON → 1 repair → valid scene); template coverage test (every reward type has a template)

**Addresses:** GEN-01, GEN-02
**Avoids:** Pitfall 4 (JSON extraction — use brace-balanced or provider JSON mode, not non-greedy regex)
**Uses:** existing OpenAI/Anthropic/Ollama SDKs; no new dep

### Phase 46: Scene Generation — VLM + Batch + Clarify (GEN-03 + GEN-04 + GEN-05)

**Rationale:** GEN-03 reuses the GEN-02 repair loop; GEN-04 reuses GEN-01 templates + `SceneComposer`; GEN-05 reuses the GEN-02 structured-output protocol and the existing `BaseParser.parse_with_context` hook. All three are independent of each other and can be parallelized within the phase.

**Delivers:**
- `editor/vlm_panel.py` — `VLMPanel` (image-upload → scene; mirrors `LLMPanel`; 2D overlay preview so user sees what the VLM "saw")
- Modify `scene_generation/vision_parser.py` — OpenAI Structured Outputs path (`SceneDefinition.model_json_schema()`); freeform fallback for Anthropic/Ollama; image preprocessing (≤1024px JPEG q85); path sanitizer (null non-existent `urdf_path` → OBJ fallback)
- `scene_generation/batch_generator.py` — `BatchGenerator` (parameter sweep over difficulty/tissue/instrument/pose jitter → N `SceneDefinition` files); pin `temperature=0` + record `generation_seed`/`system_fingerprint`; per-run cost estimator
- Modify `scene_generation/scene_composer.py` — `generate_batch()`
- `scene_generation/clarify_flow.py` — `ClarifyFlow` (explicit state machine `IDLE→AWAITING_QUESTIONS→AWAITING_ANSWERS→GENERATING→DONE/FAILED`; `ConversationState` dataclass; disable Generate during `AWAITING_*`/`GENERATING`; send full history every turn; validation gate before DONE)
- Modify `editor/llm_panel.py` — chat-mode UI for the clarifying-question flow; `stop()` with cooperative cancel + `wait()` (Pitfall 3)
- CLI: `surg-rl generate --image <path>`, `surg-rl generate --batch <spec>`, clarifying-question mode via stdin

**Addresses:** GEN-03, GEN-04, GEN-05
**Avoids:** Pitfalls 4 (VLM payload/cost/path/reproducibility), 5 (clarifying-question state race — explicit state machine, double-spawn guard, seed pinned, full history)
**Uses:** existing SDKs + optional `[vision]` extra for local VLM (no new pin)

### Phase Ordering Rationale

- **GUI first, scene generation second** per PROJECT.md. The editor is the milestone's marquee; scene-gen builds on a stable editor.
- **Phase 41 is the keystone** — render/sim decoupling fixes 2 of 3 bugs AND unblocks every other viewport feature. Bug #3 (dock state) folds in because it's the same `EditorWindow`/`_refresh_viewport_and_tree` touch point and the same `closeEvent` teardown harness.
- **Phase 42 before Phase 43** — gizmos need camera params from multi-view; recording needs the decoupled render loop. The `render()` signature extension (additive kwargs) is established in Phase 42 so Phase 43 gizmos can use it (if the spike picks the 3D-pipeline approach).
- **Phase 44 can parallelize with 42/43** — editing UX and file/IO are independent of the viewport features.
- **GEN-01 before GEN-02** — templates give the repair loop a graceful-degradation fallback.
- **GEN-02 before GEN-03/GEN-05** — the bounded repair loop and structured-output protocol are reused by VLM and clarifying questions. Build it once.
- **GEN-04 needs GEN-01** — batch sweeps need canonical templates per task type.
- **Bug-fix phases are NOT split out** — the three bugs are the proof-of-criterion for Phase 41 (bugs #1/#2) and the dock-state work in Phase 41 (bug #3). Splitting them into a separate "bug-fix phase" would decouple them from the architectural change that fixes them.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 43 (Gizmos + Recording):** the gizmo rendering approach (2D QPainter overlay vs 3D-pipeline rendering) is an unresolved cross-researcher disagreement — flag for `/gsd-plan-phase --research-phase 43` with a working spike on a real cutting/fluid scene before committing. The decision affects which package owns gizmo rendering and whether `render()` gains gizmo kwargs.
- **Phase 46 (VLM + Clarify):** OpenAI Structured Outputs API specifics (`response_format: json_schema` with `SceneDefinition.model_json_schema()` — field name collisions, `strict: True` constraints, max schema depth) need validation against the actual 62-class Pydantic schema; Anthropic tool-use structured-output path is a different code path and needs a spike. Batch-gen reproducibility (`temperature=0` + `system_fingerprint` — does OpenAI guarantee byte-identical output? Probably not; document the residual nondeterminism).
- **Phase 42 (Multi-View):** MuJoCo multi-view via `update_scene(data, camera=cam_id)` per view + PyBullet multi-view via multiple `getCameraImage` calls — verify the `_renderer_available=False` macOS short-circuit still holds with N render calls per frame (one GL context, many cameras — NOT many GL contexts).

Phases with standard patterns (skip research-phase):
- **Phase 41 (Decoupling + Bug Fixes):** QThread worker-object pattern is well-documented (Qt official docs + MuJoCo+PySide6 gists); dock-state save/restore is standard Qt. The pitfalls are known and enumerated in PITFALLS.md.
- **Phase 44 (Editing UX + File/IO):** standard Qt widget work (`QFileDialog`, `QShortcut`, `ExtendedSelection`, `QSettings`); no novel patterns.
- **Phase 45 (Templates + Structured Output):** template registry is additive to existing `templates.py`; structured-output repair loop is a well-known pattern (4 cross-checked sources in FEATURES.md).

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Single new dep (`imageio-ffmpeg>=0.6.0`) verified via `importlib.metadata.requires("imageio")` direct observation + imageio/imageio-ffmpeg GitHub. All other capabilities confirmed as "code on existing deps" via direct inspection of `pyproject.toml` + existing modules. Rejections (Qt3D, viser, mjpython, langchain) backed by v0.5.0 architecture decisions + source inspection. |
| Features | HIGH (in-repo baseline) / MEDIUM (LLM/VLM API specifics) | Table-stakes/differentiator classification cross-checked against Blender/Unity/Maya conventions and 4+ sources for the repair-loop pattern. VLM provider API specifics (Structured Outputs exact behavior) carry MEDIUM uncertainty. |
| Architecture | HIGH | Integration points verified against existing source in `src/surg_rl/editor/`, `src/surg_rl/simulators/`, `src/surg_rl/scene_generation/`. Render/sim decoupling verified against Qt official docs + MuJoCo+PySide6 community gists. VLM Structured Outputs verified against OpenAI cookbook. The gizmo-approach disagreement is deliberately left unresolved (see Open Questions) — this is a known gap, not a confidence loss. |
| Pitfalls | HIGH | Qt dock/thread pitfalls cross-checked against Qt 6 docs + Qt mailing list + Qt Forum. Render/sim and VLM pitfalls derived from reading the existing `editor/viewport.py`, `editor/llm_panel.py`, `scene_generation/vision_parser.py` + the documented v0.5.0 lessons. |

**Overall confidence:** HIGH for the GUI side; MEDIUM for the LLM/VLM API-specific parts of scene generation (GEN-03/GEN-05), which need validation against live provider behavior during Phase 46 planning.

### Gaps to Address

- **Gizmo rendering approach (2D overlay vs 3D pipeline):** unresolved cross-researcher disagreement. Resolve with a working spike on a real cutting/fluid scene during Phase 43 planning (`/gsd-plan-phase --research-phase 43`). The spike should test (a) does the 2D-overlay projection track camera orbits correctly, (b) does PyBullet debug-line fidelity suffice for rotate handles, (c) which package owns gizmo rendering.
- **OpenAI Structured Outputs with the 62-class Pydantic schema:** `SceneDefinition.model_json_schema()` is large; OpenAI's `strict: True` mode has constraints (max schema depth, all fields must be required, no `additionalProperties: false` at arbitrary depth). Needs validation that the generated schema is accepted. Fallback: keep the freeform path.
- **Batch-gen reproducibility:** `temperature=0` does NOT guarantee byte-identical output across runs (model nondeterminism, system fingerprint changes). Document the residual nondeterminism in the scene metadata rather than claiming reproducibility.
- **MuJoCo multi-view on macOS:** the `_renderer_available=False` short-circuit assumes one GL context. Multi-view uses ONE context with many cameras (not many contexts), so it should hold — but verify during Phase 42 planning that N `render()` calls per frame don't re-probe CGL.
- **PyBullet multi-view performance:** N `getCameraImage` calls per frame at ~50-120ms each means N views × render time (4 views = ~8fps). The decoupling keeps the event loop responsive, but the fps drop is real. Mitigation (stagger views / lower per-view res) needs validation during Phase 42.
- **Anthropic structured-output path:** Anthropic has no `response_format: json_schema` equivalent; tool-calling is the structured path but is a different code path than OpenAI. Needs a spike for GEN-03.

## Sources

### Primary (HIGH confidence — direct observation / official docs)
- `importlib.metadata.requires("imageio")` on installed imageio 2.37.3 — confirmed `imageio-ffmpeg` is gated behind an `ffmpeg` extra
- `pip show imageio-ffmpeg` — confirmed NOT currently installed
- imageio/imageio-ffmpeg GitHub — v0.6.0 (2025-01-16), pre-built ffmpeg binaries
- imageio v3 docs — `get_writer`/`append_data` API
- Qt 6 QThread docs — `finished()`/`isFinished()`/`wait()` semantics + destructor warning
- Qt 6 QMainWindow docs — `saveState()`/`restoreState()` + `objectName` requirement
- PySide6 QVideoFrameInput / QMediaRecorder docs (Qt 6.8+)
- OpenAI Structured Outputs Guide — `response_format: json_schema`
- MuJoCo Python docs + Renderer source — offscreen rendering, `update_scene()` camera switching, `mjvOption` flags, `mjvScene` lights
- Project files (direct inspection): `pyproject.toml`, `src/surg_rl/editor/viewport.py`, `editor/main_window.py`, `editor/llm_panel.py`, `editor/_settings.py`, `scene_generation/vision_parser.py`, `scene_generation/text_parser.py`, `.planning/PROJECT.md`

### Secondary (MEDIUM confidence — community consensus / cross-checked)
- Qt Forum / Stack Overflow: QThread `finished` race, dock `restoreState` before-show, QTimers vs threading for max performance
- MuJoCo + PySide6 decoupled render gist (cherishyuan)
- OpenAI Cookbook: GPT-4 Vision with Function Calling (Pydantic + instructor)
- LLM structured-output repair loop — OutputGuard, claudelab.net, dev.to repair-loop patterns (4 cross-checked sources)
- VLM image→3D-scene — LayoutVLM, SceneLM, SurgVLM (arXiv)
- ClarQ-LLM / ClarifyAgent — clarifying-question slot tracking
- 3D editor gizmo/snapping/multi-select conventions — Blender 5.1 Manual, Unity 6.4 Manual
- florianblume/qt3d-gizmo, fferri/qt3d-transform-gizmo — rejection evidence (unmaintained C++/QML)
- viser docs / GitHub — rejection evidence (web-based, requires QWebEngineView)

### Tertiary (LOW confidence — needs validation during planning)
- OpenAI Structured Outputs behavior with the full 62-class `SceneDefinition` schema (`strict: True` constraints, max depth) — validate during Phase 46 planning
- Anthropic tool-use structured-output path for VLM — different code path; needs a spike
- Batch-gen reproducibility with `temperature=0` (residual nondeterminism) — document, don't claim
- PyBullet multi-view performance at 4 views (fps estimate) — validate during Phase 42

---
*Research completed: 2026-07-15*
*Ready for roadmap: yes*
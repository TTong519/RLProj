# Feature Research

**Domain:** Surg-RL v0.7.0 — GUI Editor Depth (GUI-11..15) + Scene Generation (GEN-01..05) + GUI bug-fix pass
**Researched:** 2026-07-15
**Confidence:** HIGH (in-repo baseline + cross-checked web sources for standard 3D-editor UX conventions); MEDIUM for LLM/VLM provider API specifics (external packages)

## Scope Note

This is a **feature-depth milestone**, not a greenfield build. The existing v0.5.0 PySide6 editor (`src/surg_rl/editor/`) and scene-generation pipeline (`src/surg_rl/scene_generation/`) are treated as fixed dependencies — they are NOT re-researched as new. The "feature landscape" below maps each v0.7.0 target feature to standard 3D-editor / scene-generation UX conventions, classifies it as table stakes / differentiator / anti-feature, notes complexity, and calls out the dependency on existing v0.5.0 features.

**Existing baseline (already built — the dependency surface):**
- `ViewportPanel` + `ViewportCanvas` (custom QWidget, not QLabel) — 20 Hz `QTimer.singleShot(50, _tick)` self-rescheduling render loop that calls `simulator.render()` only (NEVER `simulator.step()` — root cause of the "immobile preview" bug). Orbit/pan/zoom via mouse; R-key + Ctrl+R camera reset. MuJoCo/PyBullet render bridge with framebuffer-size retry + persistent-failure short-circuit. On macOS stock Python it forces PyBullet DIRECT software renderer.
- `EditorWindow(QMainWindow)` — 3 `QDockWidget`s (Scene Tree, Properties, LLM Prompt-to-JSON) with `objectName`s set; `_action_reset_layout` re-`addDockWidget`s the 3 default docks; `closeEvent` saves `saveGeometry()`+`saveState()` to `_settings`; `_restore_geometry()` restores both. **Recent-files menu exists** (`_settings.recent_files()`) but `_refresh_recent_menu` has a duplicated clear/add block (a latent bug). **No autosave.** No import/export beyond JSON.
- `SceneTreeView` (right-click Add/Remove/Duplicate, drag-reorder, validation icons) + `PropertyForm` (QFormLayout, 150 ms debounced validation via `FieldRenderer` registry: vec3-spinbox, enum-combobox, file-picker, color-picker, range-slider) + `SceneUndoStack` (deep-copy snapshots, 100-level cap) + `LLMPanel` (QThread `TextParserWorker`).
- Scene generation: `text_parser.py`, `vision_parser.py`, `scene_composer.py`, `templates.py` (8 templates: suturing, dissection, manipulation, anastomosis, biopsy, debridement, cauterization, retraction — but NOT cleanly aligned to the 6 task reward types), `base_parser.py` (ABC with `parse` / `parse_with_context` / `validate_scene`). LLM providers openai/anthropic/ollama. 6 surgical task reward types (suturing, knot_tying, needle_passing/insertion, grasping, cutting, dissection).

**The three known GUI bugs (mapped to the feature that addresses them):**
1. **Immobile scene preview** → addressed by **GUI-11** (the render loop calls `render()` but never `step()`; decoupling puts `step()` on a sim worker thread that the render thread samples).
2. **<10 fps** → addressed jointly by **GUI-11** (decouple render from sim so a slow `render()`/`step()` no longer gates the frame loop) and **GUI-15** (perf/stability). The current 50 ms `singleShot` interval caps at 20 Hz AND `render()` blocks the GUI thread, so observed fps is well below the 20 Hz ceiling.
3. **Dock-panel layout not reset on rerun** → addressed by **GUI-15** (dock-state persistence/restore). The current `_action_reset_layout` only re-`addDockWidget`s the 3 default docks; `restoreState()` on startup re-applies the *last saved* (possibly torn-off/closed) state, and there is no "reset to default baseline" QByteArray. Qt has no built-in reset-to-default API.

---

## Feature Landscape

### Table Stakes (Users Expect These in a 3D Scene Editor)

Features users assume exist. Missing = the editor feels like a toy compared to Blender/Unity/Godot.

| Feature | Why Expected | Complexity | Notes / Depends-On |
|---------|--------------|------------|--------------------|
| **Animated (stepping) scene preview** | A "3D viewport" that shows a static frame feels broken; users expect the sim to play. This is bug #1. | MEDIUM | **GUI-11.** Currently `_tick` calls `render()` only. Fix = call `simulator.step()` on a sim worker thread; render thread samples latest sim state. Depends on existing `BaseSimulator.step()`/`render()` and the render bridge. |
| **>30 fps interactive viewport** | Sub-10 fps feels unresponsive; 30+ is the floor for "interactive". Bug #2. | MEDIUM | **GUI-11 + GUI-15.** Decouple render from sim (so a slow step doesn't stall the frame) + raise the frame-loop ceiling (drop the fixed 50 ms `singleShot` for a vsync/`frameSwapped`-driven or `QElapsedTimer`-paced loop targeting 30-60 fps). |
| **Dock layout reset to default** | "View → Reset Layout" that doesn't actually reset (bug #3) erodes trust. | LOW | **GUI-15.** Capture a baseline `saveState()` QByteArray at first show (before user customization) and restore from it on reset. Qt has no built-in reset API — must store the baseline. Depends on existing `_restore_geometry`/`closeEvent` save path. |
| **Transform gizmos (translate/rotate/scale)** | Direct manipulation in the viewport is the defining feature of a 3D editor; editing pose via a number form is a fallback, not the primary path. | HIGH | **GUI-12.** Requires ray-pick against scene objects (overlay on the rendered image, since the viewport is a 2D pixmap not a true 3D scene graph), screen-space axis handles, and write-back to the selected `Pose`. Depends on existing `SceneTreeView` selection + `PropertyForm` pose fields. Hardest part is that the viewport is a *rendered image*, not a real OpenGL scene — gizmos must be drawn as a 2D overlay with depth inferred from the sim's camera matrices. |
| **Standard view presets (front/side/top/perspective)** | Every 3D editor offers 1/3/7-key (Blender) or a view-cube (Unity/Maya) to snap to orthographic standard views. | MEDIUM | **GUI-12.** Map preset → `azimuth/elevation/distance` triples pushed into `_camera_offset` (existing orbit model). Low if reusing the existing camera-offset dict; the work is per-preset bookmark values + a toolbar/pie menu. |
| **Multi-select + copy/paste/duplicate** | Editing one object at a time is acceptable; not being able to select several and duplicate is not. The tree already has Duplicate on right-click — multi-select is the gap. | MEDIUM | **GUI-13.** Extend `SceneTreeView` to `ExtendedSelection`; copy/paste serializes selected nodes to a JSON clipboard payload; paste deserializes into new tree nodes. Depends on existing `SceneTreeView` Add/Remove/Duplicate + `SceneUndoStack`. |
| **Keyboard shortcuts (delete, undo/redo, save, copy/paste)** | Undo/redo (Ctrl+Z/Y), Save (Ctrl+S), Delete (X/Del) are already wired for undo/save; copy/paste/delete-on-key are the gaps. | LOW | **GUI-13.** `QShortcut`s mirroring Blender/Unity conventions (Ctrl+C/V, X or Del for delete, Ctrl+D for duplicate). Low because the actions already exist as menu/tree-context actions — this is wiring. |
| **Recent files menu (working)** | Already present but `_refresh_recent_menu` has a duplicated clear/add block (clears twice, re-adds twice — a latent bug to fix in passing). | LOW | **GUI-14.** Fix the duplicate block; cap recent list (10-20); persist via existing `_settings`. |
| **Autosave / crash recovery** | Losing an edited scene to a crash with no recovery is a trust killer; users expect an autosave/recovery file. | MEDIUM | **GUI-15.** `QTimer`-driven autosave to a recovery file (e.g. `~/.surg_rl/autosave/<hash>.json`) on a 60-120 s interval + dirty-flag; on startup, offer to recover if a recovery file newer than the last explicit save exists. Depends on existing `save_scene` + `_settings`. |
| **More task templates aligned to the 6 reward types** | The 6 reward classes (suturing/knot_tying/needle_passing+insertion/grasping/cutting/dissection) are the product's task spine; templates.py has 8 templates but `manipulation`/`biopsy`/`debridement`/`cauterization`/`retraction`/`anastomosis` don't map 1:1 to those reward types, so a user who picks "knot_tying" has no matching template. | MEDIUM | **GEN-01.** Add/align templates so every reward type has at least one canonical template + 2-3 difficulty variants (easy/medium/hard). Depends on existing `templates.py` `get_template`/`list_templates` registry. |
| **LLM structured-output + validation/repair loop** | LLM-prompt-to-JSON that occasionally returns malformed JSON with no auto-repair feels fragile; feeding the error back to the model and retrying is now the standard pattern. | MEDIUM | **GEN-02.** The current `text_parser` extracts JSON via regex and validates with `SceneDefinition.model_validate`; on `ValidationError` it raises. Add a bounded repair loop (1-2 attempts): feed the validation error back as model-readable prose + return the model's own bad output so it edits. Use `tool_choice`-style structured output where the provider supports it. Depends on existing `TextParser` + `BaseParser.validate_scene`. |

### Differentiators (Competitive Advantage)

Features that set surg-rl apart from a generic scene editor and from off-the-shelf LLM-to-JSON tools.

| Feature | Value Proposition | Complexity | Notes / Depends-On |
|---------|-------------------|------------|--------------------|
| **Render/sim-decoupled viewport (sim animates independently of render fps)** | The viewport shows a live, stepping simulation without the render loop gating physics — rare in lightweight editor tools; most either freeze or step-on-render. | HIGH | **GUI-11.** Two-thread split: a sim worker `QThread` calls `simulator.step()` at the scene's physics timestep and publishes state snapshots; the GUI render thread samples the latest snapshot and calls `render()`. Communicate via signals/slots (`Qt.QueuedConnection`). This is the architecturally interesting differentiator and the foundation for both fps and animation fixes. |
| **Multi-view (synchronized front/side/top/perspective viewports)** | Quad-view (one perspective + three orthographic) synced to the same scene is the pro-tool layout (Blender, Unity, Maya); a single-pane editor cannot. | HIGH | **GUI-12.** Requires N `ViewportPanel` instances sharing one sim-state source (one sim worker, multiple render samplers) — only viable *after* GUI-11 decoupling, since each viewport must sample the same advancing sim state. Camera sync (one view's orbit mirrors to others) is the hard part. Depends on GUI-11. |
| **In-app recording / video capture** | Recording the viewport for demos/papers without an external screen-capture tool is a research-tool differentiator. | MEDIUM | **GUI-12.** Capture each rendered frame to a buffer/`imageio` writer at a fixed fps; encode to mp4/gif. Cheap if the frame buffer already exists; the cost is the encoder dependency + threading. |
| **Lighting controls (interactive)** | Adjusting light color/intensity/position in-editor and seeing it live is a workflow win over editing `LightConfig` numbers blind. | LOW-MEDIUM | **GUI-12.** Expose existing `LightConfig`/`LightType` via a small panel + gizmo on light positions. Mostly UI; the sim already supports lights. |
| **VLM image→scene (surgical screenshot to SceneDefinition)** | No surgical-RL tool turns an endoscopic screenshot or a sim screenshot into an editable scene; this is the differentiator that ties the editor to scene generation. | HIGH | **GEN-03.** `vision_parser.py` already exists with OpenAI/Anthropic/Ollama vision support + image-to-scene prompts, but it is a single-shot VLM call. The SOTA pattern (LayoutVLM, SceneLM, SurgVLM) is VLM-semantic-init + geometric refinement + structured-JSON output. The work: prompt engineering for surgical domain + the repair loop from GEN-02 + a 2D-overlay preview so the user can see what the VLM "saw" before accepting. Depends on existing `VisionParser` + GEN-02 repair loop. |
| **Procedural / batch scene generation (parameter sweeps, dataset gen)** | Generating a dataset of varied scenes (sweeping tissue stiffness, instrument types, difficulty) for curriculum or benchmarking — no competitor offers this in-editor. | MEDIUM-HIGH | **GEN-04.** A parameter-sweep spec (ranges over `DifficultyLevel`, `TissueType`, `InstrumentType`, pose jitter) → batch `SceneDefinition` generation → save N JSON files. Reuse `scene_composer` + `templates`. The UI is a sweep-spec form + a progress bar + an output dir picker. Depends on existing `SceneComposer` + GEN-01 templates. |
| **Interactive LLM clarifying-question flow (GUI + CLI)** | Instead of guessing on an ambiguous prompt, the LLM asks 1-3 focused clarifying questions (single/multi-select, number, freeform) before generating — the "Disambiguation" pattern. | MEDIUM | **GEN-05.** The LLM returns a structured question card (not a scene); the GUI renders it as a form; answers are fed back as context, then the scene is generated. Needs a 2-turn protocol: `parse` → if clarifications needed, return questions → user answers → `parse_with_context(answers)`. `BaseParser.parse_with_context` already exists (it's the hook). CLI mode prints questions and reads stdin answers. Depends on existing `BaseParser.parse_with_context` + `LLMPanel` QThread. |
| **Selection sync (tree ↔ viewport ↔ form)** | Clicking a tree node highlights+focuses it in the viewport; clicking an object in the viewport selects it in the tree and loads its form. Most editors do tree↔form; tree↔viewport is the differentiator here. | MEDIUM | **GUI-13.** Tree→viewport already partially exists (`_on_node_selected` loads the form). Viewport→tree requires the same ray-pick infrastructure as gizmos (GUI-12). Depends on GUI-12's pick infrastructure. |
| **Snapping (grid / surface / vertex)** | Snapping makes precise placement feasible without typing numbers; expected in pro tools, differentiating here because the viewport is image-based. | MEDIUM-HIGH | **GUI-13.** Grid snap = quantize pose to a grid step; surface/vertex snap need ray-pick against sim geometry. Grid snap is cheap (MEDIUM); surface/vertex need GUI-12 pick infra (HIGH). |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems for this specific codebase.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Full Blender/Unity-style true 3D scene-graph viewport (Qt3D / OpenGL scene graph)** | "Make the viewport a real 3D scene graph so gizmos/picking are free." | The viewport is intentionally a *rendered-image* surface (`ViewportCanvas` paints a `QPixmap` from `simulator.render(mode="rgb_array")`) so it works headlessly across MuJoCo/PyBullet with no GL dependency. Switching to Qt3D/QtQuick3D is a rewrite of the render bridge, re-introduces the macOS `mjpython`-thread violation that v0.5.0 explicitly removed, and breaks the PyBullet software-renderer fallback. | Keep the image-based viewport; draw gizmos/selection as a 2D overlay using the sim's camera matrices for depth. GUI-12 picks overlay, not a scene graph. |
| **Re-execing under `mjpython` for native MuJoCo rendering** | "Get the real MuJoCo renderer on macOS." | v0.5.0 decision (commit `3031ed9`): mjpython runs Python on a secondary thread, violating PySide6's main-thread requirement → silent "dock icon, no window" hang. Re-introducing it reverses a documented fix. | Stay in stock interpreter; keep PyBullet DIRECT software renderer for macOS preview (already implemented). |
| **Unbounded LLM repair retries** | "Keep retrying until the JSON validates." | Measured (claudelab.net): free JSON ~2.1% drop, +tool-use 0.6%, +validation+single-repair <0.1%. More than 1-2 repair attempts rarely helps and inflates cost against already-broken output. | Bounded repair loop: 1 repair attempt by default, max 2, then graceful-degradation fallback (safe-by-default scene or a user-visible error). |
| **Replacing the SB3 training stack with DreamerV3-style scene-gen models** | "One ML framework for gen + training." | Breaks 1,513 passing tests, 6-task benchmarking, MARL. Scene-gen and training are separate concerns. | Keep LLM/VLM for generation; SB3/DreamerV3 for training. GEN features are generation-only. |
| **Fine-tuning a surgical VLM (SurgVLM-style) in-repo** | "Domain-specialize the VLM for surgical images." | SurgVLM (2025) trained on 1.81M images / 7.79M conversations — out of scope for a milestone; multi-GPU training infra not in this project's charter. | Use hosted GPT-4o/Claude vision or Ollama vision models via the existing provider abstraction; prompt-engineer for the surgical domain (GEN-03). |
| **True 3D volume fluid rendering in the editor** | "See the 3D fluid sim in the viewport." | Out of Scope per PROJECT.md; `render_fluid_3d` is a z-slice fallback by design (D-18). | 2D xz-slice preview remains the validated default; 3D solver exists behind `dim_3d=True` but is not an editor-rendering target. |
| **Multi-user networked collaborative editing** | "Two researchers edit one scene together." | Out of Scope (real-time multi-user networked surgery). Single-user editor scope. | Single-user editor; file-based sharing (save/send JSON). |
| **Continuous (modal-less) transform with live numeric input** | "Blender's modal G/R/S with typed values." | Modal transforms over an *image-based* viewport (no real scene-graph hit-testing) are fragile and the ROI is low vs. gizmo handles + numeric form. | Gizmo handles for direct manipulation + the existing `PropertyForm` numeric fields for precise entry. |
| **Helm chart / K8s editor-deployment features** | "Ship the editor as a service." | Out of Scope (Helm); the editor is a desktop tool, not a deployment target. | Desktop GUI only; K8s overlays are for training jobs (already shipped v0.6.0). |

## Feature Dependencies

```
GUI-11 (render/sim-decoupled viewport + animated preview + fps)
    ├──fixes──> Bug #1 (immobile preview: _tick never calls step())
    ├──fixes──> Bug #2 (<10 fps: render blocks GUI thread at 50ms cap)
    └──enables──> GUI-12 multi-view (N viewports share one sim-state source)

GUI-12 (multi-view / lighting / gizmos / recording)
    ├──requires──> GUI-11 (shared sim state for multi-view)
    └──enables──> GUI-13 selection sync (viewport->tree needs pick infra built for gizmos)

GUI-13 (editing UX: selection sync, snapping, multi-select, copy/paste, shortcuts)
    ├──requires──> GUI-12 pick infra (for viewport->tree selection sync, surface/vertex snap)
    └──enhances──> existing SceneTreeView (multi-select) + SceneUndoStack (copy/paste snapshots)

GUI-14 (file/IO: scene library, recent files, import/export, autosave)
    ├──enhances──> existing _settings.recent_files + save_scene
    └──part-of──> GUI-15 (autosave is also a crash-recovery mechanism)

GUI-15 (perf/stability: fps, dock-state persistence/restore, crash recovery)
    ├──fixes──> Bug #3 (dock layout not reset on rerun: needs baseline QByteArray)
    ├──requires──> GUI-11 (fps ceiling raised by decoupling)
    └──enables──> crash recovery (autosave from GUI-14 + restore-on-launch)

GEN-01 (more task templates)
    └──aligns-to──> existing 6 task reward types (suturing/knot_tying/needle_passing/grasping/cutting/dissection)

GEN-02 (better LLM text->scene: structured output, validation/repair loop)
    ├──enhances──> existing TextParser + BaseParser.validate_scene
    └──enables──> GEN-03 (VLM image->scene reuses the repair loop)
                > GEN-05 (clarifying-question flow reuses structured-output protocol)

GEN-03 (VLM image->scene)
    ├──requires──> GEN-02 repair loop (VLM output needs the same validation/repair)
    └──enhances──> existing VisionParser (single-shot -> structured + repair + 2D overlay preview)

GEN-04 (procedural/batch scene generation)
    └──requires──> GEN-01 templates (sweep needs canonical templates per task type)
       + existing SceneComposer

GEN-05 (interactive LLM clarifying-question flow)
    ├──requires──> GEN-02 structured-output protocol (questions are structured output)
    └──uses──> existing BaseParser.parse_with_context (already the 2-turn hook)
       + LLMPanel QThread (GUI) + stdin (CLI)
```

### Dependency Notes

- **GUI-11 is the keystone.** It fixes 2 of 3 known bugs AND is the prerequisite for GUI-12 multi-view and GUI-13 viewport-picking. Per PROJECT.md, the <10fps and immobile-preview bugs "likely share a root cause in render/sim coupling" — confirmed by code inspection: `_tick` calls `render()` but never `step()`, and the fixed 50 ms `singleShot` interval caps fps at 20 *before* accounting for `render()` blocking the GUI thread.
- **GUI-12 gizmos are the highest-complexity single feature** because the viewport is an *image*, not a 3D scene graph. Gizmo handles, ray-picking, and depth inference must all be done as a 2D overlay using the simulator's camera matrices. This is the main reason to NOT pursue a Qt3D/scene-graph rewrite (see Anti-Features).
- **GUI-15 dock-state reset is the cheapest bug fix.** Qt has no built-in reset-to-default; the fix is to capture a baseline `saveState()` QByteArray at first `showEvent` (guarded for one-shot, since `showEvent` fires repeatedly) and restore it on "View → Reset Layout". The current `_action_reset_layout` only re-`addDockWidget`s the 3 default docks, which doesn't restore sizes/floating state. Note also: `restoreState()` must be called AFTER all docks are added and the window is shown (Qt Forum) — a one-shot `QTimer.singleShot(0, restore)` is the safe pattern; calling it in the constructor before docks exist silently fails.
- **GEN-02 is the keystone for scene generation.** The bounded repair loop is reused by GEN-03 (VLM output validation) and GEN-05 (clarifying questions are structured output). Build it once.
- **GEN-05 has a ready-made hook.** `BaseParser.parse_with_context` already exists — the clarifying-question flow is a 2-turn use of it: turn 1 returns a question card instead of a scene; turn 2 calls `parse_with_context(answers)`.
- **GUI-13 selection sync (viewport→tree) conflicts with nothing but depends on GUI-12's pick infrastructure.** If GUI-12 gizmos ship, selection sync is a marginal addition; if GUI-12 is descoped, selection sync degrades to tree↔form only (already works).
- **Recent-files latent bug.** `_refresh_recent_menu` clears and re-adds twice (duplicated block in main_window.py). Fix in passing under GUI-14; it does not block any other feature.

## MVP Definition

### Launch With (v1 of the v0.7.0 milestone — GUI-first per PROJECT.md ordering)

The GUI-depth + bug-fix pass is the priority. Minimum to close the known bugs and make the editor feel real:

- [ ] **GUI-11 render/sim-decoupled viewport** — fixes bugs #1 + #2; the animated, >30fps viewport is the milestone's marquee. (HIGH)
- [ ] **GUI-15 dock-state persistence/reset + crash-recovery autosave** — fixes bug #3; the cheapest, highest-trust fix. (LOW-MEDIUM)
- [ ] **GUI-12 transform gizmos (translate/rotate/scale) + standard view presets** — the defining 3D-editor feature; without gizmos the editor is a form with a preview. (HIGH)
- [ ] **GUI-13 multi-select + copy/paste/duplicate + keyboard shortcuts** — closes the editing-UX gap with the existing tree/form. (MEDIUM)
- [ ] **GUI-14 recent-files fix + autosave wiring** — small but completes the file-IO story. (LOW-MEDIUM)

### Add After Validation (v1.x — scene generation, second per ordering)

- [ ] **GEN-01 task templates aligned to 6 reward types** — trigger: editor is stable; templates make hand-authoring faster. (MEDIUM)
- [ ] **GEN-02 LLM structured output + bounded repair loop** — trigger: GEN-01 gives the repair loop a fallback (template as graceful-degradation). (MEDIUM)
- [ ] **GEN-05 interactive LLM clarifying-question flow** — trigger: GEN-02's structured-output protocol is in place; clarifying questions are structured output. (MEDIUM)

### Future Consideration (v2+)

- [ ] **GEN-03 VLM image→scene** — depends on GEN-02 repair loop; highest-complexity gen feature; ship after the text path is robust. (HIGH)
- [ ] **GEN-04 procedural/batch scene generation** — depends on GEN-01 templates + `SceneComposer`; dataset-gen tooling, useful for benchmarking but not core to the editor. (MEDIUM-HIGH)
- [ ] **GUI-12 multi-view (quad-view)** — depends on GUI-11 decoupling; nice-to-have, not launch-critical. (HIGH)
- [ ] **GUI-12 in-app recording/video capture** — research/demo convenience; defer until viewport perf is stable. (MEDIUM)
- [ ] **GUI-12 lighting controls** — incremental polish over the existing `LightConfig` form. (LOW-MEDIUM)

## Sources

- Qt `QMainWindow` saveState/restoreState + dock persistence — Qt 6.11 docs, Qt Forum, Stack Overflow: https://doc.qt.io/QT-6/qmainwindow.html , https://forum.qt.io/topic/157100/restoredockwidget-reports-true-but-doesn-t-restore/2 , https://stackoverflow.com/questions/78958419/how-to-revert-a-qdockwidget-after-calling-restorestate (MEDIUM, cross-checked)
- Qt render/sim thread decoupling — `QQuickRenderControl`, Threaded QOpenGLWidget example, Qt3D `QAspectEngine`: https://doc.qt.io/qtforpython-6/PySide6/QtQuick/QQuickRenderControl.html , https://doc.qt.io/qtforpython-6/examples/example_opengl_threadedqopenglwidget.html (MEDIUM)
- LLM structured-output repair loop — OutputGuard, claudelab.net validation gates, dev.to repair-loop patterns, `validation-loop` PyPI: https://github.com/ndcorder/outputguard , https://claudelab.net/en/articles/api-sdk/claude-api-structured-output-schema-validation-repair-loop , https://dev.to/nhirschfeld/when-an-llm-response-fails-validation-feed-the-error-back-into-the-retry-2e1e (MEDIUM, cross-checked across 4 sources)
- VLM image→3D-scene — LayoutVLM, SceneLM, SurgVLM, Spatial-ORMLLM, GP-VLS: https://arxiv.org/html/2412.02193v2 , https://arxiv.org/html/2506.02555 , https://aclanthology.org/2026.findings-acl.2116.pdf (MEDIUM for pattern; HIGH uncertainty on exact provider APIs)
- Interactive clarifying-question (Disambiguation) pattern — agentpatternscatalog, AnythingLLM agent surveys, Perspective AI Concierge: https://github.com/agentpatternscatalog/patterns/blob/main/patterns/disambiguation.md (MEDIUM, cross-checked)
- 3D editor gizmo/snapping/multi-select conventions — Blender 5.1 Manual, Unity 6.4/2022.3 Manual: https://docs.blender.org/manual/en/latest/editors/3dview/display/gizmo.html , https://docs.unity3d.com/6000.4/Documentation/Manual/PositioningGameObjects.html (MEDIUM, cross-checked)
- In-repo baseline (HIGH confidence): `src/surg_rl/editor/viewport.py`, `main_window.py`, `tree_view.py`, `property_form.py`, `schema_walker.py`, `field_renderer.py`, `undo_stack.py`, `llm_panel.py`, `_settings.py`; `src/surg_rl/scene_generation/{text_parser,vision_parser,scene_composer,templates,base_parser}.py`
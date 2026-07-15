# Pitfalls Research

**Domain:** Adding GUI editor depth (render/sim-decoupled viewport, multi-view, lighting, gizmos, recording, editing UX, file/IO, perf/stability) + scene generation (VLM image→scene, LLM clarifying-question flow, procedural/batch gen, templates) to an existing PySide6 surgical-scene editor that already ships (v0.5.0+).
**Researched:** 2026-07-15
**Confidence:** HIGH (Qt dock/thread pitfalls cross-checked against Qt 6 docs + Qt mailing list; render/sim and VLM pitfalls derived from reading the existing `editor/viewport.py`, `editor/llm_panel.py`, `scene_generation/vision_parser.py` and the documented v0.5.0 lessons).

The hard-won v0.5.0 lessons (mjpython main-thread hang, PEP 562 lazy `surg_rl.rl` re-exports, `ViewportCanvas(QWidget)` not `QLabel`, offscreen-renderer short-circuit, `_normalize_pb_rgb()`, OBJ primitive fallbacks) are RESPECTED here and NOT repeated. This document covers only NEW pitfalls introduced by adding the v0.7.0 feature set to that baseline.

## Critical Pitfalls

### Pitfall 1: Render/sim coupling — the viewport `render()` call and `simulator.step()` share one QTimer loop, so "decouple" by adding a second timer usually doubles the bug instead of fixing it

**What goes wrong:**
The known bugs "<10 fps" and "scene preview immobile (sim not stepping in editor viewport)" share a root cause: the current `_tick` (viewport.py:189-290) calls `self._simulator.render(...)` every 50 ms but NEVER calls `simulator.step()`. The preview is a frozen single frame of the loaded scene. A naive "fix" is to add `simulator.step()` into the same `_tick` before `render()`. That gets the preview moving but couples sim cadence (2 ms physics timestep) to render cadence (50 ms), producing a preview that runs ~25x too slow and makes cutting/fluid look broken. A second naive fix is to spin a SECOND `QTimer` for stepping at a different interval — but two self-rescheduling `QTimer.singleShot` loops racing on the main thread re-enter `render()` while a prior `render()` is mid-framebuffer-acquire, producing CGL/EGL context contention and the exact <10 fps stutter the bug is trying to fix.

**Why it happens:**
The editor viewport was designed as a static scene preview (D-01..D-04), not a live sim playback. The simulator's `step()` advances physics by `dt`; the renderer's `render()` only samples current state. There is no shared clock, no accumulator, and no concept of "preview time" vs "wall time."

**How to avoid:**
Decouple along the correct axis: keep ONE render timer on the main thread (the existing `_tick`), and run the sim step loop on a `QThread` worker (or a `QThreadPool` task) that advances the simulator and publishes state snapshots via a queued signal `state_ready(snapshot)`. The main-thread `_tick` renders the LATEST published snapshot only — it never calls `step()` and never blocks on physics. This is the render/sim-decoupled viewport (GUI-11). Use a fixed-step accumulator inside the sim worker (`accum += wall_dt; while accum >= sim_dt: step(); accum -= sim_dt`) so preview speed is independent of render rate. Cap the snapshot publish rate (e.g. 30 Hz) so a fast sim doesn't flood the main thread with queued signals.

**Warning signs:**
- FPS drops when scene has fluids/cutting (sign `step()` got injected into `_tick`).
- Preview runs in slow-motion or fast-forward (sign timestep mismatch, no accumulator).
- Two `QTimer.singleShot` chains both calling into the simulator (grep for `singleShot` — there should be one render chain).
- CGL/EGL "context already current on another thread" warnings in the log.

**Phase to address:**
GUI-11 (render/sim-decoupled viewport). This is THE phase that fixes the immobile-preview + <10fps bugs — do not split them into a separate bug-fix phase; they are the decoupling proof-of-criterion.

---

### Pitfall 2: Dock-state restore silently no-ops because `objectName` is missing/changed or restore runs before docks exist; "reset layout" only re-adds to areas and ignores tabification/floating/closed state

**What goes wrong:**
The existing `_action_reset_layout` (main_window.py:256-262) re-adds the three docks to their default areas and calls `.show()`. That handles a simple left/right/bottom layout but does NOT restore tabified docks, floating docks, or docks the user closed via the dock context menu — and critically, the known bug "layout does NOT reset on rerun" is that `_refresh_viewport_and_tree` (called on New/Open/undo/redo/LLM-accept) swaps the central widget and re-points the tree dock's widget but never touches dock layout, so a user-rearranged layout persists across scene loads when the user expected a reset. Meanwhile `restoreState()` (main_window.py:370-371) runs once in `__init__` — but Qt requires all docks to exist with unique `objectName` BEFORE `restoreState()` is called, and `saveState()` only captures docks/ toolbars whose `objectName` is non-empty. The current docks DO have objectNames (`dock_scene_tree`, `dock_properties`, `dock_llm`), so restore should work — but the moment v0.7.0 adds new docks (multi-view, lighting, gizmo, recording) WITHOUT setting `objectName`, those new docks are invisible to `saveState`/`restoreState` and their position is lost across launches.

**Why it happens:**
`QMainWindow.saveState()`/`restoreState()` identify widgets solely by `objectName` — this is documented but easy to forget when adding a dock in a hurry. `restoreState()` called in the constructor before all docks are added (or before the window is shown) silently returns `true` while applying nothing. And "reset layout" is hand-rolled per-dock instead of restoring a known-good baseline `QByteArray`.

**How to avoid:**
1. Every new `QDockWidget` MUST call `setObjectName("dock_<unique>")` before `addDockWidget`. Add a lint/test that asserts every dock added to `EditorWindow` has a non-empty, unique `objectName`.
2. Save a factory-default layout `QByteArray` once (`saveState()` right after `_build_dock_widgets` in `__init__`) and have "Reset Layout" restore THAT baseline via `restoreState(default_state)`, not a hand-rolled re-add. This also fixes the "reset on rerun" bug: call `restoreState(default_state)` inside `_refresh_viewport_and_tree` if a "reset on open" preference is on, OR leave layout untouched (current behavior) but make it a clear preference — do not leave it ambiguous.
3. Defer the user `restoreState()` to `showEvent` (guarded against re-entry) or a `QTimer.singleShot(0, ...)` so docks exist and the window is laid out before state is applied.
4. For "reset on rerun": decide explicitly. Recommended = do NOT reset layout on scene open (users hate losing their arrangement), but DO provide the menu item AND a "Reset on open" preference. Fix the real bug (layout not resetting when the user explicitly asks) by using `restoreState(default_state)`.

**Warning signs:**
- New docks always open in their default area ignoring the saved position.
- `restoreState()` returns `true` but nothing visually changes.
- "Reset Layout" leaves tabified/floating docks in their old spot.
- `_refresh_recent_menu` is duplicated (main_window.py:352-362 rebuilds twice) — a pre-existing sign that this file has copy-paste debt; audit the whole file when touching dock logic.

**Phase to address:**
GUI-15 (perf/stability + editing UX) owns the dock-state persistence fix. New docks added in GUI-12/13/14 must set `objectName` in the SAME phase they are introduced, not "later."

---

### Pitfall 3: `QThread` worker leak and signal/slot race on window close — `closeEvent` stops the viewport but does NOT stop the LLM/VLM `QThread`

**What goes wrong:**
`LLMPanel._on_generate` (llm_panel.py:114-125) creates a `QThread` + `TextParserWorker`, connects `finished`/`failed`->`thread.quit`->`thread.deleteLater`, and starts it. The `EditorWindow.closeEvent` (main_window.py:373-382) calls `self._viewport_panel.stop()` but NEVER asks the LLM panel to tear down its thread. If the user closes the window mid-LLM-call, the worker thread is still running an HTTP request to OpenAI/Anthropic; when it finishes it emits `finished`/`failed` into a deleted `LLMPanel` -> `RuntimeError: wrapped C/C++ object of type LLMPanel has been deleted`, or a silent segfault. v0.7.0 makes this worse: VLM image->scene calls are slower (multi-second vision inference) and the clarifying-question flow may chain multiple round-trips, so the window-close-during-call window is wider.

Compounding: per Qt 6 docs, `finished()` is emitted BEFORE the thread is truly terminated — `isRunning()` can still return `true` inside a `finished`-connected slot, and `deleteLater` on the thread before `wait()` returns can crash ("Deleting a running QThread ... will result in a program crash").

**Why it happens:**
The v0.5.0 panel was added with the happy path only; teardown was deferred because the LLM call was assumed short. `closeEvent` only knew about the viewport. The worker-object pattern's teardown ordering (`quit` -> `wait` -> `deleteLater`) is easy to get wrong.

**How to avoid:**
1. Give `LLMPanel` (and the new VLM panel + clarifying-question controller) a `stop()` method: set a cooperative cancel flag on the worker (`_cancelled` property, already half-wired at llm_panel.py:129), call `thread.quit()`, then `thread.wait(3000)` to block until the thread actually terminates (this is the step the current code skips). Only then let `deleteLater` run.
2. `EditorWindow.closeEvent` MUST call `self._llm_panel.stop()` (and every new panel's `stop()`) BEFORE `self._viewport_panel.stop()` and before `super().closeEvent()`. Keep `closeEvent` best-effort (broad suppress) but ensure every long-running subsystem is enumerated.
3. For VLM: the worker's HTTP call must check the cancel flag between round-trips (clarifying-question flow has multiple LLM calls — check between each, not only at start).
4. Never `deleteLater` a thread you haven't `wait()`ed on. Wire `thread.finished`->`thread.deleteLater` (already done) but DO NOT additionally call `deleteLater` synchronously in `stop()`.
5. Add an `aboutToClose` signal from `EditorWindow` that panels subscribe to, so new panels auto-wire teardown without `closeEvent` being edited each time.

**Warning signs:**
- Intermittent segfault on window close while an LLM/VLM call is in flight.
- "RuntimeError: Internal C++ object already deleted" in stderr after close.
- `QThread: Destroyed while thread is still running` warning.
- A `QThread` shows in a debugger after the window is gone.

**Phase to address:**
GUI-15 (perf/stability) for the `closeEvent` teardown harness + `aboutToClose` signal; GEN-02 (VLM) and GEN-05 (clarifying-question flow) must each implement `stop()` with cooperative cancel + `wait()` as a first-class deliverable, not an afterthought.

---

### Pitfall 4: VLM image->scene — base64 payload size, image-format/mime, token cost, and "respond ONLY with JSON" non-determinism produce unparseable or hallucinated scenes

**What goes wrong:**
`VisionParser` (vision_parser.py) base64-encodes images and ships them to OpenAI/Anthropic/Ollama. Four failure modes: (a) Large images (4K endoscope frame, PNG) base64 to ~5-10 MB and blow past provider payload limits or cost $0.01-0.05 per call — a batch/procedural gen run of 100 images is real money. (b) The prompt (vision_prompts.py:22-43) says "Respond ONLY with the JSON object" but VLMs routinely wrap JSON in ```` ```json ```` fences or prepend prose; the existing `_JSON_CODE_BLOCK_RE` + `_JSON_OBJ_RE` fallback (vision_parser.py) catches code fences but `_JSON_OBJ_RE = re.compile(r"\{[\s\S]*?\}")` is NON-GREEDY and matches the FIRST `{...}` block — which on a nested scene JSON is the first inner object, not the whole scene, producing a truncated parse. (c) VLMs hallucinate instruments/URDF paths that don't exist (the codebase already has the "assets don't exist, OBJ primitive fallback" lesson — but the VLM will emit `urdf_path: "path/to/robot.urdf"` verbatim from the schema example, which then 404s at sim load). (d) Non-determinism: same image, two calls, two different scenes — acceptable for ideation but catastrophic for batch/procedural gen where reproducibility is expected.

**Why it happens:**
VLMs are probabilistic; the schema example in `_get_visual_schema_example` (vision_prompts.py:80-202) literally contains placeholder paths (`"path/to/robot.urdf"`, `"sky.hdr"`) that the model copies. The regex fallback was written for the text parser's smaller payloads and hasn't been re-validated against nested scene JSON.

**How to avoid:**
1. Downscale images before base64 (e.g. 1024px max edge, JPEG q85) — VLMs don't need 4K, and it cuts cost ~10x. Add a `preprocess_image(path) -> bytes` helper.
2. Replace the non-greedy `_JSON_OBJ_RE` with a brace-balanced JSON extractor (count `{`/`}` depth, ignore braces inside strings) OR demand the model return JSON via the provider's structured-output / JSON mode (OpenAI `response_format={"type":"json_object"}`, Anthropic tool-use with a scene-schema tool) and skip regex entirely.
3. Post-process the VLM scene through a "path sanitizer" that nulls out non-existent `urdf_path`/mesh paths so the simulator falls back to OBJ primitives (reuse the existing `scene_builder` fallback). Never trust a VLM-emitted filesystem path.
4. For batch/procedural gen (GEN-04): fix `temperature=0` (or provider equivalent) AND record a `generation_seed`/`system_fingerprint` in the scene metadata so a run is reproducible/diagnosable. Do NOT claim reproducibility without it.
5. Cost guard: add a `max_image_bytes` and a per-run cost estimator that warns before batch runs.

**Warning signs:**
- `ParseValidationError: field required` on VLM-generated scenes (truncated JSON from non-greedy regex).
- Sim load fails on `urdf_path: path/to/robot.urdf` (hallucinated path).
- Two batch runs on the same image set produce wildly different scenes.
- API bill spikes after a batch-gen run.

**Phase to address:**
GEN-02 (VLM image->scene) owns image preprocessing + JSON extraction fix + path sanitizer. GEN-04 (procedural/batch gen) owns the reproducibility/seed/cost-guard layer.

---

### Pitfall 5: LLM clarifying-question flow — state machine without explicit states races itself when the user clicks "Generate" twice or answers out of order

**What goes wrong:**
The interactive clarifying-question flow (GEN-05) is a multi-turn conversation: user prompt -> LLM asks N clarifying questions -> user answers -> LLM emits final scene. Implemented naively as a sequence of `QThread` calls (reusing the `LLMPanel` pattern), each call's `finished`/`failed` triggers the next. Race 1: user clicks "Generate" while a clarifying-question round-trip is in flight -> a second `QThread` is spawned (llm_panel.py:114 overwrites `self._thread` and `self._worker` without stopping the old ones) -> two workers emit `finished` into the same slots -> the panel's `_current_scene` flips between two concurrent generations. Race 2: the conversation state (questions asked, answers so far) lives only in closure variables / instance attrs with no explicit state machine, so an out-of-order answer (user edits the prompt and re-answers Q1 after Q3 was asked) silently produces a scene built from a mixed question/answer set. Race 3: non-determinism — the same prompt + answers yields different scenes across runs (no seed pinned), so "regenerate" gives a different scene and the user can't tell if their answer or the model caused the change.

**Why it happens:**
The current `LLMPanel` is single-shot (one prompt -> one scene); it has no concept of a conversation. Reusing its `_thread`/`_worker` slots for a multi-turn flow without a state machine is the mistake.

**How to avoid:**
1. Model the flow as an explicit state machine: `IDLE -> AWAITING_QUESTIONS -> AWAITING_ANSWERS -> GENERATING -> DONE/FAILED`. Store the state in a `ConversationState` dataclass (questions, answers, history, seed). Only allow `Generate` to transition from `IDLE` or `DONE`; disable the button (or route to "Cancel") in `AWAITING_*`/`GENERATING`.
2. Guard against double-spawn: before starting a new `QThread`, call `stop()` on the previous one (cooperative cancel + `wait()`). Reuse Pitfall 3's `stop()`.
3. Pin the model `seed`/`temperature` for the WHOLE conversation so a "regenerate" with the same answers is reproducible and diffs are attributable to the user's edits, not the model.
4. Send the FULL conversation history (system prompt + original user prompt + Q/A pairs) on every round-trip, not just the latest answer — stateless APIs don't remember. This is the #1 LLM multi-turn bug.
5. Validation gate between `GENERATING` and `DONE`: run the scene through `SceneDefinition.model_validate` before showing it; if it fails, route back to `AWAITING_ANSWERS` with a targeted re-question rather than dumping a ValidationError on the user.

**Warning signs:**
- "Generate" button is clickable mid-generation.
- `_thread`/`_worker` reassigned while a prior thread is still running.
- Same prompt + answers -> different scenes on regenerate (no seed).
- Clarifying questions reference answers the user never gave (history not sent).
- ValidationError shown to user instead of a useful follow-up question.

**Phase to address:**
GEN-05 (interactive LLM clarifying-question flow). Build the state machine FIRST, then wire the LLM calls onto it; do not bolt the state machine onto the existing single-shot `LLMPanel`.

---

### Pitfall 6: Recording — capture thread reads from the same GL framebuffer the render thread writes, producing torn/missing frames; writing video on the main thread drops fps

**What goes wrong:**
The recording feature (GUI-13) needs to save the viewport as an image sequence or video. Two coupling mistakes: (a) The capture reads `simulator.render()` output (or the `QPixmap` on the canvas) from a second thread while the main-thread `_tick` is mid-`render()` — GL contexts are thread-affine, so the offscreen framebuffer can only be touched from one thread; the capture either gets a stale frame, a torn frame, or crashes the GL context. (b) Encoding frames to video (imageio/ffmpeg/cv2 writer) is CPU-heavy and runs for 10s of seconds; doing it on the main thread freezes the render loop (the <10fps bug comes back) and the close-during-encode path leaks the encoder.

**Why it happens:**
GL framebuffers are not shareable across threads without an explicit shared-context. Video encoding is synchronous and slow. The natural "grab the pixmap and write it" instinct collides with both.

**How to avoid:**
1. Capture on the MAIN thread only, inside `_tick`, by copying the just-rendered `QPixmap`/`np.ndarray` into a `frame_queue` (a `queue.Queue` or `collections.deque(maxlen=N)`). The render thread never touches the encoder.
2. Encode on a SEPARATE `QThread` `RecorderWorker` that drains `frame_queue` and writes via imageio-ffmpeg / cv2 VideoWriter. This keeps the main thread free.
3. Bound the queue (`maxlen`) and drop frames if the encoder falls behind — better a 30fps recording with dropped frames than a 5fps live preview.
4. Teardown: `closeEvent` calls `recorder.stop()` which signals the worker to flush+close the video file, then `thread.quit()` + `thread.wait(5000)`. Failing to `wait()` on the encoder leaves a half-written, un-closed MP4 (moov atom missing -> unplayable).
5. Do NOT hold the GL context open across frames for recording — copy bytes out and release.

**Warning signs:**
- Recorded video is torn (top half of one frame, bottom half of another).
- Live fps drops to <5 while recording.
- MP4 files unplayable / "moov atom not found" (encoder not flushed on close).
- "framebuffer" GL errors appear only while recording.

**Phase to address:**
GUI-13 (recording). The recorder worker + bounded queue + `closeEvent` flush is a first-class deliverable, not a "nice to have."

---

### Pitfall 7: Multi-view + lighting edits mutate live simulator state, so undo/redo and "revert" corrupt the scene

**What goes wrong:**
Multi-view (GUI-12) and lighting/gizmo edits (GUI-12/13) are tempting to implement by poking attrs directly onto the live `self._simulator` (the existing viewport already does this: `_editor_camera_*` attrs pushed via `object.__setattr__` at viewport.py:222-234). The pitfall: those editor-only camera/light parameters drift out of the `SceneDefinition` (the single source of truth per the architecture decision), so (a) undo/redo (which operates on `SceneDefinition` snapshots via `SceneUndoStack`) does NOT undo camera/light changes — the user moves a light, hits undo, and nothing visibly changes; (b) "revert" reloads the scene and the light snaps back, contradicting what the user just did; (c) save writes the `SceneDefinition` without the live edits, so the saved file is missing the light the user just placed.

**Why it happens:**
It's far easier to mutate a simulator attr than to round-trip through the Pydantic `SceneDefinition`, re-validate, and reload. The existing `_editor_camera_*` hack was acceptable for a preview-only viewport but becomes wrong the moment edits are meant to persist.

**How to avoid:**
1. Edits that should persist (lights, camera, gizmo placements, object transforms) MUST be written to the `SceneDefinition` first (via `model_copy(update={...})` per the Pydantic v2 rule), pushed onto `SceneUndoStack`, THEN applied to the live simulator. The simulator is a VIEW of the scene, not the source of truth.
2. Editor-only ephemeral state (orbit camera offset for inspection, gizmo hover highlight) stays on the panel/simulator as before and is explicitly NOT undoable — tag it so the undo stack ignores it.
3. For multi-view: each view is a camera config in `SceneDefinition.environment.cameras`; editing a view edits that camera entry. Do not invent a parallel "view state" outside the schema.
4. Test: edit a light, undo, assert the light reverts in both the tree view AND the render. Edit a light, save, reload, assert the light persists.

**Warning signs:**
- Undo does nothing for camera/light/gizmo edits.
- Saved file missing edits the user just made.
- Tree view and render disagree about a value.
- `_editor_camera_*` style hacks multiply beyond camera offset.

**Phase to address:**
GUI-12 (multi-view/lighting) and GUI-13 (gizmos) — the schema-first edit contract must be established in the FIRST of these phases and reused.

---

### Pitfall 8: `QTimer.singleShot` self-rescheduling + Python object lifetime — `stop()` sets `_running=False` but a queued callback can still fire after `deleteLater`/close, and `__del__` during interpreter shutdown raises from the GL context

**What goes wrong:**
The existing `_tick` (viewport.py:189-290) guards with `self._running` at top and before reschedule (the UAT Gap 2 fix), which is correct for the normal close path. But v0.7.0 adds more self-rescheduling timers (sim worker heartbeat, recorder frame poll, clarifying-question timeout, gizmo animation). Each one inherits the same hazard: (a) a `QTimer.singleShot` callback queued before `stop()` still fires after `stop()` if the event loop hasn't drained — the `_running` guard handles this, but only if EVERY self-rescheduling callback checks the guard; a new timer that forgets the guard leaks forever. (b) `__del__` (viewport.py:182-187) suppresses broadly during interpreter shutdown, but new panels that hold GL/render/sim resources and don't define `__del__` will crash on shutdown with "CGL context already destroyed" or "wrapped C++ object deleted." (c) `closeEvent` ordering: if `stop()` is called after the GL context is torn down (e.g. after `super().closeEvent()`), `simulator.close()` raises inside the suppressed block — currently OK because of broad suppress, but new resources without the suppress will surface it.

**Why it happens:**
The self-rescheduling `singleShot` pattern (D-03) is correct but viral — every new timer must re-implement the guard. Python object lifetime doesn't match Qt object lifetime (`deleteLater` defers deletion), so "the Python object exists" doesn't mean "the C++ widget is valid."

**How to avoid:**
1. Centralize the self-rescheduling pattern into a `RenderLoop` / `PollLoop` helper that owns the `_running` guard and exposes `start()`/`stop()`. New timers use the helper, never raw `QTimer.singleShot` with a hand-rolled guard.
2. Every panel holding GL/sim/thread resources defines BOTH `stop()` (called from `closeEvent`, best-effort) and `__del__` (broad suppress, shutdown-only). Audit new panels for both.
3. `closeEvent` ordering must be: stop all long-running panels FIRST -> stop viewport -> save settings -> `super().closeEvent()`. Never call `super().closeEvent()` before stops (Qt may tear down child widgets).
4. For the sim-worker thread (Pitfall 1): its `stop()` must signal the worker to exit its loop, then `thread.wait()` — a worker that ignores the signal and is still running when `closeEvent` returns will crash.

**Warning signs:**
- Callbacks fire after window close (log "tick after stop" or use a counter).
- `AttributeError` from `__del__` on shutdown mentioning GL/CGL/EGL.
- New timer's callback runs once and stops (forgot to reschedule) OR runs forever (forgot guard).

**Phase to address:**
GUI-11 (introduce the `RenderLoop` helper) and GUI-15 (audit all new panels for `stop()`+`__del__` and enforce `closeEvent` ordering).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Mutating simulator attrs instead of round-tripping through `SceneDefinition` | Fast to implement, responsive UI | Undo/save/revert silently wrong (Pitfall 7); saved files missing edits | Never for persistent edits; only for ephemeral editor-only camera offset (current `_editor_camera_*`) |
| Reusing the single-shot `LLMPanel._thread` slot for the multi-turn clarifying-question flow | Less code | Double-spawn races + mixed question/answer state (Pitfall 5) | Never — build a state machine |
| Non-greedy `_JSON_OBJ_RE` fallback for VLM JSON extraction | Reused from text parser | Truncated nested scene JSON (Pitfall 4) | Never for nested scene JSON; use brace-balanced extraction or provider JSON mode |
| Injecting `simulator.step()` into the render `_tick` | One-line "fix" for immobile preview | Coupled cadence, wrong playback speed, <10fps (Pitfall 1) | Never — decouple via sim worker thread |
| `deleteLater` on a `QThread` without `wait()` | Less blocking on close | Crash "destroyed while still running" (Pitfall 3) | Never — always `quit()`->`wait()`->`deleteLater` |
| Hand-rolled "Reset Layout" re-adding docks to areas | Quick | Ignores tabification/floating/closed; "reset on rerun" bug persists (Pitfall 2) | Never for final; acceptable as a stub until `restoreState(default_state)` lands |
| Two `QTimer.singleShot` chains both touching the simulator | Decouple by brute force | GL context contention + stutter (Pitfall 1) | Never |
| Recording by calling `render()` from the encoder thread | Reuses render code | GL thread-affinity crash + torn frames (Pitfall 6) | Never — copy frames on main thread, encode off-main |

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| OpenAI Vision (GPT-4o) | Sending full-res PNG (~10MB base64); trusting "ONLY JSON" prose; non-greedy regex parse | Downscale to <=1024px JPEG; use `response_format={"type":"json_object"}` or function tool; brace-balanced parse fallback |
| Anthropic Claude Vision | Passing image as text base64 instead of `image` content block; wrong media type | Use `{"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":...}}` content block; JPEG preferred |
| Ollama vision models | Assuming `llava` handles multi-turn clarifying questions like GPT-4o | Local models are weaker at structured multi-turn; send full history each turn; fall back to single-shot if quality drops |
| `QSettings` (dock persistence) | Adding docks without `objectName`; calling `restoreState` in `__init__` before show | Set unique `objectName` on every dock; restore in `showEvent` (guarded) or `QTimer.singleShot(0,...)` |
| `QThread` worker-object pattern | Subclassing `QThread` and adding slots (slots run in main thread); `deleteLater` before `wait()` | Use `moveToThread`; wire `finished`->`quit`->`deleteLater`; `quit()`+`wait()` in controller `stop()` |
| MuJoCo offscreen GL on macOS | Re-probing CGL every frame after a failure (v0.5.0 already short-circuits — must preserve this when adding multi-view) | Reuse the existing `_renderer_available=False` short-circuit; multi-view must share ONE GL context or fall back to PyBullet preview per the v0.5.0 macOS fallback |
| PyBullet `getCameraImage` for multi-view | Calling it per-view per-frame without honoring `_normalize_pb_rgb()` (v0.5.0 lesson) | Every `getCameraImage` result MUST go through `_normalize_pb_rgb()` before display; multi-view multiplies the surface area for the HxWx4-vs-3 bug |
| imageio-ffmpeg / cv2 VideoWriter | Opening encoder on main thread; not flushing on close | Open on recorder worker thread; `close()` flushes moov atom; `closeEvent` must `wait()` for flush |
| LLM/VLM API keys | Storing keys in `QSettings` for convenience | `QSettings` is explicitly NOT for secrets (per `_settings.py` docstring + D-20); keys stay in `.env` via `Settings()`; UI reads via `get_settings()` |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| `step()` in the render loop | <10 fps on fluid/cutting scenes | Sim worker thread + accumulator (Pitfall 1) | Immediately on any non-trivial scene |
| Unbounded frame queue in recorder | Memory grows, then OOM | `maxlen` on `deque`, drop oldest when encoder lags (Pitfall 6) | ~30s recording at 1080p |
| Per-frame full `SceneDefinition.model_dump` for undo | UI jank on every edit | Coalesce edits; push undo snapshots on commit, not per-keystroke | Large scenes with many tissues |
| Synchronous VLM call on main thread | Whole UI frozen 5-15s per image | Always on `QThread` (already done for text; VLM must follow) | First VLM call |
| `restoreState` of a huge layout every open | Open feels slow | Restore once at show, not per scene load | 10+ dock widgets |
| Re-probing MuJoCo offscreen GL every frame after failure | Log spam + fps 0 | Reuse `_renderer_available=False` short-circuit (v0.5.0) | macOS stock Python |
| Multi-view rendering 4 views at full res in one `_tick` | fps / 4 | Render secondary views at lower res / on a slower cadence | 4 views at 1080p |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing LLM/VLM API keys in `QSettings` or scene JSON | Key leakage via shared config files | Keys only in `.env` via `Settings()` (D-20); `QSettings` docstring already forbids secrets — enforce for new panels |
| Sending user's surgical image to a cloud VLM without consent | Privacy/PHI exposure; images may contain patient data | Explicit opt-in dialog before first VLM call; document data flows; offer Ollama (local) as default for sensitive images |
| Trusting VLM-emitted `urdf_path`/mesh paths | Path traversal / loading arbitrary files | Sanitize/null non-existent paths -> OBJ fallback (reuse `scene_builder`); never `open()` a VLM-emitted path directly |
| `safe_error_message` not applied to VLM/clarifying-question errors | API key / internal path leakage in error dialogs | All user-facing errors go through `safe_error_message` (already used in `llm_panel` — extend to new VLM/clarifying panels) |
| Logging full VLM prompts/images | PHI + cost data in logs | Log metadata only (provider, model, token count, timing), redact image bytes; never log base64 payloads |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| "Generate" stays enabled during clarifying-question flow | Double-spawn races, mixed state (Pitfall 5) | Disable/relabel to "Cancel" during `AWAITING_*`/`GENERATING` |
| Undo silently ignores camera/light/gizmo edits (Pitfall 7) | User loses trust in undo | All persistent edits round-trip through `SceneDefinition` + undo stack |
| Reset Layout only partially resets (Pitfall 2) | User rearranges, hits reset, layout half-reverts | Restore a saved default `QByteArray` via `restoreState(default_state)` |
| VLM returns a scene that fails sim load (hallucinated paths) (Pitfall 4) | "Accept" produces a broken preview | Validate + sanitize before "Accept" is enabled; show targeted errors |
| Recording with no progress indicator | User doesn't know it's recording or how big | Status-bar frame counter + file-size estimate; red dot in viewport |
| Clarifying questions asked all at once vs. one-by-one | Overwhelming or tedious | Ask the top 2-3 highest-uncertainty questions first; let model prioritize |
| Multi-view with no per-view camera label | User can't tell which view is which | Label each view (top/front/side/user); sync selection across views |

## "Looks Done But Isn't" Checklist

- [ ] **Render/sim decoupling (GUI-11):** Often missing the accumulator (preview runs at wrong speed) — verify wall-clock 10s of sim time = 10s of preview for a known scene.
- [ ] **Dock persistence (GUI-15):** Often missing `objectName` on NEW docks — verify a rearranged layout survives close/reopen for every dock, including ones added in GUI-12/13/14.
- [ ] **closeEvent teardown (GUI-15):** Often missing `wait()` on LLM/VLM/recorder threads — verify closing mid-call does not segfault or leak a thread (check `ps`/Activity Monitor).
- [ ] **VLM JSON parse (GEN-02):** Often missing brace-balanced extraction — verify a nested scene JSON wrapped in ```` ```json ```` fences parses to the FULL scene, not the first inner object.
- [ ] **VLM path sanitizer (GEN-02):** Often missing — verify a VLM scene with `urdf_path: "path/to/robot.urdf"` loads via OBJ fallback, not a 404 crash.
- [ ] **Clarifying-question state machine (GEN-05):** Often missing the double-spawn guard — verify clicking Generate twice doesn't spawn two threads.
- [ ] **Recorder flush (GUI-13):** Often missing `wait()` on close — verify the produced MP4 plays (moov atom present) after closing mid-record.
- [ ] **Undo for lighting/gizmos (GUI-12/13):** Often missing the schema round-trip — verify undo reverts a light edit in both tree and render.
- [ ] **Multi-view GL sharing (GUI-12):** Often missing the macOS fallback — verify multi-view still renders on macOS stock Python (no mjpython) via the PyBullet preview fallback path.
- [ ] **Batch gen reproducibility (GEN-04):** Often missing seed/fingerprint — verify two runs of the same image set with `temperature=0` produce byte-identical scene JSON (modulo model nondeterminism documented).

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Render/sim coupled (Pitfall 1) | HIGH | Introduce sim worker thread + accumulator; re-baseline fps; re-validate cutting/fluid preview |
| Dock layout not resetting (Pitfall 2) | MEDIUM | Capture default `QByteArray` at init; replace hand-rolled reset with `restoreState(default)`; add `objectName` to all docks |
| QThread leak on close (Pitfall 3) | MEDIUM | Add `stop()`+`wait()` to every panel; wire `aboutToClose`; broad-suppress in `closeEvent` |
| VLM truncated JSON (Pitfall 4) | MEDIUM | Swap regex for brace-balanced extractor or provider JSON mode; add path sanitizer; add cost guard |
| Clarifying-question race (Pitfall 5) | HIGH | Rebuild as explicit state machine; disable Generate during flow; pin seed; send full history |
| Recording torn frames (Pitfall 6) | MEDIUM | Move encode to worker thread; bounded frame queue; flush on close |
| Edits bypass schema (Pitfall 7) | HIGH | Refactor all persistent edits through `SceneDefinition` + undo stack; add undo-covers-edit test |
| Timer guard leak (Pitfall 8) | LOW | Centralize into `RenderLoop` helper; audit all new timers for guard + `__del__` |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls. Phase numbers continue from 41 (v0.6.0 ended at 40.1). GUI features map to GUI-11..15; scene gen to GEN-01..05. The three known bugs fold into GUI-11 + GUI-15.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1 — Render/sim coupling (fixes immobile-preview + <10fps bugs) | GUI-11 (render/sim-decoupled viewport) | Wall-clock test: 10s sim = 10s preview; fps > 10 on a cutting scene; only ONE `singleShot` render chain |
| 2 — Dock-state persistence (fixes layout-not-reset-on-rerun bug) | GUI-15 (perf/stability + editing UX) | Rearrange + close + reopen -> layout preserved; Reset Layout -> full restore incl. tabified/floating; every dock has unique `objectName` |
| 3 — QThread leak on close | GUI-15 (closeEvent harness) + GEN-02/GEN-05 (panel `stop()`) | Close window mid-LLM/VLM/clarifying call -> no segfault, no leaked thread (Activity Monitor check) |
| 4 — VLM payload/cost/JSON/path | GEN-02 (VLM image->scene) + GEN-04 (batch) | Nested JSON in code fences parses to full scene; hallucinated path -> OBJ fallback; cost estimator warns; reproducible with seed |
| 5 — Clarifying-question state race | GEN-05 (interactive LLM flow) | Double-click Generate -> only one thread; regenerate same answers -> same scene (seed pinned); ValidationError -> targeted re-question |
| 6 — Recording thread/render contention | GUI-13 (recording) | 30s recording -> playable MP4 (moov present); fps stays >10 during record; close mid-record -> valid file |
| 7 — Edits bypass schema (undo/save/revert wrong) | GUI-12 (multi-view/lighting) + GUI-13 (gizmos) | Edit light -> undo -> reverts in tree AND render; edit light -> save -> reload -> light persists |
| 8 — Timer guard + `__del__` shutdown | GUI-11 (RenderLoop helper) + GUI-15 (panel audit) | No callbacks after close; no `__del__` GL errors on shutdown; every new timer uses helper |

## Sources

- [Qt 6 QThread docs — `finished()`/`isFinished()`/`wait()` semantics and destructor warning](https://doc.qt.io/QT-6/qthread.html)
- [Qt mailing list: QThread::finished() race condition (finish emits before isRunning=false)](https://lists.qt-project.org/pipermail/development/2011-November/000280.html)
- [Qt Forum: QThread relation between quit/finished/deleteLater](https://forum.qt.io/topic/32578/qthread-relation-between-quit-finished-and-deletelater)
- [Qt Forum: Proper handling of QThread on main window close](https://forum.qt.io/topic/54037/solved-proper-handling-of-qthread-on-main-window-close)
- [Stack Overflow: QDockWidgets closed state not restored by restoreDockWidget](https://stackoverflow.com/questions/2171347/closed-state-of-qdockwidgets-not-restored-by-restoredockwidget)
- [Stack Overflow: restoreDockWidget not working as expected](https://stackoverflow.com/questions/52115700/restoredockwidget-not-working-as-expected)
- [Qt Forum: restoreDockWidget reports true but doesn't restore (restore before show)](https://forum.qt.io/topic/157100/restoredockwidget-reports-true-but-doesn-t-restore)
- [Qt Docs: QMainWindow::saveState() objectName requirement](https://www.qthub.com/static/doc/qt5/qtwidgets/qmainwindow.html)
- Codebase: `src/surg_rl/editor/viewport.py` (existing render loop, `_tick`, `_editor_camera_*`, `_normalize_pb_rgb` usage, macOS PyBullet fallback)
- Codebase: `src/surg_rl/editor/main_window.py` (`_action_reset_layout`, `_refresh_viewport_and_tree`, `closeEvent`, duplicated `_refresh_recent_menu`)
- Codebase: `src/surg_rl/editor/llm_panel.py` (`TextParserWorker`, `_thread`/`_worker` slot reuse, `_cancelled` flag half-wired)
- Codebase: `src/surg_rl/editor/_settings.py` (QSettings INI, no-secrets docstring, `save_window`/`load_window`)
- Codebase: `src/surg_rl/scene_generation/vision_parser.py` + `prompts/vision_prompts.py` (base64 path, `_JSON_OBJ_RE` non-greedy, placeholder `urdf_path` in schema example)
- Project context: `.planning/PROJECT.md` (v0.5.0 lessons, v0.7.0 target features GUI-11..15 / GEN-01..05, three known GUI bugs)

---
*Pitfalls research for: adding GUI editor depth + scene-generation features to the existing PySide6 surg-rl scene editor (v0.7.0)*
*Researched: 2026-07-15*
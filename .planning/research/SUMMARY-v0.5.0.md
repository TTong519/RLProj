# Project Research Summary — v0.5.0 Scene Editor & UX Polish

**Project:** Surg-RL
**Domain:** Surgical-robotics RL training system + PySide6 GUI scene editor + demo suite + docs
**Milestone:** v0.5.0 (2026-06-18)
**Researched:** 2026-06-18
**Confidence:** HIGH

---

## Executive Summary

Surg-RL v0.5.0 is a **UI + UX polish milestone** that layers a PySide6 scene editor on top of the existing MuJoCo/PyBullet simulation framework, polishes three surgical task demos, refreshes user-facing documentation, and retires accumulated tech debt. Experts in this domain build GUI scene editors as **leaf consumers** that read a Pydantic v2 schema source-of-truth via `model_json_schema()` and reflect it into a Qt widget tree — the same pattern Blender (RNA), Godot (PropertyInfo), and rl-baselines3-zoo use for their MuJoCo viewer. The recommended architecture here is a pure-Python `SchemaWalker` that emits abstract `WidgetSpec` nodes (testable without Qt, reusable for a future `surg-rl inspect --json-schema` CLI) and a thin `SimRenderBridge` that wraps `mujoco.Renderer` and `pybullet.getCameraImage` offscreen GL → NumPy → QImage (no third-party OpenGL widget, no `pyqtgraph`/`VisPy`/`PyOpenGL` dependency, no Qt-context contention).

The recommended approach: **(1)** PySide6 6.8+ as the only new optional dep in a new `[gui]` extra (~120 MB wheel, kept off the headless install path); **(2)** MuJoCo + PyBullet's built-in offscreen render APIs produce 640×480 RGB frames at ~5 ms/frame, displayed by a 30 LOC `QWidget` subclass; **(3)** a QThread-based worker drives LLM calls (`TextParser.parse_sync`) without freezing the GUI; **(4)** `LazyImport` pattern (already proven in 7 places) keeps `surg-rl train` working on systems without PySide6; **(5)** the existing 1,134-test suite stays green because the editor is purely additive. The marquee risks are: MuJoCo GL-context thread affinity (use a `QMutex`-protected double-buffer swap), API key leakage through LLM exceptions (redact before display), Pydantic v2 `model_dump(mode="json")` enum handling for the `_FloatMixin(float, Enum)` `DifficultyLevel` (route all serialization through `scene_to_jsonable`/`scene_from_jsonable` helpers), and the 63-class schema walker rot if implemented with an `if/elif isinstance()` chain (use a `FieldRenderer` registry instead).

## Key Findings

### Recommended Stack

Two new optional dependencies enter via a new `[gui]` group; **no new core deps**. PySide6 6.8+ (LGPL-3-or-GPL, official Qt-for-Python) is the only Qt binding compatible with MIT licensing; PyQt6 would force the entire project to GPL. `markdown-it-py` is already a transitive dep of pydantic — promoted to explicit. The 3D viewport deliberately avoids PyOpenGL/pyqtgraph/VisPy/moderngl/Qt3D: the simulators' built-in `mujoco.Renderer` (MuJoCo ≥3.0) and `pybullet.getCameraImage` produce NumPy RGB arrays, which a 30-LOC `QWidget` subclass converts to `QImage` at 20 Hz via a `QTimer`.

**Core technology additions:**

- **PySide6 ≥6.8.0, <7.0** — Qt for Python (LGPL-3.0); provides `QMainWindow`, `QTreeView`, `QStandardItemModel`, `QFormLayout`, `QDoubleSpinBox`, `QComboBox`, `QThread`, `QSettings`, `QFileDialog`, `QGraphicsView`. ~120 MB wheel. Pinned to Qt 6.8 LTS (supported through Oct 2026) and current Qt 6.11.
- **markdown-it-py ≥3.0.0** — CommonMark parser for in-GUI help/docs via `QTextBrowser.setHtml`. Already transitively installed; promoted to explicit dep.
- **MuJoCo 3.x `mujoco.Renderer(model, h, w)`** — offscreen GL context that returns RGB arrays via `.render()`. Verified against official docs.
- **PyBullet ≥3.2.5 `pybullet.getCameraImage(w, h, view, proj)`** — direct offscreen frame grab. Already used in existing demos.

**Stack rejection table (NOT adding):** PyQt6 (GPL-3, license-incompatible with MIT), PyQt5 (EOL May 2025), pyqtgraph/VisPy/PyOpenGL/Qt3D (OpenGL-context-within-Qt pain, two scene graphs), `jsonschema` runtime dep (Pydantic already does this), `textual`/`nbformat` (overkill for demos).

### Expected Features

**Must-have (table stakes per category):**

*PySide6 Scene Editor:*
- Live 3D viewport at ≥15 FPS (MuJoCo + PyBullet offscreen render; `QTimer`-throttled)
- Tree editor mirroring `SceneDefinition` (Robots → Tissues → Instruments → Task → DR) with context menu (Add/Duplicate/Delete), drag-reorder, dirty-state indicator
- Schema-driven property form — `QDoubleSpinBox`/`QSpinBox` (with `Field(ge, le)` bounds), `QComboBox` for Enums, `QCheckBox`, `QLineEdit`, `QPlainTextEdit`, `QColorDialog` for `RgbColor`, vector editor for `tuple[float,float,float]`, list editor for `list[BaseModel]`, live Pydantic v2 validation
- LLM-prompt-to-JSON panel: provider/model selector (OpenAI / Anthropic / Ollama), streaming status, JSON preview, Accept/Reject/Regenerate, diff view (current vs LLM-generated), modify-with-context mode
- Editor shell: 3-pane workspace (tree + viewport + form), File→New/Open/Save, drag-drop `.json`/`.yaml`, recent files, dirty state, `QSettings` for window geometry, `Ctrl+S/O/N/Q` shortcuts, CLI `surg-rl edit` subcommand

*Demo Suite Polish:*
- `demos/_common.py` shared module — banner, scene info, scene resolver, default CLI args
- 3 demos: suturing (existing 1168-test clean), knot-tying (new, `KNOT_TIER` instrument), needle-passing (new, dual-arm handoff)
- Per-demo regression test (`--headless --steps 0 --eval-episodes 1`)
- Per-demo scene JSON in `scenes/`
- Difficulty selector (`--difficulty EASY/MEDIUM/HARD`)

*User-facing Docs Refresh:*
- README updated with `pip install 'surg-rl[gui]'` quickstart, editor screenshots, demo GIFs
- CONTRIBUTING.md overhauled (dev setup, `[gui]` install path, `demos/_common.py` pattern)
- CHANGELOG.md v0.5.0 entry (Keep-a-Changelog format)

*Tech Debt Cleanup:*
- 421 ruff issues in `src/surg_rl/dreamer/` (F841, B904, E402) → 0
- HARD-fixture env-construction integration test (`suturing_difficulty_hard.json`)
- Fluid step hook in `base_simulator.py` (default no-op, backward-compatible)
- Cut cooldown unit test (500 ms cooldown arithmetic, D-15)
- Dockerfile.ros2 amd64 hardcode → `TARGETARCH` (multi-arch build)
- PhiFlow multi-obstacle union() workaround (manual SDF merge helper)

**Should-have (differentiators — ship if time permits):**
- Backend toggle (MuJoCo ↔ PyBullet, two simulators alive simultaneously — ~150–300 MB)
- GIFs for each demo (3 GIFs in `docs/images/` via Pillow + imageio)
- 3 editor screenshots (viewport + tree/form + LLM panel)
- Demo transcripts (`docs/demos/{name}_transcript.md`)
- Screenshot capture (PNG to clipboard or file)
- Wireframe / solid / textured shading cycle

**Defer (v0.6.0+):**
- Side-by-side MuJoCo vs PyBullet render (2× GPU cost)
- Saved camera bookmarks, time-scrubber, episode replay
- Drag-from-asset-library, search/filter bar in tree
- Diff view ("show changes since last save")
- Per-field help link to markdown docs
- Template prompt library, cost estimate before generate
- Architecture diagram, FAQ, "How to add a new surgical task" tutorial
- K8s PVC e2e scaffolding, organ mesh licensing research spike, 3D fluid flag, per-tet generation counter

### Architecture Approach

The editor is a **leaf consumer** that depends on `scene_definition/`, `scene_generation/`, and `simulators/` — nothing in the codebase depends on the editor. This makes it safe to add without breaking any of the existing 1,134 tests. Six new components organize the work:

1. **`src/surg_rl/editor/`** — New PySide6 GUI package (~15 files). `__init__.py` uses `LazyImport` for PySide6 symbols and exposes `HAS_GUI` sentinel (mirrors `ros2`, `dreamer`, `marl`, `benchmark` patterns). `__main__.py` allows `python -m surg_rl.editor` launch.
2. **`SchemaWalker`** — Pure-Python walker (`src/surg_rl/editor/schema_walker.py`) that consumes `SceneDefinition.model_json_schema()` (a `dict`) and emits `WidgetSpec` dataclass trees. Does NOT import PySide6 → testable without `QT_QPA_PLATFORM=offscreen`, reusable for non-GUI contexts (`surg-rl inspect --json-schema`).
3. **`SimRenderBridge`** — Tiny adapter (~30 LOC per backend) on each simulator (`mujoco_simulator.py` + `pybullet_simulator.py`) that adds `render_to_numpy(width, height) → np.ndarray`. The bridge lives on the **simulator**, not the editor — keeps Qt out of the simulators module and lets RL training also use it (future video recording).
4. **`QThread` workers** — `LLMPanelWorker`, `LoadSceneWorker`, and `RenderBridge` use the standard Qt worker pattern (`QObject.moveToThread(QThread)` + Signal/Slot). LLM calls (5–30s) never block the GUI thread.
5. **`demos/_common.py`** — Extracted shared narration helper (banner, scene info, scene resolver). Mirrors existing `_omp_compat.py` / `_platform_guard.py` underscore-prefix convention.
6. **`tests/gui/`** — New test directory with `conftest.py` setting `QT_QPA_PLATFORM=offscreen` + `qapp` session fixture. Houses `test_editor_smoke.py`, `test_schema_walker.py`, `test_undo_redo.py`, `test_llm_panel.py`, `test_render_bridge.py`.

**Critical integration contract:** `BaseSimulator` ABC gains `render_to_numpy()` method (declared on each backend, default `NotImplementedError`). Editor's `RenderBridge` QObject wraps whichever simulator is loaded. No QObject moves across threads; GL context is owned by the GUI thread.

### Critical Pitfalls

1. **MuJoCo GL context is single-thread-affine** — MuJoCo's `MjrContext`/`GLContext` must be made current on a single thread. The `SimulatorWorker` (QObject on a QThread) holds the `threading.Lock` around `step()`; the GUI's `paintGL` acquires the same lock. Render-to-numpy runs on the GUI thread inside a `QTimer` callback (cheap, ~5 ms). On macOS, `_is_running_under_mjpython()` must extend to GUI subprocess invocation with a `os.execvp("mjpython", ...)` re-exec helper. **Phase 31 (tech-debt foundation)** designs the mjpython re-exec helper; **Phase 33 (editor)** writes the worker skeleton.

2. **Pydantic v2 round-trip with `_FloatMixin` enums** — `DifficultyLevel` inherits from `float`, not `(str, Enum)`. `model_dump(mode="json")` returns the float value (correct), but enum mixins are a known failure surface. **Centralize** all serialization in `scene_to_jsonable(scene) → dict` and `scene_from_jsonable(d) → SceneDefinition` helpers in `src/surg_rl/scene_definition/loader.py`. **Add a parametrized round-trip test** that walks all 63 schema models and asserts equality. GUI's "Save" must use `scene_to_jsonable`; existing `SceneLoader.load` continues to work.

3. **API key leakage through LLM exceptions** — `anthropic.APIError` and `openai.APIError` include the offending request in their `__str__`. Add `safe_error_message(exc)` redactor (regex over `sk-[A-Za-z0-9_-]{20,}`, `claude-[A-Za-z0-9_-]{20,}`, `ANTHROPIC_API_KEY=...`) and apply at the GUI logger handler level. **API key is in-memory only** (Password-mode `QLineEdit`); never written to `QSettings` or scene JSON. Add a pre-commit hook grepping `api_key` patterns.

4. **63-class schema walker rot** — A hand-written `if/elif isinstance()` chain for field renderers will diverge from `schema.py` within one release. **Write a `SchemaWalker` class with a `FieldRenderer` registry** (`dict[type, Callable]`). Built-in renderers: `Enum → QComboBox`, `bool → QCheckBox`, `int/float → QDoubleSpinBox/QSpinBox`, `str → QLineEdit`, `list[BaseModel] → QListWidget + Add/Delete`, `BaseModel → QGroupBox + nested walker`. **Add a coverage test** that constructs a `SceneDefinition` with all 63 model types populated and asserts every field renders a non-None `QWidget`.

5. **Optional-dependency regression** — A naive `from PySide6.QtWidgets import QApplication` at the top of `surg_rl/__init__.py` breaks the headless install (`qt.qpa.plugin: Could not load the Qt platform plugin "xcb"` on Linux CI). Use `LazyImport("PySide6.QtCore", "gui")` in `editor/__init__.py`. **The GUI launches via a separate console script** `surg-rl-gui` (`surg_rl.editor.app:main`), NOT as a Typer subcommand of `surg-rl`. Verify CI matrix: `pip install surg-rl` (no extras) passes the full headless suite without PySide6 imported.

## Implications for Roadmap

Based on the research, the planned 5-phase structure in `PROJECT.md` is sound and architecture-validated. Refinements:

### Phase 31: Tech Debt Foundation

**Rationale:** Retire quick-win tech debt before the editor phase. The 421 ruff cleanup in `src/surg_rl/dreamer/` is concentrated as F841 (unused var), B904 (`raise from`), E402 (module-level import not at top) — all auto-fixable. The Dockerfile.ros2 amd64 hardcode, fluid step hook, cut cooldown test, and PhiFlow union workaround are all small, isolated fixes. This phase **also designs the mjpython re-exec helper** (P1 pitfall) and the `[gui]` extra / `surg-rl-gui` console script (P6 + P10 pitfalls), so the editor phase has the scaffolding to call.

**Delivers:**
- `ruff check src/surg_rl/dreamer/` → 0 issues; `tests/dreamer/test_dreamer_lint.py` asserts clean
- Dockerfile.ros2 → `$TARGETARCH`; CI multi-arch build verified
- `BaseSimulator.step_fluid(dt)` default no-op + `apply_fluid` flag
- `tests/test_cutting_cooldown.py` asserts 500 ms cooldown (D-15)
- PhiFlow multi-obstacle SDF merge helper in `src/surg_rl/fluids/` + regression test
- `pyproject.toml` `[gui]` extra (`PySide6>=6.8.0,<7.0`, `markdown-it-py>=3.0.0`)
- `[project.scripts] surg-rl-gui = "surg_rl.editor.app:main"`
- `surg_rl/editor/__init__.py` with `HAS_GUI` sentinel + `LazyImport` (skeleton only)
- mjpython re-exec helper `_ensure_mjpython_or_warn()`

**Addresses:** All Category 4 features from FEATURES.md; P1, P6, P9, P10 from PITFALLS.md
**Avoids:** Eager PySide6 import regression; mjpython crash on macOS; ruff-rot baseline

**Validation:** All 1,134+ existing tests pass. New tests pass. `python -c "import surg_rl; print(surg_rl.__version__)"` runs without importing PySide6.

### Phase 32: Demo Suite Polish

**Rationale:** Phase 31 establishes a clean baseline; demos can be built without worrying about ruff regressions. Write `NARRATION_TEMPLATE.md` first (P8 pitfall: "narration drift") — a 5-stage structure (Setup → Action → Critical Moment → Outcome → Takeaway) with vocabulary constraints — then refactor the 3 demos to follow it. The editor phase (Phase 33) will benefit from `demos/_common.py`'s `resolve_scene()` for scene loading.

**Delivers:**
- `demos/_common.py` (NEW) — `print_banner()`, `print_scene_info()`, `resolve_scene()`, `DEFAULT_TRAINING_CONFIG`
- `demos/knot_tying_demo.py` (NEW) — uses `KNOT_TIER` instrument, narration follows template
- `demos/needle_passing_demo.py` (NEW) — dual-arm `MultiAgentConfig`, needle-passing narration
- `demos/suturing_demo.py` (REFACTOR) — imports from `_common`
- 3 per-demo regression tests in `tests/test_demos.py`
- `demos/README.md` walkthrough sections
- `demos/NARRATION_TEMPLATE.md` (P8 prevention)
- Optional: 3 demo GIFs in `docs/images/` (Pillow + imageio)

**Uses:** Rich (already in stack at 15.0) for narration; existing `TaskRewardRouter`, `CurriculumScheduler`, `DifficultyLevel` from v0.4.0–v0.4.2
**Implements:** Architecture Integration Point 7 (Demo Suite Refactor)
**Addresses:** Category 2 features from FEATURES.md; P8 from PITFALLS.md

**Validation:** All 3 demos run `python demos/{name}_demo.py --headless --steps 0 --eval-episodes 1` exit 0. Suturing demo stays 1168-test clean.

### Phase 33: PySide6 Scene Editor (Marquée)

**Rationale:** Largest phase — all five editor components (1A viewport, 1B tree, 1C form, 1D LLM, 1E shell) ship together because they share the schema walker and the Qt main window. Splitting them would rebuild the workspace shell twice. Depends on Phase 1 (clean baseline, mjpython helper, `[gui]` extra, console script) and Phase 2 (`demos/_common.py` resolver). Merge order within the phase (per CLAUDE.md): schema → simulators → scene_generation → editor → tests.

**Delivers (in dependency order):**
1. Per-simulator `render_to_numpy()` methods (~30 LOC each, in `mujoco_simulator.py` + `pybullet_simulator.py`); `BaseSimulator` ABC declares the method
2. `src/surg_rl/editor/schema_walker.py` — pure-Python walker + `WidgetSpec` dataclass
3. `src/surg_rl/editor/scene_model.py` + `tree_view.py` — `QAbstractItemModel` wrapping `SceneDefinition`
4. `src/surg_rl/editor/form_view.py` — `SchemaWalker` → `QFormLayout` with widget registry
5. `src/surg_rl/editor/render_bridge.py` + `viewport.py` — `QObject` adapter + `QWidget` viewport, `QTimer` 20 Hz
6. `src/surg_rl/editor/undo_redo.py` — `QUndoStack` + `QUndoCommand` subclasses for field mutations
7. `src/surg_rl/editor/llm_panel.py` + `thread_manager.py` — QThread workers for LLM call
8. `src/surg_rl/editor/main_window.py` — full `QMainWindow` integration (QSplitter tree|form|viewport, menus, status bar)
9. `src/surg_rl/editor/__main__.py` — `python -m surg_rl.editor` entrypoint
10. `tests/gui/test_editor_smoke.py` — `QT_QPA_PLATFORM=offscreen` lifecycle test
11. `tests/gui/test_schema_walker.py` — full schema coverage (all 63 model types)
12. `tests/gui/test_render_bridge.py` — `render_to_numpy()` shape + screenshot artifact
13. `tests/gui/test_undo_redo.py` + `test_llm_panel.py` — round-trip + mocked `TextParser`
14. `src/surg_rl/scene_definition/loader.py` — `scene_to_jsonable()` + `scene_from_jsonable()` helpers
15. `src/surg_rl/editor/util.py` — `safe_error_message()` redactor
16. CI matrix entry: `pip install -e ".[gui]"` + `QT_QPA_PLATFORM=offscreen pytest tests/gui/`
17. Screenshot capture to `tests/gui/screenshots/` (CI artifact upload)

**Uses:** PySide6 ≥6.8.0, markdown-it-py ≥3.0.0, existing `mujoco.Renderer`, existing `pybullet.getCameraImage`, existing `TextParser`/`VisionParser`, existing `SceneLoader`, existing `config.get_settings()`
**Implements:** Architecture Patterns 1–5 (LazyImport, SchemaWalker, RenderBridge, QThread workers, UndoRedo)
**Addresses:** Category 1 features (1A–1E) from FEATURES.md; P1, P2, P3, P4, P5, P7 from PITFALLS.md

**Validation:** `surg-rl-gui` opens editor on fixture scene, viewport renders frames at 15+ FPS, edit a field, save, reload — value persists. CI smoke tests pass headless. `surg-rl train --help` works without Qt (no PySide6 import).

### Phase 34: User-Facing Docs Refresh

**Rationale:** Sequential — needs Phase 33 screenshots and Phase 32 demo transcripts. The README hero shot + 3 demo GIFs + editor screenshots are milestone artifacts; capturing them during the relevant phases (rather than as afterthoughts in Phase 34) is critical.

**Delivers:**
- `README.md` rewrite — hero shot of editor + 3 demo GIFs, sections: Quick Start (CLI), GUI Editor (PySide6, requires `[gui]`), Demos (3 walkthroughs), For Researchers, For Developers
- 3 demo GIFs captured during Phase 32 (suturing + knot-tying + needle-passing)
- 3 editor screenshots captured during Phase 33 (viewport + tree/form + LLM panel)
- `CONTRIBUTING.md` overhaul — dev setup `pip install -e ".[dev,gui,dreamer]"`, test/lint commands, optional extras table, Pydantic v2 quirks from `AGENTS.md`
- `CHANGELOG.md` v0.5.0 entry (Keep-a-Changelog format): Added (GUI, demos, docs) / Changed (PySide6 optional dep) / Fixed (421 ruff, HARD fixture, fluid hook, cut cooldown, Dockerfile.ros2, PhiFlow union)
- Demo transcripts (`docs/demos/{name}_transcript.md`)
- Optional: FAQ, troubleshooting section

**Uses:** Pillow + imageio (already transitive via mujoco) for screenshots/GIFs
**Addresses:** Category 3 features from FEATURES.md

**Validation:** README renders correctly. `surg-rl --help` mentions `surg-rl-gui` discoverability. CONTRIBUTING links resolve.

### Phase 35: Advanced Tech Debt

**Rationale:** Closes the medium-priority deferred items from the v0.4.2 closeout (PROJECT.md "Inherited tech debt"). Runs in parallel with Phases 32–34 via worktrees (Phase 35 only needs Phase 31's clean baseline). The HARD-fixture integration test is the only meaningful new test surface; K8s/organ-mesh items are scaffolding-only.

**Delivers:**
- `tests/integration/test_suturing_hard_env_construction.py` — loads `suturing_difficulty_hard.json`, constructs `SurgicalEnv`, calls `reset()`, asserts no crash (Phase 29 code review WR-02 deferred item)
- `CurriculumStageConfig.difficulty` normalization at env-construction (Phase 29 code review WR-03)
- `tests/k8s/test_pvc_e2e.py` — `[k8s]` marker + `kind` cluster skip; defer body
- `docs/research/organ-mesh-licensing.md` — candidate sources (surgtoolloc, MakeHuman, BodyParts3D); defer license decision to v0.6.0

**Validation:** HARD-fixture test passes. K8s scaffolding imports cleanly. Organ mesh research spike documented.

### Phase Ordering Rationale

- **Phase 31 first** because the editor phase (33) starts on a ruff-clean baseline and needs the mjpython helper, `[gui]` extra, and `surg-rl-gui` console script to exist before it begins. B904 (`raise from`) auto-fixes can subtly change semantics; doing them upfront means editor work doesn't touch dreamer.
- **Phase 32 second** because demos can be built independently of the editor (no Qt dependency) and produce artifacts Phase 34 needs. Phase 32's `_common.py` resolver also helps Phase 33's scene-loading code.
- **Phase 33 (marquée) third** because it depends on Phase 31's `[gui]` extra + console script + mjpython helper, and Phase 32's `_common.py` resolver. Editor work is the largest single contribution and naturally sits in the middle.
- **Phase 34 fourth** because it needs Phase 33's screenshots and Phase 32's transcripts to be useful — these are sequential artifacts, not afterthoughts.
- **Phase 35 last** because it only needs Phase 31's clean baseline; can run in parallel with Phases 32–34 via worktrees per `CLAUDE.md` rules.

### Research Flags

Phases likely needing deeper research during planning:

- **Phase 33 (PySide6 Editor):** Complex integration with multiple subsystems. Needs research on (a) MuJoCo `Renderer` API stability across 3.x minor versions, (b) PyBullet GUI thread-safety (no Context7 library — MEDIUM confidence in PITFALLS research; needs a smoke-test prototype), (c) Qt 6.5+ behavior on macOS Apple Silicon under `mjpython` (LOW confidence — combination not well-documented). Recommend a 1-hour spike at the start of Phase 33 to validate the offscreen render → QImage pipeline on macOS before writing the worker skeleton.

- **Phase 35 (Advanced Tech Debt):** Organ mesh licensing research spike — needs domain research on CC0/CC-BY source availability (MakeHuman, BodyParts3D, NIH 3D Print Exchange). Recommend lightweight research-phase before writing the spike doc.

Phases with standard patterns (skip research-phase):

- **Phase 31 (Tech Debt):** All items are well-known fixes from PROJECT.md. Ruff cleanup is mechanical (`ruff check --fix`). Dockerfile TARGETARCH is a 1-line change with documented multi-arch CI pattern. Fluid step hook follows existing ABC extension pattern. PhiFlow union() workaround has a known implementation per v0.3.2 deferred items.
- **Phase 32 (Demos):** Narration template + shared module pattern is well-established (mirrors existing `_omp_compat.py`). Demo regression tests follow existing suturing demo pattern (already 1168-test clean).
- **Phase 34 (Docs):** Keep-a-Changelog format is standard. README/CONTRIBUTING/CHANGELOG patterns are universal.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | **HIGH** | PySide6 6.11.1 verified against PyPI JSON; `mujoco.Renderer` API verified against Context7 `/google-deepmind/mujoco`; existing PyBullet `getCameraImage` already in use. License verified (LGPL-3 compatible with MIT dynamic linking). |
| Features | **HIGH** | All four categories have well-established patterns (PySide6 schema-driven forms mirror Blender/Godot; demo narration mirrors existing suturing demo; docs follow Keep-a-Changelog). Pydantic v2 `model_json_schema()` is industry standard. |
| Architecture | **HIGH** | `editor/` package mirrors existing `ros2/`/`dreamer/`/`marl`/`benchmark` lazy-import pattern. `SchemaWalker` separation (pure-Python, no Qt) is reusable. Render-to-numpy pattern verified against rl-baselines3-zoo. Merge order follows `CLAUDE.md` schema → simulators → scene_generation → editor → tests. |
| Pitfalls | **HIGH** for Qt+simulator thread safety (verified via Context7) and Pydantic v2 round-trip (verified); **MEDIUM** for PyBullet GUI thread safety (no Context7 library; based on PyBullet public docs + existing `pybullet_simulator.py` patterns). |

**Overall confidence:** HIGH

### Gaps to Address

- **Gap 1: Qt 6.5+ behavior on macOS Apple Silicon under `mjpython`** — Qt 6.5+ has improved CGL support but the `mjpython` combination is not well-documented. **Resolution:** Phase 33 Plan 1 should include a 1-hour spike that validates the offscreen render → QImage pipeline on macOS before writing the worker skeleton. The QMutex + thread-affinity pattern is the safest fallback.
- **Gap 2: PyBullet GUI thread safety under Qt** — No Context7 library available; based on PyBullet public docs. **Resolution:** Phase 33 should write a smoke test (`test_pybullet_direct_only.py`) that asserts no `p.GUI` call exists in the GUI code path. The `p.DIRECT`-only default is conservative.
- **Gap 3: Pydantic v2 round-trip for `_FloatMixin(float, Enum)` `DifficultyLevel`** — `model_dump(mode="json")` returns the float value (0.0/0.5/1.0), but round-trip through `model_validate(strict=False)` is the unverified path. **Resolution:** Phase 33 Plan 14 writes `scene_to_jsonable`/`scene_from_jsonable` helpers + a parametrized test that walks all 63 schema models.
- **Gap 4: Schema walker coverage of all 63 model types** — Some Pydantic v2 edge cases (`Literal[...]`, `Union[...]`, nested `Optional[Enum]`) are not explicitly enumerated in the research. **Resolution:** Phase 33 Plan 12 (`test_schema_walker.py`) constructs a `SceneDefinition` with all 63 model types populated and asserts every field renders a non-None `QWidget`. This is the schema-coverage guarantee.
- **Gap 5: DreamerV3 stub-state sentinel flip** — PROJECT.md mentions this deferred item carries forward, NOT in v0.5.0 scope. **Resolution:** Confirm in `gsd-state` that this is explicitly out-of-scope before Phase 31 begins.

## Sources

### Primary (HIGH confidence)

- **Context7 `/websites/doc_qt_io_qtforpython-6`** — `QMainWindow`, `QTreeView`, `QStandardItemModel`, `QFormLayout`, `QThread`/`QObject` worker pattern, Model-View selection signals
- **Context7 `/google-deepmind/mujoco`** — `mujoco.Renderer(model, height, width)` API, `render() → np.ndarray`, `GLContext` single-thread-affine contract
- **Context7 `/pydantic/pydantic`** — `model_dump(mode="json")` enum handling, `model_validate(strict=False)` coercion, `model_json_schema()` with `$defs`
- **Context7 `/executablebooks/markdown-it-py`** — `MarkdownIt('commonmark', ...)` API, plugin loading
- **PyPI JSON (verified 2026-06-18)** — PySide6 6.11.1, mujoco 3.9.0, markdown-it-py 4.2.0
- **Local verification** — `mujoco.Renderer` API confirmed, `pybullet.getCameraImage` confirmed, Pydantic `model_json_schema()` emits complete JSON Schema with 58 `$defs`
- **Existing codebase** — `src/surg_rl/utils/lazy_imports.py` (LazyImport), `src/surg_rl/scene_definition/schema.py` (Pydantic v2 models), `src/surg_rl/scene_generation/text_parser.py` (LLM interface), `src/surg_rl/simulators/scene_builder.py` (MJCF generation), `demos/demo.py` (CLI demo template)

### Secondary (MEDIUM confidence)

- **PyBullet GUI thread safety** — No Context7 library; based on PyBullet public docs and existing `pybullet_simulator.py` patterns. The `p.DIRECT`-only recommendation is conservative and needs validation on Linux + macOS before shipping.
- **Qt 6.5+ behavior on macOS Apple Silicon under `mjpython`** — Improved CGL support but not well-documented. QMutex + thread-affinity pattern is the safest fallback.

### Tertiary (LOW confidence)

- **Organ mesh licensing sources** (surgtoolloc, MakeHuman, BodyParts3D) — needs domain research spike in Phase 35 before license decision is made.

---

*Research completed: 2026-06-18*
*Ready for roadmap: yes — PROJECT.md 5-phase structure is validated; Phase 31 (Tech Debt Foundation) → Phase 35 (Advanced Tech Debt) is the recommended execution order with Phase 32 and Phase 35 able to parallel via worktrees.*
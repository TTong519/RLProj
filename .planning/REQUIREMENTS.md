# Requirements: Surg-RL

**Defined:** 2026-07-15
**Milestone:** v0.7.0 — GUI Editor Depth & Scene Generation
**Core Value:** End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation — with automatic primitive fallbacks when real assets are missing, and a benchmarking framework for systematic RL research comparisons.

## Build Order (user-confirmed)

The phases MUST be derived in this order. Adjacent requirements may be grouped into one phase only where tightly coupled (e.g. GEN-03/04/05 share the GEN-02 repair loop); otherwise one requirement per phase.

**GUI-18 → GUI-11 → GUI-12 → GUI-13 → GUI-14 → GUI-15 → GUI-16 → GUI-17 → GEN-01 → GEN-02 → GEN-03/04/05**

- GUI-18 first: dock-layout reset + closeEvent teardown is the cheapest, independent, high-trust win (fixes bug #3). Research-endorsed to lead.
- GUI-11 before GUI-12 (NOT the reverse): render/sim decoupling is the keystone — it fixes bugs #1/#2 AND is the loop multi-view must be built on. Building multi-view first forces render-integration rework.
- GUI-14 (gizmos) phase must run a research spike to resolve the 2D-QPainter-overlay vs 3D-pipeline approach disagreement (see `.planning/research/SUMMARY.md` Open Questions) before committing.
- GEN-03/04/05 reuse the GEN-02 bounded repair loop + structured-output protocol; GEN-04 reuses GEN-01 templates.

## v1 Requirements

Requirements for v0.7.0. Each maps to a roadmap phase. REQ-IDs continue the GUI series (v0.5.0 shipped GUI-01..10) and start the GEN series.

### GUI Editor Depth

- [ ] **GUI-11**: User sees an animated scene preview (the simulation steps live in the editor viewport) at >30 fps — fixes the immobile-preview and <10fps bugs via render/sim decoupling (`SimStepWorker` on QThread + `RenderPollLoop` on UI thread)
- [ ] **GUI-12**: User can switch between standard views (front/side/top/perspective) in a synchronized multi-view layout sharing one sim-state source
- [ ] **GUI-13**: User can adjust scene lighting (add/move/intensity/color lights) from the editor, with edits persisted to `SceneDefinition` and undoable
- [ ] **GUI-14**: User can transform selected objects with on-screen gizmos (translate/rotate/scale) by dragging handles — gizmo rendering approach resolved by a phase spike (2D `QPainter` overlay vs 3D pipeline)
- [ ] **GUI-15**: User can record the viewport to an mp4 video from within the editor (needs the one new dep `imageio-ffmpeg>=0.6.0`)
- [ ] **GUI-16**: User can multi-select, copy/paste, and duplicate scene nodes with keyboard shortcuts, with selection synced across tree, viewport, and form
- [ ] **GUI-17**: User can recover unsaved work via autosave + a crash-recovery prompt on launch, and the recent-files list works correctly (also fixes the duplicated `_refresh_recent_menu` latent bug)
- [x] **GUI-18**: User can reset the editor layout to default (dock panels restore on rerun), and closing the editor mid-operation does not crash — fixes the dock-not-reset-on-rerun bug via `DockStateManager` + a `closeEvent` teardown harness

### Scene Generation

- [ ] **GEN-01**: User can generate scenes from task templates covering all 6 task types (suturing/knot-tying/needle-passing/grasping/cutting/dissection) with easy/medium/hard difficulty variants
- [ ] **GEN-02**: User can generate a scene from a text prompt with structured output + automatic validation/repair (bounded: 1 repair default, max 2), degrading gracefully to a template if repair fails
- [ ] **GEN-03**: User can generate a scene from an image (VLM image→scene) via the editor panel and the CLI
- [ ] **GEN-04**: User can batch-generate a parameterized set of scenes (difficulty/instrument/organ sweeps) for curriculum/benchmark datasets
- [ ] **GEN-05**: User can answer clarifying questions interactively before the LLM generates a scene (GUI chat panel + CLI stdin mode)

## v2 Requirements

Deferred to future milestones. Tracked but not in the v0.7.0 roadmap.

- **GUI-19**: True 3D scene-graph viewport (Qt3D / QOpenGLWidget migration) — full render-bridge rewrite; v2.0 decision
- **GUI-20**: Surface/vertex snapping — needs the GUI-14 gizmo pick infrastructure; grid-snap may fold into a v0.7.0 phase if cheap
- **GEN-06**: Local VLM inference (weights in-repo / on-device) — the v0.7.0 target is the hosted-API path via existing providers; local via the `[vision]` extra is optional/stretch
- **GEN-07**: Fine-tuning a SurgVLM-style surgical-domain VLM in-repo — multi-GPU training infra out of charter

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| `mjpython` re-exec for native MuJoCo macOS rendering | Regresses the v0.5.0 main-thread hang fix; GUI stays in the stock interpreter |
| Multi-user networked collaborative editing | Single-user desktop tool; networking is a different product |
| Helm/K8s editor deployment | The editor is a desktop tool, not a deployment target (K8s deployment is for training, already shipped) |
| `langchain`/`llamaindex` orchestration for scene generation | Adds a heavy framework for flows the existing provider SDKs + a small state machine cover; rejected in STACK.md |
| `viser` / web-based viewport | Would require `QWebEngineView` — a parallel web stack alongside the native Qt editor; rejected in STACK.md |
| `qimage2ndarray` / `pyqtgraph` / `PyOpenGL` / `moderngl` / PyAV | Unneeded for the v0.5.0 image-based render bridge + imageio recording; rejected in STACK.md |
| Batch-gen byte-identical reproducibility guarantee | `temperature=0` does not guarantee byte-identical output across runs; v0.7.0 documents residual nondeterminism in scene metadata rather than claiming reproducibility |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| GUI-18 | Phase 41 | In Progress |
| GUI-11 | Phase 42 | Pending |
| GUI-12 | Phase 43 | Pending |
| GUI-13 | Phase 44 | Pending |
| GUI-14 | Phase 45 | Pending |
| GUI-15 | Phase 46 | Pending |
| GUI-16 | Phase 47 | Pending |
| GUI-17 | Phase 48 | Pending |
| GEN-01 | Phase 49 | Pending |
| GEN-02 | Phase 50 | Pending |
| GEN-03 | Phase 51 | Pending |
| GEN-04 | Phase 51 | Pending |
| GEN-05 | Phase 51 | Pending |

**Coverage:**

- v1 requirements: 13 total
- Mapped to phases: 13 (100%)
- Unmapped: 0 ✓

**Build order respected:** GUI-18 (41) → GUI-11 (42) → GUI-12 (43) → GUI-13 (44) → GUI-14 (45) → GUI-15 (46) → GUI-16 (47) → GUI-17 (48) → GEN-01 (49) → GEN-02 (50) → GEN-03/04/05 (51). GUI-11 decoupling before GUI-12 multi-view (non-negotiable). GEN-03/04/05 grouped (share GEN-02 repair loop + structured-output protocol).

---
*Requirements defined: 2026-07-15*
*Last updated: 2026-07-15 — traceability filled by roadmapper (v0.7.0 roadmap creation)*

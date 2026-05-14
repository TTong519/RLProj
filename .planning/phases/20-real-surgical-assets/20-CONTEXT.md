# Phase 20: Real Surgical Assets — Context

**Gathered:** 2026-05-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Load OBJ surgical instrument and organ meshes via trimesh, produce URDF/MJCF collision geometry for both backends, convert organ surfaces through the existing tetgen pipeline for deformable simulation, silently fall back to procedural shapes when meshes are missing. No new simulation behavior — purely asset loading and URDF/MJCF generation.

</domain>

<decisions>
## Implementation Decisions

### Mesh source strategy
- **D-01:** Default path: procedural trimesh primitives (capsule, box, rounded cylinder) generated as OBJ shapes — no external files needed, works offline
- **D-02:** Optional: public dataset download from a configurable URL (e.g. surgtoolloc, Thingiverse CC0) — user decides what gets downloaded
- **D-03:** CLI command `surg-rl assets download --instruments forceps,scalpel,...` explicitly fetches OBJs to `assets/meshes/`
- **D-04:** Lazy prompt on first load: if a scene references a mesh not found locally and internet is available, ask the user whether to download it

### OBJ to URDF/MJCF pipeline
- **D-05:** trimesh loads OBJ → saves as intermediate URDF file with mesh references → both MuJoCo and PyBullet load the URDF natively
- **D-06:** Collision geometry: V-HACD approximate convex decomposition for concave instruments (forceps jaws, retractor hooks)
- **D-07:** Separate visual mesh (original OBJ, decimated if `MeshAsset.target_face_count` set) and collision mesh (V-HACD decomposed) per instrument
- **D-08:** Multi-link articulated URDFs with type-based templates: forceps = shaft + 2 jaws, scalpel = single-link, needle driver = shaft + jaw, retractor = single-link
- **D-09:** URDF template definitions keyed to `InstrumentType` enum, generated in code — no external URDF template files

### Organ OBJ to tetgen path
- **D-10:** trimesh loads organ OBJ → writes as STL surface mesh → tetgen reads STL → tetrahedralizes → outputs .node/.ele → existing `DeformableConfig` loads as today
- **D-11:** Auto-repair with trimesh before tetgen: fill holes, remove degenerate faces, merge close vertices, ensure watertightness

### Fallback behavior & granularity
- **D-12:** When mesh is missing and `MeshAsset.fallback_enabled=True` (default): generate type-based procedural shape via trimesh (capsule for forceps, ellipsoid for organs, box for retractors) — single warning emitted at WARNING level

### OpenCode's Discretion
- Exact trimesh procedural primitive geometry for each instrument type
- V-HACD resolution/quality parameters (trade detail vs load time)
- STL export resolution and tetgen quality hints for organs
- trimesh auto-repair pipeline details (hole-fill tolerance, vertex merge threshold)
- Download URL configuration (env var, config file, or hardcoded fallback)
- Warning message wording for fallback cases
- URDF template implementation details (XML generation, link naming convention)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/ROADMAP.md` § Phase 20 — success criteria (ASET-01..ASET-05)
- `.planning/REQUIREMENTS.md` — ASET-01 through ASET-05 requirements

### Schema contracts (from Phase 19)
- `src/surg_rl/scene_definition/schema.py` — `MeshAsset` (line 224, now with `target_face_count`, `fallback_enabled`, `mesh_origin`), `InstrumentConfig` (line 797, has `mesh: MeshAsset | None`), `TissueConfig` (line 675, has `deformable: DeformableConfig`), `DeformableConfig` (line 416, tetgen pipeline entry)

### Existing asset loading infrastructure
- `src/surg_rl/simulators/scene_builder.py` — `SceneBuilder` (line 77), `create_mjcf()` (line 458), primitive fallback generation, tetgen .node/.ele parsing
- `src/surg_rl/assets/__init__.py` — `TRIMESH = LazyImport("trimesh", "assets")` lazy import guard
- `pyproject.toml` — `[assets]` optional dependency group (`trimesh>=4.5.0`)

### Architecture & conventions
- `.planning/codebase/ARCHITECTURE.md` — Simulator abstraction layer, `SceneDefinition` as single source of truth
- `.planning/codebase/STACK.md` — trimesh integration, optional dependency pattern
- `.planning/phases/19-schema-foundation/19-CONTEXT.md` — Phase 19 decisions (D-01..D-08) — schema model contracts

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `InstrumentConfig.mesh: MeshAsset | None` (schema.py:805) — already the field Phase 20 populates
- `InstrumentConfig.primitive: Literal["box", "sphere", "cylinder", "capsule"]` (schema.py:806) — existing primitive fallback, superseded by trimesh procedural shapes when mesh is missing
- `DeformableConfig.mesh_source: Literal["tetgen", "flexcomp_grid", "file"]` (schema.py:424) — organ tetrahedralization entry point, `mesh_source="tetgen"` path is the organ pipeline target
- `SceneBuilder` primitive mesh generation — existing fallback for box/sphere/cylinder; reused for trimesh procedural shapes
- TRIMESH lazy guard (`assets/__init__.py`) — import with `.available` check, no `ImportError` on missing dep

### Established Patterns
- Intermediate format generation (in-memory tetgen → MJCF bridge from Phase 15–18)
- Graceful degradation: warn + fallback, never crash — Phase 6 pattern
- Lazy import guards for optional deps — Phase 19 pattern (D-05/D-06)
- Pydantic v2 dataclasses for all config objects

### Integration Points
- `SceneBuilder.create_mjcf()` — extend to accept trimesh-loaded geometry (or URDF path) instead of only SceneDefinition
- `InstrumentConfig` — populated with URDF path after OBJ→URDF conversion (or existing mesh field holds the reference)
- `DeformableConfig` — organ meshes feed into existing `mesh_source="tetgen"` path with STL intermediate
- `assets/meshes/` directory — destination for downloaded OBJs, source for local mesh loading
- CLI (`cli.py`) — new `surg-rl assets download` subcommand

</code_context>

<deferred>
## Deferred Ideas

- Procedural organ mesh generation (sphere → warped ellipsoid with noise) — could replace OBJ fallback, but requires geometric modeling beyond trimesh scope
- COLLADA/glTF format support — OBJ is universal baseline; multi-format deferred
- Real-time mesh decimation (for dynamic LOD during rendering) — Phase 23 (benchmarking) may revisit

</deferred>

---

*Phase: 20-real-surgical-assets*
*Context gathered: 2026-05-13*

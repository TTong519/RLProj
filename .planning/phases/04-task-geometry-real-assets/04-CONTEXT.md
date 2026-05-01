# Phase 4: Task Geometry + Real Assets — Context

**Gathered:** 2026-04-30
**Status:** Ready for planning

## Phase Boundary

Bind scene task objectives to simulator observation fields with explicit geometry references, and enable SceneBuilder to load real URDF/OBJ assets with graceful fallback logging. This phase delivers the data pipeline from scene definition → simulator state → RL observation for task-specific geometry (needle, entry/exit points, incision progress).

## Requirements Locked (TASK-01..TASK-04)

- **TASK-01**: Suturing scene observation contains `needle_pos` within 1e-3 of objective-specified geometry
- **TASK-02**: Entry/exit point observations match task objective geometry when specified
- **TASK-03**: Scene with external URDF/DAE/OBJ loads successfully (test with sample URDF)
- **TASK-04**: Fallback warning is logged once per missing asset, not per frame

## Implementation Decisions

### A: Observation field wiring (TASK-01 / TASK-02)

**Use explicit `target_body` references in task objectives rather than heuristic string matching.**

- Add optional `target_body: str` field to `TaskObjective` schema (additive, backward-compatible)
- If `target_body` is present: simulators resolve it via `self._body_ids` (PyBullet) or body names (MuJoCo) to get actual pose → observation field
- If `target_body` is absent: fall back to current heuristic (first instrument pose for needle, tissue-name string matching for entry/exit) to preserve existing scene compatibility
- Incision progress: computed from `objectives` completion ratio (already partially implemented in MuJoCo); unify logic in both backends
- Rationale: Heuristic matching (`"entry" in tissue_name`) is fragile and untestable. Explicit references make scenes self-describing.

### B: Real asset loading (TASK-03 / TASK-04)

**Support URDF and OBJ formats with single-shot fallback logging.**

- **URDF**: Use native loaders — `p.loadURDF` (PyBullet) and `mjcf` / direct URDF→MJCF conversion (MuJoCo). No new dependency needed.
- **OBJ**: Use as visual mesh only (collision geometry still from primitives or convex decomposition). PyBullet supports `.obj` in `loadURDF` via visual tags; MuJoCo supports `.obj` meshes in MJCF via `mesh` asset.
- **Missing asset handling**: Log a single `logger.warning` at `load_scene()` time if a referenced asset file does not exist. Store `self._missing_assets: set[str]` to prevent duplicate warnings. Do NOT raise — always fall back to procedural primitive.
- **Asset path resolution**: Support relative paths (resolved against scene JSON directory) and absolute paths. Use `pathlib.Path` with `resolve()`.
- Rationale: URDF is the standard robotics format; OBJ is widely supported. Single-log prevents console spam during training.

### C: Schema evolution strategy

**Minimal additive change with backward compatibility.**

- `TaskObjective` gets one new optional field: `target_body: str | None = None`
- No migration needed — existing scenes without `target_body` continue to work via heuristic fallback
- `TissueMeshDefinition` already has `mesh_path: str | None`; we wire it into SceneBuilder loaders
- Observation dataclass (`Observation`) already has `needle_pos`, `entry_point`, `exit_point`, `incision_progress` — we populate them correctly instead of with heuristics/TODOs
- Rationale: Avoid breaking changes to scene definitions. Additive fields are safest.

## Canonical References

- `.planning/ROADMAP.md` → Phase 4 definition and success criteria
- `.planning/REQUIREMENTS.md` → TASK-01..TASK-04 requirements
- `src/surg_rl/scene_definition/schema.py` → `TaskObjective`, `TissueMeshDefinition`, `SceneDefinition` models
- `src/surg_rl/simulators/pybullet_simulator.py` → `_get_observation()` lines 1424-1490 (task field population, TODO comments)
- `src/surg_rl/simulators/mujoco_simulator.py` → `_get_observation()` lines 786-870 (needle proxy, entry/exit heuristic)
- `src/surg_rl/simulators/scene_builder.py` → `_add_tissue()`, `_build_robot()` — add real asset loading hooks
- `src/surg_rl/simulators/base_simulator.py` → `Observation` dataclass (needle_pos, entry_point, exit_point, incision_progress)
- `AGENTS.md` → "Scene assets (URDFs / meshes) do not exist in `assets/`. `scene_builder` generates primitive `.obj` fallbacks on the fly."

## Existing Code Insights

### Reusable Assets
- `Observation` dataclass already has all required fields (needle_pos, entry_point, exit_point, incision_progress) — just need to populate them correctly
- `SceneBuilder` already has `_primitive_meshes` cache and primitive generation pipeline — extend with real asset branch
- `TissueMeshDefinition` already has `mesh_path` field — wire it into loader

### Established Patterns
- Simulator backends share `Observation` schema via `base_simulator.py` — changes propagate to both automatically
- `load_scene()` pattern: clear state → build bodies → return. Asset loading fits in the "build bodies" phase.
- `_body_ids` dict in PyBullet maps names → body IDs; MuJoCo uses `mj_name2id` — both support name-based lookup.

### Integration Points
- `SurgicalEnv._default_observation_config()` auto-detects observation types — no change needed if observation fields are populated
- `rewards.py` already consumes `needle_pos`, `entry_point`, etc. — data consumers are ready
- `create_default_reward()` uses `task_name` — reward functions will automatically benefit from accurate geometry

## Deferred Ideas

- **DAE/COLLADA format support** — Not in scope; OBJ covers most surgical mesh needs, URDF covers articulated assets
- **Asset preloading / shared cache across scenes** — Memory optimization; defer to Phase 5 infrastructure
- **Convex decomposition for non-convex OBJ collision** — Requires VHACD or similar; too complex for this phase. Use primitive collision fallback.
- **Texture/material loading from OBJ MTL** — Visual-only; defer to rendering phase

---

*Phase: 04-Task Geometry + Real Assets*
*Context gathered: 2026-04-30*

# Phase 3: Simulator Robustness — Context

## Domain

Performance optimization and cross-backend consistency for simulator state management, procedural mesh generation, and training evaluation. This phase delivers infrastructure that makes surgical simulations fast enough for RL training loops and deterministic enough for reproducible experiments.

---

## Requirements Locked (PERF-01..PERF-04)

- **PERF-01**: Soft-body episode reset <100ms on suturing scene
- **PERF-02**: Procedural mesh generation 64³ cells <1s
- **PERF-03**: `get_state()` → `set_state()` observation identical to `reset()` in both backends
- **PERF-04**: `evaluate()` reuses existing VecEnv; no new env creation per call

---

## Decisions

### A: Soft-body mesh caching (PERF-01)

**Cache generated tetrahedral mesh data in memory and reuse across episode resets.**

- Cache scope: PyBullet simulator instance (`self._mesh_cache: dict[str, tuple[np.ndarray, np.ndarray]]` keyed by `(tissue_name, geometry_type, params)`)
- Store NumPy arrays (`verts`, `tets`) — NOT just `.vtk` file paths
- First episode: generate → write `.vtk` → cache arrays → load soft body
- Subsequent episodes: check cache → skip generation → reuse `.vtk` path (cleaned up with `scene_builder.temp_dir` lifecycle)
- Applies only to `_get_vtk_mesh_path()` in `pybullet_simulator.py`
- Does NOT cache the loaded soft body ID itself (IDs invalidated by `resetSimulation()`)

### B: State serialization scope (PERF-03)

**Extend `State` to include soft-body node positions for full round-trip fidelity.**

- `State.custom` field used for backend-specific extensions (already exists in base class)
- PyBullet: `get_state()` calls `p.getSoftBodyData(body_id)` → store node positions/velocities in `State.custom["soft_body_nodes"]`
- PyBullet: `set_state()` reads from `State.custom["soft_body_nodes"]` and restores via `p.setSoftBodyData()` or `p.resetSoftBody()` depending on PyBullet version
- MuJoCo: Verify if deformable bodies exist in `qpos` / `qvel` (MuJoCo soft bodies are already part of the generalized coordinates). If not, add to `State.custom` with equivalent structure
- Rationale: Without node data, a `get_state` after tissue deformation → `set_state` → step would diverge from the original state because soft body would reset to rest pose

### C: Mesh generation vectorization (PERF-02)

**Hybrid strategy: fast path for primitives, library delegation for complex shapes.**

- **Simple shapes** (sphere, box, cylinder): rewrite `mesh_generation.py` using pure NumPy vectorization (`np.meshgrid`, `np.indices`, broadcasting)
  - Sphere: icosahedron subdivision → vectorized vertex indexing
  - Box: brick-tetrahedral tiling via `np.indices` + `np.stack`
  - Cylinder: radial slice stacking → vectorized polar-to-cartesian + tet connectivity
  - All three must remain under 100ms for current resolution levels (subdivisions=2, resolution=4)

- **Complex shapes** (>5000 tets or custom `.obj` input): automatic delegation to external mesher
  - Threshold: `len(tets) > 5000` triggers `try/except import trimesh; trimesh.creation` or `pyvista.Tetrahedralization`
  - If external library unavailable or fails: fallback to current slow generator with warning
  - Only add `trimesh` as optional dependency (`pip install trimesh`); soft-fail if absent

- **Caching layer**: SceneBuilder's existing `_primitive_meshes` dict already caches `.obj` paths. Extend it to also cache `.vtk` file paths (or create `_vtk_meshes` parallel dict). Same `cache_key` pattern: `(geometry_type, params, resolution)`.

### D: VecEnv evaluation reuse (PERF-04)

**Persistent evaluation environment stored on training runner, reused across evaluations.**

- `SurgicalTrainingRunner` stores `self._eval_env: DummyVecEnv | SubprocVecEnv | None = None` after first `evaluate()` call
- On subsequent `evaluate()` calls: call `self._eval_env.reset()` instead of `make_vec_env(...)`
- Fallback if config mismatch detected (scene_path, action_type, or simulator_type changed since last eval): discard cached env and create new one
- `make_vec_env` still exposed for external callers without a TrainingRunner instance
- Threading / process safety: `SubprocVecEnv` processes already isolated; `DummyVecEnv` is thread-safe at the wrapper level but the underlying `SurgicalEnv` is not. Document that `evaluate()` must not be called concurrently with training `learn()` on the same runner.

---

## Canonical Refs

- `.planning/ROADMAP.md` → Phase 3 definition and success criteria
- `.planning/REQUIREMENTS.md` → PERF-01..PERF-04 requirements
- `src/surg_rl/simulators/pybullet_simulator.py` → `_get_vtk_mesh_path`, `_load_soft_body_tissue`, `get_state`, `set_state`
- `src/surg_rl/simulators/mujoco_simulator.py` → `get_state`, `set_state`
- `src/surg_rl/utils/mesh_generation.py` → `generate_box_tet_mesh`, `generate_sphere_tet_mesh`, `generate_cylinder_tet_mesh`
- `src/surg_rl/simulators/scene_builder.py` → `_primitive_meshes` cache pattern
- `src/surg_rl/rl/training.py` → `make_vec_env`, `evaluate`

## Deferred Ideas

- **Mid-episode save/restore for soft bodies** — Not in scope; PERF-03 targets episode-start parity, not arbitrary checkpoints
- **GPU-accelerated mesh generation (CuPy/Numba)** — Overkill for current scale; revisit if resolution >256³
- **Shared memory VecEnv between train and eval** — Could reduce memory but fragile; defer to Phase 5 infrastructure

---

## Next Step

`/gsd-plan-phase 3` — Researcher and planner use this CONTEXT.md as the locked decision set.

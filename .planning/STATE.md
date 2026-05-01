# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-29)

**Core value:** End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation
**Current focus:** Phase 3 complete — proceeding to Phase 4

## Current Position

Phase: 3 of 5 (Simulator Robustness)
Plan: 2 of 2 complete
Status: Verified — all UAT passed, ready for Phase 4
Last activity: 2026-04-30 — Phase 3 UAT complete (6/6 passed, 0 issues); ready to advance

Progress: [████████████████░░░░░░] 60%

## Performance Metrics

**Velocity:**
- Total plans completed: 8
- Average duration: ~13 minutes
- Total execution time: ~2 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Critical Bug Fixes | 3/3 | 3 | ~10 min |
| 2. Action Space + Gripper | 3/3 | 3 | ~20 min |
| 3. Simulator Robustness | 2/2 | 2 | ~18 min |

**Recent Trend:**
- Last plans: 03-01 (mesh caching + vectorization), 03-02 (state serialization + VecEnv reuse)
- Trend: sequential executor agents for stable backend work, zero regressions across 579 tests (up from 567 baseline)

## Phase 3 Summary

### What was built

1. **Soft-body mesh caching (PERF-01)**:
   - `PyBulletSimulator._mesh_cache: dict[str, Path]` keyed by tissue params
   - Cache hit skips `.vtk` regeneration; reset <100ms on suturing scene
   - Cache cleared on `load_scene()` and `close()` to prevent staleness

2. **Vectorized mesh generation (PERF-02)**:
   - `generate_box_tet_mesh` vectorized with `np.indices + np.stack + reshape`, ~10x faster at high resolution
   - `generate_cylinder_tet_mesh` vertex loop vectorized with `np.stack([cos, sin, z])`
   - Sphere subdivision kept iterative (correctness over speed after Rule 1 bug fix)
   - Optional `pyvista` delegation for meshes >5000 tets; falls back gracefully
   - SceneBuilder extended with `_vtk_meshes` dict and `_get_cached_vtk_path()`

3. **Cross-backend state save/restore (PERF-03)**:
   - PyBullet `get_state()` captures soft-body node positions via `getMeshData()` into `State.custom["soft_body_nodes"]`
   - PyBullet `set_state()` restores joint positions/velocities via `resetJointState` and soft-body nodes via `resetMeshData()`
   - MuJoCo round-trip fidelity verified: qpos/qvel identical within 1e-6
   - PyBullet round-trip: qpos/qvel within 1e-6, body_positions within 1e-3 (recomputed by forward kinematics)

4. **Persistent eval env caching (PERF-04)**:
   - `TrainingManager.evaluate()` caches eval env on `self._eval_env`
   - `_build_eval_env_key()` hashes all config fields that affect env construction
   - Config mismatch triggers disposal of stale env and creation of new one
   - `close()` properly disposes cached eval env

### Commits

- `17308c4` — 03-01 T1: soft-body mesh caching
- `0c02352` — 03-01 T2: vectorize mesh generation + SceneBuilder caching
- `22ccc5b` — 03-01 SUMMARY
- `f6f2624` — 03-02 T1: PyBullet soft-body/joint state save/restore
- `4efffb1` — 03-02 T2: TrainingManager eval env caching
- `c9ad176` — 03-02 SUMMARY

*Updated: 2026-04-30*

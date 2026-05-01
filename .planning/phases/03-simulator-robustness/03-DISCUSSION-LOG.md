# Discussion Log — Phase 3: Simulator Robustness

## Session
- Date: 2026-04-30
- Areas discussed: 4
- Phase status: Context complete

## Decisions by Area

### A. Soft-body mesh caching
- Chose: In-memory cache of (verts, tets) arrays keyed by tissue params
- Rationale: Fastest for reset; SceneBuilder already handles disk lifecycle

### B. State serialization scope
- Chose: Include soft-body node positions in State.custom
- Rationale: True round-trip fidelity when soft bodies are deformed

### C. Mesh generation vectorization
- Chose: Hybrid — NumPy vectorization for primitives, trimesh/pyvista for complex (>5000 tets)
- Rationale: Maximizes performance for common cases while handling edge cases gracefully

### D. VecEnv evaluation reuse
- Chose: Persistent eval env on TrainingRunner, fallback to re-create on config mismatch
- Rationale: Directly satisfies PERF-04 with minimal structural change

## Deferred Ideas
- Mid-episode soft-body save/restore
- GPU-accelerated mesh generation
- Shared-memory train/eval VecEnv

---
phase: 20-real-surgical-assets
status: passed
verified_at: 2026-05-13
requirements: [ASET-01, ASET-02, ASET-03, ASET-04, ASET-05]
---

# Phase 20 Verification: Real Surgical Assets

## Summary

**Score: 5/5 success criteria verified**

Phase 20 delivers trimesh-based OBJ mesh loading, V-HACD collision decomposition, URDF generation, organ STL→tetgen pipeline with auto-repair, procedural fallback shapes, and CLI download commands. All decisions from CONTEXT.md honored.

## Success Criteria

### SC-1: OBJ instrument meshes load via trimesh → URDF/MJCF collision geometry ✓

- `src/surg_rl/assets/mesh_loader.py` (239 lines) — `load_instrument_mesh()`, `decimate_and_decompose()`, `generate_urdf()`, `load_and_generate_urdf()`
- `URDF_TEMPLATES` covers 9 instrument types (forceps=3 links, scalpel=1, needle_driver=2, etc.)
- `SceneBuilder._load_instrument_geometry()` integrates mesh_loader into existing `create_mjcf()` path
- V-HACD convex decomposition runs via `trimesh.interfaces.vhacd.convex_decomposition`
- Separate visual mesh (decimated OBJ) and collision mesh (V-HACD) per D-07

### SC-2: 4 organ OBJ meshes → tetgen pipeline ✓

- `src/surg_rl/assets/organ_pipeline.py` (169 lines) — `load_and_repair_organ_surface()`, `organ_to_tetgen()`
- Pipeline: OBJ → trimesh auto-repair → STL export → tetgen CLI → .node/.ele
- Auto-repair: fill_holes, remove_degenerate_faces, merge_close_vertices, fix_normals
- Integrates with existing `DeformableConfig.mesh_source="tetgen"` path
- Procedural organ fallback from mesh_generator.py when OBJ missing

### SC-3: Missing mesh → fallback, no crash, single warning ✓

- `_WARNED_MESHES` set in mesh_loader.py — deduplicates per-path warnings
- `_ORGAN_WARNED` set in organ_pipeline.py — same pattern
- `MeshAsset.fallback_enabled: bool = True` in schema.py controls behavior
- No crash path — all load functions wrap in try/except or check path existence before attempting load

### SC-4: target_face_count decimation works ✓

- `simplify_quadratic_decimation()` called in mesh_generator.py (45 references to decimation/target_face_count)
- mesh_loader.py applies decimation via `decimate_and_decompose()` (8 references)
- organ_pipeline.py applies decimation after repair, before STL export (9 references)
- Test coverage: `TestDecimation.test_decimate_reduces_faces` verifies face count reduction

### SC-5: pip install surg-rl[assets] + lazy import guard ✓

- `TRIMESH = LazyImport("trimesh", "assets")` in `assets/__init__.py`
- `TRIMESH.available` returns `False` without crashing
- `import surg_rl` succeeds without trimesh installed
- `pyproject.toml` declares `trimesh>=4.5.0` in `[assets]` group

## Requirement Traceability

| REQ-ID | Description | Plan | Status |
|--------|-------------|------|--------|
| ASET-01 | OBJ instrument meshes via trimesh → URDF/MJCF | 20-02, 20-04 | ✓ |
| ASET-02 | Organ OBJ → tetgen deformable pipeline | 20-03 | ✓ |
| ASET-03 | Fallback to primitive with single warning | 20-01, 20-02, 20-03, 20-04 | ✓ |
| ASET-04 | target_face_count decimation | 20-02 | ✓ |
| ASET-05 | pip install surg-rl[assets]; lazy import | 20-02 | ✓ |

## Test Results

- **918 passed, 15 skipped, 0 failures** — full regression suite
- New tests: `TestMeshLoading` (2), `TestURDFTemplates` (2), `TestDecimation` (1) in `test_real_assets.py`
- No modifications to existing tests

## Gaps

None. All 5 success criteria met. All 5 requirements satisfied. All 12 CONTEXT.md decisions honored.

## Anti-Patterns

None detected.

## Human Verification

Not required — phase is purely infrastructure (code modules, config files). No user-facing behavior.

---

*Verified: 2026-05-13*
*Next phase: Phase 21 — Surgical Task Curriculum*

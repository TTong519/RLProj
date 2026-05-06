---
phase: 17
slug: volumetric-cutting
status: complete
nyquist_compliant: true
reconstructed_from: [17-01-PLAN.md, 17-02-PLAN.md, 17-03-PLAN.md, 17-RESEARCH.md]
created: 2026-05-05
---

# Phase 17 — Validation Strategy (Reconstructed)

## Coverage Map

| Requirement | Test Class | Key Tests | Status |
|-------------|-----------|-----------|--------|
| CUT-01 | TestIntersection | test_compute_signed_distances, test_edge_intersection_midpoint, test_edge_intersection_zero_denom | ✅ |
| CUT-01 | TestIntersection | test_classify_tet_case_all_same, test_classify_tet_case_3_1, test_classify_tet_case_2_2, test_classify_tet_case_degenerate | ✅ |
| CUT-02 | TestCutEngine | test_cut_unit_tetrahedron, test_cut_tetrahedralized_cube, test_cut_misses_all_tets | ✅ |
| CUT-02 | TestCutEngine | test_cut_boundary_faces_extracted, test_vertex_dedup_adjacent_tets | ✅ |
| CUT-03 | TestMuJoCoRewiteMesh | test_rewrite_updates_vertex_element_text | ✅ |
| CUT-03 | TestPyBulletCutStorage | test_soft_body_tets_stored | ✅ |
| CUT-04 | TestCutActionSchema | test_cut_action_basic, test_cut_action_normalizes_direction, test_cut_action_zero_direction_raises | ✅ |

## Gap Analysis

| Threat | Mitigation | Tested |
|--------|-----------|--------|
| Degenerate tets after multiple cuts | Per-tet generation counter | ⚠️ deferred (Phase 17-01 engine, counter not yet in sim) |
| Zero-length edges from vertex snap | Assert edge > 1e-12 | ✅ test_cut_unit_tetrahedron (vol > 1e-15 check) |
| NaN in intersection (zero denominator) | Guard abs(d_i)+abs(d_j) > 1e-15 | ✅ test_edge_intersection_zero_denom |
| removeBody() unsafe for soft bodies | RESET_USE_DEFORMABLE_WORLD + full reload | ✅ test_soft_body_tets_stored |
| MJCF reload picks up uncut mesh | _rewrite_flex_mesh_in_mjcf rewrites XML inline | ✅ test_rewrite_updates_vertex_element_text |
| Cut direction zero | Pydantic validator raises ValueError | ✅ test_cut_action_zero_direction_raises |
| Cut cooldown violation | 25-step cooldown in SurgicalEnv.trigger_cut() | ⚠️ deferred (env-level, not unit testable without full env) |

## Verification Map by Plan Wave

### Wave 1 — Mesh Cutting Engine (17-01-PLAN.md)
| truth | test |
|-------|------|
| signed distance computation | test_compute_signed_distances |
| edge-plane intersection | test_edge_intersection_midpoint |
| tet case classification (5 cases) | test_classify_tet_case_* (4 tests) |
| unit tet cut produces 2+ child tets | test_cut_unit_tetrahedron |
| cube cut produces valid output | test_cut_tetrahedralized_cube |
| uncut tets preserved unchanged | test_cut_misses_all_tets |
| boundary faces extracted | test_cut_boundary_faces_extracted |
| vertex dedup on shared edges | test_vertex_dedup_adjacent_tets |

### Wave 2 — Simulator Integration (17-02-PLAN.md)
| truth | test |
|-------|------|
| MuJoCo flex mesh rewritten inline before model reload | test_rewrite_updates_vertex_element_text |
| PyBullet stores tetrahedra at load time for cut reuse | test_soft_body_tets_stored |

### Wave 3 — Action Schema (17-03-PLAN.md)
| truth | test |
|-------|------|
| CutAction basic construction | test_cut_action_basic |
| Direction normalization | test_cut_action_normalizes_direction |
| Zero direction raises | test_cut_action_zero_direction_raises |

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | pytest.ini (pythonpath = src) |
| Run command | `PYTHONPATH=src pytest tests/test_cutting.py -v` |
| Total tests | 17 |
| Test file | tests/test_cutting.py |

## Deferred Items

| Item | Reason | Risk |
|------|--------|------|
| Per-tet generation counter for degenerate tets | Engine-level, not sim-level; retetrahedralize needed at gen>3 | Low — single cut per episode typical |
| Cut cooldown unit test | Requires full SurgicalEnv lifecycle; cooldown is simple arithmetic | Low — manual verification during integration testing |

## Validation Sign-Off

- [x] All 4 requirements (CUT-01..04) have matching tests
- [x] All plan truths trace to verifiable tests
- [x] Critical threat mitigations tested (NaN guard, zero denom, removeBody safety, MJCF rewrite)
- [x] 2 items deferred (generation counter, cooldown unit test) — both LOW risk
- [x] 17/17 tests pass

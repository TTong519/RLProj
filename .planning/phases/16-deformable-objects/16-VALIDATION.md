---
phase: 16
slug: deformable-objects
status: complete
nyquist_compliant: true
reconstructed_from: [16-01-PLAN.md, 16-02-PLAN.md, 16-RESEARCH.md]
created: 2026-05-05
---

# Phase 16 — Validation Strategy (Reconstructed)

## Coverage Map

| Requirement | Test Class | Key Tests | Status |
|-------------|-----------|-----------|--------|
| DEFM-01 | TestMuJoCoFlexGeneration | test_flex_body_mjcf_structure, test_flex_body_elasticity_from_config, test_flex_body_boundary_conditions, test_backward_compat_flexcomp_fallback, test_rigid_body_path_unchanged | ✅ |
| DEFM-01 | TestMuJoCoFlexGeneration | test_parse_node_file, test_parse_ele_file_converts_to_zero_indexed | ✅ |
| DEFM-02 | TestPyBulletParamMapping | test_derive_neo_hookean_params_typical_tissue, test_derive_neo_hookean_params_low_poisson, test_derive_neo_hookean_params_zero_poisson | ✅ |
| DEFM-02 | TestPyBulletParamMapping | test_neo_hookean_auto_derive_kwargs, test_neo_hookean_explicit_override, test_mass_spring_mode_unchanged, test_pybullet_flex_overrides_flow, test_no_deformable_config_backward_compat | ✅ |
| DEFM-03 | TestDeformableConfigSchema | test_tetgen_source_requires_mesh_path, test_grid_source_allows_no_mesh_path, test_file_source_requires_mesh_path | ✅ |
| DEFM-03 | TestDeformableConfigSchema | test_mujoco_flex_config_overrides, test_pybullet_flex_config_stores_solver_type, test_boundary_condition_validation, test_backend_configs_dont_cross_contaminate | ✅ |
| DEFM-03 | TestDeformableConfigSchema | test_tissue_config_includes_deformable, test_tissue_config_without_deformable_is_none | ✅ |
| DEFM-04 | TestDeformableObservation | test_build_spec_default_max_vertices, test_build_spec_custom_max_vertices, test_pad_observation_to_spec, test_truncate_observation_to_spec, test_empty_observation_returns_zero_fallback | ✅ |
| DEFM-04 | TestDeformableObservation | test_compute_edge_strain_identical, test_compute_edge_strain_stretched, test_compute_edge_strain_zero_rest_epsilon | ✅ |

## Gap Analysis

| Threat | Mitigation | Tested |
|--------|-----------|--------|
| Cross-contamination of MuJoCo/PyBullet config | test_backend_configs_dont_cross_contaminate | ✅ |
| Missing deformable config silent fallback | test_no_deformable_config_backward_compat | ✅ |
| Neo-Hookean div-by-zero (poisson=0.5) | test_derive_neo_hookean_params_zero_poisson | ✅ |
| Observation overflow (more verts than spec) | test_truncate_observation_to_spec | ✅ |
| Empty deformation data | test_empty_observation_returns_zero_fallback | ✅ |
| Zero rest length in strain | test_compute_edge_strain_zero_rest_epsilon | ✅ |

## Verification Map by Plan Wave

### Wave 1 — Schema + MuJoCo FEM (16-01-PLAN.md)
| truth | test |
|-------|------|
| DeformableConfig schema exists with MuJoCoFlexConfig, PyBulletFlexConfig, BoundaryCondition | TestDeformableConfigSchema (9 tests) |
| TissueConfig references DeformableConfig | test_tissue_config_includes_deformable |
| SceneBuilder generates <deformable>/<flex> for tetgen meshes | test_flex_body_mjcf_structure |
| MJCF encodes vertex positions and element indices from tetgen | test_parse_node_file, test_parse_ele_file |
| Backend overrides don't cross-contaminate | test_backend_configs_dont_cross_contaminate |

### Wave 2 — PyBullet params + observation (16-02-PLAN.md)
| truth | test |
|-------|------|
| Neo-Hookean μ/λ auto-derived from Young's + Poisson's | test_derive_neo_hookean_params_* (3 tests) |
| loadSoftBody uses DeformableConfig.pybullet | test_pybullet_flex_overrides_flow |
| Observation extracts padded vertex positions | test_pad_observation_to_spec |
| TISSUE_DEFORMATION_SPEC uses configurable max_vertices | test_build_spec_default_max_vertices |
| Strain computed when observe_strain=True | test_compute_edge_strain_* (3 tests) |

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | pytest.ini (pythonpath = src) |
| Run command | `PYTHONPATH=src pytest tests/test_deformable.py -v` |
| Total tests | 31 |
| Test file | tests/test_deformable.py + tests/conftest.py |

## Validation Sign-Off

- [x] All 4 requirements (DEFM-01..04) have matching tests
- [x] All plan truths trace to verifiable tests
- [x] Edge cases covered (empty, overflow, cross-contamination, backward compat)
- [x] No gaps found
- [x] 31/31 tests pass

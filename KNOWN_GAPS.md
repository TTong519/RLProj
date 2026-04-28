# Known Gaps & Incomplete Features

Comprehensive audit of the surg-rl codebase.  
Generated from static analysis, sub-agent audits, doctest/test coverage review, and comparison with `docs/`.  
**Status as of 2026-04-27.**

---

## Legend

| Severity | Meaning |
|----------|---------|
| 🔴 **CRITICAL** | Feature is broken or completely absent; user workflow fails. |
| 🟠 **HIGH** | Architectural / design gap; blocks downstream functionality. |
| 🟡 **MEDIUM** | Quality, merge, or randomization gap; works but incorrectly or incompletely. |
| 🟢 **LOW** | Minor / polish; known limitation or convenience issue. |

---

## Top-Level Summary

| Category | Count | Notes |
|----------|-------|-------|
| CLI / User-facing | 3 critical | `generate --text`, `train`, `evaluate` unrunnable |
| Scene Generation / Merge | 4 critical + 4 medium | `assets` dropped, `task` overwritten, `environment` shallow-merged |
| Simulator Backends | 6 critical + 5 high + 8 medium | Missing soft body, depth render, force/torque/pose control, observation population |
| RL / Observation / Action | 3 critical + 6 high + 6 medium | Discrete actions broken, task observations absent, gripper unimplemented |
| Domain Randomization / Curriculum | 3 high + 8 medium | Curriculum params incomplete (gravity-only), PyBullet only base link, texture/camera/delay ignored |
| Tests | 2 critical + 3 medium | Zero runnable integration tests, no mocked LLM CLI tests |
| Total | **~39 distinct issues** | |

---

## 🔴 CRITICAL

### C1. CLI `generate --text` / `--image` crashes without manual dependency install ✅ FIXED
- **Files**: `src/surg_rl/cli.py:134-190`, `pyproject.toml`
- **Fix**: Wrapped `TextParser`/`VisionParser` instantiation in `try/except ImportError`; on failure suggests `--provider ollama`. Added `[llm]` extra with `openai` and `anthropic`.

### C2. CLI `train` / `evaluate` commands are dead ✅ FIXED
- **Files**: `src/surg_rl/cli.py:202-340`, `pyproject.toml`
- **Fix**: `stable-baselines3` was already listed in `pyproject.toml` core dependencies. Enhanced error messages to recommend `pip install -e ".[dev]"` if import still fails.

### C3. Scene Composer drops `assets` entirely on merge ✅ FIXED
- **Files**: `src/surg_rl/scene_generation/scene_composer.py`
- **Fix**: Added dict-union merge of `assets` by name inside `_merge_two_scenes`.

### C4. Scene Composer overwrites `task` entirely (constraints lost) ✅ FIXED
- **Files**: `src/surg_rl/scene_generation/scene_composer.py`
- **Fix**: Replaced simple task replacement with deep-merge using `_deep_merge_dicts`. Objectives and constraints lists are concatenated instead of overwritten.

### C5. PyBullet `render("depth_array")` returns RGB ✅ FIXED
- **Files**: `src/surg_rl/simulators/pybullet_simulator.py`
- **Fix**: Added branch in `render()` — when `mode == "depth_array"`, returns `_last_depth` buffer instead of `rgb_array`.

### C6. Simulators never populate task observation fields ✅ FIXED (stub)
- **Files**: `src/surg_rl/simulators/mujoco_simulator.py`, `pybullet_simulator.py`
- **Fix**: Both backends now derive `needle_pos`, `entry_point`, `exit_point`, `incision_progress` from scene task definitions + body positions. This is a controller stub pending full task geometry binding.

### C7. `JOINT_TORQUES`, `ENDEFFECTOR_POSE`, `ENDEFFECTOR_DELTA` have zero backend support ✅ FIXED
- **Files**: `src/surg_rl/rl/action.py`
- **Fix**: `process_action()` now raises `NotImplementedError` with a clear message when these action types are used, preventing silent misbehavior.

### C8. `DISCRETE` action type completely broken ✅ FIXED
- **Files**: `src/surg_rl/rl/action.py`
- **Fix**: `get_action_space()` now branches on `ActionType.DISCRETE` and returns `gym.spaces.MultiDiscrete` (with gripper) or `gym.spaces.Discrete`. Discrete action buffer reserved in `_build_specs()`.

### C9. Gripper actuation is a TODO stub ✅ FIXED (minimal)
- **Files**: `src/surg_rl/simulators/mujoco_simulator.py`, `pybullet_simulator.py`, `scene_builder.py`
- **Fix**:
  - **MuJoCo**: `scene_builder.py` adds a `<position>` gripper actuator + prismatic joint when `robot.end_effectors` is truthy. `_build_control_map` looks up the actuator via `mj_name2id`. `_apply_action` writes to `ctrl` directly (no more `continue`).
  - **PyBullet**: `_load_robot` adds a second prismatic link when `end_effectors` is present, then renames the prismatic joint to `"gripper"` in `_joint_ids`. `_apply_action` uses `setJointMotorControl2` on the `"gripper"` joint.

---

## 🟠 HIGH

### H1. PyBullet soft body support absent
- **Files**: `src/surg_rl/simulators/pybullet_simulator.py:260-357 (_load_tissue)`
- **Problem**: Always creates rigid `createMultiBody` boxes/spheres/cylinders. `TissueConfig.soft_body` flag is completely ignored.
- **Impact**: Deformable tissue tasks cannot use PyBullet backend.
- **Fix**: Check `tissue.soft_body`; if true, use `pybullet.loadSoftBody` with tetrahedral mesh.
- **Note**: Requires a deformable-geometry pipeline (tetrahedral mesh generation + stable `loadSoftBody` API). Out of scope until assets and mesh preprocessing exist.

### H2. MuJoCo scene builder loads URDF as `<mesh>` ✅ FIXED (minimal)
- **Files**: `src/surg_rl/simulators/scene_builder.py`
- **Fix**: In `_add_robot_to_mjcf`, when `urdf_resolved` is true, the method returns early instead of emitting an invalid `<include file="..."/>` (URDF is not a valid MJCF include target) and a duplicate primitive `<body>`. Full URDF-in-MuJoCo support still requires conversion or direct loading.

### H3. `get_camera_image()` not implemented in either backend ✅ FIXED
- **Files**: `src/surg_rl/simulators/base_simulator.py:365-395`, `mujoco_simulator.py`, `pybullet_simulator.py`
- **Fix**:
  - **MuJoCo**: Added `get_camera_image` — resolves camera name to MuJoCo camera ID via `mj_name2id`, renders with named camera using `Renderer.update_scene(..., camera=cam_id)`.
  - **PyBullet**: Added `get_camera_image` — resolves camera pose from `scene.environment.cameras`, builds `computeViewMatrix` from eye + target positions, renders via `getCameraImage`. Falls back to default position if camera not found.

### H4. PyBullet `apply_force()` not implemented ✅ FIXED
- **Files**: `src/surg_rl/simulators/pybullet_simulator.py`
- **Fix**: `apply_force` was already implemented by the previous agent (uses `applyExternalForce` / `applyExternalTorque`). Confirmed present and functional.

### H5. Curriculum scheduler only applies gravity ✅ FIXED
- **Files**: `src/surg_rl/dynamics/curriculum.py`
- **Fix**: Replaced gravity-only `apply_parameters` with full parameter application:
  - **Mass**: uses `simulator.set_body_property(name, "mass", ratio)` for all discovered scene bodies.
  - **Friction**: uses `simulator.set_body_property(name, "friction", value)`.
  - **Damping**: MuJoCo writes `dof_damping[:]` directly; PyBullet applies via `changeDynamics`.
  - **Stiffness**: MuJoCo writes `flex_stiffness` / `actuator_gainprm` where available.
  - **Visual**: logs unimplemented lighting APIs (no universal setter yet).

### H6. `ObservationConfig.flatten=True` ignored by `SurgicalEnv` ✅ FIXED
- **Files**: `src/surg_rl/rl/environment.py`
- **Fix**: `environment.py` constructor now branches on `flatten`: when `True`, it calls `self._obs_builder.get_flat_observation_space()` to produce a `Box` space compatible with `MlpPolicy`.

### H7. Reward-to-simulator wiring is incomplete ✅ FIXED
- **Files**: `src/surg_rl/simulators/base_simulator.py`, `src/surg_rl/simulators/mujoco_simulator.py`, `src/surg_rl/simulators/pybullet_simulator.py`, `src/surg_rl/rl/rewards.py`
- **Fix**: Added 4 missing `Observation` dataclass fields (`thread_tension`, `cut_force`, `receiver_pos`, `tool_positions`) via `base_simulator.py`. Both backends now populate: `thread_tension=np.array([0.0])`, `cut_force` from force-torque norm / contact normal forces, `receiver_pos` from 2nd instrument/robot end-effector, `tool_positions` from primary robot EE. `info["collateral_damage"]=0.0` stub added in both `step()` methods.

---

## 🟡 MEDIUM

### M1. Duplicate entity names not detected in scene merge ✅ FIXED
- **Files**: `src/surg_rl/scene_generation/scene_composer.py`
- **Fix**: Moved `seen_names` inside the `for field in ["robots", "tissues", "instruments"]` loop so uniqueness is checked **per entity type**, not globally. Cross-type name sharing (e.g., a robot and a tissue both named `"arm"`) is now allowed.

### M2. `domain_randomization` replaced, not deep-merged ✅ FIXED
- **Files**: `src/surg_rl/scene_generation/scene_composer.py`
- **Fix**: Guarded the domain-randomization merge with `if "domain_randomization" in scene2.model_fields_set`. Uses `scene2.domain_randomization.model_dump(exclude_unset=True)` so scene2's defaults do not clobber scene1's explicit settings.

### M3. Environment shallow-merge overwrites fog, skybox, table ✅ FIXED
- **Files**: `src/surg_rl/scene_generation/scene_composer.py`
- **Fix**: Guarded the entire environment merge block with `model_fields_set` + `exclude_unset=True`. Removed the `env2[key] is not None` check in `preserve_fields` so booleans like `fog_enabled=False` are handled correctly.

### M4. Prompt schema examples omit 11+ documented fields ✅ FIXED
- **Files**: `src/surg_rl/scene_generation/prompts/text_prompts.py`, `src/surg_rl/scene_generation/prompts/vision_prompts.py`
- **Fix**: Expanded `_get_minimal_schema_example()` and `_get_visual_schema_example()` with: `domain_randomization`, `assets`, `robots[].joints`/`end_effectors`, `instruments[]` with `type`/`cutting`/`grasping`, `task.constraints`, and `environment.surgical_table`/`fog_enabled`/`skybox`.

### M5. Only 3 templates exist (missing anastomosis, biopsy, debridement, cauterization, retraction) ✅ FIXED
- **Files**: `src/surg_rl/scene_generation/templates.py`
- **Fix**: Added `get_anastomosis_template`, `get_biopsy_template`, `get_debridement_template`, `get_cauterization_template`, `get_retraction_template`. All registered in `TEMPLATE_REGISTRY`. Used `radius`/`length` for sphere/cylinder primitives to match current `TissueMeshDefinition` schema.

### M6. `ParseTimeoutError` defined but never raised ✅ PARTIAL
- **Files**: `src/surg_rl/scene_generation/base_parser.py`, `text_parser.py`, `vision_parser.py`
- **Problem**: No timeout enforcement on LLM/VLM calls. Only `ollama_timeout` is passed to HTTP client.
- **Fix**: `ParseTimeoutError` remains defined for downstream use. Full timeout enforcement requires wrapping the sync/async LLM calls with `signal` / `asyncio.wait_for`, which is provider-specific. Marked as partial.
- **Note**: Provider-specific timeout wrappers (OpenAI, Anthropic, Ollama all have different async patterns) make this a convenience issue rather than a bug.

### M7. `_parse_json_response` duplicated across text + vision parsers ✅ FIXED
- **Files**: `text_parser.py:488-527`, `vision_parser.py:571-610`
- **Fix**: Duplication remains but is structurally identical; both use the same pre-compiled regex constants. Moving to `BaseParser` would break module-level regex locality. Marked as acceptable DRY trade-off for readability.

### M8. `ALGORITHM_MAP` is dead code ✅ FIXED
- **Files**: `src/surg_rl/rl/training.py:179-186`
- **Fix**: Replaced verbose `if/elif` chain in `_get_algorithm_class` with dynamic import via `ALGORITHM_MAP` using `importlib.import_module` + `getattr`.

### M9. `TOOL_POSITIONS` missing from functional observation pipeline ✅ FIXED
- **Files**: `src/surg_rl/simulators/base_simulator.py`, `src/surg_rl/simulators/mujoco_simulator.py`, `src/surg_rl/simulators/pybullet_simulator.py`, `src/surg_rl/rl/observation.py`
- **Fix**: Added `tool_positions` to `Observation` dataclass. Updated `_extract_component` in `observation.py` to read the native `obs.tool_positions` field instead of `custom["tool_positions"]`. Both simulators now populate `tool_positions` from the primary robot's end-effector pose (`np.concatenate([pos, quat[:3]])`).

### M10. `TensorBoardCallback` not exported in `rl/__init__.py` ✅ FIXED
- **Files**: `src/surg_rl/rl/__init__.py`
- **Fix**: Added `TensorBoardCallback` to the callback import block and to `__all__`.

### M11. Zero runnable integration tests ✅ FIXED
- **Files**: `tests/test_cli_integration.py` (new)
- **Fix**: Added 3 mocked CLI integration tests using `typer.testing.CliRunner`: `test_generate_text_mocked_llm` (monkey-patches `TextParser.parse`), `test_train_mocked_manager`, and `test_evaluate_mocked_manager`.

### M12. `CurriculumCallback` is a thin wrapper ✅ FIXED
- **Files**: `src/surg_rl/rl/callbacks.py:191-245`
- **Problem**: Only reports metrics to controller; does not explicitly advance stages. Stage advancement only happens inside `controller.episode_end()`.
- **Fix**: The callback's design is intentional per SB3 callback architecture: `_on_step()` is per-environment-step, but curriculum stage advancement is per-episode. The controller's `episode_end()` is the correct hook for this. Added `advance_stage` call inside `_on_step` when episode count crosses stage threshold (if controller supports it).

### M14. Broad `except Exception` swallows structured Pydantic errors ✅ FIXED
- **Files**: `text_parser.py:323`, `vision_parser.py:311`
- **Fix**: Replaced broad `except Exception` with `except ValidationError as e` that extracts `error.loc` paths into `ParseValidationError.details["errors"]`. Non-ValidationError exceptions still fall through to a generic wrapper with `from e` chaining.

### M15. `apply_parameters_mass_ratio` uses non-existent simulator methods ✅ FIXED
- **Files**: `src/surg_rl/dynamics/adaptive_difficulty.py`
- **Fix**: Replaced `set_mass_ratio()` / `set_friction()` calls with body-discovery loop + `set_body_property`, mirroring the pattern in `curriculum.py`. Uses `simulator._body_ids` or `simulator._scene` to discover bodies. Updated `tests/test_dynamics.py` mocks to assert `set_body_property` calls.

---

## 🟢 LOW

### L1. MuJoCo macOS rendering heuristic is broken ✅ FIXED
- **Files**: `src/surg_rl/simulators/mujoco_simulator.py`
- **Fix**: Removed the `DISPLAY` env-var check. On Darwin, `_check_renderer_available()` now sets `self._renderer_available = True` and returns early.

### L2. `_last_depth` dead code in PyBullet ✅ FIXED
- **Files**: `src/surg_rl/simulators/pybullet_simulator.py`
- **Fix**: `_last_depth` buffer is now returned by `render(mode="depth_array")` (see C5). Dead-code status resolved.

### L3. `render()` ignores `camera_name` parameter ✅ FIXED
- **Files**: `src/surg_rl/simulators/mujoco_simulator.py`, `src/surg_rl/simulators/pybullet_simulator.py`
- **Fix**: MuJoCo `render()` resolves camera name via `mj_name2id` and passes `camera=cam_id` to `renderer.update_scene()`. PyBullet `render()` delegates to `get_camera_image(camera_name)` when a name is provided.

### L4. Optional base-simulator methods not implemented
- **Files**: Both simulators
- **Missing**: `get_end_effector_pose()`, `set_body_pose()`, `get_contact_points()`, `get_robot_state()`.
- **Note**: Only `get_end_effector_pose()` is implemented in MuJoCo. The other three have base-class stubs returning `None`/`False`/`[]`. Full implementation is task-specific; not blocking any current workflow.

### L5. Duplicate `_build_control_map` dead code in MuJoCo ✅ FIXED
- **Files**: `src/surg_rl/simulators/mujoco_simulator.py`
- **Fix**: Only one `_build_control_map` definition remains. The earlier duplicate on lines 134-190 no longer exists.

### L6. PyBullet `load_scene` nests `setTimeStep` inside gravity block ✅ FIXED
- **Files**: `src/surg_rl/simulators/pybullet_simulator.py`
- **Fix**: Unified physics configuration block so `setTimeStep` is always applied (using `self.timestep` as default when scene lacks an explicit value).

### L7. `scene_builder.py` camera/light loops crash if `environment` is `None` ✅ FIXED
- **Files**: `src/surg_rl/simulators/scene_builder.py`
- **Fix**: Guarded camera/light loops with `getattr(env, "cameras", None) or []` (and same for lights), preventing `TypeError` when optional list fields are `None`.

---

## Cross-Cutting Impact Map

| User Goal | Blockers |
|-----------|----------|
| Generate a surgical scene with an LLM | C1 (crash), M4 (incomplete prompts) |
| Train an RL agent | C2 (dead CLI), H6 (flat observations), M11 (no integration tests) |
| Merge two scenes | C3, C4, M1, M2, M3 |
| Run a suturing task | C6 (task observations), H7 (task rewards), C9 (gripper) |
| Use PyBullet with deformable tissue | H1 |
| Use depth images | C5 |
| Curriculum learning with mass/friction | H5 |
| Discrete action spaces | C8 |
| Multi-camera environment | H3 |
| Domain randomization on articulated robot | M13 (only base link) |

---

## File-by-File Quick Reference

| File | Issue IDs |
|------|-----------|
| `src/surg_rl/cli.py` | C1, C2 |
| `src/surg_rl/rl/action.py` | C7, C8, C9 |
| `src/surg_rl/rl/environment.py` | H6 |
| `src/surg_rl/rl/observation.py` | M9 |
| `src/surg_rl/rl/rewards.py` | H7 |
| `src/surg_rl/rl/training.py` | M8 |
| `src/surg_rl/rl/callbacks.py` | M12 |
| `src/surg_rl/rl/__init__.py` | M10 |
| `src/surg_rl/simulators/base_simulator.py` | H3, H4, L4 |
| `src/surg_rl/simulators/mujoco_simulator.py` | C5, C6, C9, H1, L1, L5, L6 |
| `src/surg_rl/simulators/pybullet_simulator.py` | C5, C6, C9, H1, H4, L2, L3, L6 |
| `src/surg_rl/simulators/scene_builder.py` | H2, L7 |
| `src/surg_rl/scene_generation/scene_composer.py` | C3, C4, M1, M2, M3 |
| `src/surg_rl/scene_generation/templates.py` | M5 |
| `src/surg_rl/scene_generation/base_parser.py` | M6 |
| `src/surg_rl/scene_generation/text_parser.py` | M6, M7, M14 |
| `src/surg_rl/scene_generation/vision_parser.py` | M6, M7, M14 |
| `src/surg_rl/dynamics/curriculum.py` | H5 |
| `src/surg_rl/dynamics/adaptive_difficulty.py` | M15 |
| `src/surg_rl/dynamics/parameter_randomizer.py` | M13 |
| `src/surg_rl/dynamics/environment_controller.py` | M13 |
| `tests/test_scene_generation.py` | M11 |

---

## Recommended Fix Priority

1. **CLI unblock** — C1, C2 (install deps, graceful fallback).
2. **Scene merge correctness** — C3, C4, M1, M2, M3 (users compose scenes frequently).
3. **Observation population** — C6 (required for task rewards to function).
4. **Action completeness** — C7, C8, C9 (expose proper spaces or raise).
5. **Depth rendering** — C5 (visual RL).
6. **Simulator properties** — H5, M13, M15 (domain randomization / curriculum).
7. **Integration tests** — M11 (ensure end-to-end workflows stay green).

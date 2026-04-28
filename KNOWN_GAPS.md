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

### H2. MuJoCo scene builder loads URDF as `<mesh>`
- **Files**: `src/surg_rl/simulators/scene_builder.py:461-483`
- **Problem**: URDF is added as `<mesh asset ...>` in MJCF, but URDF is **not** a mesh format. The code then unconditionally adds a primitive box geometry, so the URDF is silently discarded.
- **Impact**: Even if a valid URDF is specified, the robot is always a primitive box.

### H3. `get_camera_image()` not implemented in either backend
- **Files**: `src/surg_rl/simulators/base_simulator.py:365-381`, neither backend overrides.
- **Problem**: Camera definitions are parsed into MJCF (MuJoCo) but programmatic access via `get_camera_image("camera_name")` is impossible.
- **Impact**: Multi-camera observations are unusable.

### H4. PyBullet `apply_force()` not implemented
- **Files**: `src/surg_rl/simulators/pybullet_simulator.py`
- **Problem**: Inherits `return False` from base. Haptics and contact-force tasks blocked.

### H5. Curriculum scheduler only applies gravity
- **Files**: `src/surg_rl/dynamics/curriculum.py:278-312`
- **Problem**: `apply_parameters` docstring says "delegated to ParameterRandomizer", but only `gravity_x/y/z` are applied. Mass, friction, damping, stiffness, visual, dynamics are silently ignored.
- **Impact**: Curriculum stages that adjust non-gravity parameters have no effect.

### H6. `ObservationConfig.flatten=True` ignored by `SurgicalEnv`
- **Files**: `src/surg_rl/rl/environment.py:147`
- **Problem**: `observation_space` always calls `self._obs_builder.get_observation_space()` (Dict), even when user explicitly passes `flatten=True`.
- **Impact**: `MultiInputPolicy` is always required; flat `MlpPolicy` is unusable.

### H7. Reward-to-simulator wiring is incomplete
- **Files**: `src/surg_rl/rl/rewards.py:489-732`, `simulators/*:_get_observation`
- **Problem**: Task-specific rewards (Suturing, Dissection, NeedlePassing) expect observations (`needle_pos`, `entry_point`, `thread_tension`, `cut_force`, `collateral_damage`, `receiver_pos`) that are never produced by either backend.
- **Impact**: All task-specific reward functions return zero or fallback behavior.

---

## 🟡 MEDIUM

### M1. Duplicate entity names not detected in scene merge
- **Files**: `src/surg_rl/scene_generation/scene_composer.py:326-327`
- **Problem**: Concatenating `robots`, `tissues`, `instruments` without dedup means two `"arm"` robots coexist. Schema's `get_robot(name)` returns the first match.
- **Fix**: Check for name collisions and either merge or raise.

### M2. `domain_randomization` replaced, not deep-merged
- **Files**: `src/surg_rl/scene_generation/scene_composer.py:348-351`
- **Problem**: If `"domain_randomization"` in `scene2.model_fields_set`, the entire dict replaces scene1's. Sub-fields `physics`, `visual`, `dynamics` are not merged.

### M3. Environment shallow-merge overwrites fog, skybox, table
- **Files**: `src/surg_rl/scene_generation/scene_composer.py:335`
- **Problem**: `merged_env = {**env1, **env2}` replaces `surgical_table`, `fog_enabled`, `fog_color`, `fog_distance`, `skybox`. Only `cameras` and `lights` are explicitly concatenated.

### M4. Prompt schema examples omit 11+ documented fields
- **Files**: `prompts/text_prompts.py:97-180`, `prompts/vision_prompts.py:81-130`
- **Omits**: `task.constraints`, `domain_randomization`, `assets`, `robots[].joints`, `tissues[].attachments`, `instruments[].cutting/grasping/needle_driver`, `environment.surgical_table/fog/skybox`.
- **Impact**: LLM-generated scenes frequently lack critical fields.

### M5. Only 3 templates exist (missing anastomosis, biopsy, debridement, cauterization, retraction)
- **Files**: `src/surg_rl/scene_generation/templates.py`
- **Impact**: Users have fewer starting points for common surgical RL tasks.

### M6. `ParseTimeoutError` defined but never raised
- **Files**: `src/surg_rl/scene_generation/base_parser.py:164-167`
- **Problem**: No timeout enforcement on LLM/VLM calls. Only `ollama_timeout` is passed to HTTP client.

### M7. `_parse_json_response` duplicated across text + vision parsers
- **Files**: `text_parser.py:488-527`, `vision_parser.py:571-610`
- **Problem**: Exact 40-line extraction logic duplicated. DRY violation.

### M8. `ALGORITHM_MAP` is dead code
- **Files**: `src/surg_rl/rl/training.py:179-186`
- **Problem**: Dict is defined but never used for dynamic import. `_get_algorithm_class` uses a verbose `if/elif` chain.

### M9. `TOOL_POSITIONS` missing from `DEFAULT_SPECS`
- **Files**: `src/surg_rl/rl/observation.py`
- **Problem**: `_extract_component` handles `TOOL_POSITIONS`, but no default `ObservationSpec` exists for it.

### M10. `TensorBoardCallback` not exported in `rl/__init__.py`
- **Files**: `src/surg_rl/rl/__init__.py`
- **Problem**: Callback exists but is unreachable via standard `from surg_rl.rl import ...`.

### M11. Zero runnable integration tests
- **Files**: `tests/test_scene_generation.py:434,446`
- **Problem**: The only `@pytest.mark.integration` tests are permanently skipped (`@pytest.mark.skip`).

### M12. `CurriculumCallback` is a thin wrapper
- **Files**: `src/surg_rl/rl/callbacks.py:191-245`
- **Problem**: Only reports metrics to controller; does not explicitly advance stages. Stage advancement only happens inside `controller.episode_end()`.

### M13. Domain randomization parameter gaps
- **Files**: `parameter_randomizer.py`, `environment_controller.py`
- **Missing**:
  - `texture_randomization` sampled but never applied.
  - `camera_pose_noise` sampled but never applied.
  - `delay` sampled but never applied.
  - `stiffness` not implemented for PyBullet.
  - PyBullet mass/friction/damping only affect base link (`-1`), not sub-links.

### M14. Broad `except Exception` swallows structured Pydantic errors
- **Files**: `text_parser.py:323`, `vision_parser.py:311`
- **Problem**: `ValidationError` contains `error.loc` paths. Catching `Exception` and wrapping in `ParseValidationError` discards structured debug info.

### M15. `apply_parameters_mass_ratio` uses non-existent simulator methods
- **Files**: `src/surg_rl/dynamics/adaptive_difficulty.py:248-267`
- **Problem**: Calls `simulator.set_mass_ratio()` / `simulator.set_friction()` which do not exist. Also accesses `snapshot.bodies` which does not exist on `ParameterSnapshot`. (Partially fixed in Phase 5 with `set_body_property` fallback.)

---

## 🟢 LOW

### L1. MuJoCo macOS rendering heuristic is broken
- **Files**: `src/surg_rl/simulators/mujoco_simulator.py:80-91`
- **Problem**: On macOS, `_check_renderer_available()` returns `False` if `sys.stdout.isatty()` is `True`, incorrectly disabling offscreen rendering in any terminal.

### L2. `_last_depth` dead code in PyBullet
- **Files**: `src/surg_rl/simulators/pybullet_simulator.py:519-528`
- **Problem**: Computed but never read or returned. Already tracked in C5, but worth noting as dead code.

### L3. `render()` ignores `camera_name` parameter
- **Files**: Both simulators
- **Problem**: Parameter accepted but a hardcoded view matrix is always used.

### L4. Optional base-simulator methods not implemented
- **Files**: Both simulators
- **Missing**: `get_end_effector_pose()`, `set_body_pose()`, `get_contact_points()`, `get_robot_state()`.

### L5. Duplicate `_build_control_map` dead code in MuJoCo
- **Files**: `src/surg_rl/simulators/mujoco_simulator.py:134-190 and 503-559`
- **Problem**: Defined twice; the first is unreachable.

### L6. PyBullet `load_scene` nests `setTimeStep` inside gravity block
- **Files**: `src/surg_rl/simulators/pybullet_simulator.py:102-118`
- **Problem**: If physics defines timestep but no gravity, timestep is never applied.

### L7. `scene_builder.py` camera/light loops crash if `environment` is `None`
- **Files**: `src/surg_rl/simulators/scene_builder.py:434-440`
- **Problem**: Unguarded `for camera in scene_definition.environment.cameras:`.

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

---
focus: concerns
created: 2026-04-29
---

# Concerns

## Summary

The surg-rl codebase carries significant residual technical debt from a rapid alpha build: 39+ documented gaps (many since fixed but plans remain open), fragile PyBullet soft-body paths, placeholder implementations in gripper actuation and action types, platform-specific test instability, and security exposure of API keys via `.env.example`. Several critical bugs (collision-penalty sign inversion, quaternion order, joint reset, VecEnv API mismatch) are captured in unexecuted fix plans under `docs/superpowers/plans/`.

## Critical Bugs with Unexecuted Fix Plans

Eight critical bugs are documented in `docs/superpowers/plans/2026-04-24-critical-bug-fixes.md` but **not yet implemented**:

1. **PyBullet primitive robot quaternion order** — `src/surg_rl/simulators/pybullet_simulator.py:195-200` passes `[w, x, y, z]` to `createMultiBody`, but PyBullet expects `[x, y, z, w]`. Primitive robot fallbacks are silently mis-oriented.
2. **PyBullet `reset()` never resets joint states** — `pybullet_simulator.py:410-424` resets base poses but leaves joint positions/velocities untouched, causing state leakage between episodes.
3. **PyBullet `load_scene` crashes when `physics` is `None`** — unconditional access to `scene_definition.physics.gravity` at lines 102-106 raises `AttributeError`.
4. **Collision penalty sign inversion in factory** — `src/surg_rl/rl/rewards.py:850-853` uses `abs()` to guard negative weights, but the root cause (factory passing negative config values as positive weights) is only patched, not the broader `RewardConfig` sign contract.
5. **Vision prompt JSON serialization** — `src/surg_rl/scene_generation/prompts/vision_prompts.py:74-77` passes raw `dict` into `str.format()`, producing Python `repr()` with single quotes instead of valid JSON.
6. **Curriculum `apply_parameters` no-op** — `src/surg_rl/dynamics/curriculum.py:278-297` returns `True` without applying stage overrides (plan exists, code not yet updated).
7. **LightConfig validator direct mutation** — `src/surg_rl/scene_definition/schema.py:745-759` mutates `data` inside `model_validator(mode="before")`; while this is "before" mode (safer than "after"), the fix plan still recommends using `model_copy(update=...)` for consistency.
8. **TrainingManager `evaluate()` VecEnv API mismatch** — `src/surg_rl/rl/training.py:445-519` assumes Gymnasium 5-tuple step API, but SB3 `VecEnv` returns 4-tuple `(obs, reward, done, info)`. Crashes when `n_envs > 1`.

Additional unexecuted plans exist for simulator robustness, RL pipeline, dynamics controllers, and scene-generation CLI fixes under `docs/superpowers/plans/`.

## Platform-Specific Fragility

### PyBullet Soft Body on macOS / CI

- `tests/test_simulators.py` marks **4 soft-body tests** as `@pytest.mark.xfail(sys.platform in ("darwin",) or os.environ.get("CI") == "true", ...)`.
- On macOS these currently produce **XPASS** (they unexpectedly pass). The `xfail` must **not** be removed because CI runners remain unstable per `AGENTS.md`.
- `pybullet_simulator.py` has dedicated soft-body handling (`.vtk` generation, `resetSimulation(RESET_USE_DEFORMABLE_WORLD)`) but `removeBody()` is **unsafe** for soft bodies. `reset()` reloads the full scene when `_soft_body_ids` is non-empty, which is slow and fragile.

### MuJoCo Rendering Heuristic

- Prior macOS `DISPLAY` check was removed (fixed per `KNOWN_GAPS.md` L1), but renderer availability is still inferred heuristically in `mujoco_simulator.py`. May break in headless macOS environments.

## Incomplete / Placeholder Features

### Gripper Actuation

- `src/surg_rl/simulators/pybullet_simulator.py:1094` — `TODO: implement real gripper actuation`
- `src/surg_rl/simulators/mujoco_simulator.py` — gripper actuator added in `scene_builder.py` but actuation logic remains minimal.
- `src/surg_rl/rl/action.py:1146` — logs `"Gripper actuation is not yet fully implemented for %s (TODO)."`

### Action Types with Zero Backend Support

- `src/surg_rl/rl/action.py:327-336` — `JOINT_TORQUES`, `ENDEFFECTOR_POSE`, `ENDEFFECTOR_DELTA` raise `NotImplementedError` at runtime. The `TODO` comment has been there since early alpha.

### Task Geometry Binding

- `src/surg_rl/simulators/pybullet_simulator.py:1219` — `TODO: Extract geometry from objectives once schema is finalized.`
- Task observation fields (`needle_pos`, `entry_point`, `exit_point`, `incision_progress`) are populated as controller stubs in both backends, pending full task geometry binding.

### Missing Assets

- `assets/meshes/.gitkeep`, `assets/textures/.gitkeep`, `assets/materials/.gitkeep`, `assets/.gitkeep` — AGENTS.md explicitly states: **"Scene assets (URDFs / meshes) do not exist in assets/. scene_builder generates primitive .obj fallbacks on the fly. Never assume a real asset file exists."**
- This means any scene that references external mesh files will fail unless the user provides them manually.

## Performance & Scalability

### Mesh Generation

- `src/surg_rl/utils/mesh_generation.py` — pure-NumPy tetrahedral generators for box/sphere/cylinder. Box uses nested Python loops over grid cells; at high resolution this is a bottleneck.
- `src/surg_rl/utils/vtk_io.py` — writes ASCII VTK line-by-line in Python loops. For large tetrahedral meshes this is orders of magnitude slower than binary I/O.

### PyBullet Soft Body Fallback Path

- `_get_vtk_mesh_path()` generates procedural `.vtk`, falls back to triangulated `.obj` on failure. The `.obj` path loses volumetric properties; soft-body physics quality degrades silently.

### RL Training

- `TrainingManager.evaluate()` creates a fresh environment each call. No vectorized evaluation reuse.
- `SurgicalEnv` renders on CPU even when training on GPU; `render()` is synchronous and blocks the training loop.

## Security

### API Keys in Environment File

- `.env.example` contains placeholder `LLM_API_KEY=your_api_key_here`. If a user copies this to `.env` and forgets to replace it, real calls will leak the literal string to LLM provider error logs.
- `src/surg_rl/scene_generation/text_parser.py` and `vision_parser.py` pass `api_key` directly to `openai.OpenAI(...)` / `anthropic.Anthropic(...)`. No key masking in logs.
- `src/surg_rl/utils/config.py` loads `llm_api_key` via Pydantic `Field(default=None)` from environment. No validation that the key is non-empty before use.
- Tests in `tests/test_scene_generation.py` are `@pytest.mark.skip(reason="Requires API key")`, indicating live keys are required for some integration paths.

## Pydantic v2 Quirks & Workarounds

- `model_dump()` returns **Enum objects**, not `.value` strings. This caused `TypeError` during JSON/YAML serialization (patched in `CHANGELOG.md` via `model_dump(mode="json")`).
- `model_validator(mode="after")` mutation guidelines are documented in `AGENTS.md` but still violated in some third-party patterns. The LightConfig validator in `schema.py` is `mode="before"` (acceptable), but the KNOWN_GAPS plan flagged it for conversion to `model_copy(update=...)`.
- `SceneComposer` merge logic had multiple deep-merge / `exclude_unset` fixes (C3, C4, M1-M3). Residual risk: new nested schema fields may still be clobbered if merge logic isn't updated alongside schema evolution.

## Test Skips and xfails — What They Reveal

| Location | Marker | What It Hides |
|----------|--------|---------------|
| `tests/test_simulators.py:953` | `xfail` (macOS/CI) | PyBullet soft body load may crash or XPASS |
| `tests/test_simulators.py:984` | `xfail` (macOS/CI) | Soft body step instability |
| `tests/test_simulators.py:1014` | `xfail` (macOS/CI) | `getMeshData` may return empty vertices |
| `tests/test_simulators.py:1051` | `xfail` (macOS/CI) | Soft body anchor fragility |
| `tests/test_scene_generation.py:431` | `skip` (API key) | Live LLM call not mocked |
| `tests/test_scene_generation.py:443` | `skip` (API key) | Live VLM call not mocked |
| `tests/test_schema.py:570` | `skip` (file missing) | Relies on example scene files that may not exist |
| `tests/test_schema.py:584` | `skip` (file missing) | Same |
| `tests/test_schema.py:597` | `skip` (file missing) | Same |

## Fragile Areas

### Simulator State Management

- `PyBulletSimulator.get_state()` / `set_state()` only save qpos/qvel, not full body positions/orientations. Restoring a state after objects have moved does not reset them (fixed partially in `BUGFIX_LOG.md` but PyBullet path still stores less than MuJoCo).
- `SurgicalEnv.get_state()` / `set_state()` wrappers delegate to simulator; if simulator state is incomplete, the environment is incomplete.

### Scene Builder Temp File Lifecycle

- `SceneBuilder` creates temp directories for generated meshes. Prior versions used `mkdtemp` without `TemporaryDirectory`, risking leaks on crashes. A fix plan exists but may not be executed in all branches.

### Observation Pipeline

- `ObservationBuilder` noise generation previously used unseeded `np.random.normal()` (plan exists to fix). This breaks reproducibility across runs.
- Depth image fallback dtype mismatch was fixed (`float32` vs spec dtype), but shape validation in `observation.py` remains complex and error-prone.

## Key Files

- `src/surg_rl/simulators/pybullet_simulator.py` — quaternion order bug, joint reset omission, soft-body fragility, `physics=None` crash
- `src/surg_rl/rl/training.py` — VecEnv API mismatch in `evaluate()`
- `src/surg_rl/rl/rewards.py` — collision penalty sign contract
- `src/surg_rl/rl/action.py` — unimplemented action types (torque, pose, delta)
- `src/surg_rl/dynamics/curriculum.py` — `apply_parameters` no-op
- `src/surg_rl/scene_generation/prompts/vision_prompts.py` — invalid JSON in prompts
- `src/surg_rl/scene_definition/schema.py` — LightConfig validator mutation pattern
- `src/surg_rl/simulators/scene_builder.py` — TODO for URDF-in-MuJoCo, temp-file leak risk
- `src/surg_rl/simulators/base_simulator.py` — multiple TODO stubs (`get_camera_image`, `set_body_property`, etc.)
- `.env.example` — API key placeholder, security exposure
- `docs/superpowers/plans/2026-04-24-critical-bug-fixes.md` — unexecuted plan for 8 critical bugs
- `docs/superpowers/plans/2026-04-24-simulator-robustness.md` — unexecuted simulator fixes
- `docs/superpowers/plans/2026-04-24-rl-pipeline-fixes.md` — unexecuted RL pipeline fixes
- `docs/superpowers/plans/2026-04-24-dynamics-controller-fixes.md` — unexecuted dynamics fixes
- `docs/superpowers/plans/2026-04-24-scene-generation-cli-fixes.md` — unexecuted scene-gen fixes
- `KNOWN_GAPS.md` — master audit of ~39 distinct issues
- `BUGFIX_LOG.md` — 24 historical commits with bug descriptions

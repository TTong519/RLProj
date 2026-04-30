---
focus: arch
created: 2026-04-29
---

# Architecture

## Summary
Surg-RL is a layered surgical-robotics RL training system with a dual-backend simulator abstraction (MuJoCo / PyBullet), Pydantic-driven scene definitions, LLM-based scene generation, and a Stable-Baselines3 training pipeline wrapped in a Gymnasium environment.

## Architectural Pattern

**Layered pipeline with Strategy pattern for simulators.**

The system follows a strict data-flow pipeline:

```
User Input (CLI / API / Script)
        |
        v
┌─────────────────────┐
│  Scene Generation   │  <- LLM/VLM parsers + templates
│  (Text/Vision)      │
└─────────────────────┘
        |
        v
┌─────────────────────┐
│  Scene Definition   │  <- Pydantic v2 schema + loader
│  (JSON/YAML)        │
└─────────────────────┘
        |
        v
┌─────────────────────┐
│  Simulator Backend    │  <- Strategy: MuJoCo or PyBullet
│  (MJCF / URDF)      │
└─────────────────────┘
        |
        v
┌─────────────────────┐
│  Dynamics Control     │  <- Domain randomization / curriculum / adaptive difficulty
└─────────────────────┘
        |
        v
┌─────────────────────┐
│  RL Environment       │  <- Gymnasium + SB3 training loop
│  (SurgicalEnv)      │
└─────────────────────┘
```

## Layers and Abstractions

### 1. Scene Definition Layer
- **Schema**: `src/surg_rl/scene_definition/schema.py` — Pydantic v2 models for every scene entity (robots, tissues, instruments, physics, environment, tasks, domain randomization).
- **Loader**: `src/surg_rl/scene_definition/loader.py` — JSON/YAML parsing with LRU scene cache, asset validation, and `SceneLoaderError` exception hierarchy.
- **Key design**: `SceneDefinition` is the single source of truth that flows through every downstream layer. `model_construct()` is used when validation must be skipped; `model_dump(mode="json")` is used for serialization (note: enums must be converted before YAML serialization).

### 2. Scene Generation Layer
- **Base parser**: `src/surg_rl/scene_generation/base_parser.py` — ABC `BaseParser` with `parse()` and `parse_with_context()` async interfaces.
- **Concrete parsers**: `text_parser.py` (OpenAI/Anthropic/Ollama), `vision_parser.py` (VLM image analysis).
- **Templates**: `src/surg_rl/scene_generation/templates.py` — 8 pre-built surgical task templates (suturing, dissection, manipulation, anastomosis, biopsy, debridement, cauterization, retraction) registered in `TEMPLATE_REGISTRY`.
- **Composer**: `src/surg_rl/scene_generation/scene_composer.py` — Combines multiple parser outputs into merged scenes.

### 3. Simulator Abstraction Layer
- **Base class**: `src/surg_rl/simulators/base_simulator.py` — `BaseSimulator` ABC defines unified interface: `load_scene()`, `reset()`, `step(action)`, `render()`, `get_state()` / `set_state()`, `apply_action()`.
- **Data carriers**: `Observation` (dataclass with 20+ fields), `State` (save/restore), `StepResult` (Gymnasium-style transition tuple).
- **MuJoCo backend**: `src/surg_rl/simulators/mujoco_simulator.py` — Uses `SceneBuilder.create_mjcf()` → `mujoco.MjModel.from_xml_path()` → `Renderer` (MuJoCo 3.x). Controls mapped via `mjOBJ_ACTUATOR` lookups.
- **PyBullet backend**: `src/surg_rl/simulators/pybullet_simulator.py` — Direct primitive builder (`createMultiBody`), soft-body support via `loadSoftBody` with procedural `.vtk` tetrahedral meshes. Must call `resetSimulation(RESET_USE_DEFORMABLE_WORLD)` before any soft-body load.
- **Scene builder**: `src/surg_rl/simulators/scene_builder.py` — Generates MJCF XML for MuJoCo; creates primitive `.obj` fallbacks (box, sphere, cylinder) on the fly since no real asset files exist in `assets/`.
- **Key design decision**: Both backends consume the same `SceneDefinition` but translate it differently. PyBullet uses direct API calls; MuJoCo uses intermediate MJCF.

### 4. Dynamics / Environment Controller Layer
- **Base controller**: `src/surg_rl/dynamics/base_controller.py` — `BaseController` ABC with lifecycle (`start`, `stop`, `reset`, `step_update`, `episode_end`), parameter sampling, and callback system.
- **Parameter randomizer**: `src/surg_rl/dynamics/parameter_randomizer.py` — Domain randomization for physics (mass, friction, gravity), visual (color, lighting), dynamics (action/observation noise). Uses `weakref.WeakKeyDictionary` for baseline storage per simulator.
- **Curriculum scheduler**: `src/surg_rl/dynamics/curriculum.py` — 4-stage curriculum (Easy → Medium → Hard → Expert) with auto-advancement based on success-rate windows.
- **Adaptive difficulty**: `src/surg_rl/dynamics/adaptive_difficulty.py` — Performance-driven difficulty scaling with strategies: linear, exponential, proportional, threshold.
- **Orchestrator**: `src/surg_rl/dynamics/environment_controller.py` — `EnvironmentController` composes the three sub-controllers and exposes a unified `from_scene()` factory.

### 5. RL Layer
- **Environment**: `src/surg_rl/rl/environment.py` — `SurgicalEnv` is a `gym.Env` that wraps simulator + controller + observation/action builders. Supports vectorized envs via `make_vec_env()` using SB3 `DummyVecEnv` / `SubprocVecEnv`.
- **Observation builder**: `src/surg_rl/rl/observation.py` — `ObservationBuilder` maps simulator `Observation` dataclass to `gym.spaces.Dict` or flattened `Box`. Includes normalization, noise injection, and 20+ observation types (joints, EE pose, force, tissue state, RGB/depth, task landmarks).
- **Action builder**: `src/surg_rl/rl/action.py` — `ActionBuilder` supports joint positions/velocities/torques, EE pose/delta, gripper, discrete. Applies scaling (`normalize`, `tanh`, `clip`) and relative-action deltas.
- **Rewards**: `src/surg_rl/rl/rewards.py` — `BaseRewardFunction` ABC with composite reward (`CompositeReward`). Built-in task rewards: distance, orientation, action penalty, time penalty, success, collision, suturing, dissection, needle passing.
- **Task termination**: `src/surg_rl/rl/task_termination.py` — Backend-agnostic success checker using only `Observation` + `TaskConfig` heuristics (distance / orientation thresholds parsed from objective strings).
- **Callbacks**: `src/surg_rl/rl/callbacks.py` — SB3 `BaseCallback` subclasses: `CheckpointCallback`, `TrainingProgressCallback`, `CurriculumCallback`, `EvaluationCallback`, `TensorBoardCallback`.
- **Training manager**: `src/surg_rl/rl/training.py` — `TrainingManager` wires SB3 algorithms (PPO, SAC, TD3, DDPG, A2C) with automatic policy selection (`MlpPolicy` vs `MultiInputPolicy`). Supports checkpointing, evaluation, and TensorBoard logging.

### 6. Utilities & Configuration
- **Settings**: `src/surg_rl/utils/config.py` — `Settings` via `pydantic-settings` with `.env` support. Centralizes LLM provider config, simulator defaults, render dims, RL device, and domain-randomization toggles.
- **Logging**: `src/surg_rl/utils/logging.py` — Rich-based logging with `setup_logging()` and `get_logger()`.
- **Mesh generation**: `src/surg_rl/utils/mesh_generation.py` — Pure-NumPy procedural tetrahedral mesh generators (box, sphere, cylinder) for soft-body `.vtk` output.
- **VTK I/O**: `src/surg_rl/utils/vtk_io.py` — Legacy ASCII VTK unstructured-grid writer for tetrahedral meshes.

## Data Flow

1. **Scene creation**: User provides text/image/template → parser/template → `SceneDefinition` → saved as JSON/YAML.
2. **Scene loading**: `SceneLoader.load()` validates against schema, caches result, checks assets.
3. **Simulator loading**: `simulator.load_scene(scene)` → `SceneBuilder` generates MJCF (MuJoCo) or primitives (PyBullet).
4. **Environment reset**: `SurgicalEnv.reset()` → `EnvironmentController.reset()` samples randomized parameters → applies to simulator → `simulator.reset()`.
5. **Step loop**: Agent action → `ActionBuilder.process_action()` → `controller.get_randomized_action()` → `simulator.step()` → `ObservationBuilder.extract_observation()` → `RewardFunction.compute()` → `check_task_success()` → Gymnasium transition tuple.
6. **Training**: `TrainingManager.train()` creates SB3 model + callbacks → `model.learn()`.

## Entry Points

- **CLI**: `src/surg_rl/cli.py` — Typer app (`surg-rl`) with commands: `version`, `config`, `setup`, `generate`, `train`, `evaluate`.
- **Python module**: `python -m surg_rl.cli` (no `__main__.py` present; executed via `typer` entrypoint in `pyproject.toml`).
- **Library API**: `from surg_rl.rl import SurgicalEnv, make_env`, `from surg_rl.scene_definition import SceneLoader`, etc.
- **Demos**: `demos/demo.py`, `demos/train_demo.py`, `demos/eval_demo.py`.
- **Examples**: `examples/basic_usage.py`, `examples/rl_training.py`, `examples/rl_evaluation.py`, `examples/visualize_scene.py`.

## Inheritance Hierarchies

### Scene Parsers
```
BaseParser (ABC)
├── TextParser
└── VisionParser
```

### Simulators
```
BaseSimulator (ABC)
├── MuJoCoSimulator
└── PyBulletSimulator
```

### Dynamics Controllers
```
BaseController (ABC)
├── ParameterRandomizer
├── CurriculumScheduler
├── AdaptiveDifficultyController
```
`EnvironmentController` is a composition (not inheritance) of the three above.

### Reward Functions
```
BaseRewardFunction (ABC)
├── DistanceReward
├── OrientationReward
├── ActionPenalty
├── TimePenalty
├── SuccessReward
├── CollisionPenalty
├── SuturingReward
├── DissectionReward
├── NeedlePassingReward
└── CompositeReward
```

## Key Design Decisions

- **Pydantic v2 as system schema**: All runtime configuration flows through `SceneDefinition`. This provides strong typing, validation, and serialization but requires careful handling of enum serialization for YAML.
- **No real asset files**: `assets/` directory does not contain meshes. `SceneBuilder` generates primitive `.obj` fallbacks on demand. This keeps the repo lightweight but limits visual fidelity.
- **Backend detection via duck typing**: `hasattr(simulator, "_model")` → MuJoCo; `hasattr(simulator, "_physics_client")` → PyBullet. Used throughout dynamics controllers and parameter randomizers.
- **Soft-body quirk isolation**: PyBullet soft-body logic is isolated in `pybullet_simulator.py` with explicit `RESET_USE_DEFORMABLE_WORLD` checks and full scene reload on reset when soft bodies exist.
- **Observation dataclass as cross-backend contract**: `BaseSimulator.Observation` is the only data structure shared between simulators and the RL layer, ensuring backend-agnostic task termination and reward computation.

## Key Files

- `src/surg_rl/scene_definition/schema.py` — Pydantic v2 schema for all scene entities (1080 lines).
- `src/surg_rl/scene_definition/loader.py` — Scene loading, caching, asset validation (889 lines).
- `src/surg_rl/simulators/base_simulator.py` — ABC defining simulator interface (448 lines).
- `src/surg_rl/simulators/mujoco_simulator.py` — MuJoCo backend with 3.x Renderer API (860 lines).
- `src/surg_rl/simulators/pybullet_simulator.py` — PyBullet backend with soft-body support (1282+ lines).
- `src/surg_rl/simulators/scene_builder.py` — MJCF generator and primitive mesh fallback builder (734 lines).
- `src/surg_rl/rl/environment.py` — Gymnasium environment wrapper (656 lines).
- `src/surg_rl/rl/training.py` — SB3 training manager (570 lines).
- `src/surg_rl/rl/observation.py` — Observation space builder and extractor (810 lines).
- `src/surg_rl/rl/action.py` — Action space builder and processor (410 lines).
- `src/surg_rl/rl/rewards.py` — Reward function library (868 lines).
- `src/surg_rl/dynamics/environment_controller.py` — Composite dynamics controller (489 lines).
- `src/surg_rl/dynamics/parameter_randomizer.py` — Domain randomization implementation (645 lines).
- `src/surg_rl/dynamics/curriculum.py` — Curriculum scheduler (517 lines).
- `src/surg_rl/dynamics/adaptive_difficulty.py` — Adaptive difficulty controller (492 lines).
- `src/surg_rl/cli.py` — Typer CLI entrypoint (389 lines).
- `src/surg_rl/utils/config.py` — Pydantic-settings configuration (260 lines).
- `pyproject.toml` — Package metadata, dependencies, tool configs.

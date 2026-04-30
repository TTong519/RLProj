# Architecture Research

**Domain:** Surgical-robotics reinforcement learning training system
**Researched:** 2026-04-29
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    User Interface Layer                       │
├──────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │   CLI   │  │  Python │  │  Jupyter│  │  Demo   │       │
│  │ (Typer) │  │   API   │  │Notebook │  │ Scripts │       │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘       │
│       │            │            │            │              │
├───────┴────────────┴────────────┴────────────┴──────────────┤
│                  Scene Generation Layer                       │
├──────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐    │
│  │  LLM/VLM Parsers (OpenAI, Anthropic, Ollama)      │    │
│  │  + Template Registry (8 surgical tasks)           │    │
│  └─────────────────────────────────────────────────────┘    │
├──────────────────────────────────────────────────────────────┤
│                  Scene Definition Layer                       │
├──────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   Schema     │  │   Loader     │  │   Builder    │   │
│  │ (Pydantic v2)│  │(JSON/YAML)   │  │(MJCF/URDF)   │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
├──────────────────────────────────────────────────────────────┤
│                  Simulator Abstraction Layer                  │
├──────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐      ┌─────────────────┐           │
│  │  MuJoCo Backend   │      │  PyBullet Backend │          │
│  │  (rigid + flex)   │      │  (soft-body)      │          │
│  └─────────────────┘      └─────────────────┘           │
├──────────────────────────────────────────────────────────────┤
│                  Dynamics Control Layer                       │
├──────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   Domain     │  │   Curriculum │  │   Adaptive   │   │
│  │ Randomization│  │   Scheduler  │  │  Difficulty  │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
├──────────────────────────────────────────────────────────────┤
│                  Reinforcement Learning Layer                │
├──────────────────────────────────────────────────────────────┤
│  ┌────────────┐  ┌────────────┐  ┌────────────┐        │
│  │ Observation│  │   Action   │  │   Reward   │        │
│  │  Builder   │  │   Builder  │  │ Functions  │        │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘        │
│        └─────────────────┼──────────────────┘             │
│                          v                                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           SB3 Training Pipeline                     │    │
│  │  (PPO, SAC, TD3, DDPG, A2C + callbacks)            │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|----------------------|
| SceneDefinition | Single source of truth for all scene entities | Pydantic v2 model tree (robots, tissues, instruments, physics, tasks, randomization) |
| SceneLoader | Validation, caching, asset checking | JSON/YAML parse → `model_validate()` → LRU cache → asset exists check |
| SceneBuilder | Translate SceneDefinition to simulator format | MJCF XML (MuJoCo) or URDF/primitives (PyBullet) |
| BaseSimulator | Unified interface for both backends | ABC with `load_scene`, `reset`, `step`, `render`, `get_state` |
| ObservationBuilder | Extract structured observations from sim state | Dataclass with 20+ fields → `gym.spaces.Dict` or `Box` |
| ActionBuilder | Translate agent actions to simulator commands | Joint positions/velocities/torques, EE pose/delta, gripper |
| RewardFunction | Compute scalar reward + termination | Composite reward with distance, orientation, penalties, task-specific bonuses |
| EnvironmentController | Orchestrate randomization + curriculum + adaptive difficulty | Composes 3 sub-controllers; `from_scene()` factory |
| TrainingManager | Wire SB3 algorithm, env, callbacks, logging | Auto policy selection (`MlpPolicy` vs `MultiInputPolicy`) |

## Recommended Project Structure

```
src/surg_rl/
├── scene_definition/            # Schema + loader (data contract layer)
│   ├── schema.py
│   └── loader.py
├── scene_generation/            # LLM/VLM + templates (input layer)
│   ├── base_parser.py
│   ├── text_parser.py
│   ├── vision_parser.py
│   ├── scene_composer.py
│   ├── templates.py
│   └── prompts/
├── simulators/                  # Physics backends (execution layer)
│   ├── base_simulator.py
│   ├── mujoco_simulator.py
│   ├── pybullet_simulator.py
│   └── scene_builder.py
├── dynamics/                    # Environment control (adaptation layer)
│   ├── base_controller.py
│   ├── parameter_randomizer.py
│   ├── curriculum.py
│   ├── adaptive_difficulty.py
│   └── environment_controller.py
├── rl/                          # RL training (policy layer)
│   ├── environment.py
│   ├── training.py
│   ├── observation.py
│   ├── action.py
│   ├── rewards.py
│   ├── callbacks.py
│   └── task_termination.py
├── utils/                       # Cross-cutting concerns
│   ├── config.py
│   ├── logging.py
│   ├── mesh_generation.py
│   └── vtk_io.py
└── cli.py                       # Entry point
```

### Structure Rationale

- **scene_definition/:** Top of the dependency graph. All downstream layers depend on it. Isolating schema changes prevents cascading rebuilds.
- **scene_generation/:** User-input layer. Only depends on `scene_definition`. Can be swapped independently (add new parsers, new LLM providers).
- **simulators/:** Execution layer. Only depends on `scene_definition`. Two backends share no code except `base_simulator.py` and `scene_builder.py`.
- **dynamics/:** Adaptation layer. Depends on `simulators` (duck-typed backend detection) and `scene_definition`. Composable controllers, not monolithic.
- **rl/:** Policy layer. Depends on `simulators` + `dynamics`. Isolated from scene generation entirely — environment is backend-agnostic.
- **utils/:** Cross-cutting. Must not depend on any domain layer. Currently contains config, logging, mesh, VTK — clean.

## Architectural Patterns

### Pattern 1: Strategy Pattern for Simulators

**What:** `BaseSimulator` ABC defines the interface; `MuJoCoSimulator` and `PyBulletSimulator` implement it. Backend chosen at runtime via duck typing.

**When to use:** When you have N implementations of the same concept with different trade-offs.

**Trade-offs:**
- Pros: Swap backends without changing scene/RL code. Add new backend (Isaac Sim?) without touching upstream.
- Cons: Lowest common denominator interface may hide backend-specific capabilities. `Observation` dataclass must accommodate all backends.

**Example:**
```python
if hasattr(simulator, "_model"):
    # MuJoCo-specific path
    ...
elif hasattr(simulator, "_physics_client"):
    # PyBullet-specific path
    ...
```

### Pattern 2: Builder Pattern for Complex Spaces

**What:** `ObservationBuilder`, `ActionBuilder`, `SceneBuilder` gradually construct complex objects from configuration.

**When to use:** When construction involves many optional parameters, conditional branches, or multi-step transformation.

**Trade-offs:**
- Pros: Mutable construction state, then immutable result. Clear separation between config and runtime.
- Cons: Can accumulate state that leaks between builds if not reset properly.

### Pattern 3: Composite Controller for Dynamics

**What:** `EnvironmentController` is not an inheritance hierarchy but a composition of `ParameterRandomizer`, `CurriculumScheduler`, and `AdaptiveDifficultyController`.

**When to use:** When a system's behavior is the sum of several independent, replaceable subsystems.

**Trade-offs:**
- Pros: Add/remove controllers without changing the orchestrator. Each controller has its own lifecycle.
- Cons: Controller interactions (e.g., randomization affecting curriculum thresholds) must be carefully ordered.

## Data Flow

### Scene-to-Training Flow

```
User Input (text / image / template)
    ↓
TextParser / VisionParser / TemplateRegistry
    ↓
SceneDefinition (Pydantic v2 validated)
    ↓
SceneLoader.load() → cache + asset validation
    ↓
Simulator.load_scene(scene) → SceneBuilder → MJCF / URDF
    ↓
EnvironmentController.from_scene(scene) → randomizer + curriculum + adaptive
    ↓
SurgicalEnv.reset() → randomized params applied → simulator.reset()
    ↓
Agent Action
    ↓
ActionBuilder.process_action() → controller.get_randomized_action() → simulator.step()
    ↓
ObservationBuilder.extract_observation() → RewardFunction.compute() → check_task_success()
    ↓
Gymnasium transition tuple (obs, reward, terminated, truncated, info)
    ↓
TrainingManager.train() → SB3 model.learn() → callbacks + TensorBoard
```

### Key Data Flows

1. **Scene Creation Flow:** User input → parser/template → `SceneDefinition` → JSON/YAML file. No simulator dependency.
2. **Training Flow:** JSON/YAML → `SceneLoader` → `Simulator` → `SurgicalEnv` → `TrainingManager` → SB3. No scene generation dependency.
3. **State Save/Restore Flow:** `simulator.get_state()` → `State` dataclass → `simulator.set_state()`. Backend-specific serialization.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0–1 researcher | Current monolith is fine. Single-machine training with `DummyVecEnv`. |
| 1–10 researchers | Add experiment tracking (W&B, MLflow). Split `rl/` into `env/` and `training/` if algorithms multiply. |
| 10–100 researchers | Move to cloud training (Ray + RLlib, or cloud SB3). Add real mesh asset server. Containerize for reproducibility. |
| 100+ researchers / production | Add ROS2 bridge for real robot. Multi-GPU distributed training. Separate scene database (not JSON files). |

### Scaling Priorities

1. **First bottleneck:** Training speed. `SurgicalEnv.render()` is synchronous and blocks the training loop. Fix: offscreen rendering + parallel envs.
2. **Second bottleneck:** Scene asset distribution. JSON/YAML files don't scale. Fix: asset server with versioned meshes.

## Anti-Patterns

### Anti-Pattern 1: Backend Leakage

**What people do:** Write MuJoCo-specific logic in `rl/` or `dynamics/` layers.
**Why it's wrong:** Violates Strategy pattern. When adding PyBullet (or Isaac Sim), you rewrite everything.
**Do this instead:** Use `BaseSimulator` interface + duck-typed backend detection. Keep backend specifics in `simulators/`.

### Anti-Pattern 2: Monolithic Controller

**What people do:** One `DynamicsController` class that does randomization, curriculum, and adaptive difficulty.
**Why it's wrong:** Hard to test, hard to extend. Changing curriculum logic triggers full controller regression.
**Do this instead:** Composition. `EnvironmentController` wraps `ParameterRandomizer`, `CurriculumScheduler`, `AdaptiveDifficultyController` independently.

### Anti-Pattern 3: YAML as Database

**What people do:** Store all scene definitions as flat JSON/YAML files; look them up by filename.
**Why it's wrong:** No search, no versioning, no deduplication, no asset integrity.
**Do this instead:** For research, keep JSON/YAML but add `SceneLoader` LRU cache + asset hash validation. For production, migrate to a scene database.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| OpenAI API | Async HTTP via `openai.AsyncOpenAI` | Retry with exponential backoff on rate limits |
| Anthropic API | Async HTTP via `anthropic.AsyncAnthropic` | Same retry strategy |
| Ollama | Direct `httpx` POST to `/api/generate` | Local; no auth. Handle connection errors gracefully |
| MuJoCo | Native Python bindings | No containerization needed; ships as pip package |
| PyBullet | Native Python bindings | Soft-body requires `RESET_USE_DEFORMABLE_WORLD` |
| SB3/TensorBoard | File-based logging | `RL_TENSORBOARD_LOG` directory |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| scene_generation ↔ scene_definition | Direct import / model instantiation | `SceneComposer` calls `SceneDefinition.model_validate()` |
| scene_definition ↔ simulators | `SceneBuilder` consumes `SceneDefinition` | Builder is owned by `simulators/` but only depends on schema |
| simulators ↔ dynamics | Duck-typed method calls | `hasattr(simulator, "_model")` or `hasattr(simulator, "_physics_client")` |
| dynamics ↔ rl | Direct composition | `SurgicalEnv` owns `simulator` + `controller` |
| rl ↔ training | Gymnasium API | `SurgicalEnv` is a `gym.Env`; SB3 consumes it |

## Sources

- `ARCHITECTURE.md` (codebase map) — existing system structure
- MuJoCo documentation — 3.x Renderer API and `mjOBJ_FLEX`
- Stable-Baselines3 docs — `BaseCallback`, `DummyVecEnv`, `SubprocVecEnv`
- AGENTS.md — simulator conventions and Pydantic quirks

---
*Architecture research for: surgical-robotics RL training system*
*Researched: 2026-04-29*

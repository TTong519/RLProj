# API Reference

This document provides comprehensive documentation for the Surg-RL API, covering all major modules and their public interfaces.

## Table of Contents

- [Scene Definition](#scene-definition)
- [Scene Generation](#scene-generation)
- [Simulators](#simulators)
- [Reinforcement Learning](#reinforcement-learning)
- [Utilities](#utilities)
- [CLI](#cli)

---

## Scene Definition

The `scene_definition` module provides the core schema and loading functionality for surgical scene definitions.

### `surg_rl.scene_definition.schema`

Defines the Pydantic models that represent the scene structure.

#### Key Classes

- **`SceneDefinition`**: Main container for a complete surgical scene definition
  - Contains metadata, physics, environment, robots, tissues, instruments, task, domain randomization, and simulator settings
  - Methods:
    - `get_robot(name: str) -> Optional[RobotConfig]`
    - `get_tissue(name: str) -> Optional[TissueConfig]`
    - `get_instrument(name: str) -> Optional[InstrumentConfig]`
    - `get_camera(name: str) -> Optional[CameraConfig]`
    - `get_active_cameras() -> List[CameraConfig]`

- **`Metadata`**: Scene metadata (name, description, version, author, tags)
- **`PhysicsConfig`**: Global physics configuration (gravity, timestep, solver, materials)
- **`EnvironmentConfig`**: Scene environment (lights, cameras, ground plane, surgical table, fog)
- **`RobotConfig`**: Robot definition with URDF or direct link/joint configuration
- **`TissueConfig`**: Tissue/organ definition with geometry and soft body physics
- **`InstrumentConfig`**: Surgical instrument definition with optional pose and tool properties
- **`TaskConfig`**: Task definition with objectives, constraints, and reward shaping
- **`DomainRandomizationConfig`**: Physics, visual, and dynamics randomization settings

#### Example Usage

```python
from surg_rl.scene_definition.schema import SceneDefinition, RobotConfig, TissueConfig

# Load a scene definition
scene = SceneDefinition(
    metadata={"name": "simple_suturing", "version": "1.0.0"},
    robots=[...],
    tissues=[...],
    task={"name": "suturing_task", "objectives": [...]},
)

# Access entities by name
robot = scene.get_robot("surgical_arm")
cameras = scene.get_active_cameras()
```

### `surg_rl.scene_definition.loader`

Provides functionality for loading scene definitions from various file formats.

#### Key Classes and Functions

- **`SceneLoader`**
  - `load(file_path, use_cache=True, validate=True) -> SceneDefinition`
  - `load_from_string(content, format="json", validate=True) -> SceneDefinition`
  - `load_from_dict(data, validate=True) -> SceneDefinition`
  - `save(scene, file_path, format=None) -> None`
  - `list_scenes(directory) -> List[Path]`
  - `load_directory(directory, pattern="*") -> Dict[str, SceneDefinition]`

- **`SceneCache`** — LRU cache for loaded scenes keyed by file path + mtime
- **`AssetManager`** — Resolves and validates referenced asset paths

- **`load_scene(path, use_cache=True, validate=True) -> SceneDefinition`** — Convenience function using the global loader
- **`save_scene(scene, file_path, format=None) -> None`** — Convenience function for saving

#### Exceptions

- **`SceneLoaderError`** — Base exception for loader errors
- **`SceneFileNotFoundError`** — Scene file not found
- **`SceneValidationError`** — Pydantic schema validation failed
- **`SceneParseError`** — JSON/YAML parsing failed
- **`AssetLoadError`** — Referenced asset file could not be loaded

#### Example Usage

```python
from surg_rl.scene_definition.loader import load_scene, save_scene

# Load single scene
scene = load_scene("scenes/simple_suturing.json")

# Load all scenes from directory
from surg_rl.scene_definition.loader import SceneLoader
loader = SceneLoader()
scenes = loader.load_directory("scenes/")
```

---

## Scene Generation

The `scene_generation` module provides AI-powered generation of surgical scenes from natural language descriptions and images.

### `surg_rl.scene_generation.scene_composer`

Main orchestrator for composing scenes from multiple inputs.

#### Key Classes

- **`SceneComposer`**
  - Coordinates text parsing, vision parsing, scene merging, and validation.

  **Methods:**
  - `compose(inputs=None, text_inputs=None, image_inputs=None, base_scene=None, merge_strategy="sequential") -> SceneDefinition`
    - Generate or merge scenes from multiple inputs (sequential or parallel)
  - `compose_sync(...)` — Synchronous wrapper for `compose()`

### `surg_rl.scene_generation.text_parser`

Parses text descriptions into structured scene definitions using LLMs.

#### Key Classes

- **`TextParser`**
  - Converts natural language descriptions to `SceneDefinition`
  - Supports OpenAI, Anthropic, and Ollama providers

  **Methods:**
  - `parse(input_data) -> SceneDefinition` — Async
  - `parse_with_context(input_data, context=None) -> SceneDefinition` — Async
  - `parse_sync(input_data)` — Synchronous wrapper

### `surg_rl.scene_generation.vision_parser`

Analyzes surgical images to extract scene information.

#### Key Classes

- **`VisionParser`**
  - Uses vision-language models to generate `SceneDefinition` from images
  - Supports OpenAI, Anthropic, and Ollama providers

  **Methods:**
  - `parse(input_data) -> SceneDefinition` — Async
  - `parse_with_context(input_data, context=None) -> SceneDefinition` — Async
  - `analyze_image(input_data) -> str` — Async text description only
  - `parse_sync(...)` / `analyze_image_sync(...)` — Synchronous wrappers

### `surg_rl.scene_generation.templates`

Provides template definitions for common surgical procedures.

#### Key Functions

- **`get_template(name: str) -> SceneDefinition`**
  - Get a pre-defined template by name
  - Common names: `suturing`, `dissection`, `manipulation`
- **`list_templates() -> Dict[str, str]`**
  - List available templates with descriptions

#### Example Usage

```python
from surg_rl.scene_generation import SceneComposer, TextParser, get_template

# Use a built-in template
scene = get_template("suturing")

# Generate from text
parser = TextParser()
scene = await parser.parse("A laparoscopic dissection scene with two instruments")

# Compose multiple inputs
composer = SceneComposer()
scene = composer.compose_sync(
    text_inputs=["Add a skin tissue", "Place a scalpel instrument"],
    base_scene=scene,
)
```

---

## Simulators

The `simulators` module provides unified interfaces to physics simulation backends.

### `surg_rl.simulators.base_simulator`

Abstract base class defining the simulator interface.

#### Key Classes

- **`BaseSimulator`** (ABC)
  - Defines common interface for all simulators

  **Abstract Methods:**
  - `load_scene(scene_definition) -> None`
  - `step(action: np.ndarray) -> StepResult`
  - `reset(seed=None) -> Observation`
  - `render(mode="rgb_array", width=640, height=480, camera_name=None) -> Optional[np.ndarray]`
  - `get_state() -> State`
  - `set_state(state: State) -> None`
  - `close() -> None`

  **Data Classes:**
  - `Observation` — RGB, depth, robot state, end-effector pose, force/torque, tissue state
  - `State` — qpos, qvel, body positions/orientations, time
  - `StepResult` — observation, reward, terminated, truncated, info

### `surg_rl.simulators.mujoco_simulator`

MuJoCo physics simulator implementation.

#### Key Classes

- **`MuJoCoSimulator(BaseSimulator)`**
  - High-fidelity physics simulation using MuJoCo
  - Supports soft body dynamics via MuJoCo flex API (experimental)

  **Additional Methods:**
  - `get_state() -> State`
  - `set_state(state: State) -> None`
  - `get_joint_states() -> Dict[str, Dict[str, np.ndarray]]`
  - `get_body_pose(body_name) -> Tuple[np.ndarray, np.ndarray]`
  - `apply_force(body_name, force, torque) -> bool`
  - `get_tissue_deformation(tissue_name) -> Optional[np.ndarray]`
  - `start_viewer() -> None` — Launch passive viewer (GUI)

### `surg_rl.simulators.pybullet_simulator`

PyBullet physics simulator implementation.

#### Key Classes

- **`PyBulletSimulator(BaseSimulator)`**
  - Fast simulation using PyBullet
  - Good for rapid prototyping and testing

### `surg_rl.simulators.scene_builder`

Utility for converting scene definitions to simulator-specific formats with primitive shape fallbacks.

#### Key Classes

- **`SceneBuilder`**
  - Converts `SceneDefinition` to MJCF XML for MuJoCo
  - Generates OBJ primitive meshes when real assets are missing

  **Methods:**
  - `create_mjcf(scene_definition, output_path) -> Path` — Build MJCF XML from scene
  - `resolve_asset_path(asset_path) -> Optional[Path]` — Resolve asset file
  - `cleanup() -> None` — Remove generated temp files

- **`AssetMissingError(Exception)`** — Raised when assets are missing and fallback is disabled

#### Example Usage

```python
from surg_rl.simulators.mujoco_simulator import MuJoCoSimulator
from surg_rl.scene_definition.loader import load_scene

# Load scene and initialize simulator
scene = load_scene("scenes/laparoscopic_dissection.yaml")
sim = MuJoCoSimulator()
sim.load_scene(scene)

# Run simulation
obs = sim.reset()
for _ in range(1000):
    action = policy.get_action(obs)
    result = sim.step(action)
    if result.done:
        break

sim.close()
```

---

## Reinforcement Learning

The `rl` module provides RL training infrastructure.

### `surg_rl.rl.environment`

- **`SurgicalEnv(gym.Env)`** — Gymnasium-compatible environment wrapper
  - Configurable observation and action spaces
  - Domain randomization integration via `EnvironmentController`
  - Supports vectorized environments via `make_vec_env()`
- **`SurgicalEnvConfig`** — Configuration dataclass for `SurgicalEnv`
- **`make_env()`** — Factory function to create a `SurgicalEnv`
- **`make_vec_env()`** — Create vectorized environments for parallel training

### `surg_rl.rl.training`

- **`TrainingManager`** — Orchestrates RL training with Stable-Baselines3
  - Supports PPO, SAC, TD3, DDPG, A2C algorithms
  - Checkpoint saving and evaluation
  - Handles `MultiInputPolicy` for Dict observation spaces
- **`TrainingConfig`** — Training configuration (timesteps, seed, device, etc.)
- **`AlgorithmConfig`** — Algorithm-specific hyperparameters with `to_dict()` method

### `surg_rl.rl.observation`

- **`ObservationBuilder`** — Builds observation spaces and extracts observations from simulator
- **`ObservationConfig`** — Configuration for observation types
- **`ObservationSpec`** — Specification for a single observation component
- **`ObservationType`** — Enum of available observation types (`JOINT_POSITIONS`, `RGB_IMAGE`, `TISSUE_STATE`, etc.)

### `surg_rl.rl.action`

- **`ActionBuilder`** — Builds action spaces and processes raw actions
- **`ActionConfig`** — Configuration for action types
- **`ActionSpec`** — Specification for a single action component
- **`ActionType`** — Enum of available action types (`JOINT_POSITIONS`, `ENDEFFECTOR_POSE`, `GRIPPER`, etc.)

### `surg_rl.rl.rewards`

- **`CompositeReward`** — Weighted combination of reward functions
- **`DistanceReward`** — Reward based on distance to target
- **`OrientationReward`** — Reward based on orientation alignment
- **`SuccessReward`** — Sparse terminal reward for task completion
- **`ActionPenalty`** — Penalizes large actions
- **`CollisionPenalty`** — Penalizes collisions and tissue damage
- **`SuturingReward`** / **`DissectionReward`** / **`NeedlePassingReward`** — Task-specific rewards
- **`create_default_reward(config, task_name)`** — Factory for standard surgical reward

### `surg_rl.rl.callbacks`

- **`TrainingProgressCallback`** — Logs episode rewards/lengths during training
- **`CheckpointCallback`** — Saves model checkpoints at fixed timestep intervals
- **`CurriculumCallback`** — Hooks `EnvironmentController` into SB3 training
- **`EvaluationCallback`** — Runs deterministic evaluation episodes at intervals
- **`TensorBoardCallback`** — Logs rollout metrics, curriculum stage, and domain randomization parameters

---

## Utilities

### `surg_rl.utils.config`

Configuration management via Pydantic v2 `BaseSettings`.

#### Key Classes and Functions

- **`Settings(BaseSettings)`** — Reads from `.env` file (`env_file=".env"`)
  - Fields: `project_root`, `assets_dir`, `default_simulator`, `llm_provider`, `llm_api_key`, `render_width`, `render_height`, `rl_device`, `rl_seed`, `log_level`, etc.
  - Methods:
    - `get_full_path(relative_path) -> Path`
    - `ensure_directories() -> None`

- **`get_settings() -> Settings`** — Returns the global singleton `Settings` instance
- **`reset_settings() -> None`** — Resets the global singleton

### `surg_rl.utils.logging`

Logging configuration using Rich handlers.

#### Key Functions

- **`setup_logging(level=None, log_file=None, rich_output=True) -> logging.Logger`**
  - Configures and returns the `"surg_rl"` logger
  - Defaults are pulled from `get_settings()`
  - Closes existing handlers to prevent leaks

- **`get_logger(name="surg_rl") -> logging.Logger`**
  - Simple wrapper around `logging.getLogger`

---

## CLI

### `surg_rl.cli`

Command-line interface for Surg-RL using Typer.

#### Commands

- **`surg-rl version`**
  - Print package version

- **`surg-rl config`**
  - Print current `Settings` as a Rich table

- **`surg-rl setup`**
  - Create asset/scene/config directories

- **`surg-rl generate`**
  - Generate surgical scenes from templates, text, or images
  ```bash
  surg-rl generate --template suturing --output scene.json
  surg-rl generate --text "Create a suturing scene" --provider openai
  ```

- **`surg-rl train`**
  - Train RL policies on scenes
  ```bash
  surg-rl train --scene scene.json --algorithm PPO --timesteps 100000
  ```

- **`surg-rl evaluate`**
  - Evaluate trained policies
  ```bash
  surg-rl evaluate --model model.zip --scene scene.json --episodes 10
  ```

---

## Type Definitions

Common types used throughout the API:

```python
from typing import Dict, List, Tuple, Optional, Any
import numpy as np

# Position in 3D space
PositionTuple = Tuple[float, float, float]

# Quaternion orientation
OrientationTuple = Tuple[float, float, float, float]

# Observation returned by simulator
ObservationDict = Dict[str, np.ndarray]

# Action to be applied
ActionArray = np.ndarray
```

---

## Error Handling

The API uses custom exceptions for clear error reporting:

- **`SceneValidationError`** — Scene definition fails Pydantic validation
- **`SceneFileNotFoundError`** — Scene file not found
- **`SceneParseError`** — JSON/YAML parsing failed
- **`AssetLoadError`** — Referenced asset could not be loaded
- **`ParserError`** — Scene generation parsing failed
- **`ParseTimeoutError`** — LLM/VLM parsing timed out
- **`ParseValidationError`** — Generated scene failed validation

Example error handling:

```python
from surg_rl.scene_definition.loader import load_scene
from surg_rl.scene_definition import SceneValidationError, SceneFileNotFoundError

try:
    scene = load_scene("scenes/my_scene.json")
except SceneFileNotFoundError as e:
    print(f"Scene file not found: {e}")
except SceneValidationError as e:
    print(f"Scene validation failed: {e}")
```

---

## See Also

- [Getting Started Guide](GETTING_STARTED.md) — Tutorial for beginners
- [Architecture Overview](ARCHITECTURE.md) — Understanding the system design
- [Scene Format Specification](SCENE_FORMAT.md) — Detailed scene format docs
- [Configuration Guide](CONFIGURATION.md) — Configuration options and environment variables

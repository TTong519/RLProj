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
  - Contains metadata, scene objects, task definition, success criteria, and RL parameters
  
- **`SceneObject`**: Represents a physical object in the scene
  - Properties: geometry, position, orientation, material properties
  
- **`TaskDefinition`**: Defines the surgical task to be performed
  - Includes task type, difficulty level, and specific parameters
  
- **`SuccessCriteria`**: Defines conditions for successful task completion
  - Includes position tolerances, angle tolerances, time limits

#### Example Usage

```python
from surg_rl.scene_definition.schema import SceneDefinition, SceneObject

# Create a scene object
scene_obj = SceneObject(
    name="surgical_tool",
    geometry={"type": "mesh", "file": "assets/scalpel.obj"},
    position=[0.0, 0.0, 0.5],
    orientation=[0.0, 0.0, 0.0, 1.0],
    material={"friction": 0.8, "restitution": 0.1}
)

# Create scene definition
scene_def = SceneDefinition(
    metadata={"name": "simple_suturing", "version": "1.0"},
    objects=[scene_obj],
    task=TaskDefinition(task_type="suturing", difficulty="medium")
)
```

### `surg_rl.scene_definition.loader`

Provides functionality for loading scene definitions from various file formats.

#### Key Functions

- **`load_scene(path: str) -> SceneDefinition`**
  - Load a scene definition from YAML or JSON file
  - Automatically detects format based on file extension
  - Validates scene against schema
  
- **`load_all_scenes(directory: str) -> List[SceneDefinition]`**
  - Load all scene definitions from a directory
  - Returns list of validated scene definitions

#### Example Usage

```python
from surg_rl.scene_definition.loader import load_scene, load_all_scenes

# Load single scene
scene = load_scene("scenes/simple_suturing.json")

# Load all scenes from directory
scenes = load_all_scenes("scenes/")
```

---

## Scene Generation

The `scene_generation` module provides AI-powered generation of surgical scenes from natural language descriptions.

### `surg_rl.scene_generation.scene_composer`

Main orchestrator for scene generation workflow.

#### Key Classes

- **`SceneComposer`**
  - Main entry point for generating scenes
  - Coordinates LLM parsing, template application, and validation
  
  **Methods:**
  - `generate_from_text(description: str, output_path: Optional[str] = None) -> SceneDefinition`
    - Generate scene from text description
  - `generate_from_image(image_path: str, output_path: Optional[str] = None) -> SceneDefinition`
    - Generate scene from surgical image

#### Example Usage

```python
from surg_rl.scene_generation.scene_composer import SceneComposer

# Initialize composer
composer = SceneComposer()

# Generate from text description
scene = composer.generate_from_text(
    "A laparoscopic cholecystectomy scene with a patient on the operating table, "
    "trocars positioned for optimal access, and surgical instruments ready"
)

# Save generated scene
composer.save_scene(scene, "output/generated_scene.json")
```

### `surg_rl.scene_generation.text_parser`

Parses text descriptions into structured scene parameters using LLMs.

#### Key Classes

- **`TextParser`**
  - Converts natural language descriptions to scene objects
  - Supports OpenAI and Anthropic models
  
  **Methods:**
  - `parse(description: str) -> Dict[str, Any]`
    - Parse text and return structured scene parameters

### `surg_rl.scene_generation.vision_parser`

Analyzes surgical images to extract scene information.

#### Key Classes

- **`VisionParser`**
  - Uses vision-language models to understand surgical images
  - Extracts object positions, types, and relationships
  
  **Methods:**
  - `analyze(image_path: str) -> Dict[str, Any]`
    - Analyze image and return scene parameters

### `surg_rl.scene_generation.templates`

Provides template definitions for common surgical procedures.

#### Key Functions

- **`get_template(procedure_name: str) -> Dict[str, Any]`**
  - Get a pre-defined template for a surgical procedure
  - Common procedures: `laparoscopic_cholecystectomy`, `hysterectomy`, `appendectomy`

---

## Simulators

The `simulators` module provides unified interfaces to physics simulation backends.

### `surg_rl.simulators.base_simulator`

Abstract base class defining the simulator interface.

#### Key Classes

- **`BaseSimulator`** (ABC)
  - Defines common interface for all simulators
  
  **Abstract Methods:**
  - `load_scene(scene_def: SceneDefinition) -> None`
  - `step(action: np.ndarray) -> Tuple[Observation, float, bool, Dict]`
  - `reset() -> Observation`
  - `render(mode: str = "human") -> Optional[np.ndarray]`
  - `close() -> None`

### `surg_rl.simulators.mujoco_simulator`

MuJoCo physics simulator implementation.

#### Key Classes

- **`MuJoCoSimulator(BaseSimulator)`**
  - High-fidelity physics simulation using MuJoCo
  - Supports soft body dynamics, tendon mechanics
  
  **Additional Methods:**
  - `get_state() -> np.ndarray`
  - `set_state(state: np.ndarray) -> None`
  - `get_dynamics_info() -> Dict[str, Any]`

#### Example Usage

```python
from surg_rl.simulators.mujoco_simulator import MuJoCoSimulator
from surg_rl.scene_definition.loader import load_scene

# Load scene and initialize simulator
scene = load_scene("scenes/laparoscopic_dissection.yaml")
sim = MuJoCoSimulator(scene)

# Run simulation
obs = sim.reset()
for _ in range(1000):
    action = policy.get_action(obs)
    obs, reward, done, info = sim.step(action)
    if done:
        break

sim.close()
```

### `surg_rl.simulators.pybullet_simulator`

PyBullet physics simulator implementation.

#### Key Classes

- **`PyBulletSimulator(BaseSimulator)`**
  - Fast simulation using PyBullet
  - Good for rapid prototyping and testing
  
  **Additional Methods:**
  - `save_snapshot(path: str) -> None`
  - `load_snapshot(path: str) -> None`

### `surg_rl.simulators.scene_builder`

Utility for converting scene definitions to simulator-specific formats.

#### Key Functions

- **`build_mujoco_scene(scene_def: SceneDefinition) -> MujocoScene`**
  - Convert scene definition to MuJoCo XML format
  
- **`build_pybullet_scene(scene_def: SceneDefinition) -> PyBulletScene`**
  - Convert scene definition to PyBullet URDF format

---

## Reinforcement Learning

The `rl` module provides RL training infrastructure.

### `surg_rl.rl.environment`

- **`SurgicalEnv(gym.Env)`** - Gymnasium-compatible environment wrapper
  - Configurable observation and action spaces
  - Domain randomization integration
  - Supports vectorized environments via `make_vec_env()`
- **`SurgicalEnvConfig`** - Configuration dataclass for SurgicalEnv
- **`make_env()`** - Factory function to create a SurgicalEnv
- **`make_vec_env()`** - Create vectorized environments for parallel training

### `surg_rl.rl.training`

- **`TrainingManager`** - Orchestrates RL training with Stable-Baselines3
  - Supports PPO, SAC, TD3, DDPG, A2C algorithms
  - Checkpoint saving and evaluation
- **`TrainingConfig`** - Training configuration (timesteps, seed, device, etc.)
- **`AlgorithmConfig`** - Algorithm-specific hyperparameters

### `surg_rl.rl.observation`

- **`ObservationBuilder`** - Builds observation spaces and extracts observations
- **`ObservationConfig`** - Configuration for observation types
- **`ObservationSpec`** - Specification for a single observation component
- **`ObservationType`** - Enum of available observation types

### `surg_rl.rl.action`

- **`ActionBuilder`** - Builds action spaces and processes actions
- **`ActionConfig`** - Configuration for action types
- **`ActionType`** - Enum of available action types

### `surg_rl.rl.rewards`

- **`CompositeReward`** - Weighted combination of reward functions
- **`DistanceReward`** - Reward based on distance to target
- **`SuccessReward`** - Sparse terminal reward for task completion
- **`ActionPenalty`** - Penalizes large actions
- **`create_default_reward()`** - Factory for standard surgical reward

---

## Utilities

### `surg_rl.utils.config`

Configuration management utilities.

#### Key Functions

- **`load_config(path: str) -> Dict[str, Any]`**
  - Load configuration from YAML file
  - Supports environment variable substitution

- **`get_default_config() -> Dict[str, Any]`**
  - Get default configuration values

### `surg_rl.utils.logging`

Logging and monitoring utilities.

#### Key Functions

- **`setup_logging(config: Dict[str, Any]) -> None`**
  - Configure logging with file and console handlers
  
- **`get_logger(name: str) -> Logger`**
  - Get configured logger instance

---

## CLI

### `surg_rl.cli`

Command-line interface for Surg-RL.

#### Commands

- **`surg-rl generate`**
  - Generate surgical scenes from descriptions
  ```bash
  surg-rl generate --from-text "description" --output scene.json
  surg-rl generate --from-image image.png --output scene.yaml
  ```

- **`surg-rl train`**
  - Train RL policies on scenes
  ```bash
  surg-rl train --scene scene.json --algorithm PPO --timesteps 100000
  ```

- **`surg-rl evaluate`**
  - Evaluate trained policies
  ```bash
  surg-rl evaluate --policy model.zip --scene scene.json --episodes 10
  ```

---

## Type Definitions

Common types used throughout the API:

```python
from typing import Dict, List, Tuple, Optional, Any
import numpy as np

# Position in 3D space
Position = Tuple[float, float, float]

# Quaternion orientation
Orientation = Tuple[float, float, float, float]

# Observation returned by simulator
Observation = Dict[str, np.ndarray]

# Action to be applied
Action = np.ndarray
```

---

## Error Handling

The API uses custom exceptions for clear error reporting:

- **`SceneValidationError`**: Raised when scene definition fails validation
- **`SimulatorError`**: Base class for simulator-related errors
- **`ConfigurationError`**: Raised for configuration-related issues
- **`UnsupportedFormatError`**: Raised when loading unsupported file formats

Example error handling:

```python
from surg_rl.scene_definition.loader import load_scene
from surg_rl.exceptions import SceneValidationError, UnsupportedFormatError

try:
    scene = load_scene("scenes/my_scene.json")
except SceneValidationError as e:
    print(f"Scene validation failed: {e}")
except UnsupportedFormatError as e:
    print(f"Unsupported file format: {e}")
```

---

## See Also

- [Getting Started Guide](GETTING_STARTED.md) - Tutorial for beginners
- [Architecture Overview](ARCHITECTURE.md) - Understanding the system design
- [Scene Format Specification](SCENE_FORMAT.md) - Detailed scene format docs
- [Configuration Guide](CONFIGURATION.md) - Detailed configuration options

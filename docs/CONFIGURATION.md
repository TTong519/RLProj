<!-- generated-by: gsd-doc-writer -->

# Configuration Guide

Surg-RL uses **Pydantic v2** for type-safe configuration with **pydantic-settings** to load from `.env` files. Training configuration uses Python `dataclass` models, and scene definitions use Pydantic `BaseModel` with JSON/YAML loading.

---

## Configuration Layers

Settings are resolved in the following order (later overrides earlier):

1. **Defaults** in `src/surg_rl/utils/config.py` → `Settings` class
2. **`.env` file** in the project root (loaded via `python-dotenv` → pydantic-settings `SettingsConfigDict(env_file=".env")`)
3. **Environment variables** (case-insensitive, e.g. `DEFAULT_SIMULATOR` maps to `settings.default_simulator`)
4. **Runtime overrides** — pass keyword arguments to `Settings(...)`

---

## Environment Variables

Copy `.env.example` to `.env` in the project root and fill in your values. All variables are loaded through the `Settings(BaseSettings)` class at `src/surg_rl/utils/config.py`.

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLM_PROVIDER` | No | `openai` | LLM backend for scene generation: `openai`, `anthropic`, or `ollama` |
| `LLM_MODEL` | No | `gpt-4-turbo-preview` | Model name sent to the LLM provider |
| `LLM_API_KEY` | No | `None` | API key for the LLM provider. Validated to reject placeholder values (`sk-xxxxxxxx`, `YOUR_API_KEY`, etc.) |
| `LLM_TEMPERATURE` | No | `0.7` | Temperature for LLM completions (0.0–2.0) |
| `LLM_MAX_TOKENS` | No | `4096` | Maximum tokens in LLM response |
| `VLM_MODEL` | No | `gpt-4-vision-preview` | Vision-language model for image-based scene parsing |
| `OLLAMA_BASE_URL` | No | `http://localhost:11434` | Base URL for local Ollama server |
| `OLLAMA_MODEL` | No | `llama3.2` | Default Ollama model for text generation |
| `OLLAMA_VISION_MODEL` | No | `llava` | Default Ollama model for vision tasks |
| `OLLAMA_TIMEOUT` | No | `300` | Timeout in seconds for Ollama API calls (≥1) |
| `DEFAULT_SIMULATOR` | No | `mujoco` | Simulator backend: `mujoco` or `pybullet` |
| `MUJOCO_TIMESTEP` | No | `0.002` | MuJoCo physics timestep in seconds (0.0001–0.1) |
| `PYBULLET_TIMESTEP` | No | `1/240` (~0.00417) | PyBullet physics timestep in seconds (0.0001–0.1) |
| `RENDER_WIDTH` | No | `640` | Render viewport width in pixels (≥64) |
| `RENDER_HEIGHT` | No | `480` | Render viewport height in pixels (≥64) |
| `RENDER_FPS` | No | `60` | Frames-per-second for rendering (≥1) |
| `RL_DEVICE` | No | `auto` | Compute device for RL training: `auto`, `cpu`, `cuda`, `mps` |
| `RL_SEED` | No | `42` | Random seed for reproducibility |
| `RL_TENSORBOARD_LOG` | No | `None` | Path to TensorBoard log directory (`Path \| None`) |
| `RANDOMIZATION_ENABLED` | No | `false` | Master toggle for domain randomization |
| `PHYSICS_RANDOMIZATION` | No | `true` | Randomize physics parameters |
| `VISUAL_RANDOMIZATION` | No | `true` | Randomize visual parameters |
| `DYNAMICS_RANDOMIZATION` | No | `true` | Randomize dynamics parameters |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `LOG_FILE` | No | `None` | Optional log file path (`Path \| None`) |
| `WANDB_API_KEY` | No | `None` | Weights & Biases API key for experiment tracking |
| `MLFLOW_TRACKING_URI` | No | `None` | MLflow tracking server URI |
| `GPU_BACKEND` | No | `auto` | Hardware backend for rendering/compute: `auto`, `cuda`, `rocm`, `metal`, `intel`, `cpu` |

### Accessing Settings in Code

```python
from surg_rl.utils.config import get_settings, Settings

# Get the global (cached) settings instance
settings = get_settings()
print(settings.default_simulator)  # "mujoco"
print(settings.llm_provider)       # "openai"

# Create with runtime overrides
settings = Settings(default_simulator="pybullet", rl_seed=123)
```

The global instance is lazily created and cached. Call `reset_settings()` to force a reload.

---

## Required vs Optional Settings

**Required** (application will raise errors if missing or invalid):

- `llm_api_key` — validated at field level; rejects known placeholder patterns (`sk-xxxxxxxx`, `YOUR_API_KEY`, `REPLACE_ME`). If unset (`None`), LLM-dependent features will fail at call time, but the `Settings` object itself will still construct.
- `mujoco_timestep` / `pybullet_timestep` — constrained to `[0.0001, 0.1]`. A value outside this range raises a `ValidationError` at `Settings` construction time.
- `llm_temperature` — constrained to `[0.0, 2.0]`.

**Optional** (have defaults and can be left unset):

- All other fields in the table above have sensible defaults (see the [Settings Class Defaults](#settings-class-defaults) section).

---

## Settings Class Defaults

The `Settings(BaseSettings)` class at `src/surg_rl/utils/config.py` defines the following field defaults in code (not all are exposed in `.env.example`):

| Field | Default | Source |
|---|---|---|
| `project_root` | Auto-resolved from `__file__` (4 levels up) | Derived |
| `assets_dir` | `Path("assets")` | Default factory |
| `scenes_dir` | `Path("scenes")` | Default factory |
| `configs_dir` | `Path("configs")` | Default factory |
| `mujoco_timestep` | `0.002` | Field default |
| `pybullet_timestep` | `1.0 / 240.0` | Field default |
| `render_width` | `640` | Field default |
| `render_height` | `480` | Field default |
| `render_fps` | `60` | Field default |
| `rl_device` | `"auto"` | Field default |
| `rl_seed` | `42` | Field default |
| `randomization_enabled` | `False` | Field default |
| `gpu_backend` | `"auto"` | Field default |
| `log_level` | `"INFO"` | Field default |

Computed properties (`meshes_dir`, `textures_dir`, `materials_dir`) derive from `assets_dir`:
- `meshes_dir` → `assets_dir / "meshes"`
- `textures_dir` → `assets_dir / "textures"`
- `materials_dir` → `assets_dir / "materials"`

---

## Training Configuration

Training uses two `dataclass` models at `src/surg_rl/rl/training.py`:

### AlgorithmConfig

Controls RL algorithm hyperparameters. Defaults tuned for PPO:

| Field | Type | Default | Applies to |
|---|---|---|---|
| `name` | `str` | `"PPO"` | All |
| `learning_rate` | `float` | `3e-4` | All |
| `n_steps` | `int` | `2048` | PPO, A2C |
| `batch_size` | `int` | `64` | All |
| `n_epochs` | `int` | `10` | PPO |
| `gamma` | `float` | `0.99` | All |
| `gae_lambda` | `float` | `0.95` | PPO, A2C |
| `clip_range` | `float` | `0.2` | PPO |
| `ent_coef` | `float` | `0.01` | PPO, A2C |
| `vf_coef` | `float` | `0.5` | PPO, A2C |
| `max_grad_norm` | `float` | `0.5` | PPO, A2C |
| `buffer_size` | `int` | `1_000_000` | SAC, TD3, DDPG |
| `learning_starts` | `int` | `100` | SAC, TD3, DDPG |
| `tau` | `float` | `0.005` | SAC, TD3, DDPG |
| `train_freq` | `int` | `1` | SAC, TD3, DDPG |
| `gradient_steps` | `int` | `1` | SAC, TD3, DDPG |
| `policy_kwargs` | `dict \| None` | `None` | All |

Supported algorithm names: `PPO`, `SAC`, `TD3`, `DDPG`, `A2C` (mapped to `stable_baselines3` classes at runtime).

### TrainingConfig

Top-level training run configuration:

| Field | Type | Default | Description |
|---|---|---|---|
| `scene_path` | `str` | `"scenes/simple_suturing.json"` | Path to scene definition file |
| `algorithm` | `AlgorithmConfig` | `AlgorithmConfig()` | Algorithm hyperparameters |
| `total_timesteps` | `int` | `1_000_000` | Total training steps |
| `n_envs` | `int` | `1` | Parallel environments (1 = single env, >1 = vectorized) |
| `seed` | `int` | `42` | Random seed |
| `device` | `str` | `"auto"` | Compute device |
| `log_dir` | `str` | `"logs/training"` | Log and checkpoint directory |
| `tensorboard_log` | `str \| None` | `None` | TensorBoard log directory |
| `save_freq` | `int` | `50_000` | Checkpoint save interval (steps) |
| `eval_freq` | `int` | `10_000` | Evaluation interval (steps) |
| `n_eval_episodes` | `int` | `10` | Evaluation episodes per run |
| `verbose` | `int` | `1` | Verbosity: 0=silent, 1=info, 2=debug |
| `max_episode_steps` | `int` | `1000` | Maximum steps per episode |
| `simulator` | `str` | `"mujoco"` | Simulator backend |
| `render_mode` | `str \| None` | `None` | Render mode (e.g., `"human"`) |
| `render_fps` | `float` | `30.0` | Render FPS during training |
| `use_curriculum` | `bool` | `False` | Enable curriculum learning |
| `use_adaptive_difficulty` | `bool` | `False` | Enable adaptive difficulty |
| `enable_tensorboard` | `bool` | `False` | Enable TensorBoard logging |
| `use_wandb` | `bool` | `False` | Enable W&B experiment tracking |
| `use_mlflow` | `bool` | `False` | Enable MLflow experiment tracking |
| `experiment_name` | `str \| None` | `None` | Experiment name for tracking |
| `wandb_project` | `str \| None` | `None` | W&B project name |
| `backend` | `HardwareBackend` | `HardwareBackend.auto` | Hardware backend enum |

### Example Usage

```python
from surg_rl.rl.training import AlgorithmConfig, TrainingConfig, TrainingManager

# PPO with custom hyperparameters
alg = AlgorithmConfig(name="PPO", learning_rate=1e-4, n_steps=1024, batch_size=32)

cfg = TrainingConfig(
    scene_path="scenes/simple_suturing.json",
    algorithm=alg,
    total_timesteps=500_000,
    n_envs=4,
    enable_tensorboard=True,
    use_curriculum=True,
)

manager = TrainingManager(cfg)
model = manager.train()
```

Save/load config as JSON:

```python
cfg.save("experiments/run_01/training_config.json")
restored = TrainingConfig.load("experiments/run_01/training_config.json")
```

---

## Scene Definition Schema

Scene definitions are JSON or YAML files validated against Pydantic v2 models at `src/surg_rl/scene_definition/schema.py`.

### SceneDefinition (Top-Level Model)

| Field | Type | Default | Description |
|---|---|---|---|
| `metadata` | `Metadata` | `Metadata(name="Untitled Scene")` | Scene identification and version |
| `physics` | `PhysicsConfig` | `PhysicsConfig()` | Physics simulation parameters |
| `environment` | `EnvironmentConfig` | `EnvironmentConfig()` | Environment bounding box, cameras, lights |
| `robots` | `list[RobotConfig]` | `[]` | Robot definitions |
| `tissues` | `list[TissueConfig]` | `[]` | Tissue/organ definitions |
| `instruments` | `list[InstrumentConfig]` | `[]` | Surgical instrument definitions |
| `task` | `TaskConfig \| None` | `None` | Task specification (type, targets, metrics) |
| `domain_randomization` | `DomainRandomizationConfig` | `DomainRandomizationConfig()` | Randomization ranges |
| `simulator` | `SimulatorType` | `"mujoco"` | Preferred backend (`mujoco` / `pybullet`) |
| `assets` | `dict[str, AssetReference]` | `{}` | Additional asset references |
| `fluid` | `FluidConfig \| None` | `None` | Fluid simulation configuration (PhiFlow backend) |
| `custom` | `dict[str, Any]` | `{}` | Extension point for custom parameters |

Key enum types: `SimulatorType` (`mujoco` / `pybullet`), `HardwareBackend` (`auto`, `cuda`, `rocm`, `metal`, `intel`, `cpu`), `RobotType`, `TissueType`, `InstrumentType`, `JointType`, `CameraType`, `LightType`, `FluidBoundaryType` (`open` / `wall`).

### Validation Rules

- Pydantic v2 `model_validator(mode="after")` must return via `self.model_copy(update={...})` — never mutate `self` in place.
- Use `SceneDefinition.model_construct(**data)` to skip validation for testing.
- `model_dump()` returns Enum **objects** (not `.value` strings). Convert before YAML serialization.

### Loading Scenes

The loader at `src/surg_rl/scene_definition/loader.py` supports:

- **Format auto-detection**: `.json` or `.yaml`/`.yml` based on file extension.
- **In-memory caching**: `SceneCache(max_size=100)` with LRU eviction, keyed by file path + modification time.
- **Validation**: Every loaded file is validated through `SceneDefinition.model_validate()`. Failures raise `SceneValidationError`.

```python
from surg_rl.scene_definition.loader import SceneLoader

loader = SceneLoader()
scene = loader.load("scenes/simple_suturing.json")
```

---

## Deformable Body Configuration

`DeformableConfig` (Pydantic `BaseModel`) at `src/surg_rl/scene_definition/schema.py` provides unified deformable body configuration. It is attached to `TissueConfig` via the `deformable` field when `soft_body=True`.

### DeformableConfig Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `mesh_source` | `Literal["tetgen", "flexcomp_grid", "file"]` | `"tetgen"` | How the deformable mesh is generated |
| `mesh_path` | `str \| None` | `None` | Path to mesh file or tetgen prefix (without extension). Required for `tetgen` and `file` sources |
| `mesh_resolution` | `int` | `4` | Mesh resolution hint (coarser=faster, finer=accurate). `≥1` |
| `max_vertices` | `int` | `200` | Maximum vertex count (for observation padding). `≥1` |
| `mujoco` | `MuJoCoFlexConfig` | `MuJoCoFlexConfig()` | MuJoCo FEM override parameters |
| `pybullet` | `PyBulletFlexConfig` | `PyBulletFlexConfig()` | PyBullet soft body override parameters |
| `boundary_conditions` | `list[BoundaryCondition]` | `[]` | Attachment/pin boundary conditions |
| `observe_vertex_positions` | `bool` | `True` | Include vertex positions in observation |
| `observe_strain` | `bool` | `False` | Include per-element strain in observation |
| `observe_stress` | `bool` | `False` | Include per-element stress in observation |

**Validation**: `mesh_path` is required when `mesh_source != "flexcomp_grid"`. A `ValueError` is raised at model construction if missing.

### MuJoCoFlexConfig

MuJoCo-specific FEM parameters. All fields are optional (default `None`) except `condim` and `friction`:

| Field | Type | Default | Description |
|---|---|---|---|
| `youngs_modulus` | `float \| None` | `None` | Override Young's modulus (Pa). `≥0` |
| `poissons_ratio` | `float \| None` | `None` | Override Poisson's ratio. `[0, 0.5]` |
| `fem_damping` | `float \| None` | `None` | Rayleigh damping for FEM (units: time). `≥0` |
| `edge_stiffness` | `float \| None` | `None` | Edge spring stiffness (N/m). `≥0` |
| `edge_damping` | `float \| None` | `None` | Edge spring damping. `≥0` |
| `condim` | `int` | `3` | Contact dimensionality (1, 3, 4, or 6) |
| `solref` | `str \| None` | `None` | Solver reference string (e.g., `"0.02 1"`) |
| `solimp` | `str \| None` | `None` | Solver impedance string |
| `friction` | `float` | `0.5` | Contact friction coefficient. `≥0` |
| `margin` | `float` | `0.001` | Contact margin (m). `≥0` |
| `smooth_normals` | `bool` | `True` | Use smooth shading for flex surface |

### PyBulletFlexConfig

PyBullet-specific soft body parameters:

| Field | Type | Default | Description |
|---|---|---|---|
| `solver_type` | `Literal["mass_spring", "neo_hookean"]` | `"mass_spring"` | PyBullet soft body solver type |
| `auto_derive_neo_hookean` | `bool` | `True` | Auto-derive Neo-Hookean `μ`/`λ` from `SoftBodyPhysics` `E`, `ν` |
| `repulsion_stiffness` | `float` | `800.0` | Contact repulsion stiffness. `≥0` |
| `use_self_collision` | `bool` | `False` | Enable self-collision |
| `bending_stiffness` | `float` | `0.1` | Bending stiffness (mass-spring only). `≥0` |
| `collision_margin` | `float` | `0.006` | Collision margin (m). `>0` |

### BoundaryCondition

A single boundary condition for a deformable body (e.g., clamped vertices). Attached via `DeformableConfig.boundary_conditions`:

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | — | BC name (e.g., `"clamp_left"`) |
| `type` | `Literal["pin", "fixed_displacement", "force"]` | `"pin"` | Boundary condition type |
| `anchor_body` | `str` | — | Name of the rigid body to attach to |
| `vertex_indices` | `list[int]` | `[]` | Vertex indices to constrain (empty = full weld) |
| `stiffness` | `float` | `1e6` | Attachment stiffness. `≥0` |

### Usage Example

```json
{
  "tissues": [{
    "name": "liver",
    "type": "organ",
    "soft_body": true,
    "soft_body_physics": {
      "stiffness": 1500.0,
      "youngs_modulus": 12000.0,
      "density": 1100.0
    },
    "deformable": {
      "mesh_source": "tetgen",
      "mesh_path": "meshes/liver",
      "mesh_resolution": 6,
      "max_vertices": 300,
      "mujoco": {
        "condim": 4,
        "friction": 0.7,
        "edge_stiffness": 5000.0
      },
      "pybullet": {
        "solver_type": "neo_hookean",
        "repulsion_stiffness": 1000.0
      },
      "boundary_conditions": [{
        "name": "posterior_anchor",
        "type": "pin",
        "anchor_body": "world",
        "vertex_indices": [0, 1, 2, 3],
        "stiffness": 2e6
      }]
    }
  }]
}
```

---

## Volumetric Cutting (CutAction)

`CutAction` (Pydantic `BaseModel`) at `src/surg_rl/scene_definition/schema.py` represents a volumetric surgical cut as a plane. Cutting is a **discrete event** (not continuous control). A `should_cut` flag triggers consumption of cut parameters, with a cooldown enforced in the environment to prevent spam cutting.

### CutAction Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `tissue_name` | `str` | — | Name of the tissue to cut |
| `surface_point` | `Position` | — | Entry point on tissue surface (world coordinates) |
| `direction` | `Position` | — | Cut direction vector (normalized to unit length automatically) |
| `depth` | `float` | `0.01` | Cut depth in meters. `(0, 0.05]` |

**Validation**: The `direction` vector is automatically normalized to unit length if its magnitude differs from `1.0` by more than `1e-6`. A `ValueError` is raised if the direction is a zero vector.

### Usage Example

```python
from surg_rl.scene_definition.schema import CutAction, Position

cut = CutAction(
    tissue_name="liver",
    surface_point=Position(x=0.0, y=0.05, z=0.02),
    direction=Position(x=0.0, y=0.0, z=-1.0),
    depth=0.015,
)
```

---

## Fluid Simulation Configuration

`FluidConfig` (Pydantic `BaseModel`) at `src/surg_rl/scene_definition/schema.py` configures Eulerian grid-based fluid simulation using the **PhiFlow** backend. It appears as an optional `fluid` field on `SceneDefinition`.

### FluidBoundaryType Enum

| Value | Description |
|---|---|
| `open` | Open boundary — fluid flows freely through domain boundaries |
| `wall` | Wall boundary — fluid is contained within domain boundaries |

### FluidConfig Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | `bool` | `False` | Enable fluid simulation |
| `bounds` | `BoundingBox` | — | Physical domain bounds (required) |
| `resolution` | `tuple[int, int]` | `(32, 32)` | Grid resolution `(nx, ny)`. Must be between `[4, 128]` in each dimension |
| `density` | `float` | `1000.0` | Fluid density (kg/m³). `≥1.0` |
| `viscosity` | `float` | `0.004` | Dynamic viscosity (Pa·s). `≥0` |
| `substep_dt` | `float` | `0.02` | Fluid sub-step timestep (s). `>0` |
| `boundary_type` | `FluidBoundaryType` | `FluidBoundaryType.WALL` | Domain boundary condition |
| `initial_velocity` | `Position` | `Position(0,0,0)` | Initial uniform velocity field (m/s) |

**Validation**: Resolution is capped to `128×128` maximum, minimum `4×4`. Values outside this range raise a `ValueError`.

**Dependencies**: Requires the `[simulation]` optional dependency group (see [Per-Environment Overrides](#per-environment-overrides)):
```bash
pip install -e ".[simulation]"
```

This installs `phiflow>=3.4.0` and `scikit-image>=0.21.0`.

### Usage Example

```json
{
  "fluid": {
    "enabled": true,
    "bounds": {"min": {"x": 0.0, "y": 0.0, "z": 0.0}, "max": {"x": 0.1, "y": 0.1, "z": 0.1}},
    "resolution": [64, 64],
    "density": 1000.0,
    "viscosity": 0.004,
    "substep_dt": 0.02,
    "boundary_type": "wall",
    "initial_velocity": {"x": 0.0, "y": 0.0, "z": 0.0}
  }
}
```

---

## ROS2 Bridge Configuration

The ROS2 bridge uses `Ros2BridgeConfig` (Pydantic v2 `@dataclass`) at `src/surg_rl/ros2/config.py`.

### Ros2BridgeConfig Fields

| Field | Required | Default | Description |
|---|---|---|---|
| `state_topic` | **Yes** | — | ROS2 topic for publishing joint states |
| `command_topic` | **Yes** | — | ROS2 topic for subscribing to action commands |
| `frame_id` | No | `"world"` | TF frame ID |
| `batch_size` | No | `1` | States batched before publishing (1 = no batching) |
| `qos_profile` | No | `"sensor_data"` | QoS profile name (`qos_profile_sensor_data`) |
| `on_missing_topic` | No | `"error"` | Strategy when counterpart topic is missing: `"error"` or `"warn"` |
| `on_nan_inf` | No | `"raise"` | Strategy for NaN/Inf values: `"raise"` (`ValueError`) or `"sanitize"` |
| `on_dimension_mismatch` | No | `"zero"` | Strategy for command dimension mismatch: `"zero"` (apply zero action) |

### YAML Configuration

Load from a YAML file (no default `ros2_bridge.yaml` is shipped with the repo — pass one explicitly):

```python
from surg_rl.ros2.config import Ros2BridgeConfig

config = Ros2BridgeConfig.from_yaml("configs/ros2_bridge.yaml")
```

Example YAML:

```yaml
state_topic: "/surg/sim/joint_states"
command_topic: "/surg/sim/arm_command"
frame_id: "surg_world"
on_missing_topic: "warn"
```

**Note**: `rclpy` and ROS2 message packages (`sensor-msgs`, `geometry-msgs`, `std-msgs`) must be installed via `apt` on a ROS2 Humble system; they are not pip-installable. See the `[project.optional-dependencies] ros2` section in `pyproject.toml` for details.

---

## Default YAML Config

The file `configs/default_config.yaml` provides a reference configuration showing available options. It is not automatically loaded at runtime but serves as a template:

```yaml
simulator:
  type: mujoco
  timestep: 0.002

rendering:
  width: 640
  height: 480
  fps: 60

randomization:
  enabled: false
  physics: true
  visual: true
  dynamics: true

training:
  algorithm: PPO
  total_timesteps: 100000
  learning_rate: 0.0003
  batch_size: 64
  n_steps: 2048
```

---

## pytest Configuration

**File**: `pytest.ini` (project root)

| Setting | Value |
|---|---|
| `testpaths` | `tests` |
| `python_files` | `test_*.py` |
| `pythonpath` | `src` |
| `addopts` | `-v --tb=short` |
| `asyncio_mode` | `auto` |
| `asyncio_default_fixture_loop_scope` | `function` |

**Markers**:

| Marker | Description |
|---|---|
| `integration` | Integration tests. Skip with `-m "not integration"` |
| `slow` | Tests expected to take >10 seconds |

Note: `pytest.ini` sets `pythonpath = src`, so `pytest tests/` works without `PYTHONPATH=src`. Direct Python script invocations still require `PYTHONPATH=src`.

---

## Pre-commit Hooks

Enabled via `git config core.hooksPath .githooks`. The hook at `.githooks/pre-commit` runs:

1. **Import corruption guard** — Greps for literal `\n` in Python source files under `src/` and `tests/` (excludes raw strings and `repr()` calls). This catches sed/echo multi-line injection corruption.

2. **Affected test runner** — Runs only the test files whose corresponding source module has staged changes:

   | Changed source pattern | Test file run |
   |---|---|
   | `src/surg_rl/simulators/` | `tests/test_simulators.py` |
   | `src/surg_rl/scene_generation/` | `tests/test_scene_generation.py` |
   | `src/surg_rl/scene_definition/` | `tests/test_scene_definition.py` |
   | `src/surg_rl/rl/` | `tests/test_rl.py` |
   | `src/surg_rl/dynamics/` | `tests/test_dynamics.py` |

All test invocations use `PYTHONPATH=src`. If any test fails the commit is aborted.

---

## Per-Environment Overrides

Surg-RL does not ship with separate `.env.development` or `.env.production` files. Configure different environments by:

1. **Separate `.env` files** — Maintain a `.env` per environment (e.g., `.env.dev`, `.env.staging`) and symlink or copy to `.env` before running:
   ```bash
   cp .env.dev .env && PYTHONPATH=src surg-rl train --scene scenes/suturing.json
   ```

2. **Shell environment variables** — Export variables directly before the command:
   ```bash
   DEFAULT_SIMULATOR=pybullet LOG_LEVEL=DEBUG PYTHONPATH=src surg-rl train --scene scenes/suturing.json
   ```

3. **Runtime `Settings` override** — Pass `Settings(**overrides)` in application entry points:
   ```python
   from surg_rl.utils.config import Settings
   settings = Settings(default_simulator="pybullet", log_level="DEBUG")
   ```

4. **`pyproject.toml` profiles** — Install optional dependency groups per environment:
   ```bash
   # Development
   pip install -e ".[dev]"

   # Production with tracking
   pip install -e ".[tracking]"

   # With fluid simulation (PhiFlow)
   pip install -e ".[simulation]"

   # With tetrahedral meshing (TetGen)
   pip install -e ".[meshing]"

   # With ROS2 (on a ROS2 system)
   pip install -e ".[ros2]"

   # With distributed training (Ray/RLlib)
   pip install -e ".[distributed]"

   # With vision models (PyTorch, Transformers)
   pip install -e ".[vision]"

   # All optional dependencies combined
   pip install -e ".[dev,simulation,meshing,tracking,vision]"
   ```

---

## Code Quality Tooling

Configured in `pyproject.toml`:

| Tool | Settings |
|---|---|
| **Black** | `line-length=100`, targets `py310`/`py311`/`py312` |
| **Ruff** | `line-length=100`, select `["E","F","I","N","W","UP","B","C4","SIM"]`, ignore `E501` |
| **MyPy** | `python_version=3.10`, `warn_return_any=true`, `disallow_untyped_defs=true`, plugin `pydantic.mypy` |

Recommended lint/typecheck order:
```bash
ruff check src/ tests/
black --check src/ tests/
mypy src/surg_rl
```

---

## See Also

- [Getting Started](GETTING_STARTED.md) — Prerequisites and first-run instructions
- [Architecture](ARCHITECTURE.md) — System design and component relationships
- [Scene Format](SCENE_FORMAT.md) — Detailed scene definition schema reference

# Configuration Guide

This document describes how to configure Surg-RL for your specific needs, including simulation parameters, RL training settings, and scene generation options.

## Table of Contents

- [Configuration Files](#configuration-files)
- [Configuration Hierarchy](#configuration-hierarchy)
- [Core Settings](#core-settings)
- [Simulation Configuration](#simulation-configuration)
- [RL Training Configuration](#rl-training-configuration)
- [Scene Generation Configuration](#scene-generation-configuration)
- [Environment Variables](#environment-variables)
- [Advanced Topics](#advanced-topics)

---

## Configuration Files

Surg-RL uses a Pydantic `Settings` class that automatically reads from a `.env` file. Example entries:

```bash
# .env
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
DEFAULT_SIMULATOR=mujoco
RANDOMIZATION_ENABLED=false
```

### Loading Configuration

```python
from surg_rl.utils.config import get_settings

# Get the global settings instance
settings = get_settings()

# Access fields
print(settings.default_simulator)  # "mujoco"
print(settings.project_root)
```

---

## Configuration Hierarchy

Settings are resolved in the following order (later overrides earlier):

1. **Default values** defined in `surg_rl.utils.config.Settings`
2. **Environment variables** (case-insensitive, e.g., `DEFAULT_SIMULATOR`)
3. **`.env` file** (variables prefixed or not; Pydantic `BaseSettings` handles mapping)
4. **Runtime code** — instantiate `Settings` with explicit overrides:

```python
from surg_rl.utils.config import Settings

# Explicit override
settings = Settings(default_simulator="pybullet")
```

---

## Core Settings

### Simulation Backend

Choose between MuJoCo and PyBullet:

```python
settings = get_settings()
print(settings.default_simulator)  # "mujoco"
```

**Comparison:**
- **MuJoCo**: Higher fidelity, better soft-body dynamics, faster for complex scenes
- **PyBullet**: Good for prototyping, broader community support, easier debugging

### Timestep and Physics

```yaml
# In scene definition YAML/JSON
physics:
  timestep: 0.002      # Physics simulation timestep (seconds)
  gravity: [0, 0, -9.81]
  solver_iterations: 50
```

---

## Simulation Configuration

### MuJoCo-Specific Settings

MuJoCo configuration is primarily controlled through the scene definition:

```yaml
physics:
  timestep: 0.002
  solver_iterations: 50
  integrator: implicit    # "implicit" or "RK4"
  contact_model: constraint

simulator: mujoco
```

Rendering defaults are set via `Settings`:

```python
settings.render_width   # 640
settings.render_height  # 480
```

### PyBullet-Specific Settings

PyBullet runs in `DIRECT` mode by default. GUI mode is enabled via `render_mode="human"`:

```python
env = make_env("scene.json", render_mode="human")
```

---

## RL Training Configuration

### Algorithm Selection

Surg-RL supports multiple RL algorithms through Stable-Baselines3:

```python
from surg_rl.rl.training import AlgorithmConfig, TrainingConfig, TrainingManager

alg_cfg = AlgorithmConfig(name="PPO")
train_cfg = TrainingConfig(
    scene_path="scenes/simple_suturing.json",
    algorithm=alg_cfg,
    total_timesteps=1_000_000,
    n_envs=4,
)

manager = TrainingManager(train_cfg)
manager.train()
```

### PPO Configuration

```python
from surg_rl.rl.training import AlgorithmConfig

alg_cfg = AlgorithmConfig(
    name="PPO",
    learning_rate=0.0003,
    n_steps=2048,
    batch_size=64,
    n_epochs=10,
    gamma=0.99,
    gae_lambda=0.95,
    clip_range=0.2,
    ent_coef=0.01,
    vf_coef=0.5,
    max_grad_norm=0.5,
)
```

### SAC Configuration

```python
alg_cfg = AlgorithmConfig(
    name="SAC",
    learning_rate=0.0003,
    buffer_size=1_000_000,
    learning_starts=100,
    batch_size=256,
    tau=0.005,
    gamma=0.99,
    train_freq=1,
    gradient_steps=1,
)
```

### TD3 Configuration

```python
alg_cfg = AlgorithmConfig(
    name="TD3",
    learning_rate=0.001,
    buffer_size=1_000_000,
    learning_starts=100,
    batch_size=100,
    tau=0.005,
    gamma=0.99,
    train_freq=1,
    gradient_steps=1,
    policy_delay=2,
    target_policy_noise=0.2,
    target_noise_clip=0.5,
)
```

### Training Settings

```python
from surg_rl.rl.training import TrainingConfig

cfg = TrainingConfig(
    scene_path="scenes/simple_suturing.json",
    algorithm=alg_cfg,
    total_timesteps=1_000_000,
    n_envs=4,
    eval_freq=10_000,
    n_eval_episodes=10,
    save_freq=50_000,
    log_dir="logs/",
    tensorboard_log="logs/tensorboard/",
    enable_tensorboard=True,
    max_episode_steps=1000,
)
```

---

## Scene Generation Configuration

### LLM Provider Configuration

```python
from surg_rl.scene_generation.text_parser import TextParser

# Uses settings from .env / environment variables
parser = TextParser(
    provider="openai",       # "openai", "anthropic", or "ollama"
    model="gpt-4",
    temperature=0.7,
    max_tokens=4096,
)
```

Supported providers and typical models:

| Provider | Typical Model |
|----------|--------------|
| openai   | gpt-4, gpt-4o |
| anthropic| claude-3-opus-20240229 |
| ollama   | llama3, llava |

### Vision Model Configuration

```python
from surg_rl.scene_generation.vision_parser import VisionParser

parser = VisionParser(
    provider="openai",
    model="gpt-4-vision-preview",
)
```

### Template and Output Settings

Scene generation output defaults to JSON or YAML based on file extension:

```python
from surg_rl.scene_generation import get_template, SceneComposer

# Start from a template
scene = get_template("suturing")

# Compose multiple inputs
composer = SceneComposer()
scene = composer.compose_sync(
    text_inputs=["Add a second instrument"],
    base_scene=scene,
)

# Save with auto-detected format
from surg_rl.scene_definition.loader import save_scene
save_scene(scene, "output/generated_scene.yaml")
```

---

## Environment Variables

Surg-RL respects the following environment variables via `.env` or the shell environment:

### API Keys

```bash
# LLM API Keys
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Runtime Settings

```bash
# Simulator backend
export DEFAULT_SIMULATOR="mujoco"   # or "pybullet"

# Rendering
export RENDER_WIDTH="640"
export RENDER_HEIGHT="480"

# RL
export RL_DEVICE="auto"
export RL_SEED="42"

# Logging
export LOG_LEVEL="INFO"             # DEBUG, INFO, WARNING, ERROR
export LOG_FILE="logs/surg_rl.log"

# Domain randomization toggle
export RANDOMIZATION_ENABLED="false"
```

### Ollama-Specific Settings

```bash
export OLLAMA_BASE_URL="http://localhost:11434"
export OLLAMA_MODEL="llama3"
export OLLAMA_VISION_MODEL="llava"
export OLLAMA_TIMEOUT="120"
```

### Accessing Variables in Code

```python
from surg_rl.utils.config import get_settings

settings = get_settings()
print(settings.default_simulator)
print(settings.llm_provider)
print(settings.log_level)
```

---

## Advanced Topics

### Custom Reward Functions

Define custom reward functions by subclassing `BaseRewardFunction`:

```python
from surg_rl.rl.rewards import BaseRewardFunction, RewardResult
import numpy as np

class CustomReward(BaseRewardFunction):
    def compute(self, observation, action, info):
        distance = np.linalg.norm(observation["target"] - observation["tool"])
        return RewardResult(
            total=-distance,
            components={"distance": -distance},
            info={},
        )

    def reset(self):
        pass
```

Register with `CompositeReward`:

```python
from surg_rl.rl.rewards import CompositeReward

reward = CompositeReward([
    (DistanceReward(), 1.0),
    (CustomReward(), 0.5),
])
```

### Custom Policies

Custom network architectures can be passed via `TrainingManager` or `AlgorithmConfig`:

```python
from surg_rl.rl.training import AlgorithmConfig

alg_cfg = AlgorithmConfig(
    name="PPO",
    policy_kwargs={"net_arch": [512, 256, 128]},
)
```

### Multi-Environment Training

Configure vectorized environments for faster training:

```python
from surg_rl.rl.environment import make_vec_env

env = make_vec_env(
    scene_path="scenes/simple_suturing.json",
    n_envs=8,
    vec_env_cls=None,  # Auto-selects SubprocVecEnv for n>1
)
```

---

## Best Practices

1. **Use Version Control**: Keep your config files and scene files in git
2. **Environment Variables**: Use env vars for secrets (API keys)
3. **Start Simple**: Begin with default configs and modify incrementally
4. **Document Changes**: Add version tags and descriptions in scene metadata
5. **Use Profiles**: Create separate configs for development, testing, production
6. **Validate Scene Files**: Run `pytest tests/test_schema.py -v` after changes
7. **Cache Carefully**: Scene generation caching is handled by `SceneLoader`; clear with `SceneLoader.clear_cache()`

### Example Project Structure

```
project/
├── configs/
│   └── default_config.yaml
├── scenes/
│   ├── simple_suturing.json
│   └── laparoscopic_dissection.yaml
├── logs/
│   └── ...
├── .env
└── src/surg_rl/
```

---

## Troubleshooting

### Common Issues

**Issue**: Configuration not loading  
Solution: Ensure `.env` is in the project root and environment variables are spelled correctly (case-insensitive). Check `Settings()` directly in a Python shell.

**Issue**: Invalid parameter value  
Solution: Check parameter types and ranges in `surg_rl.utils.config.Settings` or `surg_rl.scene_definition.schema`. Scene-level values are validated by Pydantic.

---

## See Also

- [Getting Started](GETTING_STARTED.md) — Basic setup and usage
- [API Reference](API_REFERENCE.md) — Detailed API documentation
- [Architecture](ARCHITECTURE.md) — System design overview

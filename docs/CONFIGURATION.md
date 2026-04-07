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

Surg-RL uses YAML configuration files. The default configuration is located at `configs/default_config.yaml`.

### Basic Configuration Structure

```yaml
# configs/default_config.yaml
simulation:
  backend: "mujoco"  # or "pybullet"
  timestep: 0.002
  gravity: [0, 0, -9.81]
  
rl:
  algorithm: "PPO"
  learning_rate: 0.0003
  batch_size: 64
  
scene_generation:
  llm_provider: "openai"  # or "anthropic"
  model: "gpt-4"
  
logging:
  level: "INFO"
  log_dir: "logs/"
```

### Loading Configuration

```python
from surg_rl.utils.config import load_config

# Load from file
config = load_config("configs/my_config.yaml")

# Use default config
from surg_rl.utils.config import get_default_config
config = get_default_config()
```

---

## Configuration Hierarchy

Surg-RL uses a three-tier configuration hierarchy:

1. **Default Configuration**: Built-in defaults (`configs/default_config.yaml`)
2. **User Configuration**: Custom config files override defaults
3. **Command-Line Arguments**: Highest priority, override all other settings

Example of overriding:

```python
# Start with defaults
config = get_default_config()

# Load user config (merges with defaults)
user_config = load_config("configs/custom.yaml")
config.update(user_config)

# Apply command-line overrides
if args.learning_rate:
    config["rl"]["learning_rate"] = args.learning_rate
```

---

## Core Settings

### Simulation Backend

Choose between MuJoCo and PyBullet:

```yaml
simulation:
  backend: "mujoco"  # Options: "mujoco", "pybullet"
```

**Comparison:**
- **MuJoCo**: Higher fidelity, better soft-body dynamics, faster for complex scenes
- **PyBullet**: Good for prototyping, broader community support, easier debugging

### Timestep and Physics

```yaml
simulation:
  timestep: 0.002  # Physics simulation timestep (seconds)
  gravity: [0, 0, -9.81]  # Gravity vector
  solver_iterations: 50  # Constraint solver iterations
  contact_damping: 0.5  # Contact damping coefficient
```

---

## Simulation Configuration

### MuJoCo-Specific Settings

```yaml
simulation:
  mujoco:
    # Rendering
    render_mode: "human"  # "human", "rgb_array", "depth_array"
    width: 640
    height: 480
    
    # Physics
    solver: "Newton"  # "Newton", "PGS", "CG", "LU"
    iterations: 50
    tolerance: 1e-8
    
    # Contacts
    contact_max_contacts: 100
    contact_impedance: [0.1, 0.5, 1.0]
    
    # Integration
    integrator: "RK4"  # "Euler", "implicit", "RK4"
    
    # Soft body dynamics
    soft_body_enabled: true
    soft_body_damping: 0.1
```

### PyBullet-Specific Settings

```yaml
simulation:
  pybullet:
    # Rendering
    render_mode: "human"
    width: 640
    height: 480
    
    # Physics
    solver_iterations: 50
    num_solver_iterations: 50
    
    # Real-time simulation
    real_time_simulation: false
    fixed_time_step: 0.002
    
    # GUI settings
    gui: true
    debug_visualization: true
```

---

## RL Training Configuration

### Algorithm Selection

Surg-RL supports multiple RL algorithms through Stable-Baselines3:

```yaml
rl:
  algorithm: "PPO"  # Options: "PPO", "SAC", "TD3", "DDPG", "A2C"
```

### PPO Configuration

```yaml
rl:
  algorithm: "PPO"
  learning_rate: 0.0003
  n_steps: 2048
  batch_size: 64
  n_epochs: 10
  gamma: 0.99
  gae_lambda: 0.95
  clip_range: 0.2
  ent_coef: 0.01
  vf_coef: 0.5
  max_grad_norm: 0.5
  
  # Network architecture
  policy:
    net_arch: [256, 256]  # Hidden layer sizes
    activation_fn: "tanh"  # "tanh", "relu", "elu"
```

### SAC Configuration

```yaml
rl:
  algorithm: "SAC"
  learning_rate: 0.0003
  buffer_size: 1000000
  learning_starts: 100
  batch_size: 256
  tau: 0.005
  gamma: 0.99
  train_freq: 1
  gradient_steps: 1
  
  # Entropy
  ent_coef: "auto"
  target_entropy: "auto"
```

### TD3 Configuration

```yaml
rl:
  algorithm: "TD3"
  learning_rate: 0.001
  buffer_size: 1000000
  learning_starts: 100
  batch_size: 100
  tau: 0.005
  gamma: 0.99
  train_freq: 1
  gradient_steps: 1
  
  # TD3-specific
  policy_delay: 2
  target_policy_noise: 0.2
  target_noise_clip: 0.5
```

### Training Settings

```yaml
training:
  total_timesteps: 1000000
  n_eval_episodes: 10
  eval_freq: 10000
  n_envs: 4  # Number of parallel environments
  
  # Logging
  tensorboard_log: "logs/tensorboard/"
  log_interval: 100
  
  # Checkpoints
  save_freq: 50000
  save_path: "checkpoints/"
  name_prefix: "surg_rl"
  
  # Early stopping
  early_stopping:
    enabled: true
    metric: "mean_reward"
    threshold: 900
    patience: 10
```

---

## Scene Generation Configuration

### LLM Provider Configuration

```yaml
scene_generation:
  # Provider selection
  llm_provider: "openai"  # "openai", "anthropic"
  
  # OpenAI settings
  openai:
    model: "gpt-4"
    api_key: "${OPENAI_API_KEY}"  # Use env variable
    temperature: 0.7
    max_tokens: 2000
    organization: null  # Optional
    
  # Anthropic settings
  anthropic:
    model: "claude-3-opus-20240229"
    api_key: "${ANTHROPIC_API_KEY}"
    temperature: 0.7
    max_tokens: 2000
```

### Vision Model Configuration

```yaml
scene_generation:
  vision:
    provider: "openai"  # "openai", "anthropic"
    
    openai:
      model: "gpt-4-vision-preview"
      detail: "high"  # "low", "high", "auto"
      
    anthropic:
      model: "claude-3-opus-20240229"
      detail: "original"  # "original" for full resolution
```

### Template and Output Settings

```yaml
scene_generation:
  # Templates
  templates_dir: "templates/"
  default_template: "basic_surgical"
  
  # Output
  output_format: "yaml"  # "yaml", "json"
  output_dir: "generated_scenes/"
  pretty_print: true
  
  # Validation
  validate_output: true
  strict_validation: false
  
  # Caching
  cache_enabled: true
  cache_dir: ".cache/scene_generation/"
  cache_ttl: 86400  # 24 hours
```

---

## Environment Variables

Surg-RL respects the following environment variables:

### API Keys

```bash
# LLM API Keys
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Runtime Settings

```bash
# Configuration file location
export SURG_RL_CONFIG="/path/to/config.yaml"

# Logging
export SURG_RL_LOG_LEVEL="INFO"  # DEBUG, INFO, WARNING, ERROR
export SURG_RL_LOG_DIR="/path/to/logs"

# Cache
export SURG_RL_CACHE_DIR="/path/to/cache"
export SURG_RL_CACHE_ENABLED="true"

# Parallel environments
export SURG_RL_NUM_ENVS="4"
```

### Using Environment Variables in Config

```yaml
# Reference environment variables with ${VAR_NAME}
scene_generation:
  openai:
    api_key: "${OPENAI_API_KEY}"
    
logging:
  level: "${SURG_RL_LOG_LEVEL:INFO}"  # Default to INFO if not set
  log_dir: "${SURG_RL_LOG_DIR:logs/}"
```

---

## Advanced Topics

### Custom Reward Functions

Define custom reward functions in Python:

```python
# custom_rewards.py
import numpy as np

def custom_reward(observation, action, info):
    """Custom reward function for surgical task."""
    # Distance to target
    target_pos = info["target_position"]
    tool_pos = observation["tool_position"]
    distance = np.linalg.norm(target_pos - tool_pos)
    
    # Reward components
    distance_reward = -distance
    action_penalty = -0.01 * np.sum(np.square(action))
    success_bonus = 10.0 if distance < 0.01 else 0.0
    
    return distance_reward + action_penalty + success_bonus
```

Reference in config:

```yaml
rl:
  reward_function: "custom_rewards.custom_reward"
```

### Custom Policies

Define custom network architectures:

```python
# custom_policy.py
import torch
from stable_baselines3 import PPO

class CustomPolicyExtractor:
    def __init__(self, observation_space, action_space):
        super().__init__(observation_space, action_space)
        
        # Custom network architecture
        self.policy_net = torch.nn.Sequential(
            torch.nn.Linear(observation_space.shape[0], 512),
            torch.nn.ReLU(),
            torch.nn.Linear(512, 256),
            torch.nn.ReLU(),
            torch.nn.Linear(256, action_space.shape[0])
        )
```

### Multi-Environment Training

Configure vectorized environments for faster training:

```yaml
training:
  n_envs: 8  # Number of parallel environments
  
  # Vectorized environment settings
  vec_env:
    method: "subproc"  # "subproc" or "dummy"
    start_method: "fork"  # "fork", "spawn", "forkserver"
```

### Distributed Training

For multi-GPU or distributed training:

```yaml
training:
  distributed:
    enabled: true
    backend: "nccl"  # "nccl", "gloo"
    world_size: 4  # Number of processes
    rank: 0  # Process rank
    
    # Gradient synchronization
    sync_frequency: 100
    gradient_accumulation_steps: 4
```

---

## Configuration Validation

Surg-RL validates configuration files on load. Invalid configurations will raise `ConfigurationError`.

### Validation Rules

- **Type checking**: All parameters have expected types
- **Range checking**: Numeric values must be within valid ranges
- **Dependency checking**: Related settings must be compatible
- **Required fields**: Mandatory fields must be present

### Manual Validation

```python
from surg_rl.utils.config import validate_config

# Validate configuration
try:
    validate_config(config)
except ConfigurationError as e:
    print(f"Configuration error: {e}")
```

---

## Best Practices

1. **Use Version Control**: Keep your config files in git
2. **Environment Variables**: Use env vars for secrets (API keys)
3. **Start Simple**: Begin with default configs and modify incrementally
4. **Document Changes**: Comment your config files
5. **Use Profiles**: Create separate configs for development, testing, production
6. **Validate Early**: Run validation before long training runs
7. **Cache Carefully**: Enable caching for scene generation but clear cache periodically

### Example Project Structure

```
project/
├── configs/
│   ├── default_config.yaml
│   ├── dev_config.yaml
│   ├── prod_config.yaml
│   └── experiments/
│       ├── ppo_baseline.yaml
│       └── sac_baseline.yaml
├── scenes/
│   └── ...
└── logs/
    └── ...
```

---

## Troubleshooting

### Common Issues

**Issue**: Configuration not loading
```
Solution: Check YAML syntax with a validator. Ensure file paths are correct.
```

**Issue**: Environment variable not expanding
```
Solution: Use ${VAR_NAME} syntax. Ensure variable is set in environment.
```

**Issue**: Invalid parameter value
```
Solution: Check parameter type and range in documentation. Use validate_config().
```

---

## See Also

- [Getting Started](GETTING_STARTED.md) - Basic setup and usage
- [API Reference](API_REFERENCE.md) - Detailed API documentation
- [Architecture](ARCHITECTURE.md) - System design overview

# Quick Reference Card

## Test Commands

```bash
# Activate environment
source venv/bin/activate

# Run all tests
PYTHONPATH=src pytest tests/ -v

# Run specific module tests
PYTHONPATH=src pytest tests/test_dynamics.py -v
PYTHONPATH=src pytest tests/test_schema.py -v
PYTHONPATH=src pytest tests/test_simulators.py -v

# Run with coverage
PYTHONPATH=src pytest tests/ --cov=surg_rl --cov-report=term-missing
```

## Dynamics Module Quick Start

```bash
# Test environment controller
PYTHONPATH=src python -c "
from surg_rl.dynamics import EnvironmentController
from surg_rl.scene_definition import SceneLoader

# Create from scene
loader = SceneLoader()
scene = loader.load('scenes/simple_suturing.json')
controller = EnvironmentController.from_scene(scene)

# Use in training loop
controller.start()
params = controller.reset(seed=42)
print(f'Physics: {params.physics}')
print(f'Visual: {params.visual}')
print(f'Dynamics: {params.dynamics}')
"
```

## Domain Randomization

```bash
PYTHONPATH=src python -c "
from surg_rl.dynamics import EnvironmentController, EnvironmentControllerConfig
from surg_rl.scene_definition.schema import (
    DomainRandomizationConfig,
    PhysicsRandomization,
    VisualRandomization,
    DynamicsRandomization,
)

# Configure randomization
domain_config = DomainRandomizationConfig(
    physics=PhysicsRandomization(
        enabled=True,
        mass_range=(0.9, 1.1),
        friction_range=(0.4, 0.6),
        gravity_range=((0,0,-9.81), (0,0,-10.0)),
    ),
    visual=VisualRandomization(
        enabled=True,
        color_range=(-0.1, 0.1),
        lighting_variation=(0.8, 1.2),
    ),
    dynamics=DynamicsRandomization(
        enabled=True,
        action_noise=(-0.05, 0.05),
        joint_noise=(-0.02, 0.02),
    ),
    randomize_each_episode=True,
    seed=42,
)

config = EnvironmentControllerConfig(
    use_randomization=True,
    randomization_config=domain_config,
)

controller = EnvironmentController(config=config)
controller.start()
params = controller.reset(seed=42)
print(f'Randomized physics: {params.physics}')
"
```

## Curriculum Learning

```bash
PYTHONPATH=src python -c "
from surg_rl.dynamics import (
    CurriculumScheduler,
    CurriculumConfig,
    CurriculumStage,
)

# Configure curriculum
config = CurriculumConfig(
    initial_stage=CurriculumStage.EASY,
    auto_advance=True,
    advancement_window=50,
    min_success_rate=0.7,
)

scheduler = CurriculumScheduler(curriculum_config=config)
scheduler.start()

# Check current stage
print(f'Stage: {scheduler.current_stage.value}')
print(f'Difficulty: {scheduler.current_difficulty}')

# Simulate episodes
for i in range(60):
    scheduler.reset()
    scheduler.episode_end({'success': 1, 'reward': 100}, simulator=None)

print(f'Final stage: {scheduler.current_stage.value}')
"
```

## Adaptive Difficulty

```bash
PYTHONPATH=src python -c "
from surg_rl.dynamics import AdaptiveDifficultyController, DifficultyConfig

config = DifficultyConfig(
    initial_difficulty=0.3,
    min_difficulty=0.1,
    max_difficulty=1.0,
    adaptation_rate=0.05,
    success_threshold_high=0.7,
    success_threshold_low=0.3,
)

adaptive = AdaptiveDifficultyController(difficulty_config=config)
adaptive.start()

print(f'Initial difficulty: {adaptive.difficulty}')

# Simulate good performance
for i in range(25):
    adaptive.reset()
    adaptive.episode_end({'success': 1, 'reward': 100}, simulator=None)

print(f'After good performance: {adaptive.difficulty}')
"
```

## Complete Training Loop

```bash
PYTHONPATH=src python -c "
from surg_rl.dynamics import (
    EnvironmentController,
    EnvironmentControllerConfig,
    CurriculumConfig,
    DifficultyConfig,
)
from surg_rl.scene_definition import SceneLoader
import numpy as np

# Load scene
loader = SceneLoader()
scene = loader.load('scenes/simple_suturing.json')

# Create controller with all features
config = EnvironmentControllerConfig(
    use_randomization=True,
    use_curriculum=True,
    use_adaptive_difficulty=True,
    curriculum_config=CurriculumConfig(auto_advance=True),
    difficulty_config=DifficultyConfig(adaptation_rate=0.05),
)

controller = EnvironmentController(config=config)
controller.start()

# Training loop
for episode in range(10):
    params = controller.reset(seed=episode)
    
    # Get randomized parameters
    physics = params.physics
    visual = params.visual
    dynamics = params.dynamics
    
    # Run episode...
    reward = np.random.random() * 100
    success = np.random.random() > 0.3
    
    # Episode end
    info = controller.episode_end(
        {'reward': reward, 'success': success},
        simulator=None
    )
    
    print(f'Episode {episode + 1}:')
    print(f'  Curriculum: {info.get("curriculum", {}).get("stage", "N/A")}')
    print(f'  Difficulty: {info.get("adaptive_difficulty", {}).get("new_difficulty", "N/A")}')
"
```

## Scene Loading

```bash
# Test JSON scene loading
PYTHONPATH=src python -c "
import json
from surg_rl.scene_definition import SceneDefinition

with open('scenes/simple_suturing.json') as f:
    data = json.load(f)

scene = SceneDefinition(**data)
print(f'✓ Loaded: {scene.metadata.name}')
print(f'  Robots: {len(scene.robots)}')
print(f'  Tissues: {len(scene.tissues)}')
print(f'  Instruments: {len(scene.instruments)}')
"

# Test YAML scene loading
PYTHONPATH=src python -c "
import yaml
from surg_rl.scene_definition import SceneDefinition

with open('scenes/laparoscopic_dissection.yaml') as f:
    data = yaml.safe_load(f)

scene = SceneDefinition(**data)
print(f'✓ Loaded: {scene.metadata.name}')
print(f'  Robots: {len(scene.robots)}')
"
```

## File Locations

| File | Description |
|------|-------------|
| `src/surg_rl/dynamics/` | Environment controllers (NEW) |
| `src/surg_rl/scene_definition/` | Scene schema and loader |
| `src/surg_rl/simulators/` | MuJoCo/PyBullet backends |
| `src/surg_rl/scene_generation/` | LLM/VLM parsers |
| `scenes/` | Example scene files |
| `tests/test_dynamics.py` | Dynamics module tests (NEW) |
| `docs/IMPLEMENTATION_PLAN.md` | Step-by-step guide |
| `docs/STATUS.md` | Current progress |
| `docs/DYNAMICS_API.md` | Dynamics API reference (NEW) |

## Import Examples

```python
# Import dynamics module
from surg_rl.dynamics import (
    EnvironmentController,
    ParameterRandomizer,
    CurriculumScheduler,
    AdaptiveDifficultyController,
)

# Import scene models
from surg_rl.scene_definition import (
    SceneDefinition, Metadata, PhysicsConfig,
    RobotConfig, TissueConfig, InstrumentConfig,
)

# Import domain randomization config
from surg_rl.scene_definition.schema import (
    DomainRandomizationConfig,
    PhysicsRandomization,
    VisualRandomization,
    DynamicsRandomization,
)
```

## Common Validation Errors

| Error | Fix |
|-------|-----|
| `Missing required field` | Add the missing field to your scene |
| `Input should be a valid tuple` | Use JSON array for tuples |
| `Value must be >= 0` | Check numeric field constraints |
| `Invalid enum value` | Use valid enum string (e.g., "mujoco" not "MuJoCo") |
| `Controller not started` | Call `controller.start()` before `reset()` |

## Continue Implementation

To continue with Step 7 (RL Training Pipeline):

```bash
# Read the implementation plan
cat docs/IMPLEMENTATION_PLAN.md

# Check current status
cat docs/STATUS.md

# Review the architecture
cat docs/ARCHITECTURE.md
```

## Common Commands

```bash
# Run tests
PYTHONPATH=src pytest tests/ -v

# Run specific test
PYTHONPATH=src pytest tests/test_dynamics.py::TestEnvironmentController -v

# Check imports
PYTHONPATH=src python -c "from surg_rl.dynamics import *; print('OK')"

# View module documentation
PYTHONPATH=src python -c "from surg_rl.dynamics import EnvironmentController; help(EnvironmentController)"
```

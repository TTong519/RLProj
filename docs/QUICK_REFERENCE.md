# Quick Reference Card

## Test Commands

```bash
# Activate environment
source venv/bin/activate

# Run all tests
PYTHONPATH=src pytest tests/ -v

# Run schema tests only
PYTHONPATH=src pytest tests/test_schema.py -v

# Run config tests
PYTHONPATH=src pytest tests/test_config.py -v

# Run import tests
PYTHONPATH=src pytest tests/test_imports.py -v
```

## Test Scene Loading

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

## Create a New Scene

```bash
PYTHONPATH=src python -c "
from surg_rl.scene_definition import (
    SceneDefinition, Metadata, PhysicsConfig,
    RobotConfig, RobotType, SimulatorType
)
import json

scene = SceneDefinition(
    metadata=Metadata(name='My Scene', version='1.0.0'),
    physics=PhysicsConfig(gravity=(0, 0, -9.81)),
    robots=[
        RobotConfig(name='arm1', type=RobotType.ROBOTIC_ARM, urdf_path='robot.urdf')
    ],
    simulator=SimulatorType.MUJOCO
)

# Save to file
with open('scenes/my_scene.json', 'w') as f:
    json.dump(scene.model_dump(mode='json'), f, indent=2)

print('✓ Created scenes/my_scene.json')
"
```

## Verify Schema Models

```bash
PYTHONPATH=src python -c "
from surg_rl.scene_definition import (
    SceneDefinition, Metadata,
    Position, Orientation, Pose,
    RobotConfig, TissueConfig, InstrumentConfig,
    PhysicsConfig, EnvironmentConfig
)

# Test basic creation
pos = Position(x=1.0, y=2.0, z=3.0)
print(f'✓ Position: {pos.to_tuple()}')

pose = Pose(position=Position(x=1, y=2, z=3))
print(f'✓ Pose created')

scene = SceneDefinition(metadata=Metadata(name='Test'))
print(f'✓ Scene: {scene.metadata.name}')
"
```

## File Locations

| File | Description |
|------|-------------|
| `src/surg_rl/scene_definition/schema.py` | Main schema definitions |
| `src/surg_rl/scene_definition/__init__.py` | Module exports |
| `scenes/simple_suturing.json` | Example JSON scene |
| `scenes/laparoscopic_dissection.yaml` | Example YAML scene |
| `tests/test_schema.py` | Schema validation tests |
| `docs/IMPLEMENTATION_PLAN.md` | Step-by-step guide |
| `docs/STATUS.md` | Current progress |
| `docs/DEVELOPMENT_GUIDE.md` | Dev workflow guide |
| `docs/STEP3_INSTRUCTIONS.md` | Next step instructions |

## Import Examples

```python
# Import specific models
from surg_rl.scene_definition import (
    SceneDefinition, Metadata, PhysicsConfig,
    RobotConfig, TissueConfig, InstrumentConfig,
    Position, Orientation, Pose, RgbColor,
    SimulatorType, RobotType, TissueType
)

# Import all models
from surg_rl.scene_definition import *

# Access config
from surg_rl.utils.config import get_settings
settings = get_settings()
print(settings.llm_provider)
```

## Common Validation Errors

| Error | Fix |
|-------|-----|
| `Missing required field` | Add the missing field to your scene |
| `Input should be a valid tuple` | Use JSON array for tuples, Pydantic converts |
| `Value must be >= 0` | Check numeric field constraints |
| `Invalid enum value` | Use valid enum string (e.g., "mujoco" not "MuJoCo") |

## Continue Implementation

To continue with Step 3 (Scene Generation):

```bash
# Read the step 3 instructions
cat docs/STEP3_INSTRUCTIONS.md

# Create the module directory
mkdir -p src/surg_rl/scene_generation

# Start with base parser
# Follow the order in STEP3_INSTRUCTIONS.md
```

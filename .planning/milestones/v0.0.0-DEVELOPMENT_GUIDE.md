# Development Guide

## Quick Start

### Environment Setup

```bash
# Navigate to project
cd /Users/tt/Documents/RLProj

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode (requires network)
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
PYTHONPATH=src pytest tests/ -v

# Run specific test file
PYTHONPATH=src pytest tests/test_schema.py -v

# Run with coverage
PYTHONPATH=src pytest tests/ --cov=surg_rl --cov-report=html
```

### Verify Installation

```bash
# Check CLI works
PYTHONPATH=src python -m surg_rl.cli version

# Check imports work
PYTHONPATH=src python -c "from surg_rl.scene_definition import SceneDefinition; print('OK')"
```

## Project Structure

```
RLProj/
├── src/surg_rl/           # Main source code
│   ├── __init__.py
│   ├── cli.py             # Command-line interface
│   ├── scene_definition/  # Scene schema (Step 2 - COMPLETED)
│   │   ├── __init__.py
│   │   └── schema.py      # Pydantic models
│   ├── scene_generation/  # Step 3 - TODO
│   ├── simulators/        # Step 5 - TODO
│   ├── dynamics/          # Step 6 - TODO
│   ├── rl/                # Step 7 - TODO
│   └── utils/
│       ├── config.py
│       └── logging.py
├── tests/                 # Test suite
├── scenes/                # Example scene files
├── docs/                  # Documentation
├── configs/               # Configuration files
└── examples/              # Example scripts
```

## Testing Scene Files

### Load and Validate a Scene

```python
import json
import yaml
from pathlib import Path
from surg_rl.scene_definition import SceneDefinition

# Load JSON scene
with open("scenes/simple_suturing.json") as f:
    data = json.load(f)
scene = SceneDefinition(**data)
print(f"Scene: {scene.metadata.name}")
print(f"Robots: {len(scene.robots)}")
print(f"Tissues: {len(scene.tissues)}")

# Load YAML scene
with open("scenes/laparoscopic_dissection.yaml") as f:
    data = yaml.safe_load(f)
scene = SceneDefinition(**data)
print(f"Scene: {scene.metadata.name}")
```

### Create a Minimal Scene

```python
from surg_rl.scene_definition import (
    SceneDefinition, Metadata, PhysicsConfig, SimulatorType
)

scene = SceneDefinition(
    metadata=Metadata(name="My Scene", version="1.0.0"),
    physics=PhysicsConfig(gravity=(0, 0, -9.81)),
    simulator=SimulatorType.MUJOCO
)

# Serialize to JSON
json_str = scene.model_dump_json(indent=2)
print(json_str)
```

## Development Workflow

### 1. Make Changes

Edit files in `src/surg_rl/`. The package uses `PYTHONPATH=src` for testing.

### 2. Run Tests

```bash
PYTHONPATH=src pytest tests/ -v
```

### 3. Check Imports

```bash
PYTHONPATH=src python -c "from surg_rl.scene_definition import SceneDefinition; print('OK')"
```

### 4. Format Code (optional)

```bash
# If you have ruff installed
ruff format src/
ruff check src/
```

## Common Tasks

### Add a New Model to Schema

1. Edit `src/surg_rl/scene_definition/schema.py`
2. Add the model class
3. Export it in `src/surg_rl/scene_definition/__init__.py`
4. Add tests in `tests/test_schema.py`

### Add a New Scene File

1. Create JSON or YAML file in `scenes/`
2. Ensure it validates against `SceneDefinition`
3. Test loading:

```bash
PYTHONPATH=src python -c "
import json
from surg_rl.scene_definition import SceneDefinition
with open('scenes/my_scene.json') as f:
    data = json.load(f)
scene = SceneDefinition(**data)
print(f'Valid: {scene.metadata.name}')
"
```

### Check Test Coverage

```bash
PYTHONPATH=src pytest tests/ --cov=surg_rl --cov-report=term-missing
```

## Troubleshooting

### Import Errors

If you see `ModuleNotFoundError: No module named 'surg_rl'`:

```bash
# Make sure to set PYTHONPATH
export PYTHONPATH=src
# Or run with:
PYTHONPATH=src python your_script.py
```

### Pydantic Validation Errors

If scene validation fails, Pydantic shows detailed error messages. Common issues:

1. **Missing required fields**: All required fields must be provided
2. **Wrong types**: Tuples should be lists in JSON/YAML
3. **Invalid values**: Check field constraints (e.g., `ge=0.0` means >= 0)

Example error handling:

```python
from pydantic import ValidationError
from surg_rl.scene_definition import SceneDefinition

try:
    scene = SceneDefinition(**data)
except ValidationError as e:
    print(f"Validation error: {e}")
    # e.errors() gives list of specific errors
```

### Network Issues During Install

If `pip install` fails due to network issues:

```bash
# Use existing installed packages
source venv/bin/activate

# The project already has dependencies installed
# Just set PYTHONPATH for development
export PYTHONPATH=src
```

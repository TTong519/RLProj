# Surgical Robotics RL Training System

AI-powered surgical robotics scene generation and reinforcement learning training system.

## Overview

This system generates complete simulation scenes for surgical robotics training from textual or visual input, then trains reinforcement learning models using those scenes in MuJoCo or PyBullet simulators with dynamic environment modification.

## Features

- **AI Scene Generation**: Generate surgical simulation scenes from natural language descriptions or medical images
- **Multi-Backend Simulation**: Support for both MuJoCo and PyBullet physics engines
- **Dynamic Environments**: Real-time parameter modification for robust RL training
- **Domain Randomization**: Automatic physics, visual, and dynamics randomization
- **Curriculum Learning**: Progressive difficulty adjustment during training
- **Extensible Architecture**: Modular design for easy extension

## Project Structure

```
RLProj/
├── src/surg_rl/           # Main source code
│   ├── scene_generation/  # Text/vision-based scene generation
│   ├── scene_definition/  # Scene schema and validation
│   ├── simulators/        # MuJoCo/PyBullet backends
│   ├── dynamics/          # Environment randomization
│   ├── rl/                # RL training pipeline
│   └── utils/             # Configuration and utilities
├── assets/                # Meshes, textures, materials
├── scenes/                # Generated scene files
├── configs/               # Configuration files
├── tests/                 # Test suite
└── examples/              # Example scripts and demos
```

## Installation

### Prerequisites

- Python 3.10 or higher
- pip or uv package manager

### Install

```bash
# Clone the repository
cd /Users/tt/Documents/RLProj

# Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the package
pip install -e ".[dev]"

# For vision features (optional)
pip install -e ".[vision]"
```

## Quick Start

```python
from surg_rl import get_settings

# Get configuration
settings = get_settings()
settings.ensure_directories()

print(f"Surg-RL version: {settings.model_dump()}")
```

## Configuration

Create a `.env` file in the project root:

```bash
# Copy example config
cp .env.example .env

# Edit with your settings
nano .env
```

Key configuration options:
- `LLM_PROVIDER`: LLM provider for scene generation (openai, anthropic)
- `LLM_API_KEY`: Your API key
- `DEFAULT_SIMULATOR`: Default simulator backend (mujoco, pybullet)

## Usage

### Generate Scene from Text

```bash
surg-rl generate --text "Laparoscopic cholecystectomy with da Vinci robot" --output scene.json
```

### Train RL Agent

```bash
surg-rl train --scene scene.json --algorithm PPO --timesteps 100000
```

### Evaluate Trained Agent

```bash
surg-rl evaluate --scene scene.json --model trained_model.zip --episodes 10
```

## Development

### Run Tests

```bash
pytest tests/
```

### Format Code

```bash
black src/
ruff check src/
```

### Type Check

```bash
mypy src/
```

## Architecture

The system follows a layered architecture:

1. **Scene Generation Layer**: LLM/VLM-based scene extraction from text/images
2. **Scene Definition Layer**: Schema-based scene representation
3. **Simulator Abstraction Layer**: Unified interface for physics engines
4. **Dynamic Environment Controller**: Real-time modification and randomization
5. **RL Training Pipeline**: Gymnasium environments and training integration

## Documentation

See the `docs/` directory for:
- [Implementation Plan](docs/IMPLEMENTATION_PLAN.md)
- API Reference (coming soon)
- Tutorials (coming soon)

## License

MIT License

## Contributing

Contributions welcome! Please read the implementation plan for project structure and guidelines.

## Status

This project is currently in active development. See the implementation plan for progress tracking.

## ⚠️ Quick Start - Fix Test Errors

If you see `ModuleNotFoundError: No module named 'pydantic'` when running tests, install the required packages:

```bash
pip install pydantic pydantic-settings pytest pyyaml rich typer
```

Then run tests:
```bash
pytest tests/ -v
```

For more details, see **FIX_TESTS.md** or **INSTALL.md**.


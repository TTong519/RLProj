# Getting Started with Surg-RL

This guide will help you set up Surg-RL and run your first surgical robotics simulation.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Configuration](#configuration)
5. [Next Steps](#next-steps)

## Prerequisites

Before installing Surg-RL, ensure you have:

- **Python 3.11+**: Download from [python.org](https://www.python.org/downloads/)
- **pip**: Usually comes with Python
- **Git**: For cloning the repository

### Optional Requirements

For LLM-based scene generation:
- **OpenAI API key** (for GPT models)
- **Anthropic API key** (for Claude models)
- **Ollama** (for local LLM inference)

For physics simulation:
- **MuJoCo**: Installed automatically via pip
- **PyBullet**: Installed automatically via pip

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/surg-rl.git
cd surg-rl
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate it
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
# Install in development mode with all dependencies
pip install -e ".[dev]"
```

This installs:
- Core dependencies (numpy, scipy, mujoco, pybullet, etc.)
- LLM libraries (openai, anthropic)
- Development tools (pytest, ruff, mypy)

### Step 4: Verify Installation

```bash
# Run tests
pytest tests/

# Check version
surg-rl version

# View configuration
surg-rl config
```

## Quick Start

### Option A: Use Pre-built Templates

Generate a scene from one of the built-in templates:

```bash
# Create a suturing scene
surg-rl generate --template suturing --output my_suturing.json

# Create a dissection scene
surg-rl generate --template dissection --output my_dissection.yaml

# List available templates
python -c "from surg_rl.scene_generation import list_templates; print(list_templates())"
```

### Option B: Generate with LLM

**Using OpenAI:**

```bash
# Set API key
export OPENAI_API_KEY="your-api-key"

# Generate scene
surg-rl generate --text "Create a suturing scene with a robotic arm and skin tissue" --output scene.json
```

**Using Anthropic:**

```bash
# Set API key
export ANTHROPIC_API_KEY="your-api-key"

# Generate scene
surg-rl generate --text "Design a laparoscopic training scene" --provider anthropic --output scene.json
```

**Using Ollama (Local):**

```bash
# Install and run Ollama (see https://ollama.ai)
ollama pull llama3.2

# Generate scene locally
surg-rl generate --text "Create a basic surgical training scene" --provider ollama --output scene.json
```

### Option C: Use Python API

```python
from surg_rl.scene_definition import load_scene, SceneDefinition
from surg_rl.scene_generation import get_template
from surg_rl.simulators import MuJoCoSimulator

# Method 1: Load existing scene
scene = load_scene("scenes/simple_suturing.json")

# Method 2: Use template
scene = get_template("suturing")

# Method 3: Create programmatically
from surg_rl.scene_definition import (
    Metadata, PhysicsConfig, RobotConfig, TissueConfig, Pose, Position
)

scene = SceneDefinition(
    metadata=Metadata(name="My Scene"),
    physics=PhysicsConfig(gravity=[0, 0, -9.81]),
    robots=[
        RobotConfig(
            name="arm1",
            urdf_path="assets/robots/arm.urdf",
            base_pose=Pose(position=Position(x=0, y=0, z=0))
        )
    ]
)

# Use in simulator
sim = MuJoCoSimulator()
sim.load_scene(scene)
obs = sim.reset()
```

## Configuration

### Environment Variables

Create a `.env` file from the template:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```ini
# LLM Provider (openai, anthropic, ollama)
LLM_PROVIDER=openai

# API Keys
LLM_API_KEY=your-api-key-here

# Ollama Settings (for local models)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
OLLAMA_VISION_MODEL=llava

# Simulator
DEFAULT_SIMULATOR=mujoco
```

### Python Configuration

```python
from surg_rl.utils.config import get_settings

settings = get_settings()
print(settings.llm_provider)  # 'openai'
print(settings.default_simulator)  # 'mujoco'
```

### Configuration Options

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `LLM_PROVIDER` | str | `openai` | LLM provider (openai, anthropic, ollama) |
| `LLM_MODEL` | str | `gpt-4-turbo-preview` | Model name |
| `LLM_API_KEY` | str | None | API key |
| `LLM_TEMPERATURE` | float | 0.7 | Generation temperature |
| `OLLAMA_BASE_URL` | str | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | str | `llama3.2` | Default text model |
| `OLLAMA_VISION_MODEL` | str | `llava` | Default vision model |
| `DEFAULT_SIMULATOR` | str | `mujoco` | Physics simulator |

## Next Steps

- Read the [Scene Format Documentation](SCENE_FORMAT.md) to understand scene definitions
- Check out [API Reference](API_REFERENCE.md) for detailed API docs
- See [Examples](EXAMPLES.md) for more code examples
- Learn about the [Architecture](ARCHITECTURE.md)

## Troubleshooting

### Import Errors

If you get import errors, ensure the package is installed:

```bash
pip install -e ".[dev]"
```

### LLM API Errors

**OpenAI:**
```
Error: OpenAI package not installed
```
Solution: `pip install openai`

**Anthropic:**
```
Error: Anthropic package not installed
```
Solution: `pip install anthropic`

**Ollama:**
```
Error: Connection refused
```
Solution: Ensure Ollama is running: `ollama serve`

### Simulator Errors

**MuJoCo:**
```
Error: MuJoCo is not installed
```
Solution: `pip install mujoco`

**PyBullet:**
```
Error: PyBullet is not installed
```
Solution: `pip install pybullet`

### Scene Loading Errors

```
Error: Scene file not found
```
Solution: Check the file path or use `surg-rl setup` to create directories.

```
Error: Missing mesh asset
```
Solution: This is expected - primitives are used as fallbacks. No action needed.

## Getting Help

- **GitHub Issues**: [Report bugs or request features](https://github.com/yourusername/surg-rl/issues)
- **Documentation**: Check the [docs/](docs/) folder for detailed guides
- **Examples**: See [examples/](examples/) for working code samples

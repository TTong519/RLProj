# Surg-RL: Surgical Robotics Reinforcement Learning Training System

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

**Surg-RL** is a comprehensive framework for training reinforcement learning agents in surgical robotics simulations. It provides a unified interface for scene generation, physics simulation, and RL training with support for both cloud LLM APIs and local models via Ollama.

---

## 🎯 Features

- **🤖 Multi-Provider LLM Integration**: Generate surgical scenes from natural language using OpenAI, Anthropic, or local Ollama models
- **🔬 Scene Generation**: Convert text descriptions or images into structured scene definitions
- **🎮 Unified Simulator Interface**: Seamless switching between MuJoCo and PyBullet physics engines
- **📦 Automatic Asset Fallbacks**: Scenes work even without mesh files—primitives are generated automatically
- **🔄 Domain Randomization**: Built-in support for training robust policies
- **📝 Comprehensive Schema**: Rich Pydantic models for surgical scene definitions
- **🖥️ CLI Interface**: Easy-to-use command-line tools for scene generation and training

---

## 📦 Installation

### Prerequisites

- Python 3.11 or higher
- pip package manager

### Quick Install

```bash
# Clone the repository
git clone https://github.com/yourusername/surg-rl.git
cd surg-rl

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"
```

### Optional: Local LLM Support

For local model inference without API keys:

```bash
# Install Ollama (see https://ollama.ai for installation)
ollama pull llama3.2
ollama pull llava  # For vision models
```

---

## 🚀 Quick Start

### 1. Generate a Scene from Template

```bash
# Using a predefined template
surg-rl generate --template suturing --output my_scene.json

# Available templates: suturing, dissection, manipulation
```

### 2. Generate a Scene from Text (Requires LLM)

```bash
# Using OpenAI (set OPENAI_API_KEY environment variable)
export OPENAI_API_KEY="your-api-key"
surg-rl generate --text "Create a suturing scene with two robotic arms" --output scene.json

# Using local Ollama
surg-rl generate --text "Create a simple surgical training scene" --provider ollama
```

### 3. Use in Python

```python
from surg_rl.scene_definition import load_scene, SceneDefinition
from surg_rl.scene_generation import TextParser
from surg_rl.simulators import MuJoCoSimulator

# Load a pre-defined scene
scene = load_scene("scenes/simple_suturing.json")
print(f"Scene: {scene.metadata.name}")
print(f"Robots: {len(scene.robots)}")
print(f"Tissues: {len(scene.tissues)}")

# Generate a scene from text
parser = TextParser(provider="ollama")
scene = await parser.parse("Create a suturing practice scene")

# Use in simulator
sim = MuJoCoSimulator()
sim.load_scene(scene)
obs = sim.reset()
result = sim.step(action)
```

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [Getting Started](docs/GETTING_STARTED.md) | Detailed setup and tutorial |
| [Scene Format](docs/SCENE_FORMAT.md) | Scene definition schema and examples |
| [API Reference](docs/API_REFERENCE.md) | Complete API documentation |
| [Architecture](docs/ARCHITECTURE.md) | System architecture overview |
| [Examples](docs/EXAMPLES.md) | Code examples and tutorials |
| [Contributing](CONTRIBUTING.md) | How to contribute |

---

## 🏗️ Project Structure

```
surg-rl/
├── src/surg_rl/
│   ├── scene_generation/      # LLM/VLM scene generation
│   │   ├── text_parser.py     # Text-to-scene parsing
│   │   ├── vision_parser.py   # Image-to-scene parsing
│   │   ├── templates.py       # Pre-defined scene templates
│   │   └── prompts/           # LLM prompt templates
│   ├── scene_definition/      # Scene schema and loading
│   │   ├── schema.py          # Pydantic models
│   │   └── loader.py          # Scene file loader
│   ├── simulators/            # Physics simulators
│   │   ├── base_simulator.py  # Abstract interface
│   │   ├── mujoco_simulator.py
│   │   ├── pybullet_simulator.py
│   │   └── scene_builder.py   # Scene-to-simulator conversion
│   ├── utils/                 # Utilities
│   │   ├── config.py          # Configuration
│   │   └── logging.py         # Logging
│   └── cli.py                 # Command-line interface
├── scenes/                    # Example scene files
├── tests/                     # Test suite
├── docs/                      # Documentation
└── examples/                  # Example scripts
```

---

## 🔧 Configuration

Create a `.env` file from the template:

```bash
cp .env.example .env
```

Key configuration options:

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | LLM provider (openai, anthropic, ollama) | `openai` |
| `LLM_API_KEY` | API key for OpenAI/Anthropic | - |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `OLLAMA_MODEL` | Default Ollama model | `llama3.2` |
| `DEFAULT_SIMULATOR` | Physics engine (mujoco, pybullet) | `mujoco` |

---

## 🎮 Scene Templates

Pre-built templates for common surgical scenarios:

### Suturing Template
```python
from surg_rl.scene_generation import get_template

scene = get_template("suturing")
# Includes: 1 robot, 1 tissue (skin), 1 instrument (needle driver)
```

### Dissection Template
```python
scene = get_template("dissection")
# Includes: 2 laparoscopic arms, 1 tissue (organ)
```

### Manipulation Template
```python
scene = get_template("manipulation")
# Includes: 1 robotic arm, pick-and-place task
```

---

## 🤖 LLM Integration

### Using OpenAI

```python
from surg_rl.scene_generation import TextParser

parser = TextParser(provider="openai", model="gpt-4")
scene = await parser.parse("Create a scene with a surgical robot and tissue sample")
```

### Using Anthropic

```python
parser = TextParser(provider="anthropic", model="claude-3-opus-20240229")
scene = await parser.parse("Design a laparoscopic training scenario")
```

### Using Ollama (Local)

```python
parser = TextParser(
    provider="ollama",
    model="llama3.2",
    ollama_base_url="http://localhost:11434"
)
scene = await parser.parse("Generate a basic surgical scene")
```

---

## 🎮 Simulator Usage

### MuJoCo

```python
from surg_rl.simulators import MuJoCoSimulator
from surg_rl.scene_definition import load_scene

scene = load_scene("my_scene.json")
sim = MuJoCoSimulator(assets_dir="assets")

sim.load_scene(scene)
observation = sim.reset()

# Run simulation
for _ in range(100):
    action = get_action(observation)  # Your policy
    result = sim.step(action)
    
sim.close()
```

### PyBullet

```python
from surg_rl.simulators import PyBulletSimulator

sim = PyBulletSimulator(render_mode="GUI")
sim.load_scene(scene)
observation = sim.reset()
# ... simulation loop
sim.close()
```

---

## 📝 Scene Definition

Scenes are defined using JSON or YAML files with comprehensive schema:

```yaml
# Example: surgical_scene.yaml
metadata:
  name: "Surgical Training Scene"
  description: "Basic suturing practice"
  
physics:
  gravity: [0.0, 0.0, -9.81]
  timestep: 0.002

robots:
  - name: surgical_arm
    type: robotic_arm
    urdf_path: assets/robots/surgical_arm.urdf
    base_pose:
      position: {x: 0.0, y: 0.0, z: 0.0}
    
tissues:
  - name: skin_pad
    type: skin
    geometry:
      primitive: box
      dimensions: [0.1, 0.1, 0.01]
      
task:
  name: suturing
  objectives:
    - name: needle_pickup
      description: "Pick up the surgical needle"
      weight: 1.0
```

See [Scene Format Documentation](docs/SCENE_FORMAT.md) for complete schema reference.

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/

# Run specific test module
pytest tests/test_simulators.py -v

# Run with coverage
pytest tests/ --cov=surg_rl
```

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Code of conduct
- Development setup
- Pull request process
- Coding standards

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [MuJoCo](https://mujoco.org/) - Physics simulation
- [PyBullet](https://pybullet.org/) - Physics simulation
- [Pydantic](https://pydantic-docs.helpmanual.io/) - Data validation
- [OpenAI](https://openai.com/) - GPT models
- [Anthropic](https://www.anthropic.com/) - Claude models
- [Ollama](https://ollama.ai/) - Local LLM inference

---

## 📊 Project Status

| Component | Status |
|-----------|--------|
| Scene Schema | ✅ Complete |
| Scene Generation | ✅ Complete |
| Scene Loader | ✅ Complete |
| Simulators | ✅ Complete |
| Domain Randomization | 🔄 In Progress |
| RL Training | 📋 Planned |
| CLI Demos | 📋 Planned |

---

## 📧 Contact

- **Issues**: [GitHub Issues](https://github.com/yourusername/surg-rl/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/surg-rl/discussions)

---

*Built with ❤️ for advancing surgical robotics through AI*

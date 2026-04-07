# Surg-RL: Surgical Robotics Reinforcement Learning Training System

A comprehensive framework for generating and simulating surgical robotics training scenes for reinforcement learning. Built with MuJoCo and PyBullet backends.

## Status

| Component | Status |
|-----------|--------|
| Scene Definition | ✅ Complete |
| Scene Generation (LLM/VLM) | ✅ Complete |
| Scene Loader | ✅ Complete |
| Simulator (MuJoCo/PyBullet) | ✅ Complete |
| Environment Controller | ⏳ Pending |
| RL Training | ⏳ Pending |
| Demos | ⏳ Partial |

**Current Version:** 0.1.0  
**Active Development:** Environment controller (Step 6)

## Features

- **Scene Definition**: Comprehensive JSON/YAML schema for surgical scenes
- **LLM/VLM Generation**: Generate scenes from text descriptions or images using OpenAI, Anthropic, or Ollama
- **Multi-Backend Simulation**: Unified interface for MuJoCo and PyBullet
- **Primitive Fallbacks**: Automatic primitive generation when mesh files are missing
- **Domain Randomization**: Built-in support for physics and visual randomization

## Installation

```bash
# Clone repository
git clone https://github.com/yourusername/surg-rl.git
cd surg-rl

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# Install MuJoCo (optional but recommended)
pip install mujoco
```

## Quick Start

### Run the Demo

View a surgical scene with visualization window:

```bash
# MuJoCo (opens window)
python demos/demo.py --scene scenes/simple_suturing.json

# PyBullet (opens window)  
python demos/demo.py --scene scenes/simple_suturing.json --backend pybullet

# Headless mode (no window, for testing)
python demos/demo.py --scene scenes/minimal_scene.json --headless --steps 100
```

### CLI Commands

```bash
# Show version
surg-rl version

# Show configuration
surg-rl config

# Generate scene from template
surg-rl generate --template suturing --output scene.json

# Generate scene from text (requires API key)
surg-rl generate --text "Create a suturing scene with two robots" --provider openai

# Generate using local Ollama
surg-rl generate --text "Create a scene" --provider ollama
```

### Python API

```python
from surg_rl.scene_definition import load_scene, save_scene
from surg_rl.simulators import MuJoCoSimulator

# Load a scene
scene = load_scene("scenes/simple_suturing.json")

# Create simulator
sim = MuJoCoSimulator(assets_dir="assets")
sim.load_scene(scene)

# Run simulation
obs = sim.reset()
for _ in range(100):
    result = sim.step(action=None)
    print(f"Reward: {result.reward}")

sim.close()
```

## Project Structure

```
surg-rl/
├── src/surg_rl/
│   ├── scene_definition/    # Scene schema and loader
│   │   ├── schema.py        # Pydantic models
│   │   └── loader.py        # JSON/YAML loading
│   ├── scene_generation/    # LLM/VLM scene generation
│   │   ├── text_parser.py   # Text-to-scene
│   │   └── vision_parser.py # Image-to-scene
│   ├── simulators/          # Physics backends
│   │   ├── base_simulator.py
│   │   ├── mujoco_simulator.py
│   │   └── pybullet_simulator.py
│   └── cli.py               # Command line interface
├── tests/                   # pytest tests
├── docs/                    # Documentation
├── scenes/                  # Example scene files
├── demos/                   # Demo scripts
└── examples/                # Usage examples
```

## Documentation

- [Getting Started](docs/GETTING_STARTED.md) - Installation and setup
- [API Reference](docs/API_REFERENCE.md) - Complete API documentation
- [Scene Format](docs/SCENE_FORMAT.md) - Scene file specification
- [Configuration](docs/CONFIGURATION.md) - Configuration options
- [Architecture](docs/ARCHITECTURE.md) - System architecture
- [Testing](docs/TESTING.md) - Testing guide

## Scene Files

Example scenes are provided in the `scenes/` directory:

| Scene | Description |
|-------|-------------|
| `simple_suturing.json` | Basic suturing practice scene |
| `laparoscopic_dissection.yaml` | Dual-arm laparoscopic scene |
| `minimal_scene.json` | Minimal test scene |

## Limitations

1. **Missing Assets**: The `assets/` directory doesn't include actual mesh/URDF files. The simulator uses primitive shapes (boxes, spheres, cylinders) as fallbacks.

2. **No Robot Control**: Joint control is not yet implemented. Objects remain static in demos.

3. **RL Training**: The reinforcement learning training pipeline is under development.

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_simulators.py -v
```

Current test status: **171 tests passing**

## Roadmap

- [ ] Step 6: Dynamic Environment Controller
- [ ] Step 7: RL Training Pipeline  
- [ ] Step 8: Complete CLI and Demos with robot control

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - See [LICENSE](LICENSE) for details.

<!-- generated-by: gsd-doc-writer -->

# surg-rl

**AI-powered surgical robotics scene generation and RL training system.**

End-to-end pipeline from a text description or JSON/YAML scene definition to a trained RL policy in a realistic surgical simulation. Generate scenes via LLM/VLM, train agents with Stable-Baselines3 or Ray/RLlib across MuJoCo and PyBullet backends, with domain randomization, curriculum learning, and adaptive difficulty.

[![Python](https://img.shields.io/badge/python-%E2%89%A53.10-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## Key Features

- **AI-powered scene generation** — Create surgical scenes from natural language (LLM) or images (VLM) with automatic primitive mesh fallbacks
- **Dual physics backends** — MuJoCo 3.x for high-fidelity simulation and PyBullet 3.x for soft-body/deformable tissue with unified API
- **RL training** — PPO, SAC, TD3, DDPG, and A2C via Stable-Baselines3 with Gymnasium environments
- **Distributed training** — Scale across clusters with Ray/RLlib, hyperparameter tuning, and checkpoint inspection
- **Domain randomization** — Physics, visual, and dynamics randomization for robust policy transfer
- **Curriculum & adaptive learning** — Progressive difficulty scheduling and performance-based adjustment
- **GPU acceleration** — Auto-detect CUDA, ROCm, Metal, Intel, or CPU with graceful fallback. Full Metal MPS compute on Apple Silicon for RL training
- **Real-time rendering** — Non-blocking viewer with 30 FPS throttle via render thread, macOS mjpython support
- **ROS2 bridge** — Publish/subscribe joint states and action commands for hardware-in-the-loop integration
- **ros2_control integration** — Hardware interface via controller_manager with launch file composition
- **Production deployment** — Multi-arch Docker images (amd64 + arm64), K8s manifests with GPU scheduling
- **Rich CLI** — Typer-powered `surg-rl` command with 12 subcommands and Rich-formatted output

## Quick Install

```bash
# Editable install with dev dependencies (recommended)
pip install -e ".[dev]"
```

**Without editable install**, prefix all commands with `PYTHONPATH=src`:

```bash
PYTHONPATH=src python -m surg_rl.cli version
```

Copy `.env.example` to `.env` and configure your LLM provider:

```bash
cp .env.example .env
```

## Quick Start

```bash
# Check version and GPU availability
surg-rl version --verbose

# Generate a scene from a text description
surg-rl generate --text "A robotic arm suturing tissue with a curved needle" --output my_scene.json

# Visualize a scene
python demos/demo.py --scene scenes/simple_suturing.json

# Train a PPO agent (100k timesteps)
surg-rl train --scene scenes/simple_suturing.json --algorithm PPO --timesteps 100000

# Evaluate a trained model
surg-rl evaluate --scene scenes/simple_suturing.json --model logs/training/final_model
```

## Simulator Backends

| Backend | Best for | Key Capability |
|---------|----------|----------------|
| **MuJoCo** | High-fidelity rigid-body simulation | Fast, accurate physics with GPU-accelerated rendering |
| **PyBullet** | Soft-body / deformable tissue | Tetrahedral mesh simulation with procedural VTK generation |

Switch backends via CLI flag or config:

```bash
# CLI
surg-rl train --backend pybullet --scene scenes/simple_suturing.json --algorithm PPO

# Environment variable
export DEFAULT_SIMULATOR=pybullet
```

## Optional Extras

Install additional capabilities with extras syntax:

```bash
pip install -e ".[distributed]"   # Ray/RLlib for distributed training
pip install -e ".[ros2]"          # ROS2 bridge (requires apt deps on Linux)
pip install -e ".[vision]"        # Vision-based scene parsing (torch, transformers)
pip install -e ".[llm]"           # LLM-based scene generation (openai, anthropic)
pip install -e ".[tracking]"      # Weights & Biases / MLflow experiment tracking
pip install -e ".[meshing]"       # PyVista for mesh manipulation
pip install -e ".[docs]"          # Sphinx documentation toolchain
```

Combine multiple extras:
```bash
pip install -e ".[dev,distributed,vision,llm,tracking]"
```

| Extra | Package | Description |
|-------|---------|-------------|
| `distributed` | `ray[rllib]` | Multi-node RL training and hyperparameter tuning |
| `ros2` | `PyYAML` | ROS2 bridge (requires system ROS2 installation) |
| `vision` | `torch`, `transformers` | Image-based scene parsing |
| `llm` | `openai`, `anthropic` | Text-based scene generation |
| `tracking` | `wandb`, `mlflow` | Experiment monitoring and logging |
| `meshing` | `pyvista` | Advanced mesh I/O and manipulation |
| `docs` | `sphinx` | Build documentation locally |
| `dev` | `pytest`, `ruff`, `black`, `mypy` | Development and testing tools |

## CLI Commands

| Command | Description |
|---------|-------------|
| `surg-rl version` | Show version and GPU availability |
| `surg-rl config` | Display current configuration |
| `surg-rl setup` | Create required directories |
| `surg-rl generate` | Generate surgical scenes from text/images |
| `surg-rl train` | Train an RL agent (PPO/SAC/TD3/DDPG/A2C) |
| `surg-rl evaluate` | Evaluate a trained model |
| `surg-rl train-rllib` | Distributed training with RLlib |
| `surg-rl tune` | Hyperparameter tuning |
| `surg-rl checkpoint-inspect` | Inspect RLlib checkpoint contents |
| `surg-rl ros2-bridge` | Start ROS2 bridge for hardware integration |
| `surg-rl ros2-replay` | Replay trajectory via ROS2 |
| `surg-rl ros2-control` | Start bridge with ros2_control hardware interface |

### Using ros2 launch with pip install

If you installed surg-rl via pip (not a colcon workspace), use `ROS_PACKAGE_PATH`:

```bash
ROS_PACKAGE_PATH=src ros2 launch surg_rl bridge.launch.py scene:=path/to/scene.json
ROS_PACKAGE_PATH=src ros2 launch surg_rl replay.launch.py model:=path/to/checkpoint.zip
```

For colcon workspaces, no `ROS_PACKAGE_PATH` is needed — colcon's `setup.bash` handles package discovery automatically.

## Documentation

Full documentation is available in the [`docs/`](docs/) directory:

| Document | Covers |
|----------|--------|
| [Getting Started](docs/GETTING_STARTED.md) | Installation, prerequisites, first run |
| [Architecture](docs/ARCHITECTURE.md) | System design, data flow, key abstractions |
| [API Reference](docs/API_REFERENCE.md) | Complete public API surface |
| [Scene Format](docs/SCENE_FORMAT.md) | JSON/YAML scene definition schema |
| [Configuration](docs/CONFIGURATION.md) | Environment variables and config options |
| [Dynamics API](docs/DYNAMICS_API.md) | Domain randomization, curriculum, adaptive difficulty |
| [Testing](docs/TESTING.md) | Test framework, running tests, coverage |
| [Development Guide](docs/DEVELOPMENT_GUIDE.md) | Local setup, build, code style, PR process |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common issues and solutions |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT — see [LICENSE](LICENSE) for details.

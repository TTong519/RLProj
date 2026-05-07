<!-- generated-by: gsd-doc-writer -->

# Getting Started

This guide walks you through installing Surg-RL, verifying your setup, and running your first RL training job on a surgical scene.

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| **Python** | `>= 3.10` | Check with `python3 --version` |
| **pip** | `>= 21.0` | Comes with Python; `pip --version` |
| **git** | any recent | Needed to clone the repository |
| **GPU (optional)** | CUDA / ROCm / Metal / Intel | Auto-detected; falls back to CPU gracefully |
| **ROS2 (optional)** | Humble | Linux-only; requires `apt` packages. See the [`ros2` extra](README.md#optional-extras). |

No system-level MuJoCo or PyBullet installation is needed — both are pip-installed as dependencies.

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/surg-rl/surg-rl.git
cd surg-rl
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
```

### 3. Install with dev dependencies (recommended)

```bash
pip install -e ".[dev]"
```

This editable install registers the `surg-rl` CLI command and includes all development tools (pytest, pytest-cov, pytest-asyncio, ruff, black, mypy, pre-commit).

For additional capabilities, use the extras from `pyproject.toml`:

```bash
pip install -e ".[simulation]"   # PhiFlow fluid simulation backend
pip install -e ".[meshing]"      # TetGen tetrahedral mesh generation
pip install -e ".[vision]"       # Vision-based scene parsing (torch, transformers)
pip install -e ".[llm]"          # LLM-based scene generation (openai, anthropic)
pip install -e ".[tracking]"     # W&B / MLflow experiment tracking
pip install -e ".[distributed]"  # Ray/RLlib distributed training
pip install -e ".[ros2]"         # ROS2 bridge (Linux + apt deps required)
```

Combine multiple extras:

```bash
pip install -e ".[dev,simulation,meshing,vision,llm,tracking]"
```

**Without editable install**, prefix all commands with `PYTHONPATH=src`:

```bash
PYTHONPATH=src python -m surg_rl.cli version
```

### 4. Configure your environment

```bash
cp .env.example .env
```

Edit `.env` to set your LLM provider and API key if you plan to use AI-powered scene generation. See [Configuration](CONFIGURATION.md) for the full list of settings.

## Verify Installation

```bash
surg-rl version
```

Expected output:

```
Surg-RL version: 0.1.0
```

For hardware details including GPU detection:

```bash
surg-rl version --verbose
```

This prints a table showing CUDA, ROCm, Metal, Intel, and CPU backend availability.

## First Run

Train a PPO agent on the built-in suturing scene for 100,000 timesteps:

```bash
surg-rl train --scene scenes/simple_suturing.json --algorithm PPO --timesteps 100000
```

This command does the following:
1. Loads and validates `scenes/simple_suturing.json` against the Pydantic v2 schema
2. Builds a Gymnasium environment wrapping the MuJoCo simulator (default backend)
3. Creates a PPO agent via Stable-Baselines3 with default hyperparameters
4. Trains for 100,000 timesteps, logging progress to the console
5. Saves the trained model to `logs/training/final_model`

You can also run the interactive demo scripts directly:

```bash
# Visualization demo (requires a display)
python demos/demo.py --scene scenes/simple_suturing.json

# Headless training demo (10k steps)
python demos/demo.py --headless --steps 10000

# Training demo with curriculum learning
python demos/train_demo.py --curriculum --timesteps 50000
```

## Core Concepts

Here is a quick tour of the key building blocks in Surg-RL. Each is explored in depth in the [Architecture](ARCHITECTURE.md) guide.

### Scenes

A scene describes everything in the surgical environment — robots, tissues, instruments, physics parameters, and the task definition. Scenes are written as JSON or YAML files that conform to the `SceneDefinition` Pydantic v2 schema. Shipped example scenes include `simple_suturing.json`, `suturing_demo.json`, and `minimal_scene.json`. You can also generate scenes from natural language with `surg-rl generate --text "..."` (requires an LLM API key).

### Simulators

Surg-RL supports two physics backends behind a unified `BaseSimulator` interface. **MuJoCo** (default) delivers high-fidelity rigid-body simulation with GPU-accelerated rendering and supports MuJoCo flexcomp deformables. **PyBullet** supports soft-body deformable tissue with procedural tetrahedral mesh generation and volumetric cutting. An optional **PhiFlow**-based Eulerian fluid simulator is available for bleeding/irrigation scenarios via `src/surg_rl/fluids/`. Switch backends with `--simulator pybullet` on the CLI or set `DEFAULT_SIMULATOR=pybullet` in `.env`.

### Environments

The `SurgicalEnv` class wraps a simulator into a standard Gymnasium environment. It handles the step loop — converting agent actions into simulator commands, extracting observations from the physics state, computing task-specific rewards, and detecting termination conditions. You can instantiate it directly in Python or let the `TrainingManager` create it from a `TrainingConfig`.

### Controllers

Three dynamics controllers run alongside the simulator to improve training robustness and policy transfer. **ParameterRandomizer** applies domain randomization to physics, visuals, and dynamics. **CurriculumScheduler** progresses through difficulty stages (Easy → Medium → Hard → Expert) based on success-rate windows. **AdaptiveDifficultyController** adjusts parameters in real time using performance-driven strategies. All three are orchestrated by `EnvironmentController` and toggled via training config flags.

## Simulator Backends

| Backend | Best for | Key capability |
|---|---|---|
| **MuJoCo** (default) | Rigid-body surgical robots | Fast, accurate physics; GPU-accelerated rendering |
| **PyBullet** | Deformable tissue/suturing | Soft-body simulation with procedural `.vtk` meshes |

Switch at runtime:

```bash
surg-rl train --simulator pybullet --scene scenes/simple_suturing.json --algorithm PPO
```

## v0.3.2 Features

Version 0.3.2 introduced three major simulation enhancements built on top of the core MuJoCo/PyBullet backends:

| Feature | Description | Extra required |
|---|---|---|
| **Deformable tissue** | MuJoCo flexcomp and PyBullet soft-body tetrahedral meshes via TetGen | `[meshing]` |
| **Volumetric cutting** | Plane-based surgical cuts (scalpel, scissors); configurable cooldown | built-in (PyBullet) |
| **Fluid simulation** | Eulerian grid-based fluid (PhiFlow) for bleeding/irrigation scenarios | `[simulation]` |

## Common Setup Issues

| Symptom | Likely cause | Fix |
|---|---|---|
| `surg-rl: command not found` | Editable install not run, or venv not active | `source .venv/bin/activate && pip install -e ".[dev]"` |
| `ModuleNotFoundError: No module named 'surg_rl'` | Direct Python invocation without `PYTHONPATH` | Prefix with `PYTHONPATH=src` |
| MuJoCo crashes on headless machine | No display available | Use `--headless` flag |
| PyBullet soft body fails silently | `resetSimulation` not called with `RESET_USE_DEFORMABLE_WORLD` | Internal; reload the scene and retry |
| LLM generation fails | API key not set or placeholder value in use | Edit `.env` with a real API key (placeholder values like `sk-xxxxxxxx` are rejected) |
| OpenGL errors on macOS | MuJoCo rendering backend mismatch | Install `mujoco` with `pip install mujoco`; macOS uses the `glfw` backend by default |

For more issues, see [Troubleshooting](TROUBLESHOOTING.md).

## Next Steps

| Document | What you'll learn |
|---|---|
| [Architecture](ARCHITECTURE.md) | System design, data flow, key abstractions, backend strategy |
| [Configuration](CONFIGURATION.md) | Environment variables, training config, scene schema, overrides |
| [Development Guide](DEVELOPMENT.md) | Local setup, build commands, code style, PR process |
| [Testing](TESTING.md) | Running tests, writing new tests, coverage, CI integration |
| [Scene Format](SCENE_FORMAT.md) | Detailed JSON/YAML scene definition reference |
| [Dynamics API](DYNAMICS_API.md) | Domain randomization, curriculum learning, adaptive difficulty |

Try these next:

1. **Visualize a scene** — `python demos/demo.py --scene scenes/simple_suturing.json`
2. **Generate a scene from text** — `surg-rl generate --text "A robotic arm suturing tissue" --output my_scene.json`
3. **Train with different algorithms** — `surg-rl train --scene scenes/simple_suturing.json --algorithm SAC --timesteps 500000`
4. **Evaluate a trained model** — `surg-rl evaluate --scene scenes/simple_suturing.json --model logs/training/final_model`
5. **Scale with distributed training** — `pip install -e ".[distributed]"` then `surg-rl train-rllib --scene scenes/simple_suturing.json`

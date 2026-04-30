---
focus: structure
created: 2026-04-29
---

# Structure

## Summary
Surg-RL is a `src/`-layout Python package with 7 submodules under `surg_rl/`, plus standalone `demos/`, `examples/`, `tests/`, `docs/`, `scenes/`, and `configs/` directories at repo root.

## Directory Layout

```
.
├── src/surg_rl/               # Main package (editable install target)
│   ├── __init__.py            # Version + re-exports Settings
│   ├── cli.py                 # Typer CLI entrypoint
│   ├── scene_definition/      # Schema + loader
│   │   ├── __init__.py
│   │   ├── schema.py          # Pydantic models (1080 lines)
│   │   └── loader.py          # JSON/YAML loader + cache + asset manager
│   ├── scene_generation/      # LLM/VLM scene generation
│   │   ├── __init__.py
│   │   ├── base_parser.py     # ABC for parsers
│   │   ├── text_parser.py     # OpenAI/Anthropic/Ollama text parser
│   │   ├── vision_parser.py   # VLM image parser
│   │   ├── scene_composer.py  # Multi-input scene composer
│   │   ├── templates.py       # 8 pre-built surgical templates + registry
│   │   └── prompts/
│   │       ├── __init__.py
│   │       ├── text_prompts.py
│   │       └── vision_prompts.py
│   ├── simulators/            # Physics backends
│   │   ├── __init__.py
│   │   ├── base_simulator.py  # ABC + Observation/State/StepResult dataclasses
│   │   ├── mujoco_simulator.py
│   │   ├── pybullet_simulator.py
│   │   └── scene_builder.py   # MJCF generator + primitive .obj fallback
│   ├── dynamics/              # Domain randomization / curriculum / adaptive difficulty
│   │   ├── __init__.py
│   │   ├── base_controller.py # ABC with lifecycle + parameter sampling
│   │   ├── parameter_randomizer.py
│   │   ├── curriculum.py      # 4-stage curriculum scheduler
│   │   ├── adaptive_difficulty.py
│   │   └── environment_controller.py  # Composite orchestrator
│   ├── rl/                    # Gymnasium env + SB3 training
│   │   ├── __init__.py
│   │   ├── environment.py     # SurgicalEnv
│   │   ├── observation.py     # ObservationBuilder + specs
│   │   ├── action.py          # ActionBuilder + specs
│   │   ├── rewards.py         # Reward functions + CompositeReward
│   │   ├── task_termination.py # Backend-agnostic success checker
│   │   ├── callbacks.py       # SB3 custom callbacks
│   │   └── training.py        # TrainingManager + configs
│   └── utils/                 # Shared utilities
│       ├── __init__.py
│       ├── config.py          # Pydantic-settings + .env support
│       ├── logging.py         # Rich logger setup
│       ├── mesh_generation.py # NumPy tetrahedral mesh generators
│       └── vtk_io.py          # Legacy ASCII VTK writer
│
├── tests/                     # pytest suite
│   ├── conftest.py
│   ├── test_schema.py
│   ├── test_loader.py
│   ├── test_scene_generation.py
│   ├── test_simulators.py
│   ├── test_scene_builder.py
│   ├── test_dynamics.py
│   ├── test_rl_environment.py
│   ├── test_rl_observation_action.py
│   ├── test_rl_training.py
│   ├── test_rl_callbacks.py
│   ├── test_rewards.py
│   ├── test_task_termination.py
│   ├── test_config.py
│   ├── test_cli.py
│   ├── test_cli_integration.py
│   ├── test_mesh_generation.py
│   ├── test_vtk_io.py
│   ├── test_imports.py
│   └── manual/
│       └── test_pybullet_soft_body.py
│
├── demos/                     # Runnable demonstrations
│   ├── demo.py
│   ├── train_demo.py
│   ├── eval_demo.py
│   ├── benchmark.py
│   └── README.md
│
├── examples/                  # Usage examples
│   ├── basic_usage.py
│   ├── visualize_scene.py
│   ├── rl_training.py
│   └── rl_evaluation.py
│
├── docs/                      # Markdown documentation
│   ├── ARCHITECTURE.md
│   ├── API_REFERENCE.md
│   ├── CONFIGURATION.md
│   ├── DYNAMICS_API.md
│   ├── GETTING_STARTED.md
│   ├── DEVELOPMENT_GUIDE.md
│   ├── QUICK_REFERENCE.md
│   ├── SCENE_FORMAT.md
│   ├── SOFTBODY_PLAN.md
│   ├── IMPLEMENTATION_PLAN.md
│   ├── TESTING.md
│   ├── TROUBLESHOOTING.md
│   ├── STATUS.md
│   ├── README.md
│   └── superpowers/plans/     # Historical plan docs
│
├── scenes/                    # Scene JSON/YAML files
├── configs/                   # Configuration files
├── assets/                    # Asset directory (runtime generated; no real mesh files)
├── notebooks/                 # Jupyter notebooks
├── scene_visualizations/      # Visualization outputs
├── logs/                      # Training logs
├── pyproject.toml             # Package config + dependencies
├── pytest.ini                 # pytest settings (pythonpath = src)
├── .env.example               # Environment variable template
├── README.md
├── AGENTS.md                  # Agent onboarding guide
├── CLAUDE.md                  # Claude-specific conventions
├── CHANGELOG.md
├── KNOWN_GAPS.md
│
└── .planning/                 # GSD planning artifacts
    └── codebase/
        ├── ARCHITECTURE.md
        └── STRUCTURE.md
```

## Naming Conventions

- **Modules**: Lowercase with underscores (`scene_definition`, `base_simulator`, `environment_controller`).
- **Classes**: PascalCase, often with suffix indicating role (`Simulator`, `Parser`, `Builder`, `Controller`, `Config`).
- **ABC files**: `base_*.py` (e.g., `base_simulator.py`, `base_parser.py`, `base_controller.py`).
- **Dataclasses / Pydantic models**: PascalCase, often with `Config` suffix for settings (`SceneDefinition`, `TaskConfig`, `AlgorithmConfig`).
- **Tests**: `test_*.py`, matching the module they cover (`test_schema.py` for `schema.py`).
- **Entry points**: `cli.py` for command-line; `__init__.py` exposes `__version__` and `Settings`.

## File Organization by Concern

| Concern | Where it lives |
|---------|---------------|
| Data models / schema | `src/surg_rl/scene_definition/schema.py` |
| I/O + validation + caching | `src/surg_rl/scene_definition/loader.py` |
| LLM/VLM integration | `src/surg_rl/scene_generation/` |
| Pre-built task scenes | `src/surg_rl/scene_generation/templates.py` |
| Physics abstraction | `src/surg_rl/simulators/base_simulator.py` |
| MuJoCo specifics | `src/surg_rl/simulators/mujoco_simulator.py` |
| PyBullet specifics | `src/surg_rl/simulators/pybullet_simulator.py` |
| MJCF / primitive generation | `src/surg_rl/simulators/scene_builder.py` |
| Domain randomization | `src/surg_rl/dynamics/parameter_randomizer.py` |
| Curriculum learning | `src/surg_rl/dynamics/curriculum.py` |
| Adaptive difficulty | `src/surg_rl/dynamics/adaptive_difficulty.py` |
| Dynamics orchestration | `src/surg_rl/dynamics/environment_controller.py` |
| Gymnasium environment | `src/surg_rl/rl/environment.py` |
| Observation spaces | `src/surg_rl/rl/observation.py` |
| Action spaces | `src/surg_rl/rl/action.py` |
| Reward functions | `src/surg_rl/rl/rewards.py` |
| Training pipeline | `src/surg_rl/rl/training.py` |
| SB3 callbacks | `src/surg_rl/rl/callbacks.py` |
| Task success detection | `src/surg_rl/rl/task_termination.py` |
| Application settings | `src/surg_rl/utils/config.py` |
| Logging setup | `src/surg_rl/utils/logging.py` |
| Procedural mesh gen | `src/surg_rl/utils/mesh_generation.py` |
| VTK export | `src/surg_rl/utils/vtk_io.py` |
| CLI commands | `src/surg_rl/cli.py` |

## Key Files

- `src/surg_rl/__init__.py` — Package version and top-level re-exports.
- `src/surg_rl/cli.py` — Typer CLI with `version`, `config`, `setup`, `generate`, `train`, `evaluate`.
- `src/surg_rl/scene_definition/schema.py` — 1080-line Pydantic v2 schema; the system's single source of truth for scene structure.
- `src/surg_rl/scene_definition/loader.py` — Scene file I/O, LRU cache, asset path resolution.
- `src/surg_rl/simulators/base_simulator.py` — ABC contract that all backends must implement.
- `src/surg_rl/simulators/scene_builder.py` — On-demand primitive `.obj` generation and MJCF serialization.
- `src/surg_rl/rl/environment.py` — `SurgicalEnv` (Gymnasium) and `make_env` / `make_vec_env` factories.
- `src/surg_rl/rl/training.py` — `TrainingManager` that wires SB3 algorithms, environments, and callbacks.
- `src/surg_rl/utils/config.py` — `Settings` with `.env` integration via `pydantic-settings`.
- `pyproject.toml` — Build config, dependencies, dev tools (black, ruff, mypy, pytest).
- `pytest.ini` — Adds `pythonpath = src` so tests run without `PYTHONPATH=src`.

---
focus: tech
created: 2026-04-29
---

# Stack

## Summary
Surg-RL is a pure-Python (>=3.10) project for surgical-robotics RL training. It uses a `src/` layout, setuptools build backend, and pip as the package manager. The core stack spans simulation (MuJoCo / PyBullet), RL training (Gymnasium / Stable-Baselines3), data validation (Pydantic v2), scene generation (LLM client SDKs + httpx), and a Typer/Rich CLI.

## Languages
| Language | Usage |
|----------|-------|
| Python   | 100 % of application code (`src/`, `tests/`, `demos/`, `examples/`) |
| Bash     | Git pre-commit hook (`.githooks/pre-commit`) |
| YAML     | Configuration templates (`configs/default_config.yaml`) |
| JSON     | Scene definitions and asset manifests (`scenes/`, `assets/`) |

## Runtime & Package Manager
- **Python:** `>=3.10` (supports 3.10, 3.11, 3.12)
- **Package manager:** `pip` (no Poetry, no Pipenv)
- **Virtual environment:** `venv` (convention in README)
- **Build backend:** `setuptools>=61.0` with `wheel`
- **Editable install:** `pip install -e ".[dev]"`

## Directory Layout (src/)
```
src/surg_rl/
├── __init__.py
├── cli.py                       # Typer CLI entrypoint
├── scene_definition/            # Pydantic v2 schema + JSON/YAML loader
├── scene_generation/            # LLM/VLM text & vision parsers, templates, prompts
├── simulators/                  # MuJoCo & PyBullet backends, scene_builder (MJCF/URDF)
├── dynamics/                    # Domain randomization, curriculum, adaptive difficulty
├── rl/                          # Gymnasium env, SB3 training, observations, actions, rewards
└── utils/                       # Config (Pydantic Settings), logging (Rich), mesh_generation, vtk_io
```

## Core Frameworks & Libraries

### Simulation
- **MuJoCo** (`mujoco>=3.0.0`) — Primary physics backend; used via `mujoco_simulator.py`
- **PyBullet** (`pybullet>=3.2.5`) — Secondary backend with soft-body support; used via `pybullet_simulator.py`

### Reinforcement Learning
- **Gymnasium** (`gymnasium>=0.29.0`) — Environment API (`rl/environment.py`, `rl/observation.py`, `rl/action.py`)
- **Stable-Baselines3** (`stable-baselines3>=2.0.0`) — Training algorithms (PPO, SAC, TD3, DDPG, A2C) in `rl/training.py`, `rl/callbacks.py`

### Data Validation & Configuration
- **Pydantic v2** (`pydantic>=2.0.0`, `pydantic-settings>=2.0.0`) — Scene schema (`scene_definition/schema.py`), app settings (`utils/config.py`)
- **PyYAML** (`pyyaml>=6.0`) — Scene serialization
- **tomli / tomli-w** — TOML read/write for Python <3.11 and config export
- **python-dotenv** (`python-dotenv>=1.0.0`) — `.env` file loading

### CLI & UX
- **Typer** (`typer>=0.9.0`) — CLI framework (`cli.py`)
- **Rich** (`rich>=13.0.0`) — Console output, tables, styled logging (`utils/logging.py`)
- **tqdm** (`tqdm>=4.65.0`) — Progress bars

### Image Processing
- **Pillow** (`pillow>=10.0.0`) — Image I/O for scene generation
- **OpenCV** (`opencv-python>=4.8.0`) — Vision preprocessing

### Scientific Computing
- **NumPy** (`numpy>=1.24.0`) — Array math throughout simulators and RL
- **SciPy** (`scipy>=1.11.0`) — Scientific utilities

## Build & Development Tools
| Tool | Config File | Purpose |
|------|-------------|---------|
| pytest | `pytest.ini` + `pyproject.toml` [tool.pytest.ini_options] | Test runner; `pythonpath = src` |
| black | `pyproject.toml` [tool.black] | Code formatting; line-length 100 |
| ruff | `pyproject.toml` [tool.ruff] + [tool.ruff.lint] | Linting (E, F, I, N, W, UP, B, C4, SIM) |
| mypy | `pyproject.toml` [tool.mypy] | Type checking; pydantic plugin enabled |
| pre-commit | `.githooks/pre-commit` | Custom bash hook (import-corruption guard + affected-test runner) |

## Optional Dependency Groups
| Group | Packages | Purpose |
|-------|----------|---------|
| `dev` | pytest, pytest-cov, pytest-asyncio, black, ruff, mypy, pre-commit | Development & testing |
| `llm` | openai, anthropic | LLM scene generation |
| `vision` | torch, torchvision, transformers | VLM / local vision model support |
| `docs` | sphinx, sphinx-rtd-theme, myst-parser | Documentation generation |

## Configuration Files
- `pyproject.toml` — Build metadata, dependencies, tool configs (black, ruff, mypy, pytest)
- `requirements.txt` — Minimal runtime + testing deps
- `requirements-dev.txt` — Includes `requirements.txt` + dev tools
- `pytest.ini` — Test paths, pythonpath, markers (integration)
- `configs/default_config.yaml` — Default simulator / rendering / training YAML template
- `.env.example` — Environment variable template for external services

## Key Files
- `pyproject.toml` — Project metadata, dependencies, and tool configuration
- `pytest.ini` — pytest runner configuration with `pythonpath = src`
- `src/surg_rl/__init__.py` — Package root; exports `Settings`, `get_settings`
- `src/surg_rl/cli.py` — Typer CLI (`surg-rl` command)
- `src/surg_rl/scene_definition/schema.py` — Pydantic v2 scene schema (1080 lines)
- `src/surg_rl/simulators/mujoco_simulator.py` — MuJoCo backend (860 lines)
- `src/surg_rl/simulators/pybullet_simulator.py` — PyBullet backend (1299 lines)
- `src/surg_rl/rl/training.py` — SB3 training manager (570 lines)
- `src/surg_rl/rl/environment.py` — Gymnasium `SurgicalEnv` wrapper (656 lines)
- `src/surg_rl/utils/config.py` — Pydantic Settings with `.env` support (260 lines)
- `.githooks/pre-commit` — Bash pre-commit hook with import-corruption guard

## Dependencies
| Package | Spec | Purpose |
|---------|------|---------|
| numpy | >=1.24.0 | Array math |
| scipy | >=1.11.0 | Scientific utilities |
| mujoco | >=3.0.0 | Primary physics simulator |
| pybullet | >=3.2.5 | Secondary physics simulator |
| gymnasium | >=0.29.0 | RL environment API |
| stable-baselines3 | >=2.0.0 | RL algorithms (PPO, SAC, etc.) |
| openai | >=1.0.0 | OpenAI GPT API client |
| anthropic | >=0.18.0 | Anthropic Claude API client |
| pillow | >=10.0.0 | Image I/O |
| opencv-python | >=4.8.0 | Vision preprocessing |
| pydantic | >=2.0.0 | Data validation / settings |
| pydantic-settings | >=2.0.0 | Pydantic-based config |
| pyyaml | >=6.0 | YAML serialization |
| tomli | >=2.0.0 (<3.11) | TOML parsing |
| tomli-w | >=1.0.0 | TOML writing |
| tqdm | >=4.65.0 | Progress bars |
| rich | >=13.0.0 | Styled console output |
| python-dotenv | >=1.0.0 | `.env` file loading |
| typer | >=0.9.0 | CLI framework |
| httpx | * (transitive / optional) | HTTP client for Ollama (imported lazily) |
| pytest | >=7.0.0 | Testing |
| pytest-cov | >=4.0.0 | Coverage |
| pytest-asyncio | >=0.21.0 | Async test support |
| black | >=23.0.0 | Formatting |
| ruff | >=0.1.0 | Linting |
| mypy | >=1.0.0 | Type checking |
| pre-commit | >=3.5.0 | Git hooks (dev convenience) |
| sphinx | >=7.0.0 | Documentation |
| sphinx-rtd-theme | >=2.0.0 | Docs theme |
| myst-parser | >=2.0.0 | Markdown-in-docs |
| torch | >=2.0.0 (optional) | Vision model inference |
| torchvision | >=0.15.0 (optional) | Vision transforms |
| transformers | >=4.35.0 (optional) | Hugging Face models |

## Notes
- No JavaScript/TypeScript, no Docker, no Makefile, no Justfile, no `package.json`.
- GitHub Actions workflows are not present (only issue/PR templates in `.github/`).
- The package is **not** installed site-wide by default; editable install is required for the `surg-rl` CLI to be available on `$PATH`.

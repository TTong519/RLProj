<!-- generated-by: gsd-doc-writer -->
# Development Guide

Surg-RL follows a **src/-layout** convention (`src/surg_rl/` contains all source code). This is a Python >=3.10 project using setuptools + pyproject.toml with Pydantic v2, MuJoCo 3.x / PyBullet 3.x backends, and Stable-Baselines3.

## Local Setup

1. **Fork and clone** the repository, then create a virtual environment:

   ```bash
   git clone <!-- VERIFY: {repository URL} -->/surg-rl.git
   cd surg-rl
   python -m venv venv
   source venv/bin/activate    # Windows: venv\Scripts\activate
   ```

2. **Install in editable mode** with dev dependencies:

   ```bash
   pip install -e ".[dev]"
   ```

   The `-e` flag makes the `surg-rl` CLI command available globally in your venv.

3. **Copy environment file** and configure your LLM provider:

   ```bash
   cp .env.example .env
   ```

   Edit `.env` to set `LLM_PROVIDER` and `LLM_API_KEY` (openai / anthropic / ollama). See [Configuration](CONFIGURATION.md) for all variables.

4. **Verify the installation**:

   ```bash
   surg-rl version
   # Without editable install, use:
   # PYTHONPATH=src python -m surg_rl.cli version
   ```

### Working without editable install

If you skip `pip install -e`, you must prefix **every command** with `PYTHONPATH=src`:

```bash
PYTHONPATH=src python -m surg_rl.cli version
PYTHONPATH=src python demos/demo.py --headless --steps 0
PYTHONPATH=src pytest tests/ -v
```

`pytest.ini` already sets `pythonpath = src`, so `pytest` works without the env var — but direct Python script invocations still require it.

## Project Structure

```
src/surg_rl/
├── cli.py                 # Typer CLI application (11 subcommands)
├── render_thread.py       # Non-blocking rendering thread (30 FPS throttle)
│
├── scene_definition/      # Pydantic v2 schema + JSON/YAML loader
│   ├── schema.py          # SceneDefinition, RobotConfig, TissueConfig, etc.
│   └── loader.py          # SceneLoader with caching
│
├── scene_generation/      # AI-powered scene creation
│   ├── base_parser.py     # Abstract parser interface
│   ├── text_parser.py     # LLM-based text→scene (OpenAI/Anthropic/Ollama)
│   ├── vision_parser.py   # VLM-based image→scene
│   ├── scene_composer.py  # Orchestrates template + parser output
│   ├── templates.py       # Built-in scene templates
│   └── prompts/           # LLM prompt templates
│
├── simulators/            # Physics backends (Strategy pattern)
│   ├── base_simulator.py  # Abstract base class (BaseSimulator ABC)
│   ├── mujoco_simulator.py     # MuJoCo 3.x backend
│   ├── pybullet_simulator.py   # PyBullet 3.x + soft-body support
│   └── scene_builder.py        # Procedural MJCF/URDF generation
│
├── rl/                    # RL training pipeline
│   ├── environment.py     # Gymnasium Env wrapper
│   ├── training.py        # Stable-Baselines3 training loop
│   ├── observation.py     # Observation space builder
│   ├── action.py          # Action space builder
│   ├── rewards.py         # Reward functions
│   ├── callbacks.py       # SB3 training callbacks
│   ├── task_termination.py  # Success/failure detection
│   └── rllib/             # Ray/RLlib integration (distributed extra)
│       ├── config.py      # RLlib algorithm configs
│       ├── env_wrapper.py # GymEnv→RLlib env adapter
│       ├── train.py       # RLlib training entry point
│       ├── tune_integration.py  # Hyperparameter tuning
│       └── checkpoint_utils.py  # Checkpoint inspection
│
├── dynamics/              # Domain randomization & curriculum
│   ├── base_controller.py       # Controller ABC
│   ├── environment_controller.py  # Orchestrator (ties components together)
│   ├── parameter_randomizer.py   # Physics/visual/dynamics randomization
│   ├── curriculum.py             # Progressive difficulty scheduling
│   └── adaptive_difficulty.py    # Performance-based adjustments
│
├── ros2/                  # ROS2 bridge (ros2 extra)
│   ├── bridge_node.py     # ROS2 node (joint states + actions)
│   ├── config.py          # ROS2 topic/qos configuration
│   └── replay.py          # Trajectory replay via ROS2
│
└── utils/                 # Shared utilities
    ├── config.py          # Pydantic-settings configuration
    ├── logging.py         # Rich-based structured logging
    ├── mesh_generation.py # PyBullet soft-body mesh generation
    ├── vtk_io.py          # Procedural VTK tet-mesh writer
    └── gpu.py             # GPU auto-detection (CUDA/ROCm/Metal/Intel)
```

Key directories outside the package:

```
tests/          # Pytest suite (40+ test files)
scenes/         # Example scene files (JSON/YAML)
demos/          # Demo scripts (demo.py for interactive visualization)
examples/       # Example scripts and notebooks
configs/        # YAML configuration files
docs/           # Project documentation
```

## Build Commands

Surg-RL does not have a compile step — it is pure Python. The key commands are:

| Command | Description |
|---------|-------------|
| `pip install -e ".[dev]"` | Install package in editable mode with all dev tools |
| `surg-rl version` | Verify installation and check GPU availability |
| `PYTHONPATH=src pytest tests/ -m "not integration" -v` | Run unit tests (skip integration) |
| `PYTHONPATH=src pytest tests/ -v` | Run full test suite |
| `PYTHONPATH=src pytest tests/test_simulators.py -v` | Run a single test file |
| `PYTHONPATH=src pytest tests/ --cov=surg_rl --cov-report=html` | Run tests with coverage report |
| `ruff check src/ tests/` | Lint all source and test files |
| `black --check src/ tests/` | Check formatting compliance |
| `mypy src/surg_rl` | Static type checking |

## Code Style

Surg-RL enforces code quality with three tools. Run them in this order before committing:

### Ruff (linter)

```bash
ruff check src/ tests/
```

Configuration is in `pyproject.toml` under `[tool.ruff]`:
- **Line length:** 100
- **Target:** Python 3.10+
- **Rules:** E, F, I, N, W, UP, B, C4, SIM (E501 ignored — handled by Black)

To auto-fix issues:

```bash
ruff check src/ tests/ --fix
```

### Black (formatter)

```bash
black --check src/ tests/
```

Configuration in `[tool.black]`:
- **Line length:** 100
- **Target:** Python 3.10–3.12

To auto-format:

```bash
black src/ tests/
```

**Important:** Always run `black` before `ruff` when auto-fixing — `ruff format` is not used in this project; only `ruff check` is configured.

### Mypy (type checker)

```bash
mypy src/surg_rl
```

Configuration in `[tool.mypy]`:
- **Python version:** 3.10
- **Strictness:** `disallow_untyped_defs = true`, `warn_return_any = true`
- **Plugins:** `pydantic.mypy` (for Pydantic v2 model support)

### Pre-commit Hook

A Git pre-commit hook is available at `.githooks/pre-commit`. Enable it with:

```bash
git config core.hooksPath .githooks
```

The hook performs two checks automatically:

1. **Import corruption guard** — rejects literal `\n` characters in Python source files, a common artifact of shell-based multi-line injection.
2. **Affected test runner** — runs only tests whose module imports trace to staged changes. Example: if you change files in `src/surg_rl/simulators/`, only `tests/test_simulators.py` runs.

No `.pre-commit-config.yaml` is used — the hook is managed directly via the `.githooks/` directory.

## Running Tests

```bash
# Full test suite (skip integration tests)
PYTHONPATH=src pytest tests/ -m "not integration" -v

# Full test suite including integration
PYTHONPATH=src pytest tests/ -v

# Single test file
PYTHONPATH=src pytest tests/test_simulators.py -v

# Single test function
PYTHONPATH=src pytest tests/test_schema.py::test_scene_validation -v

# With coverage
PYTHONPATH=src pytest tests/ --cov=surg_rl --cov-report=term-missing

# Run only integration tests
PYTHONPATH=src pytest tests/ -m integration -v
```

**Key test conventions** (see [Testing Guide](TESTING.md) for full details):

- `pytest.ini` sets `pythonpath = src` and `asyncio_mode = "auto"`
- Integration tests are marked `@pytest.mark.integration`
- PyBullet soft-body tests use `@pytest.mark.xfail` on macOS/CI (they currently XPASS on macOS)
- Prefer feature-specific test files over cross-cutting ones
- YAML invalid test strings must be **genuinely** invalid — `"key: [invalid"` (unclosed bracket) is correct

## Optional Extras

Install additional capabilities using pip extras syntax. Multiple extras can be combined:

```bash
pip install -e ".[dev,distributed,vision,llm,tracking]"
```

| Extra | Command | Description |
|-------|---------|-------------|
| `distributed` | `pip install -e ".[distributed]"` | Ray/RLlib for multi-node distributed training with hyperparameter tuning |
| `ros2` | `pip install -e ".[ros2]"` | ROS2 bridge — requires `apt install ros-humble-*` and `source /opt/ros/humble/setup.bash` |
| `vision` | `pip install -e ".[vision]"` | Vision-based scene parsing (torch, torchvision, transformers) |
| `llm` | `pip install -e ".[llm]"` | LLM-based scene generation (openai, anthropic) |
| `tracking` | `pip install -e ".[tracking]"` | Weights & Biases and MLflow experiment tracking |
| `meshing` | `pip install -e ".[meshing]"` | PyVista for advanced mesh I/O and manipulation |
| `docs` | `pip install -e ".[docs]"` | Sphinx documentation toolchain with rtd theme and MyST parser |

## Adding New Features

### Adding a Simulator Backend

1. Create a new module in `src/surg_rl/simulators/` (e.g., `isaac_simulator.py`).
2. Subclass `BaseSimulator` (ABC) and implement all abstract methods: `load_scene()`, `reset()`, `step()`, `get_observation()`, `close()`, `render()`, `get_state()`, `set_state()`, and `get_visual_meshes()`.
3. Data carriers (`Observation`, `State`, `StepResult`, `SimulationStatus`) are defined in `base_simulator.py` — use them directly.
4. Test for backend identity with a unique attribute (pattern: `MuJoCoSimulator` uses `_model`, `PyBulletSimulator` uses `_physics_client`).
5. Add tests in `tests/` — follow existing simulator test patterns. Register in `.githooks/pre-commit` under the `check_tests` calls.
6. Update CLI in `cli.py` to accept the new backend name.

### Adding an RL Algorithm

1. Open `src/surg_rl/rl/training.py` — the `AlgorithmConfig` dataclass defines per-algorithm hyperparameters. Add or extend config fields.
2. The `train()` function dispatches to SB3 classes (PPO, SAC, TD3, DDPG, A2C). Add the new algorithm branch following the existing pattern.
3. Add tests in `tests/test_rl_training.py` or a feature-specific test file.
4. If the algorithm has an RLlib equivalent, add config in `src/surg_rl/rl/rllib/config.py` and training logic in `src/surg_rl/rl/rllib/train.py`.

### Adding a Scene Type

1. Define the new Pydantic model in `src/surg_rl/scene_definition/schema.py`.
2. Use `model_construct()` to skip validation when needed (the **only** way in Pydantic v2).
3. In `model_validator(mode="after")`, mutate via `self.model_copy(update={...})` — never mutate `self` in place.
4. Export the model in `src/surg_rl/scene_definition/__init__.py`.
5. Add a template entry in `src/surg_rl/scene_generation/templates.py` if the scene type should be generatable.
6. Add JSON/YAML example scenes in `scenes/`.
7. Add tests in `tests/test_schema.py` and loader tests in `tests/test_loader.py`.

## Branch Conventions

- **Main branch:** `main`
- **Feature branches:** `feature/<description>` (e.g., `feature/add-isaac-backend`)
- **Bug fix branches:** `fix/<description>` (e.g., `fix/pybullet-reset-race`)
- **Refactor branches:** `refactor/<description>`

Use conventional commit message prefixes: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`, `ci:`.

Example:

```bash
git checkout -b feature/add-isaac-backend
# ... make changes ...
git commit -m "feat: add NVIDIA Isaac Sim simulator backend"
```

## PR Process

1. **Run quality checks locally:**
   ```bash
   ruff check src/ tests/
   black --check src/ tests/
   mypy src/surg_rl
   ```

2. **Run tests:**
   ```bash
   PYTHONPATH=src pytest tests/ -m "not integration" -v
   ```

3. **Push and create a pull request** against `main` with a descriptive title and summary:
   - What changes were made and why
   - Link to any related issues
   - Note breaking changes or new dependencies

4. **CI will run automatically** — GitHub Actions executes the same checks (ruff, black, mypy, pytest) across Python 3.10, 3.11, and 3.12. All must pass before merge.

5. **Review process:**
   - At least one maintainer must approve
   - Address all review comments
   - Squash-merge into `main` after approval

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the full contributor guide.

## CI (Continuous Integration)

GitHub Actions workflow: `.github/workflows/ci.yml`

**Trigger:** Push to `main` and pull requests against `main`

**Matrix:** Python 3.10, 3.11, 3.12 (runs all three in parallel)

**Steps (per Python version):**

| Step | Command |
|------|---------|
| Lint | `ruff check src/ tests/` |
| Format | `black --check src/ tests/` |
| Type check | `mypy src/surg_rl` |
| Test | `pytest tests/ -m "not integration" -v` |

CI also caches pip dependencies keyed on `pyproject.toml` hash. Integration tests are explicitly excluded from CI due to LLM API and hardware requirements.

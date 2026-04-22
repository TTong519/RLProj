# CLAUDE.md — surg-rl

## Project Overview

Surgical robotics RL training system. Generates/simulates surgical scenes with MuJoCo + PyBullet backends, domain randomization, and curriculum learning. Python 3.10+, Pydantic v2, Stable-Baselines3.

## Commands

```bash
# Install
pip install -e ".[dev]"

# Tests (PYTHONPATH=src is required for direct script runs; pytest.ini handles it for pytest)
PYTHONPATH=src pytest tests/ -v
PYTHONPATH=src pytest tests/test_dynamics.py -v          # single file
PYTHONPATH=src pytest tests/ --cov=surg_rl                # coverage
PYTHONPATH=src pytest tests/ -m integration -v            # integration only
PYTHONPATH=src pytest tests/ -m "not integration" -v      # skip integration

# CLI
surg-rl version
surg-rl config
surg-rl generate --template suturing --output scene.json
surg-rl generate --text "Create a suturing scene" --provider openai
surg-rl train --scene scenes/simple_suturing.json --algorithm PPO
surg-rl evaluate --model models/ppo_model.zip

# Demo (always use --headless when no display)
python demos/demo.py --scene scenes/minimal_scene.json --headless --steps 100

# Lint & type check
ruff check src/ tests/
black --check src/ tests/
mypy src/surg_rl
```

## Architecture

```
src/surg_rl/
├── scene_definition/     schema.py (Pydantic models), loader.py (JSON/YAML + cache)
├── scene_generation/     text_parser.py, vision_parser.py, scene_composer.py, templates.py, base_parser.py
├── simulators/           base_simulator.py (ABC), mujoco_simulator.py, pybullet_simulator.py, scene_builder.py
├── dynamics/             base_controller.py (ABC), parameter_randomizer.py, curriculum.py, adaptive_difficulty.py, environment_controller.py
├── rl/                   environment.py (Gymnasium), training.py (SB3), observation.py, action.py, rewards.py, callbacks.py
├── utils/                config.py (Settings), logging.py (Rich)
└── cli.py                Typer app
```

## Rules & Guidelines

### Pydantic v2
- `Model(**data)` and `Model.model_validate(data)` both perform full validation — they are NOT different paths
- To actually skip validation, use `Model.model_construct(**data)` — but beware: nested dicts remain as plain dicts, not sub-models
- In `model_validator(mode="after")`, use `self.model_copy(update={...})` instead of mutating `self` — Pydantic may internally copy the model
- Enum values in `model_dump()` stay as Enum objects, not `.value` strings — must convert before YAML serialization (`yaml.dump` will raise `RepresenterError`)

### Gymnasium / Stable-Baselines3
- `MlpPolicy` requires a flat `Box` observation space — use `MultiInputPolicy` for `Dict` spaces
- Always call `simulator.load_scene(scene)` after creating the simulator — `reset()`/`step()` will raise `RuntimeError` otherwise
- Observation/action spaces must be defined in `__init__` before any `reset()` call (Gymnasium requirement)

### Simulator internals
- MuJoCoSimulator stores its model as `_model` (private), not `model` — use `hasattr(simulator, "_model")` to detect MuJoCo backends
- PyBulletSimulator uses `_physics_client` (private) — use `hasattr(simulator, "_physics_client")` to detect PyBullet backends
- Scene assets (meshes, URDFs) don't exist in this repo — `scene_builder` generates OBJ primitives as fallbacks; don't assume real asset files

### Optional fields — always guard
- `InstrumentConfig.pose` is `Optional[Pose]` — default `None`; always check before accessing `.position`
- `SceneDefinition.task` is `Optional[TaskConfig]` — default `None`; always check before accessing `.name`, `.objectives`, etc.
- `RobotConfig.base_pose` has a default factory (always present) — safe to access without guard

### Domain randomization / controllers
- Use `EnvironmentController.apply_parameters(snapshot, simulator)` — do NOT access private `_randomizer` directly
- `ControllerConfig.warmup_episodes` (not `warmup_steps`) — the comparison is against episode count, not step count
- `CurriculumScheduler.DEFAULT_STAGES` uses mutable dataclass values — always `copy.deepcopy()`, never `dict.copy()`

### Imports
- Multi-line parenthesized imports: always verify the opening parenthesis (`from .module import (` not `from .module import`)
- The `rl` subpackage's `__init__.py` imports from `environment.py` — a syntax error there breaks the entire import chain
- Never use `sed` or `echo -e` to inject multi-line import blocks; use `python -c "import pathlib; pathlib.Path('file').write_text(...)"` or the `Edit` tool directly

### Testing
- When testing `validate=False` paths with `model_construct`, remember that nested fields are plain dicts — use `metadata.get("name")` or `hasattr(metadata, "name")` guards
- YAML "invalid" test strings must actually be invalid — `"key: value\n  nested: invalid"` is valid YAML (multiline scalar); use `"key: [invalid"` (unclosed bracket) instead
- When making an ABC method a `@staticmethod`, update the test call to remove the `self`/`None` argument
- When appending test classes to an existing file from a parallel branch, first `read` the file to check for overlapping class names and import ordering
- Test files that cover cross-cutting concerns (`test_simulators.py`, `test_scene_generation.py`) are high-conflict — prefer feature-specific files (`test_soft_body.py`, `test_joint_control.py`) when possible, and import them into the main test file

### Scene composition
- When merging scenes with a `base_scene`, iterate over ALL scenes (`for scene in scenes`), not `scenes[1:]` — the base already provides the starting point, so `scenes[0]` should not be skipped

### Parallel Development
- When running parallel agents on git worktrees, ALWAYS use Python scripts (`python -c "..."`) for multi-line file edits — `sed` with `\n` produces literal backslash-n characters that corrupt Python imports
- Before spawning parallel agents, check `git ls-files` for files likely to collide (e.g., `scene_builder.py`, `test_simulators.py`) and either:
  - Assign disjoint file sets to each agent, OR
  - Have one agent own the shared file and the others write patches
- After parallel agents finish, merge in dependency order: schema → simulators → scene_generation → rl → tests. Run `pytest` after each merge, not just at the end
- Limit per-agent debug loops to 3 attempts; if not resolved, halt and re-examine assumptions rather than adding print statements

### Algorithms
- Algorithm names are normalized to uppercase internally (`algo_name = name.upper()`) — always compare against the uppercase version in downstream conditionals

## Code Style

- Line length: 100 (black + ruff)
- Python: >=3.10
- Type hints required (`mypy disallow_untyped_defs = true`)
- ruff select: E, F, I, N, W, UP, B, C4, SIM; ignore E501
- pytest `asyncio_mode = auto`

## Environment Variables

Copy `.env.example` to `.env`. Key variables:
- `LLM_PROVIDER` / `LLM_API_KEY` — scene generation (openai, anthropic, ollama)
- `DEFAULT_SIMULATOR` — mujoco or pybullet
- `RANDOMIZATION_ENABLED` — toggle domain randomization

## Known Limitations

- `assets/` has no real mesh files; simulators use primitive shape fallbacks
- Scene generation requires API keys (OpenAI/Anthropic) or local Ollama
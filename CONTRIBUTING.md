<!-- generated-by: gsd-doc-writer -->

# Contributing to surg-rl

Thank you for your interest in contributing to **surg-rl**, the AI-powered surgical
robotics scene generation and RL training system. This document covers the
workflow, tools, and conventions we use.

## Code of Conduct

Please read our [Code of Conduct](CODE_OF_CONDUCT.md) before contributing. We are
committed to providing a welcoming and harassment-free experience for everyone.

## Development Setup

The fastest way to get started:

```bash
git clone https://github.com/surg-rl/surg-rl.git
cd surg-rl
python -m venv venv
source venv/bin/activate

# Editable install with dev + GUI dependencies (recommended for v0.5.0+)
pip install -e ".[dev,gui]"

# Copy environment template
cp .env.example .env
```

**Without editable install**, prefix direct Python invocations with `PYTHONPATH=src`:

```bash
PYTHONPATH=src python -m surg_rl.cli version
PYTHONPATH=src python demos/demo.py --headless --steps 0
```

For the full local development guide, see [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).
For first-run instructions, see [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md).

## Branch / PR Workflow

1. **Fork the repository** (or create a feature branch if you have write access).
2. **Create a feature branch** from `main`. We use the `codex/` prefix by default:
   `git checkout -b codex/my-feature`.
3. **Run the lint / type / test trio** before pushing:
   ```bash
   ruff check src/ tests/
   black --check src/ tests/
   mypy src/surg_rl
   ```
4. **Commit** with a clear message following conventional-commit style
   (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`).
5. **Push** and open a pull request. Fill in the PR template and ensure CI passes.
6. **Request review** from a maintainer. Address feedback and squash fix commits if asked.

## GSD Workflow Overview

This project is managed with **GSD** (Goal-Space Development). Large changes flow
through three stages:

1. **`/gsd-discuss-phase N`** — Gather context, decisions, and scope fences.
2. **`/gsd-plan-phase N`** — Produce executable `PLAN.md` files.
3. **`/gsd-execute-phase N`** — Run the plans, verify, and ship.

User-facing documentation phases (like Phase 34) also produce README, CONTRIBUTING,
and CHANGELOG artifacts. Check `.planning/ROADMAP.md` for the current milestone and
`.planning/STATE.md` for the active phase.

## Coding Standards

### Lint / Format / Type

Run these in order before every push:

```bash
ruff check src/ tests/
black --check src/ tests/
mypy src/surg_rl
```

Apply auto-fixes with:

```bash
black src/ tests/
ruff check src/ tests/ --fix
```

All three checks are enforced in CI.

### Pre-commit Hook

Enable the Git pre-commit hook at `.githooks/pre-commit`:

```bash
git config core.hooksPath .githooks
```

The hook guards against literal `\n` characters in Python source and runs affected tests.

## Optional Dependency Matrix

| Extra | What it adds | Typical use |
|-------|--------------|-------------|
| *(none)* | Core runtime: MuJoCo, PyBullet, Gymnasium, SB3, NumPy, SciPy | Production inference |
| `dev` | pytest, black, ruff, mypy, pre-commit | Local development |
| `gui` | PySide6 >=6.8.0, markdown-it-py >=3.0.0 | Scene editor (`surg-rl-gui`) |
| `marl` | PettingZoo, SuperSuit | Multi-agent RL |
| `dreamer` | dreamerv3, jax, tensorflow | DreamerV3 world-model training |
| `ros2` | launch, launch_ros, PyYAML | ROS2 hardware-in-the-loop bridge |
| `simulation` | PhiFlow, scikit-image | Eulerian fluids + cutting |
| `distributed` | Ray, RLlib | Distributed training |
| `vision` | torch, transformers | VLM-based scene parsing |
| `llm` | openai, anthropic | LLM-based scene generation |
| `tracking` | wandb, mlflow | Experiment tracking |
| `meshing` | trimesh | Real mesh asset loading |
| `docs` | sphinx | Documentation toolchain |
| `benchmark` | matplotlib, seaborn, pandas, rliable | Benchmark reporting |

Combine extras:

```bash
pip install -e ".[dev,gui,marl]"
```

## Project-Specific Conventions

### Pydantic v2

- `Model.model_construct(**data)` is the **only** way to skip validation entirely.
- In `model_validator(mode="after")`, mutate via `self.model_copy(update={...})` — never
  mutate `self` in place.
- `model_dump()` returns **Enum objects**, not `.value` strings. Convert before YAML
  serialization.

### Optional Field Guards

Always guard before accessing nested attributes on these:

- `InstrumentConfig.pose` — default `None`
- `SceneDefinition.task` — default `None`
- `TissueConfig.physics.pybullet` — override fields (`mass`, `scale`, `sim_mesh_path`)
  default to `None`

### Simulator Backends

- **MuJoCo** stores model as `_model`. Test with `hasattr(simulator, "_model")`.
- **PyBullet** stores client as `_physics_client`. Test with `hasattr(simulator, "_physics_client")`.
- Scene assets do **not** exist in `assets/` — `scene_builder` generates primitive `.obj`
  fallbacks on the fly. Never assume a real asset file exists.
- `simulator.load_scene(scene)` must be called before `reset()` or `step()`, or it raises
  `RuntimeError`.

### Gymnasium / Stable-Baselines3

- `MlpPolicy` requires a flat `Box` observation space — use `MultiInputPolicy` for `Dict` spaces.
- Observation/action spaces must be defined in `__init__` before any `reset()` call.

## Testing

- Framework: **pytest** (>=7.0.0)
- Test files follow the `test_*.py` pattern in `tests/`.
- `pytest.ini` auto-adds `src/` to `PYTHONPATH`, so `pytest tests/` works without
  environment variables — but direct Python script invocations still need `PYTHONPATH=src`.
- Add feature-specific test files where possible: prefer `test_soft_body.py` over
  `test_simulators.py`.
- PyBullet soft-body tests are marked `@pytest.mark.xfail` on macOS; do not remove the marker.

## Documentation

User-facing docs live at the repo root and under `docs/`:

- `README.md` — project landing page
- `CONTRIBUTING.md` — this file
- `CHANGELOG.md` — release notes
- `docs/GETTING_STARTED.md` — extended setup
- `docs/DEVELOPMENT.md` — extended dev guide
- `docs/API_REFERENCE.md` — API reference
- `docs/ARCHITECTURE.md` — system architecture

When you add a new CLI flag, environment variable, or public API, update the relevant
doc file in the same PR.

## Getting Help

- Open a [GitHub Discussion](https://github.com/surg-rl/surg-rl/discussions) for questions.
- Open a [GitHub Issue](https://github.com/surg-rl/surg-rl/issues) for bugs or feature requests.
- See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for common errors.

---

*Thanks for contributing to surgical robotics RL research!*

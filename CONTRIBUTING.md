<!-- generated-by: gsd-doc-writer -->

# Contributing to surg-rl

Thank you for your interest in contributing! This document outlines the conventions, tools, and process for contributing to the surgical robotics RL training system.

## Code of Conduct

Please read our [Code of Conduct](CODE_OF_CONDUCT.md) before contributing. We are committed to providing a welcoming and harassment-free experience for everyone.

## Development Setup

See [Getting Started](docs/GETTING_STARTED.md) for prerequisites and first-run instructions, and [Development Guide](docs/DEVELOPMENT.md) for the full local development setup. The quick start:

```bash
# Clone and set up a virtual environment
git clone https://github.com/surg-rl/surg-rl.git
cd surg-rl
python -m venv venv
source venv/bin/activate

# Editable install with dev dependencies
pip install -e ".[dev]"

# Copy environment template
cp .env.example .env
```

**Without editable install**, prefix all commands with `PYTHONPATH=src`:

```bash
PYTHONPATH=src python -m surg_rl.cli version
PYTHONPATH=src python demos/demo.py --headless --steps 0
```

## Coding Standards

### Code Style

- **Ruff** — Linter and import sorter. Run: `ruff check src/ tests/`
- **Black** — Formatter with line length 100. Run: `black --check src/ tests/` (check) or `black src/ tests/` (apply)
- **Mypy** — Static type checker with strict settings (`disallow_untyped_defs = true`, `warn_return_any = true`). Run: `mypy src/surg_rl`

All three checks are enforced in CI. Run them locally in this order before pushing:

```bash
ruff check src/ tests/
black --check src/ tests/
mypy src/surg_rl
```

For auto-fixing:

```bash
black src/ tests/
ruff check src/ tests/ --fix
```

### Pre-commit Hook

A Git pre-commit hook is available at `.githooks/pre-commit`. Enable it with:

```bash
git config core.hooksPath .githooks
```

The hook performs two checks automatically:

1. **Import corruption guard** — rejects literal `\n` characters in Python source files, a common artifact of shell-based multi-line injection.
2. **Affected test runner** — runs only tests whose module imports trace to staged changes (e.g., changes in `src/surg_rl/simulators/` trigger `tests/test_simulators.py`).

### Project-Specific Conventions

When contributing code, follow these patterns from the project's working conventions:

**Pydantic v2:**
- `Model.model_construct(**data)` is the **only** way to truly skip validation. `Model(**data)` and `Model.model_validate(data)` are equivalent — both validate.
- In `model_validator(mode="after")`, mutate via `self.model_copy(update={...})` — never mutate `self` in place.
- `model_dump()` returns **Enum objects**, not `.value` strings. Convert before YAML serialization.

**Optional field guards** — always guard before accessing nested attributes on these:
- `InstrumentConfig.pose` — default `None`
- `SceneDefinition.task` — default `None`
- `TissueConfig.physics.pybullet` — override fields (`mass`, `scale`, `sim_mesh_path`) default to `None`

**Simulator backends:**
- **MuJoCo** stores model as `_model` (private). Test backend identity with `hasattr(simulator, "_model")`.
- **PyBullet** stores client as `_physics_client`. Test with `hasattr(simulator, "_physics_client")`.
- Scene assets (URDFs/meshes) **do not exist** in `assets/` — `scene_builder` generates primitive `.obj` fallbacks on the fly. Never assume a real asset file exists.
- `simulator.load_scene(scene)` must be called before `reset()` or `step()`, or it raises `RuntimeError`.

**Gymnasium / Stable-Baselines3:**
- `MlpPolicy` requires a flat `Box` observation space — use `MultiInputPolicy` for `Dict` spaces.
- Observation/action spaces must be defined in `__init__` before any `reset()` call.

### Testing

- Test framework: **pytest** (≥7.0.0)
- Test files follow the pattern `test_*.py` in the `tests/` directory
- `pytest.ini` auto-adds `src/` to `PYTHONPATH`, so `pytest tests/` works without environment variables — but direct Python script invocations still need `PYTHONPATH=src`
- Prefer **feature-specific test files** over cross-cutting ones to reduce merge conflicts (e.g., `test_soft_body.py` rather than a monolithic `test_simulators.py`)
- Integration tests are marked with `@pytest.mark.integration` and can be skipped with `-m "not integration"`
- Slow tests are marked with `@pytest.mark.slow`
- YAML invalid test strings must be **genuinely** invalid — `"key: [invalid"` (unclosed bracket) is correct; `"key: value\n  nested: invalid"` is valid YAML (multiline scalar) and incorrect

Run the test suite:

```bash
# Full test suite
PYTHONPATH=src pytest tests/ -v

# Skip integration tests
PYTHONPATH=src pytest tests/ -m "not integration" -v

# Specific file or pattern
PYTHONPATH=src pytest tests/test_simulators.py -v
PYTHONPATH=src pytest tests/ -k "test_mesh" -v

# With coverage
PYTHONPATH=src pytest tests/ --cov=surg_rl --cov-report=term-missing
```

## Code Review Rules

When reviewing pull requests:

- Do **not** flag intentional design choices as bugs. Ask clarifying questions before labeling something as a bug.
- Constants, tolerances, and magic numbers should be assumed deliberately chosen unless proven otherwise.
- Verify that optional fields are guarded before accessing nested attributes (see [Project-Specific Conventions](#project-specific-conventions) above).
- Check for Pydantic v2 correctness: `model_construct` for skipping validation, `model_copy(update={...})` for after-validators.
- Ensure `@pytest.mark.integration` is added to tests that require LLM APIs or external services.
- Before spawning parallel agents, check `git ls-files` for collision-prone files and assign disjoint file sets.

## Pull Request Guidelines

1. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make your changes**, including tests for new functionality and updates to docstrings and relevant docs.

3. **Run the full quality check suite** before submitting:
   ```bash
   ruff check src/ tests/
   black --check src/ tests/
   mypy src/surg_rl
   PYTHONPATH=src pytest tests/ -m "not integration" -v
   ```

4. **Write a clear PR description** following the PR template, including:
   - Summary of changes and motivation
   - Type of change (bug fix, feature, breaking change, docs, refactor, performance, tests)
   - Test configuration: OS, Python version, simulation backend
   - Completion of the checklist (code style, self-review, comments, docs, tests, no new warnings)

5. **CI will run automatically** — GitHub Actions executes the same checks (ruff, black, mypy, pytest) across Python 3.10, 3.11, and 3.12. All must pass before merge.

6. **Respond to review feedback**. Maintainers will review your PR; address all comments before merge.

The PR template is available at [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md).

## Issue Reporting

The project uses GitHub Issues with templates for bug reports and feature requests.

### Bug Reports

Use the **Bug report** template. Include:

- Clear description of the bug
- Steps to reproduce (minimal working example if possible)
- Expected vs. actual behavior
- Environment: OS, Python version, surg-rl version, simulation backend (MuJoCo or PyBullet)
- Log output or error traceback

Before submitting, search existing issues to avoid duplicates.

### Feature Requests

Use the **Feature request** template. Include:

- What problem the feature would solve
- Description of the proposed solution
- Alternatives you have considered
- Whether you are willing to submit a PR (yes / need guidance / just suggesting)

For significant new features, consider opening an issue for discussion before starting implementation to get early feedback from maintainers.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).

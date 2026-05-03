<!-- generated-by: gsd-doc-writer -->

# Contributing to surg-rl

Thank you for your interest in contributing! This document outlines the conventions, tools, and process for contributing to the surgical robotics RL training system.

## Code of Conduct

Please read our [Code of Conduct](CODE_OF_CONDUCT.md) before contributing. We are committed to providing a welcoming and harassment-free experience for everyone.

## Development Setup

See [Getting Started](docs/GETTING_STARTED.md) for prerequisites and first-run instructions, and [Development Guide](docs/DEVELOPMENT_GUIDE.md) for the full local development setup. The quick start:

```bash
# Clone and set up a virtual environment
git clone https://github.com/YOUR_USERNAME/surg-rl.git
cd surg-rl
python -m venv venv
source venv/bin/activate

# Editable install with dev dependencies
pip install -e ".[dev]"

# Copy environment template
cp .env.example .env
```

## Coding Standards

### Code Style

- **Ruff** — Linter and import sorter. Run: `ruff check src/ tests/`
- **Black** — Formatter with line length 100. Run: `black --check src/ tests/` (check) or `black src/ tests/` (apply)
- **Mypy** — Static type checker with strict settings (`disallow_untyped_defs = true`). Run: `mypy src/surg_rl`

All three checks are enforced in CI. Run them locally before pushing:

```bash
ruff check src/ tests/
black --check src/ tests/
mypy src/surg_rl
```

### Testing

- Test framework: **pytest** (≥7.0.0)
- Test files follow the pattern `test_*.py` in the `tests/` directory
- `pytest.ini` auto-adds `src/` to `PYTHONPATH`, so `pytest tests/` works without environment variables
- Prefer **feature-specific test files** over cross-cutting ones (e.g., `test_soft_body.py` rather than a monolithic `test_simulators.py`)
- Integration tests are marked with `@pytest.mark.integration` and can be skipped with `-m "not integration"`
- Slow tests (>10s) are marked with `@pytest.mark.slow`

Run the test suite:

```bash
# Full test suite
pytest tests/ -v

# Skip integration tests
pytest tests/ -m "not integration" -v

# Specific file or pattern
pytest tests/test_simulators.py -v
pytest tests/ -k "test_mesh" -v
```

## Pull Request Guidelines

1. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feat/my-feature
   ```

2. **Make your changes**, including tests for new functionality and updates to docstrings and relevant docs.

3. **Run the full quality check suite** before submitting:
   ```bash
   ruff check src/ tests/
   black --check src/ tests/
   mypy src/surg_rl
   pytest tests/ -m "not integration" -v
   ```

4. **Write a clear PR description** following the PR template, including:
   - Summary of changes and motivation
   - Type of change (bug fix, feature, breaking change, docs, refactor, performance, tests)
   - Test configuration: OS, Python version, simulation backend
   - Completion of the checklist (code style, self-review, comments, docs, tests, no new warnings)

5. **Respond to review feedback**. Maintainers will review your PR; address all comments before merge.

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

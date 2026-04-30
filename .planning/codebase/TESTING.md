---
focus: testing
created: 2026-04-29
---

# Testing

## Summary
Surg-RL uses pytest with `pythonpath = src`, `pytest-cov` for coverage, and `pytest-asyncio` for async CLI tests. Tests are organized by feature in `tests/test_*.py` files with class-based grouping. Mocking mixes `unittest.mock` (in-process) and subprocess CLI invocation. Integration tests are marked with `@pytest.mark.integration`; PyBullet soft-body tests use `@pytest.mark.xfail` on macOS/CI.

## Test Framework & Configuration
- **Runner:** pytest with `pythonpath = src` (`pytest.ini` and `[tool.pytest.ini_options]`).
- **Config sources:** `pytest.ini` (primary) and `pyproject.toml` (duplicated options).
- **Key options:**
  - `testpaths = tests`
  - `python_files = test_*.py`
  - `addopts = -v --tb=short`
  - `asyncio_mode = auto`, `asyncio_default_fixture_loop_scope = function`
- **Markers:** `integration: marks tests as integration tests (deselect with '-m "not integration"')`.

## Test File Organization
- **Feature-specific files:** Preferred over cross-cutting to reduce merge conflicts (`test_soft_body.py` > `test_simulators.py`).
- **Current files:**
  - `tests/test_schema.py` — Pydantic model construction, validation, serialization round-trips.
  - `tests/test_simulators.py` — MuJoCo / PyBullet init, scene loading, joint control, soft body MJCF, rendering, regression bug tests.
  - `tests/test_scene_builder.py` — MJCF generation, asset resolution, camera/light insertion.
  - `tests/test_loader.py` — JSON/YAML load/save, cache eviction, asset validation, convenience functions.
  - `tests/test_rl.py` — Observation/action spaces, reward computation, vectorized env, callbacks, training config.
  - `tests/test_rewards.py` — Suturing, dissection, needle-passing rewards, branch coverage.
  - `tests/test_dynamics.py` — Curriculum, adaptive difficulty, parameter randomization, edge cases.
  - `tests/test_cli.py` — Subprocess CLI tests (version, config, setup, generate, train, evaluate).
  - `tests/test_cli_integration.py` — In-process mocked CLI tests using `typer.testing.CliRunner`.
  - `tests/test_vtk_io.py` — VTK unstructured grid read/write round-trips.
  - `tests/test_imports.py` — Smoke import tests for all submodules.
- **Manual tests:** `tests/manual/test_pybullet_soft_body.py` (excluded from normal collection).

## Test Structure & Classes
- **Class-based grouping:** Every test file defines `class TestXxx:` with focused docstrings. Example: `class TestObservation:`, `class TestMuJoCoSimulator:`.
- **Method naming:** `test_` prefix + descriptive snake_case (`test_load_scene_creates_joints`).
- **Docstrings:** Each test method has a one-line docstring describing intent.
- **Subprocess CLI tests:** `class TestCLIVersion:` groups commands executed via `cli_runner` fixture.
- **Edge-case classes:** Dedicated classes for branch coverage (`TestDistanceRewardBranches`, `TestCurriculumEdgeCases`, `TestAdaptiveDifficultyEdgeCases`).

## Fixtures
- **Shared fixtures:** Defined in `tests/conftest.py`:
  - `cli_runner` — Runs CLI commands via `subprocess.run` with `PYTHONPATH=src`.
  - `cli_env` — Returns `os.environ` copy with `PYTHONPATH=src`.
  - `minimal_scene` — Loads `scenes/minimal_scene.json` via `SceneLoader`.
  - `suturing_scene` — Loads `scenes/simple_suturing.json` via `SceneLoader`.
- **Built-in pytest fixtures:** `tmp_path` (file I/O), `monkeypatch` (attribute patching).
- **Fixture scope:** All shared fixtures are function-scoped.

## Mocking Patterns
- **`unittest.mock`:**
  - `MagicMock` / `AsyncMock` for object behavior (`mock_parser.parse = AsyncMock(return_value=scene)`).
  - `patch("surg_rl.cli.TextParser")` to inject fake scene generation.
  - `monkeypatch.setattr(module.Class, "method", mock)` for training manager / callback patching.
- **`pytest.MonkeyPatch` context:** Used in CLI subprocess tests for temporary env changes.
- **PyBullet mocking:** Extensive mock of `pybullet` module via `sim._pb = mock.MagicMock()` to test joint control and quaternion order without launching physics.
- **Module suppression:** `patch.dict("sys.modules", {"pybullet": None})` to test fallback branches.

## Markers & Test Categories
- **`@pytest.mark.integration`** — Integration tests that require external services or heavy compute. Skipped via `-m "not integration"`.
- **`@pytest.mark.xfail(sys.platform in ("darwin",) or os.environ.get("CI") == "true", reason="...")`** — PyBullet soft-body tests are expected to fail on macOS / CI due to auto-tetgen instability. On macOS these currently produce **XPASS**; do not remove the marker.
- **Direct python invocations:** For scripts and demos, `PYTHONPATH=src` is required because the package is not installed site-wide by default.

## Coverage & Quality
- **Coverage tool:** `pytest-cov` (`pytest-cov>=4.0.0`).
- **Branch coverage tests:** Explicit classes (`TestDistanceRewardBranches`, `TestActionPenaltyBranches`) exercise else/except/unknown-shape paths.
- **Regression tests:** Named `TestPyBulletBugs` / `TestMuJoCoReset` with docstrings referencing bug numbers (`Bug 1: createMultiBody primitive fallback must pass [x, y, z, w]`).

## Test Utilities & Helpers
- **`_convert_tuples_for_yaml(obj)`** — Recursively converts tuples and enums to lists/strings for YAML serialization in loader tests.
- **`assert result.returncode == 0`** / **`assert result.exit_code == 0, result.output`** — Standard assertions for subprocess vs in-process CLI tests.
- **`pytest.approx`** used for float comparisons (`assert np.allclose(...)`, `pytest.approx(0.6, abs=0.01)`).
- **`np.random.seed` poisoning tests:** Assert that environment reset does not call `np.random.seed()` globally.

## Key Files
- `pytest.ini` — pytest runner config, pythonpath, markers.
- `pyproject.toml` — `tool.pytest.ini_options`, dev dependencies (`pytest`, `pytest-cov`, `pytest-asyncio`).
- `tests/conftest.py` — Shared fixtures (`cli_runner`, `minimal_scene`, `suturing_scene`).
- `tests/test_cli_integration.py` — Mocked integration tests using `typer.testing.CliRunner` and `unittest.mock`.
- `tests/test_simulators.py` — `@pytest.mark.xfail` soft-body tests and regression bug coverage.
- `tests/test_rl.py` — Vectorized environment creation and seeding/reproducibility tests.
- `tests/test_rewards.py` — Branch coverage for reward shapes and penalty types.
- `tests/test_loader.py` — Cache eviction, YAML serialization edge cases, exception class tests.
- `tests/test_imports.py` — Smoke import tests asserting `__version__` and submodule presence.

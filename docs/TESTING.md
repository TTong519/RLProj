<!-- generated-by: gsd-doc-writer -->

# Testing

## Test runner and configuration

The project uses **pytest** (>=7.0.0) with **pytest-asyncio** and **pytest-cov**. Configuration lives in two places:

- **`pytest.ini`** — primary configuration file at the project root
- **`pyproject.toml`** `[tool.pytest.ini_options]` — contains testpaths, python_files, addopts, and asyncio_mode, but does NOT mirror pythonpath, asyncio_default_fixture_loop_scope, or markers from pytest.ini

```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
pythonpath = src                     # auto-adds src/ to PYTHONPATH
addopts = -v --tb=short              # verbose, short tracebacks
asyncio_mode = auto                  # automatic async test handling
asyncio_default_fixture_loop_scope = function
markers =
    integration: marks tests as integration tests (deselect with '-m "not integration"')
    slow: marks tests as slow (>10s)
```

Because `pythonpath = src` is set, running `pytest tests/` works without manually setting
`PYTHONPATH`. Direct Python script invocations (not via pytest) still need `PYTHONPATH=src`.

## Running tests

### Full suite (skip integration)

```bash
# pytest.ini auto-adds src/ — no PYTHONPATH needed
pytest tests/ -v

# Quiet mode (summary only)
PYTHONPATH=src pytest tests/ -q

# Skip integration tests
pytest tests/ -m "not integration" -v

# Skip slow tests
pytest tests/ -m "not slow" -v
```

### Single file or pattern

```bash
pytest tests/test_simulators.py -v
pytest tests/test_mesh_generation.py -v
pytest tests/test_schema.py -v
pytest tests/test_cutting.py -v
pytest tests/test_deformable.py -v
```

### Subdirectory (fluid tests)

```bash
pytest tests/test_fluids/ -v
```

### From a clean environment (no editable install)

```bash
PYTHONPATH=src pytest tests/ -v
```

### Watch / debug mode

```bash
pytest tests/ --pdb           # drop into debugger on first failure
pytest tests/ -m "not integration" --lf   # re-run only last failures
```

## Test module inventory

As of the most recent run: **910 passed, 11 skipped**.

| Test file | What it tests | Lines |
|---|---|---|
| `test_simulators.py` | MuJoCo and PyBullet backends, soft body, step/reset | 1,391 |
| `test_dynamics.py` | Domain randomization, curriculum, adaptive difficulty | 1,092 |
| `test_rl.py` | RL module — agents, policies, training loops | 1,005 |
| `test_scene_generation.py` | LLM parsers, templates, scene composer, error handling | 764 |
| `test_schema.py` | Pydantic v2 scene definition schema, enums, validators | 687 |
| `test_loader.py` | SceneLoader (JSON/YAML + cache), asset manager | 629 |
| `test_ros2_bridge.py` | ROS2 bridge config, import guard, bridge node (mocked) | 573 |
| `test_rl_environment.py` | SurgicalEnv wrapper, observation/action/config | 484 |
| `test_deformable.py` | Deformable config schema, MuJoCo FEM, PyBullet flex | 480 |
| `test_rewards.py` | Reward functions (suturing, dissection, needle passing) | 434 |
| `unit/test_rendering.py` | Rendering output verification | 399 |
| `test_ros2_replay.py` | Trajectory replay, speed throttling, ROS2 publishing | 378 |
| `test_rl_training.py` | TrainingConfig, RllibConfig, environment wrappers | 362 |
| `test_task_geometry.py` | Task geometry binding to observation fields | 355 |
| `test_cutting.py` | Volumetric tetrahedral mesh cutting (intersection, engine) | 272 |
| `test_real_assets.py` | Real asset loading with fallback and deduplicated warnings | 223 |
| `test_scene_builder.py` | MJCF/URDF generation, asset resolution | 220 |
| `test_gpu_detector.py` | GPU backend detection (CUDA, Metal, ROCm, Intel) | 215 |
| `test_tetgen_integration.py` | Tetgen mesh generation and integration | 205 |
| `test_tracking_callbacks.py` | W&B / MLflow tracking callbacks | 190 |
| `test_fluids/test_fluid_simulator.py` | Fluid simulator integration | 186 |
| `test_gpu_integration.py` | GPU integration (Metal on macOS, CUDA path) | 180 |
| `test_rl_observation_action.py` | ObservationBuilder, ActionBuilder, config coverage | 170 |
| `test_kubernetes_manifests.py` | Kubernetes manifest validation | 165 |
| `test_cli_integration.py` | Mocked CLI integration (LLM monkey-patching) | 151 |
| `test_environment_controller.py` | EnvironmentController, mode/policy switching | 150 |
| `test_task_termination.py` | Task success/failure termination, distance criteria | 148 |
| `test_rl_callbacks.py` | SB3 callbacks (curriculum, checkpoint, eval, tensorboard) | 141 |
| `test_action_reconciliation.py` | Action reconciliation between backends | 141 |
| `test_rllib_env_registration.py` | RLlib env factory, registration (mocked) | 133 |
| `test_rllib_train.py` | RLlib training entrypoint, GPU auto-config | 129 |
| `test_mesh_generation.py` | Procedural tetrahedral mesh generators (box/cylinder/sphere) | 128 |
| `test_rllib_tune.py` | Tune search space building, experiment config | 101 |
| `test_fluids/test_schema.py` | Fluid configuration schema validation | 96 |
| `test_rllib_checkpoint.py` | RLlib checkpoint metadata inspection | 93 |
| `test_ros2_launch.py` | ROS2 launch file generation and validation | 90 |
| `test_rllib_cli.py` | RLlib CLI commands (train/tune/eval via subprocess) | 90 |
| `manual/test_pybullet_soft_body.py` | Manual PyBullet soft-body stress tests | 89 |
| `test_logging.py` | Sensitive data filtering in log records | 88 |
| `test_config.py` | Settings singleton, path resolution, env var loading | 85 |
| `test_ros2_controller.py` | EnvironmentController ROS2 mode switching | 80 |
| `test_vtk_io.py` | VTK unstructured grid read/write roundtrip | 76 |
| `test_ros2_control.py` | ROS2 control interface and bridge | 73 |
| `test_ci_config.py` | CI configuration validation | 69 |
| `test_imports.py` | Package and submodule import verification | 45 |
| `test_ros2_cli.py` | ROS2 CLI help output, error cases | 44 |
| `test_rllib_install.py` | `[distributed]` extra resolution check | 37 |
| `test_ray_address.py` | Ray address resolution | 30 |
| `test_release_workflow.py` | Release workflow validation | 27 |
| `test_cli.py` | CLI commands via Typer CliRunner | 24 |

## Markers

| Marker | Purpose | Deselect |
|---|---|---|
| `integration` | Integration tests (real simulators, GPU, LLM calls, subprocess) | `-m "not integration"` |
| `slow` | Tests exceeding ~10s (install checks, full sims) | `-m "not slow"` |

`@pytest.mark.integration` is applied in:
- `test_gpu_integration.py` (7 tests — Metal, CUDA paths)
- `test_scene_generation.py` (2 tests — full LLM pipeline)

## Test patterns

### Pydantic v2 validation

All schema tests exercise Pydantic v2 quirks:
- `model_construct()` vs `model_validate()` equivalence
- `model_validator(mode="after")` uses `self.model_copy(update={...})` — never mutate in place
- `model_dump()` returns Enum objects, not `.value` strings — convert before YAML serialization

### Mocked ROS2 tests

ROS2 tests run on macOS without actual `rclpy` apt dependencies. Two patterns are used:

**Pattern 1: `sys.modules` injection** — for modules that need to be importable despite missing deps.

**Pattern 2: `unittest.mock.patch`** — decorator-based mocking of `rclpy` and related imports.

```python
# test_ros2_bridge.py — imports guarded via sys.modules + patch
from unittest.mock import MagicMock, patch
import pytest

class TestRos2BridgeConfig:
    def test_default_config_creation(self):
        from surg_rl.ros2.config import Ros2BridgeConfig
        c = Ros2BridgeConfig(
            state_topic="/surg_rl/joint_states",
            command_topic="/surg_rl/commands",
        )
        assert c.frame_id == "world"
        assert c.on_missing_topic == "error"
```

### Mocked RLlib / Ray tests

RLlib tests use `pytest.importorskip("ray")` or `@pytest.mark.skipif` to guard against
environments where Ray is not installed. Unit-level tests mock Ray internals.

```python
# test_rllib_tune.py — module-level skip
pytest.importorskip("ray", reason="ray[rllib] not installed")

def test_build_tune_search_space_basic():
    base = RllibConfig(algorithm="PPO")
    space = build_tune_search_space(
        base,
        scene_paths=["a.json", "b.json"],
        simulator_types=["mujoco", "pybullet"],
        algorithms=["PPO", "SAC"],
    )
    assert "scene_path" in space["env_config"]
```

```python
# test_rllib_train.py — GPU mocking
def test_multi_gpu_two_gpus():
    with patch.object(torch.cuda, "device_count", return_value=2):
        rc = RllibConfig.from_training_config(TrainingConfig(), env_config={})
    assert rc.num_learners == 2
    assert rc.num_gpus_per_learner == 1.0
```

### CLI integration testing

Uses `typer.testing.CliRunner` for direct in-process CLI invocation, and subprocess-based
invocation (via `cli_runner` fixture) for cross-process tests.

```python
# test_cli_integration.py — monkey-patch LLM, run via CliRunner
from typer.testing import CliRunner
from surg_rl.cli import app

runner = CliRunner()

class TestCLIGenerateMocked:
    def test_generate_text_mocked_llm(self, tmp_path):
        scene = SceneDefinition(metadata=Metadata(name="mocked"))
        with patch("surg_rl.cli.TextParser") as mock_parser_class:
            mock_parser = MagicMock()
            mock_parser.parse = AsyncMock(return_value=scene)
            mock_parser_class.return_value = mock_parser

            result = runner.invoke(
                app,
                ["generate", "--text", "suturing", "--output", str(out_file)],
            )
        assert result.exit_code == 0
```

### GPU detector testing

GPU tests use `unittest.mock` to simulate hardware backends — no physical GPU required.

```python
# test_gpu_detector.py — mock subprocess output for each backend
with patch("subprocess.run") as mock_run:
    mock_run.return_value = MagicMock(returncode=0, stdout="CUDA 12.4")
    backends = detect_backends()
    assert HardwareBackend.CUDA in backends
```

### Simulator tests

Simulator tests construct scenes programmatically (no asset files assumed), call
`load_scene()` before `reset()`/`step()`, and guard backend-specific paths by type.

```python
# test_simulators.py
from surg_rl.simulators import MuJoCoSimulator, PyBulletSimulator

scene = SceneDefinition(metadata=Metadata(name="test"), ...)
sim = MuJoCoSimulator()
sim.load_scene(scene)
obs = sim.reset()
obs = sim.step(action)
sim.close()
```

### Fluid simulator tests

Fluid tests live in `tests/test_fluids/` and cover:
- Fluid configuration schema validation (`test_fluids/test_schema.py`)
- Fluid simulator integration with the physics backend (`test_fluids/test_fluid_simulator.py`)

### Cutting tests

`test_cutting.py` exercises the volumetric tetrahedral mesh cutting pipeline:
- Signed distance computation and edge-plane intersection (`CUT-01`)
- Tet case classification (all-same, 3-1, 2-2 patterns)
- Full `cut_tetrahedral_mesh` engine end-to-end

### Deformable body tests

`test_deformable.py` validates deformable body configuration:
- `DeformableConfig` schema validation for `tetgen`, `flexcomp_grid`, `file` mesh sources
- `MuJoCoFlexConfig` (Young's modulus, Poisson's ratio, condim, friction)
- `PyBulletFlexConfig` (solver type, auto-derive flags)
- Boundary condition schema and tissue integration

## Platform-specific tests

### PyBullet soft body (macOS skip)

PyBullet soft-body physics is unreliable on macOS and slower on macOS CI runners.
Tests are marked `skipif` rather than `xfail` for clean CI signals:

```python
@pytest.mark.skipif(
    sys.platform == "darwin",
    reason="macOS PyBullet soft-body reset slower (PERF-01 — platform limitation)",
)
def test_soft_body_simulation(self):
    ...
```

Anchor-based soft-body APIs are also macOS-incompatible:

```python
@pytest.mark.skipif(
    sys.platform == "darwin",
    reason="PyBullet createSoftBodyAnchor API incompatible on macOS",
)
```

### macOS-specific GPU tests

Metal GPU tests only run on macOS:

```python
@pytest.mark.skipif(sys.platform != "darwin", reason="Metal only on macOS")
def test_metal_gpu_detection(self):
    ...
```

### RLlib import guards

Tests that require `ray[rllib]` are gated:

```python
@pytest.mark.skipif(not _check_rllib_available(), reason="Ray not installed")
def test_rllib_distributed_train(self):
    ...
```

## Fixtures

Shared fixtures live in `tests/conftest.py`:

| Fixture | Purpose |
|---|---|
| `cli_runner` | Invoke CLI via `subprocess` with correct `PYTHONPATH` |
| `cli_env` | Copy of `os.environ` with `PYTHONPATH` set |
| `minimal_scene` | Load `scenes/minimal_scene.json` via `SceneLoader` |
| `suturing_scene` | Load `scenes/simple_suturing.json` via `SceneLoader` |
| `tetgen_cube_mesh` | Generate `.node`/`.ele` files for a small tetrahedralized cube in `tmp_path` |

Usage:

```python
def test_something(minimal_scene):
    assert minimal_scene.metadata.name == "minimal_scene"
```

The `cli_runner` fixture runs CLI commands in a subprocess with the correct Python path:

```python
def test_cli_version(cli_runner):
    result = cli_runner("version")
    assert "0.1.0" in result.stdout
```

## Coverage

`pytest-cov` (>=4.0.0) is included in dev dependencies. No coverage threshold is
configured in `pytest.ini` — coverage is advisory, not enforced.

To generate a coverage report:

```bash
pytest tests/ --cov=surg_rl --cov-report=html
pytest tests/ --cov=surg_rl --cov-report=term-missing
```

## CI integration

Tests run in CI via `.github/workflows/ci.yml` with two jobs:

### `test` job — pytest across OS and Python matrix

- **Trigger:** push to `main`, pull requests to `main`
- **Strategy:** `fail-fast: false`
- **Matrix:**
  - `ubuntu-latest` / Python 3.10, 3.11, 3.12
  - `macos-latest` / Python 3.11

**Linux steps** (pytest directly):
```bash
pytest tests/ -m "not integration" -v
```

**macOS steps** (via `mjpython` to link against MuJoCo's Python):
```bash
mjpython -m pytest tests/ \
  -m "not integration" \
  -v \
  --ignore=tests/test_ros2_bridge.py \
  --ignore=tests/test_ros2_cli.py \
  --ignore=tests/test_ros2_controller.py \
  --ignore=tests/test_ros2_replay.py
```
ROS2 tests are ignored on macOS because `rclpy` is not available.

Integration tests are excluded in CI because they require real simulators, GPU, and
optional dependencies not installed in the CI environment.

### `docker-ci` job — multi-arch Docker builds

Builds four Docker flavors (all `push: false`, cached via GitHub Actions cache):
- **CPU** — `Dockerfile` (linux/amd64, linux/arm64)
- **CUDA** — `Dockerfile.cuda` (linux/amd64)
- **ROCm** — `Dockerfile.rocm` (linux/amd64)
- **Jetson** — `Dockerfile.jetson` (linux/arm64)

## Writing new tests

### File naming

- Test files: `tests/test_<module>.py`, matching `test_*.py`
- Test classes: `Test<Feature>` (PascalCase)
- Test methods: `test_<behavior>(self)` (snake_case)
- **Feature-specific test files preferred over cross-cutting ones** (e.g., `test_cutting.py` over adding cutting tests to `test_simulators.py`). This reduces merge conflicts and clarifies ownership.
- Subdirectories for grouped concerns: `tests/test_fluids/`, `tests/unit/`, `tests/manual/`

### What to test

- Schema validators — happy path + edge cases (invalid JSON, missing required fields)
- Pydantic v2 quirks — `model_construct()` vs `model_validate()`, enum serialization
- Simulator lifecycles — `load_scene()` must precede `reset()` or expect `RuntimeError`
- Optional field guards — `InstrumentConfig.pose`, `SceneDefinition.task`, `TissueConfig.physics.pybullet`
- Invalid YAML test strings must be **actually** invalid, not merely unusual

### Async tests

`asyncio_mode = auto` means pytest-asyncio automatically detects and runs `async def`
test functions. No `@pytest.mark.asyncio` decorator is needed.

### YAML validity edge cases

Invalid test strings must be unambiguously broken:

```python
# Good — unclosed bracket is actually invalid
data = "key: [invalid"

# Bad — this is valid YAML (multiline scalar)
data = "key: value\n  nested: invalid"
```

## Common test issues

1. **`RuntimeError: Scene not loaded`** — call `simulator.load_scene(scene)` before
   `reset()` or `step()`. This is by design.

2. **`RepresenterError` in YAML serialization** — Pydantic `model_dump()` returns Enum
   objects, not `.value` strings. Convert before serializing with `yaml.dump`.

3. **Asset files don't exist** — `scene_builder` generates primitive `.obj` fallbacks on
   the fly. Never assume a real asset file exists in `assets/`.

4. **Soft body tests fail silently** — PyBullet requires `resetSimulation(RESET_USE_DEFORMABLE_WORLD)`
   before any soft body is loaded, even on a fresh connect.

5. **Optional field `None` crashes** — guard `InstrumentConfig.pose`, `SceneDefinition.task`,
   and `TissueConfig.physics.pybullet` override fields (`mass`, `scale`, `sim_mesh_path`)
   before accessing nested attributes.

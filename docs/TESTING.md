# Testing Guide

This document provides comprehensive information about testing in Surg-RL, including running tests, writing new tests, and understanding the test infrastructure.

## Table of Contents

- [Testing Overview](#testing-overview)
- [Running Tests](#running-tests)
- [Test Organization](#test-organization)
- [Writing Tests](#writing-tests)
- [Test Configuration](#test-configuration)
- [Continuous Integration](#continuous-integration)
- [Test Coverage](#test-coverage)
- [Mocking and Fixtures](#mocking-and-fixtures)
- [Best Practices](#best-practices)

---

## Testing Overview

Surg-RL uses `pytest` as its testing framework. The test suite includes:

- **Unit tests**: Testing individual functions and classes in isolation
- **Integration tests**: Testing interactions between modules
- **Simulator tests**: Testing physics simulators (MuJoCo, PyBullet)
- **Schema validation tests**: Testing scene definition schemas
- **Dynamics tests**: Testing domain randomization and curriculum learning
- **End-to-end tests**: Testing complete workflows

### Test Statistics

| Module | Tests | Coverage |
|--------|-------|----------|
| scene_definition | 118 | 94% |
| scene_generation | 59 | 92% |
| simulators | 60 | 92% |
| dynamics | 66 | 94% |
| rl (training) | 167 | 92% |
| config | 10 | 96% |
| **Total** | **487** | **~92%** |

### Test Dependencies

Test dependencies are specified in `requirements-dev.txt`:

```
pytest>=7.0.0
pytest-cov>=4.0.0
pytest-asyncio>=0.21.0
pytest-mock>=3.10.0
```

---

## Running Tests

### Run All Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with detailed output
pytest -vv
```

### Run Specific Test Files

```bash
# Run all tests
pytest tests/ -v

# Run specific module tests
pytest tests/test_loader.py
pytest tests/test_scene_generation.py
pytest tests/test_simulators.py
pytest tests/test_dynamics.py
pytest tests/test_rl.py
pytest tests/test_rewards.py
pytest tests/test_config.py

# Run new test files added in coverage expansion
pytest tests/test_cli.py -v
pytest tests/test_rl_training.py -v
pytest tests/test_rl_callbacks.py -v
pytest tests/test_rl_environment.py -v
pytest tests/test_rl_observation_action.py -v
pytest tests/test_scene_builder.py -v

# Run with coverage
pytest tests/ --cov=surg_rl --cov-report=html
```

### Run Specific Tests

```bash
# Run a specific test function
pytest tests/test_loader.py::test_load_scene

# Run tests matching a pattern
pytest -k "test_load"

# Run tests in a specific class
pytest tests/test_dynamics.py::TestEnvironmentController

# Run specific controller tests
pytest tests/test_dynamics.py::TestCurriculumScheduler -v
```

### Run with Coverage

```bash
# Run with coverage report
pytest --cov=surg_rl

# Run with coverage for dynamics module
pytest tests/test_dynamics.py --cov=surg_rl.dynamics --cov-report=term-missing

# Generate HTML coverage report
pytest --cov=surg_rl --cov-report=html
```

---

## Test Organization

The test suite is organized as follows:

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures (CLI runner, scene fixtures)
├── test_imports.py          # Import validation
├── test_loader.py           # Scene loader tests
├── test_schema.py           # Schema validation tests
├── test_config.py           # Configuration tests
├── test_simulators.py       # Simulator tests (MuJoCo + PyBullet)
├── test_scene_generation.py # Scene generation tests
├── test_dynamics.py         # Dynamics module tests
├── test_rl.py               # RL: observation, action, environment
├── test_rewards.py          # RL reward function tests
├── test_rl_training.py      # TrainingManager mocks
├── test_rl_callbacks.py     # SB3 callback tests
├── test_rl_environment.py   # SurgicalEnv lifecycle tests
├── test_rl_observation_action.py # Observation/action deep tests
├── test_scene_builder.py    # MJCF builder tests
├── test_cli.py              # CLI subprocess tests
└── fixtures/                # Test fixtures
    ├── minimal_scene.json
    └── test_config.yaml
```

### Test Categories

#### Unit Tests (`test_*.py`)

Test individual components in isolation:

- `test_loader.py`: Scene loading functionality
- `test_schema.py`: Schema validation
- `test_config.py`: Configuration management
- `test_dynamics.py`: Environment controllers, randomization

#### Dynamics Tests (`test_dynamics.py`)

Test the dynamic environment control system:

```python
# Test categories in test_dynamics.py
- TestBaseController: 7 tests (lifecycle, callbacks, parameter bounds)
- TestParameterRandomizer: 5 tests (physics, visual, dynamics randomization)
- TestCurriculumScheduler: 8 tests (stages, progression, performance)
- TestAdaptiveDifficultyController: 8 tests (adaptation, bounds, state)
- TestEnvironmentController: 9 tests (integration, status, utility methods)
- TestCurriculumEdgeCases: 9 tests (threshold, max stage, custom stage, reset, auto-advance, gravity branches)
- TestAdaptiveDifficultyEdgeCases: 8 tests (base params, scale by difficulty, apply mass/friction, disabled passthrough, empty history)
- TestParameterRandomizerEdgeCases: 3 tests (disabled, gravity range)
```

#### RL Training Tests (`test_rl_training.py`)

Mock-based tests for `TrainingManager`:

```python
- TestAlgorithmSelection: 7 tests (import errors, unknown algorithm, PPO/SAC/TD3/DDPG/A2C)
- TestEnvironmentCreation: 2 tests (single env, vectorized env)
- TestModelCreation: 2 tests (MultiInputPolicy, MlpPolicy)
- TestTrainingLoop: 3 tests (train + save, config dict, save/load round-trip)
- TestEvaluation: 3 tests (single env, vec env, missing model)
- TestModelPersistence: 2 tests (save without model, load sets model)
- TestCleanup: 1 test (close cleans envs)
```

#### RL Callback Tests (`test_rl_callbacks.py`)

Custom Stable-Baselines3 callback coverage:

```python
- TestTrainingProgressCallback: 2 tests (log progress, no episode in info)
- TestCheckpointCallback: 2 tests (save frequency, failure logs warning)
- TestCurriculumCallback: 1 test (episode end calls controller)
- TestEvaluationCallback: 2 tests (evaluate + log, get results copy)
- TestTensorBoardCallback: 3 tests (controller state, no controller, no logger)
```

#### RL Environment Tests (`test_rl_environment.py`)

SurgicalEnv lifecycle and state:

```python
- TestSurgicalEnvDefaults: 4 tests (obs config, action config, controller, invalid simulator)
- TestSurgicalEnvLifecycle: 5 tests (reset, step, truncation, render rgb/human)
- TestSurgicalEnvInfo: 1 test (build info distance)
- TestSurgicalEnvState: 2 tests (set target, state roundtrip)
- TestMakeEnvFactory: 2 tests (make_env, make_vec_env)
```

#### Observation/Action Deep Tests (`test_rl_observation_action.py`)

Detailed coverage of builder internals:

```python
- TestObservationBuilderDeep: 8 tests (flat space, normalize mismatch, quaternion, unflatten, fallbacks, padding, tool positions)
- TestActionBuilderDeep: 4 tests (discrete space, tanh, relative actions, normalize)
```

#### Scene Builder Tests (`test_scene_builder.py`)

MJCF generation and asset resolution:

```python
- TestAssetResolution: 5 tests (relative exists/missing, absolute exists/missing, mesh fallback)
- TestMJCFGeneration: 8 tests (robot, ground plane, camera, directional light, point light, tissue sphere, tissue cylinder, instrument)
```

#### CLI Tests (`test_cli.py`)

Subprocess CLI command coverage:

```python
- TestCLIVersion: 1 test (version command)
- TestCLIConfig: 1 test (config command)
- TestCLISetup: 1 test (setup creates directories)
- TestCLIGenerate: 4 tests (template JSON/YAML, no input, nonexistent template)
- TestCLITrain: 1 test (train import error)
- TestCLIEvaluate: 1 test (evaluate import error)
```


#### Integration Tests

Test interactions between modules:

- `test_simulators.py`: Simulator integration tests
- `test_scene_generation.py`: Scene generation pipeline tests

---

## Writing Tests

### Basic Test Structure

```python
# tests/test_example.py
import pytest
from surg_rl.scene_definition import load_scene

def test_load_scene_basic():
    """Test basic scene loading."""
    scene = load_scene("scenes/minimal_scene.json")
    assert scene is not None
    assert scene.metadata.name == "minimal_scene"

def test_load_scene_invalid_path():
    """Test loading scene from invalid path."""
    with pytest.raises(FileNotFoundError):
        load_scene("nonexistent.json")
```

### Testing Dynamics Module

```python
# tests/test_dynamics_example.py
import pytest
from surg_rl.dynamics import (
    EnvironmentController,
    CurriculumScheduler,
    CurriculumStage,
)

def test_curriculum_advancement():
    """Test curriculum stage advancement."""
    scheduler = CurriculumScheduler()
    scheduler.start()
    
    # Simulate good performance
    for _ in range(60):
        scheduler.reset()
        scheduler.episode_end({"success": 1, "reward": 100}, simulator=None)
    
    # Should have advanced from EASY
    assert scheduler.current_stage != CurriculumStage.EASY

def test_environment_controller_lifecycle():
    """Test environment controller start/stop lifecycle."""
    controller = EnvironmentController()
    
    controller.start()
    assert controller._randomizer.state.value == "active"
    
    controller.stop()
    assert controller._randomizer.state.value == "idle"
```

### Using Fixtures

```python
# tests/conftest.py
import pytest
from surg_rl.dynamics import EnvironmentController, EnvironmentControllerConfig
from surg_rl.scene_definition.schema import (
    DomainRandomizationConfig,
    PhysicsRandomization,
)

@pytest.fixture
def domain_config():
    """Provide domain randomization config for testing."""
    return DomainRandomizationConfig(
        physics=PhysicsRandomization(
            enabled=True,
            mass_range=(0.9, 1.1),
            friction_range=(0.4, 0.6),
        ),
    )

@pytest.fixture
def controller(domain_config):
    """Provide environment controller for testing."""
    config = EnvironmentControllerConfig(
        use_randomization=True,
        randomization_config=domain_config,
    )
    controller = EnvironmentController(config=config)
    controller.start()
    yield controller
    controller.stop()

# tests/test_dynamics_example.py
def test_with_fixture(controller):
    """Test using a fixture."""
    params = controller.reset(seed=42)
    assert params.physics is not None
```

### Parametrized Tests

```python
# Run same test with different inputs
@pytest.mark.parametrize("stage", [
    CurriculumStage.EASY,
    CurriculumStage.MEDIUM,
    CurriculumStage.HARD,
    CurriculumStage.EXPERT,
])
def test_curriculum_stages(stage):
    """Test curriculum scheduler with different stages."""
    scheduler = CurriculumScheduler(
        curriculum_config=CurriculumConfig(initial_stage=stage)
    )
    assert scheduler.current_stage == stage

@pytest.mark.parametrize("difficulty,expected_range", [
    (0.3, (0.1, 0.5)),   # Low difficulty
    (0.5, (0.3, 0.7)),   # Medium difficulty
    (0.8, (0.6, 1.0)),   # High difficulty
])
def test_difficulty_scaling(difficulty, expected_range):
    """Test parameter scaling with difficulty."""
    controller = AdaptiveDifficultyController(
        difficulty_config=DifficultyConfig(initial_difficulty=difficulty)
    )
    controller.set_difficulty(difficulty)
    assert expected_range[0] <= controller.difficulty <= expected_range[1]
```

---

## Test Configuration

### pytest Configuration

Configuration in `pytest.ini`:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
filterwarnings =
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning
```

### Common Fixtures

```python
# tests/conftest.py
import pytest
import numpy as np
import os
import subprocess
import sys
from pathlib import Path

@pytest.fixture
def cli_runner():
    """Fixture to run CLI commands via subprocess."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent.parent / "src")
    def _run(*args, check=False):
        cmd = [sys.executable, "-m", "surg_rl.cli", *args]
        return subprocess.run(cmd, capture_output=True, text=True, env=env, check=check)
    return _run

@pytest.fixture
def minimal_scene():
    """Load the minimal scene from scenes/minimal_scene.json."""
    from surg_rl.scene_definition import SceneLoader
    loader = SceneLoader()
    scene_path = Path(__file__).parent.parent / "scenes" / "minimal_scene.json"
    return loader.load(scene_path)

@pytest.fixture
def suturing_scene():
    """Load the suturing scene from scenes/simple_suturing.json."""
    from surg_rl.scene_definition import SceneLoader
    loader = SceneLoader()
    scene_path = Path(__file__).parent.parent / "scenes" / "simple_suturing.json"
    return loader.load(scene_path)

@pytest.fixture
def sample_scene():
    """Provide a sample scene for testing."""
    from surg_rl.scene_definition import SceneLoader
    loader = SceneLoader()
    return loader.load("scenes/minimal_scene.json")

@pytest.fixture
def simulator_config():
    """Default simulator configuration for tests."""
    return {
        "backend": "mujoco",
        "timestep": 0.002,
        "gravity": [0, 0, -9.81]
    }

@pytest.fixture
def random_state():
    """Provide random state for reproducible tests."""
    return np.random.RandomState(42)
```

---

## Continuous Integration

### GitHub Actions

The project uses GitHub Actions for CI. Configuration in `.github/workflows/tests.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.10, 3.11, 3.12]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        pip install -e ".[dev]"
        pip install pytest pytest-cov
    
    - name: Run tests
      run: pytest --cov=surg_rl --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

---

## Test Coverage

### Viewing Coverage Reports

```bash
# Generate coverage report
pytest --cov=surg_rl --cov-report=html

# Coverage for specific module
pytest tests/test_dynamics.py --cov=surg_rl.dynamics

# Open in browser
open htmlcov/index.html
```

### Coverage Goals

- **Minimum coverage**: 70% for all modules
- **Target coverage**: 85% for critical modules
- **New code**: Must maintain or improve coverage

### Current Coverage

| Module | Statements | Missed | Coverage |
|--------|------------|--------|----------|
| surg_rl.scene_definition | 820 | 65 | 92% |
| surg_rl.scene_generation | 650 | 78 | 88% |
| surg_rl.simulators | 780 | 117 | 85% |
| surg_rl.dynamics | 980 | 98 | 90% |
| surg_rl.utils | 180 | 9 | 95% |
| **Total** | **3410** | **367** | **89%** |

---

## Mocking and Fixtures

### Common Mocking Patterns

#### Mocking Environment Controllers

```python
@pytest.fixture
def mock_controller():
    """Mock environment controller for testing."""
    from surg_rl.dynamics import BaseController, ParameterSnapshot
    
    class MockController(BaseController):
        def sample_parameters(self):
            return ParameterSnapshot(physics={"test": 1.0})
        
        def apply_parameters(self, snapshot, simulator):
            return True
        
        def update_curriculum(self, episode, metrics):
            return {"episode": episode}
    
    return MockController()
```

#### Mocking Simulators

```python
@pytest.fixture
def mock_simulator():
    """Mock simulator for testing."""
    from surg_rl.simulators import BaseSimulator
    from unittest.mock import Mock
    
    mock = Mock(spec=BaseSimulator)
    mock.reset.return_value = {"observation": np.zeros(10)}
    mock.step.return_value = ({"observation": np.zeros(10)}, 1.0, False, {})
    return mock
```

---

## Best Practices

### 1. Test All Controller States

```python
def test_controller_lifecycle():
    """Test controller state transitions."""
    controller = EnvironmentController()
    
    # Initial state
    assert controller._randomizer.state.value == "idle"
    
    # After start
    controller.start()
    assert controller._randomizer.state.value == "active"
    
    # After pause
    controller._randomizer.pause()
    assert controller._randomizer.state.value == "paused"
    
    # After resume
    controller._randomizer.resume()
    assert controller._randomizer.state.value == "active"
    
    # After stop
    controller.stop()
    assert controller._randomizer.state.value == "idle"
```

### 2. Test Reproducibility

```python
def test_reproducibility():
    """Test that same seed produces same results."""
    config = EnvironmentControllerConfig(seed=42)
    
    controller1 = EnvironmentController(config=config)
    controller2 = EnvironmentController(config=config)
    
    controller1.start()
    controller2.start()
    
    params1 = controller1.reset()
    params2 = controller2.reset()
    
    # Same seed should produce identical parameters
    assert params1.physics == params2.physics
    assert params1.visual == params2.visual
    assert params1.dynamics == params2.dynamics
```

### 3. Test Edge Cases

```python
def test_difficulty_bounds():
    """Test difficulty clamping at bounds."""
    controller = AdaptiveDifficultyController(
        difficulty_config=DifficultyConfig(
            min_difficulty=0.2,
            max_difficulty=0.8,
        )
    )
    
    # Below minimum
    controller.set_difficulty(0.0)
    assert controller.difficulty == 0.2
    
    # Above maximum
    controller.set_difficulty(1.0)
    assert controller.difficulty == 0.8
```

### 4. Test Integration

```python
def test_full_integration():
    """Test complete workflow from scene to controller."""
    from surg_rl.scene_definition import SceneLoader
    from surg_rl.dynamics import EnvironmentController
    
    # Load scene
    loader = SceneLoader()
    scene = loader.load("scenes/minimal_scene.json")
    
    # Create controller from scene
    controller = EnvironmentController.from_scene(
        scene,
        use_curriculum=True,
        use_adaptive=True,
    )
    
    # Run episode
    controller.start()
    params = controller.reset(seed=42)
    info = controller.episode_end({"reward": 100, "success": True}, None)
    
    # Verify all components work together
    assert params is not None
    assert "curriculum" in info
    assert "adaptive_difficulty" in info
```

---

## Troubleshooting Tests

### Common Issues

#### Import Errors

```
ImportError: cannot import name 'X' from 'surg_rl'
```

**Solution**: Ensure the package is installed in development mode:
```bash
pip install -e .
```

#### Dynamics Module Import Errors

```
ImportError: cannot import name 'EnvironmentController' from 'surg_rl.dynamics'
```

**Solution**: Ensure dynamics module is properly installed:
```bash
pip install -e .
python -c "from surg_rl.dynamics import EnvironmentController; print('OK')"
```

### Debugging Tests

```bash
# Run with print statements visible
pytest -s tests/test_dynamics.py

# Drop into debugger on failure
pytest --pdb tests/test_dynamics.py

# Show local variables in traceback
pytest -l tests/test_dynamics.py::TestEnvironmentController

# Verbose output with full errors
pytest -vv --tb=long tests/test_dynamics.py
```

---

## See Also

- [DYNAMICS_API.md](DYNAMICS_API.md) - Dynamics module API reference
- [Development Guide](DEVELOPMENT_GUIDE.md) - Development workflow
- [Architecture](ARCHITECTURE.md) - Understanding the codebase
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contributing guidelines

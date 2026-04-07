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
- **End-to-end tests**: Testing complete workflows

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
# Run a specific test file
pytest tests/test_loader.py

# Run multiple test files
pytest tests/test_loader.py tests/test_schema.py
```

### Run Specific Tests

```bash
# Run a specific test function
pytest tests/test_loader.py::test_load_scene

# Run tests matching a pattern
pytest -k "test_load"

# Run tests in a specific class
pytest tests/test_simulators.py::TestMuJoCoSimulator
```

### Run Tests with Markers

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run only slow tests
pytest -m slow

# Skip slow tests
pytest -m "not slow"
```

### Run with Coverage

```bash
# Run with coverage report
pytest --cov=surg_rl

# Run with coverage and show missing lines
pytest --cov=surg_rl --cov-report=term-missing

# Generate HTML coverage report
pytest --cov=surg_rl --cov-report=html
```

### Run Tests in Parallel

```bash
# Install pytest-xdist for parallel execution
pip install pytest-xdist

# Run tests in parallel using multiple CPUs
pytest -n auto

# Run with specific number of workers
pytest -n 4
```

---

## Test Organization

The test suite is organized as follows:

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── test_imports.py          # Import validation
├── test_loader.py           # Scene loader tests
├── test_schema.py           # Schema validation tests
├── test_simulators.py       # Simulator tests
├── test_scene_generation.py # Scene generation tests
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

#### Integration Tests (`test_*_integration.py`)

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

class TestSceneValidation:
    """Tests for scene validation."""
    
    def test_valid_scene(self):
        """Test validation of valid scene."""
        # Test implementation
        pass
    
    def test_invalid_scene(self):
        """Test validation of invalid scene."""
        # Test implementation
        pass
```

### Using Fixtures

```python
# tests/conftest.py
import pytest
from surg_rl.scene_definition import SceneDefinition

@pytest.fixture
def sample_scene():
    """Provide a sample scene for testing."""
    return load_scene("scenes/minimal_scene.json")

@pytest.fixture
def temp_scene_file(tmp_path):
    """Create a temporary scene file."""
    scene_file = tmp_path / "test_scene.json"
    scene_file.write_text('{"metadata": {"name": "test"}}')
    return scene_file

# tests/test_example.py
def test_with_fixture(sample_scene):
    """Test using a fixture."""
    assert sample_scene.metadata.name == "minimal_scene"
```

### Parametrized Tests

```python
# Run same test with different inputs
@pytest.mark.parametrize("backend", ["mujoco", "pybullet"])
def test_simulator_backends(backend):
    """Test simulator with different backends."""
    from surg_rl.simulators import create_simulator
    sim = create_simulator(backend)
    assert sim is not None

@pytest.mark.parametrize("scene_file,expected_objects", [
    ("minimal_scene.json", 2),
    ("simple_suturing.json", 5),
    ("laparoscopic_dissection.yaml", 8),
])
def test_scene_objects(scene_file, expected_objects):
    """Test scene loading with different files."""
    scene = load_scene(f"scenes/{scene_file}")
    assert len(scene.objects) == expected_objects
```

### Async Tests

```python
import pytest

@pytest.mark.asyncio
async def test_async_scene_generation():
    """Test async scene generation."""
    from surg_rl.scene_generation import TextParser
    
    parser = TextParser(provider="mock")
    scene = await parser.parse("test scene")
    assert scene is not None
```

### Mocking External Dependencies

```python
from unittest.mock import Mock, patch
import pytest

def test_llm_generation_mocked():
    """Test LLM generation with mocked API."""
    with patch('surg_rl.scene_generation.text_parser.openai') as mock_openai:
        # Configure mock
        mock_openai.ChatCompletion.create.return_value = {
            "choices": [{"message": {"content": '{"scene": {...}}'}}]
        }
        
        # Test code
        parser = TextParser(provider="openai")
        scene = parser.parse("test description")
        
        # Verify mock was called
        assert mock_openai.ChatCompletion.create.called
```

---

## Test Configuration

### pytest.ini

The `pytest.ini` file configures pytest behavior:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Markers
markers =
    unit: Unit tests
    integration: Integration tests
    slow: Slow running tests
    simulator: Tests requiring simulators

# Async mode
asyncio_mode = auto

# Warnings
filterwarnings =
    error
    ignore::DeprecationWarning

# Coverage settings
addopts = 
    --strict-markers
    --tb=short
    --cov=surg_rl
    --cov-report=term-missing
```

### conftest.py

Shared fixtures and configuration in `tests/conftest.py`:

```python
import pytest
import os

@pytest.fixture(scope="session")
def test_data_dir():
    """Path to test data directory."""
    return os.path.join(os.path.dirname(__file__), "fixtures")

@pytest.fixture(scope="session")
def mock_api_keys():
    """Mock API keys for testing."""
    os.environ["OPENAI_API_KEY"] = "test-key"
    os.environ["ANTHROPIC_API_KEY"] = "test-key"
    yield
    # Cleanup
    del os.environ["OPENAI_API_KEY"]
    del os.environ["ANTHROPIC_API_KEY"]

@pytest.fixture
def simulator_config():
    """Default simulator configuration for tests."""
    return {
        "backend": "mujoco",
        "timestep": 0.002,
        "gravity": [0, 0, -9.81]
    }
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

### Pre-commit Hooks

Run tests locally before committing:

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

---

## Test Coverage

### Viewing Coverage Reports

```bash
# Generate coverage report
pytest --cov=surg_rl --cov-report=html

# Open in browser
open htmlcov/index.html
```

### Coverage Goals

- **Minimum coverage**: 70% for all modules
- **Target coverage**: 85% for critical modules
- **New code**: Must maintain or improve coverage

### Coverage Configuration

In `.coveragerc` or `pyproject.toml`:

```ini
[run]
source = surg_rl
branch = True
omit = 
    */tests/*
    */__init__.py
    */conftest.py

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
```

---

## Mocking and Fixtures

### Common Mocking Patterns

#### Mocking LLM APIs

```python
@pytest.fixture
def mock_openai():
    """Mock OpenAI API for testing."""
    with patch('openai.ChatCompletion.create') as mock:
        mock.return_value = {
            "choices": [{
                "message": {
                    "content": '{"metadata": {"name": "test"}}'
                }
            }]
        }
        yield mock
```

#### Mocking Simulators

```python
@pytest.fixture
def mock_simulator():
    """Mock simulator for testing."""
    from surg_rl.simulators import BaseSimulator
    
    mock = Mock(spec=BaseSimulator)
    mock.reset.return_value = {"observation": np.zeros(10)}
    mock.step.return_value = ({"observation": np.zeros(10)}, 1.0, False, {})
    return mock
```

#### Mocking File Operations

```python
def test_file_operations(tmp_path):
    """Test file operations with temporary directory."""
    # tmp_path is a pytest fixture providing a temporary directory
    test_file = tmp_path / "test.json"
    test_file.write_text('{"test": "data"}')
    
    # Test code that reads/writes files
    result = load_config(test_file)
    assert result["test"] == "data"
```

---

## Best Practices

### 1. Write Clear Test Names

```python
# Bad
def test_1():
    pass

# Good
def test_load_scene_returns_valid_scene():
    pass
```

### 2. Use Docstrings

```python
def test_scene_validation():
    """Test that scene validation catches errors.
    
    Verifies that:
    - Missing required fields raise ValidationError
    - Invalid types are caught
    - Nested objects are validated recursively
    """
    pass
```

### 3. Keep Tests Isolated

```python
# Bad: Uses shared mutable state
scene_cache = {}

def test_load():
    scene_cache["scene"] = load_scene("test.json")

def test_validate():
    scene = scene_cache["scene"]  # Depends on test_load

# Good: Each test is independent
def test_load():
    scene = load_scene("test.json")
    assert scene is not None

def test_validate():
    scene = load_scene("test.json")
    validate_scene(scene)
```

### 4. Test Edge Cases

```python
def test_load_scene_edge_cases():
    """Test edge cases in scene loading."""
    # Empty file
    with pytest.raises(ValidationError):
        load_scene("empty.json")
    
    # Invalid JSON
    with pytest.raises(json.JSONDecodeError):
        load_scene("invalid.json")
    
    # Very large scene
    large_scene = create_large_scene()
    assert len(large_scene.objects) > 1000
```

### 5. Use Fixtures Wisely

```python
# Bad: Expensive fixture for simple test
@pytest.fixture
def complex_simulator():
    sim = create_expensive_simulator()
    yield sim
    sim.cleanup()  # Expensive cleanup

def test_simple_thing(complex_simulator):
    # Only needs a mock
    pass

# Good: Use appropriate fixture
def test_simple_thing():
    sim = Mock()
    # Test simple thing
    pass
```

### 6. Clean Up Resources

```python
@pytest.fixture
def simulator():
    """Create simulator for testing."""
    sim = MuJoCoSimulator()
    yield sim
    # Clean up
    sim.close()
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

#### Simulator Initialization Failures

```
RuntimeError: Failed to initialize MuJoCo
```

**Solution**: Check MuJoCo installation:
```bash
python -c "import mujoco; print(mujoco.__version__)"
```

#### Async Test Issues

```
RuntimeWarning: coroutine was never awaited
```

**Solution**: Install pytest-asyncio and use `@pytest.mark.asyncio`:
```bash
pip install pytest-asyncio
```

### Debugging Tests

```bash
# Run with print statements visible
pytest -s

# Drop into debugger on failure
pytest --pdb

# Show local variables in traceback
pytest -l

# Verbose output with full errors
pytest -vv --tb=long
```

---

## See Also

- [Development Guide](DEVELOPMENT_GUIDE.md) - Development workflow
- [Architecture](ARCHITECTURE.md) - Understanding the codebase
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contributing guidelines

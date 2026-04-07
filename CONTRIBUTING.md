# Contributing to Surg-RL

Thank you for your interest in contributing to Surg-RL! This document provides guidelines and instructions for contributing.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment. Please be considerate of others and follow these principles:

- Be respectful and inclusive
- Welcome newcomers and help them get started
- Accept constructive criticism gracefully
- Focus on what is best for the community

## Development Setup

### Prerequisites

- Python 3.11 or higher
- Git
- Virtual environment (venv or conda)

### Getting Started

1. **Fork and Clone**

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR_USERNAME/surg-rl.git
cd surg-rl
```

2. **Create Virtual Environment**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install Development Dependencies**

```bash
pip install -e ".[dev]"
```

4. **Run Tests**

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_simulators.py -v

# Run with coverage
pytest tests/ --cov=surg_rl
```

### Development Workflow

1. **Create a Branch**

```bash
git checkout -b feature/your-feature-name
```

2. **Make Changes**
   - Write code
   - Add tests
   - Update documentation

3. **Run Quality Checks**

```bash
# Format code
ruff format .

# Check for issues
ruff check .

# Run tests
pytest tests/ -v
```

4. **Commit Changes**

```bash
git add .
git commit -m "feat: description of your change"
```

5. **Push and Create PR**

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

## Coding Standards

### Code Style

- Follow PEP 8 conventions
- Use type hints for function parameters and return values
- Write docstrings for all public functions and classes
- Keep functions focused and small (<50 lines preferred)
- Use meaningful variable and function names

### Example

```python
def load_scene(file_path: Path, validate: bool = True) -> SceneDefinition:
    """Load a scene from a file.
    
    Args:
        file_path: Path to the scene file (JSON or YAML).
        validate: Whether to validate the scene against schema.
    
    Returns:
        Loaded SceneDefinition object.
    
    Raises:
        SceneFileNotFoundError: If file doesn't exist.
        SceneValidationError: If validation fails.
    """
    # Implementation
```

### Testing

- Write tests for all new features
- Maintain test coverage above 80%
- Use pytest fixtures for common setup
- Test edge cases and error conditions

```python
def test_load_scene(tmp_path: Path):
    """Test loading a scene from file."""
    scene = SceneDefinition(metadata=Metadata(name="Test"))
    scene_file = tmp_path / "test.json"
    scene_file.write_text(scene.model_dump_json())
    
    loaded = load_scene(scene_file)
    assert loaded.metadata.name == "Test"
```

### Documentation

- Update docstrings for modified functions
- Add examples in docstrings where helpful
- Update README.md for user-facing changes
- Update relevant docs/ files for architectural changes

## Pull Request Process

1. **Ensure all checks pass**
   - Tests pass
   - Code is formatted
   - No linting errors

2. **Update Documentation**
   - Update README.md if needed
   - Update CHANGELOG.md with your changes
   - Add/update docstrings

3. **PR Description**
   - Describe what changes you made
   - Link to related issues
   - Note any breaking changes

4. **Review Process**
   - Maintainers will review your PR
   - Address review comments
   - Once approved, it will be merged

## Project Structure

```
surg-rl/
├── src/surg_rl/           # Source code
│   ├── scene_generation/   # Scene generation
│   ├── scene_definition/   # Scene schema
│   ├── simulators/        # Physics simulators
│   └── utils/             # Utilities
├── tests/                  # Test suite
├── docs/                   # Documentation
├── examples/               # Example scripts
└── scenes/                 # Example scenes
```

## Reporting Issues

### Bug Reports

When reporting bugs, please include:

1. Python version
2. Operating system
3. Steps to reproduce
4. Expected behavior
5. Actual behavior
6. Error messages/traceback

### Feature Requests

For feature requests:

1. Describe the feature
2. Explain the use case
3. Provide examples if possible

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Questions?

- Open a GitHub Discussion for questions
- Check existing issues before creating new ones
- Tag maintainers for urgent issues

Thank you for contributing! 🎉

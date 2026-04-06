# Fix Test Errors - Quick Guide

## The Problem

You're seeing:
```
ModuleNotFoundError: No module named 'pydantic'
```

This means the required Python packages aren't installed yet.

## The Solution

### Quick Fix (One Command)

```bash
pip install pydantic pydantic-settings pytest pyyaml rich typer
```

### Then Run Tests

```bash
pytest tests/ -v
```

## Why This Happens

The project uses several Python packages:
- `pydantic` - For configuration and schema validation
- `pydantic-settings` - For settings management
- `pytest` - For running tests
- `pyyaml` - For YAML file handling
- `rich` - For CLI formatting
- `typer` - For CLI interface

These packages need to be installed before tests can run.

## Alternative: Use Requirements File

```bash
pip install -r requirements.txt
```

This installs all essential dependencies at once.

## After Installation

You should see:
```
✅ 5 passed
```

When running:
```bash
pytest tests/test_imports.py -v
```

## Files Created to Help

1. **INSTALL.md** - Complete installation guide
2. **requirements.txt** - List of essential packages
3. **requirements-dev.txt** - Development dependencies
4. **conftest.py** - Pytest configuration (already sets up import paths)
5. **pytest.ini** - Simplified pytest config
6. **setup_simple.py** - Setup script to check/install packages
7. **docs/TROUBLESHOOTING.md** - Detailed troubleshooting guide

## Next Steps

1. Install packages: `pip install pydantic pydantic-settings pytest pyyaml rich typer`
2. Run tests: `pytest tests/ -v`
3. All tests should pass
4. Continue to Step 2: Scene Schema Definition

## Need More Help?

- See **INSTALL.md** for full installation options
- See **docs/TROUBLESHOOTING.md** for detailed troubleshooting
- See **README.md** for project overview

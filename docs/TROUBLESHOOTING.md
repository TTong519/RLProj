# Troubleshooting Guide

## Common Issues

### 1. ModuleNotFoundError: No module named 'surg_rl'

**Problem:** Python can't find the `surg_rl` module when running tests.

**Solutions:**

#### Option A: Install package (Recommended)
```bash
# If you have internet access
pip install -e ".[dev]"

# If pip install fails due to network issues
pip install -r requirements.txt
```

#### Option B: Use conftest.py (Already created)
The `conftest.py` file in the project root automatically adds `src/` to Python path for pytest.

#### Option C: Set PYTHONPATH manually
```bash
# For testing
export PYTHONPATH="${PWD}/src:$PYTHONPATH"
pytest tests/

# Or run tests directly with PYTHONPATH
PYTHONPATH=src pytest tests/
```

### 2. Network/Connection Errors during pip install

**Problem:** `pip install` fails with connection errors.

**Solutions:**

#### Option A: Check internet connection
```bash
# Test connectivity
ping pypi.org
```

#### Option B: Use alternative package index
```bash
pip install --index-url https://pypi.org/simple/ -r requirements.txt
```

#### Option C: Install packages individually
```bash
pip install pydantic>=2.0.0
pip install pydantic-settings>=2.0.0
pip install pyyaml>=6.0
pip install rich>=13.0.0
pip install typer>=0.9.0
pip install pytest>=7.0.0
```

#### Option D: Use offline packages
If you have access to the packages offline:
```bash
# Download packages on a machine with internet
pip download -r requirements.txt -d ./packages

# Install from local directory
pip install --no-index --find-links=./packages -r requirements.txt
```

### 3. Missing Dependencies

**Problem:** Tests fail due to missing packages.

**Solutions:**

Run the setup script to check and install:
```bash
python setup_simple.py
```

Or manually install essentials:
```bash
pip install pydantic pydantic-settings pyyaml rich typer pytest
```

### 4. Pytest Configuration Warnings

**Problem:** Warning about unknown config option `asyncio_mode`.

**Solution:** Already fixed in pytest.ini. If you see this warning:
- The conftest.py file handles the path setup
- pytest.ini has been simplified to avoid warnings

### 5. Permission Errors

**Problem:** Permission denied when installing packages.

**Solutions:**

#### Option A: Use --user flag
```bash
pip install --user -r requirements.txt
```

#### Option B: Use virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 6. Python Version Issues

**Problem:** Package requires different Python version.

**Solution:** Check Python version:
```bash
python --version  # Should be >= 3.10
```

If you need to use a different Python version:
```bash
# Using pyenv (if installed)
pyenv install 3.10.0
pyenv local 3.10.0

# Or specify Python version when creating venv
python3.10 -m venv venv
```

## Quick Test

After fixing installation issues, verify setup:

```bash
# Test imports
python3 -c "from surg_rl.utils.config import Settings; print('✅ Config imports work')"

# Run tests
pytest tests/test_imports.py -v

# Test CLI
python -m surg_rl.cli version
```

## Still Having Issues?

1. Check the error message carefully
2. Ensure you're in the project root directory
3. Try cleaning up and reinstalling:
   ```bash
   rm -rf venv .pytest_cache __pycache__ src/__pycache__
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   pytest tests/
   ```

4. Check if all dependencies are installed:
   ```bash
   pip list | grep -E "(pydantic|pytest|rich|typer)"
   ```

## Minimal Installation

If you're having trouble with the full installation, you can run tests with minimal dependencies:

```bash
# Install only what's needed for tests
pip install pydantic pydantic-settings pytest pyyaml

# Run basic tests
PYTHONPATH=src pytest tests/test_config.py tests/test_imports.py -v
```

## Getting Help

If none of these solutions work:
1. Check the GitHub issues (if available)
2. Look at the error message for specific package names
3. Try installing packages one at a time to identify the problematic one
4. Make sure you're using Python >= 3.10

## Manual Path Setup

As a last resort, you can manually set up the Python path in each Python session:

```python
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Now you can import
from surg_rl.utils.config import Settings
```

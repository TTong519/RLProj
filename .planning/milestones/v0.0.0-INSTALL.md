# Installation Guide

## Quick Fix for Current Error

You're seeing a `ModuleNotFoundError: No module named 'pydantic'` because the required dependencies aren't installed.

### Immediate Solution

Install the essential packages:

```bash
# From the project root directory
pip install pydantic pydantic-settings pytest pyyaml rich typer
```

Then run tests again:
```bash
pytest tests/test_imports.py -v
```

## Full Installation Methods

### Method 1: Requirements File (Recommended)

```bash
pip install -r requirements.txt
```

### Method 2: Development Install

```bash
pip install -e ".[dev]"
```

Note: This method may fail if there's no internet connection or PyPI is unreachable.

### Method 3: Manual Package Installation

If you have network issues, install packages one by one:

```bash
pip install pydantic>=2.0.0
pip install pydantic-settings>=2.0.0
pip install pytest>=7.0.0
pip install pyyaml>=6.0
pip install rich>=13.0.0
pip install typer>=0.9.0
pip install python-dotenv>=1.0.0
```

### Method 4: Use Existing Virtual Environment

If you already have a virtual environment with some packages:

```bash
# Activate your virtual environment
source venv/bin/activate  # or: source ~/.venv/bin/activate

# Install missing packages
pip install pydantic pydantic-settings pytest
```

## Verify Installation

After installing packages, verify:

```bash
# Test imports
python3 -c "import pydantic; print('✅ pydantic installed')"

# Test full import chain
python3 -c "from surg_rl.utils.config import Settings; print('✅ surg_rl imports work')"

# Run tests
pytest tests/test_imports.py -v
```

## Network Issues?

If `pip install` fails with network errors:

### Option A: Check connectivity
```bash
ping pypi.org
curl https://pypi.org/simple/
```

### Option B: Use alternative index
```bash
pip install --index-url https://pypi.org/simple/ pydantic pydantic-settings
```

### Option C: Use local cache
```bash
# Use packages already in pip cache
pip install --no-index pydantic pydantic-settings
```

### Option D: Offline installation
If you have wheel files:
```bash
pip install --no-index --find-links=/path/to/wheels pydantic
```

## Still Having Issues?

1. **Check Python version:**
   ```bash
   python --version  # Should be >= 3.10
   ```

2. **Check pip version:**
   ```bash
   pip --version
   pip install --upgrade pip
   ```

3. **Clear pip cache:**
   ```bash
   pip cache purge
   ```

4. **Try in a fresh virtual environment:**
   ```bash
   python -m venv fresh_venv
   source fresh_venv/bin/activate
   pip install pydantic pydantic-settings pytest
   ```

## Minimal Working Setup

For just running tests, you only need:

```bash
pip install pydantic pydantic-settings pytest pyyaml
```

Then run tests with:
```bash
PYTHONPATH=src pytest tests/ -v
```

## Next Steps After Installation

1. Run tests: `pytest tests/ -v`
2. Test CLI: `python -m surg_rl.cli version`
3. Continue to Step 2: Scene Schema Definition

## Quick Commands

```bash
# Minimal install
pip install pydantic pydantic-settings pytest pyyaml

# Run tests
PYTHONPATH=src pytest tests/ -v

# Or with conftest.py (already set up)
pytest tests/ -v
```

The `conftest.py` file in the project root handles the import path automatically!

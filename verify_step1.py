#!/usr/bin/env python3
"""Verification script for Step 1 completion.

This script verifies that all Step 1 requirements are met.
"""

import sys
from pathlib import Path

def verify_file_exists(filepath: str) -> bool:
    """Check if a file exists."""
    path = Path(filepath)
    if path.exists():
        print(f"  ✅ {filepath}")
        return True
    else:
        print(f"  ❌ {filepath} - MISSING")
        return False

def verify_directory_exists(dirpath: str) -> bool:
    """Check if a directory exists."""
    path = Path(dirpath)
    if path.is_dir():
        print(f"  ✅ {dirpath}/")
        return True
    else:
        print(f"  ❌ {dirpath}/ - MISSING")
        return False

def main():
    """Run verification checks."""
    print("=" * 60)
    print("Step 1 Verification: Project Structure and Dependencies")
    print("=" * 60)
    
    all_passed = True
    
    # Check directories
    print("\n📁 Checking directories...")
    dirs = [
        "src/surg_rl",
        "src/surg_rl/scene_generation",
        "src/surg_rl/scene_definition",
        "src/surg_rl/simulators",
        "src/surg_rl/dynamics",
        "src/surg_rl/rl",
        "src/surg_rl/utils",
        "assets",
        "assets/meshes",
        "assets/textures",
        "assets/materials",
        "scenes",
        "configs",
        "tests",
        "examples",
        "docs",
    ]
    for d in dirs:
        if not verify_directory_exists(d):
            all_passed = False
    
    # Check files
    print("\n📄 Checking files...")
    files = [
        "pyproject.toml",
        "README.md",
        ".env.example",
        ".gitignore",
        "src/surg_rl/__init__.py",
        "src/surg_rl/cli.py",
        "src/surg_rl/utils/__init__.py",
        "src/surg_rl/utils/config.py",
        "src/surg_rl/utils/logging.py",
        "src/surg_rl/scene_generation/__init__.py",
        "src/surg_rl/scene_definition/__init__.py",
        "src/surg_rl/simulators/__init__.py",
        "src/surg_rl/dynamics/__init__.py",
        "src/surg_rl/rl/__init__.py",
        "tests/__init__.py",
        "tests/test_config.py",
        "tests/test_imports.py",
        "configs/default_config.yaml",
        "examples/basic_usage.py",
        "docs/IMPLEMENTATION_PLAN.md",
        "docs/STATUS.md",
    ]
    for f in files:
        if not verify_file_exists(f):
            all_passed = False
    
    # Check imports
    print("\n🔍 Checking Python imports...")
    try:
        sys.path.insert(0, "src")
        import surg_rl
        print(f"  ✅ import surg_rl - version {surg_rl.__version__}")
        
        from surg_rl.utils.config import Settings, get_settings
        print("  ✅ import Settings, get_settings")
        
        from surg_rl.utils.logging import setup_logging, get_logger
        print("  ✅ import setup_logging, get_logger")
        
        settings = get_settings()
        print(f"  ✅ Settings loaded: default_simulator={settings.default_simulator}")
        
    except ImportError as e:
        print(f"  ❌ Import failed: {e}")
        all_passed = False
    
    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ All Step 1 requirements met!")
        print("\nNext steps:")
        print("  1. Create virtual environment: python -m venv venv")
        print("  2. Activate: source venv/bin/activate")
        print("  3. Install: pip install -e '.[dev]'")
        print("  4. Run tests: pytest tests/")
        print("  5. Continue to Step 2: Scene Schema Definition")
        return 0
    else:
        print("❌ Some requirements not met. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

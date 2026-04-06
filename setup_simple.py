#!/usr/bin/env python3
"""Simple setup script that works around network issues.

This script provides alternative installation methods when pip install fails.
"""

import subprocess
import sys
from pathlib import Path

def check_package_installed(package_name):
    """Check if a package is installed."""
    try:
        __import__(package_name)
        return True
    except ImportError:
        return False

def install_essential_packages():
    """Install only the essential packages needed for basic functionality."""
    packages = [
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "pyyaml>=6.0",
        "rich>=13.0.0",
        "typer>=0.9.0",
    ]
    
    print("Installing essential packages...")
    for package in packages:
        print(f"  Installing {package}...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", package],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(f"    ❌ Failed to install {package}")
                print(f"    Error: {result.stderr}")
                return False
            else:
                print(f"    ✅ Installed {package}")
        except Exception as e:
            print(f"    ❌ Error installing {package}: {e}")
            return False
    
    return True

def add_to_pythonpath():
    """Add src directory to PYTHONPATH."""
    src_path = Path(__file__).parent / "src"
    print(f"\nTo run tests, add the src directory to PYTHONPATH:")
    print(f"  export PYTHONPATH=\"{src_path.absolute()}:$PYTHONPATH\"")
    print(f"\nOr run tests with:")
    print(f"  PYTHONPATH={src_path.absolute()} pytest tests/")

def create_conftest():
    """Create pytest conftest.py to add src to path."""
    conftest_content = '''"""Pytest configuration."""

import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
'''
    
    conftest_path = Path(__file__).parent / "conftest.py"
    with open(conftest_path, 'w') as f:
        f.write(conftest_content)
    print(f"✅ Created {conftest_path}")

def main():
    """Main setup function."""
    print("=" * 60)
    print("Surg-RL Setup Script")
    print("=" * 60)
    
    print("\n📦 Checking essential packages...")
    
    essential_packages = {
        "pydantic": "pydantic",
        "pydantic_settings": "pydantic-settings",
        "yaml": "pyyaml",
        "rich": "rich",
        "typer": "typer",
    }
    
    missing_packages = []
    for module_name, package_name in essential_packages.items():
        if check_package_installed(module_name):
            print(f"  ✅ {package_name}")
        else:
            print(f"  ❌ {package_name} (missing)")
            missing_packages.append(package_name)
    
    if missing_packages:
        print(f"\n⚠️  Missing packages: {', '.join(missing_packages)}")
        print("\nAttempting to install missing packages...")
        
        if not install_essential_packages():
            print("\n❌ Failed to install packages.")
            print("\nAlternative methods:")
            print("1. Fix network issue and run:")
            print(f"   pip install -e '.[dev]'")
            print("\n2. Or install packages manually:")
            for package in missing_packages:
                print(f"   pip install {package}")
            print("\n3. Or use a requirements file:")
            print("   pip install -r requirements.txt")
            
            # Create conftest.py as fallback
            create_conftest()
            add_to_pythonpath()
            return 1
    else:
        print("\n✅ All essential packages installed!")
    
    # Create conftest.py for pytest
    create_conftest()
    
    print("\n✅ Setup complete!")
    print("\nNext steps:")
    print("  1. Run tests: pytest tests/")
    print("  2. Check installation: surg-rl version")
    print("  3. Continue to Step 2: Scene Schema Definition")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

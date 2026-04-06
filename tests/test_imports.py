"""Test that all modules can be imported."""

import pytest


def test_import_main():
    """Test importing main package."""
    import surg_rl
    
    assert hasattr(surg_rl, "__version__")
    assert surg_rl.__version__ == "0.1.0"


def test_import_utils():
    """Test importing utils module."""
    from surg_rl.utils import get_settings, Settings
    
    assert get_settings is not None
    assert Settings is not None


def test_import_config():
    """Test importing config module."""
    from surg_rl.utils.config import Settings, get_settings
    
    assert Settings is not None
    assert get_settings is not None


def test_import_logging():
    """Test importing logging module."""
    from surg_rl.utils.logging import setup_logging, get_logger
    
    assert setup_logging is not None
    assert get_logger is not None


def test_import_submodules():
    """Test importing all submodules."""
    from surg_rl import scene_generation
    from surg_rl import scene_definition
    from surg_rl import simulators
    from surg_rl import dynamics
    from surg_rl import rl
    
    # All should import without error
    assert scene_generation is not None
    assert scene_definition is not None
    assert simulators is not None
    assert dynamics is not None
    assert rl is not None

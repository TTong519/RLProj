"""Shared pytest fixtures and utilities."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from surg_rl.scene_definition import SceneLoader

# Ensure src/ is on the path for pytest collection
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def cli_runner():
    """Fixture to run CLI commands via subprocess with correct PYTHONPATH."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent.parent / "src")

    def _run(*args, check: bool = False) -> subprocess.CompletedProcess:
        cmd = [sys.executable, "-m", "surg_rl.cli", *args]
        return subprocess.run(cmd, capture_output=True, text=True, env=env, check=check)

    return _run


@pytest.fixture
def cli_env():
    """Return a copy of os.environ with PYTHONPATH set for CLI subprocesses."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent.parent / "src")
    return env


@pytest.fixture
def minimal_scene():
    """Load the minimal scene from scenes/minimal_scene.json."""
    loader = SceneLoader()
    scene_path = Path(__file__).parent.parent / "scenes" / "minimal_scene.json"
    return loader.load(scene_path)


@pytest.fixture
def suturing_scene():
    """Load the suturing scene from scenes/simple_suturing.json."""
    loader = SceneLoader()
    scene_path = Path(__file__).parent.parent / "scenes" / "simple_suturing.json"
    return loader.load(scene_path)

"""LAUNCH-01..03: ROS2 launch file syntax and compatibility tests."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestLaunchFileSyntax:
    """LAUNCH-01: Verify .launch.py files are valid Python."""

    def test_bridge_launch_syntax(self):
        path = PROJECT_ROOT / "launch" / "bridge.launch.py"
        with open(path) as f:
            tree = ast.parse(f.read())
        assert tree is not None

    def test_replay_launch_syntax(self):
        path = PROJECT_ROOT / "launch" / "replay.launch.py"
        with open(path) as f:
            tree = ast.parse(f.read())
        assert tree is not None

    def test_bridge_launch_has_description(self):
        path = PROJECT_ROOT / "launch" / "bridge.launch.py"
        content = path.read_text()
        assert "generate_launch_description" in content
        assert "LaunchDescription" in content

    def test_replay_launch_has_description(self):
        path = PROJECT_ROOT / "launch" / "replay.launch.py"
        content = path.read_text()
        assert "generate_launch_description" in content
        assert "LaunchDescription" in content


class TestLaunchArguments:
    """LAUNCH-03: Verify launch arguments are declared."""

    def test_bridge_launch_arguments(self):
        path = PROJECT_ROOT / "launch" / "bridge.launch.py"
        content = path.read_text()
        assert "scene_path" in content
        assert "controller_yaml" in content

    def test_replay_launch_arguments(self):
        path = PROJECT_ROOT / "launch" / "replay.launch.py"
        content = path.read_text()
        assert "model_path" in content


class TestPipColconCompatibility:
    """LAUNCH-02: pip + colcon workflow compatibility."""

    def test_pyproject_has_data_files(self):
        import tomllib

        path = PROJECT_ROOT / "pyproject.toml"
        with open(path, "rb") as f:
            cfg = tomllib.load(f)
        data_files = cfg.get("tool", {}).get("setuptools", {}).get("data-files", {})
        assert len(data_files) > 0

    def test_ros2_extra_includes_launch(self):
        import tomllib

        path = PROJECT_ROOT / "pyproject.toml"
        with open(path, "rb") as f:
            cfg = tomllib.load(f)
        ros2_deps = (
            cfg.get("project", {}).get("optional-dependencies", {}).get("ros2", [])
        )
        assert any("launch" in dep for dep in ros2_deps)

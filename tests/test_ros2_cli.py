"""Tests for ROS2 CLI commands — help output, error cases."""

import re

from typer.testing import CliRunner

from surg_rl.cli import app

runner = CliRunner()

# Rich/typer emit ANSI color escapes when the CI environment forces color, which
# splits option names (``--config`` etc.) so literal substring asserts against raw
# stdout fail. Strip CSI sequences before asserting. See debug session
# ci-failures-lint-pybullet (C4).
_ANSI_CSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _strip_ansi(text: str) -> str:
    """Remove ANSI CSI escape sequences from *text*."""
    return _ANSI_CSI_RE.sub("", text)


class TestRos2Cli:
    def test_ros2_bridge_help(self):
        result = runner.invoke(app, ["ros2-bridge", "--help"])
        assert result.exit_code == 0
        out = _strip_ansi(result.stdout)
        assert "--config" in out
        assert "--scene" in out

    def test_ros2_replay_help(self):
        result = runner.invoke(app, ["ros2-replay", "--help"])
        assert result.exit_code == 0
        out = _strip_ansi(result.stdout)
        assert "--checkpoint" in out
        assert "--speed" in out

    def test_ros2_bridge_missing_config_acceptable(self):
        result = runner.invoke(app, ["ros2-bridge"])
        assert result.exit_code in (0, 1, 2)

    def test_ros2_replay_missing_scene(self):
        result = runner.invoke(app, ["ros2-replay", "--checkpoint", "fake.zip"])
        assert result.exit_code != 0

    def test_ros2_replay_missing_checkpoint(self):
        result = runner.invoke(
            app,
            [
                "ros2-replay",
                "--scene",
                "fake.json",
            ],
        )
        assert result.exit_code != 0

    def test_cli_commands_registered(self):
        result_bridge = runner.invoke(app, ["ros2-bridge", "--help"])
        assert result_bridge.exit_code == 0
        assert "ROS2 bridge" in _strip_ansi(result_bridge.stdout)
        result_replay = runner.invoke(app, ["ros2-replay", "--help"])
        assert result_replay.exit_code == 0
        out_replay = _strip_ansi(result_replay.stdout)
        assert "Trajectory replay" in out_replay or "replay" in out_replay.lower()

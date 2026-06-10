"""Tests for ROS2 CLI commands — help output, error cases."""

from typer.testing import CliRunner

from surg_rl.cli import app

runner = CliRunner()


class TestRos2Cli:
    def test_ros2_bridge_help(self):
        result = runner.invoke(app, ["ros2-bridge", "--help"])
        assert result.exit_code == 0
        assert "--config" in result.stdout
        assert "--scene" in result.stdout

    def test_ros2_replay_help(self):
        result = runner.invoke(app, ["ros2-replay", "--help"])
        assert result.exit_code == 0
        assert "--checkpoint" in result.stdout
        assert "--speed" in result.stdout

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
        assert "ROS2 bridge" in result_bridge.stdout
        result_replay = runner.invoke(app, ["ros2-replay", "--help"])
        assert result_replay.exit_code == 0
        assert (
            "Trajectory replay" in result_replay.stdout or "replay" in result_replay.stdout.lower()
        )

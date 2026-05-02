"""Tests for CLI commands."""

from typer.testing import CliRunner

from surg_rl.cli import app

runner = CliRunner()


class TestCLI:
    """Tests for CLI commands."""

    def test_version_command(self) -> None:
        """Version command prints version info."""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "Surg-RL" in result.output
        assert "0.1.0" in result.output

    def test_config_command(self) -> None:
        """Config command prints configuration."""
        result = runner.invoke(app, ["config"])
        assert result.exit_code == 0
        assert "Default Simulator" in result.output

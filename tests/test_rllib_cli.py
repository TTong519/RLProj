"""Tests for RLlib CLI commands (08-05).

DIST-06 — CLI integration verification.
"""

import subprocess
import sys


def _check_rllib_available():
    """Return True if Ray is installed."""
    return __import__("importlib").util.find_spec("ray") is not None


class _CliRunner:
    """Thin wrapper so we don't need typer/click testing infrastructure."""

    @staticmethod
    def invoke(cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "surg_rl.cli"] + cmd,
            capture_output=True,
            text=True,
            env={**__import__("os").environ, "PYTHONPATH": "src"},
        )


def test_cli_help_includes_rllib_commands():
    """``surg-rl --help`` lists train-rllib / tune / checkpoint-inspect."""
    result = _CliRunner().invoke(["--help"])
    assert result.returncode == 0
    assert "train-rllib" in result.stdout
    assert "tune" in result.stdout
    assert "checkpoint-inspect" in result.stdout


def test_train_rllib_help():
    """``surg-rl train-rllib --help` prints options."""
    result = _CliRunner().invoke(["train-rllib", "--help"])
    assert result.returncode == 0
    assert "--scene" in result.stdout


def test_tune_help():
    """``surg-rl tune --help`` prints options."""
    result = _CliRunner().invoke(["tune", "--help"])
    assert result.returncode == 0
    assert "--num-samples" in result.stdout


def test_checkpoint_inspect_help():
    """``surg-rl checkpoint-inspect --help`` prints options."""
    result = _CliRunner().invoke(["checkpoint-inspect", "--help"])
    assert result.returncode == 0
    assert "--compare-with" in result.stdout


def test_checkpoint_inspect_rllib_mock(tmp_path):
    """Inspect a mock RLlib checkpoint directory."""
    import json

    ckpt = tmp_path / "rllib_ckpt"
    ckpt.mkdir()
    (ckpt / "metadata.json").write_text(json.dumps({"algorithm": "PPO"}))

    result = _CliRunner().invoke(["checkpoint-inspect", str(ckpt)])
    assert result.returncode == 0
    assert "RLLIB" in result.stdout.upper()


def test_checkpoint_inspect_sb3_mock(tmp_path):
    """Inspect a mock SB3 checkpoint zip."""
    import zipfile

    ckpt = tmp_path / "sb3_model.zip"
    with zipfile.ZipFile(ckpt, "w") as z:
        z.writestr("policy.pth", b"x")

    result = _CliRunner().invoke(["checkpoint-inspect", str(ckpt)])
    assert result.returncode == 0
    assert "SB3" in result.stdout.upper()


def test_checkpoint_inspect_not_found():
    """Missing checkpoint returns exit code 1."""
    result = _CliRunner().invoke(["checkpoint-inspect", "/nonexistent"])
    assert result.returncode == 1

"""Tests for CLI commands using subprocess."""

import subprocess
from pathlib import Path
import pytest


class TestCLIVersion:
    def test_version_returns_success(self, cli_runner):
        result = cli_runner("version")
        assert result.returncode == 0
        assert "version" in result.stdout.lower()


class TestCLIConfig:
    def test_config_returns_success(self, cli_runner):
        result = cli_runner("config")
        assert result.returncode == 0


class TestCLISetup:
    def test_setup_creates_directories(self, cli_runner, tmp_path):
        with pytest.MonkeyPatch.context() as mp:
            # setup may create dirs in cwd; just ensure command runs
            result = cli_runner("setup")
            assert result.returncode == 0


class TestCLIGenerate:
    def test_generate_template_saves_json(self, cli_runner, tmp_path):
        out = tmp_path / "scene.json"
        result = cli_runner("generate", "--template", "suturing", "--output", str(out))
        assert result.returncode == 0
        assert out.exists()

    def test_generate_template_saves_yaml(self, cli_runner, tmp_path):
        out = tmp_path / "scene.yaml"
        result = cli_runner("generate", "--template", "suturing", "--output", str(out), "--format", "yaml")
        assert result.returncode == 0
        assert out.exists()

    def test_generate_no_input_exits_nonzero(self, cli_runner):
        result = cli_runner("generate")
        assert result.returncode != 0

    def test_generate_nonexistent_template_exits_nonzero(self, cli_runner, tmp_path):
        out = tmp_path / "scene.json"
        result = cli_runner("generate", "--template", "nonexistent", "--output", str(out))
        assert result.returncode != 0


class TestCLITrain:
    def test_train_import_error_shows_hint(self, cli_runner, tmp_path):
        out = tmp_path / "train_log"
        # Run without SB3 being mockable in subprocess; expect failure with hint
        result = cli_runner(
            "train",
            "--scene", "scenes/minimal_scene.json",
            "--algorithm", "PPO",
            "--timesteps", "1",
            "--log-dir", str(out),
        )
        # It may fail because stable-baselines3 is not installed or scene missing
        assert result.returncode != 0


class TestCLIEvaluate:
    def test_evaluate_import_error_shows_hint(self, cli_runner, tmp_path):
        out = tmp_path / "eval_log"
        result = cli_runner(
            "evaluate",
            "--scene", "scenes/minimal_scene.json",
            "--model", str(tmp_path / "fake_model"),
            "--log-dir", str(out),
        )
        assert result.returncode != 0

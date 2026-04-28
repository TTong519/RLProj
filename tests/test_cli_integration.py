"""Mocked CLI integration tests using typer.testing.CliRunner."""

import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

import pytest
from typer.testing import CliRunner

from surg_rl.cli import app

runner = CliRunner()


class TestCLIGenerateMocked:
    """Mocked generate command tests."""

    def test_generate_text_mocked_llm(self, tmp_path):
        """Monkeypatch TextParser.parse to return a SceneDefinition."""
        from surg_rl.scene_definition.schema import SceneDefinition, Metadata

        scene = SceneDefinition(metadata=Metadata(name="mocked"))

        with patch("surg_rl.cli.TextParser") as MockParserClass:
            mock_parser = MagicMock()
            mock_parser.parse = AsyncMock(return_value=scene)
            MockParserClass.return_value = mock_parser

            out_file = tmp_path / "out.json"
            result = runner.invoke(
                app,
                ["generate", "--text", "suturing", "--output", str(out_file)],
            )

        assert result.exit_code == 0, result.output
        assert out_file.exists()
        data = json.loads(out_file.read_text())
        assert data.get("metadata", {}).get("name") == "mocked"


class TestCLITrainMocked:
    """Mocked train command tests."""

    def test_train_mocked_manager(self, tmp_path, monkeypatch):
        """Monkeypatch TrainingManager.train to succeed without SB3."""
        from surg_rl.rl import training as training_module

        original_train = training_module.TrainingManager.train
        original_evaluate = training_module.TrainingManager.evaluate

        def mock_train(self):
            return {"status": "success"}

        def mock_evaluate(self, model_path=None, n_episodes=10, render=False):
            return {
                "n_episodes": n_episodes,
                "mean_reward": 0.0,
                "std_reward": 0.0,
                "max_reward": 0.0,
                "min_reward": 0.0,
                "mean_episode_length": 0.0,
                "success_rate": 0.0,
            }

        monkeypatch.setattr(training_module.TrainingManager, "train", mock_train)
        monkeypatch.setattr(training_module.TrainingManager, "evaluate", mock_evaluate)

        scene_path = tmp_path / "minimal_scene.json"
        scene_path.write_text(json.dumps({
            "metadata": {"name": "minimal", "description": "test", "version": "1.0.0"},
            "physics": {"gravity": [0.0, 0.0, -9.81], "timestep": 0.002},
            "environment": {"name": "env", "lights": [], "cameras": []},
            "robots": [],
            "tissues": [],
            "instruments": [],
            "task": None,
            "simulator": "mujoco",
        }))

        result = runner.invoke(
            app,
            [
                "train",
                "--scene", str(scene_path),
                "--algorithm", "PPO",
                "--timesteps", "1",
                "--log-dir", str(tmp_path / "logs"),
            ],
        )

        assert result.exit_code == 0, result.output
        assert "success" in result.output.lower() or "training complete" in result.output.lower()


class TestCLIEvaluateMocked:
    """Mocked evaluate command tests."""

    def test_evaluate_mocked_manager(self, tmp_path, monkeypatch):
        """Monkeypatch TrainingManager.evaluate to return dummy results."""
        from surg_rl.rl import training as training_module

        def mock_evaluate(self, model_path=None, n_episodes=10, render=False):
            return {
                "n_episodes": n_episodes,
                "mean_reward": 10.0,
                "std_reward": 1.0,
                "max_reward": 12.0,
                "min_reward": 8.0,
                "mean_episode_length": 50.0,
                "success_rate": 0.5,
            }

        monkeypatch.setattr(training_module.TrainingManager, "evaluate", mock_evaluate)

        scene_path = tmp_path / "minimal_scene.json"
        scene_path.write_text(json.dumps({
            "metadata": {"name": "minimal", "description": "test", "version": "1.0.0"},
            "physics": {"gravity": [0.0, 0.0, -9.81], "timestep": 0.002},
            "environment": {"name": "env", "lights": [], "cameras": []},
            "robots": [],
            "tissues": [],
            "instruments": [],
            "task": None,
            "simulator": "mujoco",
        }))

        model_path = tmp_path / "fake_model.zip"
        model_path.write_text("dummy")

        result = runner.invoke(
            app,
            [
                "evaluate",
                "--scene", str(scene_path),
                "--model", str(model_path),
                "--episodes", "2",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "10.00" in result.output or "Mean Reward" in result.output

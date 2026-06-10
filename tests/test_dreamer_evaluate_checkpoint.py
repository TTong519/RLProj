"""Tests for evaluate_checkpoint — public benchmark-facing entry point."""

from unittest.mock import MagicMock, patch

import pytest

from surg_rl.dreamer.training import evaluate_checkpoint


class TestEvaluateCheckpoint:
    """Test evaluate_checkpoint returns a benchmark-compatible metrics dict."""

    def _patch_all(
        self,
        evaluate_return=None,
    ):
        return (
            patch("surg_rl.dreamer.training.DreamerSubprocess"),
            patch("surg_rl.dreamer.training._create_env"),
            patch("surg_rl.dreamer.training._create_scene_for_task"),
            patch(
                "surg_rl.dreamer.training._find_latest_checkpoint",
                return_value=None,
            ),
            evaluate_return,
        )

    def test_returns_dict_with_all_required_keys(self):
        eval_metrics = {
            "success_rate": 0.65,
            "mean_reward": 4.2,
            "mean_episode_length": 150.0,
            "wall_clock_time": 60.0,
            "sample_efficiency": 0.001,
            "reconstruction_mse": 0.005,
            "reward_mae": 0.3,
        }
        mock_env = MagicMock()
        mock_subprocess_inst = MagicMock()
        mock_subprocess_inst.evaluate.return_value = eval_metrics

        with (
            patch("surg_rl.dreamer.training.DreamerSubprocess", return_value=mock_subprocess_inst),
            patch("surg_rl.dreamer.training._create_env", return_value=mock_env),
            patch("surg_rl.dreamer.training._create_scene_for_task", return_value=MagicMock()),
        ):
            result = evaluate_checkpoint(
                checkpoint_path="/models/dreamerv3/suturing_state/final.pt",
                task="suturing",
                obs_type="state",
                n_episodes=5,
            )

        required_keys = {
            "success_rate",
            "mean_reward",
            "mean_episode_length",
            "wall_clock_time",
            "sample_efficiency",
            "reconstruction_mse",
            "reward_mae",
            "obs_type",
            "checkpoint",
        }
        for key in required_keys:
            assert key in result, f"Missing key: {key}"

    def test_obs_type_passed_through(self):
        mock_env = MagicMock()
        mock_subprocess_inst = MagicMock()
        mock_subprocess_inst.evaluate.return_value = {}

        with (
            patch("surg_rl.dreamer.training.DreamerSubprocess", return_value=mock_subprocess_inst),
            patch("surg_rl.dreamer.training._create_env", return_value=mock_env),
            patch("surg_rl.dreamer.training._create_scene_for_task", return_value=MagicMock()),
        ):
            result = evaluate_checkpoint(
                checkpoint_path="/x.pt",
                task="suturing",
                obs_type="pixels",
                n_episodes=2,
            )
        assert result["obs_type"] == "pixels"

    def test_checkpoint_path_passed_through(self):
        mock_env = MagicMock()
        mock_subprocess_inst = MagicMock()
        mock_subprocess_inst.evaluate.return_value = {}

        with (
            patch("surg_rl.dreamer.training.DreamerSubprocess", return_value=mock_subprocess_inst),
            patch("surg_rl.dreamer.training._create_env", return_value=mock_env),
            patch("surg_rl.dreamer.training._create_scene_for_task", return_value=MagicMock()),
        ):
            result = evaluate_checkpoint(
                checkpoint_path="/path/to/ckpt.pt",
                task="suturing",
                obs_type="state",
                n_episodes=2,
            )
        assert result["checkpoint"] == "/path/to/ckpt.pt"

    def test_subprocess_shutdown_called_in_finally(self):
        mock_env = MagicMock()
        mock_subprocess_inst = MagicMock()
        mock_subprocess_inst.evaluate.return_value = {"reconstruction_mse": 0.0}

        with (
            patch("surg_rl.dreamer.training.DreamerSubprocess", return_value=mock_subprocess_inst),
            patch("surg_rl.dreamer.training._create_env", return_value=mock_env),
            patch("surg_rl.dreamer.training._create_scene_for_task", return_value=MagicMock()),
        ):
            evaluate_checkpoint(
                checkpoint_path="/x.pt",
                task="suturing",
                obs_type="state",
                n_episodes=1,
            )
        assert mock_subprocess_inst.shutdown.called
        assert mock_env.close.called

    def test_subprocess_shutdown_called_even_when_evaluate_raises(self):
        mock_env = MagicMock()
        mock_subprocess_inst = MagicMock()
        mock_subprocess_inst.evaluate.side_effect = RuntimeError("evaluate failed")

        with (
            patch("surg_rl.dreamer.training.DreamerSubprocess", return_value=mock_subprocess_inst),
            patch("surg_rl.dreamer.training._create_env", return_value=mock_env),
            patch("surg_rl.dreamer.training._create_scene_for_task", return_value=MagicMock()),
        ):
            with pytest.raises(RuntimeError, match="evaluate failed"):
                evaluate_checkpoint(
                    checkpoint_path="/x.pt",
                    task="suturing",
                    obs_type="state",
                    n_episodes=1,
                )
        assert mock_subprocess_inst.shutdown.called
        assert mock_env.close.called

    def test_metrics_values_passed_through(self):
        eval_metrics = {
            "success_rate": 0.85,
            "mean_reward": 10.0,
            "mean_episode_length": 200.0,
            "wall_clock_time": 120.0,
            "sample_efficiency": 0.002,
            "reconstruction_mse": 0.001,
            "reward_mae": 0.05,
        }
        mock_env = MagicMock()
        mock_subprocess_inst = MagicMock()
        mock_subprocess_inst.evaluate.return_value = eval_metrics

        with (
            patch("surg_rl.dreamer.training.DreamerSubprocess", return_value=mock_subprocess_inst),
            patch("surg_rl.dreamer.training._create_env", return_value=mock_env),
            patch("surg_rl.dreamer.training._create_scene_for_task", return_value=MagicMock()),
        ):
            result = evaluate_checkpoint(
                checkpoint_path="/x.pt",
                task="suturing",
                obs_type="state",
                n_episodes=10,
            )
        assert result["success_rate"] == 0.85
        assert result["mean_reward"] == 10.0
        assert result["reconstruction_mse"] == 0.001

    def test_load_checkpoint_called_with_provided_path(self):
        mock_env = MagicMock()
        mock_subprocess_inst = MagicMock()
        mock_subprocess_inst.evaluate.return_value = {}

        with (
            patch("surg_rl.dreamer.training.DreamerSubprocess", return_value=mock_subprocess_inst),
            patch("surg_rl.dreamer.training._create_env", return_value=mock_env),
            patch("surg_rl.dreamer.training._create_scene_for_task", return_value=MagicMock()),
        ):
            evaluate_checkpoint(
                checkpoint_path="/explicit/path.pt",
                task="suturing",
                obs_type="state",
                n_episodes=2,
            )
        assert mock_subprocess_inst.load_checkpoint.called
        assert mock_subprocess_inst.load_checkpoint.call_args[0][0] == "/explicit/path.pt"

    def test_send_config_called_with_dreamer_config(self):
        mock_env = MagicMock()
        mock_subprocess_inst = MagicMock()
        mock_subprocess_inst.evaluate.return_value = {}

        with (
            patch("surg_rl.dreamer.training.DreamerSubprocess", return_value=mock_subprocess_inst),
            patch("surg_rl.dreamer.training._create_env", return_value=mock_env),
            patch("surg_rl.dreamer.training._create_scene_for_task", return_value=MagicMock()),
        ):
            evaluate_checkpoint(
                checkpoint_path="/x.pt",
                task="suturing",
                obs_type="pixels",
                n_episodes=2,
                pixel_resolution=(64, 64),
            )
        assert mock_subprocess_inst.send_config.called
        config_arg = mock_subprocess_inst.send_config.call_args[0][0]
        assert config_arg["obs_type"] == "pixels"
        assert config_arg["process_isolation"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

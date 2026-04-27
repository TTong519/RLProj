"""Tests for RL callbacks."""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch

from surg_rl.rl.callbacks import (
    TrainingProgressCallback,
    CheckpointCallback,
    CurriculumCallback,
    EvaluationCallback,
    TensorBoardCallback,
)
from surg_rl.dynamics.curriculum import CurriculumStage
from surg_rl.dynamics.base_controller import ParameterSnapshot


class TestTrainingProgressCallback:
    def test_log_progress(self):
        callback = TrainingProgressCallback(verbose=1, log_interval=1)
        callback.init_callback(MagicMock())
        callback.locals = {"infos": [{"episode": {"r": 10.0, "l": 50}}]}
        callback._start_time = 0.0
        with patch("surg_rl.rl.callbacks.time.time", return_value=1.0):
            callback.on_step()
        stats = callback.get_stats()
        assert stats["episodes"] >= 1

    def test_no_episode_in_info(self):
        callback = TrainingProgressCallback(verbose=1, log_interval=1)
        callback.init_callback(MagicMock())
        callback.locals = {"infos": [{"other_key": True}]}
        callback.on_step()
        assert callback._episode_rewards == []


class TestCheckpointCallback:
    def test_saves_at_frequency(self, tmp_path):
        callback = CheckpointCallback(save_freq=5, save_path=str(tmp_path), verbose=0)
        model = MagicMock()
        model.num_timesteps = 10
        callback.init_callback(model)
        callback.num_timesteps = 10
        callback._last_save_step = 0
        callback.locals = {"self": model}
        with patch.object(callback, "_save_checkpoint") as mock_save:
            callback._on_step()
            mock_save.assert_called_once()

    def test_save_failure_logs_warning(self, tmp_path):
        callback = CheckpointCallback(save_freq=1, save_path=str(tmp_path), verbose=1)
        model = MagicMock()
        model.num_timesteps = 2
        callback.init_callback(model)
        callback.num_timesteps = 2
        callback._last_save_step = 0
        mock_model = MagicMock()
        mock_model.save.side_effect = OSError("disk full")
        callback.locals = {"self": mock_model}
        with patch("surg_rl.rl.callbacks.logger") as mock_logger:
            callback.on_step()
            mock_logger.warning.assert_called()


class TestCurriculumCallback:
    def test_episode_end_calls_controller(self):
        controller = MagicMock()
        callback = CurriculumCallback(controller=controller, verbose=0)
        callback.init_callback(MagicMock())
        callback.locals = {
            "infos": [{"episode": {"r": 5.0, "l": 10}, "success": True}]
        }
        callback.on_step()
        controller.episode_end.assert_called_once()


class TestEvaluationCallback:
    def test_evaluates_and_logs(self):
        eval_env = MagicMock()
        obs = np.zeros(4)
        eval_env.reset.return_value = (obs, {})
        eval_env.step.return_value = (obs, 1.0, True, False, {})
        callback = EvaluationCallback(eval_env=eval_env, eval_freq=1, n_eval_episodes=1, verbose=0)
        model = MagicMock()
        model.num_timesteps = 10
        model.predict.return_value = (np.zeros(1), None)
        callback.init_callback(model)
        callback.num_timesteps = 10
        callback._last_eval_step = 0
        callback._evaluate(model, 10)
        assert len(callback.get_results()) == 1

    def test_get_results_returns_copy(self):
        callback = EvaluationCallback(eval_freq=1000, n_eval_episodes=1)
        assert callback.get_results() == []


class TestTensorBoardCallback:
    def test_logs_controller_state(self):
        controller = MagicMock()
        controller.get_curriculum_stage.return_value = CurriculumStage.EASY
        controller.get_difficulty.return_value = 0.5
        controller.current_params = ParameterSnapshot(
            physics={"friction": 0.8},
            visual={},
            dynamics={},
        )
        callback = TensorBoardCallback(controller=controller, log_interval=1, verbose=0)
        model = MagicMock()
        model.num_timesteps = 1
        model.logger = MagicMock()
        callback.init_callback(model)
        callback._start_time = 0.0
        callback.locals = {"infos": []}
        with patch("surg_rl.rl.callbacks.time.time", return_value=1.0):
            callback.on_step()
        model.logger.record.assert_any_call("curriculum/stage", "easy")
        model.logger.record.assert_any_call("curriculum/difficulty", 0.5)

    def test_no_controller(self):
        callback = TensorBoardCallback(controller=None, log_interval=1, verbose=0)
        model = MagicMock()
        model.num_timesteps = 1
        model.logger = MagicMock()
        callback.init_callback(model)
        callback._start_time = 0.0
        callback.locals = {"infos": []}
        with patch("surg_rl.rl.callbacks.time.time", return_value=1.0):
            callback.on_step()
        # Should not crash and should still log FPS
        model.logger.record.assert_any_call("time/fps", 1.0)

    def test_no_logger(self):
        callback = TensorBoardCallback(controller=None, log_interval=1, verbose=0)
        model = MagicMock()
        model.num_timesteps = 1
        model.logger = None
        callback.init_callback(model)
        callback._start_time = 0.0
        callback.locals = {"infos": []}
        with patch("surg_rl.rl.callbacks.time.time", return_value=1.0):
            result = callback.on_step()
        assert result is True

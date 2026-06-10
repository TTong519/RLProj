"""Tests for WandbCallback and MLflowCallback.

These callbacks are optional dependencies (wandb/mlflow).
Tests mock both the presence and absence of these libraries.
"""

from unittest.mock import MagicMock, patch

from surg_rl.rl.callbacks import MLflowCallback, WandbCallback


class TestWandbCallback:
    """Tests for WandbCallback."""

    def test_init_default(self) -> None:
        """Default initialization sets correct defaults."""
        cb = WandbCallback()
        assert cb.project_name == "surg-rl"
        assert cb.experiment_name is None
        assert cb.wandb_api_key is None
        assert cb.controller is None
        assert cb._step == 0
        assert cb._episode_rewards == []
        assert cb._episode_lengths == []
        assert cb._start_time is None

    def test_init_custom(self) -> None:
        """Custom initialization sets provided values."""
        cb = WandbCallback(
            project_name="test-proj",
            experiment_name="exp-1",
            wandb_api_key="sk-test",
        )
        assert cb.project_name == "test-proj"
        assert cb.experiment_name == "exp-1"
        assert cb.wandb_api_key == "sk-test"

    @patch("surg_rl.rl.callbacks.logger")
    def test_on_training_start_without_wandb(self, mock_logger) -> None:
        """Warns gracefully when wandb is not installed."""
        cb = WandbCallback()
        with patch.dict("sys.modules", {"wandb": None}):
            cb._on_training_start()
        mock_logger.warning.assert_called_once()
        assert "wandb not installed" in str(mock_logger.warning.call_args[0][0])

    def test_on_training_start_with_wandb_api_key(self) -> None:
        """Logs in with API key when provided."""
        mock_wandb = MagicMock()
        cb = WandbCallback(wandb_api_key="sk-test")
        with patch.dict("sys.modules", {"wandb": mock_wandb}):
            cb._on_training_start()
        mock_wandb.login.assert_called_once_with(key="sk-test")
        mock_wandb.init.assert_called_once()

    def test_on_step_logs_episode(self) -> None:
        """Episode info is collected from infos."""
        cb = WandbCallback()
        cb._start_time = 0.0
        cb.locals = {"infos": [{"episode": {"r": 10.0, "l": 50}}]}
        cb._on_step()
        assert cb._episode_rewards == [10.0]
        assert cb._episode_lengths == [50]

    def test_log_metrics_with_controller(self) -> None:
        """Controller state is logged when available."""
        mock_wandb = MagicMock()
        mock_controller = MagicMock()
        mock_controller.get_curriculum_stage.return_value = MagicMock(value=2)
        mock_controller.get_difficulty.return_value = 0.75
        mock_params = MagicMock()
        mock_params.physics = {"mass": 1.5, "stiffness": 200.0}
        mock_params.visual = {"color": "#FF0000"}  # non-numeric -> skipped
        mock_params.dynamics = {"damping": 0.9}
        mock_controller.current_params = mock_params

        cb = WandbCallback(controller=mock_controller)
        cb._start_time = 0.0
        cb._step = 100
        cb._episode_rewards = [1.0, 2.0]
        cb._episode_lengths = [10, 20]

        with patch.dict("sys.modules", {"wandb": mock_wandb}):
            cb._log_metrics()

        call_args = mock_wandb.log.call_args
        metrics = call_args[0][0]
        assert metrics["curriculum/stage"] == 2
        assert metrics["curriculum/difficulty"] == 0.75
        assert metrics["randomization/physics/mass"] == 1.5
        assert metrics["randomization/physics/stiffness"] == 200.0
        assert "randomization/visual/color" not in metrics  # non-numeric skipped
        assert metrics["randomization/dynamics/damping"] == 0.9

    def test_on_training_end(self) -> None:
        """Finishes wandb run on training end."""
        mock_wandb = MagicMock()
        cb = WandbCallback()
        with patch.dict("sys.modules", {"wandb": mock_wandb}):
            cb._on_training_end()
        mock_wandb.finish.assert_called_once()


class TestMLflowCallback:
    """Tests for MLflowCallback."""

    def test_init_default(self) -> None:
        """Default initialization sets correct defaults."""
        cb = MLflowCallback()
        assert cb.experiment_name == "surg-rl"
        assert cb.tracking_uri is None
        assert cb.controller is None
        assert cb._step == 0
        assert cb._episode_rewards == []
        assert cb._episode_lengths == []
        assert cb._start_time is None

    def test_init_custom(self) -> None:
        """Custom initialization sets provided values."""
        cb = MLflowCallback(experiment_name="exp-1", tracking_uri="http://localhost:5000")
        assert cb.experiment_name == "exp-1"
        assert cb.tracking_uri == "http://localhost:5000"

    @patch("surg_rl.rl.callbacks.logger")
    def test_on_training_start_without_mlflow(self, mock_logger) -> None:
        """Warns gracefully when mlflow is not installed."""
        cb = MLflowCallback()
        with patch.dict("sys.modules", {"mlflow": None}):
            cb._on_training_start()
        mock_logger.warning.assert_called_once()
        assert "mlflow not installed" in str(mock_logger.warning.call_args[0][0])

    def test_on_training_start_with_tracking_uri(self) -> None:
        """Sets tracking URI when provided."""
        mock_mlflow = MagicMock()
        mock_mlflow.start_run.return_value = MagicMock(info=MagicMock(run_id="run-123"))
        cb = MLflowCallback(tracking_uri="http://localhost:5000")
        with patch.dict("sys.modules", {"mlflow": mock_mlflow}):
            cb._on_training_start()
        mock_mlflow.set_tracking_uri.assert_called_once_with("http://localhost:5000")
        mock_mlflow.set_experiment.assert_called_once()
        mock_mlflow.start_run.assert_called_once()

    def test_on_step_logs_episode(self) -> None:
        """Episode info is collected from infos."""
        cb = MLflowCallback()
        cb._start_time = 0.0
        cb.locals = {"infos": [{"episode": {"r": 5.0, "l": 30}}]}
        cb._on_step()
        assert cb._episode_rewards == [5.0]
        assert cb._episode_lengths == [30]

    def test_log_metrics_with_controller(self) -> None:
        """Controller state is logged when available."""
        mock_mlflow = MagicMock()
        mock_controller = MagicMock()
        mock_controller.get_curriculum_stage.return_value = MagicMock(value=3)
        mock_controller.get_difficulty.return_value = 0.5
        mock_params = MagicMock()
        mock_params.physics = {"mass": 2.0}
        mock_params.visual = {}
        mock_params.dynamics = {}
        mock_controller.current_params = mock_params

        cb = MLflowCallback(controller=mock_controller)
        cb._start_time = 0.0
        cb._step = 100
        cb._episode_rewards = [3.0, 4.0]
        cb._episode_lengths = [15, 25]

        with patch.dict("sys.modules", {"mlflow": mock_mlflow}):
            cb._log_metrics()

        assert mock_mlflow.log_metric.call_count >= 5
        calls = {call[0][0]: call[0][1] for call in mock_mlflow.log_metric.call_args_list}
        assert calls["curriculum_stage"] == 3
        assert calls["curriculum_difficulty"] == 0.5
        assert calls["randomization_physics_mass"] == 2.0

    def test_on_training_end(self) -> None:
        """Ends mlflow run on training end."""
        mock_mlflow = MagicMock()
        cb = MLflowCallback()
        with patch.dict("sys.modules", {"mlflow": mock_mlflow}):
            cb._on_training_end()
        mock_mlflow.end_run.assert_called_once()

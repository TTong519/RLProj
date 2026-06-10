"""Tests for DreamerV3 feasibility spike orchestrator and report generation."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from surg_rl.dreamer.spike import (
    DEFAULT_THRESHOLDS,
    SPIKE_REPORT_PATH,
    SpikeOrchestrator,
    check_spike_status,
    run_spike,
)


class TestModuleConstants:
    """Test module-level constants."""

    def test_spike_report_path_is_models_dreamerv3_spike_report_json(self):
        assert isinstance(SPIKE_REPORT_PATH, Path)
        assert SPIKE_REPORT_PATH == Path("models/dreamerv3/spike_report.json")

    def test_default_thresholds_reconstruction_mse(self):
        assert DEFAULT_THRESHOLDS["reconstruction_mse"] == 0.01

    def test_default_thresholds_reward_mae(self):
        assert DEFAULT_THRESHOLDS["reward_mae"] == 0.5


class TestSpikeOrchestratorConstructor:
    """Test SpikeOrchestrator default and custom constructor values."""

    def test_default_constructor(self):
        orch = SpikeOrchestrator()
        assert orch.task == "suturing"
        assert orch.obs_type == "pixels"
        assert orch.total_steps == 100000
        assert orch.eval_episodes == 10
        assert orch.pixel_resolution == (64, 64)
        assert orch.thresholds == DEFAULT_THRESHOLDS

    def test_custom_constructor(self):
        custom_thresholds = {"reconstruction_mse": 0.05, "reward_mae": 1.0}
        orch = SpikeOrchestrator(
            task="grasping",
            obs_type="state",
            total_steps=5000,
            eval_episodes=3,
            pixel_resolution=(128, 128),
            thresholds=custom_thresholds,
        )
        assert orch.task == "grasping"
        assert orch.obs_type == "state"
        assert orch.total_steps == 5000
        assert orch.eval_episodes == 3
        assert orch.pixel_resolution == (128, 128)
        assert orch.thresholds == custom_thresholds

    def test_constructor_initializes_training_curves(self):
        orch = SpikeOrchestrator()
        assert "reconstruction_loss" in orch._training_curves
        assert "reward_loss" in orch._training_curves
        assert "total_loss" in orch._training_curves
        assert orch._training_curves["reconstruction_loss"] == []


class TestCreateSpikeScene:
    """Test _create_spike_scene."""

    def test_create_spike_scene_falls_back_to_programmatic_when_no_file(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        orch = SpikeOrchestrator(task="suturing", obs_type="pixels")
        scene = orch._create_spike_scene()
        assert scene is not None
        assert len(scene.instruments) == 1
        assert scene.instruments[0].name == "forceps"
        assert scene.dreamer is not None
        assert scene.dreamer.obs_type == "pixels"

    def test_create_spike_scene_uses_task_name_in_instrument(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        orch = SpikeOrchestrator(task="grasping", obs_type="state")
        scene = orch._create_spike_scene()
        assert scene.dreamer.obs_type == "state"
        assert scene.task is not None
        assert scene.task.task_type == "suturing"

    def test_create_spike_scene_tries_to_load_existing_file(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        scenes_dir = tmp_path / "scenes"
        scenes_dir.mkdir()
        scene_file = scenes_dir / "suturing.json"
        scene_file.write_text("{}")
        sentinel_scene = MagicMock()
        with patch("surg_rl.dreamer.spike.load_scene", return_value=sentinel_scene) as mock_load:
            orch = SpikeOrchestrator(task="suturing", obs_type="pixels")
            scene = orch._create_spike_scene()
            assert scene is sentinel_scene
            mock_load.assert_called_once()
            args, _ = mock_load.call_args
            assert args[0] == "scenes/suturing.json"


class TestGenerateReport:
    """Test _generate_report output structure and fields."""

    def _make_orchestrator(self, **kwargs):
        defaults = dict(task="suturing", obs_type="pixels", total_steps=100)
        defaults.update(kwargs)
        return SpikeOrchestrator(**defaults)

    def test_passed_status_sets_proceed_recommendation(self):
        orch = self._make_orchestrator()
        report = orch._generate_report(
            passed=True,
            reconstruction_mse=0.001,
            reward_mae=0.1,
            eval_metrics={},
        )
        assert report["status"] == "passed"
        assert report["recommendation"] == "proceed with integration"
        assert report["deferral_reason"] is None

    def test_failed_mse_sets_failed_status_and_deferral(self):
        orch = self._make_orchestrator()
        report = orch._generate_report(
            passed=False,
            reconstruction_mse=0.05,
            reward_mae=0.1,
            eval_metrics={},
        )
        assert report["status"] == "failed"
        assert report["recommendation"] == "defer to v0.5.0"
        assert "reconstruction_mse_above_threshold" in report["deferral_reason"]

    def test_failed_mae_sets_deferral_reason(self):
        orch = self._make_orchestrator()
        report = orch._generate_report(
            passed=False,
            reconstruction_mse=0.001,
            reward_mae=0.9,
            eval_metrics={},
        )
        assert report["status"] == "failed"
        assert "reward_mae_above_threshold" in report["deferral_reason"]

    def test_both_failed_uses_and_join(self):
        orch = self._make_orchestrator()
        report = orch._generate_report(
            passed=False,
            reconstruction_mse=0.05,
            reward_mae=0.9,
            eval_metrics={},
        )
        assert report["deferral_reason"] == (
            "reconstruction_mse_above_threshold_and_reward_mae_above_threshold"
        )

    def test_report_includes_three_training_curves_keys(self):
        orch = self._make_orchestrator()
        report = orch._generate_report(
            passed=True,
            reconstruction_mse=0.001,
            reward_mae=0.1,
            eval_metrics={},
        )
        curves = report["training_curves"]
        assert "reconstruction_loss" in curves
        assert "reward_loss" in curves
        assert "total_loss" in curves

    def test_report_includes_analysis_string(self):
        orch = self._make_orchestrator()
        report = orch._generate_report(
            passed=True,
            reconstruction_mse=0.001,
            reward_mae=0.1,
            eval_metrics={},
        )
        assert isinstance(report["analysis"], str)
        assert "DreamerV3 Feasibility Spike Analysis" in report["analysis"]

    def test_report_includes_thresholds_results_timestamp(self):
        orch = self._make_orchestrator()
        report = orch._generate_report(
            passed=True,
            reconstruction_mse=0.001,
            reward_mae=0.1,
            eval_metrics={},
        )
        assert "thresholds" in report
        assert "results" in report
        assert "timestamp" in report
        assert report["thresholds"] == orch.thresholds
        assert report["results"]["reconstruction_mse"] == 0.001
        assert report["results"]["reward_mae"] == 0.1

    def test_report_results_merges_eval_metrics(self):
        orch = self._make_orchestrator()
        report = orch._generate_report(
            passed=True,
            reconstruction_mse=0.001,
            reward_mae=0.1,
            eval_metrics={"success_rate": 0.8, "mean_reward": 5.0},
        )
        assert report["results"]["success_rate"] == 0.8
        assert report["results"]["mean_reward"] == 5.0


class TestCheckSpikeStatus:
    """Test check_spike_status() helper."""

    def test_returns_none_when_report_does_not_exist(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        result = check_spike_status()
        assert result is None

    def test_returns_dict_when_report_exists(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        report_dir = tmp_path / "models" / "dreamerv3"
        report_dir.mkdir(parents=True)
        report_path = report_dir / "spike_report.json"
        report_path.write_text(json.dumps({"status": "passed", "foo": "bar"}))
        result = check_spike_status()
        assert result is not None
        assert result["status"] == "passed"
        assert result["foo"] == "bar"


class TestRunSpikeConvenience:
    """Test run_spike() convenience function."""

    def test_run_spike_calls_orchestrator_run(self):
        with patch.object(SpikeOrchestrator, "run", return_value=(True, {"status": "passed"})) as mock_run:
            passed, report = run_spike(task="grasping", obs_type="state", steps=1000, eval_episodes=2)
            assert passed is True
            assert report["status"] == "passed"
            assert mock_run.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""Tests for benchmark integration of DreamerV3 (Phase 24)."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from surg_rl.benchmark.experiment_config import ExperimentConfig
from surg_rl.benchmark.experiment_runner import ExperimentRunner
from surg_rl.benchmark.plots import DREAMER_COLOR
from surg_rl.benchmark.report import ReportGenerator


class TestDreamerColorConstant:
    """Test DREAMER_COLOR constant in plots.py."""

    def test_dreamer_color_exists(self):
        assert DREAMER_COLOR is not None

    def test_dreamer_color_is_orange_hex(self):
        assert DREAMER_COLOR == "#FF8C00"


class TestExperimentConfigDreamerFields:
    """Test ExperimentConfig has the dreamer comparison fields."""

    def test_dreamer_comparison_default_false(self):
        cfg = ExperimentConfig()
        assert cfg.dreamer_comparison is False

    def test_dreamer_obs_types_default(self):
        cfg = ExperimentConfig()
        assert "state" in cfg.dreamer_obs_types

    def test_dreamer_eval_episodes_default_10(self):
        cfg = ExperimentConfig()
        assert cfg.dreamer_eval_episodes == 10

    def test_dreamer_obs_types_can_be_set(self):
        cfg = ExperimentConfig(dreamer_obs_types=["pixels", "state"])
        assert "pixels" in cfg.dreamer_obs_types
        assert "state" in cfg.dreamer_obs_types


class TestExperimentRunnerDreamerEvaluation:
    """Test ExperimentRunner._run_dreamer_evaluation."""

    def _make_runner(self, config_overrides=None):
        cfg = ExperimentConfig(
            experiment_name="test_bench",
            task="suturing",
            backends=["mujoco"],
            seeds=[42],
            dreamer_comparison=True,
            output_dir="results/test",
        )
        if config_overrides:
            for k, v in config_overrides.items():
                setattr(cfg, k, v)
        runner = ExperimentRunner(cfg)
        return runner

    def test_returns_deferred_when_spike_report_failed(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        spike_dir = tmp_path / "models" / "dreamerv3"
        spike_dir.mkdir(parents=True)
        report_path = spike_dir / "spike_report.json"
        report_path.write_text(
            json.dumps(
                {
                    "status": "failed",
                    "results": {
                        "reconstruction_mse": 0.05,
                        "reward_mae": 0.9,
                    },
                }
            )
        )

        runner = self._make_runner()
        with patch("surg_rl.benchmark.experiment_runner.check_spike_status") as mock_check:
            mock_check.return_value = {
                "status": "failed",
                "results": {"reconstruction_mse": 0.05, "reward_mae": 0.9},
            }
            results = runner._run_dreamer_evaluation(["mujoco"])

        assert len(results) == 1
        assert results[0].status == "deferred"
        assert "Spike failed" in results[0].error

    def test_returns_pending_when_spike_report_is_none(self):
        runner = self._make_runner()
        with patch("surg_rl.benchmark.experiment_runner.check_spike_status", return_value=None):
            results = runner._run_dreamer_evaluation(["mujoco"])
        assert len(results) == 1
        assert results[0].status == "pending"
        assert "spike not run" in results[0].error.lower()

    def test_returns_pending_for_pixels_when_no_checkpoint(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        runner = self._make_runner({"dreamer_obs_types": ["pixels"]})
        with (
            patch(
                "surg_rl.benchmark.experiment_runner.check_spike_status",
                return_value={"status": "passed"},
            ),
        ):
            results = runner._run_dreamer_evaluation(["mujoco"])
        assert len(results) == 1
        assert results[0].status == "pending"
        assert "no checkpoint" in results[0].error.lower()

    def test_returns_pending_for_state_when_no_checkpoint(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        runner = self._make_runner({"dreamer_obs_types": ["state"]})
        with patch(
            "surg_rl.benchmark.experiment_runner.check_spike_status",
            return_value={"status": "passed"},
        ):
            results = runner._run_dreamer_evaluation(["mujoco"])
        assert len(results) == 1
        assert results[0].status == "pending"

    def test_returns_pending_for_both_pixels_and_state_when_no_checkpoints(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.chdir(tmp_path)
        runner = self._make_runner({"dreamer_obs_types": ["pixels", "state"]})
        with patch(
            "surg_rl.benchmark.experiment_runner.check_spike_status",
            return_value={"status": "passed"},
        ):
            results = runner._run_dreamer_evaluation(["mujoco"])
        assert len(results) == 2
        assert all(r.status == "pending" for r in results)

    def test_calls_evaluate_checkpoint_when_checkpoint_exists(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        ckpt_dir = tmp_path / "models" / "dreamerv3" / "suturing_state"
        ckpt_dir.mkdir(parents=True)
        ckpt_file = ckpt_dir / "final.pt"
        ckpt_file.write_bytes(b"x")

        runner = self._make_runner({"dreamer_obs_types": ["state"]})
        with (
            patch(
                "surg_rl.benchmark.experiment_runner.check_spike_status",
                return_value={"status": "passed"},
            ),
            patch(
                "surg_rl.benchmark.experiment_runner.evaluate_checkpoint",
                return_value={"reconstruction_mse": 0.0},
            ) as mock_eval,
        ):
            results = runner._run_dreamer_evaluation(["mujoco"])
        assert mock_eval.called
        assert len(results) == 1
        assert results[0].status == "success"
        assert results[0].eval_metrics["reconstruction_mse"] == 0.0


class TestReportGeneratorDreamerV3:
    """Test ReportGenerator._build_results_json for DreamerV3 section."""

    def _make_generator(self, dreamer_results=None, results=None):
        cfg = ExperimentConfig(
            experiment_name="test_bench",
            task="suturing",
            backends=["mujoco"],
            seeds=[42],
        )
        aggregated = results or {}
        return ReportGenerator(
            config=cfg,
            aggregated_results=aggregated,
            plot_paths=[],
            output_dir=Path("results/test"),
        )

    def test_dreamer_v3_section_reflects_failed_spike(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        spike_dir = tmp_path / "models" / "dreamerv3"
        spike_dir.mkdir(parents=True)
        report_path = spike_dir / "spike_report.json"
        report_path.write_text(
            json.dumps(
                {
                    "status": "failed",
                    "results": {"reconstruction_mse": 0.05, "reward_mae": 0.9},
                    "deferral_reason": "reconstruction_mse_above_threshold",
                }
            )
        )
        gen = self._make_generator()
        data = gen._build_results_json()
        assert data["dreamer_v3"]["status"] == "failed"
        assert data["dreamer_v3"]["spike_metrics"]["reconstruction_mse"] == 0.05
        assert data["dreamer_v3"]["deferral_reason"] == "reconstruction_mse_above_threshold"

    def test_benchmark_scope_sb3_only_when_failed(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        spike_dir = tmp_path / "models" / "dreamerv3"
        spike_dir.mkdir(parents=True)
        (spike_dir / "spike_report.json").write_text(
            json.dumps({"status": "failed", "results": {}, "deferral_reason": "x"})
        )
        gen = self._make_generator()
        data = gen._build_results_json()
        assert data["benchmark_scope"] == "sb3_only"

    def test_benchmark_scope_sb3_only_when_pending(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        gen = self._make_generator()
        data = gen._build_results_json()
        assert data["benchmark_scope"] == "sb3_only"
        assert data["dreamer_v3"]["status"] == "pending — Phase 24"

    def test_benchmark_scope_sb3_and_dreamer_when_passed(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        spike_dir = tmp_path / "models" / "dreamerv3"
        spike_dir.mkdir(parents=True)
        (spike_dir / "spike_report.json").write_text(json.dumps({"status": "passed"}))
        gen = self._make_generator()
        data = gen._build_results_json()
        assert data["benchmark_scope"] == "sb3_and_dreamer"
        assert data["dreamer_v3"]["status"] == "passed"

    def test_dreamer_v3_section_includes_spike_metrics_when_failed(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        spike_dir = tmp_path / "models" / "dreamerv3"
        spike_dir.mkdir(parents=True)
        (spike_dir / "spike_report.json").write_text(
            json.dumps(
                {
                    "status": "failed",
                    "results": {"reconstruction_mse": 0.123, "reward_mae": 0.456},
                    "deferral_reason": "both_above_threshold",
                }
            )
        )
        gen = self._make_generator()
        data = gen._build_results_json()
        assert "spike_metrics" in data["dreamer_v3"]
        assert data["dreamer_v3"]["spike_metrics"]["reconstruction_mse"] == 0.123
        assert data["dreamer_v3"]["spike_metrics"]["reward_mae"] == 0.456
        assert data["dreamer_v3"]["deferral_reason"] == "both_above_threshold"

    def test_missing_spike_report_uses_default_status(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        gen = self._make_generator()
        data = gen._build_results_json()
        assert data["dreamer_v3"]["status"] == "pending — Phase 24"
        assert "spike_metrics" not in data["dreamer_v3"]
        assert "deferral_reason" not in data["dreamer_v3"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""Tests for DreamerV3 training task type support."""

import inspect
import json
from unittest.mock import MagicMock

import pytest

from surg_rl.dreamer import training as dreamer_training
from surg_rl.dreamer.training import _create_scene_for_task, run_dreamer_training
from surg_rl.scene_definition.schema import InstrumentType, TissueType


class TestDreamerTrainingTaskTypes:
    """Test that all 6 surgical task types create valid SceneDefinitions."""

    @pytest.mark.parametrize(
        "task,expected_instrument,expected_tissue",
        [
            ("suturing", InstrumentType.NEEDLE_DRIVER, TissueType.ORGAN),
            ("knot_tying", InstrumentType.KNOT_TIER, TissueType.CUSTOM),
            ("needle_insertion", InstrumentType.NEEDLE, TissueType.ORGAN),
            ("grasping", InstrumentType.FORCEPS, TissueType.SKIN),
            ("cutting", InstrumentType.SCISSORS, TissueType.SKIN),
            ("dissection", InstrumentType.SCISSORS, TissueType.MUSCLE),
        ],
    )
    def test_task_creates_scene_with_correct_types(
        self, task, expected_instrument, expected_tissue
    ):
        """Test each task creates scene with correct instrument and tissue types."""
        scene = _create_scene_for_task(task, "state", (64, 64))

        assert scene is not None, f"Scene creation failed for {task}"
        assert (
            len(scene.instruments) == 1
        ), f"Expected 1 instrument for {task}, got {len(scene.instruments)}"
        assert len(scene.tissues) == 1, f"Expected 1 tissue for {task}, got {len(scene.tissues)}"

        assert (
            scene.instruments[0].type == expected_instrument
        ), f"Expected instrument {expected_instrument} for {task}, got {scene.instruments[0].type}"
        assert (
            scene.tissues[0].type == expected_tissue
        ), f"Expected tissue {expected_tissue} for {task}, got {scene.tissues[0].type}"

    def test_all_tasks_have_unique_task_types(self):
        """Test all 6 tasks produce scenes with unique task_type matching input."""
        tasks = ["suturing", "knot_tying", "needle_insertion", "grasping", "cutting", "dissection"]
        seen_types = set()

        for task in tasks:
            scene = _create_scene_for_task(task, "state", (64, 64))
            assert scene.task is not None, f"No task config for {task}"
            assert (
                scene.task.task_type == task
            ), f"Task type mismatch for {task}: {scene.task.task_type}"
            assert task not in seen_types, f"Duplicate task type: {task}"
            seen_types.add(task)

    def test_dreamer_config_present(self):
        """Test DreamerConfig is present with correct fields for all tasks."""
        tasks = ["suturing", "knot_tying", "needle_insertion", "grasping", "cutting", "dissection"]

        for task in tasks:
            scene = _create_scene_for_task(task, "pixels", (64, 64))
            assert scene.dreamer is not None, f"No DreamerConfig for {task}"
            assert scene.dreamer.obs_type == "pixels", f"Wrong obs_type for {task}"
            assert scene.dreamer.pixel_resolution == (64, 64), f"Wrong pixel_resolution for {task}"
            assert scene.dreamer.process_isolation is True
            assert scene.dreamer.memory_fraction == 0.4

    def test_state_observation_mode(self):
        """Test state observation mode works for all tasks."""
        tasks = ["suturing", "knot_tying", "needle_insertion", "grasping", "cutting", "dissection"]

        for task in tasks:
            scene = _create_scene_for_task(task, "state", (64, 64))
            assert scene.dreamer.obs_type == "state"

    def test_no_custom_fallback_for_new_tasks(self):
        """Test that new tasks don't fall back to CUSTOM instrument type."""
        for task in ["knot_tying", "needle_insertion", "dissection"]:
            scene = _create_scene_for_task(task, "state", (64, 64))
            assert (
                scene.instruments[0].type != InstrumentType.CUSTOM
            ), f"{task} should not use CUSTOM instrument type"
            assert (
                scene.tissues[0].type != TissueType.CUSTOM or task == "knot_tying"
            ), f"{task} should not use CUSTOM tissue type (except knot_tying uses CUSTOM intentionally)"


class TestTrainingMetricsSave:
    """Regression tests for the end-of-training metrics save (Phase 26 D-01).

    The original code had `json.dump(metrics_log, f, indig=2)` at the
    final-save site which raised `TypeError: got an unexpected keyword
    argument 'indig'` at end of every real training run. The fix uses
    `indent=2` and must be regression-tested.
    """

    def test_no_indig_kwarg_in_training_source(self):
        """Source code must not contain `indig=` (the typo)."""
        src = inspect.getsource(dreamer_training)
        assert "indig=" not in src, (
            "training.py still contains 'indig=' typo — would raise "
            "TypeError at end of training. Expected 'indent='."
        )

    def test_final_metrics_save_uses_indent_keyword(self, tmp_path):
        """End-of-training save writes an indented, human-readable training_metrics.json."""
        fake_subprocess = MagicMock()
        fake_subprocess.train.return_value = iter(
            [
                {"step": 100, "reconstruction_loss": 0.1, "reward_loss": 0.2, "total_loss": 0.3},
                {"step": 200, "reconstruction_loss": 0.05, "reward_loss": 0.1, "total_loss": 0.15},
            ]
        )
        fake_subprocess.evaluate.return_value = {
            "success_rate": 0.5,
            "mean_reward": 1.0,
            "mean_episode_length": 50,
        }

        monkeypatch_calls = []

        def _patch_subprocess_module():
            import surg_rl.dreamer.training as t

            original = getattr(t, "DreamerSubprocess", None)
            t.DreamerSubprocess = MagicMock(return_value=fake_subprocess)
            monkeypatch_calls.append("patched")
            return original

        original = _patch_subprocess_module()
        try:
            # Drive run_dreamer_training to the final save path.
            run_dreamer_training(
                task="suturing",
                obs_type="state",
                total_steps=200,
                eval_episodes=1,
                eval_every=100,
                checkpoint_dir=str(tmp_path / "checkpoints"),
            )
        finally:
            import surg_rl.dreamer.training as t

            t.DreamerSubprocess = original

        # Verify the final metrics file exists, parses, and is human-readable.
        metrics_path = tmp_path / "checkpoints" / "training_metrics.json"
        assert metrics_path.exists(), f"Expected {metrics_path} to exist"
        content = metrics_path.read_text()
        # Indented JSON has internal newlines; a single-line minified blob would not.
        assert "\n" in content, "training_metrics.json is not indented (indent=2 missing?)"
        # Must round-trip through json.load.
        loaded = json.loads(content)
        assert loaded["task"] == "suturing"
        assert loaded["total_steps"] == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

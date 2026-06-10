"""Tests for DreamerV3 training task type support."""

import pytest

from surg_rl.dreamer.training import _create_scene_for_task
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

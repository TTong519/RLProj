"""Tests for backend-agnostic task success termination (Phase 2)."""
from typing import Any

import numpy as np
import pytest

from surg_rl.rl.task_termination import check_task_success, _parse_distance_criteria
from surg_rl.scene_definition.schema import SceneDefinition
from surg_rl.simulators.base_simulator import Observation


def _make_obs(ee_pos: Any = None, ee_quat: Any = None) -> Observation:
    obs = Observation()
    obs.end_effector_pos = np.array(ee_pos, dtype=np.float32) if ee_pos is not None else None
    obs.end_effector_quat = (
        np.array(ee_quat, dtype=np.float32) if ee_quat is not None else None
    )
    return obs


def _minimal_scene_with_task(threshold: float = 0.02) -> SceneDefinition:
    data: dict[str, Any] = {
        "metadata": {"name": "task_scene", "version": "1.0"},
        "task": {
            "name": "reach_target",
            "description": "Reach target pose",
            "success_threshold": threshold,
            "objectives": [
                {
                    "name": "reach",
                    "description": "Reach target",
                    "success_criteria": "distance < 0.03",
                }
            ],
        },
        "robots": [
            {
                "name": "robot0",
                "type": "custom",
                "base_pose": {
                    "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                },
                "links": [
                    {"name": "base", "physics": {"mass": 1.0}},
                ],
                "joints": [
                    {
                        "name": "joint0",
                        "type": "revolute",
                        "limits": {"lower": -1.0, "upper": 1.0},
                        "initial_position": 0.0,
                        "damping": 0.1,
                        "friction": 0.0,
                    }
                ],
            }
        ],
    }
    return SceneDefinition(**data)


class TestParseDistanceCriteria:
    def test_simple_less_than(self) -> None:
        assert _parse_distance_criteria("distance < 0.05") == 0.05

    def test_with_unit_m(self) -> None:
        assert _parse_distance_criteria("reach target within 0.02m") == 0.02

    def test_no_number_returns_none(self) -> None:
        assert _parse_distance_criteria("no criteria here") is None

    def test_none_input(self) -> None:
        assert _parse_distance_criteria(None) is None  # type: ignore[arg-type]


class TestCheckTaskSuccess:
    def test_no_task_returns_false(self) -> None:
        scene = _minimal_scene_with_task()
        scene.task = None  # type: ignore[assignment]
        success, details = check_task_success(scene, _make_obs([0, 0, 0]), np.zeros(3))
        assert not success
        assert details == {}

    def test_within_threshold_succeeds(self) -> None:
        scene = _minimal_scene_with_task(threshold=0.05)
        success, details = check_task_success(
            scene,
            _make_obs([0.01, 0.01, 0.01]),
            np.array([0.0, 0.0, 0.0]),
        )
        assert success
        assert "distance" in details

    def test_outside_threshold_fails(self) -> None:
        scene = _minimal_scene_with_task(threshold=0.01)
        success, details = check_task_success(
            scene,
            _make_obs([0.1, 0.1, 0.1]),
            np.array([0.0, 0.0, 0.0]),
        )
        assert not success

    def test_stricter_objective_tightens(self) -> None:
        scene = _minimal_scene_with_task(threshold=0.1)
        # objective says distance < 0.03; overall threshold is 0.1
        success, details = check_task_success(
            scene,
            _make_obs([0.05, 0.0, 0.0]),
            np.zeros(3),
        )
        # 0.05 > 0.03 → fails because objective threshold is stricter
        assert not success

    def test_info_override_success(self) -> None:
        scene = _minimal_scene_with_task(threshold=0.01)
        success, details = check_task_success(
            scene,
            _make_obs([0.1, 0.0, 0.0]),
            np.zeros(3),
            info={"success": True},
        )
        assert success

    def test_missing_ee_pos_returns_false(self) -> None:
        scene = _minimal_scene_with_task()
        obs = Observation()
        success, details = check_task_success(scene, obs, np.zeros(3))
        assert not success


class TestEnvironmentTaskTermination:
    def test_import_and_call_exists(self) -> None:
        """Ensure check_task_success is imported and called inside step()."""
        from surg_rl.rl.environment import SurgicalEnv, SurgicalEnvConfig
        import inspect

        scene = _minimal_scene_with_task(threshold=0.1)
        env = SurgicalEnv(
            config=SurgicalEnvConfig(
                scene=scene,
                simulator_type="mujoco",
                render_mode=None,
                max_episode_steps=100,
            )
        )
        # The fact that env instantiated without error means _default_action_config
        # queried get_num_controls and action space was sized correctly.
        assert "check_task_success" in inspect.getsource(env.step)

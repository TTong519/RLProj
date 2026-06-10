"""Tests for task geometry binding to observation fields (TASK-01, TASK-02)."""

from typing import Any

import numpy as np
import pytest

from surg_rl.scene_definition.schema import (
    InstrumentConfig,
    InstrumentType,
    Orientation,
    Pose,
    Position,
    SceneDefinition,
    SimulatorType,
    TaskObjective,
    TissueConfig,
    TissueType,
)
from surg_rl.simulators import MuJoCoSimulator, PyBulletSimulator


def _scene_with_target_body(
    simulator_type: SimulatorType = SimulatorType.MUJOCO,
    target_body: str | None = None,
    objective_name: str = "needle_pickup",
    success_criteria: str = "Needle grasped",
    with_instrument: bool = True,
) -> SceneDefinition:
    """Build a minimal scene with a single task objective."""
    instruments: list[Any] = []
    if with_instrument:
        instruments.append(
            InstrumentConfig(
                name="needle_instrument",
                type=InstrumentType.CUSTOM,
                pose=Pose(
                    position=Position(x=0.12, y=0.0, z=0.05),
                    orientation=Orientation(w=1.0, x=0.0, y=0.0, z=0.0),
                ),
            )
        )

    objectives = [
        TaskObjective(
            name=objective_name,
            description="Test objective",
            success_criteria=success_criteria,
            target_body=target_body,
        )
    ]

    data: dict[str, Any] = {
        "metadata": {"name": "target_body_scene", "version": "1.0"},
        "simulator": simulator_type.value,
        "robots": [
            {
                "name": "robot0",
                "type": "robotic_arm",
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
        "tissues": [
            {
                "name": "entry_marker",
                "type": "skin",
                "pose": {
                    "position": {"x": 0.2, "y": 0.0, "z": 0.05},
                    "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                },
                "geometry": {
                    "primitive": "box",
                    "dimensions": [0.01, 0.01, 0.01],
                },
                "physics": {"mass": 0.01},
            },
            {
                "name": "exit_marker",
                "type": "skin",
                "pose": {
                    "position": {"x": 0.3, "y": 0.0, "z": 0.05},
                    "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                },
                "geometry": {
                    "primitive": "box",
                    "dimensions": [0.01, 0.01, 0.01],
                },
                "physics": {"mass": 0.01},
            },
        ],
        "instruments": instruments,
        "task": {
            "name": "test_task",
            "description": "Test task",
            "objectives": [obj.model_dump() for obj in objectives],
        },
    }
    return SceneDefinition(**data)


class TestPyBulletTaskGeometry:
    """TASK-01 / TASK-02 for PyBullet."""

    def test_needle_pos_from_target_body(self):
        """obs.needle_pos matches target_body body position within 1e-3."""
        sim = PyBulletSimulator()
        scene = _scene_with_target_body(
            simulator_type=SimulatorType.PYBULLET,
            target_body="needle_instrument",
            objective_name="needle_pickup",
        )
        sim.load_scene(scene)
        obs = sim._get_observation()
        assert obs.needle_pos is not None
        # Instrument pose in scene: x=0.12, y=0.0, z=0.05
        expected = np.array([0.12, 0.0, 0.05])
        assert np.linalg.norm(obs.needle_pos - expected) < 1e-3

    def test_entry_exit_from_target_body(self):
        """obs.entry_point and obs.exit_point match target_body bodies."""
        sim = PyBulletSimulator()
        scene = _scene_with_target_body(
            simulator_type=SimulatorType.PYBULLET,
            target_body="entry_marker",
            objective_name="entry_point",
        )
        # Add second objective for exit
        scene.task.objectives.append(
            TaskObjective(
                name="exit_point",
                description="Exit",
                success_criteria="Done",
                target_body="exit_marker",
            )
        )
        sim.load_scene(scene)
        obs = sim._get_observation()
        assert obs.entry_point is not None
        expected_entry = np.array([0.2, 0.0, 0.05])
        assert np.linalg.norm(obs.entry_point - expected_entry) < 1e-3
        assert obs.exit_point is not None
        expected_exit = np.array([0.3, 0.0, 0.05])
        assert np.linalg.norm(obs.exit_point - expected_exit) < 1e-3

    def test_fallback_without_target_body(self):
        """Scene without target_body still produces needle_pos via heuristic."""
        sim = PyBulletSimulator()
        scene = _scene_with_target_body(
            simulator_type=SimulatorType.PYBULLET,
            target_body=None,
            objective_name="needle_pickup",
            with_instrument=False,
        )
        # Add a tissue named exactly "needle" so PyBullet heuristic matches
        scene.tissues.append(
            TissueConfig(
                name="needle",
                type=TissueType.CUSTOM,
                pose=Pose(
                    position=Position(x=0.15, y=0.0, z=0.05),
                    orientation=Orientation(w=1.0, x=0.0, y=0.0, z=0.0),
                ),
                geometry={"primitive": "box", "dimensions": [0.01, 0.01, 0.01]},
                physics={"mass": 0.01},
            )
        )
        sim.load_scene(scene)
        obs = sim._get_observation()
        # Fallback: body named "needle" used as needle proxy
        assert obs.needle_pos is not None
        expected = np.array([0.15, 0.0, 0.05])
        assert np.linalg.norm(obs.needle_pos - expected) < 1e-3

    def test_incision_progress_computed(self):
        """incision_progress is computed from objectives completion ratio."""
        sim = PyBulletSimulator()
        scene = _scene_with_target_body(
            simulator_type=SimulatorType.PYBULLET,
            target_body="needle_instrument",
            objective_name="needle_pickup",
            success_criteria="Complete the needle pass",  # contains "complete"
        )
        sim.load_scene(scene)
        obs = sim._get_observation()
        assert obs.incision_progress == 1.0  # 1 objective, 1 with "complete"

    def test_no_target_body_no_heuristic_match(self):
        """When target_body is None and no heuristic names match, fields stay None."""
        sim = PyBulletSimulator()
        scene = _scene_with_target_body(
            simulator_type=SimulatorType.PYBULLET,
            target_body=None,
            objective_name="some_task",
            with_instrument=False,
        )
        sim.load_scene(scene)
        obs = sim._get_observation()
        # No instrument, no "needle" body name → needle_pos should be None
        assert obs.needle_pos is None


class TestMuJoCoTaskGeometry:
    """TASK-01 / TASK-02 for MuJoCo."""

    def test_needle_pos_from_target_body(self):
        """obs.needle_pos matches target_body body position within 1e-3."""
        sim = MuJoCoSimulator()
        scene = _scene_with_target_body(
            simulator_type=SimulatorType.MUJOCO,
            target_body="needle_instrument",
            objective_name="needle_pickup",
        )
        sim.load_scene(scene)
        obs = sim._get_observation()
        assert obs.needle_pos is not None
        expected = np.array([0.12, 0.0, 0.05])
        assert np.linalg.norm(obs.needle_pos - expected) < 1e-3

    def test_entry_exit_from_target_body(self):
        """obs.entry_point and obs.exit_point match target_body bodies."""
        sim = MuJoCoSimulator()
        scene = _scene_with_target_body(
            simulator_type=SimulatorType.MUJOCO,
            target_body="entry_marker",
            objective_name="entry_point",
        )
        scene.task.objectives.append(
            TaskObjective(
                name="exit_point",
                description="Exit",
                success_criteria="Done",
                target_body="exit_marker",
            )
        )
        sim.load_scene(scene)
        obs = sim._get_observation()
        assert obs.entry_point is not None
        expected_entry = np.array([0.2, 0.0, 0.05])
        assert np.linalg.norm(obs.entry_point - expected_entry) < 1e-3
        assert obs.exit_point is not None
        expected_exit = np.array([0.3, 0.0, 0.05])
        assert np.linalg.norm(obs.exit_point - expected_exit) < 1e-3

    def test_fallback_without_target_body(self):
        """Scene without target_body still produces needle_pos via heuristic."""
        sim = MuJoCoSimulator()
        scene = _scene_with_target_body(
            simulator_type=SimulatorType.MUJOCO,
            target_body=None,
            objective_name="needle_pickup",
            with_instrument=True,
        )
        sim.load_scene(scene)
        obs = sim._get_observation()
        assert obs.needle_pos is not None
        expected = np.array([0.12, 0.0, 0.05])
        assert np.linalg.norm(obs.needle_pos - expected) < 1e-3

    def test_incision_progress_consistency(self):
        """incision_progress computed consistently across backends."""
        criteria = ["Complete A", "Fail B", "Complete C"]
        objectives = [
            TaskObjective(
                name=f"obj{i}",
                description="d",
                success_criteria=c,
            )
            for i, c in enumerate(criteria)
        ]

        scene_pb = _scene_with_target_body(
            simulator_type=SimulatorType.PYBULLET,
            target_body=None,
            objective_name="obj0",
        )
        scene_pb.task.objectives = objectives

        scene_mj = _scene_with_target_body(
            simulator_type=SimulatorType.MUJOCO,
            target_body=None,
            objective_name="obj0",
        )
        scene_mj.task.objectives = objectives

        sim_pb = PyBulletSimulator()
        sim_pb.load_scene(scene_pb)
        obs_pb = sim_pb._get_observation()

        sim_mj = MuJoCoSimulator()
        sim_mj.load_scene(scene_mj)
        obs_mj = sim_mj._get_observation()

        # 2 out of 3 contain "complete"
        expected = 2.0 / 3.0
        assert obs_pb.incision_progress == pytest.approx(expected)
        assert obs_mj.incision_progress == pytest.approx(expected)
        assert obs_pb.incision_progress == pytest.approx(obs_mj.incision_progress)

    def test_no_target_body_no_heuristic_match(self):
        """When target_body is None and no instrument, needle_pos stays None."""
        sim = MuJoCoSimulator()
        scene = _scene_with_target_body(
            simulator_type=SimulatorType.MUJOCO,
            target_body=None,
            objective_name="some_task",
            with_instrument=False,
        )
        sim.load_scene(scene)
        obs = sim._get_observation()
        assert obs.needle_pos is None


class TestTargetBodySchema:
    """Schema-level tests for target_body."""

    def test_target_body_optional(self):
        """TaskObjective works with and without target_body."""
        obj_with = TaskObjective(
            name="test", description="d", success_criteria="s", target_body="body1"
        )
        assert obj_with.target_body == "body1"

        obj_without = TaskObjective(name="test", description="d", success_criteria="s")
        assert obj_without.target_body is None

    def test_target_body_serialization(self):
        """target_body round-trips through model_dump."""
        obj = TaskObjective(
            name="test", description="d", success_criteria="s", target_body="marker"
        )
        dumped = obj.model_dump()
        assert dumped["target_body"] == "marker"

        obj2 = TaskObjective(**dumped)
        assert obj2.target_body == "marker"

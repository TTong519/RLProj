"""Tests for SceneBuilder MJCF generation and asset resolution."""

import tempfile
from pathlib import Path

from surg_rl.scene_definition.schema import (
    CameraConfig,
    EndEffectorConfig,
    EnvironmentConfig,
    GroundPlaneConfig,
    InstrumentConfig,
    JointConfig,
    JointLimits,
    JointType,
    LightConfig,
    Metadata,
    Orientation,
    Pose,
    Position,
    RgbColor,
    RobotConfig,
    SceneDefinition,
    TissueConfig,
    TissueMeshDefinition,
)
from surg_rl.simulators.scene_builder import SceneBuilder


class TestAssetResolution:
    def test_resolve_asset_path_relative_exists(self):
        with tempfile.TemporaryDirectory() as td:
            builder = SceneBuilder(assets_dir=td)
            test_file = Path(td) / "test.txt"
            test_file.write_text("hello")
            path = builder.resolve_asset_path("test.txt")
            assert path == Path(td) / "test.txt"

    def test_resolve_asset_path_relative_missing(self):
        with tempfile.TemporaryDirectory() as td:
            builder = SceneBuilder(assets_dir=td)
            path = builder.resolve_asset_path("test.txt")
            assert path is None

    def test_resolve_asset_path_absolute_exists(self, tmp_path):
        builder = SceneBuilder()
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")
        assert builder.resolve_asset_path(str(test_file)) == test_file.resolve()

    def test_resolve_asset_path_absolute_missing(self):
        builder = SceneBuilder()
        abs_path = "/tmp/test.txt"
        assert builder.resolve_asset_path(abs_path) is None

    def test_get_mesh_or_primitive_missing_mesh_uses_fallback(self, tmp_path):
        builder = SceneBuilder(assets_dir=str(tmp_path))
        mesh_path, is_prim = builder.get_mesh_or_primitive(
            mesh_path=None,
            primitive="box",
            dimensions=(0.1, 0.1, 0.01),
            name="fallback_box",
        )
        assert mesh_path.exists()
        assert is_prim is True
        assert "fallback_box" in mesh_path.name or "box" in mesh_path.name


class TestMJCFGeneration:
    def test_create_mjcf_includes_robot(self, tmp_path):
        builder = SceneBuilder(assets_dir=str(tmp_path))
        scene = SceneDefinition(
            metadata=Metadata(name="robot_scene"),
            robots=[RobotConfig(name="arm", urdf_path=None, links=[{"name": "link0"}])],
        )
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")
        assert mjcf.exists()
        content = mjcf.read_text()
        assert "body" in content.lower() or "robot" in content.lower()

    def test_add_ground_plane_enabled(self, tmp_path):
        builder = SceneBuilder(assets_dir=str(tmp_path))
        scene = SceneDefinition(
            metadata=Metadata(name="ground"),
            environment=EnvironmentConfig(ground_plane=GroundPlaneConfig(enabled=True)),
        )
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")
        content = mjcf.read_text()
        assert "plane" in content.lower() or "geom" in content.lower()

    def test_add_camera_to_mjcf(self, tmp_path):
        builder = SceneBuilder(assets_dir=str(tmp_path))
        scene = SceneDefinition(
            metadata=Metadata(name="cam"),
            environment=EnvironmentConfig(
                cameras=[
                    CameraConfig(
                        name="main",
                        type="perspective",
                        pose=Pose(
                            position=Position(x=1, y=0, z=1),
                            orientation=Orientation(w=1, x=0, y=0, z=0),
                        ),
                        fov=60.0,
                    )
                ]
            ),
        )
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")
        content = mjcf.read_text()
        assert "camera" in content.lower()

    def test_add_light_directional(self, tmp_path):
        builder = SceneBuilder(assets_dir=str(tmp_path))
        scene = SceneDefinition(
            metadata=Metadata(name="light"),
            environment=EnvironmentConfig(
                lights=[
                    LightConfig(
                        name="sun",
                        type="directional",
                        direction=[0.0, 0.0, -1.0],
                        color=RgbColor(r=1.0, g=1.0, b=1.0, a=1.0),
                        intensity=1.0,
                    )
                ]
            ),
        )
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")
        content = mjcf.read_text()
        assert "light" in content.lower()

    def test_add_light_point(self, tmp_path):
        builder = SceneBuilder(assets_dir=str(tmp_path))
        scene = SceneDefinition(
            metadata=Metadata(name="point_light"),
            environment=EnvironmentConfig(
                lights=[
                    LightConfig(
                        name="bulb",
                        type="point",
                        position=Position(x=0.5, y=0.5, z=1.0),
                        color=RgbColor(r=1.0, g=0.0, b=0.0, a=1.0),
                        intensity=0.8,
                    )
                ]
            ),
        )
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")
        content = mjcf.read_text()
        assert "light" in content.lower()

    def test_add_tissue_sphere(self, tmp_path):
        builder = SceneBuilder(assets_dir=str(tmp_path))
        scene = SceneDefinition(
            metadata=Metadata(name="tissue"),
            tissues=[
                TissueConfig(
                    name="sphere_tissue",
                    geometry=TissueMeshDefinition(
                        primitive="sphere", dimensions=(0.05, 0.05, 0.05), radius=0.05
                    ),
                )
            ],
        )
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")
        content = mjcf.read_text()
        assert "sphere" in content.lower() or "geom" in content.lower()

    def test_add_tissue_cylinder(self, tmp_path):
        builder = SceneBuilder(assets_dir=str(tmp_path))
        scene = SceneDefinition(
            metadata=Metadata(name="tissue"),
            tissues=[
                TissueConfig(
                    name="cyl_tissue",
                    geometry=TissueMeshDefinition(
                        primitive="cylinder", dimensions=(0.05, 0.05, 0.1)
                    ),
                )
            ],
        )
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")
        content = mjcf.read_text()
        assert "cylinder" in content.lower() or "geom" in content.lower()

    def test_add_instrument_to_mjcf(self, tmp_path):
        builder = SceneBuilder(assets_dir=str(tmp_path))
        scene = SceneDefinition(
            metadata=Metadata(name="inst_scene"),
            instruments=[InstrumentConfig(name="needle", type="needle_driver")],
        )
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")
        content = mjcf.read_text()
        # Instrument should be added as a body or geom
        assert "body" in content.lower() or "geom" in content.lower()


class TestSceneBuilderNoneLists:
    """Regression tests for None camera/light lists."""

    def test_scene_builder_environment_none_lists(self, tmp_path):
        """MJCF generation must not crash when cameras or lights are None."""
        builder = SceneBuilder(assets_dir=str(tmp_path))
        scene = SceneDefinition(
            metadata=Metadata(name="none_env"),
        )
        # Bypass Pydantic default factories by constructing manually
        from surg_rl.scene_definition.schema import EnvironmentConfig

        env = EnvironmentConfig.model_construct(
            name="empty_room",
            cameras=None,
            lights=None,
            ground_plane=None,
            surgical_table=None,
            environment_mesh=None,
            background_color=None,
        )
        scene = scene.model_copy(update={"environment": env})
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")
        assert mjcf.exists()
        content = mjcf.read_text()
        # Should contain basic MJCF without cameras/lights
        assert "mujoco" in content.lower()


class TestRobotDofSplitting:
    """Regression tests for the primitive-fallback kinematic chain.

    The primitive fallback builds a kinematic chain of nested bodies (one body
    per joint) to avoid two well-conditioned failure modes:

    1. MuJoCo's hard limit of 6 DOFs per body (DOF-splitting for 7+ joint
       robots).
    2. Rank-deficient configuration from multiple hinges stacked on one
       body or on the same axis — produces ``Nan, Inf or huge value in
       QACC`` warnings and a NaN-terminated episode after one step.

    See debug sessions ppo-demo-mujoco-dof-limit and ppo-demo-mujoco-qacc-nan.
    """

    def _make_joint(self, name: str) -> JointConfig:
        return JointConfig(
            name=name,
            type=JointType.REVOLUTE,
            limits=JointLimits(lower=-1.0, upper=1.0, effort=10.0, velocity=1.0),
            damping=0.1,
        )

    def _seven_dof_scene(self) -> SceneDefinition:
        joints = [self._make_joint(f"joint_{i}") for i in range(1, 8)]
        robot = RobotConfig(
            name="surgical_arm_1",
            joints=joints,
            end_effectors=[
                EndEffectorConfig(name="needle_driver", type="needle_driver")
            ],
        )
        return SceneDefinition(metadata=Metadata(name="dof_split"), robots=[robot])

    def test_seven_dof_robot_generates_valid_mjcf(self, tmp_path):
        """7-DOF robot + 1 gripper slide must not produce >6 DOFs on one body.

        Before the fix this raised ``ValueError: more than 6 dofs in body ...``
        when MuJoCo tried to load the generated XML.
        """
        builder = SceneBuilder(assets_dir=str(tmp_path))
        scene = self._seven_dof_scene()
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")
        assert mjcf.exists()

        # The generated MJCF must load in MuJoCo. This is the regression check.
        mujoco = pytest_mujoco()
        model = mujoco.MjModel.from_xml_path(str(mjcf))
        # 7 hinges + 1 slide = 8 joints
        assert model.njnt == 8
        assert model.nq == 8

    def test_seven_dof_robot_uses_kinematic_chain(self, tmp_path):
        """7-DOF robot must emit nested link bodies, one per joint.

        The chain structure (one body per joint) is required to avoid the
        rank-deficient configuration that produces QACC NaN.
        """
        builder = SceneBuilder(assets_dir=str(tmp_path))
        scene = self._seven_dof_scene()
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")
        content = mjcf.read_text()
        # Each joint is hosted on its own nested link body. We expect 7 link
        # bodies named "<robot>_link<N>" for N in 1..7.
        for n in range(1, 8):
            assert f"surgical_arm_1_link{n}" in content, f"missing link{n} body"

    def test_seven_dof_robot_loads_and_steps_without_nan(self, tmp_path):
        """Full chain must be numerically stable — no QACC NaN on first step.

        Regression test for the QACC NaN bug: even with zero controls, the
        previous chunking structure produced a rank-deficient kinematic
        tree. The chain structure (one body per joint) is well-conditioned.
        """
        import numpy as np
        builder = SceneBuilder(assets_dir=str(tmp_path))
        scene = self._seven_dof_scene()
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")
        mujoco = pytest_mujoco()
        model = mujoco.MjModel.from_xml_path(str(mjcf))
        data = mujoco.MjData(model)
        # Zero controls — the simulation should remain finite for several steps.
        for _ in range(5):
            mujoco.mj_step(model, data)
            assert np.all(np.isfinite(data.qpos)), f"qpos went non-finite: {data.qpos}"
            assert np.all(np.isfinite(data.qvel)), f"qvel went non-finite: {data.qvel}"

    def test_low_dof_robot_uses_chain_too(self, tmp_path):
        """A small (3-joint) robot still uses the chain structure.

        The chain is now universal — every joint gets its own body — so the
        same path is exercised regardless of DOF count. The previous flat
        path was the source of the QACC NaN bug.
        """
        joints = [self._make_joint(f"joint_{i}") for i in range(1, 4)]  # 3 joints
        robot = RobotConfig(
            name="small_arm",
            joints=joints,
            end_effectors=[EndEffectorConfig(name="gripper", type="gripper")],
        )
        scene = SceneDefinition(metadata=Metadata(name="low_dof"), robots=[robot])
        builder = SceneBuilder(assets_dir=str(tmp_path))
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")
        content = mjcf.read_text()
        # 3 link bodies (one per joint), not "seg" naming from the old path.
        for n in range(1, 4):
            assert f"small_arm_link{n}" in content, f"missing link{n} body"
        assert "small_arm_seg" not in content

        # Sanity: the MJCF still loads and exposes the expected joint count.
        mujoco = pytest_mujoco()
        model = mujoco.MjModel.from_xml_path(str(mjcf))
        assert model.njnt == 4  # 3 hinges + 1 gripper slide


class TestControlModeActuators:
    """Regression tests for control_mode-aware actuator generation.

    The builder must emit the right MuJoCo actuator type for the scene's
    declared ``robot.control_mode``, and forward ``PhysicsConfig.integrator``
    and ``PhysicsConfig.solver_iterations`` to the MJCF ``<option>`` element.
    """

    def _make_joint(self, name: str) -> JointConfig:
        return JointConfig(
            name=name,
            type=JointType.REVOLUTE,
            limits=JointLimits(lower=-1.0, upper=1.0, effort=10.0, velocity=1.0),
            damping=0.1,
        )

    def test_position_mode_emits_position_actuators(self, tmp_path):
        """control_mode="position" must emit <position> actuators, not <motor>."""
        joints = [self._make_joint(f"joint_{i}") for i in range(1, 4)]
        robot = RobotConfig(
            name="arm",
            joints=joints,
            control_mode="position",
            end_effectors=[EndEffectorConfig(name="gripper", type="gripper")],
        )
        scene = SceneDefinition(metadata=Metadata(name="pos_mode"), robots=[robot])
        builder = SceneBuilder(assets_dir=str(tmp_path))
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")
        content = mjcf.read_text()
        # Each joint should have a <position kp="..."> actuator.
        for j in ("joint_1", "joint_2", "joint_3"):
            assert f'<position name="{j}_motor"' in content, (
                f"missing position actuator for {j} in:\n{content}"
            )
        # And the gripper too.
        assert '<position name="arm_gripper"' in content
        # No <motor> actuators for arm joints.
        assert "<motor" not in content

    def test_torque_mode_emits_motor_actuators(self, tmp_path):
        """control_mode="torque" (and unset) must emit <motor> actuators."""
        joints = [self._make_joint(f"joint_{i}") for i in range(1, 3)]
        robot = RobotConfig(
            name="arm",
            joints=joints,
            control_mode="torque",
        )
        scene = SceneDefinition(metadata=Metadata(name="torque_mode"), robots=[robot])
        builder = SceneBuilder(assets_dir=str(tmp_path))
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")
        content = mjcf.read_text()
        for j in ("joint_1", "joint_2"):
            assert f'<motor name="{j}_motor"' in content, (
                f"missing motor actuator for {j}"
            )

    def test_velocity_mode_emits_velocity_actuators(self, tmp_path):
        """control_mode="velocity" must emit <velocity> actuators."""
        joints = [self._make_joint(f"joint_{i}") for i in range(1, 3)]
        robot = RobotConfig(
            name="arm",
            joints=joints,
            control_mode="velocity",
        )
        scene = SceneDefinition(metadata=Metadata(name="vel_mode"), robots=[robot])
        builder = SceneBuilder(assets_dir=str(tmp_path))
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")
        content = mjcf.read_text()
        for j in ("joint_1", "joint_2"):
            assert f'<velocity name="{j}_motor"' in content, (
                f"missing velocity actuator for {j}"
            )

    def test_option_forwards_integrator_and_iterations(self, tmp_path):
        """PhysicsConfig.integrator and solver_iterations must reach <option>."""
        from surg_rl.scene_definition.schema import PhysicsConfig

        # Use a custom integrator/iterations value to verify it's forwarded.
        scene = SceneDefinition(
            metadata=Metadata(name="opts"),
            physics=PhysicsConfig(
                gravity=(0.0, 0.0, -9.81),
                timestep=0.002,
                integrator="RK4",
                solver_iterations=100,
            ),
        )
        builder = SceneBuilder(assets_dir=str(tmp_path))
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")
        content = mjcf.read_text()
        # MuJoCo's attribute name is "iterations" (not "solver_iterations").
        assert 'integrator="RK4"' in content
        assert 'iterations="100"' in content


def pytest_mujoco():
    """Lazy import of the optional mujoco dependency for these regression tests."""
    import mujoco  # type: ignore[import-untyped]

    return mujoco

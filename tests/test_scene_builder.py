"""Tests for SceneBuilder MJCF generation and asset resolution."""

import tempfile
from pathlib import Path

from surg_rl.scene_definition import SceneLoader
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
            end_effectors=[EndEffectorConfig(name="needle_driver", type="needle_driver")],
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


class TestLinkStaggering:
    """Regression tests for end-to-end staggering of the kinematic chain.

    The primitive-fallback MJCF builder must stagger each link body along
    +z by the per-joint ``link_length`` (or DEFAULT_LINK_LENGTH when unset),
    so the visual boxes form an extended chain rather than collapsing to
    a single point at the robot base. The previous zero-offset structure
    produced 7 overlapping boxes at the same location — visually a single
    blob and physically indistinguishable from a fixed body.
    """

    def _make_joint(self, name: str, link_length: float | None = None) -> JointConfig:
        kwargs: dict = {
            "name": name,
            "type": JointType.REVOLUTE,
            "limits": JointLimits(lower=-1.0, upper=1.0, effort=10.0, velocity=1.0),
            "damping": 0.1,
        }
        if link_length is not None:
            kwargs["link_length"] = link_length
        return JointConfig(**kwargs)

    def test_default_length_staggers_seven_dof_chain(self, tmp_path):
        """All link bodies must have non-zero z offset using DEFAULT_LINK_LENGTH.

        The first link is offset by ``BASE_GEOM_HALF_Z + link_length`` so
        it sits above the mounting-block geom (otherwise the chain would
        intersect the base). Subsequent links are offset by ``link_length``
        from their parent (their pos attribute is in the parent's local
        frame, so the BASE_GEOM_HALF_Z only appears on link1).
        """
        from surg_rl.simulators.scene_builder import SceneBuilder

        joints = [self._make_joint(f"joint_{i}") for i in range(1, 8)]
        robot = RobotConfig(name="arm", joints=joints)
        scene = SceneDefinition(metadata=Metadata(name="stagger"), robots=[robot])
        builder = SceneBuilder(assets_dir=str(tmp_path))
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")

        import re

        content = mjcf.read_text()
        expected_default = SceneBuilder.DEFAULT_LINK_LENGTH
        base_half_z = SceneBuilder.BASE_GEOM_HALF_Z
        link_z = re.findall(r'<body[^>]*name="arm_link(\d+)"[^>]*pos="([^"]+)"', content)
        assert len(link_z) == 7, f"expected 7 link bodies, got {link_z}"

        # XML pos attribute is the offset in the PARENT body frame, not
        # world frame. Link1's offset = base_half_z + length (it sits on
        # top of the base geom); each subsequent link's offset = length
        # (sits on top of its parent).
        for name, pos in link_z:
            n = int(name)
            x, y, z = (float(v) for v in pos.split())
            assert x == 0.0 and y == 0.0, f"link{name} should be on z axis, got pos={pos}"
            expected_z = base_half_z + expected_default if n == 1 else expected_default
            assert (
                abs(z - expected_z) < 1e-9
            ), f"link{name} should be at z={expected_z} (parent-frame), got pos={pos}"

    def test_per_joint_link_length_overrides_default(self, tmp_path):
        """When JointConfig.link_length is set, that value (not the default) is used."""
        from surg_rl.simulators.scene_builder import SceneBuilder

        joints = [
            self._make_joint("joint_1", link_length=0.10),
            self._make_joint("joint_2", link_length=0.20),
            self._make_joint("joint_3"),  # uses default
        ]
        robot = RobotConfig(name="arm", joints=joints)
        scene = SceneDefinition(metadata=Metadata(name="per_joint"), robots=[robot])
        builder = SceneBuilder(assets_dir=str(tmp_path))
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")

        import re

        content = mjcf.read_text()
        base_half_z = SceneBuilder.BASE_GEOM_HALF_Z
        link_z = dict(re.findall(r'<body[^>]*name="arm_link(\d+)"[^>]*pos="([^"]+)"', content))
        # link1 offset in parent (root) frame = base_half_z + its own length
        assert float(link_z["1"].split()[2]) == base_half_z + 0.10
        # link2 offset in parent (link1) frame = its own length
        assert float(link_z["2"].split()[2]) == 0.20
        # link3 offset in parent (link2) frame = its own length (default)
        assert float(link_z["3"].split()[2]) == SceneBuilder.DEFAULT_LINK_LENGTH

    def test_geom_sits_between_parent_and_child_joints(self, tmp_path):
        """The visual geom box must be centered between the parent joint (at the
        link body's local origin) and the next link's joint (at link_length).

        Adjacent boxes then touch at the joint but do not overlap. The
        geom's z half-extent is ``link_length / 2`` so the box spans
        exactly one link — short links don't visually overlap their
        neighbors.
        """
        from surg_rl.simulators.scene_builder import SceneBuilder

        joints = [self._make_joint(f"joint_{i}") for i in range(1, 4)]
        robot = RobotConfig(name="arm", joints=joints)
        scene = SceneDefinition(metadata=Metadata(name="geom_center"), robots=[robot])
        builder = SceneBuilder(assets_dir=str(tmp_path))
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")

        import re

        content = mjcf.read_text()
        # The geom element emits attributes in insertion order: name, type,
        # size, pos (the order they're set in the builder).
        geom_re = re.compile(
            r'<geom\s+name="arm_link(\d+)_geom"\s+'
            r'type="(?P<tp>[^"]*)"\s+'
            r'size="(?P<sz>[^"]*)"\s+'
            r'pos="(?P<pos>[^"]*)"',
        )
        geoms = geom_re.findall(content)
        assert len(geoms) == 3, f"expected 3 link geoms, got {geoms}"

        default_length = SceneBuilder.DEFAULT_LINK_LENGTH
        for n, _type, size, pos_value in geoms:
            x, y, z = (float(v) for v in pos_value.split())
            assert z == default_length / 2, (
                f"link{n} geom should be at z={default_length / 2} (mid-link), "
                f"got pos={pos_value}"
            )
            # Geom z half-extent == link_length / 2 so the box spans exactly
            # one link (no overlap with neighbors).
            sx, sy, sz = (float(v) for v in size.split())
            assert sz == default_length / 2, (
                f"link{n} geom z half-extent should be {default_length / 2}, " f"got size={size}"
            )

    def test_chain_loads_and_joints_extend_visibly(self, tmp_path):
        """End-to-end: with the chain staggered, MuJoCo must report joint anchors
        at distinct world-frame z positions. If the chain were collapsed, every
        joint anchor would be at z=0.
        """
        import mujoco

        from surg_rl.simulators.scene_builder import SceneBuilder

        joints = [self._make_joint(f"joint_{i}") for i in range(1, 8)]
        robot = RobotConfig(name="arm", joints=joints)
        scene = SceneDefinition(metadata=Metadata(name="anchor"), robots=[robot])
        builder = SceneBuilder(assets_dir=str(tmp_path))
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")
        model = mujoco.MjModel.from_xml_path(str(mjcf))
        data = mujoco.MjData(model)
        mujoco.mj_forward(model, data)

        # Joint N (1-indexed) anchor sits at z = BASE_GEOM_HALF_Z + N *
        # link_length in world frame. We look up each joint by name so the
        # test is robust to MuJoCo's joint ordering.
        expected_default = SceneBuilder.DEFAULT_LINK_LENGTH
        base_half_z = SceneBuilder.BASE_GEOM_HALF_Z
        for n in range(1, 8):
            joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, f"joint_{n}")
            assert joint_id >= 0, f"joint_{n} not found in model"
            anchor_z = float(data.xanchor[joint_id][2])
            expected_z = base_half_z + n * expected_default
            assert (
                abs(anchor_z - expected_z) < 1e-6
            ), f"joint_{n} anchor at z={anchor_z}, expected {expected_z}"

    def test_zero_link_length_keeps_chain_but_no_visual_extent(self, tmp_path):
        """An explicit link_length=0 is permitted (a real zero-length joint)
        and produces a valid MJCF; the chain is just visually collapsed at
        that joint. This guards against the case where someone sets
        link_length=0.0 to express 'no extension' without breaking.
        """
        from surg_rl.simulators.scene_builder import SceneBuilder

        joints = [
            self._make_joint("joint_1", link_length=0.0),
            self._make_joint("joint_2", link_length=0.0),
        ]
        robot = RobotConfig(name="arm", joints=joints)
        scene = SceneDefinition(metadata=Metadata(name="zero_len"), robots=[robot])
        builder = SceneBuilder(assets_dir=str(tmp_path))
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")
        import mujoco

        model = mujoco.MjModel.from_xml_path(str(mjcf))
        # MJCF is valid and the chain is still 1 body per joint.
        assert model.njnt == 2

    def test_qpos_stays_finite_with_staggered_chain(self, tmp_path):
        """The staggered chain must remain numerically stable.

        Each link's body is offset by ``link_length`` from its parent (plus
        the base-geom half-extent for the first link), and the link's
        center of mass is at the link's midpoint. With the inertia placed
        at the center of mass, the rotational inertia is finite and
        well-conditioned under zero control.
        """
        import numpy as np

        from surg_rl.simulators.scene_builder import SceneBuilder

        joints = [self._make_joint(f"joint_{i}") for i in range(1, 8)]
        robot = RobotConfig(name="arm", joints=joints)
        scene = SceneDefinition(metadata=Metadata(name="stagger_stable"), robots=[robot])
        builder = SceneBuilder(assets_dir=str(tmp_path))
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")
        import mujoco

        model = mujoco.MjModel.from_xml_path(str(mjcf))
        data = mujoco.MjData(model)
        for _ in range(20):
            mujoco.mj_step(model, data)
            assert np.all(np.isfinite(data.qpos)), f"qpos went non-finite: {data.qpos}"
            assert np.all(np.isfinite(data.qvel)), f"qvel went non-finite: {data.qvel}"

    def test_chain_does_not_intersect_base_geom(self, tmp_path):
        """The first link's geom must not penetrate the robot's base/mount geom.

        Without the BASE_GEOM_HALF_Z clearance, the first link's geom (whose
        bottom is at z=0 in body-local frame) would overlap the base geom
        (whose top is at z=BASE_GEOM_HALF_Z in root-local frame). The
        staggered first-link offset puts the link just above the base.
        """
        from surg_rl.simulators.scene_builder import SceneBuilder

        joints = [self._make_joint(f"joint_{i}") for i in range(1, 4)]
        robot = RobotConfig(name="arm", joints=joints)
        scene = SceneDefinition(metadata=Metadata(name="base_clear"), robots=[robot])
        builder = SceneBuilder(assets_dir=str(tmp_path))
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")

        import re

        content = mjcf.read_text()
        # Base geom size (z half-extent)
        base_size_re = re.search(r'<geom\s+name="arm_base"[^>]*size="([^"]+)"', content)
        assert base_size_re, "base geom not found"
        base_z_half = float(base_size_re.group(1).split()[2])
        assert base_z_half == SceneBuilder.BASE_GEOM_HALF_Z

        # First link body offset (parent-frame z)
        link1_re = re.search(r'<body\s+name="arm_link1"[^>]*pos="([^"]+)"', content)
        assert link1_re, "link1 body not found"
        link1_z = float(link1_re.group(1).split()[2])
        default_length = SceneBuilder.DEFAULT_LINK_LENGTH

        # The link1 body is at z = base_half_z + link_length. Its geom
        # (centered at z=link_length/2 in body-local frame with z half-extent
        # = link_length/2) has its bottom at z=0 in body-local frame, which
        # is z=link1_z in root frame. The base geom top is at z=base_z_half
        # in root frame. link1_z - link_length/2 (geom bottom in body local
        # frame) ... wait — geom at z=link_length/2, half-extent link_length/2,
        # so geom bottom in body local frame = 0, in root frame = link1_z.
        # Base top in root frame = base_z_half. For no intersection:
        # link1_z > base_z_half, i.e. base_z_half + link_length > base_z_half.
        assert link1_z == base_z_half + default_length
        assert (
            link1_z > base_z_half
        ), f"link1 at z={link1_z} should be above base top at z={base_z_half}"

    def test_suturing_demo_arm_does_not_intersect_workspace(self, tmp_path):
        """End-to-end: the actual suturing_demo scene must have zero
        arm/workspace contacts at reset and after gravity settles.

        Regression test for the bug where the chain at z=0.4 directly
        intersected the skin patches (also at z=0.4) on the first frame.
        """
        from surg_rl.simulators.scene_builder import SceneBuilder

        scene = SceneLoader().load("scenes/suturing_demo.json")
        builder = SceneBuilder(assets_dir=str(tmp_path))
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")
        import mujoco

        model = mujoco.MjModel.from_xml_path(str(mjcf))
        data = mujoco.MjData(model)
        mujoco.mj_forward(model, data)

        def _count_arm_workspace_contacts() -> int:
            """Count active contacts between any arm link geom and the
            skin/needle workspace geoms."""
            count = 0
            for c in range(data.ncon):
                g1, g2 = data.contact[c].geom1, data.contact[c].geom2
                n1 = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, g1) or ""
                n2 = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, g2) or ""
                arm_side = ("link" in n1 and ("skin" in n2 or "curved" in n2)) or (
                    "link" in n2 and ("skin" in n1 or "curved" in n1)
                )
                if arm_side:
                    count += 1
            return count

        # Frame 0: no contacts
        assert _count_arm_workspace_contacts() == 0, (
            "arm intersects workspace at frame 0; check base_pose and "
            "link_length in scenes/suturing_demo.json"
        )

        # After gravity settles, still no contacts (chain shouldn't
        # swing into the workspace).
        for _ in range(50):
            mujoco.mj_step(model, data)
        assert _count_arm_workspace_contacts() == 0, (
            "arm intersects workspace after 50 gravity steps; chain " "swing is too large"
        )


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
            assert (
                f'<position name="{j}_motor"' in content
            ), f"missing position actuator for {j} in:\n{content}"
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
            assert f'<motor name="{j}_motor"' in content, f"missing motor actuator for {j}"

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
            assert f'<velocity name="{j}_motor"' in content, f"missing velocity actuator for {j}"

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


class TestSuturingDemoSceneRealism:
    """Regression tests for the realistic suturing demo scene.

    The scene (`scenes/suturing_demo.json`) was reworked to be a
    plausible surgical suturing setup: soft deformable skin patches
    (FEM flexcomp), a small curved needle (procedural thin-torus
    generator), and a visible needle-driver gripper on the arm.
    These tests guard the three realism properties so a future
    scene edit can't silently revert to rigid boxes and box-needle.
    """

    def test_suturing_demo_scene_soft_body_enabled(self):
        """Both skin patches must have soft_body=True so the FEM path
        triggers, and the instrument must be type='needle' so the
        procedural thin-torus generator runs (not the 2x2x10cm box)."""
        scene = SceneLoader().load("scenes/suturing_demo.json")
        assert len(scene.tissues) == 2, f"expected 2 skin patches, got {len(scene.tissues)}"
        for i, t in enumerate(scene.tissues):
            assert t.soft_body is True, (
                f"tissue {i} ({t.name}) is not soft_body=True; "
                f"skin patches must use the FEM flexcomp path"
            )
        assert len(scene.instruments) == 1
        assert scene.instruments[0].type.value == "needle", (
            f"instrument type is {scene.instruments[0].type.value}, "
            f"expected 'needle' (uses the procedural thin-torus "
            f"generator with ~16mm arc and ~1.2mm wire)"
        )

    def test_suturing_demo_scene_mjcf_has_flexcomp(self, tmp_path):
        """Building the suturing scene MJCF must produce a flexcomp
        grid for each soft-body tissue and a body for the needle."""
        scene = SceneLoader().load("scenes/suturing_demo.json")
        builder = SceneBuilder(assets_dir=str(tmp_path))
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")
        content = mjcf.read_text()
        # Two flexcomp blocks (one per skin patch) in the deformable
        # body section. The soft_body=True setting on each tissue
        # routes through _add_tissue_to_mjcf's flexcomp branch.
        flexcomp_count = content.count("<flexcomp")
        assert flexcomp_count == 2, (
            f"expected 2 flexcomp blocks (one per soft-body tissue), "
            f"got {flexcomp_count}. Check that both tissues have "
            f"soft_body=True in scenes/suturing_demo.json."
        )
        # The needle body must be present (procedural generator
        # produced a real mesh, not a 2x2x10cm box).
        assert "curved_suturing_needle" in content, "needle body missing from generated MJCF"

    def test_gripper_has_two_jaw_geoms(self, tmp_path):
        """A robot with end_effectors must have two cylindrical jaw
        geoms (left + right) attached to the last link body, both
        with contype=0 conaffinity=0 (visual only — they must NOT
        participate in MuJoCo contact dynamics)."""
        from surg_rl.scene_definition import (
            EndEffectorConfig,
            JointConfig,
            JointLimits,
            JointType,
            RobotConfig,
        )
        from surg_rl.simulators.scene_builder import SceneBuilder

        joints = [
            JointConfig(
                name=f"j{i}",
                type=JointType.REVOLUTE,
                limits=JointLimits(lower=-1, upper=1, effort=10, velocity=1),
                link_length=0.08,
            )
            for i in range(1, 4)
        ]
        robot = RobotConfig(
            name="arm",
            joints=joints,
            end_effectors=[
                EndEffectorConfig(
                    name="gripper",
                    type="gripper",
                    max_aperture=0.05,
                    force_limit=10,
                )
            ],
        )
        scene = SceneDefinition(metadata=Metadata(name="gripper"), robots=[robot])
        builder = SceneBuilder(assets_dir=str(tmp_path))
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")
        content = mjcf.read_text()

        import re

        jaw_names = re.findall(r'name="(arm_gripper_jaw_[lr])"', content)
        assert jaw_names == ["arm_gripper_jaw_l", "arm_gripper_jaw_r"], (
            f"expected jaw geoms arm_gripper_jaw_l and arm_gripper_jaw_r "
            f"in that order, got {jaw_names}"
        )
        # Both jaws must be visual-only (no contact participation).
        # We look at the <geom> blocks for each jaw and check the
        # contype/conaffinity attributes.
        for side in ("l", "r"):
            jaw_re = re.compile(
                rf'<geom\s+name="arm_gripper_jaw_{side}"[^>]*contype="(\d+)"[^>]*conaffinity="(\d+)"',
            )
            match = jaw_re.search(content)
            assert match is not None, f"jaw_{side} geom missing contype/conaffinity attributes"
            contype, conaffinity = match.groups()
            assert contype == "0" and conaffinity == "0", (
                f"jaw_{side} has contype={contype} conaffinity={conaffinity}; "
                f"jaws must be visual-only (contype=0 conaffinity=0) so they "
                f"don't fight the gripper slide joint via contact dynamics"
            )

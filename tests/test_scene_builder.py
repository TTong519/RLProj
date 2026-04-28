"""Tests for SceneBuilder MJCF generation and asset resolution."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from surg_rl.simulators.scene_builder import SceneBuilder
from surg_rl.scene_definition.schema import (
    SceneDefinition,
    Metadata,
    RobotConfig,
    TissueConfig,
    TissueMeshDefinition,
    InstrumentConfig,
    EnvironmentConfig,
    GroundPlaneConfig,
    CameraConfig,
    LightConfig,
    Position,
    Orientation,
    Pose,
    RgbColor,
)


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

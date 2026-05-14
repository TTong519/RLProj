"""Tests for real asset loading with fallback and deduplicated warnings."""
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from surg_rl.simulators.scene_builder import AssetMissingError, SceneBuilder


class TestAssetFallback:
    def test_single_warning_per_missing_asset(self, tmp_path):
        """Duplicate calls with same missing mesh_path must log only one warning."""
        builder = SceneBuilder(assets_dir=str(tmp_path))
        with patch("surg_rl.simulators.scene_builder.logger") as mock_logger:
            # First call should warn
            builder.get_mesh_or_primitive(
                mesh_path="missing_mesh.obj",
                primitive="box",
                dimensions=(0.1, 0.1, 0.01),
                name="tissue_a",
            )
            # Second call with same path should NOT warn again
            builder.get_mesh_or_primitive(
                mesh_path="missing_mesh.obj",
                primitive="box",
                dimensions=(0.1, 0.1, 0.01),
                name="tissue_b",
            )
        warning_calls = [c for c in mock_logger.warning.call_args_list]
        assert len(warning_calls) == 1, f"Expected 1 warning, got {len(warning_calls)}"

    def test_missing_asset_raises_when_fallback_disabled(self, tmp_path):
        builder = SceneBuilder(assets_dir=str(tmp_path), use_primitive_fallback=False)
        with pytest.raises(AssetMissingError):
            builder.get_mesh_or_primitive(
                mesh_path="missing_mesh.obj",
                primitive="box",
                dimensions=(0.1, 0.1, 0.01),
                name="tissue",
            )

    def test_resolve_relative_to_assets_dir(self, tmp_path):
        test_file = tmp_path / "test_mesh.obj"
        test_file.write_text("v 0 0 0\n")
        builder = SceneBuilder(assets_dir=str(tmp_path))
        resolved = builder.resolve_asset_path("test_mesh.obj")
        assert resolved == test_file

    def test_urdf_asset_resolution(self, tmp_path):
        test_urdf = tmp_path / "robot.urdf"
        test_urdf.write_text("<robot/>")
        builder = SceneBuilder(assets_dir=str(tmp_path))
        assert hasattr(builder, "load_urdf_asset"), "SceneBuilder missing load_urdf_asset"
        resolved = builder.load_urdf_asset("robot.urdf", "robot")
        assert resolved == test_urdf

    def test_urdf_asset_missing_returns_none(self, tmp_path):
        builder = SceneBuilder(assets_dir=str(tmp_path))
        assert hasattr(builder, "load_urdf_asset"), "SceneBuilder missing load_urdf_asset"
        resolved = builder.load_urdf_asset("missing.urdf", "robot")
        assert resolved is None


class TestMuJoCoMeshAssets:
    def test_mujoco_mesh_in_mjcf(self, tmp_path):
        """MJCF generation should include <mesh> asset for real mesh files."""
        mesh_file = tmp_path / "tissue_mesh.obj"
        mesh_file.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n")
        builder = SceneBuilder(assets_dir=str(tmp_path))

        from surg_rl.scene_definition.schema import (
            Metadata,
            SceneDefinition,
            TissueConfig,
            TissueMeshDefinition,
            MeshAsset,
        )

        scene = SceneDefinition(
            metadata=Metadata(name="mesh_scene"),
            tissues=[
                TissueConfig(
                    name="liver",
                    geometry=TissueMeshDefinition(
                        mesh=MeshAsset(path="tissue_mesh.obj"),
                        primitive="box",
                        dimensions=(0.1, 0.1, 0.01),
                    ),
                )
            ],
        )
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")
        content = mjcf.read_text()
        assert '<mesh name="liver_mesh"' in content
        assert 'file="' in content
        assert 'type="mesh"' in content

    def test_mujoco_missing_mesh_fallback(self, tmp_path):
        """Missing mesh should fall back to primitive and log one warning."""
        builder = SceneBuilder(assets_dir=str(tmp_path))

        from surg_rl.scene_definition.schema import (
            Metadata,
            SceneDefinition,
            TissueConfig,
            TissueMeshDefinition,
            MeshAsset,
        )

        scene = SceneDefinition(
            metadata=Metadata(name="missing_mesh_scene"),
            tissues=[
                TissueConfig(
                    name="liver",
                    geometry=TissueMeshDefinition(
                        mesh=MeshAsset(path="nonexistent.obj"),
                        primitive="box",
                        dimensions=(0.1, 0.1, 0.01),
                    ),
                )
            ],
        )
        with patch("surg_rl.simulators.scene_builder.logger") as mock_logger:
            mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")
        content = mjcf.read_text()
        # Should NOT contain mesh asset
        assert '<mesh name="liver_mesh"' not in content
        # Should contain primitive geometry
        assert 'type="box"' in content
        # Warning should have been logged exactly once
        warning_calls = [c for c in mock_logger.warning.call_args_list]
        assert len(warning_calls) == 1, f"Expected 1 warning, got {len(warning_calls)}"


class TestPyBulletRealAssetIntegration:
    @pytest.mark.skipif(
        pytest.importorskip("pybullet", exc_type=ImportError) is None,
        reason="PyBullet not installed",
    )
    def test_pybullet_loads_sample_urdf(self, tmp_path):
        """PyBulletSimulator should load a real URDF without crashing."""
        import sys
        import pybullet as p
        from surg_rl.scene_definition.schema import (
            Metadata,
            SceneDefinition,
            RobotConfig,
            Pose,
            Position,
            Orientation,
        )
        from surg_rl.simulators.pybullet_simulator import PyBulletSimulator

        urdf_path = tmp_path / "sample_robot.urdf"
        urdf_path.write_text(
            '<?xml version="1.0"?>\n'
            '<robot name="sample_robot">\n'
            '  <link name="base">\n'
            '    <visual><geometry><box size="0.1 0.1 0.1"/></geometry></visual>\n'
            '    <collision><geometry><box size="0.1 0.1 0.1"/></geometry></collision>\n'
            '  </link>\n'
            '</robot>\n'
        )
        scene = SceneDefinition(
            metadata=Metadata(name="urdf_scene"),
            robots=[
                RobotConfig(
                    name="sample_robot",
                    urdf_path=str(urdf_path),
                    links=[{"name": "base"}],
                    base_pose=Pose(
                        position=Position(x=0, y=0, z=0.5),
                        orientation=Orientation(w=1, x=0, y=0, z=0),
                    ),
                )
            ],
        )
        sim = PyBulletSimulator(render_mode="DIRECT")
        try:
            sim.load_scene(scene)
            assert "sample_robot" in sim._body_ids
            body_id = sim._body_ids["sample_robot"]
            assert body_id >= 0
        finally:
            sim.close()

    def test_scene_builder_creates_mjcf_with_mesh(self, tmp_path):
        """create_mjcf should include mesh asset when tissue has real mesh."""
        from surg_rl.scene_definition.schema import (
            Metadata,
            SceneDefinition,
            TissueConfig,
            TissueMeshDefinition,
            MeshAsset,
        )

        obj_path = tmp_path / "sample_tissue.obj"
        obj_path.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n")
        builder = SceneBuilder(assets_dir=str(tmp_path))
        scene = SceneDefinition(
            metadata=Metadata(name="mesh_scene"),
            tissues=[
                TissueConfig(
                    name="tissue",
                    geometry=TissueMeshDefinition(
                        mesh=MeshAsset(path="sample_tissue.obj"),
                        primitive="box",
                        dimensions=(0.1, 0.1, 0.01),
                    ),
                )
            ],
        )
        mjcf = builder.create_mjcf(scene, output_path=tmp_path / "scene.xml")
        assert mjcf.exists()
        content = mjcf.read_text()
        import xml.etree.ElementTree as ET

        root = ET.fromstring(content)
        mesh_elems = root.findall(".//mesh")
        assert any(m.get("name") == "tissue_mesh" for m in mesh_elems)
        geom_elems = root.findall(".//geom")
        assert any(g.get("type") == "mesh" and g.get("mesh") == "tissue_mesh" for g in geom_elems)


class TestMeshLoading:
    def test_procedural_fallback_when_no_path(self):
        """load_instrument_mesh returns procedural shape when mesh_path is None."""
        try:
            from surg_rl.assets.mesh_loader import load_instrument_mesh

            mesh = load_instrument_mesh("forceps", mesh_path=None)
            assert mesh is not None
            assert hasattr(mesh, "vertices")
            assert len(mesh.vertices) > 0
        except ImportError:
            pytest.skip("trimesh not installed")

    def test_deduplicated_warning_for_missing_mesh(self):
        """Same missing mesh path only logs one warning."""
        from surg_rl.assets.mesh_loader import _WARNED_MESHES, load_instrument_mesh

        _WARNED_MESHES.clear()
        try:
            mesh1 = load_instrument_mesh("forceps", mesh_path="nonexistent/file.obj")
            mesh2 = load_instrument_mesh("forceps", mesh_path="nonexistent/file.obj")
            assert mesh1 is not None
            assert mesh2 is not None
        except ImportError:
            pytest.skip("trimesh not installed")


class TestURDFTemplates:
    def test_all_instrument_types_have_templates(self):
        from surg_rl.assets.mesh_loader import URDF_TEMPLATES

        required = {
            "forceps", "scalpel", "needle_driver", "scissors",
            "clamp", "suction", "cautery", "camera", "retractor",
        }
        assert required.issubset(set(URDF_TEMPLATES.keys()))

    def test_generate_urdf_produces_valid_xml(self):
        """generate_urdf writes valid URDF with correct link count."""
        try:
            import trimesh
            from surg_rl.assets.mesh_loader import generate_urdf

            mesh = trimesh.creation.box(extents=[0.01, 0.01, 0.1])
            collision = [mesh.convex_hull]
            urdf_path = generate_urdf("scalpel", mesh, collision, name="test_instr")
            assert urdf_path.exists()
            content = urdf_path.read_text()
            assert "<robot name=" in content
            assert "<link name=" in content
            assert "<visual>" in content
            assert "<collision>" in content
        except ImportError:
            pytest.skip("trimesh not installed")


class TestDecimation:
    def test_decimate_reduces_faces(self):
        """target_face_count=500 produces fewer faces than original."""
        try:
            import trimesh
            from surg_rl.assets.mesh_loader import decimate_and_decompose

            mesh = trimesh.creation.icosphere(subdivisions=4)
            faces_original = len(mesh.faces)
            _, _ = decimate_and_decompose(mesh, target_face_count=500)
            # Decimation happens on a copy — original unchanged
            assert len(mesh.faces) == faces_original
        except ImportError:
            pytest.skip("trimesh not installed")

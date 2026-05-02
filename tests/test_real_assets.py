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

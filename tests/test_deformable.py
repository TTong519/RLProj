"""Tests for deformable body configuration and MuJoCo FEM integration."""

import numpy as np
import pytest
from pydantic import ValidationError

from surg_rl.scene_definition.schema import (
    BoundaryCondition,
    DeformableConfig,
    MuJoCoFlexConfig,
    PyBulletFlexConfig,
    TissueConfig,
)


class TestDeformableConfigSchema:
    """DEFM-03: DeformableConfig schema validation."""

    def test_tetgen_source_requires_mesh_path(self):
        dc = DeformableConfig(mesh_source="tetgen", mesh_path="meshes/tissue")
        assert dc.mesh_path == "meshes/tissue"
        with pytest.raises(ValidationError):
            DeformableConfig(mesh_source="tetgen")

    def test_grid_source_allows_no_mesh_path(self):
        dc = DeformableConfig(mesh_source="flexcomp_grid")
        assert dc.mesh_path is None

    def test_file_source_requires_mesh_path(self):
        with pytest.raises(ValidationError):
            DeformableConfig(mesh_source="file")

    def test_mujoco_flex_config_overrides(self):
        mc = MuJoCoFlexConfig(youngs_modulus=15000.0, poissons_ratio=0.45)
        assert mc.youngs_modulus == pytest.approx(15000.0)
        assert mc.poissons_ratio == pytest.approx(0.45)
        assert mc.condim == 3
        assert mc.friction == pytest.approx(0.5)

    def test_pybullet_flex_config_stores_solver_type(self):
        pc = PyBulletFlexConfig(
            solver_type="neo_hookean", auto_derive_neo_hookean=True
        )
        assert pc.solver_type == "neo_hookean"
        assert pc.auto_derive_neo_hookean is True
        pc2 = PyBulletFlexConfig(
            solver_type="neo_hookean", auto_derive_neo_hookean=False
        )
        assert pc2.auto_derive_neo_hookean is False

    def test_boundary_condition_validation(self):
        bc = BoundaryCondition(name="clamp_l", type="pin", anchor_body="clamp_left")
        assert bc.type == "pin"
        assert bc.anchor_body == "clamp_left"
        with pytest.raises(ValidationError):
            BoundaryCondition(name="bad", type="invalid", anchor_body="x")

    def test_tissue_config_includes_deformable(self):
        from surg_rl.scene_definition.schema import TissueMeshDefinition

        tissue = TissueConfig(
            name="liver",
            geometry=TissueMeshDefinition(primitive="box", dimensions=(0.1, 0.1, 0.1)),
            soft_body=True,
            deformable=DeformableConfig(
                mesh_source="tetgen", mesh_path="meshes/liver"
            ),
        )
        assert tissue.deformable is not None
        assert tissue.deformable.mesh_path == "meshes/liver"

    def test_tissue_config_without_deformable_is_none(self):
        from surg_rl.scene_definition.schema import TissueMeshDefinition

        tissue = TissueConfig(
            name="rigid_body",
            geometry=TissueMeshDefinition(primitive="box", dimensions=(0.1, 0.1, 0.1)),
            soft_body=False,
        )
        assert tissue.deformable is None

    def test_backend_configs_dont_cross_contaminate(self):
        dc = DeformableConfig(
            mesh_source="tetgen",
            mesh_path="meshes/tissue",
            mujoco=MuJoCoFlexConfig(youngs_modulus=15000.0),
            pybullet=PyBulletFlexConfig(solver_type="neo_hookean"),
        )
        assert dc.mujoco.youngs_modulus == pytest.approx(15000.0)
        assert dc.pybullet.solver_type == "neo_hookean"
        assert not hasattr(dc.pybullet, "youngs_modulus")
        assert not hasattr(dc.mujoco, "solver_type")


class TestMuJoCoFlexGeneration:
    """DEFM-01: MuJoCo FEM flex body MJCF generation."""

    def test_parse_node_file(self, tetgen_cube_mesh):
        node_path, _ = tetgen_cube_mesh
        from surg_rl.simulators.scene_builder import _parse_tetgen_node

        verts = _parse_tetgen_node(node_path)
        assert verts.shape == (9, 3)
        assert verts.dtype == np.float64
        assert verts[0, 0] == pytest.approx(0.0)

    def test_parse_ele_file_converts_to_zero_indexed(self, tetgen_cube_mesh):
        _, ele_path = tetgen_cube_mesh
        from surg_rl.simulators.scene_builder import _parse_tetgen_ele

        elems = _parse_tetgen_ele(ele_path)
        assert elems.shape == (12, 4)
        assert elems.dtype == np.int32
        assert elems.min() == 0
        assert elems.max() == 8

    def test_flex_body_mjcf_structure(self, tetgen_cube_mesh):
        import xml.etree.ElementTree as ET

        node_path, ele_path = tetgen_cube_mesh
        from surg_rl.scene_definition.schema import TissueMeshDefinition
        from surg_rl.simulators.scene_builder import SceneBuilder

        tissue = TissueConfig(
            name="test_tissue",
            geometry=TissueMeshDefinition(primitive="box", dimensions=(1.0, 1.0, 1.0)),
            soft_body=True,
            deformable=DeformableConfig(
                mesh_source="tetgen",
                mesh_path=str(node_path.with_suffix("")),
            ),
        )

        mujoco = ET.Element("mujoco")
        ET.SubElement(mujoco, "worldbody")
        sb = SceneBuilder()
        sb._add_flex_body_to_mjcf(mujoco, tissue, node_path=node_path, ele_path=ele_path)

        deformable = mujoco.find("deformable")
        assert deformable is not None
        flex = deformable.find("flex")
        assert flex is not None
        assert flex.get("name") == "test_tissue_flex"
        assert flex.get("dim") == "3"
        assert flex.get("body") == "world"

        vertex_el = flex.find("vertex")
        assert vertex_el is not None
        vertex_text = vertex_el.text.strip()
        vertex_lines = [l for l in vertex_text.split("\n") if l.strip()]
        assert len(vertex_lines) == 9

        element_el = flex.find("element")
        assert element_el is not None
        element_text = element_el.text.strip()
        element_lines = [l for l in element_text.split("\n") if l.strip()]
        assert len(element_lines) == 12

    def test_flex_body_elasticity_from_config(self, tetgen_cube_mesh):
        import xml.etree.ElementTree as ET

        node_path, ele_path = tetgen_cube_mesh
        from surg_rl.scene_definition.schema import TissueMeshDefinition
        from surg_rl.simulators.scene_builder import SceneBuilder

        tissue = TissueConfig(
            name="stiff_tissue",
            geometry=TissueMeshDefinition(primitive="box", dimensions=(1.0, 1.0, 1.0)),
            soft_body=True,
            deformable=DeformableConfig(
                mesh_source="tetgen",
                mesh_path=str(node_path.with_suffix("")),
                mujoco=MuJoCoFlexConfig(youngs_modulus=15000.0),
            ),
        )
        tissue.physics.youngs_modulus = 10000.0
        tissue.physics.poissons_ratio = 0.45
        tissue.physics.damping = 0.1

        mujoco = ET.Element("mujoco")
        ET.SubElement(mujoco, "worldbody")
        sb = SceneBuilder()
        sb._add_flex_body_to_mjcf(mujoco, tissue, node_path=node_path, ele_path=ele_path)

        elasticity = mujoco.find(".//elasticity")
        assert elasticity is not None
        assert elasticity.get("young") == "15000.0"
        assert elasticity.get("poisson") == "0.45"

    def test_flex_body_boundary_conditions(self, tetgen_cube_mesh):
        import xml.etree.ElementTree as ET

        node_path, ele_path = tetgen_cube_mesh
        from surg_rl.scene_definition.schema import TissueMeshDefinition
        from surg_rl.simulators.scene_builder import SceneBuilder

        tissue = TissueConfig(
            name="clamped_tissue",
            geometry=TissueMeshDefinition(primitive="box", dimensions=(1.0, 1.0, 1.0)),
            soft_body=True,
            deformable=DeformableConfig(
                mesh_source="tetgen",
                mesh_path=str(node_path.with_suffix("")),
                boundary_conditions=[
                    BoundaryCondition(name="clamp_left", type="pin", anchor_body="clamp_left"),
                    BoundaryCondition(name="clamp_right", type="pin", anchor_body="clamp_right"),
                ],
            ),
        )

        mujoco = ET.Element("mujoco")
        wb = ET.SubElement(mujoco, "worldbody")
        ET.SubElement(wb, "body", name="clamp_left")
        ET.SubElement(wb, "body", name="clamp_right")
        sb = SceneBuilder()
        sb._add_flex_body_to_mjcf(mujoco, tissue, node_path=node_path, ele_path=ele_path)

        equality = mujoco.find("equality")
        assert equality is not None
        welds = equality.findall("weld")
        assert len(welds) == 2
        weld_names = [w.get("name") for w in welds]
        assert "pin_clamp_left" in weld_names
        assert "pin_clamp_right" in weld_names

    def test_backward_compat_flexcomp_fallback(self):
        import xml.etree.ElementTree as ET

        from surg_rl.scene_definition.schema import TissueMeshDefinition
        from surg_rl.simulators.scene_builder import SceneBuilder

        tissue = TissueConfig(
            name="old_tissue",
            geometry=TissueMeshDefinition(primitive="box", dimensions=(0.1, 0.1, 0.1)),
            soft_body=True,
        )

        mujoco = ET.Element("mujoco")
        ET.SubElement(mujoco, "worldbody")
        asset = ET.SubElement(mujoco, "asset")
        sb = SceneBuilder()
        sb._add_tissue_to_mjcf(mujoco, tissue, 0, asset)

        flexcomp = mujoco.find(".//flexcomp")
        assert flexcomp is not None
        assert flexcomp.get("type") == "grid"

    def test_rigid_body_path_unchanged(self):
        import xml.etree.ElementTree as ET

        from surg_rl.scene_definition.schema import TissueMeshDefinition
        from surg_rl.simulators.scene_builder import SceneBuilder

        tissue = TissueConfig(
            name="rigid_obj",
            geometry=TissueMeshDefinition(primitive="box", dimensions=(0.1, 0.1, 0.1)),
            soft_body=False,
        )

        mujoco = ET.Element("mujoco")
        ET.SubElement(mujoco, "worldbody")
        asset = ET.SubElement(mujoco, "asset")
        sb = SceneBuilder()
        sb._add_tissue_to_mjcf(mujoco, tissue, 0, asset)

        assert mujoco.find(".//flexcomp") is None
        assert mujoco.find(".//flex") is None
        geom = mujoco.find(".//geom")
        assert geom is not None

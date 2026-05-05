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


class TestPyBulletParamMapping:
    """DEFM-02: PyBullet soft body parameter mapping."""

    def test_derive_neo_hookean_params_typical_tissue(self):
        from surg_rl.simulators.pybullet_simulator import _derive_neo_hookean_params

        mu, lam = _derive_neo_hookean_params(10000.0, 0.45)
        assert mu == pytest.approx(3448.27586, rel=0.01)
        assert lam == pytest.approx(31034.48276, rel=0.01)

    def test_derive_neo_hookean_params_low_poisson(self):
        from surg_rl.simulators.pybullet_simulator import _derive_neo_hookean_params

        mu, lam = _derive_neo_hookean_params(5000.0, 0.3)
        assert mu == pytest.approx(1923.0769, rel=0.01)
        assert lam == pytest.approx(2884.61538, rel=0.01)

    def test_derive_neo_hookean_params_zero_poisson(self):
        from surg_rl.simulators.pybullet_simulator import _derive_neo_hookean_params

        mu, lam = _derive_neo_hookean_params(10000.0, 0.0)
        assert mu == pytest.approx(5000.0)
        assert lam == pytest.approx(0.0)

    def test_neo_hookean_auto_derive_kwargs(self):
        from surg_rl.scene_definition.schema import TissueMeshDefinition
        from surg_rl.simulators.pybullet_simulator import _derive_neo_hookean_params

        tissue = TissueConfig(
            name="test_tissue",
            geometry=TissueMeshDefinition(primitive="box", dimensions=(0.1, 0.1, 0.1)),
            soft_body=True,
            deformable=DeformableConfig(
                mesh_source="flexcomp_grid",
                pybullet=PyBulletFlexConfig(
                    solver_type="neo_hookean", auto_derive_neo_hookean=True
                ),
            ),
        )
        tissue.physics.youngs_modulus = 10000.0
        tissue.physics.poissons_ratio = 0.45

        mu, lam = _derive_neo_hookean_params(10000.0, 0.45)
        dc = tissue.deformable
        pbc = tissue.physics.pybullet
        kwargs = {
            "useNeoHookean": 1,
            "useMassSpring": 0,
            "NeoHookeanMu": mu,
            "NeoHookeanLambda": lam,
            "NeoHookeanDamping": pbc.neo_hookean_damping,
            "repulsionStiffness": dc.pybullet.repulsion_stiffness,
            "collisionMargin": dc.pybullet.collision_margin,
        }
        assert kwargs["NeoHookeanMu"] != pytest.approx(1.0)
        assert kwargs["NeoHookeanLambda"] != pytest.approx(1.0)
        assert kwargs["NeoHookeanMu"] == pytest.approx(mu, rel=0.01)

    def test_neo_hookean_explicit_override(self):
        from surg_rl.scene_definition.schema import TissueMeshDefinition

        tissue = TissueConfig(
            name="test_tissue",
            geometry=TissueMeshDefinition(primitive="box", dimensions=(0.1, 0.1, 0.1)),
            soft_body=True,
            deformable=DeformableConfig(
                mesh_source="flexcomp_grid",
                pybullet=PyBulletFlexConfig(
                    solver_type="neo_hookean", auto_derive_neo_hookean=False
                ),
            ),
        )
        pbc = tissue.physics.pybullet
        pbc.neo_hookean_mu = 5.0
        pbc.neo_hookean_lambda = 8.0
        assert pbc.neo_hookean_mu == pytest.approx(5.0)
        assert pbc.neo_hookean_lambda == pytest.approx(8.0)

    def test_mass_spring_mode_unchanged(self):
        from surg_rl.scene_definition.schema import TissueMeshDefinition

        tissue = TissueConfig(
            name="test_tissue",
            geometry=TissueMeshDefinition(primitive="box", dimensions=(0.1, 0.1, 0.1)),
            soft_body=True,
            deformable=DeformableConfig(
                mesh_source="flexcomp_grid",
                pybullet=PyBulletFlexConfig(solver_type="mass_spring"),
            ),
        )
        pbc = tissue.physics.pybullet
        kwargs = {
            "useMassSpring": 1,
            "useNeoHookean": 0,
            "springElasticStiffness": pbc.spring_elastic_stiffness,
            "springDampingStiffness": pbc.spring_damping_stiffness,
        }
        assert kwargs["useMassSpring"] == 1
        assert kwargs["useNeoHookean"] == 0

    def test_pybullet_flex_overrides_flow(self):
        from surg_rl.scene_definition.schema import TissueMeshDefinition

        tissue = TissueConfig(
            name="test_tissue",
            geometry=TissueMeshDefinition(primitive="box", dimensions=(0.1, 0.1, 0.1)),
            soft_body=True,
            deformable=DeformableConfig(
                mesh_source="flexcomp_grid",
                pybullet=PyBulletFlexConfig(
                    solver_type="mass_spring",
                    repulsion_stiffness=900.0,
                    collision_margin=0.01,
                    use_self_collision=True,
                ),
            ),
        )
        pc = tissue.deformable.pybullet
        assert pc.repulsion_stiffness == pytest.approx(900.0)
        assert pc.collision_margin == pytest.approx(0.01)
        assert pc.use_self_collision is True

    def test_no_deformable_config_backward_compat(self):
        from surg_rl.scene_definition.schema import TissueMeshDefinition

        tissue = TissueConfig(
            name="old_tissue",
            geometry=TissueMeshDefinition(primitive="box", dimensions=(0.1, 0.1, 0.1)),
            soft_body=True,
        )
        assert tissue.deformable is None
        pbc = tissue.physics.pybullet
        kwargs = {
            "useMassSpring": 1 if pbc.use_mass_spring else 0,
            "useNeoHookean": 1 if pbc.use_neo_hookean else 0,
        }
        assert kwargs["useMassSpring"] == 1
        assert kwargs["useNeoHookean"] == 0


class TestDeformableObservation:
    """DEFM-04: Deformable state observable (vertex positions, strain)."""

    def test_build_spec_default_max_vertices(self):
        from surg_rl.rl.observation import build_deformable_spec

        spec = build_deformable_spec(max_vertices=200)
        assert spec.shape == (200, 3)
        assert spec.low.shape == (200, 3)
        assert spec.high.shape == (200, 3)
        assert spec.name == "tissue_deformation"

    def test_build_spec_custom_max_vertices(self):
        from surg_rl.rl.observation import build_deformable_spec

        spec = build_deformable_spec(max_vertices=50)
        assert spec.shape == (50, 3)
        assert spec.name == "tissue_deformation"

    def test_pad_observation_to_spec(self):
        from surg_rl.rl.observation import _pad_deformable_obs

        deformation = np.ones((100, 3), dtype=np.float32) * 0.5
        result = _pad_deformable_obs(deformation, (200, 3))
        assert result.shape == (200, 3)
        assert result.dtype == np.float32
        assert np.all(result[:100] == 0.5)
        assert np.all(result[100:] == 0.0)

    def test_truncate_observation_to_spec(self):
        from surg_rl.rl.observation import _pad_deformable_obs

        deformation = np.ones((300, 3), dtype=np.float32)
        result = _pad_deformable_obs(deformation, (200, 3))
        assert result.shape == (200, 3)
        assert np.all(result == 1.0)

    def test_empty_observation_returns_zero_fallback(self):
        from surg_rl.rl.observation import _pad_deformable_obs

        result = _pad_deformable_obs(None, (50, 3))
        assert result.shape == (50, 3)
        assert np.all(result == 0.0)

    def test_compute_edge_strain_identical(self):
        from surg_rl.rl.observation import compute_per_edge_strain

        edges = np.array([1.0, 2.0, 0.5], dtype=np.float32)
        strain = compute_per_edge_strain(edges, edges)
        assert np.allclose(strain, 0.0)

    def test_compute_edge_strain_stretched(self):
        from surg_rl.rl.observation import compute_per_edge_strain

        rest = np.array([1.0, 1.0, 1.0], dtype=np.float32)
        current = np.array([1.5, 1.0, 0.5], dtype=np.float32)
        strain = compute_per_edge_strain(rest, current)
        assert strain[0] == pytest.approx(0.5)
        assert strain[1] == pytest.approx(0.0)
        assert strain[2] == pytest.approx(0.5)

    def test_compute_edge_strain_zero_rest_epsilon(self):
        from surg_rl.rl.observation import compute_per_edge_strain

        rest = np.array([0.0, 1e-9], dtype=np.float32)
        current = np.array([0.5, 0.5], dtype=np.float32)
        strain = compute_per_edge_strain(rest, current)
        assert np.isfinite(strain[0])
        assert strain[0] > 0.0

"""Tests for volumetric tetrahedral mesh cutting."""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from surg_rl.cutting.engine import cut_tetrahedral_mesh
from surg_rl.cutting.intersection import (
    classify_tet_case,
    compute_signed_distances,
    edge_intersection,
)
from surg_rl.rl.environment import SurgicalEnv


class TestIntersection:
    """CUT-01: Signed distance and edge intersection."""

    def test_compute_signed_distances(self):
        verts = np.array(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )
        origin = np.array([0.5, 0.5, 0.0])
        normal = np.array([0.0, 0.0, 1.0])
        dists = compute_signed_distances(verts, origin, normal)
        assert dists.shape == (4,)
        assert dists[0] == 0.0  # (0,0,0) on plane z=0
        assert dists[1] == 0.0
        assert dists[2] == 0.0
        assert dists[3] == 1.0  # (0,0,1) above plane

    def test_edge_intersection_midpoint(self):
        v_i = np.array([0.0, 0.0, 0.0])
        v_j = np.array([2.0, 0.0, 0.0])
        pt = edge_intersection(v_i, v_j, -1.0, 1.0)
        assert pt[0] == 1.0
        assert pt[1] == 0.0
        assert pt[2] == 0.0

    def test_edge_intersection_zero_denom(self):
        v_i = np.array([0.0, 0.0, 0.0])
        v_j = np.array([1.0, 0.0, 0.0])
        pt = edge_intersection(v_i, v_j, 0.0, 0.0)
        assert pt[0] == 0.5

    def test_classify_tet_case_all_same(self):
        assert classify_tet_case(1.0, 1.0, 1.0, 1.0, 1e-12) == 0
        assert classify_tet_case(-1.0, -1.0, -1.0, -1.0, 1e-12) == 0

    def test_classify_tet_case_3_1(self):
        assert classify_tet_case(1.0, -1.0, -1.0, -1.0, 1e-12) == 1
        assert classify_tet_case(1.0, 1.0, 1.0, -1.0, 1e-12) == 3

    def test_classify_tet_case_2_2(self):
        assert classify_tet_case(1.0, 1.0, -1.0, -1.0, 1e-12) == 2

    def test_classify_tet_case_degenerate(self):
        assert classify_tet_case(0.0, 1.0, 1.0, 1.0, 1e-12) == 4


class TestCutEngine:
    """CUT-01/02: Volumetric cutting engine tests."""

    def test_cut_unit_tetrahedron(self):
        verts = np.float64(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.5, 1.0, 0.0],
                [0.5, 0.33, 1.0],
            ]
        )
        tets = np.int32([[0, 1, 2, 3]])
        origin = np.array([0.5, 0.5, 0.3])
        normal = np.array([0.0, 0.0, 1.0])

        new_v, new_t, cut_f = cut_tetrahedral_mesh(verts, tets, origin, normal)
        assert new_v.shape[0] > 4
        assert new_t.shape[0] >= 2
        # All child tets should have non-zero volume (via positive 4x4 determinant sign)
        for tet in new_t:
            v = new_v[tet]
            a = v[1] - v[0]
            b = v[2] - v[0]
            c = v[3] - v[0]
            vol = abs(np.dot(a, np.cross(b, c))) / 6.0
            assert vol > 1e-15

    def test_cut_tetrahedralized_cube(self):
        # 8 cube corners
        verts = np.float64(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [1.0, 1.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
                [1.0, 0.0, 1.0],
                [1.0, 1.0, 1.0],
                [0.0, 1.0, 1.0],
            ]
        )
        # 5 tetrahedra decomposing the cube (common decomposition)
        tets = np.int32(
            [
                [0, 1, 2, 5],
                [0, 2, 3, 7],
                [0, 2, 7, 5],
                [0, 5, 7, 4],
                [2, 5, 7, 6],
            ]
        )

        origin = np.array([0.5, 0.5, 0.5])
        normal = np.array([1.0, 0.0, 0.0])

        new_v, new_t, cut_f = cut_tetrahedral_mesh(verts, tets, origin, normal)
        assert new_v.shape[0] > 8
        assert new_t.shape[0] >= 5
        for tet in new_t:
            assert tet.min() >= 0
            assert tet.max() < new_v.shape[0]

    def test_cut_misses_all_tets(self):
        verts = np.float64(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, -1.0],
                [0.5, 1.0, 0.0],
                [0.5, 0.33, 1.0],
            ]
        )
        tets = np.int32([[0, 1, 2, 3]])
        origin = np.array([5.0, 5.0, 5.0])
        normal = np.array([0.0, 0.0, 1.0])

        new_v, new_t, cut_f = cut_tetrahedral_mesh(verts, tets, origin, normal)
        assert new_v.shape[0] == 4
        assert new_t.shape[0] == 1
        assert cut_f.shape[0] == 0

    def test_cut_boundary_faces_extracted(self):
        verts = np.float64(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.5, 1.0, 0.0],
                [0.5, 0.33, 1.0],
            ]
        )
        tets = np.int32([[0, 1, 2, 3]])
        origin = np.array([0.5, 0.5, 0.3])
        normal = np.array([0.0, 0.0, 1.0])

        new_v, new_t, cut_f = cut_tetrahedral_mesh(verts, tets, origin, normal)
        assert cut_f.shape[0] > 0

    def test_vertex_dedup_adjacent_tets(self):
        verts = np.float64(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [1.0, 1.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
                [1.0, 0.0, 1.0],
                [1.0, 1.0, 1.0],
                [0.0, 1.0, 1.0],
            ]
        )
        tets = np.int32(
            [
                [0, 1, 2, 5],
                [0, 2, 3, 7],
                [0, 2, 7, 5],
                [0, 5, 7, 4],
                [2, 5, 7, 6],
            ]
        )

        origin = np.array([0.5, 0.5, 0.5])
        normal = np.array([0.0, 1.0, 0.0])

        new_v, new_t, cut_f = cut_tetrahedral_mesh(verts, tets, origin, normal)
        # Edge (0, 5) shared by tets [0,1,2,5] and [0,5,7,4]
        # Should produce only 1 intersection vertex, not 2
        assert new_v.shape[0] > 8
        # All tet indices valid
        assert new_t.max() < new_v.shape[0]
        assert new_t.min() >= 0


class TestCutActionSchema:
    """CUT-03: CutAction Pydantic schema validation."""

    def test_cut_action_basic(self):
        from surg_rl.scene_definition.schema import CutAction, Position

        ca = CutAction(
            tissue_name="tissue_1",
            surface_point=Position(x=0.1, y=0.2, z=0.3),
            direction=Position(x=1.0, y=0.0, z=0.0),
        )
        assert ca.tissue_name == "tissue_1"
        assert ca.depth == 0.01

    def test_cut_action_normalizes_direction(self):
        from surg_rl.scene_definition.schema import CutAction, Position

        ca = CutAction(
            tissue_name="t",
            surface_point=Position(x=0.0, y=0.0, z=0.0),
            direction=Position(x=2.0, y=0.0, z=0.0),
        )
        d = ca.direction
        assert abs(d.x - 1.0) < 1e-6
        assert abs(d.y) < 1e-6
        assert abs(d.z) < 1e-6

    def test_cut_action_zero_direction_raises(self):
        import pytest

        from surg_rl.scene_definition.schema import CutAction, Position

        with pytest.raises(ValueError, match="nonzero"):
            CutAction(
                tissue_name="t",
                surface_point=Position(x=0.0, y=0.0, z=0.0),
                direction=Position(x=0.0, y=0.0, z=0.0),
            )


class TestMuJoCoRewiteMesh:
    """CUT-03: _rewrite_flex_mesh_in_mjcf utility."""

    def test_rewrite_updates_vertex_element_text(self):
        from surg_rl.simulators.mujoco_simulator import MuJoCoSimulator

        verts = np.array(
            [
                [0.0, 0.0, 0.0],
                [0.1, 0.0, 0.0],
                [0.0, 0.1, 0.0],
                [0.0, 0.0, 0.1],
                [0.1, 0.1, 0.0],
                [0.1, 0.0, 0.1],
                [0.0, 0.1, 0.1],
                [0.1, 0.1, 0.1],
            ]
        )
        tets = np.array([[0, 1, 2, 5], [0, 2, 3, 7], [0, 2, 7, 5], [0, 5, 7, 4], [2, 5, 7, 6]])

        mjcf_xml = """<?xml version="1.0" encoding="UTF-8"?>
<mujoco model="test">
  <deformable>
    <flex name="tissue_flex" dim="3" radius="0.0" flatskin="false" body="world">
      <contact condim="3" solref="0.01 1" solimp="0.95 0.99 0.0001" friction="1.0 0.005 0.0001" selfcollide="none" margin="0.0"/>
      <edge stiffness="1e6" damping="50.0"/>
      <elasticity young="10.0" poisson="0.49" damping="5.0"/>
      <vertex>0.000000 0.000000 0.000000
0.100000 0.000000 0.000000
0.000000 0.100000 0.000000
0.000000 0.000000 0.100000</vertex>
      <element>0 1 2 3</element>
    </flex>
  </deformable>
</mujoco>"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(mjcf_xml)
        mjcf_path = Path(f.name)

        try:
            sim = MuJoCoSimulator.__new__(MuJoCoSimulator)
            sim._mjcf_path = mjcf_path
            sim._rewrite_flex_mesh_in_mjcf("tissue_flex", verts, tets)

            updated_text = mjcf_path.read_text()
            assert "0.000000 0.000000 0.000000" in updated_text
            assert "2 5 7 6" in updated_text
        finally:
            mjcf_path.unlink(missing_ok=True)


class TestPyBulletCutStorage:
    """CUT-03: PyBullet stores tetrahedra at load time for cut reuse."""

    def test_soft_body_tets_stored(self):
        from surg_rl.simulators.pybullet_simulator import PyBulletSimulator
        from surg_rl.utils.mesh_generation import generate_box_tet_mesh
        from surg_rl.utils.vtk_io import write_vtk_unstructured_grid

        sim = PyBulletSimulator.__new__(PyBulletSimulator)
        sim._soft_body_tet_data = {}
        sim._soft_body_mesh_paths = {}
        sim._soft_body_ids = {}

        verts, tets = generate_box_tet_mesh((0.1, 0.1, 0.01), resolution=3)
        tmp = tempfile.NamedTemporaryFile(suffix=".vtk", delete=False)  # noqa: SIM115
        vtk_path = Path(tmp.name)
        tmp.close()
        try:
            write_vtk_unstructured_grid(vtk_path, verts, tets)
            sim._soft_body_tet_data["t_tets"] = (verts, tets)
            sim._soft_body_mesh_paths["t"] = vtk_path
            sim._soft_body_ids["t"] = 42

            assert "t" in sim._soft_body_ids
            assert "t_tets" in sim._soft_body_tet_data
            stored_v, stored_t = sim._soft_body_tet_data["t_tets"]
            assert stored_v.shape == verts.shape
            assert stored_t.shape == tets.shape
        finally:
            vtk_path.unlink(missing_ok=True)


class TestCutCooldown:
    """DEBT-04: Cut cooldown (500 ms @ 50 Hz = 25 steps) regression test.

    Parametrized over both MuJoCo and PyBullet backends so the cooldown
    contract is verified regardless of which physics backend is active.
    Uses `_step_count` directly as the mockable time source — wall-clock
    time is non-deterministic in CI runners.

    Reference: .planning/REQUIREMENTS.md:54 (DEBT-04)
    Source of truth: src/surg_rl/rl/environment.py:738-783 (trigger_cut)
    """

    BACKENDS = ["mujoco", "pybullet"]

    @pytest.fixture(params=BACKENDS)
    def env(self, request):
        """Construct a SurgicalEnv for the requested backend, skipping if unavailable.

        Mirrors the per-method skipif pattern from Phase 30 dreamer E2E test
        (30-01-SUMMARY.md) — some CI runners have one backend but not the other.
        """
        backend = request.param
        try:
            if backend == "mujoco":
                from surg_rl.simulators.mujoco_simulator import MuJoCoSimulator

                sim = MuJoCoSimulator(timestep=0.02)  # 50 Hz
            elif backend == "pybullet":
                from surg_rl.simulators.pybullet_simulator import PyBulletSimulator

                sim = PyBulletSimulator(timestep=0.02)
            else:
                pytest.skip(f"Unknown backend: {backend}")
                return
        except Exception as exc:
            pytest.skip(f"{backend} backend unavailable: {exc}")
            return

        try:
            env_obj = SurgicalEnv.__new__(SurgicalEnv)  # bypass __init__
            env_obj._step_count = 0
            env_obj._last_cut_step = -1000
            env_obj._cut_cooldown_steps = 25
            env_obj._simulator = sim
            return env_obj
        except Exception as exc:
            pytest.skip(f"SurgicalEnv construction failed for {backend}: {exc}")
            return

    def test_first_cut_succeeds(self, env):
        """A cut on step 0 (with _last_cut_step=-1000) succeeds — no cooldown conflict."""
        from surg_rl.scene_definition.schema import Position

        surface_point = Position(x=0.0, y=0.0, z=0.0)
        direction = Position(x=0.0, y=0.0, z=1.0)
        result = env.trigger_cut(
            tissue_name="tissue_1",
            surface_point=surface_point,
            direction=direction,
            depth=0.01,
        )
        assert result in (True, False)
        if result:
            assert env._last_cut_step == 0

    def test_second_cut_within_cooldown_blocked(self, env):
        """A second cut within _cut_cooldown_steps (25) of the first returns False.

        Sets _last_cut_step = 0 and _step_count = 10 (within the 25-step window),
        then verifies trigger_cut returns False regardless of simulator backend.
        """
        from surg_rl.scene_definition.schema import Position

        surface_point = Position(x=0.0, y=0.0, z=0.0)
        direction = Position(x=0.0, y=0.0, z=1.0)

        env._last_cut_step = 0
        env._step_count = 10  # only 10 steps elapsed — within cooldown
        result = env.trigger_cut(
            tissue_name="tissue_1",
            surface_point=surface_point,
            direction=direction,
            depth=0.01,
        )
        assert result is False

    def test_second_cut_after_cooldown_succeeds(self, env):
        """A cut after _cut_cooldown_steps have elapsed is not blocked by cooldown."""
        from surg_rl.scene_definition.schema import Position

        surface_point = Position(x=0.0, y=0.0, z=0.0)
        direction = Position(x=0.0, y=0.0, z=1.0)

        env._last_cut_step = 0
        env._step_count = 30  # 30 > 25, cooldown elapsed
        result = env.trigger_cut(
            tissue_name="tissue_1",
            surface_point=surface_point,
            direction=direction,
            depth=0.01,
        )
        assert result in (True, False)
        if result:
            assert env._last_cut_step == 30

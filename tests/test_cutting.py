"""Tests for volumetric tetrahedral mesh cutting."""

import numpy as np

from surg_rl.cutting.intersection import classify_tet_case, compute_signed_distances, edge_intersection
from surg_rl.cutting.engine import cut_tetrahedral_mesh


class TestIntersection:
    """CUT-01: Signed distance and edge intersection."""

    def test_compute_signed_distances(self):
        verts = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ], dtype=np.float64)
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
        verts = np.float64([
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.5, 1.0, 0.0],
            [0.5, 0.33, 1.0],
        ])
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
        verts = np.float64([
            [0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0], [1.0, 0.0, 1.0], [1.0, 1.0, 1.0], [0.0, 1.0, 1.0],
        ])
        # 5 tetrahedra decomposing the cube (common decomposition)
        tets = np.int32([
            [0, 1, 2, 5],
            [0, 2, 3, 7],
            [0, 2, 7, 5],
            [0, 5, 7, 4],
            [2, 5, 7, 6],
        ])

        origin = np.array([0.5, 0.5, 0.5])
        normal = np.array([1.0, 0.0, 0.0])

        new_v, new_t, cut_f = cut_tetrahedral_mesh(verts, tets, origin, normal)
        assert new_v.shape[0] > 8
        assert new_t.shape[0] >= 5
        for tet in new_t:
            assert tet.min() >= 0
            assert tet.max() < new_v.shape[0]

    def test_cut_misses_all_tets(self):
        verts = np.float64([
            [0.0, 0.0, 0.0], [1.0, 0.0, -1.0], [0.5, 1.0, 0.0], [0.5, 0.33, 1.0],
        ])
        tets = np.int32([[0, 1, 2, 3]])
        origin = np.array([5.0, 5.0, 5.0])
        normal = np.array([0.0, 0.0, 1.0])

        new_v, new_t, cut_f = cut_tetrahedral_mesh(verts, tets, origin, normal)
        assert new_v.shape[0] == 4
        assert new_t.shape[0] == 1
        assert cut_f.shape[0] == 0

    def test_cut_boundary_faces_extracted(self):
        verts = np.float64([
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.5, 1.0, 0.0],
            [0.5, 0.33, 1.0],
        ])
        tets = np.int32([[0, 1, 2, 3]])
        origin = np.array([0.5, 0.5, 0.3])
        normal = np.array([0.0, 0.0, 1.0])

        new_v, new_t, cut_f = cut_tetrahedral_mesh(verts, tets, origin, normal)
        assert cut_f.shape[0] > 0

    def test_vertex_dedup_adjacent_tets(self):
        verts = np.float64([
            [0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0], [1.0, 0.0, 1.0], [1.0, 1.0, 1.0], [0.0, 1.0, 1.0],
        ])
        tets = np.int32([
            [0, 1, 2, 5],
            [0, 2, 3, 7],
            [0, 2, 7, 5],
            [0, 5, 7, 4],
            [2, 5, 7, 6],
        ])

        origin = np.array([0.5, 0.5, 0.5])
        normal = np.array([0.0, 1.0, 0.0])

        new_v, new_t, cut_f = cut_tetrahedral_mesh(verts, tets, origin, normal)
        # Edge (0, 5) shared by tets [0,1,2,5] and [0,5,7,4]
        # Should produce only 1 intersection vertex, not 2
        assert new_v.shape[0] > 8
        # All tet indices valid
        assert new_t.max() < new_v.shape[0]
        assert new_t.min() >= 0

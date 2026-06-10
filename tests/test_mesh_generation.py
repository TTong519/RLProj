"""Tests for procedural tetrahedral mesh generators."""

import numpy as np
import pytest

from surg_rl.utils.mesh_generation import (
    generate_box_tet_mesh,
    generate_cylinder_tet_mesh,
    generate_sphere_tet_mesh,
)
from surg_rl.utils.vtk_io import (
    read_vtk_unstructured_grid,
    validate_vtk,
    write_vtk_unstructured_grid,
)


def _tet_volume(vertices: np.ndarray, tet: np.ndarray) -> float:
    a = vertices[tet[1]] - vertices[tet[0]]
    b = vertices[tet[2]] - vertices[tet[0]]
    c = vertices[tet[3]] - vertices[tet[0]]
    return abs(float(np.dot(a, np.cross(b, c))) / 6.0)


class TestBoxTetMesh:
    def test_volume_exact(self):
        """Box volume should be exact for integer resolutions."""
        dims = (2.0, 3.0, 4.0)
        vertices, tetrahedra = generate_box_tet_mesh(dims, resolution=4)
        total = sum(_tet_volume(vertices, t) for t in tetrahedra)
        expected = np.prod(dims)
        assert total == pytest.approx(expected, abs=1e-6)

    def test_all_cells_type_10(self):
        """After VTK round-trip, all CELL_TYPES should be 10."""
        vertices, tetrahedra = generate_box_tet_mesh((1.0, 1.0, 1.0), resolution=2)
        assert tetrahedra.shape[1] == 4
        assert tetrahedra.min() >= 0
        assert tetrahedra.max() < len(vertices)

    def test_resolution_increases_cells(self):
        """Higher resolution should produce more tets."""
        _, t2 = generate_box_tet_mesh((1.0, 1.0, 1.0), resolution=2)
        _, t4 = generate_box_tet_mesh((1.0, 1.0, 1.0), resolution=4)
        assert len(t4) > len(t2)


class TestSphereTetMesh:
    def test_volume_within_5_percent(self):
        """Sphere volume should approximate 4/3 π r³ within 5%."""
        radius = 1.0
        vertices, tetrahedra = generate_sphere_tet_mesh(radius, subdivisions=3)
        total = sum(_tet_volume(vertices, t) for t in tetrahedra)
        expected = 4.0 / 3.0 * np.pi * radius**3
        assert total == pytest.approx(expected, rel=0.05)

    def test_vertices_on_surface(self):
        """Surface vertices should be close to the requested radius."""
        radius = 2.0
        vertices, _ = generate_sphere_tet_mesh(radius, subdivisions=2)
        dists = np.linalg.norm(vertices, axis=1)
        # The center point has distance 0; all others should be ~radius
        surface_dists = dists[dists > 0.1]
        assert np.allclose(surface_dists, radius, atol=0.1 * radius)

    def test_subdivision_increases_tets(self):
        _, t2 = generate_sphere_tet_mesh(1.0, subdivisions=2)
        _, t3 = generate_sphere_tet_mesh(1.0, subdivisions=3)
        assert len(t3) > len(t2)


class TestCylinderTetMesh:
    def test_volume_within_5_percent(self):
        """Cylinder volume should approximate π r² h within 5%."""
        radius, height = 1.0, 2.0
        vertices, tetrahedra = generate_cylinder_tet_mesh(
            radius, height, theta_segments=16, height_segments=4
        )
        total = sum(_tet_volume(vertices, t) for t in tetrahedra)
        expected = np.pi * radius**2 * height
        assert total == pytest.approx(expected, rel=0.05)

    def test_no_duplicate_vertices_after_deduplication(self):
        """Cylinder should not produce obvious duplicate vertices."""
        vertices, _ = generate_cylinder_tet_mesh(1.0, 1.0, theta_segments=8, height_segments=2)
        unique = np.unique(np.round(vertices, decimals=6), axis=0)
        assert len(unique) == len(vertices)


class TestVtkRoundtripWithGeneratedMeshes:
    def test_box_vtk_roundtrip(self, tmp_path):
        vertices, tetrahedra = generate_box_tet_mesh((1.0, 1.0, 1.0), resolution=2)
        path = tmp_path / "box.vtk"
        write_vtk_unstructured_grid(path, vertices, tetrahedra)
        v, t = read_vtk_unstructured_grid(path)
        assert np.allclose(v, vertices)
        assert np.array_equal(t, tetrahedra)
        validate_vtk(path)

    def test_sphere_vtk_roundtrip(self, tmp_path):
        vertices, tetrahedra = generate_sphere_tet_mesh(0.5, subdivisions=2)
        path = tmp_path / "sphere.vtk"
        write_vtk_unstructured_grid(path, vertices, tetrahedra)
        v, t = read_vtk_unstructured_grid(path)
        assert np.allclose(v, vertices)
        assert np.array_equal(t, tetrahedra)

    def test_cylinder_vtk_roundtrip(self, tmp_path):
        vertices, tetrahedra = generate_cylinder_tet_mesh(
            0.5, 1.0, theta_segments=8, height_segments=2
        )
        path = tmp_path / "cyl.vtk"
        write_vtk_unstructured_grid(path, vertices, tetrahedra)
        v, t = read_vtk_unstructured_grid(path)
        assert np.allclose(v, vertices)
        assert np.array_equal(t, tetrahedra)


class TestMeshGenerationPerformance:
    def test_box_64_cubed_under_10s(self):
        """PERF-02: 64³ box mesh must generate in <10s (tetgen)."""
        import time

        start = time.perf_counter()
        vertices, tets = generate_box_tet_mesh((1.0, 1.0, 1.0), resolution=64)
        elapsed = time.perf_counter() - start
        assert elapsed < 10.0, f"Box mesh 64³ took {elapsed:.2f}s, expected <10s"
        assert len(vertices) == 65**3

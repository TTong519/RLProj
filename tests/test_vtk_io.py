"""Tests for surg_rl.utils.vtk_io pure-Python VTK I/O."""

from pathlib import Path

import numpy as np
import pytest

from surg_rl.utils.vtk_io import (
    read_vtk_unstructured_grid,
    validate_vtk,
    write_vtk_unstructured_grid,
)


class TestVtkIO:
    def test_vtk_roundtrip(self, tmp_path: Path) -> None:
        vertices = np.array(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.5, 1.0, 0.0],
                [0.5, 0.33, 1.0],
            ],
            dtype=float,
        )
        tetrahedra = np.array(
            [
                [0, 1, 2, 3],
            ],
            dtype=int,
        )
        path = tmp_path / "test.vtk"
        write_vtk_unstructured_grid(path, vertices, tetrahedra)
        v, t = read_vtk_unstructured_grid(path)
        assert np.allclose(v, vertices)
        assert np.array_equal(t, tetrahedra)

    def test_validate_vtk_passes(self, tmp_path: Path) -> None:
        vertices = np.array(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.5, 1.0, 0.0],
                [0.5, 0.33, 1.0],
            ],
            dtype=float,
        )
        tetrahedra = np.array([[0, 1, 2, 3]], dtype=int)
        path = tmp_path / "test.vtk"
        write_vtk_unstructured_grid(path, vertices, tetrahedra)
        validate_vtk(path)  # should not raise

    def test_invalid_cell_types_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.vtk"
        # Manually write a VTK with a triangle (type 5) mixed in
        content = """# vtk DataFile Version 2.0
Test
ASCII
DATASET UNSTRUCTURED_GRID
POINTS 4 float
0 0 0
1 0 0
0 1 0
0 0 1
CELLS 1 5
4 0 1 2 3
CELL_TYPES 1
5
"""
        path.write_text(content)
        with pytest.raises(ValueError, match="cell type"):
            read_vtk_unstructured_grid(path)

    def test_file_not_found_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            read_vtk_unstructured_grid("/nonexistent/file.vtk")

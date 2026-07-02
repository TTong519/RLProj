"""Tests for tetgen-based tetrahedral mesh generation."""

import numpy as np
import pytest

# tetgen is an optional `meshing` extra; skip the whole module when tetgen is
# absent so CI installs without the meshing extra stay green. See debug session
# ci-failures-lint-pybullet (C2).
pytest.importorskip("tetgen")


class TestTetGenCore:
    """TETG-01: tetgen produces valid (nodes, elems) from surface arrays."""

    def test_tetgen_generates_tetrahedral_mesh(self):
        import tetgen

        verts = np.array(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.5, 1.0, 0.0],
                [0.5, 0.33, 1.0],
            ],
            dtype=np.float64,
        )
        faces = np.array(
            [
                [0, 1, 2],
                [0, 1, 3],
                [0, 2, 3],
                [1, 2, 3],
            ],
            dtype=np.int32,
        )

        tgen = tetgen.TetGen(verts, faces)
        nodes, elems = tgen.tetrahedralize(order=1, quiet=True)[:2]

        assert nodes.ndim == 2
        assert nodes.shape[1] == 3
        assert nodes.dtype == np.float64
        assert nodes.shape[0] > 0
        assert elems.ndim == 2
        assert elems.shape[1] == 4
        assert elems.min() >= 0
        assert elems.max() < nodes.shape[0]

    def test_cube_tetrahedralization(self):
        import tetgen

        verts = np.array(
            [
                [-0.5, -0.5, -0.5],
                [-0.5, -0.5, 0.5],
                [-0.5, 0.5, -0.5],
                [-0.5, 0.5, 0.5],
                [0.5, -0.5, -0.5],
                [0.5, -0.5, 0.5],
                [0.5, 0.5, -0.5],
                [0.5, 0.5, 0.5],
            ],
            dtype=np.float64,
        )
        faces = np.int32(
            [
                [0, 1, 5],
                [0, 5, 4],
                [2, 3, 7],
                [2, 7, 6],
                [0, 2, 6],
                [0, 6, 4],
                [1, 3, 7],
                [1, 7, 5],
                [0, 1, 3],
                [0, 3, 2],
                [4, 5, 7],
                [4, 7, 6],
            ]
        )

        tgen = tetgen.TetGen(verts, faces)
        nodes, elems = tgen.tetrahedralize(order=1, quiet=True)[:2]
        assert nodes.shape[0] > 0
        assert elems.shape[0] > 0
        assert elems.min() >= 0


class TestObjToTetGen:
    """TETG-02: OBJ file -> tetrahedral mesh via tetgen."""

    @staticmethod
    def _write_triangulated_obj(tmp_path, verts, faces):
        path = str(tmp_path / "test.obj")
        lines = []
        for v in verts:
            lines.append(f"v {v[0]} {v[1]} {v[2]}")
        for f in faces:
            idxs = [int(i) + 1 for i in f]
            lines.append(f"f {idxs[0]} {idxs[1]} {idxs[2]}")
        with open(path, "w") as fh:
            fh.write("\n".join(lines) + "\n")
        return path

    def test_obj_to_tetrahedral_mesh(self, tmp_path):
        import tetgen

        verts = np.float64(
            [
                [-0.5, -0.5, -0.5],
                [-0.5, -0.5, 0.5],
                [-0.5, 0.5, -0.5],
                [-0.5, 0.5, 0.5],
                [0.5, -0.5, -0.5],
                [0.5, -0.5, 0.5],
                [0.5, 0.5, -0.5],
                [0.5, 0.5, 0.5],
            ]
        )
        faces = np.int32(
            [
                [0, 1, 5],
                [0, 5, 4],
                [2, 3, 7],
                [2, 7, 6],
                [0, 2, 6],
                [0, 6, 4],
                [1, 3, 7],
                [1, 7, 5],
                [0, 1, 3],
                [0, 3, 2],
                [4, 5, 7],
                [4, 7, 6],
            ]
        )

        obj_path = self._write_triangulated_obj(tmp_path, verts, faces)

        parsed_verts, parsed_faces = [], []
        with open(obj_path) as f:
            for line in f:
                parts = line.strip().split()
                if not parts or parts[0].startswith("#"):
                    continue
                if parts[0] == "v":
                    parsed_verts.append([float(p) for p in parts[1:4]])
                elif parts[0] == "f":
                    idxs = [int(p.split("/")[0]) - 1 for p in parts[1:]]
                    if len(idxs) == 3:
                        parsed_faces.append(idxs)
                    elif len(idxs) == 4:
                        parsed_faces.append([idxs[0], idxs[1], idxs[2]])
                        parsed_faces.append([idxs[0], idxs[2], idxs[3]])

        pv = np.array(parsed_verts, dtype=np.float64)
        pf = np.array(parsed_faces, dtype=np.int32)

        tgen = tetgen.TetGen(pv, pf)
        nodes, elems = tgen.tetrahedralize(order=1, quiet=True)[:2]
        assert nodes.shape[0] > 0
        assert elems.shape[0] > 0

    def test_quad_face_conversion(self, tmp_path):
        import tetgen

        path = str(tmp_path / "quad.obj")
        with open(path, "w") as f:
            f.write("v 0.0 0.0 0.0\n")
            f.write("v 1.0 0.0 0.0\n")
            f.write("v 1.0 1.0 0.0\n")
            f.write("v 0.0 1.0 0.0\n")
            f.write("v 0.5 0.5 1.0\n")
            f.write("f 1 2 3 4\n")
            f.write("f 1 2 5\n")
            f.write("f 2 3 5\n")
            f.write("f 3 4 5\n")
            f.write("f 4 1 5\n")

        parsed_verts, parsed_faces = [], []
        with open(path) as fh:
            for line in fh:
                parts = line.strip().split()
                if not parts:
                    continue
                if parts[0] == "v":
                    parsed_verts.append([float(p) for p in parts[1:4]])
                elif parts[0] == "f":
                    idxs = [int(p.split("/")[0]) - 1 for p in parts[1:]]
                    if len(idxs) == 3:
                        parsed_faces.append(idxs)
                    elif len(idxs) == 4:
                        parsed_faces.append([idxs[0], idxs[1], idxs[2]])
                        parsed_faces.append([idxs[0], idxs[2], idxs[3]])

        pv = np.array(parsed_verts, dtype=np.float64)
        pf = np.array(parsed_faces, dtype=np.int32)
        assert len(pf) == 6, f"Expected 6 faces (4 tri + 1 quad->2 tri), got {len(pf)}"

        tgen = tetgen.TetGen(pv, pf)
        nodes, elems = tgen.tetrahedralize(order=1, quiet=True)[:2]
        assert nodes.shape[0] > 0
        assert elems.shape[0] > 0


class TestNoPyVista:
    """TETG-03: Mesh generation works without PyVista installed."""

    def test_no_pyvista_import(self):
        import os
        import subprocess
        import sys

        code = """
import sys

class Blocker:
    def find_module(self, name, path=None):
        if name == 'pyvista' or name.startswith('pyvista.'):
            return self
        return None
    def load_module(self, name):
        raise ImportError("pyvista is blocked")

sys.meta_path.insert(0, Blocker())

from surg_rl.utils import mesh_generation
print("mesh_generation imported successfully (no pyvista)")
"""

        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": "src"},
        )
        assert result.returncode == 0, f"Import failed:\n{result.stderr}"
        assert "mesh_generation imported successfully" in result.stdout

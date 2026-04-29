"""Pure-Python VTK I/O for tetrahedral meshes (legacy ASCII unstructured grid)."""

from pathlib import Path
from typing import Tuple, Union

import numpy as np


def write_vtk_unstructured_grid(
    path: Union[str, Path], vertices: np.ndarray, tetrahedra: np.ndarray
) -> None:
    """Write a legacy ASCII VTK file containing an unstructured grid of tetrahedra.

    Args:
        path: Destination file path.
        vertices: Array of shape (N, 3) with float coordinates.
        tetrahedra: Array of shape (M, 4) with integer vertex indices.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    if vertices.shape[1] != 3:
        raise ValueError(f"vertices must have shape (N, 3), got {vertices.shape}")
    if tetrahedra.shape[1] != 4:
        raise ValueError(f"tetrahedra must have shape (M, 4), got {tetrahedra.shape}")

    n_points = vertices.shape[0]
    n_cells = tetrahedra.shape[0]
    total_ints = n_cells * 5

    lines = [
        "# vtk DataFile Version 2.0",
        "Surg-RL Tetrahedral Mesh",
        "ASCII",
        "DATASET UNSTRUCTURED_GRID",
        f"POINTS {n_points} float",
    ]
    for v in vertices:
        lines.append(f"{v[0]:.6g} {v[1]:.6g} {v[2]:.6g}")

    lines.append(f"CELLS {n_cells} {total_ints}")
    for cell in tetrahedra:
        lines.append(f"4 {int(cell[0])} {int(cell[1])} {int(cell[2])} {int(cell[3])}")

    lines.append(f"CELL_TYPES {n_cells}")
    for _ in range(n_cells):
        lines.append("10")

    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_vtk_unstructured_grid(path: Union[str, Path]) -> Tuple[np.ndarray, np.ndarray]:
    """Read a legacy ASCII VTK unstructured grid file and return vertices and tetrahedra.

    Args:
        path: Path to the VTK file.

    Returns:
        Tuple of (vertices, tetrahedra) as float/int arrays with shapes (N, 3) and (M, 4).

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is not a valid unstructured grid, cell types mismatch,
            or point/cell counts don't match.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"VTK file not found: {p}")

    content = p.read_text(encoding="utf-8")
    lines = content.strip().splitlines()

    # Basic header validation
    if not lines or not lines[0].startswith("# vtk DataFile Version"):
        raise ValueError("Not a valid legacy VTK file: missing header")

    # Find DATASET keyword
    dataset_idx = None
    for i, line in enumerate(lines):
        if line.strip().upper().startswith("DATASET"):
            dataset_idx = i
            break
    if dataset_idx is None:
        raise ValueError("Not a valid unstructured grid VTK file: missing DATASET keyword")
    if lines[dataset_idx].strip().upper() != "DATASET UNSTRUCTURED_GRID":
        raise ValueError("Only DATASET UNSTRUCTURED_GRID is supported")

    # Parse POINTS
    points_idx = None
    for i in range(dataset_idx + 1, len(lines)):
        if lines[i].strip().upper().startswith("POINTS"):
            points_idx = i
            break
    if points_idx is None:
        raise ValueError("Missing POINTS section")

    parts = lines[points_idx].strip().split()
    if len(parts) < 3:
        raise ValueError("Malformed POINTS line")
    try:
        n_points = int(parts[1])
    except ValueError as exc:
        raise ValueError(f"Invalid point count: {parts[1]}") from exc

    if points_idx + 1 + n_points > len(lines):
        raise ValueError("POINTS section truncated")
    vertex_lines = lines[points_idx + 1 : points_idx + 1 + n_points]
    vertices = np.fromstring(" ".join(vertex_lines), sep=" ").reshape(n_points, 3)

    # Parse CELLS
    cells_idx = None
    for i in range(points_idx + 1 + n_points, len(lines)):
        if lines[i].strip().upper().startswith("CELLS"):
            cells_idx = i
            break
    if cells_idx is None:
        raise ValueError("Missing CELLS section")

    cparts = lines[cells_idx].strip().split()
    if len(cparts) < 3:
        raise ValueError("Malformed CELLS line")
    try:
        n_cells = int(cparts[1])
        total_ints = int(cparts[2])
    except ValueError as exc:
        raise ValueError(f"Invalid CELLS counts: {cparts[1]} {cparts[2]}") from exc

    expected_ints = n_cells * 5
    if total_ints != expected_ints:
        raise ValueError(
            f"CELLS total_ints mismatch: {total_ints} (expected {expected_ints})"
        )

    if cells_idx + 1 + n_cells > len(lines):
        raise ValueError("CELLS section truncated")
    cell_lines = lines[cells_idx + 1 : cells_idx + 1 + n_cells]
    tetrahedra = np.empty((n_cells, 4), dtype=int)
    for idx, cl in enumerate(cell_lines):
        ints = cl.strip().split()
        if len(ints) != 5:
            raise ValueError(
                f"Cell {idx} has {len(ints)} entries (expected 5: count + 4 indices)"
            )
        if int(ints[0]) != 4:
            raise ValueError(f"Cell {idx} has count {ints[0]} (expected 4)")
        tetrahedra[idx] = [int(ints[1]), int(ints[2]), int(ints[3]), int(ints[4])]

    # Parse CELL_TYPES
    types_idx = None
    for i in range(cells_idx + 1 + n_cells, len(lines)):
        if lines[i].strip().upper().startswith("CELL_TYPES"):
            types_idx = i
            break
    if types_idx is None:
        raise ValueError("Missing CELL_TYPES section")

    tparts = lines[types_idx].strip().split()
    if len(tparts) < 2:
        raise ValueError("Malformed CELL_TYPES line")
    try:
        n_types = int(tparts[1])
    except ValueError as exc:
        raise ValueError(f"Invalid CELL_TYPES count: {tparts[1]}") from exc

    if n_types != n_cells:
        raise ValueError(
            f"CELL_TYPES count {n_types} does not match CELLS count {n_cells}"
        )

    if types_idx + 1 + n_types > len(lines):
        raise ValueError("CELL_TYPES section truncated")
    type_lines = lines[types_idx + 1 : types_idx + 1 + n_types]
    for idx, tl in enumerate(type_lines):
        val = int(tl.strip())
        if val != 10:
            raise ValueError(
                f"Unsupported cell type {val} at index {idx} (expected 10 for tetrahedron)"
            )

    return vertices.astype(float), tetrahedra


def validate_vtk(path: Union[str, Path]) -> None:
    """Read and validate a VTK unstructured grid file.

    Args:
        path: Path to the VTK file.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If validation fails.
    """
    read_vtk_unstructured_grid(path)

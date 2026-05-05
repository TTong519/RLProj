"""Procedural tetrahedral mesh generators with tetgen-backed tetrahedralization.

Produces (vertices, tetrahedra) tuples suitable for :func:`write_vtk_unstructured_grid`.
All generators output pure tetrahedra (VTK cell type 10) with no duplicate vertices.
"""

import logging

import numpy as np

logger = logging.getLogger(__name__)


def _try_external_tetrahedralization(vertices, faces):
    """Attempt tetrahedralization using tetgen (required dependency: tetgen>=0.8.4).

    Args:
        vertices: Array of shape (N, 3).
        faces: Array of shape (M, 3) with triangular face indices.

    Returns:
        (tet_verts_Nx3_float64, tet_cells_Mx4_int32) tuple or None if tetgen
        is unavailable or the surface is non-manifold.
    """
    if len(vertices) == 0 or len(faces) == 0:
        return None
    if vertices.shape[1] != 3:
        return None
    if faces.shape[1] != 3:
        return None
    if not np.isfinite(vertices).all():
        return None
    if faces.max() >= len(vertices) or faces.min() < 0:
        return None

    try:
        import tetgen  # type: ignore[import-untyped]
    except ImportError:
        return None

    try:
        tgen = tetgen.TetGen(
            vertices.astype(np.float64, copy=False),
            faces.astype(np.int32, copy=False),
        )
        nodes, elems = tgen.tetrahedralize(order=1, quiet=True)[:2]
        return nodes, elems
    except RuntimeError:
        return None


def _generate_box_surface(dims, resolution=8):
    """Generate a triangulated surface mesh of a box for external tetrahedralization.

    Returns:
        (vertices, faces) arrays with shapes (N, 3) and (M, 3).
    """
    dx, dy, dz = dims
    nx = ny = nz = max(1, resolution)

    x = np.linspace(-dx / 2, dx / 2, nx + 1)
    y = np.linspace(-dy / 2, dy / 2, ny + 1)
    z = np.linspace(-dz / 2, dz / 2, nz + 1)

    i, j, k = np.indices((nx + 1, ny + 1, nz + 1))
    vertices = np.stack([x[i], y[j], z[k]], axis=-1).reshape(-1, 3).astype(float)

    npx = nx + 1
    npy = ny + 1

    # Build surface faces: 6 faces × (nx*ny or nx*nz or ny*nz) quads → 2 triangles each
    faces = []

    def _add_quad(a, b, c, d):
        faces.append([a, b, c])
        faces.append([a, c, d])

    # z = -dz/2 face
    for j_idx in range(ny):
        for i_idx in range(nx):
            a = j_idx * npx + i_idx
            b = a + 1
            c = b + npx
            d = a + npx
            _add_quad(a, b, c, d)

    # z = dz/2 face
    base = nz * npx * npy
    for j_idx in range(ny):
        for i_idx in range(nx):
            a = base + j_idx * npx + i_idx
            b = a + 1
            c = b + npx
            d = a + npx
            _add_quad(a, d, c, b)

    # y = -dy/2 face
    for k_idx in range(nz):
        for i_idx in range(nx):
            a = k_idx * npx * npy + i_idx
            b = a + 1
            c = b + npx * npy
            d = a + npx * npy
            _add_quad(a, d, c, b)

    # y = dy/2 face
    for k_idx in range(nz):
        for i_idx in range(nx):
            a = k_idx * npx * npy + (npy - 1) * npx + i_idx
            b = a + 1
            c = b + npx * npy
            d = a + npx * npy
            _add_quad(a, b, c, d)

    # x = -dx/2 face
    for k_idx in range(nz):
        for j_idx in range(ny):
            a = k_idx * npx * npy + j_idx * npx
            b = a + npx
            c = b + npx * npy
            d = a + npx * npy
            _add_quad(a, d, c, b)

    # x = dx/2 face
    for k_idx in range(nz):
        for j_idx in range(ny):
            a = k_idx * npx * npy + j_idx * npx + (npx - 1)
            b = a + npx
            c = b + npx * npy
            d = a + npx * npy
            _add_quad(a, b, c, d)

    return vertices, np.array(faces, dtype=int)


def _dedup_vertices(vertices: np.ndarray, tol: float = 1e-6) -> tuple[np.ndarray, np.ndarray]:
    """Remove duplicate vertices (within *tol*) and return remap indices.

    Args:
        vertices: Array of shape (N, 3).
        tol: Squared distance tolerance for deduplication.

    Returns:
        (unique_vertices, remap) where remap is an int array of length N mapping
        old vertex indices to new unique indices.
    """
    if vertices.shape[0] == 0:
        return vertices, np.array([], dtype=int)

    # Round to a tolerance grid for hashing
    scaled = np.round(vertices / tol).astype(np.int64)
    # Lexicographic sort to bring duplicates together
    order = np.lexsort((scaled[:, 2], scaled[:, 1], scaled[:, 0]))
    sorted_scaled = scaled[order]

    remap = np.empty(len(vertices), dtype=int)
    unique = []
    remap[order[0]] = 0
    unique.append(vertices[order[0]])

    for idx in range(1, len(order)):
        if np.array_equal(sorted_scaled[idx], sorted_scaled[idx - 1]):
            remap[order[idx]] = remap[order[idx - 1]]
        else:
            remap[order[idx]] = len(unique)
            unique.append(vertices[order[idx]])

    return np.stack(unique), remap


def generate_box_tet_mesh(
    dims: tuple[float, float, float], resolution: int = 8
) -> tuple[np.ndarray, np.ndarray]:
    """Generate a tetrahedral mesh of a rectangular box.

    Uses a regular Cartesian grid + standard 5-decomposition per cube cell.

    Args:
        dims: Box dimensions (dx, dy, dz).
        resolution: Number of subdivisions along each axis.

    Returns:
        (vertices, tetrahedra) arrays with shapes (N, 3) and (M, 4).
    """
    dx, dy, dz = dims
    nx = ny = nz = max(1, resolution)
    n_tets_estimated = nx * ny * nz * 5
    if n_tets_estimated > 5000:
        vertices, faces = _generate_box_surface(dims, resolution)
        result = _try_external_tetrahedralization(vertices, faces)
        if result is not None:
            return result
        logger.warning(
            "External tetrahedralization failed for box %d³; falling back to slow generator",
            resolution,
        )

    # Regular grid from (-dx/2, -dy/2, -dz/2) to (dx/2, dy/2, dz/2)
    x = np.linspace(-dx / 2, dx / 2, nx + 1)
    y = np.linspace(-dy / 2, dy / 2, ny + 1)
    z = np.linspace(-dz / 2, dz / 2, nz + 1)

    # Vectorized vertex generation using np.indices + np.stack
    i, j, k = np.indices((nx + 1, ny + 1, nz + 1))
    vertices = np.stack([x[i], y[j], z[k]], axis=-1).reshape(-1, 3).astype(float)

    npx = nx + 1
    npy = ny + 1

    # Vectorized cell corner indices
    cell_i = np.arange(nx)
    cell_j = np.arange(ny)
    cell_k = np.arange(nz)
    ci, cj, ck = np.meshgrid(cell_i, cell_j, cell_k, indexing='ij')

    corners = np.stack([
        ck * npx * npy + cj * npx + ci,
        ck * npx * npy + cj * npx + (ci + 1),
        ck * npx * npy + (cj + 1) * npx + (ci + 1),
        ck * npx * npy + (cj + 1) * npx + ci,
        (ck + 1) * npx * npy + cj * npx + ci,
        (ck + 1) * npx * npy + cj * npx + (ci + 1),
        (ck + 1) * npx * npy + (cj + 1) * npx + (ci + 1),
        (ck + 1) * npx * npy + (cj + 1) * npx + ci,
    ], axis=-1)  # shape: (nx, ny, nz, 8)

    # 5-decomposition pattern per cube cell
    cube_tets = np.array(
        [
            [0, 1, 2, 5],
            [0, 2, 3, 7],
            [0, 5, 7, 4],
            [2, 5, 6, 7],
            [0, 2, 7, 5],
        ],
        dtype=int,
    )
    tets = corners[..., cube_tets]  # shape: (nx, ny, nz, 5, 4)
    tets = tets.reshape(-1, 4)

    return vertices, tets


def generate_sphere_tet_mesh(radius: float, subdivisions: int = 2) -> tuple[np.ndarray, np.ndarray]:
    """Generate a tetrahedral mesh of a sphere.

    Starts from an icosahedron, repeatedly subdivides each surface triangle,
    then connects each surface triangle to the centre point to form a
    tetrahedron.

    Args:
        radius: Sphere radius.
        subdivisions: Number of subdivision levels (>= 0).  Each level splits
            every triangle into 4.

    Returns:
        (vertices, tetrahedra) arrays with shapes (N, 3) and (M, 4).
    """
    phi = (1.0 + np.sqrt(5.0)) / 2.0  # golden ratio

    # Icosahedron vertices (12) — normals already point outward
    raw_vertices = np.array(
        [
            [-1.0, phi, 0.0],
            [1.0, phi, 0.0],
            [-1.0, -phi, 0.0],
            [1.0, -phi, 0.0],
            [0.0, -1.0, phi],
            [0.0, 1.0, phi],
            [0.0, -1.0, -phi],
            [0.0, 1.0, -phi],
            [phi, 0.0, -1.0],
            [phi, 0.0, 1.0],
            [-phi, 0.0, -1.0],
            [-phi, 0.0, 1.0],
        ],
        dtype=float,
    )
    raw_vertices /= np.linalg.norm(raw_vertices, axis=1, keepdims=True)
    raw_vertices *= radius

    # Icosahedron faces (20 triangles)
    faces = [
        [0, 11, 5],
        [0, 5, 1],
        [0, 1, 7],
        [0, 7, 10],
        [0, 10, 11],
        [1, 5, 9],
        [5, 11, 4],
        [11, 10, 2],
        [10, 7, 6],
        [7, 1, 8],
        [3, 9, 4],
        [3, 4, 2],
        [3, 2, 6],
        [3, 6, 8],
        [3, 8, 9],
        [4, 9, 5],
        [2, 4, 11],
        [6, 2, 10],
        [8, 6, 7],
        [9, 8, 1],
    ]

    # Subdivide faces
    for _ in range(subdivisions):
        new_faces = []
        for a, b, c in faces:
            ab = _normalized_midpoint(raw_vertices[a], raw_vertices[b]) * radius
            bc = _normalized_midpoint(raw_vertices[b], raw_vertices[c]) * radius
            ca = _normalized_midpoint(raw_vertices[c], raw_vertices[a]) * radius

            ia = len(raw_vertices)
            ib = ia + 1
            ic = ia + 2
            raw_vertices = np.vstack([raw_vertices, ab, bc, ca])

            new_faces.append([a, ia, ic])
            new_faces.append([ia, b, ib])
            new_faces.append([ic, ib, c])
            new_faces.append([ia, ib, ic])
        faces = new_faces

    # Add centre point
    center = np.array([[0.0, 0.0, 0.0]], dtype=float)
    vertices = np.vstack([raw_vertices, center])
    centre_idx = len(raw_vertices)

    tetrahedra = np.array([[centre_idx, a, b, c] for a, b, c in faces], dtype=int)

    # Deduplicate any coincident vertices introduced by floating-point noise
    vertices, remap = _dedup_vertices(vertices, tol=1e-6)
    tetrahedra = remap[tetrahedra]

    return vertices, tetrahedra


def _normalized_midpoint(v1: np.ndarray, v2: np.ndarray) -> np.ndarray:
    """Midpoint of two vectors, projected onto the unit sphere."""
    m = (v1 + v2) / 2.0
    norm = np.linalg.norm(m, axis=-1, keepdims=True)
    norm = np.where(norm == 0, 1.0, norm)
    return m / norm


def generate_cylinder_tet_mesh(
    radius: float,
    height: float,
    theta_segments: int = 16,
    height_segments: int = 4,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate a tetrahedral mesh of a right circular cylinder.

    Method:
    1. Slice the cylinder into *height_segments* layers.
    2. Each layer is split radially into *theta_segments* wedges.
    3. Each wedge is a triangular prism (bottom cap-triangle → top cap-triangle)
       decomposed into 3 tetrahedra.

    Args:
        radius: Cylinder radius.
        height: Total height.
        theta_segments: Number of angular slices.
        height_segments: Number of vertical layers.

    Returns:
        (vertices, tetrahedra) arrays with shapes (N, 3) and (M, 4).
    """
    n_theta = max(3, theta_segments)
    n_h = max(1, height_segments)

    zs = np.linspace(-height / 2, height / 2, n_h + 1)
    thetas = np.linspace(0.0, 2.0 * np.pi, n_theta, endpoint=False)

    # Vectorized level construction using np.stack
    levels = []
    for z in zs:
        level = np.concatenate([
            [[0.0, 0.0, z]],
            np.stack([
                radius * np.cos(thetas),
                radius * np.sin(thetas),
                np.full_like(thetas, z),
            ], axis=1),
        ], axis=0)
        levels.append(level)
    vertices = np.concatenate(levels, axis=0)

    verts_per_level = 1 + n_theta

    # Triangular prism → 3 tetrahedra per wedge × n_theta × n_h
    tets = []
    for lev in range(n_h):
        base_off = lev * verts_per_level
        top_off = (lev + 1) * verts_per_level
        for i in range(n_theta):
            i_next = (i + 1) % n_theta
            # Bottom triangle: centre_b, ring_b[i], ring_b[i_next]
            b0 = base_off
            b1 = base_off + 1 + i
            b2 = base_off + 1 + i_next
            # Top triangle: centre_t, ring_t[i], ring_t[i_next]
            t0 = top_off
            t1 = top_off + 1 + i
            t2 = top_off + 1 + i_next

            # Standard 3-tet decomposition of a triangular prism
            tets.append([b0, b1, b2, t0])
            tets.append([t0, b1, b2, t2])
            tets.append([t0, b1, t1, t2])

    return vertices, np.array(tets, dtype=int)

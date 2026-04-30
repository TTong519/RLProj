"""Pure-NumPy procedural tetrahedral mesh generators.

Produces (vertices, tetrahedra) tuples suitable for :func:`write_vtk_unstructured_grid`.
All generators output pure tetrahedra (VTK cell type 10) with no duplicate vertices.
"""

import numpy as np


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

    # Regular grid from (-dx/2, -dy/2, -dz/2) to (dx/2, dy/2, dz/2)
    x = np.linspace(-dx / 2, dx / 2, nx + 1)
    y = np.linspace(-dy / 2, dy / 2, ny + 1)
    z = np.linspace(-dz / 2, dz / 2, nz + 1)

    # Build vertex array: all grid points
    vertices = np.array([[xi, yi, zi] for zi in z for yi in y for xi in x], dtype=float)
    npx = nx + 1
    npy = ny + 1

    def _idx(i: int, j: int, k: int) -> int:
        return k * npx * npy + j * npx + i

    # 5-decomposition of a unit cube with corner indices:
    # 0=(i,j,k), 1=(i+1,j,k), 2=(i+1,j+1,k), 3=(i,j+1,k)
    # 4=(i,j,k+1), 5=(i+1,j,k+1), 6=(i+1,j+1,k+1), 7=(i,j+1,k+1)
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

    tets = []
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                base = np.array(
                    [
                        _idx(i, j, k),
                        _idx(i + 1, j, k),
                        _idx(i + 1, j + 1, k),
                        _idx(i, j + 1, k),
                        _idx(i, j, k + 1),
                        _idx(i + 1, j, k + 1),
                        _idx(i + 1, j + 1, k + 1),
                        _idx(i, j + 1, k + 1),
                    ],
                    dtype=int,
                )
                for ct in cube_tets:
                    tets.append(base[ct])

    return vertices, np.array(tets, dtype=int)


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
    norm = float(np.linalg.norm(m))
    if norm == 0:
        return m
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

    # Vertices: for each level, a centre + ring
    vert_list = []
    for z in zs:
        vert_list.append([0.0, 0.0, z])  # centre
        for t in thetas:
            vert_list.append([radius * np.cos(t), radius * np.sin(t), z])
    vertices = np.array(vert_list, dtype=float)

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

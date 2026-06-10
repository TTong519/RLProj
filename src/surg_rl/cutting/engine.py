"""Tetrahedral mesh cutting engine — subdivision, remeshing, boundary extraction."""

import numpy as np

from surg_rl.cutting.intersection import classify_tet_case, edge_intersection


def _subdivide_3_1(
    minority_v: int,
    majority_verts: list[int],
    intersection_pts: list[int],
    cut_faces_out: list[np.ndarray],
) -> list[np.ndarray]:
    """Case 1/3: 1 vertex on one side, 3 on other. Produces 4 child tets."""
    p1, p2, p3 = intersection_pts
    v1, v2, v3 = majority_verts
    cut_faces_out.append(np.array([p1, p2, p3], dtype=np.int32))
    return [
        np.array([minority_v, p1, p2, p3], dtype=np.int32),
        np.array([v1, v2, v3, p1], dtype=np.int32),
        np.array([v2, v3, p1, p2], dtype=np.int32),
        np.array([v3, p1, p2, p3], dtype=np.int32),
    ]


def _subdivide_2_2(
    pos_verts: list[int],
    neg_verts: list[int],
    intersection_pts: list[int],
    cut_faces_out: list[np.ndarray],
) -> list[np.ndarray]:
    """Case 2: 2 vertices on each side. Produces 6 child tets."""
    A, B = pos_verts
    C, D = neg_verts
    p_AC, p_BC, p_AD, p_BD = intersection_pts

    cut_faces_out.append(np.array([p_AC, p_BC, p_BD], dtype=np.int32))
    cut_faces_out.append(np.array([p_AC, p_BD, p_AD], dtype=np.int32))

    return [
        np.array([A, B, p_AC, p_BD], dtype=np.int32),
        np.array([A, p_AC, p_AD, p_BD], dtype=np.int32),
        np.array([p_AC, B, p_BC, p_BD], dtype=np.int32),
        np.array([C, D, p_AC, p_BD], dtype=np.int32),
        np.array([C, p_AC, p_AD, p_BD], dtype=np.int32),
        np.array([p_AC, D, p_BC, p_BD], dtype=np.int32),
    ]


def cut_tetrahedral_mesh(
    vertices: np.ndarray,
    tetrahedra: np.ndarray,
    cut_origin: np.ndarray,
    cut_normal: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Cut a tetrahedral mesh along a plane.

    Args:
        vertices: (N, 3) float64 vertex positions.
        tetrahedra: (M, 4) int32 element indices (0-indexed).
        cut_origin: (3,) point on the cut plane.
        cut_normal: (3,) unit normal defining cut direction.

    Returns:
        new_vertices: (N', 3)
        new_tetrahedra: (M', 4)
        cut_faces: (F, 3) faces along the cut surface
    """
    cut_normal = cut_normal / (np.linalg.norm(cut_normal) + 1e-30)

    from surg_rl.cutting.intersection import compute_signed_distances

    distances = compute_signed_distances(vertices, cut_origin, cut_normal)

    max_extent = np.max(np.linalg.norm(vertices.max(axis=0) - vertices.min(axis=0)))
    eps = 1e-12 * max(max_extent, 1e-6)

    tet_distances = distances[tetrahedra]
    tet_cases = np.array([classify_tet_case(d[0], d[1], d[2], d[3], eps) for d in tet_distances])

    straddle_mask = (tet_cases >= 1) & (tet_cases <= 3)
    keep_mask = ~straddle_mask
    keep_tets = tetrahedra[keep_mask]

    new_verts_accum: list[np.ndarray] = []
    new_tets_accum: list[np.ndarray] = []
    cut_faces_accum: list[np.ndarray] = []
    edge_to_vertex: dict[tuple[int, int], int] = {}
    cut_vertex_indices: set[int] = set()

    n_original = vertices.shape[0]

    def _get_or_create_intersection(vi: int, vj: int) -> int:
        key = (min(vi, vj), max(vi, vj))
        if key in edge_to_vertex:
            return edge_to_vertex[key]
        d_i = distances[vi]
        d_j = distances[vj]
        pt = edge_intersection(vertices[vi], vertices[vj], d_i, d_j)
        new_verts_accum.append(pt.reshape(1, 3))
        allocated_idx = n_original + len(new_verts_accum) - 1
        edge_to_vertex[key] = allocated_idx
        cut_vertex_indices.add(allocated_idx)
        return allocated_idx

    for tet_idx in np.where(straddle_mask)[0]:
        v_idx = [int(x) for x in tetrahedra[tet_idx]]
        v0, v1, v2, v3 = v_idx
        d0 = float(distances[v0])
        d1 = float(distances[v1])
        d2 = float(distances[v2])
        d3 = float(distances[v3])

        pos_mask = np.array([d0 > eps, d1 > eps, d2 > eps, d3 > eps])
        pos_count = pos_mask.sum()
        neg_mask = np.array([d0 < -eps, d1 < -eps, d2 < -eps, d3 < -eps])

        if pos_count == 1:
            minority_i = int(np.argmax(pos_mask))
            minority_v = v_idx[minority_i]
            majority_verts = [v_idx[i] for i in range(4) if not pos_mask[i]]
            ips = [_get_or_create_intersection(minority_v, mv) for mv in majority_verts]
            new_tets_accum.extend(_subdivide_3_1(minority_v, majority_verts, ips, cut_faces_accum))
        elif pos_count == 3:
            minority_i = int(np.argmax(neg_mask))
            minority_v = v_idx[minority_i]
            majority_verts = [v_idx[i] for i in range(4) if not neg_mask[i]]
            ips = [_get_or_create_intersection(minority_v, mv) for mv in majority_verts]
            new_tets_accum.extend(_subdivide_3_1(minority_v, majority_verts, ips, cut_faces_accum))
        elif pos_count == 2:
            pos_idx = [i for i in range(4) if pos_mask[i]]
            neg_idx = [i for i in range(4) if neg_mask[i]]
            pos_v = [v_idx[i] for i in pos_idx]
            neg_v = [v_idx[i] for i in neg_idx]
            ips = []
            for pv in pos_v:
                for nv in neg_v:
                    ips.append(_get_or_create_intersection(pv, nv))
            new_tets_accum.extend(_subdivide_2_2(pos_v, neg_v, ips, cut_faces_accum))

    # Build final arrays
    if new_verts_accum:
        new_vertices_all = np.vstack([vertices] + new_verts_accum)
    else:
        new_vertices_all = vertices.copy()

    if new_tets_accum:
        new_tets_all = (
            np.vstack([keep_tets] + new_tets_accum)
            if len(keep_tets) > 0
            else np.vstack(new_tets_accum)
        )
    else:
        new_tets_all = keep_tets.copy()

    if cut_faces_accum:
        cut_faces = np.vstack(cut_faces_accum)
    else:
        cut_faces = np.zeros((0, 3), dtype=np.int32)

    return new_vertices_all, new_tets_all, cut_faces

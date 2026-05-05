"""Signed distance computation, edge intersection, and tet-plane classification."""

import numpy as np


def compute_signed_distances(
    vertices: np.ndarray,
    plane_origin: np.ndarray,
    plane_normal: np.ndarray,
) -> np.ndarray:
    """Compute signed distance of each vertex from the plane.

    Positive = in direction of normal.
    """
    plane_normal = plane_normal / np.linalg.norm(plane_normal)
    return np.dot(vertices - plane_origin, plane_normal)


def edge_intersection(
    v_i: np.ndarray,
    v_j: np.ndarray,
    d_i: float,
    d_j: float,
) -> np.ndarray:
    """Find where edge (v_i, v_j) crosses the zero-distance plane.

    Uses t = |d_i| / (|d_i| + |d_j|) which is stable even when d_i ≈ d_j.
    """
    denom = abs(d_i) + abs(d_j)
    if denom < 1e-15:
        return 0.5 * (v_i + v_j)
    t = abs(d_i) / denom
    return v_i + t * (v_j - v_i)


def classify_tet_case(
    d0: float,
    d1: float,
    d2: float,
    d3: float,
    eps: float = 1e-12,
) -> int:
    """Classify a tetrahedron's intersection with a plane.

    Returns case number:
        0: All vertices on same side (no cut)
        1: 1 vertex on one side, 3 on other (3-1 split)
        2: 2 vertices on each side (2-2 split)
        3: Same as case 1 (3-1 split, just reversed signs)
        4: Degenerate (vertex on plane) — epsilon-snap needed

    Case 3 is returned as-is (not merged with 1) so callers can
    distinguish which side has the single vertex.
    """
    signs = [0, 0, 0, 0]
    dists = [d0, d1, d2, d3]
    for i, d in enumerate(dists):
        if d > eps:
            signs[i] = 1
        elif d < -eps:
            signs[i] = -1
        else:
            signs[i] = 0

    pos_count = signs.count(1)
    neg_count = signs.count(-1)
    zero_count = signs.count(0)

    if zero_count > 0:
        return 4

    if pos_count == 4 or neg_count == 4:
        return 0
    if pos_count == 1 and neg_count == 3:
        return 1
    if pos_count == 3 and neg_count == 1:
        return 3
    if pos_count == 2 and neg_count == 2:
        return 2

    return 0

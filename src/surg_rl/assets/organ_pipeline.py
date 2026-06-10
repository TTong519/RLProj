"""Organ OBJ → STL → tetgen pipeline with trimesh auto-repair.

Converts surgical organ OBJ surface meshes to tetrahedral meshes via the
existing tetgen infrastructure. Auto-repairs non-watertight or degenerate
geometry before tetrahedralization.
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Any

from surg_rl.assets import TRIMESH
from surg_rl.assets.mesh_generator import generate_procedural_organ
from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)

_ORGAN_WARNED: set[str] = set()


def load_and_repair_organ_surface(
    organ_type: str,
    mesh_path: str | None = None,
    target_face_count: int | None = None,
    assets_dir: str = "assets/meshes",
    repair: bool = True,
) -> Any:
    """Load organ OBJ, auto-repair, return watertight trimesh surface.

    Repair steps (when repair=True):
    1. Fill holes (trimesh.repair.fill_holes)
    2. Remove degenerate faces (trimesh.repair.remove_degenerate_faces)
    3. Merge close vertices (trimesh.merge_close_vertices)
    4. Fix normals (trimesh.fix_normals)

    Returns a trimesh.Trimesh ready for STL export.
    """
    TRIMESH
    import trimesh

    if mesh_path:
        resolved = Path(mesh_path)
        if not resolved.is_absolute():
            resolved = Path(assets_dir) / resolved
        if resolved.exists():
            try:
                mesh = trimesh.load(str(resolved), force="mesh")
                if not isinstance(mesh, trimesh.Trimesh):
                    mesh = trimesh.Trimesh()
                logger.info(f"Loaded organ mesh: {resolved}")
            except Exception as e:
                logger.warning(f"Failed to load {resolved}: {e}. Falling back.")
                mesh = generate_procedural_organ(organ_type, target_face_count)
        else:
            if mesh_path not in _ORGAN_WARNED:
                _ORGAN_WARNED.add(mesh_path)
                logger.warning(
                    f"Organ mesh not found: {resolved}. "
                    f"Falling back to procedural {organ_type} shape."
                )
            mesh = generate_procedural_organ(organ_type, target_face_count)
    else:
        mesh = generate_procedural_organ(organ_type, target_face_count)

    if repair:
        try:
            if mesh.is_watertight:
                logger.info(f"Organ mesh is watertight: {len(mesh.faces)} faces")
            else:
                logger.info("Repairing non-watertight organ mesh...")
                mesh = mesh.fill_holes()
                mesh = mesh.remove_degenerate_faces()
                mesh.merge_close_vertices()
                mesh.fix_normals()
                logger.info(
                    f"Repair complete: watertight={mesh.is_watertight}, " f"{len(mesh.faces)} faces"
                )
        except Exception as e:
            logger.warning(f"Auto-repair failed: {e}. Proceeding with raw mesh.")

    if target_face_count and len(mesh.faces) > target_face_count:
        mesh = mesh.simplify_quadratic_decimation(target_face_count)
        logger.info(f"Decimated organ to {len(mesh.faces)} faces")

    return mesh


def organ_to_tetgen(
    organ_type: str,
    mesh_path: str | None = None,
    target_face_count: int | None = None,
    work_dir: str | None = None,
    tetgen_bin: str = "tetgen",
    tetgen_quality: str = "pq1.2a0.01",
) -> Path:
    """Convert organ OBJ to tetrahedral mesh via tetgen.

    Pipeline: OBJ → trimesh repair → STL export → tetgen → .node/.ele

    Args:
        organ_type: e.g. "liver", "kidney", "stomach", "gallbladder"
        mesh_path: path to OBJ file (None = procedural fallback)
        target_face_count: decimation target for surface mesh
        work_dir: working directory for STL + tetgen output (temp if None)
        tetgen_bin: path or name of tetgen binary
        tetgen_quality: tetgen quality flags (default "pq1.2a0.01")

    Returns:
        Path prefix for tetgen output files (work_dir/tetgen_output)
    """
    TRIMESH

    if work_dir is None:
        work_dir = tempfile.mkdtemp(prefix="surg_rl_organ_")

    out = Path(work_dir)
    out.mkdir(parents=True, exist_ok=True)

    surface = load_and_repair_organ_surface(
        organ_type=organ_type,
        mesh_path=mesh_path,
        target_face_count=target_face_count,
        repair=True,
    )

    stl_path = out / "tetgen_output.stl"
    surface.export(str(stl_path))
    logger.info(f"Exported STL: {stl_path} ({stl_path.stat().st_size} bytes)")

    output_prefix = out / "tetgen_output"
    cmd = [
        tetgen_bin,
        "-" + tetgen_quality,
        str(stl_path),
    ]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(out),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            logger.warning(
                f"tetgen command failed (exit {result.returncode}): " f"{result.stderr[:500]}"
            )
        else:
            logger.info(f"tetgen completed: {output_prefix}.1.node + .1.ele generated")
    except FileNotFoundError:
        logger.warning(
            f"tetgen binary '{tetgen_bin}' not found. " f"Install tetgen or ensure it is on PATH."
        )
    except subprocess.TimeoutExpired:
        logger.warning("tetgen timed out after 60s")

    return output_prefix


__all__ = [
    "load_and_repair_organ_surface",
    "organ_to_tetgen",
]

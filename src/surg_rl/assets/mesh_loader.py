"""OBJ mesh loading, V-HACD collision decomposition, and URDF generation.

All functions use the TRIMESH lazy import guard — no ImportError at module
load time when trimesh is not installed.
"""

import tempfile
from pathlib import Path
from typing import Any

from surg_rl.assets import TRIMESH
from surg_rl.assets.mesh_generator import (
    generate_procedural_instrument,
    generate_procedural_organ,
)
from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)

URDF_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "forceps": [
        {"name": "shaft", "type": "cylinder", "radius": 0.004, "length": 0.15},
        {"name": "jaw_left", "type": "capsule", "radius": 0.003, "length": 0.04},
        {"name": "jaw_right", "type": "capsule", "radius": 0.003, "length": 0.04},
    ],
    "scalpel": [
        {"name": "body", "type": "box", "size": [0.005, 0.015, 0.18]},
    ],
    "needle_driver": [
        {"name": "shaft", "type": "cylinder", "radius": 0.004, "length": 0.14},
        {"name": "jaw", "type": "box", "size": [0.006, 0.015, 0.03]},
    ],
    "scissors": [
        {"name": "blade_a", "type": "box", "size": [0.004, 0.012, 0.07]},
        {"name": "blade_b", "type": "box", "size": [0.004, 0.012, 0.07]},
    ],
    "clamp": [
        {"name": "shaft", "type": "cylinder", "radius": 0.005, "length": 0.13},
        {"name": "jaw", "type": "box", "size": [0.008, 0.02, 0.025]},
    ],
    "suction": [
        {"name": "body", "type": "cylinder", "radius": 0.006, "length": 0.15},
    ],
    "cautery": [
        {"name": "body", "type": "cylinder", "radius": 0.004, "length": 0.16},
    ],
    "camera": [
        {"name": "body", "type": "cylinder", "radius": 0.005, "length": 0.16},
    ],
    "retractor": [
        {"name": "body", "type": "box", "size": [0.015, 0.003, 0.12]},
    ],
}


def _resolve_mesh_path(mesh_path: str, assets_dir: str = "assets/meshes") -> Path:
    """Resolve a mesh path relative to the assets directory."""
    p = Path(mesh_path)
    if p.is_absolute():
        return p
    return Path(assets_dir) / p


_WARNED_MESHES: set[str] = set()


def load_instrument_mesh(
    instrument_type: str,
    mesh_path: str | None = None,
    target_face_count: int | None = None,
    assets_dir: str = "assets/meshes",
) -> Any:
    """Load an instrument OBJ mesh, falling back to procedural shape if missing.

    Returns a trimesh.Trimesh object.
    Emits a single WARNING per missing mesh (deduplicated across the session).
    """
    TRIMESH
    import trimesh

    if mesh_path:
        resolved = _resolve_mesh_path(mesh_path, assets_dir)
        if resolved.exists():
            mesh = trimesh.load(str(resolved), force="mesh")
            if not isinstance(mesh, trimesh.Trimesh):
                mesh = mesh if hasattr(mesh, "vertices") else trimesh.Trimesh()
            logger.info(f"Loaded mesh: {resolved}")
            return mesh
        elif mesh_path not in _WARNED_MESHES:
            _WARNED_MESHES.add(mesh_path)
            logger.warning(
                f"Mesh file not found: {resolved}. "
                f"Falling back to procedural shape for {instrument_type}. "
                f"Run 'surg-rl assets download' to fetch real meshes."
            )

    return generate_procedural_instrument(instrument_type, target_face_count)


def decimate_and_decompose(
    mesh: Any,
    target_face_count: int | None = None,
) -> tuple[Any, list[Any]]:
    """Decimate visual mesh and decompose collision geometry via V-HACD.

    Returns:
        (visual_mesh, [collision_mesh, ...])
    """
    TRIMESH
    import trimesh

    visual = mesh.copy()
    if target_face_count and len(visual.faces) > target_face_count:
        visual = visual.simplify_quadratic_decimation(target_face_count)
        logger.info(
            f"Decimated mesh from {len(mesh.faces)} to {len(visual.faces)} faces"
        )

    try:
        from trimesh.interfaces.vhacd import convex_decomposition

        collision_parts = convex_decomposition(mesh)
        logger.info(f"V-HACD: decomposed into {len(collision_parts)} convex parts")
        return visual, collision_parts
    except Exception:
        logger.warning(
            "V-HACD decomposition failed — falling back to convex hull"
        )
        hull = mesh.convex_hull
        return visual, [hull]


def generate_urdf(
    instrument_type: str,
    visual_mesh: Any,
    collision_meshes: list[Any],
    name: str = "instrument",
    output_dir: str | None = None,
) -> Path:
    """Generate a URDF file for the instrument with visual + collision meshes.

    Writes OBJ files for visual and collision meshes, then generates a URDF
    referencing them. Multi-link instruments get articulated joints per the
    URDF_TEMPLATES definition.

    Returns the path to the generated URDF file.
    """
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="surg_rl_urdf_")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    template = URDF_TEMPLATES.get(instrument_type, [{"name": "body", "type": "mesh"}])
    is_multi_link = len(template) > 1

    # Export meshes as OBJ
    visual_path = out / f"{name}_visual.obj"
    visual_mesh.export(str(visual_path))

    collision_paths: list[Path] = []
    for i, cm in enumerate(collision_meshes):
        cp = out / f"{name}_collision_{i}.obj"
        cm.export(str(cp))
        collision_paths.append(cp)

    # Build URDF XML
    urdf_xml = f"""<?xml version="1.0"?>
<robot name="{name}">
"""

    for i, link_def in enumerate(template):
        link_name = f"{name}_{link_def['name']}"
        vis_ref = str(visual_path.relative_to(out)) if i == 0 else ""
        col_ref = (
            str(collision_paths[0].relative_to(out))
            if collision_paths else ""
        )
        urdf_xml += f"""  <link name="{link_name}">
    <visual>
      <geometry>
        <mesh filename="{vis_ref}" scale="1 1 1"/>
      </geometry>
    </visual>
    <collision>
      <geometry>
        <mesh filename="{col_ref}" scale="1 1 1"/>
      </geometry>
    </collision>
  </link>
"""

    # Add joints for multi-link instruments
    if is_multi_link:
        for i in range(len(template) - 1):
            parent = f"{name}_{template[i]['name']}"
            child = f"{name}_{template[i+1]['name']}"
            joint_type = "revolute" if instrument_type in ("forceps", "scissors") else "fixed"
            urdf_xml += f"""  <joint name="{name}_joint_{i}" type="{joint_type}">
    <parent link="{parent}"/>
    <child link="{child}"/>
    <origin xyz="0 0 -0.05" rpy="0 0 0"/>
  </joint>
"""

    urdf_xml += "</robot>\n"

    urdf_path = out / f"{name}.urdf"
    urdf_path.write_text(urdf_xml)
    logger.info(f"Generated URDF: {urdf_path}")
    return urdf_path


def load_and_generate_urdf(
    instrument_type: str,
    mesh_path: str | None = None,
    target_face_count: int | None = None,
    name: str = "instrument",
) -> Path:
    """End-to-end: load mesh, decimate/decompose, generate URDF.

    Returns the path to the generated URDF file.
    """
    mesh = load_instrument_mesh(
        instrument_type=instrument_type,
        mesh_path=mesh_path,
        target_face_count=target_face_count,
    )
    visual, collision = decimate_and_decompose(mesh, target_face_count)
    return generate_urdf(instrument_type, visual, collision, name)


__all__ = [
    "URDF_TEMPLATES",
    "decimate_and_decompose",
    "generate_urdf",
    "load_and_generate_urdf",
    "load_instrument_mesh",
]

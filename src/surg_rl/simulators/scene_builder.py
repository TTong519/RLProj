"""Scene builder for creating simulator objects from scene definitions.

This module provides functionality to convert scene definitions into
simulator-specific formats (MJCF for MuJoCo, URDF for PyBullet) with
automatic fallback to primitive shapes for missing assets.
"""

import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import numpy as np

from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)

try:
    from surg_rl.assets.mesh_loader import load_and_generate_urdf  # noqa: F401
except ImportError:
    load_and_generate_urdf = None  # type: ignore[assignment]


class AssetMissingError(Exception):
    """Exception raised when a required asset file is missing."""

    def __init__(self, asset_path: str, asset_type: str):
        self.asset_path = asset_path
        self.asset_type = asset_type
        super().__init__(
            f"Missing {asset_type} asset: {asset_path}. " f"Primitive fallback will be used."
        )


def _parse_tetgen_node(node_path: Path) -> "np.ndarray":
    """Parse tetgen .node file into (N,3) float64 vertex array.

    .node format:
        <#vertices> <dim> <#attributes> <boundary_markers_flag>
        <index> <x> <y> <z> [attributes] [boundary marker]
    """
    with open(node_path) as f:
        lines = f.readlines()
    header = lines[0].strip().split()
    n_verts = int(header[0])
    verts = np.zeros((n_verts, 3), dtype=np.float64)
    for i, line in enumerate(lines[1 : 1 + n_verts]):
        parts = line.strip().split()
        if not parts or parts[0].startswith("#"):
            continue
        verts[i, 0] = float(parts[1])
        verts[i, 1] = float(parts[2])
        verts[i, 2] = float(parts[3])
    return verts


def _parse_tetgen_ele(ele_path: Path) -> "np.ndarray":
    """Parse tetgen .ele file into (M,4) int32 0-indexed element array.

    .ele format:
        <#tetrahedra> <nodes_per_tet> <region_attribute_flag>
        <index> <v1> <v2> <v3> <v4> [region attribute]

    tetgen uses 1-indexed vertex IDs -> converts to 0-indexed.
    """
    with open(ele_path) as f:
        lines = f.readlines()
    header = lines[0].strip().split()
    n_tets = int(header[0])
    elems = np.zeros((n_tets, 4), dtype=np.int32)
    for i, line in enumerate(lines[1 : 1 + n_tets]):
        parts = line.strip().split()
        if not parts or parts[0].startswith("#"):
            continue
        elems[i, 0] = int(parts[1]) - 1
        elems[i, 1] = int(parts[2]) - 1
        elems[i, 2] = int(parts[3]) - 1
        elems[i, 3] = int(parts[4]) - 1
    return elems


class SceneBuilder:
    """Build simulator scenes from SceneDefinition objects.

    Currently supports MJCF generation for MuJoCo.
    PyBullet scenes use the same SceneDefinition but are loaded
    via the PyBulletSimulator's direct primitive builder.

    Attributes:
        assets_dir: Base directory for asset files.
        use_primitive_fallback: Whether to use primitives for missing assets.
        primitive_meshes: Cache of generated primitive mesh files.
    """

    # Default colors for different entity types
    DEFAULT_COLORS = {
        "robot": (0.3, 0.3, 0.8, 1.0),  # Blue
        "tissue_skin": (0.95, 0.85, 0.8, 1.0),  # Skin tone
        "tissue_muscle": (0.8, 0.3, 0.3, 1.0),  # Red
        "tissue_organ": (0.85, 0.65, 0.55, 1.0),  # Organ color
        "tissue_vessel": (0.7, 0.2, 0.2, 1.0),  # Dark red
        "instrument_scalpel": (0.7, 0.7, 0.7, 1.0),  # Silver
        "instrument_forceps": (0.5, 0.5, 0.5, 1.0),  # Gray
        "ground": (0.3, 0.3, 0.3, 1.0),  # Dark gray
    }

    def __init__(
        self,
        assets_dir: str | Path | None = None,
        use_primitive_fallback: bool = True,
    ):
        """Initialize the scene builder.

        Args:
            assets_dir: Base directory for asset files.
            use_primitive_fallback: Whether to use primitives for missing assets.
        """
        self.assets_dir = Path(assets_dir) if assets_dir else None
        self.use_primitive_fallback = use_primitive_fallback
        self._temp_dir_obj = tempfile.TemporaryDirectory(prefix="surg_rl_")
        self.temp_dir = Path(self._temp_dir_obj.name)
        self._primitive_meshes: dict[str, Path] = {}
        self._vtk_meshes: dict[str, Path] = {}
        self._missing_assets: set[str] = set()

    def _get_cached_vtk_path(self, cache_key: str, generator_fn, *args, **kwargs) -> Path:
        """Get a cached .vtk path or generate it via *generator_fn*."""
        if cache_key in self._vtk_meshes:
            return self._vtk_meshes[cache_key]
        mesh_path = self.temp_dir / f"{cache_key}.vtk"
        verts, tets = generator_fn(*args, **kwargs)
        from surg_rl.utils.vtk_io import write_vtk_unstructured_grid

        write_vtk_unstructured_grid(mesh_path, verts, tets)
        self._vtk_meshes[cache_key] = mesh_path
        return mesh_path

    def resolve_asset_path(self, asset_path: str) -> Path | None:
        """Resolve an asset path to an absolute path.

        Args:
            asset_path: Path to the asset file.

        Returns:
            Resolved path if file exists, None otherwise.
        """
        path = Path(asset_path)

        # Try absolute path
        if path.is_absolute() and path.exists():
            return path

        # Try relative to assets_dir
        if self.assets_dir:
            full_path = self.assets_dir / path
            if full_path.exists():
                return full_path

        # Try relative to current directory
        if path.exists():
            return path.resolve()

        return None

    def _log_missing_asset(self, asset_path: str, entity_name: str) -> None:
        """Log a single warning for a missing asset. Duplicate warnings are suppressed."""
        if asset_path in self._missing_assets:
            return
        self._missing_assets.add(asset_path)
        logger.warning(
            f"Asset missing for '{entity_name}': {asset_path}. " f"Using primitive fallback."
        )

    def _load_instrument_geometry(self, instrument_config) -> str:
        """Load instrument mesh and generate URDF, returning the path."""
        if load_and_generate_urdf is None:
            logger.warning(
                "trimesh not installed — using primitive fallback for instrument "
                f"'{instrument_config.name}'. Install with: pip install surg-rl[assets]"
            )
            return ""
        try:
            mesh_path = None
            target_faces = None
            if instrument_config.mesh is not None:
                mesh_path = instrument_config.mesh.path
                target_faces = instrument_config.mesh.target_face_count
            urdf_path = load_and_generate_urdf(
                instrument_type=instrument_config.type.value,
                mesh_path=mesh_path,
                target_face_count=target_faces,
                name=instrument_config.name,
            )
            return str(urdf_path)
        except ImportError:
            logger.warning(
                "trimesh not installed — using primitive fallback for instrument "
                f"'{instrument_config.name}'. Install with: pip install surg-rl[assets]"
            )
            return ""

    def _get_primitive_color(
        self,
        entity_type: str,
        subtype: str | None = None,
    ) -> tuple[float, float, float, float]:
        """Get default color for a primitive based on entity type.

        Args:
            entity_type: Type of entity ('robot', 'tissue', 'instrument').
            subtype: Subtype (e.g., 'skin', 'muscle' for tissue).

        Returns:
            RGBA tuple (0-1 range).
        """
        if entity_type == "tissue" and subtype:
            key = f"tissue_{subtype}"
            if key in self.DEFAULT_COLORS:
                return self.DEFAULT_COLORS[key]

        if entity_type == "instrument" and subtype:
            key = f"instrument_{subtype}"
            if key in self.DEFAULT_COLORS:
                return self.DEFAULT_COLORS[key]

        return self.DEFAULT_COLORS.get(entity_type, (0.5, 0.5, 0.5, 1.0))

    def _create_box_mesh(
        self,
        dimensions: tuple[float, float, float],
        name: str,
        output_dir: Path | None = None,
    ) -> Path:
        """Create an OBJ file for a box primitive.

        Args:
            dimensions: Box dimensions (x, y, z).
            name: Name for the mesh.
            output_dir: Output directory (uses temp_dir if None).

        Returns:
            Path to created mesh file.
        """
        output_dir = output_dir or self.temp_dir
        mesh_path = output_dir / f"{name}_box.obj"

        # Check cache
        cache_key = f"box_{dimensions}_{name}"
        if cache_key in self._primitive_meshes:
            return self._primitive_meshes[cache_key]

        hx, hy, hz = dimensions[0] / 2, dimensions[1] / 2, dimensions[2] / 2

        # Create OBJ content (all faces triangulated for soft-body loaders)
        obj_content = f"""# Box mesh generated by Surg-RL
# {name}
o {name}

# Vertices
v {-hx} {-hy} {-hz}
v {hx} {-hy} {-hz}
v {hx} {hy} {-hz}
v {-hx} {hy} {-hz}
v {-hx} {-hy} {hz}
v {hx} {-hy} {hz}
v {hx} {hy} {hz}
v {-hx} {hy} {hz}

# Faces
f 1 2 3
f 1 3 4
f 5 8 7
f 5 7 6
f 1 5 6
f 1 6 2
f 2 6 7
f 2 7 3
f 3 7 8
f 3 8 4
f 5 1 4
f 5 4 8
"""

        mesh_path.write_text(obj_content)
        self._primitive_meshes[cache_key] = mesh_path
        return mesh_path

    def _create_cylinder_mesh(
        self,
        radius: float,
        height: float,
        name: str,
        segments: int = 16,
        output_dir: Path | None = None,
    ) -> Path:
        """Create an OBJ file for a cylinder primitive.

        Args:
            radius: Cylinder radius.
            height: Cylinder height.
            name: Name for the mesh.
            segments: Number of segments around the circumference.
            output_dir: Output directory (uses temp_dir if None).

        Returns:
            Path to created mesh file.
        """
        import math

        output_dir = output_dir or self.temp_dir
        mesh_path = output_dir / f"{name}_cylinder.obj"

        cache_key = f"cylinder_{radius}_{height}_{name}"
        if cache_key in self._primitive_meshes:
            return self._primitive_meshes[cache_key]

        lines = [f"# Cylinder mesh generated by Surg-RL\n# {name}\no {name}\n"]

        h = height / 2

        # Generate vertices
        # Bottom center
        lines.append(f"v 0 0 {-h}")
        # Top center
        lines.append(f"v 0 0 {h}")

        # Bottom ring
        for i in range(segments):
            angle = 2 * math.pi * i / segments
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            lines.append(f"v {x} {y} {-h}")

        # Top ring
        for i in range(segments):
            angle = 2 * math.pi * i / segments
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            lines.append(f"v {x} {y} {h}")

        # Faces (1-indexed in OBJ)
        # Bottom cap
        lines.append("s off")
        for i in range(segments):
            next_i = (i + 1) % segments + 3
            curr_i = i + 3
            lines.append(f"f 1 {curr_i} {next_i}")

        # Top cap
        for i in range(segments):
            next_i = (i + 1) % segments + segments + 3
            curr_i = i + segments + 3
            lines.append(f"f 2 {next_i} {curr_i}")

        # Side faces (triangulated)
        for i in range(segments):
            next_i = (i + 1) % segments
            b1 = i + 3
            b2 = next_i + 3
            t1 = i + segments + 3
            t2 = next_i + segments + 3
            lines.append(f"f {b1} {b2} {t2}")
            lines.append(f"f {b1} {t2} {t1}")

        mesh_path.write_text("\n".join(lines))
        self._primitive_meshes[cache_key] = mesh_path
        return mesh_path

    def _create_sphere_mesh(
        self,
        radius: float,
        name: str,
        segments: int = 16,
        rings: int = 8,
        output_dir: Path | None = None,
    ) -> Path:
        """Create an OBJ file for a sphere primitive.

        Args:
            radius: Sphere radius.
            name: Name for the mesh.
            segments: Number of segments around the circumference.
            rings: Number of rings from pole to pole.
            output_dir: Output directory (uses temp_dir if None).

        Returns:
            Path to created mesh file.
        """
        import math

        output_dir = output_dir or self.temp_dir
        mesh_path = output_dir / f"{name}_sphere.obj"

        cache_key = f"sphere_{radius}_{name}"
        if cache_key in self._primitive_meshes:
            return self._primitive_meshes[cache_key]

        lines = [f"# Sphere mesh generated by Surg-RL\n# {name}\no {name}\n"]

        # Generate vertices
        for ring in range(rings + 1):
            phi = math.pi * ring / rings
            for seg in range(segments):
                theta = 2 * math.pi * seg / segments
                x = radius * math.sin(phi) * math.cos(theta)
                y = radius * math.sin(phi) * math.sin(theta)
                z = radius * math.cos(phi)
                lines.append(f"v {x} {y} {z}")

        # Generate faces (triangulated)
        lines.append("s off")
        for ring in range(rings):
            for seg in range(segments):
                next_seg = (seg + 1) % segments
                # Current ring vertices (1-indexed)
                v1 = ring * segments + seg + 1
                v2 = ring * segments + next_seg + 1
                # Next ring vertices
                v3 = (ring + 1) * segments + seg + 1
                v4 = (ring + 1) * segments + next_seg + 1
                lines.append(f"f {v1} {v2} {v4}")
                lines.append(f"f {v1} {v4} {v3}")

        mesh_path.write_text("\n".join(lines))
        self._primitive_meshes[cache_key] = mesh_path
        return mesh_path

    def get_mesh_or_primitive(
        self,
        mesh_path: str | None,
        primitive: str | None,
        dimensions: tuple[float, float, float],
        name: str,
        radius: float | None = None,
    ) -> tuple[Path, bool]:
        """Get mesh file or create primitive fallback.

        Args:
            mesh_path: Path to mesh file (may be None).
            primitive: Primitive type ('box', 'sphere', 'cylinder').
            dimensions: Dimensions for primitive (x, y, z) or radius.
            name: Name for generated primitive.
            radius: Radius for sphere/cylinder (optional, uses dimensions).

        Returns:
            Tuple of (mesh_path, is_primitive).
        """
        # Try to load existing mesh
        if mesh_path:
            resolved = self.resolve_asset_path(mesh_path)
            if resolved:
                logger.debug(f"Using mesh asset: {resolved}")
                return resolved, False
            elif not self.use_primitive_fallback:
                raise AssetMissingError(mesh_path, "mesh")
            else:
                self._log_missing_asset(mesh_path, name)

        # Create primitive
        if not self.use_primitive_fallback:
            raise AssetMissingError(mesh_path or "unknown", "mesh")

        if primitive == "sphere":
            r = radius or min(dimensions) / 2
            mesh_file = self._create_sphere_mesh(r, name)
        elif primitive == "cylinder":
            r = radius or min(dimensions[0], dimensions[1]) / 2
            h = dimensions[2]
            mesh_file = self._create_cylinder_mesh(r, h, name)
        else:  # Default to box
            mesh_file = self._create_box_mesh(dimensions, name)

        logger.info(f"Created primitive mesh: {mesh_file}")
        return mesh_file, True

    def load_urdf_asset(self, urdf_path: str, entity_name: str) -> Path | None:
        """Resolve a URDF asset path. Returns resolved Path if found, None if missing.

        On missing: logs single warning (deduplicated) and returns None.
        Caller decides fallback (primitive builder or raise).
        """
        resolved = self.resolve_asset_path(urdf_path)
        if resolved:
            return resolved
        self._log_missing_asset(urdf_path, entity_name)
        if not self.use_primitive_fallback:
            raise AssetMissingError(urdf_path, "urdf")
        return None

    def create_mjcf(
        self,
        scene_definition: Any,
        output_path: str | Path | None = None,
    ) -> Path:
        """Create MuJoCo MJCF (XML) file from scene definition.

        Args:
            scene_definition: SceneDefinition object.
            output_path: Output file path (uses temp_dir if None).

        Returns:
            Path to created MJCF file.
        """
        output_path = Path(output_path) if output_path else self.temp_dir / "scene.xml"

        # Create MJCF structure
        mujoco = ET.Element("mujoco", model=scene_definition.metadata.name)

        # Add compiler options
        compiler = ET.SubElement(mujoco, "compiler")
        compiler.set("angle", "radian")
        compiler.set("meshdir", str(self.assets_dir or "."))
        compiler.set("autolimits", "true")

        # Add simulation options. Forward the stability-relevant PhysicsConfig
        # fields to the MJCF <option> element so MuJoCo doesn't fall back to
        # its Euler + Newton defaults (which are far less stable when stiff
        # contacts and high-gain actuators interact).
        option = ET.SubElement(mujoco, "option")
        option.set("timestep", str(scene_definition.physics.timestep))
        option.set("gravity", " ".join(map(str, scene_definition.physics.gravity)))
        option.set("integrator", str(scene_definition.physics.integrator))
        # MuJoCo's <option> attribute is "iterations" (not "solver_iterations").
        option.set("iterations", str(scene_definition.physics.solver_iterations))

        # Add default settings
        default = ET.SubElement(mujoco, "default")
        ET.SubElement(default, "geom", contype="1", conaffinity="1")

        # Add assets (meshes)
        asset = ET.SubElement(mujoco, "asset")

        # Add textures and materials
        ET.SubElement(
            asset,
            "texture",
            name="groundplane",
            type="2d",
            builtin="checker",
            width="512",
            height="512",
        )
        ET.SubElement(asset, "material", name="groundplane", texture="groundplane", texrepeat="5 5")

        # Add worldbody before entities so that robot/tissue/instrument
        # helpers can append children to it.
        worldbody = ET.SubElement(mujoco, "worldbody")

        # Add robots
        for i, robot in enumerate(scene_definition.robots):
            self._add_robot_to_mjcf(mujoco, robot, i, asset)

        # Add tissues
        for i, tissue in enumerate(scene_definition.tissues):
            self._add_tissue_to_mjcf(mujoco, tissue, i, asset)

        # Add instruments
        for i, instrument in enumerate(scene_definition.instruments):
            self._add_instrument_to_mjcf(mujoco, instrument, i, asset)

        # Add ground plane if enabled
        ground_enabled = False
        if hasattr(scene_definition, "environment") and scene_definition.environment is not None:
            env = scene_definition.environment
            if hasattr(env, "ground_plane") and env.ground_plane is not None:
                ground_enabled = getattr(env.ground_plane, "enabled", False)
        if ground_enabled:
            self._add_ground_plane_to_mjcf(worldbody, scene_definition)

        env = getattr(scene_definition, "environment", None)
        if env is not None:
            # Add cameras
            for camera in getattr(env, "cameras", None) or []:
                self._add_camera_to_mjcf(worldbody, camera)

            # Add lights
            for light in getattr(env, "lights", None) or []:
                self._add_light_to_mjcf(worldbody, light)

        # Write to file
        tree = ET.ElementTree(mujoco)
        ET.indent(tree, space="  ")
        tree.write(output_path, encoding="unicode")

        logger.info(f"Created MJCF file: {output_path}")
        return output_path

    def _add_robot_to_mjcf(
        self,
        mujoco: ET.Element,
        robot: Any,
        index: int,
        asset: ET.Element,
    ) -> None:
        """Add robot to MJCF structure.

        The primitive fallback builds a kinematic chain of nested bodies, one
        body per joint, anchored to the world by a fixed root body. This
        structure is well-conditioned for the MuJoCo solver — putting
        multiple hinges on a single body (especially on the same axis) leaves
        the system rank-deficient and produces QACC NaN on the first step
        regardless of the integrator or control mode. The chain structure
        avoids that by giving each joint its own body so its motion is
        independent of the others.
        """

        # Get robot mesh or create primitive
        if robot.urdf_path:
            resolved = self.resolve_asset_path(robot.urdf_path)
            if resolved:
                # TODO: full URDF-in-MuJoCo support requires conversion or direct loading.
                return
            else:
                self._log_missing_asset(robot.urdf_path, robot.name)

        # Create body for robot
        worldbody = mujoco.find("worldbody")
        if worldbody is None:
            return

        body = ET.SubElement(worldbody, "body", name=robot.name)
        pos = f"{robot.base_pose.position.x} {robot.base_pose.position.y} {robot.base_pose.position.z}"
        quat = f"{robot.base_pose.orientation.w} {robot.base_pose.orientation.x} {robot.base_pose.orientation.y} {robot.base_pose.orientation.z}"
        body.set("pos", pos)
        body.set("quat", quat)

        # Root body: anchored to the world, no joints, holds a base inertial so
        # MuJoCo's mjMINVAL check passes. The base mass (1 kg) is large enough
        # to feel "fixed" to the world for the child chain dynamics.
        ET.SubElement(
            body,
            "inertial",
            pos="0 0 0",
            mass="1.0",
            diaginertia="1e-2 1e-2 1e-2",
        )
        # Small base geom for visual reference (primitive fallback only).
        ET.SubElement(body, "geom", name=f"{robot.name}_base", type="box", size="0.06 0.06 0.06")

        # Build the list of joints to emit. If the config defines joints use those,
        # otherwise fall back to a single default 1-DOF revolute joint for MVP.
        has_gripper = bool(robot.end_effectors)
        if robot.joints:
            joint_specs: list[tuple[str, str, str, str, str]] = [
                (
                    j.name,
                    "hinge" if j.type.value == "revolute" else "slide",
                    f"{j.limits.lower} {j.limits.upper}",
                    str(j.damping),
                    "0 1 0",
                )
                for j in robot.joints
            ]
        else:
            joint_specs = [
                (
                    f"{robot.name}_joint",
                    "hinge",
                    "-1.57 1.57",
                    "0.1",
                    "0 1 0",
                )
            ]

        # Build a kinematic chain: root body → link_1 body → link_2 body → ...
        # → gripper body. Each non-root body hosts exactly one joint, so the
        # system is rank-independent of the joint count. Bodies nested as
        # zero-offset children preserve the qpos order declared in joint_specs.
        #
        # We vary the joint axis per index to avoid multiple hinges on parallel
        # axes (which would still be rank-deficient even with one body per
        # joint, because nested zero-offset children with same-axis hinges are
        # kinematically equivalent to a single hinge at the same point).
        axis_cycle = ["0 0 1", "0 1 0", "1 0 0", "0 1 0", "0 0 1", "1 0 0"]
        current_parent: ET.Element = body
        for j_idx, (jname, jtype, jrange, jdamping, _ignored_axis) in enumerate(joint_specs):
            # Each link body is a child of the previous one (or the root for
            # the first link). We give it a small inertial so MuJoCo's mjMINVAL
            # check passes; the mass and inertia are large enough (50 g,
            # 1e-4 kg·m²) to be numerically well-behaved under proportional or
            # torque control.
            link_body = ET.SubElement(
                current_parent,
                "body",
                name=f"{robot.name}_link{j_idx + 1}",
            )
            link_body.set("pos", "0 0 0")
            link_body.set("quat", "1 0 0 0")
            ET.SubElement(
                link_body,
                "inertial",
                pos="0 0 0",
                mass="0.05",
                diaginertia="1e-4 1e-4 1e-4",
            )
            # Cycle the joint axis so adjacent hinges aren't parallel.
            jaxis = axis_cycle[j_idx % len(axis_cycle)]
            ET.SubElement(
                link_body,
                "joint",
                name=jname,
                type=jtype,
                axis=jaxis,
                range=jrange,
                damping=jdamping,
            )
            # Add a tiny visual geom on each link so the chain is visible
            # during rendering. (Primitive fallback only.)
            ET.SubElement(
                link_body,
                "geom",
                name=f"{robot.name}_link{j_idx + 1}_geom",
                type="box",
                size="0.04 0.04 0.08",
            )
            current_parent = link_body

        # Gripper goes on the last (deepest) link body.
        if has_gripper:
            ET.SubElement(
                current_parent,
                "joint",
                name=f"{robot.name}_gripper",
                type="slide",
                axis="0 0 1",
                range="0 0.05",
                damping="0.1",
            )

        # Add actuators. The actuator type depends on ``robot.control_mode``:
        #
        # - "position"  → <position kp=100 ctrlrange=...>: action is a joint
        #                 position setpoint in radians (matches the env's
        #                 JOINT_POSITIONS_SPEC action space of (-π, π)).
        # - "velocity"  → <velocity kv=10 ctrlrange=...>: action is a joint
        #                 velocity setpoint in rad/s (matches
        #                 JOINT_VELOCITIES_SPEC action space of (-2, 2)).
        # - "torque" / "effort" → <motor gear=100>: action is a generalized
        #                 force (caller is responsible for scaling).
        #
        # Previously the builder always emitted <motor gear=100>, which made
        # the env's (-π, π) action → force = 100·π ≈ 314 N·m on a small body
        # → angular acc of 1e5+ rad/s² → QACC NaN on the very first step.
        # (See debug session ppo-demo-mujoco-dof-limit.)
        actuator = mujoco.find("actuator")
        if actuator is None:
            actuator = ET.SubElement(mujoco, "actuator")

        control_mode = getattr(robot, "control_mode", "position") or "position"

        if robot.joints:
            for joint in robot.joints:
                lo, hi = joint.limits.lower, joint.limits.upper
                if control_mode == "position":
                    # kp=10 gives a peak torque of ~30 N·m at the action-space
                    # limit (target=π, kp=10, torque=π·10≈31 N·m), which is
                    # well within the per-joint effort bound (50-100 N·m in
                    # the scene JSON) and stable for a 50g primitive link.
                    # (Previously kp=100 → 314 N·m peak → QACC NaN.)
                    ET.SubElement(
                        actuator,
                        "position",
                        name=f"{joint.name}_motor",
                        joint=joint.name,
                        kp="10",
                        ctrlrange=f"{lo} {hi}",
                    )
                elif control_mode == "velocity":
                    vmax = max(0.1, joint.limits.velocity)
                    # kv=5 gives a peak torque of ~10 N·m at the action-space
                    # limit (target=2 rad/s, kv=5, torque=2·5=10 N·m).
                    ET.SubElement(
                        actuator,
                        "velocity",
                        name=f"{joint.name}_motor",
                        joint=joint.name,
                        kv="5",
                        ctrlrange=f"{-vmax} {vmax}",
                    )
                else:  # "torque" or "effort" or unknown → motor
                    if control_mode not in ("torque", "effort"):
                        logger.warning(
                            "Unknown robot.control_mode=%r for %s; falling back to <motor gear=100>",
                            control_mode,
                            robot.name,
                        )
                    ET.SubElement(
                        actuator,
                        "motor",
                        name=f"{joint.name}_motor",
                        joint=joint.name,
                        gear="100",
                    )
        else:
            # Default single joint (no explicit joints list). Use a wide
            # ctrlrange since we don't have limits.
            if control_mode == "position":
                ET.SubElement(
                    actuator,
                    "position",
                    name=f"{robot.name}_motor",
                    joint=f"{robot.name}_joint",
                    kp="10",
                    ctrlrange="-3.14 3.14",
                )
            elif control_mode == "velocity":
                ET.SubElement(
                    actuator,
                    "velocity",
                    name=f"{robot.name}_motor",
                    joint=f"{robot.name}_joint",
                    kv="5",
                    ctrlrange="-2 2",
                )
            else:
                ET.SubElement(
                    actuator,
                    "motor",
                    name=f"{robot.name}_motor",
                    joint=f"{robot.name}_joint",
                    gear="100",
                )

        if robot.end_effectors:
            # Gripper is a position actuator with the same reduced kp. The
            # gripper ctrlrange is small (0..0.05 m) so the peak force stays
            # around 0.5 N·m — appropriate for a 1 mg instrument.
            ET.SubElement(
                actuator,
                "position",
                name=f"{robot.name}_gripper",
                joint=f"{robot.name}_gripper",
                kp="10",
            )

    def _add_flex_body_to_mjcf(
        self,
        mujoco: ET.Element,
        tissue: Any,
        node_path: Path | None = None,
        ele_path: Path | None = None,
        vertices: "np.ndarray | None" = None,
        elements: "np.ndarray | None" = None,
    ) -> bool:
        """Add a low-level <flex> FEM body to MJCF from tetgen mesh.

        Supports both in-memory numpy arrays and on-disk .node/.ele files.
        In-memory arrays take precedence.

        Args:
            mujoco: Root <mujoco> element.
            tissue: TissueConfig with soft_body=True and DeformableConfig.
            node_path: Path to tetgen .node file (vertices).
            ele_path: Path to tetgen .ele file (elements).
            vertices: (N,3) float64 numpy array of vertex positions.
            elements: (M,4) int32 numpy array of 0-indexed tetrahedral elements.

        Returns:
            True if the flex body was added, False if not.
        """
        dc = tissue.deformable

        if vertices is not None and elements is not None:
            pass  # in-memory arrays provided, skip file I/O
        elif node_path is None and dc.mesh_path is not None:
            node_path = Path(str(dc.mesh_path) + ".1.node")
            if ele_path is None:
                ele_path = Path(str(dc.mesh_path) + ".1.ele")
        elif node_path is None or ele_path is None:
            return False

        if vertices is None or elements is None:
            if node_path is None or ele_path is None:
                return False
            if not node_path.exists() or not ele_path.exists():
                self._log_missing_asset(str(node_path), tissue.name)
                return False
            vertices = _parse_tetgen_node(node_path)
            elements = _parse_tetgen_ele(ele_path)

        assert vertices is not None and elements is not None

        deformable = mujoco.find("deformable")
        if deformable is None:
            deformable = ET.SubElement(mujoco, "deformable")

        mc = dc.mujoco
        physics = tissue.physics

        flex = ET.SubElement(
            deformable,
            "flex",
            name=f"{tissue.name}_flex",
            dim="3",
            radius="0.0",
            flatskin="false" if mc.smooth_normals else "true",
            body="world",
        )

        friction_val = mc.friction
        solref = mc.solref or "0.01 1"
        solimp = mc.solimp or "0.95 0.99 0.0001"
        margin_val = mc.margin
        ET.SubElement(
            flex,
            "contact",
            condim=str(mc.condim),
            solref=solref,
            solimp=solimp,
            friction=f"{friction_val} 0.005 0.0001",
            selfcollide="none",
            margin=str(margin_val),
        )

        # edge element only for dim=1 (cables), use elasticity for 3D flex
        young = mc.youngs_modulus or physics.youngs_modulus
        poisson = mc.poissons_ratio or physics.poissons_ratio
        fem_damping = mc.fem_damping or (physics.damping * 0.1)
        ET.SubElement(
            flex, "elasticity", young=str(young), poisson=str(poisson), damping=str(fem_damping)
        )

        vert_str = "\n".join(f"{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}" for v in vertices)
        ET.SubElement(flex, "vertex").text = vert_str

        elem_str = "\n".join(f"{int(e[0])} {int(e[1])} {int(e[2])} {int(e[3])}" for e in elements)
        ET.SubElement(flex, "element").text = elem_str

        if dc.boundary_conditions:
            equality = mujoco.find("equality")
            if equality is None:
                equality = ET.SubElement(mujoco, "equality")
            for bc in dc.boundary_conditions:
                if bc.type == "pin":
                    ET.SubElement(
                        equality,
                        "weld",
                        name=f"pin_{bc.name}",
                        body1=f"{tissue.name}_flex",
                        body2=bc.anchor_body,
                        solref="0.01 1",
                    )

        flex_name = f"{tissue.name}_flex"
        if not hasattr(self, "_flex_body_names"):
            self._flex_body_names: list[str] = []
        if flex_name not in self._flex_body_names:
            self._flex_body_names.append(flex_name)

        return True

    def _add_tissue_to_mjcf(
        self,
        mujoco: ET.Element,
        tissue: Any,
        index: int,
        asset: ET.Element,
    ) -> None:
        """Add tissue to MJCF structure."""
        worldbody = mujoco.find("worldbody")
        if worldbody is None:
            return

        body = ET.SubElement(worldbody, "body", name=tissue.name)
        pos = f"{tissue.pose.position.x} {tissue.pose.position.y} {tissue.pose.position.z}"
        body.set("pos", pos)

        if getattr(tissue, "soft_body", False):
            deformable = getattr(tissue, "deformable", None)
            if deformable is not None and deformable.mesh_source == "tetgen":
                from surg_rl.utils.mesh_generation import (
                    _generate_box_surface,
                    _try_external_tetrahedralization,
                )

                dims = getattr(tissue.geometry, "dimensions", (0.1, 0.1, 0.01))
                surf_verts, surf_faces = _generate_box_surface(tuple(dims))
                result = _try_external_tetrahedralization(surf_verts, surf_faces)
                if result is not None:
                    verts, tets = result
                    self._add_flex_body_to_mjcf(mujoco, tissue, vertices=verts, elements=tets)
                else:
                    self._add_flex_body_to_mjcf(mujoco, tissue)
                return
            elif deformable is not None and deformable.mesh_source == "file":
                self._add_flex_body_to_mjcf(mujoco, tissue)
                return
            # flexcomp_grid or None -> existing flexcomp path (backward compat)

            # Soft body tissue using MuJoCo flexcomp (grid-based deformable object)
            dims = tissue.geometry.dimensions or (0.1, 0.1, 0.01)
            # flexcomp generates a 3D grid of vertices
            flexcomp = ET.SubElement(
                body,
                "flexcomp",
                name=f"{tissue.name}_flex",
                type="grid",
                dim="3",
                count="5 5 2",
                spacing=f"{dims[0]/4} {dims[1]/4} {dims[2]/2}",
                pos="0 0 0",
            )
            # Add material properties for the soft body
            flexcomp.set("radius", "0.002")
            flexcomp.set("mass", str(tissue.physics.density * dims[0] * dims[1] * dims[2] / 50))
            # Contact properties
            ET.SubElement(
                flexcomp,
                "contact",
                selfcollide="pair" if tissue.physics.self_collision else "none",
                solref="0.01 1",
            )
            # Edge stiffness (Young's modulus proxy) - only for dim=1, use elasticity for 3D
            # ET.SubElement(
            #     flexcomp,
            #     "edge",
            #     stiffness=str(tissue.physics.youngs_modulus),
            #     damping=str(tissue.physics.damping),
            # )
            # Bending stiffness (if supported by the simulator) - commented out due to plugin compatibility
            # if tissue.physics.bending_stiffness > 0:
            #     ET.SubElement(
            #         flexcomp,
            #         "plugin",
            #         plugin="mujoco.elasticity.cable",
            #     )
        else:
            # Rigid body tissue — prefer real mesh if available, fall back to primitive
            mesh_asset = getattr(tissue.geometry, "mesh", None)
            if mesh_asset and getattr(mesh_asset, "path", None):
                resolved = self.resolve_asset_path(mesh_asset.path)
                if resolved and resolved.exists():
                    mesh_name = f"{tissue.name}_mesh"
                    ET.SubElement(asset, "mesh", name=mesh_name, file=str(resolved))
                    ET.SubElement(
                        body, "geom", name=f"{tissue.name}_geom", type="mesh", mesh=mesh_name
                    )
                else:
                    self._log_missing_asset(mesh_asset.path, tissue.name)
                    # Fall through to primitive fallback below
                    mesh_asset = None
            if not mesh_asset or not getattr(mesh_asset, "path", None):
                geom_type = tissue.geometry.primitive or "box"
                if geom_type == "box":
                    dims = tissue.geometry.dimensions or (0.1, 0.1, 0.01)
                    size = f"{dims[0]/2} {dims[1]/2} {dims[2]/2}"
                    ET.SubElement(body, "geom", name=f"{tissue.name}_geom", type="box", size=size)
                elif geom_type == "sphere":
                    r = tissue.geometry.radius or 0.05
                    ET.SubElement(
                        body, "geom", name=f"{tissue.name}_geom", type="sphere", size=str(r)
                    )
                elif geom_type == "cylinder":
                    dims = tissue.geometry.dimensions or (0.05, 0.1)
                    r = dims[0] / 2 if len(dims) > 0 else 0.025
                    h = dims[1] / 2 if len(dims) > 1 else 0.05
                    ET.SubElement(
                        body, "geom", name=f"{tissue.name}_geom", type="cylinder", size=f"{r} {h}"
                    )
                else:
                    dims = tissue.geometry.dimensions or (0.1, 0.1, 0.01)
                    size = f"{dims[0]/2} {dims[1]/2} {dims[2]/2}"
                    ET.SubElement(body, "geom", name=f"{tissue.name}_geom", type="box", size=size)

            # Add physics properties
            if tissue.physics and tissue.physics.stiffness:
                pass  # MuJoCo soft bodies require more complex setup

    def _add_instrument_to_mjcf(
        self,
        mujoco: ET.Element,
        instrument: Any,
        index: int,
        asset: ET.Element,
    ) -> None:
        """Add instrument to MJCF structure.

        Attempts to load real mesh via trimesh → URDF path first,
        falling back to primitive box if trimesh is unavailable
        or mesh files are missing.
        """
        worldbody = mujoco.find("worldbody")
        if worldbody is None:
            return

        body = ET.SubElement(worldbody, "body", name=instrument.name)
        if instrument.pose is not None:
            pos = f"{instrument.pose.position.x} {instrument.pose.position.y} {instrument.pose.position.z}"
        else:
            pos = "0 0 0"
        body.set("pos", pos)

        # Try loading via trimesh mesh_loader first (produces URDF with V-HACD)
        mesh_asset = getattr(instrument, "mesh", None)
        if mesh_asset is not None:
            urdf_path = self._load_instrument_geometry(instrument)
            if urdf_path:
                include_elem = ET.SubElement(body, "include", file=urdf_path)
                return

        # Fallback to direct OBJ mesh reference (existing code path)
        if mesh_asset and getattr(mesh_asset, "path", None):
            resolved = self.resolve_asset_path(mesh_asset.path)
            if resolved and resolved.exists():
                mesh_name = f"{instrument.name}_mesh"
                ET.SubElement(asset, "mesh", name=mesh_name, file=str(resolved))
                ET.SubElement(
                    body, "geom", name=f"{instrument.name}_geom", type="mesh", mesh=mesh_name
                )
                return
            else:
                self._log_missing_asset(mesh_asset.path, instrument.name)

        # Ultimate fallback: primitive box
        ET.SubElement(
            body, "geom", name=f"{instrument.name}_geom", type="box", size="0.01 0.01 0.05"
        )

        # Note: Instrument is static for now (no control implemented yet)
        # To make it dynamic, add: <freejoint name="instrument_root"/>

    def _add_ground_plane_to_mjcf(
        self,
        worldbody: ET.Element,
        scene_definition: Any,
    ) -> None:
        """Add ground plane to MJCF."""
        ground = scene_definition.environment.ground_plane
        if not ground or not ground.enabled:
            return

        size = ground.size or (2.0, 2.0)
        ET.SubElement(
            worldbody,
            "geom",
            name="ground",
            type="plane",
            size=f"{size[0]} {size[1]} 0.1",
            material="groundplane",
        )

    def _add_camera_to_mjcf(
        self,
        worldbody: ET.Element,
        camera: Any,
    ) -> None:
        """Add camera to MJCF."""
        cam = ET.SubElement(worldbody, "camera", name=camera.name)
        pos = f"{camera.pose.position.x} {camera.pose.position.y} {camera.pose.position.z}"
        quat = f"{camera.pose.orientation.w} {camera.pose.orientation.x} {camera.pose.orientation.y} {camera.pose.orientation.z}"
        cam.set("pos", pos)
        cam.set("quat", quat)
        if camera.fov:
            cam.set("fovy", str(camera.fov / 2))  # MuJoCo uses half-fov

    def _add_light_to_mjcf(
        self,
        worldbody: ET.Element,
        light: Any,
    ) -> None:
        """Add light to MJCF."""
        from surg_rl.scene_definition import LightType

        light_elem = ET.SubElement(worldbody, "light", name=light.name)
        light_elem.set("diffuse", " ".join(map(str, [light.intensity] * 3)))

        if light.type == LightType.DIRECTIONAL:
            if light.direction:
                light_elem.set("dir", " ".join(map(str, light.direction)))
            light_elem.set("pos", "0 0 3")
        elif light.type == LightType.POINT:
            if light.position:
                pos = f"{light.position.x} {light.position.y} {light.position.z}"
                light_elem.set("pos", pos)

    @staticmethod
    def _inject_ros2_control_tags(urdf_xml: str, joint_names: list[str]) -> str:
        """Inject ``<ros2_control>`` XML into a URDF string.

        Adds position and velocity state interfaces plus position command
        interface for each joint, referencing the standard
        ``mock_components/GenericSystem`` hardware plugin.

        Args:
            urdf_xml: Raw URDF XML as a string.
            joint_names: Joint names to annotate.

        Returns:
            Modified URDF XML string with ros2_control tags appended.
        """
        root = ET.fromstring(urdf_xml)
        rc = ET.SubElement(root, "ros2_control", name="RobotSystem", type="system")
        hw = ET.SubElement(rc, "hardware")
        ET.SubElement(hw, "plugin").text = "mock_components/GenericSystem"
        ET.SubElement(hw, "param", name="joint_names").text = " ".join(joint_names)
        for name in joint_names:
            joint = ET.SubElement(rc, "joint", name=name)
            ET.SubElement(joint, "command_interface", name="position")
            ET.SubElement(joint, "state_interface", name="position")
            ET.SubElement(joint, "state_interface", name="velocity")
        return ET.tostring(root, encoding="unicode")

    def create_urdf(
        self,
        scene_definition: Any,
        output_path: str | Path | None = None,
        inject_ros2_control: bool = False,
    ) -> Path:
        """Create a URDF file from a scene definition.

        Generates a minimal URDF with robot links/joints and optionally
        injects ``<ros2_control>`` tags for hardware interface integration.

        Args:
            scene_definition: SceneDefinition object.
            output_path: Output file path (uses temp_dir if None).
            inject_ros2_control: Whether to add ros2_control XML tags.

        Returns:
            Path to created URDF file.
        """
        output_path = Path(output_path) if output_path else self.temp_dir / "scene.urdf"

        robot = ET.Element("robot", name=scene_definition.metadata.name)

        for joint_name in self._collect_joint_names(scene_definition):
            ET.SubElement(robot, "joint", name=joint_name, type="revolute")

        urdf_xml = ET.tostring(robot, encoding="unicode")

        if inject_ros2_control and self._collect_joint_names(scene_definition):
            urdf_xml = self._inject_ros2_control_tags(
                urdf_xml, self._collect_joint_names(scene_definition)
            )

        output_path.write_text(urdf_xml)
        logger.info("Created URDF file: %s (ros2_control=%s)", output_path, inject_ros2_control)
        return output_path

    def _collect_joint_names(self, scene_definition: Any) -> list[str]:
        """Collect all joint names from robots in the scene definition."""
        names: list[str] = []
        for robot in getattr(scene_definition, "robots", []) or []:
            for joint in getattr(robot, "joints", []) or []:
                names.append(joint.name)
        return names

    def cleanup(self) -> None:
        """Clean up temporary files."""
        if hasattr(self, "_temp_dir_obj") and self._temp_dir_obj is not None:
            self._temp_dir_obj.cleanup()
            self._temp_dir_obj = None
        self._primitive_meshes.clear()
        self._vtk_meshes.clear()

    def __del__(self):
        """Destructor to clean up temp files."""
        self.cleanup()

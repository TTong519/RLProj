"""Scene builder for creating simulator objects from scene definitions.

This module provides functionality to convert scene definitions into
simulator-specific formats (MJCF for MuJoCo, URDF for PyBullet) with
automatic fallback to primitive shapes for missing assets.
"""

import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)


class AssetMissingError(Exception):
    """Exception raised when a required asset file is missing."""

    def __init__(self, asset_path: str, asset_type: str):
        self.asset_path = asset_path
        self.asset_type = asset_type
        super().__init__(
            f"Missing {asset_type} asset: {asset_path}. " f"Primitive fallback will be used."
        )


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
                logger.warning(f"Mesh file not found: {mesh_path}. Using primitive fallback.")

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

        # Add simulation options
        option = ET.SubElement(mujoco, "option")
        option.set("timestep", str(scene_definition.physics.timestep))
        option.set("gravity", " ".join(map(str, scene_definition.physics.gravity)))

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
        """Add robot to MJCF structure."""

        # Get robot mesh or create primitive
        if robot.urdf_path:
            resolved = self.resolve_asset_path(robot.urdf_path)
            if resolved:
                # TODO: full URDF-in-MuJoCo support requires conversion or direct loading.
                return
            else:
                logger.warning(f"Robot URDF not found: {robot.urdf_path}. Using primitive.")

        # Create body for robot
        worldbody = mujoco.find("worldbody")
        if worldbody is None:
            return

        body = ET.SubElement(worldbody, "body", name=robot.name)
        pos = f"{robot.base_pose.position.x} {robot.base_pose.position.y} {robot.base_pose.position.z}"
        quat = f"{robot.base_pose.orientation.w} {robot.base_pose.orientation.x} {robot.base_pose.orientation.y} {robot.base_pose.orientation.z}"
        body.set("pos", pos)
        body.set("quat", quat)

        # Add simple geometry for now (box as placeholder)
        ET.SubElement(body, "geom", name=f"{robot.name}_body", type="box", size="0.05 0.05 0.1")

        # Add joints
        if robot.joints:
            for joint in robot.joints:
                joint_type = "hinge" if joint.type.value == "revolute" else "slide"
                ET.SubElement(
                    body,
                    "joint",
                    name=joint.name,
                    type=joint_type,
                    axis="0 1 0",
                    range=f"{joint.limits.lower} {joint.limits.upper}",
                    damping=str(joint.damping),
                )
        else:
            # Default 1-DOF revolute joint for MVP
            ET.SubElement(
                body,
                "joint",
                name=f"{robot.name}_joint",
                type="hinge",
                axis="0 1 0",
                range="-1.57 1.57",
                damping="0.1",
            )

        # Add actuators
        actuator = mujoco.find("actuator")
        if actuator is None:
            actuator = ET.SubElement(mujoco, "actuator")

        if robot.joints:
            for joint in robot.joints:
                ET.SubElement(
                    actuator,
                    "motor",
                    name=f"{joint.name}_motor",
                    joint=joint.name,
                    gear="100",
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
            ET.SubElement(
                body,
                "joint",
                name=f"{robot.name}_gripper",
                type="slide",
                axis="0 0 1",
                range="0 0.05",
                damping="0.1",
            )
            ET.SubElement(
                actuator,
                "position",
                name=f"{robot.name}_gripper",
                joint=f"{robot.name}_gripper",
                kp="100",
            )

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
                selfcollide="true" if tissue.physics.self_collision else "false",
                solref="0.01 1",
            )
            # Edge stiffness (Young's modulus proxy)
            ET.SubElement(
                flexcomp,
                "edge",
                stiffness=str(tissue.physics.youngs_modulus),
                damping=str(tissue.physics.damping),
            )
            # Bending stiffness (if supported by the simulator)
            if tissue.physics.bending_stiffness > 0:
                ET.SubElement(
                    flexcomp,
                    "plugin",
                    plugin="mujoco.elasticity.cable",
                )
        else:
            # Rigid body tissue
            geom_type = tissue.geometry.primitive or "box"
            if geom_type == "box":
                dims = tissue.geometry.dimensions or (0.1, 0.1, 0.01)
                size = f"{dims[0]/2} {dims[1]/2} {dims[2]/2}"
                ET.SubElement(body, "geom", name=f"{tissue.name}_geom", type="box", size=size)
            elif geom_type == "sphere":
                r = tissue.geometry.radius or 0.05
                ET.SubElement(body, "geom", name=f"{tissue.name}_geom", type="sphere", size=str(r))
            elif geom_type == "cylinder":
                dims = tissue.geometry.dimensions or (0.05, 0.1)
                r = dims[0] / 2 if len(dims) > 0 else 0.025
                h = dims[1] / 2 if len(dims) > 1 else 0.05
                ET.SubElement(
                    body, "geom", name=f"{tissue.name}_geom", type="cylinder", size=f"{r} {h}"
                )
            else:
                # Default to box
                dims = tissue.geometry.dimensions or (0.1, 0.1, 0.01)
                size = f"{dims[0]/2} {dims[1]/2} {dims[2]/2}"
                ET.SubElement(body, "geom", name=f"{tissue.name}_geom", type="box", size=size)

            # Add physics properties
            if tissue.physics and tissue.physics.stiffness:
                # Soft body properties (simplified)
                pass  # MuJoCo soft bodies require more complex setup

    def _add_instrument_to_mjcf(
        self,
        mujoco: ET.Element,
        instrument: Any,
        index: int,
        asset: ET.Element,
    ) -> None:
        """Add instrument to MJCF structure."""
        worldbody = mujoco.find("worldbody")
        if worldbody is None:
            return

        body = ET.SubElement(worldbody, "body", name=instrument.name)
        if instrument.pose is not None:
            pos = f"{instrument.pose.position.x} {instrument.pose.position.y} {instrument.pose.position.z}"
        else:
            pos = "0 0 0"
        body.set("pos", pos)

        # Add geometry based on type
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

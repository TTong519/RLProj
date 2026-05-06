"""PyBullet simulator backend implementation."""

from pathlib import Path
from typing import Any

import numpy as np

from surg_rl.scene_definition.schema import HardwareBackend
from surg_rl.utils.gpu import select_backend
from surg_rl.utils.logging import get_logger
from surg_rl.utils.mesh_generation import (
    generate_box_tet_mesh,
    generate_cylinder_tet_mesh,
    generate_sphere_tet_mesh,
)
from surg_rl.utils.vtk_io import write_vtk_unstructured_grid

from .base_simulator import BaseSimulator, Observation, State, StepResult
from .scene_builder import SceneBuilder

logger = get_logger(__name__)


def _derive_neo_hookean_params(
    youngs_modulus: float,
    poissons_ratio: float,
) -> tuple[float, float]:
    """Derive Neo-Hookean mu and lambda from linear elastic constants.

    mu = E / (2 * (1 + nu))
    lambda = E * nu / ((1 + nu) * (1 - 2*nu))
    """
    mu = youngs_modulus / (2.0 * (1.0 + poissons_ratio))
    lam = (youngs_modulus * poissons_ratio) / (
        (1.0 + poissons_ratio) * (1.0 - 2.0 * poissons_ratio)
    )
    return mu, lam


class PyBulletSimulator(BaseSimulator):
    """PyBullet physics simulator backend.

    This simulator uses PyBullet for physics simulation.
    It converts scene definitions to URDF/SDF format and handles
    rendering through PyBullet's built-in renderer.
    """

    def __init__(
        self,
        timestep: float = 0.002,
        frame_skip: int = 1,
        render_width: int = 640,
        render_height: int = 480,
        assets_dir: str | Path | None = None,
        render_mode: str = "DIRECT",
        backend: HardwareBackend | None = None,
    ):
        """Initialize PyBullet simulator.

        Args:
            timestep: Simulation timestep in seconds.
            frame_skip: Number of simulation steps per action.
            render_width: Width of rendered images.
            render_height: Height of rendered images.
            assets_dir: Directory containing asset files.
            render_mode: PyBullet connection mode ('DIRECT', 'GUI').
            backend: Hardware backend hint.
        """
        super().__init__(
            timestep=timestep,
            frame_skip=frame_skip,
            render_width=render_width,
            render_height=render_height,
            backend=backend,
            render_mode=render_mode,
        )
        self.assets_dir = Path(assets_dir) if assets_dir else None
        self.scene_builder = SceneBuilder(assets_dir=assets_dir)
        self.render_mode = render_mode

        self._physics_client = None
        self._body_ids: dict[str, int] = {}
        self._soft_body_ids: dict[str, int] = {}
        self._joint_ids: dict[str, dict[str, int]] = {}
        self._control_map: list[dict[str, Any]] = []
        self._initial_positions: dict[str, list] = {}  # Store initial positions
        self._initial_orientations: dict[str, list] = {}  # Store initial orientations

        self._action_mode: str = "position"
        self._torque_control_joints: dict[tuple[int, int], bool] = {}  # (body_id, joint_idx) -> enabled
        self._endeffector_target_pos: np.ndarray | None = None
        self._endeffector_target_quat: np.ndarray | None = None
        self._mesh_cache: dict[str, Path] = {}
        self._soft_body_tet_data: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        self._soft_body_mesh_paths: dict[str, Path] = {}

        # Resolve backend (defaults to auto)
        if backend is None:
            backend = HardwareBackend.auto
        self._active_backend = select_backend(backend)
        logger.info("PyBullet simulator: selected backend=%s", self._active_backend.value)

        # GPU warning in DIRECT mode
        if render_mode == "DIRECT" and self._active_backend in (HardwareBackend.cuda, HardwareBackend.rocm):
            logger.warning(
                "PyBullet DIRECT mode does not support explicit GPU acceleration. "
                "GPU rendering requires GUI mode with display connected to GPU."
            )

    def _check_pybullet(self) -> None:
        """Check if PyBullet is available."""
        try:
            import pybullet

            self._pb = pybullet
        except ImportError:
            raise ImportError(
                "PyBullet is not installed. Install it with: pip install pybullet"
            ) from None

    def set_action_mode(self, mode: str) -> None:
        """Set the action mode for the simulation.

        Args:
            mode: Action mode ('position' or 'torque').
        """
        self._action_mode = mode
        if mode == "torque":
            # Disable default position/velocity motors so torque control works
            for robot_name in self._joint_ids:
                if robot_name not in self._body_ids:
                    continue
                body_id = self._body_ids[robot_name]
                for joint_idx in self._joint_ids[robot_name].values():
                    self._pb.setJointMotorControl2(
                        body_id,
                        joint_idx,
                        self._pb.VELOCITY_CONTROL,
                        targetVelocity=0.0,
                        force=0.0,
                        physicsClientId=self._physics_client,
                    )
                    self._torque_control_joints[(body_id, joint_idx)] = True

    def load_scene(self, scene_definition: Any) -> None:
        """Load a scene definition into PyBullet.

        Args:
            scene_definition: SceneDefinition object.

        Raises:
            ImportError: If PyBullet is not installed.
            RuntimeError: If scene cannot be loaded.
        """
        self._check_pybullet()

        self._scene = scene_definition

        # Use scene's timestep if specified
        if hasattr(scene_definition, "physics") and scene_definition.physics:
            self.timestep = scene_definition.physics.timestep

        # Connect to physics server
        if self._physics_client is None:
            if self.render_mode == "GUI":
                self._physics_client = self._pb.connect(self._pb.GUI)
            else:
                self._physics_client = self._pb.connect(self._pb.DIRECT)
            # Fresh connection — must enable deformable world before any load
            has_soft_body = any(getattr(t, "soft_body", False) for t in scene_definition.tissues)
            if has_soft_body:
                try:
                    self._pb.resetSimulation(
                        self._pb.RESET_USE_DEFORMABLE_WORLD,
                        physicsClientId=self._physics_client,
                    )
                except (AttributeError, TypeError):
                    self._pb.resetSimulation(physicsClientId=self._physics_client)
        else:
            # Clear previous bodies if reloading
            has_soft_body = any(getattr(t, "soft_body", False) for t in scene_definition.tissues)
            if has_soft_body:
                try:
                    self._pb.resetSimulation(
                        self._pb.RESET_USE_DEFORMABLE_WORLD,
                        physicsClientId=self._physics_client,
                    )
                except (AttributeError, TypeError):
                    # Fallback for older PyBullet without RESET_USE_DEFORMABLE_WORLD
                    self._pb.resetSimulation(physicsClientId=self._physics_client)
            else:
                self._pb.resetSimulation(physicsClientId=self._physics_client)
            self._body_ids.clear()
            self._joint_ids.clear()
            self._initial_positions.clear()
            self._initial_orientations.clear()
            self._soft_body_ids.clear()
            self._mesh_cache.clear()

        # Configure physics
        physics = getattr(scene_definition, "physics", None)
        if physics is not None:
            self._pb.setGravity(
                getattr(physics, "gravity", [0, 0, -9.81])[0],
                getattr(physics, "gravity", [0, 0, -9.81])[1],
                getattr(physics, "gravity", [0, 0, -9.81])[2],
                physicsClientId=self._physics_client,
            )
            self._pb.setTimeStep(
                getattr(physics, "timestep", self.timestep),
                physicsClientId=self._physics_client,
            )
        else:
            self._pb.setGravity(0, 0, -9.81, physicsClientId=self._physics_client)
            self._pb.setTimeStep(self.timestep, physicsClientId=self._physics_client)

        # Load robots
        for robot in scene_definition.robots:
            self._load_robot(robot)

        # Load tissues
        for tissue in scene_definition.tissues:
            self._load_tissue(tissue)

        # Load instruments
        for instrument in scene_definition.instruments:
            self._load_instrument(instrument)

        # Load environment
        self._load_environment(scene_definition)

        self._loaded = True
        self._build_control_map()

        # Let objects settle by stepping simulation a few times
        # This prevents objects from having initial velocities that cause them to fly off
        for _ in range(100):
            self._pb.stepSimulation(physicsClientId=self._physics_client)

        logger.info(f"Loaded scene: {scene_definition.metadata.name}")

    def _load_robot(self, robot: Any) -> None:
        """Load a robot into the simulation."""
        # Try to load URDF or use primitive
        if robot.urdf_path:
            urdf_resolved = self.scene_builder.load_urdf_asset(
                robot.urdf_path, robot.name
            )
            if urdf_resolved is not None:
                try:
                    body_id = self._pb.loadURDF(
                        str(urdf_resolved),
                        basePosition=[
                            robot.base_pose.position.x,
                            robot.base_pose.position.y,
                            robot.base_pose.position.z,
                        ],
                        baseOrientation=[
                            robot.base_pose.orientation.x,
                            robot.base_pose.orientation.y,
                            robot.base_pose.orientation.z,
                            robot.base_pose.orientation.w,
                        ],
                        physicsClientId=self._physics_client,
                    )
                    self._body_ids[robot.name] = body_id
                    self._collect_joint_info(robot.name, body_id)
                    return
                except Exception as e:
                    logger.warning(f"Failed to load robot URDF: {e}. Using primitive.")
            else:
                # Fall back to primitive robot builder
                pass

        # Primitive fallback: create a base + 1-DOF revolute joint (+ optional gripper)
        base_collision = self._pb.createCollisionShape(
            self._pb.GEOM_BOX,
            halfExtents=[0.05, 0.05, 0.1],
            physicsClientId=self._physics_client,
        )
        base_visual = self._pb.createVisualShape(
            self._pb.GEOM_BOX,
            halfExtents=[0.05, 0.05, 0.1],
            rgbaColor=[0.3, 0.3, 0.8, 1.0],
            physicsClientId=self._physics_client,
        )
        link_collision = self._pb.createCollisionShape(
            self._pb.GEOM_BOX,
            halfExtents=[0.03, 0.03, 0.08],
            physicsClientId=self._physics_client,
        )
        link_visual = self._pb.createVisualShape(
            self._pb.GEOM_BOX,
            halfExtents=[0.03, 0.03, 0.08],
            rgbaColor=[0.4, 0.4, 0.9, 1.0],
            physicsClientId=self._physics_client,
        )

        has_end_effectors = bool(getattr(robot, "end_effectors", None))

        if has_end_effectors:
            gripper_collision = self._pb.createCollisionShape(
                self._pb.GEOM_BOX,
                halfExtents=[0.02, 0.02, 0.02],
                physicsClientId=self._physics_client,
            )
            gripper_visual = self._pb.createVisualShape(
                self._pb.GEOM_BOX,
                halfExtents=[0.02, 0.02, 0.02],
                rgbaColor=[0.5, 0.5, 0.5, 1.0],
                physicsClientId=self._physics_client,
            )
            link_masses = [0.5, 0.1]
            link_collision_indices = [link_collision, gripper_collision]
            link_visual_indices = [link_visual, gripper_visual]
            link_positions = [[0.0, 0.0, 0.15], [0.0, 0.0, 0.1]]
            link_orientations = [[0.0, 0.0, 0.0, 1.0], [0.0, 0.0, 0.0, 1.0]]
            link_inertial_positions = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
            link_inertial_orientations = [[0.0, 0.0, 0.0, 1.0], [0.0, 0.0, 0.0, 1.0]]
            link_parent_indices = [0, 1]
            link_joint_types = [self._pb.JOINT_REVOLUTE, self._pb.JOINT_PRISMATIC]
            link_joint_axes = [[0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        else:
            link_masses = [0.5]
            link_collision_indices = [link_collision]
            link_visual_indices = [link_visual]
            link_positions = [[0.0, 0.0, 0.15]]
            link_orientations = [[0.0, 0.0, 0.0, 1.0]]
            link_inertial_positions = [[0.0, 0.0, 0.0]]
            link_inertial_orientations = [[0.0, 0.0, 0.0, 1.0]]
            link_parent_indices = [0]
            link_joint_types = [self._pb.JOINT_REVOLUTE]
            link_joint_axes = [[0.0, 1.0, 0.0]]

        body_id = self._pb.createMultiBody(
            baseMass=0.0,
            baseCollisionShapeIndex=base_collision,
            baseVisualShapeIndex=base_visual,
            basePosition=[
                robot.base_pose.position.x,
                robot.base_pose.position.y,
                robot.base_pose.position.z,
            ],
            baseOrientation=[
                robot.base_pose.orientation.x,
                robot.base_pose.orientation.y,
                robot.base_pose.orientation.z,
                robot.base_pose.orientation.w,
            ],
            linkMasses=link_masses,
            linkCollisionShapeIndices=link_collision_indices,
            linkVisualShapeIndices=link_visual_indices,
            linkPositions=link_positions,
            linkOrientations=link_orientations,
            linkInertialFramePositions=link_inertial_positions,
            linkInertialFrameOrientations=link_inertial_orientations,
            linkParentIndices=link_parent_indices,
            linkJointTypes=link_joint_types,
            linkJointAxis=link_joint_axes,
            physicsClientId=self._physics_client,
        )
        self._body_ids[robot.name] = body_id
        self._collect_joint_info(robot.name, body_id)
        # Map pybullet's auto-named prismatic joint to "gripper" if end_effectors exist.
        if has_end_effectors and robot.name in self._joint_ids:
            for joint_name, joint_idx in list(self._joint_ids[robot.name].items()):
                info = self._pb.getJointInfo(
                    body_id, joint_idx, physicsClientId=self._physics_client
                )
                if info[2] == self._pb.JOINT_PRISMATIC:
                    del self._joint_ids[robot.name][joint_name]
                    self._joint_ids[robot.name]["gripper"] = joint_idx
                    break
        # Store initial pose for reset
        self._initial_positions[robot.name] = [
            robot.base_pose.position.x,
            robot.base_pose.position.y,
            robot.base_pose.position.z,
        ]
        self._initial_orientations[robot.name] = [
            robot.base_pose.orientation.x,
            robot.base_pose.orientation.y,
            robot.base_pose.orientation.z,
            robot.base_pose.orientation.w,
        ]

    def _collect_joint_info(self, robot_name: str, body_id: int) -> None:
        """Collect joint indices for a loaded robot body."""
        num_joints = self._pb.getNumJoints(body_id, physicsClientId=self._physics_client)
        joint_dict: dict[str, int] = {}
        for j in range(num_joints):
            info = self._pb.getJointInfo(body_id, j, physicsClientId=self._physics_client)
            joint_name = info[1].decode("utf-8")
            joint_dict[joint_name] = j
            # Enable position control by default
            self._pb.setJointMotorControl2(
                body_id,
                j,
                self._pb.POSITION_CONTROL,
                targetPosition=0.0,
                force=100.0,
                physicsClientId=self._physics_client,
            )
        self._joint_ids[robot_name] = joint_dict

    def _load_tissue(self, tissue: Any) -> None:
        """Load a tissue into the simulation."""
        if getattr(tissue, "soft_body", False):
            self._load_soft_body_tissue(tissue)
            return
        # Resolve mesh or primitive fallback
        mesh_path = None
        if tissue.geometry is not None and getattr(tissue.geometry, "mesh", None):
            mesh_path = tissue.geometry.mesh.path
        resolved, is_primitive = self.scene_builder.get_mesh_or_primitive(
            mesh_path=mesh_path,
            primitive=tissue.geometry.primitive if tissue.geometry is not None else None,
            dimensions=tissue.geometry.dimensions or (0.1, 0.1, 0.01)
            if tissue.geometry is not None
            else (0.1, 0.1, 0.01),
            name=tissue.name,
            radius=getattr(tissue.geometry, "radius", None) if tissue.geometry is not None else None,
        )
        # Determine primitive parameters for collision shape
        primitive = tissue.geometry.primitive if tissue.geometry is not None else None
        if primitive == "box":
            dims = tissue.geometry.dimensions or (0.1, 0.1, 0.01)
            shape_type = self._pb.GEOM_BOX
            half_extents = [d / 2 for d in dims]
        elif primitive == "sphere":
            r = tissue.geometry.radius or 0.05
            shape_type = self._pb.GEOM_SPHERE
            half_extents = [r]
        elif primitive == "cylinder":
            shape_type = self._pb.GEOM_CYLINDER
            dims = tissue.geometry.dimensions or (0.05, 0.05, 0.1)
            half_extents = [dims[2] / 2, dims[0] / 2]  # height, radius
        else:
            dims = (
                tissue.geometry.dimensions or (0.1, 0.1, 0.01)
                if tissue.geometry is not None
                else (0.1, 0.1, 0.01)
            )
            shape_type = self._pb.GEOM_BOX
            half_extents = [d / 2 for d in dims]

        # Create collision shape (always primitive for stability)
        if shape_type == self._pb.GEOM_BOX:
            collision_shape = self._pb.createCollisionShape(
                shape_type,
                halfExtents=half_extents,
                physicsClientId=self._physics_client,
            )
        elif shape_type == self._pb.GEOM_SPHERE:
            collision_shape = self._pb.createCollisionShape(
                shape_type,
                radius=half_extents[0],
                physicsClientId=self._physics_client,
            )
        elif shape_type == self._pb.GEOM_CYLINDER:
            collision_shape = self._pb.createCollisionShape(
                shape_type,
                radius=half_extents[1],
                height=half_extents[0] * 2,
                physicsClientId=self._physics_client,
            )

        # Create visual shape
        color = [0.95, 0.85, 0.8, 1.0]
        if hasattr(tissue, "color") and tissue.color is not None:
            color = [tissue.color.r, tissue.color.g, tissue.color.b, tissue.color.a]

        if not is_primitive and resolved is not None:
            # Use real mesh for visual shape
            scale = (
                getattr(tissue.geometry.mesh, "scale", (1.0, 1.0, 1.0))
                if tissue.geometry is not None and getattr(tissue.geometry, "mesh", None)
                else (1.0, 1.0, 1.0)
            )
            visual_shape = self._load_mesh_visual_shape(resolved, scale=scale)
            if visual_shape == -1:
                # Fallback to primitive visual
                if shape_type == self._pb.GEOM_BOX:
                    visual_shape = self._pb.createVisualShape(
                        shape_type,
                        halfExtents=half_extents,
                        rgbaColor=color,
                        physicsClientId=self._physics_client,
                    )
                elif shape_type == self._pb.GEOM_SPHERE:
                    visual_shape = self._pb.createVisualShape(
                        shape_type,
                        radius=half_extents[0],
                        rgbaColor=color,
                        physicsClientId=self._physics_client,
                    )
                elif shape_type == self._pb.GEOM_CYLINDER:
                    visual_shape = self._pb.createVisualShape(
                        shape_type,
                        radius=half_extents[1],
                        length=half_extents[0] * 2,
                        rgbaColor=color,
                        physicsClientId=self._physics_client,
                    )
        else:
            # Primitive visual shape
            if shape_type == self._pb.GEOM_BOX:
                visual_shape = self._pb.createVisualShape(
                    shape_type,
                    halfExtents=half_extents,
                    rgbaColor=color,
                    physicsClientId=self._physics_client,
                )
            elif shape_type == self._pb.GEOM_SPHERE:
                visual_shape = self._pb.createVisualShape(
                    shape_type,
                    radius=half_extents[0],
                    rgbaColor=color,
                    physicsClientId=self._physics_client,
                )
            elif shape_type == self._pb.GEOM_CYLINDER:
                visual_shape = self._pb.createVisualShape(
                    shape_type,
                    radius=half_extents[1],
                    length=half_extents[0] * 2,
                    rgbaColor=color,
                    physicsClientId=self._physics_client,
                )

        pose = tissue.pose
        if pose is None or not hasattr(pose, "position"):
            position = (0.0, 0.0, 0.0)
            orientation = (0.0, 0.0, 0.0, 1.0)
        else:
            position = (pose.position.x, pose.position.y, pose.position.z)
            orientation = (
                pose.orientation.x,
                pose.orientation.y,
                pose.orientation.z,
                pose.orientation.w,
            )

        body_id = self._pb.createMultiBody(
            baseMass=0.0,
            baseCollisionShapeIndex=collision_shape,
            baseVisualShapeIndex=visual_shape,
            basePosition=list(position),
            physicsClientId=self._physics_client,
        )
        self._body_ids[tissue.name] = body_id
        self._initial_positions[tissue.name] = list(position)
        self._initial_orientations[tissue.name] = list(orientation)

    def _load_mesh_visual_shape(self, mesh_path: Path, scale: tuple[float, float, float] = (1.0, 1.0, 1.0)) -> int:
        """Create a visual shape from a mesh file (OBJ/DAE). Returns shape ID."""
        try:
            visual_shape_id = self._pb.createVisualShape(
                shapeType=self._pb.GEOM_MESH,
                fileName=str(mesh_path),
                meshScale=scale,
                physicsClientId=self._physics_client,
            )
            return visual_shape_id
        except Exception as e:
            logger.warning(f"Failed to create visual shape for mesh {mesh_path}: {e}. Falling back to primitive.")
            return -1

    def _get_vtk_mesh_path(self, tissue: Any) -> Path:
        """Generate or return cached .vtk tetrahedral mesh for a soft body tissue."""
        dims = getattr(tissue.geometry, "dimensions", None) or (0.1, 0.1, 0.01)
        radius = getattr(tissue.geometry, "radius", None)
        primitive = getattr(tissue.geometry, "primitive", None)

        # Build stable cache key
        cache_key = f"{tissue.name}_{primitive}_{tuple(dims)}_{radius}"
        if cache_key in self._mesh_cache:
            return self._mesh_cache[cache_key]

        if primitive == "sphere":
            r = radius or min(dims) / 2
            mesh_path = self.scene_builder.temp_dir / f"{tissue.name}_sphere_tet.vtk"
            if not mesh_path.exists():
                verts, tets = generate_sphere_tet_mesh(r, subdivisions=2)
                write_vtk_unstructured_grid(mesh_path, verts, tets)
        elif primitive == "cylinder":
            r = radius or min(dims[0], dims[1]) / 2 if len(dims) >= 2 else 0.05
            h = dims[2] if len(dims) >= 3 else 0.1
            mesh_path = self.scene_builder.temp_dir / f"{tissue.name}_cylinder_tet.vtk"
            if not mesh_path.exists():
                verts, tets = generate_cylinder_tet_mesh(r, h, theta_segments=16, height_segments=4)
                write_vtk_unstructured_grid(mesh_path, verts, tets)
        else:  # Default to box
            mesh_path = self.scene_builder.temp_dir / f"{tissue.name}_box_tet.vtk"
            if not mesh_path.exists():
                verts, tets = generate_box_tet_mesh(tuple(dims), resolution=4)
                write_vtk_unstructured_grid(mesh_path, verts, tets)

        self._mesh_cache[cache_key] = mesh_path
        return mesh_path

    def _load_soft_body_tissue(self, tissue: Any) -> None:
        """Load a deformable tissue via pybullet.loadSoftBody.

        Prefers a volumetric .vtk mesh (A2) but falls back to the triangulated
        .obj surface mesh (A1) if generation fails.
        """
        # 1. Mesh generation
        try:
            mesh_path = self._get_vtk_mesh_path(tissue)
        except Exception:
            dims = getattr(tissue.geometry, "dimensions", (0.1, 0.1, 0.01))
            mesh_path, _ = self.scene_builder.get_mesh_or_primitive(
                mesh_path=(
                    getattr(tissue.geometry, "mesh_path", None)
                    if tissue.geometry is not None
                    else None
                ),
                primitive=(
                    getattr(tissue.geometry, "primitive", None)
                    if tissue.geometry is not None
                    else None
                ),
                dimensions=dims if isinstance(dims, tuple) else tuple(dims),
                name=tissue.name,
                radius=getattr(tissue.geometry, "radius", None),
            )

        # 2. Map PyBulletSoftBodyConfig to loadSoftBody kwargs
        physics = getattr(tissue, "physics", None)
        pbc = getattr(physics, "pybullet", None) if physics is not None else None
        if pbc is None:
            kwargs: dict[str, Any] = {
                "useMassSpring": 1,
                "springElasticStiffness": 1.0,
                "springDampingStiffness": 0.1,
                "physicsClientId": self._physics_client,
            }
        else:
            kwargs = {
                "fileName": str(mesh_path),
                "basePosition": [
                    tissue.pose.position.x,
                    tissue.pose.position.y,
                    tissue.pose.position.z,
                ],
                "baseOrientation": [
                    tissue.pose.orientation.x,
                    tissue.pose.orientation.y,
                    tissue.pose.orientation.z,
                    tissue.pose.orientation.w,
                ],
                "useMassSpring": 1 if pbc.use_mass_spring else 0,
                "useNeoHookean": 1 if pbc.use_neo_hookean else 0,
                "useBendingSprings": 1 if pbc.use_bending_springs else 0,
                "useSelfCollision": 1 if pbc.use_self_collision else 0,
                "springElasticStiffness": pbc.spring_elastic_stiffness,
                "springDampingStiffness": pbc.spring_damping_stiffness,
                "springBendingStiffness": pbc.spring_bending_stiffness,
                "NeoHookeanMu": pbc.neo_hookean_mu,
                "NeoHookeanLambda": pbc.neo_hookean_lambda,
                "NeoHookeanDamping": pbc.neo_hookean_damping,
                "repulsionStiffness": pbc.repulsion_stiffness,
                "frictionCoeff": pbc.friction_coefficient,
                "springDampingAllDirections": 1 if pbc.spring_damping_all_directions else 0,
                "physicsClientId": self._physics_client,
            }
            if pbc.mass is not None:
                kwargs["mass"] = pbc.mass
            if pbc.scale is not None:
                kwargs["scale"] = pbc.scale
            if pbc.collision_margin is not None:
                kwargs["collisionMargin"] = pbc.collision_margin
            if pbc.sim_mesh_path is not None:
                kwargs["simFileName"] = pbc.sim_mesh_path

            if "mass" not in kwargs:
                density = getattr(physics, "density", 1000.0)
                volume = 1.0
                dims = getattr(tissue.geometry, "dimensions", (0.1, 0.1, 0.01))
                if hasattr(dims, "__iter__") and len(list(dims)) == 3:
                    volume = float(dims[0] * dims[1] * dims[2])
                kwargs["mass"] = density * volume

            dc = getattr(tissue, "deformable", None)
            if dc is not None:
                pc = dc.pybullet
                if pc.solver_type == "neo_hookean":
                    kwargs["useMassSpring"] = 0
                    kwargs["useNeoHookean"] = 1
                    if pc.auto_derive_neo_hookean and physics is not None:
                        mu, lam = _derive_neo_hookean_params(
                            physics.youngs_modulus, physics.poissons_ratio
                        )
                        kwargs["NeoHookeanMu"] = mu
                        kwargs["NeoHookeanLambda"] = lam
                        kwargs["NeoHookeanDamping"] = physics.damping * 0.01
                else:
                    kwargs["useMassSpring"] = 1
                    kwargs["useNeoHookean"] = 0
                kwargs["repulsionStiffness"] = pc.repulsion_stiffness
                kwargs["collisionMargin"] = pc.collision_margin
                kwargs["useSelfCollision"] = 1 if pc.use_self_collision else 0
                if pc.solver_type == "mass_spring":
                    kwargs["useBendingSprings"] = 1 if pc.bending_stiffness > 0 else 0
                    kwargs["springBendingStiffness"] = pc.bending_stiffness

        soft_id = self._pb.loadSoftBody(
            fileName=str(mesh_path),
            **{k: v for k, v in kwargs.items() if k != "fileName"},
        )
        self._soft_body_ids[tissue.name] = soft_id

        from surg_rl.utils.vtk_io import read_vtk_unstructured_grid

        tet_verts, tet_elems = read_vtk_unstructured_grid(mesh_path)
        self._soft_body_tet_data[tissue.name + "_tets"] = (tet_verts, tet_elems)
        self._soft_body_mesh_paths[tissue.name] = mesh_path

    def _load_instrument(self, instrument: Any) -> None:
        """Load an instrument into the simulation."""
        # Use primitive for instruments
        collision_shape = self._pb.createCollisionShape(
            self._pb.GEOM_BOX,
            halfExtents=[0.01, 0.01, 0.05],
            physicsClientId=self._physics_client,
        )
        visual_shape = self._pb.createVisualShape(
            self._pb.GEOM_BOX,
            halfExtents=[0.01, 0.01, 0.05],
            rgbaColor=[0.7, 0.7, 0.7, 1.0],
            physicsClientId=self._physics_client,
        )

        pose = instrument.pose
        if pose is None or not hasattr(pose, "position"):
            position = (0.0, 0.0, 0.0)
            orientation = (0.0, 0.0, 0.0, 1.0)
        else:
            position = (pose.position.x, pose.position.y, pose.position.z)
            orientation = (
                pose.orientation.x,
                pose.orientation.y,
                pose.orientation.z,
                pose.orientation.w,
            )

        body_id = self._pb.createMultiBody(
            baseMass=0.0,  # Static (no control implemented yet)
            baseCollisionShapeIndex=collision_shape,
            baseVisualShapeIndex=visual_shape,
            basePosition=list(position),
            physicsClientId=self._physics_client,
        )
        self._body_ids[instrument.name] = body_id
        # Store initial position for reset
        self._initial_positions[instrument.name] = list(position)
        self._initial_orientations[instrument.name] = list(orientation)

    def _load_environment(self, scene_definition: Any) -> None:
        """Load environment elements."""
        # Load ground plane
        ground_enabled = False
        if hasattr(scene_definition, "environment") and scene_definition.environment is not None:
            env = scene_definition.environment
            if hasattr(env, "ground_plane") and env.ground_plane is not None:
                ground_enabled = getattr(env.ground_plane, "enabled", False)
        if ground_enabled:
            try:
                import pybullet_data

                self._pb.setAdditionalSearchPath(pybullet_data.getDataPath())
            except ImportError:
                logger.warning("pybullet_data not available; ground plane URDF may fail to load")
            self._pb.loadURDF(
                "plane.urdf",
                physicsClientId=self._physics_client,
            )

    def get_camera_image(
        self,
        camera_name: str,
        width: int | None = None,
        height: int | None = None,
    ) -> np.ndarray | None:
        """Render from a named scene camera (scene.environment.cameras)."""
        if not self._loaded:
            return None
        width = width or self.render_width
        height = height or self.render_height
        camera_pos = np.array([0.5, 0.0, 1.0], dtype=float)
        target_pos = np.array([0.0, 0.0, 0.0], dtype=float)
        # Attempt to resolve camera from scene definition
        scene = getattr(self, "_scene", None)
        if scene is not None and scene.environment is not None:
            for cam in scene.environment.cameras:
                if cam.name == camera_name:
                    p = cam.pose.position
                    camera_pos = np.array([p.x, p.y, p.z], dtype=float)
                    if cam.look_at:
                        la = cam.look_at
                        target_pos = np.array([la.x, la.y, la.z], dtype=float)
                    else:
                        # Default: look slightly forward/down
                        target_pos = camera_pos + np.array([0.3, 0.0, -0.3], dtype=float)
                    break
        else:
            logger.warning(f"Camera '{camera_name}' not defined in scene; using fallback position.")
        view_matrix = self._pb.computeViewMatrix(
            cameraEyePosition=camera_pos.tolist(),
            cameraTargetPosition=target_pos.tolist(),
            cameraUpVector=[0, 0, 1],
            physicsClientId=self._physics_client,
        )
        proj_matrix = self._pb.computeProjectionMatrixFOV(
            fov=60,
            aspect=width / height,
            nearVal=0.1,
            farVal=100.0,
            physicsClientId=self._physics_client,
        )
        _, _, rgb, _, _ = self._pb.getCameraImage(
            width=width,
            height=height,
            viewMatrix=view_matrix,
            projectionMatrix=proj_matrix,
            physicsClientId=self._physics_client,
        )
        return rgb

    def reset(self, seed: int | None = None) -> Observation:
        """Reset the simulation."""
        if not self._loaded:
            raise RuntimeError("Scene not loaded. Call load_scene() first.")

        if seed is not None:
            np.random.seed(seed)

        if self._soft_body_ids:
            # Soft bodies don't support per-body reset; reload scene entirely
            try:
                self._pb.resetSimulation(
                    self._pb.RESET_USE_DEFORMABLE_WORLD,
                    physicsClientId=self._physics_client,
                )
            except (AttributeError, TypeError):
                self._pb.resetSimulation(physicsClientId=self._physics_client)
            self._body_ids.clear()
            self._joint_ids.clear()
            self._initial_positions.clear()
            self._initial_orientations.clear()
            self._soft_body_ids.clear()
            self.load_scene(self._scene)
            return self._get_observation()

        # Reset all bodies to their initial positions
        for name, body_id in self._body_ids.items():
            pos = self._initial_positions.get(name, [0, 0, 0])
            orn = self._initial_orientations.get(name, [0, 0, 0, 1])
            self._pb.resetBasePositionAndOrientation(
                body_id,
                pos,
                orn,
                physicsClientId=self._physics_client,
            )
            # Also reset velocity
            self._pb.resetBaseVelocity(
                body_id, [0, 0, 0], [0, 0, 0], physicsClientId=self._physics_client
            )
            # Reset joint positions and velocities
            if name in self._joint_ids:
                for joint_idx in self._joint_ids[name].values():
                    self._pb.resetJointState(
                        body_id,
                        joint_idx,
                        targetValue=0.0,
                        targetVelocity=0.0,
                        physicsClientId=self._physics_client,
                    )

        self._simulation_time = 0.0
        return self._get_observation()

    def step(self, action: np.ndarray) -> StepResult:
        """Execute one simulation step."""
        if not self._loaded:
            raise RuntimeError("Scene not loaded. Call load_scene() first.")

        # Apply action
        if action is not None:
            self._apply_action(action)

        # Step simulation
        for _ in range(self.frame_skip):
            self._pb.stepSimulation(physicsClientId=self._physics_client)

        self._simulation_time += self.timestep * self.frame_skip

        obs = self._get_observation()
        reward = self._compute_reward()
        terminated = self._check_termination()
        truncated = self._check_truncation()

        info = {"simulation_time": self._simulation_time, "collateral_damage": 0.0}

        return StepResult(
            observation=obs, reward=reward, terminated=terminated, truncated=truncated, info=info
        )

    def render(
        self,
        mode: str = "rgb_array",
        width: int | None = None,
        height: int | None = None,
        camera_name: str | None = None,
    ) -> np.ndarray | None:
        """Render the current simulation state."""
        if not self._loaded:
            return None

        width = width or self.render_width
        height = height or self.render_height

        if mode == "human":
            # Already handled by GUI mode
            return None

        if camera_name is not None:
            return self.get_camera_image(camera_name, width=width, height=height)

        # Offscreen rendering
        view_matrix = self._pb.computeViewMatrixFromYawPitchRoll(
            cameraTargetPosition=[0, 0, 0],
            distance=1.0,
            yaw=45,
            pitch=-30,
            roll=0,
            upAxisIndex=2,
            physicsClientId=self._physics_client,
        )
        proj_matrix = self._pb.computeProjectionMatrixFOV(
            fov=60,
            aspect=width / height,
            nearVal=0.1,
            farVal=100.0,
            physicsClientId=self._physics_client,
        )

        _, _, rgb, depth, seg = self._pb.getCameraImage(
            width=width,
            height=height,
            viewMatrix=view_matrix,
            projectionMatrix=proj_matrix,
            physicsClientId=self._physics_client,
        )

        rgb_array = (
            rgb[:, :, :3]
            if hasattr(rgb, "shape")
            else (
                np.array(rgb).reshape((height, width, 4))[:, :, :3]
                if len(rgb) == width * height * 4
                else np.zeros((height, width, 3), dtype=np.uint8)
            )
        )

        # Store depth for later retrieval via render('depth_array')
        if isinstance(depth, (tuple, list)):
            try:
                self._last_depth = np.array(depth).reshape((height, width, 1))
            except Exception:
                self._last_depth = None
        elif isinstance(depth, np.ndarray):
            self._last_depth = depth.reshape((height, width, 1)) if depth.ndim == 1 else depth
        else:
            self._last_depth = None

        if mode == "depth_array":
            return self._last_depth

        return rgb_array

    def get_state(self) -> State:
        """Get current simulation state."""
        if not self._loaded:
            return State()

        # Get all body positions/orientations
        body_positions = {}
        body_orientations = {}

        for name, body_id in self._body_ids.items():
            pos, orn = self._pb.getBasePositionAndOrientation(
                body_id, physicsClientId=self._physics_client
            )
            body_positions[name] = np.array(pos)
            body_orientations[name] = np.array(orn)

        # Get joint states
        joint_states = self.get_joint_states()
        qpos_list = []
        qvel_list = []
        for _robot_name, states in joint_states.items():
            qpos_list.append(states["positions"])
            qvel_list.append(states["velocities"])

        qpos = np.concatenate(qpos_list) if qpos_list else None
        qvel = np.concatenate(qvel_list) if qvel_list else None

        # Capture soft-body node positions
        soft_body_nodes = {}
        for tissue_name, soft_id in self._soft_body_ids.items():
            try:
                data = self._pb.getMeshData(soft_id, physicsClientId=self._physics_client)
                if len(data) >= 2 and len(data[1]) > 0:
                    vertices = np.array(data[1], dtype=np.float32)  # (N, 3)
                    soft_body_nodes[tissue_name] = vertices
            except Exception:
                pass  # getMeshData may fail on some PyBullet versions

        return State(
            time=self._simulation_time,
            qpos=qpos,
            qvel=qvel,
            body_positions=body_positions,
            body_orientations=body_orientations,
            custom={"soft_body_nodes": soft_body_nodes} if soft_body_nodes else {},
        )

    def get_joint_states(self) -> dict[str, dict[str, np.ndarray]]:
        """Get joint positions and velocities for all robots.

        Returns:
            Dictionary mapping robot name to {'positions': array, 'velocities': array}.
        """
        result: dict[str, dict[str, np.ndarray]] = {}
        if not self._loaded:
            return result

        for robot_name, joint_dict in self._joint_ids.items():
            if robot_name not in self._body_ids:
                continue
            body_id = self._body_ids[robot_name]
            positions = []
            velocities = []
            for joint_name in sorted(joint_dict.keys()):
                joint_idx = joint_dict[joint_name]
                state = self._pb.getJointState(
                    body_id, joint_idx, physicsClientId=self._physics_client
                )
                positions.append(state[0])
                velocities.append(state[1])
            result[robot_name] = {
                "positions": np.array(positions, dtype=np.float32),
                "velocities": np.array(velocities, dtype=np.float32),
            }
        return result

    def set_state(self, state: State) -> None:
        """Restore simulation state."""
        if not self._loaded:
            return

        self._simulation_time = state.time

        # Restore body positions/orientations
        for name, pos in state.body_positions.items():
            if name in self._body_ids:
                orn = state.body_orientations.get(name, [0, 0, 0, 1])
                self._pb.resetBasePositionAndOrientation(
                    self._body_ids[name],
                    pos.tolist(),
                    orn.tolist() if hasattr(orn, "tolist") else orn,
                    physicsClientId=self._physics_client,
                )

        # Restore joint states — iterate in same order as get_state() builds qpos
        if state.qpos is not None and state.qvel is not None:
            idx = 0
            for robot_name in sorted(self._joint_ids.keys()):
                if robot_name not in self._body_ids:
                    continue
                body_id = self._body_ids[robot_name]
                joint_dict = self._joint_ids[robot_name]
                for joint_name in sorted(joint_dict.keys()):
                    joint_idx = joint_dict[joint_name]
                    if idx < len(state.qpos):
                        self._pb.resetJointState(
                            body_id,
                            joint_idx,
                            targetValue=float(state.qpos[idx]),
                            targetVelocity=float(state.qvel[idx]) if idx < len(state.qvel) else 0.0,
                            physicsClientId=self._physics_client,
                        )
                    idx += 1

        # Restore soft body node positions
        soft_body_nodes = state.custom.get("soft_body_nodes", {})
        for tissue_name, node_positions in soft_body_nodes.items():
            if tissue_name not in self._soft_body_ids:
                continue
            soft_id = self._soft_body_ids[tissue_name]
            try:
                self._pb.resetMeshData(
                    soft_id,
                    node_positions.flatten().tolist(),
                    physicsClientId=self._physics_client,
                )
            except Exception:
                logger.warning(f"Failed to restore soft body mesh data for {tissue_name}")

    def set_body_property(self, body_name: str, property_name: str, value: float) -> bool:
        """Set a named property on a body (mass or friction).

        Args:
            body_name: Name of the body.
            property_name: Property name ('mass' or 'friction').
            value: New value.

        Returns:
            True if applied successfully.
        """
        if not self._loaded or body_name not in self._body_ids:
            return False
        try:
            body_id = self._body_ids[body_name]
            if property_name == "mass":
                self._pb.changeDynamics(
                    body_id,
                    -1,
                    mass=max(value, 1e-6),
                    physicsClientId=self._physics_client,
                )
                return True
            elif property_name == "friction":
                self._pb.changeDynamics(
                    body_id,
                    -1,
                    lateralFriction=max(value, 0.0),
                    physicsClientId=self._physics_client,
                )
                return True
        except Exception:
            pass
        return False

    # Optional controller stubs -----------------------------------------------------

    def get_robot_state(self, robot_name: str) -> np.ndarray | None:
        """Get joint state for a specific robot."""
        # TODO: Extend to include velocities or full state once needed.
        if not self._loaded or robot_name not in self._joint_ids:
            return None
        body_id = self._body_ids.get(robot_name)
        if body_id is None:
            return None
        positions = []
        for joint_name in sorted(self._joint_ids[robot_name].keys()):
            joint_idx = self._joint_ids[robot_name][joint_name]
            state = self._pb.getJointState(body_id, joint_idx, physicsClientId=self._physics_client)
            positions.append(state[0])
        return np.array(positions, dtype=np.float32)

    def get_end_effector_pose(self, robot_name: str) -> tuple[np.ndarray, np.ndarray] | None:
        """Get end effector pose for a specific robot."""
        # TODO: Map to a dedicated end-effector link instead of base.
        if not self._loaded or robot_name not in self._body_ids:
            return None
        body_id = self._body_ids[robot_name]
        pos, orn = self._pb.getBasePositionAndOrientation(
            body_id, physicsClientId=self._physics_client
        )
        return np.array(pos), np.array(orn)

    def set_end_effector_target(
        self, position: np.ndarray, orientation: np.ndarray | None = None
    ) -> None:
        """Set the target end-effector pose for IK control.

        Args:
            position: Target position [x, y, z].
            orientation: Target orientation quaternion [x, y, z, w] or None.
        """
        self._endeffector_target_pos = np.asarray(position, dtype=np.float64)
        if orientation is not None:
            self._endeffector_target_quat = np.asarray(orientation, dtype=np.float64)
        else:
            self._endeffector_target_quat = None

    def get_body_pose(self, body_name: str) -> tuple[np.ndarray, np.ndarray] | None:
        """Get pose of a named body in the simulation."""
        if not self._loaded:
            return None
        if body_name in self._soft_body_ids:
            data = self._pb.getMeshData(
                self._soft_body_ids[body_name],
                physicsClientId=self._physics_client,
            )
            vertices = np.array(data[1])  # list of (x,y,z) tuples
            if len(vertices) == 0:
                return None
            centroid = vertices.mean(axis=0)
            return centroid, np.array([0.0, 0.0, 0.0, 1.0])
        if body_name not in self._body_ids:
            return None
        body_id = self._body_ids[body_name]
        pos, orn = self._pb.getBasePositionAndOrientation(
            body_id, physicsClientId=self._physics_client
        )
        return np.array(pos), np.array(orn)

    def set_body_pose(
        self,
        body_name: str,
        position: np.ndarray,
        orientation: np.ndarray,
    ) -> bool:
        """Set pose of a named body in the simulation."""
        if not self._loaded or body_name not in self._body_ids:
            return False
        self._pb.resetBasePositionAndOrientation(
            self._body_ids[body_name],
            position.tolist(),
            orientation.tolist(),
            physicsClientId=self._physics_client,
        )
        return True

    def _apply_cut(self, cut_action: Any) -> None:
        """Apply a volumetric cut to PyBullet soft body.

        Uses stored tetrahedra from load time for remeshing, overwrites the
        original mesh file, then reloads the full scene.
        """
        from surg_rl.cutting.engine import cut_tetrahedral_mesh
        from surg_rl.utils.vtk_io import write_vtk_unstructured_grid

        tissue_name = cut_action.tissue_name
        if tissue_name not in self._soft_body_ids:
            logger.warning("Cut target '%s' is not a soft body", tissue_name)
            return

        mesh_key = tissue_name + "_tets"
        if mesh_key not in self._soft_body_tet_data:
            logger.warning("No tetrahedral mesh data stored for '%s'", tissue_name)
            return

        vertices, tetrahedra = self._soft_body_tet_data[mesh_key]

        cut_origin = np.array([
            cut_action.surface_point.x, cut_action.surface_point.y, cut_action.surface_point.z
        ])
        cut_dir = np.array([
            cut_action.direction.x, cut_action.direction.y, cut_action.direction.z
        ])

        new_verts, new_tets, _ = cut_tetrahedral_mesh(
            vertices, tetrahedra, cut_origin, cut_dir
        )

        mesh_path = self._soft_body_mesh_paths.get(tissue_name)
        if mesh_path is not None:
            write_vtk_unstructured_grid(mesh_path, new_verts, new_tets)
            self._soft_body_tet_data[mesh_key] = (new_verts, new_tets)

        from pybullet import RESET_USE_DEFORMABLE_WORLD
        self._pb.resetSimulation(RESET_USE_DEFORMABLE_WORLD)
        self._soft_body_ids.clear()
        self.load_scene(self._scene_definition)

    def apply_force(
        self,
        body_name: str,
        force: np.ndarray,
        torque: np.ndarray | None = None,
    ) -> bool:
        """Apply external force to a body."""
        if not self._loaded or body_name not in self._body_ids:
            return False
        body_id = self._body_ids[body_name]
        try:
            self._pb.applyExternalForce(
                body_id,
                -1,
                force.tolist(),
                self._pb.getBasePositionAndOrientation(
                    body_id, physicsClientId=self._physics_client
                )[0],
                self._pb.WORLD_FRAME,
                physicsClientId=self._physics_client,
            )
            if torque is not None:
                self._pb.applyExternalTorque(
                    body_id,
                    -1,
                    torque.tolist(),
                    self._pb.WORLD_FRAME,
                    physicsClientId=self._physics_client,
                )
            return True
        except Exception:
            return False

    def get_contact_points(self, body_name: str) -> list[dict[str, Any]]:
        """Get contact points for a body."""
        if not self._loaded or body_name not in self._body_ids:
            return []
        body_id = self._body_ids[body_name]
        contacts: list[dict[str, Any]] = []
        for other_name, other_id in self._body_ids.items():
            if other_name == body_name:
                continue
            points = self._pb.getContactPoints(
                bodyA=body_id,
                bodyB=other_id,
                physicsClientId=self._physics_client,
            )
            for point in points:
                contacts.append(
                    {
                        "body_a": body_name,
                        "body_b": other_name,
                        "position": np.array(point[5]),
                        "normal": np.array(point[7]),
                        "distance": float(point[8]),
                        "normal_force": float(point[9]),
                    }
                )
        return contacts

    def close(self) -> None:
        """Clean up simulator resources."""
        if self._physics_client is not None:
            self._pb.disconnect(physicsClientId=self._physics_client)
            self._physics_client = None

        self._body_ids.clear()
        self._joint_ids.clear()
        self._loaded = False
        self._mesh_cache.clear()
        self.scene_builder.cleanup()

    def _build_control_map(self) -> None:
        """Build mapping from flat action indices to PyBullet joint indices.

        Populates self._control_map with dicts:
        {"robot_name": str, "joint_name": str, "ctrl_index": int,
         "is_gripper": bool}
        """
        self._control_map = []
        if not self._loaded or not self._scene or not self._scene.robots:
            return
        ctrl_idx = 0
        for robot in self._scene.robots:
            joint_dict = self._joint_ids.get(robot.name, {})
            for joint_name in sorted(joint_dict.keys()):
                self._control_map.append(
                    {
                        "robot_name": robot.name,
                        "joint_name": joint_name,
                        "ctrl_index": ctrl_idx,
                        "is_gripper": False,
                    }
                )
                ctrl_idx += 1
            # Minimal gripper placeholder (TODO: implement real gripper actuation)
            if robot.end_effectors:
                self._control_map.append(
                    {
                        "robot_name": robot.name,
                        "joint_name": "gripper",
                        "ctrl_index": ctrl_idx,
                        "is_gripper": True,
                    }
                )
                ctrl_idx += 1

    def get_num_controls(self) -> int:
        """Return number of controllable DOFs."""
        if self._control_map:
            return len(self._control_map)
        total = 0
        for joints in self._joint_ids.values():
            total += len(joints)
        return total

    def _compute_ik(
        self, robot_name: str, target_pos: np.ndarray, target_quat: np.ndarray | None = None
    ) -> np.ndarray:
        """Compute inverse kinematics for a robot.

        Args:
            robot_name: Name of the robot.
            target_pos: Target end-effector position [x, y, z].
            target_quat: Target end-effector orientation quaternion [x, y, z, w].

        Returns:
            Flat array of joint angles. Falls back to current joint state on error.
        """
        if not self._loaded or robot_name not in self._body_ids:
            return np.array([], dtype=np.float32)
        body_id = self._body_ids[robot_name]
        if not hasattr(self._pb, "calculateInverseKinematics"):
            return self.get_robot_state(robot_name) or np.array([], dtype=np.float32)
        num_joints = self._pb.getNumJoints(body_id, physicsClientId=self._physics_client)
        ee_link_idx = max(0, num_joints - 1)
        try:
            if target_quat is not None:
                ik_solution = self._pb.calculateInverseKinematics(
                    body_id,
                    ee_link_idx,
                    target_pos.tolist(),
                    targetOrientation=target_quat.tolist(),
                    physicsClientId=self._physics_client,
                )
            else:
                ik_solution = self._pb.calculateInverseKinematics(
                    body_id,
                    ee_link_idx,
                    target_pos.tolist(),
                    physicsClientId=self._physics_client,
                )
            return np.array(ik_solution, dtype=np.float32)
        except Exception:
            return self.get_robot_state(robot_name) or np.array([], dtype=np.float32)

    def _apply_action(self, action: np.ndarray) -> None:
        """Apply action to the simulation.

        Args:
            action: Action vector with joint position targets.
        """
        if action is None or len(action) == 0:
            return

        if self._action_mode in ("endeffector_pose", "endeffector_delta"):
            self._apply_action_ik(action)
            return

        if self._control_map:
            for mapping in self._control_map:
                idx = mapping["ctrl_index"]
                if idx >= len(action):
                    continue
                if mapping.get("is_gripper"):
                    robot_name = mapping["robot_name"]
                    gripper_target = float(action[idx])
                    if robot_name in self._joint_ids and "gripper" in self._joint_ids[robot_name]:
                        body_id = self._body_ids[robot_name]
                        joint_idx = self._joint_ids[robot_name]["gripper"]
                        self._pb.setJointMotorControl2(
                            body_id,
                            joint_idx,
                            self._pb.POSITION_CONTROL,
                            targetPosition=gripper_target,
                            force=100.0,
                            physicsClientId=self._physics_client,
                        )
                    else:
                        logger.debug(
                            "Gripper actuation is not yet fully implemented for %s (TODO).",
                            robot_name,
                        )
                    continue
                robot_name = mapping["robot_name"]
                joint_name = mapping["joint_name"]
                if robot_name not in self._body_ids:
                    continue
                body_id = self._body_ids[robot_name]
                joint_idx = self._joint_ids[robot_name].get(joint_name)
                if joint_idx is None:
                    continue
                target = float(action[idx])
                if self._action_mode == "torque":
                    self._pb.setJointMotorControl2(
                        body_id,
                        joint_idx,
                        self._pb.TORQUE_CONTROL,
                        force=target,
                        physicsClientId=self._physics_client,
                    )
                else:
                    self._pb.setJointMotorControl2(
                        body_id,
                        joint_idx,
                        self._pb.POSITION_CONTROL,
                        targetPosition=target,
                        force=100.0,
                        physicsClientId=self._physics_client,
                    )
            return

        idx = 0
        for robot_name, joint_dict in self._joint_ids.items():
            if robot_name not in self._body_ids:
                continue
            body_id = self._body_ids[robot_name]
            for joint_name in sorted(joint_dict.keys()):
                if idx >= len(action):
                    break
                joint_idx = joint_dict[joint_name]
                target = float(action[idx])
                if self._action_mode == "torque":
                    self._pb.setJointMotorControl2(
                        body_id,
                        joint_idx,
                        self._pb.TORQUE_CONTROL,
                        force=target,
                        physicsClientId=self._physics_client,
                    )
                else:
                    self._pb.setJointMotorControl2(
                        body_id,
                        joint_idx,
                        self._pb.POSITION_CONTROL,
                        targetPosition=target,
                        force=100.0,
                        physicsClientId=self._physics_client,
                    )
                idx += 1

    def _apply_action_ik(self, action: np.ndarray) -> None:
        """Apply action using inverse kinematics for end-effector control.

        Args:
            action: Action vector where first 3 are [x,y,z] position (or delta),
                    next 3 are Euler angles (or delta), and optional last value
                    is gripper target.
        """
        if not self._scene or not self._scene.robots:
            return
        robot = self._scene.robots[0]
        robot_name = robot.name
        if robot_name not in self._body_ids:
            return

        body_id = self._body_ids[robot_name]
        current_pos, current_orn = self._pb.getBasePositionAndOrientation(
            body_id, physicsClientId=self._physics_client
        )
        current_pos = np.array(current_pos)
        current_orn = np.array(current_orn)

        if len(action) < 6:
            return

        pos_input = np.array(action[:3], dtype=np.float64)
        euler_input = np.array(action[3:6], dtype=np.float64)

        if self._action_mode == "endeffector_delta":
            target_pos = current_pos + pos_input
            current_euler = np.array(
                self._pb.getEulerFromQuaternion(current_orn.tolist()), dtype=np.float64
            )
            target_euler = current_euler + euler_input
            target_quat = np.array(
                self._pb.getQuaternionFromEuler(target_euler.tolist()), dtype=np.float64
            )
        else:
            target_pos = pos_input
            target_quat = np.array(
                self._pb.getQuaternionFromEuler(euler_input.tolist()), dtype=np.float64
            )

        ik_angles = self._compute_ik(robot_name, target_pos, target_quat)

        joint_dict = self._joint_ids.get(robot_name, {})
        joint_items = sorted(joint_dict.items(), key=lambda item: item[1])
        for i, (joint_name, joint_idx) in enumerate(joint_items):
            if i >= len(ik_angles):
                break
            if joint_name == "gripper":
                continue
            self._pb.setJointMotorControl2(
                body_id,
                joint_idx,
                self._pb.POSITION_CONTROL,
                targetPosition=float(ik_angles[i]),
                force=100.0,
                physicsClientId=self._physics_client,
            )

        if len(action) > 6 and "gripper" in joint_dict:
            gripper_target = float(action[6])
            joint_idx = joint_dict["gripper"]
            self._pb.setJointMotorControl2(
                body_id,
                joint_idx,
                self._pb.POSITION_CONTROL,
                targetPosition=gripper_target,
                force=100.0,
                physicsClientId=self._physics_client,
            )

    def _get_observation(self) -> Observation:
        """Get current observation."""
        import contextlib

        obs = Observation()

        # Render image
        with contextlib.suppress(Exception):
            obs.rgb_image = self.render("rgb_array")

        # Get body positions
        obs.tissue_state = {}
        for name, body_id in self._body_ids.items():
            pos, orn = self._pb.getBasePositionAndOrientation(
                body_id, physicsClientId=self._physics_client
            )
            obs.tissue_state[name] = np.concatenate([np.array(pos), np.array(orn)])

        # Get robot joint states
        joint_states = self.get_joint_states()
        if joint_states:
            all_positions = []
            for robot_name in sorted(joint_states.keys()):
                all_positions.append(joint_states[robot_name]["positions"])
            if all_positions:
                obs.robot_state = np.concatenate(all_positions)

        # Populate task-related observation fields if a task is defined
        self._resolve_task_observations(obs)

        # Collision detection: check contact points between any two bodies
        for i, body_a in enumerate(self._body_ids.values()):
            for body_b in list(self._body_ids.values())[i + 1 :]:
                contacts = self._pb.getContactPoints(
                    bodyA=body_a, bodyB=body_b, physicsClientId=self._physics_client
                )
                if contacts:
                    obs.collision_detected = True
                    break
            if obs.collision_detected:
                break

        # New observation fields (H7 wiring)
        obs.thread_tension = np.array([0.0])
        if self._scene is not None and self._scene.robots:
            contacts = self.get_contact_points(self._scene.robots[0].name)
            total_force = sum(c.get("normal_force", 0.0) for c in contacts)
            obs.cut_force = np.array([total_force])
        else:
            obs.cut_force = np.array([0.0])

        if self._scene is not None:
            if len(self._scene.instruments) > 1:
                pose = self.get_body_pose(self._scene.instruments[1].name)
                if pose is not None:
                    obs.receiver_pos = pose[0]
            elif len(self._scene.robots) > 1:
                pose = self.get_end_effector_pose(self._scene.robots[1].name)
                if pose is not None:
                    obs.receiver_pos = pose[0]

        if self._scene is not None and self._scene.robots:
            try:
                ee = self.get_end_effector_pose(self._scene.robots[0].name)
                if ee is not None:
                    obs.tool_positions = np.concatenate([ee[0], ee[1][:3]])
            except Exception:
                pass

        return obs

    def _resolve_task_observations(self, obs: Observation) -> None:
        """Populate task observation fields from scene task objectives."""
        if not (self._scene and self._scene.task and self._scene.task.objectives):
            return

        def _obs_field_for_name(name: str) -> str | None:
            name_lower = name.lower()
            if "needle" in name_lower:
                return "needle_pos"
            if "entry" in name_lower:
                return "entry_point"
            if "exit" in name_lower:
                return "exit_point"
            return None

        # Explicit target_body resolution (preferred)
        for objective in self._scene.task.objectives:
            target_body = getattr(objective, "target_body", None)
            if not target_body:
                continue
            field = _obs_field_for_name(objective.name)
            if field is None:
                continue
            if target_body not in self._body_ids:
                continue
            pos, _ = self._pb.getBasePositionAndOrientation(
                self._body_ids[target_body],
                physicsClientId=self._physics_client,
            )
            setattr(obs, field, np.array(pos))

        # Fallback: heuristic body name matching when no target_body or field still empty
        if self._body_ids:
            for name, body_id in self._body_ids.items():
                if name in ("needle",) and obs.needle_pos is None:
                    pos, _ = self._pb.getBasePositionAndOrientation(
                        body_id, physicsClientId=self._physics_client
                    )
                    obs.needle_pos = np.array(pos)
                if name in ("entry_point",) and obs.entry_point is None:
                    pos, _ = self._pb.getBasePositionAndOrientation(
                        body_id, physicsClientId=self._physics_client
                    )
                    obs.entry_point = np.array(pos)
                if name in ("exit_point",) and obs.exit_point is None:
                    pos, _ = self._pb.getBasePositionAndOrientation(
                        body_id, physicsClientId=self._physics_client
                    )
                    obs.exit_point = np.array(pos)

        # Compute incision progress from objectives completion ratio
        total = len(self._scene.task.objectives)
        completed = sum(
            1 for obj in self._scene.task.objectives
            if "complete" in obj.success_criteria.lower()
        )
        obs.incision_progress = completed / total if total > 0 else 0.0

    def _compute_reward(self) -> float:
        """Compute reward."""
        return 0.0

    def _check_termination(self) -> bool:
        """Check if simulation should terminate due to instability."""
        for name, body_id in self._body_ids.items():
            pos, orn = self._pb.getBasePositionAndOrientation(
                body_id, physicsClientId=self._physics_client
            )
            if any(np.isnan(p) for p in pos) or any(np.isnan(o) for o in orn):
                logger.warning(f"NaN detected in body {name}, terminating episode")
                return True
        return False

    def _check_truncation(self) -> bool:
        """Check truncation."""
        if self._scene and hasattr(self._scene, "task") and self._scene.task:
            max_time = 120.0 if self._scene.task.time_limit is None else self._scene.task.time_limit
            if self._simulation_time >= max_time:
                return True
        return False

    # ------------------------------------------------------------------ #
    #  Viewer methods (PyBullet – GUI is set at construction time)
    # ------------------------------------------------------------------ #

    def start_viewer(self, target_fps: float = 30.0) -> bool:
        """Return True if already in GUI mode; warn otherwise."""
        if self.render_mode == "GUI":
            return True
        logger.warning(
            "PyBullet human render requires GUI mode (render_mode='GUI'). "
            "DIRECT mode has no viewer."
        )
        return False

    def stop_viewer(self) -> None:
        """No-op for PyBullet – GUI mode manages its own lifecycle."""
        pass

"""PyBullet simulator backend implementation."""

import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from surg_rl.utils.logging import get_logger
from .base_simulator import BaseSimulator, Observation, State, StepResult
from .scene_builder import SceneBuilder

logger = get_logger(__name__)


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
        assets_dir: Optional[Union[str, Path]] = None,
        render_mode: str = "DIRECT",
    ):
        """Initialize PyBullet simulator.

        Args:
            timestep: Simulation timestep in seconds.
            frame_skip: Number of simulation steps per action.
            render_width: Width of rendered images.
            render_height: Height of rendered images.
            assets_dir: Directory containing asset files.
            render_mode: PyBullet connection mode ('DIRECT', 'GUI').
        """
        super().__init__(
            timestep=timestep,
            frame_skip=frame_skip,
            render_width=render_width,
            render_height=render_height,
        )
        self.assets_dir = Path(assets_dir) if assets_dir else None
        self.scene_builder = SceneBuilder(assets_dir=assets_dir)
        self.render_mode = render_mode

        self._physics_client = None
        self._body_ids: Dict[str, int] = {}
        self._joint_ids: Dict[str, Dict[str, int]] = {}
        self._initial_positions: Dict[str, list] = {}  # Store initial positions
        self._initial_orientations: Dict[str, list] = {}  # Store initial orientations

    def _check_pybullet(self) -> None:
        """Check if PyBullet is available."""
        try:
            import pybullet
            self._pb = pybullet
        except ImportError:
            raise ImportError(
                "PyBullet is not installed. Install it with: pip install pybullet"
            )

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
        if hasattr(scene_definition, 'physics') and scene_definition.physics:
            self.timestep = scene_definition.physics.timestep

        # Connect to physics server
        if self._physics_client is None:
            if self.render_mode == "GUI":
                self._physics_client = self._pb.connect(self._pb.GUI)
            else:
                self._physics_client = self._pb.connect(self._pb.DIRECT)
        else:
            # Clear previous bodies if reloading
            self._pb.resetSimulation(physicsClientId=self._physics_client)
            self._body_ids.clear()
            self._joint_ids.clear()
            self._initial_positions.clear()
            self._initial_orientations.clear()

        # Configure physics
        self._pb.setGravity(
            scene_definition.physics.gravity[0],
            scene_definition.physics.gravity[1],
            scene_definition.physics.gravity[2],
            physicsClientId=self._physics_client,
        )
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
        
        # Let objects settle by stepping simulation a few times
        # This prevents objects from having initial velocities that cause them to fly off
        for _ in range(100):
            self._pb.stepSimulation(physicsClientId=self._physics_client)
        
        logger.info(f"Loaded scene: {scene_definition.metadata.name}")

    def _load_robot(self, robot: Any) -> None:
        """Load a robot into the simulation."""
        # Try to load URDF or use primitive
        if robot.urdf_path:
            resolved = self.scene_builder._resolve_asset_path(robot.urdf_path)
            if resolved:
                try:
                    body_id = self._pb.loadURDF(
                        str(resolved),
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
                    return
                except Exception as e:
                    logger.warning(f"Failed to load robot URDF: {e}. Using primitive.")

        # Create primitive collision shape
        collision_shape = self._pb.createCollisionShape(
            self._pb.GEOM_BOX,
            halfExtents=[0.05, 0.05, 0.1],
            physicsClientId=self._physics_client,
        )
        visual_shape = self._pb.createVisualShape(
            self._pb.GEOM_BOX,
            halfExtents=[0.05, 0.05, 0.1],
            rgbaColor=[0.3, 0.3, 0.8, 1.0],
            physicsClientId=self._physics_client,
        )

        body_id = self._pb.createMultiBody(
            baseMass=0.0,  # Static (no joint control implemented yet)
            baseCollisionShapeIndex=collision_shape,
            baseVisualShapeIndex=visual_shape,
            basePosition=[
                robot.base_pose.position.x,
                robot.base_pose.position.y,
                robot.base_pose.position.z,
            ],
            physicsClientId=self._physics_client,
        )
        self._body_ids[robot.name] = body_id
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

    def _load_tissue(self, tissue: Any) -> None:
        """Load a tissue into the simulation."""
        # Get geometry
        if tissue.geometry.primitive == "box":
            dims = tissue.geometry.dimensions or (0.1, 0.1, 0.01)
            shape_type = self._pb.GEOM_BOX
            half_extents = [d / 2 for d in dims]
        elif tissue.geometry.primitive == "sphere":
            r = tissue.geometry.radius or 0.05
            shape_type = self._pb.GEOM_SPHERE
            half_extents = [r]
        elif tissue.geometry.primitive == "cylinder":
            shape_type = self._pb.GEOM_CYLINDER
            dims = tissue.geometry.dimensions or (0.05, 0.05, 0.1)
            half_extents = [dims[2] / 2, dims[0] / 2]  # height, radius
        else:
            # Default to box
            dims = tissue.geometry.dimensions or (0.1, 0.1, 0.01)
            shape_type = self._pb.GEOM_BOX
            half_extents = [d / 2 for d in dims]

        # Create shapes - only pass the relevant parameters for each shape type
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
            # For cylinder: half_extents = [height/2, radius]
            collision_shape = self._pb.createCollisionShape(
                shape_type,
                radius=half_extents[1],  # radius
                height=half_extents[0] * 2,  # full height
                physicsClientId=self._physics_client,
            )

        # Get color
        color = [0.95, 0.85, 0.8, 1.0]  # Default skin color
        if tissue.color:
            color = [tissue.color.r, tissue.color.g, tissue.color.b, tissue.color.a]

        # Create visual shape - only pass the relevant parameters for each shape type
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
                length=half_extents[0] * 2,  # PyBullet uses 'length' for cylinders
                rgbaColor=color,
                physicsClientId=self._physics_client,
            )

        body_id = self._pb.createMultiBody(
            baseMass=0.0,  # Static (attached to ground in scene)
            baseCollisionShapeIndex=collision_shape,
            baseVisualShapeIndex=visual_shape,
            basePosition=[
                tissue.pose.position.x,
                tissue.pose.position.y,
                tissue.pose.position.z,
            ],
            physicsClientId=self._physics_client,
        )
        self._body_ids[tissue.name] = body_id
        # Store initial position for reset
        self._initial_positions[tissue.name] = [
            tissue.pose.position.x,
            tissue.pose.position.y,
            tissue.pose.position.z,
        ]
        self._initial_orientations[tissue.name] = [
            tissue.pose.orientation.x,
            tissue.pose.orientation.y,
            tissue.pose.orientation.z,
            tissue.pose.orientation.w,
        ]

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

        body_id = self._pb.createMultiBody(
            baseMass=0.0,  # Static (no control implemented yet)
            baseCollisionShapeIndex=collision_shape,
            baseVisualShapeIndex=visual_shape,
            basePosition=[
                instrument.pose.position.x,
                instrument.pose.position.y,
                instrument.pose.position.z,
            ],
            physicsClientId=self._physics_client,
        )
        self._body_ids[instrument.name] = body_id
        # Store initial position for reset
        self._initial_positions[instrument.name] = [
            instrument.pose.position.x,
            instrument.pose.position.y,
            instrument.pose.position.z,
        ]
        self._initial_orientations[instrument.name] = [
            instrument.pose.orientation.x,
            instrument.pose.orientation.y,
            instrument.pose.orientation.z,
            instrument.pose.orientation.w,
        ]

    def _load_environment(self, scene_definition: Any) -> None:
        """Load environment elements."""
        # Load ground plane
        if (
            hasattr(scene_definition, "physics")
            and scene_definition.physics is not None
            and scene_definition.physics.ground_plane
        ):
            try:
                import pybullet_data
                self._pb.setAdditionalSearchPath(pybullet_data.getDataPath())
            except ImportError:
                logger.warning("pybullet_data not available; ground plane URDF may fail to load")
            ground_id = self._pb.loadURDF(
                "plane.urdf",
                physicsClientId=self._physics_client,
            )

    def reset(self, seed: Optional[int] = None) -> Observation:
        """Reset the simulation."""
        if not self._loaded:
            raise RuntimeError("Scene not loaded. Call load_scene() first.")

        if seed is not None:
            np.random.seed(seed)

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
            self._pb.resetBaseVelocity(body_id, [0, 0, 0], [0, 0, 0], physicsClientId=self._physics_client)

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

        info = {"simulation_time": self._simulation_time}

        return StepResult(observation=obs, reward=reward, terminated=terminated, truncated=truncated, info=info)

    def render(self, mode: str = "rgb_array", width: Optional[int] = None, height: Optional[int] = None, camera_name: Optional[str] = None) -> Optional[np.ndarray]:
        """Render the current simulation state."""
        if not self._loaded:
            return None

        width = width or self.render_width
        height = height or self.render_height

        if mode == "human":
            # Already handled by GUI mode
            return None

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

        _, _, rgb, _, _ = self._pb.getCameraImage(
            width=width,
            height=height,
            viewMatrix=view_matrix,
            projectionMatrix=proj_matrix,
            physicsClientId=self._physics_client,
        )

        return rgb[:, :, :3]  # Remove alpha channel

    def get_state(self) -> State:
        """Get current simulation state."""
        if not self._loaded:
            return State()

        # Get all body positions/orientations
        body_positions = {}
        body_orientations = {}

        for name, body_id in self._body_ids.items():
            pos, orn = self._pb.getBasePositionAndOrientation(body_id, physicsClientId=self._physics_client)
            body_positions[name] = np.array(pos)
            body_orientations[name] = np.array(orn)

        return State(
            time=self._simulation_time,
            body_positions=body_positions,
            body_orientations=body_orientations,
        )

    def set_state(self, state: State) -> None:
        """Restore simulation state."""
        if not self._loaded:
            return

        self._simulation_time = state.time

        for name, pos in state.body_positions.items():
            if name in self._body_ids:
                orn = state.body_orientations.get(name, [0, 0, 0, 1])
                self._pb.resetBasePositionAndOrientation(
                    self._body_ids[name],
                    pos.tolist(),
                    orn.tolist() if hasattr(orn, 'tolist') else orn,
                    physicsClientId=self._physics_client,
                )

    def close(self) -> None:
        """Clean up simulator resources."""
        if self._physics_client is not None:
            self._pb.disconnect(physicsClientId=self._physics_client)
            self._physics_client = None

        self._body_ids.clear()
        self._joint_ids.clear()
        self._loaded = False
        self.scene_builder.cleanup()

    def _apply_action(self, action: np.ndarray) -> None:
        """Apply action to the simulation."""
        # Placeholder - would set joint targets
        pass

    def _get_observation(self) -> Observation:
        """Get current observation."""
        obs = Observation()

        # Render image
        try:
            obs.rgb_image = self.render("rgb_array")
        except Exception:
            pass

        # Get body positions
        obs.tissue_state = {}
        for name, body_id in self._body_ids.items():
            pos, orn = self._pb.getBasePositionAndOrientation(body_id, physicsClientId=self._physics_client)
            obs.tissue_state[name] = np.concatenate([np.array(pos), np.array(orn)])

        return obs

    def _compute_reward(self) -> float:
        """Compute reward."""
        return 0.0

    def _check_termination(self) -> bool:
        """Check termination."""
        return False

    def _check_truncation(self) -> bool:
        """Check truncation."""
        if self._scene and hasattr(self._scene, 'task') and self._scene.task:
            max_time = 120.0 if self._scene.task.time_limit is None else self._scene.task.time_limit
            if self._simulation_time >= max_time:
                return True
        return False

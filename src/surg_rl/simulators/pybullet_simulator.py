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
        self._control_map: List[Dict[str, Any]] = []
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
        if (
            hasattr(scene_definition, "physics")
            and scene_definition.physics is not None
            and hasattr(scene_definition.physics, "gravity")
        ):
            self._pb.setGravity(
                scene_definition.physics.gravity[0],
                scene_definition.physics.gravity[1],
                scene_definition.physics.gravity[2],
                physicsClientId=self._physics_client,
            )
            if hasattr(scene_definition.physics, "timestep"):
                self._pb.setTimeStep(
                    scene_definition.physics.timestep,
                    physicsClientId=self._physics_client,
                )
        else:
            self._pb.setGravity(0, 0, -9.81, physicsClientId=self._physics_client)

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
            resolved = self.scene_builder.resolve_asset_path(robot.urdf_path)
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
                    self._collect_joint_info(robot.name, body_id)
                    return
                except Exception as e:
                    logger.warning(f"Failed to load robot URDF: {e}. Using primitive.")

        # Primitive fallback: create a base + 1-DOF revolute joint
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
            linkMasses=[0.5],
            linkCollisionShapeIndices=[link_collision],
            linkVisualShapeIndices=[link_visual],
            linkPositions=[[0.0, 0.0, 0.15]],
            linkOrientations=[[0.0, 0.0, 0.0, 1.0]],
            linkInertialFramePositions=[[0.0, 0.0, 0.0]],
            linkInertialFrameOrientations=[[0.0, 0.0, 0.0, 1.0]],
            linkParentIndices=[0],
            linkJointTypes=[self._pb.JOINT_REVOLUTE],
            linkJointAxis=[[0.0, 1.0, 0.0]],
            physicsClientId=self._physics_client,
        )
        self._body_ids[robot.name] = body_id
        self._collect_joint_info(robot.name, body_id)
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
        joint_dict: Dict[str, int] = {}
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
        # Get geometry
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
            # Default to box
            dims = tissue.geometry.dimensions or (0.1, 0.1, 0.01) if tissue.geometry is not None else (0.1, 0.1, 0.01)
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
        if hasattr(tissue, "color") and tissue.color is not None:
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
            baseMass=0.0,  # Static (attached to ground in scene)
            baseCollisionShapeIndex=collision_shape,
            baseVisualShapeIndex=visual_shape,
            basePosition=list(position),
            physicsClientId=self._physics_client,
        )
        self._body_ids[tissue.name] = body_id
        # Store initial position for reset
        self._initial_positions[tissue.name] = list(position)
        self._initial_orientations[tissue.name] = list(orientation)

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

        # Get joint states
        joint_states = self.get_joint_states()
        qpos_list = []
        qvel_list = []
        for robot_name, states in joint_states.items():
            qpos_list.append(states["positions"])
            qvel_list.append(states["velocities"])

        qpos = np.concatenate(qpos_list) if qpos_list else None
        qvel = np.concatenate(qvel_list) if qvel_list else None

        return State(
            time=self._simulation_time,
            qpos=qpos,
            qvel=qvel,
            body_positions=body_positions,
            body_orientations=body_orientations,
        )

    def get_joint_states(self) -> Dict[str, Dict[str, np.ndarray]]:
        """Get joint positions and velocities for all robots.

        Returns:
            Dictionary mapping robot name to {'positions': array, 'velocities': array}.
        """
        result: Dict[str, Dict[str, np.ndarray]] = {}
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
                state = self._pb.getJointState(body_id, joint_idx, physicsClientId=self._physics_client)
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

    def _apply_action(self, action: np.ndarray) -> None:
        """Apply action to the simulation.

        Args:
            action: Action vector with joint position targets.
        """
        if action is None or len(action) == 0:
            return

        # Use mapping if available
        if self._control_map:
            for mapping in self._control_map:
                idx = mapping["ctrl_index"]
                if idx >= len(action):
                    continue
                if mapping.get("is_gripper"):
                    continue  # TODO real gripper actuation
                robot_name = mapping["robot_name"]
                joint_name = mapping["joint_name"]
                if robot_name not in self._body_ids:
                    continue
                body_id = self._body_ids[robot_name]
                joint_idx = self._joint_ids[robot_name].get(joint_name)
                if joint_idx is None:
                    continue
                target = float(action[idx])
                self._pb.setJointMotorControl2(
                    body_id,
                    joint_idx,
                    self._pb.POSITION_CONTROL,
                    targetPosition=target,
                    force=100.0,
                    physicsClientId=self._physics_client,
                )
            return

        # Fallback sequential
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
                self._pb.setJointMotorControl2(
                    body_id,
                    joint_idx,
                    self._pb.POSITION_CONTROL,
                    targetPosition=target,
                    force=100.0,
                    physicsClientId=self._physics_client,
                )
                idx += 1

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

        # Get robot joint states
        joint_states = self.get_joint_states()
        if joint_states:
            all_positions = []
            for robot_name in sorted(joint_states.keys()):
                all_positions.append(joint_states[robot_name]["positions"])
            if all_positions:
                obs.robot_state = np.concatenate(all_positions)

        return obs

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
        if self._scene and hasattr(self._scene, 'task') and self._scene.task:
            max_time = 120.0 if self._scene.task.time_limit is None else self._scene.task.time_limit
            if self._simulation_time >= max_time:
                return True
        return False

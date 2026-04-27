"""MuJoCo simulator backend implementation."""

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from surg_rl.utils.logging import get_logger
from .base_simulator import BaseSimulator, Observation, State, StepResult
from .scene_builder import SceneBuilder

logger = get_logger(__name__)


class MuJoCoSimulator(BaseSimulator):
    """MuJoCo physics simulator backend.

    This simulator uses MuJoCo (MuJoCo Physics Engine) for physics simulation.
    It converts scene definitions to MJCF (MuJoCo XML) format and handles
    rendering through MuJoCo's built-in renderer.
    """

    def __init__(
        self,
        timestep: float = 0.002,
        frame_skip: int = 1,
        render_width: int = 640,
        render_height: int = 480,
        assets_dir: Optional[Union[str, Path]] = None,
    ):
        """Initialize MuJoCo simulator.

        Args:
            timestep: Simulation timestep in seconds.
            frame_skip: Number of simulation steps per action.
            render_width: Width of rendered images.
            render_height: Height of rendered images.
            assets_dir: Directory containing asset files.
        """
        super().__init__(
            timestep=timestep,
            frame_skip=frame_skip,
            render_width=render_width,
            render_height=render_height,
        )
        self.assets_dir = Path(assets_dir) if assets_dir else None
        self.scene_builder = SceneBuilder(assets_dir=assets_dir)

        self._model = None
        self._data = None
        self._viewer = None
        self._renderer = None
        self._mjcf_path: Optional[Path] = None
        self._renderer_available: Optional[bool] = None
        self._control_map: List[Dict[str, Any]] = []

    def _check_mujoco(self) -> None:
        """Check if MuJoCo is available."""
        try:
            import mujoco
            self._mujoco = mujoco
        except ImportError:
            raise ImportError(
                "MuJoCo is not installed. Install it with: pip install mujoco"
            )

    def _check_renderer_available(self) -> bool:
        """Check if rendering is available (requires display or EGL)."""
        if self._renderer_available is not None:
            return self._renderer_available
        
        # Check if we have a display
        if os.environ.get('DISPLAY') or os.environ.get('PYOPENGL_PLATFORM'):
            self._renderer_available = True
            return True
        
        # On macOS, check if we have a display connection
        import platform
        if platform.system() == 'Darwin':
            # macOS uses CGL, not EGL
            # If we're in a terminal without display, rendering won't work
            # We'll try to detect this, but default to False for headless
            import sys
            if sys.stdout.isatty():
                # We're in a terminal, likely no GUI
                self._renderer_available = False
            else:
                self._renderer_available = True
            return self._renderer_available
        
        # For Linux, try EGL for headless GPU rendering
        try:
            from OpenGL import EGL
            self._renderer_available = True
        except Exception:
            self._renderer_available = False
        
        return self._renderer_available

    def load_scene(self, scene_definition: Any) -> None:
        """Load a scene definition into MuJoCo.

        Args:
            scene_definition: SceneDefinition object.

        Raises:
            ImportError: If MuJoCo is not installed.
            RuntimeError: If scene cannot be loaded.
        """
        self._check_mujoco()

        self._scene = scene_definition

        # Use scene's timestep if specified
        if hasattr(scene_definition, 'physics') and scene_definition.physics:
            self.timestep = scene_definition.physics.timestep

        # Build MJCF from scene
        self._mjcf_path = self.scene_builder.create_mjcf(scene_definition)

        # Load model
        try:
            self._model = self._mujoco.MjModel.from_xml_path(str(self._mjcf_path))
            self._data = self._mujoco.MjData(self._model)
            self._loaded = True
            self._build_control_map()
            logger.info(f"Loaded scene: {scene_definition.metadata.name}")
        except Exception as e:
            logger.error(f"Failed to load MuJoCo model: {e}")
            raise RuntimeError(f"Failed to load MuJoCo model: {e}")

    def _build_control_map(self) -> None:
        """Build mapping from flat action indices to MuJoCo ctrl indices.

        Populates self._control_map with dicts:
        {"robot_name": str, "joint_name": str, "ctrl_index": int,
         "is_gripper": bool}
        """
        self._control_map = []
        if not self._loaded or not self._scene or not self._scene.robots:
            return
        for robot in self._scene.robots:
            if robot.joints:
                for joint in robot.joints:
                    ctrl_name = f"{joint.name}_motor"
                    try:
                        ctrl_idx = self._mujoco.mj_name2id(
                            self._model, self._mujoco.mjtObj.mjOBJ_ACTUATOR, ctrl_name
                        )
                        if ctrl_idx >= 0:
                            self._control_map.append(
                                {
                                    "robot_name": robot.name,
                                    "joint_name": joint.name,
                                    "ctrl_index": ctrl_idx,
                                    "is_gripper": False,
                                }
                            )
                    except Exception:
                        pass
            else:
                ctrl_name = f"{robot.name}_motor"
                try:
                    ctrl_idx = self._mujoco.mj_name2id(
                        self._model, self._mujoco.mjtObj.mjOBJ_ACTUATOR, ctrl_name
                    )
                    if ctrl_idx >= 0:
                        self._control_map.append(
                            {
                                "robot_name": robot.name,
                                "joint_name": f"{robot.name}_joint",
                                "ctrl_index": ctrl_idx,
                                "is_gripper": False,
                            }
                        )
                except Exception:
                    pass
            # Minimal gripper placeholder (TODO: implement real gripper actuation)
            if robot.end_effectors and self._data is not None:
                if len(self._data.ctrl) > len(self._control_map):
                    self._control_map.append(
                        {
                            "robot_name": robot.name,
                            "joint_name": "gripper",
                            "ctrl_index": len(self._control_map),
                            "is_gripper": True,
                        }
                    )

    def get_num_controls(self) -> int:
        """Return number of controllable DOFs."""
        if self._control_map:
            return len(self._control_map)
        if self._loaded and hasattr(self._data, "ctrl"):
            return len(self._data.ctrl)
        return 0

    def reset(self, seed: Optional[int] = None) -> Observation:
        """Reset the simulation to initial state.

        Args:
            seed: Random seed for reproducibility.

        Returns:
            Initial observation.
        """
        if not self._loaded:
            raise RuntimeError("Scene not loaded. Call load_scene() first.")

        if seed is not None:
            self._seed = seed
            self._rng = np.random.default_rng(seed)

        self._mujoco.mj_resetData(self._model, self._data)
        self._simulation_time = 0.0

        return self._get_observation()

    def step(self, action: np.ndarray) -> StepResult:
        """Execute one simulation step.

        Args:
            action: Action vector (robot controls).

        Returns:
            StepResult with observation, reward, and done flags.
        """
        if not self._loaded:
            raise RuntimeError("Scene not loaded. Call load_scene() first.")

        # Apply action
        if action is not None:
            self._apply_action(action)

        # Step simulation
        for _ in range(self.frame_skip):
            self._mujoco.mj_step(self._model, self._data)

        self._simulation_time += self.timestep * self.frame_skip

        # Get observation
        obs = self._get_observation()

        # Compute reward (placeholder - should be task-specific)
        reward = self._compute_reward()

        # Check termination
        terminated = self._check_termination()
        truncated = self._check_truncation()

        # Info
        info = {
            "simulation_time": self._simulation_time,
            "robot_positions": self._data.qpos.copy() if self._data.qpos is not None else None,
        }

        return StepResult(
            observation=obs,
            reward=reward,
            terminated=terminated,
            truncated=truncated,
            info=info,
        )

    def render(
        self,
        mode: str = "rgb_array",
        width: Optional[int] = None,
        height: Optional[int] = None,
        camera_name: Optional[str] = None,
    ) -> Optional[np.ndarray]:
        """Render the current simulation state.

        Args:
            mode: Rendering mode ('rgb_array', 'depth_array', 'human').
            width: Image width.
            height: Image height.
            camera_name: Camera to render from.

        Returns:
            Rendered image or None for 'human' mode.
        """
        if not self._loaded:
            return None

        width = width or self.render_width
        height = height or self.render_height

        if mode == "human":
            # Use passive viewer for GUI rendering
            # This requires running in an event loop context
            if self._viewer is not None:
                self._viewer.sync()
            return None

        # Offscreen rendering using mujoco.Renderer (MuJoCo 3.x API)
        if not self._check_renderer_available():
            logger.debug("Rendering not available (no display)")
            return None

        try:
            # Initialize renderer if needed
            if self._renderer is None:
                self._renderer = self._mujoco.Renderer(
                    self._model,
                    height=height,
                    width=width,
                )
            elif self._renderer.width != width or self._renderer.height != height:
                # Recreate renderer with new dimensions
                try:
                    self._renderer.close()
                except Exception:
                    pass
                self._renderer = self._mujoco.Renderer(
                    self._model,
                    height=height,
                    width=width,
                )

            # Update scene and render
            self._mujoco.mj_forward(self._model, self._data)
            self._renderer.update_scene(self._data)
            
            if mode == "depth_array":
                # Get depth image
                depth = self._renderer.render(depth=True)
                return depth
            else:
                # Get RGB image
                rgb = self._renderer.render()
                return rgb

        except Exception as e:
            logger.debug(f"Rendering failed: {e}")
            return None

    def get_state(self) -> State:
        """Get current simulation state.

        Returns:
            State object with all state information.
        """
        if not self._loaded:
            return State()

        # Collect body positions/orientations
        body_positions: Dict[str, np.ndarray] = {}
        body_orientations: Dict[str, np.ndarray] = {}
        if self._scene:
            for robot in self._scene.robots:
                pose = self.get_body_pose(robot.name)
                if pose is not None:
                    body_positions[robot.name] = pose[0]
                    body_orientations[robot.name] = pose[1]
            for tissue in self._scene.tissues:
                pose = self.get_body_pose(tissue.name)
                if pose is not None:
                    body_positions[tissue.name] = pose[0]
                    body_orientations[tissue.name] = pose[1]
            for instrument in self._scene.instruments:
                pose = self.get_body_pose(instrument.name)
                if pose is not None:
                    body_positions[instrument.name] = pose[0]
                    body_orientations[instrument.name] = pose[1]

        return State(
            time=self._simulation_time,
            qpos=self._data.qpos.copy() if self._data.qpos is not None else None,
            qvel=self._data.qvel.copy() if self._data.qvel is not None else None,
            mocap_pos=self._data.mocap_pos.copy() if hasattr(self._data, 'mocap_pos') else None,
            mocap_quat=self._data.mocap_quat.copy() if hasattr(self._data, 'mocap_quat') else None,
            body_positions=body_positions,
            body_orientations=body_orientations,
        )

    def get_joint_states(self) -> Dict[str, Dict[str, np.ndarray]]:
        """Get joint positions and velocities for all robots.

        Returns:
            Dictionary mapping robot name to {'positions': array, 'velocities': array}.
        """
        result: Dict[str, Dict[str, np.ndarray]] = {}
        if not self._loaded or self._scene is None:
            return result

        for robot in self._scene.robots:
            # Map robot joints to qpos indices
            # For MVP, assume a single joint per robot; in full implementation
            # we would parse joint addresses from the model.
            joint_positions = []
            joint_velocities = []
            if robot.joints:
                for joint in robot.joints:
                    try:
                        joint_id = self._mujoco.mj_name2id(
                            self._model, self._mujoco.mjtObj.mjOBJ_JOINT, joint.name
                        )
                        qpos_adr = self._model.jnt_qposadr[joint_id]
                        qvel_adr = self._model.jnt_dofadr[joint_id]
                        joint_positions.append(self._data.qpos[qpos_adr])
                        joint_velocities.append(self._data.qvel[qvel_adr])
                    except (ValueError, KeyError):
                        continue
            else:
                # Default single joint fallback
                try:
                    joint_id = self._mujoco.mj_name2id(
                        self._model, self._mujoco.mjtObj.mjOBJ_JOINT, f"{robot.name}_joint"
                    )
                    qpos_adr = self._model.jnt_qposadr[joint_id]
                    qvel_adr = self._model.jnt_dofadr[joint_id]
                    joint_positions.append(self._data.qpos[qpos_adr])
                    joint_velocities.append(self._data.qvel[qvel_adr])
                except (ValueError, KeyError):
                    continue
            if joint_positions:
                result[robot.name] = {
                    "positions": np.array(joint_positions, dtype=np.float32),
                    "velocities": np.array(joint_velocities, dtype=np.float32),
                }
        return result

    def set_state(self, state: State) -> None:
        """Restore simulation state.

        Args:
            state: State object to restore.
        """
        if not self._loaded:
            return

        self._simulation_time = state.time

        if state.qpos is not None:
            self._data.qpos[:] = state.qpos
        if state.qvel is not None:
            self._data.qvel[:] = state.qvel
        if state.mocap_pos is not None and hasattr(self._data, 'mocap_pos'):
            self._data.mocap_pos[:] = state.mocap_pos
        if state.mocap_quat is not None and hasattr(self._data, 'mocap_quat'):
            self._data.mocap_quat[:] = state.mocap_quat

        self._mujoco.mj_forward(self._model, self._data)

    def close(self) -> None:
        """Clean up simulator resources."""
        if self._viewer is not None:
            self._viewer = None

        if self._renderer is not None:
            try:
                self._renderer.close()
            except Exception:
                pass
            self._renderer = None

        self._model = None
        self._data = None
        self._loaded = False

        # Clean up scene builder temp files
        self.scene_builder.cleanup()

    def _build_control_map(self) -> None:
        """Build mapping from flat action indices to MuJoCo ctrl indices.

        Populates self._control_map with dicts:
        {"robot_name": str, "joint_name": str, "ctrl_index": int,
         "is_gripper": bool}
        """
        self._control_map = []
        if not self._loaded or not self._scene or not self._scene.robots:
            return
        for robot in self._scene.robots:
            if robot.joints:
                for joint in robot.joints:
                    ctrl_name = f"{joint.name}_motor"
                    try:
                        ctrl_idx = self._mujoco.mj_name2id(
                            self._model, self._mujoco.mjtObj.mjOBJ_ACTUATOR, ctrl_name
                        )
                        if ctrl_idx >= 0:
                            self._control_map.append(
                                {
                                    "robot_name": robot.name,
                                    "joint_name": joint.name,
                                    "ctrl_index": ctrl_idx,
                                    "is_gripper": False,
                                }
                            )
                    except Exception:
                        pass
            else:
                ctrl_name = f"{robot.name}_motor"
                try:
                    ctrl_idx = self._mujoco.mj_name2id(
                        self._model, self._mujoco.mjtObj.mjOBJ_ACTUATOR, ctrl_name
                    )
                    if ctrl_idx >= 0:
                        self._control_map.append(
                            {
                                "robot_name": robot.name,
                                "joint_name": f"{robot.name}_joint",
                                "ctrl_index": ctrl_idx,
                                "is_gripper": False,
                            }
                        )
                except Exception:
                    pass
            # Minimal gripper placeholder (TODO: implement real gripper actuation)
            if robot.end_effectors and self._data is not None:
                if len(self._data.ctrl) > len(self._control_map):
                    self._control_map.append(
                        {
                            "robot_name": robot.name,
                            "joint_name": "gripper",
                            "ctrl_index": len(self._control_map),
                            "is_gripper": True,
                        }
                    )

    def get_num_controls(self) -> int:
        """Return number of controllable DOFs."""
        if self._control_map:
            return len(self._control_map)
        if self._loaded and hasattr(self._data, "ctrl"):
            return len(self._data.ctrl)
        return 0

    def _apply_action(self, action: np.ndarray) -> None:
        """Apply action to the simulation.

        Args:
            action: Action vector.
        """
        if action is None or len(action) == 0:
            return

        if self._control_map:
            for i, mapping in enumerate(self._control_map):
                if i < len(action):
                    ctrl_idx = mapping["ctrl_index"]
                    if ctrl_idx < len(self._data.ctrl):
                        self._data.ctrl[ctrl_idx] = action[i]
            return

        # Fallback: apply sequentially
        if hasattr(self._data, 'ctrl') and len(self._data.ctrl) > 0:
            n_controls = min(len(action), len(self._data.ctrl))
            self._data.ctrl[:n_controls] = action[:n_controls]

    def _get_observation(self) -> Observation:
        """Get current observation.

        Returns:
            Observation object.
        """
        obs = Observation()

        # Only render if renderer is available
        if self._check_renderer_available():
            try:
                obs.rgb_image = self.render("rgb_array")
            except Exception:
                pass

        # Get robot state
        joint_states = self.get_joint_states()
        if joint_states:
            all_positions = []
            for robot_name in sorted(joint_states.keys()):
                all_positions.append(joint_states[robot_name]["positions"])
            if all_positions:
                obs.robot_state = np.concatenate(all_positions)
        elif self._data.qpos is not None:
            obs.robot_state = self._data.qpos.copy()

        # Get end effector position (simplified)
        if hasattr(self._data, 'xpos') and len(self._data.xpos) > 0:
            obs.end_effector_pos = self._data.xpos[-1].copy()

        # Collision detection: count MuJoCo contacts with non-zero force
        if hasattr(self._data, 'ncon') and self._data.ncon > 0:
            for c in range(self._data.ncon):
                con = self._data.contact[c]
                # Distances <= 0 indicate penetration (active contact)
                if hasattr(con, 'dist') and con.dist <= 0:
                    obs.collision_detected = True
                    break

        return obs

    def _compute_reward(self) -> float:
        """Compute reward (placeholder for task-specific rewards).

        Returns:
            Reward value.
        """
        # This should be overridden by task-specific implementations
        return 0.0

    def _check_termination(self) -> bool:
        """Check if episode should terminate.

        Returns:
            True if terminated.
        """
        # Check for simulation errors
        if self._data is None:
            return True

        # Check for NaN
        if np.any(np.isnan(self._data.qpos)) or np.any(np.isnan(self._data.qvel)):
            logger.warning("NaN detected in simulation state")
            return True

        return False

    def _check_truncation(self) -> bool:
        """Check if episode should be truncated.

        Returns:
            True if truncated.
        """
        # Check time limit
        if self._scene and hasattr(self._scene, 'task') and self._scene.task:
            max_time = 120.0 if self._scene.task.time_limit is None else self._scene.task.time_limit
            if self._simulation_time >= max_time:
                return True

        return False

    def get_body_pose(self, body_name: str) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """Get pose of a named body.

        Args:
            body_name: Name of the body.

        Returns:
            Tuple of (position, quaternion) or None.
        """
        if not self._loaded:
            return None

        try:
            body_id = self._mujoco.mj_name2id(
                self._model, self._mujoco.mjtObj.mjOBJ_BODY, body_name
            )
            pos = self._data.xpos[body_id].copy()
            quat = self._data.xquat[body_id].copy()
            return pos, quat
        except (ValueError, KeyError):
            return None

    def get_tissue_deformation(self, tissue_name: str) -> Optional[np.ndarray]:
        """Get vertex displacements for a soft body tissue.

        Args:
            tissue_name: Name of the tissue.

        Returns:
            Array of vertex displacements from rest shape (N, 3) or None.
        """
        if not self._loaded:
            return None

        try:
            # MuJoCo flex bodies store vertices in the flex data
            flex_id = self._mujoco.mj_name2id(
                self._model,
                self._mujoco.mjtObj.mjOBJ_FLEX,
                f"{tissue_name}_flex",
            )
            if flex_id < 0:
                return None

            # Get flex vertex positions
            flex_start = self._model.flex_vertadr[flex_id]
            flex_num = self._model.flex_vertnum[flex_id]
            current_pos = self._data.flexvert_xpos[flex_start : flex_start + flex_num].copy()

            # Rest positions are stored in model
            rest_pos = self._model.flex_vert[flex_start : flex_start + flex_num].copy()

            # Compute displacement
            displacements = current_pos - rest_pos
            return displacements
        except (ValueError, KeyError, AttributeError):
            # Fallback: flex API may not be available in all MuJoCo versions
            return None

    def apply_force(
        self,
        body_name: str,
        force: np.ndarray,
        torque: Optional[np.ndarray] = None,
    ) -> bool:
        """Apply external force to a body.

        Args:
            body_name: Name of the body.
            force: Force vector (fx, fy, fz).
            torque: Torque vector (tx, ty, tz).

        Returns:
            True if successful.
        """
        if not self._loaded:
            return False

        try:
            body_id = self._mujoco.mj_name2id(
                self._model, self._mujoco.mjtObj.mjOBJ_BODY, body_name
            )
            self._data.xfrc_applied[body_id, :3] = force
            if torque is not None:
                self._data.xfrc_applied[body_id, 3:] = torque
            return True
        except (ValueError, KeyError):
            return False

    def start_viewer(self):
        """Start an interactive viewer for the simulation.
        
        This method launches a passive viewer that can be used for
        real-time visualization. Must be called before the simulation loop.
        
        Example:
            sim.load_scene(scene)
            sim.start_viewer()
            for i in range(1000):
                sim.step(action)
                sim.render(mode='human')
            sim.close()
        
        Returns:
            bool: True if viewer started successfully, False otherwise.
        """
        if not self._loaded:
            raise RuntimeError("Scene not loaded. Call load_scene() first.")
        
        if not self._check_renderer_available():
            logger.warning("Cannot start viewer: no display available")
            return False
        
        if self._viewer is None:
            try:
                self._viewer = self._mujoco.viewer.launch_passive(self._model, self._data)
                return True
            except Exception as e:
                logger.warning(f"Failed to start viewer: {e}")
                return False
        return True

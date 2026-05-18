"""MuJoCo simulator backend implementation."""

import contextlib
import os
import platform
import sys
from pathlib import Path
from typing import Any

import numpy as np

from surg_rl.scene_definition.schema import HardwareBackend
from surg_rl.utils.gpu import select_backend
from surg_rl.utils.logging import get_logger

from .base_simulator import BaseSimulator, Observation, State, StepResult
from .scene_builder import SceneBuilder
from ..render_thread import RenderThread

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
        assets_dir: str | Path | None = None,
        backend: HardwareBackend | None = None,
        render_mode: str = "rgb_array",
    ):
        """Initialize MuJoCo simulator.

        Args:
            timestep: Simulation timestep in seconds.
            frame_skip: Number of simulation steps per action.
            render_width: Width of rendered images.
            render_height: Height of rendered images.
            assets_dir: Directory containing asset files.
            backend: Hardware backend hint.
            render_mode: Rendering mode ("rgb_array", "human", etc.).
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

        self._model = None
        self._data = None
        self._viewer = None
        self._renderer = None
        self._render_thread = None
        self._mjcf_path: Path | None = None
        self._renderer_available: bool | None = None
        self._control_map: list[dict[str, Any]] = []
        self._arm_joint_ranges: dict[str, tuple[int, int]] | None = None
        self._last_depth: np.ndarray | None = None
        self._action_mode: str = "position"
        self._end_effector_target_pos: np.ndarray | None = None
        self._end_effector_target_quat: np.ndarray | None = None
        self._ik_result_joints: dict[str, np.ndarray] = {}
        # Resolve backend (defaults to auto)
        if backend is None:
            backend = HardwareBackend.auto
        self._active_backend = select_backend(backend)
        logger.info("MuJoCo simulator: selected backend=%s", self._active_backend.value)

    def _check_mujoco(self) -> None:
        """Check if MuJoCo is available."""
        try:
            import mujoco

            self._mujoco = mujoco
        except ImportError as exc:
            raise ImportError(
                "MuJoCo is not installed. Install it with: pip install mujoco"
            ) from exc

    def _check_renderer_available(self) -> bool:
        """Check if rendering is available (requires display or EGL)."""
        if self._renderer_available is not None:
            return self._renderer_available

        # Check if we have a display
        if os.environ.get("DISPLAY") or os.environ.get("PYOPENGL_PLATFORM"):
            self._renderer_available = True
            return True

        # On macOS, check if we have a display connection
        import platform

        if platform.system() == "Darwin":
            # macOS uses CGL, not EGL; just try initialising Renderer
            self._renderer_available = True
            return self._renderer_available

        # For Linux, try EGL for headless GPU rendering
        try:
            self._renderer_available = True
        except Exception:
            self._renderer_available = False

        return self._renderer_available

    def set_action_mode(self, mode: str) -> None:
        """Set the action mode for the simulation.

        In MuJoCo, ``ctrl`` values are actuator commands whose interpretation
        depends on the actuator type. For the default ``motor`` actuators, ``ctrl``
        is the scaled force/torque (``gear`` multiplies ctrl into the joint).
        Setting mode to "torque" here is mainly informational; the write path
        remains the same. Future work: generate MuJoCo actuators of type
        ``motor`` with gear=1 for true torque control, or ``position`` actuators
        for position control.

        Args:
            mode: Action mode (e.g. 'position', 'torque').
        """
        self._action_mode = mode

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
        if hasattr(scene_definition, "physics") and scene_definition.physics:
            self.timestep = scene_definition.physics.timestep

        # Build MJCF from scene
        self._mjcf_path = self.scene_builder.create_mjcf(scene_definition)

        # Load model
        try:
            self._model = self._mujoco.MjModel.from_xml_path(str(self._mjcf_path))
            self._data = self._mujoco.MjData(self._model)
            self._loaded = True
            self._build_control_map()
            self._build_arm_joint_ranges()
            logger.info(f"Loaded scene: {scene_definition.metadata.name}")
        except Exception as exc:
            logger.error(f"Failed to load MuJoCo model: {exc}")
            raise RuntimeError(f"Failed to load MuJoCo model: {exc}") from exc

    def reset(self, seed: int | None = None) -> Observation:
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
            "collateral_damage": 0.0,
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
        width: int | None = None,
        height: int | None = None,
        camera_name: str | None = None,
    ) -> np.ndarray | None:
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
                with contextlib.suppress(Exception):
                    self._renderer.close()
                self._renderer = self._mujoco.Renderer(
                    self._model,
                    height=height,
                    width=width,
                )

            # Update scene and render
            self._mujoco.mj_forward(self._model, self._data)
            cam_id = -1
            if camera_name is not None:
                try:
                    cam_id = self._mujoco.mj_name2id(
                        self._model, self._mujoco.mjtObj.mjOBJ_CAMERA, camera_name
                    )
                except Exception:
                    logger.warning(f"Camera '{camera_name}' not found in MuJoCo model.")
            if cam_id >= 0:
                self._renderer.update_scene(self._data, camera=cam_id)
            else:
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

    def get_camera_image(
        self,
        camera_name: str,
        width: int | None = None,
        height: int | None = None,
    ) -> np.ndarray | None:
        """Render an RGB image from a named scene camera.

        Resolves the camera definition from `self._scene.environment.cameras`
        and renders via MuJoCo 3.x by looking up the camera ID by name.
        """
        if not self._loaded or self._model is None or self._data is None:
            return None
        width = width or self.render_width
        height = height or self.render_height
        try:
            cam_id = self._mujoco.mj_name2id(self._model, self._mujoco.mjOBJ_CAMERA, camera_name)
        except Exception:
            logger.warning(f"Camera '{camera_name}' not found in MuJoCo model.")
            return None
        if self._renderer is None:
            self._renderer = self._mujoco.Renderer(self._model, height=height, width=width)
        elif self._renderer.width != width or self._renderer.height != height:
            with contextlib.suppress(Exception):
                self._renderer.close()
            self._renderer = self._mujoco.Renderer(self._model, height=height, width=width)
        self._mujoco.mj_forward(self._model, self._data)
        self._renderer.update_scene(self._data, camera=cam_id)
        return self._renderer.render()

    def get_state(self) -> State:
        """Get current simulation state.

        Returns:
            State object with all state information.
        """
        if not self._loaded:
            return State()

        # Collect body positions/orientations
        body_positions: dict[str, np.ndarray] = {}
        body_orientations: dict[str, np.ndarray] = {}
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
            mocap_pos=self._data.mocap_pos.copy() if hasattr(self._data, "mocap_pos") else None,
            mocap_quat=self._data.mocap_quat.copy() if hasattr(self._data, "mocap_quat") else None,
            body_positions=body_positions,
            body_orientations=body_orientations,
        )

    def get_joint_states(self) -> dict[str, dict[str, np.ndarray]]:
        """Get joint positions and velocities for all robots.

        Returns:
            Dictionary mapping robot name to {'positions': array, 'velocities': array}.
        """
        result: dict[str, dict[str, np.ndarray]] = {}
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
        if state.mocap_pos is not None and hasattr(self._data, "mocap_pos"):
            self._data.mocap_pos[:] = state.mocap_pos
        if state.mocap_quat is not None and hasattr(self._data, "mocap_quat"):
            self._data.mocap_quat[:] = state.mocap_quat

        self._mujoco.mj_forward(self._model, self._data)

    def set_body_property(self, body_name: str, property_name: str, value: float) -> bool:
        """Set a named property on a body (mass or friction).

        Args:
            body_name: Name of the body.
            property_name: Property name ('mass' or 'friction').
            value: New value.

        Returns:
            True if applied successfully.
        """
        if not self._loaded or self._model is None or self._data is None:
            return False
        try:
            body_id = self._mujoco.mj_name2id(
                self._model, self._mujoco.mjtObj.mjOBJ_BODY, body_name
            )
            if body_id < 0:
                return False
            if property_name == "mass":
                if body_id < len(self._model.body_mass):
                    self._model.body_mass[body_id] = value
                    return True
            elif property_name == "friction":
                geom_start = self._model.body_geomadr[body_id]
                geom_num = self._model.body_geomnum[body_id]
                if geom_num > 0:
                    friction_arr_len = len(self._model.geom_friction[geom_start])
                    for g in range(geom_start, geom_start + geom_num):
                        for d in range(friction_arr_len):
                            self._model.geom_friction[g][d] = max(value, 0.0)
                    return True
        except Exception:
            pass
        return False

    def close(self) -> None:
        """Clean up simulator resources."""
        self.stop_viewer()

        if self._renderer is not None:
            with contextlib.suppress(Exception):
                self._renderer.close()
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
            # Gripper actuator
            if robot.end_effectors:
                gripper_actuator_name = f"{robot.name}_gripper"
                try:
                    ctrl_idx = self._mujoco.mj_name2id(
                        self._model,
                        self._mujoco.mjtObj.mjOBJ_ACTUATOR,
                        gripper_actuator_name,
                    )
                    if ctrl_idx >= 0:
                        self._control_map.append(
                            {
                                "robot_name": robot.name,
                                "joint_name": "gripper",
                                "ctrl_index": ctrl_idx,
                                "is_gripper": True,
                            }
                        )
                except Exception:
                    pass

    def _build_arm_joint_ranges(self) -> None:
        """Build per-arm joint index ranges for arm_id routing.

        Only populated when scene has MultiAgentConfig with arm role bindings.
        Maps arm role (e.g., "surgeon", "assistant") → (start_dof, end_dof)
        in the _control_map flat action space.
        """
        self._arm_joint_ranges = None
        scene = self._scene
        if scene is None:
            return
        multi_agent = getattr(scene, "multi_agent", None)
        if multi_agent is None:
            return

        self._arm_joint_ranges = {}
        ctrl_offset = 0
        for robot in scene.robots:
            # Count non-gripper controls for this robot
            robot_ctrls = [m for m in self._control_map
                           if m["robot_name"] == robot.name and not m.get("is_gripper")]
            n_ctrls = len(robot_ctrls)
            if n_ctrls == 0:
                continue

            # Find which arm role binds to this robot
            arm = multi_agent.get_arm(robot.name)
            if arm is None:
                # Try matching by robot_ref
                for arm_cfg in multi_agent.arm_configs:
                    if arm_cfg.robot_ref == robot.name:
                        arm = arm_cfg
                        break

            if arm is not None:
                role_value = arm.role.value if hasattr(arm.role, "value") else str(arm.role)
                self._arm_joint_ranges[role_value] = (ctrl_offset, ctrl_offset + n_ctrls)

            ctrl_offset += n_ctrls
            # Skip gripper controls in offset counting
            gripper_ctrls = [m for m in self._control_map
                             if m["robot_name"] == robot.name and m.get("is_gripper")]
            ctrl_offset += len(gripper_ctrls)

    def get_num_controls(self) -> int:
        """Return number of controllable DOFs."""
        if self._control_map:
            return len(self._control_map)
        if self._loaded and hasattr(self._data, "ctrl"):
            return len(self._data.ctrl)
        return 0

    def set_end_effector_target(
        self, position: np.ndarray, orientation: np.ndarray | None = None
    ) -> None:
        """Store target end-effector pose for IK-based control.

        Args:
            position: Target position [x, y, z].
            orientation: Target orientation quaternion [w, x, y, z] or None.
        """
        self._end_effector_target_pos = np.asarray(position, dtype=np.float64)
        if orientation is not None:
            self._end_effector_target_quat = np.asarray(orientation, dtype=np.float64)
        else:
            self._end_effector_target_quat = None

    def _compute_ik(
        self,
        robot_name: str,
        target_pos: np.ndarray,
        target_quat: np.ndarray | None = None,
    ) -> np.ndarray:
        """Compute inverse kinematics for a robot.

        For primitive 1-DOF robots the Y-Euler angle (pitch) is mapped
        to the hinge joint directly. For robots with >1 DOF a Jacobian-
        based damped-least-squares solver is used when MuJoCo Jacobian
        functions are available.

        Args:
            robot_name: Name of the robot.
            target_pos: Target end-effector position [x, y, z].
            target_quat: Target orientation quaternion [w, x, y, z].

        Returns:
            Target joint angles. Falls back to current state if IK fails.
        """
        joint_state = self.get_joint_states().get(robot_name, {})
        current_positions = joint_state.get("positions", np.array([])).copy()

        joints = [
            m for m in self._control_map if m["robot_name"] == robot_name and not m["is_gripper"]
        ]
        if not joints:
            return current_positions

        n = len(joints)

        # --- 1-DOF primitive → map pitch to hinge joint ---------------------
        if n == 1:
            # Extract target rotation about Y (pitch) from quaternion.
            if target_quat is not None:
                w, x, y, z = target_quat
                siny_cosp = 2.0 * (w * y - z * x)
                cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
                target_pitch = float(np.arctan2(siny_cosp, cosy_cosp))
            else:
                target_pitch = 0.0
            return np.array([target_pitch], dtype=np.float32)

        # --- Multi-DOF → Jacobian IK (best-effort) -------------------------
        try:
            # Pick the end-effector body (heuristic: last link or robot base)
            ee_name = f"{robot_name}_link_{n - 1}"
            body_id = self._mujoco.mj_name2id(
                self._model, self._mujoco.mjtObj.mjOBJ_BODY, ee_name
            )
            if body_id < 0:
                body_id = self._mujoco.mj_name2id(
                    self._model, self._mujoco.mjtObj.mjOBJ_BODY, robot_name
                )
            if body_id < 0:
                return current_positions

            nv = self._model.nv
            jacp = np.zeros((3, nv), dtype=np.float64)
            jacr = np.zeros((3, nv), dtype=np.float64)
            self._mujoco.mj_jacBody(self._model, self._data, jacp, jacr, body_id)

            # Build reduced Jacobian for just this robot's joints
            reduced_jac = np.zeros((6, n), dtype=np.float64)
            col = 0
            for m in joints:
                jnt_id = self._mujoco.mj_name2id(
                    self._model, self._mujoco.mjtObj.mjOBJ_JOINT, m["joint_name"]
                )
                if jnt_id < 0:
                    continue
                dofr = self._model.jnt_dofadr[jnt_id]
                ndof = self._model.jnt_dofnum[jnt_id]
                for d in range(ndof):
                    if dofr + d < nv:
                        reduced_jac[:3, col] = jacp[:, dofr + d]
                        reduced_jac[3:, col] = jacr[:, dofr + d]
                        col += 1

            # Error vector [pos_err; rot_err]
            current_pos = self._data.xpos[body_id].copy()
            pos_err = (target_pos - current_pos).astype(np.float64)

            if target_quat is not None:
                # Angular error ≈ 2 * imag( q_target ⊗ conj(q_current) )
                w1, x1, y1, z1 = target_quat
                w2, x2, y2, z2 = self._data.xquat[body_id]
                # q_err = q_target * inverse(q_current)
                qw = w1 * w2 + x1 * x2 + y1 * y2 + z1 * z2
                qx = -w1 * x2 + x1 * w2 - y1 * z2 + z1 * y2
                qy = -w1 * y2 + x1 * z2 + y1 * w2 - z1 * x2
                qz = -w1 * z2 - x1 * y2 + y1 * x2 + z1 * w2
                # axis-angle: angle ≈ 2*atan2(sqrt(qx²+qy²+qz²), qw)
                # Simplified angular error vector:
                rot_err = np.array([qx, qy, qz], dtype=np.float64)
                if qw < 0.0:
                    rot_err = -rot_err
                err = np.concatenate([pos_err, rot_err])
            else:
                err = np.concatenate([pos_err, np.zeros(3, dtype=np.float64)])

            # Damped least squares
            alpha = 0.1
            lam_sq = 0.001
            J = reduced_jac[:, :col]
            dq = alpha * np.linalg.solve(
                J.T @ J + lam_sq * np.eye(col), J.T @ err
            )

            # Current qpos for these joints
            current_q = []
            for m in joints:
                jnt_id = self._mujoco.mj_name2id(
                    self._model, self._mujoco.mjtObj.mjOBJ_JOINT, m["joint_name"]
                )
                current_q.append(float(self._data.qpos[self._model.jnt_qposadr[jnt_id]]))
            target_q = np.array(current_q, dtype=np.float32) + dq[:n].astype(np.float32)
            return target_q
        except Exception:
            return current_positions

    def _apply_action(self, action: np.ndarray, arm_id: str | None = None) -> None:
        """Apply action to the simulation.

        Args:
            action: Action vector.
            arm_id: Optional arm identifier for multi-agent routing.
                None applies to all arms (backward compatible).
        """
        if action is None or len(action) == 0:
            return

        # Validate arm_id if provided
        if arm_id is not None:
            if self._arm_joint_ranges is None or arm_id not in self._arm_joint_ranges:
                raise ValueError(
                    f"Unknown arm_id={arm_id!r}. "
                    f"Available: {list(self._arm_joint_ranges.keys()) if self._arm_joint_ranges else 'none'}"
                )

        # --- End-effector control modes (IK) --------------------------------
        if self._action_mode in ("endeffector_pose", "endeffector_delta"):
            if not self._scene or not self._scene.robots:
                return

            # When arm_id specified, find the corresponding robot
            robot_name = None
            if arm_id is not None:
                multi_agent = getattr(self._scene, "multi_agent", None)
                if multi_agent is not None:
                    arm = multi_agent.get_arm(arm_id)
                    if arm is not None:
                        robot_name = arm.robot_ref

            if robot_name is None:
                robot_name = self._scene.robots[0].name

            if len(action) < 6:
                return

            pos_input = np.array(action[:3], dtype=np.float64)
            euler_input = np.array(action[3:6], dtype=np.float64)

            if self._action_mode == "endeffector_delta":
                # Delta mode: add to current pose
                current_pos, current_quat = self.get_body_pose(robot_name) or (
                    np.zeros(3),
                    np.array([1.0, 0.0, 0.0, 0.0]),
                )
                target_pos = current_pos + pos_input
                # Current Euler
                w, x, y, z = current_quat
                siny_cosp = 2.0 * (w * y - z * x)
                cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
                current_yaw = np.arctan2(siny_cosp, cosy_cosp)
                target_yaw = current_yaw + euler_input[1]
                # Back to quaternion
                qw = np.cos(target_yaw / 2.0)
                qy = np.sin(target_yaw / 2.0)
                target_quat = np.array([qw, 0.0, float(qy), 0.0], dtype=np.float64)
            else:
                # Pose mode: absolute target
                target_pos = pos_input
                target_yaw = euler_input[1]
                qw = np.cos(target_yaw / 2.0)
                qy = np.sin(target_yaw / 2.0)
                target_quat = np.array([qw, 0.0, float(qy), 0.0], dtype=np.float64)

            joint_targets = self._compute_ik(robot_name, target_pos, target_quat)

            # Apply targets through control map
            joint_idx = 0
            for mapping in self._control_map:
                if mapping.get("is_gripper") and len(action) > 6:
                    ctrl_idx = mapping["ctrl_index"]
                    if ctrl_idx < len(self._data.ctrl):
                        self._data.ctrl[ctrl_idx] = float(action[6])
                    continue
                if mapping["robot_name"] != robot_name or mapping.get("is_gripper"):
                    continue
                if joint_idx < len(joint_targets):
                    ctrl_idx = mapping["ctrl_index"]
                    if ctrl_idx < len(self._data.ctrl):
                        self._data.ctrl[ctrl_idx] = float(joint_targets[joint_idx])
                    joint_idx += 1

            # Store for possible use in step() or observation
            self._ik_result_joints[robot_name] = joint_targets
            return

        # --- Joint-space modes (position / torque / velocity) ---------------
        if self._control_map:
            if arm_id is not None:
                # Route action only to the specified arm's DOFs
                start_dof, end_dof = self._arm_joint_ranges[arm_id]  # type: ignore[index]
                action_idx = 0
                for mapping in self._control_map:
                    ctrl_idx = mapping["ctrl_index"]
                    if ctrl_idx < len(self._data.ctrl):
                        # Check if this mapping belongs to the target arm
                        robot_name = mapping["robot_name"]
                        role_matched = False
                        multi_agent = getattr(self._scene, "multi_agent", None)
                        if multi_agent is not None:
                            arm = multi_agent.get_arm(arm_id)
                            if arm is not None and arm.robot_ref == robot_name:
                                role_matched = True

                        if role_matched and action_idx < len(action):
                            self._data.ctrl[ctrl_idx] = float(action[action_idx])
                            action_idx += 1
            else:
                # arm_id=None: apply to all controls (backward compatible)
                for i, mapping in enumerate(self._control_map):
                    if i < len(action):
                        ctrl_idx = mapping["ctrl_index"]
                        if ctrl_idx < len(self._data.ctrl):
                            self._data.ctrl[ctrl_idx] = action[i]
            return

        # Fallback: apply sequentially
        if hasattr(self._data, "ctrl") and len(self._data.ctrl) > 0:
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
            with contextlib.suppress(Exception):
                obs.rgb_image = self.render("rgb_array")
            try:
                depth = self.render("depth_array")
                if depth is not None:
                    self._last_depth = depth
                    obs.depth_image = depth
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
        if hasattr(self._data, "xpos") and len(self._data.xpos) > 0:
            obs.end_effector_pos = self._data.xpos[-1].copy()

        # Collision detection: count MuJoCo contacts with non-zero force
        if hasattr(self._data, "ncon") and self._data.ncon > 0:
            for c in range(self._data.ncon):
                con = self._data.contact[c]
                # Distances <= 0 indicate penetration (active contact)
                if hasattr(con, "dist") and con.dist <= 0:
                    obs.collision_detected = True
                    break

        # Populate task-specific observations from scene task definition
        self._resolve_task_observations(obs)

        # New observation fields (H7 wiring)
        obs.thread_tension = np.array([0.0])
        if obs.force_torque is not None:
            obs.cut_force = np.array([np.linalg.norm(obs.force_torque[:3])])
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
        if not (self._scene and getattr(self._scene, "task", None)):
            return
        task = self._scene.task
        if not (hasattr(task, "objectives") and task.objectives):
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
        for objective in task.objectives:
            target_body = getattr(objective, "target_body", None)
            if not target_body:
                continue
            field = _obs_field_for_name(objective.name)
            if field is None:
                continue
            pose = self.get_body_pose(target_body)
            if pose is None:
                continue
            setattr(obs, field, pose[0])

        # Fallback: if no target_body and no needle_pos yet, use instrument heuristic
        if obs.needle_pos is None and self._scene.instruments:
            instrument_name = self._scene.instruments[0].name
            pose = self.get_body_pose(instrument_name)
            if pose is not None:
                obs.needle_pos = pose[0]

        # Fallback: heuristic tissue name matching for entry/exit
        if obs.entry_point is None or obs.exit_point is None:
            for tissue in getattr(self._scene, "tissues", []):
                tissue_name = tissue.name.lower()
                t_pose = self.get_body_pose(tissue.name)
                if t_pose is not None:
                    if "entry" in tissue_name and obs.entry_point is None:
                        obs.entry_point = t_pose[0]
                    elif "exit" in tissue_name and obs.exit_point is None:
                        obs.exit_point = t_pose[0]

        # Incision progress: completion ratio
        total = len(task.objectives)
        completed = sum(
            1 for obj in task.objectives
            if "complete" in obj.success_criteria.lower()
        )
        obs.incision_progress = completed / total if total > 0 else 0.0

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
        if self._scene and hasattr(self._scene, "task") and self._scene.task:
            max_time = 120.0 if self._scene.task.time_limit is None else self._scene.task.time_limit
            if self._simulation_time >= max_time:
                return True

        return False

    def get_body_pose(self, body_name: str) -> tuple[np.ndarray, np.ndarray] | None:
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

    def get_end_effector_pose(self, robot_name: str) -> tuple[np.ndarray, np.ndarray] | None:
        """Get the current end effector position and orientation.

        Args:
            robot_name: Name of the robot.

        Returns:
            Tuple of (position, quaternion) or None.
        """
        if not self._loaded or self._scene is None:
            return None

        # Find the robot and its end effector
        robot = None
        for r in self._scene.robots:
            if r.name == robot_name:
                robot = r
                break
        if robot is None or not robot.end_effectors:
            return None

        ee = robot.end_effectors[0]
        body_name = ee.tool_name if ee.tool_name else f"{robot_name}_ee"
        return self.get_body_pose(body_name)

    def get_tissue_deformation(self, tissue_name: str) -> np.ndarray | None:
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

    def _apply_cut(self, cut_action: Any) -> None:
        """Apply a volumetric cut and rebuild the MuJoCo model.

        Rewrites the MJCF XML with cut mesh data inline, then rebuilds
        model from the updated XML. Saves/restores qpos/qvel.
        """
        from surg_rl.cutting.engine import cut_tetrahedral_mesh

        tissue_name = cut_action.tissue_name
        flex_name = f"{tissue_name}_flex"

        try:
            flex_id = self._mujoco.mj_name2id(
                self._model, self._mujoco.mjtObj.mjOBJ_FLEX, flex_name
            )
        except Exception:
            logger.warning("Cut target '%s' has no flex body", tissue_name)
            return

        flex_start = self._model.flex_vertadr[flex_id]
        flex_num = self._model.flex_vertnum[flex_id]
        current_pos = self._data.flexvert_xpos[flex_start : flex_start + flex_num].copy()

        tet_elem_adr = self._model.flex_elemadr[flex_id]
        tet_elem_num = self._model.flex_elemnum[flex_id]
        tetrahedra = self._model.flex_elem[tet_elem_adr : tet_elem_adr + tet_elem_num].reshape(-1, 4)

        cut_origin = np.array([
            cut_action.surface_point.x, cut_action.surface_point.y, cut_action.surface_point.z
        ])
        cut_dir = np.array([
            cut_action.direction.x, cut_action.direction.y, cut_action.direction.z
        ])

        new_verts, new_tets, _ = cut_tetrahedral_mesh(
            current_pos, tetrahedra, cut_origin, cut_dir
        )

        qpos = self._data.qpos.copy()
        qvel = self._data.qvel.copy()

        self._rewrite_flex_mesh_in_mjcf(flex_name, new_verts, new_tets)

        self._model = self._mujoco.MjModel.from_xml_path(str(self._mjcf_path))
        self._data = self._mujoco.MjData(self._model)

        min_len = min(len(qpos), self._data.qpos.shape[0])
        self._data.qpos[:min_len] = qpos[:min_len]
        min_vlen = min(len(qvel), self._data.qvel.shape[0])
        self._data.qvel[:min_vlen] = qvel[:min_vlen]
        self._mujoco.mj_forward(self._model, self._data)

    def _rewrite_flex_mesh_in_mjcf(
        self, flex_name: str, vertices: np.ndarray, tetrahedra: np.ndarray
    ) -> None:
        """Replace vertex/element text in a <flex> element within the MJCF XML."""
        import xml.etree.ElementTree as ET

        mjcf_str = self._mjcf_path.read_text()
        root = ET.fromstring(mjcf_str)

        flex = None
        for candidate in root.iter("flex"):
            if candidate.get("name") == flex_name:
                flex = candidate
                break

        if flex is None:
            logger.warning("Flex '%s' not found in MJCF XML", flex_name)
            return

        vert_str = "\n".join(
            f"{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}" for v in vertices
        )
        for vtx_elem in flex.findall("vertex"):
            vtx_elem.text = vert_str

        elem_str = "\n".join(
            f"{int(e[0])} {int(e[1])} {int(e[2])} {int(e[3])}" for e in tetrahedra
        )
        for el_elem in flex.findall("element"):
            el_elem.text = elem_str

        ET.indent(root)
        self._mjcf_path.write_text(
            ET.tostring(root, encoding="unicode")
        )

    def apply_force(
        self,
        body_name: str,
        force: np.ndarray,
        torque: np.ndarray | None = None,
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

    # ------------------------------------------------------------------ #
    #  Viewer methods (non-blocking passive viewer + background thread)
    # ------------------------------------------------------------------ #

    def start_viewer(self, target_fps: float = 30.0) -> bool:
        """Start MuJoCo passive viewer in a background render thread.

        On macOS, raises RuntimeError if ``mjpython`` is not detected in
        ``sys.executable`` (Cocoa GL requires fork-safe interpreter).

        Args:
            target_fps: Desired refresh rate for the viewer.

        Returns:
            True if the viewer started (or was already running).
            False if the display is unavailable (headless).

        Raises:
            RuntimeError: On macOS without ``mjpython``.
        """
        if not self._loaded:
            raise RuntimeError("Scene not loaded. Call load_scene() first.")

        if not self._check_renderer_available():
            logger.warning("Cannot start viewer: no display available")
            return False

        if platform.system() == "Darwin":
            if "mjpython" not in sys.executable:
                raise RuntimeError(
                    "MuJoCo passive viewer requires 'mjpython' on macOS. "
                    "Run: mjpython -m surg_rl.cli train ..."
                )

        if self._viewer is not None:
            return True

        try:
            self._viewer = self._mujoco.viewer.launch_passive(self._model, self._data)
            self._render_thread = RenderThread(self._viewer, target_fps=target_fps)
            self._render_thread.start()
            logger.info("MuJoCo viewer started at %.1f FPS", target_fps)
            return True
        except Exception as e:
            logger.warning("Failed to start viewer: %s", e)
            return False

    def stop_viewer(self) -> None:
        """Stop the background render thread and release the viewer."""
        if self._render_thread is not None:
            self._render_thread.stop()
            self._render_thread = None
        self._viewer = None

    def close(self) -> None:
        """Clean up simulator resources."""
        self.stop_viewer()
        self._renderer = None
        self._model = None
        self._data = None
        self._loaded = False

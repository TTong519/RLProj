"""Abstract base class for physics simulators.

This module defines the interface that all simulator backends must implement,
providing a unified API for loading scenes, stepping simulation, and rendering.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    # HardwareBackend is used only in a string annotation below
    # (`backend: "HardwareBackend"`). Imported under TYPE_CHECKING to avoid a
    # circular import: scene_definition.schema references simulators indirectly.
    from surg_rl.scene_definition.schema import HardwareBackend


class SimulationStatus(Enum):
    """Status of simulation step."""

    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"


@dataclass
class Observation:
    """Observation returned by the simulator.

    Attributes:
        rgb_image: RGB camera image (H, W, 3).
        depth_image: Depth image (H, W) or None.
        segmentation: Segmentation mask (H, W) or None.
        robot_state: Robot joint positions and velocities.
        end_effector_pos: End effector position (x, y, z).
        end_effector_quat: End effector orientation (w, x, y, z).
        force_torque: Force/torque sensor readings or None.
        tissue_state: Tissue positions/velocities or None.
        custom: Additional custom observations.
    """

    rgb_image: np.ndarray | None = None
    depth_image: np.ndarray | None = None
    segmentation: np.ndarray | None = None
    robot_state: np.ndarray | None = None
    end_effector_pos: np.ndarray | None = None
    end_effector_quat: np.ndarray | None = None
    force_torque: np.ndarray | None = None
    tissue_state: dict[str, np.ndarray] | None = None
    collision_detected: bool = False
    needle_pos: np.ndarray | None = None
    entry_point: np.ndarray | None = None
    exit_point: np.ndarray | None = None
    incision_progress: float = 0.0
    thread_tension: np.ndarray | None = None
    cut_force: np.ndarray | None = None
    receiver_pos: np.ndarray | None = None
    tool_positions: np.ndarray | None = None
    custom: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert observation to dictionary."""
        return {
            "rgb_image": self.rgb_image,
            "depth_image": self.depth_image,
            "segmentation": self.segmentation,
            "robot_state": self.robot_state,
            "end_effector_pos": self.end_effector_pos,
            "end_effector_quat": self.end_effector_quat,
            "force_torque": self.force_torque,
            "tissue_state": self.tissue_state,
            "collision_detected": self.collision_detected,
            "needle_pos": self.needle_pos,
            "entry_point": self.entry_point,
            "exit_point": self.exit_point,
            "incision_progress": self.incision_progress,
            "thread_tension": self.thread_tension,
            "cut_force": self.cut_force,
            "receiver_pos": self.receiver_pos,
            "tool_positions": self.tool_positions,
            "custom": self.custom,
        }


@dataclass
class State:
    """Simulator state for saving/restoring.

    Attributes:
        time: Current simulation time.
        qpos: Joint positions.
        qvel: Joint velocities.
        mocap_pos: Mocap body positions.
        mocap_quat: Mocap body orientations.
        body_positions: Named body positions.
        body_orientations: Named body orientations.
        custom: Additional state data.
    """

    time: float = 0.0
    qpos: np.ndarray | None = None
    qvel: np.ndarray | None = None
    mocap_pos: np.ndarray | None = None
    mocap_quat: np.ndarray | None = None
    body_positions: dict[str, np.ndarray] = field(default_factory=dict)
    body_orientations: dict[str, np.ndarray] = field(default_factory=dict)
    custom: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepResult:
    """Result of a simulation step.

    Attributes:
        observation: Current observation.
        reward: Reward value.
        terminated: Whether episode ended in success.
        truncated: Whether episode was cut short.
        info: Additional information.
    """

    observation: Observation
    reward: float
    terminated: bool
    truncated: bool
    info: dict[str, Any] = field(default_factory=dict)

    @property
    def done(self) -> bool:
        """Whether episode is done."""
        return self.terminated or self.truncated


class BaseSimulator(ABC):
    """Abstract base class for physics simulators.

    This class defines the interface for loading scenes, stepping simulation,
    and rendering. Concrete implementations (MuJoCo, PyBullet) must implement
    all abstract methods.

    Attributes:
        scene: Currently loaded scene definition.
        timestep: Simulation timestep.
        frame_skip: Number of simulation steps per action.
        render_mode: Current rendering mode.
        render_width: Width of rendered images.
        render_height: Height of rendered images.
    """

    def __init__(
        self,
        timestep: float = 0.002,
        frame_skip: int = 1,
        render_width: int = 640,
        render_height: int = 480,
        backend: "HardwareBackend" = None,  # type: ignore
        render_mode: str = "rgb_array",
    ):
        """Initialize the simulator.

        Args:
            timestep: Simulation timestep in seconds.
            frame_skip: Number of simulation steps per action.
            render_width: Width of rendered images.
            render_height: Height of rendered images.
            backend: Hardware backend hint (e.g. cuda, cpu).
            render_mode: Rendering mode ("rgb_array", "human", "depth_array").
        """
        self.timestep = timestep
        self.frame_skip = frame_skip
        self.render_mode = render_mode
        self.render_width = render_width
        self.render_height = render_height
        self._scene = None
        self._loaded = False
        self._simulation_time = 0.0
        self._backend = backend

    @property
    def scene(self) -> Any:
        """Currently loaded scene."""
        return self._scene

    @property
    def simulation_time(self) -> float:
        """Current simulation time."""
        return self._simulation_time

    @abstractmethod
    def load_scene(self, scene_definition: Any) -> None:
        """Load a scene definition into the simulator.

        Args:
            scene_definition: SceneDefinition object from scene_definition module.

        Raises:
            RuntimeError: If scene cannot be loaded.
            FileNotFoundError: If required assets are missing.
        """
        pass

    @abstractmethod
    def reset(self, seed: int | None = None) -> Observation:
        """Reset the simulation to initial state.

        Args:
            seed: Optional random seed for reproducibility.

        Returns:
            Initial observation.
        """
        pass

    @abstractmethod
    def step(self, action: np.ndarray) -> StepResult:
        """Execute one simulation step.

        Args:
            action: Action vector (robot joint targets or end effector pose).

        Returns:
            StepResult containing observation, reward, and done flags.
        """
        pass

    @abstractmethod
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
            width: Image width (uses default if None).
            height: Image height (uses default if None).
            camera_name: Name of camera to render from (uses default if None).

        Returns:
            Rendered image array or None for 'human' mode.
        """
        pass

    @abstractmethod
    def get_state(self) -> State:
        """Get current simulation state for saving.

        Returns:
            State object containing all state information.
        """
        pass

    @abstractmethod
    def set_state(self, state: State) -> None:
        """Restore simulation state from saved state.

        Args:
            state: State object to restore.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Clean up simulator resources."""
        pass

    @abstractmethod
    def start_viewer(self, target_fps: float = 30.0) -> bool:
        """Start a non-blocking 3D viewer if a display is available.

        Returns True if viewer started (or already running), False if
        headless/no display.
        """
        pass

    @abstractmethod
    def stop_viewer(self) -> None:
        """Stop the viewer and cleanup resources."""
        pass

    @abstractmethod
    def get_joint_states(self) -> dict[str, dict[str, np.ndarray]]:
        """Get joint positions and velocities for all robots.

        Returns:
            Dictionary mapping robot name to a dict with 'positions'
            and 'velocities' arrays.
        """
        pass

    def apply_action(self, action: np.ndarray, arm_id: str | None = None) -> None:
        """Apply an action to the simulation.

        Args:
            action: Action vector (robot joint targets or end effector pose).
            arm_id: Optional arm identifier for multi-agent routing.
                None applies to all arms (backward compatible).
                Specific arm_id routes only to that arm's DOFs.
        """
        self._apply_action(action, arm_id=arm_id)

    def get_num_controls(self) -> int:
        """Return the number of controllable DOFs.

        Subclasses should override this after load_scene().
        """
        return 0

    def set_action_mode(self, mode: str) -> None:
        """Set the action mode for the simulator.

        Subclasses should override to support per-backend mode switching
        (e.g. POSITION_CONTROL vs TORQUE_CONTROL in PyBullet).

        Args:
            mode: Action mode (e.g. 'position', 'torque').

        Raises:
            NotImplementedError: If the backend does not support mode switching.
        """
        raise NotImplementedError(f"Backend does not support action mode switching: {mode}")

    @abstractmethod
    def _apply_action(self, action: np.ndarray, arm_id: str | None = None) -> None:
        """Internal implementation of action application.

        Subclasses may override this instead of apply_action.

        Args:
            action: Action vector (robot joint targets or end effector pose).
            arm_id: Optional arm identifier for multi-agent routing.
        """
        pass

    def fluid_step(self, dt: float | None = None) -> None:
        """Per-step fluid simulation hook. Default: no-op.

        Subclasses with native fluid support (e.g., a future MuJoCoMPM-fluid
        backend) should override this to advance their internal fluid state
        by ``dt`` seconds. The default implementation is a no-op because
        MuJoCo and PyBullet have no built-in Eulerian fluid solver; fluid
        simulation in surg-rl today is delegated to ``FluidSimulator``
        (PhiFlow) and driven by ``SurgicalEnv.step()`` directly via
        ``env._fluid_simulator.step()``.

        Args:
            dt: Simulation timestep in seconds. ``None`` means "use the
                simulator's default timestep" — interpretation is backend-
                specific. MuJoCo and PyBullet ignore this argument.

        Returns:
            None. Subclasses with native fluid support should compute the
            per-step fluid update as a side effect and may return forces or
            velocity fields via separate APIs (not via this method's return).
        """
        return None

    # Optional methods with default implementations

    def get_robot_state(self, robot_name: str) -> np.ndarray | None:
        """Get joint state for a specific robot.

        (TODO: implement in subclass)

        Args:
            robot_name: Name of the robot.

        Returns:
            Array of joint positions and velocities, or None.
        """
        return None

    def get_end_effector_pose(self, robot_name: str) -> tuple[np.ndarray, np.ndarray] | None:
        """Get end effector pose for a specific robot.

        (TODO: implement in subclass)

        Args:
            robot_name: Name of the robot.

        Returns:
            Tuple of (position, quaternion) or None.
        """
        return None

    def get_body_pose(self, body_name: str) -> tuple[np.ndarray, np.ndarray] | None:
        """Get pose of a named body in the simulation.

        (TODO: implement in subclass)

        Args:
            body_name: Name of the body.

        Returns:
            Tuple of (position, quaternion) or None.
        """
        return None

    def set_body_pose(
        self,
        body_name: str,
        position: np.ndarray,
        orientation: np.ndarray,
    ) -> bool:
        """Set pose of a named body in the simulation.

        (TODO: implement in subclass)

        Args:
            body_name: Name of the body.
            position: Position (x, y, z).
            orientation: Orientation (w, x, y, z) quaternion.

        Returns:
            True if successful, False otherwise.
        """
        return False

    def apply_force(
        self,
        body_name: str,
        force: np.ndarray,
        torque: np.ndarray | None = None,
    ) -> bool:
        """Apply external force to a body.

        (TODO: implement in subclass)

        Args:
            body_name: Name of the body.
            force: Force vector (fx, fy, fz).
            torque: Torque vector (tx, ty, tz) or None.

        Returns:
            True if successful, False otherwise.
        """
        return False

    def get_contact_points(self, body_name: str) -> list[dict[str, Any]]:
        """Get contact points for a body.

        (TODO: implement in subclass)

        Args:
            body_name: Name of the body.

        Returns:
            List of contact point dictionaries.
        """
        return []

    def get_camera_image(
        self,
        camera_name: str,
        width: int | None = None,
        height: int | None = None,
    ) -> np.ndarray | None:
        """Get image from a specific camera.

        (TODO: implement in subclass)

        Args:
            camera_name: Name of the camera.
            width: Image width.
            height: Image height.

        Returns:
            RGB image array or None.
        """
        return None

    def set_body_property(self, body_name: str, property_name: str, value: float) -> bool:
        """Set a named property on a body.

        Subclasses should override to support backend-specific property setting
        (e.g., mass via MuJoCo body_mass, friction via PyBullet dynamics).

        Args:
            body_name: Name of the body.
            property_name: Property name (e.g., 'mass', 'friction').
            value: New value.

        Returns:
            True if applied successfully.
        """
        return False

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        """Context manager exit."""
        self.close()
        return False

    def __del__(self):
        """Destructor to ensure cleanup."""
        import contextlib
        import sys

        if sys.is_finalizing():
            return
        with contextlib.suppress(Exception):
            self.close()

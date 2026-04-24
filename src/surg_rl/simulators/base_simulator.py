"""Abstract base class for physics simulators.

This module defines the interface that all simulator backends must implement,
providing a unified API for loading scenes, stepping simulation, and rendering.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np


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
    rgb_image: Optional[np.ndarray] = None
    depth_image: Optional[np.ndarray] = None
    segmentation: Optional[np.ndarray] = None
    robot_state: Optional[np.ndarray] = None
    end_effector_pos: Optional[np.ndarray] = None
    end_effector_quat: Optional[np.ndarray] = None
    force_torque: Optional[np.ndarray] = None
    tissue_state: Optional[Dict[str, np.ndarray]] = None
    custom: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
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
    qpos: Optional[np.ndarray] = None
    qvel: Optional[np.ndarray] = None
    mocap_pos: Optional[np.ndarray] = None
    mocap_quat: Optional[np.ndarray] = None
    body_positions: Dict[str, np.ndarray] = field(default_factory=dict)
    body_orientations: Dict[str, np.ndarray] = field(default_factory=dict)
    custom: Dict[str, Any] = field(default_factory=dict)


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
    info: Dict[str, Any] = field(default_factory=dict)

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
    ):
        """Initialize the simulator.

        Args:
            timestep: Simulation timestep in seconds.
            frame_skip: Number of simulation steps per action.
            render_width: Width of rendered images.
            render_height: Height of rendered images.
        """
        self.timestep = timestep
        self.frame_skip = frame_skip
        self.render_mode = "rgb_array"
        self.render_width = render_width
        self.render_height = render_height
        self._scene = None
        self._loaded = False
        self._simulation_time = 0.0

    @property
    def scene(self):
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
    def reset(self, seed: Optional[int] = None) -> Observation:
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
        width: Optional[int] = None,
        height: Optional[int] = None,
        camera_name: Optional[str] = None,
    ) -> Optional[np.ndarray]:
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
    def get_joint_states(self) -> Dict[str, Dict[str, np.ndarray]]:
        """Get joint positions and velocities for all robots.

        Returns:
            Dictionary mapping robot name to a dict with 'positions'
            and 'velocities' arrays.
        """
        pass

    def apply_action(self, action: np.ndarray) -> None:
        """Apply an action to the simulation.

        Args:
            action: Action vector (robot joint targets or end effector pose).
        """
        self._apply_action(action)

    def _apply_action(self, action: np.ndarray) -> None:
        """Internal implementation of action application.

        Subclasses may override this instead of apply_action.
        """
        pass

    # Optional methods with default implementations

    def get_robot_state(self, robot_name: str) -> Optional[np.ndarray]:
        """Get joint state for a specific robot.

        Args:
            robot_name: Name of the robot.

        Returns:
            Array of joint positions and velocities, or None.
        """
        return None

    def get_end_effector_pose(self, robot_name: str) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """Get end effector pose for a specific robot.

        Args:
            robot_name: Name of the robot.

        Returns:
            Tuple of (position, quaternion) or None.
        """
        return None

    def get_body_pose(self, body_name: str) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """Get pose of a named body in the simulation.

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
        torque: Optional[np.ndarray] = None,
    ) -> bool:
        """Apply external force to a body.

        Args:
            body_name: Name of the body.
            force: Force vector (fx, fy, fz).
            torque: Torque vector (tx, ty, tz) or None.

        Returns:
            True if successful, False otherwise.
        """
        return False

    def get_contact_points(self, body_name: str) -> List[Dict[str, Any]]:
        """Get contact points for a body.

        Args:
            body_name: Name of the body.

        Returns:
            List of contact point dictionaries.
        """
        return []

    def get_camera_image(
        self,
        camera_name: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> Optional[np.ndarray]:
        """Get image from a specific camera.

        Args:
            camera_name: Name of the camera.
            width: Image width.
            height: Image height.

        Returns:
            RGB image array or None.
        """
        return None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False

    def __del__(self):
        """Destructor to ensure cleanup."""
        import sys
        if sys.is_finalizing():
            return
        try:
            self.close()
        except Exception:
            # Suppress cleanup errors during interpreter shutdown
            pass

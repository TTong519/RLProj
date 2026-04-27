"""Observation space definitions for surgical RL environments.

This module provides observation space definitions and processors for
surgical robotics RL environments, supporting multiple observation types
including proprioceptive, visual, force, and task-specific observations.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import gymnasium as gym
import numpy as np

from surg_rl.simulators.base_simulator import Observation


class ObservationType(str, Enum):
    """Types of observations available in surgical environments."""

    JOINT_POSITIONS = "joint_positions"
    JOINT_VELOCITIES = "joint_velocities"
    ENDEFFECTOR_POS = "endeffector_pos"
    ENDEFFECTOR_QUAT = "endeffector_quat"
    FORCE_TORQUE = "force_torque"
    TISSUE_STATE = "tissue_state"
    TISSUE_DEFORMATION = "tissue_deformation"
    RGB_IMAGE = "rgb_image"
    DEPTH_IMAGE = "depth_image"
    SEGMENTATION = "segmentation"
    TARGET_POS = "target_pos"
    TARGET_QUAT = "target_quat"
    TOOL_POSITIONS = "tool_positions"
    DISTANCE_TO_TARGET = "distance_to_target"
    ANGLE_TO_TARGET = "angle_to_target"
    NEEDLE_POS = "needle_pos"
    ENTRY_POINT = "entry_point"
    EXIT_POINT = "exit_point"
    INCISION_PROGRESS = "incision_progress"
    CUSTOM = "custom"


@dataclass
class ObservationSpec:
    """Specification for a single observation component.

    Attributes:
        name: Observation name/identifier.
        obs_type: Type of observation.
        shape: Shape of the observation array.
        dtype: Data type of the observation.
        low: Lower bound (for Box spaces).
        high: Upper bound (for Box spaces).
        normalize: Whether to normalize this observation.
        noise_scale: Scale of observation noise to apply (0 = none).
        description: Human-readable description.
    """

    name: str
    obs_type: ObservationType
    shape: Tuple[int, ...]
    dtype: type = np.float32
    low: Optional[np.ndarray] = None
    high: Optional[np.ndarray] = None
    normalize: bool = False
    noise_scale: float = 0.0
    description: str = ""

    def get_space(self) -> gym.Space:
        """Create the Gymnasium space for this observation.

        Returns:
            Gymnasium Space object.
        """
        if self.low is not None and self.high is not None:
            low = np.asarray(self.low, dtype=self.dtype)
            high = np.asarray(self.high, dtype=self.dtype)
            return gym.spaces.Box(
                low=low,
                high=high,
                shape=self.shape,
                dtype=self.dtype,
            )
        # Unbounded space
        return gym.spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=self.shape,
            dtype=self.dtype,
        )


@dataclass
class ObservationConfig:
    """Configuration for the observation space of a surgical environment.

    Attributes:
        observation_types: Which observations to include.
        image_size: Size of image observations (width, height).
        include_visual: Whether to include visual observations.
        include_force: Whether to include force/torque observations.
        include_tissue: Whether to include tissue state observations.
        normalize: Whether to normalize observations.
        stack_frames: Number of frames to stack for visual observations.
        flatten: Whether to flatten the observation into a single vector.
    """

    observation_types: List[ObservationType] = field(default_factory=lambda: [
        ObservationType.JOINT_POSITIONS,
        ObservationType.JOINT_VELOCITIES,
        ObservationType.ENDEFFECTOR_POS,
        ObservationType.ENDEFFECTOR_QUAT,
        ObservationType.TARGET_POS,
        ObservationType.DISTANCE_TO_TARGET,
    ])
    image_size: Tuple[int, int] = (64, 64)
    include_visual: bool = False
    include_force: bool = False
    include_tissue: bool = False
    normalize: bool = True
    stack_frames: int = 1
    flatten: bool = True


# ============================================================================
# Default Observation Specifications
# ============================================================================

# Robot proprioception
JOINT_POSITIONS_SPEC = ObservationSpec(
    name="joint_positions",
    obs_type=ObservationType.JOINT_POSITIONS,
    shape=(7,),  # 7-DOF robot arm
    low=-np.pi * np.ones(7),
    high=np.pi * np.ones(7),
    normalize=True,
    description="Joint positions (radians)",
)

JOINT_VELOCITIES_SPEC = ObservationSpec(
    name="joint_velocities",
    obs_type=ObservationType.JOINT_VELOCITIES,
    shape=(7,),
    low=-2.0 * np.ones(7),
    high=2.0 * np.ones(7),
    normalize=True,
    description="Joint velocities (rad/s)",
)

# End effector
ENDEFFECTOR_POS_SPEC = ObservationSpec(
    name="endeffector_pos",
    obs_type=ObservationType.ENDEFFECTOR_POS,
    shape=(3,),
    low=-1.0 * np.ones(3),
    high=1.0 * np.ones(3),
    normalize=True,
    description="End effector position (x, y, z)",
)

ENDEFFECTOR_QUAT_SPEC = ObservationSpec(
    name="endeffector_quat",
    obs_type=ObservationType.ENDEFFECTOR_QUAT,
    shape=(4,),
    low=-1.0 * np.ones(4),
    high=1.0 * np.ones(4),
    normalize=True,
    description="End effector orientation (quaternion w, x, y, z)",
)

# Force/torque
FORCE_TORQUE_SPEC = ObservationSpec(
    name="force_torque",
    obs_type=ObservationType.FORCE_TORQUE,
    shape=(6,),
    low=-100.0 * np.ones(6),
    high=100.0 * np.ones(6),
    normalize=True,
    noise_scale=0.01,
    description="Force/torque sensor readings (fx, fy, fz, tx, ty, tz)",
)

# Tissue state
TISSUE_STATE_SPEC = ObservationSpec(
    name="tissue_state",
    obs_type=ObservationType.TISSUE_STATE,
    shape=(12,),  # Position + velocity for tissue nodes
    low=np.full(12, -np.inf),
    high=np.full(12, np.inf),
    normalize=False,
    description="Tissue node positions and velocities",
)

# Tissue deformation (soft body vertex displacements)
TISSUE_DEFORMATION_SPEC = ObservationSpec(
    name="tissue_deformation",
    obs_type=ObservationType.TISSUE_DEFORMATION,
    shape=(50, 3),  # 5x5x2 flexcomp grid vertices, 3D displacements
    low=np.full((50, 3), -1.0),
    high=np.full((50, 3), 1.0),
    normalize=False,
    description="Soft body tissue vertex displacements from rest shape",
)

# Task-related
TARGET_POS_SPEC = ObservationSpec(
    name="target_pos",
    obs_type=ObservationType.TARGET_POS,
    shape=(3,),
    low=-1.0 * np.ones(3),
    high=1.0 * np.ones(3),
    normalize=True,
    description="Target position (x, y, z)",
)

TARGET_QUAT_SPEC = ObservationSpec(
    name="target_quat",
    obs_type=ObservationType.TARGET_QUAT,
    shape=(4,),
    low=-1.0 * np.ones(4),
    high=1.0 * np.ones(4),
    normalize=True,
    description="Target orientation (quaternion)",
)

DISTANCE_TO_TARGET_SPEC = ObservationSpec(
    name="distance_to_target",
    obs_type=ObservationType.DISTANCE_TO_TARGET,
    shape=(1,),
    low=np.zeros(1),
    high=np.ones(1) * 10.0,
    normalize=True,
    description="Euclidean distance to target",
)

ANGLE_TO_TARGET_SPEC = ObservationSpec(
    name="angle_to_target",
    obs_type=ObservationType.ANGLE_TO_TARGET,
    shape=(1,),
    low=np.zeros(1),
    high=np.pi * np.ones(1),
    normalize=True,
    description="Angular distance to target orientation",
)

# Visual observations
RGB_IMAGE_SPEC = ObservationSpec(
    name="rgb_image",
    obs_type=ObservationType.RGB_IMAGE,
    shape=(64, 64, 3),
    low=np.zeros((64, 64, 3), dtype=np.uint8),
    high=255 * np.ones((64, 64, 3), dtype=np.uint8),
    dtype=np.uint8,
    normalize=False,
    description="RGB camera image",
)

DEPTH_IMAGE_SPEC = ObservationSpec(
    name="depth_image",
    obs_type=ObservationType.DEPTH_IMAGE,
    shape=(64, 64, 1),
    low=np.zeros((64, 64, 1)),
    high=np.ones((64, 64, 1)) * 10.0,
    normalize=True,
    description="Depth camera image",
)

SEGMENTATION_SPEC = ObservationSpec(
    name="segmentation",
    obs_type=ObservationType.SEGMENTATION,
    shape=(64, 64, 1),
    low=np.zeros((64, 64, 1), dtype=np.int32),
    high=255 * np.ones((64, 64, 1), dtype=np.int32),
    dtype=np.int32,
    normalize=False,
    description="Segmentation mask",
)

# Task-specific observations
NEEDLE_POS_SPEC = ObservationSpec(
    name="needle_pos",
    obs_type=ObservationType.NEEDLE_POS,
    shape=(3,),
    low=-1.0 * np.ones(3),
    high=1.0 * np.ones(3),
    normalize=True,
    description="Needle tool position (x, y, z)",
)

ENTRY_POINT_SPEC = ObservationSpec(
    name="entry_point",
    obs_type=ObservationType.ENTRY_POINT,
    shape=(3,),
    low=-1.0 * np.ones(3),
    high=1.0 * np.ones(3),
    normalize=True,
    description="Suture entry point on tissue (x, y, z)",
)

EXIT_POINT_SPEC = ObservationSpec(
    name="exit_point",
    obs_type=ObservationType.EXIT_POINT,
    shape=(3,),
    low=-1.0 * np.ones(3),
    high=1.0 * np.ones(3),
    normalize=True,
    description="Suture exit point on tissue (x, y, z)",
)

INCISION_PROGRESS_SPEC = ObservationSpec(
    name="incision_progress",
    obs_type=ObservationType.INCISION_PROGRESS,
    shape=(1,),
    low=np.zeros(1),
    high=np.ones(1),
    normalize=True,
    description="Incision completion ratio (0.0–1.0)",
)


# ============================================================================
# Observation Builder
# ============================================================================

# Registry of default observation specs
DEFAULT_SPECS: Dict[ObservationType, ObservationSpec] = {
    ObservationType.JOINT_POSITIONS: JOINT_POSITIONS_SPEC,
    ObservationType.JOINT_VELOCITIES: JOINT_VELOCITIES_SPEC,
    ObservationType.ENDEFFECTOR_POS: ENDEFFECTOR_POS_SPEC,
    ObservationType.ENDEFFECTOR_QUAT: ENDEFFECTOR_QUAT_SPEC,
    ObservationType.FORCE_TORQUE: FORCE_TORQUE_SPEC,
    ObservationType.TISSUE_STATE: TISSUE_STATE_SPEC,
    ObservationType.TISSUE_DEFORMATION: TISSUE_DEFORMATION_SPEC,
    ObservationType.TARGET_POS: TARGET_POS_SPEC,
    ObservationType.TARGET_QUAT: TARGET_QUAT_SPEC,
    ObservationType.DISTANCE_TO_TARGET: DISTANCE_TO_TARGET_SPEC,
    ObservationType.ANGLE_TO_TARGET: ANGLE_TO_TARGET_SPEC,
    ObservationType.NEEDLE_POS: NEEDLE_POS_SPEC,
    ObservationType.ENTRY_POINT: ENTRY_POINT_SPEC,
    ObservationType.EXIT_POINT: EXIT_POINT_SPEC,
    ObservationType.INCISION_PROGRESS: INCISION_PROGRESS_SPEC,
    ObservationType.RGB_IMAGE: RGB_IMAGE_SPEC,
    ObservationType.DEPTH_IMAGE: DEPTH_IMAGE_SPEC,
    ObservationType.SEGMENTATION: SEGMENTATION_SPEC,
}


class ObservationBuilder:
    """Build observation spaces and extract observations for surgical environments.

    This class creates Gymnasium-compatible observation spaces based on
    configuration and extracts observations from simulator step results.

    Example:
        >>> config = ObservationConfig(
        ...     observation_types=[
        ...         ObservationType.JOINT_POSITIONS,
        ...         ObservationType.ENDEFFECTOR_POS,
        ...         ObservationType.DISTANCE_TO_TARGET,
        ...     ],
        ... )
        >>> builder = ObservationBuilder(config)
        >>> obs_space = builder.get_observation_space()
        >>> obs = builder.extract_observation(observation)
    """

    def __init__(
        self,
        config: Optional[ObservationConfig] = None,
        custom_specs: Optional[Dict[str, ObservationSpec]] = None,
        num_joints: int = 7,
        image_size: Tuple[int, int] = (64, 64),
    ):
        """Initialize the observation builder.

        Args:
            config: Observation configuration. Uses defaults if None.
            custom_specs: Custom observation specifications.
            num_joints: Number of robot joints (adjusts proprioceptive sizes).
            image_size: Size of visual observations (H, W).
        """
        self.config = config or ObservationConfig()
        self.custom_specs = custom_specs or {}
        self.num_joints = num_joints
        self.image_size = image_size

        # Build observation specs based on config
        self._specs: Dict[str, ObservationSpec] = {}
        self._build_specs()

        # Pre-allocate fallback zero arrays to avoid repeated allocations
        self._fallback_cache: Dict[str, np.ndarray] = {
            name: np.zeros(spec.shape, dtype=spec.dtype)
            for name, spec in self._specs.items()
        }
        # Override quaternion fallbacks with identity (valid default quaternion)
        for quat_name in ("endeffector_quat", "target_quat"):
            if quat_name in self._fallback_cache:
                self._fallback_cache[quat_name] = np.array(
                    [1.0, 0.0, 0.0, 0.0], dtype=self._specs[quat_name].dtype
                )

        # Running statistics for normalization
        self._running_mean: Optional[np.ndarray] = None
        self._running_var: Optional[np.ndarray] = None
        self._count: int = 0

        self._rng = np.random.default_rng(seed=0)

    def seed(self, seed: int) -> None:
        self._rng = np.random.default_rng(seed=seed)

    def _apply_noise(self, obs_array: np.ndarray, noise_scale: float) -> np.ndarray:
        noise = self._rng.normal(0, noise_scale, obs_array.shape)
        return obs_array + noise.astype(obs_array.dtype)

    def _build_specs(self) -> None:
        """Build observation specifications from configuration."""
        for obs_type in self.config.observation_types:
            if obs_type in DEFAULT_SPECS:
                spec = DEFAULT_SPECS[obs_type]
                # Adjust joint dimensions if needed
                if obs_type == ObservationType.JOINT_POSITIONS:
                    spec = ObservationSpec(
                        name="joint_positions",
                        obs_type=obs_type,
                        shape=(self.num_joints,),
                        low=-np.pi * np.ones(self.num_joints),
                        high=np.pi * np.ones(self.num_joints),
                        normalize=spec.normalize,
                        description=spec.description,
                    )
                elif obs_type == ObservationType.JOINT_VELOCITIES:
                    spec = ObservationSpec(
                        name="joint_velocities",
                        obs_type=obs_type,
                        shape=(self.num_joints,),
                        low=-2.0 * np.ones(self.num_joints),
                        high=2.0 * np.ones(self.num_joints),
                        normalize=spec.normalize,
                        description=spec.description,
                    )
                elif obs_type in (
                    ObservationType.RGB_IMAGE,
                    ObservationType.DEPTH_IMAGE,
                    ObservationType.SEGMENTATION,
                ):
                    # Adjust image dimensions
                    h, w = self.image_size
                    if obs_type == ObservationType.RGB_IMAGE:
                        spec = ObservationSpec(
                            name="rgb_image",
                            obs_type=obs_type,
                            shape=(h, w, 3),
                            low=np.zeros((h, w, 3), dtype=np.uint8),
                            high=255 * np.ones((h, w, 3), dtype=np.uint8),
                            dtype=np.uint8,
                            normalize=False,
                            description=spec.description,
                        )
                    elif obs_type == ObservationType.DEPTH_IMAGE:
                        spec = ObservationSpec(
                            name="depth_image",
                            obs_type=obs_type,
                            shape=(h, w, 1),
                            low=np.zeros((h, w, 1)),
                            high=np.ones((h, w, 1)) * 10.0,
                            normalize=True,
                            description=spec.description,
                        )
                    elif obs_type == ObservationType.SEGMENTATION:
                        spec = ObservationSpec(
                            name="segmentation",
                            obs_type=obs_type,
                            shape=(h, w, 1),
                            low=np.zeros((h, w, 1), dtype=np.int32),
                            high=255 * np.ones((h, w, 1), dtype=np.int32),
                            dtype=np.int32,
                            normalize=False,
                            description=spec.description,
                        )
                self._specs[spec.name] = spec
            elif obs_type == ObservationType.CUSTOM:
                # Add custom specs
                for name, spec in self.custom_specs.items():
                    self._specs[name] = spec

        # Add force/torque if requested
        if self.config.include_force and ObservationType.FORCE_TORQUE not in [
            s.obs_type for s in self._specs.values()
        ]:
            self._specs["force_torque"] = FORCE_TORQUE_SPEC

        # Add tissue state if requested
        if self.config.include_tissue and ObservationType.TISSUE_STATE not in [
            s.obs_type for s in self._specs.values()
        ]:
            self._specs["tissue_state"] = TISSUE_STATE_SPEC

    def get_observation_space(self) -> gym.spaces.Dict:
        """Create the Gymnasium observation space.

        Returns:
            Dict observation space with all configured observation components.
        """
        spaces = {}
        for name, spec in self._specs.items():
            spaces[name] = spec.get_space()
        return gym.spaces.Dict(spaces)

    def get_flat_observation_space(self) -> gym.spaces.Box:
        """Create a flattened observation space.

        Returns:
            Box observation space with all observations concatenated.
        """
        total_size = 0
        lows = []
        highs = []

        for name, spec in self._specs.items():
            size = int(np.prod(spec.shape))
            total_size += size
            if spec.low is not None and spec.high is not None:
                lows.append(spec.low.flatten())
                highs.append(spec.high.flatten())
            else:
                lows.append(np.full(size, -np.inf))
                highs.append(np.full(size, np.inf))

        low = np.concatenate(lows) if lows else np.full(total_size, -np.inf)
        high = np.concatenate(highs) if highs else np.full(total_size, np.inf)

        return gym.spaces.Box(low=low, high=high, dtype=np.float32)

    def extract_observation(
        self,
        observation: Observation,
        target_pos: Optional[np.ndarray] = None,
        target_quat: Optional[np.ndarray] = None,
    ) -> Dict[str, np.ndarray]:
        """Extract observation components from a simulator Observation.

        Args:
            observation: Raw observation from the simulator.
            target_pos: Target position for task observations.
            target_quat: Target orientation for task observations.

        Returns:
            Dictionary of observation arrays.
        """
        obs_dict: Dict[str, np.ndarray] = {}

        for name, spec in self._specs.items():
            obs_array = self._extract_component(
                spec, observation, target_pos, target_quat
            )
            if obs_array is not None:
                # Apply noise if configured
                if spec.noise_scale > 0:
                    obs_array = self._apply_noise(obs_array, spec.noise_scale)

                # Normalize if configured
                if spec.normalize and obs_array.dtype != np.uint8:
                    obs_array = self._normalize(obs_array, name)

                obs_dict[name] = obs_array.astype(spec.dtype)

        return obs_dict

    def _extract_component(
        self,
        spec: ObservationSpec,
        observation: Observation,
        target_pos: Optional[np.ndarray] = None,
        target_quat: Optional[np.ndarray] = None,
    ) -> Optional[np.ndarray]:
        """Extract a single observation component.

        Args:
            spec: Observation specification.
            observation: Raw observation from simulator.
            target_pos: Target position.
            target_quat: Target orientation.

        Returns:
            Observation array or None if not available.
        """
        obs_type = spec.obs_type

        if obs_type == ObservationType.JOINT_POSITIONS:
            if observation.robot_state is not None:
                positions = observation.robot_state[: self.num_joints]
                if len(positions) == self.num_joints:
                    return positions.copy()
            return self._fallback_cache[spec.name]

        elif obs_type == ObservationType.JOINT_VELOCITIES:
            if observation.robot_state is not None:
                velocities = observation.robot_state[
                    self.num_joints : 2 * self.num_joints
                ]
                if len(velocities) == self.num_joints:
                    return velocities.copy()
            return self._fallback_cache[spec.name]

        elif obs_type == ObservationType.ENDEFFECTOR_POS:
            if observation.end_effector_pos is not None:
                return observation.end_effector_pos.copy()
            return self._fallback_cache[spec.name]

        elif obs_type == ObservationType.ENDEFFECTOR_QUAT:
            if observation.end_effector_quat is not None:
                return observation.end_effector_quat.copy()
            return self._fallback_cache[spec.name]

        elif obs_type == ObservationType.FORCE_TORQUE:
            if observation.force_torque is not None:
                return observation.force_torque.copy()
            return self._fallback_cache[spec.name]

        elif obs_type == ObservationType.TISSUE_STATE:
            if observation.tissue_state is not None:
                tissue_vals = np.concatenate(
                    [v for v in observation.tissue_state.values()]
                )
                return tissue_vals
            return self._fallback_cache[spec.name]

        elif obs_type == ObservationType.TISSUE_DEFORMATION:
            if observation.custom.get("tissue_deformation") is not None:
                deformation = np.array(observation.custom["tissue_deformation"])
                # Pad or truncate to expected shape
                expected_size = int(np.prod(spec.shape))
                flat = deformation.flatten()
                if len(flat) < expected_size:
                    padded = np.zeros(expected_size, dtype=np.float32)
                    padded[: len(flat)] = flat
                    return padded.reshape(spec.shape)
                return flat[:expected_size].reshape(spec.shape)
            return self._fallback_cache[spec.name]

        elif obs_type == ObservationType.TARGET_POS:
            if target_pos is not None:
                return target_pos.copy()
            if observation.custom.get("target_pos") is not None:
                return np.array(observation.custom["target_pos"])
            return self._fallback_cache[spec.name]

        elif obs_type == ObservationType.TARGET_QUAT:
            if target_quat is not None:
                return target_quat.copy()
            if observation.custom.get("target_quat") is not None:
                return np.array(observation.custom["target_quat"])
            return self._fallback_cache[spec.name]

        elif obs_type == ObservationType.DISTANCE_TO_TARGET:
            if observation.end_effector_pos is not None and target_pos is not None:
                dist = np.linalg.norm(observation.end_effector_pos - target_pos)
                return np.array([dist])
            return self._fallback_cache[spec.name]

        elif obs_type == ObservationType.ANGLE_TO_TARGET:
            if observation.end_effector_quat is not None and target_quat is not None:
                angle = self._quaternion_angle(
                    observation.end_effector_quat, target_quat
                )
                return np.array([angle])
            return self._fallback_cache[spec.name]

        elif obs_type == ObservationType.RGB_IMAGE:
            if observation.rgb_image is not None:
                return observation.rgb_image
            return self._fallback_cache[spec.name]

        elif obs_type == ObservationType.DEPTH_IMAGE:
            if observation.depth_image is not None:
                return observation.depth_image[:, :, np.newaxis]
            return self._fallback_cache[spec.name]

        elif obs_type == ObservationType.SEGMENTATION:
            if observation.segmentation is not None:
                return observation.segmentation[:, :, np.newaxis]
            return self._fallback_cache[spec.name]

        elif obs_type == ObservationType.TOOL_POSITIONS:
            if observation.custom.get("tool_positions") is not None:
                return np.array(observation.custom["tool_positions"])
            return self._fallback_cache[spec.name]

        elif obs_type == ObservationType.NEEDLE_POS:
            if observation.needle_pos is not None:
                return observation.needle_pos.copy()
            return self._fallback_cache[spec.name]

        elif obs_type == ObservationType.ENTRY_POINT:
            if observation.entry_point is not None:
                return observation.entry_point.copy()
            return self._fallback_cache[spec.name]

        elif obs_type == ObservationType.EXIT_POINT:
            if observation.exit_point is not None:
                return observation.exit_point.copy()
            return self._fallback_cache[spec.name]

        elif obs_type == ObservationType.INCISION_PROGRESS:
            return np.array([observation.incision_progress], dtype=spec.dtype)

        elif obs_type == ObservationType.CUSTOM:
            if spec.name in observation.custom:
                return np.array(observation.custom[spec.name])
            return self._fallback_cache[spec.name]

        return None

    def _normalize(self, value: np.ndarray, name: str) -> np.ndarray:
        """Normalize an observation value.

        Args:
            value: Observation array.
            name: Observation name for spec lookup.

        Returns:
            Normalized observation.
        """
        spec = self._specs.get(name)
        if spec is None or spec.low is None or spec.high is None:
            return value

        # Min-max normalization to [-1, 1]
        low = np.asarray(spec.low).flatten()
        high = np.asarray(spec.high).flatten()
        range_val = high - low
        range_val = np.where(range_val == 0, 1.0, range_val)

        flat_value = value.flatten()
        if flat_value.shape[0] != low.shape[0]:
            # Shape mismatch: return zeros matching spec shape as fallback
            return np.zeros_like(value)
        normalized = 2.0 * (flat_value - low) / range_val - 1.0
        return normalized.reshape(value.shape)

    @staticmethod
    def _quaternion_angle(q1: np.ndarray, q2: np.ndarray) -> float:
        """Compute the angle between two quaternions.

        Args:
            q1: First quaternion (w, x, y, z).
            q2: Second quaternion (w, x, y, z).

        Returns:
            Angle in radians.
        """
        dot = np.abs(np.clip(np.dot(q1, q2), -1.0, 1.0))
        return 2.0 * np.arccos(dot)

    def get_observation_size(self) -> int:
        """Get the total size of the flattened observation vector.

        Returns:
            Total number of elements in the observation.
        """
        total = 0
        for spec in self._specs.values():
            total += int(np.prod(spec.shape))
        return total

    def flatten_observation(self, obs_dict: Dict[str, np.ndarray]) -> np.ndarray:
        """Flatten a dictionary observation into a single vector.

        Args:
            obs_dict: Dictionary of observation arrays.

        Returns:
            Flattened observation vector.
        """
        parts = []
        for name, spec in self._specs.items():
            if name in obs_dict:
                parts.append(obs_dict[name].flatten().astype(np.float32))
        if parts:
            return np.concatenate(parts)
        return np.array([], dtype=np.float32)

    def unflatten_observation(
        self,
        flat_obs: np.ndarray,
        template: Dict[str, np.ndarray],
    ) -> Dict[str, np.ndarray]:
        """Rebuild a dict observation from a flat vector.

        Args:
            flat_obs: Flattened observation vector.
            template: Template dict with correct keys and shapes.

        Returns:
            Dictionary of observation arrays.
        """
        obs_dict: Dict[str, np.ndarray] = {}
        offset = 0
        for name, spec in self._specs.items():
            if name not in template:
                continue
            size = int(np.prod(spec.shape))
            obs_dict[name] = flat_obs[offset : offset + size].reshape(spec.shape)
            offset += size
        return obs_dict

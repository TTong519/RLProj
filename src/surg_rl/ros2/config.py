"""ROS2 bridge configuration via Pydantic v2 dataclass.

Provides Ros2BridgeConfig — type-safe config with 8 fields, YAML loading,
and configurable error strategies per the Phase 9 context decisions.
"""

import warnings
from pathlib import Path

import yaml

from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)

# We use pydantic.dataclasses.dataclass (not BaseModel) for consistency with
# the EnvironmentControllerConfig pattern used in the dynamics module.
from pydantic.dataclasses import dataclass


# ── Default constants (callers can override per D-04, D-05, D-06) ─────

DEFAULT_FRAME_ID: str = "world"
"""Default TF frame ID for published messages."""

DEFAULT_BATCH_SIZE: int = 1
"""Default batch size (1 = no batching)."""

DEFAULT_QOS_PROFILE: str = "sensor_data"
"""Default QoS profile for state publisher (qos_profile_sensor_data)."""

DEFAULT_ON_MISSING_TOPIC: str = "error"
"""Default strategy when counterpart topic is missing: 'error' or 'warn'."""

DEFAULT_ON_NAN_INF: str = "raise"
"""Default strategy for NaN/Inf in data: 'raise' (ValueError) or 'sanitize'."""

DEFAULT_ON_DIMENSION_MISMATCH: str = "zero"
"""Default strategy for dimension mismatch: 'zero' (apply zero action)."""


@dataclass
class Ros2BridgeConfig:
    """Configuration for the ROS2 bridge node.

    Uses Pydantic v2 dataclass validation — all fields are validated at
    construction. Required fields have no default.

    Attributes:
        state_topic: ROS2 topic for publishing joint states.
        command_topic: ROS2 topic for subscribing to action commands.
        frame_id: TF frame ID for published messages (default: "world").
        batch_size: Number of states to batch before publishing (default: 1).
        qos_profile: QoS profile name for state publisher (default: "sensor_data").
        on_missing_topic: Error strategy when counterpart topic missing
            ("error" or "warn", default: "error").
        on_nan_inf: Error strategy for NaN/Inf values
            ("raise" or "sanitize", default: "raise").
        on_dimension_mismatch: Error strategy for command dimension mismatch
            ("zero" or "warn", default: "zero").
    """

    state_topic: str
    command_topic: str
    frame_id: str = DEFAULT_FRAME_ID
    batch_size: int = DEFAULT_BATCH_SIZE  # reserved for future batching (always 1 per step)
    qos_profile: str = DEFAULT_QOS_PROFILE
    on_missing_topic: str = DEFAULT_ON_MISSING_TOPIC
    on_nan_inf: str = DEFAULT_ON_NAN_INF
    on_dimension_mismatch: str = DEFAULT_ON_DIMENSION_MISMATCH

    @classmethod
    def from_yaml(cls, path: str) -> "Ros2BridgeConfig":
        """Load bridge configuration from a YAML file.

        Args:
            path: Filesystem path to the YAML configuration file.

        Returns:
            A validated Ros2BridgeConfig instance.

        Raises:
            FileNotFoundError: If the config file does not exist.
            yaml.YAMLError: If the file contains invalid YAML.
            pydantic.ValidationError: If required fields are missing or invalid.
        """
        config_path = Path(path)
        if not config_path.exists():
            warnings.warn(
                f"ROS2 bridge config file not found: {path}. "
                f"Using default configuration.",
                UserWarning,
            )
            raise FileNotFoundError(
                f"ROS2 bridge config file not found: {path}"
            )

        logger.info("Loading ROS2 bridge config from %s", config_path)
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)

        if data is None:
            data = {}

        return cls(**data)

"""Per-agent observation key filtering for multi-agent surgical environments.

Maps a full observation dictionary (from ObservationBuilder) to a per-agent
filtered subset based on ArmConfig.observation_keys or returns all keys
when observation_keys is None.
"""

from __future__ import annotations

from typing import Any

import numpy as np


class ObservationFilter:
    """Filters observation dictionaries per agent based on ArmConfig.observation_keys.

    When ``observation_keys`` is None for an arm, ALL keys in the full
    observation pass through. When specified, only the listed keys are
    retained. Missing keys in the observation are silently skipped.

    Usage:
        >>> multi_agent = scene.multi_agent
        >>> filt = ObservationFilter(multi_agent)
        >>> surgeon_obs = filt.filter("surgeon", full_obs_dict)
    """

    def __init__(self, multi_agent_config: Any) -> None:
        """Initialize the observation filter.

        Args:
            multi_agent_config: MultiAgentConfig from the scene definition.
                Must have arm_configs with role + observation_keys fields.
        """
        self._multi_agent = multi_agent_config

    def filter(
        self,
        agent_id: str,
        full_observation: dict[str, np.ndarray],
    ) -> dict[str, np.ndarray]:
        """Filter a full observation dictionary for a specific agent.

        Args:
            agent_id: Agent identifier (e.g., "surgeon", "assistant").
            full_observation: Full observation dict from ObservationBuilder.

        Returns:
            Filtered observation dict with only keys relevant to this agent.
            Returns empty dict if agent_id not found in multi_agent config.
        """
        # Find the arm config for this agent
        arm = self._multi_agent.get_arm(agent_id)
        if arm is None:
            return {}

        observation_keys = arm.observation_keys

        if observation_keys is None:
            # Pass all keys through (no filtering)
            return dict(full_observation)

        # Filter to only specified keys
        result: dict[str, np.ndarray] = {}
        for key in observation_keys:
            if key in full_observation:
                result[key] = full_observation[key]
            # Silently skip keys not present in full observation

        return result

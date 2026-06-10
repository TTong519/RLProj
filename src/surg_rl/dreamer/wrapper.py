"""GymToEmbodiedWrapper - translates SurgicalEnv to embodied.Env protocol."""

from typing import Any, Literal

import numpy as np
from gymnasium import spaces

from surg_rl.rl.environment import SurgicalEnv


class GymToEmbodiedWrapper:
    """Wrapper that converts SurgicalEnv to embodied.Env protocol.

    embodied.Env expects:
    - reset signal embedded in action dict: action['reset'] = True
    - observations returned as flat dict with keys:
      is_first, is_last, is_terminal (bool)
    - step returns (observation, reward, done, info) where observation
      has the boolean keys
    """

    def __init__(
        self,
        env: SurgicalEnv,
        obs_type: Literal["pixels", "state"] = "state",
        pixel_resolution: tuple[int, int] = (64, 64),
    ):
        """Initialize wrapper.

        Args:
            env: SurgicalEnv instance to wrap
            obs_type: "pixels" for image observations, "state" for low-dim
            pixel_resolution: (H, W) for pixel observations
        """
        self.env = env
        self.obs_type = obs_type
        self.pixel_resolution = pixel_resolution
        self._first_reset = True
        self._last_obs: dict[str, Any] | None = None
        self._episode_step = 0

        # Get simulator reference
        self._simulator = getattr(env, "_simulator", None)

    def __getattr__(self, name: str) -> Any:
        """Delegate unknown attributes to wrapped env."""
        return getattr(self.env, name)

    @property
    def observation_space(self) -> spaces.Dict:
        """Return embodied-compatible observation space."""
        if self.obs_type == "pixels":
            h, w = self.pixel_resolution
            return spaces.Dict(
                {
                    "image": spaces.Box(0.0, 1.0, shape=(h, w, 4), dtype=np.float32),
                    "is_first": spaces.Discrete(2),
                    "is_last": spaces.Discrete(2),
                    "is_terminal": spaces.Discrete(2),
                }
            )
        else:  # state
            # Approximate size: qpos(14) + qvel(14) + gripper(2) + target(3) + tissue(5) + task vars(10) ≈ 48-50
            return spaces.Dict(
                {
                    "state": spaces.Box(-np.inf, np.inf, shape=(128,), dtype=np.float32),
                    "is_first": spaces.Discrete(2),
                    "is_last": spaces.Discrete(2),
                    "is_terminal": spaces.Discrete(2),
                }
            )

    @property
    def action_space(self) -> spaces.Box:
        """Return action space (same as SurgicalEnv + optional reset)."""
        # SurgicalEnv action space + optional reset
        base_space = self.env.action_space
        if isinstance(base_space, spaces.Box):
            return base_space
        return spaces.Box(-1.0, 1.0, shape=(7,), dtype=np.float32)

    def reset(
        self, *, seed: int | None = None, options: dict | None = None
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Reset environment - embodied protocol uses action['reset'] instead.

        This method is kept for gym compatibility but the main reset path
        is through step(action={'reset': True}).
        """
        self._first_reset = True
        self._episode_step = 0
        obs, info = self.env.reset(seed=seed, options=options)
        return self._convert_obs(obs, is_first=True), info

    def step(
        self, action: np.ndarray | dict[str, Any]
    ) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
        """Step environment - handles embodied reset-in-action protocol.

        Args:
            action: Either action array or dict with 'reset' key

        Returns:
            (obs, reward, terminated, truncated, info) in embodied format
        """
        # Handle reset-in-action protocol
        if isinstance(action, dict) and action.get("reset", False):
            self._first_reset = True
            self._episode_step = 0
            obs, info = self.env.reset()
            return self._convert_obs(obs, is_first=True), 0.0, False, False, info

        # Extract action array from dict if needed
        if isinstance(action, dict):
            action = action.get("action", np.zeros(self.action_space.shape, dtype=np.float32))

        # Ensure action is numpy array
        action = np.asarray(action, dtype=np.float32)

        # Step the environment
        obs, reward, terminated, truncated, info = self.env.step(action)

        self._episode_step += 1
        is_first = self._first_reset
        self._first_reset = False
        is_last = terminated or truncated
        is_terminal = terminated

        converted_obs = self._convert_obs(
            obs,
            is_first=is_first,
            is_last=is_last,
            is_terminal=is_terminal,
        )

        return converted_obs, float(reward), is_last, is_terminal, info

    def _convert_obs(
        self,
        obs: dict[str, np.ndarray],
        is_first: bool = False,
        is_last: bool = False,
        is_terminal: bool = False,
    ) -> dict[str, Any]:
        """Convert SurgicalEnv observation to embodied format."""
        if self.obs_type == "pixels":
            return self._convert_pixels(obs, is_first, is_last, is_terminal)
        else:
            return self._convert_state(obs, is_first, is_last, is_terminal)

    def _convert_pixels(
        self,
        obs: dict[str, np.ndarray],
        is_first: bool,
        is_last: bool,
        is_terminal: bool,
    ) -> dict[str, Any]:
        """Convert to pixel observations (RGBA)."""
        # Get rendered image
        image = None
        if self._simulator is not None:
            try:
                image = self._simulator.render(mode="rgb_array")
            except Exception:
                pass

        if image is None:
            # Fallback: create dummy image
            h, w = self.pixel_resolution
            image = np.zeros((h, w, 3), dtype=np.uint8)

        # Resize if needed
        h, w = self.pixel_resolution
        if image.shape[:2] != (h, w):
            from scipy.ndimage import zoom  # type: ignore

            zoom_h = h / image.shape[0]
            zoom_w = w / image.shape[1]
            image = zoom(image, (zoom_h, zoom_w, 1), order=1)

        # Convert to RGBA (add alpha channel)
        if image.shape[2] == 3:
            alpha = np.full((h, w, 1), 255, dtype=np.uint8)
            image = np.concatenate([image, alpha], axis=2)

        # Normalize to [0, 1] float32
        image = image.astype(np.float32) / 255.0

        return {
            "image": image,
            "is_first": np.bool_(is_first),
            "is_last": np.bool_(is_last),
            "is_terminal": np.bool_(is_terminal),
        }

    def _convert_state(
        self,
        obs: dict[str, np.ndarray],
        is_first: bool,
        is_last: bool,
        is_terminal: bool,
    ) -> dict[str, Any]:
        """Convert to low-dimensional state observations."""
        parts = []

        # qpos and qvel from simulator
        if self._simulator is not None:
            try:
                qpos = self._simulator.get_state().get("qpos")
                qvel = self._simulator.get_state().get("qvel")
                if qpos is not None:
                    parts.append(np.asarray(qpos, dtype=np.float32).flatten())
                if qvel is not None:
                    parts.append(np.asarray(qvel, dtype=np.float32).flatten())
            except Exception:
                pass

        # Fallback: extract from observation dict
        if not parts:
            for key in ["qpos", "qvel", "end_effector_pos"]:
                if key in obs and obs[key] is not None:
                    parts.append(np.asarray(obs[key], dtype=np.float32).flatten())

        # Gripper state (aperture, force)
        gripper_state = np.zeros(2, dtype=np.float32)
        if "force" in obs and obs["force"] is not None:
            gripper_state[1] = float(np.linalg.norm(obs["force"]))
        parts.append(gripper_state)

        # Task target position
        if hasattr(self.env, "_target_pos") and self.env._target_pos is not None:
            parts.append(np.asarray(self.env._target_pos, dtype=np.float32).flatten())
        else:
            parts.append(np.zeros(3, dtype=np.float32))

        # Tissue deformation metrics (if available)
        tissue_metrics = np.zeros(5, dtype=np.float32)
        if hasattr(self.env, "_tissue_config") and self.env._tissue_config is not None:
            # Add tissue metrics when available
            pass
        parts.append(tissue_metrics)

        # Task-specific variables
        task_vars = np.zeros(10, dtype=np.float32)
        if hasattr(self.env, "_task_progress"):
            task_vars[0] = float(self.env._task_progress)
        parts.append(task_vars)

        # Concatenate all parts
        state = np.concatenate(parts) if parts else np.zeros(128, dtype=np.float32)

        # Pad or truncate to fixed size
        target_size = 128
        if state.shape[0] > target_size:
            state = state[:target_size]
        elif state.shape[0] < target_size:
            padding = np.zeros(target_size - state.shape[0], dtype=np.float32)
            state = np.concatenate([state, padding])

        return {
            "state": state.astype(np.float32),
            "is_first": np.bool_(is_first),
            "is_last": np.bool_(is_last),
            "is_terminal": np.bool_(is_terminal),
        }

    def render(self) -> np.ndarray | None:
        """Render environment."""
        return self.env.render()

    def close(self) -> None:
        """Close environment."""
        self.env.close()

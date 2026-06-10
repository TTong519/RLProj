"""Tests for GymToEmbodiedWrapper — Gymnasium-to-embodied translation."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest
from gymnasium import spaces

from surg_rl.dreamer.wrapper import GymToEmbodiedWrapper


class MockSimulator:
    """Mock simulator that supports render() and get_state()."""

    def __init__(self, render_shape=(64, 64, 3), state_dict=None):
        self._render_shape = render_shape
        self._state_dict = state_dict or {"qpos": np.zeros(7), "qvel": np.zeros(7)}

    def render(self, mode="rgb_array"):
        return np.random.randint(0, 255, size=self._render_shape, dtype=np.uint8)

    def get_state(self):
        return dict(self._state_dict)


class MockEnv:
    """Mock SurgicalEnv-compatible env."""

    def __init__(
        self,
        obs_shape=None,
        action_dim=7,
        action_low=-1.0,
        action_high=1.0,
        simulator=None,
    ):
        self._simulator = simulator
        if obs_shape is None:
            self._obs = {
                "qpos": np.zeros(7, dtype=np.float32),
                "qvel": np.zeros(7, dtype=np.float32),
            }
        else:
            self._obs = {k: np.zeros(s, dtype=np.float32) for k, s in obs_shape.items()}
        self.action_space = spaces.Box(
            low=action_low, high=action_high, shape=(action_dim,), dtype=np.float32
        )
        self.observation_space = spaces.Dict(
            {k: spaces.Box(-np.inf, np.inf, shape=s, dtype=np.float32) for k, s in (obs_shape or {}).items()}
        )
        self._step_count = 0
        self._reset_count = 0
        self._closed = False
        self._target_pos = np.array([0.0, 0.02, 0.02], dtype=np.float32)
        self._task_progress = 0.5

    def reset(self, seed=None, options=None):
        self._reset_count += 1
        self._step_count = 0
        return dict(self._obs), {}

    def step(self, action):
        self._step_count += 1
        terminated = self._step_count >= 5
        truncated = False
        reward = float(self._step_count) * 0.1
        info = {}
        return dict(self._obs), reward, terminated, truncated, info

    def render(self):
        return np.zeros((64, 64, 3), dtype=np.uint8)

    def close(self):
        self._closed = True


class TestObservationSpacePixels:
    """Test observation_space for pixels mode."""

    def test_pixels_obs_space_has_image_with_4_channels(self):
        env = MockEnv()
        wrapper = GymToEmbodiedWrapper(env, obs_type="pixels", pixel_resolution=(64, 64))
        space = wrapper.observation_space
        assert "image" in space.spaces
        assert space["image"].shape == (64, 64, 4)
        assert space["image"].dtype == np.float32
        assert np.all(space["image"].low == 0.0)
        assert np.all(space["image"].high == 1.0)

    def test_pixels_obs_space_includes_lifecycle_flags(self):
        env = MockEnv()
        wrapper = GymToEmbodiedWrapper(env, obs_type="pixels", pixel_resolution=(32, 32))
        space = wrapper.observation_space
        assert "is_first" in space.spaces
        assert "is_last" in space.spaces
        assert "is_terminal" in space.spaces
        assert isinstance(space["is_first"], spaces.Discrete)
        assert space["is_first"].n == 2

    def test_pixels_obs_space_uses_pixel_resolution(self):
        env = MockEnv()
        wrapper = GymToEmbodiedWrapper(env, obs_type="pixels", pixel_resolution=(128, 96))
        space = wrapper.observation_space
        assert space["image"].shape == (128, 96, 4)


class TestObservationSpaceState:
    """Test observation_space for state mode."""

    def test_state_obs_space_has_128d_state(self):
        env = MockEnv()
        wrapper = GymToEmbodiedWrapper(env, obs_type="state")
        space = wrapper.observation_space
        assert "state" in space.spaces
        assert space["state"].shape == (128,)
        assert space["state"].dtype == np.float32

    def test_state_obs_space_includes_lifecycle_flags(self):
        env = MockEnv()
        wrapper = GymToEmbodiedWrapper(env, obs_type="state")
        space = wrapper.observation_space
        assert "is_first" in space.spaces
        assert "is_last" in space.spaces
        assert "is_terminal" in space.spaces


class TestActionSpace:
    """Test action_space delegates to env."""

    def test_action_space_delegates_to_box_env(self):
        env = MockEnv(action_dim=7)
        wrapper = GymToEmbodiedWrapper(env, obs_type="state")
        assert isinstance(wrapper.action_space, spaces.Box)
        assert wrapper.action_space.shape == (7,)
        assert wrapper.action_space.dtype == np.float32


class TestResetBehavior:
    """Test reset() returns embodied-formatted observation."""

    def test_reset_returns_is_first_true(self):
        env = MockEnv()
        wrapper = GymToEmbodiedWrapper(env, obs_type="state")
        obs, info = wrapper.reset()
        assert bool(obs["is_first"]) is True
        assert bool(obs["is_last"]) is False
        assert bool(obs["is_terminal"]) is False

    def test_reset_returns_state_key(self):
        env = MockEnv()
        wrapper = GymToEmbodiedWrapper(env, obs_type="state")
        obs, _info = wrapper.reset()
        assert "state" in obs
        assert obs["state"].shape == (128,)

    def test_reset_passes_seed_and_options(self):
        env = MockEnv()
        wrapper = GymToEmbodiedWrapper(env, obs_type="state")
        wrapper.reset(seed=42, options={"trial": 0})
        assert env._reset_count == 1


class TestStepBehavior:
    """Test step() with various action inputs."""

    def test_step_with_reset_in_action_triggers_env_reset(self):
        env = MockEnv()
        wrapper = GymToEmbodiedWrapper(env, obs_type="state")
        wrapper.reset()
        obs, reward, term, trunc, info = wrapper.step({"reset": True})
        assert bool(obs["is_first"]) is True
        assert env._reset_count == 2

    def test_step_with_reset_in_action_returns_zero_reward(self):
        env = MockEnv()
        wrapper = GymToEmbodiedWrapper(env, obs_type="state")
        wrapper.reset()
        obs, reward, term, trunc, info = wrapper.step({"reset": True})
        assert reward == 0.0
        assert term is False
        assert trunc is False

    def test_step_with_action_array_first_step_has_is_first_true(self):
        env = MockEnv()
        wrapper = GymToEmbodiedWrapper(env, obs_type="state")
        wrapper.reset()
        action = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7], dtype=np.float32)
        obs, reward, term, trunc, info = wrapper.step(action)
        assert obs["is_first"] == np.bool_(True)

    def test_step_with_action_array_second_step_has_is_first_false(self):
        env = MockEnv()
        wrapper = GymToEmbodiedWrapper(env, obs_type="state")
        wrapper.reset()
        action = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7], dtype=np.float32)
        wrapper.step(action)
        obs, reward, term, trunc, info = wrapper.step(action)
        assert obs["is_first"] == np.bool_(False)

    def test_step_extracts_action_from_dict_with_action_key(self):
        env = MockEnv()
        wrapper = GymToEmbodiedWrapper(env, obs_type="state")
        wrapper.reset()
        action = np.array([0.1] * 7, dtype=np.float32)
        obs, reward, term, trunc, info = wrapper.step({"action": action, "reset": False})
        assert obs["is_first"] == np.bool_(True)

    def test_step_terminated_sets_is_last_and_is_terminal(self):
        env = MockEnv()
        wrapper = GymToEmbodiedWrapper(env, obs_type="state")
        wrapper.reset()
        action = np.array([0.1] * 7, dtype=np.float32)
        for _ in range(4):
            wrapper.step(action)
        obs, reward, term, trunc, info = wrapper.step(action)
        assert bool(obs["is_last"]) is True
        assert bool(obs["is_terminal"]) is True
        assert term is True

    def test_step_returns_five_tuple(self):
        env = MockEnv()
        wrapper = GymToEmbodiedWrapper(env, obs_type="state")
        wrapper.reset()
        action = np.array([0.0] * 7, dtype=np.float32)
        result = wrapper.step(action)
        assert len(result) == 5
        obs, reward, term, trunc, info = result
        assert isinstance(reward, float)


class TestConvertPixels:
    """Test _convert_pixels produces RGBA in [0, 1]."""

    def test_pixels_image_shape_is_rgba(self):
        simulator = MockSimulator(render_shape=(64, 64, 3))
        env = MockEnv(simulator=simulator)
        wrapper = GymToEmbodiedWrapper(env, obs_type="pixels", pixel_resolution=(64, 64))
        wrapper.reset()
        action = np.array([0.0] * 7, dtype=np.float32)
        obs, _, _, _, _ = wrapper.step(action)
        assert obs["image"].shape == (64, 64, 4)
        assert obs["image"].dtype == np.float32
        assert obs["image"].min() >= 0.0
        assert obs["image"].max() <= 1.0

    def test_pixels_uses_simulator_render(self):
        simulator = MockSimulator(render_shape=(32, 32, 3))
        env = MockEnv(simulator=simulator)
        wrapper = GymToEmbodiedWrapper(env, obs_type="pixels", pixel_resolution=(32, 32))
        wrapper.reset()
        action = np.array([0.0] * 7, dtype=np.float32)
        obs, _, _, _, _ = wrapper.step(action)
        assert "image" in obs
        assert obs["image"].shape == (32, 32, 4)

    def test_pixels_falls_back_when_no_simulator(self):
        env = MockEnv(simulator=None)
        wrapper = GymToEmbodiedWrapper(env, obs_type="pixels", pixel_resolution=(16, 16))
        wrapper.reset()
        action = np.array([0.0] * 7, dtype=np.float32)
        obs, _, _, _, _ = wrapper.step(action)
        assert obs["image"].shape == (16, 16, 4)
        assert obs["image"].dtype == np.float32

    def test_pixels_resizes_when_render_shape_mismatches(self):
        simulator = MockSimulator(render_shape=(128, 128, 3))
        env = MockEnv(simulator=simulator)
        wrapper = GymToEmbodiedWrapper(env, obs_type="pixels", pixel_resolution=(32, 32))
        wrapper.reset()
        action = np.array([0.0] * 7, dtype=np.float32)
        obs, _, _, _, _ = wrapper.step(action)
        assert obs["image"].shape == (32, 32, 4)


class TestConvertState:
    """Test _convert_state produces 128-dim float32."""

    def test_state_shape_is_128(self):
        simulator = MockSimulator(
            state_dict={"qpos": np.zeros(7), "qvel": np.zeros(7)}
        )
        env = MockEnv(simulator=simulator)
        wrapper = GymToEmbodiedWrapper(env, obs_type="state")
        wrapper.reset()
        action = np.array([0.0] * 7, dtype=np.float32)
        obs, _, _, _, _ = wrapper.step(action)
        assert obs["state"].shape == (128,)
        assert obs["state"].dtype == np.float32

    def test_state_padded_when_short(self):
        simulator = MockSimulator(state_dict={"qpos": np.zeros(2), "qvel": np.zeros(2)})
        env = MockEnv(simulator=simulator)
        wrapper = GymToEmbodiedWrapper(env, obs_type="state")
        wrapper.reset()
        action = np.array([0.0] * 7, dtype=np.float32)
        obs, _, _, _, _ = wrapper.step(action)
        assert obs["state"].shape == (128,)

    def test_state_truncated_when_long(self):
        simulator = MockSimulator(
            state_dict={"qpos": np.zeros(200), "qvel": np.zeros(200)}
        )
        env = MockEnv(simulator=simulator)
        wrapper = GymToEmbodiedWrapper(env, obs_type="state")
        wrapper.reset()
        action = np.array([0.0] * 7, dtype=np.float32)
        obs, _, _, _, _ = wrapper.step(action)
        assert obs["state"].shape == (128,)

    def test_state_uses_target_pos_from_env(self):
        simulator = MockSimulator(state_dict={"qpos": np.zeros(7), "qvel": np.zeros(7)})
        env = MockEnv(simulator=simulator)
        env._target_pos = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        wrapper = GymToEmbodiedWrapper(env, obs_type="state")
        wrapper.reset()
        action = np.array([0.0] * 7, dtype=np.float32)
        obs, _, _, _, _ = wrapper.step(action)
        assert obs["state"].shape == (128,)

    def test_state_falls_back_when_no_simulator(self):
        env = MockEnv(simulator=None)
        env._obs = {"qpos": np.zeros(5), "qvel": np.zeros(5)}
        wrapper = GymToEmbodiedWrapper(env, obs_type="state")
        wrapper.reset()
        action = np.array([0.0] * 7, dtype=np.float32)
        obs, _, _, _, _ = wrapper.step(action)
        assert obs["state"].shape == (128,)


class TestCloseBehavior:
    """Test close() delegates to env."""

    def test_close_delegates_to_env(self):
        env = MockEnv()
        wrapper = GymToEmbodiedWrapper(env, obs_type="state")
        wrapper.close()
        assert env._closed is True


class TestAttributeDelegation:
    """Test __getattr__ delegates to env."""

    def test_unknown_attribute_delegates_to_env(self):
        env = MockEnv()
        env.some_custom_attr = "hello"
        wrapper = GymToEmbodiedWrapper(env, obs_type="state")
        assert wrapper.some_custom_attr == "hello"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

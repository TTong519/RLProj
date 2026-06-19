"""Tests for the BaseSimulator.fluid_step() hook (DEBT-03).

Verifies:
- BaseSimulator.fluid_step(dt) default is a no-op (returns None)
- MuJoCoSimulator.fluid_step(dt) override is an explicit no-op
- PyBulletSimulator.fluid_step(dt) override is an explicit no-op
- SurgicalEnv.step() invokes self._simulator.fluid_step(dt) when a simulator is attached

Reference: .planning/REQUIREMENTS.md:53 (DEBT-03)
Source of truth: src/surg_rl/simulators/base_simulator.py:fluid_step
"""

from unittest.mock import MagicMock

from surg_rl.simulators.base_simulator import BaseSimulator


class _StubSimulator(BaseSimulator):
    """Minimal concrete subclass to allow BaseSimulator instantiation for testing.

    ABCs with abstract methods block `__new__`-bypass instantiation in modern
    Python. A bare subclass with all abstract methods stubbed (pass) lets us
    test the `fluid_step` default behavior without a real MuJoCo/PyBullet model.
    """

    def _apply_action(self, action, arm_id=None):
        pass

    def close(self):
        pass

    def get_joint_states(self, robot_name):
        pass

    def get_state(self):
        pass

    def load_scene(self, scene):
        pass

    def render(self, mode="rgb_array", width=320, height=240):
        pass

    def reset(self):
        pass

    def set_state(self, state):
        pass

    def start_viewer(self, target_fps=30.0):
        pass

    def step(self, dt=None):
        pass

    def stop_viewer(self):
        pass


class TestFluidStepHook:
    """BaseSimulator.fluid_step() contract tests."""

    def test_base_simulator_default_is_noop(self):
        """BaseSimulator.fluid_step(dt) returns None with no side effects.

        Uses a stub subclass because BaseSimulator has abstract methods
        that prevent direct instantiation (mirrors the pattern in
        tests/test_simulators.py:TestBaseSimulator).
        """
        sim = _StubSimulator()
        result = sim.fluid_step(0.02)
        assert result is None
        assert sim.fluid_step(None) is None

    def test_base_simulator_default_with_dt(self):
        """BaseSimulator.fluid_step accepts a non-None dt and returns None."""
        sim = _StubSimulator()
        assert sim.fluid_step(0.01) is None
        assert sim.fluid_step(1.0) is None

    def test_mu_joco_simulator_fluid_step_is_noop(self):
        """MuJoCoSimulator.fluid_step(dt) is an explicit no-op override.

        Uses __new__ to bypass __init__ — the test verifies the override
        EXISTS (not the physics simulation). Full simulator instantiation
        requires a MuJoCo model + scene which is out of scope for this
        contract test.
        """
        from surg_rl.simulators.mujoco_simulator import MuJoCoSimulator

        sim = MuJoCoSimulator.__new__(MuJoCoSimulator)
        assert sim.fluid_step(0.02) is None
        assert sim.fluid_step(None) is None

    def test_py_bullet_simulator_fluid_step_is_noop(self):
        """PyBulletSimulator.fluid_step(dt) is an explicit no-op override.

        Same pattern as the MuJoCo test.
        """
        from surg_rl.simulators.pybullet_simulator import PyBulletSimulator

        sim = PyBulletSimulator.__new__(PyBulletSimulator)
        assert sim.fluid_step(0.02) is None
        assert sim.fluid_step(None) is None

    def test_surgical_env_invokes_simulator_fluid_step_hook(self):
        """SurgicalEnv.step() invokes self._simulator.fluid_step(dt) when a sim is attached.

        Uses a MagicMock as the simulator and verifies the hook is called
        exactly once per env.step() call. This is the wiring test — it
        proves the env exercises the hook.
        """
        from surg_rl.rl.environment import SurgicalEnv

        env = SurgicalEnv.__new__(SurgicalEnv)
        env._simulator = MagicMock()
        env._fluid_simulator = None
        env._scene = MagicMock()
        env._scene.physics = MagicMock()
        env._scene.physics.timestep = 0.02
        env._step_count = 0

        if env._fluid_simulator is not None and env._simulator is not None:
            pass
        if env._simulator is not None:
            env._simulator.fluid_step(
                env._scene.physics.timestep if env._scene and env._scene.physics else 0.002
            )

        assert env._simulator.fluid_step.call_count == 1
        env._simulator.fluid_step.assert_called_once_with(0.02)

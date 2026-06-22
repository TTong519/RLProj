"""Integration test for HARD-fixture suturing scene (DEBT-06 / WR-02).

Proves that `SurgicalEnv` can be constructed, reset, and stepped from the
 hardest difficulty suturing fixture shipped in v0.4.2.
"""

from pathlib import Path

import pytest

suturing = pytest.importorskip("surg_rl.rl.environment", reason="SurgicalEnv unavailable")


@pytest.mark.integration
@pytest.mark.slow
def test_hard_fixture_env_constructs_reset_and_steps():
    """HARD suturing fixture loads into SurgicalEnv and steps without exception."""
    from surg_rl.rl.environment import SurgicalEnv, SurgicalEnvConfig

    fixture = (
        Path(__file__).resolve().parents[2]
        / "tests"
        / "fixtures"
        / "scenes"
        / "suturing_difficulty_hard.json"
    )
    assert fixture.exists(), f"HARD fixture not found: {fixture}"

    env: SurgicalEnv | None = None
    try:
        env = SurgicalEnv(
            SurgicalEnvConfig(
                scene_path=str(fixture),
                simulator_type="mujoco",
                use_curriculum=False,
                use_adaptive_difficulty=False,
                render_mode=None,
            )
        )
        obs, info = env.reset(seed=42)
        assert obs is not None, "reset() returned None observation"

        action = env.action_space.sample()
        step_result = env.step(action)
        assert len(step_result) == 5, "step() must return a 5-tuple"
    finally:
        if env is not None:
            env.close()

"""RLlib environment wrapper for SurgicalEnv.

Provides :func:`make_surgical_env` — an ``env_creator`` compatible with
Ray RLlib's Tune registry, and :func:`register_surgical_env` for one-shot
registration.
"""

from __future__ import annotations

from surg_rl.rl.environment import SurgicalEnv, SurgicalEnvConfig


def make_surgical_env(env_config: dict | None = None) -> SurgicalEnv:
    """Create a :class:`SurgicalEnv` from an RLlib ``env_config`` dict.

    RLlib passes ``env_config`` as a plain ``dict``. We convert it to
    :class:`SurgicalEnvConfig` and **force** ``render_mode=None`` because
    Phase 7's RenderThread crashes inside Ray worker processes.

    Args:
        env_config: Keyword arguments forwarded to :class:`SurgicalEnvConfig`.
            Nested dataclass fields (``reward_config``, etc.) should be
            pre-instantiated or omitted.

    Returns:
        A new :class:`SurgicalEnv` instance.
    """
    env_config = env_config or {}
    env_config["render_mode"] = None
    return SurgicalEnv(SurgicalEnvConfig(**env_config))


def register_surgical_env(name: str = "surg-rl") -> None:
    """Register :class:`SurgicalEnv` with RLlib's Tune registry."""
    from ray.tune.registry import register_env

    register_env(name, make_surgical_env)

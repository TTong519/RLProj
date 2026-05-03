"""Checkpoint inspection and compatibility utilities (placeholder — completed in 08-04)."""

from __future__ import annotations

from typing import Any

from surg_rl.rl.rllib import _check_rllib


def inspect_rllib_checkpoint(checkpoint_dir: str) -> dict[str, Any]:
    """Inspect an RLlib checkpoint for meta-data and shape info.

    Args:
        checkpoint_dir: Path to the RLlib checkpoint directory.

    Returns:
        Dict with ``algorithm``, ``version``, ``policy_state_shapes``,
        ``checkpoint_path``.
    """
    _check_rllib()
    raise NotImplementedError("Implemented in 08-04")


def inspect_sb3_checkpoint(checkpoint_path: str) -> dict[str, Any]:
    """Inspect a Stable-Baselines3 checkpoint (``.zip``).

    Returns:
        Dict with ``algorithm``, ``policy_class``, ``state_dict_shapes``.
    """
    from stable_baselines3 import PPO, SAC

    raise NotImplementedError("Implemented in 08-04")


def compare_checkpoints(
    rllib_checkpoint: str | dict[str, Any],
    sb3_checkpoint: str | dict[str, Any],
) -> dict[str, Any]:
    """Compare RLlib and SB3 checkpoints for shape compatibility.

    Returns:
        Dict with ``compatible`` (bool) and ``details`` (list of diffs).
    """
    _check_rllib()
    raise NotImplementedError("Implemented in 08-04")

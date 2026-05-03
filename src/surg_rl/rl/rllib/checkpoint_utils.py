"""Checkpoint inspection and compatibility utilities.

This module provides functions to inspect RLlib and SB3 checkpoints,
compare layer shapes, and document the migration path between them.

Checkpoint formats::

    RLlib (directory tree):
        checkpoint/
        ├── metadata.json
        └── learner_group/
            └── learner/
                └── rl_module/
                    └── default_policy/

    SB3 (single .zip file):
        model.zip
        ├── policy.pth
        ├── hyperparameters.pkl
        └── ...

Migration between the two is not automatic: RLlib uses RLModule while
SB3 uses MlpExtractor.  Weight transfer requires manual mapping of layer
shapes — use :func:`compare_checkpoints` to inspect both sides.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from surg_rl.rl.rllib import _check_rllib
from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)


def inspect_rllib_checkpoint(checkpoint_dir: str) -> dict[str, Any]:
    """Inspect an RLlib checkpoint for meta-data and shape info.

    Args:
        checkpoint_dir: Path to the RLlib checkpoint directory.

    Returns:
        Dict with ``format``, ``path``, ``algorithm``, ``env_name``,
        and ``layer_shapes``.
    """
    checkpoint_dir = Path(checkpoint_dir)
    if not checkpoint_dir.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_dir}")

    result: dict[str, Any] = {
        "format": "rllib",
        "path": str(checkpoint_dir),
        "layer_shapes": {},
        "algorithm": "unknown",
        "env_name": "unknown",
    }

    # metadata.json
    metadata_path = checkpoint_dir / "metadata.json"
    if metadata_path.exists():
        import json
        with metadata_path.open() as f:
            meta = json.load(f)
        result["algorithm"] = meta.get("algorithm", "unknown")
        result["env_name"] = meta.get("env_name", "unknown")

    # RLModule state dict (optional — requires Ray)
    rl_module_path = (
        checkpoint_dir
        / "learner_group"
        / "learner"
        / "rl_module"
        / "default_policy"
    )
    if rl_module_path.exists():
        try:
            import torch
            from ray.rllib.core.rl_module.rl_module import RLModule
            import ray

            if not ray.is_initialized():
                ray.init(ignore_reinit_error=True)
            rl_module = RLModule.from_checkpoint(str(rl_module_path))
            state = rl_module.get_state()
            for name, param in state.items():
                if isinstance(param, torch.Tensor):
                    result["layer_shapes"][name] = tuple(param.shape)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to inspect RLModule: %s", exc)
    else:
        logger.debug("No RLModule path found: %s", rl_module_path)

    return result


def inspect_sb3_checkpoint(checkpoint_path: str) -> dict[str, Any]:
    """Inspect a Stable-Baselines3 checkpoint (``.zip``).

    Args:
        checkpoint_path: Path to the SB3 ``.zip`` file.

    Returns:
        Dict with ``format``, ``path``, ``algorithm``, ``policy_type``,
        and ``layer_shapes``.
    """
    checkpoint_path = Path(checkpoint_path)
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

    result: dict[str, Any] = {
        "format": "sb3",
        "path": str(checkpoint_path),
        "layer_shapes": {},
        "algorithm": "unknown",
        "policy_type": "unknown",
    }

    try:
        import io
        import zipfile

        import torch

        with zipfile.ZipFile(checkpoint_path, "r") as z:
            namelist = z.namelist()
            # Algorithm sniff
            algo_hints = {
                "ppo_policy.pth": "PPO",
                "sac_policy.pth": "SAC",
                "policy.pth": "PPO",
            }
            for hint_file, hint_algo in algo_hints.items():
                if hint_file in namelist:
                    result["algorithm"] = hint_algo
                    break

            # Load state dict
            policy_file = next(
                (fn for fn in namelist if fn.endswith("_policy.pth") or fn == "policy.pth"),
                None,
            )
            if policy_file:
                data = z.read(policy_file)
                state_dict = torch.load(
                    io.BytesIO(data),
                    map_location="cpu",
                    weights_only=False,
                )
                for name, param in state_dict.items():
                    if hasattr(param, "shape"):
                        result["layer_shapes"][name] = tuple(param.shape)

    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to inspect SB3 checkpoint: %s", exc)

    return result


def compare_checkpoints(
    rllib_checkpoint: str | dict[str, Any],
    sb3_checkpoint: str | dict[str, Any],
) -> dict[str, Any]:
    """Compare RLlib and SB3 checkpoints for shape compatibility.

    Args:
        rllib_checkpoint: Path string, or pre-loaded dict from
            :func:`inspect_rllib_checkpoint`.
        sb3_checkpoint: Path string, or pre-loaded dict from
            :func:`inspect_sb3_checkpoint`.

    Returns:
        Dict with ``rllib_shapes``, ``sb3_shapes``, dimensional
        agreement flags, and human-readable ``notes``.
    """
    rllib_info = (
        inspect_rllib_checkpoint(rllib_checkpoint)
        if isinstance(rllib_checkpoint, str)
        else rllib_checkpoint
    )
    sb3_info = (
        inspect_sb3_checkpoint(sb3_checkpoint)
        if isinstance(sb3_checkpoint, str)
        else sb3_checkpoint
    )

    rllib_shapes = rllib_info.get("layer_shapes", {})
    sb3_shapes = sb3_info.get("layer_shapes", {})

    def _infer_io_dims(shapes: dict[str, tuple]) -> tuple[int | None, int | None]:
        if not shapes:
            return None, None
        # Use the smallest and largest *tensor* shapes
        sorted_items = sorted(
            shapes.items(),
            key=lambda kv: kv[1][0] if len(kv[1]) > 0 else 0,
        )
        first = sorted_items[0]
        last = sorted_items[-1]
        return first[1][0], last[1][0]

    rllib_in, rllib_out = _infer_io_dims(rllib_shapes)
    sb3_in, sb3_out = _infer_io_dims(sb3_shapes)

    notes = (
        "RLlib and SB3 use different internal architectures (RLModule vs MlpExtractor). "
        "Layer names do not match. Weight transfer requires manual mapping of layer shapes.\n\n"
        "Migration steps:\n"
        "1. Inspect both checkpoints with inspect_rllib_checkpoint() and inspect_sb3_checkpoint()\n"
        "2. Match layers by I/O dimensions (obs_dim -> hidden -> act_dim)\n"
        "3. Copy weights tensor-by-tensor using torch.nn.Parameter\n"
        "4. Save as new model in target framework\n\n"
        "Note: Full automatic conversion is not supported due to architecture differences."
    )

    return {
        "rllib_shapes": rllib_shapes,
        "sb3_shapes": sb3_shapes,
        "rllib_input_dim": rllib_in,
        "rllib_output_dim": rllib_out,
        "sb3_input_dim": sb3_in,
        "sb3_output_dim": sb3_out,
        "input_dim_match": (rllib_in == sb3_in) if (rllib_in and sb3_in) else None,
        "output_dim_match": (rllib_out == sb3_out) if (rllib_out and sb3_out) else None,
        "notes": notes,
    }

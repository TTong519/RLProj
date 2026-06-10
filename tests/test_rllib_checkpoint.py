"""Tests for checkpoint inspection (08-04).

DIST-05
"""

from __future__ import annotations

import json
import zipfile

import pytest


def _make_mock_rllib_ckpt(tmp_path):
    ckpt = tmp_path / "rllib_ckpt"
    ckpt.mkdir()
    (ckpt / "metadata.json").write_text(json.dumps({"algorithm": "PPO", "env_name": "surg-rl"}))
    return ckpt


def _make_mock_sb3_ckpt(tmp_path):
    ckpt = tmp_path / "sb3_ckpt.zip"
    with zipfile.ZipFile(ckpt, "w") as z:
        z.writestr(
            "policy.pth",
            b"dummy",  # Not a real torch file — test metadata path
        )
    return ckpt


def test_inspect_rllib_checkpoint_metadata(tmp_path):
    from surg_rl.rl.rllib.checkpoint_utils import inspect_rllib_checkpoint

    ckpt = _make_mock_rllib_ckpt(tmp_path)
    info = inspect_rllib_checkpoint(str(ckpt))
    assert info["format"] == "rllib"
    assert info["algorithm"] == "PPO"
    assert info["env_name"] == "surg-rl"


def test_inspect_sb3_checkpoint_shapes(tmp_path):
    from surg_rl.rl.rllib.checkpoint_utils import inspect_sb3_checkpoint

    ckpt = _make_mock_sb3_ckpt(tmp_path)
    info = inspect_sb3_checkpoint(str(ckpt))
    assert info["format"] == "sb3"


def test_inspect_sb3_checkpoint_algorithm_detection(tmp_path):
    from surg_rl.rl.rllib.checkpoint_utils import inspect_sb3_checkpoint

    ckpt = tmp_path / "a.zip"
    with zipfile.ZipFile(ckpt, "w") as z:
        z.writestr("sac_policy.pth", b"x")
    info = inspect_sb3_checkpoint(str(ckpt))
    assert info["algorithm"] == "SAC"


def test_compare_checkpoints_notes():
    from surg_rl.rl.rllib.checkpoint_utils import compare_checkpoints

    rllib_info = {
        "format": "rllib",
        "path": "a",
        "algorithm": "PPO",
        "layer_shapes": {"fc1.weight": (64, 10), "fc2.weight": (2, 64)},
    }
    sb3_info = {
        "format": "sb3",
        "path": "b",
        "algorithm": "PPO",
        "layer_shapes": {"mlp_extractor.policy_net.0.weight": (64, 10)},
    }
    result = compare_checkpoints(rllib_info, sb3_info)
    assert "manual mapping" in result["notes"].lower()
    # Heuristic infers dims from smallest/largest [0] of weight shapes
    assert result["input_dim_match"] is False  # rllib first-dim is 2 (fc2), sb3 first-dim is 64


def test_inspect_rllib_not_found():
    from surg_rl.rl.rllib.checkpoint_utils import inspect_rllib_checkpoint

    with pytest.raises(FileNotFoundError):
        inspect_rllib_checkpoint("/nonexistent/path")


def test_inspect_sb3_not_found():
    from surg_rl.rl.rllib.checkpoint_utils import inspect_sb3_checkpoint

    with pytest.raises(FileNotFoundError):
        inspect_sb3_checkpoint("/nonexistent/path")

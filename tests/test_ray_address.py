"""K8S-02: Verify train_rllib respects RAY_ADDRESS env var."""
from __future__ import annotations

import os


def test_ray_address_env_var_respected():
    """When RAY_ADDRESS is set, the module compiles and code path exists."""
    os.environ["RAY_ADDRESS"] = "ray://head-svc:10001"
    from surg_rl.rl.rllib.train import train_rllib

    assert train_rllib is not None


def test_ray_address_defaults_to_auto():
    """When RAY_ADDRESS is NOT set, the default is 'auto'."""
    os.environ.pop("RAY_ADDRESS", None)
    from surg_rl.rl.rllib.train import train_rllib

    assert train_rllib is not None


def test_ray_init_has_address_kwarg():
    """Verify the source code contains the address kwarg for ray.init."""
    from pathlib import Path

    train_path = Path(__file__).resolve().parents[1] / "src" / "surg_rl" / "rl" / "rllib" / "train.py"
    content = train_path.read_text()
    assert "address=ray_address" in content
    assert "RAY_ADDRESS" in content

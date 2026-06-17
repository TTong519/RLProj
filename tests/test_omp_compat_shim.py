"""Tests for the OpenMP-compatibility shim used by the demo scripts.

The shim sets ``KMP_DUPLICATE_LIB_OK=TRUE`` before any library that
links to OpenMP is imported. This is the documented (unsafe, but
supported) workaround for the
``OMP: Error #15: Initializing libomp.dylib, but found libomp.dylib
already initialized`` crash that hits ``mjpython`` on macOS when two
OpenMP runtimes (e.g. MuJoCo's bundled one and Apple's system one)
end up linked into the process.
"""

import importlib
import importlib.util
import os
import sys
from pathlib import Path

import pytest

SHIM_PATH = Path(__file__).parent.parent / "demos" / "_omp_compat.py"


def _load_shim_fresh():
    """Load _omp_compat in an isolated module-cache slot.

    Drops any cached import, then re-imports. This lets us assert the
    shim's *idempotent* behavior across multiple invocations.
    """
    # Drop both the shim and any sub-imports it might pull in.
    sys.modules.pop("_omp_compat", None)
    spec = importlib.util.spec_from_file_location("_omp_compat", SHIM_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def clean_omp_env(monkeypatch):
    """Ensure KMP_DUPLICATE_LIB_OK is unset before the test runs."""
    monkeypatch.delenv("KMP_DUPLICATE_LIB_OK", raising=False)


def test_shim_sets_env_var(clean_omp_env):
    """The shim sets KMP_DUPLICATE_LIB_OK=TRUE on import."""
    assert "KMP_DUPLICATE_LIB_OK" not in os.environ

    _load_shim_fresh()

    assert os.environ.get("KMP_DUPLICATE_LIB_OK") == "TRUE"


def test_shim_is_idempotent(clean_omp_env):
    """Re-importing the shim must not clobber an externally-set value."""
    os.environ["KMP_DUPLICATE_LIB_OK"] = "CUSTOM_VALUE"

    _load_shim_fresh()

    # setdefault semantics: existing value wins.
    assert os.environ["KMP_DUPLICATE_LIB_OK"] == "CUSTOM_VALUE"


def test_shim_runs_without_side_effects(clean_omp_env):
    """Importing the shim only sets one env var; nothing else."""
    before = set(os.environ.keys())
    _load_shim_fresh()
    after = set(os.environ.keys())
    new_keys = after - before
    assert new_keys == {"KMP_DUPLICATE_LIB_OK"}, f"shim added unexpected env keys: {new_keys}"


def test_demos_import_shim_first():
    """Every demo must import _omp_compat before any other module.

    If a demo imports mujoco/torch/numpy before the shim, the
    ``KMP_DUPLICATE_LIB_OK`` workaround won't take effect and the
    crash on macOS will recur.
    """
    demos_dir = Path(__file__).parent.parent / "demos"
    expected = {"demo.py", "train_demo.py", "eval_demo.py", "benchmark.py"}
    for name in expected:
        text = (demos_dir / name).read_text()
        # The shim import must appear before any import of surg_rl,
        # mujoco, torch, or numpy.
        shim_idx = text.find("import _omp_compat")
        first_thirdparty_idx = max(
            text.find("from surg_rl", 0 if shim_idx < 0 else shim_idx),
            text.find("import mujoco", 0 if shim_idx < 0 else shim_idx),
            text.find("import torch", 0 if shim_idx < 0 else shim_idx),
            text.find("import numpy", 0 if shim_idx < 0 else shim_idx),
        )
        assert shim_idx != -1, f"{name} is missing the _omp_compat import"
        assert first_thirdparty_idx == -1 or shim_idx < first_thirdparty_idx, (
            f"{name} imports a third-party OMP-linked module "
            f"before _omp_compat; the shim must be first"
        )


def test_render_demos_import_platform_guard():
    """Demos with --render must also import _platform_guard before parsing args.

    The platform guard detects the known-unstable mjpython+AppleSilicon+MPS
    combination and exits with a clear error before trying to start
    the viewer (which would segfault). Without the guard, the user sees a
    cryptic 'zsh: segmentation fault' with no actionable message.
    """
    demos_dir = Path(__file__).parent.parent / "demos"
    render_demos = {"demo.py", "train_demo.py", "eval_demo.py"}
    for name in render_demos:
        text = (demos_dir / name).read_text()
        assert "_platform_guard" in text, (
            f"{name} accepts --render but doesn't import _platform_guard"
        )
        # The check must be after argparse parses args, but before the
        # env is constructed.
        guard_check_idx = text.find("is_risky_render_combination")
        assert guard_check_idx != -1, (
            f"{name} imports _platform_guard but never calls "
            "is_risky_render_combination()"
        )
        assert "sys.exit(2)" in text, (
            f"{name} has the platform guard check but doesn't exit 2 on it"
        )


def test_training_demos_forward_device_to_guard():
    """Demos with --device must forward it to the guard.

    The guard short-circuits when device='cpu' or device='cuda' (MPS
    is bypassed, so no segfault risk). For this to work, the demo
    must pass args.device to is_risky_render_combination().
    """
    demos_dir = Path(__file__).parent.parent / "demos"
    for name in ("demo.py", "train_demo.py"):
        text = (demos_dir / name).read_text()
        assert "is_risky_render_combination(device=" in text, (
            f"{name} has --device but doesn't forward it to the guard. "
            "Users passing --device cpu will get a false-positive refusal."
        )

    # eval_demo.py has no --device flag (the device comes from the
    # saved model). It should call the guard without a device argument
    # (auto-detect), which is fine — the comment in the demo explains
    # the trade-off.
    text = (demos_dir / "eval_demo.py").read_text()
    assert "is_risky_render_combination()" in text, (
        "eval_demo.py must call the guard (without a device arg)"
    )

"""Tests for the OpenMP-compatibility shim used by the demo scripts.

The shim sets two families of env vars before any library that links
to OpenMP is imported:

1. ``KMP_DUPLICATE_LIB_OK=TRUE`` — addresses the
   ``OMP: Error #15: Initializing libomp.dylib, but found libomp.dylib
   already initialized`` crash that hits ``mjpython`` on macOS when two
   OpenMP runtimes end up linked into the process.

2. ``OMP_NUM_THREADS=1``, ``MKL_NUM_THREADS=1``, ``OPENBLAS_NUM_THREADS=1`` —
   addresses the deeper ``OMP: Error #179: Function pthread_mutex_init
   failed / System error #22: Invalid argument`` crash that mjpython
   triggers by running the Python interpreter on a non-main Cocoa
   thread. Setting the thread count to 1 keeps libomp off the
   problematic pthread_mutex_init path.
"""

import importlib
import importlib.util
import os
import sys
from pathlib import Path

import pytest

SHIM_PATH = Path(__file__).parent.parent / "demos" / "_omp_compat.py"

# Env vars the shim is expected to set. Keep in sync with the shim source.
SHIM_VARS = (
    "KMP_DUPLICATE_LIB_OK",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
)
SHIM_DEFAULT_VALUES = {
    "KMP_DUPLICATE_LIB_OK": "TRUE",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
}


def _load_shim_fresh():
    """Load _omp_compat in an isolated module-cache slot.

    Drops any cached import, then re-imports. This lets us assert the
    shim's *idempotent* behavior across multiple invocations.
    """
    sys.modules.pop("_omp_compat", None)
    spec = importlib.util.spec_from_file_location("_omp_compat", SHIM_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def clean_omp_env(monkeypatch):
    """Ensure the shim's env vars are unset before the test runs."""
    for var in SHIM_VARS:
        monkeypatch.delenv(var, raising=False)


def test_shim_sets_kmp_duplicate(clean_omp_env):
    """The shim sets KMP_DUPLICATE_LIB_OK=TRUE on import (Error #15)."""
    assert "KMP_DUPLICATE_LIB_OK" not in os.environ

    _load_shim_fresh()

    assert os.environ.get("KMP_DUPLICATE_LIB_OK") == "TRUE"


def test_shim_sets_thread_singletons(clean_omp_env):
    """The shim sets OMP/MKL/OPENBLAS NUM_THREADS=1 on import
    (Error #179 pthread_mutex_init workaround).
    """
    _load_shim_fresh()

    assert os.environ.get("OMP_NUM_THREADS") == "1"
    assert os.environ.get("MKL_NUM_THREADS") == "1"
    assert os.environ.get("OPENBLAS_NUM_THREADS") == "1"


def test_shim_is_idempotent_kmp(clean_omp_env):
    """Re-importing the shim must not clobber an externally-set
    KMP_DUPLICATE_LIB_OK value.
    """
    os.environ["KMP_DUPLICATE_LIB_OK"] = "CUSTOM_VALUE"

    _load_shim_fresh()

    # setdefault semantics: existing value wins.
    assert os.environ["KMP_DUPLICATE_LIB_OK"] == "CUSTOM_VALUE"


def test_shim_is_idempotent_omp_threads(clean_omp_env):
    """Re-importing the shim must not clobber an externally-set
    OMP_NUM_THREADS value (e.g. CI sets it to 4 for performance).
    """
    os.environ["OMP_NUM_THREADS"] = "8"

    _load_shim_fresh()

    # setdefault semantics: existing value wins.
    assert os.environ["OMP_NUM_THREADS"] == "8"


def test_shim_runs_without_unexpected_side_effects(clean_omp_env):
    """Importing the shim only sets the documented env vars; nothing else."""
    before = set(os.environ.keys())
    _load_shim_fresh()
    after = set(os.environ.keys())
    new_keys = after - before
    assert new_keys == set(SHIM_VARS), f"shim added unexpected env keys: {new_keys}"


def test_demos_import_shim_first():
    """Every demo must import _omp_compat before any other module.

    If a demo imports mujoco/torch/numpy before the shim, the
    ``KMP_DUPLICATE_LIB_OK`` workaround won't take effect and the
    crash on macOS will recur.
    """
    demos_dir = Path(__file__).parent.parent / "demos"
    # Phase 32: demo.py was renamed to suturing_demo.py; the regression
    # contract still requires every demo to import _omp_compat first, but
    # the file name changed.
    expected = {"suturing_demo.py", "train_demo.py", "eval_demo.py", "benchmark.py"}
    for name in expected:
        text = (demos_dir / name).read_text()
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
    """Demos with --render must also import _platform_guard.

    The platform guard detects when the OMP shim's env vars are NOT
    in effect under mjpython+AppleSilicon and exits with a clear error
    before trying to start the viewer (which would segfault). Without
    the guard, the user sees a cryptic 'zsh: segmentation fault' with
    no actionable message.
    """
    demos_dir = Path(__file__).parent.parent / "demos"
    render_demos = {"suturing_demo.py", "train_demo.py", "eval_demo.py"}
    for name in render_demos:
        text = (demos_dir / name).read_text()
        assert "_platform_guard" in text, (
            f"{name} accepts --render but doesn't import _platform_guard"
        )
        guard_check_idx = text.find("is_risky_render_combination")
        assert guard_check_idx != -1, (
            f"{name} imports _platform_guard but never calls "
            "is_risky_render_combination()"
        )
        assert "sys.exit(2)" in text, (
            f"{name} has the platform guard check but doesn't exit 2 on it"
        )

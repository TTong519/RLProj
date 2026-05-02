"""Integration tests for GPU detection and backend selection.

These tests check real hardware when available, otherwise skip gracefully.
Safe for CI (CPU-only runners) — uses @skipif or mocking.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

import pytest

from surg_rl.scene_definition.schema import HardwareBackend
from surg_rl.utils.gpu import detect_backends, get_cuda_version, get_rocm_version, select_backend


# ---------------------------------------------------------------------------
# Detection on real hardware (must not crash)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_detect_backends_runs_without_crash():
    """detect_backends() must run on any machine without crashing."""
    backends = detect_backends()
    assert len(backends) >= 1
    assert HardwareBackend.cpu in backends


@pytest.mark.integration
def test_select_backend_auto_returns_something():
    """auto selection must always return a valid backend."""
    chosen = select_backend(HardwareBackend.auto)
    assert chosen in list(HardwareBackend)


# ---------------------------------------------------------------------------
# Physical GPU tests (skip when not present)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.skipif(sys.platform != "darwin", reason="Metal only on macOS")
def test_metal_detected_on_macos():
    """On macOS, Metal should be detected."""
    backends = detect_backends()
    assert HardwareBackend.metal in backends


@pytest.mark.integration
@pytest.mark.skipif(
    shutil.which("nvidia-smi") is None,
    reason="No NVIDIA GPU / nvidia-smi not found",
)
def test_cuda_version_when_gpu_present():
    """If nvidia-smi exists, get_cuda_version returns a non-empty string."""
    version = get_cuda_version()
    assert version is not None
    assert len(version) > 0


@pytest.mark.integration
@pytest.mark.skipif(
    shutil.which("rocminfo") is None,
    reason="No AMD GPU / rocminfo not found",
)
def test_rocm_version_when_gpu_present():
    """If rocminfo exists, get_rocm_version returns a non-empty string."""
    version = get_rocm_version()
    # rocminfo may exist but GPU not present; accept None or non-empty
    if version is not None:
        assert len(version) > 0


# ---------------------------------------------------------------------------
# Simulator integration
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_simulator_constructors_accept_backend():
    """Both simulators accept backend kwarg and resolve it."""
    from surg_rl.simulators.pybullet_simulator import PyBulletSimulator

    # PyBullet (always available, no heavy deps)
    p = PyBulletSimulator(render_mode="DIRECT", backend=HardwareBackend.auto)
    assert p._active_backend is not None
    assert p._active_backend in list(HardwareBackend)


@pytest.mark.integration
def test_cli_version_verbose_runs():
    """surg-rl version --verbose exits 0 on any machine."""
    result = subprocess.run(
        [sys.executable, "-m", "surg_rl.cli", "version", "--verbose"],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "src"},
    )
    assert result.returncode == 0
    assert "GPU Availability" in result.stdout or "Backend" in result.stdout

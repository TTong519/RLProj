"""Unit tests for GPU detection and backend selection.

These tests use mocking to cover all backend paths without requiring
physical GPUs. Safe for CI (CPU-only runners).
"""
from __future__ import annotations

import subprocess
import sys
import unittest.mock as mock

import pytest

from surg_rl.scene_definition.schema import HardwareBackend
from surg_rl.utils.gpu import (
    _has_cuda,
    _has_intel,
    _has_metal,
    _has_rocm,
    detect_backends,
    get_cuda_version,
    select_backend,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear LRU cache so each test sees fresh _has_* results."""
    detect_backends.cache_clear()
    yield


# ---------------------------------------------------------------------------
# CUDA
# ---------------------------------------------------------------------------

def test_has_cuda_true():
    with mock.patch("surg_rl.utils.gpu._find_binary", return_value="/usr/bin/nvidia-smi"):
        proc = mock.Mock(returncode=0, stdout="535.104.05\n", stderr="")
        with mock.patch("subprocess.run", return_value=proc):
            assert _has_cuda() is True


def test_has_cuda_false_no_binary():
    with mock.patch("surg_rl.utils.gpu._find_binary", return_value=None):
        assert _has_cuda() is False


def test_has_cuda_false_subprocess_fails():
    with mock.patch("surg_rl.utils.gpu._find_binary", return_value="/usr/bin/nvidia-smi"):
        with mock.patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "nvidia-smi")):
            assert _has_cuda() is False


# ---------------------------------------------------------------------------
# ROCm
# ---------------------------------------------------------------------------

def test_has_rocm_true():
    with mock.patch("surg_rl.utils.gpu._find_binary", return_value="/opt/rocm/bin/rocminfo"):
        proc = mock.Mock(returncode=0, stdout="Agent 1\n", stderr="")
        with mock.patch("subprocess.run", return_value=proc):
            assert _has_rocm() is True


def test_has_rocm_false_permission_error():
    with mock.patch("surg_rl.utils.gpu._find_binary", return_value="/opt/rocm/bin/rocminfo"):
        proc = mock.Mock(returncode=1, stdout="Unable to open /dev/kfd\n", stderr="")
        with mock.patch("subprocess.run", return_value=proc):
            assert _has_rocm() is False


# ---------------------------------------------------------------------------
# Intel
# ---------------------------------------------------------------------------

def test_has_intel_true():
    with mock.patch("surg_rl.utils.gpu._find_binary", return_value="/opt/intel/oneapi/compiler/latest/bin/sycl-ls"):
        proc = mock.Mock(returncode=0, stdout="Device 1\n", stderr="")
        with mock.patch("subprocess.run", return_value=proc):
            assert _has_intel() is True


# ---------------------------------------------------------------------------
# Metal
# ---------------------------------------------------------------------------

def test_has_metal_true_darwin():
    with mock.patch("surg_rl.utils.gpu._find_binary", return_value="/usr/bin/system_profiler"):
        proc = mock.Mock(returncode=0, stdout="Metal: Yes\n", stderr="")
        with mock.patch("subprocess.run", return_value=proc):
            with mock.patch.object(sys, "platform", "darwin"):
                assert _has_metal() is True


def test_has_metal_false_linux():
    with mock.patch.object(sys, "platform", "linux"):
        assert _has_metal() is False


# ---------------------------------------------------------------------------
# detect_backends
# ---------------------------------------------------------------------------

def test_detect_backends_empty_returns_cpu():
    with mock.patch("surg_rl.utils.gpu._has_cuda", return_value=False), \
         mock.patch("surg_rl.utils.gpu._has_rocm", return_value=False), \
         mock.patch("surg_rl.utils.gpu._has_metal", return_value=False), \
         mock.patch("surg_rl.utils.gpu._has_intel", return_value=False):
        result = detect_backends()
        assert result == (HardwareBackend.cpu,)


def test_detect_backends_cuda_first():
    with mock.patch("surg_rl.utils.gpu._has_cuda", return_value=True), \
         mock.patch("surg_rl.utils.gpu._has_rocm", return_value=False), \
         mock.patch("surg_rl.utils.gpu._has_metal", return_value=False), \
         mock.patch("surg_rl.utils.gpu._has_intel", return_value=False):
        result = detect_backends()
        assert result[0] == HardwareBackend.cuda
        assert HardwareBackend.cpu in result


# ---------------------------------------------------------------------------
# select_backend
# ---------------------------------------------------------------------------

def test_select_backend_auto():
    with mock.patch("surg_rl.utils.gpu._has_cuda", return_value=True), \
         mock.patch("surg_rl.utils.gpu._has_rocm", return_value=False), \
         mock.patch("surg_rl.utils.gpu._has_metal", return_value=False), \
         mock.patch("surg_rl.utils.gpu._has_intel", return_value=False):
        assert select_backend(HardwareBackend.auto) == HardwareBackend.cuda


def test_select_backend_explicit_available():
    with mock.patch("surg_rl.utils.gpu._has_cuda", return_value=True), \
         mock.patch("surg_rl.utils.gpu._has_rocm", return_value=False), \
         mock.patch("surg_rl.utils.gpu._has_metal", return_value=False), \
         mock.patch("surg_rl.utils.gpu._has_intel", return_value=False):
        assert select_backend(HardwareBackend.cuda) == HardwareBackend.cuda


def test_select_backend_explicit_unavailable_raises():
    with mock.patch("surg_rl.utils.gpu._has_cuda", return_value=False), \
         mock.patch("surg_rl.utils.gpu._has_rocm", return_value=False), \
         mock.patch("surg_rl.utils.gpu._has_metal", return_value=False), \
         mock.patch("surg_rl.utils.gpu._has_intel", return_value=False):
        with pytest.raises(RuntimeError, match="not available"):
            select_backend(HardwareBackend.cuda)


def test_select_backend_cpu_always_works():
    with mock.patch("surg_rl.utils.gpu._has_cuda", return_value=False), \
         mock.patch("surg_rl.utils.gpu._has_rocm", return_value=False), \
         mock.patch("surg_rl.utils.gpu._has_metal", return_value=False), \
         mock.patch("surg_rl.utils.gpu._has_intel", return_value=False):
        assert select_backend(HardwareBackend.cpu) == HardwareBackend.cpu


def test_select_backend_intel_fallback_to_cpu(caplog: pytest.LogCaptureFixture):
    """GPU-08: Intel gracefully falls back to CPU when unavailable."""
    with mock.patch("surg_rl.utils.gpu._has_cuda", return_value=False), \
         mock.patch("surg_rl.utils.gpu._has_rocm", return_value=False), \
         mock.patch("surg_rl.utils.gpu._has_metal", return_value=False), \
         mock.patch("surg_rl.utils.gpu._has_intel", return_value=False):
        with caplog.at_level("INFO", logger="surg_rl.utils.gpu"):
            result = select_backend(HardwareBackend.intel)
        assert result == HardwareBackend.cpu
        assert "falling back to CPU" in caplog.text


# ---------------------------------------------------------------------------
# get_cuda_version
# ---------------------------------------------------------------------------

def test_get_cuda_version():
    with mock.patch("surg_rl.utils.gpu._find_binary", return_value="/usr/bin/nvidia-smi"):
        proc = mock.Mock(returncode=0, stdout="535.104.05\n", stderr="")
        with mock.patch("subprocess.run", return_value=proc):
            assert get_cuda_version() == "535.104.05"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def test_logs_selected_backend(caplog: pytest.LogCaptureFixture):
    with mock.patch("surg_rl.utils.gpu._has_cuda", return_value=True), \
         mock.patch("surg_rl.utils.gpu._has_rocm", return_value=False), \
         mock.patch("surg_rl.utils.gpu._has_metal", return_value=False), \
         mock.patch("surg_rl.utils.gpu._has_intel", return_value=False):
        with caplog.at_level("INFO", logger="surg_rl.utils.gpu"):
            select_backend(HardwareBackend.auto)
        assert "Selected backend: cuda" in caplog.text


# ---------------------------------------------------------------------------
# GAP-05: MPS detection delegation
# ---------------------------------------------------------------------------


def test_mps_available_delegates_to_has_metal():
    """Verify _mps_available() imports from gpu._has_metal, not duplicating torch logic."""
    from surg_rl.rl.rllib.config import _mps_available

    with mock.patch("surg_rl.utils.gpu._has_metal", return_value=True):
        assert _mps_available() is True
    with mock.patch("surg_rl.utils.gpu._has_metal", return_value=False):
        assert _mps_available() is False

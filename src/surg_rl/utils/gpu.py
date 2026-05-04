"""GPU and hardware backend detection."""

from __future__ import annotations

import functools
import os
import shutil
import subprocess
import sys

from surg_rl.scene_definition.schema import HardwareBackend
from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)


# Known non-standard paths for vendor tools
_INTEL_PATHS = ["/opt/intel/oneapi/compiler/latest/bin", "/usr/local/bin"]


def _find_binary(name: str) -> str | None:
    """Find a binary in PATH or known vendor locations."""
    path = shutil.which(name)
    if path:
        return path
    # Search known vendor locations
    for directory in _INTEL_PATHS:
        candidate = os.path.join(directory, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _run_binary(args: list[str], timeout: int = 5) -> str | None:
    """Run a binary and return stdout on success, None on any failure."""
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError, FileNotFoundError):
        return None


def _has_cuda() -> bool:
    """Detect NVIDIA CUDA via nvidia-smi."""
    binary = _find_binary("nvidia-smi")
    if not binary:
        return False
    output = _run_binary([binary, "--query-gpu=driver_version", "--format=csv,noheader"])
    return output is not None and len(output) > 0


def _has_rocm() -> bool:
    """Detect AMD ROCm via rocminfo."""
    binary = _find_binary("rocminfo")
    if not binary:
        return False
    output = _run_binary([binary])
    if output is None:
        return False
    if "Unable to open /dev/kfd" in output:
        logger.info(
            "ROCm GPU detected but user lacks /dev/kfd permissions. "
            "Add user to 'video' or 'render' group."
        )
        return False
    return len(output) > 0


def _has_intel() -> bool:
    """Detect Intel oneAPI / XPU via sycl-ls or dpctl."""
    for binary_name in ("sycl-ls", "dpctl"):
        binary = _find_binary(binary_name)
        if binary:
            output = _run_binary([binary])
            if output:
                return True
    return False


def _has_metal() -> bool:
    """Detect Apple Metal (macOS only)."""
    if sys.platform != "darwin":
        return False
    # Prefer system_profiler for broad compatibility (no torch dependency)
    binary = _find_binary("system_profiler")
    if binary:
        output = _run_binary([binary, "SPDisplaysDataType"])
        if output and "Metal" in output:
            return True
    # Fallback: try torch if installed
    try:
        import torch
        return torch.backends.mps.is_available()  # type: ignore[no-any-return]
    except ImportError:
        pass
    return False


@functools.lru_cache(maxsize=1)
def detect_backends() -> tuple[HardwareBackend, ...]:
    """Detect available hardware backends.

    Returns:
        Tuple of available backends in priority order (CUDA > ROCm > Metal > Intel > CPU).
        CPU is always included as the final fallback.
    """
    available: list[HardwareBackend] = []
    if _has_cuda():
        available.append(HardwareBackend.cuda)
    if _has_rocm():
        available.append(HardwareBackend.rocm)
    if _has_metal():
        available.append(HardwareBackend.metal)
    if _has_intel():
        available.append(HardwareBackend.intel)
    # CPU is always available
    available.append(HardwareBackend.cpu)
    return tuple(available)


def select_backend(requested: HardwareBackend) -> HardwareBackend:
    """Select the actual backend to use.

    Args:
        requested: User-requested backend (e.g. auto, cuda, cpu).

    Returns:
        The selected backend.

    Raises:
        RuntimeError: If an explicit non-CPU backend is requested but unavailable.
    """
    available = detect_backends()

    if requested == HardwareBackend.auto:
        chosen = available[0]
        logger.info("Selected backend: %s", chosen.value)
        return chosen

    if requested == HardwareBackend.cpu:
        logger.info("Selected backend: cpu")
        return HardwareBackend.cpu

    if requested in available:
        logger.info("Selected backend: %s", requested.value)
        return requested

    # Intel gracefully falls back to CPU per GPU-08
    available_names = ", ".join(b.value for b in available)
    if requested == HardwareBackend.intel:
        logger.info(
            "Intel oneAPI not available — falling back to CPU. Available: %s.",
            available_names,
        )
        return HardwareBackend.cpu

    raise RuntimeError(
        f"Requested backend '{requested.value}' is not available. "
        f"Available backends: {available_names}"
    )


def get_cuda_version() -> str | None:
    """Get NVIDIA driver version string."""
    binary = _find_binary("nvidia-smi")
    if not binary:
        return None
    output = _run_binary([binary, "--query-gpu=driver_version", "--format=csv,noheader"])
    if output:
        # Take first line (first GPU)
        return output.splitlines()[0].strip() or None
    return None


def get_rocm_version() -> str | None:
    """Get ROCm version string."""
    binary = _find_binary("rocminfo")
    if not binary:
        return None
    output = _run_binary([binary])
    if output:
        for line in output.splitlines():
            if "ROCm version" in line:
                # Extract version after colon
                parts = line.split(":", 1)
                if len(parts) > 1:
                    return parts[1].strip() or None
    return None

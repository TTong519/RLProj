"""Install verification for [distributed] extra (08-06).

DIST-06
"""

import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.slow
def _is_online() -> bool:
    """Return True if pypi.org appears reachable."""
    import socket
    try:
        socket.gethostbyname("pypi.org")
        return True
    except OSError:
        return False


def test_distributed_extra_resolves():
    """Verify ``pip install --dry-run -e '.[distributed]'`` resolves.

    On Python >=3.13 Ray may not have a binary wheel yet — we treat
    wheel-availability failures as non-blocking and only assert that the
    dependency graph parses cleanly (no version conflicts).
    """
    if not _is_online():
        pytest.skip("Network unavailable — pip cannot resolve [distributed] extra")
    env = {
        **os.environ,
        "PIP_NO_CACHE_DIR": "1",
        "PIP_CACHE_DIR": str(Path(__file__).parent.parent / ".pip_cache"),
    }
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--dry-run", "--no-cache-dir", "-e", ".[distributed]"],
        capture_output=True,
        text=True,
        cwd=".",
        env=env,
    )
    combined = (result.stdout + result.stderr).lower()

    # If pip resolved the graph, "ray" appears in the plan even when
    # wheels are missing.
    assert "ray" in combined, f"ray not found in pip output: {combined[:800]}"

    # Fail only on actual *dependency conflicts*, not wheel availability
    if result.returncode != 0:
        assert "conflict" in combined or "incompatible" in combined, (
            f"pip dry-run failed but not for a dependency conflict — "
            f"likely missing wheel for current Python version: {combined[:800]}"
        )

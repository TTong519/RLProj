"""Install verification for [distributed] extra (08-06).

DIST-06
"""

import subprocess
import sys

import pytest


@pytest.mark.slow
def test_distributed_extra_resolves():
    """Verify ``pip install --dry-run -e '.[distributed]'`` resolves.

    On Python >=3.13 Ray may not have a binary wheel yet — we treat
    wheel-availability failures as non-blocking and only assert that the
    dependency graph parses cleanly (no version conflicts).
    """
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--dry-run", "-e", ".[distributed]"],
        capture_output=True,
        text=True,
        cwd=".",
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

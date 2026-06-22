"""K8s PVC end-to-end test stub (DEBT-06 / v0.4.2 deferred work).

A real PVC read/write/delete cycle requires a live Kubernetes cluster with a
persistent-volume provider (for example, `kind` with a local-path provisioner).
This file commits the test scaffolding and marker registry in v0.5.0; the
body is intentionally stubbed and deferred to v0.6.0.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest


def _kind_cluster_available() -> bool:
    """Return True if a local `kind` cluster is running."""
    if not shutil.which("kind"):
        return False
    result = subprocess.run(
        ["kind", "get", "clusters"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False
    return bool(result.stdout.strip())


@pytest.mark.k8s
@pytest.mark.integration
@pytest.mark.slow
def test_pvc_read_write_stub() -> None:
    """Stub for the K8s PVC read/write/delete e2e test.

    Skips unless a local `kind` cluster is available. When the cluster is
    present, the body is a documented TODO for the v0.6.0 implementation.
    """
    if not _kind_cluster_available():
        pytest.skip("No local kind cluster available (K8s PVC e2e deferred to v0.6.0)")

    # TODO(v0.6.0): implement PVC create/write/read/delete cycle.
    #   1. kubectl apply -f k8s/base/pvc.yaml (or an e2e overlay).
    #   2. Launch a Job that writes a checkpoint file to the PVC.
    #   3. Launch a second Job that reads the checkpoint back and verifies
    #      contents.
    #   4. Clean up PVC + Jobs.
    pass

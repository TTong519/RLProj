"""K8s PVC end-to-end checkpoint-persistence test (DEPLOY-01).

Asserts write -> pod restart -> read byte-equality on a bound PVC, via a
pytest-kind session-scoped kind cluster. Skips gracefully when a Docker
daemon is unavailable (e.g. macOS local runs without Docker Desktop), since
kind needs Docker to provision K8s nodes. pytest-kind auto-downloads the
`kind` + `kubectl` binaries to `./.pytest-kind/{cluster-name}/` on first run,
so the skip gate is Docker-daemon reachability, NOT a system-installed `kind`
binary.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest


def _k8s_e2e_available() -> bool:
    """True if a Docker daemon is reachable (kind needs Docker to run).

    Probes `docker info` (NOT a system-installed kind binary check) because
    pytest-kind downloads its own `kind` binary to `./.pytest-kind/` -- a
    system-installed `kind` is NOT required, but Docker is.
    """
    if not shutil.which("docker"):
        return False
    result = subprocess.run(["docker", "info"], capture_output=True, check=False)
    return result.returncode == 0


# Module-level skip gate: evaluated at setup time BEFORE the `kind_cluster`
# fixture is invoked. Without this, the pytest-kind `kind_cluster` fixture
# would call `kind get clusters` (-> `docker ps`) at setup and ERROR (not
# skip) when the Docker daemon is down -- the in-test `pytest.skip` below
# would never run because fixture setup fails first. Mirrors the
# `pytestmark = pytest.mark.skipif(...)` pattern in
# tests/dreamer/test_dreamerv3_subprocess_e2e.py. The @pytest.mark.k8s +
# @pytest.mark.integration + @pytest.mark.slow stack on the test function
# is preserved (this module-level mark is additive, not a replacement).
pytestmark = pytest.mark.skipif(
    not _k8s_e2e_available(),
    reason=(
        "Skipped: K8s PVC e2e requires a reachable Docker daemon (kind runs "
        "K8s nodes in Docker containers). Remediation: start Docker Desktop "
        "(macOS) or run on a Linux host with Docker preinstalled, then "
        '`pip install -e ".[dev,k8s-test]"` and '
        "`pytest tests/k8s/test_pvc_e2e.py -m k8s -v --cluster-name=surg-rl-e2e`."
    ),
)


@pytest.mark.k8s
@pytest.mark.integration
@pytest.mark.slow
def test_pvc_checkpoint_persistence(kind_cluster) -> None:
    """Write a checkpoint to a bound PVC, restart the pod, read it back.

    The cycle: apply the e2e overlay (PVC + write-Job together, so the PVC
    binds once the write-Job pod is scheduled -- kind uses
    WaitForFirstConsumer binding), wait on PVC Bound, wait on write-Job
    Complete, capture the written SHA from the write-Job logs, apply the
    read-Job standalone (a NEW pod mounting the SAME PVC -- the "restart"
    step), wait on read-Job Complete, capture the read SHA, and assert
    byte-equality across the pod restart.
    """
    # Redundant backup to the module-level `pytestmark` skipif -- in case the
    # module-level gate is ever removed, this keeps the skip-on-no-Docker
    # contract explicit at the call site.
    if not _k8s_e2e_available():
        pytest.skip("No Docker daemon available (K8s PVC e2e requires kind/Docker)")

    # 1. Apply the e2e overlay (PVC + CPU-only write Job together, so the PVC
    #    binds once the write-Job pod is scheduled -- kind uses
    #    WaitForFirstConsumer). read-job.yaml is NOT in the overlay.
    kind_cluster.kubectl("apply", "-k", "k8s/overlays/e2e")

    # 2. Wait for the PVC to bind (consumer pod scheduling triggers binding).
    # Keep single-line so the acceptance grep `kubectl("wait", "--for=condition=Bound"` matches; the full call is 102 chars (>100), so `# fmt: skip` prevents black from wrapping it and breaking the grep.
    kind_cluster.kubectl("wait", "--for=condition=Bound", "pvc/surg-rl-checkpoints", "--timeout=180s")  # fmt: skip

    # 3. Wait for the write Job to complete (writes 4096 random bytes to
    #    /checkpoints/ckpt.bin and prints the sha256 to stdout, captured in
    #    the Job logs).
    kind_cluster.kubectl("wait", "--for=condition=complete", "job/surg-rl-e2e-write", "--timeout=120s")  # fmt: skip
    write_sha = kind_cluster.kubectl("logs", "job/surg-rl-e2e-write").strip()

    # 4. Apply the read Job standalone (a NEW pod mounting the SAME PVC --
    #    the "restart" step). NOT `-k` -- this is a single-file apply of
    #    read-job.yaml only, creating the read-Job AFTER the write-Job has
    #    completed and the checkpoint exists on the PVC.
    kind_cluster.kubectl("apply", "-f", "k8s/overlays/e2e/read-job.yaml")
    kind_cluster.kubectl("wait", "--for=condition=complete", "job/surg-rl-e2e-read", "--timeout=120s")  # fmt: skip
    read_sha = kind_cluster.kubectl("logs", "job/surg-rl-e2e-read").strip()

    # 5. Byte-equality across pod restart = checkpoint persisted on the PVC.
    assert read_sha == write_sha, f"PVC persistence broken: wrote {write_sha}, read back {read_sha}"

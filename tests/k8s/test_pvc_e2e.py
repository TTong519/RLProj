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
import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    # Import only for type checkers -- the module-level skip gate
    # (`_k8s_e2e_available`) must run without importing pytest_kind (it's a
    # test-only dep; importing it at module top level would couple the skip
    # gate to that dep being installed). `from __future__ import annotations`
    # + the TYPE_CHECKING block lets the bare `KindCluster` annotations
    # below stay unevaluated at runtime.
    from pytest_kind.cluster import KindCluster


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


# Label selector identifying the e2e write-Job's pod (matches
# e2e-write-job.yaml `template.metadata.labels`). Used by the
# `_dump_pvc_diagnostics` timeout handler so we describe the RIGHT pod
# (the one whose scheduling triggers WaitForFirstConsumer binding) instead of
# every pod in the cluster.
_E2E_WRITE_JOB_POD_LABELS = "app=surg-rl,component=e2e"


def _dump_pvc_diagnostics(kind_cluster: KindCluster, *, label: str) -> None:
    """Print PVC + pod state to stderr for post-mortem root-cause analysis.

    Called when the PVC Bound wait times out. The timeout alone tells us the
    PVC stayed Pending for 180s but NOT WHY -- kind's default `standard`
    StorageClass uses `volumeBindingMode: WaitForFirstConsumer`, so a Pending
    PVC can mean:
      (a) the write-Job pod never scheduled (FailedScheduling /
          no-available-topology),
      (b) the write-Job pod is in ImagePullBackOff (busybox:1.36 rate-limit
          on Docker Hub), so the consumer never "arrives" to trigger binding,
      (c) the StorageClass provisioner failed (ProvisioningFailed), or
      (d) something else entirely.
    Capturing `kubectl describe pvc` + `kubectl describe pod -l <labels>` +
    `kubectl get pvc/pods -o wide` surfaces the Events section that
    distinguishes these. Pure observability -- no behavior change. All
    diagnostic commands are best-effort: a failure here MUST NOT mask the
    original timeout error.
    """
    print(
        "\n===== PVC/Pod diagnostics (post-timeout) =====",
        file=sys.stderr,
        flush=True,
    )
    for argv in (
        ("get", "pvc", "-o", "wide", "--show-kind"),
        ("get", "pods", "-l", label, "-o", "wide"),
        ("describe", "pvc", "surg-rl-checkpoints"),
        ("describe", "pod", "-l", label),
        ("get", "events", "--sort-by=.lastTimestamp"),
        ("get", "sc", "standard", "-o", "yaml"),
    ):
        print(f"\n--- kubectl {' '.join(argv)} ---", file=sys.stderr, flush=True)
        try:
            out = kind_cluster.kubectl(*argv)
        except subprocess.CalledProcessError as exc:
            # Don't let a failed diagnostic mask the original timeout.
            print(
                f"[diagnostic failed: rc={exc.returncode}]\n"
                f"stdout:\n{exc.stdout!s}\nstderr:\n{exc.stderr!s}",
                file=sys.stderr,
                flush=True,
            )
            continue
        print(out, file=sys.stderr, flush=True)
    print("\n===== end diagnostics =====\n", file=sys.stderr, flush=True)


def _kubectl_wait_bound(kind_cluster: KindCluster, *, timeout: str = "180s") -> None:
    """Wait for PVC Bound, dumping diagnostics on timeout before re-raising.

    Uses `kubectl wait --for=jsonpath={.status.phase}=Bound pvc/...` -- the
    CORRECT PVC-bound wait idiom. PVCs (v1 core API) do NOT populate
    `.status.conditions` at all; they expose bound state via `.status.phase`
    (Pending / Bound / Lost). The structurally-broken
    `--for=condition=Bound` form polls `.status.conditions[].type == "Bound"`,
    which can never exist on a PVC, so it ALWAYS times out at 180s regardless
    of actual binding state (root cause of run 28606248332 k8s-e2e failure:
    the PVC was Bound in ~14s but the wait timed out 180s later). NOTE: no
    single quotes around the jsonpath expression here -- kind_cluster.kubectl
    passes argv directly to subprocess (no shell), so `{}` is literal; adding
    shell-style quotes makes kubectl reject the path (run 28612169371
    regression: "error: unexpected path string").

    On a FUTURE timeout (for any NEW reason -- FailedScheduling /
    ImagePullBackOff / ProvisioningFailed / WaitForFirstConsumer timing), the
    wrapper prints `kubectl describe pvc` + `kubectl describe pod -l
    <e2e-labels>` + related state to stderr BEFORE re-raising the original
    CalledProcessError. This turns an opaque "timed out" into a
    root-cause-revealing Events section for the next CI run's log. The
    diagnostics are a regression tripwire: the wait idiom is now correct, so a
    timeout here means a NEW failure class worth surfacing.
    """
    try:
        # `--for=jsonpath={.status.phase}=Bound` polls the field PVCs actually
        # populate. NO single quotes here: kind_cluster.kubectl passes argv
        # directly to subprocess (no shell), so the `{}` in the jsonpath is
        # NOT subject to shell globbing. Adding single quotes (as required in
        # a real shell) makes kubectl receive the LITERAL `'{{.status.phase}}'`
        # (quotes included) and reject it with
        # "error: unexpected path string" (run 28612169371 regression). The
        # `# fmt: skip` keeps the call single-line so the regression guard in
        # tests/test_pvc_wait_idiom.py can match the exact substring
        # `--for=jsonpath={{.status.phase}}=Bound`.
        kind_cluster.kubectl("wait", "--for=jsonpath={.status.phase}=Bound", "pvc/surg-rl-checkpoints", f"--timeout={timeout}")  # fmt: skip
    except subprocess.CalledProcessError:
        # Surface the real Pending cause BEFORE re-raising. Diagnostics are
        # best-effort; a failure inside _dump_pvc_diagnostics is swallowed so
        # the original timeout error (not a diagnostic error) reaches pytest.
        try:
            _dump_pvc_diagnostics(kind_cluster, label=_E2E_WRITE_JOB_POD_LABELS)
        except Exception as exc_diag:  # noqa: BLE001 -- never mask the original
            print(
                f"[diagnostic capture failed: {exc_diag!r}]",
                file=sys.stderr,
                flush=True,
            )
        raise


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
    # The wait uses `--for=jsonpath={.status.phase}=Bound` -- the CORRECT
    # PVC-bound idiom (PVCs expose bound state via .status.phase, NOT
    # .status.conditions[]). No shell quotes around the jsonpath: kubectl is
    # invoked via subprocess (no shell), so `{}` is literal. The wrapper
    # dumps `kubectl describe pvc/pod` + Events to stderr on timeout as a
    # regression tripwire: the wait idiom is now correct, so a timeout here
    # means a NEW failure class worth surfacing (FailedScheduling /
    # ImagePullBackOff / ProvisioningFailed / WaitForFirstConsumer timing).
    _kubectl_wait_bound(kind_cluster, timeout="180s")

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

"""Guard: k8s/overlays/e2e must kustomize-build cleanly.

Regression guard for the CI k8s-e2e job failure (run 28492071094, job 84450697516):
`kubectl apply -k k8s/overlays/e2e` failed because kustomization.yaml referenced
`../../base/pvc.yaml` -- a single FILE outside the overlay directory, which
kubectl's embedded kustomize forbids under its default load_restrictor=security
(`file '...' is not in or below '...'`). The fix made the e2e overlay
self-contained (a local pvc.yaml copy). This test pins that invariant two ways:

1. STATIC (always runs, no deps): every `resources:` entry in the e2e
   kustomization.yaml must NOT reference a path outside the overlay dir (no
   `../` prefix) -- the exact regression class. Catches the bug without kubectl.
2. RUNTIME (when kubectl is available): `kubectl kustomize k8s/overlays/e2e`
   exits 0 and emits the expected Kinds (PVC + write-Job).

Not marked integration/slow/k8s so it runs in the regular matrix (the static
guard is the always-on regression net; the runtime guard is a bonus where
kubectl exists).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
E2E_OVERLAY = REPO_ROOT / "k8s" / "overlays" / "e2e"
E2E_KUSTOMIZATION = E2E_OVERLAY / "kustomization.yaml"


def _load_kustomization() -> dict:
    with open(E2E_KUSTOMIZATION) as f:
        return yaml.safe_load(f)


def test_e2e_overlay_resources_are_local() -> None:
    """No `resources:` entry may escape the overlay dir (`../...` triggers the
    kustomize load_restrictor=security failure)."""
    kust = _load_kustomization()
    resources = kust.get("resources", [])
    assert resources, f"No resources listed in {E2E_KUSTOMIZATION}"
    escaping = [r for r in resources if isinstance(r, str) and r.startswith("..")]
    assert not escaping, (
        f"{E2E_KUSTOMIZATION}: resources reference paths outside the overlay dir "
        f"({escaping}). kubectl's kustomize load_restrictor=security forbids this; "
        f"keep the e2e overlay self-contained (copy the manifest locally)."
    )


def test_e2e_overlay_has_pvc_and_write_job_resources() -> None:
    """The e2e overlay must list the PVC + write-Job (the test's design intent:
    ONLY those two -- not the full base stack)."""
    kust = _load_kustomization()
    resources = kust.get("resources", [])
    # The PVC may be a local pvc.yaml OR a directory; the write-Job is a local file.
    assert any(
        isinstance(r, str) and "pvc" in r.lower() for r in resources
    ), f"PVC resource missing from {E2E_KUSTOMIZATION}: {resources}"
    assert any(
        isinstance(r, str) and "write" in r.lower() for r in resources
    ), f"write-Job resource missing from {E2E_KUSTOMIZATION}: {resources}"


def test_e2e_overlay_read_job_not_in_resources() -> None:
    """read-job.yaml is deliberately applied standalone AFTER the write-Job
    completes (listed in resources it would race the write-Job). Guard the intent."""
    kust = _load_kustomization()
    resources = kust.get("resources", [])
    assert not any(
        isinstance(r, str) and "read" in r.lower() for r in resources
    ), f"read-job.yaml must NOT be in {E2E_KUSTOMIZATION} resources (race with write-Job)"


@pytest.mark.skipif(
    shutil.which("kubectl") is None,
    reason="kubectl not installed (static guards above cover the regression class)",
)
def test_e2e_overlay_kustomize_builds() -> None:
    """`kubectl kustomize k8s/overlays/e2e` exits 0 and emits PVC + write-Job."""
    result = subprocess.run(
        ["kubectl", "kustomize", str(E2E_OVERLAY)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert (
        result.returncode == 0
    ), f"kubectl kustomize failed (rc={result.returncode}):\n{result.stderr}"
    docs = list(yaml.safe_load_all(result.stdout))
    kinds = [d.get("kind") for d in docs if isinstance(d, dict)]
    assert "PersistentVolumeClaim" in kinds, f"PVC missing from build output: {kinds}"
    assert "Job" in kinds, f"write-Job missing from build output: {kinds}"

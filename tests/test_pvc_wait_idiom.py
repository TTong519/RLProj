"""Guard: the k8s PVC e2e test must use the correct Bound-wait idiom.

Regression guard for the CI k8s-e2e job failure (run 28606248332, job 84827124284):
`kubectl wait --for=condition=Bound pvc/surg-rl-checkpoints` timed out at 180s
even though the PVC was Bound in ~14s. Root cause: the `--for=condition=<type>`
flag polls `.status.conditions[].type == <type>` AND `.status.conditions[].status
== "True"`, but PVCs do NOT populate `.status.conditions` at all -- they expose
bound state via `.status.phase = "Bound"`. So `--for=condition=Bound` on a PVC
waits for a condition that structurally cannot exist and ALWAYS times out,
regardless of actual binding state. The fix uses the correct PVC-bound idiom:

    kubectl wait --for=jsonpath='{.status.phase}'=Bound pvc/<name> --timeout=180s

This test pins that invariant statically (no kubectl/kind/Docker needed): the
e2e test file must use the jsonpath wait on `.status.phase` for the PVC, and
must NOT use the structurally-broken `--for=condition=Bound` form on a PVC.
The diagnostics wrapper (`_dump_pvc_diagnostics` / `_kubectl_wait_bound`) must
also still be present as a regression tripwire so a FUTURE timeout (for any NEW
reason) surfaces `kubectl describe` output.

Runs in the regular matrix (no kubectl/kind/Docker needed).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
E2E_TEST = REPO_ROOT / "tests" / "k8s" / "test_pvc_e2e.py"


def _e2e_source() -> str:
    return E2E_TEST.read_text()


def test_pvc_wait_uses_jsonpath_on_status_phase() -> None:
    """The PVC Bound wait must poll `.status.phase` via jsonpath, not the
    structurally-nonexistent `.status.conditions[].type` (PVCs do not populate
    .status.conditions)."""
    src = _e2e_source()
    # The correct idiom: jsonpath on .status.phase = Bound. Allow either
    # single-quoted or shell-escaped forms; the key substring is the jsonpath
    # expression targeting .status.phase with value Bound.
    assert "jsonpath" in src, (
        f"{E2E_TEST}: PVC Bound wait must use --for=jsonpath, not --for=condition. "
        "PVCs expose bound state via .status.phase, not .status.conditions[]."
    )
    assert (
        re.search(
            r"jsonpath\s*=\s*['\"]?\\?\{\.status\.phase\}['\"]?\s*=\s*Bound",
            src,
        )
        or re.search(r"\.status\.phase['\"]?\s*,?\s*['\"]?=Bound", src)
        or re.search(
            r"jsonpath.*\.status\.phase.*=Bound",
            src,
        )
    ), (
        f"{E2E_TEST}: PVC Bound wait must target .status.phase = Bound via jsonpath. "
        "Found jsonpath token but not the .status.phase=Bound expression."
    )


def test_pvc_wait_does_not_use_condition_bound_on_pvc() -> None:
    """The structurally-broken `--for=condition=Bound` on a PVC MUST be gone
    from the actual kubectl wait call site. (`--for=condition=Bound` polls
    .status.conditions[].type, which PVCs never populate -> unconditional 180s
    timeout.) References in comments/docstrings explaining the OLD broken form
    are fine; the CALL must use jsonpath."""
    src = _e2e_source()
    # Find every kubectl wait call site (lines containing kubectl("wait" or
    # .kubectl("wait"). For each, if it references pvc/ it MUST use jsonpath,
    # not --for=condition=Bound.
    wait_lines = re.findall(r'.*kubectl\("wait".*', src)
    assert wait_lines, f"{E2E_TEST}: no kubectl wait calls found (guard stale?)"
    for line in wait_lines:
        if "pvc/" in line or "pvc" in line.replace(" ", ""):
            assert "condition=Bound" not in line.replace(" ", ""), (
                f"{E2E_TEST}: kubectl wait on a PVC must NOT use "
                "--for=condition=Bound (PVCs do not populate .status.conditions; "
                "use --for=jsonpath='{.status.phase}'=Bound). Offending line: {line}"
            )
            assert "jsonpath" in line, (
                f"{E2E_TEST}: kubectl wait on a PVC must use jsonpath on .status.phase. "
                f"Offending line: {line}"
            )


def test_pvc_diagnostics_wrapper_still_present() -> None:
    """The `_dump_pvc_diagnostics` + `_kubectl_wait_bound` wrapper must remain
    as a regression tripwire: on a FUTURE PVC-bound timeout (for any NEW reason)
    the test must still print `kubectl describe pvc/pod` + Events before
    re-raising. Removing the wrapper would silently hide the next failure class."""
    src = _e2e_source()
    assert "_dump_pvc_diagnostics" in src, (
        f"{E2E_TEST}: _dump_pvc_diagnostics regression-tripwire removed. "
        "Keep it so a future PVC-bound timeout surfaces describe output."
    )
    assert "_kubectl_wait_bound" in src, (
        f"{E2E_TEST}: _kubectl_wait_bound wrapper removed. "
        "Keep it so diagnostics fire on timeout before re-raising."
    )
    # The diagnostics must still capture describe pvc + describe pod (the
    # Events section that distinguishes FailedScheduling / ImagePullBackOff /
    # ProvisioningFailed / WaitForFirstConsumer timing).
    assert (
        "describe" in src and "pvc" in src
    ), f"{E2E_TEST}: diagnostics must still `kubectl describe pvc` on timeout."

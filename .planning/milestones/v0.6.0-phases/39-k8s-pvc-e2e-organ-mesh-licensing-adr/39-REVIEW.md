---
phase: 39-k8s-pvc-e2e-organ-mesh-licensing-adr
reviewed: 2026-06-27T00:00:00Z
depth: deep
files_reviewed: 9
files_reviewed_list:
  - .github/workflows/ci.yml
  - .gitignore
  - pyproject.toml
  - tests/k8s/test_pvc_e2e.py
  - k8s/overlays/e2e/kustomization.yaml
  - k8s/overlays/e2e/e2e-write-job.yaml
  - k8s/overlays/e2e/read-job.yaml
  - docs/adr/0001-organ-mesh-licensing.md
  - docs/adr/README.md
findings:
  critical: 0
  blocker: 0
  warning: 1
  info: 6
  total: 7
status: issues_found
---

# Phase 39: Code Review Report

**Reviewed:** 2026-06-27
**Depth:** deep
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 39 closes DEPLOY-01 (K8s PVC checkpoint-persistence e2e) and ASET-06
(first MADR ADR recording the organ-mesh licensing decision). Deep review
covered the K8s overlay + test + CI job, the pyproject `k8s-test` extra,
.gitignore pytest-kind entry, and both ADR docs.

All explicit phase constraints hold: the e2e overlay lists exactly
`../../base/pvc.yaml` + `e2e-write-job.yaml` (no `- ../../base`, no
`secret.yaml`, no `serviceAccountName`, no `spec.nodeName`); Jobs use
`busybox:1.36`; the read-Job is applied standalone in the test body after
the write-Job completes; the module-level `pytestmark = skipif(...)`
correctly converts a Docker-daemon-down setup into a SKIP (not an ERROR)
before the session-scoped `kind_cluster` fixture runs; the CI `k8s-e2e`
job is CPU-only, ubuntu-latest, installs `.[dev,k8s-test]`, and is
independent of the main matrix; the ADR quotes only the PUBLIC
challenge-guidelines page (not the gated EULA), links no downloadable
samples, and explicitly states SurgToolLoc contains NO organ meshes. Both
public URLs are present; the verbatim non-commercial clause is corroborated
by `39-RESEARCH.md` (verified against the live page on 2026-06-27).

No BLOCKERs found. One WARNING on test-failure diagnostics, plus six INFO
items (robustness/footguns/doc-verification notes).

## Structural Findings (fallow)

No structural pre-pass was provided for this phase; the review was performed
directly against the nine listed files.

## Warnings

### WR-01: `kubectl wait --for=condition=complete` cannot distinguish Complete from Failed — opaque 120s CI hang on Job failure

**File:** `tests/k8s/test_pvc_e2e.py:86` and `tests/k8s/test_pvc_e2e.py:94`
**Issue:**
`pytest-kind`'s `KindCluster.kubectl` (cluster.py:149) uses
`subprocess.check_output`, which raises `CalledProcessError` on non-zero
exit. `kubectl wait --for=condition=complete job/<name>` only matches the
`Complete` condition — a *Failed* Job (e.g. write-Job pod exits non-zero
because `/dev/urandom` is unavailable, or read-Job pod fails because
`ckpt.bin` is missing) never reaches `Complete`, so `kubectl wait` burns
the full `--timeout=120s` then raises an opaque `CalledProcessError` with
no indication of *which* Job failed or why. With `backoffLimit: 0` and
`restartPolicy: Never`, a single pod failure is permanent — the test will
always time out rather than surface the failing pod's logs. This turns a
simple write-Job failure into a 120s+ opaque CI hang, harming
debuggability of an already-slow e2e test.

**Fix:**
Wait on both conditions and capture pod logs on failure, e.g.:

```python
def _wait_job(cluster, job_name: str, timeout: str = "120s") -> None:
    # Race complete vs. failed; the first to succeed wins.
    cluster.kubectl(
        "wait", "--for=condition=complete", f"job/{job_name}",
        f"--timeout={timeout}",
    )
    # If the above raised, surface the pod failure reason + logs.
    import subprocess
    try:
        cluster.kubectl("wait", "--for=condition=failed", f"job/{job_name}", "--timeout=5s")
    except subprocess.CalledProcessError:
        pass  # not failed — good
    else:
        logs = cluster.kubectl("logs", f"job/{job_name}")
        raise AssertionError(f"Job {job_name} failed. Pod logs:\n{logs}")
```

At minimum, wrap each `kubectl wait --for=condition=complete` in a
try/except that, on `CalledProcessError`, captures
`kubectl logs job/<name>` and re-raises with the logs in the message.

## Info

### INF-01: Redundant in-test skip check duplicates the module-level `pytestmark`

**File:** `tests/k8s/test_pvc_e2e.py:71-72`
**Issue:** The `if not _k8s_e2e_available(): pytest.skip(...)` block is
dead in normal operation because the module-level
`pytestmark = pytest.mark.skipif(not _k8s_e2e_available(), ...)`
(lines 42-51) already skips before the test body runs. The block is
documented as an intentional "redundant backup," but it cannot actually
fire (the module-level gate is evaluated at collection time and short-
circuits the test). It is dead code that implies a runtime guarantee it
cannot provide.
**Fix:** Remove the in-test block, or convert the module-level gate to a
comment explaining that the in-test check is the real guard. Keeping both
with the current docstring misrepresents which gate is load-bearing.

### INF-02: `# fmt: skip` encodes a fragile contract with an external acceptance grep

**File:** `tests/k8s/test_pvc_e2e.py:81,86,94`
**Issue:** Three `kubectl wait` calls carry `# fmt: skip` to keep them
single-line so an acceptance grep
(`kubectl("wait", "--for=condition=Bound"`) matches. This couples the
test's formatting to an out-of-tree grep pattern; a future black upgrade
that changes `# fmt: skip` semantics, or a refactor that rewrites the
call, would silently break the acceptance check while the test still
passes. The contract is undocumented in the test file beyond the inline
comment.
**Fix:** Move the acceptance-critical substring into a constant or
assertion (e.g. `assert "--for=condition=Bound" in source_of(test_pvc_e2e)`)
rather than relying on a particular line shape, or document the grep
contract in `39-VALIDATION.md` next to the grep pattern.

### INF-03: `k8s-e2e` CI job lacks a pip-dependency cache step

**File:** `.github/workflows/ci.yml:136-154`
**Issue:** The main `test` job caches pip via
`actions/cache@v4` keyed on `pyproject.toml` (lines 35-41); the `k8s-e2e`
job does not, despite installing the heavier `.[dev,k8s-test]` extra
(pytest-kind pulls kind + kubectl binaries on first run). This makes the
already-slow kind e2e job slower and more network-dependent than
necessary.
**Fix:** Add the same `actions/cache@v4` step keyed on
`hashFiles('pyproject.toml')` before the Install step in the `k8s-e2e`
job.

### INF-04: ADR verbatim clause quotes are not independently re-verifiable from the ADR alone

**File:** `docs/adr/0001-organ-mesh-licensing.md:107,114`
**Issue:** The clause-2 and clause-13 quotes are presented as verbatim
from the public challenge-guidelines page. Their accuracy is corroborated
by `39-RESEARCH.md` (lines 13, 290-294, 590 — "verified 2026-06-27"), but
a future auditor reading only the ADR cannot re-verify the wording without
fetching the external URL. The research artifact is the audit trail; the
ADR does not cross-reference it.
**Fix:** Add a footnote or References line: "Verbatim clauses verified
against the live page on 2026-06-27; see
`.planning/phases/39-.../39-RESEARCH.md` §Pitfall 6 for the audit
trail." This is documentation completeness, not a correctness defect.

### INF-05: Running the full suite without `k8s-test` extra errors at `kind_cluster` fixture resolution rather than skipping

**File:** `tests/k8s/test_pvc_e2e.py:57` (in combination with
`pyproject.toml` `dev` extra which omits `pytest-kind`)
**Issue:** The module-level skip gate probes *Docker* availability, not
*pytest-kind* installation. If a developer runs `pytest tests/` (no
`-m "not integration"`) with only `.[dev]` installed on a host where
Docker IS available, the skipif evaluates False, the test is selected,
and pytest errors with `fixture 'kind_cluster' not found` because the
pytest-kind plugin is not registered. The CI paths are safe (main matrix
uses `-m "not integration"`; `k8s-e2e` installs `k8s-test`), but the
local-dev footgun is real.
**Fix:** Add a `pytest.importorskip("pytest_kind")` at module top, or
extend `_k8s_e2e_available()` to also check
`importlib.util.find_spec("pytest_kind") is not None` so the skip gate
covers both preconditions.

### INF-06: Test relies on cwd == repo root for relative `kubectl apply -k k8s/overlays/e2e`

**File:** `tests/k8s/test_pvc_e2e.py:77,93`
**Issue:** `kubectl("apply", "-k", "k8s/overlays/e2e")` and
`kubectl("apply", "-f", "k8s/overlays/e2e/read-job.yaml")` use
repo-root-relative paths. `pytest.ini` does not change cwd, so this works
under the CI invocation (`pytest tests/k8s/test_pvc_e2e.py ...` from repo
root) but breaks if the test is run from any other cwd (e.g. a developer
running `pytest` from inside `tests/`).
**Fix:** Resolve the overlay path from `__file__`:
`Path(__file__).resolve().parents[2] / "k8s" / "overlays" / "e2e"` and
pass the string form to `kubectl`. Decouples the test from the runner's
cwd.

---

_Reviewed: 2026-06-27_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
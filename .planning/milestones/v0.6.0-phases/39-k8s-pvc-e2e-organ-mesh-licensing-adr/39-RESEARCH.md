# Phase 39: K8s PVC e2e + Organ-Mesh Licensing ADR - Research

**Researched:** 2026-06-27
**Domain:** Kubernetes PVC persistence e2e testing (pytest-kind + kind) + architecture decision records (organ-mesh asset licensing)
**Confidence:** HIGH (workstream A: pytest-kind + kind storage verified against PyPI + kind source; workstream B: SurgToolLoc license clauses verified verbatim from challenge-guidelines page)

## Summary

Phase 39 has two independent, low-risk workstreams that close carried-forward tech debt from v0.5.0 Phase 35.

**Workstream A (DEPLOY-01, success criteria 1–3)** de-stubs `tests/k8s/test_pvc_e2e.py` using the `pytest-kind` plugin (v22.11.1, already noted as the locked version in STATE.md). The plugin's session-scoped `kind_cluster` fixture provisions a local Kubernetes-in-Docker cluster inside the pytest session, downloads the `kind` + `kubectl` binaries to `./.pytest-kind/{cluster-name}/`, and exposes a `kubectl(*args)` helper. The existing `k8s/base/pvc.yaml` already uses `storageClassName: standard`, which EXACTLY matches kind's default StorageClass (rancher.io/local-path provisioner) — no manifest fix needed. The one critical pitfall is that kind's default StorageClass uses `volumeBindingMode: WaitForFirstConsumer`, so a PVC will NOT bind until a consuming Pod is scheduled; the test must apply the PVC + a consuming Job together and then `kubectl wait --for=condition=Bound pvc/surg-rl-checkpoints` (not wait on the PVC alone before scheduling a pod). A new `k8s/overlays/e2e/` Kustomize overlay (modeled on `k8s/overlays/cpu/`) applies the PVC + a CPU-only, no-GPU checkpoint write/read Job. CI runs the marked test in a dedicated Ubuntu job (`pytest -m k8s tests/k8s/`); macOS local runs without Docker/kind skip gracefully.

**Workstream B (ASET-06, success criteria 4–5)** writes the repo's first ADR recording the organ-mesh licensing decision. The SurgToolLoc challenge guidelines (https://surgtoolloc23.grand-challenge.org/challenge-guidelines/) were verified to contain the verbatim non-commercial clause: *"Your team will use the provided data only in the scope of the challenge and neither pass it on to a third party nor use it for any publication or for commercial uses."* The dataset is confirmed to be 24,695 endoscopic video clips with tool-presence labels (https://surgtoolloc23.grand-challenge.org/data-description/) — NOT organ geometry — so the rejection rests on BOTH modality mismatch (primary) AND licensing incompatibility (secondary, but required by SC#5). Procedural generation is the default; the ADR is the cite-able closure artifact.

**Primary recommendation:** Land workstream B (ADR, pure documentation, zero execution risk) and workstream A (test + overlay + CI job) as two parallel plans; A's risk is confined to CI flakiness from kind cluster startup time, mitigated by a generous `kubectl wait --timeout=180s` and a dedicated `k8s-e2e` CI job isolated from the main test matrix.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEPLOY-01 | K8s PVC checkpoint-persistence e2e test asserts write → pod restart → read on a bound PVC (de-stubbed via `pytest-kind` `kind_cluster` fixture + `kubectl wait --for=condition=Bound`) | Workstream A: pytest-kind 22.11.1 fixture API, kind `standard` StorageClass + WaitForFirstConsumer binding behavior, e2e overlay structure, CI Ubuntu job pattern, macOS skip pattern |
| ASET-06 | Organ-mesh licensing decision is recorded as an ADR — procedural generation as the default, surgtoolloc rejected with cited rationale (continues ASET-01..05) | Workstream B: SurgToolLoc challenge-guidelines verbatim non-commercial clause, data-description page (video + tool-presence labels, no organ meshes), ADR format/location recommendation, ADR content structure |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| PVC provisioning + binding | K8s cluster (kind) | — | kind's local-path provisioner owns PV creation; test observes, does not provision |
| Checkpoint write/read cycle | K8s Job (batch/v1) | — | A Job runs to completion, writes a file to the mounted PVC, exits; a second Job reads it back — Jobs are the correct workload for one-shot e2e assertions (not Deployments) |
| Test orchestration / assertions | Test tier (pytest) | — | pytest session-scoped `kind_cluster` fixture brings up the cluster; the test function drives `kubectl apply/wait/logs` and asserts byte-equality |
| Kustomize overlay authoring | Repo config tier (`k8s/overlays/e2e/`) | — | Declarative manifest patching; no code tier involved |
| CI gating | CI tier (`.github/workflows/ci.yml`) | — | Dedicated Ubuntu `k8s-e2e` job; main matrix stays on `not integration` |
| Licensing decision (ADR) | Documentation tier (`docs/adr/`) | — | Pure documentation artifact; no runtime code tier |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest-kind | 22.11.1 | pytest plugin: session-scoped `kind_cluster` fixture provisions a kind K8s cluster for e2e tests | The de-facto Python K8s e2e testing plugin; maintained by Henning Jacobs (ex-Zalando); pinned in STATE.md v0.6.0 research as the locked choice `[VERIFIED: pypi.org/project/pytest-kind]` |
| kind (binary) | 0.17.0 (bundled by pytest-kind 22.11.1) | Kubernetes IN Docker — runs a K8s 1.25 cluster inside Docker containers | pytest-kind auto-downloads this to `./.pytest-kind/{cluster-name}/kind`; no manual install required in CI or locally `[VERIFIED: pypi.org/project/pytest-kind]` |
| kubectl (binary) | (downloaded by pytest-kind) | K8s API client for `kubectl apply/wait/logs` | pytest-kind downloads kubectl to `./.pytest-kind/{cluster-name}/kubectl`; the `KindCluster.kubectl(*args)` helper uses it `[VERIFIED: pypi.org/project/pytest-kind]` |
| pykube-ng | 23.6.0 (transitive) | Python K8s API client; exposed as `kind_cluster.api` | Optional Python-typed access to the cluster (the fixture's `.api` attribute); not required if the test uses `kubectl(*args)` exclusively `[VERIFIED: pypi.org/project/pykube-ng]` |
| Kustomize | v5.7.1 (built into kubectl) | Declarative overlay patching for `k8s/overlays/e2e/` | Already available via `kubectl apply -k` (kubectl 1.34.1 ships Kustomize v5.7.1); no separate install `[VERIFIED: local kubectl version --client]` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Docker | 29.6.1 (local) / preinstalled on GitHub Ubuntu runners | kind runs K8s nodes inside Docker containers | Required by kind to provision nodes; GitHub Actions Ubuntu runners have Docker preinstalled `[VERIFIED: local docker --version]` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest-kind | minikube + raw kubectl subprocess | minikube is heavier (full VM vs. containers), slower to start, and lacks the pytest fixture integration; pytest-kind is the locked decision (STATE.md) |
| pytest-kind | k3s + k3d | k3d is lighter but less commonly paired with pytest; pytest-kind's session-scoped fixture + auto binary download is the lowest-friction path |
| Kustomize overlay | Helm chart | Helm was explicitly deferred ("Helm chart / ROS2 DDS router — out of scope", REQUIREMENTS.md line 75); Kustomize overlays are the existing pattern (`k8s/overlays/cpu/`, `k8s/overlays/gpu/`) |

**Installation:**

```bash
# Add a [k8s-test] dev extra to pyproject.toml (already decided in STATE.md v0.6.0 research)
pip install -e ".[dev,k8s-test]"
# pytest-kind auto-downloads kind + kubectl binaries to ./.pytest-kind/{cluster-name}/ on first run
```

**Version verification:** (run this session)
```bash
$ pip index versions pytest-kind
pytest-kind (22.11.1)   # latest; locked version
$ pip index versions pykube-ng
pykube-ng (23.6.0)      # latest transitive
$ kubectl version --client
Client Version: v1.34.1, Kustomize Version: v5.7.1   # local (Darwin)
```

## Package Legitimacy Audit

> Package Legitimacy Gate run via `gsd-tools query package-legitimacy check --ecosystem pypi pytest-kind pykube-ng`.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| pytest-kind | PyPI | 3.6 yrs (pub 2022-11-30) | unknown (seam returned null) | https://codeberg.org/hjacobs/pytest-kind | SUS | Flagged — planner inserts checkpoint:human-verify before install |
| pykube-ng | PyPI | 2.9 yrs (pub 2023-06-16) | unknown (seam returned null) | https://codeberg.org/hjacobs/pykube-ng | SUS | Flagged — planner inserts checkpoint:human-verify before install |

**Packages removed due to [SLOP] verdict:** none

**Packages flagged as suspicious [SUS]:** `pytest-kind`, `pykube-ng`

**SUS-flag context (the planner should relay this to the human-verify checkpoint):** both packages are flagged SUS *solely* because the legitimacy seam could not retrieve a download count (`weeklyDownloads: null`), NOT because of any hostile signal. Both are well-established, maintained by a known author (Henning Jacobs, ex-Zalando, also author of `kube-web-view` / `kube-resource-report`), have public source repos on Codeberg, are non-deprecated, and have NO `postinstall`/setup-side-effect scripts (`postinstall: null` on PyPI). The SUS verdict here is a "low-traffic niche library" signal, not a "slopsquat" signal. The locked version `pytest-kind>=22.11.1` is already recorded in STATE.md v0.6.0 research as the intended dev-only `[k8s-test]` extra. Realistic risk: LOW. Recommendation: proceed with the install after the human-verify checkpoint confirms.

*Packages discovered via WebSearch (PyPI lookup) and verified against the PyPI registry + official Codeberg source repo. Tagged `[VERIFIED: pypi registry]` for existence + provenance; the SUS flag is a download-volume caveat, not a legitimacy rejection.*

## Architecture Patterns

### System Architecture Diagram — Workstream A (PVC e2e)

```
pytest session (CI Ubuntu runner, Docker available)
   │
   ▼
[session-scoped kind_cluster fixture]  (pytest-kind 22.11.1)
   │ - downloads kind 0.17.0 + kubectl to ./.pytest-kind/surg-rl-e2e/
   │ - kind create cluster (K8s 1.25 inside Docker)
   │ - exposes kubeconfig_path, kubectl(*args), api (pykube)
   ▼
[test_pvc_read_write_cycle]
   │
   ├─▶ kubectl apply -k k8s/overlays/e2e/
   │      ├─ PVC surg-rl-checkpoints (storageClassName: standard, 50Gi RWO)
   │      └─ Job surg-rl-e2e-write (CPU-only, mounts PVC at /checkpoints)
   │
   ├─▶ kubectl wait --for=condition=Bound pvc/surg-rl-checkpoints --timeout=180s
   │      (PVC binds AFTER write-Job pod is scheduled — WaitForFirstConsumer)
   │
   ├─▶ kubectl wait --for=condition=complete job/surg-rl-e2e-write --timeout=120s
   │      (write Job writes random N-byte checkpoint to /checkpoints/ckpt.bin)
   │
   ├─▶ kubectl apply -f write-or-read-pod (restart/replace: a NEW read Job)
   │      └─ Job surg-rl-e2e-read (mounts SAME PVC at /checkpoints, reads ckpt.bin)
   │
   ├─▶ kubectl wait --for=condition=complete job/surg-rl-e2e-read --timeout=120s
   │
   ├─▶ kubectl logs job/surg-rl-e2e-read  →  captures SHA256 of read-back bytes
   │
   └─▶ assert read_sha == write_sha  (byte-equality across pod restart)
   │
   ▼
[session teardown]  →  kind delete cluster  (unless --keep-cluster)
```

### System Architecture Diagram — Workstream B (ADR)

```
(docs only — no runtime data flow)
research findings (this RESEARCH.md)
   │
   ├─▶ modality fact: SurgToolLoc = endoscopic video + tool-presence labels
   │     source: https://surgtoolloc23.grand-challenge.org/data-description/
   │
   ├─▶ license fact: challenge guidelines clause 2 (non-commercial, no redistribution)
   │     source: https://surgtoolloc23.grand-challenge.org/challenge-guidelines/
   │
   ▼
docs/adr/0001-organ-mesh-licensing.md   (MADR format, status: accepted)
   ├─ Context      : v0.4.0 Phase 20 need for 4 organ OBJ meshes
   ├─ Options      : procedural gen (default) | SurgToolLoc (rejected) | other
   ├─ Decision     : procedural generation = default; SurgToolLoc rejected
   ├─ Consequences : +MIT-clean, +reproducible, -lower photorealism
   └─ References   : the two URLs above + arXiv:2305.07152 overview paper
```

### Recommended Project Structure

```
k8s/
├── base/
│   ├── pvc.yaml                 # existing — storageClassName: standard (matches kind)
│   ├── training-job.yaml        # existing — GPU job (NOT used by e2e)
│   └── ...
└── overlays/
    ├── cpu/                     # existing — CPU overlay (model for e2e)
    ├── gpu/                     # existing — GPU overlay
    └── e2e/                     # NEW — K8s PVC e2e overlay (SC#3)
        ├── kustomization.yaml   # resources: ../../base/pvc.yaml + patch Job to CPU-only e2e image
        └── e2e-job.yaml         # write/read Job (or patch training-job to a tiny e2e command)

tests/k8s/
└── test_pvc_e2e.py              # EXISTING STUB — de-stub (SC#1, SC#2)

.github/workflows/
└── ci.yml                       # add k8s-e2e job (SC#2)

docs/adr/                        # NEW directory (first ADR in repo)
└── 0001-organ-mesh-licensing.md # NEW ADR (SC#4, SC#5)

pyproject.toml                   # add [k8s-test] extra: pytest-kind>=22.11.1
```

### Pattern 1: pytest-kind session-scoped fixture usage

**What:** A single kind cluster is provisioned once per pytest session and shared across all `@pytest.mark.k8s` tests; teardown deletes it.
**When to use:** Any K8s e2e test — the fixture handles binary download, cluster creation, kubeconfig, and `kubectl` invocation.
**Example:**
```python
# Source: https://pypi.org/project/pytest-kind/ (pytest-kind 22.11.1 docs)
def test_myapp(kind_cluster):
    kind_cluster.load_docker_image("myapp")
    kind_cluster.kubectl("apply", "-f", "deployment.yaml")
    kind_cluster.kubectl("rollout", "status", "deployment/myapp")
    # kind_cluster.api is a pykube HTTPClient for typed access
```

### Pattern 2: apply-then-wait with WaitForFirstConsumer PVC binding

**What:** kind's default `standard` StorageClass uses `volumeBindingMode: WaitForFirstConsumer`. The PVC stays `Pending` until a consuming Pod is scheduled. `kubectl wait --for=condition=Bound` started before a Pod exists will time out.
**When to use:** Always with kind — apply the PVC AND a consuming Job/Pod together, then wait for Bound.
**Example:**
```python
# Source: https://github.com/kubernetes-sigs/kind/blob/main/pkg/build/nodeimage/const_storage.go
#         + https://github.com/kubernetes-sigs/kind/issues/3897
def test_pvc_read_write_cycle(kind_cluster):
    kind_cluster.kubectl("apply", "-k", "k8s/overlays/e2e")
    # PVC + write-Job applied together; PVC binds once the write-Job pod is scheduled
    kind_cluster.kubectl(
        "wait", "--for=condition=Bound", "pvc/surg-rl-checkpoints",
        "--timeout=180s",
    )
    kind_cluster.kubectl(
        "wait", "--for=condition=complete", "job/surg-rl-e2e-write",
        "--timeout=120s",
    )
    # ... apply read-Job, wait, compare SHAs ...
```

### Anti-Patterns to Avoid

- **`nodeName` in the e2e Job/Pod spec:** bypasses the Kubernetes scheduler, so with `WaitForFirstConsumer` binding the PVC is NEVER bound (kind issue #3897). Use `nodeSelector: {kubernetes.io/hostname: kind-control-plane}` if you must pin a node. The e2e overlay should NOT set `nodeName`. `[CITED: github.com/kubernetes-sigs/kind/issues/3897]`
- **`kubectl wait --for=condition=Bound pvc/...` BEFORE scheduling a consumer:** times out because the PVC stays Pending. Apply the consuming Job first (or together with the PVC). `[CITED: github.com/kubernetes-sigs/kind/blob/main/pkg/build/nodeimage/const_storage.go]`
- **Reusing the GPU `training-job.yaml` for the e2e test:** the base Job has `nvidia.com/gpu.present: "true"` nodeSelector + GPU tolerations/resources — kind has no GPU nodes, so the pod would stay Pending. The e2e overlay MUST strip GPU constraints (mirror `k8s/overlays/cpu/`).
- **Relying on a system-installed `kind` binary locally:** pytest-kind downloads its own `kind` to `./.pytest-kind/`. The existing `_kind_cluster_available()` helper checks `shutil.which("kind")` + `kind get clusters` — this does NOT reflect pytest-kind's auto-downloaded binary. The skip logic must be updated (see Workstream A pitfalls).
- **Treating the SurgToolLoc dataset as organ geometry:** the dataset is endoscopic video + tool-presence labels. There are NO organ meshes in SurgToolLoc. The ADR's primary rejection rationale is modality mismatch, with licensing secondary.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| K8s cluster provisioning for tests | Custom `kind create cluster` subprocess + kubeconfig management | `pytest-kind` `kind_cluster` session fixture | Handles binary download, cluster lifecycle, kubeconfig wiring, `kubectl(*args)` helper, and teardown; hand-rolled version reinvents all of this and leaks clusters on failure |
| K8s API access from Python | Raw `urllib`/`requests` against the K8s API with manual auth | `kind_cluster.api` (pykube HTTPClient) or `kind_cluster.kubectl(*args)` | pykube handles auth, retries, object serialization; raw HTTP against the K8s API is a known tarpit of TLS + token + protobuf details |
| PVC binding wait logic | Polling loop on `kubectl get pvc` parsing JSON output | `kubectl wait --for=condition=Bound pvc/<name> --timeout=180s` | `kubectl wait` is the blessed imperative; JSON-polling reinvents it with worse error handling |
| Kustomize overlay patching | Hand-editing base manifests for the e2e variant | `kustomization.yaml` with `patches:` (JSON6902 or strategic merge) | The repo already uses this pattern (`k8s/overlays/cpu/`); hand-editing base files breaks the cpu/gpu overlays |
| ADR format | Freeform markdown | MADR (Markdown Any Decision Record) template | Provides Context/Options/Decision/Consequences/References sections that match SC#4 exactly; the repo's first ADR sets the template for future ones |

**Key insight:** Every moving part in Workstream A already has a blessed tool (`pytest-kind` for cluster lifecycle, `kubectl wait` for polling, Kustomize for patching). Hand-rolling any of them is a net negative. Workstream B is pure prose with a conventional template.

## Runtime State Inventory

> Phase 39 is NOT a rename/refactor/migration phase. Inventory SKIPPED — no stored data, live service config, OS-registered state, secrets, or build artifacts carry a renamed string. The only runtime state created is ephemeral (a kind cluster + PVC + Jobs inside it, torn down at session end by pytest-kind).

## Common Pitfalls

### Pitfall 1: WaitForFirstConsumer PVC binding + `kubectl wait` timeout

**What goes wrong:** `kubectl wait --for=condition=Bound pvc/surg-rl-checkpoints` is invoked AFTER applying the PVC but BEFORE any consuming Pod is scheduled. With kind's default `standard` StorageClass (`volumeBindingMode: WaitForFirstConsumer`), the PVC stays `Pending` and `kubectl wait` times out at 180s — the test fails with a timeout, not a real persistence failure.
**Why it happens:** kind's local-path provisioner deliberately defers binding until the scheduler picks a node for the consumer Pod, so the PV lands on the right node.
**How to avoid:** Apply the PVC AND a consuming write-Job together (`kubectl apply -k k8s/overlays/e2e`), THEN run `kubectl wait --for=condition=Bound pvc/...`. The PVC binds once the write-Job Pod is scheduled. Optionally also `kubectl wait --for=condition=ready pod -l app=surg-rl-e2e --timeout=120s` to confirm scheduling.
**Warning signs:** PVC stuck in `Pending`; `kubectl get pvc` shows empty `VOLUME` column; events show `wait-for-first-consumer` wait.

### Pitfall 2: `nodeName` in Pod spec breaks PVC binding

**What goes wrong:** A well-meaning overlay pins the e2e Pod to `kind-control-plane` via `spec.nodeName: kind-control-plane`. The PVC never binds.
**Why it happens:** `nodeName` bypasses the scheduler; with `WaitForFirstConsumer` the scheduler is the component that sets the `volume.kubernetes.io/selected-node` annotation that triggers binding (kind issue #3897, rancher/local-path-provisioner#383).
**How to avoid:** Never set `nodeName` in the e2e Job spec. If node pinning is needed, use `nodeSelector: {kubernetes.io/hostname: kind-control-plane}` — the scheduler still runs.
**Warning signs:** Pod stays `Pending` with `PodHasNoVolumes` or PVC events show `provisioning` but never `provisioned`.

### Pitfall 3: macOS local run fails because Docker/kind unavailable

**What goes wrong:** A developer runs `pytest tests/` on macOS without Docker Desktop running (or without `kind` installed). The e2e test either errors out (Docker daemon unreachable → kind create fails) or is collected and fails.
**Why it happens:** The current `_kind_cluster_available()` only checks `shutil.which("kind")` + `kind get clusters` — it does NOT check Docker, and it does NOT account for pytest-kind's auto-downloaded `kind` binary. On this host, `kind` is NOT installed system-wide (`shutil.which("kind")` returns None) but `docker` is present — so the current helper skips correctly, but for the wrong reason.
**How to avoid:** Replace the skip gate with a Docker-daemon-reachability check + a platform opt-in. Recommended skip condition:
```python
def _k8s_e2e_available() -> bool:
    # CI forces the test via the k8s-e2e job (SURGRL_K8S_E2E=1 or runner.os == Linux)
    if not shutil.which("docker"):
        return False
    result = subprocess.run(["docker", "info"], capture_output=True, check=False)
    return result.returncode == 0
```
Keep the `@pytest.mark.k8s` + `@pytest.mark.integration` + `@pytest.mark.slow` marks so the default `pytest -m "not integration"` run never collects it. The dedicated `k8s-e2e` CI job runs `pytest -m k8s tests/k8s/` explicitly.
**Warning signs:** Test collected and failed (not skipped) on macOS; `pytest-kind` errors with "docker: Cannot connect to the Docker daemon".

### Pitfall 4: kind cluster startup time blows the CI job budget

**What goes wrong:** `kind create cluster` takes 1–3 minutes on a cold GitHub Actions runner (image pull + node bootstrap + CoreDNS readiness). A test that starts asserting immediately after `kind_cluster` fixture creation sees transient `NotFound`/`Connection refused` errors.
**Why it happens:** kind nodes and CoreDNS are not instantly ready; `kubectl wait` for system pods is needed.
**How to avoid:** The `kind_cluster` fixture already blocks until the cluster is up, but add an explicit `kubectl wait --for=condition=Ready node --all --timeout=180s` + `kubectl wait --for=condition=available deployment/coredns -n kube-system --timeout=180s` at the start of the test before applying the overlay. Budget the CI job for ~5 min total (cluster up + apply + write + restart + read + teardown).
**Warning signs:** Flaky CI failures on the first `kubectl apply` or `kubectl wait`; CoreDNS pods still `ContainerCreating`.

### Pitfall 5: e2e image not available in kind

**What goes wrong:** The e2e Job references `ghcr.io/surg-rl/surg-rl:v0.3.0` (or similar). kind does NOT pull from the GHCR by default in a clean CI environment, and image-pull failures leave the Job Pending.
**Why it happens:** `imagePullPolicy: IfNotPresent` + no prior pull; or a private registry without credentials.
**How to avoid:** Use a tiny public image for the e2e write/read Job (e.g., `busybox:1.36` or `python:3.11-slim`) with an inline `sh -c` command that writes/reads a file. The e2e test verifies PVC persistence, NOT the surg-rl training stack — so the image should be the smallest thing that can `echo` bytes to a mount path and `sha256sum` them back. Alternatively, build the surg-rl image in the CI job and `kind_cluster.load_docker_image(...)` it in — but that is heavier than the e2e assertion needs.
**Warning signs:** Job pod stuck in `ImagePullBackOff`; `kubectl describe pod` shows `Failed to pull image`.

### Pitfall 6: ADR cites a license clause that isn't actually public

**What goes wrong:** The ADR quotes "verbatim license text" that turns out to live behind a registration wall (the SurgToolLoc data download requires an agreement form emailed to `isi.challenges@intusurg.com`). A future auditor can't verify the citation.
**Why it happens:** The dataset EULA itself is NOT publicly displayable — only the challenge guidelines (which embed the data-use clauses as participant rules) are public.
**How to avoid:** Cite the PUBLIC challenge-guidelines page (https://surgtoolloc23.grand-challenge.org/challenge-guidelines/) which contains the verbatim clause text (clauses 2, 12, 13) as participant-facing rules. The dataset description page (https://surgtoolloc23.grand-challenge.org/data-description/) is also public and confirms the modality (video + tool-presence labels, no organ meshes). Do NOT claim to quote the private EULA — quote the public guidelines. State in the ADR that the dataset-specific EULA is gated behind an agreement form (isi.challenges@intusurg.com) and that the public challenge guidelines are the authoritative citable source for the non-commercial/no-redistribution terms.
**Warning signs:** An ADR reference URL returns a login/registration wall; a quoted clause cannot be found verbatim on the cited page.

## Code Examples

### Workstream A — de-stubbed PVC e2e test

```python
# Source: pytest-kind 22.11.1 fixture API (https://pypi.org/project/pytest-kind/)
#         + kind storage source (kubernetes-sigs/kind const_storage.go)
#         + existing tests/k8s/test_pvc_e2e.py stub
"""K8s PVC end-to-end checkpoint-persistence test (DEPLOY-01).

Asserts write -> pod restart -> read byte-equality on a bound PVC, via a
pytest-kind session-scoped kind cluster. Skips gracefully when Docker/kind
is unavailable (e.g. macOS local runs without Docker Desktop).
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess

import pytest


def _k8s_e2e_available() -> bool:
    """True if a Docker daemon is reachable (kind needs Docker to run)."""
    if not shutil.which("docker"):
        return False
    result = subprocess.run(["docker", "info"], capture_output=True, check=False)
    return result.returncode == 0


@pytest.mark.k8s
@pytest.mark.integration
@pytest.mark.slow
def test_pvc_checkpoint_persistence(kind_cluster) -> None:
    """Write a checkpoint to a bound PVC, restart the pod, read it back."""
    if not _k8s_e2e_available():
        pytest.skip("No Docker daemon available (K8s PVC e2e requires kind/Docker)")

    # 1. Apply the e2e overlay (PVC + CPU-only write Job together, so the PVC
    #    binds once the write-Job pod is scheduled -- kind uses WaitForFirstConsumer).
    kind_cluster.kubectl("apply", "-k", "k8s/overlays/e2e")

    # 2. Wait for the PVC to bind (consumer pod scheduling triggers binding).
    kind_cluster.kubectl(
        "wait", "--for=condition=Bound", "pvc/surg-rl-checkpoints",
        "--timeout=180s",
    )

    # 3. Wait for the write Job to complete (writes N random bytes to /checkpoints/ckpt.bin
    #    and prints the sha256 to stdout, captured in the Job logs).
    kind_cluster.kubectl(
        "wait", "--for=condition=complete", "job/surg-rl-e2e-write",
        "--timeout=120s",
    )
    write_sha = kind_cluster.kubectl("logs", "job/surg-rl-e2e-write").strip()

    # 4. Apply the read Job (a NEW pod mounting the SAME PVC -- the "restart" step).
    kind_cluster.kubectl("apply", "-f", "k8s/overlays/e2e/read-job.yaml")
    kind_cluster.kubectl(
        "wait", "--for=condition=complete", "job/surg-rl-e2e-read",
        "--timeout=120s",
    )
    read_sha = kind_cluster.kubectl("logs", "job/surg-rl-e2e-read").strip()

    # 5. Byte-equality across pod restart = checkpoint persisted on the bound PVC.
    assert read_sha == write_sha, (
        f"PVC persistence broken: wrote {write_sha}, read back {read_sha}"
    )
```

### Workstream A — `k8s/overlays/e2e/kustomization.yaml`

```yaml
# Source: modeled on k8s/overlays/cpu/kustomization.yaml (existing pattern)
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base/pvc.yaml      # the PVC under test (storageClassName: standard -- matches kind)
  - e2e-write-job.yaml       # CPU-only Job that writes a checkpoint to the PVC

# Strip GPU constraints (mirror k8s/overlays/cpu/) -- not present on the e2e
# Job since it is a fresh manifest, but kept here as the documented pattern.
patches: []
```

### Workstream A — `k8s/overlays/e2e/e2e-write-job.yaml`

```yaml
# Source: new file -- tiny CPU-only Job for PVC write/read persistence assertion.
# Uses busybox (public, ~2MB) -- the test verifies PVC persistence, not the surg-rl stack.
apiVersion: batch/v1
kind: Job
metadata:
  name: surg-rl-e2e-write
  labels:
    app: surg-rl
    component: e2e
spec:
  backoffLimit: 0
  ttlSecondsAfterFinished: 600
  template:
    metadata:
      labels:
        app: surg-rl
        component: e2e
    spec:
      restartPolicy: Never
      containers:
        - name: writer
          image: busybox:1.36
          command: ["/bin/sh", "-c"]
          args:
            - |
              set -e
              ckpt=/checkpoints/ckpt.bin
              head -c 4096 /dev/urandom > "$ckpt"
              sha256sum "$ckpt" | awk '{print $1}'
          volumeMounts:
            - name: checkpoints
              mountPath: /checkpoints
      volumes:
        - name: checkpoints
          persistentVolumeClaim:
            claimName: surg-rl-checkpoints
```

### Workstream A — CI job addition (`.github/workflows/ci.yml`)

```yaml
# Source: new job -- GitHub Actions Ubuntu runner has Docker preinstalled.
#         pytest-kind downloads kind + kubectl itself (no manual install needed).
  k8s-e2e:
    name: K8s PVC e2e (kind)
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev,k8s-test]"
      - name: Run PVC e2e test (CPU-only kind cluster)
        run: pytest tests/k8s/test_pvc_e2e.py -m k8s -v --cluster-name=surg-rl-e2e
```

### Workstream B — ADR content (verbatim license clauses to cite)

```markdown
# Source: https://surgtoolloc23.grand-challenge.org/challenge-guidelines/ (verified 2026-06-27)
> Clause 2: "Your team will use the provided data only in the scope of the
> challenge and neither pass it on to a third party nor use it for any
> publication or for commercial uses."

> Clause 13: "The data used for SurgToolLoc 2023 can only be used for
> publication purposes after the results of this challenge have been
> submitted for publication."
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| kind 0.10.0 / K8s 1.20 (older pytest-kind forks) | kind 0.17.0 / K8s 1.25 (pytest-kind 22.11.1) | pytest-kind 22.11.1 (2022-11-30) | Modern K8s API; `kubectl wait --for=condition=Bound` works as expected |
| Manual `kind create cluster` in CI | `pytest-kind` session fixture auto-provisions | pytest-kind 22.11.1 | Cluster lifecycle bound to test session; no leaked clusters |
| SurgToolLoc 2022 challenge (Intuitive Surgical) | SurgToolLoc 2022 + 2023 + SurgVU 2024–2026 (combined "Intuitive Surgical SurgToolLoc and SurgVU Challenges Results: 2022-2025" overview paper, arXiv:2305.07152) | 2022–2025 | Dataset is now publicly released ("free for use with proper citation" per challenge site) BUT the challenge guidelines still impose non-commercial / no-redistribution / challenge-scoped use clauses on participants |

**Deprecated/outdated:**
- The older `aantn/pytest-kind` GitHub fork (kind 0.10.0 / K8s 1.20) is superseded by the canonical `hjacobs/pytest-kind` on Codeberg + PyPI (22.11.1). Do NOT install the fork.
- The STATE.md note "needs the specific SurgToolLoc/EndoVis MICCAI license clause text cited (legal-text research, not code)" is now RESOLVED — the verbatim clause text is captured in this research (clauses 2 and 13 from the public challenge-guidelines page).

## Assumptions Log

> List all claims tagged `[ASSUMED]` in this research. The planner and discuss-phase use this section to identify decisions that need user confirmation before execution.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `pytest-kind>=22.11.1` will be added as a new `[k8s-test]` dev extra in `pyproject.toml` | Standard Stack / Package Legitimacy Audit | If the user prefers a different extra name or wants it under `[dev]`, the install command changes — low impact |
| A2 | The e2e Job uses `busybox:1.36` (a tiny public image) rather than the full surg-rl image, because the test verifies PVC persistence not the training stack | Code Examples / Pitfall 5 | If the user wants the e2e to exercise the actual surg-rl image, the CI job must build + `kind_cluster.load_docker_image(...)` it — heavier, ~2–3 min added |
| A3 | ADR location is `docs/adr/0001-organ-mesh-licensing.md` (MADR format, 4-digit zero-padded), creating the `docs/adr/` directory as the first ADR in the repo | Workstream B / Recommended Project Structure | Prior v0.5.0 research suggested `.planning/decisions/organ-mesh-licensing.md`; if the user prefers that location, the path changes — low impact; the content is identical |
| A4 | The e2e overlay applies ONLY `../../base/pvc.yaml` + a new `e2e-write-job.yaml`, NOT the full base (`training-job.yaml`, `raycluster.yaml`, etc.) | Workstream A / Recommended Project Structure | Applying the full base would pull in GPU nodeSelector/raycluster resources that fail on kind; the e2e only needs the PVC + a write/read Job |
| A5 | The macOS skip condition is "no Docker daemon" (not "no kind binary"), because pytest-kind auto-downloads kind but kind still needs Docker | Pitfall 3 / Code Examples | If the user wants to also gate on explicit opt-in (`SURGRL_K8S_E2E=1` env var), the skip helper gains one line — low impact |
| A6 | `pykube-ng` is a transitive dependency of pytest-kind (used by the `kind_cluster.api` attribute) and does not need to be declared explicitly in `[k8s-test]` | Standard Stack | If pytest-kind does not declare it as a hard dep, the test must `pip install pykube-ng` explicitly — verify in Wave 0 |

**If this table is empty:** N/A — six assumed claims listed. All are low-impact (path/name/extra choices) and can be confirmed at plan time.

## Open Questions (RESOLVED)

1. **Does the e2e test need to exercise the actual surg-rl training image, or is a `busybox` write/read cycle sufficient for DEPLOY-01?**
   - What we know: DEPLOY-01 says "K8s PVC checkpoint-persistence e2e test asserts write → pod restart → read on a bound PVC" — it does NOT mention the surg-rl image.
   - What's unclear: whether the milestone audit will consider a `busybox`-based persistence test "end-to-end" enough.
   - Recommendation: Use `busybox` for the persistence assertion (it tests the PVC path, which IS the unit of work for DEPLOY-01). If a reviewer wants the surg-rl image, add `kind_cluster.load_docker_image(...)` in a follow-up. The persistence property is image-independent.
   - RESOLVED: Use `busybox:1.36` for the e2e write/read Jobs (adopted in Plan 39-01 Task 2 — e2e-write-job.yaml + read-job.yaml both use `image: busybox:1.36`; the test asserts PVC persistence, not the surg-rl stack).

2. **Should the read-Job be a separate manifest (`read-job.yaml`) or a re-apply of the write-Job with a different command?**
   - What we know: The "restart" step needs a NEW pod mounting the same PVC.
   - What's unclear: whether to model it as two separate Jobs or one Job re-run with a different arg.
   - Recommendation: Two separate Job manifests (`e2e-write-job.yaml` + `read-job.yaml`) — clearer, and `kubectl wait --for=condition=complete` works per-Job.
   - RESOLVED: Two separate Job manifests — `e2e-write-job.yaml` (listed in the e2e overlay kustomization.yaml resources) + `read-job.yaml` (a directory artifact applied standalone via `kubectl apply -f` in Plan 39-01 Task 3's test body step (f), AFTER the write-Job completes; NOT listed in the overlay resources to avoid racing the write-Job for /checkpoints/ckpt.bin before it exists).

3. **ADR format: MADR (structured) vs. Nygard classic (prose)?**
   - What we know: This is the repo's first ADR; no prior format exists.
   - Recommendation: MADR (Markdown Any Decision Record) — its Context/Options/Decision/Consequences/References sections map directly onto SC#4's required content (Decision, Context, Considered options, Consequences, References). Sets a reusable template for future ADRs.
   - RESOLVED: MADR format (adopted in Plan 39-02 — ADR at `docs/adr/0001-organ-mesh-licensing.md` uses MADR Context/Options/Decision/Consequences/References structure).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | kind (provisions K8s nodes in containers) | ✓ (local: Darwin) / ✓ (CI Ubuntu runner, preinstalled) | 29.6.1 (local) | None — kind cannot run without Docker; test skips if unavailable |
| kind binary | pytest-kind (auto-downloads to `./.pytest-kind/`) | ✗ (local: not system-installed) / N/A (pytest-kind downloads it) | — | pytest-kind auto-download — no manual install needed |
| kubectl | `KindCluster.kubectl(*args)` (auto-downloaded) | ✓ (local: /usr/local/bin/kubectl) / ✓ (pytest-kind downloads it) | v1.34.1 (local) | pytest-kind auto-download |
| Kustomize | `kubectl apply -k` | ✓ (built into kubectl v1.34.1) | v5.7.1 | None — `kubectl apply -k` is the standard path |
| kind default StorageClass `standard` | PVC binding | ✓ (kind ships rancher.io/local-path provisioner named `standard`) | — | None — matches existing `k8s/base/pvc.yaml` |
| GitHub Actions Ubuntu runner | CI `k8s-e2e` job | ✓ (preinstalled Docker) | ubuntu-latest | None — macOS runner is NOT used for the k8s-e2e job (no Docker Desktop in macOS GHA runner by default) |

**Missing dependencies with no fallback:** none — all required tooling is either locally available (kubectl, Docker) or auto-provisioned by pytest-kind (kind, kubectl in CI).

**Missing dependencies with fallback:**
- `kind` binary not system-installed locally → pytest-kind auto-downloads it; the macOS local-skip path means this is moot for local runs (test skips when Docker daemon is down).

## Validation Architecture

> `workflow.nyquist_validation` is `true` in `.planning/config.json` — this section is REQUIRED.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >=7.0 (+ pytest-kind 22.11.1 for the k8s-marked test) |
| Config file | `pytest.ini` (markers: `integration`, `slow`, `k8s` registered) + `[tool.pytest.ini_options]` in `pyproject.toml` |
| Quick run command | `PYTHONPATH=src pytest tests/ -m "not integration" -v` (default — skips k8s) |
| Full suite command | `PYTHONPATH=src pytest tests/ -v` (includes k8s-marked test; will skip locally if no Docker) |
| K8s e2e command | `PYTHONPATH=src pytest tests/k8s/test_pvc_e2e.py -m k8s -v --cluster-name=surg-rl-e2e` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEPLOY-01 | PVC write → pod restart → read byte-equality on a bound PVC | integration (k8s) | `pytest tests/k8s/test_pvc_e2e.py::test_pvc_checkpoint_persistence -m k8s -v` | ✅ stub exists (to be de-stubbed in Wave 1) |
| DEPLOY-01 (skip path) | Test skips gracefully when Docker daemon unavailable | unit (skip-gate) | `pytest tests/k8s/test_pvc_e2e.py -m k8s -v` on macOS w/o Docker → SKIP | ✅ stub skip logic exists (to be refined) |
| ASET-06 | ADR file exists at `docs/adr/0001-organ-mesh-licensing.md` with status=accepted, cited URL, verbatim license clause | static (doc audit) | `test -f docs/adr/0001-organ-mesh-licensing.md && grep -q "challenge-guidelines" docs/adr/0001-organ-mesh-licensing.md` | ❌ Wave 0 (ADR is the deliverable) |
| ASET-06 (clause cite) | ADR quotes SurgToolLoc challenge guidelines clause 2 verbatim | static (doc audit) | `grep -F "neither pass it on to a third party" docs/adr/0001-organ-mesh-licensing.md` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `PYTHONPATH=src pytest tests/ -m "not integration" -v` (the k8s test is excluded from the default run; it runs only in the dedicated CI job)
- **Per wave merge:** `PYTHONPATH=src pytest tests/ -v` + the ADR static-audit grep checks
- **Phase gate:** Full suite green on Linux CI + the `k8s-e2e` job green on Ubuntu + ADR audit grep checks pass

### Wave 0 Gaps

- [ ] `tests/k8s/test_pvc_e2e.py` — de-stub the body (replace TODO with the write/read cycle)
- [ ] `k8s/overlays/e2e/kustomization.yaml` + `e2e-write-job.yaml` + `read-job.yaml` — new overlay (SC#3)
- [ ] `docs/adr/0001-organ-mesh-licensing.md` — new ADR (SC#4, SC#5)
- [ ] `.github/workflows/ci.yml` — add `k8s-e2e` job (SC#2)
- [ ] `pyproject.toml` — add `[k8s-test]` extra with `pytest-kind>=22.11.1` (verify pykube-ng is transitively pulled; if not, add explicitly)
- [ ] Framework install: `pip install -e ".[dev,k8s-test]"` — pytest-kind is NOT currently a dependency (confirm in Wave 0)

## Security Domain

> `security_enforcement` is not set in `.planning/config.json` (absent = enabled). However, Phase 39 introduces no new user-input handling, auth, crypto, or access-control surface. The K8s e2e test operates on an ephemeral local kind cluster with no real secrets; the ADR is documentation. Include the applicable categories for completeness.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A — e2e test uses kind's local admin kubeconfig; no user auth |
| V3 Session Management | no | N/A — no sessions |
| V4 Access Control | yes (minimal) | The e2e test uses the existing `k8s/base/rbac.yaml` ServiceAccount (`surg-rl`); the Job mounts the PVC via `claimName`, no privilege escalation. kind's RBAC is default-deny |
| V5 Input Validation | no | N/A — the test reads its own written bytes back; no external input |
| V6 Cryptography | no | N/A — `sha256sum` is used for byte-equality assertion, not for security |

### Known Threat Patterns for K8s e2e

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| PVC data leak across test runs | Information Disclosure | kind cluster is ephemeral and torn down at session end (`kind delete cluster`); `reclaimPolicy: Delete` on the `standard` StorageClass wipes PVs on PVC deletion |
| Image pull from untrusted registry | Tampering | Use a pinned public image (`busybox:1.36` with digest pin recommended) — no private registry credentials in the e2e path |
| Kubeconfig leak | Information Disclosure | pytest-kind writes kubeconfig to `./.pytest-kind/{cluster-name}/kubeconfig.conf` (local, ephemeral); the CI job does not upload artifacts from that path |

## Sources

### Primary (HIGH confidence)

- **PyPI — pytest-kind 22.11.1** — https://pypi.org/project/pytest-kind/ — fixture API (methods, attributes, session scope), CLI options (`--cluster-name`, `--keep-cluster`), binary provisioning (`./.pytest-kind/{cluster-name}/`), bundled kind 0.17.0 / K8s 1.25, license GPL-3.0+
- **kind source — `const_storage.go`** — https://github.com/kubernetes-sigs/kind/blob/main/pkg/build/nodeimage/const_storage.go — default StorageClass named `standard`, provisioner `rancher.io/local-path`, `volumeBindingMode: WaitForFirstConsumer`, `reclaimPolicy: Delete`, default-class annotation
- **kind issue #3897** — https://github.com/kubernetes-sigs/kind/issues/3897 — `nodeName` bypasses scheduler → PVC stays Pending with WaitForFirstConsumer
- **SurgToolLoc 2023 Challenge Guidelines** — https://surgtoolloc23.grand-challenge.org/challenge-guidelines/ — verbatim clause 2 ("...only in the scope of the challenge and neither pass it on to a third party nor use it for any publication or for commercial uses."), clause 13 (publication embargo until challenge results submitted)
- **SurgToolLoc 2023 Data Description** — https://surgtoolloc23.grand-challenge.org/data-description/ — 24,695 endoscopic video clips, 720p, tool-presence labels for 14 tools across 4 robotic arms; NO organ meshes mentioned
- **SurgToolLoc 2022 Getting Started** — https://surgtoolloc.grand-challenge.org/getting-started/ — agreement-form requirement, contact `isi.challenges@intusurg.com`, data download gated behind registration
- **arXiv:2305.07152** — https://arxiv.org/abs/2305.07152 — "Intuitive Surgical SurgToolLoc and SurgVU Challenges Results: 2022-2025"; challenge organized by Intuitive Surgical; hosted through MICCAI; paper itself CC BY 4.0

### Secondary (MEDIUM confidence)

- **EndoVis MICCAI challenge data-use patterns** — web search corroborated that Intuitive Surgical-organized EndoVis sub-challenges using surgical training video (SurgVu 2025/2026, CASVU 2024) apply CC BY-NC-ND / CC BY-NC-SA licenses; SurgToolLoc's challenge-guidelines clauses are consistent with this non-commercial pattern (the guidelines predate the CC-licensed public re-release)
- **rancher/local-path-provisioner#383** — https://github.com/rancher/local-path-provisioner/issues/383 — confirms the `nodeName`-vs-`nodeSelector` binding failure mode

### Tertiary (LOW confidence)

- **Dataset paper arXiv:2501.09209** — referenced from the overview paper (2305.07152) as "detailed in a separate paper"; not fetched this session (the data-description page already confirms the modality — endoscopic video + tool-presence labels, no organ meshes). Cite as a secondary reference in the ADR if the user wants the dataset description paper.

## Metadata

**Confidence breakdown:**
- Standard stack (pytest-kind): HIGH — verified against PyPI (version, fixture API, binary provisioning, bundled kind version) and local kubectl/docker availability
- K8s storage behavior: HIGH — verified against kind source code (`const_storage.go`) + the WaitForFirstConsumer binding pitfall is documented in kind's own issue tracker
- ADR licensing clauses: HIGH — verbatim clause text fetched directly from the public challenge-guidelines page; modality confirmed from the public data-description page
- ADR format/location: MEDIUM — first ADR in repo; MADR format is a recommendation, the path `docs/adr/0001-...` is a convention choice (prior research suggested `.planning/decisions/...`)
- CI job pattern: HIGH — GitHub Actions Ubuntu runners have Docker preinstalled (well-documented); pytest-kind handles kind/kubectl download

**Research date:** 2026-06-27
**Valid until:** 2026-07-27 (30 days — stable; pytest-kind 22.11.1 is the latest release as of research date, and the SurgToolLoc challenge guidelines are stable public pages)
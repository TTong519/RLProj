---
status: complete
phase: 39-k8s-pvc-e2e-organ-mesh-licensing-adr
source: [39-01-SUMMARY.md, 39-02-SUMMARY.md]
started: 2026-06-28T05:36:27Z
updated: 2026-07-09T00:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Observe the `k8s-e2e` CI job go GREEN on the next push/PR (or a local Docker run)
expected: Job `K8s PVC e2e (kind)` on ubuntu-latest passes the `pytest tests/k8s/test_pvc_e2e.py -m k8s -v --cluster-name=surg-rl-e2e` step with exit 0; the test executes `assert read_sha == write_sha` against a bound PVC (not skipped). Equivalently, a local run with Docker Desktop running + `PYTHONPATH=src pytest tests/k8s/test_pvc_e2e.py -m k8s -v --cluster-name=surg-rl-e2e` is GREEN.
result: pass
note: "Re-tested 2026-07-09. Post-merge CI fix (ae773b7) landed on main; latest run on 601819a (2026-07-04) shows K8s PVC e2e (kind) -> success, test_pvc_checkpoint_persistence PASSED [100%] (executed against bound PVC, not skipped). User confirmed."

### 2. ADR-0001 records the organ-mesh licensing decision with cited rationale
expected: Open `docs/adr/0001-organ-mesh-licensing.md`. It is a MADR-format ADR with `Status: accepted` that records procedural generation as the DEFAULT organ-mesh source and SurgToolLoc as REJECTED on dual grounds — PRIMARY modality mismatch (endoscopic video + tool-presence labels, no organ meshes) and SECONDARY licensing incompatibility (MICCAI/EndoVis non-commercial clause 2 quoted verbatim on a single line). Both public URLs are cited in References: https://surgtoolloc23.grand-challenge.org/challenge-guidelines/ and https://surgtoolloc23.grand-challenge.org/data-description/.
result: pass

### 3. ADR README index lists and links ADR-0001
expected: Open `docs/adr/README.md`. It contains a 4-column table (`ADR | Title | Status | Date`) with a single row for `0001` titled "Organ-Mesh Licensing" (or similar), status `accepted`, dated 2026-06-27, linking to `./0001-organ-mesh-licensing.md`.
result: pass

## Summary

total: 3
passed: 3
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none — prior blocker on test 1 resolved by post-merge CI fix on main; re-confirmed 2026-07-09]
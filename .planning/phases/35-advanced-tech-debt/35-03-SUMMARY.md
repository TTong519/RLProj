---
phase: 35-advanced-tech-debt
plan: 03
subsystem: infrastructure
status: complete
tags:
  - kubernetes
  - pvc
  - stub
key-files:
  created:
    - tests/k8s/__init__.py
    - tests/k8s/test_pvc_e2e.py
  modified:
    - pytest.ini
metrics:
  lines_added: 0
  lines_removed: 0
  tests_added: 1
commits:
  - hash: TBD
    description: "infra(35-03): add K8s PVC e2e stub and [k8s] pytest marker"
deviations:
  - "Test body is intentionally a TODO/pass stub; real PVC read/write/delete cycle requires a live kind cluster and is deferred to v0.6.0."
self_check: PASSED
---

# Plan 35-03 Summary

## What was done
- Created `tests/k8s/__init__.py` and `tests/k8s/test_pvc_e2e.py`.
- The test is marked `@pytest.mark.k8s`, `@pytest.mark.integration`, and
  `@pytest.mark.slow`.
- It skips when no local `kind` cluster is available and documents the v0.6.0
  TODO for the full PVC read/write/delete cycle.
- Registered the `k8s` marker in `pytest.ini`.

## Verification
- `PYTHONPATH=src pytest tests/k8s/test_pvc_e2e.py -v` skips cleanly on a
  machine without `kind`.
- `pytest --collect-only -m k8s` shows the marker is registered.

## Self-Check: PASSED

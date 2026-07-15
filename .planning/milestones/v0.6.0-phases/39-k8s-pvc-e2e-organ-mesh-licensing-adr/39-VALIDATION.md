---
phase: 39
slug: k8s-pvc-e2e-organ-mesh-licensing-adr
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-27
updated: 2026-07-15
---

# Phase 39 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

> Source of truth for sampling details: the `## Validation Architecture` section in
> `39-RESEARCH.md` (Workstream A: PVC write→restart→read byte-equality on a Bound PVC,
> CPU-only CI sample point, macOS skip path; Workstream B: ADR auditability check — file
> exists at `docs/adr/0001-organ-mesh-licensing.md`, contains the cited challenge-terms URL,
> quotes the verbatim non-commercial license clause, decision status = accepted). The
> per-task map below was completed during execution and audited on 2026-07-15.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (pytest.ini present) |
| **Config file** | `pytest.ini` (markers: `integration`, `slow`, `k8s`; `pythonpath=src`; `addopts=-v --tb=short`) |
| **Quick run command** | `PYTHONPATH=src pytest tests/test_adr_licensing.py tests/test_dreamer_checkpoints.py -v` |
| **Full suite command** | `PYTHONPATH=src pytest tests/ -m "not integration" -q` |
| **Estimated runtime** | ~20s (ADR + checkpoint unit guards); `tests/k8s/test_pvc_e2e.py` runs in the `k8s-e2e` CI job on ubuntu-latest (~3–6 min, skips on macOS without Docker) |

---

## Sampling Rate

- **After every task commit:** Run the quick run command (ADR + checkpoint unit guards)
- **After every plan wave:** Run the full suite command
- **Before `/gsd-verify-work`:** Full suite must be green; `k8s-e2e` CI job observed GREEN on the next push/PR
- **Max feedback latency:** ~20s (unit guards); the PVC e2e invariant's authoritative GREEN is the CI job (~6 min)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 39-01-01 | 01 | 1 | DEPLOY-01 | T-39-SC / T-39-01..05 | PVC write→restart→read byte-equality on a bound PVC; e2e Jobs mount no secret, no serviceAccountName, no nodeName | e2e (CI) | `PYTHONPATH=src pytest tests/k8s/test_pvc_e2e.py -m k8s -v` (CI `k8s-e2e` job) | ✅ | ✅ green (CI observed GREEN 2026-07-09, `assert read_sha == write_sha` on bound PVC; skips gracefully on macOS) |
| 39-01-02 | 01 | 1 | DEPLOY-01 | T-39-02/03/05 | Overlay references ONLY `../../base/pvc.yaml`; no bare `- ../../base`; read-job applied standalone; CPU-only CI job | unit (source-inspection) | `python -c "import yaml; ..."` + greps (run during execution; structural) | ✅ | ✅ green |
| 39-02-01 | 02 | 1 | ASET-06 | T-39-06..09 | ADR quotes only the public challenge-guidelines page (no gated EULA); both public URLs cited; verbatim clause 2 on a grep-matchable line | unit (static-content guard) | `PYTHONPATH=src pytest tests/test_adr_licensing.py -v` | ✅ | ✅ green (10/10, added 2026-07-15 Nyquist audit) |
| 39-02-02 | 02 | 1 | ASET-06 | T-39-08 | ADR decision is auditable: `Status: accepted`, both rationales cited, README index links ADR-0001 | unit (static-content guard) | `PYTHONPATH=src pytest tests/test_adr_licensing.py::test_adr_readme_indexes_adr_0001 -v` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.* The `[k8s-test]` pyproject extra (`pytest-kind>=22.11.1`) was installed during Plan 01; no new framework was needed for the ADR guard (plain pytest + stdlib `pathlib`).

---

## Manual-Only Verifications

*None remaining.* The sole behavior-dependent truth (SC#1 live-cluster GREEN) was closed on 2026-07-09: the `k8s-e2e` CI job ran `test_pvc_checkpoint_persistence` PASSED against a bound PVC (commit `601819a`), confirmed in `39-UAT.md` test 1. See `39-VERIFICATION.md` re-verification note.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (ADR guard added 2026-07-15)
- [x] No watch-mode flags
- [x] Feedback latency < 20s (unit guards); e2e invariant ~6 min in CI
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-15

---

## Validation Audit 2026-07-15

| Metric | Count |
|--------|-------|
| Gaps found | 1 |
| Resolved | 1 |
| Escalated | 0 |

**Gap closed:** ASET-06 (Plan 39-02) had no persistent automated test — the plan's SC#4/SC#5 auditability checks were run as one-off grep gates during execution. Added `tests/test_adr_licensing.py` (10 CPU-runnable, unconditional assertions: ADR file exists, `procedural generation` / `rejected` / `modality` / `endoscopic` / `Status: accepted` tokens, verbatim MICCAI/EndoVis clause 2, both public URLs, README index link). Runs green in 0.01s. Verified `ruff`/`black` clean.

**DEPLOY-01** confirmed COVERED — `test_pvc_checkpoint_persistence` is fully de-stubbed and the `k8s-e2e` CI job was observed GREEN on a bound PVC (re-verification 2026-07-09). The local-macOS SKIP is the designed graceful-skip path (Docker-gated), not a gap.

**Phase 39 verdict: NYQUIST-COMPLIANT** — all requirements (DEPLOY-01, ASET-06) have automated verification that runs green.
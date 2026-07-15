---
phase: 40
slug: real-dreamerv3-integration-sentinel-flip
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-11
updated: 2026-07-15
---

# Phase 40 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

> Audited 2026-07-15. Per the phase's INV-8 contract, the runtime GREEN for DMV3-07/08/10
> is by design deferred to the CI `dreamer-gpu` job (Wave 3, Plan 40-04), pending GitHub
> GPU Actions runner enablement (an ops step, not a code gap). CPU-runnable guards
> (regression guard, JAX-leak guard, `*.ckpt` glob unit tests) are GREEN and run on every PR.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (pytest.ini present) |
| **Config file** | `pytest.ini` (markers: `integration`, `slow`, `k8s`; `pythonpath=src`; `addopts=-v --tb=short`) |
| **Quick run command** | `PYTHONPATH=src pytest tests/dreamer/test_dreamerv3_regression_guard.py tests/test_dreamer_subprocess.py::TestProcessIsolationImport tests/test_dreamer_checkpoints.py -v` |
| **Full suite command** | `PYTHONPATH=src pytest tests/ -m "not integration" -q` |
| **Estimated runtime** | ~2s (CPU guards, 13+ tests); GPU-gated `tests/dreamer/` E2E+resume tests run in the `dreamer-gpu` CI job on `ubuntu-latest-4-core-gpu` (~3–5 min + install) |

---

## Sampling Rate

- **After every task commit:** Run the quick run command (regression guard + JAX-leak guard + checkpoint unit tests)
- **After every plan wave:** Run the full suite command (CPU suite green; GPU-gated tests skip cleanly per INV-8)
- **Before `/gsd-verify-work`:** CPU suite green; GPU GREEN observed on the `dreamer-gpu` CI job (pending runner enablement)
- **Max feedback latency:** ~2s (CPU guards); GPU smoke ~5 min in CI

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 40-01-01 | 01 | 1 | DMV3-09 | T-40-01 | `_build_agent` never returns `None` (regression guard against stub regression); AST source-inspection, no skipif (runs every PR) | unit (source-inspection) | `PYTHONPATH=src pytest tests/dreamer/test_dreamerv3_regression_guard.py -v` | ✅ | ✅ green (1/1) |
| 40-01-02 | 01 | 1 | DMV3-09 / SC#5 | T-40-05 | No module-top `jax`/`dreamerv3`/`embodied`/`optax` imports in `subprocess.py` (JAX isolation); logger→stderr | unit (source-inspection) | `PYTHONPATH=src pytest tests/test_dreamer_subprocess.py::TestProcessIsolationImport -v` | ✅ | ✅ green (3/3) |
| 40-02-01 | 02 | 2 | DMV3-07 / DMV3-09 | T-40-04/05/06 | Real `_train_loop` (manual `embodied.Driver` + `agent.train`, NOT `embodied.run.train`); METRICS dict yield; logger→stderr; sentinel E2E flipped negative→positive | unit (source-inspection) + e2e (GPU) | CPU greps + `pytest tests/dreamer/test_dreamerv3_subprocess_e2e.py` (GPU-gated) | ✅ | ⚠️ partial (source green; runtime GREEN deferred to CI `dreamer-gpu`) |
| 40-02-02 | 02 | 2 | DMV3-10 | T-40-06 | Structural-only E2E assertions: `math.isfinite`, `last <= first * 2.0`, checkpoint exists, training completes — NO `MSE<0.01`/`reward_mae<0.5` threshold | unit (source-inspection) + e2e (GPU) | `grep -c 'MSE<0.01\|...'` == 0 + `pytest tests/dreamer/test_dreamerv3_subprocess_e2e.py` (GPU-gated) | ✅ | ⚠️ partial (source green; runtime GREEN deferred to CI) |
| 40-03-01 | 03 | 2 | DMV3-08 | T-40-07/08 | `_find_latest_checkpoint` globs `*.ckpt` (no `.pt` shim, D-09); `run_dreamer_training` path refs `.ckpt`; signature unchanged | unit | `PYTHONPATH=src pytest tests/test_dreamer_checkpoints.py -v` | ✅ | ✅ green (8/8) |
| 40-03-02 | 03 | 2 | DMV3-08 | T-40-07/08 | Restart-then-continue resume test (run1 writes `checkpoint.ckpt`; run2 `resume=True` completes to 1000 steps, finite loss) | e2e (GPU) | `pytest tests/dreamer/test_dreamerv3_checkpoint_resume.py` (GPU-gated) | ✅ | ⚠️ partial (collects + skips cleanly on macOS per INV-8; resume GREEN deferred to CI) |
| 40-04-01 | 04 | 3 | DMV3-10 | — | `dreamer-gpu` CI job: `ubuntu-latest-4-core-gpu`, not-per-PR gate (`push main`/`v*`/`workflow_dispatch`), `jax[cuda12]` installed first, `pytest tests/dreamer/ -v -rs`, `timeout-minutes:15`, structural smoke | CI (GPU) | trigger `dreamer-gpu` job (merge-to-main / `v*` tag / Actions Run workflow) | ✅ | ⚠️ partial (job structurally complete + YAML valid; GREEN pending GPU runner enablement) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.* The `[dreamer]` pyproject extra (`dreamerv3~=1.5.0`, `optax>=0.1.7`) was already declared; `[k8s-test]` from Phase 39. No new framework needed for CPU guards.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| First `dreamer-gpu` CI job GREEN on a real GPU runner (all 5 `tests/dreamer/` tests pass) | DMV3-07 / DMV3-08 / DMV3-10 | Requires GitHub-hosted GPU Actions runners enabled on the repo account (org billing → Actions → GPU runners, `ubuntu-latest-4-core-gpu` label per D-01) — an ops enablement step, not a code change. Cannot be exercised on macOS per INV-8. | Enable GPU runners; trigger the `dreamer-gpu` job (push to `main`, `v*` release tag, or Actions tab → CI → Run workflow). Confirm GREEN within 15 min: regression guard + color constant + `test_e2e_run_dreamer_training_real_agent` (finite + non-explosive loss) + `test_e2e_checkpoint_files_written` + `test_restart_then_continue` (resume to 1000 steps). |

> This is the designed end-state of Phase 40 (the GPU-gated LAST phase of v0.6.0), matching the status Phase 30 carried. The tests + CI job exist and are structurally complete; CPU guards are GREEN; the GPU GREEN certifies DMV3-07 runtime, DMV3-08 resume, and DMV3-10 CI in one observed run. Flagged for the v0.6.0 milestone audit.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (no MISSING tests — all reqs have tests/CI)
- [x] No watch-mode flags
- [x] Feedback latency < 2s (CPU guards); GPU smoke ~5 min in CI
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-15

---

## Validation Audit 2026-07-15

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

**No MISSING tests.** Every Phase 40 requirement (DMV3-07, DMV3-08, DMV3-09, DMV3-10) has an automated test or CI job that targets its behavior:

- **DMV3-09** — COVERED: `tests/dreamer/test_dreamerv3_regression_guard.py` (CPU, 1/1 green) + JAX-leak guard (`tests/test_dreamer_subprocess.py::TestProcessIsolationImport`, 3/3 green). The sentinel flip + regression guard is fully verified on CPU.
- **DMV3-07** — PARTIAL by design: `tests/dreamer/test_dreamerv3_subprocess_e2e.py::test_e2e_run_dreamer_training_real_agent` exists and is wired; runtime GREEN is GPU-gated (skips on macOS per INV-8) and deferred to the `dreamer-gpu` CI job. Not a MISSING test.
- **DMV3-08** — PARTIAL by design: `tests/test_dreamer_checkpoints.py` (8/8 CPU green, `*.ckpt` glob) + GPU-gated `tests/dreamer/test_dreamerv3_checkpoint_resume.py::test_restart_then_continue` (collects + skips cleanly). Resume runtime GREEN deferred to CI. Not a MISSING test.
- **DMV3-10** — PARTIAL by design: `dreamer-gpu` CI job in `.github/workflows/ci.yml` (structurally complete, YAML valid); GREEN pending GitHub GPU runner enablement (ops step). Not a MISSING test.

The PARTIAL statuses are GPU-gated-by-design (INV-8), not fixable by generating new tests — the tests and CI job already exist. Generating CPU tests for GPU-gated runtime behavior would not add real coverage (they cannot execute the real `dreamerv3.Agent` path). The runtime GREEN routes to Manual-Only (observe first `dreamer-gpu` GREEN after GPU runner enablement), consistent with `40-VERIFICATION.md`.

**Phase 40 verdict: NYQUIST-COMPLIANT (PARTIAL until GPU GREEN)** — all requirements have automated verification; DMV3-09 runs green on CPU; DMV3-07/08/10 GREEN is deferred to the `dreamer-gpu` CI job pending the GPU-runner ops enablement action item flagged for the v0.6.0 milestone audit.
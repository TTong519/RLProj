---
phase: 24
slug: dreamerv3-world-models
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-09
audited: 2026-06-09
---

# Phase 24 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Reconstructed from SUMMARY.md artifacts (State B) and gap-filled by gsd-nyquist-auditor.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pytest.ini (auto-adds `src/` to pythonpath) |
| **Quick run command** | `PYTHONPATH=src python -m pytest tests/test_dreamer_training.py tests/test_dreamer_subprocess.py tests/test_dreamer_wrapper.py tests/test_dreamer_spike.py tests/test_dreamer_evaluate_checkpoint.py tests/test_dreamer_checkpoints.py tests/test_dreamer_benchmark_integration.py` |
| **Full suite command** | `PYTHONPATH=src python -m pytest tests/` |
| **Estimated runtime** | ~5 seconds (7 dreamer test files, 114 tests) |

---

## Sampling Rate

- **After every task commit:** Run the dreamer test subset above
- **After every plan wave:** Run full suite
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-task Verification Map

| task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 24-01-01 | 01 | 1 | DMV3-03 | T-24-01, T-24-05 | DreamerSubprocess spawns isolated subprocess; XLA memory fraction set; no JAX in main process | unit | `python -m pytest tests/test_dreamer_subprocess.py` | ✅ | ✅ green |
| 24-01-02 | 01 | 1 | DMV3-04 | T-24-01, T-24-02 | GymToEmbodiedWrapper produces pixel (64×64 RGBA) and state (128-dim) embodied observations | unit | `python -m pytest tests/test_dreamer_wrapper.py` | ✅ | ✅ green |
| 24-01-03 | 01 | 1 | DMV3-01 | T-24-01 | SpikeOrchestrator creates forceps+liver+suturing scene, runs spike, writes report | unit | `python -m pytest tests/test_dreamer_spike.py` | ✅ | ✅ green |
| 24-02-01 | 02 | 2 | DMV3-02, DMV3-04 | T-24-06, T-24-07 | run_dreamer_training supports all 6 tasks, both obs modes, checkpoints, resume, eval_only | unit | `python -m pytest tests/test_dreamer_evaluate_checkpoint.py tests/test_dreamer_checkpoints.py` | ✅ | ✅ green |
| 24-02-02 | 02 | 2 | DMV3-03, DMV3-04 | T-24-09 | `surg-rl dreamer-train` CLI runs JAX subprocess, checks spike status | unit | `python -m pytest tests/test_dreamer_subprocess.py` | ✅ | ✅ green |
| 24-03-01 | 03 | 3 | DMV3-05 | T-24-10 | ExperimentRunner auto-discovers DreamerV3 checkpoints, integrates results | unit | `python -m pytest tests/test_dreamer_benchmark_integration.py` | ✅ | ✅ green |
| 24-03-02 | 03 | 3 | DMV3-05 | T-24-12 | ReportGenerator JSON exports `dreamer_v3` section with `benchmark_scope`; DREAMERV3_COLOR used in plots | unit | `python -m pytest tests/test_dreamer_benchmark_integration.py` | ✅ | ✅ green |
| 24-04-01 | 04 | 4 | DMV3-01, DMV3-05 | T-24-13, T-24-15 | SpikeOrchestrator writes detailed failure report; check_spike_status returns it | unit | `python -m pytest tests/test_dreamer_spike.py` | ✅ | ✅ green |
| 24-04-02 | 04 | 4 | DMV3-05 | T-24-15 | `surg-rl dreamer-train` exits code 2 on spike failure; `surg-rl dreamer-spike` is standalone | unit | `python -m pytest tests/test_dreamer_benchmark_integration.py` | ✅ | ✅ green |
| 24-05-01 | 05 | 5 | DMV3-02, DMV3-04 | T-24-16, T-24-17 | `_create_scene_for_task` handles all 6 task types with proper InstrumentType / TissueType | unit | `python -m pytest tests/test_dreamer_training.py` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

### Coverage by Requirement

| Requirement | Description | Covered by |
|-------------|-------------|------------|
| DMV3-01 | Feasibility spike (forceps + liver tet mesh + suturing) | test_dreamer_spike.py (16 tests on SpikeOrchestrator + check_spike_status + report schema) |
| DMV3-02 | DreamerV3 training supports all 6 tasks + checkpoint discovery | test_dreamer_training.py (10 tests), test_dreamer_evaluate_checkpoint.py (8 tests), test_dreamer_checkpoints.py (8 tests) |
| DMV3-03 | Process-isolated JAX subprocess with JSON protocol | test_dreamer_subprocess.py (23 tests) |
| DMV3-04 | Pixel (64×64 RGBA) + low-dim state (128-dim) embodied observations | test_dreamer_wrapper.py (27 tests) |
| DMV3-05 | Benchmark integration / SB3-only mode / spike failure handling | test_dreamer_benchmark_integration.py (18 tests) |

---

## Wave 0 Requirements

- [x] `tests/test_dreamer_training.py` — stubs for DMV3-02 / DMV3-04 task types (existed pre-audit)
- [x] `tests/test_dreamer_subprocess.py` — DreamerSubprocess (NEW, 2026-06-09)
- [x] `tests/test_dreamer_wrapper.py` — GymToEmbodiedWrapper (NEW, 2026-06-09)
- [x] `tests/test_dreamer_spike.py` — SpikeOrchestrator + check_spike_status (NEW, 2026-06-09)
- [x] `tests/test_dreamer_evaluate_checkpoint.py` — evaluate_checkpoint (NEW, 2026-06-09)
- [x] `tests/test_dreamer_checkpoints.py` — _find_latest_checkpoint (NEW, 2026-06-09)
- [x] `tests/test_dreamer_benchmark_integration.py` — DREAMERV3_COLOR + ExperimentRunner + ReportGenerator (NEW, 2026-06-09)
- [x] `tests/conftest.py` — shared fixtures (exists, no modifications needed)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `surg-rl dreamer-spike` end-to-end run on real GPU/JAX | DMV3-01 | Requires dreamerv3 JAX install + GPU; spike is a long-running training job (100k steps) | Run `surg-rl dreamer-spike --task suturing --steps 100000` on a CUDA-capable host. Verify `models/dreamerv3/spike_report.json` written and pass/fail determined against thresholds (MSE < 0.01, MAE < 0.5). |
| `surg-rl dreamer-train` end-to-end training | DMV3-02, DMV3-04 | Requires JAX/GPU + dreamerv3 + completed passing spike | Run `surg-rl dreamer-train --task suturing --obs-type state --steps 500000`. Verify checkpoint at `models/dreamerv3/suturing_state/final.pt` and `training_metrics.json` with non-empty curves. |
| `surg-rl benchmark --dreamer-comparison` end-to-end | DMV3-05 | Requires full benchmark + dreamer checkpoints | Run `surg-rl benchmark --dreamer-comparison` after dreamer training. Verify `models/dreamerv3/.../benchmark_report.html` shows DreamerV3 results in orange or "DEFERRED TO v0.5.0" banner. |

These are CI-deployable manual checks. All structural / API contracts are fully covered by the 114 automated tests above.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (6 new test files generated)
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-09

---

## Validation Audit 2026-06-09

| Metric | Count |
|--------|-------|
| Gaps found | 6 |
| Resolved | 6 |
| Escalated to manual-only | 0 |
| Test files added | 6 |
| Tests added | 104 |
| Total dreamer tests | 114 (all green) |

### Files added
- `tests/test_dreamer_subprocess.py` (23 tests)
- `tests/test_dreamer_wrapper.py` (27 tests)
- `tests/test_dreamer_spike.py` (20 tests)
- `tests/test_dreamer_evaluate_checkpoint.py` (8 tests)
- `tests/test_dreamer_checkpoints.py` (8 tests)
- `tests/test_dreamer_benchmark_integration.py` (18 tests)

### Notes
- Audit performed via `gsd-validate-phase` (State B: VALIDATION.md did not exist; reconstructed from SUMMARY.md artifacts).
- Existing `tests/test_dreamer_training.py` (10 tests) already COVERED Plan 05 (all 6 task types).
- All 6 gap areas (Plans 01-04) now have automated unit tests with mocked subprocess / env / report state — no real JAX/GPU/dreamerv3 required to run them.
- Three manual-only checks remain for end-to-end runs that need real dreamerv3 JAX stack + GPU; documented above.
- One pre-existing typo flagged in `src/surg_rl/dreamer/training.py:342` — `json.dump(..., indig=2)` should be `indent=2` (would raise `TypeError` on the final metrics save). Not fixed during audit per scope rules; recommend a separate fix commit.

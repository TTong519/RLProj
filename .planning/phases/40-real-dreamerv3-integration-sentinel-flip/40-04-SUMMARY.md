---
phase: 40-real-dreamerv3-integration-sentinel-flip
plan: 04
subsystem: infra
tags: [github-actions, ci, gpu, dreamerv3, jax, cuda, smoke-test]

# Dependency graph
requires:
  - phase: 40-real-dreamerv3-integration-sentinel-flip
    provides: "40-02 flipped E2E test (positive real-agent assertions) + 40-03 restart-then-continue resume test + 40-01 regression guard — the tests this CI job runs"
provides:
  - "dreamer-gpu GitHub Actions job (DMV3-10 closure signal on GPU merge-to-main)"
  - "workflow_dispatch trigger on the CI workflow (manual GPU smoke runs from the Actions tab)"
  - "push.tags ['v*'] trigger on the CI workflow (release-tag GPU smoke)"
affects: [milestone-audit, DMV3-10, v0.6.0-release, gpu-runner-ops-enablement]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Metered GPU-runner CI gating: per-PR CPU guards + merge-to-main/release-tag/manual-dispatch GPU smoke (D-02 spend control)"
    - "CUDA-jax install ordering: pip install jax[cuda12]~=0.4.20 BEFORE pip install -e .[dev,dreamer] so pip resolves jaxlib against the CUDA build (AI-SPEC Section 3)"

key-files:
  created: []
  modified:
    - ".github/workflows/ci.yml"

key-decisions:
  - "Used ubuntu-latest-4-core-gpu as the runs-on label (D-01 GitHub-hosted GPU runner). If the account's enabled GPU runner label differs, the label is the single line to update."
  - "Implemented the D-02 not-per-PR gate as a job-level if: condition (push to main || release tags || workflow_dispatch) rather than a separate workflow file — keeps the GPU job adjacent to the CPU matrix it complements."
  - "Set DREAMER_TOTAL_STEPS=1000 + DREAMER_EVAL_EVERY=500 as env on the pytest step (D-03 smoke budget) so tests that read the env get the budget without hardcoding it into CI."
  - "Added an on-failure checkpoint artifact upload (models/dreamerv3/) for post-mortem — optional per the plan, included for debuggability."

patterns-established:
  - "GPU smoke job pattern: CPU guards per-PR in the test matrix, GPU positive-assertion smoke on merge-to-main + manual dispatch + release tags (metered-spend CI design for GPU-gated RL tests)"
  - "CUDA-jax install-first ordering: install jax[cuda12]~=0.4.20 BEFORE the project extra so pip resolves jaxlib against the CUDA build, not the CPU default"

requirements-completed: [DMV3-10]

coverage:
  - id: D1
    description: "dreamer-gpu GitHub Actions job runs the real-agent DreamerV3 smoke (flipped E2E + resume + regression guard) on a GitHub-hosted GPU runner on merge-to-main + release tags + workflow_dispatch (NOT per-PR)"
    requirement: "DMV3-10"
    verification:
      - kind: other
        ref: "python -c \"import yaml; y=yaml.safe_load(open('.github/workflows/ci.yml')); assert 'dreamer-gpu' in y['jobs']; assert 'gpu' in y['jobs']['dreamer-gpu']['runs-on']; assert 'workflow_dispatch' in (y.get(True) or y.get('on',{}))\" → ok"
        status: pass
      - kind: other
        ref: "git diff --stat .github/workflows/ci.yml → 65 insertions(+), 0 deletions(-) (additive; existing test/docker-ci/k8s-e2e jobs unchanged)"
        status: pass
      - kind: unit
        ref: "tests/dreamer/test_dreamerv3_regression_guard.py#test_build_agent_does_not_return_none — CPU guard (source-inspection, no GPU)"
        status: pass
      - kind: unit
        ref: "tests/test_dreamer_subprocess.py#TestProcessIsolationImport::test_no_jax_or_dreamerv3_loaded_in_main_process — JAX-leak guard (no GPU)"
        status: pass
    human_judgment: true
    rationale: "The deliverable's core claim — that the dreamer-gpu job passes the flipped E2E + resume tests on a real GPU runner — CANNOT be proven in this execution environment (macOS, no NVIDIA GPU; the GPU-gated tests skipif locally per INV-8). The job + tests are added and structurally validated (YAML, grep, additive diff, CPU guards green); GPU GREEN is pending GitHub GPU runner enablement on the repo account (user_setup). The verifier/auditor must confirm the first GREEN run on a GPU runner to close DMV3-10 fully."

# Metrics
duration: 1min
completed: 2026-07-12
status: complete
---

# Phase 40 Plan 04: DreamerV3 GPU CI Smoke Job Summary

**Additive `dreamer-gpu` GitHub Actions job on `ubuntu-latest-4-core-gpu` firing on merge-to-main + release tags `v*` + `workflow_dispatch` (NOT per-PR), installing `jax[cuda12]~=0.4.20` before `.[dev,dreamer]` and running `pytest tests/dreamer/ -v -rs` with `total_steps=1000` structural-only smoke assertions**

## Performance

- **Duration:** 1 min
- **Started:** 2026-07-12T04:24:18Z
- **Completed:** 2026-07-12T04:25:36Z
- **Tasks:** 1
- **Files modified:** 1 (`.github/workflows/ci.yml`)

## Accomplishments

- Added a NEW `dreamer-gpu` job to `.github/workflows/ci.yml` (65 insertions, 0 deletions — purely additive; existing `test` / `docker-ci` / `k8s-e2e` jobs byte-unchanged)
- The job runs on `ubuntu-latest-4-core-gpu` (GitHub-hosted GPU Actions runner, D-01) with `timeout-minutes: 15` (smoke budget ~3-5 min + jax/dreamerv3 install + first-time JIT headroom)
- Trigger gate (D-02): job-level `if: (github.event_name == 'push' && github.ref == 'refs/heads/main') || startsWith(github.ref, 'refs/tags/') || github.event_name == 'workflow_dispatch'` — excludes pull_request events so per-PR spend stays zero; PR-time signal comes from the CPU-only regression guard + JAX-leak guard in the `test` matrix
- Extended the top-level `on:` block to add `workflow_dispatch:` + `push.tags: ['v*']` while keeping the existing `push.branches:[main]` + `pull_request.branches:[main]` triggers
- Install order (AI-SPEC Section 3): `pip install "jax[cuda12]~=0.4.20"` runs BEFORE `pip install -e ".[dev,dreamer]"` so pip resolves `jaxlib` against the CUDA build, not the CPU default; `dreamerv3~=1.5.0` + `optax>=0.1.7` come from the `[dreamer]` extra (D-04 pins UNCHANGED)
- Smoke step runs `pytest tests/dreamer/ -v -rs` with `DREAMER_TOTAL_STEPS=1000` + `DREAMER_EVAL_EVERY=500` env (D-03); the `-rs` flag surfaces skip reasons. Structural-only assertions (finite + non-explosive loss, `checkpoint.ckpt` exists, training completes, resume takes effect) live in the tests themselves (40-02/40-03) — NOT convergence thresholds (DMV3-10 exclusion)
- On-failure `actions/upload-artifact@v4` step uploads `models/dreamerv3/` for post-mortem (`if-no-files-found: ignore`)
- YAML validity confirmed via `python -c 'import yaml; yaml.safe_load(open(".github/workflows/ci.yml"))'` (parsed: jobs = test, docker-ci, k8s-e2e, dreamer-gpu)
- CPU guards unaffected: `PYTHONPATH=src pytest tests/dreamer/test_dreamerv3_regression_guard.py tests/test_dreamer_subprocess.py::TestProcessIsolationImport -v` → 4 passed in 0.24s (the CI job does not touch them)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add dreamer-gpu job to ci.yml** - `a8b5a38` (ci)

**Plan metadata:** uncommitted (left on disk — `commit_docs=false` in `.planning/config.json`; the orchestrator commits the tracking files after the test gate passes)

## Files Created/Modified

- `.github/workflows/ci.yml` — NEW `dreamer-gpu` job (GPU smoke, DMV3-10) + extended `on:` block (workflow_dispatch + push.tags `v*`). Additive only: 65 insertions, 0 deletions; existing test/docker-ci/k8s-e2e jobs unchanged.

## Decisions Made

- **Runner label `ubuntu-latest-4-core-gpu`** — used the D-01-recommended GitHub-hosted GPU Actions runner label. If the account's enabled GPU runner uses a different label, `runs-on` is the single line to update (documented in the summary for the ops/PR surface).
- **Job-level `if:` gate vs separate workflow file** — implemented the D-02 not-per-PR gate as a job-level `if:` condition inside the existing CI workflow, keeping the GPU job adjacent to the CPU matrix it complements and avoiding a second workflow file. The PR trigger stays in the `on:` block for the CPU `test` job; the `dreamer-gpu` job's `if:` excludes PRs.
- **`DREAMER_TOTAL_STEPS` + `DREAMER_EVAL_EVERY` env** — set as `env:` on the pytest step (D-03) so tests that read the env get the smoke budget without hardcoding it into CI. The 40-02/40-03 tests' own call args / run_dreamer_training defaults already target `total_steps=1000`; the env is belt-and-suspenders for any test that reads it.
- **On-failure artifact upload included** — the plan marked the `upload-artifact@v4` step for `models/dreamerv3/` as optional / Claude's discretion; included it for post-mortem debuggability (zero cost when the job passes; `if-no-files-found: ignore` keeps it clean on a no-checkpoint failure).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

**External service configuration required to close DMV3-10 fully.** The `dreamer-gpu` job + the GPU-gated tests are added and structurally validated, but the job CANNOT run GREEN until GitHub-hosted GPU Actions runners are enabled on the repo account. This is an ops enablement step (not a code change) and is recorded in the plan's `user_setup` frontmatter.

**Action required (GitHub organizational billing settings → Actions → GPU runners):**
- Enable GitHub-hosted GPU Actions runners (e.g. `ubuntu-latest-4-core-gpu`) on the repo account. If not enabled, the `dreamer-gpu` job will be queued/blocked on the first merge-to-main after this commit — document the gap in the PR per D-01 and mark DMV3-10 as pending GPU enablement (the job + tests are added; they run once the runner is enabled).
- Confirm the `dreamer-gpu` job's `workflow_dispatch` trigger is manually runnable from the Actions tab (GitHub repo → Actions → CI → Run workflow) after merge.

Until the GPU runner is enabled, DMV3-10's GREEN is pending. This is the same status Phase 30 carried — the tests + job exist, they just cannot execute without GPU infrastructure. The PR that lands this commit should call out the GPU-runner enablement step explicitly so it is not silently left 100%-skipped (per the plan's `100%-skipped audit failure` risk).

## Next Phase Readiness

- **Phase 40 complete** — this is the final plan (40-04) in phase 40. All four plans (40-01 regression guard, 40-02 flipped E2E test, 40-03 resume test, 40-04 GPU CI job) are done; summaries for all four are on disk.
- **DMV3-10 closure pending GPU GREEN** — the requirement's code/test/CI surface is complete; the only remaining step is the first GREEN run on a GPU runner (pending the user_setup enablement above). The milestone audit should treat DMV3-10 as "implemented, pending GPU runner enablement" rather than "100%-skipped" — the job exists and will run on the first merge-to-main after the runner is enabled.
- **No blockers for the next phase** — this plan modified only `.github/workflows/ci.yml` (additive) and touched no source/test files. Downstream phases inherit the corrected `dreamer_config` (task + checkpoint_dir threading) from 40-03's `fix(40-04-prep)` commit `81588c2`.

## Self-Check: PASSED

- `40-04-SUMMARY.md` exists on disk: FOUND
- commit `a8b5a38` exists in git log: FOUND
- `.github/workflows/ci.yml` still parses as valid YAML: YES
- `dreamer-gpu` job present in jobs map: YES (jobs = test, docker-ci, k8s-e2e, dreamer-gpu)
- Existing test / docker-ci / k8s-e2e jobs unchanged: YES (git diff = 65 insertions, 0 deletions)
- CPU guards green: 4 passed (regression guard + JAX-leak guards)

---
*Phase: 40-real-dreamerv3-integration-sentinel-flip*
*Completed: 2026-07-12*
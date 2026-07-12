# Phase 40: Real DreamerV3 Integration + Sentinel Flip - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-11
**Phase:** 40-real-dreamerv3-integration-sentinel-flip
**Areas discussed:** CI GPU host provisioning, Upstream API target + pin, Training loop approach, Checkpoint format + resume

---

## CI GPU host provisioning

### Q1 — How should the real-agent GPU smoke test be run in CI?

| Option | Description | Selected |
|--------|-------------|----------|
| GH Actions GPU runner | Add `dreamer-gpu` job using GitHub-hosted GPU runners; install jax[cuda12]+[dreamer]; metered but no infra maintenance | ✓ |
| Self-hosted GPU runner | Register your own GPU box as a self-hosted runner; no per-minute cost but you own driver/CUDA upkeep | |
| Docker/CUDA container job | Extend Dockerfile.cuda with [dreamer]+jax[cuda12]; most reproducible but adds Dockerfile maintenance + build time | |
| Test added, pending provisioning | Add job + skipif now but gate/disable it; DMV3-10 "pending GPU provisioning" — likely blocks v0.6.0 close | |

**User's choice:** GH Actions GPU runner
**Notes:** Cleanest path — no infra to maintain. If GitHub GPU runners aren't enabled on the repo account, that's an ops enablement step documented in the PR, not a code change.

### Q2 — When should the dreamer-gpu job fire?

| Option | Description | Selected |
|--------|-------------|----------|
| On every push/PR | Highest signal; metered GPU minutes add up fast | |
| On merge-to-main + manual | Once per merge + release tags + workflow_dispatch; PRs get CPU-only skipif path | ✓ |
| Nightly schedule + manual | Cheapest; a regression can land up to 24h before caught | |

**User's choice:** On merge-to-main + manual
**Notes:** Balances signal vs metered-GPU cost. PR-time regression signal comes from the GPU-less `_build_agent is None` regression-guard test.

### Q3 — Smoke-test step budget (total_steps)?

| Option | Description | Selected |
|--------|-------------|----------|
| 1000 steps | Same as Phase 30 D-STEPS-01; ~3-5 min; ~100 metric messages over the pipe | ✓ |
| 500 steps | Faster (~1-2 min); fewer pipe messages; below Phase 30's proven floor | |
| 2000 steps | Heavier (~10 min); 5x GPU cost; slower feedback | |

**User's choice:** 1000 steps
**Notes:** `eval_every=500` so the periodic-checkpoint branch fires (writes `checkpoint.ckpt` mid-run for the resume path).

---

## Upstream API target + pin

### Q4 — Which upstream API should the stubs target?

| Option | Description | Selected |
|--------|-------------|----------|
| PyPI 1.5.0 object API | Keep `dreamerv3~=1.5.0` pin; object-based Agent(4 args)+embodied.run.train+embodied.Checkpoint; matches what's installed; verified from PyPI tarball | ✓ |
| Current-repo factory API | Change pin to git install of danijar/dreamerv3 main; factory make_*+elements.*; matches STATE.md blocker naming; riskier, unpinned | |
| PyPI 1.5.0, factory as fallback | Lock 1.5.0 now; record factory API as fallback only if 1.5.0 lacks a needed capability | |

**User's choice:** PyPI 1.5.0 object API
**Notes:** Resolves the STATE.md blocker API-drift (the blocker named the factory API, but the pin installs the object API). No `elements` dep introduced. Also locks obs_type to `pixels`/`state` (research Q5 resolved) and `GymToEmbodiedWrapper` over `FromGym` (gym-vs-gymnasium).

---

## Training loop approach

### Q5 — How should _train_loop drive training?

| Option | Description | Selected |
|--------|-------------|----------|
| Manual Driver loop | _train_loop drives embodied.Driver + agent.train() batches; owns the JSON pipe; yields METRICS per batch; calls _save_checkpoint on CHECKPOINT messages | ✓ |
| embodied.run.train | Call run.train(agent, env, replay, logger, args); built-in ckpt/logging but conflicts with subprocess protocol's own CHECKPOINT/METRICS | |
| Manual loop, run.train as fallback | Lock manual Driver loop; document run.train as fallback if Driver API proves insufficient | |

**User's choice:** Manual Driver loop
**Notes:** Avoids double-checkpointing and protocol conflict; `_train_loop` owns the pipe. `embodied.run.train` is a documented fallback only, not the primary path.

---

## Checkpoint format + resume

### Q6 — Which checkpoint format + resume approach?

| Option | Description | Selected |
|--------|-------------|----------|
| Native .ckpt | embodied.Checkpoint native `checkpoint.ckpt`; cp.agent/cp.replay/cp.step + cp.load_or_save() attribute-registration resume; _find_latest_checkpoint globs *.ckpt | ✓ |
| Keep .pt naming | Configure embodied.Checkpoint to write checkpoint_*.pt/final.pt; fights upstream API (Checkpoint wants single .ckpt), likely needs wrapper/fork | |
| Native .ckpt + .pt compat shim | Native .ckpt + dual-glob shim recognizing stub-era .pt leftovers | |

**User's choice:** Native .ckpt
**Notes:** `.pt` naming was a stub-era placeholder; the Phase 30 E2E `.pt` assertions are being flipped anyway. No compat shim — clean retirement of the `.pt` glob.

---

## Claude's Discretion

- Exact `embodied.Driver`/`agent.train()` batch loop structure inside `_train_loop` (batch size, METRICS sampling).
- Exact `agent.policy` rollout structure inside `_evaluate`, provided return shape matches the existing EVAL handler.
- Exact `embodied.Checkpoint` attribute set registered for resume (agent+replay+step minimum; planner may add more if API requires).
- Whether `wrapper.py`'s `action_space` returns a dict `{"action": box, "reset": bool}` — planner verifies against installed Agent constructor.
- Exact `dreamer-gpu` job YAML (runner label, install steps, timeout), provided it uses a GitHub GPU runner, fires on merge-to-main + manual, runs total_steps=1000 with structural-only assertions.
- Exact structural-property assertions in the GPU smoke test (finite/non-increasing loss, checkpoint.ckpt exists) — NOT convergence thresholds.
- Exact source-inspection mechanism in `test_dreamerv3_regression_guard.py` (inspect.getsource + AST vs string match), provided it fails closed if `_build_agent` can return None.

## Deferred Ideas

- Extending `Dockerfile.cuda` to install `[dreamer]` + `jax[cuda12]` — fallback only if GitHub GPU runner path is blocked.
- `embodied.run.train` as the training driver — documented fallback (locked out as primary).
- Current-repo factory API — explicitly not adopted; revisit only if pin is bumped beyond `~=1.5.0`.
- Additional obs_type values beyond pixels/state — deferred until a new obs type is actually required.
- Convergence-threshold CI assertions (MSE<0.01) — excluded by DMV3-10; a separate convergence CI job is its own phase.
- Migrating the 7 existing `tests/test_dreamer_*.py` into `tests/dreamer/` — separate cleanup phase (carried from Phase 30 D-30-04).
- KubeRay / Dockerfile.ros2 amd64 — out of v0.6.0 scope.
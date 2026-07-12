# Phase 40: Real DreamerV3 Integration + Sentinel Flip - Context

**Gathered:** 2026-07-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the 5 stub functions (`_build_agent` / `_train_loop` / `_evaluate` /
`_save_checkpoint` / `_load_checkpoint`) in `src/surg_rl/dreamer/subprocess.py`
with real DreamerV3 training implementations, add per-task/obs-type checkpoint
persistence + resume across subprocess restarts, **invert** the Phase 30
sentinel E2E test from a negative stub assertion to a positive real-agent
assertion (plus a new `_build_agent is None` regression guard), and stand up a
CI GPU smoke test. All changes live inside the child-process functions; the
subprocess protocol is unchanged. GPU-gated; the LAST phase in v0.6.0.

**What this phase delivers:**
1. The 5 stubs become real implementations against the **PyPI 1.5.0 object-based
   API** (`dreamerv3.Agent(obs_space, act_space, step, config)` +
   `embodied.run.train` + `embodied.Checkpoint`). The JSON-over-stdio subprocess
   protocol, `_JsonStdout` wrapper, `DreamerSubprocess` parent class,
   `_subprocess_main`, and `_run_subprocess_loop` message dispatch are
   **unchanged** (SC#1).
2. `_train_loop` drives a **manual `embodied.Driver` + `agent.train()` batch
   loop** — it owns the JSON pipe: yields `METRICS` per batch and calls
   `_save_checkpoint` on the protocol's `CHECKPOINT` messages. No
   double-checkpointing via `embodied.run.train`'s internal cadence.
3. Checkpoints persist per task/obs-type under `models/dreamerv3/{task}_{obs_type}/`
   in `embodied.Checkpoint`'s native `checkpoint.ckpt` binary format, using the
   attribute-registration resume pattern (`cp.agent=agent; cp.replay=replay;
   cp.step=step; cp.load_or_save()`). `_find_latest_checkpoint` is updated to
   glob `*.ckpt` (the stub-era `checkpoint_*.pt` / `final.pt` glob is retired).
   Resume is verified by a restart-then-continue test (SC#2 / DMV3-08).
4. The Phase 30 E2E test is **inverted, not deleted**: its two
   `pytest.raises(RuntimeError, match="Agent not configured")` assertions
   become positive real-agent-completion assertions; a NEW source-inspection
   guard (`test_dreamerv3_regression_guard.py`) fails if `_build_agent` ever
   returns `None` again (SC#3 / DMV3-09). Runs without a GPU.
5. A `dreamer-gpu` CI job on a **GitHub Actions GPU runner** fires on
   **merge-to-main + manual `workflow_dispatch`** (not per-PR), installs
   `jax[cuda12]~=0.4.20` + `[dreamer]`, runs `total_steps=1000`, and asserts
   **structural-only** properties (finite and non-increasing loss, checkpoint
   file exists) — NOT the v0.4.0 spike's converged `MSE<0.01`. macOS local skips
   cleanly per INV-8 (SC#4 / DMV3-10).
6. JAX never leaks into the parent: all `import jax` / `import dreamerv3` stay
   inside the stub function bodies (child process only); the `LazyImport` guard
   in `dreamer/__init__.py` is unchanged. The embodied logger writes to **stderr**
   (not stdout — stdout stays clean for the JSON pipe) (SC#5).

**What this phase does NOT deliver:**
- Convergence-threshold assertions (`MSE<0.01`) — explicitly excluded by DMV3-10
  (smoke-vs-convergence split).
- A change to the `dreamerv3~=1.5.0` pin or a switch to the danijar/dreamerv3
  current-repo factory API — the PyPI 1.5.0 object API is the target.
- Any change to `DreamerConfig` schema (`scene_definition/schema.py`) — additive
  phase; `obs_type ∈ {pixels, state}` is unchanged.
- The DMV3-01 spike (`dreamer/spike.py`) — out of scope, not modified.
- Difficulty-chain work (36/37), 3D fluids (38), K8s PVC e2e / organ-mesh ADR (39)
  — already landed.

</domain>

<decisions>
## Implementation Decisions

### CI GPU host provisioning
- **D-01:** Run the real-agent smoke test on a **GitHub-hosted GPU Actions
  runner** (e.g. `ubuntu-latest-4-core-gpu`). Add a `dreamer-gpu` job to
  `.github/workflows/ci.yml` that installs `jax[cuda12]~=0.4.20` + the
  `[dreamer]` extra + `optax>=0.1.7`, then runs the smoke test. No self-hosted
  runner, no Docker/CUDA container job — keep infra maintenance on GitHub.
  (If GitHub GPU runners are not enabled on the repo account, this is an ops
  enablement step, not a code change — document in the PR.)
- **D-02:** The `dreamer-gpu` job fires on **merge-to-main + release tags +
  manual `workflow_dispatch`** — NOT on every push/PR. PRs get only the
  CPU-only skipif path; the real-agent smoke runs once per merge to control
  metered GPU-runner spend. The regression-guard test (D-09, no GPU) runs in
  the normal CPU matrix on every PR.
- **D-03:** Smoke-test budget is `total_steps=1000` (same as Phase 30
  D-STEPS-01, ~3-5 min on a GPU runner; ~100 metric messages round-trip the
  JSON pipe). `eval_every=500` so the periodic-checkpoint branch fires.

### Upstream API target + pin
- **D-04:** Target the **PyPI 1.5.0 object-based API** — keep the
  `dreamerv3~=1.5.0` pin in `pyproject.toml` unchanged. Stubs are written
  against `dreamerv3.Agent(obs_space, act_space, step, config)` (4 args),
  `embodied.run.train(agent, env, replay, logger, args)`, and
  `embodied.Checkpoint` (attribute-registration pattern). Do NOT use the
  current-repo factory API (`make_agent` / `make_replay` / `make_stream` /
  `make_logger` + `elements.*`) — that describes `danijar/dreamerv3` main, not
  what `pip install '.[dreamer]'` installs. This resolves the STATE.md blocker
  API-drift. No `elements` dependency is introduced.
- **D-05:** Use the project's existing **`GymToEmbodiedWrapper`**
  (`src/surg_rl/dreamer/wrapper.py`) — NOT `embodied.wrappers.FromGym`
  (dreamerv3's `FromGym` pins `gym==0.19.0`, which conflicts with the project's
  `gymnasium>=0.29.0`). The wrapper already produces the dict keys
  (`image`/`state` + `is_first`/`is_last`/`is_terminal`) dreamerv3 1.5.0 expects.
- **D-06:** `obs_type` stays `Literal["pixels", "state"]` — no new obs types.
  No `encoder.mlp_keys`/`cnn_keys` configuration needed beyond what the wrapper
  already emits. (Resolves research Q5.)

### Training loop approach
- **D-07:** `_train_loop` drives a **manual `embodied.Driver` +
  `agent.train()` batch loop**. It owns the JSON pipe directly: yields
  `METRICS` messages per training batch and calls `_save_checkpoint` when the
  parent sends `CHECKPOINT` messages. No `embodied.run.train()` call — its
  internal checkpointing + logging would double-checkpoint and conflict with
  the subprocess protocol's own `CHECKPOINT`/`METRICS` message types.
  (`embodied.run.train` is the documented fallback only if the Driver API
  proves insufficient during implementation — but start manual.)
- **D-08:** `_evaluate` implements real `agent.policy` rollouts over the
  wrapped env; its return shape matches what `_run_subprocess_loop`'s `EVAL`
  handler already expects (do not change the handler).

### Checkpoint format + resume
- **D-09:** Use `embodied.Checkpoint` with its **native `checkpoint.ckpt`
  binary format** (pickle of numpy arrays). The attribute-registration resume
  pattern is: `cp = embodied.Checkpoint(path); cp.agent = agent; cp.replay =
  replay; cp.step = step; cp.load_or_save()` — `load_or_save()` resumes if the
  path exists, otherwise initializes. Update `_find_latest_checkpoint`
  (`training.py:191-197`) to glob `*.ckpt`; retire the stub-era
  `checkpoint_*.pt` / `final.pt` glob and naming. The `.pt` naming was a
  stub-era placeholder; the Phase 30 E2E's `.pt` assertions are being flipped
  anyway (D-10), so no compatibility shim is needed. No `.pt` compat path.
- **D-10 (sentinel flip):** In `tests/dreamer/test_dreamerv3_subprocess_e2e.py`,
  the two `pytest.raises(RuntimeError, match="Agent not configured")`
  assertions (lines ~72, ~91) and the `final.pt NOT written` negative
  assertion (lines ~99-101) become **positive** real-agent-completion
  assertions (agent ran, `checkpoint.ckpt` exists, no `RuntimeError`). The
  module-level `pytestmark = pytest.mark.skipif(...)` (line 42) stays as the
  GPU + dreamerv3 + jax gate (INV-8 macOS skip). Add a NEW
  `tests/dreamer/test_dreamerv3_regression_guard.py` that statically inspects
  `_build_agent` source and **fails if it can return `None`** — runs without a
  GPU, in the normal CPU matrix on every PR. This is the "guard that fails if
  `_build_agent` ever returns `None` again" locked by the v0.6.0 research.

### Claude's Discretion
- Exact `embodied.Driver` / `agent.train()` batch loop structure inside
  `_train_loop` (batch size, how `METRICS` are sampled off the agent), provided
  it owns the JSON pipe and yields `METRICS` per batch (D-07).
- Exact `agent.policy` rollout structure inside `_evaluate` (D-08), provided
  its return shape matches the existing `EVAL` handler.
- Exact `embodied.Checkpoint` attribute set registered for resume (D-09) —
  `agent` + `replay` + `step` is the minimum; the planner may add more (e.g.
  `logger` state) if the installed API requires it.
- Whether `wrapper.py`'s `action_space` property returns a dict
  `{"action": box, "reset": bool}` (research A4) — planner verifies against
  the installed `Agent` constructor's expected act_space shape.
- Exact `dreamer-gpu` job YAML (runner label, install steps, timeout-minutes),
  provided it uses a GitHub GPU runner, fires on merge-to-main + manual, and
  runs `total_steps=1000` with structural-only assertions (D-01/02/03).
- Exact structural-property assertions in the GPU smoke test (finite loss,
  non-increasing-ish loss, `checkpoint.ckpt` exists), provided they are NOT
  convergence thresholds (DMV3-10 exclusion).
- Exact source-inspection mechanism in `test_dreamerv3_regression_guard.py`
  (`inspect.getsource` + AST `Return(None)` check, or string match on
  `return None`), provided it fails closed if `_build_agent` can return `None`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase research (PRIMARY — read first)
- `.planning/phases/40-real-dreamerv3-integration-sentinel-flip/40-RESEARCH.md`
  — HIGH-confidence research: the 5-stub inventory, the PyPI 1.5.0 vs
  current-repo API drift (the critical Q1 finding), `embodied.run.train` /
  `Agent` / `Checkpoint` / `FromGym` signatures verified from the PyPI
  tarball, checkpoint-resume design, sentinel-inversion design, CI GPU smoke
  design, risks/pitfalls. This CONTEXT.md locks the 6 Open Questions; the
  research contains the implementation detail (signatures, line numbers,
  patterns) the planner needs.

### Requirements & roadmap
- `.planning/ROADMAP.md` § "Phase 40: Real DreamerV3 Integration + Sentinel
  Flip" (lines ~166-189) — goal, 5 success criteria, requirements DMV3-07/08/09/10,
  "GPU-gated; runs LAST" ordering note.
- `.planning/REQUIREMENTS.md` — DMV3-07, DMV3-08, DMV3-09, DMV3-10 acceptance
  criteria.
- `.planning/STATE.md` § Blockers/Concerns — the Phase 40 blocker naming the
  factory-API drift (RESOLVED by D-04 — target PyPI 1.5.0 object API, not the
  factory API named in the blocker). § Decisions — the `[v0.6.0 research]`
  locked decisions (sentinel flip not delete, logger→stderr, JAX isolation,
  structural-only smoke, XLA_PYTHON_CLIENT_MEM_FRACTION=0.4).
- `.planning/PROJECT.md` — v0.6.0 milestone scope; Key Architecture Decisions
  on process isolation (LOCKED — do not re-litigate).

### Source artifacts (the surfaces this phase modifies)
- `src/surg_rl/dreamer/subprocess.py:125-129` — `_build_agent` stub (→ real
  `Agent(obs_space, act_space, step, config)`).
- `src/surg_rl/dreamer/subprocess.py:132-134` — `_train_loop` stub (→ manual
  Driver loop, D-07).
- `src/surg_rl/dreamer/subprocess.py:137-139` — `_evaluate` stub (→
  `agent.policy` rollouts, D-08).
- `src/surg_rl/dreamer/subprocess.py:142-144` — `_save_checkpoint` stub (→
  `cp.save()`).
- `src/surg_rl/dreamer/subprocess.py:147-149` — `_load_checkpoint` stub (→
  `cp.load()` / `load_or_save()`, D-09).
- `src/surg_rl/dreamer/subprocess.py:88,98` — the two `"Agent not configured"`
  ERROR emissions (the stub reality the sentinel flip targets).
- `src/surg_rl/dreamer/subprocess.py:29-53` — `_JsonStdout` wrapper (UNCHANGED,
  SC#1).
- `src/surg_rl/dreamer/subprocess.py:57-122` — JSON-over-stdio protocol
  (UNCHANGED, SC#1).
- `src/surg_rl/dreamer/subprocess.py:19-20` — `XLA_PYTHON_CLIENT_MEM_FRACTION=0.4`
  isolation (UNCHANGED, SC#1).
- `src/surg_rl/dreamer/training.py:191-197` — `_find_latest_checkpoint` (glob
  → `*.ckpt`, D-09).
- `src/surg_rl/dreamer/training.py:188,315,333` — stub-era `checkpoint_*.pt` /
  `final.pt` writes (retired by D-09).
- `src/surg_rl/dreamer/wrapper.py` — `GymToEmbodiedWrapper` (reused, D-05;
  `action_space` property possibly updated per Claude's discretion).
- `src/surg_rl/dreamer/__init__.py` — `LazyImport` guard (UNCHANGED, SC#5).
- `pyproject.toml:137-141` — `jax~=0.4.20`, `optax>=0.1.7`, `dreamerv3~=1.5.0`
  pins (UNCHANGED, D-04).

### Tests (modified/new)
- `tests/dreamer/test_dreamerv3_subprocess_e2e.py` — the Phase 30 sentinel test
  to flip negative→positive (D-10). Lines ~42 (skipif), ~72, ~91 (RuntimeError
  assertions), ~99-101 (final.pt NOT-written negative assertion).
- `tests/dreamer/test_dreamerv3_regression_guard.py` — NEW `_build_agent is
  None` source-inspection guard, no GPU (D-10).
- `tests/dreamer/test_dreamerv3_checkpoint_resume.py` — NEW restart-then-
  continue resume test, GPU-gated (DMV3-08).
- `tests/test_dreamer_subprocess.py` — add a JAX-import-leak guard test
  (parent-package import never imports jax/dreamerv3, SC#5).

### CI config
- `.github/workflows/ci.yml` — add the `dreamer-gpu` job (D-01/02/03). Current
  config has no GPU/dreamer job.
- `Dockerfile.cuda` — currently installs `[dev,tracking]` but NOT `[dreamer]`;
  no change required under D-01 (GitHub GPU runner, not Docker-based), but the
  planner may add `[dreamer]` + `jax[cuda12]` if a container build is needed.

### Prior phase context (patterns to mirror)
- `.planning/phases/30-dreamerv3-real-subprocess-e2e-test/30-CONTEXT.md` — the
  sentinel test's design (D-SKIP-01 skipif union, D-COLOR-01, D-CKPT-01/02), the
  `tests/dreamer/` directory + module-level `pytestmark` pattern, the
  `_find_latest_checkpoint` auto-discovery contract this phase updates.
- `.planning/phases/30-dreamerv3-real-subprocess-e2e-test/30-VERIFICATION.md` —
  the sentinel's stub-reality revision history (what the flip inverts).
- `.planning/phases/24-dreamerv3-world-models/24-CONTEXT.md` — process-isolation
  design (D-04/D-05/D-06) + feasibility spike; the subprocess protocol this
  phase preserves.

### Architecture & conventions
- `.planning/codebase/ARCHITECTURE.md` — subprocess / module layout.
- `.planning/codebase/TESTING.md` — skipif / integration-marker conventions.
- `.planning/codebase/CONVENTIONS.md` — lazy imports, pytest patterns.

### External references (PyPI 1.5.0 API)
- `dreamerv3-1.5.0` PyPI tarball (downloaded + inspected in research) —
  `Agent(obs_space, act_space, step, config)`, `embodied.run.train(agent, env,
  replay, logger, args)`, `embodied.Checkpoint` attribute-registration pattern.
  The research file captures the verified signatures; the planner/executor
  re-verifies against the installed package.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`GymToEmbodiedWrapper`** (`src/surg_rl/dreamer/wrapper.py`) — already
  produces the dict keys (`image`/`state` + `is_first`/`is_last`/`is_terminal`)
  dreamerv3 1.5.0 expects; reused so the stubs don't have to wrap the env
  themselves (D-05). Avoids the `FromGym` gym-vs-gymnasium conflict.
- **`DreamerSubprocess`** parent class + `_run_subprocess_loop` message
  dispatch (`subprocess.py:57-122`) — the protocol handlers (`TRAIN`/`EVAL`/
  `CHECKPOINT`/`METRICS`) are unchanged; the stubs are *called by* these
  handlers, so replacing the stubs is the entire production change surface.
- **`_JsonStdout`** (`subprocess.py:29-53`) — the pipe wrapper; unchanged, so
  any `print(..., flush=True)` inside `_train_loop`'s real implementation rides
  the same JSON pipe the stubs' ERROR messages used.
- **`_find_latest_checkpoint`** (`training.py:191-197`) — the auto-discovery
  helper; updated to glob `*.ckpt` (D-09), exercised by the DMV3-08 resume test.
- **`LazyImport` guard** (`dreamer/__init__.py`) — keeps `import jax` /
  `import dreamerv3` out of the parent-package import path (SC#5); the new
  `test_dreamer_subprocess.py` import-leak guard pins this.

### Established Patterns
- **Module-level `pytestmark = pytest.mark.skipif`** on the union of GPU +
  `dreamerv3` + `jax` (Phase 30 D-SKIP-01) — the sentinel + resume tests stay
  gated by this; the regression-guard test does NOT need it (no GPU).
- **`importlib.util.find_spec(...) is None` skipif pattern**
  (`tests/test_rllib_train.py:62-94`) — reused for the dreamer/jax gating.
- **Structural-only CI smoke assertions** (v0.6.0 research) — finite +
  non-increasing loss, checkpoint file exists; NOT convergence thresholds.
- **All JAX/dreamerv3 imports inside stub function bodies** (child process
  only) — the JAX-isolation discipline; verified by the new import-leak guard.

### Integration Points
1. `_run_subprocess_loop` `TRAIN` handler → `_build_agent` → `_train_loop`
   (real Agent + manual Driver loop; pipe METRICS per batch).
2. `_run_subprocess_loop` `CHECKPOINT` handler → `_save_checkpoint`
   (`cp.save()` to `models/dreamerv3/{task}_{obs_type}/checkpoint.ckpt`).
3. `_run_subprocess_loop` `EVAL` handler → `_evaluate` (`agent.policy`
   rollouts; return shape unchanged).
4. Subprocess restart → `_load_checkpoint` (`cp.load_or_save()` resumes from
   `*.ckpt` via `_find_latest_checkpoint`) — exercised by the restart-then-
   continue test.
5. `ci.yml` new `dreamer-gpu` job → runs `tests/dreamer/test_dreamerv3_subprocess_e2e.py`
   (flipped positive) + `test_dreamerv3_checkpoint_resume.py` on a GPU runner.

### Common Landmines
- **API drift (HIGH)** — the STATE.md blocker names the factory API; the pin
  installs the object API. Stubs MUST target the object API (D-04). Re-verify
  signatures against the installed package, not the GitHub main branch.
- **JAX leak (MEDIUM)** — any `import jax` / `import dreamerv3` at module top
  in `subprocess.py` breaks SC#5; keep imports inside stub function bodies +
  the import-leak guard test.
- **Logger→stdout (MEDIUM)** — the embodied logger defaults to stdout and
  would corrupt the JSON pipe; redirect to stderr (locked decision).
- **gym vs gymnasium (MEDIUM)** — do not use `embodied.wrappers.FromGym`
  (pins `gym==0.19.0`); use `GymToEmbodiedWrapper` (D-05).
- **Double-checkpointing (LOW-MEDIUM)** — `embodied.run.train`'s internal
  ckpt cadence would conflict with the protocol's `CHECKPOINT` messages; the
  manual Driver loop avoids this (D-07).
- **100%-skipped audit failure (MEDIUM-HIGH)** — if the `dreamer-gpu` job
  never runs (GPU runner not enabled), DMV3-10 appears untested. D-01/D-02
  address the job; if the runner isn't enabled on the account, document it as
  an ops enablement step in the PR (do NOT silently leave it 100%-skipped).

</code_context>

<specifics>
## Specific Ideas

- The user explicitly chose a **GitHub-hosted GPU Actions runner** over a
  self-hosted runner or Docker/CUDA container — downstream agents should not
  introduce self-hosted-runner provisioning or extend `Dockerfile.cuda` unless
  the GitHub GPU runner is unavailable on the account (in which case: document,
  don't silently switch).
- The user explicitly chose **merge-to-main + manual dispatch** (not per-PR)
  for the GPU job — the PR-time signal comes from the GPU-less
  regression-guard test; the real-agent smoke runs once per merge.
- The user explicitly chose the **manual Driver loop** over
  `embodied.run.train` — `_train_loop` owns the JSON pipe; `embodied.run.train`
  is only a documented fallback, not the primary path.
- The user explicitly chose **native `.ckpt` with no `.pt` compat shim** —
  the `.pt` naming is a stub-era placeholder and is retired cleanly; do not
  add a dual-glob compatibility path.
- The sentinel flip is **inversion, not deletion** — the Phase 30 test stays
  in place with its skipif; its assertions change sign. The new
  `_build_agent is None` regression guard is the structural mechanism that
  prevents stub regression (not just an acknowledgment).

</specifics>

<deferred>
## Deferred Ideas

- **Extending `Dockerfile.cuda` to install `[dreamer]` + `jax[cuda12]`** — not
  needed under D-01 (GitHub GPU runner), but kept as a fallback if a
  container-based GPU build is later required. Belongs to a future ops/CI
  phase if the GitHub GPU runner path is blocked.
- **`embodied.run.train` as the training driver** — locked out as the primary
  path (D-07) but recorded as the documented fallback if the manual Driver
  loop proves insufficient during implementation.
- **Current-repo factory API (`make_agent`/`make_replay`/`make_stream`/
  `make_logger` + `elements.*`)** — explicitly NOT adopted (D-04); revisit
  only if the pin is ever bumped beyond `~=1.5.0`.
- **Additional `obs_type` values beyond `pixels`/`state`** — none needed;
  `encoder.mlp_keys`/`cnn_keys` configuration is deferred until a new obs type
  is actually required.
- **Convergence-threshold CI assertions (`MSE<0.01`)** — explicitly excluded
  by DMV3-10 (smoke-vs-convergence split); a separate convergence CI job, if
  ever wanted, is its own phase.
- **Migrating the 7 existing `tests/test_dreamer_*.py` files into
  `tests/dreamer/`** — separate cleanup phase (carried from Phase 30
  D-30-04); not inflated into this phase.
- **KubeRay / `Dockerfile.ros2` amd64** — out of v0.6.0 scope (closed-partial
  in Phase 39); not a Phase 40 concern.

</deferred>

---

*Phase: 40-real-dreamerv3-integration-sentinel-flip*
*Context gathered: 2026-07-11 via v0.6.0 research (STATE.md locked decisions) + 40-RESEARCH.md (HIGH confidence, PyPI tarball-verified) + 30-CONTEXT.md sentinel design + codebase scout + user discussion (4 gray areas: CI GPU host, API target, training loop, checkpoint format)*
---
gsd_context_version: 1.0
phase: 35
phase_name: advanced-tech-debt
gathered: 2026-06-21
status: Ready for planning
source: Roadmap + prior phase artifacts
---

# Phase 35: Advanced Tech Debt - Context

**Read first:** `.planning/phases/35-advanced-tech-debt/35-CONTEXT.md` must be read by every plan agent.

## Phase Boundary

This phase closes four medium-priority deferred items carried forward from the
v0.4.2 closeout and one documentation update. It can run in parallel with Phases
32-34 because it only needs the Phase 31 clean baseline.

**What this phase delivers:**
1. An end-to-end integration test that loads the HARD-fixture suturing scene,
   constructs a `SurgicalEnv`, and runs `reset()` + `step()` without exception
   (`tests/integration/test_suturing_hard_env_construction.py`).
2. Normalization of `CurriculumStageConfig.difficulty` to a scalar `float` at
   env-construction boundary, plus extraction of reward setup into
   `SurgicalEnv._setup_rewards()`.
3. A K8s PVC end-to-end stub test marked with `[k8s]` that detects a local
   `kind` cluster and skips otherwise (`tests/k8s/test_pvc_e2e.py`).
4. A research document surveying organ-mesh licensing candidates and deferring
   the asset decision to v0.6.0 (`docs/research/organ-mesh-licensing.md`).
5. `STATE.md` updated to mark Phase 29 code-review findings WR-02 and WR-03 as
   Closed in v0.5.0.

**What this phase does NOT deliver:**
- New surgical tasks, RL algorithms, or GUI features.
- Real human-organ mesh assets (only the licensing research spike).
- A fully functional K8s PVC e2e test on CI (the test body is intentionally
  stubbed with a TODO/rationale).

## Implementation Decisions

### Locked decisions (from ROADMAP.md / prior phases)
- The HARD-fixture integration test must use
  `tests/fixtures/scenes/suturing_difficulty_hard.json` and assert no exception
  during `SurgicalEnv` construction, `reset()`, and at least one `step()`.
- `CurriculumStageConfig.difficulty` is widened to `float | DifficultyLevel`; the
  env-construction boundary must resolve either arm to a scalar `float` before
  it reaches reward builders.
- The K8s PVC e2e test must be marked `@pytest.mark.k8s` and skip when no
  local `kind` cluster is available, with a TODO body deferred to v0.6.0.
- The organ-mesh licensing doc must cover at least surgtoolloc, MakeHuman, and
  BodyParts3D candidates with their license constraints.

### the agent's Discretion
- Exact test class/function naming and skip condition wording, provided the
  marker and semantics are preserved.
- Whether to normalize `CurriculumStageConfig.difficulty` via a dataclass
  `__post_init__`, a `current_difficulty` property fix, or inside the new
  `SurgicalEnv._setup_rewards()` helper. The recommended approach is a
  combination: keep `current_difficulty` honest and make `_setup_rewards()` the
  single place where reward difficulty is resolved.
- Exact structure of the research doc beyond the three mandatory candidates.

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project context
- `.planning/PROJECT.md` - v0.5.0 milestone overview and deferred items.
- `.planning/ROADMAP.md` - Phase 35 entry, success criteria, dependencies.
- `.planning/REQUIREMENTS.md` - DEBT-06 acceptance criteria.
- `.planning/STATE.md` - deferred WR-02 / WR-03 items to be closed.

### Prior phase artifacts
- `.planning/phases/29-task-02-3-difficulty-levels/29-REVIEW.md` - WR-02 / WR-03
  findings and recommended fixes.
- `.planning/phases/31-tech-debt-foundation/31-01-PLAN.md` - clean baseline
  context; ruff must stay green.

### Code references
- `tests/fixtures/scenes/suturing_difficulty_hard.json` - HARD fixture target.
- `src/surg_rl/rl/environment.py` - env construction, reward setup, controller
  wiring.
- `src/surg_rl/rl/task_reward_router.py` - already normalizes
  `DifficultyLevel` to `float`; the gap is the curriculum path.
- `src/surg_rl/dynamics/curriculum.py` - `CurriculumStageConfig` and
  `CurriculumScheduler.current_difficulty`.
- `src/surg_rl/rl/difficulty.py` - `DifficultyLevel` float-mixin enum.
- `tests/test_kubernetes_manifests.py` - existing K8s manifest tests for
  structure/style reference.
- `pytest.ini` - marker registry (needs the new `[k8s]` marker).

### Documentation references
- `AGENTS.md` - simulator backend quirks, PYTHONPATH=src, Pydantic v2 quirks.

## Specific Ideas

- The HARD-fixture test can be guarded by a MuJoCo-importability / platform
  check and marked `@pytest.mark.integration` + `@pytest.mark.slow` because it
  constructs a real simulator. Use a `try/finally` to ensure `env.close()`.
- The `_setup_rewards()` refactor should move the reward-building block out of
  `SurgicalEnv.__init__` into a private method, preserving the existing
  fallback chain: `task.difficulty_level` -> `config.difficulty` -> default 0.5.
  Add a branch that, if curriculum is configured, resolves
  `controller._curriculum.current_difficulty` and normalizes it before passing
  to `TaskRewardRouter`.
- `CurriculumScheduler.current_difficulty` should be fixed to always return a
  `float` by handling the `DifficultyLevel` arm explicitly, closing the type
  lie noted in WR-03.

## Deferred Ideas

- Full K8s PVC end-to-end validation (create PVC, write checkpoint, read back,
  delete) - deferred to v0.6.0 per roadmap.
- Procurement or procedural generation of real human organ meshes - deferred
  to v0.6.0 pending licensing research outcome.

---

*Phase: 35-advanced-tech-debt*  
*Context gathered: 2026-06-21 via roadmap + prior phase artifacts*

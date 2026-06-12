# Phase 29: TASK-02 3-Difficulty-Levels Completion — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-11
**Phase:** 29-TASK-02 3-Difficulty-Levels Completion
**Areas discussed:** EASY/HARD direction semantics, Router→reward plumbing path

---

## EASY/HARD direction semantics in the test

**Context:** ROADMAP.md §127 flags that some PARAM_BOUNDS (lo>hi vs lo<hi) flip the loose/strict direction between 0.0 and 1.0. Audit of all 6 PARAM_BOUNDS dictionaries confirmed: all are consistent (0.0 = loose, 1.0 = strict). The "inverted" PARAM_BOUNDS (tissue_stiffness, action_noise, object_mass with lo<hi) physically mean stiffer/noisier/heavier = harder.

| Option | Description | Selected |
|--------|-------------|----------|
| Inequality only | Assert "at least one of the 4 named parameter families strictly differs between EASY and HARD" — quick to write, allows flexibility. Risk: a future inverted bound could pass even if EASY=HARD=same difficulty direction. | |
| Per-family direction assertion | Assert "for at least one of 4 families, the value moves toward stricter at HARD vs EASY" — e.g., for tolerance-like params (down) HARD < EASY, for tissue_stiffness-like (up) HARD > EASY. Tighter test, still allows per-task variation. | ✓ |
| Magnitude + direction | Assert "at least one of the 4 families has a >=2x ratio change between EASY and HARD" — guarantees meaningful magnitude, not just direction. Most rigorous but most brittle. | |

**User's choice:** Per-family direction assertion (Recommended)
**Notes:** User confirmed after I audited all 6 PARAM_BOUNDS. Implementation must NOT flip any bounds — the existing direction is the design (D-DIR-02). Locked as D-DIR-01 in CONTEXT.md.

---

## Router→reward plumbing path

**Context:** `TaskRewardRouter._difficulty` is currently set in `__init__` (line 52) but never used in `build()`. Today, `TaskRewardRouter(difficulty=0.0).build(task_type)` and `TaskRewardRouter(difficulty=1.0).build(task_type)` produce identical reward instances. Success criterion #4 only requires the float/enum paths to produce equivalent instances — which they do today, since difficulty is ignored. Going deeper mutates reward internals.

| Option | Description | Selected |
|--------|-------------|----------|
| Signature + method only | Add DifficultyLevel enum, get_params_for_difficulty() on all 6 classes, and accept DifficultyLevel in TaskRewardRouter signature. Router stores self._difficulty but doesn't yet feed it into the reward (Phase 21 contract; deferred). | |
| Also wire apply_difficulty (larger scope) | Above + add an apply_difficulty(level) method to BaseRewardFunction. Each subclass implements a per-task field mapping. Router calls apply_difficulty() after construction. | ✓ |
| Enum + method, ignore difficulty in router | Add the enum + get_params_for_difficulty, but the router still uses **reward_kwargs passthrough** only. Difficulty is a separate state, not consumed. | |

**User's choice:** Also wire apply_difficulty (larger scope)
**Notes:** User opted for the fully-wired version. The "fully wired" makes the existing `self._difficulty` field load-bearing. Per-subclass field mapping can be partial (D-PLUMB-02). Per-subclass `apply_difficulty` may need to add new ctor params for previously-unmapped `PARAM_BOUNDS` keys (D-PLUMB-03). Locked as D-PLUMB-01..06 in CONTEXT.md.

---

## Other areas considered but not deep-dived (left to OpenCode's discretion)

| Area | Reason for deferral |
|------|---------------------|
| `DifficultyLevel` enum module location (`rl/difficulty.py` vs `task_reward_router.py` vs `rewards.py` vs `dynamics/curriculum.py`) | Implementation detail; success criterion #1 only requires `from surg_rl.rl import DifficultyLevel`. Documented circular-import risk in CONTEXT.md "Specific Ideas" → "D-SCHEMA-01 minimal addition". |
| Integration test scope (D-TEST-05) | Match Phase 27 precedent (Pydantic-validate only) was the minimum. Deeper variants (env.reset, curriculum activation) are allowed but not required. |
| Test fixture granularity (one class per task type vs one parametrized class for all 6) | AGENTS.md prefers feature-specific files; both fit in `tests/test_difficulty_levels.py`. |
| `apply_difficulty` placement (on `BaseRewardFunction` with no-op default vs duck-typed on subclasses) | Either is acceptable; base-class approach is more discoverable. |
| Per-subclass field mapping exactness (1 mapped field minimum vs all keys mapped) | Partial mapping is acceptable per D-PLUMB-02; minimum is at least one mapped field per subclass. |
| Whether to add new ctor params for previously-unmapped `PARAM_BOUNDS` keys (D-PLUMB-03) | OpenCode's call — add if reachable from `compute()`/`check_success`/`check_failure`, omit if purely descriptive. |

---

## OpenCode's Discretion

Documented in CONTEXT.md § "OpenCode's Discretion":
- Enum module location (with circular-import resolution options)
- `apply_difficulty` placement (base-class vs duck-typed)
- Per-subclass field mapping exactness
- New ctor param additions for unmapped PARAM_BOUNDS keys
- Test fixture granularity
- Integration test depth

---

## Deferred Ideas

Documented in CONTEXT.md § "Deferred Ideas" (out of phase scope, all from D-29-03 / D-29-05 / scope_guardrail):
- Per-level scene override blocks (`difficulty_levels: list[3]`) — v0.5.0+
- Discrete level progression in `CurriculumScheduler` — v0.5.0+
- `DifficultyLevelConfig` Pydantic model — v0.5.0+
- Renaming `CurriculumStage` to `CurriculumStageName` for clarity — out of scope (existing name stays)
- Adding `apply_difficulty` to the 4 generic rewards — future phase if needed
- `TaskRewardRouter.difficulty_level` backward-compat alias — not needed (existing signature is a strict superset)

---

## Pre-decided items (carried forward, not re-asked)

From ROADMAP.md D-29-01..05 (already locked at roadmap time):
- **D-29-01:** Single phase for TASK-02 is appropriate
- **D-29-02:** DifficultyLevel is enum-only, not Pydantic-validated scalar
- **D-29-03:** No new DifficultyLevelConfig schema model
- **D-29-04:** interpolate_params() remains the single source of truth
- **D-29-05:** Float path is preserved everywhere

---

*Phase: 29-TASK-02 3-Difficulty-Levels Completion*
*Discussion log generated: 2026-06-11*

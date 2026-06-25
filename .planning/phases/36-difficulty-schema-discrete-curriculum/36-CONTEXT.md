# Phase 36: Difficulty Schema + Discrete Curriculum - Context

**Gathered:** 2026-06-24
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers a `DifficultyLevelConfig` Pydantic v2 leaf model carrying
four per-level override fields, and an additive `progression_mode` on
`CurriculumScheduler` that advances EASY→MEDIUM→HARD via new
`set_difficulty_level` / `advance_level` methods — without touching the
validated continuous `advance_stage` path. Pure schema + curriculum internals;
non-GPU; lowest-risk first phase of v0.6.0 (continues from v0.5.0 Phase 35).

**What this phase delivers:**
1. A `DifficultyLevelConfig` Pydantic v2 leaf model with four override fields
   (`tissue_stiffness` / `target_precision_tolerance` / `tool_position_noise` /
   `time_limit`), validating types and ranges.
2. An abstract→concrete override mapping (the four abstract field names → the
   real per-task `PARAM_BOUNDS` keys) plus a `DiscreteCurriculumConfig` Pydantic
   model that holds the three per-level `DifficultyLevelConfig` instances.
3. Additive composition: per-level overrides compose additively over
   `interpolate_params()` — an overridden field replaces only that field's
   interpolated value; unoverridden fields retain the interpolated value
   (verified by a truth-table test).
4. An additive `progression_mode` on `CurriculumScheduler` that advances
   EASY→MEDIUM→HARD via `set_difficulty_level` / `advance_level`, while the
   continuous `advance_stage` path produces byte-identical output to v0.5.0.
5. The full v0.4.0 + v0.4.2 curriculum + difficulty test suite passes unchanged
   (additive-regression gate; no test edits beyond additions).

**What this phase does NOT deliver:**
- Scene JSON `difficulty_blocks` authoring or `SurgicalEnv` precedence wiring
  (that is Phase 37 — TASK-08).
- 3D fluids, K8s PVC e2e, real DreamerV3 (Phases 38/39/40).
- Any change to the continuous `advance_stage` scalars or `CurriculumStage`
  defaults (those stay byte-identical to v0.5.0).
- New `PARAM_BOUNDS` keys on reward classes (the four abstract fields map onto
  EXISTING keys; no reward surface is edited).

</domain>

<decisions>
## Implementation Decisions

### Override field → PARAM_BOUNDS mapping
- **D-01:** The four override field names are **abstract aliases**, not literal
  `PARAM_BOUNDS` keys. Only `tissue_stiffness` and `time_limit` coincide with
  real keys (and not on every task); `target_precision_tolerance` and
  `tool_position_noise` match no task's keys. A per-task mapping resolves each
  abstract name to the concrete `PARAM_BOUNDS` key for the loaded task.
- **D-02:** The mapping lives as a **pure-data dict in a non-leaf wiring module**
  (task-name string → `{abstract_field → concrete PARAM_BOUNDS key string}`),
  co-located with `DiscreteCurriculumConfig` (see D-08). This keeps
  `DifficultyLevelConfig` a true import-free leaf. Recommended module:
  `src/surg_rl/dynamics/difficulty_wiring.py` (planner confirms final path).
- **D-03:** The mapping is **keyed by `TaskConfig.name` string** and is populated
  for **all six v0.4.0 tasks** in this phase (suturing, knot_tying,
  needle_insertion, grasping, cutting, dissection) so Phase 37's load-all-6
  regression is unblocked.
- **D-04:** When a set override field has **no mapping for the loaded task**
  (e.g. `tissue_stiffness` on a suturing scene), log a **warning** and keep the
  interpolated value (do not raise). Matches "unoverridden fields retain the
  interpolated value"; warns so author intent is not silently lost.
- **D-05:** The locked per-task abstract→concrete mapping (confirmed by user):

  | Abstract field | suturing | dissection | needle_insertion | knot_tying | grasping | cutting |
  |---|---|---|---|---|---|---|
  | `tissue_stiffness` | — | `tissue_stiffness` | — | `tissue_stiffness` | — | `tissue_stiffness` |
  | `target_precision_tolerance` | `needle_position_tolerance` | `incision_path_tolerance` | `needle_alignment_tolerance` | `loop_deviation_tolerance` | `approach_tolerance` | `cut_path_accuracy` |
  | `tool_position_noise` | — | — | `action_noise` | `action_noise` | `action_noise` | — |
  | `time_limit` | `time_limit` | `time_limit` | `time_limit` | `time_limit` | `time_limit` | `time_limit` |

  Rationale for judgment calls: on `target_precision_tolerance`, the positional
  precision key is chosen over force/tension/proximity alternatives
  (`needle_alignment_tolerance` over `handoff_proximity_tolerance`;
  `approach_tolerance` over `grip_force_accuracy`; `loop_deviation_tolerance`
  over `knot_tension_tolerance`). `tool_position_noise` maps to `action_noise`
  wherever that key exists; no-op on suturing/dissection/cutting. Empty cells =
  no mapping (warn + no-op per D-04).

### Override value representation & validation
- **D-06:** An override value is an **absolute scalar** that REPLACES the
  interpolated value for the mapped concrete key. Composing = compute
  `interpolate_params(level.value)`, then for each set override field replace
  the mapped concrete key's value with the override value. Unoverridden keys
  keep the interpolated value. (Not a delta, not a multiplier.)
- **D-07:** Each override field is range-validated against **global bounds
  derived from the union of per-task `PARAM_BOUNDS`** for that abstract field
  (min lo, max hi across the six tasks). Catches authoring errors at schema
  time. Basic positivity is implied; researchers cannot push beyond the union
  range without opting out. (Planner: derive the four global bound pairs from
  the existing `PARAM_BOUNDS` values enumerated in rewards.py.)

### progression_mode config & coexistence
- **D-08:** A separate **`DiscreteCurriculumConfig` Pydantic model** wraps the
  three per-level `DifficultyLevelConfig` instances via a
  `levels: dict[DifficultyLevel, DifficultyLevelConfig]` field (default empty =
  pure `interpolate_params(level.value)` baseline, i.e. additive composition
  with zero overrides). `DiscreteCurriculumConfig` imports
  `DifficultyLevelConfig` + `DifficultyLevel`, so it MUST live in the wiring
  module, NOT in the `DifficultyLevelConfig` leaf file (else the leaf gains
  in-project imports and violates success criterion #5).
- **D-09:** `CurriculumConfig` gains a new
  `progression_mode: Literal["continuous", "discrete"] = "continuous"` field
  and an optional reference to `DiscreteCurriculumConfig`. Default `"continuous"`
  keeps v0.5.0 `advance_stage` output byte-identical (additive-regression gate
  safe). `curriculum.py` imports `DiscreteCurriculumConfig` one-directionally
  from the wiring module (the leaf stays import-free; no cycle).
- **D-10:** In `"discrete"` mode the scheduler holds a separate
  `_current_level: DifficultyLevel` whose `.value` (0.0 / 0.5 / 1.0) feeds
  `interpolate_params`. The continuous `_current_stage` state and `advance_stage`
  path are left untouched. The `DifficultyLevel` scalars (0.0/0.5/1.0) are
  intentionally distinct from the `CurriculumStage` default scalars
  (0.25/0.5/0.75/1.0) — the two paths must not share state.

### advance_level trigger
- **D-11:** `advance_level` reuses the existing `_should_advance` success-rate
  gate (`min_success_rate` over `advancement_window`, with
  `difficulty_hysteresis`). One threshold mechanism shared with continuous mode;
  least new logic and keeps the continuous path byte-identical. No new
  episode-count-per-level config field.
- **D-12:** `advance_level` at the top level (HARD) is a no-op returning
  `False` (terminal level). `set_difficulty_level` accepts a `DifficultyLevel`
  enum and sets `_current_level` directly (manual override).

### Claude's Discretion
- Exact file path for the wiring module (`difficulty_wiring.py` vs extending
  `task_reward_router.py`) — planner decides, provided the leaf stays solo and
  import-free.
- Exact truth-table test layout and parametrization, provided it verifies:
  (a) overriding one field changes only that field; (b) unoverridden fields
  retain the interpolated value; (c) empty `levels` dict == pure interpolation.
- Exact validator implementation (Pydantic `field_validator` vs
  `model_validator`) for the four union-bound ranges.
- Naming of internal `_current_level` field and the
  `progression_mode` Literal values, provided semantics match the decisions
  above.
- Whether `set_difficulty_level` additionally accepts a string and coerces to
  the enum (minor; not required).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project context
- `.planning/PROJECT.md` — milestone overview; v0.6.0 scope.
- `.planning/ROADMAP.md` §"Phase 36: Difficulty Schema + Discrete Curriculum" —
  goal, success criteria (5), dependency on nothing (first phase of v0.6.0).
- `.planning/REQUIREMENTS.md` — TASK-06, TASK-07, TASK-09 acceptance criteria
  (the four override fields; additive `progression_mode`; additive-regression
  gate).
- `.planning/STATE.md` — current milestone state; Phase 35 closeout context.

### Prior phase artifacts
- `.planning/phases/35-advanced-tech-debt/35-CONTEXT.md` — established
  `SurgicalEnv._setup_rewards()` as the single reward-difficulty resolution
  point; `CurriculumScheduler.current_difficulty` already normalizes
  `DifficultyLevel`→`float`. Phase 36 builds on this clean baseline.
- `.planning/phases/29-task-02-3-difficulty-levels/29-REVIEW.md` — WR-02/WR-03
  findings (difficulty normalization type-lie) closed in v0.5.0; background for
  the discrete-level path.

### Code references (the validated surfaces this phase must NOT perturb)
- `src/surg_rl/dynamics/curriculum.py` — `CurriculumStage` enum (5 members:
  EASY/MEDIUM/HARD/EXPERT/CUSTOM, default scalars 0.25/0.5/0.75/1.0);
  `CurriculumConfig` dataclass; `CurriculumScheduler` with `advance_stage`,
  `_should_advance`, `current_difficulty`, `sample_parameters`.
- `src/surg_rl/rl/rewards.py` — the six task reward classes and their
  `PARAM_BOUNDS` (the concrete keys the abstract fields map onto); the
  `interpolate_params(cls, difficulty: float)` classmethod (the additive
  baseline). DO NOT edit these surfaces (additive-regression gate).
- `src/surg_rl/rl/difficulty.py` — `DifficultyLevel` float-mixin enum
  (EASY=0.0, MEDIUM=0.5, HARD=1.0); intentionally a leaf (no `surg_rl.*`
  imports) — the pattern `DifficultyLevelConfig` must mirror.
- `src/surg_rl/scene_definition/schema.py:1491-1506` — the v0.4.2
  `model_rebuild()` cycle-resolution pattern (late import + forward-ref
  resolution) that `DifficultyLevelConfig` leaf wiring MUST follow so no
  Pydantic cross-package cycle is (re)introduced.
- `src/surg_rl/rl/task_reward_router.py` — already normalizes
  `DifficultyLevel`→`float`; candidate co-location for the wiring module
  (planner decides vs a new `difficulty_wiring.py`).

### Testing references
- `tests/test_difficulty_levels.py` — existing up/down family direction tests
  (tissue_stiffness = up family; time_limit/tolerance = down family); the
  additive-regression gate this phase must keep green.
- `pytest.ini` — marker registry.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `DifficultyLevel` (`rl/difficulty.py`) — the float-mixin enum whose `.value`
  scalars (0.0/0.5/1.0) drive `interpolate_params`. Reuse directly as the
  discrete-mode level enum and as the `levels` dict key type in
  `DiscreteCurriculumConfig`.
- `interpolate_params(cls, difficulty: float)` (`rl/rewards.py`) — the additive
  baseline. Discrete composition computes this first, then applies override
  replacements on top. Do NOT modify it.
- `_should_advance` / `advance_stage` / `current_difficulty`
  (`dynamics/curriculum.py`) — reuse `_should_advance` for `advance_level`
  (D-11); leave `advance_stage` byte-identical.
- `model_rebuild()` cycle pattern (`scene_definition/schema.py:1491-1506`) —
  the template for wiring the `DifficultyLevelConfig` leaf without introducing
  a Pydantic cross-package cycle.

### Established Patterns
- **Leaf model pattern:** `rl/difficulty.py` is a deliberate zero-import leaf
  so `rewards.py` stays importable from `schema.py`. `DifficultyLevelConfig`
  must follow the same discipline (success criterion #5).
- **Late-import + `model_rebuild()`** to resolve forward refs across packages
  without a runtime cycle.
- **Additive-regression gate:** new code is additive; existing
  v0.4.0 + v0.4.2 tests pass unchanged (no edits beyond additions).

### Integration Points
- `CurriculumConfig` (dataclass in `dynamics/curriculum.py`) — gains
  `progression_mode` + optional `DiscreteCurriculumConfig` reference.
- `CurriculumScheduler` — gains `_current_level`, `set_difficulty_level`,
  `advance_level`; reads `DiscreteCurriculumConfig.levels` only in discrete mode.
- The wiring module (new) — owns the abstract→concrete mapping dict AND
  `DiscreteCurriculumConfig`; imported one-directionally by `curriculum.py`.
- `SurgicalEnv._setup_rewards()` (Phase 35) — the eventual consumer of
  per-level overrides, but precedence wiring is Phase 37, NOT this phase.

</code_context>

<specifics>
## Specific Ideas

- The user confirmed the exact per-task abstract→concrete mapping table (D-05)
  during discussion, including the three judgment calls on
  `target_precision_tolerance` for needle_insertion / grasping / knot_tying.
  Downstream agents should treat D-05 as the authoritative mapping, not
  re-derive it.
- "Additive over `interpolate_params()`" means per-field absolute replacement
  unioned onto the interpolated dict — NOT arithmetic addition to the value.
  The truth-table test must assert this precisely (override one field → only
  that field's value differs from pure interpolation; all others equal).
- The `DifficultyLevel` scalars (0.0/0.5/1.0) are deliberately different from
  `CurriculumStage` default scalars (0.25/0.5/0.75/1.0). This is intentional:
  discrete mode is a separate axis, not a relabeling of stages. Do not "fix"
  the mismatch by aligning them — that would perturb the continuous path.

</specifics>

<deferred>
## Deferred Ideas

- Scene JSON `difficulty_blocks` authoring + `SurgicalEnv` override-precedence
  chain (`scene-level > TaskConfig.difficulty_level > config.difficulty >
  default 0.5`) — Phase 37 (TASK-08).
- Extending the abstract override vocabulary beyond the four locked fields
  (e.g. a `thread_tension` or `object_mass` override) — would be a new
  capability; belongs in a future phase if needed.
- Per-task override of the abstract→concrete mapping itself (letting a scene
  remap `target_precision_tolerance` to a non-default concrete key) — not in
  scope; the mapping is project-level canonical in this phase.
- EXPERT/CUSTOM `DifficultyLevel` entries — the discrete path is EASY→MEDIUM→
  HARD only (three levels), matching `DifficultyLevel`. EXPERT stays a
  `CurriculumStage` concept on the continuous path.

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 36-difficulty-schema-discrete-curriculum*
*Context gathered: 2026-06-24 via roadmap + prior phase artifacts + codebase scout + user discussion*
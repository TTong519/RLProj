# Phase 29: TASK-02 3-Difficulty-Levels Completion — Context

**Gathered:** 2026-06-11
**Status:** Ready for planning
**Source:** v0.4.2 milestone roadmap (D-29-01..05 pre-decided) + this discussion (D-DIR-01, D-PLUMB-01) closing the remaining open questions.

<domain>
## Phase Boundary

Each of the 6 task types supports EASY/MEDIUM/HARD difficulty levels via a new `DifficultyLevel` enum, drives observable parameter changes through the existing `PARAM_BOUNDS` + `interpolate_params()` machinery, and threads cleanly through `TaskRewardRouter` (with full `apply_difficulty` wiring), `TaskConfig` (Pydantic v2), and `CurriculumScheduler` — all without breaking the existing float-based difficulty path. Closes the partial v0.4.0 audit gap.

</domain>

<decisions>
## Implementation Decisions

### Pre-decided (carried forward from ROADMAP.md D-29-01..05)

- **D-29-01 (carry):** Single phase for TASK-02 is appropriate. The 6 requirements form one tightly-coupled feature: enum → per-task methods → router → TaskConfig → CurriculumScheduler. Subdividing into "implementation" and "integration" plans within Phase 29 is acceptable (planner's choice), but splitting into two phases would over-engineer a gap-closure milestone.
- **D-29-02 (carry):** `DifficultyLevel` is enum-only, not Pydantic-validated scalar. The enum is the public API; internally, only the scalar (`0.0`/`0.5`/`1.0`) is used. Avoids confusing double-validation (Pydantic validates enum membership; downstream uses scalar).
- **D-29-03 (carry):** No new `DifficultyLevelConfig` schema model. `TaskConfig` gets a single optional `difficulty_level` field; per-level override blocks (tissue_stiffness, target_precision_tolerance, tool_position_noise, time_limit) are deferred. The 6 `PARAM_BOUNDS` already encode the progression — adding scene-level overrides is scope creep.
- **D-29-04 (carry):** `interpolate_params(difficulty)` remains the single source of truth. `get_params_for_difficulty(level)` is a thin wrapper that calls `interpolate_params(level.value)`. No duplicate math.
- **D-29-05 (carry):** Float path is preserved everywhere. `TaskRewardRouter(difficulty=0.5)` and `TaskRewardRouter(difficulty=DifficultyLevel.MEDIUM)` produce equivalent behavior. Mixed `CurriculumStageConfig.task_difficulty` (float in stage 1, enum in stage 2) works without migration. (Note: the existing `CurriculumStageConfig.difficulty` field is renamed-or-aliased to `task_difficulty` only if the planner finds it cleaner — the field is at `src/surg_rl/dynamics/curriculum.py:55`.)

### Direction semantics (this discussion)

- **D-DIR-01:** The parametrized test must assert **per-family direction**, not just inequality. The 6 `PARAM_BOUNDS` dictionaries split into two physical families:
  - **Down family** (lo > hi — "more = looser", HARD pulls the value down): tolerance-like params (needle_position_tolerance, thread_tension_threshold, stitch_spacing_tolerance, incision_path_tolerance, collateral_damage_threshold, force_precision, time_limit, handoff_proximity_tolerance, needle_alignment_tolerance, loop_deviation_tolerance, knot_tension_tolerance, approach_tolerance, grip_force_accuracy, cut_path_accuracy, collateral_threshold). For these, the test asserts `HARD_value < EASY_value`.
  - **Up family** (lo < hi — "more = stricter", HARD pushes the value up): tissue_stiffness (stiffer = harder), action_noise (noisier = harder), object_mass (heavier = harder). For these, the test asserts `HARD_value > EASY_value`.
  The test parametrizes over 6 task types × 3 levels and asserts: for each task type, at least one parameter of each family present in that task's `PARAM_BOUNDS` strictly moves in the correct direction between EASY and HARD. A task with only down-family params still passes (the up-family check is vacuous for it). A single test class with `@pytest.mark.parametrize` covering all 6 task types is the minimum.
- **D-DIR-02:** Audit confirms all 6 PARAM_BOUNDS are directionally consistent: 0.0 = loose/easy, 1.0 = strict/hard. No flipping of bounds is required. The "inverted" PARAM_BOUNDS (lo<hi) are physically meaningful — stiffer tissue, heavier object, more noise correspond to harder difficulty. The implementation must NOT flip any `PARAM_BOUNDS` entries; the existing direction is the design.

### Plumbing depth (this discussion)

- **D-PLUMB-01:** Add an `apply_difficulty(level: DifficultyLevel | float)` method to `BaseRewardFunction` (or to each of the 6 task-specific reward subclasses — planner's choice). The method is a no-op default on `BaseRewardFunction` and is overridden by each task subclass to map `interpolate_params(difficulty)` results to the subclass's own ctor fields. `TaskRewardRouter.build()` calls `reward.apply_difficulty(self._difficulty)` after `reward_cls(**reward_kwargs)` returns. This is the "fully wired" version — the existing `TaskRewardRouter._difficulty` field (currently set but never used at `src/surg_rl/rl/task_reward_router.py:52`) becomes load-bearing.
- **D-PLUMB-02:** Per-task field mapping is allowed to be partial — a subclass may use only a subset of `interpolate_params()` results (e.g., `SuturingReward.apply_difficulty` may map `needle_position_tolerance` → `self.position_threshold` and `time_limit` → a new `self.time_limit` field, while ignoring `thread_tension_threshold` and `stitch_spacing_tolerance`). The test only requires that the *observable* effect (e.g., the position threshold value used in `compute()`) actually changes; unmapped params are silently ignored. The plan should document each subclass's mapping explicitly.
- **D-PLUMB-03:** The mapping may require adding new fields to the reward class (e.g., `SuturingReward.time_limit`) if the PARAM_BOUNDS contains keys not in the current constructor. The plan should audit each of the 6 classes for missing-field gaps and either add the field or document the omission. Existing ctor defaults must remain backward-compatible (no breaking signature changes).
- **D-PLUMB-04:** `get_params_for_difficulty(level: DifficultyLevel) -> dict[str, float]` remains a separate public method on each of the 6 reward classes (success criterion #2). It is a pure delegating wrapper: `return cls.interpolate_params(level.value)`. It does NOT mutate the reward; `apply_difficulty` is the mutating method. Both can coexist — `get_params_for_difficulty` is read-only introspection, `apply_difficulty` is state mutation.
- **D-PLUMB-05:** `TaskRewardRouter.__init__` signature changes from `difficulty: float = 0.5` to `difficulty: float | DifficultyLevel = 0.5`. Internally, normalize: `scalar = difficulty.value if isinstance(difficulty, DifficultyLevel) else difficulty`. Store `self._difficulty = scalar` and pass it to `apply_difficulty(scalar)` in `build()`. The float-only path (today's default) is preserved — `TaskRewardRouter(difficulty=0.5).build(task_type)` works exactly as before from a caller's perspective, but now actually mutates the reward.
- **D-PLUMB-06:** `BaseRewardFunction.apply_difficulty` default implementation is a no-op (`pass`). This keeps the 4 generic reward classes (`DistanceReward`, `ActionPenalty`, `TimePenalty`, `CollisionPenalty`) unaffected — they have no `PARAM_BOUNDS` and no difficulty semantics. The 6 task-specific subclasses override.

### Test design

- **D-TEST-01:** Single parametrized test class in a new file `tests/test_difficulty_levels.py` (or appended to an existing `tests/test_rewards.py` if the planner prefers feature consolidation — but per AGENTS.md, feature-specific files are preferred to reduce merge conflicts). The class covers all 6 task types × 3 levels = 18 cases (or 6 cases if parametrized only over task type with EASY/HARD comparison).
- **D-TEST-02:** Per D-DIR-01, the test must assert direction per family. The recommended structure:
  ```python
  @pytest.mark.parametrize("task_type,reward_cls,families", [
      ("suturing", SuturingReward, {"down": ["needle_position_tolerance", "time_limit"]}),
      ("dissection", DissectionReward, {"down": ["incision_path_tolerance", "time_limit"], "up": ["tissue_stiffness"]}),
      # ... 4 more
  ])
  def test_difficulty_direction(task_type, reward_cls, families):
      easy = reward_cls.get_params_for_difficulty(DifficultyLevel.EASY)
      hard = reward_cls.get_params_for_difficulty(DifficultyLevel.HARD)
      for name in families.get("down", []):
          assert hard[name] < easy[name], f"{task_type}: {name} did not move strict (HARD<{name}<EASY)"
      for name in families.get("up", []):
          assert hard[name] > easy[name], f"{task_type}: {name} did not move strict (HARD>{name}>EASY)"
  ```
- **D-TEST-03:** A second test verifies that `apply_difficulty` actually mutates the reward (D-PLUMB-01). For each subclass, build a default-constructed instance, capture a relevant field (e.g., `position_threshold`), call `apply_difficulty(DifficultyLevel.HARD)`, assert the field moved in the expected direction. This is the wiring-smoke test.
- **D-TEST-04:** A third test verifies float/enum equivalence in the router (D-PLUMB-05, success criterion #4). For each of the 6 task types, build `TaskRewardRouter(difficulty=0.5).build(task_type)` and `TaskRewardRouter(difficulty=DifficultyLevel.MEDIUM).build(task_type)`, then assert the resulting reward instances have identical post-`apply_difficulty` state on every mapped field.
- **D-TEST-05:** Integration test (plan 29-02) is in the same `tests/test_difficulty_levels.py` (or a sibling `tests/test_difficulty_integration.py` per AGENTS.md feature-file preference). It loads a scene JSON (use the existing `scenes/simple_suturing.json` which already has `task.task_type = "suturing"`) with a new `task.difficulty_level = "HARD"` field, runs `SceneLoader.load()`, asserts the resulting `TaskConfig.difficulty_level == DifficultyLevel.HARD`, and confirms env.reset() builds a HARD-configured `SuturingReward`. A `task.difficulty_level = null` (or absent) path is tested separately — should fall through to the float path with no level applied.

### Pydantic v2 schema (TaskConfig field)

- **D-SCHEMA-01:** Add to `TaskConfig` at `src/surg_rl/scene_definition/schema.py:1065-1090`:
  ```python
  difficulty_level: DifficultyLevel | None = Field(
      default=None,
      description="Surgical difficulty preset (EASY/MEDIUM/HARD). None = use the float difficulty path.",
  )
  ```
  `DifficultyLevel` must be importable from `surg_rl.rl` (success criterion #1) — the enum lives in the `rl` module per OpenCode's discretion (see "OpenCode's Discretion" below).
- **D-SCHEMA-02:** `DifficultyLevel` enum values are scalars: `EASY = 0.0`, `MEDIUM = 0.5`, `HARD = 1.0` (D-29-02). The `value` of each member is the float used by `interpolate_params()`. Pydantic v2 validates the literal; downstream uses `.value`.
- **D-SCHEMA-03:** Mixed scene JSONs (some with `difficulty_level`, some without, some with a numeric `difficulty` field on a different config layer) load without migration. The loader's Pydantic v2 default of `None` is the explicit "use float path" sentinel.

### CurriculumScheduler integration

- **D-CURR-01:** `CurriculumStageConfig.difficulty` (at `src/surg_rl/dynamics/curriculum.py:55`, currently `float = 0.5`) becomes `float | DifficultyLevel = 0.5`. Internally normalize to float scalar. No renaming of the field is required (the roadmap's "task_difficulty" terminology maps to this existing `difficulty` field — no schema churn).
- **D-CURR-02:** When a stage activates, its `difficulty` (now potentially a `DifficultyLevel`) flows into the env's `TaskRewardRouter` construction. The env's `_setup_rewards()` method reads `self._scene.task.difficulty_level` first (Pydantic field); if `None`, it reads `self.config.difficulty` (SurgicalEnvConfig's float field, if any) or defaults to `0.5`. The router is constructed with whichever is set.
- **D-CURR-03:** No new discrete level progression logic in `CurriculumScheduler` (D-29-03 — deferred per roadmap). The scheduler still uses the continuous `difficulty` field for progression; the enum is just an alternative input source.

### Backwards compatibility

- **D-BC-01:** `TaskRewardRouter()` (no args) and `TaskRewardRouter(difficulty=0.5)` produce equivalent reward lists to today's behavior, modulo `apply_difficulty` now actually running. For a default-constructed reward (ctor defaults) and `apply_difficulty(0.5)`, the resulting fields are the ctor-default value interpolated at 0.5. If the ctor default is the *midpoint* of `PARAM_BOUNDS` (which is the Phase 21 intent — all ctor defaults are midpoints), `apply_difficulty(0.5)` is a no-op numerically and the test for "float 0.5 == enum MEDIUM" passes trivially. **Verify this during planning** — if any ctor default is NOT the midpoint, the test must assert a tighter equality.
- **D-BC-02:** All 6 task scene JSONs from Phase 27 (`scenes/{suturing,knot_tying,needle_insertion,grasping,cutting,dissection}.json`) load unchanged. They do not need to add `task.difficulty_level` — Pydantic v2 default of `None` preserves today's behavior (float path with default 0.5).

### OpenCode's Discretion

- **Enum module location:** `src/surg_rl/rl/difficulty.py` (new file) vs. co-located in `src/surg_rl/rl/task_reward_router.py` vs. `src/surg_rl/rl/rewards.py`. Success criterion #1 requires `from surg_rl.rl import DifficultyLevel`, so it must be exported from `surg_rl.rl.__init__`. The choice between new file vs. existing file is OpenCode's — both work. The existing `CurriculumStage` enum at `src/surg_rl/dynamics/curriculum.py:25-32` (with string values) is a different concept and should NOT be reused — it represents the *stage* in the curriculum progression, not the *difficulty preset* on a single scene.
- **Whether `apply_difficulty` lives on `BaseRewardFunction` (with no-op default) or only on the 6 task-specific subclasses (as a duck-typed method called via `getattr`):** Either is acceptable. The base-class approach is more discoverable; the duck-typed approach is more minimal. OpenCode picks.
- **Per-subclass field mapping exactness:** the planner documents which `interpolate_params()` keys are mapped to which ctor fields for each of the 6 subclasses. The minimum is: at least one mapped field per subclass so D-TEST-03 has something to assert. The maximum is: every key mapped. OpenCode chooses — a partial mapping is acceptable per D-PLUMB-02.
- **Whether to add new ctor params for previously-unmapped `PARAM_BOUNDS` keys** (D-PLUMB-03): e.g., `SuturingReward.time_limit` may not exist as a ctor param today (verify during planning). The plan may either add the param with a default or leave it as a known gap. Adding is preferred if the field is reachable from `compute()` or `check_success/failure`; omitting is fine if it's purely descriptive metadata.
- **Test fixture granularity:** whether to split the per-direction test (D-DIR-01) into one test class per task type or one parametrized class for all 6. Both are acceptable. AGENTS.md prefers feature-specific files; either fits in `tests/test_difficulty_levels.py`.
- **Integration test depth:** D-TEST-05 lists the minimum. A deeper test (curriculum stage activation → env reset → reward check) is allowed but not required. The Phase 27 precedent is "Pydantic-validate only" + "env.reset() doesn't crash" — match that depth.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/REQUIREMENTS.md` — TASK-02-01..06 v1 requirements
- `.planning/ROADMAP.md` § Phase 29 — goal, success criteria, plans, D-29-01..05 pre-decisions, the "Risk" note on PARAM_BOUNDS direction
- `.planning/v0.4.0-MILESTONE-AUDIT.md` — TASK-02 partial gap evidence
- `.planning/STATE.md` § Decisions — D-29-01..05 carried forward; v0.4.2 D-29-01..05 listed

### Source artifacts — reward classes (the 6 task types)
- `src/surg_rl/rl/rewards.py:519-656` — `SuturingReward` (PARAM_BOUNDS at 527, interpolate_params at 650)
- `src/surg_rl/rl/rewards.py:659-794` — `DissectionReward` (PARAM_BOUNDS at 666, interpolate_params at 787)
- `src/surg_rl/rl/rewards.py:796-923` — `NeedlePassingReward` (PARAM_BOUNDS at 803, interpolate_params at 916)
- `src/surg_rl/rl/rewards.py:925-1069` — `KnotTyingReward` (PARAM_BOUNDS at 932, interpolate_params at 1062)
- `src/surg_rl/rl/rewards.py:1071-1217` — `GraspingReward` (PARAM_BOUNDS at 1078, interpolate_params at 1210)
- `src/surg_rl/rl/rewards.py:1219-1361` — `CuttingReward` (PARAM_BOUNDS at 1226, interpolate_params at 1354)
- `src/surg_rl/rl/rewards.py:1363-1494` — `CompositeReward` (where the router output gets assembled)

### Source artifacts — router & environment
- `src/surg_rl/rl/task_reward_router.py:44-80` — `TaskRewardRouter` (caches `_difficulty` at line 52, never uses it in `build()` — Phase 29 makes this load-bearing)
- `src/surg_rl/rl/task_reward_router.py:27-34` — `TASK_REWARD_REGISTRY` (the 6 task types)
- `src/surg_rl/rl/environment.py:192-205` — `_setup_rewards()` where the router is called with no difficulty today (Phase 29 reads `task.difficulty_level` and passes it)
- `src/surg_rl/rl/environment.py:51` — `from .task_reward_router import TaskRewardRouter`
- `src/surg_rl/rl/environment.py:208` — `self._task_difficulty = 0.5` (where the difficulty scalar lives post-reset; will be populated from `task.difficulty_level`)

### Source artifacts — Pydantic v2 schema
- `src/surg_rl/scene_definition/schema.py:1065-1090` — `TaskConfig` (current fields: `name`, `description`, `objectives`, `constraints`, `reward_shaping`, `max_episode_length`, `time_limit`, `success_threshold`, `task_type`); Phase 29 adds `difficulty_level`
- `src/surg_rl/scene_definition/loader.py` — `SceneLoader.load()` (Pydantic v2 entry point)

### Source artifacts — curriculum
- `src/surg_rl/dynamics/curriculum.py:25-32` — `CurriculumStage` enum (EASY/MEDIUM/HARD/EXPERT/CUSTOM with string values — different concept from the new `DifficultyLevel`)
- `src/surg_rl/dynamics/curriculum.py:35-60` — `CurriculumStageConfig` (has `difficulty: float = 0.5` at line 55 — Phase 29 widens this to `float | DifficultyLevel`)
- `src/surg_rl/dynamics/curriculum.py:267` — comment "difficulty is the single source of truth" — Phase 29 honors this

### Source artifacts — test patterns
- `tests/test_rewards.py` — existing reward tests (mirror for D-TEST-01..04)
- `tests/test_task_termination.py` — per-task-type parametrized tests (mirror for D-TEST-01)
- `tests/test_benchmark_scenes.py` — Phase 27 integration test (mirror for D-TEST-05; uses `SceneLoader.load` with no env spin-up)
- `tests/test_loader.py` — existing scene loader tests (mirror for D-TEST-05 Pydantic-validate-only path)

### Reference scene
- `scenes/simple_suturing.json` — has `task.task_type = "suturing"` (from Phase 27 D-06); Phase 29 may add a `difficulty_level` field for D-TEST-05, or use a separate test fixture scene. Either is acceptable.

### Prior phase context
- `.planning/phases/21-surgical-task-curriculum/21-CONTEXT.md` — `interpolate_params()` design (D-04 of Phase 21); the `difficulty: float = 0.5` semantic
- `.planning/phases/27-complete-benchmark-scene-coverage/27-CONTEXT.md` — gap-closure phase pattern (1 plan, scene JSON contract)
- `.planning/phases/26-fix-dreamerv3-training-bugs/26-CONTEXT.md` — gap-closure phase pattern (minimal scope, no architectural changes)
- `.planning/phases/25-fix-marl-runtime-wiring/25-CONTEXT.md` — gap-closure phase pattern

### Architecture & conventions
- `.planning/codebase/ARCHITECTURE.md` — env → router → reward data flow
- `.planning/codebase/CONVENTIONS.md` — pytest patterns, lazy imports
- `AGENTS.md` § Pydantic v2 — `Model.model_construct(**data)` is the only way to skip validation; in `model_validator(mode="after")` mutate via `self.model_copy(update={...})`; `model_dump()` returns Enum objects (Phase 29 relevant when serializing `difficulty_level`)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`PARAM_BOUNDS` (6 dicts, 1 per task type):** already encode the difficulty progression. No edits to the bounds themselves (D-DIR-02). The bound direction is correct: down-params (lo>hi) mean "more = looser", up-params (lo<hi) mean "more = stricter" — both align with 0.0=loose, 1.0=strict.
- **`interpolate_params(difficulty: float) -> dict[str, float]`:** 6 classmethods (one per task reward), all using the formula `bounds[0] + (bounds[1] - bounds[0]) * difficulty`. `get_params_for_difficulty(level)` is a thin wrapper around this (D-29-04).
- **`TaskRewardRouter._difficulty`:** the field is set in `__init__` (line 52) but never read in `build()` (line 80). Phase 29 reads it and calls `apply_difficulty(scalar)` on the constructed reward.
- **`TaskRewardRouter.TASK_REWARD_REGISTRY`:** the 6 task types → reward class map at lines 27-34. No edits to the registry required.
- **`TaskConfig.task_type` (Pydantic v2 Literal | None):** at `src/surg_rl/scene_definition/schema.py:1084-1090`. `difficulty_level` is added next to it as another optional field.
- **`SceneLoader.load()`:** at `src/surg_rl/scene_definition/loader.py`. Validates Pydantic v2 — Phase 29 needs no loader changes; the new field validates automatically with default `None`.

### Established Patterns
- **Pydantic v2 `Field(default=None, description=...)`:** matches existing `task_type` pattern at `schema.py:1084-1090`.
- **Optional Pydantic union with `None` default:** the existing pattern for `task_type`, `TaskConfig.difficulty_level` follows it.
- **Float + enum dual support (Pydantic v2):** AGENTS.md and Phase 21 set the pattern: validate the literal, normalize to scalar downstream.
- **Class-level `PARAM_BOUNDS` dict + classmethod `interpolate_params`:** 6 existing instances of this pattern. `get_params_for_difficulty` is a third method on each class (D-PLUMB-04).
- **Method on `BaseRewardFunction` with no-op default for generics:** the 4 generic rewards (`DistanceReward`, `ActionPenalty`, `TimePenalty`, `CollisionPenalty`) have no `PARAM_BOUNDS`. `apply_difficulty` no-op default keeps them untouched (D-PLUMB-06).
- **Test parametrization with `pytest.mark.parametrize`:** matches `tests/test_task_termination.py` per-task-type pattern.
- **Pydantic-validate-only integration tests (no env spin-up):** matches Phase 27's `tests/test_benchmark_scenes.py` pattern.

### Integration Points
1. **`DifficultyLevel` enum** → `surg_rl.rl.__init__` (success criterion #1) — the enum is exported alongside `SuturingReward`, `DissectionReward`, etc.
2. **`TaskConfig.difficulty_level`** → `SceneLoader.load()` → `SurgicalEnv._setup_rewards()` at `environment.py:192-205` — the env reads the field and constructs `TaskRewardRouter(difficulty=difficulty_level)`.
3. **`TaskRewardRouter.__init__(difficulty= float | DifficultyLevel)`** → `TaskRewardRouter._difficulty` (normalized to scalar) → `build()` → `reward_cls(**reward_kwargs).apply_difficulty(self._difficulty)`.
4. **`reward.apply_difficulty(scalar)`** → per-subclass field mapping (D-PLUMB-02) → mutates `self.position_threshold` etc.
5. **`CurriculumStageConfig.difficulty: float | DifficultyLevel`** → at stage activation, the env reads it (if `TaskConfig.difficulty_level is None`) and passes to the router.
6. **`SurgicalEnvConfig.difficulty` (if exists)** → fallback float source. Verify during planning whether `SurgicalEnvConfig` has a `difficulty` field; if not, the only float path is `CurriculumStageConfig.difficulty`.

### Common Landmines
- **Do NOT edit any `PARAM_BOUNDS` entries.** The direction is already correct (D-DIR-02). Flipping bounds would break existing test contracts.
- **Do NOT change `CurriculumStage` enum (EASY/MEDIUM/HARD with string values).** It's a separate concept (the *stage* in progression) from the new `DifficultyLevel` (the *difficulty preset* on a scene). Renaming the new enum to avoid collision with `CurriculumStage` is the right move; `DifficultyLevel` is the chosen name per roadmap.
- **Do NOT add a new `DifficultyLevelConfig` Pydantic model.** D-29-03 explicitly excludes this. `TaskConfig.difficulty_level` is a single optional field; per-level override blocks are deferred.
- **Do NOT add discrete level progression to `CurriculumScheduler`.** D-29-03 explicitly excludes this. The scheduler still progresses continuously; the enum is just an input source.
- **Do NOT remove `interpolate_params` or `PARAM_BOUNDS` from any reward class.** D-29-04 mandates they remain the single source of truth. `get_params_for_difficulty` is a delegating wrapper.
- **Do NOT break the float-only path.** `TaskRewardRouter(difficulty=0.5)` must still work. `CurriculumStageConfig(difficulty=0.5)` must still work. D-29-05 + D-BC-01.
- **Do NOT modify `BaseRewardFunction.__init__` signature.** Adding a `difficulty` default ctor arg would break the 4 generic rewards and the existing test surface. Use `apply_difficulty` as the post-construction hook (D-PLUMB-01).
- **Do NOT add `apply_difficulty` to the 4 generic rewards** (`DistanceReward`, `ActionPenalty`, `TimePenalty`, `CollisionPenalty`). They have no difficulty semantics; the no-op default on `BaseRewardFunction` is sufficient (D-PLUMB-06).
- **Do NOT rename `CurriculumStageConfig.difficulty` to `task_difficulty`.** D-CURR-01 — the field is already called `difficulty`; the roadmap's "task_difficulty" terminology is informal. The field is at `curriculum.py:55`.
- **Pydantic v2 quirk (AGENTS.md):** `model_dump()` returns Enum objects, not `.value` strings. If the plan serializes `difficulty_level` to YAML or JSON, convert via `.value` first.

</code_context>

<specifics>
## Specific Ideas

### Specific implementation anchors

- **D-PLUMB-05 signature change** at `src/surg_rl/rl/task_reward_router.py:51`:
  ```python
  def __init__(self, difficulty: float | DifficultyLevel = 0.5):
      if isinstance(difficulty, DifficultyLevel):
          self._difficulty = difficulty.value
      else:
          self._difficulty = float(difficulty)
  ```
  And at line 71-72 (the `build()` body), after `rewards.append(task_reward)`, add:
  ```python
  task_reward.apply_difficulty(self._difficulty)
  ```
  The generic rewards in the loop at lines 77-78 are unaffected (no-op `apply_difficulty` default).

- **D-PLUMB-01 minimal `apply_difficulty` for `SuturingReward`** (the others follow the same pattern; planner fills in the per-subclass field mapping):
  ```python
  def apply_difficulty(self, difficulty: float) -> None:
      """Apply interpolated difficulty parameters to this reward instance."""
      params = self.interpolate_params(difficulty)
      if "needle_position_tolerance" in params:
          self.position_threshold = params["needle_position_tolerance"]
      if "time_limit" in params:
          self.time_limit = params["time_limit"]  # new field — see D-PLUMB-03
      # thread_tension_threshold, stitch_spacing_tolerance: optionally map
  ```
  Verify during planning whether `SuturingReward` already has a `time_limit` field; if not, add it (D-PLUMB-03).

- **D-SCHEMA-01 minimal `TaskConfig` addition** at `src/surg_rl/scene_definition/schema.py:1084` (just before the existing `task_type` field):
  ```python
  from surg_rl.rl.difficulty import DifficultyLevel  # add import at top of schema.py — circular import risk! See landmine below
  ...
  difficulty_level: DifficultyLevel | None = Field(
      default=None,
      description="Surgical difficulty preset (EASY/MEDIUM/HARD). None = use the float difficulty path.",
  )
  ```
  **Circular import risk:** `src/surg_rl/rl/difficulty.py` would import from `src/surg_rl/rl/__init__.py` if the enum is co-located in rewards.py. Avoid this by:
  - Putting the enum in a new leaf module `src/surg_rl/rl/difficulty.py` with no imports from `surg_rl.rl.*`.
  - Or using `from __future__ import annotations` + `TYPE_CHECKING` guard in `schema.py`.
  - Or defining the enum in `src/surg_rl/rl/rewards.py` and re-exporting from `__init__.py` (no circular import from `schema.py` → `rewards.py` exists today; verify). The current `src/surg_rl/rl/rewards.py` has no imports from `surg_rl.scene_definition.*`, so importing `DifficultyLevel` from `rewards.py` into `schema.py` is safe.
  OpenCode picks the resolution.

- **D-TEST-01 test fixture scene** (for D-TEST-05 integration): copy `scenes/simple_suturing.json` to `tests/fixtures/scenes/suturing_difficulty_hard.json` (or similar; use a fixture path so the production scene file isn't mutated) with the addition of `"difficulty_level": "HARD"` in the `task` block. The fixture file is local to `tests/` and not loaded by production code.

- **D-CURR-02 `SurgicalEnv._setup_rewards()` modification** at `src/surg_rl/rl/environment.py:200-202`:
  ```python
  if task_type is not None:
      difficulty = (
          self._scene.task.difficulty_level
          if self._scene.task.difficulty_level is not None
          else self.config.difficulty  # verify this field exists on SurgicalEnvConfig
      )
      router = TaskRewardRouter(difficulty=difficulty)
      reward_list = router.build(task_type)
      ...
  ```
  Verify during planning whether `SurgicalEnvConfig` has a `difficulty` field. If not, the only fallback is `CurriculumStageConfig.difficulty` (env reads it from the curriculum controller, not from its own config).

### Deferred Ideas (out of phase scope)

- **Per-level scene override blocks** (D-29-03 carries forward) — adding `difficulty_levels: list[3]` of per-level override dicts to scene JSONs. Deferred to v0.5.0+.
- **Discrete level progression in `CurriculumScheduler`** (D-29-03 carries forward) — the scheduler stepping through EASY → MEDIUM → HARD explicitly. Currently progression is continuous via the float `difficulty` field. Deferred to v0.5.0+.
- **`DifficultyLevelConfig` Pydantic model** (D-29-03 carries forward) — a richer schema for per-level override blocks. Deferred.
- **Renaming `CurriculumStage` to `CurriculumStageName` for clarity** — the new `DifficultyLevel` enum could cause confusion for newcomers. Out of scope; the existing name stays.
- **Adding `apply_difficulty` to the 4 generic rewards** (`DistanceReward`, etc.) — they have no difficulty semantics. If future work makes them difficulty-aware, that's a new phase.
- **Backward-compat alias `TaskRewardRouter.difficulty_level`** as an alias for the renamed field — not needed; the existing `difficulty: float | DifficultyLevel` signature is a strict superset.

### Prior context (carry forward, do not re-ask)
- User prefers `PYTHONPATH=src` for direct Python script invocations (per AGENTS.md).
- User prefers feature-specific test files (per AGENTS.md).
- User rejects removing "intentional" numeric constants (per AGENTS.md).
- The 421 ruff issues in `src/surg_rl/dreamer/` are explicitly out of scope (PROJECT.md accepted tech debt).

</specifics>

---

*Phase: 29-TASK-02 3-Difficulty-Levels Completion*
*Context gathered: 2026-06-11 from v0.4.2 roadmap (D-29-01..05 pre-decided) + discussion (D-DIR-01, D-PLUMB-01..06, D-TEST-01..05, D-SCHEMA-01..03, D-CURR-01..03, D-BC-01..02)*

# Phase 37: Scene-Level difficulty_blocks + Env Wiring - Research

**Researched:** 2026-06-24
**Domain:** Pydantic v2 scene schema + SurgicalEnv reward-difficulty precedence wiring (additive, non-GPU)
**Confidence:** HIGH

## Summary

Phase 37 is the env-wiring step of the difficulty-curriculum work begun in Phase 36. It
adds a `difficulty_blocks` field to `TaskConfig` (scene JSON authors can specify per-level
override blocks), and threads a single documented override-precedence chain through
`SurgicalEnv._setup_rewards()` so a scene with hard-mode blocks produces a hard-mode
environment without code changes. It reuses Phase 36's `DifficultyLevelConfig` leaf,
`DiscreteCurriculumConfig` wrapper, and `compose_difficulty_overrides` helper verbatim —
no new schema primitive is invented.

Phase 36 is **fully shipped** (3/3 plans, commits `166a52b`, `42ee64c`, `879907d`). The
artifacts this phase builds on are all live in the codebase: `DifficultyLevelConfig`
(`src/surg_rl/rl/difficulty.py`), `ABSTRACT_TO_CONCRETE` + `DiscreteCurriculumConfig` +
`compose_difficulty_overrides` (`src/surg_rl/dynamics/difficulty_wiring.py`), and
`CurriculumScheduler.progression_mode` / `set_difficulty_level` / `advance_level`
(`src/surg_rl/dynamics/curriculum.py`). Nothing in Phase 37 needs to re-derive P36
primitives — it consumes them.

Three integration seams dominate the plan, each verified with file:line evidence this
session: (1) the schema attachment point (`TaskConfig` in `schema.py:1087-1121`, with the
exact `model_rebuild()` pattern at `schema.py:1491-1506` to copy); (2) the env precedence
point (`_setup_rewards` at `environment.py:484-521`, whose current chain
`task.difficulty_level → config.difficulty → curriculum → default 0.5` is the single
reward-difficulty resolution site); (3) the reward-application seam — `apply_difficulty(scalar)`
on each of the 6 task rewards re-interpolates internally and maps only ONE `PARAM_BOUNDS`
key to a ctor field, so applying a composed-override dict requires either a new
`apply_params(dict)` method on each task reward or a refactor that extracts
`apply_difficulty`'s mapping body into `apply_params(params)` (additive, regression-safe).
The planner MUST pick one of these two application seams; both are documented below.

**Primary recommendation:** Add `difficulty_blocks: dict[DifficultyLevel, DifficultyLevelConfig]
| None = None` (or a `DiscreteCurriculumConfig | None = None` wrapper) to `TaskConfig` as a
string forward-ref, reusing P36's `DiscreteCurriculumConfig.levels` shape verbatim. In
`_setup_rewards`, resolve the level first (`task.difficulty_level` → default), then when
`difficulty_blocks` is present call `compose_difficulty_overrides(task_type, level,
difficulty_blocks[level], reward_cls)` and apply the composed dict via a new
`apply_params(params)` method on each task reward (refactor `apply_difficulty` to delegate
to it — pure refactor, observable output unchanged → regression-safe). Keep the continuous
curriculum path untouched.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TASK-08 | Scene JSON can specify `difficulty_blocks` per level and `SurgicalEnv` applies them at construction with a documented, tested override-precedence chain | (1) `TaskConfig.difficulty_blocks` field added via the `schema.py:1491-1506` `model_rebuild()` pattern (SC#1, SC#5); (2) `_setup_rewards` (`environment.py:484-521`) rewritten to the documented 4-level precedence `difficulty_blocks[level] > task.difficulty_level > config.difficulty > default 0.5` (SC#2); (3) `compose_difficulty_overrides` (P36, live) reused as the override composer; (4) 6×3 fixture regression gate + `suturing_difficulty_hard.json` back-compat scalar gate (SC#3, SC#4); (5) naming-drift reconciliation to `difficulty_blocks` across PROJECT.md/STATE.md (SC#5) |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Pydantic v2:** `Model(**data)` and `model_validate()` both fully validate (not
  different paths). To skip validation use `model_construct` (nested dicts stay plain
  dicts). In `model_validator(mode="after")` use `self.model_copy(update={...})`, not
  mutation. **Enum values in `model_dump()` stay as Enum objects** — convert before YAML
  serialization (`yaml.dump` raises `RepresenterError`). `DifficultyLevel` is a
  `_FloatMixin(float, Enum)`; if `difficulty_blocks` is `dict[DifficultyLevel, ...]`, a
  YAML round-trip of a scene with blocks set will raise unless the loader's YAML
  representer is extended (the loader uses `yaml.safe_dump`-style paths — verify).
- **Leaf-model + late-import + `model_rebuild()` cycle-resolution pattern** is project
  canon (v0.4.2). `TaskConfig.difficulty_blocks` MUST be a string forward-ref to
  `DifficultyLevelConfig` / `DiscreteCurriculumConfig`, resolved by the late-import +
  `TaskConfig.model_rebuild()` block at `schema.py:1491-1506`. Adding an eager import of
  the wiring module in `schema.py` re-opens the cross-package cycle (Pitfall 4 below).
- **Gymnasium/SB3:** `simulator.load_scene(scene)` MUST be called before `reset()`/`step()`;
  observation/action spaces defined in `__init__` before any `reset()`. Relevant to SC#3
  (the 6×3 regression gate must construct + step the env).
- **Optional-field guards:** `SceneDefinition.task` is `Optional[TaskConfig]` — always
  guard `if self._scene.task is not None` before reading `.difficulty_level` /
  `.difficulty_blocks` / `.task_type`. `_setup_rewards` already guards task (line 492);
  the new blocks read must extend the same guard.
- **Domain randomization controllers:** `CurriculumScheduler.DEFAULT_STAGES` uses mutable
  dataclass values — always `copy.deepcopy()`. Not directly edited this phase, but the
  precedence chain interacts with `current_difficulty` (curriculum-driven path).
- **Imports:** verify opening parens on multi-line imports; never use `sed`/`echo` to
  inject multi-line blocks — use `Edit` or `python -c pathlib.write_text`.
- **Testing:** `PYTHONPATH=src pytest ...` (pytest.ini sets `pythonpath = src`); the full
  suite aborts on macOS for several MuJoCo/PyBullet-backend test files (pre-existing,
  logged in 36-03-SUMMARY) — the targeted regression subset must avoid those files.
- **Code style:** line length 100; Python ≥3.10; type hints required
  (`mypy disallow_untyped_defs = true`); ruff select E,F,I,N,W,UP,B,C4,SIM (ignore E501);
  `from __future__ import annotations` is already present in `schema.py:5` and
  `curriculum.py` (added P36-03) — reuse, do not re-add.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `difficulty_blocks` scene field (schema) | Schema (`scene_definition/schema.py`) | — | `TaskConfig` is the existing home of `difficulty_level`; blocks attach here. String forward-ref + `model_rebuild()` keeps the cross-package cycle closed (SC#1, SC#5). |
| Per-level override composition | Wiring (`dynamics/difficulty_wiring.py`) | — | P36's `compose_difficulty_overrides` already does interpolate-then-override (D-06). Reuse verbatim — do NOT re-implement in the env. |
| Override-precedence resolution | RL env (`rl/environment.py::_setup_rewards`) | — | The single env-construction reward-difficulty resolution point (P35 baseline). The 4-level chain lives here and only here. |
| Composed-dict → reward ctor-field application | Reward classes (`rl/rewards.py`) | — | Each task reward's `apply_difficulty` already maps `interpolate_params` output to ctor fields. A new `apply_params(params)` (or refactored `apply_difficulty`) is the application seam. |
| Continuous curriculum path | Curriculum scheduler (`dynamics/curriculum.py`) | — | MUST stay byte-identical (TASK-09 additive gate). The blocks path is orthogonal: blocks apply at env construction; curriculum drives `current_difficulty` only when `use_curriculum=True` and blocks absent. |
| Fixture + naming-drift reconciliation | Docs + fixtures | — | SC#5: PROJECT.md:82 `difficulty_levels` → `difficulty_blocks`; STATE.md historical drift note updated. No schema/fixture uses `difficulty_levels`. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | v2 (pinned) | `TaskConfig.difficulty_blocks` field (string forward-ref); `model_rebuild()` cycle resolution | Already project standard; the exact pattern is live at `schema.py:1491-1506` [VERIFIED: codebase] |
| enum (stdlib) | — | `DifficultyLevel` `_FloatMixin(float, Enum)` reused as the `difficulty_blocks` dict key / level selector | Existing `rl/difficulty.py:14-50` [VERIFIED: codebase] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `typing.Literal` / `dict` / `Optional` | stdlib | Field typing on `TaskConfig` | Schema field declaration |
| pytest | dev | parametrized truth-table + 6×3 fixture matrix + back-compat scalar gate | Validation Architecture |

No new packages are installed in this phase. All dependencies are already pinned.
`[VERIFIED: codebase — no new third-party imports required beyond stdlib + pydantic]`

**Installation:** None — `pip install -e ".[dev]"` already covers everything.

**Version verification:** Not applicable (no new packages).

## Package Legitimacy Audit

No external packages are installed in this phase. The audit is skipped — only stdlib
(`enum`, `typing`) and the already-pinned `pydantic` v2 are used, plus reuse of P36's
in-project modules (`rl.difficulty`, `dynamics.difficulty_wiring`, `rl.rewards`,
`rl.task_reward_router`). `[VERIFIED: codebase grep — no new third-party imports needed]`

## Architecture Patterns

### System Architecture Diagram

```
                         Scene JSON (author input)
                         task.difficulty_blocks: {EASY: {...}, MEDIUM: {...}, HARD: {...}}
                         task.difficulty_level: 1.0   (existing v0.4.2 field)
                                              |
                                              v
+----------------------------------------------------------------+
| scene_definition/schema.py  (TaskConfig — SC#1, SC#5)          |
|  difficulty_blocks: "dict[DifficultyLevel, DifficultyLevelConfig] | None"  |
|       (string forward-ref; resolved by model_rebuild() bottom) |
|  difficulty_level: "DifficultyLevel | None"   (existing)       |
+----------------------------------------------------------------+
              |  (SceneLoader.load → SceneDefinition(**data); round-trips)
              v
+----------------------------------------------------------------+
| rl/environment.py :: SurgicalEnv._setup_rewards()  (SC#2)      |
|  PRECEDENCE (documented + truth-table-tested):                 |
|   1. resolve level:                                            |
|      task.difficulty_level (enum)  ──> if blocks present,      |
|      else default (MEDIUM or 0.5)      compose overrides       |
|   2. if difficulty_blocks is not None AND level in blocks:     |
|        params = compose_difficulty_overrides(task_type, level, |
|                   difficulty_blocks[level], reward_cls)  --P36 |
|        reward.apply_params(params)         (NEW application    |
|                                             seam)              |
|      else:                                                     |
|        router = TaskRewardRouter(difficulty=level.value)       |
|        router.build(task_type)  (existing apply_difficulty)    |
|   3. self._task_difficulty = float(level.value)                |
+----------------------------------------------------------------+
              |                                  |
              |  (reuses P36 live helper)        | (existing path, untouched
              v                                  v  when blocks absent)
+-----------------------------+    +--------------------------------------+
| dynamics/difficulty_wiring  |    | rl/task_reward_router.py             |
|  compose_difficulty_overrides|   |  TaskRewardRouter.build ->           |
|   (D-06: interpolate-then-  |    |   task_reward.apply_difficulty(scalar)|
|    override; ABSOLUTE)      |    +--------------------------------------+
|  DiscreteCurriculumConfig   |
|  ABSTRACT_TO_CONCRETE (D-05)|    +--------------------------------------+
+-----------------------------+    | rl/rewards.py (6 task rewards)       |
                                   |  apply_difficulty(scalar):           |
                                   |   params = interpolate_params(scalar)|
                                   |   map ONE key -> ctor field          |
                                   |  apply_params(params): NEW — map     |
                                   |   composed dict -> ctor fields       |
                                   +--------------------------------------+

Decision points:
  blocks present + level resolved  -> compose + apply_params (new path)
  blocks absent                    -> existing TaskRewardRouter + apply_difficulty
  use_curriculum=True (no blocks)  -> curriculum.current_difficulty drives scalar
                                      (continuous path byte-identical, TASK-09)
```

### Recommended Project Structure
```
src/surg_rl/
├── scene_definition/
│   └── schema.py          # EDIT (additive): TaskConfig.difficulty_blocks forward-ref field
├── rl/
│   ├── environment.py     # EDIT (additive): _setup_rewards precedence chain
│   └── rewards.py         # EDIT (additive refactor): extract apply_params(params) from
│                          #   apply_difficulty on 6 task rewards; base no-op unchanged
└── (no other src edits — difficulty_wiring.py / difficulty.py are reused read-only)
tests/
├── test_difficulty_blocks.py      # NEW: SC#1 round-trip + SC#2 truth-table + SC#5 naming
└── (existing test_difficulty_levels.py, test_discrete_curriculum.py stay green)
.planning/PROJECT.md      # EDIT: line 82 difficulty_levels -> difficulty_blocks
.planning/STATE.md        # EDIT: historical drift note (line 82, 131) reconciled
```

### Pattern 1: String forward-ref + late import + `model_rebuild()` (v0.4.2 canon)
**What:** A Pydantic field whose type lives in another package is declared as a string
forward-ref; the type is imported at module bottom AFTER all classes are defined, then
`TaskConfig.model_rebuild()` resolves the forward ref.
**When to use:** Whenever a `TaskConfig` field type lives in `rl.difficulty` or
`dynamics.difficulty_wiring` (cross-package).
**Source:** `src/surg_rl/scene_definition/schema.py:1491-1506` [VERIFIED: codebase]
```python
# schema.py bottom (the existing block — EXTEND it, do not duplicate):
from surg_rl.rl.difficulty import (  # noqa: E402
    DifficultyLevel,
    DifficultyLevelConfig,   # NEW import for the difficulty_blocks forward ref
)  # noqa: F401 — module-level binding for forward ref resolution
TaskConfig.model_rebuild()
```
`DifficultyLevelConfig` already imports only stdlib + pydantic (P36-01 leaf, verified
`rl/difficulty.py` has zero in-project imports). Adding it to the existing late-import
block introduces NO new cycle: `schema.py` → `rl.difficulty` (leaf) is the same one-way
edge that `DifficultyLevel` already uses. **Do NOT import `dynamics.difficulty_wiring`
into `schema.py`** — that would create `scene_definition → dynamics` (new edge). If the
field type is `DiscreteCurriculumConfig` (which lives in `dynamics.difficulty_wiring`),
the forward-ref import would cross into `dynamics` — risky. Safer: type the field as
`dict[DifficultyLevel, DifficultyLevelConfig] | None` so only `rl.difficulty` symbols are
needed (both already imported at `schema.py:1501`). `[VERIFIED: codebase import graph]`

### Pattern 2: Reuse P36's `compose_difficulty_overrides` (D-06) — do NOT re-implement
**What:** The composed-params dict is `interpolate_params(level.value)` with SET override
fields ABSOLUTELY replacing mapped concrete keys.
**Source:** `src/surg_rl/dynamics/difficulty_wiring.py:85-135` [VERIFIED: codebase, P36-02 shipped]
```python
# In _setup_rewards (NEW branch, only when difficulty_blocks present):
from surg_rl.dynamics.difficulty_wiring import compose_difficulty_overrides
from surg_rl.rl.task_reward_router import TASK_REWARD_REGISTRY

reward_cls = TASK_REWARD_REGISTRY.get(task_type)
if reward_cls is not None and level in difficulty_blocks:
    params = compose_difficulty_overrides(task_type, level, difficulty_blocks[level], reward_cls)
    # apply params to the constructed task reward (see Pattern 3)
```
`compose_difficulty_overrides` already handles D-04 (unmapped field → warn + keep
interpolated value, never raises). The env branch only needs to resolve `level` and
dispatch. `[VERIFIED: codebase `difficulty_wiring.py:117-135`]`

### Pattern 3: `apply_params(params)` — the reward application seam (TWO options)
**What:** `apply_difficulty(difficulty: float)` on each of the 6 task rewards calls
`interpolate_params(difficulty)` internally and maps exactly ONE `PARAM_BOUNDS` key to a
ctor field. To apply a composed dict (with overrides), the env needs a way to apply an
arbitrary `params: dict[str, float]` to the reward instance.

**Option A (recommended — pure refactor, regression-safe):** Extract the mapping body of
each task reward's `apply_difficulty` into a new `apply_params(self, params: dict[str,
float]) -> None`, and rewrite `apply_difficulty(difficulty)` as
`self.apply_params(self.interpolate_params(difficulty))`. Observable output of
`apply_difficulty` is byte-identical (regression-safe). The env then calls
`reward.apply_params(compose_difficulty_overrides(...))`.
[VERIFIED: codebase `rewards.py:696-704, 852-859, 999-1006, 1163-1170, 1329-1336, 1491-1498`]

```python
# SuturingReward — refactor (Option A):
def apply_params(self, params: dict[str, float]) -> None:
    if "needle_position_tolerance" in params and hasattr(self, "position_threshold"):
        self.position_threshold = params["needle_position_tolerance"]

def apply_difficulty(self, difficulty: float) -> None:
    self.apply_params(self.interpolate_params(difficulty))
```

**Option B (additive only, no refactor):** Add a NEW `apply_params(params)` method
alongside `apply_difficulty` on each task reward, duplicating the mapping one-liner. The
env calls `apply_params` for the blocks path; `apply_difficulty` is untouched. Slightly
more duplication; zero regression risk.

**Either way:** `BaseRewardFunction.apply_difficulty` (the no-op default at
`rewards.py:161-184`) stays a no-op; `BaseRewardFunction` gains a default `apply_params`
that is also a no-op (D-PLUMB-06 — generic rewards must not consume difficulty).
`[VERIFIED: codebase `rewards.py:161-184`]`

### Anti-Patterns to Avoid
- **Importing `dynamics.difficulty_wiring` into `schema.py`** — creates a new
  `scene_definition → dynamics` edge. Type `difficulty_blocks` as
  `dict[DifficultyLevel, DifficultyLevelConfig] | None` so only `rl.difficulty` symbols
  are needed (already late-imported). `[CITED: PITFALLS.md:106-108]`
- **Re-implementing the override composer in the env** — duplicates P36's
  `compose_difficulty_overrides` and the D-05 mapping. Reuse it.
- **Editing `interpolate_params` or any `PARAM_BOUNDS`** — breaks the additive-regression
  gate (TASK-09). Overrides compose ON TOP of `interpolate_params` (D-06).
- **Treating `config.difficulty` as a live precedence level** — `SurgicalEnvConfig` has NO
  `difficulty` field (verified: `__dataclass_fields__` keys are scene_path, scene,
  simulator_type, ... controller_yaml — no `difficulty`). `getattr(self.config,
  "difficulty", 0.5)` at `environment.py:502` ALWAYS returns 0.5. The SC#2 precedence
  level `config.difficulty > default 0.5` is therefore currently a no-op (both 0.5). The
  planner should either (a) document that `config.difficulty` is reserved for a future
  `SurgicalEnvConfig.difficulty` field and keep the chain structural, or (b) note that the
  effective chain is `difficulty_blocks[level] > task.difficulty_level > default 0.5`.
  `[VERIFIED: codebase — `SurgicalEnvConfig.__dataclass_fields__` inspected via
  PYTHONPATH=src python3 this session]`
- **Letting `difficulty_blocks` overrides silently lose effect** — `apply_difficulty`
  maps only ONE key per task reward (e.g. SuturingReward maps
  `needle_position_tolerance → position_threshold` and ignores `time_limit`,
  `tissue_stiffness`, etc.). A `difficulty_blocks` override on `time_limit` or
  `tissue_stiffness` would be INERT through `apply_difficulty`. The planner MUST decide
  whether `apply_params` maps ALL override-relevant keys (expanding the per-reward
  mapping) or only the existing one. See Open Question Q1 + Pitfall 3.
- **Making `difficulty_blocks` required or length-validated to reject existing scenes** —
  the 6 v0.4.0 task scenes have no blocks field; `None` default keeps them loading.
  `[CITED: PITFALLS.md:178-186]`

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-level override composition | New interpolate-then-override in the env | `compose_difficulty_overrides(task_type, level, config, reward_cls)` (P36, live) | Already TDD-verified by a 54-case truth table (P36-02); D-05 mapping authoritative |
| Abstract→concrete key mapping | Re-derive per-task keys | `ABSTRACT_TO_CONCRETE` (P36, live) | D-05 cell-for-cell validated; reuse avoids drift |
| Reward class lookup by task | New registry | `TASK_REWARD_REGISTRY` (`task_reward_router.py`) | Already maps the 6 `task_type` literals → reward classes; `compose_difficulty_overrides` accepts `reward_cls` as a param |
| Cross-package forward-ref resolution | Manual `__pydantic_internal__` hacks | `schema.py:1491-1506` late-import + `model_rebuild()` pattern | Proven v0.4.2; extending the existing block with `DifficultyLevelConfig` is a one-line addition |
| Difficulty→scalar normalization | New float coercion | `float(level.value) if isinstance(level, DifficultyLevel) else float(level)` (already at `environment.py:513`) | Existing normalization; reuse |

**Key insight:** Every primitive this phase needs already exists: `DifficultyLevelConfig`
(P36-01), `compose_difficulty_overrides` + `ABSTRACT_TO_CONCRETE` +
`DiscreteCurriculumConfig` (P36-02), `TASK_REWARD_REGISTRY` (v0.4.0), the
`model_rebuild()` pattern (v0.4.2), and the `_setup_rewards` resolution site (P35). The
phase is pure assembly: one new schema field + one precedence branch + one reward
application seam. No algorithm is invented.

## Common Pitfalls

### Pitfall 1: `config.difficulty` is a dead precedence level (SurgicalEnvConfig has no such field)
**What goes wrong:** SC#2 lists `config.difficulty > default 0.5` as a precedence level,
implying `SurgicalEnvConfig.difficulty` is a real field. It is NOT.
`SurgicalEnvConfig` (`environment.py:79-91`) has `scene_path, scene, simulator_type,
timestep, frame_skip, max_episode_steps, render_mode, render_fps, reward_config,
observation_config, action_config, use_curriculum, use_adaptive_difficulty,
controller_config, seed, ros2_bridge_config, use_ros2_control, controller_yaml` — no
`difficulty`. `getattr(self.config, "difficulty", 0.5)` at `environment.py:502` always
returns the default 0.5.
**Why it happens:** The precedence chain was documented against a future/planned
`SurgicalEnvConfig.difficulty` field that was never added (or was removed).
**How to avoid:** The truth-table test MUST treat `config.difficulty` and `default 0.5`
as the SAME level (both yield 0.5) unless the planner also adds a `difficulty: float =
0.5` field to `SurgicalEnvConfig` (a small additive change — recommend the planner do
this so the 4-level chain is real and testable as 4 distinct levels). If the field is NOT
added, the truth table collapses to 3 distinct levels.
**Warning signs:** A truth-table case asserting `config.difficulty=0.25` produces a
different result than `default 0.5` — it cannot, because the attribute does not exist.
`[VERIFIED: codebase this session — `SurgicalEnvConfig.__dataclass_fields__` inspected]`

### Pitfall 2: `apply_difficulty` maps only ONE key → most `difficulty_blocks` overrides are inert
**What goes wrong:** Each task reward's `apply_difficulty` maps exactly one
`PARAM_BOUNDS` key to one ctor field:
- SuturingReward: `needle_position_tolerance → position_threshold` (`rewards.py:703-704`)
- DissectionReward: `force_precision → force_threshold` (`rewards.py:857-858`)
- NeedlePassingReward: `handoff_proximity_tolerance → handoff_threshold` (`rewards.py:1005-1006`)
- KnotTyingReward: `loop_deviation_tolerance → loop_deviation_threshold` (`rewards.py:1169-1170`)
- GraspingReward: `approach_tolerance → grasp_threshold` (`rewards.py:1335-1336`)
- CuttingReward: `force_precision → force_threshold` (`rewards.py:1497-1498`)

But D-05 maps the abstract `target_precision_tolerance` to a DIFFERENT concrete key on
some tasks (e.g. SuturingReward D-05 → `needle_position_tolerance` ✓ matches; but
DissectionReward D-05 → `incision_path_tolerance`, while `apply_difficulty` maps
`force_precision`, NOT `incision_path_tolerance`). So a `difficulty_blocks` override on
`target_precision_tolerance` for dissection composes into the dict as
`incision_path_tolerance=override`, but `apply_difficulty`/`apply_params` (Option A
refactor) would NOT map `incision_path_tolerance` to any ctor field (DissectionReward
maps `force_precision` only). The override is present in the dict but never reaches the
reward's state.
**Why it happens:** P36 designed `compose_difficulty_overrides` to produce a complete
params dict, but the reward classes' `apply_difficulty` only consumes a subset of
`PARAM_BOUNDS` keys (D-PLUMB-02 "partial mapping is acceptable"). The two were designed
independently and the consumption seam is narrower than the production seam.
**How to avoid:** The planner MUST decide, per task reward, which concrete keys
`apply_params` maps. Two paths:
- (a) `apply_params` maps ONLY the same single key `apply_difficulty` already maps →
  `difficulty_blocks` overrides are only effective on `target_precision_tolerance` for
  suturing (matches `needle_position_tolerance`) and on `tool_position_noise` /
  `tissue_stiffness` / `time_limit` for tasks where `apply_difficulty` happens to map
  those (none currently do). Effective override surface is tiny.
- (b) `apply_params` maps ALL D-05 concrete keys to the corresponding ctor fields →
  expands the per-reward mapping (a real reward-surface edit, additive but needs new ctor
  field mappings / attributes that may not exist yet, e.g. DissectionReward needs an
  `incision_path_threshold` attribute to receive `incision_path_tolerance`). Higher
  coverage, more invasive.
**Recommendation:** Start with (a) for this phase (document the inert surface explicitly
in the truth table — assert that only the mapped key's ctor field changes), and defer
(b) to a future phase that expands the reward ctor-field surface. The SC#2 truth-table
test should assert the composed DICT is correct (full D-06 composition) AND that the
reward ctor field changes ONLY for the one key `apply_difficulty` maps. This keeps the
phase additive and the regression gate intact.
**Warning signs:** A truth-table case asserting `time_limit` override changes a reward
ctor field — it will not (no `apply_difficulty` maps `time_limit`). A truth-table case
asserting `tissue_stiffness` override changes a reward ctor field on dissection — it
will not (DissectionReward maps `force_precision` only).
`[VERIFIED: codebase `rewards.py` apply_difficulty bodies — 6 sites read this session]`

### Pitfall 3: `time_limit` field-ownership mismatch (TaskConfig vs reward PARAM_BOUNDS)
**What goes wrong:** `time_limit` appears in TWO places: (1) `TaskConfig.time_limit`
(`schema.py:1102`, the episode time cap read by the env), (2) `PARAM_BOUNDS["time_limit"]`
on all 6 reward classes (a reward-param, currently NOT mapped to any ctor field by
`apply_difficulty`). A `difficulty_blocks` override on `time_limit` composes into the
reward-params dict, but does NOT change `TaskConfig.time_limit` (the field the env
actually uses for episode truncation). So "hard mode = less time" author intent is lost
unless the env ALSO patches `TaskConfig.time_limit` (or `max_episode_steps`) from the
override.
**Why it happens:** `compose_difficulty_overrides` operates on reward-params; the
episode-cap lives on the scene/task config. The two are separate surfaces.
**How to avoid:** Decide and document: either (a) `difficulty_blocks.time_limit`
overrides ONLY the reward-param (currently inert — see Pitfall 2) and the author must
also set `TaskConfig.time_limit` directly for the episode cap; or (b) the env, when
blocks are present, also applies `difficulty_blocks[level].time_limit` to
`self._scene.task.time_limit` (or `max_episode_steps`) at construction. Option (b) is
more useful but crosses a surface boundary. Recommend (a) for this phase + document the
limitation; defer (b).
**Warning signs:** A test asserting a shorter `time_limit` override truncates the episode
earlier — it will not, unless option (b) is implemented.
`[VERIFIED: codebase — `TaskConfig.time_limit` at `schema.py:1102`; `PARAM_BOUNDS`
`time_limit` at `rewards.py:552,714,869,1016,1180,1346`]`

### Pitfall 4: Importing `dynamics.difficulty_wiring` into `schema.py` re-opens the cycle
**What goes wrong:** If `difficulty_blocks` is typed as `DiscreteCurriculumConfig | None`
and `DiscreteCurriculumConfig` is imported into `schema.py` to resolve the forward ref,
`schema.py` gains a `scene_definition → dynamics.difficulty_wiring → rl.difficulty` edge.
That itself does not cycle (rl.difficulty is a leaf), BUT `dynamics.difficulty_wiring`
could in future import `scene_definition` (it does not today — verified), and the
project's v0.4.2 cycle scar is exactly `scene_definition ↔ rl ↔ dynamics`.
**How to avoid:** Type `difficulty_blocks` as
`dict[DifficultyLevel, DifficultyLevelConfig] | None` (both types live in `rl.difficulty`,
already late-imported at `schema.py:1501`). Add `DifficultyLevelConfig` to that existing
late-import block. NO `dynamics.*` import in `schema.py`. The env imports
`compose_difficulty_overrides` from `dynamics.difficulty_wiring` lazily inside
`_setup_rewards` (function-body local import), keeping the module-import graph clean.
**Warning signs:** `ImportError` during pytest collection; `PydanticUndefinedAnnotation`
at validation time.
`[VERIFIED: codebase — `difficulty_wiring.py` imports only `rl.difficulty` + `utils.logging`;
no `scene_definition` import today]`

### Pitfall 5: Enum keys in `difficulty_blocks` dict break YAML scene round-trips
**What goes wrong:** Per CLAUDE.md, Enum values in `model_dump()` stay as Enum objects.
If `difficulty_blocks` is `dict[DifficultyLevel, DifficultyLevelConfig]`, dumping a scene
with blocks to YAML would raise `yaml.RepresenterError` on the `DifficultyLevel` dict keys
unless the loader's YAML representer is extended.
**How to avoid:** The scene fixtures are JSON (not YAML) — JSON keys are strings, so
`DifficultyLevel.EASY` serializes as `"EASY"` or `0.0` depending on Pydantic config. The
loader's YAML path (`loader.py:_parse_yaml`) is used by some tests. The planner should
either (a) add a `DifficultyLevel` yaml representer in `loader.py`, or (b) restrict
`difficulty_blocks` to JSON fixtures only (documented). Verify by round-tripping a scene
with blocks through `SceneLoader.load_from_string(format="yaml")`.
**Warning signs:** `RepresenterError` on YAML dump of a scene with blocks.
`[CITED: CLAUDE.md Pydantic v2 notes; PITFALLS.md:106-108]`

### Pitfall 6: Curriculum path vs blocks path interaction
**What goes wrong:** The current `_setup_rewards` lets `use_curriculum=True` OVERRIDE
`task.difficulty_level` (lines 504-510: curriculum `current_difficulty` replaces the
resolved difficulty). If a scene has BOTH `difficulty_blocks` AND `use_curriculum=True`,
the curriculum's continuous scalar (e.g. 0.37) is not one of the 3 enum levels, so
`difficulty_blocks[level]` has no level to index — silent fallthrough or crash.
**How to avoid:** Document precedence: `difficulty_blocks` apply ONLY when the resolved
level is one of EASY/MEDIUM/HARD (discrete path); when `use_curriculum=True` drives a
continuous scalar, blocks do not apply (fall back to `interpolate_params(scalar)` — the
existing continuous path). This matches PITFALLS.md:130 recommendation and keeps discrete
and continuous orthogonal. The truth table MUST include a `use_curriculum=True +
difficulty_blocks present` case asserting blocks are NOT applied (continuous scalar wins
via the existing curriculum branch).
**Warning signs:** A blocks-override ctor field changes when `use_curriculum=True` with a
continuous scalar — it should not.
`[VERIFIED: codebase `environment.py:504-510`]`

## Code Examples

### `TaskConfig.difficulty_blocks` — forward-ref field (SC#1, SC#5)
```python
# schema.py — inside TaskConfig (after difficulty_level, ~line 1121):
difficulty_blocks: "dict[DifficultyLevel, DifficultyLevelConfig] | None" = (
    Field(  # noqa: F821 — forward ref resolved at bottom of file
        default=None,
        description="Per-level difficulty override blocks keyed by DifficultyLevel "
        "(EASY/MEDIUM/HARD). None = no overrides; use the float difficulty path. "
        "Each value is a DifficultyLevelConfig carrying 0-4 SET override fields. "
        "When present, SurgicalEnv._setup_rewards composes overrides additively "
        "over interpolate_params(level.value) via compose_difficulty_overrides.",
    )
)

# schema.py bottom — EXTEND the existing late-import block (do NOT duplicate):
from surg_rl.rl.difficulty import (  # noqa: E402
    DifficultyLevel,
    DifficultyLevelConfig,  # NEW
)  # noqa: F401
TaskConfig.model_rebuild()  # already present; resolves both forward refs
```
`[CITED: schema.py:1113-1121 + 1491-1506 pattern]`

### `_setup_rewards` precedence branch (SC#2)
```python
# environment.py :: _setup_rewards (additive rewrite of the resolution block):
# Resolve level: task.difficulty_level > config.difficulty > default 0.5
task = self._scene.task
difficulty: float | DifficultyLevel
if task is not None and task.difficulty_level is not None:
    difficulty = task.difficulty_level
else:
    difficulty = getattr(self.config, "difficulty", 0.5)  # currently always 0.5 (Pitfall 1)

# Continuous curriculum overrides the scalar (existing behavior, untouched):
if (
    self.config.use_curriculum
    and self._controller is not None
    and self._controller._curriculum is not None
):
    difficulty = self._controller._curriculum.current_difficulty

difficulty_float = float(difficulty.value) if isinstance(difficulty, DifficultyLevel) else float(difficulty)
self._task_difficulty = difficulty_float

# NEW: blocks path (only when blocks present AND level is a discrete DifficultyLevel):
blocks = getattr(task, "difficulty_blocks", None) if task is not None else None
if (
    blocks
    and isinstance(difficulty, DifficultyLevel)
    and task is not None
    and task.task_type is not None
    and difficulty in blocks
):
    from surg_rl.dynamics.difficulty_wiring import compose_difficulty_overrides  # local
    from surg_rl.rl.task_reward_router import TASK_REWARD_REGISTRY
    reward_cls = TASK_REWARD_REGISTRY.get(task.task_type)
    if reward_cls is not None:
        params = compose_difficulty_overrides(
            task.task_type, difficulty, blocks[difficulty], reward_cls
        )
        router = TaskRewardRouter(difficulty=difficulty_float)
        reward_list = router.build(task.task_type)
        # apply composed params to the task reward (first in the list):
        if hasattr(reward_list[0], "apply_params"):
            reward_list[0].apply_params(params)
        self._reward_fn = CompositeReward([(r, 1.0) for r in reward_list])
        return
# else: fall through to the existing TaskRewardRouter / create_default_reward path
```
`[VERIFIED: codebase `environment.py:496-521` current shape; `difficulty_wiring.py:85-135`]`

### `apply_params` on SuturingReward (Option A refactor — Pattern 3)
```python
# rewards.py :: SuturingReward (refactor — observable output unchanged):
def apply_params(self, params: dict[str, float]) -> None:
    """Apply a composed params dict to ctor fields (D-PLUMB-02 partial mapping)."""
    if "needle_position_tolerance" in params and hasattr(self, "position_threshold"):
        self.position_threshold = params["needle_position_tolerance"]

def apply_difficulty(self, difficulty: float) -> None:
    self.apply_params(self.interpolate_params(difficulty))
```
`[VERIFIED: codebase `rewards.py:696-704`]`

### Scene JSON with `difficulty_blocks` (SC#1 fixture shape)
```json
{
  "task": {
    "name": "suturing_task",
    "description": "Suturing with hard-mode blocks",
    "task_type": "suturing",
    "difficulty_level": 1.0,
    "difficulty_blocks": {
      "EASY":   {"target_precision_tolerance": 0.02},
      "MEDIUM": {"target_precision_tolerance": 0.005},
      "HARD":   {"target_precision_tolerance": 0.002}
    }
  }
}
```
`[CITED: STACK.md:128-142 + D-05 mapping]`

### Truth-table test shape (SC#2)
```python
# tests/test_difficulty_blocks.py — parametrized over (level, source, expected_scalar, blocks, expect_override_applied):
@pytest.mark.parametrize("level,source,expected", [
    (DifficultyLevel.HARD, "blocks", 1.0),   # blocks override wins
    (DifficultyLevel.HARD, "task_difficulty_level", 1.0),  # no blocks
    (DifficultyLevel.MEDIUM, "config_difficulty", 0.5),    # currently == default (Pitfall 1)
    (DifficultyLevel.MEDIUM, "default", 0.5),
])
def test_precedence_truth_table(level, source, expected):
    # construct env with the given source configuration, assert _task_difficulty
    # and the composed params dict / reward ctor field match the truth table
    ...
```
`[CITED: P36-02 truth-table pattern at `tests/test_difficulty_config.py::TestComposeDifficultyOverrides`]`

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `task.difficulty_level` (scalar enum) only | + `task.difficulty_blocks` (per-level override dict) | Phase 37 (this) | Scene authors can override per-level params without code changes |
| `apply_difficulty(scalar)` re-interpolates | + `apply_params(composed_dict)` (refactor) | Phase 37 (this) | Composed-override dict reaches reward ctor fields; existing scalar path byte-identical |
| `_setup_rewards` 3-source chain | + `difficulty_blocks[level]` as highest precedence | Phase 37 (this) | 4-level documented chain (Pitfall 1: `config.difficulty` level currently inert) |

**Deprecated/outdated:**
- `difficulty_levels` spelling (PROJECT.md:82, STATE.md drift note) — superseded by
  `difficulty_blocks` (SC#5 reconciliation).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `DifficultyLevelConfig` and `DifficultyLevel` are the only types needed in `schema.py` to type `difficulty_blocks` (both in `rl.difficulty`, already late-imported) | Architecture Patterns / Pitfall 4 | LOW — verified `rl/difficulty.py` is a leaf; `schema.py:1501` already imports `DifficultyLevel` |
| A2 | `compose_difficulty_overrides` can be imported lazily inside `_setup_rewards` without a module-level `dynamics` import in `environment.py` | Architecture Patterns | LOW — `environment.py` already does lazy local `SceneLoader` import inside `_load_scene` (verified PROJECT.md:65); same pattern applies |
| A3 | `SurgicalEnvConfig` will NOT gain a `difficulty` field in this phase (so `config.difficulty` precedence level == default 0.5) | Pitfall 1 | MEDIUM — planner may choose to add it; if added, truth table gains a real 4th level. Recommend adding it (small additive field) so SC#2's 4-level chain is real |
| A4 | `apply_params` (Option A refactor) maps the SAME single key `apply_difficulty` maps; most D-05 override fields are inert on the reward ctor surface | Pitfall 2 / Open Q1 | MEDIUM — planner may choose to expand the mapping (Option b); affects truth-table expectations |
| A5 | The 6 v0.4.0 task scene fixtures construct + step cleanly under pytest on the target host (SC#3 regression gate) | Validation Architecture | MEDIUM — 36-03-SUMMARY logged macOS C-level aborts in `test_rl.py`/`test_benchmark_*.py` during full collection; the 6×3 gate must be verified in Wave 0 to use a scene-load + env-construct (or step) path that does not abort. `tests/test_rl_environment.py` constructs + steps envs from `scenes/minimal_scene.json` cleanly, so the path works for at least one scene |
| A6 | `difficulty_blocks` keyed by `DifficultyLevel` enum serializes as JSON string keys (`"EASY"/"MEDIUM"/"HARD"`) | Pitfall 5 | LOW — Pydantic v2 coerces enum dict keys to/from JSON string keys by default; verify in SC#1 round-trip test |

## Open Questions (RESOLVED)

1. **`apply_params` mapping scope (Pitfall 2)** — RESOLVED: adopted in 37-02 `<decisions>` (Q1 — MINIMAL Option a, single-key mapping, inert surface documented in truth table)
   - What we know: `apply_difficulty` maps exactly ONE `PARAM_BOUNDS` key per task reward.
     D-05 maps `target_precision_tolerance` to a different concrete key on some tasks
     (e.g. DissectionReward D-05 → `incision_path_tolerance`, but `apply_difficulty` maps
     `force_precision`). So a `target_precision_tolerance` override composes into the dict
     but never reaches a ctor field on dissection.
   - What's unclear: should `apply_params` map ALL D-05 concrete keys (expanding the
     per-reward ctor-field surface — invasive) or only the existing single key (minimal,
     mostly-inert overrides)?
   - Recommendation: Option (a) — minimal mapping this phase; document the inert surface
     in the truth table; defer expansion. Keeps the phase additive and regression-safe.

2. **Should `SurgicalEnvConfig` gain a `difficulty: float = 0.5` field? (Pitfall 1)** — RESOLVED: adopted in 37-02 Task 3 (SurgicalEnvConfig.difficulty: float = 0.5 added as the last dataclass field)
   - What we know: SC#2 lists `config.difficulty` as a precedence level, but the field
     does not exist; `getattr(..., "difficulty", 0.5)` always returns 0.5.
   - What's unclear: whether to add it (making the 4-level chain real and truth-table-
     testable as 4 distinct levels) or document it as a reserved-but-inert level.
   - Recommendation: Add it — a one-line additive `difficulty: float = 0.5` field on
     `SurgicalEnvConfig`. Makes SC#2's chain honest and the truth table a real 4-level
     test. Low risk (default 0.5 preserves v0.5.0 behavior).

3. **`difficulty_blocks` field shape: `dict[DifficultyLevel, DifficultyLevelConfig]` vs `DiscreteCurriculumConfig`** — RESOLVED: adopted in 37-01 `<decisions>` (Q3 — flat `dict[DifficultyLevel, DifficultyLevelConfig] | None` directly on TaskConfig, no dynamics.* import in schema.py)
   - What we know: P36's `DiscreteCurriculumConfig.levels` is already
     `dict[DifficultyLevel, DifficultyLevelConfig]`. Reusing it as the field type is DRY
     but requires importing `dynamics.difficulty_wiring` into `schema.py` (Pitfall 4) and
     nests the scene field under a `levels` key.
   - Recommendation: `dict[DifficultyLevel, DifficultyLevelConfig] | None` directly on
     `TaskConfig` — flat for scene authors, only `rl.difficulty` types needed, no
     `dynamics.*` import in `schema.py`. The env can wrap the dict in a
     `DiscreteCurriculumConfig(levels=blocks)` at consumption time if needed.

4. **Curriculum + blocks coexistence (Pitfall 6)** — RESOLVED: adopted in 37-02 Task 3 (Q4 — blocks apply ONLY under isinstance(difficulty, DifficultyLevel) enum guard; continuous scalar falls through to existing router, blocks inert)
   - What we know: `use_curriculum=True` overrides `task.difficulty_level` with a
     continuous scalar (e.g. 0.37) which is not a `DifficultyLevel` enum value.
   - Recommendation: When the resolved difficulty is a continuous scalar (not a
     `DifficultyLevel`), blocks do NOT apply (fall back to the existing
     `interpolate_params(scalar)` continuous path). Blocks apply ONLY when the resolved
     level is one of EASY/MEDIUM/HARD. Document + truth-table test this case.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | All | ✓ | 3.13 (venv) | — |
| pydantic v2 | Schema field | ✓ | pinned | — |
| pytest | Tests | ✓ | dev | — |
| MuJoCo / PyBullet (simulator backends) | SC#3 6×3 env-construct/step gate | partial (macOS aborts on some backend test files per 36-03-SUMMARY) | — | If env-step aborts on the target host, fall back to a SCENE-LOAD + env-CONSTRUCT-only gate (still satisfies "loads and produces a stepped environment" if a single `env.step(action)` succeeds; otherwise assert construction + `_setup_rewards` ran). `tests/test_rl_environment.py` constructs + steps envs from `scenes/minimal_scene.json` cleanly, so the path is viable for at least minimal scenes — verify the 6 task scenes in Wave 0. |

**Missing dependencies with no fallback:** None for the schema/truth-table/back-compat
gates. The 6×3 regression gate is the only host-sensitive test; design it to degrade to
construct-only if step aborts, and flag the abort as pre-existing (not caused by this
phase).

**Missing dependencies with fallback:** MuJoCo/PyBullet display path — use
`render_mode=None` (headless) in the regression gate (CLAUDE.md: "always use --headless
when no display").

## Validation Architecture

`workflow.nyquist_validation` is **true** in `.planning/config.json` (verified).
`workflow.tdd_mode` is also **true** — TDD-eligible tasks are flagged below.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (via `pytest.ini`; `pythonpath = src`, `asyncio_mode = auto`) |
| Config file | `pytest.ini` |
| Quick run command | `PYTHONPATH=src pytest tests/test_difficulty_blocks.py tests/test_difficulty_config.py tests/test_difficulty_levels.py tests/test_discrete_curriculum.py -v` |
| Full suite command | `PYTHONPATH=src pytest tests/ -v` (note: full suite has pre-existing macOS aborts in `test_rl.py`, `test_benchmark_*.py`, `test_dreamer_benchmark_integration.py`, `test_rl_callbacks.py`, `test_tracking_callbacks.py` per 36-03-SUMMARY — NOT caused by this phase; the targeted subset is the gate) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TASK-08 / SC#1 | Scene JSON with `difficulty_blocks` for all 3 levels loads via `SceneLoader` and round-trips through Pydantic v2 (blocks == authored values) | unit (TDD) | `PYTHONPATH=src pytest tests/test_difficulty_blocks.py::TestSceneBlocksRoundTrip -v` | ❌ Wave 0 (new) |
| TASK-08 / SC#1 | Scene JSON WITHOUT `difficulty_blocks` still loads (None default) — 6 existing scenes unaffected | regression | `PYTHONPATH=src pytest tests/test_difficulty_blocks.py::test_existing_scenes_load_without_blocks tests/test_difficulty_levels.py::TestDifficultyIntegration::test_all_phase27_scenes_load_with_difficulty_level_none -v` | ✅ (existing) + ❌ new |
| TASK-08 / SC#2 | Precedence truth table: `difficulty_blocks[level] > task.difficulty_level > config.difficulty > default 0.5` — parametrized, asserts `_task_difficulty` + composed params dict + reward ctor field | unit (TDD, parametrized) | `PYTHONPATH=src pytest tests/test_difficulty_blocks.py::TestPrecedenceTruthTable -v` | ❌ Wave 0 |
| TASK-08 / SC#2 | Blocks + `use_curriculum=True` continuous scalar → blocks NOT applied (Pitfall 6) | unit | `PYTHONPATH=src pytest tests/test_difficulty_blocks.py::test_blocks_inert_under_continuous_curriculum -v` | ❌ Wave 0 |
| TASK-08 / SC#3 | 6 v0.4.0 task scenes × 3 difficulty levels construct + step (regression gate) | regression (parametrized 6×3) | `PYTHONPATH=src pytest tests/test_difficulty_blocks.py::TestSixSceneThreeLevelRegression -v` | ❌ Wave 0 |
| TASK-08 / SC#4 | `tests/fixtures/scenes/suturing_difficulty_hard.json` still loads and produces the same difficulty scalar (1.0 → HARD → 1.0) as before this phase | regression (back-compat) | `PYTHONPATH=src pytest tests/test_difficulty_blocks.py::test_hard_fixture_scalar_unchanged tests/test_difficulty_levels.py::TestDifficultyIntegration::test_scene_load_with_difficulty_level_hard -v` | ✅ (existing) + ❌ new scalar-equivalence |
| TASK-08 / SC#5 | `difficulty_blocks` canonical across PROJECT.md, schema, STATE.md; `difficulty_levels` gone | structural (grep audit) | `grep -rn "difficulty_levels" .planning/PROJECT.md .planning/STATE.md src/surg_rl/` returns 0 (excluding historical milestone archives) | ❌ Wave 0 |
| TASK-09 | Existing v0.4.0 + v0.4.2 curriculum + difficulty suite passes unchanged | regression | `PYTHONPATH=src pytest tests/test_difficulty_levels.py tests/test_dynamics.py tests/test_difficulty_config.py tests/test_discrete_curriculum.py -v` | ✅ (existing — must stay green) |

### Sampling Rate
- **Per task commit:** quick run command above (the 4-5 difficulty test files).
- **Per wave merge:** `PYTHONPATH=src pytest tests/test_difficulty_blocks.py tests/test_difficulty_levels.py tests/test_dynamics.py tests/test_difficulty_config.py tests/test_discrete_curriculum.py tests/test_rl_environment.py -v` (targeted — avoids the macOS-aborting backend files).
- **Phase gate:** targeted subset green + a manual confirm that the full suite's only failures are the pre-existing macOS backend aborts (not caused by this phase).

### Wave 0 Gaps
- [ ] `tests/test_difficulty_blocks.py` — NEW. Covers SC#1 round-trip, SC#2 precedence
      truth table (4 levels + curriculum-coexistence case), SC#3 6×3 regression matrix,
      SC#4 hard-fixture scalar equivalence, SC#5 naming audit. TDD RED gate for the
      `difficulty_blocks` field + `_setup_rewards` precedence branch + `apply_params` seam.
- [ ] Wave 0 spike: verify the 6 task scenes (`scenes/simple_suturing.json`,
      `knot_tying.json`, `needle_insertion.json`, `grasping.json`, `cutting.json`,
      `dissection.json`) construct + step under `SurgicalEnv` headless on the target host.
      If any abort, design the SC#3 gate as construct-only + log the abort as pre-existing.
- [ ] No framework install needed — pytest + pydantic already installed.

### TDD eligibility (`workflow.tdd_mode = true`)
| Task | TDD? | Rationale |
|------|------|-----------|
| `TaskConfig.difficulty_blocks` field + `model_rebuild()` resolution | `type: tdd` | Defined schema I/O: round-trip + validation; RED test asserts the field accepts 3-level blocks and rejects malformed |
| `_setup_rewards` precedence branch | `type: tdd` | 4-level truth table is the RED gate; defined I/O |
| `apply_params(params)` refactor on 6 task rewards | `type: tdd` (regression-anchored) | Refactor: RED = existing `apply_difficulty` tests stay green + new `apply_params` tests assert composed dict reaches ctor field |
| `compose_difficulty_overrides` reuse | standard (not TDD) | Already TDD-verified by P36-02's 54-case truth table; reused read-only |
| Naming-drift reconciliation (PROJECT.md/STATE.md edits) | standard | Doc edit; verified by grep audit (SC#5) |
| 6×3 fixture regression gate | standard (regression) | Asserts existing scenes still load/step; not new behavior |

### How each success criterion is testably verified
- **SC#1:** Round-trip test: author a scene JSON with `difficulty_blocks` for all 3
  levels, `SceneLoader().load()`, assert `scene.task.difficulty_blocks` is a
  `dict[DifficultyLevel, DifficultyLevelConfig]` with the authored values; assert
  `model_dump()`/JSON re-serialization preserves them. Plus the negative: a scene without
  blocks loads with `difficulty_blocks is None`.
- **SC#2:** Parametrized truth table over (source ∈ {blocks, task_difficulty_level,
  config_difficulty, default}) × (level ∈ {EASY, MEDIUM, HARD}) — for each, construct the
  env with that source configuration and assert (a) `env._task_difficulty` matches the
  expected scalar, (b) when blocks present, the composed params dict (intercept via
  `compose_difficulty_overrides` call or a spy) matches D-06 composition, (c) the reward
  ctor field that `apply_params` maps matches the override value. Plus the
  curriculum-coexistence case (Pitfall 6).
- **SC#3:** `@pytest.mark.parametrize` over the 6 scene files × 3 levels. For each,
  construct `SurgicalEnv(SurgicalEnvConfig(scene_path=..., render_mode=None))` with the
  level set, `env.reset()`, `env.step(action)`, assert no exception and a well-formed
  `(obs, reward, terminated, truncated, info)` tuple. If a scene aborts on the host, fall
  back to construct-only and assert `_setup_rewards` ran (`env._reward_fn is not None`).
- **SC#4:** Load `tests/fixtures/scenes/suturing_difficulty_hard.json` before and after
  the phase; assert `scene.task.difficulty_level == DifficultyLevel.HARD` and
  `float(env._task_difficulty) == 1.0` (the same scalar the v0.4.2 baseline produced).
  Capture the pre-phase scalar in the test for byte-identical comparison.
- **SC#5:** `grep -rn "difficulty_levels" .planning/PROJECT.md .planning/STATE.md
  src/surg_rl/` returns 0 hits (excluding historical milestone archives under
  `.planning/milestones/`). `grep -rn "difficulty_blocks" .planning/PROJECT.md
  .planning/STATE.md src/surg_rl/scene_definition/schema.py` returns the canonical hits.

## Security Domain

`security_enforcement` is not explicitly set in `.planning/config.json` — treat as
enabled. This phase introduces minimal new attack surface: a new optional Pydantic field
on `TaskConfig` (validated by the existing `DifficultyLevelConfig` range validators from
P36-01 — D-07 global union bounds) and an additive branch in `_setup_rewards`. No I/O,
no network, no secrets, no auth. The field IS scene-author input parsed by Pydantic v2
(ASVS V5).

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | Pydantic v2 validation on `difficulty_blocks` (dict key enum membership + `DifficultyLevelConfig` D-07 range validators inherited from P36-01); malformed blocks raise `ValidationError` at scene-load time |
| V6 Cryptography | no | — |

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed `difficulty_blocks` scene authoring (typo / out-of-range override) | Tampering | Pydantic v2 `ValidationError` at `SceneLoader.load` (D-07 range validators on `DifficultyLevelConfig`, P36-01) |
| Pydantic cross-package cycle re-introduced by `schema.py` import | Denial of Service (import failure) | String forward-ref + late import + `model_rebuild()` (Pitfall 4); type field as `dict[DifficultyLevel, DifficultyLevelConfig]` to avoid `dynamics.*` import in `schema.py` |
| `difficulty_blocks` override silently inert (Pitfall 2) | Information Spoofing (author believes hard mode is applied; it is not) | Truth-table test documents the effective override surface; SC#2 asserts the composed dict AND the ctor-field change |

## Sources

### Primary (HIGH confidence)
- `src/surg_rl/scene_definition/schema.py:1087-1121` — `TaskConfig` (current fields:
  `difficulty_level` string forward-ref, `task_type` Literal, `time_limit`); `:1491-1506`
  — the late-import + `model_rebuild()` cycle pattern to extend.
- `src/surg_rl/rl/environment.py:484-521` — `_setup_rewards` (the precedence seam);
  `:79-91` — `SurgicalEnvConfig` fields (NO `difficulty` field — verified this session);
  `:180-245` — `__init__` order (controller → rewards → state); `:262-277` — `_load_scene`
  (lazy `SceneLoader` import pattern to mirror for `compose_difficulty_overrides`).
- `src/surg_rl/dynamics/difficulty_wiring.py:1-135` — P36-02 shipped: `ABSTRACT_TO_CONCRETE`
  (D-05), `DiscreteCurriculumConfig`, `compose_difficulty_overrides` (D-06, D-04).
- `src/surg_rl/rl/difficulty.py:14-97` — P36-01 shipped: `DifficultyLevel` +
  `DifficultyLevelConfig` (leaf, zero in-project imports, D-07 range validators).
- `src/surg_rl/rl/rewards.py:161-184` (base `apply_difficulty` no-op), `:552-557, 696-704,
  714-720, 852-859, 869-874, 999-1006, 1016-1022, 1163-1170, 1180-1186, 1329-1336,
  1346-1352, 1491-1498` — `PARAM_BOUNDS` + `interpolate_params` + `apply_difficulty`
  (one-key-per-task mapping) on all 6 task rewards.
- `src/surg_rl/rl/task_reward_router.py:45-99` — `TaskRewardRouter.build` (constructs
  task reward + calls `apply_difficulty(scalar)`); `TASK_REWARD_REGISTRY` keys.
- `src/surg_rl/scene_definition/loader.py:545-651` — `SceneLoader.load` /
  `load_from_string` (Pydantic v2 validation path; `SceneDefinition(**data)`).
- `src/surg_rl/dynamics/curriculum.py` — P36-03 shipped: `progression_mode`,
  `set_difficulty_level`, `advance_level`, `_meets_success_threshold`,
  `current_difficulty` mode branch (continuous path byte-identical).
- `tests/test_difficulty_levels.py:316-401` — `TestDifficultyIntegration` (the existing
  scene-load + 6-scene regression pattern to mirror); `HARD_FIXTURE` at
  `tests/fixtures/scenes/suturing_difficulty_hard.json`.
- `tests/fixtures/scenes/suturing_difficulty_hard.json:305-307` — `difficulty_level: 1.0`
  (the SC#4 back-compat fixture).
- `scenes/{simple_suturing,knot_tying,needle_insertion,grasping,cutting,dissection}.json`
  — the 6 v0.4.0 task fixtures (all have `task.task_type` set, `task.difficulty_level`
  null, no `difficulty_blocks` — verified this session via JSON parse).
- `.planning/PROJECT.md:23,82` + `.planning/STATE.md:82,131` — naming-drift occurrences
  (`difficulty_levels` at PROJECT.md:82; canonical `difficulty_blocks` elsewhere).
- `.planning/research/PITFALLS.md:100-186` — Pitfalls 4/5/7 (cycle, precedence ambiguity,
  schema migration) — cited.
- `.planning/research/STACK.md:120-144` — `DifficultyLevelConfig` + `difficulty_blocks:
  list[3]` research shape (cited; this research recommends dict-keyed instead, see Open Q3).
- `.planning/config.json` — `nyquist_validation: true`, `tdd_mode: true`.

### Secondary (MEDIUM confidence)
- `.planning/phases/36-.../36-CONTEXT.md` D-01..D-12, `36-RESEARCH.md`, `36-PATTERNS.md`,
  `36-01/02/03-SUMMARY.md` — P36 shipped artifacts (locked decisions + execution
  confirmations).
- `.planning/ROADMAP.md` §"Phase 37" — goal, success criteria (5).

### Tertiary (LOW confidence)
- None — all findings verified against the codebase this session with line numbers.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all primitives exist in codebase (P36 shipped).
- Architecture (schema field + env precedence + reward application seam): HIGH — all
  three seams read with line numbers this session; the `model_rebuild()` pattern is live
  and proven.
- Pitfalls: HIGH — grounded in code reads (`SurgicalEnvConfig` field list, `apply_difficulty`
  one-key mapping, `time_limit` dual ownership, current `_setup_rewards` chain).
- Open Questions: MEDIUM — Q1 (apply_params mapping scope) and Q2 (config.difficulty
  field) are real design decisions the planner must make; Q3 (field shape) and Q4
  (curriculum coexistence) have clear recommendations.
- Validation: HIGH — test framework verified; 6×3 gate host-sensitivity flagged (A5).

**Research date:** 2026-06-24
**Valid until:** 2026-07-24 (stable — internal schema/env-wiring phase, no external API;
P36 artifacts are committed and unlikely to change before this phase lands).
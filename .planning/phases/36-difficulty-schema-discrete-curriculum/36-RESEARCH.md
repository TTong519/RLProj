# Phase 36: Difficulty Schema + Discrete Curriculum - Research

**Researched:** 2026-06-24
**Domain:** Pydantic v2 schema design + curriculum scheduler internals (additive, non-GPU)
**Confidence:** HIGH

## Summary

Phase 36 is a pure schema + curriculum-internals phase that adds two Pydantic v2
models (`DifficultyLevelConfig` leaf + `DiscreteCurriculumConfig` wiring model), a
pure-data abstract→concrete override mapping dict, an additive composition
helper, and an additive `progression_mode` on `CurriculumScheduler`. It touches
no reward surface and no continuous-path scalar. All five success criteria are
verifiable by unit tests against the existing code, which I read in full this
session.

The D-05 abstract→concrete mapping table is **fully validated cell-by-cell**
against the real `PARAM_BOUNDS` keys in `src/surg_rl/rl/rewards.py` — every
non-empty cell maps to a key that exists on the named reward class, and the two
"no coincidence" claims (only `tissue_stiffness` and `time_limit` are literal
keys; `target_precision_tolerance` and `tool_position_noise` match no task's
keys) are confirmed. One wording issue in D-03 ("keyed by `TaskConfig.name`")
conflicts with the codebase: the canonical 6 keys in D-05 are `task_type`
literals (matching `TASK_REWARD_REGISTRY` and `TaskConfig.task_type`), not the
free-form `TaskConfig.name` field. The planner must key the mapping by
`task_type`.

The D-07 range-validation rule has a **critical pitfall**: the literal recipe
"min lo, max hi across the six tasks" produces inverted/nonsensical bounds for
down-family params (`time_limit` → [90, 60]; `target_precision_tolerance` →
[0.01, 0.05] which rejects valid HARD values like 0.002). The correct formula is
`min(all endpoints), max(all endpoints)` over every mapped concrete key. The
four verified global bound pairs are derived below.

**Primary recommendation:** Put `DifficultyLevelConfig` in the existing
`rl/difficulty.py` leaf (extend it; stays zero in-project imports), put
`DiscreteCurriculumConfig` + the mapping dict + the composition helper in a new
`dynamics/difficulty_wiring.py`, and have `curriculum.py` import
`DiscreteCurriculumConfig` one-directionally from there. Validate ranges with
`min/max over all endpoints`, not `min lo / max hi`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** The four override field names are abstract aliases, not literal
  `PARAM_BOUNDS` keys. Only `tissue_stiffness` and `time_limit` coincide with
  real keys (and not on every task); `target_precision_tolerance` and
  `tool_position_noise` match no task's keys. A per-task mapping resolves each
  abstract name to the concrete `PARAM_BOUNDS` key for the loaded task.
- **D-02:** The mapping lives as a pure-data dict in a non-leaf wiring module
  (task-name string → `{abstract_field → concrete PARAM_BOUNDS key string}`),
  co-located with `DiscreteCurriculumConfig`. Recommended:
  `src/surg_rl/dynamics/difficulty_wiring.py` (planner confirms final path).
- **D-03:** The mapping is keyed by `TaskConfig.name` string and populated for
  all six v0.4.0 tasks (suturing, knot_tying, needle_insertion, grasping,
  cutting, dissection). **[RESEARCH FINDING: see Open Question Q1 — D-05's keys
  are `task_type` literals, not `TaskConfig.name`; planner must reconcile.]**
- **D-04:** When a set override field has no mapping for the loaded task, log a
  warning and keep the interpolated value (do not raise).
- **D-05:** The locked per-task abstract→concrete mapping (authoritative — do
  not re-derive):

  | Abstract field | suturing | dissection | needle_insertion | knot_tying | grasping | cutting |
  |---|---|---|---|---|---|---|
  | `tissue_stiffness` | — | `tissue_stiffness` | — | `tissue_stiffness` | — | `tissue_stiffness` |
  | `target_precision_tolerance` | `needle_position_tolerance` | `incision_path_tolerance` | `needle_alignment_tolerance` | `loop_deviation_tolerance` | `approach_tolerance` | `cut_path_accuracy` |
  | `tool_position_noise` | — | — | `action_noise` | `action_noise` | `action_noise` | — |
  | `time_limit` | `time_limit` | `time_limit` | `time_limit` | `time_limit` | `time_limit` | `time_limit` |
- **D-06:** An override value is an ABSOLUTE scalar that REPLACES the
  interpolated value for the mapped concrete key. Composing = compute
  `interpolate_params(level.value)`, then for each set override field replace
  the mapped concrete key's value with the override value. Unoverridden keys
  keep the interpolated value. (Not a delta, not a multiplier.)
- **D-07:** Each override field is range-validated against global bounds
  derived from the union of per-task `PARAM_BOUNDS` for that abstract field.
  **[RESEARCH FINDING: the "min lo, max hi" recipe is broken for down-family —
  use `min/max over all endpoints`. See Pitfall 1 + the validated bounds table
  in Architecture Patterns.]**
- **D-08:** A separate `DiscreteCurriculumConfig` Pydantic model wraps the three
  per-level `DifficultyLevelConfig` instances via
  `levels: dict[DifficultyLevel, DifficultyLevelConfig]` (default empty = pure
  interpolation baseline). It imports `DifficultyLevelConfig` + `DifficultyLevel`,
  so it MUST live in the wiring module, NOT the leaf file.
- **D-09:** `CurriculumConfig` gains
  `progression_mode: Literal["continuous", "discrete"] = "continuous"` and an
  optional reference to `DiscreteCurriculumConfig`. Default `"continuous"` keeps
  v0.5.0 `advance_stage` output byte-identical. `curriculum.py` imports
  `DiscreteCurriculumConfig` one-directionally from the wiring module.
- **D-10:** In `"discrete"` mode the scheduler holds a separate
  `_current_level: DifficultyLevel` whose `.value` (0.0/0.5/1.0) feeds
  `interpolate_params`. The continuous `_current_stage` state and `advance_stage`
  path are left untouched. The `DifficultyLevel` scalars (0.0/0.5/1.0) are
  intentionally distinct from `CurriculumStage` defaults (0.25/0.5/0.75/1.0).
- **D-11:** `advance_level` reuses the existing `_should_advance` success-rate
  gate (`min_success_rate` over `advancement_window`, with
  `difficulty_hysteresis`). One threshold mechanism shared with continuous mode.
  No new episode-count-per-level config field.
- **D-12:** `advance_level` at the top level (HARD) is a no-op returning `False`.
  `set_difficulty_level` accepts a `DifficultyLevel` enum and sets `_current_level`
  directly (manual override).

### Claude's Discretion
- Exact file path for the wiring module (`difficulty_wiring.py` vs extending
  `task_reward_router.py`) — provided the leaf stays solo and import-free.
- Exact truth-table test layout and parametrization, provided it verifies:
  (a) overriding one field changes only that field; (b) unoverridden fields
  retain the interpolated value; (c) empty `levels` dict == pure interpolation.
- Exact validator implementation (`field_validator` vs `model_validator`) for
  the four union-bound ranges.
- Naming of internal `_current_level` field and the `progression_mode` Literal
  values, provided semantics match the decisions.
- Whether `set_difficulty_level` additionally accepts a string and coerces.

### Deferred Ideas (OUT OF SCOPE)
- Scene JSON `difficulty_blocks` authoring + `SurgicalEnv` override-precedence
  chain — Phase 37 (TASK-08).
- Extending the abstract override vocabulary beyond the four locked fields.
- Per-task override of the abstract→concrete mapping itself.
- EXPERT/CUSTOM `DifficultyLevel` entries — discrete path is EASY→MEDIUM→HARD
  only (three levels). EXPERT stays a `CurriculumStage` concept.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TASK-06 | Per-level difficulty overrides (`DifficultyLevelConfig`: tissue_stiffness / target_precision_tolerance / tool_position_noise / time_limit) apply additively over `interpolate_params()` — never replace it | `DifficultyLevelConfig` leaf model (4 optional float fields, range-validated) + composition helper in wiring module; `interpolate_params` confirmed as classmethod on all 6 reward classes returning `{key: lo+(hi-lo)*difficulty}`; D-05 mapping validated cell-by-cell; truth-table test design in Validation Architecture |
| TASK-07 | `CurriculumScheduler` advances through discrete EASY→MEDIUM→HARD levels via an additive `progression_mode` (continuous float `advance_stage` path preserved unchanged) | `CurriculumScheduler`/`CurriculumConfig` shapes captured; `progression_mode` + `DiscreteCurriculumConfig` reference added to config; `set_difficulty_level`/`advance_level` added; `current_difficulty` already normalizes `DifficultyLevel`→float (line 207-210); `advance_stage` left byte-identical |
| TASK-09 | Existing v0.4.0 + v0.4.2 curriculum suite passes unchanged (additive-regression gate) | Existing suites enumerated: `tests/test_difficulty_levels.py` (direction + wiring + integration) and `tests/test_dynamics.py::TestCurriculumScheduler` (stage progression/regression/auto-advance); all additions are additive; `progression_mode` defaults to `"continuous"` |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Pydantic v2:** `Model(**data)` and `model_validate()` both fully validate
  (not different paths). To skip validation use `model_construct` (nested dicts
  stay plain dicts). In `model_validator(mode="after")` use
  `self.model_copy(update={...})`, not mutation. Enum values in `model_dump()`
  stay Enum objects (convert before YAML dump).
- **Leaf-model / late-import + `model_rebuild()` cycle-resolution pattern** is
  project canon (v0.4.2) — `DifficultyLevelConfig` MUST follow it (success
  criterion #5).
- **Gymnasium/SB3:** not relevant to this phase (no env/observation changes).
- **Simulator internals:** not relevant (no simulator edits).
- **Domain randomization controllers:** `EnvironmentController.apply_parameters(
  snapshot, simulator)` is the public API; `ControllerConfig.warmup_episodes`
  (not warmup_steps); `CurriculumScheduler.DEFAULT_STAGES` uses mutable
  dataclass values — always `copy.deepcopy()`, never `dict.copy()`.
- **Imports:** verify opening parens on multi-line imports; never use `sed`/`echo`
  to inject multi-line import blocks — use `Edit`/`python -c pathlib.write_text`.
- **Testing:** `asyncio_mode = auto`; `PYTHONPATH=src` for direct script runs
  (pytest.ini handles it for pytest).
- **Code style:** line length 100; Python ≥3.10; type hints required
  (`mypy disallow_untyped_defs = true`); ruff select E,F,I,N,W,UP,B,C4,SIM
  (ignore E501).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `DifficultyLevelConfig` schema (4 fields + range validation) | Schema (Pydantic leaf, `rl/difficulty.py`) | — | Pure data model; must be import-free leaf so `rewards.py`/`schema.py` import paths stay cycle-free (success criterion #5) |
| Abstract→concrete override mapping dict | Wiring (`dynamics/difficulty_wiring.py`) | — | Pure-data dict keyed by `task_type`; co-located with `DiscreteCurriculumConfig` (D-02/D-08); must NOT live in the leaf |
| `DiscreteCurriculumConfig` schema (levels dict) | Wiring (`dynamics/difficulty_wiring.py`) | — | Imports `DifficultyLevel` + `DifficultyLevelConfig`; cannot be in the leaf (would give the leaf in-project imports) |
| Additive composition (interpolate then override) | Wiring helper (`dynamics/difficulty_wiring.py`) | Reward classes (read-only `interpolate_params`) | Needs `interpolate_params` (classmethod on reward classes) + the mapping; tested via truth table; does NOT mutate reward surfaces |
| `progression_mode` + `set_difficulty_level`/`advance_level` | Curriculum scheduler (`dynamics/curriculum.py`) | — | State machine for EASY→MEDIUM→HARD lives with the existing scheduler; imports `DiscreteCurriculumConfig` one-directionally from wiring |
| Continuous `advance_stage` path | Curriculum scheduler (`dynamics/curriculum.py`) | — | MUST stay byte-identical (additive-regression gate); only read by tests |
| Reward `PARAM_BOUNDS` + `interpolate_params` | Reward classes (`rl/rewards.py`) | — | Additive baseline — DO NOT EDIT (regression gate) |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | v2 (pinned) | `DifficultyLevelConfig` + `DiscreteCurriculumConfig` BaseModel; `field_validator` for ranges | Already project standard; `model_rebuild()` cycle pattern proven in v0.4.2 [VERIFIED: codebase `schema.py:1491-1506`] |
| enum (stdlib) | — | `DifficultyLevel` `_FloatMixin(float, Enum)` reused as `levels` dict key | Existing pattern `rl/difficulty.py` [VERIFIED: codebase] |
| dataclasses (stdlib) | — | `CurriculumConfig` is a `@dataclass` — `progression_mode` field added there | Existing `dynamics/curriculum.py` [VERIFIED: codebase] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| typing.Literal | stdlib | `progression_mode: Literal["continuous","discrete"]` | D-09 |
| pytest | dev | truth-table parametrized tests; regression gate | Validation Architecture |

No new packages are installed in this phase. All dependencies are already
pinned. `[VERIFIED: codebase — no new imports required beyond stdlib + pydantic]`

**Installation:** None — `pip install -e ".[dev]"` already covers everything.

**Version verification:** Not applicable (no new packages).

## Package Legitimacy Audit

No external packages are installed in this phase. The audit is skipped — only
stdlib (`enum`, `dataclasses`, `typing`) and the already-pinned `pydantic` v2
are used. `[VERIFIED: codebase grep — no new third-party imports needed]`

## Architecture Patterns

### System Architecture Diagram

```
                        +-----------------------------+
                        |  rl/difficulty.py (LEAF)    |
                        |  DifficultyLevel (Enum)     |   zero in-project imports
                        |  DifficultyLevelConfig (NEW)|   (pydantic + stdlib only)
                        +-----------------------------+
                              ^           ^
            imports DifficultyLevel   imports DifficultyLevel + DifficultyLevelConfig
                              |           |
+-----------------------------+           +------------------------------------+
| dynamics/difficulty_wiring.py (NEW)            |   rl/task_reward_router.py        |
|  ABSTRACT_TO_CONCRETE: dict[task_type, ...]    |   TASK_REWARD_REGISTRY            |
|  DiscreteCurriculumConfig (Pydantic)           |   (task_type -> reward class)     |
|  compose_difficulty_overrides(task_type,level, +--> interpolate_params() on reward  |
|         config, reward_cls) -> dict            |   cls (read-only; NOT edited)     |
+-----------------------------+                  +-----------------------------------+
                              |
            imports DiscreteCurriculumConfig (one-directional)
                              v
+-----------------------------+
| dynamics/curriculum.py      |
|  CurriculumConfig (+progression_mode, +DiscreteCurriculumConfig ref)  |
|  CurriculumScheduler (+_current_level, +set_difficulty_level,         |
|                       +advance_level, current_difficulty branches)    |
|  advance_stage / _should_advance  -- UNTOUCHED (regression gate)      |
+-----------------------------+

Decision points:
  progression_mode == "continuous"  ->  advance_stage path (v0.5.0 byte-identical)
  progression_mode == "discrete"    ->  _current_level.value feeds interpolate_params
                                        advance_level reuses success-rate gate
```

### Recommended Project Structure
```
src/surg_rl/
├── rl/
│   └── difficulty.py            # EXTEND: add DifficultyLevelConfig (leaf, import-free)
├── dynamics/
│   ├── difficulty_wiring.py     # NEW: mapping dict + DiscreteCurriculumConfig + compose helper
│   └── curriculum.py            # EDIT (additive): progression_mode + level methods
└── ... (no other edits)
tests/
├── test_difficulty_config.py    # NEW: DifficultyLevelConfig validation + truth table
└── test_discrete_curriculum.py  # NEW: set/advance_level + regression parity
```

### Pattern 1: Leaf model + late-import + `model_rebuild()` (v0.4.2 cycle pattern)
**What:** A Pydantic model that must be importable from a package that would
otherwise create a cross-package import cycle is kept in a zero-in-project-import
leaf file. Downstream modules use `from __future__ import annotations` + string
forward refs, then import the leaf name at module bottom and call
`model_rebuild()` to resolve the forward ref.
**When to use:** Whenever a Pydantic model is referenced across the
`scene_definition` ↔ `rl` ↔ `dynamics` boundary.
**Source:** `src/surg_rl/scene_definition/schema.py:1491-1506` [VERIFIED: codebase]
```python
# schema.py bottom (the canonical pattern):
# Phase 29 (D-SCHEMA-01): Late import of DifficultyLevel to break the
# surg_rl.scene_definition.schema -> surg_rl.rl -> ... -> schema import cycle.
# With `from __future__ import annotations` + string annotation on
# TaskConfig.difficulty_level, the type is not resolved at class body time.
from surg_rl.rl.difficulty import (  # noqa: E402
    DifficultyLevel,
)  # noqa: F401 — module-level binding for forward ref resolution
TaskConfig.model_rebuild()
```
For Phase 36: `DifficultyLevelConfig` lives in `rl/difficulty.py` (the existing
leaf). `DiscreteCurriculumConfig` (in `dynamics/difficulty_wiring.py`) imports
`DifficultyLevel` + `DifficultyLevelConfig` normally — no forward ref needed
because `dynamics.difficulty_wiring` importing `rl.difficulty` is a one-way edge
(rl.difficulty imports nothing in-project). `curriculum.py` imports
`DiscreteCurriculumConfig` from `difficulty_wiring` — also one-way
(`difficulty_wiring` does not import `curriculum`). **No cycle is created.**
[VERIFIED: codebase import graph — `rl/difficulty.py` has zero in-project
imports; `dynamics/curriculum.py` already imports `from surg_rl.rl.difficulty
import DifficultyLevel` at line 14 with no cycle]

### Pattern 2: Additive composition (interpolate-then-override)
**What:** Compute the interpolated baseline dict, then for each SET override
field replace the mapped concrete key's value with the absolute override value.
**Source:** D-06 + `interpolate_params` classmethod [VERIFIED: codebase
`rewards.py` lines 676-681, 836-841, 983-988, 1147-1152, 1313-1318, 1475-1480]
```python
# interpolate_params (DO NOT EDIT — the additive baseline):
@classmethod
def interpolate_params(cls, difficulty: float) -> dict[str, float]:
    return {
        name: bounds[0] + (bounds[1] - bounds[0]) * difficulty
        for name, bounds in cls.PARAM_BOUNDS.items()
    }

# compose (NEW, in difficulty_wiring.py):
def compose_difficulty_overrides(
    task_type: str,
    level: DifficultyLevel,
    config: DifficultyLevelConfig,
    reward_cls: type[BaseRewardFunction] | None = None,
) -> dict[str, float]:
    # 1. baseline = interpolate_params(level.value) on the task's reward class
    # 2. for each set override field on config, look up concrete key via
    #    ABSTRACT_TO_CONCRETE[task_type].get(abstract_field); if missing -> warn (D-04)
    # 3. replace that key's value with config.<field> (absolute, D-06)
    # 4. return the composed dict (unoverridden keys retain interpolated value)
```

### Pattern 3: `_FloatMixin(float, Enum)` for DifficultyLevel
**Source:** `src/surg_rl/rl/difficulty.py:17-50` [VERIFIED: codebase]
```python
class _FloatMixin(float, Enum):
    """Enum whose members are also float instances (DifficultyLevel.EASY == 0.0)."""

class DifficultyLevel(_FloatMixin):
    EASY = 0.0
    MEDIUM = 0.5
    HARD = 1.0
```
`DiscreteCurriculumConfig.levels: dict[DifficultyLevel, DifficultyLevelConfig]`
uses this enum directly as the dict key. Pydantic v2 validates enum membership
by the float value.

### Anti-Patterns to Avoid
- **Editing `interpolate_params` or any `PARAM_BOUNDS`** — breaks the
  additive-regression gate (success criterion #4) and TASK-09. The four abstract
  fields map onto EXISTING keys; no reward surface is edited.
- **Aligning `DifficultyLevel` scalars (0.0/0.5/1.0) with `CurriculumStage`
  defaults (0.25/0.5/0.75/1.0)** — they are intentionally distinct (D-10);
  "fixing" the mismatch perturbs the continuous path.
- **Putting `DiscreteCurriculumConfig` in `rl/difficulty.py`** — it imports
  `DifficultyLevel` + `DifficultyLevelConfig`, which would give the leaf
  in-project imports (it already imports `DifficultyLevel` from the same file,
  but `DifficultyLevelConfig` is fine; the real issue is `DiscreteCurriculumConfig`
  conceptually belongs to the dynamics/wiring layer and D-08 explicitly forbids
  it in the leaf file). [CITED: CONTEXT.md D-08]
- **Using `min lo, max hi` for D-07 range validation** — broken for down-family
  params (see Pitfall 1).
- **Sharing `_current_stage` state between continuous and discrete paths** —
  D-10 requires separate `_current_level` state.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Float-equal enum members | Custom `__eq__` | `_FloatMixin(float, Enum)` (existing) | Already implemented + tested; `DifficultyLevel.EASY == 0.0` works |
| Difficulty→parameter interpolation | New interpolation in the wiring module | `reward_cls.interpolate_params(level.value)` (existing classmethod) | The additive baseline; reusing it is success criterion #2; never recompute |
| Cross-package forward-ref resolution | Manual `__pydantic_internal__` hacks | `from __future__ import annotations` + late import + `model_rebuild()` | Proven v0.4.2 pattern; avoids the cycle that bit v0.4.2 |
| Success-rate advancement gate | New threshold logic for `advance_level` | Reuse the success-rate computation from `_should_advance` (D-11) | One threshold mechanism; keeps continuous path byte-identical |
| Reward class lookup by task | New registry | `TASK_REWARD_REGISTRY` in `task_reward_router.py` (existing) | Already maps the 6 `task_type` strings → reward classes |

**Key insight:** Every primitive this phase needs already exists in the
codebase (`interpolate_params`, `DifficultyLevel`, `TASK_REWARD_REGISTRY`,
`_should_advance`'s success-rate computation, the `model_rebuild()` pattern).
The phase is pure assembly of existing primitives into two new Pydantic models
+ one wiring dict + three scheduler methods. No algorithm is invented.

## Common Pitfalls

### Pitfall 1: D-07 "min lo, max hi" breaks for down-family params
**What goes wrong:** `PARAM_BOUNDS` stores `[lo, hi]` where EASY=lo, HARD=hi.
For down-family params (tolerances, `time_limit`) the EASY value is LARGER than
the HARD value (e.g. `time_limit: [120.0, 45.0]` — more time at EASY). The
literal D-07 recipe "min lo, max hi across the six tasks" yields:
- `time_limit` → min lo = 90.0, max hi = 60.0 → the "range" [90, 60] is
  inverted; `lo <= v <= hi` rejects every value.
- `target_precision_tolerance` → min lo = 0.01, max hi = 0.05 → [0.01, 0.05]
  rejects valid HARD values like 0.002 (suturing needle_position_tolerance HARD)
  and valid EASY values like 0.3 (needle_alignment_tolerance EASY).
**Why it happens:** D-07's wording assumed up-family semantics (lo < hi). Two of
the four abstract fields are down-family.
**How to avoid:** Compute global bounds as **`min(all endpoints), max(all
endpoints)`** over every concrete key the abstract field maps to (both `lo` AND
`hi` from each pair). This is direction-agnostic.
**Warning signs:** A validator that rejects `time_limit=45.0` (a legitimate HARD
suturing value) or `target_precision_tolerance=0.002`.

**Verified global bounds (use these — computed from real `PARAM_BOUNDS`):**

| Abstract field | Concrete keys (task → key) | All endpoints | Global bounds (min, max) |
|---|---|---|---|
| `tissue_stiffness` (up) | dissection/knot_tying/cutting `tissue_stiffness` | {50, 200, 50, 200, 50, 300} | **[50.0, 300.0]** |
| `target_precision_tolerance` (down) | 6 keys (see D-05 row 2) | {0.02, 0.002, 0.01, 0.002, 0.3, 0.05, 0.03, 0.005, 0.05, 0.005, 0.01, 0.002} | **[0.002, 0.3]** |
| `tool_position_noise` (up) | needle_insertion/knot_tying/grasping `action_noise` | {0.01, 0.06, 0.01, 0.08, 0.01, 0.06} | **[0.01, 0.08]** |
| `time_limit` (down) | all 6 tasks `time_limit` | {120, 45, 180, 60, 90, 30, 120, 45, 90, 30, 120, 60} | **[30.0, 180.0]** |

[VERIFIED: codebase `rewards.py` PARAM_BOUNDS — values read lines 552-557,
714-720, 869-874, 1016-1022, 1180-1186, 1346-1352]

Note: `tissue_stiffness` and `tool_position_noise` only map to 3 of the 6 tasks
(D-05 empty cells), so "across the six tasks" in D-07 is loose wording — it is
across the tasks where the abstract field has a mapping.

### Pitfall 2: D-03 "keyed by `TaskConfig.name`" vs `task_type`
**What goes wrong:** `TaskConfig.name` is a free-form "Task name" string (e.g.
`"suturing_task"` in `test_difficulty_levels.py:283`), NOT one of the 6
canonical task identifiers. D-05's table headers (`suturing`, `dissection`,
`needle_insertion`, `knot_tying`, `grasping`, `cutting`) are exactly the
`TaskConfig.task_type` Literal values and the `TASK_REWARD_REGISTRY` keys.
**Why it happens:** Wording slip in D-03.
**How to avoid:** Key `ABSTRACT_TO_CONCRETE` by `task_type` (the Literal), not
`TaskConfig.name`. The composition helper receives `task_type` (already
available on every `TaskConfig` and already used by `TaskRewardRouter`).
**Warning signs:** A mapping keyed by `TaskConfig.name` would miss every real
scene (whose `name` is arbitrary) and the truth-table test would never hit a
non-empty mapping.

### Pitfall 3: `_should_advance` is stage-coupled
**What goes wrong:** D-11 says `advance_level` "reuses the existing
`_should_advance` success-rate gate". But `_should_advance` (`curriculum.py:470-
508`) is hardwired to the continuous stage path: it reads
`self._stages[self._current_stage].success_threshold`,
`stage_cfg.episode_threshold`, and checks `self._stage_order.index(...)`. It
does not accept a threshold argument and does not know about `DifficultyLevel`.
**Why it happens:** `_should_advance` was written for the 4-stage continuous
path; discrete levels have no per-level `episode_threshold` (D-11: no new
config field) and no `CurriculumStage`.
**How to avoid:** Extract a thin shared helper
`_meets_success_threshold(threshold: float) -> bool` that computes
`success_rate over advancement_window` and compares to `threshold` (using
`difficulty_hysteresis` exactly as `_should_regress` does at lines 564-568).
`_should_advance` calls it with `stage_cfg.success_threshold`; `advance_level`
calls it with `curriculum_config.min_success_rate`. This satisfies D-11's "one
threshold mechanism shared" without perturbing the continuous path (the
extracted helper is a pure refactor — `_should_advance`'s observable output is
unchanged, preserving the regression gate).
**Warning signs:** `advance_level` silently inheriting the current continuous
stage's `episode_threshold`/`success_threshold` (stage-dependent, not
level-appropriate), or duplicating the success-rate arithmetic.

### Pitfall 4: `CurriculumConfig` is a dataclass, not a Pydantic model
**What goes wrong:** `progression_mode` and the `DiscreteCurriculumConfig`
reference are added to `CurriculumConfig` (`curriculum.py:64-86`), which is a
`@dataclass`, not a `BaseModel`. A Pydantic model field (`DiscreteCurriculumConfig`)
held on a dataclass is fine, but the planner must use dataclass field syntax
(`field(default_factory=...)` / `Optional[...] = None`), not Pydantic `Field(...)`.
**How to avoid:** Add `progression_mode: Literal["continuous","discrete"] =
"continuous"` and `discrete_config: DiscreteCurriculumConfig | None = None` as
plain dataclass fields. Default `"continuous"` + `None` keeps v0.5.0 behavior.
**Warning signs:** Using `pydantic.Field(default=...)` inside a `@dataclass`
that does not use `pydantic.dataclasses`.

### Pitfall 5: Enum values in `model_dump()` / YAML
**What goes wrong:** Per CLAUDE.md, Enum values in `model_dump()` stay as Enum
objects. If `DiscreteCurriculumConfig` is ever serialized to YAML (Phase 37
scene JSON), the `DifficultyLevel` dict keys would raise
`yaml.RepresenterError`.
**How to avoid:** Not a Phase 36 concern (no scene JSON authoring — deferred to
Phase 37), but the planner should keep `DifficultyLevelConfig` fields as plain
`float | None` (not enums) so the model is serialization-safe from the start.
**Warning signs:** Any enum-typed override field.

## Code Examples

### `interpolate_params` — the additive baseline (DO NOT EDIT)
[VERIFIED: codebase `rewards.py:676-681` — identical classmethod on all 6 task reward classes]
```python
@classmethod
def interpolate_params(cls, difficulty: float) -> dict[str, float]:
    return {
        name: bounds[0] + (bounds[1] - bounds[0]) * difficulty
        for name, bounds in cls.PARAM_BOUNDS.items()
    }
```
`difficulty` is a scalar in `[0.0, 1.0]` (0.0=EASY, 1.0=HARD). Returns a dict
keyed by the class's `PARAM_BOUNDS` keys. This is the baseline the override
composition builds on (D-06).

### `current_difficulty` — already normalizes DifficultyLevel→float
[VERIFIED: codebase `curriculum.py:207-210`]
```python
@property
def current_difficulty(self) -> float:
    d = self._stages[self._current_stage].difficulty
    return float(d.value) if isinstance(d, DifficultyLevel) else float(d)
```
In discrete mode this property should branch on `progression_mode` and return
`float(self._current_level.value)`.

### `DifficultyLevel` leaf (extend with `DifficultyLevelConfig`)
[VERIFIED: codebase `rl/difficulty.py:14-50`]
```python
from enum import Enum
from typing import Optional
from pydantic import BaseModel, field_validator

class _FloatMixin(float, Enum): ...
class DifficultyLevel(_FloatMixin):
    EASY = 0.0
    MEDIUM = 0.5
    HARD = 1.0

# NEW (same file — stays import-free; pydantic + stdlib only):
class DifficultyLevelConfig(BaseModel):
    """Per-level override config (success criterion #1). Leaf: zero in-project imports."""
    tissue_stiffness: Optional[float] = None
    target_precision_tolerance: Optional[float] = None
    tool_position_noise: Optional[float] = None
    time_limit: Optional[float] = None

    @field_validator("tissue_stiffness")
    @classmethod
    def _check_tissue(cls, v):
        if v is not None and not (50.0 <= v <= 300.0):
            raise ValueError("tissue_stiffness out of global union bounds [50.0, 300.0]")
        return v
    # ... analogous for the other three using the verified bounds above
```

### `DiscreteCurriculumConfig` + mapping (NEW, in `dynamics/difficulty_wiring.py`)
```python
from surg_rl.rl.difficulty import DifficultyLevel, DifficultyLevelConfig
from pydantic import BaseModel, Field

# D-05 mapping (validated cell-by-cell against rewards.py PARAM_BOUNDS).
# Keyed by task_type (NOT TaskConfig.name — see Pitfall 2).
ABSTRACT_TO_CONCRETE: dict[str, dict[str, str]] = {
    "suturing":         {"target_precision_tolerance": "needle_position_tolerance",
                         "time_limit": "time_limit"},
    "dissection":       {"tissue_stiffness": "tissue_stiffness",
                         "target_precision_tolerance": "incision_path_tolerance",
                         "time_limit": "time_limit"},
    "needle_insertion": {"target_precision_tolerance": "needle_alignment_tolerance",
                         "tool_position_noise": "action_noise",
                         "time_limit": "time_limit"},
    "knot_tying":       {"tissue_stiffness": "tissue_stiffness",
                         "target_precision_tolerance": "loop_deviation_tolerance",
                         "tool_position_noise": "action_noise",
                         "time_limit": "time_limit"},
    "grasping":         {"target_precision_tolerance": "approach_tolerance",
                         "tool_position_noise": "action_noise",
                         "time_limit": "time_limit"},
    "cutting":          {"tissue_stiffness": "tissue_stiffness",
                         "target_precision_tolerance": "cut_path_accuracy",
                         "time_limit": "time_limit"},
}

class DiscreteCurriculumConfig(BaseModel):
    levels: dict[DifficultyLevel, DifficultyLevelConfig] = Field(default_factory=dict)
    # default empty == pure interpolate_params(level.value) baseline (D-08)
```

### Scheduler additions (additive — `curriculum.py`)
```python
# In CurriculumConfig (dataclass):
progression_mode: Literal["continuous", "discrete"] = "continuous"
discrete_config: Optional["DiscreteCurriculumConfig"] = None  # late import + model_rebuild

# In CurriculumScheduler.__init__ (additive):
self._current_level: DifficultyLevel = DifficultyLevel.EASY
self._level_entry_episode: int = 0

# New methods:
def set_difficulty_level(self, level: DifficultyLevel) -> None: ...
def advance_level(self) -> bool: ...  # EASY->MEDIUM->HARD; HARD->False (D-12)

# current_difficulty branches on progression_mode
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Float-only difficulty scalar | `DifficultyLevel` float-mixin enum + float path coexist | v0.4.2 (Phase 29) | Enum validated at schema boundary; scalar used downstream — `DifficultyLevelConfig` extends this with per-level overrides |
| `create_default_reward` string matching | `TaskRewardRouter` + `TASK_REWARD_REGISTRY` | v0.4.0 (Phase 27/29) | Reward class lookup by `task_type` — the wiring mapping reuses the same 6 keys |
| `advance_stage` continuous 4-stage | + additive `progression_mode` discrete 3-level | Phase 36 (this) | Two independent axes; continuous path byte-identical |

**Deprecated/outdated:**
- `create_default_reward`'s `if "sutur" in task_lower` matching is superseded by
  the registry but still exists — not this phase's concern.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `DifficultyLevelConfig` can co-locate in `rl/difficulty.py` and remain a leaf (pydantic + stdlib only) | Standard Stack / Architecture | LOW — pydantic is external; verified `rl/difficulty.py` currently imports only `enum` |
| A2 | `dynamics.difficulty_wiring` importing `rl.difficulty` + (optionally) `rl.task_reward_router` creates no cycle | Architecture Patterns | LOW — verified `rl.difficulty` and `rl.task_reward_router` import nothing from `dynamics` |
| A3 | `advance_level`'s success-rate gate should use `curriculum_config.min_success_rate` (config-level), not a per-stage threshold | Pitfall 3 / Open Q2 | MEDIUM — D-11 says reuse `_should_advance`'s gate but that is stage-coupled; needs planner decision |
| A4 | `advance_level` needs no episode-count gate (D-11 forbids a new field) | Pitfall 3 | MEDIUM — could reuse current stage's `episode_threshold`; see Open Q2 |

All other claims are `[VERIFIED: codebase]` (read this session with line numbers)
or `[CITED: CONTEXT.md]` (locked decisions).

## Open Questions (RESOLVED — via Phase 36 plans 01/02/03; user-confirmed 2026-06-24)

1. **D-03 key source: `TaskConfig.name` vs `task_type`**
   - What we know: D-05's 6 column headers exactly match `task_type` Literal
     values and `TASK_REWARD_REGISTRY` keys. `TaskConfig.name` is free-form
     (`"suturing_task"` in tests).
   - What's unclear: whether the user meant the canonical `task_type` or really
     wants the mapping keyed by the arbitrary `name` field (which would make the
     mapping unmatchable in practice).
   - Recommendation: Key by `task_type`. Flag for confirmation at plan time.
     This is a locked-decision wording issue, not a re-derivation — the mapping
     cells (D-05) are authoritative and validated.
   - **RESOLVED (user-confirmed 2026-06-24, Plan 02):** Key by `task_type` — `ABSTRACT_TO_CONCRETE` in `dynamics/difficulty_wiring.py` is keyed by `task_type` (the `Literal` / `TASK_REWARD_REGISTRY` keys: suturing, knot_tying, needle_insertion, grasping, cutting, dissection), NOT `TaskConfig.name`.

2. **`advance_level` gate composition (D-11)**
   - What we know: `_should_advance` is stage-coupled (uses
     `stage_cfg.success_threshold` + `episode_threshold` + `_stage_order`).
     D-11 says reuse the success-rate gate; D-11 forbids a new
     episode-count-per-level config field.
   - What's unclear: whether `advance_level` should (a) reuse only the
     success-rate portion (via an extracted `_meets_success_threshold(threshold)`
     helper using `curriculum_config.min_success_rate`), or (b) also inherit the
     current continuous stage's `episode_threshold`.
   - Recommendation: Option (a) — extract the shared helper, call it with
     `curriculum_config.min_success_rate`, skip the episode-count gate for
     levels (or track `_level_entry_episode` and reuse the current stage's
     `episode_threshold` if a gate is desired). The extracted helper is a pure
     refactor that preserves `_should_advance`'s observable output (regression-
     safe). Planner to confirm.
   - **RESOLVED (user-confirmed 2026-06-24, Plan 03):** Option (a) — extract `_meets_success_threshold(threshold: float) -> bool` (pure refactor; `_should_advance` calls it with `stage_cfg.success_threshold`, observable output unchanged → regression-safe); `advance_level` calls it with `curriculum_config.min_success_rate`; no new episode-count-per-level config field.

3. **Wiring-module path (Claude's Discretion)**
   - What we know: D-02 recommends `dynamics/difficulty_wiring.py`;
     `task_reward_router.py` is the alternative.
   - Recommendation: `dynamics/difficulty_wiring.py`. Rationale: keeps
     `DiscreteCurriculumConfig` in the dynamics layer next to its only consumer
     (`curriculum.py`); avoids `dynamics` → `rl.task_reward_router` cross-layer
     coupling; the composition helper can accept `reward_cls` (or the
     interpolated dict) as a parameter so the wiring module need not import
     `task_reward_router` at all (the test/truth-table resolves the reward class
     via `TASK_REWARD_REGISTRY` directly).
   - **RESOLVED (user-confirmed 2026-06-24, Plan 02):** `dynamics/difficulty_wiring.py` with `reward_cls` accepted as a parameter — the wiring module does NOT import `task_reward_router`; the truth-table test resolves the reward class via `TASK_REWARD_REGISTRY` directly.

## Environment Availability

Step 2.6: SKIPPED — pure code/config/schema phase with no external tools,
services, runtimes, or CLI utilities beyond the project's existing Python +
pytest. No GPU, no databases, no simulators are exercised by this phase's tests.

## Validation Architecture

`workflow.nyquist_validation` is **true** in `.planning/config.json` (verified).
`workflow.tdd_mode` is also **true** — TDD-eligible tasks are flagged below.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (via `pytest.ini`; `pythonpath = src`, `asyncio_mode = auto`) |
| Config file | `pytest.ini` |
| Quick run command | `PYTHONPATH=src pytest tests/test_difficulty_levels.py tests/test_dynamics.py tests/test_difficulty_config.py tests/test_discrete_curriculum.py -v` |
| Full suite command | `PYTHONPATH=src pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TASK-06 / SC#1 | `DifficultyLevelConfig` accepts 4 fields, validates types + ranges (rejects out-of-bounds) | unit (TDD) | `PYTHONPATH=src pytest tests/test_difficulty_config.py -v` | ❌ Wave 0 (new) |
| TASK-06 / SC#2 | Additive truth table: override one field → only that field differs; unoverridden fields == interpolated; empty `levels` == pure interpolation | unit (TDD, parametrized) | `PYTHONPATH=src pytest tests/test_difficulty_config.py::test_compose_truth_table -v` | ❌ Wave 0 (new) |
| TASK-06 / SC#2 | D-04: override with no mapping for task → warns + keeps interpolated value (no raise) | unit | `PYTHONPATH=src pytest tests/test_difficulty_config.py::test_unmapped_override_warns -v` | ❌ Wave 0 |
| TASK-07 / SC#3 | `set_difficulty_level` sets `_current_level`; `advance_level` EASY→MEDIUM→HARD→False | unit (TDD) | `PYTHONPATH=src pytest tests/test_discrete_curriculum.py -v` | ❌ Wave 0 (new) |
| TASK-07 / SC#3 | `advance_stage` continuous path byte-identical to v0.5.0 (regression parity) | unit | `PYTHONPATH=src pytest tests/test_discrete_curriculum.py::test_advance_stage_unchanged tests/test_dynamics.py::TestCurriculumScheduler -v` | ✅ (test_dynamics.py exists; parity test new) |
| TASK-07 / SC#3 | `progression_mode="continuous"` is default; `current_difficulty` returns stage scalar in continuous, level scalar in discrete | unit | `PYTHONPATH=src pytest tests/test_discrete_curriculum.py::test_current_difficulty_mode_branch -v` | ❌ Wave 0 |
| TASK-09 / SC#4 | Full v0.4.0 + v0.4.2 curriculum + difficulty suite passes unchanged | regression | `PYTHONPATH=src pytest tests/test_difficulty_levels.py tests/test_dynamics.py -v` | ✅ (existing — must stay green) |
| SC#5 | `DifficultyLevelConfig` is a zero-in-project-import leaf (no `surg_rl.*` imports) | unit (import audit) | `PYTHONPATH=src pytest tests/test_difficulty_config.py::test_leaf_no_inproject_imports -v` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** quick run command above (the 4 files).
- **Per wave merge:** `PYTHONPATH=src pytest tests/ -v` (full suite).
- **Phase gate:** Full suite green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_difficulty_config.py` — covers SC#1, SC#2 (truth table), D-04,
      SC#5 (leaf import audit). TDD RED gate for the `DifficultyLevelConfig`
      model + composition helper.
- [ ] `tests/test_discrete_curriculum.py` — covers SC#3 (set/advance level,
      `advance_stage` parity, `current_difficulty` mode branch). TDD RED gate
      for the scheduler additions.
- [ ] No framework install needed — pytest + pydantic already installed.

### TDD eligibility (`workflow.tdd_mode = true`)
| Task | TDD? | Rationale |
|------|------|-----------|
| `DifficultyLevelConfig` model + range validators | `type: tdd` | Algorithmic I/O: defined field types + bounds; RED test asserts rejection of out-of-range values |
| Additive composition helper | `type: tdd` | Transformation with defined I/O: truth table is the RED gate (override one field → only that field changes) |
| `advance_level` / `set_difficulty_level` | `type: tdd` | State-machine transition with defined I/O: EASY→MEDIUM→HARD→False |
| Abstract→concrete mapping dict | standard (not TDD) | Pure data; verified by the truth-table test consuming it, not by its own RED test |
| `DiscreteCurriculumConfig` Pydantic model | standard | Thin schema wrapper; covered by composition tests |
| `progression_mode` field + `current_difficulty` branch | standard | Glue/wiring; covered by scheduler tests |
| `model_rebuild()` / leaf placement | standard | Structural; covered by SC#5 import-audit test |

### How each success criterion is testably verified
- **SC#1:** Unit test constructs `DifficultyLevelConfig` with each field in-range
  (passes) and out-of-range (raises `ValidationError`); type test rejects
  non-float. TDD RED: write the rejection tests first.
- **SC#2:** Parametrized truth-table test over the 6 `task_type`s × 4 abstract
  fields × {EASY, MEDIUM, HARD}. For each (task, level, single-field-override):
  assert the composed dict differs from pure `interpolate_params(level.value)`
  ONLY on the mapped concrete key; all other keys equal. Plus the empty-`levels`
  case: `compose(..., config=DiscreteCurriculumConfig()) == interpolate_params(...)`.
- **SC#3:** (a) Construct a `CurriculumScheduler` with
  `progression_mode="continuous"` and snapshot `advance_stage` outputs/scalars
  at each stage; assert identical to a v0.5.0 baseline (regression parity —
  reuse `TestCurriculumScheduler::test_stage_progression`). (b) Construct one
  with `progression_mode="discrete"`, call `set_difficulty_level`/`advance_level`,
  assert EASY→MEDIUM→HARD→False and `current_difficulty` == `_current_level.value`.
- **SC#4:** `PYTHONPATH=src pytest tests/test_difficulty_levels.py tests/test_dynamics.py`
  runs the existing v0.4.0 + v0.4.2 suites unchanged (additive — no edits to
  those files).
- **SC#5:** Import-audit test: import `surg_rl.rl.difficulty` as a module,
  introspect its AST / `sys.modules` sources, assert no `from surg_rl.` / `import
  surg_rl.` import statements appear in the module source. (Or simpler: a test
  that grep's the file source for `surg_rl.` and asserts zero matches outside
  comments.) Plus: a test that `DiscreteCurriculumConfig` imports succeed from
  `dynamics.difficulty_wiring` without triggering a cycle (import both
  `curriculum` and `schema` in the same test process — the v0.4.2 cycle would
  surface as `ImportError`/`RecursionError`).

## Security Domain

`security_enforcement` is not explicitly set in `.planning/config.json` — per
the protocol, treat as enabled. However, this phase introduces no new attack
surface: it adds pure data-validation Pydantic models and additive scheduler
methods with no I/O, no network, no secrets, no auth, no external input parsing
beyond Pydantic field validation (which IS the ASVS V5 input-validation
control). No new cryptography, sessions, or access control.

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — (no auth in this phase) |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | Pydantic v2 `field_validator` range checks on the 4 override fields (D-07) — this IS the input-validation control; out-of-range values raise `ValidationError` |
| V6 Cryptography | no | — |

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Out-of-range override authoring (researcher typo) | Tampering | Pydantic range validators reject at schema time (D-07) |
| Pydantic cross-package cycle (regression) | Denial of Service (import failure) | Leaf-module placement + `model_rebuild()` pattern (v0.4.2) |

## Sources

### Primary (HIGH confidence)
- `src/surg_rl/rl/rewards.py` — `PARAM_BOUNDS` for all 6 task reward classes
  (lines 552-557, 714-720, 869-874, 1016-1022, 1180-1186, 1346-1352) and
  `interpolate_params` classmethod (lines 676-681 et al.) — read in full.
- `src/surg_rl/rl/difficulty.py` — `DifficultyLevel` + `_FloatMixin` (lines
  14-50); confirmed zero in-project imports (leaf).
- `src/surg_rl/dynamics/curriculum.py` — `CurriculumStage`, `CurriculumConfig`,
  `CurriculumScheduler` (`advance_stage`, `_should_advance`, `current_difficulty`,
  `sample_parameters`) — read in full (lines 1-617).
- `src/surg_rl/rl/task_reward_router.py` — `TASK_REWARD_REGISTRY` keys (the 6
  `task_type` literals); `DifficultyLevel`→float normalization (lines 56-66).
- `src/surg_rl/scene_definition/schema.py:1087-1122` — `TaskConfig` (`name` is
  free-form, `task_type` is the Literal, `difficulty_level` is the string
  forward-ref field) and `schema.py:1491-1506` — the `model_rebuild()` cycle
  pattern.
- `tests/test_difficulty_levels.py` — existing direction + wiring + integration
  tests (the additive-regression gate for SC#4).
- `tests/test_dynamics.py:336-487` — `TestCurriculumScheduler` (continuous-path
  regression suite).
- `.planning/config.json` — `nyquist_validation: true`, `tdd_mode: true`.

### Secondary (MEDIUM confidence)
- `.planning/phases/36-.../36-CONTEXT.md` — locked decisions D-01..D-12 (cited).
- `.planning/STATE.md` — v0.4.2 Pydantic cycle risk; naming-drift note
  (`difficulty_blocks` canonical).

### Tertiary (LOW confidence)
- None — all findings verified against the codebase this session.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all primitives exist in codebase.
- Architecture (leaf/wiring/curriculum split): HIGH — import graph verified;
  one-way edges confirmed.
- D-05 mapping: HIGH — every cell validated against real `PARAM_BOUNDS` keys.
- D-07 global bounds: HIGH — values computed from real `PARAM_BOUNDS`; the
  "min lo/max hi" pitfall is the one place D-07's wording is wrong.
- Pitfalls: HIGH — all grounded in code reads with line numbers.
- Open Questions: MEDIUM — Q1 (D-03 wording) and Q2 (advance_level gate) need
  planner/user confirmation.

**Research date:** 2026-06-24
**Valid until:** 2026-07-24 (stable — internal schema phase, no external API).
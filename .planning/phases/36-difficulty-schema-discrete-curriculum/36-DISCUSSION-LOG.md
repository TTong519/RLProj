# Phase 36: Difficulty Schema + Discrete Curriculum - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-24
**Phase:** 36-difficulty-schema-discrete-curriculum
**Areas discussed:** Field→PARAM_BOUNDS mapping, Override value representation, advance_level trigger, progression_mode config & default, per-task concrete-key mapping

---

## Field → PARAM_BOUNDS mapping

| Option | Description | Selected |
|--------|-------------|----------|
| Abstract aliases + per-task map | Four abstract fields resolved to concrete PARAM_BOUNDS keys per task via a central mapping; override is a no-op on tasks with no mapping. Keeps the four locked names; leaf stays clean. | ✓ |
| Literal keys (no-op if absent) | Treat the four as literal keys; target_precision_tolerance / tool_position_noise would be no-ops everywhere (match no task). | |
| Add as new PARAM_BOUNDS keys | Add the four names as new keys on every reward class. Edits validated rewards surface; risks regression gate. | |

**User's choice:** Abstract aliases + per-task map
**Notes:** Scout surfaced that the four override names do not all match real PARAM_BOUNDS keys — only tissue_stiffness and time_limit coincide (and not on every task). This made the mapping the crux of the phase.

### Where the mapping lives

| Option | Description | Selected |
|--------|-------------|----------|
| Data dict in wiring module | Pure-data dict (task-name → {abstract → concrete key string}) in a non-leaf wiring module; DifficultyLevelConfig stays import-free. | ✓ |
| Inside the leaf as string dict | String-only mapping table inside DifficultyLevelConfig; zero imports so leaf holds, but couples schema to task vocabulary. | |
| Declared per reward class | Each reward class declares its abstract field map; spreads mapping across rewards.py and touches validated surface. | |

**User's choice:** Data dict in wiring module

### Unmapped override behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Warn + keep interpolated | Log a warning so author intent is not silently lost; keep the interpolated value and continue. | ✓ |
| Silent no-op | Silently ignore; interpolated value retained with no signal. | |
| Error on unmapped override | Raise at apply time; strictest but can break scene loading. | |

**User's choice:** Warn + keep interpolated

### Mapping key & coverage

| Option | Description | Selected |
|--------|-------------|----------|
| Task name, all 6 tasks | Keyed by TaskConfig.name; populated for all six v0.4.0 tasks now. | ✓ |
| Keyed by reward class | Keyed by reward class type; more type-safe but couples wiring to reward imports. | |
| Minimal subset, extend later | Start with suturing + one more; Phase 37 load-all-6 would partially fail. | |

**User's choice:** Task name, all 6 tasks

---

## Override value representation

| Option | Description | Selected |
|--------|-------------|----------|
| Absolute scalar replacement | Override stores the final scalar; composing replaces only the mapped key. Matches success criterion; easy to range-validate. | ✓ |
| Delta added to interpolated | Override is +/- adjustment on top of interpolated value; harder to validate/author. | |
| Multiplier on interpolated | Override scales the interpolated value; awkward for time_limit. | |

**User's choice:** Absolute scalar replacement

### Range validation strictness

| Option | Description | Selected |
|--------|-------------|----------|
| Global union bounds | Validate against global bounds from union of per-task PARAM_BOUNDS for that abstract field; catches authoring errors at schema time. | ✓ |
| Basic sanity only | Positive-value checks where physical; lets researchers push beyond baseline ranges. | |
| Type check only | Must be float, no range enforcement; relies on downstream clamp. | |

**User's choice:** Global union bounds

---

## advance_level trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse _should_advance | Reuse existing success-rate gate (min_success_rate over advancement_window + difficulty_hysteresis); shared with continuous mode; keeps continuous path byte-identical. | ✓ |
| Episode-count per level | Separate discrete criterion: N successful episodes at current level; new config field. | |
| Manual only | No auto-advance; set_difficulty_level is the sole way to change levels. | |

**User's choice:** Reuse _should_advance
**Notes:** advance_level at HARD is a no-op returning False (terminal) — locked as Claude discretion.

---

## progression_mode config & default

### Default mode + coexistence

| Option | Description | Selected |
|--------|-------------|----------|
| Default continuous, discrete carries own state | progression_mode defaults to "continuous" (v0.5.0 byte-identical); discrete mode holds separate _current_level whose .value feeds interpolate_params; _current_stage untouched. | ✓ |
| Default discrete | Flips default to new level path; breaks byte-identical v0.5.0 output unless every test opts back in. | |
| Single shared state | Discrete set_difficulty_level writes into _current_stage; conflicts with scalar mismatch (0.0 vs 0.25) and perturbs continuous path. | |

**User's choice:** Default continuous, discrete carries own state
**Notes:** Scout surfaced that CurriculumStage (5 members, scalars 0.25/0.5/0.75/1.0) does not align with DifficultyLevel (3 levels, scalars 0.0/0.5/1.0) — discrete mode must carry its own level state.

### Where per-level overrides live

| Option | Description | Selected |
|--------|-------------|----------|
| New field on CurriculumConfig | difficulty_levels dict field on CurriculumConfig; empty = pure interpolation baseline. | |
| Separate DiscreteCurriculumConfig model | Separate Pydantic model wrapping the three DifficultyLevelConfig, referenced by CurriculumConfig via an optional field. | ✓ |
| On each CurriculumStageConfig | Rejected: stages are continuous path; scalars don't align with DifficultyLevel. | |

**User's choice:** Separate DiscreteCurriculumConfig model

### DiscreteCurriculumConfig structure & file placement

| Option | Description | Selected |
|--------|-------------|----------|
| Dict field + co-located wiring module | levels: dict[DifficultyLevel, DifficultyLevelConfig] (default empty); co-located with the mapping in one wiring module; DifficultyLevelConfig stays a solo leaf file. | ✓ |
| Explicit easy/medium/hard fields | Three optional explicit fields instead of a dict; more rigid, harder to iterate. | |
| Split wiring into two modules | Mapping and DiscreteCurriculumConfig in separate files; no benefit over co-location. | |

**User's choice:** Dict field + co-located wiring module

---

## Per-task concrete-key mapping

**User's choice:** Confirmed the proposed abstract→concrete mapping table as authoritative (CONTEXT.md D-05).
**Notes:** Judgment calls confirmed — target_precision_tolerance maps to needle_alignment_tolerance (needle_insertion), approach_tolerance (grasping), loop_deviation_tolerance (knot_tying); tool_position_noise maps to action_noise where present. Empty cells = no mapping (warn + no-op).

---

## Claude's Discretion

- Exact wiring-module file path (difficulty_wiring.py vs extending task_reward_router.py).
- Truth-table test layout and parametrization.
- Validator implementation choice (field_validator vs model_validator) for union-bound ranges.
- Internal field naming (_current_level, progression_mode Literal values).
- Whether set_difficulty_level additionally accepts a string and coerces.

## Deferred Ideas

- Scene JSON difficulty_blocks authoring + SurgicalEnv precedence chain — Phase 37 (TASK-08).
- Extending the abstract override vocabulary beyond the four locked fields — future phase.
- Per-task override of the abstract→concrete mapping itself — out of scope this phase.
- EXPERT/CUSTOM DifficultyLevel entries — discrete path is EASY/MEDIUM/HARD only.
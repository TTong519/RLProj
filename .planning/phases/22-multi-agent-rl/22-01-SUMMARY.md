---
phase: 22-multi-agent-rl
plan: 01
type: execute
wave: 1
subsystem: scene_definition
tags: [schema, multi-agent, pydantic-v2, arm-role, dual-arm, tdd]
requires: []
provides: [ArmRole, ArmConfig, MultiAgentConfig, SceneDefinition.multi_agent]
affects: [src/surg_rl/scene_definition/schema.py, tests/test_multi_agent_config.py]
tech-stack:
  added: []
  patterns: [Pydantic v2 model_validator (mode="after"), str Enum, @property derived fields, extra="forbid", min_length validation]
key-files:
  created: [tests/test_multi_agent_config.py]
  modified: [src/surg_rl/scene_definition/schema.py]
decisions:
  - "D-01/D-03: MultiAgentConfig cross-validates robot_ref against SceneDefinition.robots[] via model_validator"
  - "D-02: ArmRole enum (SURGEON, ASSISTANT) drives swappable roles — no hardcoded robot-name-to-role mapping"
  - "Old num_agents field replaced by @property; old agent_roles dict replaced by arm_configs list"
  - "extra='forbid' on MultiAgentConfig prevents accidental use of removed fields"
metrics:
  duration: "~14 min"
  task_count: 2
  completed_date: "2026-05-18"
---

# Phase 22 Plan 01: Multi-Agent Schema Extension Summary

Extended Pydantic v2 scene schema with `ArmRole` enum, `ArmConfig` model, expanded `MultiAgentConfig`, and `SceneDefinition.multi_agent` field — all with validation coverage and full backward compatibility for single-arm scenes.

## Tasks Completed

| # | Name | Commit | Key Changes |
|---|------|--------|-------------|
| 1 | ArmRole + ArmConfig + MultiAgentConfig | 4b54ae7 | Added ArmRole enum, ArmConfig model, replaced old MultiAgentConfig skeleton fields, added SceneDefinition.multi_agent |
| 2 | Cross-validation + round-trip + SceneLoader | 943e4e2 | Added validate_multi_agent_robot_refs validator, JSON/YAML round-trip tests, SceneLoader integration |

## TDD Cycle

| Phase | Commit | What |
|-------|--------|------|
| RED (Task 1) | c509950 | 17 failing tests for schema types |
| GREEN (Task 1) | 4b54ae7 | ArmRole, ArmConfig, MultiAgentConfig, SceneDefinition.multi_agent |
| RED (Task 2) | 721252d | 8 failing tests for cross-validation, round-trip, SceneLoader |
| GREEN (Task 2) | 943e4e2 | validate_multi_agent_robot_refs validator, all tests pass |

## Schema Changes

### New Types
- **`ArmRole(str, Enum)`** — `SURGEON = "surgeon"`, `ASSISTANT = "assistant"`
- **`ArmConfig(BaseModel)`** — `role: ArmRole`, `robot_ref: str` (min_length=1), `observation_keys: list[str] | None`

### MultiAgentConfig (replaced)
- **Removed:** `num_agents: int` (field → @property), `agent_roles: dict[str, ...]` (replaced by `arm_configs`)
- **New:** `arm_configs: list[ArmConfig]` (min_length=2), `model_config = {"extra": "forbid"}`
- **Validators:** `validate_unique_roles` (no duplicate ArmRole entries)
- **Accessors:** `get_arm(role) -> ArmConfig | None`, `num_agents -> int` (property)

### SceneDefinition (extended)
- **New field:** `multi_agent: MultiAgentConfig | None = None` (after `task` field)
- **Validator:** `validate_multi_agent_robot_refs` — ensures arm_configs robot_ref entries exist in SceneDefinition.robots[]

## Backward Compatibility

- Single-arm scenes: `multi_agent` defaults to `None` — `model_dump()` returns `multi_agent: null`
- All 918 existing tests pass without modification
- Existing `SceneDefinition(**data)` with no `multi_agent` key works unchanged

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added `extra="forbid"` to MultiAgentConfig**
- **Found during:** task 1 (GREEN phase)
- **Issue:** Pydantic v2 allows extra fields by default — `MultiAgentConfig(num_agents=3, arm_configs=[...])` accepted the removed `num_agents` field silently
- **Fix:** Added `model_config = {"extra": "forbid"}` to MultiAgentConfig
- **Files modified:** `src/surg_rl/scene_definition/schema.py`
- **Commit:** 4b54ae7

**2. [Rule 1 - Bug] Fixed `get_arm()` crash on unknown role strings**
- **Found during:** task 1 (GREEN phase)
- **Issue:** `get_arm("camera")` raised `ValueError` from `ArmRole("camera")` instead of returning `None`
- **Fix:** Wrapped string conversion in try/except ValueError, returning `None` for unknown roles
- **Files modified:** `src/surg_rl/scene_definition/schema.py`
- **Commit:** 4b54ae7

**3. [Rule 3 - Blocking] Fixed test helper creating invalid RobotConfig**
- **Found during:** task 2 (RED phase)
- **Issue:** `_make_robot()` used `num_joints` (non-existent field) instead of `urdf_path` (required to pass RobotConfig validator)
- **Fix:** Used `urdf_path="fake_robot.urdf"` in test helper; added `urdf_path` to SceneLoader scene_dict
- **Files modified:** `tests/test_multi_agent_config.py`
- **Commit:** 721252d

## Threat Flags

None — this plan modifies only Pydantic schema definitions and their tests. No new network endpoints, auth paths, or file access patterns introduced.

## Known Stubs

None — all schema fields are fully wired with validation. `observation_keys` defaults to `None` by design (signals "use all available keys" per D-04 decision).

## Self-Check: PASSED

- [x] `tests/test_multi_agent_config.py` exists — 25 tests, all passing
- [x] `src/surg_rl/scene_definition/schema.py` contains `ArmRole`, `ArmConfig`, updated `MultiAgentConfig`, `SceneDefinition.multi_agent`
- [x] Commits c509950, 4b54ae7, 721252d, 943e4e2 all verified in git log
- [x] 918 existing tests pass without modification

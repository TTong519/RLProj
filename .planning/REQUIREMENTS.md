# Requirements: Surg-RL

**Defined:** 2026-06-11 (v0.4.2 milestone)
**Core Value:** End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation

## v1 Requirements — Milestone v0.4.2 Audit Leftovers

This milestone closes the 2 remaining gaps deferred from the v0.4.0 audit gap closure milestone (v0.4.1). Pure gap-closure — no new features beyond what's listed.

### TASK-02 — 3 Difficulty Levels

Closes the partial v0.4.0 audit gap (`TASK-02` was marked `Partial` in v0.4.1 closure — `TaskRewardRouter` was activated in Phase 27, but the 3-difficulty-levels portion remained open).

- [x] **TASK-02-01**: A `DifficultyLevel` enum (EASY, MEDIUM, HARD) is defined in `src/surg_rl/rl/`, mapped to scalar difficulty values 0.0, 0.5, 1.0 respectively
- [x] **TASK-02-02**: Each of the 6 task reward classes (`SuturingReward`, `KnotTyingReward`, `NeedleInsertionReward`, `GraspingReward`, `CuttingReward`, `DissectionReward`) exposes a `get_params_for_difficulty(level: DifficultyLevel) -> dict[str, float]` method that delegates to the existing `interpolate_params()` infrastructure
- [x] **TASK-02-03**: `TaskRewardRouter` accepts a `DifficultyLevel` (in addition to the existing float) and passes the mapped scalar through to the appropriate reward class; float path is preserved for backwards compatibility
- [x] **TASK-02-04**: For each of the 6 task types, the easy → hard direction demonstrably changes at least one observable parameter (e.g., tissue stiffness increases, target precision tolerance tightens, tool position noise decreases, time limit shortens). Verified by a unit test that runs all 3 levels and asserts that at least 1 param in PARAM_BOUNDS changes between EASY and HARD for each task.
- [x] **TASK-02-05**: `TaskConfig` (Pydantic v2) gains an optional `difficulty_level: DifficultyLevel | None` field (default `None` = use existing float path). When set, the level overrides the float difficulty at construction time.
- [x] **TASK-02-06**: CurriculumScheduler (`CurriculumStageConfig.task_difficulty`) accepts `DifficultyLevel` in addition to float. Mixed-stage configs (some float, some enum) work without migration.

### DreamerV3 — Real-Subprocess E2E Test

Closes the deferred v0.4.0 audit gap. The Phase 26 fixes (`_JsonStdout` wrapper, `indigo→indent` typo fix, `DREAMER_COLOR` constant) are verified at the code level; this requirement adds a real-subprocess smoke test.

- [x] **DMV3-E2E-01**: A pytest test (`tests/dreamer/test_dreamerv3_subprocess_e2e.py`) spawns a real `dreamerv3` subprocess via the existing process-isolated harness, runs 100 environment steps on the Phase 24 forceps+liver suturing feasibility scene, and asserts the subprocess completes without exception
- [x] **DMV3-E2E-02**: The test verifies that the `_JsonStdout` wrapper correctly consumes the subprocess's stdout pipe — no `BlockingIOError`, no missing lines, no truncated JSONL metrics records
- [x] **DMV3-E2E-03**: The test verifies that the subprocess log output contains the `DREAMER_COLOR` ANSI color (the post-Phase-26 fix — not the pre-fix `indigo` color)
- [x] **DMV3-E2E-04**: The test is gated by `@pytest.mark.skipif` on (a) no GPU available, (b) `dreamerv3` not installed, (c) `jax` not installed. Skip message is descriptive and includes remediation steps.
- [x] **DMV3-E2E-05**: On successful run, a checkpoint is written to `models/dreamerv3/{task}_{obs_type}/` (existing auto-discovery path from Phase 24), and the test asserts the checkpoint directory exists and contains a checkpoint file

## v1 Requirements — Carried Forward (Already Complete)

All v0.4.0/v0.4.1 requirements are validated and live in `.planning/milestones/v0.4.1-REQUIREMENTS.md`. They are referenced here for traceability context but not re-asserted as v0.4.2 work:

- ✓ ASET-01..05 (Real Surgical Assets) — v0.4.0
- ✓ TASK-01, TASK-03, TASK-04 (Task Curriculum non-difficulty parts) — v0.4.0
- ✓ BENCH-01..05 (Performance Benchmarking) — v0.4.0 + v0.4.1
- ✓ MARL-01..04 (Multi-Agent RL) — v0.4.0 + v0.4.1
- ✓ DMV3-01..05 (DreamerV3 World Models — code-level) — v0.4.0 + v0.4.1

**TASK-02** is partially complete (the 3-difficulty-levels portion is what v0.4.2 closes). **DMV3-03** is currently marked Complete with a deferred E2E validation note — v0.4.2 closes that deferred validation.

## v2 Requirements (Deferred to v0.5.0+, Carried Forward)

- **TASK-05**: Task chain system compositing subtasks into procedures (grasp → cut → suture)
- **MARL-05**: RLlib-backed centralized critic for MARL training (beyond independent SB3 policies)
- **DMV3-06**: DreamerV3 offline training from recorded surgical demonstrations

## Out of Scope (v0.4.2)

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Tech debt cleanup (421 ruff issues in `src/surg_rl/dreamer/`) | Pre-existing, deferred to v0.5.0+ cleanup milestone |
| Cut cooldown unit test | Requires full env lifecycle, deferred from v0.3.2 |
| Per-tet generation counter for degenerate tets | Single cut per episode typical, deferred from v0.3.2 |
| Fluid step hook in `base_simulator.py` | Env-level hook sufficient, deferred from v0.3.2 |
| 3D fluid simulation (`dim_3d=True` flag) | 2D xz-plane slice sufficient, deferred from v0.3.2 |
| PhiFlow multi-obstacle `union()` workaround | Documented pitfall, no code change needed |
| Dockerfile.ros2 amd64 hardcode | Deferred from v0.3.1, K8s e2e prereq |
| K8s PVC e2e tests | Deferred from v0.3.1, requires PVC provisioner |
| KubeRay prerequisite tests | Deferred from v0.3.1 |
| Linux-only ROS2 subscriber e2e tests | Requires real ROS2 runtime; macOS local insufficient |
| Organ mesh source licensing (surgtoolloc) | Acknowledged, requires legal review |
| REQUIREMENTS.md BENCH-02..05 body checkboxes | Pre-existing v0.4.0 audit process gap, not v0.4.2 scope |
| New task types beyond the existing 6 | TASK-01..04 locked at 6 types in v0.4.0 |
| New mesh formats (glTF, COLLADA) | OBJ universal baseline, multi-format deferred |
| Real-time multi-user networked surgery | Single-agent / dual-agent training scope |
| FDA certification / medical-grade validation | Research and simulation tool, not clinical device |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| TASK-02-01 | Phase 29 | Complete |
| TASK-02-02 | Phase 29 | Complete |
| TASK-02-03 | Phase 29 | Complete |
| TASK-02-04 | Phase 29 | Complete |
| TASK-02-05 | Phase 29 | Complete |
| TASK-02-06 | Phase 29 | Complete |
| DMV3-E2E-01 | Phase 30 | Complete |
| DMV3-E2E-02 | Phase 30 | Complete |
| DMV3-E2E-03 | Phase 30 | Complete |
| DMV3-E2E-04 | Phase 30 | Complete |
| DMV3-E2E-05 | Phase 30 | Complete |

**Coverage:**
- v1 requirements: 11 total (6 TASK-02 + 5 DMV3-E2E)
- Mapped to phases: 11
- Unmapped: 0 ✓
- Out of scope items: 0 (all v0.4.2 requirements are mapped)

---

*Requirements defined: 2026-06-11 (v0.4.2 milestone start)*
*Last updated: 2026-06-12 after Phase 29 completion (TASK-02-01..06 Complete, 6/6 v0.4.2 requirements remaining: DMV3-E2E-01..05 → Phase 30)*

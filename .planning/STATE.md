---
gsd_state_version: 1.0
milestone: v0.6.0
milestone_name: Carried-Forward Debt Closure
status: Awaiting next milestone
stopped_at: Completed 40.1-02-PLAN.md (Phase 40.1 ready_for_verification)
last_updated: "2026-07-15T20:00:28.826Z"
last_activity: 2026-07-15
last_activity_desc: Milestone v0.6.0 completed and archived
progress:
  total_phases: 6
  completed_phases: 6
  total_plans: 18
  completed_plans: 18
  percent: 100
current_phase: 40.1
current_phase_name: close-gap-dmv3-08-thread-checkpoint-dir-into-find-latest-che
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-15 — v0.6.0 shipped)

**Core value:** End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation — with automatic primitive fallbacks when real assets are missing, and a benchmarking framework for systematic RL research comparisons.
**Current focus:** v0.6.0 Carried-Forward Debt Closure SHIPPED 2026-07-15. Next milestone not yet planned — run `/gsd-new-milestone` (deferred candidate: v0.7.0 GUI editor depth GUI-11..15 + scene generation GEN-01..05).

> **Note:** v0.6.0 closed as a verified closeout. Phase 40 was re-verified `passed` (5/5 truths) on 2026-07-15 after the `dreamer-gpu` GitHub Actions job was observed GREEN on `ubuntu-latest-4-core-gpu` — DMV3-07/08/10 runtime GREEN certified (previously `human_needed` per INV-8). Phase 40.1 closed the DMV3-08 parent-side resume gap and the Phase 38 advisories (CR-01 magnitude test + real TWO_WAY feedback + substep loop). All 6 v0.6.0 phases VERIFIED `passed`; 13/13 requirements closed.

## Current Position

Phase: Milestone v0.6.0 complete
Plan: —
Status: Awaiting next milestone
Last activity: 2026-07-15 — Milestone v0.6.0 completed and archived

## Performance Metrics

**Velocity:**

- Total plans completed: 115 across v0.1.0–v0.5.0 (12 + 19 + 18 + 1 + 9 + 21 + 4 + 3 + 22)
- Total execution time: tracked per phase in milestone archives

**By Milestone:**

| Milestone | Phases | Plans | Tests |
|-----------|--------|-------|-------|
| v0.1.0 | 1–5 | 12 | 607 |
| v0.2.0 | 6–9 | 19 | 775 |
| v0.3.0 | 10–13 | 18 | 826 |
| v0.3.1 | 14 | 1 | 833 |
| v0.3.2 | 15–18 | 9 | 910 |
| v0.4.0 | 19–24 | 21 | 1,043 |
| v0.4.1 | 25–28 | 4 | 1,053 |
| v0.4.2 | 29–30 | 3 | 1,134 |
| v0.5.0 | 31–35 | 22 | 1,325 |
| v0.6.0 | 36–40 | TBD | — |

**Recent Trend:**

- Last 5 milestones: 21 → 4 → 3 → 22 plans (closure milestones are small by design)
- Trend: Stable — v0.6.0 is another focused closure milestone

*Updated after each plan completion*
| Phase 36 P01 | 6m | 2 tasks | 2 files |
| Phase 36 P02 | 8m | 2 tasks | 2 files |
| Phase 36 P03 | 15m | 2 tasks | 2 files |
| Phase 37 P01 | 25m | 3 tasks | 4 files |
| Phase 38 P01 | 1m | 2 tasks | 2 files |
| Phase 38 P02 | 206s | 2 tasks | 4 files |
| Phase 38 P03 | ~3m | 2 tasks | 3 files |
| Phase 38 P04 | 13min | 3 tasks | 3 files |
| Phase 39 P02 | ~12m | 2 tasks | 2 files |
| Phase 39 P01 | ~6m | 2 tasks | 7 files |
| Phase 40 P01 | ~3m | 2 tasks | 4 files |
| Phase 40 P02 | 19min | 2 tasks | 2 files |
| Phase 40 P03 | 919 | 2 tasks | 3 files |
| Phase 40 P04 | 1min | 1 tasks | 1 files |
| Phase 40.1 P01 | 6min | 2 tasks | 2 files |
| Phase 40.1 P02 | 20min | 2 tasks | 4 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Architecture Decisions. Recent decisions affecting current work:

- [v0.6.0 research]: No new runtime deps for 3/4 items (dreamerv3~=1.5.0, phiflow>=3.4.0, Pydantic v2 already pinned). Only addition is `pytest-kind>=22.11.1` as a dev-only `[k8s-test]` extra for the PVC e2e test.
- [v0.6.0 research]: Every closure item is ADDITIVE — `dim_3d=False` default, `difficulty_overrides: ... | None = None`, new `set_difficulty_level`/`advance_level` alongside (not replacing) `advance_stage`. Existing scene JSON loads unchanged.
- [v0.6.0 research]: Phase 30 sentinel is FLIPPED (negative→positive), not deleted — the flip IS the milestone closure signal. Add a guard that fails if `_build_agent` ever returns `None` again.
- [v0.6.0 research]: DreamerV3 dreamerv3 logger MUST go to stderr (not stdout) — stdout is the JSON-over-stdio pipe; logger output there corrupts the protocol.
- [v0.6.0 research]: JAX must NEVER leak into the parent process — keep parent↔child on JSON-over-stdio; set `XLA_PYTHON_CLIENT_MEM_FRACTION` before JAX's first import in the subprocess only.
- [v0.6.0 research]: 3D fluids — cubic NxNxN memory blow-up mitigated by a separate smaller 3D default `grid_size` + validator; thin-instrument coupling instability mitigated by `coupling_mode="one_way"` default in 3D, two-way opt-in.
- [v0.6.0 research]: Naming drift — `difficulty_blocks` (PROJECT.md) vs prior plural-s spelling (STATE.md) → canonical = `difficulty_blocks`; reconciled in Phase 37 (TASK-08/SC#5). Drift spelling removed from PROJECT.md and STATE.md.
- [v0.6.0 research]: CI smoke test asserts STRUCTURAL properties (finite/decreasing loss, checkpoint exists), NOT the v0.4.0 spike's converged `MSE<0.01` thresholds — smoke-vs-convergence split.
- [v0.4.2 Phase 29]: DifficultyLevel uses `_FloatMixin(float, Enum)`; Pydantic v2 cycle-resolution pattern (`from __future__ import annotations` + string forward-ref + `model_rebuild()` + lazy local imports) — REUSE for DifficultyLevelConfig in Phase 36.
- [v0.4.2 Phase 30]: E2E test asserts EXPECTED `RuntimeError("Agent not configured")` from the Phase 24 `_build_agent` stub — sentinel that will START FAILING when real dreamerv3 is integrated; Phase 40 must invert it.
- [v0.5.0 close]: K8s PVC e2e scaffolding stubbed in Phase 35; organ-mesh licensing research spike deferred; both to be closed in v0.6.0 (Phases 39).
- [Phase ?]: Phase 36-01: DifficultyLevelConfig Pydantic v2 leaf with D-07 range validators.
- [Phase ?]: Plan 02: ABSTRACT_TO_CONCRETE keyed by task_type (corrected D-03) in dynamics/difficulty_wiring.py — matches TASK_REWARD_REGISTRY keys
- [Phase ?]: Plan 02: compose_difficulty_overrides is additive over interpolate_params (D-06 ABSOLUTE replacement); unmapped override warns via logger.warning and keeps interpolated value (D-04, no raise)
- [Phase ?]: Plan 02: DiscreteCurriculumConfig is a Pydantic BaseModel with levels dict defaulting to empty (D-08); reward_cls passed as param — one-way edge, no task_reward_router import
- [Phase ?]: Phase 36-03: CurriculumScheduler additive progression_mode (continuous/discrete, default continuous) + set_difficulty_level/advance_level (EASY->MEDIUM->HARD->False, D-12) on separate _current_level axis (D-10); advance_level carries shared _meets_success_threshold(min_success_rate) gate (corrected D-11)
- [Phase ?]: Phase 36-03: _meets_success_threshold pure helper shared by continuous _should_advance (stage_cfg.success_threshold) and discrete advance_level (min_success_rate); _should_advance pure refactor (observable output unchanged, SC#4); update_curriculum discrete early-return branch (continuous path byte-identical)
- [Phase ?]: Phase 36-03: discrete_config uses stdlib dataclass field DiscreteCurriculumConfig | None = None (PEP 563 + late bottom-of-file import); no model_rebuild (dataclass not Pydantic); one-way edge curriculum->difficulty_wiring->rl.difficulty (no cycle, SC#5)
- [Phase ?]: Phase 37-01: TaskConfig.difficulty_blocks = dict[DifficultyLevel, DifficultyLevelConfig] | None = None — string forward-ref + extended late-import + single model_rebuild() (Pitfall 4 guarded)
- [Phase ?]: Phase 37-01: field_validator(mode=before) coerces JSON enum-name string keys to DifficultyLevel members (float-enum value-based coercion rejects name strings; plan A6 corrected)
- [Phase ?]: Phase 37-01: SC#5 naming drift reconciled — difficulty_blocks canonical across PROJECT.md + STATE.md; drift spelling removed
- [Phase 37]: Plan 37-02: apply_params(params) extracted on BaseRewardFunction (no-op) + 6 task rewards (Q1 MINIMAL single-key mapping); apply_difficulty delegates — pure refactor, observable output unchanged
- [Phase 37]: Plan 37-02: SurgicalEnvConfig.difficulty: float = 0.5 added (Q2 — makes config.difficulty precedence level real); _setup_rewards additive blocks branch with Q4 isinstance(difficulty, DifficultyLevel) guard (blocks inert under continuous curriculum — Pitfall 6); compose_difficulty_overrides lazy-local imported (Pitfall 4); 4-level precedence difficulty_blocks > task.difficulty_level > config.difficulty > default 0.5 (SC#2)
- [Phase 37]: Plan 37-02: Pitfall 3 path (a) — env does NOT patch TaskConfig.time_limit or max_episode_steps from difficulty_blocks (deferred); documented in TestPrecedenceTruthTable blocks_time_limit_inert case
- [Phase ?]: Phase 38-01: FluidCouplingMode str-Enum placed after FluidBoundaryType (no model_rebuild); grid_size hard-error when dim_3d=True is the SC#3 guard
- [Phase 38]: 3D force path uses separate _compute_obstacle_forces_3d helper (keeps 2D compute_obstacle_forces signature byte-identical; D-16)
- [Phase 38]: add_instrument dims=(shaft_radius, shaft_length, tip_half_size); Box tip uses 2-arg Box(center,size) form (half_size kwarg unsupported in phi 3.4.0)
- [Phase ?]: render_fluid_3d is a slice-of-3D fallback (D-18), NOT a true volume renderer (deferred per CONTEXT.md)
- [Phase ?]: _render_np_2d extracted from render_fluid_2d; 2D byte-identical guard pins pre-refactor output array (SC#1)
- [Phase ?]: SC#1 2D baseline uses SHA256 hash-pin for byte-identical regression
- [Phase ?]: SC#4 overlapping: pressure finite-or-None (union(*geoms) graceful degradation; NaN contract preserved)
- [Phase 39]: Procedural generation is the DEFAULT organ-mesh source for surg-rl (ADR-0001, status: accepted)
- [Phase 39]: SurgToolLoc REJECTED as organ-mesh source: modality mismatch (primary) + MICCAI/EndoVis challenge-guidelines licensing incompatibility (secondary), both cited from public URLs
- [Phase 39]: MADR format adopted as repo ADR template; docs/adr/ is canonical ADR directory with 4-digit zero-padded numbering
- [Phase 39]: [Phase 39-01]: pytest-kind>=22.11.1 + pykube-ng (transitive) added as [k8s-test] extra after human-verify SUS gate approved; e2e overlay references ../../base/pvc.yaml directly (NOT - ../../base) and read-job.yaml applied standalone in test body to avoid racing the write-Job
- [Phase 39]: [Phase 39-01]: Module-level pytestmark skipif required (not just in-test pytest.skip) so K8s e2e test SKIPS not ERRORs when Docker is down -- kind_cluster fixture errors at setup before the test body runs
- [Phase ?]: 40-01: wrapper.py action_space left unchanged (D-05/A4 discretion) — _build_agent builds dict-form act_space from the wrapper's bare Box
- [Phase ?]: 40-01: DMV3-09 regression guard uses AST Return(None) walk (not string match) to avoid false positives
- [Phase ?]: 40-02: _train_loop drives manual embodied.Driver + agent.train() batch loop (D-07, NOT embodied.run.train); _coerce_metric maps version-varying dreamerv3 metrics keys
- [Phase ?]: 40-02: _evaluate returns reconstruction_mse/reward_mae as 0.0 finite placeholders (DMV3-10 finiteness only); real values deferred to 40-04
- [Phase ?]: 40-02: _save_checkpoint delegates to cp.save() (registered .ckpt path); _load_checkpoint delegates to cp.load() + load_or_save() fallback (D-09)
- [Phase ?]: 40-02: did NOT modify _run_subprocess_loop cleanup (SC#1); AttributeError on dict bundle swallowed by suppress — cosmetic for 40-04
- [Phase ?]: 40-02: Phase 30 sentinel flipped negative→positive (DMV3-09) with structural-only assertions (DMV3-10, NO MSE<0.01 threshold); skipif preserved; macOS SKIPs cleanly per INV-8
- [Phase ?]: 40-03 retired .pt glob for embodied.Checkpoint native .ckpt format D-09
- [Phase 40]: 40-04: Used ubuntu-latest-4-core-gpu as the dreamer-gpu runs-on label (D-01). Implemented D-02 not-per-PR gate as a job-level if condition (push main || tags v* || workflow_dispatch) inside the existing CI workflow rather than a separate workflow file. Set DREAMER_TOTAL_STEPS=1000 + DREAMER_EVAL_EVERY=500 as env on the pytest step (D-03). Added on-failure checkpoint artifact upload for post-mortem. DMV3-10 GREEN pending GitHub GPU runner enablement on the repo account (user_setup).
- [Phase ?]: test decision
- [Phase ?]: 40.1-01: additive checkpoint_dir param with candidate-list fallback (custom dir first, default dir second) — preserves default-dir behavior when None (D-01)
- [Phase ?]: 40.1-01: MagicMock subprocess stub + JSON-serializable evaluate return for CPU-runnable resume wiring test (D-03 deliberate contrast, no skipif)
- [Phase ?]: 40.1-02: Implemented real TWO_WAY obstacle-velocity feedback via Obstacle(merged, velocity=(float,float,float)) moving-wall boundary in make_incompressible (D-05/D-08) — closes Phase 38 WR-01/WR-02 advisory (coupling_mode/coupling_substeps were inert)
- [Phase ?]: 40.1-02: 3D substep loop runs for BOTH ONE_WAY and TWO_WAY with sub_dt = dt / coupling_substeps (D-06); 2D path early-returns byte-identical to v0.5.0 (SC#1)
- [Phase ?]: 40.1-02: m_obs = 1e-3 kg for added-mass feedback (D-08); Obstacle velocity passed as tuple of Python floats NOT np.ndarray (PhiFlow 3.4.0 Obstacle.__init__ wraps tuple/list only, RESEARCH landmine 7)

### Pending Todos

- None. Roadmap created; next: `/gsd-plan-phase 36` (Difficulty Schema + Discrete Curriculum — non-GPU, lowest risk, unblocks 37).

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260614-1 | Clean up pre-GSD files archived to .planning/milestones/v0.0.0-* | 2026-06-14 | (this commit) | (inline) |
| 20260617-demo-rework | Reworked suturing_demo.json + scene_builder; 3 regression tests | 2026-06-17 | 9e11c3f | [20260617-demo-rework](./quick/20260617-demo-rework/) |

### Blockers/Concerns

- **Phase 40 (Real DreamerV3):** GPU-gated — requires CI GPU host; macOS local skips per INV-8. Highest external-API risk: dreamerv3 factory composition (`make_agent`/`make_replay`/`make_stream`/`make_logger` + `encoder.mlp_keys`/`cnn_keys`) signatures inferred from DeepWiki + `embodied.run.train` source (official `example.py` is 404). Needs deeper research during Phase 40 planning. Also: CI GPU host provisioning strategy — must run the GPU-skipif tests, else milestone audit fails on 100%-skipped.
- **Phase 38 (3D fluid — `force_computation` 3D bbox branch):** 2D pressure-gradient bbox integration generalization to a z-axis slice needs design validation. PhiFlow 3D API itself is HIGH confidence. (3D obstacle-force magnitude bug CR-01 tracked in `38-REVIEW.md` — fix via `/gsd-code-review 38 --fix`.)
- **Phase 36/37 (DifficultyLevelConfig):** main risk is re-introducing the v0.4.2 Pydantic cross-package cycle — mitigated by leaf-module placement + `model_rebuild()`. Override precedence must be TDD'd as a truth table against the existing 4-source chain in `_setup_rewards`.
- **Cross-phase:** `CurriculumScheduler` regression — discrete progression MUST be additive (`progression_mode` flag); full v0.4.0+v0.4.2 curriculum suite must pass unchanged as the additive gate.

### Roadmap Evolution

- Phase 40.1 inserted after Phase 40: Close gap: DMV3-08 thread checkpoint_dir into _find_latest_checkpoint + Phase 38 advisory cleanups (CR-01 3D force units, inert coupling_mode/substeps) (URGENT)

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| TASK-02 | 3-difficulty-levels (easy/medium/hard presets) | **Closed in v0.4.2** | v0.4.1 |
| DreamerV3 | Real-subprocess E2E test | **Closed in v0.4.2** | v0.4.1 |

### Acknowledged at v0.5.0 close (2026-06-24) — being closed in v0.6.0

| Category | Item | v0.6.0 Phase | Note |
|----------|------|--------------|------|
| verification | Phase 09 ros2-bridge `09-VERIFICATION.md` gaps_found | (out of v0.6.0 scope) | Older v0.3.0 verification debt; not in this milestone's 13 requirements |
| uat | Phase 24 DreamerV3 `24-UAT.md` partial | Phase 40 (DMV3-09/10) | GPU-gated; closed by the sentinel flip + CI GPU smoke test |
| TASK-02 | Per-level override schema (DifficultyLevelConfig) | Phase 36 (TASK-06) | |
| TASK-02 | CurriculumScheduler discrete level progression | Phase 36 (TASK-07) | |
| TASK-02 | Scene-level `difficulty_blocks: dict[DifficultyLevel, DifficultyLevelConfig] \| None` | Phase 37 (TASK-08) | Naming reconciled to `difficulty_blocks`; shape = dict-keyed (RESEARCH.md Open Q3) |
| Phase 30 | Stub-state sentinel flip when real dreamerv3 is integrated | Phase 40 (DMV3-09) | Flip IS the closure signal |
| Config | 2D fluids only (3D behind dim_3d=True flag) | Phase 38 (FLUID-01..03) | |
| Config | Dockerfile.ros2 amd64 / K8S PVC e2e / KubeRay prerequisite | Phase 39 (DEPLOY-01, PVC only) | **Closed in Phase 39** — K8s PVC e2e de-stubbed (pytest-kind) + `k8s-e2e` CI job observed GREEN. KubeRay + Dockerfile.ros2 amd64 still out of scope |
| Assets | Organ mesh source licensing (surgtoolloc or procedural) | Phase 39 (ASET-06) | **Closed in Phase 39** — ADR-0001 (MADR, accepted): procedural generation default, SurgToolLoc rejected (modality mismatch primary + licensing secondary) |

### Carried forward (unchanged, out of v0.6.0 scope)

| Category | Item | Status |
|----------|------|--------|
| Phase 17 | Per-tet generation counter for degenerate tets | Deferred (v0.3.2) |
| v2 | TASK-05 task chains (grasp→cut→suture) | v2 |
| v2 | MARL-05 RLlib centralized critic | v2 |
| v2 | DMV3-06 DreamerV3 offline training from demos | v2 |
| v0.7.0 | GUI-11..15 editor depth | Deferred to v0.7.0 |
| v0.7.0 | GEN-01..05 scene generation | Deferred to v0.7.0 |
| Process | REQUIREMENTS.md BENCH-02..05 body checkboxes remain `[ ]` | Acknowledged (v0.4.0) |
| Testing | Linux-only ROS2 subscriber e2e tests | Acknowledged (v0.3.1) |

### Acknowledged at v0.6.0 close (2026-07-15)

Pre-v0.6.0 cross-milestone debt flagged by pre-close `audit-open`. None are v0.6.0 scope; all acknowledged and carried forward (not blockers for the v0.6.0 verified closeout).

| Category | Item | Status | Note |
|----------|------|--------|------|
| verification | Phase 09 ros2-bridge `09-VERIFICATION.md` gaps_found | Acknowledged | Older v0.3.0 verification debt; out of v0.6.0's 13 requirements |
| uat | Phase 24 DreamerV3 `24-UAT.md` partial | Effectively closed | GPU-gated; closed by the Phase 40 sentinel flip + `dreamer-gpu` CI GREEN (2026-07-15); stale `partial` marker left as-is |
| quick_task | `demo-rework` (20260617) | Stale marker | Work was complete at v0.5.0 close; `audit-open` flag is a stale completion marker |

## Session Continuity

Last session: 2026-07-15 — v0.6.0 milestone close
Stopped at: Milestone v0.6.0 completed and archived
Resume file: None

*Updated: 2026-07-15 — v0.6.0 SHIPPED (verified closeout). Phase 40 re-verified `passed` after `dreamer-gpu` CI GREEN observed; all 6 phases VERIFIED; 13/13 requirements closed. Phase dirs archived to `.planning/milestones/v0.6.0-phases/`. Next: `/gsd-new-milestone`.*

## Operator Next Steps

- Start the next milestone with `/gsd-new-milestone` (deferred candidate: v0.7.0 GUI editor depth GUI-11..15 + scene generation GEN-01..05)

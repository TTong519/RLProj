# Pitfalls Research — v0.6.0: Carried-Forward Debt Closure

**Domain:** Closing 4 carried-forward tech-debt items in an existing surgical-robotics RL system (Surg-RL v0.6.0): real DreamerV3 integration, TASK-02 per-level difficulty schema, K8s PVC e2e + organ-mesh licensing, 3D fluid flag.
**Researched:** 2026-06-24
**Confidence:** HIGH (built on verified codebase state + 9 milestones of documented prior pitfalls; extended, not re-discovered)

## Scope Note

This file extends — not re-discovers — the known prior pitfalls documented in `PROJECT.md` (Key Architecture Decisions), `STATE.md` (Blockers/Concerns), and `MILESTONES.md`. The following are treated as established facts and are NOT re-litigated here:

- JAX+PyTorch GPU memory conflict → mitigated by process isolation + `XLA_PYTHON_CLIENT_MEM_FRACTION=0.4`
- Pydantic v2 cross-package cycle resolution pattern → `from __future__ import annotations` + string forward-ref + late import + `model_rebuild()` + lazy local imports
- PhiFlow multi-obstacle `union()` bug → merged-SDF workaround, documented at module level in `fluid_simulator.py`
- Cutting is discrete trigger with 500ms cooldown (PyBullet uses RESET_USE_DEFORMABLE_WORLD + full reload)
- Phase 30 sentinel test asserts the EXPECTED `RuntimeError("Agent not configured")` and MUST flip when real dreamerv3 is integrated
- CurriculumScheduler extension must be ADDITIVE (never replace Phase 3 fix)
- `DifficultyLevel` uses `_FloatMixin(float, Enum)` so `level.value` is duck-typed

This file covers the **common mistakes when CLOSING these 4 items on top of the existing system** — the integration/regression hazards specific to flipping stubs to real implementations.

---

## Critical Pitfalls

### Pitfall 1: Sentinel-test flip done as a deletion instead of an inversion

**What goes wrong:**
The Phase 30 E2E test (`tests/dreamer/test_dreamerv3_subprocess_e2e.py:72,91`) currently asserts `pytest.raises(RuntimeError, match="Agent not configured")` against the `_build_agent` stub at `subprocess.py:125-131` which returns `None`. When real DreamerV3 is wired in, that stub stops returning `None`, the subprocess stops emitting `{"type": "ERROR", "error": "Agent not configured"}`, and these two tests START FAILING — which is the designed sentinel. The mistake is to delete the sentinel tests (or skip them) to make CI green, losing the regression signal entirely.

**Why it happens:**
The test names and bodies read like negative-path tests ("asserts the stub raises"). A developer closing the debt sees red tests that "test the old stub" and deletes them as obsolete, rather than inverting them into positive-path tests that assert real training produces `{"type": "READY"}` / metrics within the step budget.

**How to avoid:**
- FLIP, do not delete. Rewrite each sentinel test to assert the positive contract: subprocess sends `READY`, training loop yields at least one `{"step": N, "loss": ...}` dict, evaluation returns a non-stub dict, checkpoint save/load round-trips. Keep the module-level `@pytest.mark.skipif` gating on (GPU + `dreamerv3` + `jax`) so macOS still skips cleanly.
- Add a NEW guard test that fails LOUDLY if `_build_agent` ever returns `None` again — `assert agent is not None, "_build_agent reverted to stub"` — so the sentinel inverts to protect the real implementation.
- Keep the `_JsonStdout` wrapper and `DREAMER_COLOR` assertions from Phase 26 — those fixes must still hold under the real agent.

**Warning signs:**
- `tests/dreamer/test_dreamerv3_subprocess_e2e.py` is removed or fully `pytest.skip`'d without replacement.
- A new test asserts only "subprocess didn't crash" instead of "subprocess trained ≥1 step and saved a checkpoint."
- macOS collection still works (heavy imports inside test bodies, not at module top) — if collection starts crashing on macOS after the flip, the lazy-import discipline was broken.

**Phase to address:**
Real DreamerV3 integration phase (the phase that replaces `_build_agent`). This is the single highest-risk flip in the milestone — it is both the integration proof AND the regression guard.

---

### Pitfall 2: Real DreamerV3 agent built outside the process-isolated JAX subprocess

**What goes wrong:**
The entire point of the `DreamerSubprocess` architecture (`subprocess.py`) is that JAX and PyTorch never share a process — `XLA_PYTHON_CLIENT_MEM_FRACTION=0.4` only means something if JAX is the only thing in that process. The mistake is to import `dreamerv3` / `jax` into the parent process (e.g., in `rl/training.py` or the CLI) to "peek" at the agent, validate config, or build a wrapper, which re-introduces the GPU OOM / CUDA-init conflict that process isolation was designed to prevent.

**Why it happens:**
The parent needs to pass config to the subprocess and read metrics back. It's tempting to import the agent class in the parent for type hints, config validation, or to construct a `GymToEmbodiedWrapper` before spawning. Any `import jax` or `import dreamerv3` in the parent loads the XLA runtime into the PyTorch process.

**How to avoid:**
- Parent process talks to the subprocess ONLY via the existing `_JsonStdout` JSON-over-stdio protocol. Config goes in as a plain `dict[str, Any]`; metrics come back as JSON dicts. No typed agent object crosses the boundary.
- `_build_agent`, `_train_loop`, `_evaluate`, `_save_checkpoint`, `_load_checkpoint` stay inside `subprocess.py` (the child side) — they are the only place `dreamerv3`/`jax` imports live, and those imports must be lazy (inside the function body, not at module top), so importing `subprocess.py` in the parent for the `DreamerSubprocess` controller class does not pull JAX into the parent.
- Keep `XLA_PYTHON_CLIENT_MEM_FRACTION=0.4` set in the child's env BEFORE `import jax` — JAX reads it at first import. Setting it after import is a no-op.
- The `GymToEmbodiedWrapper` (reset-in-action protocol) stays in the child; the parent never instantiates it.

**Warning signs:**
- `import jax` or `import dreamerv3` appears at the top of any module other than the child side of `subprocess.py`.
- Parent-process tests start failing with CUDA OOM or "XLA could not allocate" on the CI GPU host.
- `XLA_PYTHON_CLIENT_MEM_FRACTION` is set after a `jax` import has already run.

**Phase to address:**
Real DreamerV3 integration phase. Add a lint/test guard: grep-assert that `import jax`/`import dreamerv3` only appears in `dreamer/subprocess.py` (or a child-only helper module), and add a parent-process import test that asserts `surg_rl.rl.training` imports without `jax` in `sys.modules`.

---

### Pitfall 3: World-model training instability masked by the spike's MSE<0.01 / reward-MAE<0.5 thresholds

**What goes wrong:**
The Phase 24 feasibility spike validated against `MSE < 0.01` and `reward MAE < 0.5` on a forceps + liver tet-mesh suturing scene. The mistake is to treat those thresholds as the real-integration acceptance bar. Real DreamerV3 on the full 6-task suite with domain randomization + curriculum + cutting dynamics (discrete trigger, 500ms cooldown, tet remeshing) is a much harder distribution, and the world model can quietly diverge (loss explodes, recon MSE rises, reward MAE drifts) while the subprocess still reports "training proceeded" — because the stub `_train_loop` just yielded `{"loss": 0.0}`.

**Why it happens:**
The stub returns constant zeros. Replacing it with a real loop that yields real metrics means CI either (a) passes because the thresholds aren't checked at all, or (b) fails flakily because a 1-step GPU smoke test doesn't converge. The thresholds from the spike were for a converged model, not a smoke test.

**How to avoid:**
- Separate SMOKE from CONVERGENCE. The CI GPU test should assert structural properties (loss is finite, decreasing-ish over a tiny budget, recon MSE is finite, checkpoint file exists and is non-empty, eval dict has the expected keys with finite values) — NOT the spike's converged thresholds.
- The spike's `MSE < 0.01 / reward MAE < 0.5` belongs in a LONG-running acceptance test (marked `@pytest.mark.slow` + `@pytest.mark.gpu`, not in the default CI gate), or in a manual `dreamer-spike` CLI run that writes a report artifact.
- Log per-step metrics to a JSONL file in `models/dreamerv3/{task}_{obs_type}/` so divergence is inspectable post-hoc, not just pass/fail.
- Cutting dynamics: DreamerV3's ability to model tet-mesh cutting is explicitly flagged as UNCERTAIN in `STATE.md` (Phase 24 blocker). Do not include cutting tasks in the real-integration smoke test initially — start with suturing (the spike scene), then expand.

**Warning signs:**
- CI GPU test asserts `mse < 0.01` on a 50-step budget → guaranteed flaky or guaranteed pass-by-stub-residual.
- `loss` values are `inf`/`nan` but the test passes because it only checks "no exception."
- Test covers all 6 task types but only runs for N steps where N << convergence time.

**Phase to address:**
Real DreamerV3 integration phase (smoke test design) + a downstream/long-run acceptance phase (convergence thresholds). Split the two explicitly in the roadmap.

---

### Pitfall 4: Per-level `DifficultyLevelConfig` re-introduces the Pydantic v2 cross-package cycle

**What goes wrong:**
TASK-02 per-level schema adds `DifficultyLevelConfig` (tissue_stiffness / target_precision_tolerance / tool_position_noise / time_limit) as a new Pydantic v2 model, and wires it into `TaskConfig` (scene_definition) AND into `CurriculumStageConfig` / `CurriculumScheduler` (dynamics) AND into the reward classes (rl). The existing cycle (scene_definition ↔ rl ↔ dynamics) was broken in v0.4.2 with the `from __future__ import annotations` + string forward-ref + late import + `model_rebuild()` pattern. The mistake is to add `DifficultyLevelConfig` as a typed field referencing a model from another package at class-definition time, re-introducing the import cycle that crashes collection.

**Why it happens:**
The pattern that fixed it is non-obvious and spread across 3 files. A new model is naturally added where it "belongs" (e.g., `difficulty.py` or `schema.py`), and then referenced eagerly elsewhere, creating a new edge in the import graph that closes a cycle.

**How to avoid:**
- `DifficultyLevelConfig` lives in a LEAF module (no in-project imports), like `difficulty.py` already is. It must not import from `schema.py`, `curriculum.py`, or `rewards.py`.
- In `schema.py`'s `TaskConfig`, declare `difficulty_blocks: list["DifficultyLevelConfig"] | None = None` as a STRING forward-ref (exactly like the existing `difficulty_level: "DifficultyLevel | None"`), and call `TaskConfig.model_rebuild()` at the bottom of `schema.py` AFTER the late import of `DifficultyLevelConfig`.
- In `curriculum.py` and `rewards.py`, use the same string-forward-ref + `model_rebuild()` discipline; keep the `DifficultyLevel` scalar as the cross-package currency (do not pass `DifficultyLevelConfig` objects across package boundaries where a scalar suffices).
- Re-run the existing cycle-resolution regression tests from v0.4.2 (the HARD-fixture `SurgicalEnv`-construction integration test from Phase 35) — if those still pass after the schema addition, the cycle has not re-formed.
- `model_rebuild()` must be called AFTER every late import that resolves a forward-ref; calling it once at the top and then adding a new forward-ref below it leaves the new ref unresolved.

**Warning signs:**
- `ImportError: cannot import name 'X' from 'surg_rl.rl.difficulty'` (or similar) during pytest collection.
- `PydanticUndefinedAnnotation: 'DifficultyLevelConfig' is not fully defined` at model validation time — forward-ref was never resolved.
- Tests pass when run as a single file but fail when run as a suite (import-order-dependent cycle).

**Phase to address:**
TASK-02 per-level difficulty schema phase. Add a regression test that imports `surg_rl.scene_definition.schema` and `surg_rl.dynamics.curriculum` and `surg_rl.rl.environment` in every order and asserts no `ImportError`.

---

### Pitfall 5: Override-vs-base-parameter precedence ambiguity in `DifficultyLevelConfig`

**What goes wrong:**
`DifficultyLevelConfig` provides per-level overrides (tissue_stiffness, target_precision_tolerance, tool_position_noise, time_limit). But the existing system already has FOUR sources of difficulty: (1) `TaskConfig.difficulty_level` (enum/scalar), (2) `SurgicalEnvConfig.difficulty` (getattr fallback), (3) `CurriculumScheduler.current_difficulty` (curriculum-driven), (4) `PARAM_BOUNDS` + `interpolate_params()` in each reward class. Adding a 5th source without a documented precedence order produces silent conflicts: e.g., scene says `difficulty_level=EASY` with a `difficulty_blocks[EASY]` override, but curriculum is at stage 3 (HARD) and overwrites the override at env-construction.

**Why it happens:**
`environment.py:_setup_rewards()` (line 484-517) already implements a precedence chain: `task.difficulty_level` → `config.difficulty` → `curriculum.current_difficulty` → default 0.5. The new per-level overrides plug into that chain, but it's unclear whether the override is a function of the LEVEL (enum) or of the resolved SCALAR (float). If the override dict is keyed by level but the resolved difficulty is a curriculum-driven 0.37 (between EASY and MEDIUM), which override applies? Naive code picks the nearest level and silently drops the curriculum's continuous value.

**How to avoid:**
- Decide and DOCUMENT one precedence rule. Recommended: `difficulty_blocks` overrides apply ONLY when the resolved difficulty is exactly one of the 3 enum levels (EASY/MEDIUM/HARD scalar); for continuous (curriculum-driven) values, fall back to `interpolate_params()` (the existing continuous path). This keeps discrete and continuous paths orthogonal and ADDITIVE.
- Make the override application a single function with a clear contract: `resolve_params(difficulty_scalar, task_config) -> (stiffness, tolerance, noise, time_limit)`. One function, one precedence, tested with a truth table.
- The override should MUTATE the reward params via the existing `apply_difficulty()` hook (Phase 29 pattern), NOT bypass it. Do not introduce a parallel param-construction path.
- `DifficultyLevelConfig` fields must have the SAME names as the reward `PARAM_BOUNDS` keys they override, or the mapping is implicit and breaks silently when a reward class renames a field.

**Warning signs:**
- Two tests pass individually (one asserts EASY override applies, one asserts curriculum scalar applies) but fail when run together (shared mutable reward params).
- A `difficulty_blocks` override for `time_limit` has no effect because `time_limit` is read from `TaskConfig`, not from reward params — field ownership mismatch.
- Curriculum regression: existing v0.4.2 tests for continuous `interpolate_params()` start failing because the discrete override path intercepts them.

**Phase to address:**
TASK-02 per-level difficulty schema phase. Write the precedence truth-table test BEFORE the implementation (TDD the precedence rule).

---

### Pitfall 6: CurriculumScheduler discrete-level progression breaks the ADDITIVE invariant

**What goes wrong:**
TASK-02 asks for discrete `CurriculumScheduler` level progression (EASY → MEDIUM → HARD). The existing `CurriculumScheduler` (v0.4.0 Phase 21 + v0.4.2 Phase 29) uses continuous `difficulty: float` with `advance_stage`/`regress_stage` over `DEFAULT_STAGES` (4 stages at 0.25/0.5/0.75/1.0). The mistake is to REPLACE the continuous stage progression with a discrete 3-level progression, regressing the Phase 3 + Phase 21 fixes that `STATE.md` explicitly flags as "must be ADDITIVE — never replace."

**Why it happens:**
Discrete EASY/MEDIUM/HARD feels like a cleaner API than 4 continuous stages, and the new `difficulty_blocks: list[3]` aligns naturally with 3 levels. A developer "refactors" the scheduler to be 3-level-native.

**How to avoid:**
- Discrete progression is an ADDITIONAL mode, not a replacement. Add `progression_mode: "continuous" | "discrete" = "continuous"` to `CurriculumStageConfig` (or the scheduler config), and a `advance_level()`/`regress_level()` method pair that snaps to the nearest of {EASY, MEDIUM, HARD} WITHOUT touching the existing `advance_stage()`/`regress_stage()` continuous path.
- `DEFAULT_STAGES` stays 4-stage continuous; do NOT mutate it. `copy.deepcopy()` the existing pattern (mutable dataclass values — never `dict.copy()`).
- The discrete path maps levels to stages: EASY→stage0 (0.25), MEDIUM→stage1-2 (0.5), HARD→stage3 (1.0), or define a separate `DEFAULT_LEVELS` that is purely additive.
- Keep `current_difficulty` returning the scalar (the existing duck-typed contract); discrete mode just constrains WHICH scalars are reachable.

**Warning signs:**
- `CurriculumScheduler.DEFAULT_STAGES` is rewritten from 4 stages to 3.
- Existing v0.4.0/v0.4.2 curriculum tests (continuous interpolation, hysteresis, advance/regress on success rate) start failing.
- `current_difficulty` type-lie (flagged MEDIUM in Phase 29 code review WR-02) is "fixed" by narrowing the return type to `DifficultyLevel`, breaking float consumers.

**Phase to address:**
TASK-02 per-level difficulty schema phase. The additive-invariant regression test (run the full v0.4.0+v0.4.2 curriculum test suite unchanged) is the gate.

---

### Pitfall 7: Scene-level `difficulty_blocks: list[3]` schema migration breaks existing scene JSON

**What goes wrong:**
Adding `difficulty_blocks: list[3]` (or `difficulty_levels: list[3]` per STATE.md) to `TaskConfig` is optional with `None` default — that's safe. The mistake is making it REQUIRED for new scenes, or validating that the list length matches the number of difficulty levels in a way that rejects the existing 6 task scene JSONs (which don't have the field), or naming the field inconsistently with the v0.4.2 fixtures (`tests/fixtures/scenes/suturing_difficulty_hard.json`).

**Why it happens:**
The field seems like a natural required field ("every task should define its 3 levels"). But all existing scene JSONs predate the field.

**How to avoid:**
- `difficulty_blocks: list["DifficultyLevelConfig"] | None = None` — optional, `None` default, exactly like the v0.4.2 `difficulty_level` field. Existing scenes load unchanged.
- If the list is present, validate length == 3 AND that the 3 entries correspond to EASY/MEDIUM/HARD in order (add a `model_validator(mode="after")` that checks this and raises a clear error). If absent, fall back to `PARAM_BOUNDS` + `interpolate_params()` (the existing path).
- Do NOT rename the field between `difficulty_blocks` (PROJECT.md target) and `difficulty_levels` (STATE.md target). Pick ONE — `difficulty_blocks` matches the PROJECT.md milestone target — and update STATE.md if needed. Naming drift here will cause fixture/test mismatches.
- Update the existing `suturing_difficulty_hard.json` fixture to include a `difficulty_blocks` array so the coercion test covers both the enum field AND the new blocks field.

**Warning signs:**
- One of the 6 existing task scene JSONs fails to load after the schema change.
- A `model_validator` raises on a scene that doesn't set `difficulty_blocks` (should be `None`, not required).
- Tests reference `difficulty_levels` but the schema field is `difficulty_blocks` (or vice versa).

**Phase to address:**
TASK-02 per-level difficulty schema phase. Add a "load all 6 existing task scene JSONs" regression test to the schema phase.

---

### Pitfall 8: 3D fluid `dim_3d=True` flips PhiFlow grid memory 2D→3D (NxNxN) without perf gating

**What goes wrong:**
The current `FluidSimulator` (`fluid_simulator.py`) operates on a 2D xz-slice (Nx×Nz). Flipping `dim_3d=True` makes the grid (Nx×Ny×Nz) — a cubic blow-up. A 128² 2D grid becomes a 128³ 3D grid = 2M cells × 4+ fields (velocity, pressure, SDF) × float32 = hundreds of MB to GB, and the per-step PhiFlow solve cost scales ~N³. Running with the same resolution as 2D silently OOMs or turns a 20Hz fluid step into a 0.5Hz stall.

**Why it happens:**
The flag is a boolean; it's tempting to just branch on `dim_3d` and keep the same `grid_size`. The 2D resolution was tuned for surgical bleeding/irrigation; 3D needs a different (smaller) default.

**How to avoid:**
- `dim_3d=True` MUST come with a separate (smaller) default `grid_size` for 3D, or a validation that rejects 3D + large grid. Recommended: 3D default = 32³ or 48³, NOT the 2D default.
- Add a `FluidConfig` validator: if `dim_3d and grid_size > MAX_3D_GRID`, raise or warn (Rich warning). Document the memory cost in the field docstring.
- Gate the 3D path behind the `[fluids]` extra (if one exists) or at minimum a lazy `import phi.flow` inside the 3D branch only — 2D users should not pay the 3D import cost.
- The two-way solid coupling (obstacle SDF) in 3D is more expensive than 2D: the merged-SDF `union(*geoms)` workaround (documented at module level) still applies but `union` over 3D SDFs is slower; cap the number of coupled obstacles in 3D.

**Warning signs:**
- `FluidSimulator.step()` time goes from <50ms (2D) to >2s (3D at same resolution) — step budget blown.
- RAM usage spikes when `dim_3d=True` is set on an existing scene with no other changes.
- Tests that run fluid for N steps start timing out in CI.

**Phase to address:**
3D fluid flag phase. The resolution/memory gating is the FIRST thing to implement, before any 3D physics correctness work.

---

### Pitfall 9: 3D two-way solid-coupling stability — the `union()` workaround in 3D

**What goes wrong:**
The documented PhiFlow multi-obstacle `union()` bug (module-level note in `fluid_simulator.py:13-41`) was worked around in 2D by merging all obstacle geometries into one SDF via `union(*geoms)`. In 3D, the same `union()` call is more likely to hit the bug (more SDF samples, larger arrays), and two-way coupling (solid→fluid and fluid→solid force transfer) is conditionally unstable in 3D: pressure projection can produce non-physical forces on thin surgical instruments, launching them out of the scene.

**Why it happens:**
The 2D slice is forgiving — pressure errors average out over the thin dimension. 3D exposes full pressure gradients on thin geometries (needle, forceps jaws), and the coupling force = pressure_gradient × surface_area is large and noisy on thin features.

**How to avoid:**
- Default 3D coupling to ONE-WAY (solid→fluid only; fluid does not push back on instruments) until two-way is explicitly validated. Add `coupling_mode: "one_way" | "two_way" = "one_way"` for 3D; keep two-way default for 2D (existing behavior).
- Keep the `union(*geoms)` merged-SDF workaround in 3D, and add a regression test that constructs a scene with 2+ obstacles in 3D and asserts the SDF is finite everywhere (the bug produces NaN/Inf at obstacle boundaries).
- For thin instruments in 3D, consider voxelizing the instrument into the SDF grid at a coarser resolution than the visual mesh (avoid sub-cell features that the grid can't represent).
- Cap `dt` for 3D two-way coupling via CFL condition on the fluid velocity; document the CFL check.

**Warning signs:**
- Instruments drift/launch when fluid is active in 3D (coupling instability).
- `union()` in 3D returns NaN at obstacle surfaces (re-introduced multi-obstacle bug in 3D).
- 2D fluid tests still pass but 3D tests fail with diverging pressure.

**Phase to address:**
3D fluid flag phase. The coupling-mode default + `union()`-in-3D regression test is part of the phase's must-haves.

---

### Pitfall 10: K8s PVC e2e test flakiness from PVC binding race + CI-without-cluster

**What goes wrong:**
The current stub (`tests/k8s/test_pvc_e2e.py`) skips unless `kind get clusters` returns non-empty. De-stubbing means actually creating a PVC, writing a checkpoint, reading it back, and deleting. The common failures: (1) PVC binding race — `PersistentVolumeClaim` is `Pending` because no `PersistentVolume` provisioner is ready, and the test reads before bind completes; (2) the test passes locally against `kind` but is flaky in CI because CI spins up a fresh `kind` cluster per run and the local-path provisioner takes 5-15s to initialize; (3) checkpoint path mounting mismatch — the test writes to `/models/...` in the pod but the PVC is mounted at `/data` and the checkpoint path isn't reconciled.

**Why it happens:**
PVC binding is asynchronous. `kubectl get pvc` returning the object doesn't mean it's `Bound`. CI environments rarely have a real cluster, so the test either (a) always skips (no coverage) or (b) runs against an ephemeral `kind` cluster with slow provisioner startup.

**How to avoid:**
- Poll `kubectl get pvc <name> -o jsonpath='{.status.phase}'` until `Bound` with a timeout (e.g., 60s), BEFORE writing the checkpoint. Do not sleep a fixed amount — poll.
- Separate the test into two layers: (a) a UNIT test that validates the manifest YAML (`pvc.yaml`, the checkpoint `volumeMounts`, `volumeClaimTemplates`) without a cluster — runs everywhere, no skip; (b) an INTEGRATION test (`@pytest.mark.k8s` + `@pytest.mark.integration` + `@pytest.mark.slow`) that requires `kind` and does the real read/write/delete cycle.
- Reconcile the checkpoint path: assert that `DreamerConfig.checkpoint_dir` (or wherever checkpoints are saved) is the SAME path mounted from the PVC. The current `auto-discovery checkpoints from models/dreamerv3/{task}_{obs_type}/` path must match the PVC mount. Add a manifest-level test that grep-asserts the mountPath equals the configured checkpoint root.
- Use `kind` with the built-in local-path provisioner explicitly; document the `kind create cluster` command in the test module docstring so CI can reproduce.
- Add cleanup (`kubectl delete pvc`) in a `finally`/fixture teardown so failed runs don't leak PVCs and cause the next run to fail with name collision.

**Warning signs:**
- Test fails intermittently with "PVC Pending" then passes on retry (binding race).
- Test passes locally but skips in CI (no `kind` in CI) — de-stubbing achieved no coverage gain.
- Checkpoint written successfully in pod but read-back returns empty (mount path mismatch).

**Phase to address:**
K8s PVC e2e phase. Split unit (manifest validation, always runs) from integration (`kind`-gated) as the first task of the phase, so the unit coverage lands even if the integration test remains `kind`-gated.

---

### Pitfall 11: Organ-mesh licensing — surgtoolloc license terms vs procedural generation fidelity

**What goes wrong:**
The organ-mesh licensing decision (procedural vs surgtoolloc) was deferred from v0.4.0 Phase 20. The two failure modes: (a) choose surgtoolloc without reading the license terms, ship organ meshes under a license incompatible with the project's MIT/Apache stance (surgtoolloc / EndoVis datasets often have non-commercial / research-only / attribution clauses that don't transfer to a downstream user); (b) choose procedural generation to "stay clean" but the generated organs are too low-fidelity to serve the realism goal of v0.4.0's real-assets pipeline, silently regressing the tetgen deformable + cutting pipeline.

**Why it happens:**
The decision is framed as binary (procedural OR surgtoolloc). It's actually two separate questions: (1) what license terms does surgtoolloc impose, and (2) what fidelity does procedural gen achieve. Neither has been documented yet (Phase 20 research spike deferred the decision, not the research).

**How to avoid:**
- DO THE LICENSE RESEARCH FIRST, as a documented artifact (a `LICENSE-NOTES.md` or phase research note), NOT in a commit message. Cite the specific surgtoolloc/dataset license text (EndoVis MICCAI sub-challenge data typically has a research-only, non-redistribution, attribution-required clause). Decision must cite the clause that blocks redistribution, if any.
- Recommended: procedural generation for SHIPPED organs (clean license, deterministic, matches the existing `scene_builder` primitive-fallback philosophy), with surgtoolloc as an OPTIONAL `[assets-research]` extra that users download themselves and sign the dataset EULA. This mirrors the existing "primitive fallback when real assets missing" pattern.
- If procedural is chosen, define a fidelity bar: organ mesh must (a) be watertight, (b) tetgen-able without degenerate tets, (c) deform plausibly under `<flex>`, (d) cut without producing non-manifold geometry. Add a regression test that runs each organ through the tetgen + cut pipeline.
- Document the decision in `PROJECT.md` Key Architecture Decisions and update the "Organ mesh source licensing" line in STATE.md Deferred Items to "Closed."

**Warning signs:**
- Decision commit message says "chose procedural, cleaner" with no license-citation artifact.
- Organ meshes shipped in `assets/` without a `LICENSE` file covering them.
- Procedural organs fail tetgen/cut silently (falls back to primitives) — fidelity regression masked by fallback.

**Phase to address:**
K8s PVC e2e + organ-mesh licensing phase (the licensing sub-task can run in parallel with the PVC work). The license-citation artifact is a phase must-have, not a post-hoc doc.

---

## Moderate Pitfalls

### Pitfall 12: DreamerV3 checkpoint format mismatch with SB3 auto-discovery

**What goes wrong:**
Real DreamerV3 saves checkpoints in its own format (JAX/Orbax checkpoint, not `.zip`). The existing `ExperimentRunner` and `evaluate` CLI expect SB3 `.zip` checkpoints at `models/{algo}_{task}/`. The auto-discovery path (`models/dreamerv3/{task}_{obs_type}/`) was designed for the stub. Mixing the two formats in the same evaluation pipeline produces "could not load model" errors or silent evaluation of the wrong format.

**Prevention:**
Keep DreamerV3 checkpoints in a separate directory namespace (`models/dreamerv3/...`) with a distinct loader; do not route them through `stable_baselines3.common.save.load`. The `ExperimentRunner` must dispatch on algo family (SB3 vs DreamerV3) before loading.

**Phase to address:** Real DreamerV3 integration phase.

---

### Pitfall 13: `GymToEmbodiedWrapper` action/obs contract drift under real agent

**What goes wrong:**
The wrapper (reset-in-action protocol, 64×64 RGBA pixel + low-dim state) was validated against the STUB agent which accepts any obs/action shape. A real DreamerV3 agent has strict obs space requirements (e.g., pixel obs must be `uint8 [H,W,C]`, state obs must match a registered vector). Contract mismatch surfaces only when the real agent runs.

**Prevention:**
Pin the wrapper's `observation_space` / `action_space` to the exact `gymnasium.spaces.Box` the DreamerV3 config declares, and add a contract test that asserts `wrapper.observation_space == agent.obs_space` before training. Validate the reset-in-action protocol against the real agent's expected `obs` dict keys.

**Phase to address:** Real DreamerV3 integration phase.

---

### Pitfall 14: macOS local skip masquerading as pass in CI gate

**What goes wrong:**
The DreamerV3 E2E test skips on macOS (no GPU/dreamerv3/jax). If CI also lacks a GPU host, the test skips EVERYWHERE and the "real integration" milestone closes with zero real coverage — the sentinel was flipped but never run.

**Prevention:**
Add a CI-matrix entry with a GPU runner that RUNS the DreamerV3 tests (no skip). Add a coverage-gate check: if the DreamerV3 test module is 100% skipped across ALL CI jobs, fail the milestone audit. The `audit-uat` skill should flag "all GPU tests skipped" as a partial, not a pass.

**Phase to address:** Real DreamerV3 integration phase (CI matrix) + milestone audit.

---

### Pitfall 15: `dim_3d` flag default safety — scenes silently flip to 3D

**What goes wrong:**
If `dim_3d` defaults to `True` (or is read from an env var that's set on a dev machine), existing 2D scenes start running 3D fluid, hitting Pitfall 8/9. If it defaults to `False` and the 3D path is never exercised in tests, the 3D code rots.

**Prevention:**
Default `dim_3d=False` (preserves all existing 2D behavior). Add a parametrized test that runs the fluid suite with BOTH `dim_3d=False` and `dim_3d=True` at a SMALL 3D grid size, so the 3D path is always exercised. Never read `dim_3d` from a raw env var without going through `FluidConfig` validation.

**Phase to address:** 3D fluid flag phase.

---

### Pitfall 16: `DifficultyLevel` scalar-vs-enum precedence flip in `TaskRewardRouter`

**What goes wrong:**
v0.4.2 established `TaskRewardRouter` with strict `type() is float` check (not `==`) to avoid float-mixin false-positives. Adding `DifficultyLevelConfig` may introduce a new code path that passes a `DifficultyLevel` enum to the router where a scalar is expected, and the strict check rejects it, or worse, a new path bypasses the router's normalization and applies the enum directly.

**Prevention:**
Keep `TaskRewardRouter` as the single normalization point; ALL difficulty inputs (scalar, enum, or config-with-overrides) funnel through `build()` which calls `apply_difficulty(float(difficulty.value))`. Do not add a second apply path for `DifficultyLevelConfig` — it feeds INTO the router as resolved params, not as a parallel router.

**Phase to address:** TASK-02 per-level difficulty schema phase.

---

## Minor Pitfalls

### Pitfall 17: DreamerV3 `XLA_PYTHON_CLIENT_MEM_FRACTION` set too late

Set the env var in the child's `os.environ` BEFORE any `import jax`. JAX reads it at first import. Setting it in `_build_agent` after JAX is already imported (e.g., via a transitive import) is a no-op. Set it at the very top of the child entry, before importing `dreamerv3`/`jax`.

**Phase to address:** Real DreamerV3 integration phase.

---

### Pitfall 18: `CurriculumStageConfig.difficulty` union not normalized at env-construction for the new discrete path

Phase 29 code review WR-03 (closed in v0.5.0) normalized `difficulty: float | DifficultyLevel` at env-construction. The new discrete-progression path adds a third type (`DifficultyLevelConfig`-derived scalar). Ensure the same normalization point (`environment.py:_setup_rewards`) handles the new path, rather than normalizing in a second place.

**Phase to address:** TASK-02 per-level difficulty schema phase.

---

### Pitfall 19: Organ-mesh `assets/` directory shipped without `.gitignore` for large binaries

If procedural organs are generated, commit the GENERATOR (deterministic, seeded), not the output meshes. Committing generated `.obj`/`.tet` bloats the repo. Add `assets/generated/` to `.gitignore` and document the regeneration command.

**Phase to address:** K8s PVC e2e + organ-mesh licensing phase.

---

### Pitfall 20: K8s PVC test leaks resources on failure

If the PVC-creation step succeeds but the read/write assertion fails, the PVC and PV are left around. Next run: name collision (`pvc-xxx already exists`). Use a pytest fixture with `yield` + `finally` that `kubectl delete` ignores-not-found, and generate a unique PVC name per run (`pvc-e2e-{uuid4}`).

**Phase to address:** K8s PVC e2e phase.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Real DreamerV3 integration | Sentinel test deleted instead of flipped (P1); JAX imported in parent (P2); smoke test asserts converged thresholds (P3); checkpoint format mismatch (P12); wrapper contract drift (P13) | Flip-not-delete; parent-import guard test; split smoke vs convergence; separate DreamerV3 checkpoint namespace; pin obs/action space contract test |
| Real DreamerV3 integration (CI) | All GPU tests skip everywhere (P14) | CI matrix GPU job + coverage-gate that fails audit if 100% skipped |
| TASK-02 per-level difficulty schema | Pydantic v2 cycle re-introduced (P4); override precedence ambiguity (P5); additive-invariant broken (P6); scene JSON migration breaks (P7); router bypass (P16) | Leaf-module placement + `model_rebuild()` regression test; precedence truth-table TDD; additive-mode flag; optional `None` default + load-all-6-scenes test; single router normalization |
| 3D fluid flag | 2D→3D memory blow-up (P8); two-way coupling instability in 3D (P9); default safety (P15) | Separate 3D default grid_size + validator; one-way default for 3D + `union()`-in-3D regression test; `dim_3d=False` default + parametrized dual-mode test |
| K8s PVC e2e | PVC binding race + CI-without-cluster (P10); resource leak (P20) | Poll-until-Bound; split unit (manifest) vs integration (kind); checkpoint-path reconciliation; unique-name fixture with teardown |
| Organ-mesh licensing | License terms unread / procedural fidelity regression (P11); binary bloat (P19) | License-citation artifact FIRST; procedural-as-default + optional research extra; commit generator not output; tetgen+cut fidelity regression test |

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Delete Phase 30 sentinel tests | Makes CI green after flip | Loses regression guard; stub can return silently | Never — flip, don't delete |
| Import `jax` in parent for config validation | Type-safe config in parent | Re-introduces GPU OOM; breaks process isolation | Never — use JSON-over-stdio dict |
| Assert spike's MSE<0.01 in CI smoke | Reuses existing threshold | Flaky on short budgets or masks divergence | Only in a `@slow @gpu` long-run acceptance test |
| Replace `CurriculumScheduler.DEFAULT_STAGES` with 3 discrete levels | Cleaner discrete API | Regresses Phase 3/21 continuous fixes | Never — add a `progression_mode`, don't replace |
| Make `difficulty_blocks` required | "Every task should define 3 levels" | Breaks all 6 existing scene JSONs | Never — optional with `None` default |
| Reuse 2D `grid_size` for 3D fluid | One config field | Cubic memory blow-up, step budget blown | Never — separate 3D default + validator |
| Choose procedural organs without fidelity test | Clean license, fast decision | Realism regression masked by primitive fallback | Only with a tetgen+cut fidelity regression test |
| Skip PVC unit tests because "needs a cluster" | Less test code | Zero coverage when CI has no cluster | Never — split manifest-unit (always runs) from kind-integration |

## Sources

- `.planning/PROJECT.md` — Key Architecture Decisions, Accepted Tech Debt, Active v0.6.0 requirements (HIGH confidence, project source-of-truth)
- `.planning/STATE.md` — Phase 24 DreamerV3 uncertainty, Phase 29 WR-02/WR-03, Phase 30 sentinel, Deferred Items table (HIGH confidence, project source-of-truth)
- `.planning/MILESTONES.md` — v0.4.0 Phase 24 DreamerV3 spike decisions, v0.4.2 Phase 29/30 decisions (HIGH confidence)
- `src/surg_rl/dreamer/subprocess.py:125-131` — verified `_build_agent` stub returns `None` (HIGH, direct code inspection)
- `tests/dreamer/test_dreamerv3_subprocess_e2e.py:64-91` — verified sentinel asserts `RuntimeError("Agent not configured")` at two sites (HIGH, direct code inspection)
- `src/surg_rl/rl/difficulty.py:17-50` — verified `_FloatMixin(float, Enum)` + EASY/MEDIUM/HARD scalars (HIGH, direct code inspection)
- `src/surg_rl/rl/environment.py:484-517` — verified `_setup_rewards` precedence chain (HIGH, direct code inspection)
- `src/surg_rl/dynamics/curriculum.py:89-260` — verified `CurriculumScheduler` + `DEFAULT_STAGES` 4-stage continuous (HIGH, direct code inspection)
- `src/surg_rl/scene_definition/schema.py:1087-1505` — verified `TaskConfig.difficulty_level` string forward-ref + `model_rebuild()` pattern (HIGH, direct code inspection)
- `src/surg_rl/fluids/fluid_simulator.py:1-118` — verified 2D xz-slice + `union(*geoms)` workaround (HIGH, direct code inspection)
- `tests/k8s/test_pvc_e2e.py:1-40` — verified stub + `kind`-gated skip (HIGH, direct code inspection)
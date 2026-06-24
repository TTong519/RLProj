---
phase: 35
phase_name: "Advanced Tech Debt"
project: "Surg-RL"
generated: "2026-06-24"
counts:
  decisions: 5
  lessons: 3
  patterns: 4
  surprises: 2
missing_artifacts:
  - "VERIFICATION.md"
  - "UAT.md"
---

# Phase 35 Learnings: Advanced Tech Debt

## Decisions

### Close WR-02 with an end-to-end HARD-fixture integration test
Added an integration test that loads `tests/fixtures/scenes/suturing_difficulty_hard.json` into a `SurgicalEnv`, calls `reset()`, steps with a sampled action, and asserts no exception. The HARD fixture previously was only tested at the `SceneLoader.load()` layer; no test actually constructed a `SurgicalEnv` from it.

**Rationale:** WR-02 (from Phase 29 code review) identified a coverage gap where the hardest difficulty preset shipped in v0.4.2 had no env-construction test. Closing it proves the full wiring from `SceneLoader` lazy import through reward construction to simulator load is functional for the hardest preset.
**Source:** 35-01-PLAN.md

---

### Normalize `CurriculumStageConfig.difficulty` to `float` at the curriculum boundary
Updated `CurriculumScheduler.current_difficulty` to return `float(d.value)` for `DifficultyLevel` inputs and `float(d)` for plain floats, so consumers always receive a scalar. The union `float | DifficultyLevel` was already accepted but leaked an enum instance to consumers expecting a scalar.

**Rationale:** WR-03 noted that if a future plan wired `current_difficulty` into the env's `_task_difficulty`, the env would receive a `DifficultyLevel` member and fail or behave unexpectedly. Normalizing now prevents a latent bug from surfacing in v0.6.0 curriculum integration work.
**Source:** 35-02-PLAN.md

---

### Extract reward construction into `SurgicalEnv._setup_rewards()`
Refactored the reward-building block (previously inline in `SurgicalEnv.__init__`) into a private `_setup_rewards(self) -> None` method, run after controller/bridge setup so curriculum difficulty is available. A precedence chain resolves the scalar difficulty: `task.difficulty_level` -> `config.difficulty` -> `controller._curriculum.current_difficulty` -> default `0.5`.

**Rationale:** Gives a single env-construction point where difficulty is coerced to a scalar float before reaching the reward builder, and ensures the controller is set up before reward construction so curriculum can supply difficulty.
**Source:** 35-02-PLAN.md

---

### Commit a K8s PVC e2e stub test (not a full e2e) and defer the real body to v0.6.0
Created `tests/k8s/test_pvc_e2e.py` with a `@pytest.mark.k8s` marker, a `kind`-cluster skip guard, and a TODO/pass stub body documenting the future PVC read/write/delete cycle. Registered the `k8s` marker in `pytest.ini`. The full PVC e2e test is deferred to v0.6.0.

**Rationale:** A real PVC e2e test requires a live Kubernetes cluster (`kind`) and persistent volume provider, which is out of scope for v0.5.0 CI. Committing the stub now lays down the test file, marker, and skip logic so v0.6.0 can fill in the body without restructuring the test suite.
**Source:** 35-03-PLAN.md

---

### Defer organ-mesh asset procurement to v0.6.0; keep procedural fallback as default
Completed a research spike documenting three candidate organ-mesh sources (SurgToolLoc/SARAS, MakeHuman, BodyParts3D/Anatomography) with a license comparison table and a recommendation to defer the asset decision to v0.6.0. No procedural generation or asset import work was started in v0.5.0.

**Rationale:** Realistic organ meshes are out of scope for v0.5.0, but the project needs a written record of the licensing landscape so v0.6.0 can choose between permissive datasets, CC0 proxies, procedural generation, or attribution-required assets.
**Source:** 35-04-PLAN.md

---

## Lessons

### Union type fields leak enum instances to downstream consumers
The `CurriculumStageConfig.difficulty` union `float | DifficultyLevel` was accepted by Pydantic but passed a `DifficultyLevel` enum instance to code expecting a scalar float, creating a latent type lie at the boundary.

**Context:** Discovered while closing Phase 29 code-review finding WR-03; the bug would have surfaced when v0.6.0 curriculum integration wired `current_difficulty` into the env's `_task_difficulty`.
**Source:** 35-02-PLAN.md

---

### Reward setup ordering depends on controller availability
Reward construction in `SurgicalEnv.__init__` was inline and ran before controller setup, which meant curriculum-supplied difficulty was not yet available when the reward builder needed it. Reordering so controller setup precedes `_setup_rewards()` was required for the curriculum path to work.

**Context:** Found while refactoring reward construction into `_setup_rewards()`; the original inline placement assumed difficulty came only from the scene/task, not from a later-initialized controller.
**Source:** 35-02-PLAN.md

---

### Organ-mesh licensing constraints differ sharply across candidate sources
SurgToolLoc/SARAS is academic/non-commercial with redistribution restrictions; MakeHuman exports CC0 assets but the application is AGPLv3 and internal organs need extra modeling; BodyParts3D/Anatomography is CC BY 2.1 JP requiring attribution with high-quality segmented organs needing conversion. No single source is permissive, complete, and redistribution-friendly.

**Context:** Surveyed while scoping the v0.6.0 asset decision; the trade-off between license permissiveness and anatomical completeness drove the deferral recommendation.
**Source:** 35-04-SUMMARY.md

---

## Patterns

### Integration test for env construction with MuJoCo skip guard
Mark the test with both `@pytest.mark.integration` and `@pytest.mark.slow`, resolve the fixture path relative to `__file__`, construct `SurgicalEnv`, call `reset()`, sample an action, call `step()`, assert no exception, and guarantee `env.close()` via `try/finally`. Convert `ImportError` for `mujoco` into `pytest.skip`, not a hard failure.

**When to use:** Closing coverage gaps where a fixture/scene exists but no test exercises the full env-construction -> reset -> step chain; especially when a simulator backend may be unavailable in CI.
**Source:** 35-01-PLAN.md

---

### Normalize union-typed values at the boundary property
Expose a property that returns a single concrete type (`float`) by branching on `isinstance` and coercing both union arms, so downstream consumers never have to handle the enum-vs-scalar distinction.

**When to use:** Whenever a Pydantic union field (`A | B`) is consumed by code that expects only one type; normalize at the property/boundary rather than at every call site.
**Source:** 35-02-PLAN.md

---

### Skip-gated K8s test with a dedicated marker and binary/cluster detection helper
Create a module-level helper (`_kind_cluster_available()`) that checks both `shutil.which("kind")` truthiness and a non-empty `kind get clusters` output, then `pytest.skip` with a v0.6.0 deferral reason if unavailable. Register a dedicated `[k8s]` marker in `pytest.ini` so the test can be deselected with `-m "not k8s"` and pytest does not warn about an unknown marker.

**When to use:** Scaffolding infrastructure-dependent e2e tests (K8s, cloud, external services) that cannot run in default CI; lets the test shape and marker exist now while deferring the real body to a later milestone.
**Source:** 35-03-PLAN.md

---

### Research spike as a deferred-decision deliverable
When a milestone cannot act on an open question (licensing, asset choice), produce a research markdown doc with candidate sections, a comparison table, an explicit deferral recommendation, and action items split by milestone. Update `STATE.md` deferred-items table to record the outcome. Do not start any implementation work in the current milestone.

**When to use:** When realistic implementation is out of scope for the current milestone but a written record of the landscape is needed so the next milestone can make an informed choice without re-doing the survey.
**Source:** 35-04-PLAN.md

---

## Surprises

### K8s stub test ended up with more markers than the plan specified
The plan called for `@pytest.mark.k8s`, but the committed test is also decorated with `@pytest.mark.integration` and `@pytest.mark.slow` per the summary, expanding the marker set beyond the original plan.

**Impact:** The test is now gated by three markers, meaning default `-m "not integration"` runs will also exclude it; this broadens the skip surface but keeps the test out of fast CI runs.
**Source:** 35-03-SUMMARY.md

---

### The HARD fixture integration test passed end-to-end locally without skipping
Despite MuJoCo availability being a common skip condition across the project, the 35-01 test passed fully (construct -> reset -> step) rather than skipping, confirming the HARD fixture wiring is functional on the local backend.

**Impact:** Validates that the entire chain from `SceneLoader` lazy import through reward construction to simulator load works for the hardest difficulty preset, not just that it imports cleanly.
**Source:** 35-01-SUMMARY.md
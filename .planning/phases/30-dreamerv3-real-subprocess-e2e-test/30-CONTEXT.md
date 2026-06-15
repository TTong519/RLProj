# Phase 30: DreamerV3 Real-Subprocess E2E Test — Context

**Gathered:** 2026-06-12
**Status:** Ready for planning
**Source:** v0.4.2 milestone roadmap (D-30-01..05 pre-decided) + this discussion (D-LOC-01, D-STEPS-01, D-SKIP-01, D-COLOR-01, D-CKPT-01) closing the remaining open questions.

<domain>
## Phase Boundary

A single pytest test module spawns a real `dreamerv3` subprocess via the existing process-isolated harness, runs 1000 environment steps on the Phase 24 forceps+liver suturing feasibility scene, and verifies the three Phase 26 fixes (`_JsonStdout` wrapper, `indent=2` typo, `DREAMER_COLOR="#FF8C00"` constant) hold end-to-end. The test is gated by `@pytest.mark.skipif` on (GPU + `dreamerv3` importable + `jax` importable) — skip-with-reason on macOS local (xfail-skip expected per `STATE.md` Blocker #4), runs on CI with GPU. No new functionality, no architecture changes — only a real subprocess smoke test for the Phase 26 fixes.

</domain>

<decisions>
## Implementation Decisions

### Pre-decided (carried forward from ROADMAP.md D-30-01..05)

- **D-30-01 (carry):** Single phase, single plan E2E test. Splitting into "subprocess spawn" and "assertions" is over-engineering for a test-only phase; all 5 requirements describe the same test.
- **D-30-02 (carry):** macOS local run is expected to skip — `STATE.md` Blocker #4 already documented this. The skip message must include `pip install '.[dreamer]'` as remediation so a developer with GPU can enable locally.
- **D-30-03 (carry):** Use the existing `DreamerSubprocess` and `_create_scene_for_task` infrastructure (Phase 24). Do NOT re-implement subprocess management in the test — only orchestrate via `run_dreamer_training(task=..., obs_type=..., total_steps=..., eval_every=...)`.
- **D-30-04 (carry, resolved by D-LOC-01):** Test file lives in `tests/dreamer/test_dreamerv3_subprocess_e2e.py` (with the new directory created); the top-level fallback is no longer needed. The 7 existing `tests/test_dreamer_*.py` files are NOT migrated — they stay at `tests/` top level (out of scope).
- **D-30-05 (carry):** Phase 30 verifies the Phase 26 fixes hold end-to-end — the unit tests in `tests/test_dreamer_subprocess.py` (5 tests, `TestSubprocessStdoutProtocol`) and `tests/test_dreamer_training.py` (2 tests, `TestTrainingMetricsSave`) remain the primary regression coverage. The E2E test is a smoke test that runs the full code path on real hardware; it is the deferred DMV3-03 E2E validation.

### Test file location (this discussion)

- **D-LOC-01:** Create new directory `tests/dreamer/` with empty `__init__.py` (or no `__init__.py` — pytest discovers nested dirs without one in default rootdir mode; planner verifies which form the project uses, default to no `__init__.py` to match `tests/` top-level layout). Place `test_dreamerv3_subprocess_e2e.py` inside. Path: `tests/dreamer/test_dreamerv3_subprocess_e2e.py`. Matches roadmap success criterion #1 wording exactly. The 7 existing `tests/test_dreamer_*.py` files are NOT migrated as part of this phase (separate cleanup).

### Step count (this discussion)

- **D-STEPS-01:** `total_steps=1000` (heavier than the roadmap's 100-step floor, but still well below the 100K production training). CI runtime estimate: 3–5 min on a GPU runner. Rationale: at 1000 steps, the `_JsonStdout` wrapper round-trips ~100 metric messages, giving statistical confidence the pipe protocol is stable. The 100-step floor was a roadmap placeholder; the user has opted for a heavier smoke test.

### Skip mechanism (this discussion)

- **D-SKIP-01:** `@pytest.mark.skipif` on the union of three conditions, evaluated at collection time. Test is COLLECTED, then SKIPPED before running on macOS (no subprocess spawn attempted). Skip message is a single descriptive string that lists ALL remediation steps the developer needs.
  - **Condition A** (GPU): `not (torch.cuda.is_available() or len([d for d in jax.devices() if d.platform == "gpu"]) > 0)`. Guard each import inside the `skipif` arg with `try/except ImportError` so a missing `torch` or `jax` does not crash collection.
  - **Condition B** (`dreamerv3`): `importlib.util.find_spec("dreamerv3") is None`.
  - **Condition C** (`jax`): `importlib.util.find_spec("jax") is None`.
  - **Union logic:** skip if A OR B OR C.
  - **Skip message** (single string, ≤200 chars):
    ```
    "Skipped: DreamerV3 E2E requires GPU + dreamerv3 + jax. Remediation: pip install '.[dreamer]' (jax with CUDA) on a GPU host; on macOS the test is expected to skip per STATE.md Blocker #4."
    ```
- **D-SKIP-02:** Use the `importlib.util.find_spec(...) is None` pattern established in `tests/test_rllib_train.py:62`. Do NOT use `@pytest.mark.xfail` — the PyBullet soft-body precedent is for tests that RUN and are expected to fail; here we don't even want the subprocess spawn to attempt on macOS (it would fail noisily and add 5–10s to local runs for nothing).
- **D-SKIP-03:** Do NOT add a secondary xfail inner marker. D-SKIP-01's single skipif is sufficient. The roadmap's D-30-02 phrase "xfail-skip expected" is shorthand for "this test is expected to skip on macOS" — it is NOT prescribing an xfail marker.

### DREAMER_COLOR verification path (this discussion)

- **D-COLOR-01:** Import-level constant assertion: `from surg_rl.benchmark.plots import DREAMER_COLOR; assert DREAMER_COLOR == "#FF8C00"`. This is exactly what `tests/test_benchmark_plots.py` already verifies at the unit-test level; the E2E repeats the assertion to prove the constant is the post-Phase-26 value in a real-import scenario (not just a unit-test-import scenario).
- **D-COLOR-02:** Do NOT attempt to assert `#FF8C00` appears in subprocess stdout — `_run_subprocess_loop` only emits JSON messages; `DREAMER_COLOR` lives in `src/surg_rl/benchmark/plots.py` and is never referenced by the dreamer subprocess. The success criterion #4 wording "subprocess output contains" is interpreted as "the test run's importable state contains" (i.e., the constant survives a full `import surg_rl.dreamer.training` round-trip).
- **D-COLOR-03:** Do NOT add a `print(DREAMER_COLOR)` banner to `_subprocess_main` — that would be a production-code change purely to satisfy the test, violating Phase 26's "no functionality changes" principle. The Phase 26 fix (changing the constant value) is fully covered by the unit test; the E2E just re-asserts it.

### Checkpoint assertion target (this discussion)

- **D-CKPT-01:** Call `run_dreamer_training(task="suturing", obs_type="state", total_steps=1000, eval_every=500)`. With `eval_every=500` (vs. default 10000), the periodic-checkpoint branch at `training.py:318` fires at `step=500` and `step=1000`, writing `checkpoint_500.pt` and `checkpoint_1000.pt`. The end-of-run try-block writes `final.pt` (line 337). The post-loop code writes `training_metrics.json` (line 349). The test asserts:
  - `models/dreamerv3/suturing_state/final.pt` exists (Phase 26 typo fix verified — `final.pt` is only written if the run completes cleanly through the `json.dump(..., indent=2)` call at line 342)
  - `models/dreamerv3/suturing_state/checkpoint_500.pt` exists (proves the periodic-checkpoint branch fires at `step=500`)
  - `models/dreamerv3/suturing_state/training_metrics.json` exists AND parses as valid JSON (verifies the `indent=2` fix is in effect — a typo `indig=2` would have raised `TypeError` before the file is written)
- **D-CKPT-02:** Use the existing `_find_latest_checkpoint` helper at `training.py:191-197` to confirm the auto-discovery path works (it globs `checkpoint_*.pt` and returns the most recent by mtime). This is the same path that `ExperimentRunner` uses to resume training; E2E exercising it closes the Phase 24 → Phase 30 contract.

### Test contract (delegated to OpenCode's discretion)

The planner and executor decide the test-class structure and helper extraction. The minimum acceptable form is:
- A single module-level test function (or a single test class with 4–6 test methods, one per success criterion) inside `tests/dreamer/test_dreamerv3_subprocess_e2e.py`.
- A module-level `pytestmark = pytest.mark.skipif(<D-SKIP-01 condition>, reason=...)` so the entire module is gated by the union of A/B/C.
- A fixture (or inline `tmp_path` / `monkeypatch.chdir`) that scopes the run to a temp dir so the `models/dreamerv3/suturing_state/` directory does not pollute the working tree.
- A try/finally that cleans up the `DreamerSubprocess` (call `.close()` if available) so the daemon process doesn't leak.

### OpenCode's Discretion

- Whether to use a `tmp_path` fixture or a hardcoded `models/dreamerv3/suturing_state_e2e/` path for the run output. The former is more isolated; the latter matches the Phase 24 auto-discovery path verbatim. Either is acceptable.
- Whether to mark the entire test module with the skipif (single gate) or to gate each test method individually (granular skip reporting). Both work; module-level is simpler.
- Whether to add a `--dreamer-e2e-steps=...` CLI override via `pytest.ini` (e.g., `addopts = --dreamer-e2e-steps=1000`). Not required; the test is the only consumer of the value, so a module constant is sufficient.
- Whether to assert `_JsonStdout` was used (vs. the pre-Phase-26 `os.fdopen`) by introspecting the subprocess's `sys.stdout` type. The Phase 26 unit test `TestSubprocessStdoutProtocol` already covers this; the E2E just verifies the subprocess completes without raising — if `_JsonStdout` were missing, the parent would get `BlockingIOError` on `pipe.send()` and the test would fail on the "no exception" assertion (D-E2E-01).
- Exact form of the `__init__.py` in `tests/dreamer/` (empty vs. absent). Default to empty `__init__.py` for consistency with other potential future subdirs; the project may or may not have a convention here (planner checks before writing).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/REQUIREMENTS.md` — DMV3-E2E-01..05 v1 requirements (lines 25–29)
- `.planning/ROADMAP.md` § Phase 30 — goal, success criteria, plans, D-30-01..05 pre-decisions
- `.planning/STATE.md` § Blockers/Concerns — Phase 30 (DreamerV3 E2E) Blocker #4 (macOS local expected to xfail-skip)
- `.planning/STATE.md` § Decisions — v0.4.2 D-30-01..05 listed
- `.planning/v0.4.0-MILESTONE-AUDIT.md` — gap evidence for DMV3-03 (the deferred E2E)

### Source artifacts (Phase 24 + 26)
- `src/surg_rl/dreamer/subprocess.py:15-26` — `_subprocess_main` entry (the `sys.stdout = _JsonStdout(child_stdout)` line at 23 is what the test exercises end-to-end)
- `src/surg_rl/dreamer/subprocess.py:29-53` — `_JsonStdout` wrapper class (Phase 26 fix #1)
- `src/surg_rl/dreamer/subprocess.py:154-249` — `DreamerSubprocess` parent class (the test's primary entry point)
- `src/surg_rl/dreamer/training.py:15-190` — `_create_scene_for_task` (test calls this via `run_dreamer_training`)
- `src/surg_rl/dreamer/training.py:191-197` — `_find_latest_checkpoint` (test exercises this to verify Phase 24 auto-discovery)
- `src/surg_rl/dreamer/training.py:200-359` — `run_dreamer_training` (the test's top-level entry point)
- `src/surg_rl/dreamer/training.py:337-352` — final checkpoint + `training_metrics.json` write (Phase 26 fix #2 `indent=2`)
- `src/surg_rl/benchmark/plots.py:30` — `DREAMER_COLOR = "#FF8C00"` (Phase 26 fix #3)
- `src/surg_rl/benchmark/plots.py:78` — `PlotRenderer._color_map["DreamerV3"] = DREAMER_COLOR` (the only consumer of the constant)

### Tests
- `tests/test_dreamer_subprocess.py:434 lines` — existing 5 `TestSubprocessStdoutProtocol` tests cover `_JsonStdout` at unit level
- `tests/test_dreamer_training.py:164 lines` — existing 2 `TestTrainingMetricsSave` tests cover `indent=2` at unit level
- `tests/test_benchmark_plots.py` — existing import-level test for `DREAMER_COLOR == "#FF8C00"` (this is what D-COLOR-01 mirrors)
- `tests/test_rllib_train.py:62-94` — `importlib.util.find_spec('ray') is None` skipif pattern (D-SKIP-02)
- `tests/test_simulators.py:1014, 1225` — `@pytest.mark.xfail` precedent for env-conditional tests (D-SKIP-02 notes we deliberately do NOT use this pattern)

### Reference scene
- `scenes/simple_suturing.json` — Phase 24 forceps+liver suturing feasibility scene (test loads this via `_create_scene_for_task(task="suturing")`)

### Prior phase context
- `.planning/phases/24-dreamerv3-world-models/24-CONTEXT.md` — Phase 24 D-04/D-05/D-06 process isolation design + feasibility spike results
- `.planning/phases/24-dreamerv3-world-models/24-04-SUMMARY.md` — `DreamerSubprocess` current implementation (matches what the test exercises)
- `.planning/phases/24-dreamerv3-world-models/24-UAT.md` — Test 9 orange color spec (`#FF8C00` rationale)
- `.planning/phases/26-fix-dreamerv3-training-bugs/26-CONTEXT.md` — Phase 26 D-04 (subprocess pipe fix), D-01 (indent fix), D-09 (color fix) — the three fixes this E2E verifies
- `.planning/phases/26-fix-dreamerv3-training-bugs/26-CONTEXT.md` § "Specific Ideas" — exact `_JsonStdout` shape and D-11 import-level test (the pattern D-COLOR-01 mirrors)

### Architecture & conventions
- `.planning/codebase/ARCHITECTURE.md` — subprocess / module layout
- `.planning/codebase/TESTING.md` — skipif / xfail / integration marker conventions
- `.planning/codebase/CONVENTIONS.md` — pytest patterns, lazy imports, fixture usage
- `AGENTS.md` § Testing — pytest.ini sets `pythonpath = src` (no `PYTHONPATH` prefix needed for pytest)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`run_dreamer_training(task, obs_type, total_steps, eval_every, ...)`** at `src/surg_rl/dreamer/training.py:200` — the test's top-level entry point. It internally calls `_create_scene_for_task` (line 241), `DreamerSubprocess.spawn()` (line 257), and the full training loop. Accepts `total_steps` and `eval_every` as keyword args, so the test can pass `total_steps=1000, eval_every=500` (D-STEPS-01 + D-CKPT-01) without subclassing or monkey-patching.
- **`_JsonStdout`** at `src/surg_rl/dreamer/subprocess.py:29-53` — the wrapper class the test exercises end-to-end. Each `print(..., flush=True)` in `_run_subprocess_loop` ends up as `pipe.send(payload)`. If the wrapper were missing or broken, the parent would see `BlockingIOError` on `pipe.send()` (or pre-fix `os.fdopen` would race with the parent's `recv()`); D-E2E-01's "no exception" assertion catches both.
- **`_find_latest_checkpoint(task, obs_type)`** at `src/surg_rl/dreamer/training.py:191-197` — auto-discovery helper that globs `models/dreamerv3/{task}_{obs_type}/checkpoint_*.pt`. The test calls this after the run to verify the Phase 24 auto-discovery path is intact (D-CKPT-02).
- **`DREAMER_COLOR`** at `src/surg_rl/benchmark/plots.py:30` — module-level constant. The test imports and asserts (D-COLOR-01).
- **`importlib.util.find_spec(...)` skipif pattern** at `tests/test_rllib_train.py:62-94` — the established pattern for "test gated by optional dependency." D-SKIP-02 lifts this pattern for `dreamerv3` and `jax`.

### Established Patterns
- **`@pytest.mark.skipif` on optional dependency** (Phase 11, 25, others): pattern is `pytest.mark.skipif(__import__("importlib").util.find_spec("X") is None, reason="X not installed")`. The `__import__("importlib")` form keeps the import lazy (the module is not imported at collection time if `pytest` itself is missing it).
- **Try/except around device checks** (`tests/test_gpu_integration.py:67, 79`): the project wraps `torch.cuda.is_available()` in `try/except ImportError` for `torch` itself. D-SKIP-01 mirrors this for `torch` and `jax`.
- **Module-level `pytestmark` for global skip** vs. **per-test skipif**: both are accepted. The `tests/test_rllib_train.py` form uses per-test skipif because each test exercises a different code path; Phase 30's single test exercises one code path (the full subprocess flow), so module-level `pytestmark` is sufficient.
- **JSON-parse-back assertion** (`tests/test_dreamer_training.py`): the existing unit test for `indent=2` reads back `training_metrics.json` and asserts `json.load` succeeds. D-CKPT-01's third assertion mirrors this.
- **Test fixture scoping** (`tests/test_dreamer_checkpoints.py`): uses `tmp_path` fixture to scope checkpoint writes. The E2E test can use the same pattern to avoid polluting the working tree.

### Integration Points
1. **`tests/dreamer/test_dreamerv3_subprocess_e2e.py`** → `surg_rl.dreamer.training.run_dreamer_training` (the only direct call from the test)
2. **`run_dreamer_training`** → `_create_scene_for_task` → `load_scene("scenes/suturing.json")` (fails to load — see D-LOC note below; the test passes `task="suturing"`, but `scenes/suturing.json` does NOT exist; only `scenes/simple_suturing.json` does. The fallback in `_create_scene_for_task:30` synthesizes a suturing scene from `InstrumentConfig` + `TissueConfig` defaults, so the test will work as long as the schema constructs cleanly.)
3. **`run_dreamer_training`** → `DreamerSubprocess.spawn()` → `_subprocess_main` (in child process) → `sys.stdout = _JsonStdout(child_stdout)` (line 23) — the test exercises this line via the protocol round-trip
4. **`run_dreamer_training`** → periodic checkpoint branch (line 318-323) writes `checkpoint_500.pt` when `step % eval_every == 0`
5. **`run_dreamer_training`** → `final.pt` write (line 337) and `training_metrics.json` write (line 349) — D-CKPT-01's three-file assertion
6. **D-CKPT-02**: `run_dreamer_training` → `_find_latest_checkpoint` — exercised after the run
7. **D-COLOR-01**: `from surg_rl.benchmark.plots import DREAMER_COLOR` — independent import path; tests the constant is the post-Phase-26 value

### Common Landmines
- **`scenes/suturing.json` does NOT exist** — only `scenes/simple_suturing.json` does. The fallback in `_create_scene_for_task:30-90` synthesizes a suturing scene from `InstrumentConfig(type=NEEDLE_DRIVER)` + `TissueConfig(tissue_type=ORGAN, name="liver")` defaults. The test will work as-is. If the fallback schema ever changes to require a real scene file, the test would break; planner verifies during planning.
- **`_run_subprocess_loop` currently returns immediately** after the `READY` handshake because `_build_agent` returns `None` (line 127-131 is a stub: "This will be implemented when dreamerv3 is available"). On a real GPU + dreamerv3 host, the loop WILL execute the `TRAIN` branch and yield metrics. On macOS, the test is skipped (D-SKIP-01), so the stub return doesn't matter. **On CI without dreamerv3 installed**, the test still skips (D-SKIP-01 condition B). The test only runs on a host that has BOTH `dreamerv3` AND `jax` AND a GPU.
- **`eval_every=500` with `total_steps=1000`**: the periodic branch fires at `step=500` and `step=1000` (both `% 500 == 0`). The `step=1000` checkpoint coincides with the loop end, so the `final.pt` write at line 337 may overwrite or coexist with `checkpoint_1000.pt`. The test asserts `checkpoint_500.pt` exists, NOT `checkpoint_1000.pt`, to avoid the overwrite/coexist ambiguity. (D-CKPT-01)
- **`os.fdopen(2, "w", buffering=1)`** at `subprocess.py:24` — the stderr line, unchanged by Phase 26. The test should NOT assert anything about stderr unless explicitly needed; the JSONL stdout protocol is the focus.
- **Pydantic v2 cycle resolution pattern** (from Phase 29 D-SCHEMA-01) does NOT apply here — Phase 30 has no schema changes, only a new test file. The pattern is irrelevant.
- **macOS PyBullet soft-body `xfail` precedent** at `test_simulators.py` is for tests that RUN and are EXPECTED TO FAIL. Phase 30's test SKIPS (does not run) on macOS — different semantics. Do not copy the xfail marker; copy only the skipif-via-find_spec pattern.

</code_context>

<deferred>
## Deferred Ideas

- **Per-method granular skipif** (vs. module-level `pytestmark`) — could be added for more granular skip reporting, but module-level is sufficient. Not in v0.4.2 scope.
- **Migration of the 7 existing `tests/test_dreamer_*.py` files to `tests/dreamer/`** — separate cleanup phase. The D-30-04 carry-forward says they're not migrated as part of Phase 30; doing so would inflate scope.
- **Adding a `--dreamer-e2e-steps=...` pytest CLI option** to override the 1000-step default — could be useful for developers running locally who want a 100-step quick check. Not required by the success criteria; deferred.
- **Asserting the absence of `#4B0082` (pre-fix indigo color) in subprocess captured logs** — could be added as a negative assertion alongside D-COLOR-01, but the constant is in `benchmark/plots.py`, never in the dreamer subprocess. The check would always pass regardless of the Phase 26 fix being applied. Not useful.
- **D-30-04 wording vs. D-LOC-01 reality** — the roadmap says "if `tests/dreamer/` does not exist as a directory, use `tests/test_dreamerv3_subprocess_e2e.py` at the top level (planner checks before plan execution)." D-LOC-01 chose to CREATE the directory instead. This is a deliberate decision; the roadmap wording is "fallback if directory does not exist" which is now satisfied (directory WILL exist after the test file is added). No roadmap amendment needed.
- **GPU-based CI runner configuration** — out of scope per the roadmap's "Out of scope" list (CI config is operations work, not code; assume CI with GPU exists or will be added separately). If the test never runs because no CI runner is configured, that is a separate ops problem.
- **Cleaning up 421 ruff issues in `src/surg_rl/dreamer/`** — deferred per v0.4.2 PROJECT.md tech debt list. The new test file is not expected to be ruff-clean beyond the standard lint config.
- **Real GPU + dreamerv3 E2E in CI** — the test is added; running it requires CI infrastructure. If the test silently skips on every dev machine AND every CI runner, the DMV3-E2E-01..05 requirements will appear "untested" in coverage reports. This is documented in `STATE.md` Blocker #4; ops work to add a GPU CI runner is not in v0.4.2 scope.

</deferred>

---

*Phase: 30-DreamerV3 Real-Subprocess E2E Test*
*Context gathered: 2026-06-12 from v0.4.2 roadmap (D-30-01..05 pre-decided) + discussion (D-LOC-01, D-STEPS-01, D-SKIP-01..03, D-COLOR-01..03, D-CKPT-01..02)*

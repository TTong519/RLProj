# Phase 30: DreamerV3 Real-Subprocess E2E Test — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-12
**Phase:** 30-dreamerv3-real-subprocess-e2e-test
**Areas discussed:** Test file location, Step count for smoke test, Skip mechanism: skipif vs xfail, DREAMER_COLOR verification path, Checkpoint assertion target

---

## Test file location

| Option | Description | Selected |
|--------|-------------|----------|
| Create `tests/dreamer/` subdir | New dir + `__init__.py`, place `test_dreamerv3_subprocess_e2e.py` inside. Matches roadmap SC#1 wording exactly. Future dreamer tests have a home; existing 7 `test_dreamer_*.py` files NOT migrated. | ✓ |
| Top-level `tests/test_dreamerv3_subprocess_e2e.py` | Put file at `tests/` top level alongside 7 existing `test_dreamer_*.py` files. Matches D-30-04 fallback; SC#1 wording technically violated. | |

**User's choice:** Create `tests/dreamer/` subdir (Recommended)
**Notes:** User chose the recommended option without modification. The 7 existing top-level `test_dreamer_*.py` files stay as-is (out of scope per D-30-04).

---

## Step count for smoke test

| Option | Description | Selected |
|--------|-------------|----------|
| 100 env steps | Roadmap floor; exercises ~10 metric messages through `_JsonStdout`. CI runtime ~30-60s. | |
| 10 env steps | ~10× faster CI; still proves spawn + pipe round-trip. Risks missing race conditions. | |
| 1000 env steps (heavier) | ~3-5 min CI runtime; ~100 metric messages; closer to 'real run' statistical confidence. | ✓ |

**User's choice:** 1000 env steps (heavier)
**Notes:** User opted for the heaviest option, prioritizing protocol round-trip confidence over CI speed. The 100-step floor in the roadmap was a placeholder; the user wants the heavier smoke.

---

## Skip mechanism: skipif vs xfail

| Option | Description | Selected |
|--------|-------------|----------|
| `@pytest.mark.skipif` on (GPU + dreamerv3 + jax) | Module-level gate; SKIPS before run on macOS. Matches SC#5 wording exactly. Lifts `importlib.util.find_spec` pattern from `tests/test_rllib_train.py:62`. | ✓ |
| `@pytest.mark.xfail` (PyBullet precedent) | RUNS, then fails as expected. On macOS produces XFAIL output. Cost: 5-10s wasted spawn attempt. | |
| Both: skipif gate + xfail inner | Module skipif on macOS + xfail only when running on GPU. Most granular; added complexity. | |

**User's choice:** `@pytest.mark.skipif` on (GPU + dreamerv3 + jax) (Recommended)
**Notes:** User chose the recommended option. The roadmap's D-30-02 phrase "xfail-skip expected" is shorthand for "expected to skip on macOS" — NOT a prescription of the xfail marker. The PyBullet soft-body xfail precedent is for tests that RUN and are expected to fail; Phase 30's test SKIPS (does not run) on macOS.

---

## DREAMER_COLOR verification path

| Option | Description | Selected |
|--------|-------------|----------|
| Import-level constant assertion | `from surg_rl.benchmark.plots import DREAMER_COLOR; assert DREAMER_COLOR == "#FF8C00"`. Mirrors `test_benchmark_plots.py`. Zero subprocess complexity. | ✓ |
| Call PlotRenderer + grep rendered output | Render a tiny plot via `PlotRenderer` on dummy data, grep SVG/PNG/HTML for `#FF8C00`. Truer to "subprocess output contains" wording. | |
| Inject banner into `_subprocess_main` | Add a `print(DREAMER_COLOR)` line to `subprocess.py` purely to satisfy the test. Violates Phase 26 "no functionality changes" principle. | |
| Negative assert: no `#4B0082` in captured logs | Combined import-level + negative check for pre-fix indigo. Most aligned with "fix is active" framing. | |

**User's choice:** Import-level constant assertion (Recommended)
**Notes:** User chose the recommended option. The `DREAMER_COLOR` constant is in `src/surg_rl/benchmark/plots.py`, never referenced by the dreamer subprocess. Asserting it appears in subprocess stdout would require a production-code banner change, which violates Phase 26's no-functionality-changes principle. The unit test in `test_benchmark_plots.py` already covers the constant at import level; D-COLOR-01 repeats the assertion to prove the constant survives a full `import surg_rl.dreamer.training` round-trip in the E2E scenario.

---

## Checkpoint assertion target

| Option | Description | Selected |
|--------|-------------|----------|
| `eval_every=500` → assert `final.pt` + `checkpoint_500.pt` | Use `eval_every=500` so periodic checkpoints ARE written (1000/500 = 2 periodic checkpoints at step 500 and 1000). Assert `final.pt` + at least one periodic `checkpoint_500.pt`. | ✓ |
| Assert directory + (`final.pt` OR `training_metrics.json`) | Match SC#5's "or" alternative exactly. No `eval_every` tuning. | |
| Assert `training_metrics.json` only | Most direct E2E check on Phase 26 typo fix. Bypasses "checkpoint file" half. | |

**User's choice:** `eval_every=500` → assert `final.pt` + `checkpoint_500.pt` (Recommended)
**Notes:** User chose the recommended option. With `total_steps=1000, eval_every=500`, the periodic-checkpoint branch at `training.py:318` fires at `step=500` and `step=1000`, writing `checkpoint_500.pt` and `checkpoint_1000.pt`. The test asserts `final.pt` (Phase 26 typo fix target) + `checkpoint_500.pt` (proves periodic branch fires) + `training_metrics.json` (verifies `indent=2` is in effect). The `step=1000` checkpoint is intentionally NOT asserted to avoid the overwrite/coexist ambiguity with `final.pt`.

---

## OpenCode's Discretion

- Whether to use `tmp_path` fixture vs. hardcoded `models/dreamerv3/suturing_state_e2e/` path
- Module-level `pytestmark` vs. per-test skipif
- Whether to add `--dreamer-e2e-steps=...` CLI override
- Whether to assert `_JsonStdout` was used (vs. pre-fix `os.fdopen`) by introspecting subprocess `sys.stdout` type
- Exact form of `__init__.py` in `tests/dreamer/` (empty vs. absent)

## Deferred Ideas

- **Per-method granular skipif** — deferred; module-level sufficient
- **Migration of 7 existing `test_dreamer_*.py` to `tests/dreamer/`** — separate cleanup phase, not v0.4.2
- **`--dreamer-e2e-steps` CLI option** — could be useful for local quick-checks, not required
- **Negative assert for `#4B0082` (pre-fix indigo)** — would always pass regardless of Phase 26 fix being applied; not useful
- **D-30-04 wording vs. D-LOC-01 reality** — roadmap says "fallback if directory does not exist"; directory WILL exist after the test file is added; no roadmap amendment needed
- **GPU-based CI runner configuration** — out of scope (ops work, not code); if the test never runs, that's a separate ops problem
- **Cleanup of 421 ruff issues in `src/surg_rl/dreamer/`** — deferred per v0.4.2 PROJECT.md tech debt list

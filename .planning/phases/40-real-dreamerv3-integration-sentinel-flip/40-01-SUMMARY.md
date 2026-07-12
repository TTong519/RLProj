---
phase: 40-real-dreamerv3-integration-sentinel-flip
plan: 01
subsystem: dreamer
tags: [dreamerv3, jax, subprocess, tdd, checkpoint, regression-guard]
requires:
  - 24-dreamerv3-world-models (subprocess protocol + stubs)
  - 30-dreamerv3-real-subprocess-e2e-test (sentinel skipif pattern)
provides:
  - "_build_agent real implementation returning {agent, env, checkpoint, replay, step} bundle"
  - "test_dreamerv3_regression_guard.py (DMV3-09 CPU-runnable source-inspection guard)"
  - "extended TestProcessIsolationImport (dreamerv3 sys.modules + AST module-level-import guard)"
affects:
  - "40-02 (unpacks _build_agent bundle in _train_loop/_evaluate/_save_checkpoint/_load_checkpoint)"
  - "40-03 (training.py checkpoint glob + resume test)"
  - "40-04 (CI dreamer-gpu job runs the runtime GREEN path)"
tech-stack:
  added: []
  patterns:
    - "PyPI 1.5.0 object API: Agent(obs_space, act_space, step, config) — 4-arg ctor (D-04)"
    - "embodied.Checkpoint attribute-registration resume: cp.step/cp.agent/cp.replay + cp.load_or_save() (D-09)"
    - "SC#5 JAX isolation: all jax/dreamerv3/embodied imports inside function body, AST-guarded at module level"
    - "TDD RED→GREEN: source-inspection regression guard (AST Return(None) walk) fails closed on stub regression"
key-files:
  created:
    - tests/dreamer/test_dreamerv3_regression_guard.py
    - .planning/phases/40-real-dreamerv3-integration-sentinel-flip/deferred-items.md
  modified:
    - src/surg_rl/dreamer/subprocess.py
    - tests/test_dreamer_subprocess.py
decisions:
  - "wrapper.py action_space left unchanged (discretion D-05/A4) — _build_agent builds the dict-form act_space {'action': Box, 'reset': Discrete(2)} from the wrapper's bare Box, keeping clean env-action-space semantics in the wrapper"
  - "Regression guard uses AST Return(value=Constant(None)) + bare-Return walk (not string match) to avoid false positives on docstrings/comments mentioning None"
  - "Extended JAX-leak guard walks module-body top-level ast.Import/ImportFrom nodes only (not nested) for jax/dreamerv3/embodied/optax"
metrics:
  duration: ~3m
  completed: 2026-07-12
  tasks: 2
  files: 4
status: complete
---

# Phase 40 Plan 01: Real _build_agent + DMV3-09 Regression Guard + Extended JAX-Leak Guard Summary

Real DreamerV3 `_build_agent` against the PyPI 1.5.0 object API (4-arg `Agent` ctor + `embodied.Checkpoint` attribute-registration resume) plus the two CPU-runnable guards (DMV3-09 source-inspection regression guard + SC#5 AST module-level-import leak guard) that protect the sentinel flip.

## What Was Built

### Task 1 (RED) — Regression guard + extended JAX-leak guard
- **`tests/dreamer/test_dreamerv3_regression_guard.py`** (NEW): CPU-runnable source-inspection guard with NO module-level `pytestmark` skipif (runs unconditionally on every PR per D-10). Uses `inspect.getsource(_build_agent)` + `textwrap.dedent` + `ast.parse` + an AST walk for `ast.Return` nodes whose `.value` is `ast.Constant(value=None)` OR a bare `return` (`Return(value=None)`). Failure message tags `DMV3-09`. Against the Phase 24 None-valued stub this guard FAILED (RED) — verified.
- **`tests/test_dreamer_subprocess.py`** (MODIFIED): `TestProcessIsolationImport` extended with `test_no_module_level_jax_dreamerv3_or_embodied_imports` — AST source inspection asserting `subprocess.py` module-body top-level nodes have no `import jax/dreamerv3/embodied/optax` (SC#5). The existing `test_no_jax_or_dreamerv3_loaded_in_main_process` already asserted both `jax` and `dreamerv3` absent from `sys.modules` after a fresh import (no change needed there). Added `ast` and `textwrap` imports at module top of the test file.

### Task 2 (GREEN) — Real `_build_agent` against PyPI 1.5.0 object API
- **`src/surg_rl/dreamer/subprocess.py`** `_build_agent` (MODIFIED, lines 125–205): stub `return None` replaced with a real implementation. All `jax`/`dreamerv3`/`embodied`/`optax` imports live INSIDE the function body (SC#5). The function:
  1. Locally imports `embodied`, `dreamerv3.agent.Agent`, `gymnasium.spaces`, `pathlib.Path`, and the project helpers `GymToEmbodiedWrapper` + `_create_scene_for_task` + `_create_env` (lazy/local per CLAUDE.md rl-subpackage import-chain rule).
  2. Constructs the `SurgicalEnv` inside the child via `_create_scene_for_task(task, obs_type, pixel_resolution)` + `_create_env(scene)`, then wraps it in `GymToEmbodiedWrapper` (D-05 — NOT dreamerv3's gym-0.19 adapter).
  3. Builds `embodied.Counter()` for the `step` arg (VERIFY on GPU host).
  4. Builds `embodied.Config(**config.get("agent", {}))` (VERIFY ctor).
  5. Builds `obs_space = dict(wrapped.observation_space)` and `act_space = {"action": wrapped.action_space, "reset": spaces.Discrete(2)}` (Agent ctor extracts `act_space['action']` per research A4).
  6. Constructs `Agent(obs_space, act_space, step, agent_config)` — 4 positional args, PyPI 1.5.0 object API (D-04).
  7. Constructs `embodied.replay.Replay(length=config.get("replay_length", 10_000))` (VERIFY ctor).
  8. Creates `models/dreamerv3/{task}_{obs_type}/` (mkdir parents/exist_ok — defensive, Rule 2), registers `embodied.Checkpoint(ckpt_dir / "checkpoint.ckpt")` with `cp.step`/`cp.agent`/`cp.replay`, and calls `cp.load_or_save()` (D-09 resume-or-init).
  9. Returns a bundle dict `{"agent", "env", "checkpoint", "replay", "step"}` for 40-02's stubs to unpack.
- **`src/surg_rl/dreamer/wrapper.py`** left UNCHANGED (discretion per D-05/A4 — see Decisions).

## Verification Results

| Check | Command | Result |
|-------|---------|--------|
| RED state (Task 1) | `PYTHONPATH=src pytest tests/dreamer/test_dreamerv3_regression_guard.py -v` | FAILED as expected (DMV3-09 message) against the None-valued stub |
| Extended JAX-leak guard | `pytest tests/test_dreamer_subprocess.py::TestProcessIsolationImport -v` | 3/3 PASSED |
| GREEN state (Task 2) | `pytest tests/dreamer/test_dreamerv3_regression_guard.py -v` | PASSED (no `return None` in `_build_agent`) |
| Full non-torch dreamer/subprocess suite | `pytest tests/test_dreamer_subprocess.py tests/dreamer/test_dreamerv3_regression_guard.py -v` | 30/30 PASSED |
| Lint | `ruff check src/surg_rl/dreamer/subprocess.py tests/dreamer/test_dreamerv3_regression_guard.py tests/test_dreamer_subprocess.py` | clean |
| Format | `black --check` | clean (after auto-fix of trailing newline) |

### Source-inspection acceptance criteria
- `grep -v '^#' tests/dreamer/test_dreamerv3_regression_guard.py | grep -c 'pytest.mark.skipif'` == 0 — PASS
- `grep -cE 'make_agent|make_replay|make_stream|make_logger|elements\.' src/surg_rl/dreamer/subprocess.py` == 0 — PASS
- `grep -c 'FromGym' src/surg_rl/dreamer/subprocess.py` == 0 — PASS
- `grep -v '^#' src/surg_rl/dreamer/subprocess.py | grep -c 'Agent('` >= 1 — PASS (3: docstring + comment + call)
- `embodied.Checkpoint(` present — PASS
- `cp.load_or_save` present — PASS
- `GymToEmbodiedWrapper` present — PASS
- AST module-level import walk for jax/dreamerv3/embodied/optax → hits: [] — PASS
- `_train_loop` / `_evaluate` / `_save_checkpoint` / `_load_checkpoint` stubs untouched (40-02 owns them) — PASS

## Decisions Made

1. **wrapper.py action_space left unchanged (discretion D-05/A4).** `_build_agent` builds the dict-form `act_space = {"action": wrapped.action_space, "reset": spaces.Discrete(2)}` from the wrapper's bare `spaces.Box`. This keeps the wrapper's semantics clean (its `action_space` is the env's action space) and centralizes the embodied-protocol shaping in `_build_agent`. The wrapper's `step()` already handles dict actions with an `"action"` key (line 115–116), so the flow is consistent. Could not VERIFY against the installed `Agent` ctor (dreamerv3 not installed on macOS); the GPU job (40-04) confirms at runtime.
2. **Regression guard uses AST `Return(value=Constant(None))` + bare-`Return` walk** (not a naive `"return None" in source` string match) to avoid false positives on docstrings/comments mentioning `None`. A bare `return` (`Return(value=None)` at the AST level) is also caught — both shapes indicate the function can yield `None`.
3. **Extended JAX-leak guard walks only `tree.body` top-level nodes** (module-scope imports), not `ast.walk` over the whole tree, so imports inside function bodies (which are SC#5-compliant) don't trip the guard. Checks `jax`/`dreamerv3`/`embodied`/`optax` top-level package names.
4. **`ckpt_dir.mkdir(parents=True, exist_ok=True)` added** before `embodied.Checkpoint(...)` (Rule 2 — defensive: ensure the checkpoint dir exists before the checkpoint tries to write; the upstream `Checkpoint` may not create parent dirs itself).

## Deviations from Plan

### Auto-fixed Issues
- **[Rule 2] Added `ckpt_dir.mkdir(parents=True, exist_ok=True)` before `embodied.Checkpoint(...)`.** The plan's action did not explicitly create the checkpoint directory. Creating it defensively ensures `cp.load_or_save()` can write `checkpoint.ckpt` on a fresh run. Files modified: `src/surg_rl/dreamer/subprocess.py`. Commit: `1c1ab4b`.

### Discretion exercised (in-plan)
- **wrapper.py action_space left unchanged.** The plan's action said to update `wrapper.py`'s `action_space` property to return a dict with an `"action"` key, OR leave it unchanged and document in the summary if the bare Box is accepted. Per A4/D-05 discretion, left unchanged and documented in Decisions above. The `_build_agent` builds the dict form from the wrapper's bare Box.

## Known Stubs

None. The `_build_agent` implementation is complete (source-level). Its runtime GREEN (actually constructing a real `dreamerv3.Agent`) is GPU-gated and deferred to the CI `dreamer-gpu` job (40-04) per INV-8 — locally the runtime path skips because `dreamerv3`/`embodied`/`optax` are not installed on macOS. The four remaining stubs (`_train_loop` / `_evaluate` / `_save_checkpoint` / `_load_checkpoint`) are owned by 40-02 and were NOT touched by this plan (verified — stubs unchanged at their original lines).

## TDD Gate Compliance

- **RED gate:** commit `936aa88` — `test(40-01): add _build_agent regression guard (RED) + extend JAX-leak guard`. The regression guard FAILED against the current None-valued stub (verified: `test_build_agent_does_not_return_none` FAILED with DMV3-09 message before the GREEN implementation landed).
- **GREEN gate:** commit `1c1ab4b` — `feat(40-01): real _build_agent (PyPI 1.5.0 object API) + checkpoint registration`. The regression guard now PASSES (no `return None` in `_build_agent` source).
- Both gates present in git log in the correct order. No REFACTOR gate needed (no cleanup-only changes beyond a trailing-newline style fix in `0e772df`).

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries beyond what the plan's `<threat_model>` already accounted for (T-40-01 CONFIG dict, T-40-02 checkpoint pickle, T-40-03 XLA memory — all `accept`/`mitigate` dispositions unchanged). The `ckpt_dir.mkdir` is a local-disk filesystem operation within the existing `models/dreamerv3/` trust boundary.

## Self-Check: PASSED

- FOUND: `tests/dreamer/test_dreamerv3_regression_guard.py`
- FOUND: `src/surg_rl/dreamer/subprocess.py`
- FOUND: `tests/test_dreamer_subprocess.py`
- FOUND: commit `936aa88` (RED)
- FOUND: commit `1c1ab4b` (GREEN)
- FOUND: commit `0e772df` (style)
- RED gate verified FAILED on stub; GREEN gate verified PASSED after implementation.
- 30/30 non-torch dreamer/subprocess tests pass on CPU.

## Notes for Downstream Plans

- **40-02:** `_build_agent` returns a **dict bundle** `{agent, env, checkpoint, replay, step}` — NOT a bare agent. The downstream `_train_loop`/`_evaluate`/`_save_checkpoint`/`_load_checkpoint` must unpack it (the `_run_subprocess_loop` dispatch at line 83 passes the bundle as `agent`; the `agent is None` gate at lines 87/97 passes for a non-None dict; the cleanup at line 122 `agent.close()` raises `AttributeError` on a dict which `contextlib.suppress(Exception)` swallows — 40-02 may want to give the bundle a `close()` or adjust the cleanup).
- **40-02:** VERIFY the `embodied.*` symbols (`Counter`, `Config`, `replay.Replay`, `Checkpoint`, `Space`) against the installed dreamerv3 1.5.0 package on the GPU host — items marked VERIFY in `_build_agent` source comments.
- **40-03:** `_find_latest_checkpoint` glob update (`*.ckpt`) and the resume test are owned by 40-03.
- **40-04:** The CI `dreamer-gpu` job satisfies the runtime GREEN (actually constructing a real agent) — this plan only delivers source-level GREEN + CPU-runnable guards.
- **Pre-existing env issue:** torch + libomp fatal abort on Python 3.14 at import time (logged in `deferred-items.md`). Reproduces on commit `936aa88` (before GREEN edits) — NOT caused by this plan. The e2e test's module-level `_gpu_available()` does `import torch` which triggers it. Non-torch dreamer/subprocess suite (30 tests) passes. Out of v0.6.0 scope.
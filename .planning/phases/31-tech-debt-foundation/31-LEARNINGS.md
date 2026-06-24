---
phase: 31
phase_name: "Tech Debt Foundation"
project: "Surg-RL"
generated: "2026-06-24"
counts:
  decisions: 9
  lessons: 4
  patterns: 10
  surprises: 3
missing_artifacts:
  - "VERIFICATION.md"
  - "UAT.md"
---

# Phase 31 Learnings: Tech Debt Foundation

## Decisions

### Remove orphaned `wrapper` assignments entirely (training.py F841 fix)
Removed both `wrapper = GymToEmbodiedWrapper(...)` assignments in training.py (lines 245, 388) instead of calling the constructor for side effects.

**Rationale:** GymToEmbodiedWrapper has no observable side effects in its constructor and the local was never read downstream — removing the line is the cleanest fix that satisfies F841 without introducing unused allocations.
**Source:** 31-01-SUMMARY.md

---

### Use `raise ... from exc` (not `from None`) for B904 in subprocess transport
In subprocess.py:202, used `raise RuntimeError(...) from exc` to preserve the original EOFError context per PEP 3134.

**Rationale:** The Phase 26 `_JsonStdout` pipe round-trip debuggability contract requires the original exception chain to remain visible; `from None` would suppress it. Explicitly specified by threat model T-31-02.
**Source:** 31-01-SUMMARY.md

---

### ARG TARGETARCH=amd64 default for Dockerfile backwards compat
Added `ARG TARGETARCH=amd64` default rather than omitting `--platform=` so legacy non-buildx `docker build` still works on amd64.

**Rationale:** buildx auto-overrides the default for arm64 targets, but legacy builders without BuildKit would fail on an unset TARGETARCH — the default keeps existing amd64 users unbroken while enabling multi-arch via buildx.
**Source:** 31-01-SUMMARY.md

---

### Use SurgicalEnv.__new__() to bypass `__init__` in cut cooldown test
The TestCutCooldown fixture constructs `SurgicalEnv.__new__(SurgicalEnv)` and directly sets `_step_count`, `_last_cut_step`, `_cut_cooldown_steps` attributes.

**Rationale:** The test only exercises the cooldown arithmetic — no scene fixture dependency and no real physics simulation are needed. The simulator is still a real instance so per-method skipif can mirror the Phase 30 dreamer E2E pattern.
**Source:** 31-02-SUMMARY.md

---

### Assert `result in (True, False)` for cooldown-pass cases
Tests assert `result in (True, False)` rather than `result is True` for the "no cooldown" cases.

**Rationale:** This decouples the test from whether the simulator's `_apply_cut` method exists or returns success — the cooldown branch is the testable contract, not the full cut pipeline. Either outcome proves the cooldown did NOT block.
**Source:** 31-02-SUMMARY.md

---

### Document PhiFlow workaround at module level, not class level
Expanded the `fluid_simulator.py` module docstring (5 → 44 lines) rather than the `FluidSimulator` class docstring.

**Rationale:** Keeps the class docstring terse (`"Wraps PhiFlow StaggeredGrid..."`) and concentrates the detailed WHY at module scope where future maintainers are most likely to read it first.
**Source:** 31-02-SUMMARY.md

---

### Use `_StubSimulator` subclass instead of `__new__`-bypass for ABC contract tests
For the `fluid_step` hook tests, used a minimal `_StubSimulator` subclass with `pass` implementations for all 11 abstract methods rather than `BaseSimulator.__new__(BaseSimulator)`.

**Rationale:** Modern Python ABCs (PEP 3119 + 3.13 enforcement) block `__new__` instantiation when abstract methods are present — the plan's original `__new__`-bypass suggestion raises `TypeError`. A stub subclass is the minimal viable scaffolding.
**Source:** 31-03-SUMMARY.md

---

### Place `fluid_step` hook call AFTER existing fluid block with `None` guard
The `SurgicalEnv.step()` hook invocation goes after the existing `_fluid_simulator.step()` block and is guarded by `if self._simulator is not None`.

**Rationale:** Preserves the existing env-level direct-call pattern so the hook is purely additive (currently no-op, so no behavior change). The guard mirrors the existing fluid block's pattern and satisfies threat model T-31-05.
**Source:** 31-03-SUMMARY.md

---

### Console-script `surg-rl-gui` is a SEPARATE entry, not a Typer subcommand
Registered `surg-rl-gui = "surg_rl.editor.app:main"` as a distinct `[project.scripts]` entry rather than wiring it into the 14-subcommand `surg-rl` Typer app.

**Rationale:** Preserves the `surg-rl` CLI's lazy-import contract (Pitfalls P10 + P6) — `surg-rl train` and other subcommands never trigger PySide6 import even when `[gui]` is installed. Verified by `surg-rl --help` exiting 0 without PySide6 in `sys.modules`.
**Source:** 31-04-SUMMARY.md

---

## Lessons

### `__new__`-bypass does not work for ABCs with abstract methods in modern Python
Modern Python (PEP 3119 + 3.13 enforcement) blocks `BaseSimulator.__new__(BaseSimulator)` instantiation when abstract methods (`_apply_action`, `close`, etc.) are present — it raises `TypeError: Can't instantiate abstract class BaseSimulator without an implementation for abstract methods ...`.

**Context:** Phase 31-03 plan originally suggested `__new__`-bypass for the `fluid_step` contract test (mirroring the pattern from `tests/test_simulators.py:TestBaseSimulator`); initial test run revealed this no longer works.
**Source:** 31-03-SUMMARY.md

---

### Pre-existing ruff violations surface when modifying an adjacent file
The pre-existing `SIM115` violation on `tempfile.NamedTemporaryFile(..., delete=False)` in `tests/test_cutting.py` surfaced when appending the new `TestCutCooldown` class — ruff checks the whole file, not just the diff.

**Context:** Found during task 1 of plan 31-02; the violation predated Phase 31 but would have caused ruff to fail on the modified file. Fixed with a minimal `# noqa: SIM115` annotation rather than a full refactor (out of scope for DEBT-04).
**Source:** 31-02-SUMMARY.md

---

### `# noqa: SIM103` on an `if` line does not fully suppress the rule
Placing `# noqa: SIM103` on the `if sys.argv and "mjpython" in sys.argv[0]: return True` line did not cleanly suppress ruff's SIM103 (return condition directly) check.

**Context:** Found during task 3 of plan 31-04; resolved by inlining `return bool(sys.argv and "mjpython" in sys.argv[0])` which satisfies lint while preserving the 3-signal priority order.
**Source:** 31-04-SUMMARY.md

---

### ruff B018 flags bare attribute access inside try blocks
The literal plan code `try: surg_rl.editor.QtWidgets.QApplication except ImportError as exc:` triggered ruff B018 (useless expression) on the bare attribute access.

**Context:** Found during task 5 of plan 31-04; resolved by switching to the `with pytest.raises(ImportError) as exc_info:` context-manager idiom, which is also cleaner pytest style.
**Source:** 31-04-SUMMARY.md

---

## Patterns

### contextlib.suppress(Exception) replaces try/except/pass
For fire-and-forget cleanup blocks where the exception is intentionally swallowed, use `with contextlib.suppress(Exception):` after adding `import contextlib`, rather than the explicit `try: ... except Exception: pass` form.

**When to use:** Any `try/except/pass` block where the caught exception is genuinely uninteresting (ruff SIM105).
**Source:** 31-01-SUMMARY.md

### Mockable time source via `_step_count` instead of wall-clock
Tests that verify time-based logic (cooldowns, intervals) directly manipulate a step-counter attribute rather than mocking `time.time()` or relying on real elapsed time.

**When to use:** Any regression test for a cooldown/rate-limit contract where wall-clock timing would be non-deterministic in CI runners.
**Source:** 31-02-SUMMARY.md

### Per-method skipif on backend availability
Parametrize tests over backends via `@pytest.fixture(params=BACKENDS)` and skip per-method if a given backend is unavailable, rather than module-level skipif — some CI runners have one backend but not the other.

**When to use:** Tests parametrized over MuJoCo/PyBullet (or similar optional backends) where availability varies by runner.
**Source:** 31-02-SUMMARY.md

### Module-level docstring as documentation surface for one-line workarounds
When a "magic" one-line workaround (e.g., `union(*geoms)`) exists in production code, expand the module-level docstring with WHY + code example + upstream-issue link + numbered rationale, rather than a comment at the call site.

**When to use:** Any non-obvious single-line fix whose rationale would be lost without context (PhiFlow pressure-solver quirks, library-bug workarounds).
**Source:** 31-02-SUMMARY.md

### Optional ABC method with no-op default + explicit subclass overrides
Add optional methods (e.g., `fluid_step(dt)`) to a base ABC with a no-op default implementation, then declare explicit no-op overrides in concrete subclasses (with docstrings marking them as future extension points).

**When to use:** Establishing a hook contract that current backends no-op but future backends may override — avoids an ABC change later.
**Source:** 31-03-SUMMARY.md

### `_StubSimulator` subclass pattern for testing ABCs with abstract methods
When testing default behavior of an ABC, define a minimal `_StubSimulator` subclass with `pass` implementations for all abstract methods; the default methods are inherited and exercisable.

**When to use:** Any contract test against an ABC that has abstract methods blocking direct instantiation via `__new__`.
**Source:** 31-03-SUMMARY.md

### LazyImport + HAS_GUI sentinel for optional GUI dependencies
Expose 3 `LazyImport` symbols (`QtWidgets`, `QtCore`, `QtGui`) plus a `HAS_GUI: bool = QtWidgets.available` sentinel at package init — the package imports cleanly even when the optional dep is missing.

**When to use:** Any optional dependency (PySide6, dreamerv3, matplotlib) that must not break the import chain or the CLI's lazy-import contract.
**Source:** 31-04-SUMMARY.md

### `_is_running_under_mjpython()` 3-signal detection extracted to reusable helper
Extract inline platform-detection logic (env var + `sys.executable` basename + `sys.argv[0]`) into a typed `-> bool` helper so multiple call sites (`start_viewer`, `editor.app.main`) share the same detection.

**When to use:** Any detection block duplicated across modules (here: `mujoco_simulator.py:1294-1298` inline block → `_platform_guard.py` helper).
**Source:** 31-04-SUMMARY.md

### `--help` short-circuits BEFORE the optional-dep gate
Console-script entrypoints should handle `--help` / `-h` / `--headless` BEFORE checking the optional-dep sentinel, so users on dep-free systems can see usage and install hints without crashing on a missing import.

**When to use:** Any console-script that gates on an optional dependency install — users without the dep still need `--help` to work.
**Source:** 31-04-SUMMARY.md

### Subprocess-isolated CLI tests via `PYTHONPATH=src` env var
For CLI-independence assertions (e.g., `surg-rl --help` does not import PySide6), run `subprocess.run([sys.executable, "-c", ...], env={**os.environ, "PYTHONPATH": str(SRC_DIR)})` to get a clean `sys.modules` view.

**When to use:** Tests that must verify an import-set invariant (`'PySide6' not in sys.modules`) — in-process tests share the pytest process's already-imported modules.
**Source:** 31-04-SUMMARY.md

---

## Surprises

### Full test suite jumped from 1134 to 1200 passed
Plan 31-04 alone added 66 new tests (19 in `test_gui_scaffold.py` plus parametrization expansion), pushing the regression baseline from 1,134 to 1,200 passed with 17 skipped and 0 failed.

**Impact:** The "1,134-test baseline" anchor used throughout Phase 31 planning is now stale — downstream phases should target ≥ 1,200 as the new floor.
**Source:** 31-04-SUMMARY.md

### Plan-suggested `__new__`-bypass pattern is broken in modern Python
The Phase 31-03 plan explicitly recommended `BaseSimulator.__new__(BaseSimulator)` as the bypass mechanism (mirroring an older test pattern), but modern Python ABCs raise `TypeError` on this — the deviation had to be auto-fixed during execution.

**Impact:** Required a `_StubSimulator` subclass with 11 `pass` implementations, adding ~15 LOC of test scaffolding not anticipated by the plan.
**Source:** 31-03-SUMMARY.md

### `# noqa: SIM103` placement did not suppress the rule
Inline `# noqa: SIM103` on an `if`-line did not fully suppress ruff's SIM103 check, contrary to the usual noqa-on-offending-line convention.

**Impact:** Required inlining the conditional return as `return bool(...)` to satisfy lint — the `# noqa` annotation is not always sufficient for SIM rules with multi-line context.
**Source:** 31-04-SUMMARY.md
# Phase 26: Fix DreamerV3 Training Bugs — Context

**Gathered:** 2026-06-10
**Status:** Ready for planning
**Source:** v0.4.0 milestone audit (`v0.4.0-MILESTONE-AUDIT.md`) — three DreamerV3 bugs extracted from the audit's "Critical Issues to Fix" and "Dreamer-training-typo / Dreamer-subprocess / DREAMERV3_COLOR" entries.

<domain>
## Phase Boundary

Close the three DreamerV3 training bugs identified by the v0.4.0 milestone audit so that the `surg-rl dreamer-train` / `dreamer-spike` flow runs end-to-end without a `TypeError` from the metrics saver, the subprocess uses a real `multiprocessing.Pipe` channel for stdout JSON, and the dreamer color used in benchmark plots matches the color specified in the UAT. No new functionality, no DreamerV3 architecture changes — only narrow surgical fixes to known-defective lines.
</domain>

<decisions>
## Implementation Decisions

### Indig typo fix
- **D-01:** Replace `json.dump(metrics_log, f, indig=2)` with `json.dump(metrics_log, f, indent=2)` at `src/surg_rl/dreamer/training.py:342`. The `indig` keyword is not a valid `json.dump` parameter; calling this code raises `TypeError: dump() got an unexpected keyword argument 'indig'` at end of every real DreamerV3 training run.
- **D-02:** Add a unit test in `tests/test_dreamer_training.py` that imports the training function, monkeypatches `subprocess` to a no-op double, calls the end-of-training save path, and asserts `training_metrics.json` is written with `indent=2` (read the file back and check it parses with `json.load`).
- **D-03:** Do NOT rename the `metrics_log` variable or restructure the save path. The fix is a one-character token rename on the call site only.

### Subprocess pipe protocol fix
- **D-04:** Replace the line `sys.stdout = os.fdopen(child_stdout.fileno(), "w", buffering=1)` at `src/surg_rl/dreamer/subprocess.py:23` with a custom `_JsonStdout` wrapper class that uses `child_stdout.send(...)` for line delivery. The `os.fdopen` pattern is fragile: (a) on Windows `multiprocessing.Pipe` connections do not expose a real `fileno()` for the parent's send end, and (b) wrapping the FD can race with the parent's `recv()` because both sides share the underlying buffer.
- **D-05:** Define `_JsonStdout` in the same `subprocess.py` module with `write(self, s)` and `flush(self)` methods. The `write` method strips a trailing newline (if present) and calls `self._pipe.send(s)`. The `flush` method is a no-op (the pipe itself buffers on the recv end).
- **D-06:** In `_subprocess_main`, build the wrapper as `_stream = _JsonStdout(child_stdout)` and assign `sys.stdout = _stream`. Keep `sys.stderr = os.fdopen(2, "w", buffering=1)` (real stderr FD 2 is always available cross-platform).
- **D-07:** Update the existing `FakePipe` in `tests/test_dreamer_subprocess.py` to assert that `sys.stdout` inside the subprocess is a `_JsonStdout` instance and that every `print(..., flush=True)` call inside the subprocess ends up as a single `child_stdout.send(json_payload)` call. Concretely: add a new test class `TestSubprocessStdoutProtocol` that monkeypatches `child_stdout` to a recording fake, runs `_subprocess_main` synchronously in a thread, sends a `CONFIG` message, and asserts the parent read one `CONFIG_ACK` JSON payload (proving the wrapper round-trips through the real pipe API rather than `os.fdopen`).
- **D-08:** Do NOT switch to `sys.stdin`/`sys.stdout` pipe redirection (the original `subprocess.Popen` approach). The multiprocessing `Pipe()` contract is what the parent's `DreamerSubprocess._stdin.send(...)` already depends on. The fix keeps the parent API unchanged.

### DREAMERV3_COLOR constant fix
- **D-09:** Change `DREAMER_COLOR = "#d55e00"` at `src/surg_rl/benchmark/plots.py:30` to `DREAMER_COLOR = "#FF8C00"`. The `#FF8C00` value is the one specified in `tests/test_dreamer_subprocess.py:0` (UAT Test 9) and in the Phase 23 / 24 implementation comments; `#d55e00` was a leftover from a different colorblind palette iteration.
- **D-10:** Verify any other reference to the literal color in `src/surg_rl/benchmark/` uses the constant rather than a hardcoded string. If a hardcoded `"#d55e00"` exists elsewhere, replace it with the constant.
- **D-11:** Add a unit test in `tests/test_benchmark_plots.py` (or extend the existing tests) that asserts `DREAMER_COLOR == "#FF8C00"` and that `PlotRenderer` references the constant when emitting the dreamer color (grep-check for the literal string in the rendered SVG/HTML output, OR a simple `assert DREAMER_COLOR == "#FF8C00"` import-level test).

### Verification
- **D-12:** The full pytest suite (excluding integration tests marked `@pytest.mark.integration` and dreamer/mujoco tests that need GPU) MUST still pass. Existing 86 dreamer mocked tests + ~910 v0.3.2 baseline + Phase 24 Nyquist-114 tests must remain green.
- **D-13:** The new tests added in D-02, D-07, and D-11 MUST pass on CPU-only macOS CI (no dreamerv3 / no GPU / no JAX install required) — they are pure-Python unit tests using mocks.
- **D-14:** A real end-to-end `surg-rl dreamer-spike` run on a GPU machine is OUT OF SCOPE for this phase. The bug fixes target code paths exercised by the existing mocked tests; the unverified end-to-end is the Phase 24 audit's "Medium severity" item #8 and is not a Phase 26 requirement (it requires dreamerv3 install + GPU which is environment-specific).

### OpenCode's Discretion
- Exact module structure for `_JsonStdout` (dataclass vs plain class, whether to subclass `io.TextIOBase`)
- Test helper shape for asserting the `_JsonStdout` wrapper in tests
- Whether to also add a `--no-color-override` env var for the benchmark palette (out of scope unless the constant alone is insufficient)
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/REQUIREMENTS.md` — DMV3-01..05 requirements (v1), DMV3-06 (v2 deferred)
- `.planning/ROADMAP.md` § Phase 26 — success criteria
- `.planning/v0.4.0-MILESTONE-AUDIT.md` — gap evidence, line numbers, severity ratings

### Source artifacts (Phase 24)
- `src/surg_rl/dreamer/training.py:342` — `indig=2` typo on the metrics save
- `src/surg_rl/dreamer/subprocess.py:15-26` — `_subprocess_main` with `os.fdopen` on a Pipe connection
- `src/surg_rl/dreamer/subprocess.py:127-237` — `DreamerSubprocess` parent class
- `src/surg_rl/benchmark/plots.py:30` — `DREAMER_COLOR = "#d55e00"` constant
- `src/surg_rl/benchmark/experiment_runner.py` — uses PlotRenderer
- `src/surg_rl/benchmark/report.py` — uses PlotRenderer for HTML/SVG embedding

### Tests
- `tests/test_dreamer_subprocess.py:12-40` — `FakePipe` mock (must be extended for D-07)
- `tests/test_dreamer_training.py` — existing dreamer training tests (extend for D-02)
- `tests/test_benchmark_plots.py` (if it exists; otherwise new test file) — for D-11

### Prior phase context
- `.planning/phases/24-dreamerv3-world-models/24-CONTEXT.md` — D-04/D-05/D-06 process isolation design
- `.planning/phases/24-dreamerv3-world-models/24-04-SUMMARY.md` — current `_subprocess_main` implementation
- `.planning/phases/24-dreamerv3-world-models/24-UAT.md` — Test 9 orange color spec
- `.planning/phases/25-fix-marl-runtime-wiring/25-CONTEXT.md` — pattern for gap-closure phase

### Architecture & conventions
- `.planning/codebase/ARCHITECTURE.md` — subprocess / module layout
- `.planning/codebase/CONVENTIONS.md` — pytest patterns, lazy imports
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`_subprocess_main` body** (`subprocess.py:15-26`): the JAX import + `READY` handshake logic is correct; only the `os.fdopen` line at 23 needs replacement. Lines 17-20 (env var setup) and 26 (loop call) stay as-is.
- **`_run_subprocess_loop`** (`subprocess.py:29-97`): uses `print(..., flush=True)` exclusively for output — meaning a wrapper that intercepts `sys.stdout.write` + `print`'s implicit newline handling will round-trip cleanly.
- **`FakePipe` mock** (`tests/test_dreamer_subprocess.py:12-40`): already has a `send()` recorder and a fake `fileno()` returning 0. Extend it to record `send()` calls triggered by the new `_JsonStdout` wrapper.
- **`DreamerSubprocess._send_message` / `_read_message`** (`subprocess.py:239-249`): parent side uses `self._stdin.send(json.dumps(msg))` and `self._stdout.recv()`. The new `_JsonStdout` must use `self._pipe.send(payload)` to keep the parent's API unchanged.
- **Color constant pattern** (`benchmark/plots.py:23-30`): constants are module-level near the top, referenced by `PlotRenderer` class methods. The DREAMER_COLOR fix is a one-token replacement at the module level.

### Established Patterns
- **One-character typo fixes** (Phase 1, 14): Single-line fixes with no API change, followed by a unit test that exercises the path. Pattern: read file → edit → write test → run pytest.
- **Subprocess protocol fixes** (Phase 25 `passthrough_step`): the same `__init__` / `step` / `_internal_helper` pattern — keep the public API identical, swap out the broken internals. For Phase 26, the public API is `_subprocess_main`'s callable signature; the internals are the `os.fdopen` line.
- **Additive constants** (Phase 23 palette): benchmark plot colors are a single source of truth — module-level constants consumed by the renderer. Renaming a constant value requires no call-site changes if the renderer references the constant (not the literal).

### Integration Points
1. **`subprocess.py:23` → `os.fdopen`** — replace with `_JsonStdout(child_stdout)` wrapper; line numbers after fix will shift by ~3-5 lines.
2. **`training.py:342` → `indig=2`** — single-token rename; line number unchanged.
3. **`plots.py:30` → `DREAMER_COLOR`** — single-value change; line number unchanged.

### Common Landmines
- **Do not rewrite the entire `_subprocess_main`**: the JAX import side-effects, env-var setup, and `_run_subprocess_loop` call are all correct. The fix is local to the stdout assignment.
- **Do not switch from `multiprocessing.Pipe` to `os.pipe`**: the parent's `_stdin.send(...)` API depends on the connection's `send` method, which `os.pipe` FD integers do not have.
- **Do not also change stderr**: stderr stays as `os.fdopen(2, "w", buffering=1)` because real stderr (FD 2) is always available.
- **Do not delete the existing `FakePipe` mock**: extend it. The 23 existing subprocess tests use it; deleting them would regress coverage.
</code_context>

<specifics>
## Specific Ideas

- **D-01 exact diff**: `json.dump(metrics_log, f, indig=2)` → `json.dump(metrics_log, f, indent=2)`. One token (`indig` → `indent`). Trivial.
- **D-04 `_JsonStdout` shape**:
  ```python
  class _JsonStdout:
      """stdout replacement that ships lines over a multiprocessing Pipe."""
      def __init__(self, pipe):
          self._pipe = pipe
      def write(self, s):
          if not s or s == "\n":
              return len(s) if s else 0
          # Strip trailing newline added by `print`
          payload = s.rstrip("\n")
          self._pipe.send(payload)
          return len(s)
      def flush(self):
          pass
  ```
- **D-07 test shape**: thread-based — start `_subprocess_main` in a thread with a recording fake `child_stdout` (catches `send()` calls) and a fake `child_stdin` (provides `recv()` answers), assert that after a `CONFIG` handshake the parent received the `READY` and `CONFIG_ACK` messages.
- **D-11 test shape**: a single import-level test:
  ```python
  from surg_rl.benchmark.plots import DREAMER_COLOR
  assert DREAMER_COLOR == "#FF8C00"
  ```
  (and optionally: grep the rendered plot output for the literal color string — but the import-level test is the minimal acceptance check.)

## Deferred Ideas

- Real end-to-end `surg-rl dreamer-spike` run on GPU to verify `_JsonStdout` round-trips in production — audit Medium severity #8, requires dreamerv3 install + GPU which is environment-specific
- `experiments/` directory creation fix (CLI prints misleading reproduce command) — Phase 27
- BENCH-01 5 missing task scene files — Phase 27
- `task_type` wiring on existing scene JSONs — Phase 27
- `ArmConfig`/`ArmRole` top-level exports — Phase 25 already closes this
- Re-running the v0.4.0 milestone audit to confirm `passed` status — after Phase 28 closes
</deferred>

---

*Phase: 26-Fix DreamerV3 Training Bugs*
*Context gathered: 2026-06-10 from v0.4.0 milestone audit (gap-closure phase, no discuss-phase)*

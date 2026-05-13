---
phase: 19-schema-foundation
plan: 02
subsystem: utils
tags: [lazy-import, optional-dependencies, pydantic, trimesh, pettingzoo, dreamerv3, matplotlib]

# Dependency graph
requires: []
provides:
  - LazyImport helper class in surg_rl.utils.lazy_imports — defers ImportError to first attribute access
  - TRIMESH lazy import guard in surg_rl.assets — trimesh OBJ loading without crashing import surg_rl
  - MATPLOTLIB lazy import guard in surg_rl.benchmark — experiment runner plots without crashing import surg_rl
  - PETTINGZOO lazy import guard in surg_rl.marl — multi-agent RL without crashing import surg_rl
  - DREAMER lazy import guard in surg_rl.dreamer — DreamerV3 JAX without crashing import surg_rl
affects: [20-assets, 21-task-curriculum, 22-benchmarking, 23-marl, 24-dreamerv3]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "LazyImport pattern: defers module import until first attribute access with pip install hint"
    - "Per-package __init__.py with single LazyImport instance for primary optional dependency"

key-files:
  created:
    - src/surg_rl/utils/lazy_imports.py
    - src/surg_rl/assets/__init__.py
    - src/surg_rl/benchmark/__init__.py
    - src/surg_rl/marl/__init__.py
    - src/surg_rl/dreamer/__init__.py
    - tests/test_lazy_imports.py
  modified: []

key-decisions:
  - "LazyImport lives in surg_rl.utils.lazy_imports.py (separate module, not utils/__init__.py)"
  - "LazyImport is dependency-free — pure importlib + typing, no logging or warnings"
  - "Each optional package exports a single LazyImport instance via __all__"

patterns-established:
  - "LazyImport(module_name, package_name) — constructor with importlib module name and extras group name"
  - "__getattr__ defers ImportError with pip install surg-rl[{package_name}] hint on missing deps"
  - ".available property safely probes importability without raising"

requirements-completed: []

# Metrics
duration: 3m 26s
completed: 2026-05-13
---

# Phase 19 Plan 02: LazyImport — Optional Dependency Guard System

**LazyImport helper class deployed across 4 optional dependency packages — `import surg_rl` succeeds even without trimesh, pettingzoo, jax, or dreamerv3 installed**

## Performance

- **Duration:** 3 min 26 sec
- **Started:** 2026-05-13T22:09:55Z
- **Completed:** 2026-05-13T22:13:21Z
- **Tasks:** 2
- **Files modified:** 6 (5 source, 1 test)

## Accomplishments

- `LazyImport` class in `surg_rl.utils.lazy_imports.py` — defers `ImportError` to first attribute access, provides `.available` bool property, and raises informative `pip install surg-rl[{group}]` hints on missing dependencies
- 4 lazy import guards created — `TRIMESH` (assets), `MATPLOTLIB` (benchmark), `PETTINGZOO` (marl), `DREAMER` (dreamer) — each in its own `__init__.py`
- `import surg_rl` now succeeds unconditionally — zero `ImportError` from any optional dependency group
- 7 new unit tests for LazyImport covering construction, `.available`, `__getattr__` error/success/caching, and `__repr__`
- Full regression: 917 passed, 11 skipped, zero failures — no existing tests modified

## Task Commits

Each task was committed atomically:

1. **Task 1a: RED — failing test for LazyImport** — `b612e51` (test)
2. **Task 1b: GREEN — LazyImport implementation** — `b230c8b` (feat)
3. **Task 2: lazy import guards in assets/, benchmark/, marl/, dreamer/** — `4f51492` (feat)

_Note: Task 1 was TDD — RED test commit followed by GREEN implementation commit._

## Files Created/Modified

- `src/surg_rl/utils/lazy_imports.py` — `LazyImport` class: defers import, `.available` property, `pip install` hint, attribute caching
- `src/surg_rl/assets/__init__.py` — `TRIMESH = LazyImport("trimesh", "assets")` guard
- `src/surg_rl/benchmark/__init__.py` — `MATPLOTLIB = LazyImport("matplotlib", "benchmark")` guard
- `src/surg_rl/marl/__init__.py` — `PETTINGZOO = LazyImport("pettingzoo", "marl")` guard
- `src/surg_rl/dreamer/__init__.py` — `DREAMER = LazyImport("dreamerv3", "dreamer")` guard
- `tests/test_lazy_imports.py` — 7 tests covering construction, available, getattr (error/success/cache), repr

## Decisions Made

- None — followed plan as specified. All decisions (D-05: LazyImport pattern, D-06: per-module __init__.py structure) were locked in CONTEXT.md before planning.

## Deviations from Plan

None — plan executed exactly as written. All 6 files match the specified content and all success criteria were met.

## Issues Encountered

None — implementation was straightforward. Tests ran cleanly on first pass.

## User Setup Required

None — no external service configuration required. All optional dependency packages degrade gracefully at import time.

## Next Phase Readiness

- `LazyImport` class is reusable across all v0.4.0 optional dependency packages (Phases 20–24)
- Each downstream phase can reference its guard: `from surg_rl.assets import TRIMESH`, `from surg_rl.marl import PETTINGZOO`, etc.
- Pattern is self-documenting — each `__init__.py` has a clear docstring with install instructions

---

*Phase: 19-schema-foundation*
*Completed: 2026-05-13*

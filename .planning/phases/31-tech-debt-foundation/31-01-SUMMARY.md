---
phase: 31-tech-debt-foundation
plan: 01
subsystem: lint, build
tags: [ruff, docker, dreamer, multi-arch, tech-debt]

# Dependency graph
requires: []
provides:
  - "Lint-clean dreamer module (ruff exits 0)"
  - "Multi-arch Dockerfile.ros2 using $TARGETARCH for buildx"
affects: [32-demo-suite-polish, 33-pyside6-scene-editor, 35-advanced-tech-debt]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "contextlib.suppress(Exception) replaces try/except/pass for fire-and-forget cleanup"
    - "raise X from exc preserves exception chain (PEP 3134) for subprocess transports"
    - "Docker ARG TARGETARCH with buildx enables single Dockerfile for amd64 + arm64"

key-files:
  created: []
  modified:
    - src/surg_rl/dreamer/__init__.py
    - src/surg_rl/dreamer/subprocess.py
    - src/surg_rl/dreamer/training.py
    - src/surg_rl/dreamer/wrapper.py
    - Dockerfile.ros2

key-decisions:
  - "Removed both orphaned 'wrapper = GymToEmbodiedWrapper(...)' assignments in training.py (lines 245, 388) instead of calling for side effects — GymToEmbodiedWrapper has no side-effecting constructor and the local was never read downstream"
  - "Used 'raise ... from exc' (not 'from None') in subprocess.py:202 to preserve original EOFError context per Phase 26 _JsonStdout debuggability contract"
  - "ARG TARGETARCH=amd64 default keeps backwards compat with legacy non-buildx docker build (no user is broken)"

patterns-established:
  - "Pattern: defer PySide6/Qt imports via LazyImport until console-script invocation"
  - "Pattern: ARG default values in Dockerfiles provide backwards compat with non-BuildKit builders"

requirements-completed: [DEBT-01, DEBT-02]

# Metrics
duration: 8min
completed: 2026-06-18
---

# Phase 31 Plan 01 Summary

**Lint-clean dreamer module (10/10 ruff issues fixed) and multi-arch Dockerfile.ros2 via `$TARGETARCH`**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-06-18T01:00:00Z
- **Completed:** 2026-06-18T01:08:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- DEBT-01 closed: `ruff check src/surg_rl/dreamer/` exits 0 with "All checks passed!"
- DEBT-02 closed: `Dockerfile.ros2` portable across amd64 + arm64 via `$TARGETARCH`
- Dreamer E2E tests still skip correctly on macOS (3 SKIPPED with documented reason)
- Two atomic commits, one per task

## task Commits

1. **task 1: clean 10 ruff issues in src/surg_rl/dreamer/** - `c702e5a` (chore)
2. **task 2: update Dockerfile.ros2 to use $TARGETARCH** - `ec15c4a` (chore)

## Files Created/Modified

- `src/surg_rl/dreamer/__init__.py` - moved 4 `from .X import` lines above the LazyImport to resolve 4× E402 (imports now at the top of the module)
- `src/surg_rl/dreamer/subprocess.py` - removed F841 unused `env` (line 67), converted try/except/pass to `contextlib.suppress` (line 121), added `from exc` to raise (line 202)
- `src/surg_rl/dreamer/training.py` - removed 2 orphaned `wrapper = GymToEmbodiedWrapper(...)` assignments (lines 245, 388); the now-unused import was auto-dropped by `ruff --fix`
- `src/surg_rl/dreamer/wrapper.py` - converted try/except/pass to `contextlib.suppress` (line 162)
- `Dockerfile.ros2` - added `ARG TARGETARCH=amd64`, replaced hardcoded `--platform=linux/amd64` with `--platform=linux/${TARGETARCH}`, updated build example comment to multi-arch form, added `# requires Docker BuildKit` documentation

## Decisions Made

- **Removed both `wrapper` assignments in training.py entirely** rather than calling `GymToEmbodiedWrapper(...)` for side effects. The class constructor allocates a wrapper object with no observable side effects, and the local was never read after assignment. This is the cleanest fix that satisfies F841 without introducing unused allocations.
- **Used `from exc` (not `from None`) for B904 fix** at `subprocess.py:202` — the plan specified this explicitly per T-31-02 threat model (preserves debugging context for the Phase 26 `_JsonStdout` pipe round-trip).
- **Used `ARG TARGETARCH=amd64` default** rather than omitting `--platform=` — this lets legacy `docker build` (without buildx) still work on amd64 while buildx auto-overrides the default for arm64.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 31 plans 02, 03, 04 can now build on a lint-clean dreamer module
- Phase 35 K8s sidecar work can build Dockerfile.ros2 on Apple Silicon Macs (arm64) without changes
- 1,134-test regression baseline preserved (dreamer subprocess E2E tests still skip on macOS as documented)

---
*Phase: 31-tech-debt-foundation*
*Plan: 01*
*Completed: 2026-06-18*
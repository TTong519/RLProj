# 10-03 Summary: macOS CI Runner

**Plan:** 10-03-PLAN.md
**Status:** Complete
**Depends on:** 10-01
**Commits:** 1

## Accomplishments

- Rewrote `.github/workflows/ci.yml` with OS matrix: `ubuntu-latest` (3.10/3.11/3.12) + `macos-latest` (3.11)
- `fail-fast: false` so macOS failures don't block ubuntu results
- Lint/format/mypy restricted to Linux only (avoids duplication, avoids macOS-specific lint bugs)
- mjpython path resolved dynamically in CI via Python import: `python -c "import mujoco; ..."`
- macOS pytest runs under mjpython, ignores all 4 ROS2 test files
- Guarded `test_macos_raises_without_mjpython` with `CI=true` skip (would fail under mjpython)

## Files Modified

| File | Change |
|------|--------|
| `.github/workflows/ci.yml` | Rewritten: 48→81 lines, OS matrix, mjpython step |
| `tests/unit/test_rendering.py` | +1 import, +1 CI guard on RuntimeError test |

## Self-Check: PASSED

- `tests/unit/test_rendering.py` — 21/21 tests pass
- CI file syntax valid (YAML)

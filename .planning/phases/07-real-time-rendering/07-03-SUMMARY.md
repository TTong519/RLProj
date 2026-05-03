# Wave 3 Summary — 07-03-PLAN.md

## Tasks Completed

### Task 1: CLI Flags
- Added `--render-human` and `--render-fps` Typer options to `surg-rl train`
- `--render-human` sets `TrainingConfig.render_mode = "human"`
- `--render-fps` sets `TrainingConfig.render_fps` (default 30.0)
- Console prints "Live viewer: enabled (N FPS)" when active

### Task 2: Comprehensive Test Suite
- **New file:** `tests/unit/test_rendering.py` (18 tests, 366 lines)
  - `TestRenderThread`: daemon, FPS throttle, stop lifecycle
  - `TestMuJoCoViewer`: start/stop, headless fallback, macOS guard
  - `TestPyBulletViewer`: GUI True, DIRECT False, no-op stop
  - `TestSurgicalEnvViewer`: eager start, render branching, close cleanup
  - `TestStepOverhead`: steps complete regardless of viewer state

## Artifacts
- Modified: `src/surg_rl/cli.py`
- New: `tests/unit/test_rendering.py`

## Key Decisions
- All viewer tests use MagicMock (no real OS windows in CI)
- macOS RuntimeError tested via `platform.system()` monkeypatch
- Tests run on headless machines without display

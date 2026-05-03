# Wave 2 Summary — 07-02-PLAN.md

## Tasks Completed

### Task 1: SurgicalEnvConfig.render_fps + Eager Viewer Start
- Added `render_fps: float = 30.0` to `SurgicalEnvConfig`
- `SurgicalEnv.__init__` starts viewer eagerly after `load_scene()` when `render_mode == "human"`
- Headless fallback: catches `RuntimeError` (macOS/no display), sets `render_mode = None`, logs warning
- `render()` branching: `"rgb_array"` delegates to simulator, `"human"` returns `None` (async)

### Task 2: SIGINT + atexit Handlers
- Added `_setup_signal_handlers()` method to `SurgicalEnv`
- SIGINT handler: calls `close()` then re-raises `KeyboardInterrupt`
- `atexit.register(self.close)` for cleanup on unclean exit
- `_handlers_registered` guard prevents double-registration

### Task 3: TrainingConfig.render_mode + render_fps
- Added `render_mode: str | None = None` and `render_fps: float = 30.0` to `TrainingConfig`
- TrainingManager._create_environment() passes them to `SurgicalEnvConfig`

## Artifacts
- Modified: `src/surg_rl/rl/environment.py`
- Modified: `src/surg_rl/rl/training.py`

## Key Decisions
- Headless fallback is a warning, not an error (training continues)
- Signal handler falls back silently on non-main threads (SubprocVecEnv)
- `render_fps` is a config field, not metadata (type-safe)

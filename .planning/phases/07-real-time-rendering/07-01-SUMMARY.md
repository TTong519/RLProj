# Wave 1 Summary — 07-01-PLAN.md

## Tasks Completed

### Task 1: BaseSimulator viewer contract + RenderThread
- **BaseSimulator** extended with `start_viewer(target_fps) -> bool` and `stop_viewer() -> None` abstract methods
- `__init__` now accepts `render_mode` kwarg (default `"rgb_array"`)
- **New file:** `src/surg_rl/render_thread.py` — daemon thread calling `viewer.sync(state_only=True)` at target FPS via `time.sleep()`

### Task 2: Fix `_create_simulator` to pass render_mode
- `SurgicalEnv._create_simulator()` now passes `render_mode` to both backends:
  - MuJoCo receives the raw render_mode string
  - PyBullet receives `"GUI"` if `render_mode == "human"`, else `"DIRECT"`

### Task 3: Implement MuJoCoSimulator.start_viewer
- `start_viewer()` launches MuJoCo `launch_passive` viewer wrapped in `RenderThread`
- **macOS guard:** raises `RuntimeError` with clear instructions if not using `mjpython`
- `stop_viewer()` stops thread and releases viewer
- `close()` calls `stop_viewer()` before cleanup

### Task 4: Wire PyBullet render_mode
- PyBulletSimulator already accepts `render_mode` in `__init__`; verified it works
- Added `start_viewer()` (returns `True` in GUI, `False` in DIRECT) and `stop_viewer()` (no-op)

## Artifacts
- `src/surg_rl/render_thread.py` (65 lines)
- Modified: `src/surg_rl/simulators/base_simulator.py`
- Modified: `src/surg_rl/simulators/mujoco_simulator.py`
- Modified: `src/surg_rl/simulators/pybullet_simulator.py`
- Modified: `src/surg_rl/rl/environment.py`

## Key Decisions
- RenderThread as daemon thread (auto-cleanup on process exit)
- FPS throttle via `time.sleep()` (simple, portable, no extra deps)
- macOS RuntimeError instead of silent failure (developer UX)

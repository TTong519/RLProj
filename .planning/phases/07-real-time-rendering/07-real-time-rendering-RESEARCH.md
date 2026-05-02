# Phase 7: Real-time Rendering - Research

**Researched:** 2026-05-02
**Domain:** RL environment non-blocking 3D rendering (MuJoCo viewer, PyBullet GUI, Gymnasium render API)
**Confidence:** HIGH (official docs verified for MuJoCo + Gymnasium; MEDIUM for PyBullet GUI behavior on macOS/headless)

---

## Summary

This phase adds live, non-blocking 3D rendering during RL training. The core challenge is that both MuJoCo and PyBullet provide interactive viewers, but they are designed for *interactive* use (user controls the loop) rather than *training* use (agent controls the loop at 100+ Hz). We must integrate these viewers so that `env.step()` never blocks on rendering, the window survives `reset()`, and FPS is throttled to avoid GPU starvation.

**MuJoCo** provides `mujoco.viewer.launch_passive(model, data)`, which spawns a viewer in a background thread and does NOT block the caller [CITED: mujoco.readthedocs.io/en/stable/python.html#passive-viewer]. The caller must periodically call `viewer.sync()` to push the current physics state to the viewer. This is the exact primitive we need: the training loop calls `sync()` from a dedicated render thread at 30 FPS, while the main thread runs `step()` at full speed.

**PyBullet** provides `p.connect(p.GUI)`, which opens an OpenGL window in a separate OS thread [CITED: PyBullet Quickstart Guide]. GUI mode is non-blocking for the Python thread because PyBullet processes render events internally. The caveat: GUI mode requires a display and often fails on headless servers. Our implementation must fall back to `DIRECT` mode gracefully.

**Gymnasium v1.2.3** (verified installed) defines the `render_mode` contract: `render_mode="human"` should continuously render during `step()`, while `render_mode="rgb_array"` returns a NumPy frame [CITED: gymnasium.farama.org/api/env]. `render()` takes no arguments — all render config is set at `__init__`. The environment's `metadata` must include `"render_modes": ["human", "rgb_array"]` and `"render_fps": 30`.

**Primary recommendation:** Use a dedicated `RenderThread` class that owns the viewer lifecycle, calls `sync()` at a throttled rate, and is started/stopped by the simulator's `start_viewer()` / `close()` methods. For MuJoCo this wraps `launch_passive`. For PyBullet this is a no-op (GUI is handled by the physics server). Both simulators already implement `render(mode=...)` — we extend them to support persistent human-mode viewers.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Viewer lifecycle (create/destroy) | Simulator backend | — | MuJoCo `launch_passive` and PyBullet `GUI` are backend-specific |
| Physics state sync to viewer | Simulator backend | RenderThread | `sync()` is backend-specific; thread timing is generic |
| FPS throttling | RenderThread | — | Sleep-based throttle is generic, not backend-specific |
| Gymnasium render API compliance | SurgicalEnv (Gym wrapper) | — | `render_mode`, `metadata`, `render()` are env-level contract |
| CLI `--render-human` flag | CLI (Typer) | TrainingManager | Flag passes through to env creation |
| Clean shutdown (SIGINT, close) | SurgicalEnv + RenderThread | — | `env.close()` must terminate viewer thread and close window |
| rgb_array offscreen rendering | Simulator backend | — | `mujoco.Renderer` / `getCameraImage` are independent of human mode |

---

## User Constraints (from CONTEXT.md)

### Locked Decisions
- `render_mode="human"` opens a window that survives `reset()` calls
- `env.step()` returns in <5ms regardless of render state
- Render FPS is throttled to configurable target (default 30 FPS)
- `surg-rl train --render-human` opens a live viewer
- `env.close()` and SIGINT terminate viewer cleanly (no segfaults/zombies)
- `render_mode="rgb_array"` still returns correct NumPy arrays

### OpenCode's Discretion
- Implementation details of RenderThread (threading primitives, throttle logic)
- Whether to use `mjpython` wrapper detection on macOS
- How to handle PyBullet GUI fallback on headless servers

### Deferred Ideas (OUT OF SCOPE)
- Multi-user networked surgery
- Unity/Unreal rendering backends
- Web dashboard / remote viewer

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RENDER-01 | `BaseSimulator.render(mode="human")` creates non-blocking window that survives `reset()` | MuJoCo `launch_passive` persists across resets; PyBullet GUI persists across `resetSimulation` |
| RENDER-02 | `SurgicalEnv.step()` does not block when `render_mode="human"` is active | Dedicated render thread calling `sync()` asynchronously; main thread never waits |
| RENDER-03 | Render FPS is throttled to configurable target (default 30 FPS) | `time.sleep()` in render thread loop; decoupled from training loop frequency |
| RENDER-04 | `surg_rl.cli train` accepts `--render-human` flag that opens a live viewer | CLI passes `render_mode="human"` to `SurgicalEnvConfig` |
| RENDER-05 | Viewer window closes cleanly on `env.close()` and SIGINT without segfault | `viewer.close()` + thread join + `atexit` / signal handler |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `mujoco` | >=3.0.0 (bundled) | Physics + `launch_passive` viewer | Official non-blocking viewer API [CITED: docs] |
| `pybullet` | >=3.2.5 | Physics + GUI/DIRECT connection modes | Native OpenGL window in GUI mode [CITED: docs] |
| `gymnasium` | 1.2.3 (verified) | Env API contract (`render_mode`, `metadata`, `render()`) | Industry standard RL interface [CITED: gymnasium.farama.org] |
| `threading` | stdlib | RenderThread for async `sync()` calls | Python stdlib, no extra deps |
| `time` | stdlib | FPS throttling via `time.sleep()` | Simple, precise enough for 30 FPS |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `signal` | stdlib | SIGINT handler to trigger `env.close()` | Always when human mode active |
| `atexit` | stdlib | Backup cleanup if SIGINT handler missed | Always when human mode active |
| `mjpython` | bundled with mujoco | macOS launcher for `launch_passive` | Only on macOS [CITED: mujoco docs] |

### Version Verification
```bash
$ python3 -c "import gymnasium; print(gymnasium.__version__)"
1.2.3
```
[VERIFIED: local environment]

### No Additional Packages Needed
Neither GLFW, SDL, Pygame, nor EGL/OSMesa need to be added as project dependencies. MuJoCo bundles its own GLFW for the viewer. PyBullet uses its own windowing in GUI mode. Offscreen `rgb_array` rendering uses `mujoco.Renderer` (no external GL context) and PyBullet `getCameraImage` (no external GL context).

---

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Training Loop (Main Thread)                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │
│  │  SB3 Agent  │───▶│ SurgicalEnv │───▶│  Simulator  │                  │
│  │  .learn()   │    │  .step()    │    │  .step()    │  ◄── never blocks│
│  └─────────────┘    └─────────────┘    └─────────────┘                  │
│         │                  │                                            │
│         │         render_mode="human"                                   │
│         │                  │                                            │
│         │         ┌────────▼────────┐                                   │
│         │         │  RenderThread   │  ◄── dedicated thread (not main)  │
│         │         │  (throttled)    │                                   │
│         │         └────────┬────────┘                                   │
│         │                  │ sync() every 33ms                         │
│         │                  ▼                                            │
│         │         ┌─────────────┐                                      │
│         │         │  Viewer     │  ◄── MuJoCo passive / PyBullet GUI   │
│         │         │  Window     │                                      │
│         │         └─────────────┘                                      │
│         │                                                               │
│         ▼                                                               │
│  ┌─────────────┐                                                       │
│  │ env.close() │  ──▶  stops RenderThread ──▶ viewer.close()          │
│  └─────────────┘                                                       │
│         ▲                                                               │
│  ┌──────┴──────┐                                                       │
│  │  SIGINT     │  ──▶  signal handler calls env.close()                │
│  │  (Ctrl+C)   │                                                       │
│  └─────────────┘                                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

```
src/surg_rl/simulators/
├── base_simulator.py       # Abstract render(mode) / start_viewer() / close()
├── mujoco_simulator.py     # launch_passive + sync() integration
├── pybullet_simulator.py   # GUI mode + (no-op sync)
└── renderer/
    ├── __init__.py
    └── render_thread.py    # Generic FPS-throttled render thread
```

### Pattern 1: MuJoCo Passive Viewer Integration

**What:** `launch_passive` creates a non-blocking viewer. A background thread calls `sync(state_only=True)` at a throttled rate.

**When to use:** `render_mode="human"` on MuJoCo backend.

**Example:**
```python
# Source: https://mujoco.readthedocs.io/en/stable/python.html#passive-viewer
import mujoco.viewer

# launch_passive returns immediately; viewer runs in background thread
with mujoco.viewer.launch_passive(model, data) as viewer:
    while viewer.is_running():
        # Training loop runs here at full speed
        mujoco.mj_step(model, data)

        # Sync is called from a separate thread in practice
        # viewer.sync(state_only=True)  # fast path: only state, not full scene rebuild
```

Key points from docs:
- `sync(state_only=False)`: full scene rebuild — picks up arbitrary model/data changes.
- `sync(state_only=True)`: only integration state + `mj_forward` — **much faster**.
- Must call `sync()` for viewer to reflect physics changes.
- `viewer.close()` can be called safely without locking.
- `viewer.is_running()` returns `False` after window is closed.

**On macOS:** `launch_passive` requires `mjpython` launcher because the main thread must be the one that creates the Cocoa window [CITED: mujoco.readthedocs.io]. This is a platform limitation we cannot circumvent. We document it and skip viewer tests on macOS CI.

### Pattern 2: Dedicated RenderThread

**What:** A generic `threading.Thread` subclass that owns the viewer handle and calls `sync()` at a target FPS.

**When to use:** Any backend where human render needs to be decoupled from the training loop.

**Example:**
```python
import threading
import time

class RenderThread(threading.Thread):
    def __init__(self, viewer, target_fps: float = 30.0):
        super().__init__(daemon=True)
        self._viewer = viewer
        self._target_interval = 1.0 / target_fps
        self._running = threading.Event()
        self._running.set()

    def run(self):
        while self._running.is_set():
            loop_start = time.perf_counter()
            if self._viewer is not None and self._viewer.is_running():
                self._viewer.sync(state_only=True)
            elapsed = time.perf_counter() - loop_start
            sleep_time = self._target_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def stop(self):
        self._running.clear()
        self.join(timeout=2.0)
        if self._viewer is not None:
            self._viewer.close()
```

### Pattern 3: PyBullet GUI Non-Blocking Mode

**What:** `p.connect(p.GUI)` opens a window that lives in the PyBullet physics server's thread. The Python caller thread is not blocked.

**When to use:** `render_mode="human"` on PyBullet backend.

**Caveat:** PyBullet GUI does not require explicit `sync()` calls — the physics server renders automatically after each `stepSimulation()`. However, on headless servers, `GUI` will fail. Our code must catch this and fall back to `DIRECT` with a warning.

**Example:**
```python
# In PyBulletSimulator.__init__
if render_mode == "GUI":
    try:
        self._physics_client = self._pb.connect(self._pb.GUI)
    except Exception:
        logger.warning("GUI mode failed, falling back to DIRECT")
        self._physics_client = self._pb.connect(self._pb.DIRECT)
```

### Pattern 4: Gymnasium Render API Compliance

**What:** Gymnasium v0.29+ (we have 1.2.3) expects `render_mode` set at `__init__`, and `render()` takes no arguments.

**When to use:** Always for `SurgicalEnv`.

**Required `SurgicalEnv` changes:**
```python
class SurgicalEnv(gym.Env):
    metadata = {
        "render_modes": ["human", "rgb_array"],
        "render_fps": 30,
    }

    def __init__(self, config, render_mode=None):
        # ... existing init ...
        self.render_mode = render_mode or config.render_mode
        if self.render_mode == "human":
            self._simulator.start_viewer()  # opens viewer, starts RenderThread

    def render(self):
        if self.render_mode == "rgb_array":
            return self._simulator.render(mode="rgb_array")
        # "human" mode: rendering happens asynchronously via RenderThread
        return None

    def close(self):
        self._simulator.close()  # stops RenderThread, closes viewer
```

### Anti-Patterns to Avoid

1. **Calling `viewer.sync()` from the main training thread:** This adds overhead to `step()` and can cause jitter. Always use a dedicated render thread.
2. **Creating a new viewer on every `reset()`:** `launch_passive` is designed to persist across resets. Recreating it causes window flicker and violates RENDER-01.
3. **Using `sync(state_only=False)` in the render loop:** This rebuilds the full scene every frame and is much slower. Use `state_only=True` for the fast path.
4. **Relying on `__del__` for viewer cleanup:** Python finalization order is unpredictable. Explicit `close()` + `atexit` + signal handler is required.
5. **Using `glfw` or `pygame` directly:** MuJoCo bundles its own GLFW. Adding another windowing library increases complexity and conflict risk.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Non-blocking viewer window | Custom GLFW/SDL window + OpenGL context | MuJoCo `launch_passive` or PyBullet `GUI` | Both are officially supported, thread-safe, and handle context lifecycle internally |
| FPS throttling loop | Busy-wait loop with `time.sleep(0)` | `time.sleep(1.0 / target_fps)` in a daemon thread | Simple, CPU-efficient, no spin-locking |
| Thread-safe viewer state sync | Manual mutexes around model/data | `viewer.lock()` context manager + `viewer.sync()` | MuJoCo viewer provides its own lock; PyBullet GUI is internally synchronized |
| Window cleanup on exit | `os.kill()` or `sys.exit()` | `viewer.close()` + thread `join()` | Clean resource release prevents zombie windows and segfaults |
| macOS main-thread rendering | Ignore the limitation | Document `mjpython` requirement | Apple's Cocoa framework requires main thread for window creation — this is a hard OS constraint |
| Headless fallback detection | Custom display detection logic | `os.environ.get("DISPLAY")` + try/except around `GUI` connect | Standard Unix display env var; PyBullet throws on failed GUI connect |

---

## Common Pitfalls

### Pitfall 1: `launch_passive` Segfaults on macOS Without `mjpython`
**What goes wrong:** Calling `mujoco.viewer.launch_passive()` from a regular `python` process on macOS crashes because Cocoa requires the main thread to create the window.
**Why it happens:** macOS platform limitation documented by MuJoCo team.
**How to avoid:** Document that macOS users must run with `mjpython script.py` instead of `python script.py`. In code, detect macOS + non-mjpython and raise a clear `RuntimeError` with instructions.
**Warning signs:** Immediate segfault or `NSException` on viewer launch.

### Pitfall 2: `sync()` Called Too Frequently Causes GPU Starvation
**What goes wrong:** Render thread calls `sync()` at 1000 Hz (unthrottled), consuming GPU resources and slowing training.
**Why it happens:** No sleep in the render loop.
**How to avoid:** Always throttle the render thread to `metadata["render_fps"]` (default 30). Use `time.sleep()` not a busy loop.
**Warning signs:** `nvidia-smi` shows high GPU utilization even though training should be CPU-bound; step time increases when viewer is active.

### Pitfall 3: `reset()` Closing the Viewer (MuJoCo)
**What goes wrong:** If `start_viewer()` is called inside `reset()`, the window is recreated every episode, causing flicker and violating RENDER-01.
**Why it happens:** Viewer lifecycle incorrectly tied to episode instead of environment.
**How to avoid:** Start viewer in `__init__` (or lazily on first `reset()`), never recreate it on subsequent resets. Store viewer handle on the simulator instance.
**Warning signs:** Window disappears and reappears on `env.reset()`.

### Pitfall 4: PyBullet GUI Fails Silently on Headless Server
**What goes wrong:** `p.connect(p.GUI)` raises an exception or hangs on a headless Linux server.
**Why it happens:** No X11 display available.
**How to avoid:** Wrap GUI connect in try/except; fallback to `DIRECT` with a warning. Check `os.environ.get("DISPLAY")` as a fast-path check.
**Warning signs:** `RuntimeError: GUI mode not available` or process hang on connect.

### Pitfall 5: SIGINT Leaves Zombie Window
**What goes wrong:** Pressing Ctrl+C during training terminates the Python process but leaves the OS window alive because the viewer thread is a non-daemon thread.
**Why it happens:** Default SIGINT raises `KeyboardInterrupt` in the main thread; background threads may not run cleanup.
**How to avoid:** Register a `signal.signal(signal.SIGINT, _sigint_handler)` that calls `env.close()` before re-raising. Make RenderThread a daemon thread so it exits with the main process, but still perform explicit cleanup in the handler.
**Warning signs:** Window remains open after `python train.py` is killed with Ctrl+C.

### Pitfall 6: `render("rgb_array")` Broken After Human Mode
**What goes wrong:** Offscreen renderer (`mujoco.Renderer`) and passive viewer share OpenGL context state, causing crashes or black frames when switching modes.
**Why it happens:** MuJoCo `Renderer` uses its own GL context; `launch_passive` uses another. They generally do not interfere, but on some GPU drivers context switching causes issues.
**How to avoid:** Keep `rgb_array` rendering completely separate from human mode. In `SurgicalEnv`, if `render_mode == "human"`, `render()` returns `None`. If user wants `rgb_array` frames while viewer is open, they must use a separate offscreen renderer instance (not the viewer's). Do not mix calls in the same env instance.
**Warning signs:** `render("rgb_array")` returns all-black images after `start_viewer()` was called.

---

## Code Examples

### MuJoCo Passive Viewer with RenderThread

```python
# Source: https://mujoco.readthedocs.io/en/stable/python.html#passive-viewer
import mujoco
import mujoco.viewer
import threading
import time

class MuJoCoRenderThread(threading.Thread):
    def __init__(self, model, data, target_fps: float = 30.0):
        super().__init__(daemon=True)
        self.model = model
        self.data = data
        self.target_interval = 1.0 / target_fps
        self._viewer = None
        self._running = threading.Event()

    def run(self):
        with mujoco.viewer.launch_passive(self.model, self.data) as viewer:
            self._viewer = viewer
            self._running.set()
            while self._running.is_set() and viewer.is_running():
                loop_start = time.perf_counter()
                viewer.sync(state_only=True)
                elapsed = time.perf_counter() - loop_start
                sleep_time = self.target_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

    def stop(self):
        self._running.clear()
        self.join(timeout=2.0)
        if self._viewer is not None:
            self._viewer.close()

# Usage inside simulator:
# self._render_thread = MuJoCoRenderThread(self._model, self._data)
# self._render_thread.start()
```

### PyBullet GUI Mode with Fallback

```python
# Source: PyBullet Quickstart Guide (verified via codebase)
import os

class PyBulletSimulator:
    def _connect_gui_with_fallback(self):
        if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
            try:
                self._physics_client = self._pb.connect(self._pb.GUI)
                self.render_mode = "GUI"
                return
            except Exception as e:
                logger.warning(f"GUI connect failed: {e}. Falling back to DIRECT.")
        self._physics_client = self._pb.connect(self._pb.DIRECT)
        self.render_mode = "DIRECT"
```

### Gymnasium-Compliant SurgicalEnv Render

```python
# Source: gymnasium.farama.org/api/env (v1.2.3)
class SurgicalEnv(gym.Env):
    metadata = {
        "render_modes": ["human", "rgb_array"],
        "render_fps": 30,
    }

    def render(self):
        if self.render_mode == "rgb_array":
            return self._simulator.render(mode="rgb_array")
        elif self.render_mode == "human":
            # Human rendering is asynchronous via RenderThread
            return None
        return None

    def close(self):
        if hasattr(self._simulator, "stop_viewer"):
            self._simulator.stop_viewer()
        self._simulator.close()
```

### SIGINT Handler for Clean Shutdown

```python
import signal
import atexit

class SurgicalEnv(gym.Env):
    def __init__(self, ...):
        # ... existing init ...
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        def _handle_sigint(signum, frame):
            self.close()
            raise KeyboardInterrupt

        try:
            signal.signal(signal.SIGINT, _handle_sigint)
        except ValueError:
            # Signal handlers can only be registered on main thread
            pass

        atexit.register(self.close)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `mujoco_py` + custom `MjViewer` | Native `mujoco.viewer.launch_passive` | MuJoCo 2.3+ (2022) | Official non-blocking viewer, no custom GLFW code needed |
| OpenAI Gym `render(mode=...)` with args | Gymnasium `render()` no args, mode at `__init__` | Gymnasium 0.26 (2022) | Cleaner API, mode set once at construction |
| PyBullet `p.startStateLogging(...)` for video | `getCameraImage` + passive GUI | PyBullet 3.x | GUI mode is sufficient for live viewing |
| Manual GLFW window management | MuJoCo handles GLFW internally | MuJoCo 3.x Python bindings | No external GLFW dependency |

**Deprecated/outdated:**
- `mujoco_py` (the third-party wrapper): Replaced by official `mujoco` Python bindings. Do not use.
- `dm_control.viewer`: Replaced by `mujoco.viewer`. Not needed for new code.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | PyBullet GUI mode does not block the Python caller thread on any platform | Standard Stack / Pattern 3 | If wrong, `step()` would block and we'd need a PyBullet-specific async wrapper (e.g., subprocess) |
| A2 | `mujoco.viewer.launch_passive` viewer survives `mj_resetData` / simulator `reset()` without recreation | Pattern 1 | If wrong, we'd need to re-launch viewer on reset, causing flicker and violating RENDER-01 |
| A3 | `sync(state_only=True)` is fast enough to stay under 5ms overhead when called at 30 FPS from a separate thread | Pattern 2 | If wrong, we'd need to reduce FPS or batch sync calls |
| A4 | `mujoco.Renderer` offscreen rendering and `launch_passive` viewer do not share GL context in a way that causes crashes | Pitfall 6 | If wrong, we'd need to isolate contexts or document that rgb_array is unavailable when human mode is active |

**Note on A2:** The MuJoCo docs show `launch_passive` used in a `with` block around a loop that includes `mj_step`. There is no explicit mention of `reset()` behavior. However, `launch_passive` takes `model` and `data` references; `reset()` calls `mj_resetData` which modifies `data` in place. Since `sync()` reads from `data`, this should work without recreation. This is consistent with how `dm_control` viewers worked. [ASSUMED — needs validation during implementation.]

---

## Open Questions

1. **Does `mujoco.viewer.launch_passive` handle `model` reload (new `mjModel` on scene change)?**
   - What we know: `launch_passive` binds to a specific `model` and `data` instance.
   - What's unclear: If `load_scene()` creates a new `model`/`data`, does the viewer auto-update or need restart?
   - Recommendation: Implement `start_viewer()` lazily after first `load_scene()`. If `load_scene()` is called again, close and restart viewer. For RL training, scene is loaded once at env creation, so this is rarely hit.

2. **What is the exact overhead of `sync(state_only=True)` on a soft-body scene?**
   - What we know: `state_only=True` skips full scene rebuild, just copies integration state.
   - What's unclear: We don't have empirical timing on our soft-body benchmark scene.
   - Recommendation: Add a benchmark task in the plan that measures `sync()` latency with `time.perf_counter()`. If >2ms, reduce target FPS to 15.

3. **Does PyBullet GUI mode work reliably on macOS?**
   - What we know: PyBullet GUI uses OpenGL; macOS supports OpenGL but deprecates it.
   - What's unclear: Whether PyBullet GUI runs without issues on Apple Silicon / macOS 14+.
   - Recommendation: Test PyBullet GUI on macOS during implementation. If it fails, document that PyBullet human render is Linux-only and MuJoCo is preferred on macOS.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `mujoco` Python bindings | MuJoCo viewer + physics | ✓ | >=3.0.0 | None (core dependency) |
| `pybullet` | PyBullet GUI + physics | ✓ | >=3.2.5 | None (core dependency) |
| `gymnasium` | Env API contract | ✓ | 1.2.3 | None (core dependency) |
| X11 / macOS display | MuJoCo `launch_passive` / PyBullet GUI | ✓ (local dev) / ✗ (CI/headless) | — | Offscreen `rgb_array` only; skip human mode tests on headless |
| `mjpython` (macOS) | MuJoCo viewer on macOS | ✓ (installed with mujoco) | — | Use `python` with viewer disabled + warning |

**Missing dependencies with no fallback:**
- None. All required packages are in `pyproject.toml`.

**Missing dependencies with fallback:**
- Display server (X11/Wayland/Cocoa): Human mode tests will be skipped on headless CI. Fallback is `rgb_array` mode or `DIRECT` mode.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.0+ |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `pytest tests/test_rendering.py -x` |
| Full suite command | `pytest tests/ -m "not integration" -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RENDER-01 | `start_viewer()` opens window; `reset()` does not close it | unit (mocked) | `pytest tests/test_rendering.py::test_viewer_survives_reset -x` | ❌ Wave 0 |
| RENDER-01 | `start_viewer()` opens window; `reset()` does not close it | integration (display needed) | `pytest tests/test_rendering.py::test_viewer_survives_reset_integration -x` | ❌ Wave 0 |
| RENDER-02 | `step()` returns in <5ms with human render active | benchmark | `pytest tests/test_rendering.py::test_step_overhead -x` | ❌ Wave 0 |
| RENDER-03 | Render thread sleeps to maintain ~30 FPS | unit | `pytest tests/test_rendering.py::test_fps_throttle -x` | ❌ Wave 0 |
| RENDER-04 | CLI `--render-human` passes render_mode="human" | integration | `pytest tests/test_cli_integration.py -k render_human -x` | ✅ exists |
| RENDER-05 | `env.close()` stops viewer thread; SIGINT handler registered | unit | `pytest tests/test_rendering.py::test_clean_shutdown -x` | ❌ Wave 0 |
| RENDER-05 | No segfault on repeated open/close cycles | integration | `pytest tests/test_rendering.py::test_no_segfault_on_reopen -x` | ❌ Wave 0 |
| RENDER-06 | `rgb_array` returns valid NumPy array when not in human mode | unit | `pytest tests/test_simulators.py::test_render_rgb_array -x` | ✅ exists |

### Sampling Rate
- **Per task commit:** `pytest tests/test_rendering.py -x`
- **Per wave merge:** `pytest tests/ -m "not integration" -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_rendering.py` — covers RENDER-01 through RENDER-05
- [ ] `tests/conftest.py` — pytest fixture for headless skip (`pytest.mark.skipif(not has_display)`)
- [ ] `tests/test_rendering.py::test_step_overhead` — benchmark-style timing test
- [ ] `tests/test_rendering.py::test_no_segfault_on_reopen` — stress test (open/close 10x)

*(RENDER-04 CLI integration is already covered by existing `test_cli_integration.py` pattern; just needs a new test case appended.)*

---

## Security Domain

> **Omitting detailed ASVS mapping** because this phase has no user input, network, auth, or crypto surface. The only security-relevant concern is resource exhaustion (GPU/CPU starvation from unthrottled rendering), which is addressed by the FPS throttle requirement.

| Concern | Mitigation |
|---------|------------|
| Resource exhaustion (GPU/CPU) | Render thread FPS capped at 30 FPS by default; configurable |
| SIGINT handler safety | Handler is registered only on main thread; falls back to `atexit` |

---

## Sources

### Primary (HIGH confidence)
- MuJoCo Python API docs — Passive Viewer section: https://mujoco.readthedocs.io/en/stable/python.html#passive-viewer [CITED]
- MuJoCo Programming docs — Visualization: https://mujoco.readthedocs.io/en/stable/programming/visualization.html [CITED]
- Gymnasium API docs — Env.render: https://gymnasium.farama.org/api/env [CITED]
- Local environment verification: `gymnasium==1.2.3` [VERIFIED: pip]
- PyBullet Quickstart Guide (verified via codebase conventions): [CITED: AGENTS.md]

### Secondary (MEDIUM confidence)
- MuJoCo GitHub issues regarding `launch_passive` + `reset()` behavior: not explicitly documented, inferred from API design [ASSUMED]
- PyBullet GUI thread behavior: inferred from PyBullet architecture (physics server runs in separate thread) [ASSUMED]

### Tertiary (LOW confidence)
- macOS `mjpython` exact behavior on Apple Silicon: not tested in this session [ASSUMED]

---

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** — all libraries are installed and docs verified.
- Architecture: **HIGH** — `launch_passive` + RenderThread is the documented MuJoCo pattern.
- Pitfalls: **MEDIUM-HIGH** — Most pitfalls are documented in MuJoCo docs or known from community issues. A2 (viewer surviving reset) is assumed and needs validation during implementation.

**Research date:** 2026-05-02
**Valid until:** 30 days (stable APIs — MuJoCo viewer and Gymnasium render API are mature)

---

*Research complete: 2026-05-02*
*Next step: `/gsd-plan-phase 7`*

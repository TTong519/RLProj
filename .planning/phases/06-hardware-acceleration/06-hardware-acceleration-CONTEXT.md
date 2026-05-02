# Phase 6 Context: Universal Hardware Acceleration

**Phase:** 6 — Universal Hardware Acceleration  
**Milestone:** v0.2.0  
**Date:** 2026-05-02  
**Status:** Discussion in progress

## Domain

Detect and leverage CUDA (NVIDIA), oneAPI/XPU (Intel), ROCm/HIP (AMD), and Metal (Apple) for simulation rendering and compute. Provide a unified `HardwareBackend` enum with auto-detection, per-platform graceful degradation, and Docker variants for each vendor.

## Decisions

### 1. GPU Detection Strategy — External Binaries (Chosen)

**Decision:** Use `shutil.which()` + `subprocess.run()` for detection, with Python imports as secondary/confirmation.

| Backend | Primary Check | Secondary Check |
|---------|---------------|-----------------|
| CUDA | `nvidia-smi --query-gpu=driver_version --format=csv,noheader` | `torch.cuda.is_available()` |
| Intel | `sycl-ls` or `dpctl -l` | `torch.xpu.is_available()` |
| AMD | `rocminfo` | `torch.cuda.is_available()` with hip visible |
| Metal | `system_profiler SPDisplaysDataType` | `torch.backends.mps.is_available()` |

**Rationale:** External binaries are the ground truth for driver/runtime presence. Python imports may succeed against a system lib even if the actual GPU driver is not loaded. Subprocess calls are cached at module level to avoid repeated invocations (lru_cache on the detection function).

### 2. Docker Strategy — Separate Dockerfiles (Chosen)

**Decision:** Separate Dockerfiles per vendor, NOT build-args.

| Dockerfile | Base Image | Use Case |
|------------|-----------|----------|
| `Dockerfile` | `python:3.11-slim-bookworm` | CPU-only (default) |
| `Dockerfile.cuda` | `nvidia/cuda:12.2.0-runtime-ubuntu22.04` | NVIDIA GPU |
| `Dockerfile.rocm` | `rocm/dev-ubuntu-22.04` | AMD GPU |

**Rationale:** Build-args with `FROM ${BASE}` are fragile — ARG substitution doesn't work in all Docker versions, and the base image determines the entire package manager (ubuntu vs debian vs alpine). Separate files are explicit and easier to maintain. No Intel/Metal Dockerfiles — Intel uses CPU docker + optional oneAPI libs; Metal is macOS-only (no Docker).

### 3. MuJoCo Metal on macOS — NSOpenGL Fallback (Chosen)

**Decision:** Metal is NOT supported for MuJoCo in this phase. MuJoCo 3.x on macOS uses the existing `NSOpenGL`/`EGL` path. Metal support in MuJoCo is experimental/not yet stable for our use case.

**Rationale:** MuJoCo's `MjrContext` on macOS falls back to NSOpenGL automatically. Adding a Metal renderer would require MuJoCo API changes we can't control. The "GPU-13: MuJoCo Metal" requirement is downgraded to a documentation note explaining that Metal rendering is not yet available in MuJoCo and the system uses the existing OpenGL path.

**User confirmed:** "Metal is tricky, skip it for now."

### 4. TrainingConfig — Pydantic Enum Model (Chosen)

**Decision:** `HardwareBackend` is a Pydantic `str`-based Enum in `schema.py`, NOT an unconstrained string.

```python
class HardwareBackend(str, Enum):
    auto = "auto"
    cuda = "cuda"
    rocm = "rocm"
    metal = "metal"
    intel = "intel"
    cpu = "cpu"
```

**Rationale:** `str, Enum` gives us JSON/YAML serialization for free (stores as string), but validation rejects invalid values. The `auto` default means users don't need to think about it. `TrainingConfig` gets `backend: HardwareBackend = HardwareBackend.auto`.

### 5. Graceful Degradation — Warn + Fallback to CPU (Chosen)

**Decision:** Explicit warning at `INFO` level, then transparent fallback to CPU. No exception raised for missing GPU.

```
# Example log output
INFO  [surg_rl.utils.gpu] No CUDA driver found (nvidia-smi not in PATH)
INFO  [surg_rl.utils.gpu] No ROCm runtime found (rocminfo not in PATH)
INFO  [surg_rl.utils.gpu] No Metal GPU found (no Apple Silicon detected)
INFO  [surg_rl.utils.gpu] Selected backend: cpu (auto-detect found no GPU)
```

**Rationale:** Researchers running on headless servers, macOS laptops, or CI should not crash. Warning makes the fallback visible. Error only on explicit `backend="cuda"` when CUDA is missing (user asked for something impossible).

### 6. Test Strategy — Mock + Conditional Skip (Chosen)

**Decision:** Unit tests mock `subprocess.run()` and `shutil.which()` to test all code paths. Integration tests skip when no physical GPU is present.

| Test Type | Approach | Location |
|-----------|----------|----------|
| Unit | Mock `subprocess.run(...nvidia-smi...)` to return driver version 535.104.05 | `test_gpu_detector.py` |
| Unit | Mock `shutil.which("rocminfo")` = None, assert fallback to CPU | `test_gpu_detector.py` |
| Integration | `@pytest.mark.skipif(not has_nvidia_gpu(), ...)` | `test_gpu_integration.py` |

**Rationale:** We can't rely on CI having all GPU types (GitHub Actions is CPU-only). Mocks ensure logic paths are covered. Integration tests run on developer machines with GPUs. No GPU-specific integration tests in CI — unit tests are sufficient.

## Deferred Ideas

- **Vulkan compute backend** (ACC-02) — Requires major renderer rewrite; defer to v0.3.0+
- **DirectML for Windows** (ACC-01) — Windows not primary target; defer indefinitely
- **Docker buildx multi-platform** (DEP-02) — In roadmap v0.3.0
- **Kubernetes GPU scheduling** (DEP-01) — In roadmap v0.3.0

## Code Context

- `src/surg_rl/utils/config.py` — `Settings` class with pydantic `BaseSettings`; add `gpu_backend: str = "auto"` field
- `src/surg_rl/simulators/base_simulator.py` — `BaseSimulator.__init__` accepts `**kwargs`; add `backend` param extraction
- `src/surg_rl/simulators/mujoco_simulator.py` — MuJoCo renderer context setup in `__init__` or `_build_renderer()`
- `src/surg_rl/simulators/pybullet_simulator.py` — PyBullet `p.connect()` options; add `options="--gpu"` when backend is GPU
- `src/surg_rl/rl/training.py` — `TrainingConfig` pydantic model; add `backend: HardwareBackend = HardwareBackend.auto`
- `src/surg_rl/cli.py` — Typer CLI; add `--backend [auto|cuda|rocm|metal|intel|cpu]` flag
- `src/surg_rl/utils/__init__.py` or new `src/surg_rl/utils/gpu.py` — Detection module
- `Dockerfile` — already exists; create `Dockerfile.cuda`, `Dockerfile.rocm`
- `pyproject.toml` — add `[gpu]` optional dependency? No — GPU drivers are system-level; no pip packages for NVIDIA/AMD drivers. OneAPI deps optional.

## Dependencies

Phase 7 **blocks** on this phase because:
- Renderer's GPU context (`MjrContext`, EGL, NSOpenGL) must be stable before real-time rendering can be built on it
- `TrainingConfig(backend=...)` must exist before `--render-human` can select the appropriate render path

## Canonical Refs

- `.planning/ROADMAP.md` — Phase 6 goal and success criteria (requirements GPU-01..GPU-16)
- `.planning/REQUIREMENTS.md` — Hardware acceleration requirements (v0.2.0)
- `.planning/PROJECT.md` — Milestone goals and constraints
- `src/surg_rl/simulators/mujoco_simulator.py` — Existing renderer setup
- `src/surg_rl/simulators/pybullet_simulator.py` — Existing `p.connect()` options
- `src/surg_rl/utils/config.py` — `Settings` pydantic model
- `src/surg_rl/rl/training.py` — `TrainingConfig` pydantic model
- `src/surg_rl/cli.py` — CLI entrypoint for `--backend` flag
- `Dockerfile` — Existing multi-stage Dockerfile (CPU-only)

---
*Context captured: 2026-05-02*
*Next step: `/gsd-plan-phase 6` or `/gsd-research-phase 6`*

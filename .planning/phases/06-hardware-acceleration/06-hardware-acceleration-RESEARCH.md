# Phase 6 Research: Universal Hardware Acceleration

**Phase:** 6 — Universal Hardware Acceleration  
**Date:** 2026-05-02  
**Confidence:** High for CUDA/NVIDIA; Medium for Intel/AMD (docs verified); High for macOS/Metal (well-documented)

---

## Standard Stack

### GPU Detection

| Backend | Primary Tool | Python Fallback | Package |
|---------|--------------|---------------|---------|
| NVIDIA CUDA | `nvidia-smi` (subprocess) | `torch.cuda.is_available()` | `torch` (already in deps) |
| Intel oneAPI | `sycl-ls` (subprocess) | `torch.xpu.is_available()` | `intel_extension_for_pytorch` (optional) |
| AMD ROCm | `rocminfo` (subprocess) | `torch.cuda.is_available()` with `torch.version.hip` | `torch` (ROCm build) |
| Apple Metal | `system_profiler` (subprocess) | `torch.backends.mps.is_available()` | `torch` (already in deps) |

**Verdict:** Use `shutil.which()` + `subprocess.run()` as primary for all backends. Python import checks as fast-path confirmation. Rationale: system binaries reflect actual driver installation; Python packages may be installed against system stubs without GPU driver loaded.

### MuJoCo Rendering

MuJoCo 3.x supports these render contexts:

| OS | Context Type | API | GPU? | Notes |
|----|-------------|-----|------|-------|
| Linux | `mjrContext` with `GLFW` | OpenGL 3.3+ | Yes if `libGL` is NVIDIA/AMD | Requires display or EGL |
| Linux | `mjrContext` with `EGL` | EGL 1.4+ | Yes, headless GPU | **Preferred for headless** |
| macOS | `mjrContext` with `Cocoa` | NSOpenGL | Metal translation layer | Apple Silicon uses Metal under hood |
| macOS | `mjrContext` with `GLFW` | OpenGL | Metal translation layer | Same as Cocoa path |

`mujoco.Renderer(model, height, width)` creates an offscreen renderer. It does NOT accept a `gl_context` parameter in MuJoCo 3.x Python bindings. Instead, MuJoCo auto-detects the best available context at runtime. For GPU-accelerated rendering on Linux, ensure `libEGL_nvidia` or `libEGL_mesa` is available.

**Verdict:** Do NOT try to configure `gl_context` in MuJoCo Python. The C API has `mjr_makeContext` but the Python `Renderer` class abstracts this. GPU rendering on Linux is automatic when EGL + GPU driver is present. On macOS, MuJoCo uses Apple's OpenGL-to-Metal translation layer — Metal support is NOT user-configurable.

### PyBullet GPU

PyBullet has NO explicit GPU rendering mode. `p.connect(p.DIRECT)` is CPU-only. `p.connect(p.GUI)` opens an OpenGL window that may use the GPU for rendering IF the display is connected to a GPU.

`getCameraImage(..., renderer=p.ER_BULLET_HARDWARE_OPENGL)` — `ER_BULLET_HARDWARE_OPENGL` uses the GPU if the OpenGL context is GPU-backed. `ER_TINY_RENDERER` is CPU-only.

**Verdict:** PyBullet GPU rendering is implicit (depends on display OpenGL context). Our `backend` flag affects MuJoCo only for rendering. PyBullet gets GPU rendering automatically when running on a machine with GPU + display.

### Docker GPU

| Vendor | Dockerfile Pattern | Runtime Flags |
|--------|-------------------|---------------|
| NVIDIA | `FROM nvidia/cuda:12.2.0-runtime-ubuntu22.04` | `docker run --gpus all` |
| AMD ROCm | `FROM rocm/dev-ubuntu-22.04` | `docker run --device=/dev/kfd --device=/dev/dri` |
| CPU | `FROM python:3.11-slim-bookworm` | None |

NVIDIA Container Toolkit: `--gpus all` mounts the GPU devices and sets `NVIDIA_VISIBLE_DEVICES=all`. The runtime image must have `libnvidia-ml.so` and `libcuda.so` stub symlinks. `nvidia-smi` is NOT always present in the runtime image — the 12.2.0-runtime image includes it, but `12.2.0-base` does not.

ROCm: The `rocm/dev-ubuntu-22.04` image includes `rocminfo` and `rocm-smi`. Volume mounts for `/dev/kfd` (kernel fusion driver) and `/dev/dri` are required. ROCm does NOT use `--gpus` (NVIDIA-specific).

**Verdict:** Use `nvidia/cuda:12.2.0-runtime-ubuntu22.04` for CUDA Dockerfile. It has `nvidia-smi`, `libcuda`, and Ubuntu apt. Use `rocm/dev-ubuntu-22.04` for ROCm.

---

## Architecture Patterns

### Detection Module Structure

```python
# src/surg_rl/utils/gpu.py
import functools
import shutil
import subprocess
from enum import Enum

class HardwareBackend(str, Enum):
    auto = "auto"
    cuda = "cuda"
    rocm = "rocm"
    metal = "metal"
    intel = "intel"
    cpu = "cpu"

@functools.lru_cache(maxsize=1)
def detect_backends() -> list[HardwareBackend]:
    """Return ordered list of available backends (best first)."""
    backends = []
    if _has_cuda(): backends.append(HardwareBackend.cuda)
    if _has_rocm(): backends.append(HardwareBackend.rocm)
    if _has_metal(): backends.append(HardwareBackend.metal)
    if _has_intel(): backends.append(HardwareBackend.intel)
    if not backends:
        backends.append(HardwareBackend.cpu)
    return backends

def select_backend(requested: HardwareBackend) -> HardwareBackend:
    if requested == HardwareBackend.auto:
        return detect_backends()[0]
    available = detect_backends()
    if requested in available:
        return requested
    if requested == HardwareBackend.cpu:
        return HardwareBackend.cpu  # CPU always available
    raise RuntimeError(f"Requested backend {requested.value} not available. "
                       f"Available: {[b.value for b in available]}")
```

**Why `lru_cache(maxsize=1)`:** Detection is idempotent per process. Caching avoids repeated `subprocess` calls. Cache is invalidated implicitly on process restart.

**Why ordered list with CUDA first:** Priority order: CUDA > ROCm > Metal > Intel > CPU. This matches typical research hardware prevalence.

### Simulator Integration

```python
# In MuJoCoSimulator.__init__
backend = select_backend(kwargs.get("backend", HardwareBackend.auto))
self._renderer = mujoco.Renderer(model, height, width)
# MuJoCo auto-detects GPU context; no explicit GPU flag needed
```

```python
# In PyBulletSimulator.__init__
backend = select_backend(kwargs.get("backend", HardwareBackend.auto))
# PyBullet has no explicit GPU flag; ignore backend for rendering
# But log it for user visibility
```

### TrainingConfig Wiring

```python
# In TrainingConfig (src/surg_rl/rl/training.py)
from surg_rl.utils.gpu import HardwareBackend

class TrainingConfig(BaseModel):
    backend: HardwareBackend = HardwareBackend.auto
    # ... existing fields
```

```python
# In CLI (src/surg_rl/cli.py)
@app.command()
def train(
    backend: HardwareBackend = typer.Option(
        HardwareBackend.auto,
        "--backend",
        help="Hardware backend: auto, cuda, rocm, metal, intel, cpu",
    ),
    # ...
):
    config = TrainingConfig(backend=backend, ...)
```

---

## Don't Hand-Roll

| Problem | Use This Instead | Why |
|---------|----------------|-----|
| GPU detection logic | `shutil.which()` + `subprocess.run()` on system binaries | Battle-tested; PyTorch itself wraps nvidia-smi internally |
| MuJoCo offscreen rendering | `mujoco.Renderer()` (Python API) | C API `mjr_makeContext` is internal; Python class is the public API |
| NVIDIA Docker runtime | `nvidia/cuda` base image + `--gpus all` | NVIDIA Container Toolkit is the standard |
| ROCm Docker runtime | `rocm/dev-ubuntu` base image + device mounts | AMD's official container pattern |
| GPU info parsing | `nvidia-smi --query-gpu=... --format=csv` | Stable CLI output format across driver versions |
| Backend enum | `str, Enum` (Python stdlib) | JSON/YAML serialization for free; no custom class needed |

---

## Common Pitfalls

### Pitfall 1: `nvidia-smi` exists but driver is not loaded
`shutil.which("nvidia-smi")` returns a path, but `nvidia-smi` may fail with "NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver." Always check the subprocess return code, not just binary existence.

**Prevention:**
```python
def _has_cuda() -> bool:
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return False
    try:
        result = subprocess.run(
            [nvidia_smi, "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, check=True, timeout=5
        )
        return bool(result.stdout.strip())
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False
```

### Pitfall 2: PyTorch import succeeds but no GPU driver
`import torch` may succeed even if no NVIDIA driver is installed (PyTorch CPU-only wheels). `torch.cuda.is_available()` is the correct check, but it initializes CUDA context (slow, ~1-2s). Use `subprocess` as fast path; only call `torch.cuda` if subprocess succeeds.

**Prevention:** Subprocess first, PyTorch confirmation second. Cache both.

### Pitfall 3: MuJoCo `Renderer` on headless Linux without EGL
On headless servers without display, MuJoCo's `Renderer` defaults to OSMesa (CPU software rendering). This is slow but functional. GPU rendering requires:
1. NVIDIA/AMD driver installed
2. `libEGL.so` available in `LD_LIBRARY_PATH`
3. `__EGL_VENDOR_LIBRARY_DIRS` pointing to vendor EGL ICD

**Prevention:** Log the renderer type. If user requested `backend="cuda"` but MuJoCo falls back to OSMesa, warn them.

### Pitfall 4: ROCm `rocminfo` requires root / video group
`rocminfo` fails with "Unable to open /dev/kfd" if the user is not in the `video` or `render` group. This is a permissions issue, not a missing GPU.

**Prevention:** Check `rocminfo` return code. If it fails with permission error, log a specific message: "ROCm GPU detected but user lacks /dev/kfd permissions. Add user to 'video' group."

### Pitfall 5: `lru_cache` on detection with mutable return values
`detect_backends()` returns a `list`. If cached and then mutated by caller, subsequent calls get the mutated list.

**Prevention:** Return `tuple` instead of `list`, or return a new list each time (but caching the list is fine if we never mutate it). Use `tuple`.

### Pitfall 6: `sycl-ls` not in PATH on Intel systems
Intel oneAPI's `sycl-ls` is typically in `/opt/intel/oneapi/compiler/latest/bin`. Users must `source /opt/intel/oneapi/setvars.sh` before it's available. The detection module should check this path explicitly.

**Prevention:**
```python
_INTEL_PATHS = [
    "/opt/intel/oneapi/compiler/latest/bin",
    "/usr/local/bin",  # common install location
]
def _find_sycl_ls() -> str | None:
    for path in _INTEL_PATHS:
        candidate = os.path.join(path, "sycl-ls")
        if os.path.isfile(candidate):
            return candidate
    return shutil.which("sycl-ls")
```

---

## Code Examples

### Minimal GPU Detection

```python
import shutil
import subprocess

def get_cuda_version() -> str | None:
    """Return CUDA driver version string, or None if not available."""
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return None
    try:
        result = subprocess.run(
            [nvidia_smi, "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, check=True, timeout=5
        )
        return result.stdout.strip().split("\n")[0]
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None
```

### TrainingConfig with Backend

```python
from enum import Enum
from pydantic import BaseModel, Field

class HardwareBackend(str, Enum):
    auto = "auto"
    cuda = "cuda"
    rocm = "rocm"
    metal = "metal"
    intel = "intel"
    cpu = "cpu"

class TrainingConfig(BaseModel):
    backend: HardwareBackend = Field(default=HardwareBackend.auto)
    # ... other fields
```

### MuJoCo with GPU Rendering (Linux)

```python
import mujoco

model = mujoco.MjModel.from_xml_path("scene.xml")
data = mujoco.MjData(model)

# Renderer auto-detects GPU if EGL + NVIDIA driver available
renderer = mujoco.Renderer(model, height=480, width=640)

# Update physics
mujoco.mj_step(model, data)

# Render (offscreen, GPU if available)
renderer.update_scene(data)
img = renderer.render()
```

### Docker CUDA Build

```dockerfile
# Dockerfile.cuda
FROM nvidia/cuda:12.2.0-runtime-ubuntu22.04

# System deps (same as CPU Dockerfile)
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# nvidia-smi is already present in runtime image
COPY pyproject.toml pytest.ini ./
RUN pip install -e ".[dev,tracking]"

COPY . .
```

### Docker ROCm Build

```dockerfile
# Dockerfile.rocm
FROM rocm/dev-ubuntu-22.04

RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev \
    rocminfo \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml pytest.ini ./
RUN pip install -e ".[dev,tracking]"

COPY . .
```

---

## Confidence Levels

| Section | Confidence | Notes |
|---------|-----------|-------|
| CUDA Detection | **High** | `nvidia-smi` is universally used; PyTorch wraps it internally |
| MuJoCo Rendering on Linux | **High** | EGL + NVIDIA driver is well-documented in MuJoCo docs |
| MuJoCo Rendering on macOS | **High** | NSGL path is stable; Metal is not user-configurable |
| PyBullet GPU | **High** | Implicit via OpenGL context; no explicit flag needed |
| Intel oneAPI Detection | **Medium** | `sycl-ls` path varies by install method; may need multiple search paths |
| AMD ROCm Detection | **Medium** | `rocminfo` permissions issue is common; docs are less consolidated |
| Docker NVIDIA | **High** | NVIDIA Container Toolkit is the standard |
| Docker ROCm | **Medium** | Less common than CUDA; device mount requirements vary by host kernel |
| Test Strategy (mock) | **High** | `unittest.mock.patch("subprocess.run")` is standard Python testing |

---

## SOTA vs Training Knowledge

| Topic | What Training Thinks | What's Actually True |
|-------|---------------------|----------------------|
| MuJoCo GPU rendering | "Use `gl_context` kwarg" | Python `Renderer` has no `gl_context`; it's auto-detected |
| PyBullet GPU | "Pass `--gpu` flag" | No such flag; GPU rendering is implicit |
| Intel oneAPI | "Check `torch.xpu`" | `torch.xpu` only with IPEX installed; `sycl-ls` is the ground truth |
| ROCm | "It's like CUDA but for AMD" | ROCm uses HIP, not CUDA; PyTorch must be compiled with ROCm support |
| Docker GPU | "One image with build args" | Separate images per vendor are more reliable (per CONTEXT.md decision) |

---

## References

- MuJoCo Python API docs: https://mujoco.readthedocs.io/en/stable/python.html#rendering
- MuJoCo EGL rendering: https://github.com/deepmind/mujoco/issues/679
- NVIDIA Container Toolkit: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/
- ROCm Docker: https://rocm.docs.amd.com/projects/install-on-linux/en/latest/how-to/docker.html
- Intel oneAPI setvars: https://www.intel.com/content/www/us/en/docs/oneapi/programming-guide/2024-0/oneapi-vars.html
- PyBullet getCameraImage: https://docs.google.com/document/d/10sXEhzFRSnvFcl3XxNGhnD4N2SdaqNHgtjLLEiV9i40/edit

---
*Research complete: 2026-05-02*
*Next step: `/gsd-plan-phase 6`*

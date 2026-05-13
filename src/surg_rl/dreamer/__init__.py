"""DreamerV3 world models — JAX subprocess training from pixels/state.

Optional dependencies: dreamerv3 ~= 1.5.0, jax ~= 0.4.20
Install: pip install surg-rl[dreamer]

Warning: JAX + PyTorch GPU memory conflict — DreamerV3 runs in an isolated
subprocess with XLA_PYTHON_CLIENT_MEM_FRACTION=0.4 (see Phase 24).
"""

from surg_rl.utils.lazy_imports import LazyImport

DREAMER = LazyImport("dreamerv3", "dreamer")

__all__ = ["DREAMER"]

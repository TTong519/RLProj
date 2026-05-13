"""Real surgical mesh assets — trimesh OBJ loading + decimation.

Optional dependency: trimesh >= 4.5.0
Install: pip install surg-rl[assets]
"""

from surg_rl.utils.lazy_imports import LazyImport

TRIMESH = LazyImport("trimesh", "assets")

__all__ = ["TRIMESH"]

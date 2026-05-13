"""Performance benchmarking — experiment runner, plots, per-backend reports.

Optional dependencies: matplotlib, seaborn, pandas, rliable
Install: pip install surg-rl[benchmark]
"""

from surg_rl.utils.lazy_imports import LazyImport

MATPLOTLIB = LazyImport("matplotlib", "benchmark")

__all__ = ["MATPLOTLIB"]

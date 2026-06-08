"""Performance benchmarking — experiment runner, plots, per-backend reports.

Optional dependencies: matplotlib, seaborn, pandas, rliable
Install: pip install surg-rl[benchmark]
"""

from surg_rl.utils.lazy_imports import LazyImport

MATPLOTLIB = LazyImport("matplotlib", "benchmark")
SEABORN = LazyImport("seaborn", "benchmark")
PANDAS = LazyImport("pandas", "benchmark")
RLIABLE = LazyImport("rliable", "benchmark")

from surg_rl.benchmark.experiment_config import ExperimentConfig
from surg_rl.benchmark.experiment_runner import ExperimentRunner
from surg_rl.benchmark.metrics import MetricCollectorCallback, Aggregator

__all__ = [
    "MATPLOTLIB", "SEABORN", "PANDAS", "RLIABLE",
    "ExperimentConfig", "ExperimentRunner",
    "MetricCollectorCallback", "Aggregator",
]

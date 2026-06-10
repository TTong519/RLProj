"""Metric collection and aggregation for benchmark experiments.

Provides MetricCollectorCallback for per-timestep CSV logging during SB3 training,
and Aggregator for computing publication-ready statistics (IQM, mean±std, scalar metrics)
from per-seed CSV files.

Optional dependencies: rliable for IQM/stratified bootstrap CI
Install: pip install surg-rl[benchmark]
"""

import csv
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from stable_baselines3.common.callbacks import BaseCallback

from surg_rl.utils.lazy_imports import LazyImport
from surg_rl.utils.logging import get_logger

RLIABLE = LazyImport("rliable", "benchmark")

logger = get_logger(__name__)


class MetricCollectorCallback(BaseCallback):
    """SB3 callback that writes per-timestep metrics to a CSV file per seed run.

    CSV schema: timestep,reward,episode,episode_reward,episode_length,success,wall_time,algorithm,seed,backend,task

    Attributes:
        csv_path: Path to write per-seed CSV file.
        eval_freq: Frequency (in timesteps) to log evaluation metrics.
    """

    def __init__(self, csv_path: Path, eval_freq: int = 1000):
        """Initialize the metric collector callback.

        Args:
            csv_path: Path to output CSV file (e.g., seed_42_metrics.csv).
            eval_freq: Frequency to write evaluation metrics.
        """
        super().__init__(verbose=0)
        self.csv_path = Path(csv_path)
        self.eval_freq = eval_freq
        self._start_time = None
        self._episode_count = 0
        self._current_episode_reward = 0.0
        self._current_episode_length = 0
        self._csv_file = None
        self._csv_writer = None
        self._algorithm = "unknown"
        self._seed = 0
        self._backend = "unknown"
        self._task = "unknown"

    def _on_training_start(self) -> None:
        """Called when training starts - initialize CSV with header."""
        self._start_time = time.time()

        # Extract metadata from model/env if available
        if hasattr(self.model, "config") and hasattr(self.model.config, "algorithm"):
            self._algorithm = self.model.config.algorithm.name
        if hasattr(self.model, "seed"):
            self._seed = self.model.seed
        # Backend and task from env
        if hasattr(self.model, "env") and self.model.env is not None:
            env = self.model.env
            if hasattr(env, "simulator_type"):
                self._backend = env.simulator_type
            elif hasattr(env, "get_attr"):
                # VecEnv
                try:
                    backend = env.get_attr("simulator_type")[0]
                    self._backend = backend
                except Exception:
                    pass

        # Open CSV file and write header
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        self._csv_file = open(self.csv_path, "w", newline="")
        self._csv_writer = csv.writer(self._csv_file)
        self._csv_writer.writerow(
            [
                "timestep",
                "reward",
                "episode",
                "episode_reward",
                "episode_length",
                "success",
                "wall_time",
                "algorithm",
                "seed",
                "backend",
                "task",
            ]
        )

    def _on_step(self) -> bool:
        """Called at each training step - record metrics."""
        if self._start_time is None:
            return True

        # Get current timestep from model
        timestep = self.model.num_timesteps

        # Get step reward from locals
        locals_dict = self.locals
        rewards = locals_dict.get("rewards", [0.0])
        step_reward = float(rewards[0]) if rewards else 0.0

        # Get info dict for success flag
        infos = locals_dict.get("infos", [{}])
        info = infos[0] if infos else {}
        success = info.get("task_success", info.get("success", False))

        # Update episode tracking
        self._current_episode_reward += step_reward
        self._current_episode_length += 1

        # Calculate wall time
        wall_time = time.time() - self._start_time

        # Check for episode end
        episode = self._episode_count
        episode_reward = 0.0
        episode_length = 0
        episode_end = False

        for ep_info in infos:
            if "episode" in ep_info:
                ep = ep_info["episode"]
                episode_reward = ep.get("r", self._current_episode_reward)
                episode_length = ep.get("l", self._current_episode_length)
                self._episode_count += 1
                # Success from episode info if available
                success = ep_info.get("task_success", ep_info.get("success", success))
                episode_end = True
                break

        # Write row
        self._csv_writer.writerow(
            [
                timestep,
                step_reward,
                episode,
                episode_reward if episode_end else "",
                episode_length if episode_end else "",
                success,
                wall_time,
                self._algorithm,
                self._seed,
                self._backend,
                self._task,
            ]
        )

        # Reset episode accumulators if episode ended
        if episode_end:
            self._current_episode_reward = 0.0
            self._current_episode_length = 0

        return True

    def _on_training_end(self) -> None:
        """Called when training ends - flush and close CSV."""
        self.flush()

    def flush(self) -> None:
        """Flush and close the CSV file."""
        if self._csv_file is not None:
            self._csv_file.flush()
            self._csv_file.close()
            self._csv_file = None
            self._csv_writer = None

    def set_metadata(self, algorithm: str, seed: int, backend: str, task: str) -> None:
        """Set metadata for the CSV (call before training starts)."""
        self._algorithm = algorithm
        self._seed = seed
        self._backend = backend
        self._task = task


class Aggregator:
    """Computes statistics from per-seed CSV files.

    Reads per-seed CSVs, groups by (algorithm, backend), and computes:
    - Learning curve: IQM with stratified bootstrap CI (via rliable)
    - Learning curve: mean ± 1σ across seeds per timestep
    - Scalar metrics: success rate, mean episode length, wall clock time, sample efficiency

    Backend separation is mandatory - MuJoCo and PyBullet results are never aggregated together.
    """

    def __init__(self):
        """Initialize the aggregator."""
        self._rliable_available = RLIABLE.available
        if not self._rliable_available:
            logger.warning("rliable not available - IQM will fall back to mean")

    def read_all_seeds(
        self, results_dir: Path, pattern: str = "seed_*_metrics.csv"
    ) -> dict[tuple[str, str], pd.DataFrame]:
        """Read all per-seed CSVs and group by (algorithm, backend).

        Args:
            results_dir: Directory containing seed_*_metrics.csv files.
            pattern: Glob pattern for CSV files.

        Returns:
            Dictionary mapping (algorithm, backend) to combined DataFrame.
        """
        csv_files = list(results_dir.rglob(pattern))
        if not csv_files:
            logger.warning(f"No CSV files found in {results_dir} with pattern {pattern}")
            return {}

        # Read all CSVs
        dfs = []
        for csv_file in csv_files:
            try:
                df = pd.read_csv(csv_file)
                if not df.empty:
                    dfs.append(df)
            except Exception as e:
                logger.warning(f"Failed to read {csv_file}: {e}")

        if not dfs:
            return {}

        # Combine all data
        combined = pd.concat(dfs, ignore_index=True)

        # Group by (algorithm, backend)
        grouped = {}
        for (algo, backend), group in combined.groupby(["algorithm", "backend"]):
            grouped[(algo, backend)] = group.sort_values(["seed", "timestep"]).reset_index(
                drop=True
            )

        return grouped

    def compute_iqm_ci(
        self, data: pd.DataFrame, confidence: float = 0.95, n_bootstrap: int = 10000
    ) -> dict[str, Any]:
        """Compute Interquartile Mean (IQM) with stratified bootstrap CI.

        Uses rliable library when available. Falls back to mean ± std approximation.

        Args:
            data: DataFrame with columns timestep, reward, seed.
            confidence: Confidence level for CI (default 0.95).
            n_bootstrap: Number of bootstrap samples (default 10000).

        Returns:
            Dictionary with iqm, ci_low, ci_high, method.
        """
        # Pivot to (seeds × timesteps) for rliable
        pivot = data.pivot_table(
            index="seed", columns="timestep", values="reward", aggfunc="first"
        ).sort_index(axis=1)

        # rliable expects (runs, timesteps) array
        scores = pivot.values.T  # Shape: (timesteps, seeds)

        if self._rliable_available:
            try:
                import rliable.metrics as metrics
                import rliable.plot_utils as plot_utils

                # Compute IQM with stratified bootstrap
                iqm = metrics.interquartile_mean(scores)
                ci = plot_utils.stratified_bootstrap_ci(
                    scores,
                    metric_fn=metrics.interquartile_mean,
                    confidence=confidence,
                    n_bootstrap=n_bootstrap,
                )

                return {
                    "iqm": float(iqm),
                    "ci_low": float(ci[0]),
                    "ci_high": float(ci[1]),
                    "method": "iqm_bootstrap",
                }
            except Exception as e:
                logger.warning(f"rliable IQM computation failed: {e}. Falling back to mean.")
                self._rliable_available = False

        # Fallback: mean ± approximate CI using std
        mean_scores = np.mean(scores, axis=1)
        std_scores = np.std(scores, axis=1, ddof=1)
        n_seeds = scores.shape[1]

        # Approximate CI using t-distribution
        from scipy import stats

        t_val = stats.t.ppf((1 + confidence) / 2, n_seeds - 1) if n_seeds > 1 else 1.96
        margin = t_val * std_scores / np.sqrt(n_seeds)

        return {
            "iqm": float(np.mean(mean_scores)),
            "ci_low": float(np.mean(mean_scores) - np.mean(margin)),
            "ci_high": float(np.mean(mean_scores) + np.mean(margin)),
            "method": "mean_approx",
        }

    def compute_mean_std(self, data: pd.DataFrame) -> dict[str, Any]:
        """Compute mean ± 1σ across seeds per timestep.

        Args:
            data: DataFrame with columns timestep, reward, seed.

        Returns:
            Dictionary with mean (Series), std (Series), method.
        """
        # Pivot to get per-seed time series
        pivot = data.pivot_table(
            index="seed", columns="timestep", values="reward", aggfunc="first"
        ).sort_index(axis=1)

        mean_series = pivot.mean(axis=0)
        std_series = pivot.std(axis=0, ddof=1)

        return {"mean": mean_series, "std": std_series, "method": "mean_std"}

    def compute_scalar_metrics(self, data: pd.DataFrame) -> dict[str, Any]:
        """Compute scalar metrics from episode-end data.

        Args:
            data: DataFrame with episode-level columns.

        Returns:
            Dictionary with success_rate, mean_episode_length, wall_clock_time, sample_efficiency.
        """
        # Get episode-end rows (where episode_reward is not NaN)
        episode_data = data.dropna(subset=["episode_reward"])

        if episode_data.empty:
            return {
                "success_rate": 0.0,
                "mean_episode_length": 0.0,
                "wall_clock_time": 0.0,
                "sample_efficiency": 0.0,
            }

        # Success rate
        success_rate = float(episode_data["success"].mean())

        # Mean episode length
        mean_episode_length = float(episode_data["episode_length"].mean())

        # Wall clock time (max wall_time per seed, then mean across seeds)
        wall_times = data.groupby("seed")["wall_time"].max()
        wall_clock_time = float(wall_times.mean())

        # Sample efficiency: mean episode_reward / timestep at evaluation points
        # Use mean reward per timestep ratio
        if "timestep" in episode_data.columns and episode_data["timestep"].max() > 0:
            sample_efficiency = float(
                episode_data["episode_reward"].sum() / episode_data["timestep"].max()
            )
        else:
            sample_efficiency = 0.0

        return {
            "success_rate": success_rate,
            "mean_episode_length": mean_episode_length,
            "wall_clock_time": wall_clock_time,
            "sample_efficiency": sample_efficiency,
        }

    def aggregate_all(self, results_dir: Path) -> dict[tuple[str, str], dict[str, Any]]:
        """Main entry point: read all CSVs, group by (algo, backend), compute all statistics.

        Args:
            results_dir: Directory containing per-seed CSV files.

        Returns:
            Dictionary mapping (algorithm, backend) to aggregated results.
        """
        grouped = self.read_all_seeds(results_dir)
        results = {}

        for (algo, backend), df in grouped.items():
            # Compute all statistics
            learning_curve_iqm = self.compute_iqm_ci(df)
            learning_curve_mean_std = self.compute_mean_std(df)
            scalar_metrics = self.compute_scalar_metrics(df)

            results[(algo, backend)] = {
                "learning_curve_iqm": learning_curve_iqm,
                "learning_curve_mean_std": learning_curve_mean_std,
                "scalar_metrics": scalar_metrics,
            }

        return results

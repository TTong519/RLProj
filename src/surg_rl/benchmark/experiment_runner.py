"""Experiment runner for benchmark experiments.

Orchestrates multiprocessing seed sweeps across algorithms and backends,
collects per-seed metrics, and produces aggregated results.
"""

import logging
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from surg_rl.benchmark.experiment_config import ExperimentConfig
from surg_rl.benchmark.metrics import Aggregator, MetricCollectorCallback
from surg_rl.dreamer.spike import check_spike_status
from surg_rl.dreamer.training import evaluate_checkpoint
from surg_rl.rl.training import AlgorithmConfig, TrainingConfig, TrainingManager
from surg_rl.utils.lazy_imports import LazyImport

RICH = LazyImport("rich", "benchmark")

logger = logging.getLogger(__name__)


@dataclass
class SeedRunResult:
    """Result of a single seed run."""

    algorithm: str
    backend: str
    seed: int
    eval_metrics: dict[str, Any]
    csv_path: Path | None
    status: str  # 'success' or 'failed'
    error: str | None = None


TASK_SCENE_MAP = {
    "suturing": "scenes/simple_suturing.json",
    "knot_tying": "scenes/knot_tying.json",
    "needle_insertion": "scenes/needle_insertion.json",
    "grasping": "scenes/grasping.json",
    "cutting": "scenes/cutting.json",
    "dissection": "scenes/dissection.json",
}


def _run_single_seed(
    algorithm: str,
    backend: str,
    seed: int,
    config: ExperimentConfig,
    output_dir: Path,
    hyperparams: dict | None = None,
) -> SeedRunResult:
    """Run a single seed experiment in a worker process.

    Args:
        algorithm: Algorithm name (PPO, SAC, etc.)
        backend: Simulator backend (mujoco, pybullet)
        seed: Random seed
        config: Experiment configuration
        output_dir: Output directory for this seed
        hyperparams: Algorithm-specific hyperparameter overrides

    Returns:
        SeedRunResult with metrics and status.
    """
    try:
        # Build scene path
        task = config.task or "suturing"
        scene_path = TASK_SCENE_MAP.get(task, f"scenes/{task}.json")

        # Build algorithm config with hyperparameter overrides
        algo_config = AlgorithmConfig(name=algorithm)
        if hyperparams and algorithm in hyperparams:
            for key, value in hyperparams[algorithm].items():
                if hasattr(algo_config, key):
                    setattr(algo_config, key, value)

        # Create training config
        training_config = TrainingConfig(
            scene_path=scene_path,
            algorithm=algo_config,
            total_timesteps=config.timesteps,
            n_envs=1,  # Single env per seed for clean metrics
            seed=seed,
            device=config.device if hasattr(config, "device") else "auto",
            log_dir=str(output_dir / "logs"),
            save_freq=config.save_freq if hasattr(config, "save_freq") else 50000,
            eval_freq=config.eval_freq if hasattr(config, "eval_freq") else 10000,
            n_eval_episodes=config.eval_episodes,
            simulator=backend,
            max_episode_steps=(
                config.max_episode_steps if hasattr(config, "max_episode_steps") else 1000
            ),
            verbose=0,  # Quiet in worker
        )

        # Create output directory for this seed
        seed_dir = output_dir / f"seed_{seed}"
        seed_dir.mkdir(parents=True, exist_ok=True)

        # Create metric collector callback
        csv_path = seed_dir / f"seed_{seed}_metrics.csv"
        metric_callback = MetricCollectorCallback(csv_path, eval_freq=1000)
        metric_callback.set_metadata(algorithm, seed, backend, task)

        # Create training manager and train
        manager = TrainingManager(training_config)
        manager.train(callback=metric_callback)

        # Evaluate
        eval_metrics = manager.evaluate(n_episodes=config.eval_episodes)
        manager.close()

        return SeedRunResult(
            algorithm=algorithm,
            backend=backend,
            seed=seed,
            eval_metrics=eval_metrics,
            csv_path=csv_path,
            status="success",
        )

    except Exception as e:
        logger.error(f"Seed run failed: {algorithm}/{backend}/seed={seed}: {e}")
        traceback.print_exc()
        return SeedRunResult(
            algorithm=algorithm,
            backend=backend,
            seed=seed,
            eval_metrics={},
            csv_path=None,
            status="failed",
            error=str(e),
        )


class ExperimentRunner:
    """Orchestrates benchmark experiment sweeps over algorithms, backends, and seeds."""

    def __init__(self, config: ExperimentConfig):
        """Initialize the experiment runner.

        Args:
            config: Experiment configuration.
        """
        self.config = config
        self.timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.experiment_name = config.experiment_name or f"bench_{self.timestamp}"
        self.task = config.task or "suturing"

        # Build output directory: results/{experiment_name}_{timestamp}/{task}/{backend}/
        self.base_output_dir = (
            Path(config.output_dir or "results") / f"{self.experiment_name}_{self.timestamp}"
        )
        self.base_output_dir.mkdir(parents=True, exist_ok=True)

        # Save effective config
        if config.save_aggregated_json:
            config.to_yaml(self.base_output_dir / "effective_config.yaml")

        # Phase 27 (audit gap "Benchmark-experiments-dir"): write the effective
        # config to experiments/{experiment_name}.yaml so the CLI's "Reproduce
        # with: surg-rl benchmark --config experiments/{name}.yaml" hint
        # (cli.py:1286) points to a real file. to_yaml() auto-mkdirs the
        # experiments/ directory (experiment_config.py:119).
        self.config.to_yaml(Path("experiments") / f"{self.experiment_name}.yaml")

        self._aggregator = Aggregator()

    def run(self) -> dict[tuple[str, str], dict[str, Any]]:
        """Run the full experiment sweep.

        Returns:
            Aggregated results dict mapping (algorithm, backend) to statistics.
        """
        # Resolve algorithms
        algorithms = self.config.effective_algorithms
        # Resolve backends
        backends = self.config.expanded_backends
        # Resolve seeds
        seeds = self.config.seeds if self.config.seeds is not None else [42]

        logger.info(f"Starting experiment: {self.experiment_name}")
        logger.info(f"Task: {self.task}")
        logger.info(f"Algorithms: {algorithms}")
        logger.info(f"Backends: {backends}")
        logger.info(f"Seeds: {seeds}")
        logger.info(f"Timesteps: {self.config.timesteps}")
        logger.info(f"Max parallel: {self.config.max_parallel}")

        all_results = []

        # Run for each backend
        for backend in backends:
            backend_output_dir = self.base_output_dir / self.task / backend
            backend_output_dir.mkdir(parents=True, exist_ok=True)

            logger.info(f"Running backend: {backend}")

            # Run for each algorithm
            for algorithm in algorithms:
                algo_output_dir = backend_output_dir / algorithm.lower()
                algo_output_dir.mkdir(parents=True, exist_ok=True)

                logger.info(f"  Algorithm: {algorithm}")

                # Prepare seed runs
                seed_runs = [
                    (
                        algorithm,
                        backend,
                        seed,
                        self.config,
                        algo_output_dir,
                        self.config.hyperparameters,
                    )
                    for seed in seeds
                ]

                # Run seeds in parallel
                if self.config.max_parallel > 1 and len(seeds) > 1:
                    with ProcessPoolExecutor(max_workers=self.config.max_parallel) as executor:
                        futures = [executor.submit(_run_single_seed, *args) for args in seed_runs]
                        for future in as_completed(futures):
                            result = future.result()
                            all_results.append(result)
                            if result.status == "success":
                                logger.info(
                                    f"    Seed {result.seed}: success (reward={result.eval_metrics.get('mean_reward', 'N/A'):.2f})"
                                )
                            else:
                                logger.warning(f"    Seed {result.seed}: failed - {result.error}")
                else:
                    # Sequential mode
                    for args in seed_runs:
                        result = _run_single_seed(*args)
                        all_results.append(result)
                        if result.status == "success":
                            logger.info(
                                f"    Seed {result.seed}: success (reward={result.eval_metrics.get('mean_reward', 'N/A'):.2f})"
                            )
                        else:
                            logger.warning(f"    Seed {result.seed}: failed - {result.error}")

                # Print summary for this algorithm
                self._print_algo_summary(algorithm, backend, seeds, all_results)

        # Run DreamerV3 evaluation if enabled
        if self.config.dreamer_comparison:
            logger.info("Running DreamerV3 evaluation...")
            dreamer_results = self._run_dreamer_evaluation(backends)
            all_results.extend(dreamer_results)

        # Aggregate results
        logger.info("Aggregating results...")
        aggregated = self._aggregator.aggregate_all(self.base_output_dir)

        # Save aggregated JSON
        if self.config.save_aggregated_json:
            import json

            # Convert to JSON-serializable format
            json_results = {}
            for (algo, backend), stats in aggregated.items():
                key = f"{algo}|{backend}"
                if "status" in stats:
                    json_results[key] = stats
                else:
                    json_results[key] = {
                        "algorithm": algo,
                        "backend": backend,
                        "learning_curve_iqm": stats["learning_curve_iqm"],
                        "learning_curve_mean_std": {
                            "mean": (
                                stats["learning_curve_mean_std"]["mean"].to_dict()
                                if hasattr(stats["learning_curve_mean_std"]["mean"], "to_dict")
                                else str(stats["learning_curve_mean_std"]["mean"])
                            ),
                            "std": (
                                stats["learning_curve_mean_std"]["std"].to_dict()
                                if hasattr(stats["learning_curve_mean_std"]["std"], "to_dict")
                                else str(stats["learning_curve_mean_std"]["std"])
                            ),
                            "method": stats["learning_curve_mean_std"]["method"],
                        },
                        "scalar_metrics": stats["scalar_metrics"],
                    }

            with open(self.base_output_dir / "metrics.json", "w") as f:
                json.dump(json_results, f, indent=2, default=str)

            logger.info(f"Aggregated results saved to {self.base_output_dir / 'metrics.json'}")

        return aggregated

    def _run_dreamer_evaluation(self, backends: list[str]) -> list:
        """Run DreamerV3 evaluation for each task/obs_type if checkpoint exists.

        Args:
            backends: List of backends (for reporting consistency, though DreamerV3 is backend-agnostic)

        Returns:
            List of SeedRunResult-like objects for DreamerV3
        """
        from dataclasses import dataclass
        from pathlib import Path

        @dataclass
        class DreamerResult:
            algorithm: str
            backend: str
            seed: int
            eval_metrics: dict[str, Any]
            csv_path: Path | None
            status: str
            error: str | None = None

        # Check spike status first
        spike_report = check_spike_status()
        results = []

        if spike_report and spike_report.get("status") == "failed":
            logger.warning("DreamerV3 deferred to v0.5.0 (spike failed)")
            for backend in backends:
                results.append(
                    DreamerResult(
                        algorithm="DreamerV3",
                        backend=backend,
                        seed=0,
                        eval_metrics={},
                        csv_path=None,
                        status="deferred",
                        error=f"Spike failed: MSE={spike_report['results']['reconstruction_mse']:.4f}, MAE={spike_report['results']['reward_mae']:.4f}",
                    )
                )
            return results

        if spike_report is None:
            logger.warning("Feasibility spike not run — DreamerV3 will show as pending")
            for backend in backends:
                results.append(
                    DreamerResult(
                        algorithm="DreamerV3",
                        backend=backend,
                        seed=0,
                        eval_metrics={},
                        csv_path=None,
                        status="pending",
                        error="Feasibility spike not run",
                    )
                )
            return results

        # Try to evaluate DreamerV3 checkpoints
        task = self.task or "suturing"
        eval_episodes = (
            self.config.dreamer_eval_episodes
            if hasattr(self.config, "dreamer_eval_episodes")
            else 10
        )

        for obs_type in (
            ["pixels", "state"]
            if getattr(self.config, "dreamer_obs_types", ["pixels", "state"]) == ["pixels", "state"]
            else (
                ["pixels"]
                if getattr(self.config, "dreamer_obs_types", ["pixels"]) == ["pixels"]
                else ["state"]
            )
        ):
            checkpoint_dir = Path(f"models/dreamerv3/{task}_{obs_type}")
            if not checkpoint_dir.exists():
                logger.info(f"No DreamerV3 checkpoint for {task}_{obs_type}")
                for backend in backends:
                    results.append(
                        DreamerResult(
                            algorithm=f"DreamerV3 ({obs_type})",
                            backend=backend,
                            seed=0,
                            eval_metrics={},
                            csv_path=None,
                            status="pending",
                            error="No checkpoint found",
                        )
                    )
                continue

            checkpoints = list(checkpoint_dir.glob("checkpoint_*.pt"))
            if not checkpoints:
                final = checkpoint_dir / "final.pt"
                if final.exists():
                    checkpoints = [final]

            if not checkpoints:
                logger.info(f"No DreamerV3 checkpoint files for {task}_{obs_type}")
                for backend in backends:
                    results.append(
                        DreamerResult(
                            algorithm=f"DreamerV3 ({obs_type})",
                            backend=backend,
                            seed=0,
                            eval_metrics={},
                            csv_path=None,
                            status="pending",
                            error="No checkpoint files",
                        )
                    )
                continue

            latest = max(checkpoints, key=lambda p: p.stat().st_mtime)
            logger.info(f"Evaluating DreamerV3 checkpoint: {latest}")

            try:
                # Use the evaluation function from dreamer.training
                metrics = evaluate_checkpoint(
                    checkpoint_path=str(latest),
                    task=task,
                    obs_type=obs_type,
                    n_episodes=eval_episodes,
                )

                # Add metadata
                metrics["obs_type"] = obs_type
                metrics["checkpoint"] = str(latest)

                for backend in backends:
                    results.append(
                        DreamerResult(
                            algorithm=f"DreamerV3 ({obs_type})",
                            backend=backend,
                            seed=0,
                            eval_metrics=metrics,
                            csv_path=None,
                            status="success",
                        )
                    )

                logger.info(f"DreamerV3 ({obs_type}) evaluation complete: {metrics}")

            except Exception as e:
                logger.error(f"DreamerV3 evaluation failed: {e}")
                for backend in backends:
                    results.append(
                        DreamerResult(
                            algorithm=f"DreamerV3 ({obs_type})",
                            backend=backend,
                            seed=0,
                            eval_metrics={},
                            csv_path=None,
                            status="failed",
                            error=str(e),
                        )
                    )

        return results

    def _print_algo_summary(
        self, algorithm: str, backend: str, seeds: list[int], all_results: list
    ) -> None:
        """Print a summary table for an algorithm/backend combination."""
        algo_results = [r for r in all_results if r.algorithm == algorithm and r.backend == backend]

        if not algo_results:
            return

        [r for r in algo_results if r.status == "success"]
        failed = [r for r in algo_results if r.status == "failed"]

        if RICH.available:
            from rich.console import Console
            from rich.table import Table

            console = Console()

            table = Table(title=f"{algorithm} on {backend}")
            table.add_column("Seed", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Mean Reward", style="yellow")
            table.add_column("Success Rate", style="blue")
            table.add_column("Mean Length", style="magenta")

            for r in algo_results:
                if r.status == "success":
                    m = r.eval_metrics
                    table.add_row(
                        str(r.seed),
                        "✓ success",
                        f"{m.get('mean_reward', 0):.2f}",
                        f"{m.get('success_rate', 0):.1%}",
                        f"{m.get('mean_episode_length', 0):.1f}",
                    )
                else:
                    table.add_row(str(r.seed), "[red]failed[/red]", "-", "-", "-")

            console.print(table)
        else:
            print(f"\n  {algorithm} on {backend}:")
            for r in algo_results:
                if r.status == "success":
                    m = r.eval_metrics
                    print(
                        f"    seed={r.seed}: reward={m.get('mean_reward', 0):.2f}, success={m.get('success_rate', 0):.1%}"
                    )
                else:
                    print(f"    seed={r.seed}: FAILED - {r.error}")

            if failed:
                print(f"  WARNING: {len(failed)}/{len(seeds)} seeds failed")

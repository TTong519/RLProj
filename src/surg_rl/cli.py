"""Command-line interface for Surg-RL."""

import asyncio
import json
import os
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from surg_rl import __version__
from surg_rl.scene_definition.schema import HardwareBackend
from surg_rl.scene_generation import TextParser, VisionParser, get_template
from surg_rl.utils.config import get_settings
from surg_rl.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


def _yaml_serialize(scene):
    """Serialize a scene to YAML-safe dict."""
    return scene.model_dump(mode="json")


app = typer.Typer(
    name="surg-rl",
    help="Surgical Robotics RL Training System",
    add_completion=False,
)

console = Console()


@app.callback()
def main():
    """CLI entry point."""
    setup_logging()


@app.command()
def version(verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed system info including GPU availability")) -> None:
    """Show version information."""
    from surg_rl.scene_definition.schema import HardwareBackend
    from surg_rl.utils.gpu import (
        detect_backends,
        get_cuda_version,
        get_rocm_version,
        select_backend,
    )
    console.print(f"[bold blue]Surg-RL[/bold blue] version: [green]{__version__}[/green]")
    if verbose:
        backends = detect_backends()
        table = Table(title="GPU Availability")
        table.add_column("Backend", style="cyan")
        table.add_column("Available", style="green")
        table.add_column("Version / Info", style="yellow")
        for backend in [HardwareBackend.cuda, HardwareBackend.rocm, HardwareBackend.metal, HardwareBackend.intel, HardwareBackend.cpu]:
            available = backend in backends
            version_info = "N/A"
            if backend == HardwareBackend.cuda and available:
                version_info = get_cuda_version() or "N/A"
            elif backend == HardwareBackend.rocm and available:
                version_info = get_rocm_version() or "N/A"
            elif backend == HardwareBackend.metal and available:
                version_info = "Apple Silicon" if "arm" in os.uname().machine.lower() else "Intel Mac"
            elif backend == HardwareBackend.intel and available:
                version_info = "oneAPI / XPU"
            elif backend == HardwareBackend.cpu:
                version_info = "Always available"
            table.add_row(backend.value, "Yes" if available else "No", version_info)
        console.print(table)
        default_backend = select_backend(HardwareBackend.auto)
        console.print(f"Default backend: {default_backend.value}")


@app.command()
def config() -> None:
    """Show current configuration."""
    settings = get_settings()

    table = Table(title="Current Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    config_items = [
        ("Version", __version__),
        ("Project Root", str(settings.project_root)),
        ("Default Simulator", settings.default_simulator),
        ("", ""),
        ("LLM Provider", settings.llm_provider),
        ("LLM Model", settings.llm_model),
        ("VLM Model", settings.vlm_model),
        ("", ""),
        ("Ollama Base URL", settings.ollama_base_url),
        ("Ollama Model", settings.ollama_model),
        ("Ollama Vision Model", settings.ollama_vision_model),
        ("Ollama Timeout", f"{settings.ollama_timeout}s"),
        ("", ""),
        ("Render Width", str(settings.render_width)),
        ("Render Height", str(settings.render_height)),
        ("RL Seed", str(settings.rl_seed)),
        ("Log Level", settings.log_level),
    ]

    for key, value in config_items:
        if key == "":
            table.add_row("", "")
        else:
            table.add_row(key, value)

    console.print(table)


@app.command()
def setup() -> None:
    """Set up project directories."""
    settings = get_settings()
    settings.ensure_directories()

    console.print("[bold green]✓[/bold green] Project directories created:")
    console.print(f"  • Assets: {settings.assets_dir}")
    console.print(f"  • Scenes: {settings.scenes_dir}")
    console.print(f"  • Configs: {settings.configs_dir}")


@app.command()
def generate(
    text: str = typer.Option(None, "--text", "-t", help="Text description of scene"),
    image: str = typer.Option(None, "--image", "-i", help="Path to image file"),
    template: str = typer.Option(None, "--template", "-T", help="Use a predefined template"),
    output: str = typer.Option("scene.json", "--output", "-o", help="Output file path"),
    format: str = typer.Option("json", "--format", "-f", help="Output format (json or yaml)"),
    provider: str = typer.Option(
        None, "--provider", "-p", help="LLM provider (openai, anthropic, ollama)"
    ),
    model: str = typer.Option(None, "--model", "-m", help="Model name to use"),
    ollama_url: str = typer.Option(
        None, "--ollama-url", help="Ollama API base URL (for ollama provider)"
    ),
) -> None:
    """Generate a scene from text, image, or template input."""
    try:
        if template:
            console.print(f"[bold blue]Loading template:[/bold blue] {template}")
            try:
                scene = get_template(template)
            except ValueError as e:
                console.print(f"[bold red]Error:[/bold red] {e}")
                console.print("[dim]Available templates: suturing, dissection, manipulation[/dim]")
                raise typer.Exit(1) from e

            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if format == "yaml":
                import yaml

                content = yaml.dump(
                    _yaml_serialize(scene), default_flow_style=False, sort_keys=False
                )
            else:
                content = json.dumps(scene.model_dump(mode="json"), indent=2)

            output_path.write_text(content)
            console.print(f"[bold green]✓[/bold green] Scene saved to: {output_path}")
            console.print(f"  • Name: {scene.metadata.name}")
            console.print(f"  • Robots: {len(scene.robots)}")
            console.print(f"  • Tissues: {len(scene.tissues)}")
            console.print(f"  • Instruments: {len(scene.instruments)}")
            return

        if text:
            console.print("[bold blue]Generating scene from text...[/bold blue]")
            console.print(f"[dim]Provider: {provider or 'default'}[/dim]")
            console.print(f"[dim]Description: {text[:100]}{'...' if len(text) > 100 else ''}[/dim]")

            try:
                parser = TextParser(
                    provider=provider,
                    model=model,
                    ollama_base_url=ollama_url,
                )
                scene = asyncio.run(parser.parse(text))
            except ImportError as e:
                console.print(f"[bold red]Import Error:[/bold red] {e}")
                console.print(
                    "[dim]The required LLM package may not be installed. "
                    "Try using --provider ollama to use a local model instead.[/dim]"
                )
                raise typer.Exit(1) from e

            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if format == "yaml":
                import yaml

                content = yaml.dump(
                    _yaml_serialize(scene), default_flow_style=False, sort_keys=False
                )
            else:
                content = json.dumps(scene.model_dump(mode="json"), indent=2)

            output_path.write_text(content)
            console.print(f"[bold green]✓[/bold green] Scene saved to: {output_path}")
            console.print(f"  • Name: {scene.metadata.name}")
            console.print(f"  • Robots: {len(scene.robots)}")
            console.print(f"  • Tissues: {len(scene.tissues)}")
            console.print(f"  • Instruments: {len(scene.instruments)}")
            return

        if image:
            console.print("[bold blue]Generating scene from image...[/bold blue]")
            console.print(f"[dim]Provider: {provider or 'default'}[/dim]")
            console.print(f"[dim]Image: {image}[/dim]")

            try:
                parser = VisionParser(
                    provider=provider,
                    model=model,
                    ollama_base_url=ollama_url,
                )
                scene = asyncio.run(parser.parse(image))
            except ImportError as e:
                console.print(f"[bold red]Import Error:[/bold red] {e}")
                console.print(
                    "[dim]The required LLM package may not be installed. "
                    "Try using --provider ollama to use a local model instead.[/dim]"
                )
                raise typer.Exit(1) from e

            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if format == "yaml":
                import yaml

                content = yaml.dump(
                    _yaml_serialize(scene), default_flow_style=False, sort_keys=False
                )
            else:
                content = json.dumps(scene.model_dump(mode="json"), indent=2)

            output_path.write_text(content)
            console.print(f"[bold green]✓[/bold green] Scene saved to: {output_path}")
            console.print(f"  • Name: {scene.metadata.name}")
            console.print(f"  • Robots: {len(scene.robots)}")
            console.print(f"  • Tissues: {len(scene.tissues)}")
            console.print(f"  • Instruments: {len(scene.instruments)}")
            return

        console.print("[bold red]Error:[/bold red] No input provided.")
        console.print("[dim]Use --text, --image, or --template to specify input.[/dim]")
        raise typer.Exit(1)

    except Exception as e:
        logger.error(f"Scene generation failed: {e}")
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e


@app.command()
def train(
    scene: str = typer.Option(..., "--scene", "-s", help="Path to scene file"),
    algorithm: str = typer.Option(
        "PPO", "--algorithm", "-a", help="RL algorithm (PPO, SAC, TD3, DDPG, A2C)"
    ),
    timesteps: int = typer.Option(100000, "--timesteps", "-t", help="Total training timesteps"),
    n_envs: int = typer.Option(1, "--n-envs", "-n", help="Number of parallel environments"),
    seed: int = typer.Option(42, "--seed", help="Random seed"),
    learning_rate: float = typer.Option(3e-4, "--lr", help="Learning rate"),
    batch_size: int = typer.Option(64, "--batch-size", help="Batch size"),
    device: str = typer.Option("auto", "--device", help="Device (auto, cpu, cuda, mps)"),
    log_dir: str = typer.Option("logs/training", "--log-dir", help="Log directory"),
    save_freq: int = typer.Option(50000, "--save-freq", help="Checkpoint save frequency"),
    eval_freq: int = typer.Option(10000, "--eval-freq", help="Evaluation frequency"),
    curriculum: bool = typer.Option(False, "--curriculum", help="Enable curriculum learning"),
    adaptive: bool = typer.Option(False, "--adaptive", help="Enable adaptive difficulty"),
    simulator: str = typer.Option(
        "mujoco", "--simulator", help="Simulator backend (mujoco, pybullet)"
    ),
    max_episode_steps: int = typer.Option(1000, "--max-steps", help="Max steps per episode"),
    verbose: int = typer.Option(1, "--verbose", "-v", help="Verbosity level (0, 1, 2)"),
    wandb: bool = typer.Option(False, "--wandb", help="Enable Weights \u0026 Biases logging"),
    mlflow: bool = typer.Option(False, "--mlflow", help="Enable MLflow logging"),
    experiment_name: str | None = typer.Option(None, "--experiment-name", "-e", help="Experiment name for tracking"),
    wandb_project: str | None = typer.Option(None, "--wandb-project", help="W\u0026B project name (default: surg-rl)"),
    backend: str = typer.Option(
        "auto", "--backend", help="Hardware backend: auto, cuda, rocm, metal, intel, cpu"
    ),
) -> None:
    """Train an RL agent on a surgical scene.

    Supports PPO, SAC, TD3, DDPG, and A2C algorithms via Stable-Baselines3.

    Examples:
        surg-rl train --scene scenes/suturing.json --algorithm PPO --timesteps 100000
        surg-rl train --scene scenes/suturing.json --algorithm SAC --lr 1e-4 --curriculum
        surg-rl train --scene scenes/suturing.json --algorithm PPO --n-envs 4 --device cuda
    """
    from surg_rl.rl.training import AlgorithmConfig, TrainingConfig, TrainingManager

    console.print("[bold blue]Starting RL Training[/bold blue]")
    console.print(f"  • Scene: {scene}")
    console.print(f"  • Algorithm: {algorithm}")
    console.print(f"  • Timesteps: {timesteps:,}")
    console.print(f"  • Seed: {seed}")

    try:
        algo_config = AlgorithmConfig(
            name=algorithm.upper(),
            learning_rate=learning_rate,
            batch_size=batch_size,
        )

        backend_enum = HardwareBackend(backend)

        config = TrainingConfig(
            scene_path=scene,
            algorithm=algo_config,
            total_timesteps=timesteps,
            n_envs=n_envs,
            seed=seed,
            device=device,
            log_dir=log_dir,
            save_freq=save_freq,
            eval_freq=eval_freq,
            simulator=simulator,
            max_episode_steps=max_episode_steps,
            use_curriculum=curriculum,
            use_adaptive_difficulty=adaptive,
            verbose=verbose,
            use_wandb=wandb,
            use_mlflow=mlflow,
            experiment_name=experiment_name,
            wandb_project=wandb_project,
            backend=backend_enum,
        )

        manager = TrainingManager(config)
        manager.train()

        console.print("[bold green]✓ Training complete![/bold green]")
        console.print(f"  • Model saved to: {log_dir}/final_model")

    except ImportError as e:
        console.print(f"[bold red]Import Error:[/bold red] {e}")
        console.print(
            "[dim]Make sure stable-baselines3 is installed: pip install stable-baselines3[/dim]"
        )
        console.print(
            "[dim]stable-baselines3 is listed in pyproject.toml dependencies. "
            'If the import still fails, reinstall with: pip install -e ".[dev]"[/dim]'
        )
        raise typer.Exit(1) from e
    except Exception as e:
        logger.error(f"Training failed: {e}")
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e


@app.command()
def evaluate(
    scene: str = typer.Option(..., "--scene", "-s", help="Path to scene file"),
    model: str = typer.Option(..., "--model", "-m", help="Path to trained model"),
    episodes: int = typer.Option(10, "--episodes", "-e", help="Number of evaluation episodes"),
    render: bool = typer.Option(False, "--render", "-r", help="Render during evaluation"),
    simulator: str = typer.Option("mujoco", "--simulator", help="Simulator backend"),
    seed: int = typer.Option(42, "--seed", help="Random seed"),
    verbose: int = typer.Option(1, "--verbose", "-v", help="Verbosity level"),
) -> None:
    """Evaluate a trained RL agent.

    Runs evaluation episodes and reports performance metrics.

    Examples:
        surg-rl evaluate --scene scenes/suturing.json --model logs/training/final_model
        surg-rl evaluate --scene scenes/suturing.json --model model.zip --episodes 20 --render
    """
    from surg_rl.rl.training import TrainingConfig, TrainingManager

    console.print("[bold blue]Starting Evaluation[/bold blue]")
    console.print(f"  • Scene: {scene}")
    console.print(f"  • Model: {model}")
    console.print(f"  • Episodes: {episodes}")

    try:
        config = TrainingConfig(
            scene_path=scene,
            seed=seed,
            simulator=simulator,
            verbose=verbose,
        )

        manager = TrainingManager(config)
        results = manager.evaluate(
            model_path=model,
            n_episodes=episodes,
            render=render,
        )

        # Display results
        table = Table(title="Evaluation Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Episodes", str(results["n_episodes"]))
        table.add_row("Mean Reward", f"{results['mean_reward']:.2f}")
        table.add_row("Std Reward", f"{results['std_reward']:.2f}")
        table.add_row("Max Reward", f"{results['max_reward']:.2f}")
        table.add_row("Min Reward", f"{results['min_reward']:.2f}")
        table.add_row("Mean Length", f"{results['mean_episode_length']:.1f}")
        table.add_row("Success Rate", f"{results['success_rate']:.1%}")

        console.print(table)

    except ImportError as e:
        console.print(f"[bold red]Import Error:[/bold red] {e}")
        console.print(
            "[dim]Make sure stable-baselines3 is installed: pip install stable-baselines3[/dim]"
        )
        console.print(
            "[dim]stable-baselines3 is listed in pyproject.toml dependencies. "
            'If the import still fails, reinstall with: pip install -e ".[dev]"[/dim]'
        )
        raise typer.Exit(1) from e
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e


if __name__ == "__main__":
    app()

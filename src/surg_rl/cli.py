"""Command-line interface for Surg-RL."""

import typer
from rich.console import Console
from rich.table import Table

from surg_rl import __version__
from surg_rl.utils.config import get_settings

app = typer.Typer(
    name="surg-rl",
    help="Surgical Robotics RL Training System",
    add_completion=False,
)

console = Console()


@app.command()
def version() -> None:
    """Show version information."""
    console.print(f"[bold blue]Surg-RL[/bold blue] version: [green]{__version__}[/green]")


@app.command()
def config() -> None:
    """Show current configuration."""
    settings = get_settings()

    table = Table(title="Current Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    # Display key settings
    config_items = [
        ("Version", __version__),
        ("Project Root", str(settings.project_root)),
        ("Default Simulator", settings.default_simulator),
        ("LLM Provider", settings.llm_provider),
        ("LLM Model", settings.llm_model),
        ("Render Width", str(settings.render_width)),
        ("Render Height", str(settings.render_height)),
        ("RL Seed", str(settings.rl_seed)),
        ("Log Level", settings.log_level),
    ]

    for key, value in config_items:
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
    output: str = typer.Option("scene.json", "--output", "-o", help="Output file path"),
) -> None:
    """Generate a scene from text or image input.

    This command will be implemented in Step 3 (Scene Generation Module).
    """
    console.print("[yellow]Scene generation not yet implemented.[/yellow]")
    console.print("[yellow]This feature will be available after Step 3.[/yellow]")
    console.print(f"[dim]Text: {text}[/dim]")
    console.print(f"[dim]Image: {image}[/dim]")
    console.print(f"[dim]Output: {output}[/dim]")


@app.command()
def train(
    scene: str = typer.Option(..., "--scene", "-s", help="Path to scene file"),
    algorithm: str = typer.Option("PPO", "--algorithm", "-a", help="RL algorithm"),
    timesteps: int = typer.Option(100000, "--timesteps", "-t", help="Training timesteps"),
) -> None:
    """Train an RL agent on a scene.

    This command will be implemented in Step 7 (RL Training Pipeline).
    """
    console.print("[yellow]Training not yet implemented.[/yellow]")
    console.print("[yellow]This feature will be available after Step 7.[/yellow]")
    console.print(f"[dim]Scene: {scene}[/dim]")
    console.print(f"[dim]Algorithm: {algorithm}[/dim]")
    console.print(f"[dim]Timesteps: {timesteps}[/dim]")


@app.command()
def evaluate(
    scene: str = typer.Option(..., "--scene", "-s", help="Path to scene file"),
    model: str = typer.Option(..., "--model", "-m", help="Path to trained model"),
    episodes: int = typer.Option(10, "--episodes", "-e", help="Number of episodes"),
) -> None:
    """Evaluate a trained agent.

    This command will be implemented in Step 7 (RL Training Pipeline).
    """
    console.print("[yellow]Evaluation not yet implemented.[/yellow]")
    console.print("[yellow]This feature will be available after Step 7.[/yellow]")
    console.print(f"[dim]Scene: {scene}[/dim]")
    console.print(f"[dim]Model: {model}[/dim]")
    console.print(f"[dim]Episodes: {episodes}[/dim]")


if __name__ == "__main__":
    app()

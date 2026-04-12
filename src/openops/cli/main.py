"""Main CLI application for OpenOps.

Provides the command-line interface using Typer with Rich formatting.
"""

import logging
import sys
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel

from openops import __version__
from openops.config import get_config
from openops.credentials.platforms import (
    get_deployment_platforms,
    get_llm_platforms,
    get_platform_credential,
)
from openops.exceptions import ConfigurationError, CredentialError, OpenOpsError

console = Console()
err_console = Console(stderr=True)

app = typer.Typer(
    name="openops",
    help="OpenOps - An agentic DevOps assistant",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def setup_logging(debug: bool = False) -> None:
    """Configure logging based on debug flag."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )
    if not debug:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("langgraph").setLevel(logging.WARNING)


def show_error(error: Exception, hint: str | None = None) -> None:
    """Display an error message with optional hint."""
    message = str(error)
    content = f"[red]Error:[/red] {message}"
    if hint:
        content += f"\n\n[dim]Hint: {hint}[/dim]"

    err_console.print(Panel(content, title="Error", border_style="red"))


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        console.print(f"[bold blue]OpenOps[/bold blue] version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-v",
            help="Show version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
    debug: Annotated[
        bool,
        typer.Option("--debug", "-d", help="Enable debug logging."),
    ] = False,
) -> None:
    """OpenOps - An agentic DevOps assistant.

    Use natural language to deploy and manage your applications.
    """
    setup_logging(debug)


@app.command()
def version() -> None:
    """Show version information."""
    console.print(f"[bold blue]OpenOps[/bold blue] version {__version__}")

    config = get_config()
    console.print(f"Model: {config.model_provider}/{config.model_name}")
    console.print(f"Data dir: {config.data_dir}")


@app.command()
def doctor() -> None:
    """Check system health and configuration."""
    import importlib.metadata

    console.print(Panel("[bold]OpenOps Health Check[/bold]", style="blue"))
    console.print()

    console.print(f"Python:     [green]✓[/green] {sys.version.split()[0]}")

    try:
        langchain_ver = importlib.metadata.version("langchain")
        console.print(f"LangChain:  [green]✓[/green] {langchain_ver}")
    except importlib.metadata.PackageNotFoundError:
        console.print("LangChain:  [red]✗[/red] not installed")

    try:
        langgraph_ver = importlib.metadata.version("langgraph")
        console.print(f"LangGraph:  [green]✓[/green] {langgraph_ver}")
    except importlib.metadata.PackageNotFoundError:
        console.print("LangGraph:  [red]✗[/red] not installed")

    config = get_config()

    console.print()
    console.print("[bold]Configuration:[/bold]")
    console.print(f"  Data dir: {config.data_dir}")
    if config.data_dir.exists():
        console.print("  Status:   [green]✓[/green] exists")
    else:
        console.print("  Status:   [yellow]○[/yellow] not created yet")

    console.print()
    console.print("[bold]LLM Providers:[/bold]")

    for platform_id, platform in get_llm_platforms().items():
        key = getattr(config, platform.config_attr, None)
        if key:
            console.print(f" {platform_id} {platform.name}:".ljust(14) + "[green]✓[/green] configured")
        else:
            console.print(f" {platform_id} {platform.name}:".ljust(14) + "[dim]○[/dim] not configured")

    console.print()
    console.print("[bold]Deployment Platforms:[/bold]")
    for platform_id, platform in get_deployment_platforms().items():
        token = get_platform_credential(platform_id, config)
        if token:
            console.print(f" {platform_id} {platform.name}:".ljust(14) + "[green]✓[/green] configured")
        else:
            console.print(f" {platform_id} {platform.name}:".ljust(14) + "[dim]○[/dim] not configured")


@app.command()
def monitor(
    action: Annotated[
        str,
        typer.Argument(help="Action: start, stop, status, logs"),
    ] = "status",
) -> None:
    """Monitoring daemon (coming in Phase 2).

    Actions:
    - start: Start background monitoring daemon
    - stop: Stop the daemon
    - status: Check daemon status
    - logs: Stream daemon logs
    """
    console.print(
        Panel(
            "[yellow]The monitoring feature is coming in Phase 2.[/yellow]\n\n"
            "This will include:\n"
            "• Background daemon for continuous monitoring\n"
            "• Log streaming and aggregation\n"
            "• Alerting and notifications\n"
            "• Health check automation",
            title="Coming Soon",
            border_style="yellow",
        )
    )


def _handle_cli_error(error: Exception) -> None:
    """Handle CLI errors with appropriate messaging."""
    if isinstance(error, ConfigurationError):
        show_error(error, hint="Run 'openops init' to configure OpenOps")
    elif isinstance(error, CredentialError):
        show_error(error, hint="Run 'openops credentials add <platform>' to add credentials")
    elif isinstance(error, OpenOpsError):
        show_error(error)
    else:
        show_error(error, hint="Run with --debug for more details")


def run_cli() -> None:
    """Entry point for the CLI with error handling."""
    try:
        app()
    except OpenOpsError as e:
        _handle_cli_error(e)
        raise typer.Exit(1) from e
    except KeyboardInterrupt as e:
        console.print("\n[dim]Interrupted[/dim]")
        raise typer.Exit(130) from e
    except Exception as e:
        _handle_cli_error(e)
        raise typer.Exit(1) from e


__all__ = ["app", "console", "err_console", "show_error", "run_cli"]

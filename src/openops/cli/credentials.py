"""Credentials management commands for OpenOps.

Provides commands to add, list, remove, and test platform credentials.
"""

import logging
import os
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from openops.cli.main import app, show_error
from openops.config import get_config
from openops.credentials import (
    get_all_platforms,
    get_deployment_platforms,
    get_llm_platforms,
    get_platform,
)

logger = logging.getLogger(__name__)
console = Console()

credentials_app = typer.Typer(
    name="credentials",
    help="Manage platform credentials.",
    no_args_is_help=True,
)

app.add_typer(credentials_app, name="credentials")

ENV_FILE_PATH = Path.home() / ".openops" / ".env"


def _load_env_file() -> dict[str, str]:
    """Load environment variables from the OpenOps .env file."""
    env_vars: dict[str, str] = {}
    if ENV_FILE_PATH.exists():
        with open(ENV_FILE_PATH) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    env_vars[key.strip()] = value.strip()
    return env_vars


def _save_env_file(env_vars: dict[str, str]) -> None:
    """Save environment variables to the OpenOps .env file."""
    ENV_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(ENV_FILE_PATH, "w") as f:
        f.write("# OpenOps Configuration\n")
        f.write("# Managed by 'openops credentials'\n\n")
        for key, value in sorted(env_vars.items()):
            f.write(f"{key}={value}\n")


def _mask_token(token: str) -> str:
    """Mask a token for display."""
    if len(token) > 8:
        return token[:4] + "*" * (len(token) - 8) + token[-4:]
    return "*" * len(token)


def _get_valid_platforms() -> str:
    """Get comma-separated list of valid platform names."""
    return ", ".join(get_all_platforms().keys())


@credentials_app.command("list")
def credentials_list(
    reveal: Annotated[
        bool,
        typer.Option(
            "--reveal",
            "-r",
            help="Reveal credential values.",
        ),
    ] = False,
) -> None:
    """List all configured credentials.

    Shows the status of all platform and LLM provider credentials.

    Examples:

        openops credentials list            # List with masked values

        openops credentials list --reveal   # Show actual values
    """
    config = get_config()

    console.print(Panel("[bold]Configured Credentials[/bold]", style="blue"))
    console.print()

    table = Table(show_header=True, header_style="bold")
    table.add_column("Platform", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Value", style="dim")

    table.add_row("[bold]LLM Providers[/bold]", "", "")

    for _platform_id, info in get_llm_platforms().items():
        value = getattr(config, info.config_attr, None)

        if value:
            status = "[green]✓ configured[/green]"
            display = value if reveal else _mask_token(value)
        else:
            status = "[dim]○ not set[/dim]"
            display = ""

        table.add_row(info.name, status, display)

    table.add_row("", "", "")
    table.add_row("[bold]Deployment Platforms[/bold]", "", "")

    for _platform_id, info in get_deployment_platforms().items():
        value = getattr(config, info.config_attr, None)

        if value:
            status = "[green]✓ configured[/green]"
            display = value if reveal else _mask_token(value)
        else:
            status = "[dim]○ not set[/dim]"
            display = ""

        table.add_row(info.name, status, display)

    console.print(table)

    console.print()
    console.print(f"[dim]API keys stored in: {ENV_FILE_PATH}[/dim]")


@credentials_app.command("add")
def credentials_add(
    platform: Annotated[
        str,
        typer.Argument(
            help="Platform to add credentials for (vercel, railway, render, anthropic, openai, google, deepseek).",
        ),
    ],
    token: Annotated[
        str | None,
        typer.Option(
            "--token",
            "-t",
            help="Token/API key value. If not provided, will prompt.",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Overwrite existing credentials without confirmation.",
        ),
    ] = False,
) -> None:
    """Add credentials for a platform.

    Examples:

        openops credentials add vercel              # Interactive prompt

        openops credentials add railway --token=XXX # Direct input

        openops credentials add deepseek            # Add DeepSeek API key

        openops credentials add vercel --force      # Overwrite existing
    """
    info = get_platform(platform)

    if info is None:
        show_error(
            ValueError(f"Unknown platform: {platform}"),
            hint=f"Valid platforms: {_get_valid_platforms()}",
        )
        raise typer.Exit(1)

    config = get_config()

    existing = getattr(config, info.config_attr, None)
    if existing and not force:
        console.print(f"[yellow]Credentials for {info.name} already exist.[/yellow]")
        if not Confirm.ask("Overwrite?", default=False):
            console.print("[dim]Cancelled.[/dim]")
            return

    if token is None:
        console.print(f"\n[bold]{info.name}[/bold]")
        console.print(f"[dim]{info.description}[/dim]")
        console.print(f"[dim]Get your token at: {info.help_url}[/dim]")
        console.print()

        token = Prompt.ask(f"Enter your {info.name} token/key", password=True)

    if not token.strip():
        show_error(ValueError("Token cannot be empty"))
        raise typer.Exit(1)

    env_vars = _load_env_file()
    env_vars[info.env_var] = token.strip()
    _save_env_file(env_vars)

    os.environ[info.env_var] = token.strip()

    console.print(f"[green]✓[/green] Added credentials for {info.name}")
    console.print(f"[dim]Saved to {ENV_FILE_PATH}[/dim]")


@credentials_app.command("remove")
def credentials_remove(
    platform: Annotated[
        str,
        typer.Argument(
            help="Platform to remove credentials for.",
        ),
    ],
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Skip confirmation prompt.",
        ),
    ] = False,
) -> None:
    """Remove credentials for a platform.

    Examples:

        openops credentials remove vercel           # With confirmation

        openops credentials remove railway --force  # Skip confirmation
    """
    info = get_platform(platform)

    if info is None:
        show_error(
            ValueError(f"Unknown platform: {platform}"),
            hint=f"Valid platforms: {_get_valid_platforms()}",
        )
        raise typer.Exit(1)

    env_vars = _load_env_file()
    if info.env_var not in env_vars:
        console.print(f"[dim]No credentials found for {info.name}.[/dim]")
        return

    if not force:
        if not Confirm.ask(
            f"[yellow]Remove credentials for {info.name}?[/yellow]",
            default=False,
        ):
            console.print("[dim]Cancelled.[/dim]")
            return

    del env_vars[info.env_var]
    _save_env_file(env_vars)

    if info.env_var in os.environ:
        del os.environ[info.env_var]

    console.print(f"[green]✓[/green] Removed credentials for {info.name}")


@credentials_app.command("test")
def credentials_test(
    platform: Annotated[
        str,
        typer.Argument(
            help="Platform to test credentials for.",
        ),
    ],
) -> None:
    """Test credentials for a platform.

    Attempts to make a simple API call to verify credentials are valid.

    Examples:

        openops credentials test anthropic

        openops credentials test vercel
    """
    info = get_platform(platform)

    if info is None:
        show_error(
            ValueError(f"Unknown platform: {platform}"),
            hint=f"Valid platforms: {_get_valid_platforms()}",
        )
        raise typer.Exit(1)

    config = get_config()

    token = getattr(config, info.config_attr)
    if not token:
        show_error(
            ValueError(f"No credentials configured for {info.name}"),
            hint=f"Run 'openops credentials add {platform}' to configure",
        )
        raise typer.Exit(1)

    if info.validator is None:
        console.print(f"[yellow]○[/yellow] Testing not implemented for {info.name}")
        return

    console.print(f"Testing {info.name} credentials...")

    result = info.validator(token)

    if result.valid:
        console.print(f"[green]✓[/green] {info.name} credentials are valid")
        if result.details:
            for key, value in result.details.items():
                console.print(f"  [dim]{key}: {value}[/dim]")
    else:
        console.print(f"[red]✗[/red] {info.name} credentials are invalid")
        if result.message:
            console.print(f"  [dim]{result.message}[/dim]")
        raise typer.Exit(1)


__all__ = ["credentials_app"]

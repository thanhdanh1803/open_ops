"""Configuration management commands for OpenOps.

Provides commands to view and modify OpenOps configuration.
"""

import logging
import os
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from openops.cli.main import app, show_error
from openops.config import get_config

logger = logging.getLogger(__name__)
console = Console()

config_app = typer.Typer(
    name="config",
    help="Manage OpenOps configuration.",
    no_args_is_help=True,
)

app.add_typer(config_app, name="config")

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
        f.write("# Managed by 'openops config'\n\n")
        for key, value in sorted(env_vars.items()):
            f.write(f"{key}={value}\n")


def _mask_sensitive(key: str, value: str) -> str:
    """Mask sensitive values like API keys."""
    sensitive_keywords = ["key", "token", "secret", "password", "api"]
    if any(kw in key.lower() for kw in sensitive_keywords):
        if len(value) > 8:
            return value[:4] + "*" * (len(value) - 8) + value[-4:]
        return "*" * len(value)
    return value


@config_app.command("show")
def config_show(
    reveal: Annotated[
        bool,
        typer.Option(
            "--reveal",
            "-r",
            help="Reveal sensitive values (API keys, tokens).",
        ),
    ] = False,
) -> None:
    """Show current configuration.

    Displays all configuration values from environment and config files.
    Sensitive values are masked by default.

    Examples:

        openops config show             # Show config with masked secrets

        openops config show --reveal    # Show all values including secrets
    """
    config = get_config()

    console.print(Panel("[bold]OpenOps Configuration[/bold]", style="blue"))
    console.print()

    table = Table(show_header=True, header_style="bold")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Source", style="dim")

    model_settings = [
        ("model_provider", config.model_provider, "env/default"),
        ("model_name", config.model_name, "env/default"),
        ("model_temperature", str(config.model_temperature), "env/default"),
        ("model_max_tokens", str(config.model_max_tokens), "env/default"),
    ]

    for key, value, source in model_settings:
        table.add_row(key, value, source)

    table.add_row("", "", "")
    table.add_row("[bold]Paths[/bold]", "", "")

    table.add_row("data_dir", str(config.data_dir), "env/default")
    table.add_row("projects_db", str(config.projects_db_path), "computed")
    table.add_row("checkpoints_db", str(config.checkpoints_db_path), "computed")

    table.add_row("", "", "")
    table.add_row("[bold]Credentials[/bold]", "", "")

    credentials = [
        ("anthropic_api_key", config.anthropic_api_key, "ANTHROPIC_API_KEY"),
        ("openai_api_key", config.openai_api_key, "OPENAI_API_KEY"),
        ("google_api_key", config.google_api_key, "GOOGLE_API_KEY"),
        ("vercel_token", config.vercel_token, "OPENOPS_VERCEL_TOKEN"),
        ("railway_token", config.railway_token, "OPENOPS_RAILWAY_TOKEN"),
        ("render_api_key", config.render_api_key, "OPENOPS_RENDER_API_KEY"),
    ]

    for key, value, env_var in credentials:
        if value:
            display_value = value if reveal else _mask_sensitive(key, value)
            source = f"env ({env_var})"
        else:
            display_value = "[dim]not set[/dim]"
            source = ""
        table.add_row(key, display_value, source)

    table.add_row("", "", "")
    table.add_row("[bold]Behavior[/bold]", "", "")

    table.add_row("default_platform", config.default_platform, "env/default")
    table.add_row("dry_run", str(config.dry_run), "env/default")
    table.add_row("debug", str(config.debug), "env/default")
    table.add_row("log_level", config.log_level, "env/default")

    console.print(table)

    console.print()
    console.print(f"[dim]Config file: {ENV_FILE_PATH}[/dim]")


@config_app.command("get")
def config_get(
    key: Annotated[
        str,
        typer.Argument(help="Configuration key to retrieve."),
    ],
    reveal: Annotated[
        bool,
        typer.Option(
            "--reveal",
            "-r",
            help="Reveal sensitive values.",
        ),
    ] = False,
) -> None:
    """Get a specific configuration value.

    Examples:

        openops config get model_provider

        openops config get vercel_token --reveal
    """
    config = get_config()

    try:
        value = getattr(config, key)
    except AttributeError as e:
        show_error(
            KeyError(f"Unknown configuration key: {key}"),
            hint="Run 'openops config show' to see all available keys.",
        )
        raise typer.Exit(1) from e

    if value is None:
        console.print(f"{key}: [dim]not set[/dim]")
    else:
        display_value = str(value)
        if not reveal:
            display_value = _mask_sensitive(key, display_value)
        console.print(f"{key}: {display_value}")


@config_app.command("set")
def config_set(
    key: Annotated[
        str,
        typer.Argument(help="Configuration key to set."),
    ],
    value: Annotated[
        str,
        typer.Argument(help="Value to set."),
    ],
) -> None:
    """Set a configuration value.

    Configuration is stored in ~/.openops/.env

    Examples:

        openops config set model_provider openai

        openops config set model_name gpt-4o

        openops config set default_platform railway
    """
    config_key_to_env = {
        "model_provider": "OPENOPS_MODEL_PROVIDER",
        "model_name": "OPENOPS_MODEL_NAME",
        "model_temperature": "OPENOPS_MODEL_TEMPERATURE",
        "model_max_tokens": "OPENOPS_MODEL_MAX_TOKENS",
        "data_dir": "OPENOPS_DATA_DIR",
        "default_platform": "OPENOPS_DEFAULT_PLATFORM",
        "dry_run": "OPENOPS_DRY_RUN",
        "debug": "OPENOPS_DEBUG",
        "log_level": "OPENOPS_LOG_LEVEL",
        "vercel_token": "OPENOPS_VERCEL_TOKEN",
        "railway_token": "OPENOPS_RAILWAY_TOKEN",
        "render_api_key": "OPENOPS_RENDER_API_KEY",
        "anthropic_api_key": "ANTHROPIC_API_KEY",
        "openai_api_key": "OPENAI_API_KEY",
        "google_api_key": "GOOGLE_API_KEY",
    }

    if key not in config_key_to_env:
        show_error(
            KeyError(f"Unknown configuration key: {key}"),
            hint="Run 'openops config show' to see all available keys.",
        )
        raise typer.Exit(1)

    env_var = config_key_to_env[key]

    env_vars = _load_env_file()
    env_vars[env_var] = value
    _save_env_file(env_vars)

    os.environ[env_var] = value

    display_value = _mask_sensitive(key, value)
    console.print(f"[green]✓[/green] Set {key} = {display_value}")
    console.print(f"[dim]Saved to {ENV_FILE_PATH}[/dim]")


@config_app.command("reset")
def config_reset(
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Skip confirmation prompt.",
        ),
    ] = False,
) -> None:
    """Reset configuration to defaults.

    This removes the ~/.openops/.env file. Your credentials will need
    to be reconfigured.

    Examples:

        openops config reset            # Interactive confirmation

        openops config reset --force    # Skip confirmation
    """
    if not ENV_FILE_PATH.exists():
        console.print("[dim]No configuration file to reset.[/dim]")
        return

    if not force:
        from rich.prompt import Confirm

        if not Confirm.ask(
            "[yellow]This will delete your configuration file. Continue?[/yellow]",
            default=False,
        ):
            console.print("[dim]Cancelled.[/dim]")
            return

    ENV_FILE_PATH.unlink()
    console.print(f"[green]✓[/green] Removed {ENV_FILE_PATH}")
    console.print("[dim]Run 'openops init' to reconfigure.[/dim]")


@config_app.command("path")
def config_path() -> None:
    """Show configuration file path.

    Useful for scripting or manual editing.
    """
    console.print(str(ENV_FILE_PATH))


__all__ = ["config_app"]

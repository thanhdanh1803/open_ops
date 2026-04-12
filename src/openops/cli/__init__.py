"""CLI module - command-line interface."""

import typer

app = typer.Typer(
    name="openops",
    help="OpenOps - An agentic DevOps assistant",
    no_args_is_help=True,
)

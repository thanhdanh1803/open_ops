"""CLI module - command-line interface for OpenOps.

This module provides the main CLI application and all subcommands.
"""

from openops.cli.chat import chat
from openops.cli.config_cmd import config_app
from openops.cli.credentials import credentials_app
from openops.cli.deploy import deploy
from openops.cli.init_cmd import init_cmd
from openops.cli.main import app, console, err_console, run_cli, show_error

__all__ = [
    "app",
    "console",
    "err_console",
    "run_cli",
    "show_error",
    "chat",
    "config_app",
    "credentials_app",
    "deploy",
    "init_cmd",
]

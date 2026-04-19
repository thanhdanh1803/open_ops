"""Helpers for running local commands and ensuring CLI prerequisites.

This module is used by interactive CLI commands (e.g. `openops init`).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys

from rich.console import Console
from rich.prompt import Confirm

logger = logging.getLogger(__name__)

_LINUXBREW_CANDIDATES = [
    "/home/linuxbrew/.linuxbrew/bin/brew",
    str(os.path.expanduser("~/.linuxbrew/bin/brew")),
]


def which(cmd: str) -> str | None:
    """Locate a command in PATH."""
    return shutil.which(cmd)


def run_live_command(command: list[str], *, console: Console, check: bool = True) -> int:
    """Run a command with live output (stdin/stdout/stderr attached).

    Returns the process return code.
    """
    logger.info("Running command: %s", " ".join(command))
    try:
        completed = subprocess.run(command, check=False)
    except FileNotFoundError:
        console.print(f"[red]✗[/red] Command not found: {command[0]}")
        return 127
    except Exception as e:
        logger.debug("Command failed to start: %s", e)
        console.print(f"[red]✗[/red] Failed to run command: {' '.join(command)}")
        return 1

    if check and completed.returncode != 0:
        console.print(f"[red]✗[/red] Command failed (exit {completed.returncode})")
    return completed.returncode


def ensure_brew(*, console: Console) -> bool:
    """Ensure Homebrew exists on macOS."""
    if which("brew"):
        return True

    if sys.platform == "darwin":
        console.print("[yellow]Homebrew not found.[/yellow]")
        console.print("[dim]To install Homebrew, see: https://brew.sh[/dim]")
        return False

    if sys.platform.startswith("linux"):
        console.print("[yellow]Homebrew (Linuxbrew) not found.[/yellow]")
        console.print("[dim]We can install Homebrew to manage tmux and Node.js.[/dim]")
        console.print("[dim]This will run Homebrew's official installer script.[/dim]")

        if not Confirm.ask("Install Homebrew now?", default=True):
            return False

        if not which("curl"):
            console.print("[red]✗[/red] curl not found. Please install curl and rerun `openops init`.")
            return False

        rc = run_live_command(
            [
                "bash",
                "-lc",
                'NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"',
            ],
            console=console,
            check=True,
        )
        if rc != 0:
            return False

        # The installer may add brew in common prefixes but not to PATH for this process.
        for brew_path in _LINUXBREW_CANDIDATES:
            if os.path.exists(brew_path):
                os.environ["PATH"] = f"{os.path.dirname(brew_path)}:{os.environ.get('PATH', '')}"
                break

        if which("brew"):
            return True

        console.print("[yellow]Homebrew installed but not found on PATH.[/yellow]")
        console.print("[dim]Open a new terminal (or add Homebrew to your PATH) and rerun `openops init`.[/dim]")
        return False

    return False


def ensure_tmux(*, console: Console) -> bool:
    """Ensure tmux exists (required for interactive tmux tool)."""
    if which("tmux"):
        return True

    console.print()
    console.print("[bold]Prerequisite: tmux[/bold]")
    console.print("[dim]OpenOps uses tmux for fully interactive commands (TTY prompts, editors, pagers).[/dim]")

    if not Confirm.ask("tmux is not installed. Install it now?", default=True):
        console.print("[red]✗[/red] tmux is required for interactive command execution.")
        return False

    if sys.platform == "darwin":
        if not ensure_brew(console=console):
            return False
        rc = run_live_command(["brew", "install", "tmux"], console=console, check=True)
        return rc == 0 and which("tmux") is not None

    console.print("[red]✗[/red] Automatic tmux installation is only supported on macOS right now.")
    console.print("[dim]Please install tmux and rerun `openops init`.[/dim]")
    return False


def ensure_npx(*, console: Console) -> bool:
    """Ensure npx exists (required to bootstrap community skills tooling)."""
    if which("npx"):
        return True

    console.print()
    console.print("[bold]Prerequisite: npx (Node.js)[/bold]")
    console.print("[dim]npx is provided by Node.js/npm and is used to install the community skills tooling.[/dim]")

    if not Confirm.ask("npx is not installed. Install Node.js (includes npx) now?", default=True):
        console.print("[red]✗[/red] npx is required to bootstrap find-skill.")
        return False

    if sys.platform == "darwin":
        if not ensure_brew(console=console):
            return False
        rc = run_live_command(["brew", "install", "node"], console=console, check=True)
        return rc == 0 and which("npx") is not None

    console.print("[red]✗[/red] Automatic Node.js installation is only supported on macOS right now.")
    console.print("[dim]Please install Node.js (which includes npx) and rerun `openops init`.[/dim]")
    return False


def add_find_skills_global(*, console: Console) -> bool:
    """Install the Vercel Labs skills pack globally via `skills` CLI."""
    if not which("npx"):
        console.print("[red]✗[/red] npx not found. Cannot add community skills pack.")
        return False

    console.print()
    console.print("[bold]Step: Community skills[/bold]")
    console.print("[dim]Adding Vercel Labs skills pack globally...[/dim]")

    rc = run_live_command(
        [
            "npx",
            "skills",
            "add",
            "https://github.com/vercel-labs/skills",
            "--skill",
            "find-skills",
            "--global",
            "--yes",
        ],
        console=console,
        check=True,
    )
    return rc == 0

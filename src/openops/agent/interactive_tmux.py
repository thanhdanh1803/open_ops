"""tmux-based interactive command execution for local development.

This module provides a helper to run a command in a temporary tmux session,
attach the user for interactive input, and then return a captured transcript.

It is intended for LocalShellBackend usage only.
"""

from __future__ import annotations

import logging
import os
import secrets
import shlex
import subprocess
import tempfile
from pathlib import Path

from openops.live_display_bridge import (
    pause_cli_live_for_external_tty,
    resume_cli_live_after_external_tty,
)

logger = logging.getLogger(__name__)


class TmuxError(RuntimeError):
    pass


def _run_tmux(args: list[str], *, timeout_s: float) -> subprocess.CompletedProcess[str]:
    logger.debug("Running tmux: %s", " ".join(shlex.quote(a) for a in args))
    try:
        return subprocess.run(
            ["tmux", *args],
            text=True,
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
    except FileNotFoundError as e:
        raise TmuxError("tmux is not installed or not on PATH") from e


def interactive_execute_tmux(
    command: str,
    *,
    timeout_s: float = 1800.0,
    tmux_timeout_s: float = 15.0,
) -> dict[str, str]:
    """Run `command` in a temporary tmux session, attach, and return transcript.

    Notes:
    - Uses tmux `pipe-pane` to capture all pane output to a temp log file.
    - Attaches the user to the session (interactive). User detaches (Ctrl-b d)
      or exits the shell to return control to the caller.
    - Cleans up the session and temp log afterward.
    """
    if not command.strip():
        raise ValueError("command must be non-empty")

    session = f"openops-{secrets.token_hex(6)}"
    log_path = Path(tempfile.gettempdir()) / f"{session}.log"

    logger.info("Creating tmux session %s", session)
    log_path.write_text("", encoding="utf-8")

    # Run inside a login shell so common env setup is applied.
    # Keep the user in a shell after the command finishes.
    banner = "--- tmux: interactive shell (exit or detach to return) ---"
    wrapped_cmd = f"{command}; " f"echo; echo {shlex.quote(banner)}; " f'exec "${{SHELL:-bash}}" -l'
    wrapped = f"bash -lc {shlex.quote(wrapped_cmd)}"

    # Ensure PATH exists for tmux and common CLIs.
    os.environ.setdefault("PATH", "/usr/bin:/bin:/usr/local/bin")

    created = _run_tmux(["new-session", "-d", "-s", session, wrapped], timeout_s=tmux_timeout_s)
    if created.returncode != 0:
        raise TmuxError(created.stderr.strip() or created.stdout.strip() or "Failed to create tmux session")

    try:
        pipe_cmd = f"cat >> {shlex.quote(str(log_path))}"
        piped = _run_tmux(
            ["pipe-pane", "-o", "-t", f"{session}:0.0", pipe_cmd],
            timeout_s=tmux_timeout_s,
        )
        if piped.returncode != 0:
            raise TmuxError(piped.stderr.strip() or piped.stdout.strip() or "Failed to enable tmux pipe-pane")

        logger.info("Attaching to tmux session %s (detach with Ctrl-b then d)", session)
        pause_cli_live_for_external_tty()
        try:
            attach = subprocess.run(
                ["tmux", "attach-session", "-t", session],
                timeout=timeout_s,
                check=False,
            )
        finally:
            resume_cli_live_after_external_tty()
        if attach.returncode != 0:
            raise TmuxError(f"tmux attach failed with exit code {attach.returncode}")

        transcript = log_path.read_text(encoding="utf-8").rstrip() + "\n"
        return {
            "session": session,
            "log_path": str(log_path),
            "transcript": transcript,
            "note": "Detached/exited tmux. Transcript includes pane output and may contain sensitive data.",
        }
    except subprocess.TimeoutExpired as e:
        raise TmuxError(f"Interactive session timed out after {timeout_s:.0f}s") from e
    finally:
        logger.info("Cleaning up tmux session %s", session)
        _run_tmux(["pipe-pane", "-t", f"{session}:0.0"], timeout_s=tmux_timeout_s)
        _run_tmux(["kill-session", "-t", session], timeout_s=tmux_timeout_s)
        try:
            log_path.unlink(missing_ok=True)
        except Exception:
            logger.debug("Failed to delete temp log %s", log_path, exc_info=True)

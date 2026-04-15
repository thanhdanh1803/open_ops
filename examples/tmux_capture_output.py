#!/usr/bin/env python3
"""Run a command inside tmux and print its output back to this terminal.

This script:
1) starts a temporary detached tmux session
2) runs a command inside that session
3) captures the tmux pane output
4) kills the temporary session
5) prints the captured output to stdout

Usage:
    python examples/tmux_capture_output.py
    python examples/tmux_capture_output.py --cmd "echo hello from tmux && uname -a"
"""

from __future__ import annotations

import argparse
import logging
import os
import secrets
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

# Add src to path for local development (matches other examples)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class TmuxError(RuntimeError):
    pass


def _run_tmux(args: list[str], *, timeout_s: float = 15.0) -> subprocess.CompletedProcess[str]:
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


def run_command_in_tmux_and_capture(
    command: str,
) -> str:
    """
    Run `command` inside a temporary tmux session, attach interactively, then return output.

    Behavior (always-on interactive):
    - The command runs inside tmux and its output is also appended to a temp log file.
    - After the command finishes, tmux leaves you in an interactive shell so you can type.
    - When you detach/exit, this function reads the log file and returns it, then cleans up.
    """
    session = f"openops-{secrets.token_hex(6)}"
    logger.info("Creating tmux session %s", session)

    # Use a temp file to reliably capture output, even after the user interacts.
    log_path = Path(tempfile.gettempdir()) / f"{session}.log"
    # Ensure it exists/empty.
    log_path.write_text("", encoding="utf-8")

    # Run inside a login shell so common env setup is applied.
    # We rely on tmux `pipe-pane` (enabled below) to capture *all* pane output,
    # including anything you run interactively after the command finishes.
    wrapped_cmd = (
        f"{command}; "
        f"echo; echo '--- tmux: interactive shell (exit or detach to return) ---'; "
        f'exec "${{SHELL:-bash}}" -l'
    )
    wrapped = f"bash -lc {shlex.quote(wrapped_cmd)}"

    created = _run_tmux(["new-session", "-d", "-s", session, wrapped], timeout_s=15.0)
    if created.returncode != 0:
        raise TmuxError(f"Failed to create session: {created.stderr.strip() or created.stdout.strip()}")

    try:
        # Capture everything rendered in the main pane to the log file.
        # -o: only set if not already set (avoid duplicate piping if re-run)
        pipe_cmd = f"cat >> {shlex.quote(str(log_path))}"
        piped = _run_tmux(["pipe-pane", "-o", "-t", f"{session}:0.0", pipe_cmd], timeout_s=15.0)
        if piped.returncode != 0:
            raise TmuxError(f"Failed to enable pipe-pane: {piped.stderr.strip() or piped.stdout.strip()}")

        logger.info("Attaching to tmux session %s (detach with Ctrl-b then d)", session)
        attach = subprocess.run(["tmux", "attach-session", "-t", session], check=False)
        if attach.returncode != 0:
            raise TmuxError(f"tmux attach failed with exit code {attach.returncode}")

        # User detached/exited; return the captured command output.
        return log_path.read_text(encoding="utf-8").rstrip() + "\n"
    finally:
        logger.info("Cleaning up tmux session %s", session)
        _run_tmux(["pipe-pane", "-t", f"{session}:0.0"], timeout_s=15.0)
        _run_tmux(["kill-session", "-t", session], timeout_s=15.0)
        try:
            log_path.unlink(missing_ok=True)
        except Exception:
            logger.debug("Failed to delete temp log %s", log_path, exc_info=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a command in tmux and print its output.")
    parser.add_argument(
        "--cmd",
        default="echo 'hello from tmux' && pwd",
        help="Shell command to run inside tmux (executed via bash -lc).",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Ensure PATH is set (some environments run python with minimal env).
    os.environ.setdefault("PATH", "/usr/bin:/bin:/usr/local/bin")

    try:
        output = run_command_in_tmux_and_capture(args.cmd)
    except TmuxError as e:
        logger.error("%s", e)
        return 2

    # Print the output captured from tmux back to this terminal.
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

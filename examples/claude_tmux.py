#!/usr/bin/env python3
"""Test script to run a command inside tmux and capture the output back to the terminal.

This script:
1. Creates a new tmux session
2. Runs a command inside tmux
3. Leaves the session open so the user can interact / type input
4. On exit (Ctrl+C or session close), captures and prints the final pane output

Usage:
    cd /Users/danhmac/Documents/open_ops
    python examples/claude_tmux.py
"""

import signal
import subprocess
import time

SESSION_NAME = "claude_tmux_session"


def cleanup():
    """Kill the tmux session on exit."""
    subprocess.run(
        ["tmux", "kill-session", "-t", SESSION_NAME],
        capture_output=True,
    )


def run_initial_command(command: str) -> str:
    """Send an initial command to a running tmux session and capture output.

    Args:
        command: The shell command to send to the tmux pane.

    Returns:
        The captured pane output after the command runs.
    """
    # Send the command to the tmux pane
    subprocess.run(
        ["tmux", "send-keys", "-t", SESSION_NAME, command, "C-m"],
        check=True,
    )
    # Brief pause to let the command render
    time.sleep(0.3)
    # Capture the pane output
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", SESSION_NAME, "-p"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def wait_for_session_close() -> str:
    """Wait for the tmux session to close and return the final pane output."""
    # Poll the session periodically until it's gone
    last_output = ""
    while True:
        # Check if session still exists
        check = subprocess.run(
            ["tmux", "has-session", "-t", SESSION_NAME],
            capture_output=True,
        )
        if check.returncode != 0:
            # Session is gone — try to capture one last time from a dead session
            # (it may already be cleaned up, so fall back to last output)
            break

        # Capture current pane output
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", SESSION_NAME, "-p"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            last_output = result.stdout

        time.sleep(0.5)

    return last_output


def main():
    print("=== Starting tmux session ===\n")
    print("A tmux session will be opened with your command pre-loaded.")
    print("You can interact with it normally (type input, run commands).")
    print("Press Ctrl+C or close the tmux session to finish —")
    print("the final pane output will be printed below.\n")

    # Clean up any stale session from a previous run
    subprocess.run(
        ["tmux", "kill-session", "-t", SESSION_NAME],
        capture_output=True,
    )

    # Register cleanup on exit (Ctrl+C)
    signal.signal(signal.SIGINT, lambda sig, frame: cleanup())
    signal.signal(signal.SIGTERM, lambda sig, frame: cleanup())

    # Create a detached tmux session running bash
    # -d: detached, -s: session name, the rest: the command to run
    subprocess.run(
        [
            "tmux",
            "new-session",
            "-d",
            "-s",
            SESSION_NAME,
            "bash --norc --noprofile",
        ],
        check=True,
    )
    print(f"[OK] Created tmux session: {SESSION_NAME}")
    print(f"     Attach with: tmux attach-session -t {SESSION_NAME}\n")

    # --- Define the initial command to pre-load ---
    initial_command = 'echo "Hello from tmux! Type something below..."'
    # You can change this to anything, e.g.:
    # initial_command = "ls -la"

    print(f"--- Sending initial command: {initial_command} ---")
    output = run_initial_command(initial_command)
    print(f"Pane output:\n{output}\n")

    print("=== Session is open — interact with tmux now ===")
    print("Attach with: tmux attach-session -t", SESSION_NAME)
    print("When you're done, close the session (Ctrl+D, exit, or detach).\n")

    # Wait for the session to close, collecting final output
    try:
        final_output = wait_for_session_close()
    finally:
        cleanup()

    print("=== Session closed — final pane output ===")
    print(final_output if final_output else "(no output captured)")
    print("\n=== Done ===")


if __name__ == "__main__":
    main()

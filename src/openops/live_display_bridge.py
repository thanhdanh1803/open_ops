"""Bridge so non-CLI code can pause Rich ``Live`` while the TTY is handed to another process.

The interactive chat wraps ``runtime.invoke`` in ``Live`` + ``Spinner``. Subprocesses
that take over the terminal (e.g. ``tmux attach-session``) must stop that refresh
loop first, or the spinner keeps drawing on the same TTY.
"""

from __future__ import annotations

import logging

from rich.live import Live

logger = logging.getLogger(__name__)

_active_live: Live | None = None
_paused_for_external_tty: bool = False


def bind_cli_live(live: Live | None) -> None:
    """Register the chat ``Live`` instance for the current invoke (or clear)."""
    global _active_live
    _active_live = live


def unbind_cli_live() -> None:
    """Clear registration; resume display if still paused from a nested TTY handoff."""
    global _active_live, _paused_for_external_tty
    if _paused_for_external_tty:
        resume_cli_live_after_external_tty()
    _active_live = None


def pause_cli_live_for_external_tty() -> None:
    """Stop Rich Live refresh/hooks before another program owns the terminal."""
    global _paused_for_external_tty
    if _active_live is None or not _active_live.is_started:
        return
    logger.info("Pausing CLI live display for external TTY session")
    _active_live.stop()
    _paused_for_external_tty = True


def resume_cli_live_after_external_tty() -> None:
    """Restore Rich Live after returning from an external TTY session."""
    global _paused_for_external_tty
    if not _paused_for_external_tty:
        return
    _paused_for_external_tty = False
    if _active_live is None or _active_live.is_started:
        return
    logger.info("Resuming CLI live display after external TTY session")
    _active_live.start(refresh=True)


__all__ = [
    "bind_cli_live",
    "pause_cli_live_for_external_tty",
    "resume_cli_live_after_external_tty",
    "unbind_cli_live",
]

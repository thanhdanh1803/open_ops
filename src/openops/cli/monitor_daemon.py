"""Background monitoring daemon for OpenOps.

Runs periodic orchestrator invocations for projects with monitoring enabled.
Uses a PID file and log file under the configured data directory.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import signal
import subprocess
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import IO, Any

from openops.config import OpenOpsConfig, get_config
from openops.models import MonitoringPrefs
from openops.storage.base import ProjectStoreBase
from openops.storage.sqlite_store import SqliteProjectStore

logger = logging.getLogger(__name__)

MONITOR_PID_FILENAME = "monitor_daemon.pid"
MONITOR_LOCK_FILENAME = "monitor_invoke.lock"
MONITOR_LOG_FILENAME = "monitor_daemon.log"
POLL_INTERVAL_SECONDS = 15


@dataclass(frozen=True)
class MonitorDaemonPaths:
    """Paths for PID file, invoke lock, and daemon log."""

    pid_file: Path
    lock_file: Path
    log_file: Path


def resolve_daemon_paths(config: OpenOpsConfig) -> MonitorDaemonPaths:
    """Return standard paths under ``config.data_dir``."""
    root = config.data_dir
    return MonitorDaemonPaths(
        pid_file=root / MONITOR_PID_FILENAME,
        lock_file=root / MONITOR_LOCK_FILENAME,
        log_file=root / MONITOR_LOG_FILENAME,
    )


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def read_daemon_pid(paths: MonitorDaemonPaths) -> int | None:
    """Read PID from file if present and valid-looking."""
    if not paths.pid_file.exists():
        return None
    try:
        raw = paths.pid_file.read_text().strip()
        return int(raw)
    except (OSError, ValueError):
        return None


def is_daemon_running(config: OpenOpsConfig) -> bool:
    """Return True if PID file exists and the process is alive."""
    paths = resolve_daemon_paths(config)
    pid = read_daemon_pid(paths)
    if pid is None:
        return False
    if _is_pid_alive(pid):
        return True
    try:
        paths.pid_file.unlink(missing_ok=True)
    except OSError:
        logger.debug("Could not remove stale PID file %s", paths.pid_file)
    return False


def write_daemon_pid(paths: MonitorDaemonPaths) -> None:
    paths.pid_file.parent.mkdir(parents=True, exist_ok=True)
    paths.pid_file.write_text(str(os.getpid()))


def remove_daemon_pid(paths: MonitorDaemonPaths) -> None:
    paths.pid_file.unlink(missing_ok=True)


def append_daemon_log(paths: MonitorDaemonPaths, line: str) -> None:
    """Append one line (with newline) to the daemon log."""
    paths.log_file.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().isoformat(timespec="seconds")
    with paths.log_file.open("a", encoding="utf-8") as f:
        f.write(f"{stamp} {line}\n")


def monitoring_thread_id(store: ProjectStoreBase, project_path: str) -> str:
    """Stable LangGraph thread id for monitoring (separate from chat thread)."""
    path = str(Path(project_path).resolve())
    proj = store.get_project(path)
    if proj:
        return f"monitor:{proj.id}"
    digest = hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]
    return f"monitor:noproject:{digest}"


def extract_assistant_text(result: dict[str, Any]) -> str:
    """Best-effort extraction of assistant text from an invoke result."""
    messages = result.get("messages", [])
    if not messages:
        return ""
    last_message = messages[-1]
    if hasattr(last_message, "content"):
        content = last_message.content
    elif isinstance(last_message, dict):
        content = last_message.get("content", "")
    else:
        content = str(last_message)
    if isinstance(content, list):
        text_parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                text_parts.append(block)
            elif isinstance(block, dict) and "text" in block:
                text_parts.append(str(block["text"]))
        return "\n".join(text_parts) if text_parts else ""
    return content if isinstance(content, str) else str(content)


def interrupt_pending(runtime: Any, thread_id: str) -> bool:
    """True if graph is waiting on human approval (HITL)."""
    try:
        state = runtime.get_state(thread_id)
        if state and getattr(state, "next", None):
            tasks = getattr(state, "tasks", None) or []
            for task in tasks:
                interrupts = getattr(task, "interrupts", None)
                if interrupts:
                    return True
        return False
    except Exception:
        logger.debug("interrupt_pending check failed", exc_info=True)
        return False


@contextmanager
def acquire_invoke_lock(lock_path: Path) -> Generator[IO[str], None, None]:
    """Exclusive non-blocking lock across daemon / overlapping ticks (POSIX flock)."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(lock_path, "w", encoding="utf-8")
    try:
        try:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:
            logger.debug("fcntl not available; skipping cross-process invoke lock")
        except BlockingIOError as e:
            fh.close()
            raise RuntimeError("invoke lock held") from e
        yield fh
    finally:
        try:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except ImportError:
            pass
        fh.close()


def monitoring_tick_is_due(prefs: MonitoringPrefs, now: datetime) -> bool:
    """Whether ``prefs.interval_seconds`` has elapsed since ``last_run_at``."""
    if prefs.last_run_at is None:
        return True
    delta = (now - prefs.last_run_at).total_seconds()
    return delta >= float(prefs.interval_seconds)


def try_start_daemon_subprocess() -> tuple[bool, str]:
    """Spawn ``openops monitor start`` detached if CLI is on PATH."""
    cfg = get_config()
    cfg.ensure_data_dir()
    if is_daemon_running(cfg):
        return False, "Monitoring daemon is already running."

    exe = shutil.which("openops")
    if not exe:
        logger.info("openops CLI not found on PATH; user must start daemon manually")
        return False, (
            "Could not find `openops` on PATH. After enabling monitoring, run "
            "`openops monitor start` in a terminal (or use nohup/systemd)."
        )

    try:
        subprocess.Popen(
            [exe, "monitor", "start"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        logger.info("Spawned monitoring daemon subprocess (%s)", exe)
        return True, "Started the monitoring daemon in the background (`openops monitor start`)."
    except OSError as e:
        logger.warning("Failed to spawn monitoring daemon: %s", e)
        return False, f"Failed to start daemon subprocess: {e}"


def stop_daemon(config: OpenOpsConfig) -> tuple[bool, str]:
    """SIGTERM to PID from file."""
    paths = resolve_daemon_paths(config)
    pid = read_daemon_pid(paths)
    if pid is None:
        return False, "Daemon is not running (no PID file)."
    if not _is_pid_alive(pid):
        remove_daemon_pid(paths)
        return False, "Stale PID file removed; daemon was not running."

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as e:
        return False, f"Could not signal daemon: {e}"

    # Wait briefly for graceful exit
    for _ in range(30):
        time.sleep(0.1)
        if not _is_pid_alive(pid):
            remove_daemon_pid(paths)
            return True, "Monitoring daemon stopped."
    return True, "SIGTERM sent; daemon should exit shortly."


def daemon_status_message(config: OpenOpsConfig) -> str:
    paths = resolve_daemon_paths(config)
    if is_daemon_running(config):
        pid = read_daemon_pid(paths)
        return f"Monitoring daemon running (pid={pid}). Log: {paths.log_file}"
    return "Monitoring daemon is not running."


def tail_daemon_log(config: OpenOpsConfig, lines: int = 200) -> str:
    paths = resolve_daemon_paths(config)
    if not paths.log_file.exists():
        return "(no log file yet)"
    try:
        content = paths.log_file.read_text(encoding="utf-8", errors="replace").splitlines()
        selected = content[-lines:] if len(content) > lines else content
        return "\n".join(selected)
    except OSError as e:
        return f"(could not read log: {e})"


def run_single_tick_for_prefs(config: OpenOpsConfig, prefs: MonitoringPrefs, shared_store: SqliteProjectStore) -> None:
    """One invoke for a single project's monitoring prefs."""
    from openops.agent.monitoring import MonitoringAgentRuntime
    from openops.agent.monitoring_sinks import publish_to_all

    paths = resolve_daemon_paths(config)
    project_path = Path(prefs.project_path)
    if not project_path.is_dir():
        shared_store.touch_monitoring_run(prefs.project_path, last_error=f"project path missing: {project_path}")
        append_daemon_log(paths, f"SKIP missing path {project_path}")
        return

    runtime = None
    try:
        runtime = MonitoringAgentRuntime(
            config=config,
            project_store=shared_store,
            working_directory=project_path,
        )
        thread_id = monitoring_thread_id(shared_store, str(project_path.resolve()))
        logger.info("Monitor tick project=%s thread_id=%s", project_path, thread_id)
        append_daemon_log(paths, f"TICK begin project={project_path}")
        report = runtime.run_tick(str(project_path.resolve()), thread_id)

        if interrupt_pending(runtime, thread_id):
            msg = "tick paused: human approval required (HITL); will retry after interval"
            now = datetime.now()
            shared_store.touch_monitoring_run(prefs.project_path, last_run_at=now, last_error=msg)
            append_daemon_log(paths, f"TICK interrupt project={project_path} ({msg})")
            return

        published_sinks = publish_to_all(report)
        now = datetime.now()
        shared_store.touch_monitoring_run(prefs.project_path, last_run_at=now, last_error="")
        append_daemon_log(
            paths,
            (
                "TICK ok "
                f"project={project_path} status={report.overall_status.value} "
                f"findings={len(report.findings)} sinks={','.join(published_sinks) or '(none)'}"
            ),
        )
    except Exception as e:
        logger.exception("Monitor tick failed for %s", project_path)
        shared_store.touch_monitoring_run(prefs.project_path, last_error=str(e))
        append_daemon_log(paths, f"TICK error project={project_path}: {e}")


def run_daemon_foreground(config: OpenOpsConfig) -> None:
    """Main loop (blocking). Caller must ensure single-instance PID file."""
    from openops.agent.monitoring_sinks import DaemonLogSink, clear_sinks, load_sinks_from_entry_points, register_sink

    config.ensure_data_dir()
    paths = resolve_daemon_paths(config)
    shared_store = SqliteProjectStore(config.projects_db_path)

    stop = False

    def _handle_signal(signum: int, _frame: Any) -> None:
        nonlocal stop
        logger.info("Monitor daemon received signal %s", signum)
        stop = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    clear_sinks()
    register_sink(DaemonLogSink(paths.log_file))
    loaded_sink_names = load_sinks_from_entry_points()
    logger.info("Loaded monitoring sinks: %s", loaded_sink_names or ["daemon-log"])

    append_daemon_log(paths, f"daemon start pid={os.getpid()} sinks={','.join(loaded_sink_names) or 'daemon-log'}")

    try:
        while not stop:
            prefs_list = shared_store.list_enabled_monitoring_prefs()
            now = datetime.now()
            due = [p for p in prefs_list if monitoring_tick_is_due(p, now)]
            if due:
                try:
                    with acquire_invoke_lock(paths.lock_file):
                        # Refresh prefs after acquiring lock
                        refreshed = shared_store.list_enabled_monitoring_prefs()
                        now2 = datetime.now()
                        for prefs in refreshed:
                            if not prefs.enabled:
                                continue
                            if not monitoring_tick_is_due(prefs, now2):
                                continue
                            run_single_tick_for_prefs(config, prefs, shared_store)
                except RuntimeError:
                    logger.debug("Invoke lock busy; will retry next poll")

            for _ in range(POLL_INTERVAL_SECONDS):
                if stop:
                    break
                time.sleep(1)
    finally:
        shared_store.close()
        remove_daemon_pid(paths)
        append_daemon_log(paths, "daemon exit")


def ensure_single_instance_and_write_pid(config: OpenOpsConfig) -> None:
    paths = resolve_daemon_paths(config)
    if paths.pid_file.exists():
        pid = read_daemon_pid(paths)
        if pid is not None and _is_pid_alive(pid):
            raise RuntimeError(f"monitoring daemon already running (pid={pid})")
        paths.pid_file.unlink(missing_ok=True)
    write_daemon_pid(paths)


__all__ = [
    "MonitorDaemonPaths",
    "acquire_invoke_lock",
    "append_daemon_log",
    "daemon_status_message",
    "extract_assistant_text",
    "interrupt_pending",
    "is_daemon_running",
    "monitoring_thread_id",
    "monitoring_tick_is_due",
    "resolve_daemon_paths",
    "run_daemon_foreground",
    "run_single_tick_for_prefs",
    "stop_daemon",
    "tail_daemon_log",
    "try_start_daemon_subprocess",
    "ensure_single_instance_and_write_pid",
]

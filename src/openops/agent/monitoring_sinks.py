"""Pluggable sink layer for publishing monitoring reports.

Third-party packages can register sinks through the `openops.monitoring_sinks`
entry-point group. Each entry point should resolve to an instance or callable
that returns an object implementing `MonitoringReportSink`.
"""

from __future__ import annotations

import logging
from importlib.metadata import entry_points
from pathlib import Path
from typing import Protocol, runtime_checkable

from openops.models import MonitoringReport

logger = logging.getLogger(__name__)


@runtime_checkable
class MonitoringReportSink(Protocol):
    """Contract for report delivery backends."""

    name: str

    def publish(self, report: MonitoringReport) -> None:
        """Publish a monitoring report."""


class DaemonLogSink:
    """Write monitoring reports to the daemon log file."""

    name = "daemon-log"

    def __init__(self, log_path: Path):
        self.log_path = log_path

    def publish(self, report: MonitoringReport) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"{report.generated_at.isoformat(timespec='seconds')} MONITOR_REPORT "
            f"project={report.project_path} status={report.overall_status.value}",
            f"summary: {report.summary}",
        ]
        for finding in report.findings:
            lines.append(
                f"- [{finding.severity.value}] {finding.service_name}: {finding.title} "
                f"(root_cause={finding.root_cause or 'n/a'})"
            )
            if finding.suggested_fix:
                lines.append(f"  fix: {finding.suggested_fix}")
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
            handle.write("\n---\n")


_SINKS: list[MonitoringReportSink] = []


def register_sink(sink: MonitoringReportSink) -> None:
    """Register a report sink."""
    _SINKS.append(sink)
    logger.debug("Registered monitoring sink: %s", sink.name)


def get_registered_sinks() -> list[MonitoringReportSink]:
    """Return registered sinks."""
    return list(_SINKS)


def clear_sinks() -> None:
    """Clear sink registry (mostly for tests)."""
    _SINKS.clear()


def load_sinks_from_entry_points() -> list[str]:
    """Load sink plugins from Python entry points."""
    loaded: list[str] = []
    try:
        eps = entry_points(group="openops.monitoring_sinks")
    except TypeError:
        eps = entry_points().get("openops.monitoring_sinks", [])

    for ep in eps:
        try:
            loaded_obj = ep.load()
            sink = loaded_obj() if callable(loaded_obj) else loaded_obj
            if not isinstance(sink, MonitoringReportSink):
                logger.warning(
                    "Skipping sink entry point '%s': object does not implement MonitoringReportSink", ep.name
                )
                continue
            register_sink(sink)
            loaded.append(ep.name)
        except Exception:
            logger.exception("Failed loading monitoring sink entry point: %s", ep.name)
    return loaded


def publish_to_all(report: MonitoringReport) -> list[str]:
    """Publish report to all registered sinks and return sink names that succeeded."""
    published: list[str] = []
    for sink in _SINKS:
        try:
            sink.publish(report)
            published.append(sink.name)
        except Exception:
            logger.exception("Failed publishing monitoring report to sink '%s'", sink.name)
    return published


__all__ = [
    "MonitoringReportSink",
    "DaemonLogSink",
    "register_sink",
    "get_registered_sinks",
    "clear_sinks",
    "load_sinks_from_entry_points",
    "publish_to_all",
]

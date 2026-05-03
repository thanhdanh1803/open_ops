"""Tests for monitoring report sinks."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from openops.agent.monitoring_sinks import (
    DaemonLogSink,
    clear_sinks,
    get_registered_sinks,
    load_sinks_from_entry_points,
    publish_to_all,
    register_sink,
)
from openops.models import FindingSeverity, MonitoringReport


def _sample_report() -> MonitoringReport:
    return MonitoringReport(
        project_path="/tmp/proj",
        project_id="proj-1",
        generated_at=datetime.now(),
        overall_status=FindingSeverity.WARNING,
        summary="Detected recurring 500 errors",
        findings=[],
        services_checked=["api"],
    )


class TestSinkRegistry:
    def setup_method(self):
        clear_sinks()

    def test_register_and_get_sinks(self):
        sink = MagicMock()
        sink.name = "mock"
        register_sink(sink)
        sinks = get_registered_sinks()
        assert len(sinks) == 1
        assert sinks[0].name == "mock"

    def test_publish_to_all(self):
        sink_a = MagicMock()
        sink_a.name = "a"
        sink_b = MagicMock()
        sink_b.name = "b"
        register_sink(sink_a)
        register_sink(sink_b)

        names = publish_to_all(_sample_report())
        assert names == ["a", "b"]
        sink_a.publish.assert_called_once()
        sink_b.publish.assert_called_once()


class TestDaemonLogSink:
    def test_writes_report_to_log_file(self, tmp_path: Path):
        log_file = tmp_path / "monitor.log"
        sink = DaemonLogSink(log_file)
        sink.publish(_sample_report())

        content = log_file.read_text(encoding="utf-8")
        assert "MONITOR_REPORT" in content
        assert "Detected recurring 500 errors" in content


class TestEntryPointLoader:
    def setup_method(self):
        clear_sinks()

    def test_loads_sink_from_entry_points(self):
        class PluginSink:
            name = "plugin"

            def publish(self, report: MonitoringReport) -> None:
                return

        ep = MagicMock()
        ep.name = "plugin_sink"
        ep.load.return_value = PluginSink

        with patch("openops.agent.monitoring_sinks.entry_points", return_value=[ep]):
            loaded = load_sinks_from_entry_points()

        assert loaded == ["plugin_sink"]
        assert [sink.name for sink in get_registered_sinks()] == ["plugin"]

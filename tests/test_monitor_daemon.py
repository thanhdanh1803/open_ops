"""Tests for monitoring daemon helpers (no live LLM)."""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from openops.cli.monitor_daemon import (
    interrupt_pending,
    monitoring_thread_id,
    monitoring_tick_is_due,
    run_single_tick_for_prefs,
)
from openops.config import OpenOpsConfig
from openops.models import FindingSeverity, MonitoringPrefs, MonitoringReport, Project


class TestMonitoringTickIsDue:
    def test_never_run_is_due(self):
        prefs = MonitoringPrefs(
            project_path="/tmp/x",
            enabled=True,
            interval_seconds=300,
            last_run_at=None,
        )
        assert monitoring_tick_is_due(prefs, datetime.now()) is True

    def test_inside_interval_not_due(self):
        now = datetime(2026, 5, 3, 12, 0, 0)
        prefs = MonitoringPrefs(
            project_path="/tmp/x",
            enabled=True,
            interval_seconds=300,
            last_run_at=now - timedelta(seconds=60),
        )
        assert monitoring_tick_is_due(prefs, now) is False

    def test_after_interval_due(self):
        now = datetime(2026, 5, 3, 12, 0, 0)
        prefs = MonitoringPrefs(
            project_path="/tmp/x",
            enabled=True,
            interval_seconds=300,
            last_run_at=now - timedelta(seconds=400),
        )
        assert monitoring_tick_is_due(prefs, now) is True


class TestMonitoringThreadId:
    def test_uses_project_id_when_known(self):
        store = MagicMock()
        proj = Project(id="proj-abc", path=str(Path("/tmp/foo").resolve()), name="foo")
        store.get_project.return_value = proj

        tid = monitoring_thread_id(store, "/tmp/foo")
        assert tid == "monitor:proj-abc"

    def test_fallback_when_unknown_project(self):
        store = MagicMock()
        store.get_project.return_value = None

        tid = monitoring_thread_id(store, "/nonexistent/path/for/hash")
        assert tid.startswith("monitor:noproject:")


class TestInterruptPending:
    def test_no_interrupt(self):
        runtime = MagicMock()
        state = MagicMock()
        state.next = []
        state.tasks = []
        runtime.get_state.return_value = state
        assert interrupt_pending(runtime, "t1") is False

    def test_interrupt_when_task_has_interrupts(self):
        runtime = MagicMock()
        interrupt_obj = MagicMock()
        task = MagicMock()
        task.interrupts = [interrupt_obj]
        state = MagicMock()
        state.next = ["something"]
        state.tasks = [task]
        runtime.get_state.return_value = state
        assert interrupt_pending(runtime, "t1") is True


class TestRunSingleTick:
    @patch("openops.agent.monitoring_sinks.publish_to_all")
    @patch("openops.agent.monitoring.MonitoringAgentRuntime")
    def test_invokes_monitoring_runtime_and_publishes(
        self,
        mock_runtime_cls,
        mock_publish,
        tmp_path: Path,
    ):
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        cfg = OpenOpsConfig(data_dir=tmp_path, model_provider="anthropic", model_name="claude-sonnet-4-5")
        shared_store = MagicMock()
        shared_store.get_project.return_value = None
        prefs = MonitoringPrefs(
            project_path=str(project_dir),
            enabled=True,
            interval_seconds=300,
        )

        report = MonitoringReport(
            project_path=str(project_dir),
            generated_at=datetime.now(),
            overall_status=FindingSeverity.INFO,
            summary="tick ok",
            findings=[],
            services_checked=["api"],
        )
        runtime = MagicMock()
        runtime.run_tick.return_value = report
        runtime.get_state.return_value = MagicMock(next=[], tasks=[])
        mock_runtime_cls.return_value = runtime
        mock_publish.return_value = ["daemon-log"]

        run_single_tick_for_prefs(cfg, prefs, shared_store)

        mock_runtime_cls.assert_called_once()
        runtime.run_tick.assert_called_once()
        mock_publish.assert_called_once_with(report)
        shared_store.touch_monitoring_run.assert_called()

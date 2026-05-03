"""Tests for dedicated monitoring agent runtime."""

import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from openops.agent.monitoring import MonitoringAgentRuntime, create_monitoring_agent
from openops.config import OpenOpsConfig
from openops.models import (
    Deployment,
    FindingSeverity,
    MonitoringPrefs,
    MonitoringReport,
    Project,
    Service,
)
from openops.storage.base import ProjectStoreBase


class MockProjectStore(ProjectStoreBase):
    def __init__(self):
        self._projects: dict[str, Project] = {}
        self._services: dict[str, Service] = {}
        self._deployments: dict[str, list[Deployment]] = {}
        self._monitoring: dict[str, MonitoringPrefs] = {}

    def upsert_project(self, project: Project) -> None:
        self._projects[project.id] = project

    def get_project(self, path: str) -> Project | None:
        for project in self._projects.values():
            if project.path == path:
                return project
        return None

    def get_project_by_id(self, project_id: str) -> Project | None:
        return self._projects.get(project_id)

    def list_projects(self) -> list[Project]:
        return list(self._projects.values())

    def delete_project(self, project_id: str) -> bool:
        return self._projects.pop(project_id, None) is not None

    def upsert_service(self, service: Service) -> None:
        self._services[service.id] = service

    def get_service(self, service_id: str) -> Service | None:
        return self._services.get(service_id)

    def get_services_for_project(self, project_id: str) -> list[Service]:
        return [service for service in self._services.values() if service.project_id == project_id]

    def delete_service(self, service_id: str) -> bool:
        return self._services.pop(service_id, None) is not None

    def add_deployment(self, deployment: Deployment) -> None:
        self._deployments.setdefault(deployment.service_id, []).append(deployment)

    def get_active_deployment(self, service_id: str) -> Deployment | None:
        return next((d for d in self._deployments.get(service_id, []) if d.status == "active"), None)

    def get_deployments_for_service(self, service_id: str) -> list[Deployment]:
        return self._deployments.get(service_id, [])

    def upsert_monitoring_prefs(self, prefs: MonitoringPrefs) -> None:
        self._monitoring[prefs.project_path] = prefs

    def get_monitoring_prefs(self, project_path: str) -> MonitoringPrefs | None:
        return self._monitoring.get(project_path)

    def list_enabled_monitoring_prefs(self) -> list[MonitoringPrefs]:
        return [p for p in self._monitoring.values() if p.enabled]

    def touch_monitoring_run(self, project_path: str, *, last_run_at=None, last_error: str | None = None) -> None:
        return


def _config() -> OpenOpsConfig:
    env = {"ANTHROPIC_API_KEY": "sk-ant-test-key"}
    with patch.dict(os.environ, env, clear=True):
        return OpenOpsConfig(model_provider="anthropic", model_name="claude-sonnet-4-5")


class TestCreateMonitoringAgent:
    @patch("openops.agent.monitoring.create_deep_agent")
    def test_uses_official_skill_wiring_and_read_only_toolset(self, mock_create_deep_agent):
        mock_create_deep_agent.return_value = MagicMock()
        store = MockProjectStore()
        config = _config()

        create_monitoring_agent(config=config, project_store=store, skill_directories=["/skills/custom"])
        kwargs = mock_create_deep_agent.call_args.kwargs
        tool_names = {tool.name for tool in kwargs["tools"]}

        assert kwargs["name"] == "openops-monitor"
        assert kwargs["skills"] == ["/skills/custom"]
        assert kwargs["interrupt_on"] == {}
        assert kwargs["response_format"] == MonitoringReport

        assert "skills_search" in tool_names
        assert "skills_install" in tool_names
        assert "query_project_knowledge" in tool_names
        assert "list_projects" in tool_names
        assert "record_deployment" not in tool_names
        assert "save_project_knowledge" not in tool_names
        assert "set_project_monitoring" not in tool_names


class TestMonitoringAgentRuntime:
    @patch("openops.agent.monitoring.create_deep_agent")
    def test_run_tick_returns_structured_report(self, mock_create_deep_agent):
        report = MonitoringReport(
            project_path="/tmp/proj",
            project_id="proj-1",
            generated_at=datetime.now(),
            overall_status=FindingSeverity.INFO,
            summary="All good",
            findings=[],
            services_checked=["api"],
        )
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"structured_response": report}
        mock_create_deep_agent.return_value = mock_agent

        runtime = MonitoringAgentRuntime(
            config=_config(),
            project_store=MockProjectStore(),
            working_directory=Path("/tmp"),
            skill_directories=[],
        )
        result = runtime.run_tick("/tmp/proj", "monitor:proj-1")

        assert isinstance(result, MonitoringReport)
        assert result.summary == "All good"
        invoke_args = mock_agent.invoke.call_args[0][0]
        assert "Scheduled monitoring tick" in invoke_args["messages"][0]["content"]

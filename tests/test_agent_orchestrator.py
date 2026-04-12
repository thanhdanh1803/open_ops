"""Tests for OpenOps orchestrator agent."""

import os
from unittest.mock import MagicMock, patch

import pytest

from openops.agent.orchestrator import OrchestratorRuntime, create_orchestrator
from openops.config import OpenOpsConfig
from openops.models import Project, Service
from openops.storage.base import ProjectStoreBase


class MockProjectStore(ProjectStoreBase):
    """Mock implementation of ProjectStoreBase for testing."""

    def __init__(self):
        self._projects: dict[str, Project] = {}
        self._services: dict[str, Service] = {}
        self._deployments = {}

    def upsert_project(self, project: Project) -> None:
        self._projects[project.id] = project

    def get_project(self, path: str) -> Project | None:
        for p in self._projects.values():
            if p.path == path:
                return p
        return None

    def get_project_by_id(self, project_id: str) -> Project | None:
        return self._projects.get(project_id)

    def list_projects(self) -> list[Project]:
        return list(self._projects.values())

    def delete_project(self, project_id: str) -> bool:
        if project_id in self._projects:
            del self._projects[project_id]
            return True
        return False

    def upsert_service(self, service: Service) -> None:
        self._services[service.id] = service

    def get_service(self, service_id: str) -> Service | None:
        return self._services.get(service_id)

    def get_services_for_project(self, project_id: str) -> list[Service]:
        return [s for s in self._services.values() if s.project_id == project_id]

    def delete_service(self, service_id: str) -> bool:
        if service_id in self._services:
            del self._services[service_id]
            return True
        return False

    def add_deployment(self, deployment) -> None:
        if deployment.service_id not in self._deployments:
            self._deployments[deployment.service_id] = []
        self._deployments[deployment.service_id].append(deployment)

    def get_active_deployment(self, service_id: str):
        deployments = self._deployments.get(service_id, [])
        for d in deployments:
            if d.status == "active":
                return d
        return None

    def get_deployments_for_service(self, service_id: str) -> list:
        return self._deployments.get(service_id, [])


@pytest.fixture
def mock_store():
    return MockProjectStore()


@pytest.fixture
def config():
    env = {"ANTHROPIC_API_KEY": "sk-ant-test-key"}
    with patch.dict(os.environ, env, clear=True):
        return OpenOpsConfig(
            model_provider="anthropic",
            model_name="claude-sonnet-4-5",
        )


class TestCreateOrchestrator:
    @patch("openops.agent.orchestrator.create_deep_agent")
    def test_creates_agent_with_correct_config(self, mock_create_agent, config, mock_store):
        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        _agent = create_orchestrator(
            config=config,
            project_store=mock_store,
        )

        assert mock_create_agent.called
        call_kwargs = mock_create_agent.call_args.kwargs

        assert call_kwargs["name"] == "openops-orchestrator"
        assert call_kwargs["model"] == "anthropic:claude-sonnet-4-5"
        assert "system_prompt" in call_kwargs
        assert len(call_kwargs["tools"]) >= 4
        assert len(call_kwargs["subagents"]) == 3

    @patch("openops.agent.orchestrator.create_deep_agent")
    def test_interrupt_on_deploy_tools(self, mock_create_agent, config, mock_store):
        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        create_orchestrator(config=config, project_store=mock_store)

        call_kwargs = mock_create_agent.call_args.kwargs
        interrupt_config = call_kwargs["interrupt_on"]

        assert interrupt_config["vercel_deploy"] is True
        assert interrupt_config["railway_deploy"] is True
        assert interrupt_config["render_deploy"] is True

    @patch("openops.agent.orchestrator.create_deep_agent")
    def test_custom_skill_directories(self, mock_create_agent, config, mock_store):
        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        custom_skills = ["./custom/skills/", "/other/skills/"]
        create_orchestrator(
            config=config,
            project_store=mock_store,
            skill_directories=custom_skills,
        )

        call_kwargs = mock_create_agent.call_args.kwargs
        assert call_kwargs["skills"] == custom_skills

    @patch("openops.agent.orchestrator.create_deep_agent")
    def test_additional_tools(self, mock_create_agent, config, mock_store):
        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        extra_tool = MagicMock()
        create_orchestrator(
            config=config,
            project_store=mock_store,
            additional_tools=[extra_tool],
        )

        call_kwargs = mock_create_agent.call_args.kwargs
        assert extra_tool in call_kwargs["tools"]


class TestOrchestratorRuntime:
    @patch("openops.agent.orchestrator.create_deep_agent")
    def test_runtime_initialization(self, mock_create_agent, config, mock_store):
        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        runtime = OrchestratorRuntime(
            config=config,
            project_store=mock_store,
        )

        assert runtime.config == config
        assert runtime.project_store == mock_store
        assert runtime.agent is not None

    @patch("openops.agent.orchestrator.create_deep_agent")
    def test_invoke_calls_agent(self, mock_create_agent, config, mock_store):
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"messages": []}
        mock_create_agent.return_value = mock_agent

        runtime = OrchestratorRuntime(config=config, project_store=mock_store)
        _result = runtime.invoke("Hello", thread_id="test-thread")

        mock_agent.invoke.assert_called_once()
        call_args = mock_agent.invoke.call_args
        assert call_args[0][0]["messages"][0]["content"] == "Hello"
        assert call_args[1]["config"]["configurable"]["thread_id"] == "test-thread"

    @patch("openops.agent.orchestrator.create_deep_agent")
    def test_get_state(self, mock_create_agent, config, mock_store):
        mock_agent = MagicMock()
        mock_state = MagicMock()
        mock_agent.get_state.return_value = mock_state
        mock_create_agent.return_value = mock_agent

        runtime = OrchestratorRuntime(config=config, project_store=mock_store)
        state = runtime.get_state("test-thread")

        assert state == mock_state
        mock_agent.get_state.assert_called_once()

    @patch("openops.agent.orchestrator.create_deep_agent")
    def test_resume_approve(self, mock_create_agent, config, mock_store):
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"messages": []}
        mock_create_agent.return_value = mock_agent

        runtime = OrchestratorRuntime(config=config, project_store=mock_store)
        runtime.resume(thread_id="test-thread", decision="approve")

        call_args = mock_agent.invoke.call_args
        command = call_args[0][0]
        assert command.resume["decisions"][0]["type"] == "approve"

    @patch("openops.agent.orchestrator.create_deep_agent")
    def test_resume_approve_batched_hitl(self, mock_create_agent, config, mock_store):
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"messages": []}
        mock_create_agent.return_value = mock_agent

        runtime = OrchestratorRuntime(config=config, project_store=mock_store)
        runtime.resume(
            thread_id="test-thread",
            decision="approve",
            hitl_action_count=3,
        )

        command = mock_agent.invoke.call_args[0][0]
        assert len(command.resume["decisions"]) == 3
        assert all(d["type"] == "approve" for d in command.resume["decisions"])

    @patch("openops.agent.orchestrator.create_deep_agent")
    def test_resume_reject_with_message(self, mock_create_agent, config, mock_store):
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"messages": []}
        mock_create_agent.return_value = mock_agent

        runtime = OrchestratorRuntime(config=config, project_store=mock_store)
        runtime.resume(
            thread_id="test-thread",
            decision="reject",
            message="Not ready yet",
        )

        call_args = mock_agent.invoke.call_args
        command = call_args[0][0]
        assert command.resume["decisions"][0]["type"] == "reject"
        assert command.resume["decisions"][0]["message"] == "Not ready yet"

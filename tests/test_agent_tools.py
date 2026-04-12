"""Tests for OpenOps custom tools."""

from datetime import datetime

import pytest

from openops.agent.tools import create_project_knowledge_tools
from openops.models import Deployment, Project, Service
from openops.storage.base import ProjectStoreBase


class MockProjectStore(ProjectStoreBase):
    """Mock implementation of ProjectStoreBase for testing."""

    def __init__(self):
        self._projects: dict[str, Project] = {}
        self._services: dict[str, Service] = {}
        self._deployments: dict[str, list[Deployment]] = {}

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

    def add_deployment(self, deployment: Deployment) -> None:
        if deployment.service_id not in self._deployments:
            self._deployments[deployment.service_id] = []
        for d in self._deployments[deployment.service_id]:
            if d.status == "active":
                d.status = "superseded"
        self._deployments[deployment.service_id].append(deployment)

    def get_active_deployment(self, service_id: str) -> Deployment | None:
        if service_id not in self._deployments:
            return None
        for d in self._deployments[service_id]:
            if d.status == "active":
                return d
        return None

    def get_deployments_for_service(self, service_id: str) -> list[Deployment]:
        return self._deployments.get(service_id, [])


@pytest.fixture
def mock_store():
    return MockProjectStore()


@pytest.fixture
def tools(mock_store):
    return create_project_knowledge_tools(mock_store)


class TestQueryProjectKnowledge:
    def test_query_nonexistent_project(self, tools):
        query_tool = tools[0]
        result = query_tool.invoke({"project_path": "/nonexistent/project"})

        assert result["found"] is False
        assert result["project"] is None
        assert result["services"] == []

    def test_query_existing_project(self, tools, mock_store):
        project = Project(
            id="proj-123",
            path="/test/project",
            name="Test Project",
            description="A test project",
            keypoints=["Uses Python", "FastAPI backend"],
            analyzed_at=datetime.now(),
        )
        mock_store.upsert_project(project)

        service = Service(
            id="svc-456",
            project_id="proj-123",
            name="api",
            path="./api",
            type="backend",
            framework="FastAPI",
            language="Python",
        )
        mock_store.upsert_service(service)

        query_tool = tools[0]
        result = query_tool.invoke({"project_path": "/test/project"})

        assert result["found"] is True
        assert result["project"]["name"] == "Test Project"
        assert result["project"]["description"] == "A test project"
        assert len(result["services"]) == 1
        assert result["services"][0]["service"]["name"] == "api"
        assert result["services"][0]["service"]["framework"] == "FastAPI"


class TestSaveProjectKnowledge:
    def test_save_new_project(self, tools, mock_store):
        save_tool = tools[1]
        result = save_tool.invoke(
            {
                "project_path": "/new/project",
                "project_name": "New Project",
                "description": "A brand new project",
                "keypoints": ["React frontend", "Node.js backend"],
                "services": [
                    {
                        "name": "frontend",
                        "path": "./frontend",
                        "type": "frontend",
                        "framework": "React",
                        "language": "TypeScript",
                    },
                    {
                        "name": "backend",
                        "path": "./backend",
                        "type": "backend",
                        "framework": "Express",
                        "language": "JavaScript",
                    },
                ],
            }
        )

        assert result["success"] is True
        assert result["project_id"] is not None
        assert len(result["service_ids"]) == 2

        project = mock_store.get_project("/new/project")
        assert project is not None
        assert project.name == "New Project"

        services = mock_store.get_services_for_project(result["project_id"])
        assert len(services) == 2

    def test_update_existing_project(self, tools, mock_store):
        project = Project(
            id="existing-proj",
            path="/existing/project",
            name="Old Name",
            description="Old description",
        )
        mock_store.upsert_project(project)

        save_tool = tools[1]
        result = save_tool.invoke(
            {
                "project_path": "/existing/project",
                "project_name": "Updated Name",
                "description": "Updated description",
                "keypoints": ["New keypoint"],
                "services": [],
            }
        )

        assert result["success"] is True
        assert result["project_id"] == "existing-proj"

        updated = mock_store.get_project("/existing/project")
        assert updated.name == "Updated Name"
        assert updated.description == "Updated description"


class TestRecordDeployment:
    def test_record_deployment_success(self, tools, mock_store):
        service = Service(
            id="svc-123",
            project_id="proj-456",
            name="api",
            path="./api",
        )
        mock_store.upsert_service(service)

        record_tool = tools[2]
        result = record_tool.invoke(
            {
                "service_id": "svc-123",
                "platform": "vercel",
                "url": "https://api.vercel.app",
                "dashboard_url": "https://vercel.com/dashboard",
            }
        )

        assert result["success"] is True
        assert result["deployment_id"] is not None
        assert result["url"] == "https://api.vercel.app"

        deployment = mock_store.get_active_deployment("svc-123")
        assert deployment is not None
        assert deployment.platform == "vercel"

    def test_record_deployment_nonexistent_service(self, tools):
        record_tool = tools[2]
        result = record_tool.invoke(
            {
                "service_id": "nonexistent",
                "platform": "vercel",
            }
        )

        assert result["success"] is False
        assert "not found" in result["message"]


class TestListProjects:
    def test_list_empty(self, tools):
        list_tool = tools[3]
        result = list_tool.invoke({})

        assert result["count"] == 0
        assert result["projects"] == []

    def test_list_multiple_projects(self, tools, mock_store):
        for i in range(3):
            project = Project(
                id=f"proj-{i}",
                path=f"/project/{i}",
                name=f"Project {i}",
                analyzed_at=datetime.now(),
            )
            mock_store.upsert_project(project)

        list_tool = tools[3]
        result = list_tool.invoke({})

        assert result["count"] == 3
        assert len(result["projects"]) == 3

"""Tests for the base storage interface."""

from datetime import datetime
from pathlib import Path

import pytest

from openops.models import Deployment, MonitoringPrefs, Project, Service
from openops.storage.base import ProjectStoreBase


class InMemoryStore(ProjectStoreBase):
    """In-memory implementation for testing."""

    def __init__(self):
        self._projects: dict[str, Project] = {}
        self._services: dict[str, Service] = {}
        self._deployments: dict[str, Deployment] = {}
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
        for d in self._deployments.values():
            if d.service_id == deployment.service_id and d.status == "active":
                d.status = "superseded"
        self._deployments[deployment.id] = deployment

    def get_active_deployment(self, service_id: str) -> Deployment | None:
        for deployment in self._deployments.values():
            if deployment.service_id == service_id and deployment.status == "active":
                return deployment
        return None

    def get_deployments_for_service(self, service_id: str) -> list[Deployment]:
        deployments = [d for d in self._deployments.values() if d.service_id == service_id]
        return sorted(deployments, key=lambda d: d.deployed_at or datetime.min, reverse=True)

    def upsert_monitoring_prefs(self, prefs: MonitoringPrefs) -> None:
        path = str(Path(prefs.project_path).resolve())
        incoming = prefs.model_copy(update={"project_path": path})
        if existing := self._monitoring.get(path):
            incoming.last_run_at = existing.last_run_at
            incoming.last_error = existing.last_error
        self._monitoring[path] = incoming

    def get_monitoring_prefs(self, project_path: str) -> MonitoringPrefs | None:
        path = str(Path(project_path).resolve())
        return self._monitoring.get(path)

    def list_enabled_monitoring_prefs(self) -> list[MonitoringPrefs]:
        return [p for p in self._monitoring.values() if p.enabled]

    def touch_monitoring_run(
        self,
        project_path: str,
        *,
        last_run_at=None,
        last_error: str | None = None,
    ) -> None:
        path = str(Path(project_path).resolve())
        existing = self._monitoring.get(path)
        if not existing:
            return
        kwargs = {}
        if last_run_at is not None:
            kwargs["last_run_at"] = last_run_at
        if last_error is not None:
            kwargs["last_error"] = last_error
        self._monitoring[path] = existing.model_copy(update=kwargs)


@pytest.fixture
def store():
    return InMemoryStore()


@pytest.fixture
def sample_project():
    return Project(
        id="proj-123",
        path="/home/user/myproject",
        name="myproject",
        description="A test project",
    )


@pytest.fixture
def sample_service(sample_project):
    return Service(
        id="svc-123",
        project_id=sample_project.id,
        name="frontend",
        path="frontend",
        type="frontend",
        framework="Next.js",
    )


class TestProjectOperations:
    def test_upsert_and_get_project(self, store, sample_project):
        store.upsert_project(sample_project)
        retrieved = store.get_project(sample_project.path)

        assert retrieved is not None
        assert retrieved.id == sample_project.id
        assert retrieved.name == sample_project.name

    def test_get_project_not_found(self, store):
        result = store.get_project("/nonexistent")
        assert result is None

    def test_get_project_by_id(self, store, sample_project):
        store.upsert_project(sample_project)
        retrieved = store.get_project_by_id(sample_project.id)

        assert retrieved is not None
        assert retrieved.path == sample_project.path

    def test_list_projects(self, store, sample_project):
        store.upsert_project(sample_project)
        another = Project(id="proj-456", path="/other/project", name="other")
        store.upsert_project(another)

        projects = store.list_projects()
        assert len(projects) == 2

    def test_delete_project(self, store, sample_project):
        store.upsert_project(sample_project)
        assert store.delete_project(sample_project.id) is True
        assert store.get_project_by_id(sample_project.id) is None

    def test_delete_nonexistent_project(self, store):
        assert store.delete_project("nonexistent") is False


class TestServiceOperations:
    def test_upsert_and_get_service(self, store, sample_service):
        store.upsert_service(sample_service)
        retrieved = store.get_service(sample_service.id)

        assert retrieved is not None
        assert retrieved.name == sample_service.name
        assert retrieved.framework == "Next.js"

    def test_get_services_for_project(self, store, sample_project, sample_service):
        store.upsert_project(sample_project)
        store.upsert_service(sample_service)

        backend = Service(
            id="svc-456",
            project_id=sample_project.id,
            name="backend",
            path="backend",
            type="backend",
        )
        store.upsert_service(backend)

        services = store.get_services_for_project(sample_project.id)
        assert len(services) == 2

    def test_delete_service(self, store, sample_service):
        store.upsert_service(sample_service)
        assert store.delete_service(sample_service.id) is True
        assert store.get_service(sample_service.id) is None


class TestDeploymentOperations:
    def test_add_and_get_deployment(self, store, sample_service):
        deployment = Deployment(
            id="deploy-123",
            service_id=sample_service.id,
            platform="vercel",
            url="https://myapp.vercel.app",
            deployed_at=datetime.now(),
            status="active",
        )
        store.add_deployment(deployment)

        retrieved = store.get_active_deployment(sample_service.id)
        assert retrieved is not None
        assert retrieved.url == "https://myapp.vercel.app"

    def test_new_deployment_supersedes_old(self, store, sample_service):
        old = Deployment(
            id="deploy-1",
            service_id=sample_service.id,
            platform="vercel",
            deployed_at=datetime.now(),
            status="active",
        )
        store.add_deployment(old)

        new = Deployment(
            id="deploy-2",
            service_id=sample_service.id,
            platform="vercel",
            deployed_at=datetime.now(),
            status="active",
        )
        store.add_deployment(new)

        active = store.get_active_deployment(sample_service.id)
        assert active.id == "deploy-2"

        all_deployments = store.get_deployments_for_service(sample_service.id)
        superseded = [d for d in all_deployments if d.id == "deploy-1"][0]
        assert superseded.status == "superseded"


class TestProjectSummary:
    def test_get_project_summary(self, store, sample_project, sample_service):
        store.upsert_project(sample_project)
        store.upsert_service(sample_service)

        deployment = Deployment(
            id="deploy-123",
            service_id=sample_service.id,
            platform="vercel",
            url="https://myapp.vercel.app",
            deployed_at=datetime.now(),
            status="active",
        )
        store.add_deployment(deployment)

        summary = store.get_project_summary(sample_project.path)

        assert summary is not None
        assert summary["project"].name == "myproject"
        assert len(summary["services"]) == 1
        assert summary["services"][0]["service"].name == "frontend"
        assert summary["services"][0]["deployment"].url == "https://myapp.vercel.app"

    def test_get_project_summary_not_found(self, store):
        summary = store.get_project_summary("/nonexistent")
        assert summary is None

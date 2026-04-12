"""Tests for SqliteProjectStore."""

from datetime import datetime

import pytest

from openops.models import Deployment, Project, Service
from openops.storage.sqlite_store import SqliteProjectStore


@pytest.fixture
def store():
    """Create an in-memory SQLite store for testing."""
    store = SqliteProjectStore(":memory:")
    yield store
    store.close()


@pytest.fixture
def sample_project():
    """Create a sample project for testing."""
    return Project(
        id="proj-123",
        path="/home/user/myproject",
        name="myproject",
        description="A test project",
        keypoints=["Uses Next.js", "Has API routes"],
        analyzed_at=datetime(2024, 1, 15, 10, 30, 0),
        updated_at=datetime(2024, 1, 15, 10, 30, 0),
    )


@pytest.fixture
def sample_service(sample_project):
    """Create a sample service for testing."""
    return Service(
        id="svc-frontend",
        project_id=sample_project.id,
        name="frontend",
        path="frontend",
        description="Next.js frontend application",
        type="frontend",
        framework="Next.js",
        language="TypeScript",
        version="14.0.0",
        entry_point="src/app/page.tsx",
        build_command="npm run build",
        start_command="npm start",
        port=3000,
        env_vars=["NEXT_PUBLIC_API_URL", "NEXT_PUBLIC_SITE_URL"],
        dependencies=[],
        keypoints=["Uses App Router", "Has server components"],
    )


@pytest.fixture
def sample_deployment(sample_service):
    """Create a sample deployment for testing."""
    return Deployment(
        id="deploy-123",
        service_id=sample_service.id,
        platform="vercel",
        url="https://myproject.vercel.app",
        dashboard_url="https://vercel.com/myteam/myproject",
        deployed_at=datetime(2024, 1, 15, 11, 0, 0),
        config={"framework": "nextjs", "nodeVersion": "20.x"},
        status="active",
    )


class TestProjectOperations:
    def test_upsert_and_get_project(self, store, sample_project):
        store.upsert_project(sample_project)

        retrieved = store.get_project(sample_project.path)

        assert retrieved is not None
        assert retrieved.id == sample_project.id
        assert retrieved.path == sample_project.path
        assert retrieved.name == sample_project.name
        assert retrieved.description == sample_project.description
        assert retrieved.keypoints == sample_project.keypoints
        assert retrieved.analyzed_at == sample_project.analyzed_at

    def test_get_project_not_found(self, store):
        result = store.get_project("/nonexistent/path")
        assert result is None

    def test_get_project_by_id(self, store, sample_project):
        store.upsert_project(sample_project)

        retrieved = store.get_project_by_id(sample_project.id)

        assert retrieved is not None
        assert retrieved.id == sample_project.id

    def test_get_project_by_id_not_found(self, store):
        result = store.get_project_by_id("nonexistent-id")
        assert result is None

    def test_list_projects(self, store, sample_project):
        project2 = Project(
            id="proj-456",
            path="/home/user/another",
            name="another",
            updated_at=datetime(2024, 1, 16, 10, 0, 0),
        )

        store.upsert_project(sample_project)
        store.upsert_project(project2)

        projects = store.list_projects()

        assert len(projects) == 2
        assert projects[0].id == project2.id
        assert projects[1].id == sample_project.id

    def test_list_projects_empty(self, store):
        projects = store.list_projects()
        assert projects == []

    def test_upsert_project_update(self, store, sample_project):
        store.upsert_project(sample_project)

        updated_project = Project(
            id=sample_project.id,
            path=sample_project.path,
            name="updated-name",
            description="Updated description",
            keypoints=["New keypoint"],
            analyzed_at=sample_project.analyzed_at,
            updated_at=datetime(2024, 1, 16, 12, 0, 0),
        )
        store.upsert_project(updated_project)

        retrieved = store.get_project(sample_project.path)

        assert retrieved.name == "updated-name"
        assert retrieved.description == "Updated description"
        assert retrieved.keypoints == ["New keypoint"]

    def test_delete_project(self, store, sample_project):
        store.upsert_project(sample_project)

        result = store.delete_project(sample_project.id)

        assert result is True
        assert store.get_project(sample_project.path) is None

    def test_delete_project_not_found(self, store):
        result = store.delete_project("nonexistent-id")
        assert result is False

    def test_delete_project_cascades_to_services(
        self, store, sample_project, sample_service
    ):
        store.upsert_project(sample_project)
        store.upsert_service(sample_service)

        store.delete_project(sample_project.id)

        assert store.get_service(sample_service.id) is None


class TestServiceOperations:
    def test_upsert_and_get_service(self, store, sample_project, sample_service):
        store.upsert_project(sample_project)
        store.upsert_service(sample_service)

        retrieved = store.get_service(sample_service.id)

        assert retrieved is not None
        assert retrieved.id == sample_service.id
        assert retrieved.project_id == sample_service.project_id
        assert retrieved.name == sample_service.name
        assert retrieved.framework == sample_service.framework
        assert retrieved.env_vars == sample_service.env_vars
        assert retrieved.keypoints == sample_service.keypoints

    def test_get_service_not_found(self, store):
        result = store.get_service("nonexistent-id")
        assert result is None

    def test_get_services_for_project(self, store, sample_project, sample_service):
        backend_service = Service(
            id="svc-backend",
            project_id=sample_project.id,
            name="backend",
            path="backend",
            type="backend",
            framework="FastAPI",
            language="Python",
        )

        store.upsert_project(sample_project)
        store.upsert_service(sample_service)
        store.upsert_service(backend_service)

        services = store.get_services_for_project(sample_project.id)

        assert len(services) == 2
        names = [s.name for s in services]
        assert "frontend" in names
        assert "backend" in names

    def test_get_services_for_project_empty(self, store, sample_project):
        store.upsert_project(sample_project)

        services = store.get_services_for_project(sample_project.id)

        assert services == []

    def test_upsert_service_update(self, store, sample_project, sample_service):
        store.upsert_project(sample_project)
        store.upsert_service(sample_service)

        updated_service = Service(
            id=sample_service.id,
            project_id=sample_project.id,
            name="frontend-updated",
            path="frontend",
            framework="Remix",
            language="TypeScript",
            port=4000,
        )
        store.upsert_service(updated_service)

        retrieved = store.get_service(sample_service.id)

        assert retrieved.name == "frontend-updated"
        assert retrieved.framework == "Remix"
        assert retrieved.port == 4000

    def test_delete_service(self, store, sample_project, sample_service):
        store.upsert_project(sample_project)
        store.upsert_service(sample_service)

        result = store.delete_service(sample_service.id)

        assert result is True
        assert store.get_service(sample_service.id) is None

    def test_delete_service_not_found(self, store):
        result = store.delete_service("nonexistent-id")
        assert result is False


class TestServiceDependencies:
    def test_service_dependencies_stored_and_synced(self, store, sample_project):
        store.upsert_project(sample_project)

        database_service = Service(
            id="svc-db",
            project_id=sample_project.id,
            name="database",
            path="db",
            type="database",
            dependencies=[],
        )
        backend_service = Service(
            id="svc-backend",
            project_id=sample_project.id,
            name="backend",
            path="backend",
            type="backend",
            dependencies=["svc-db"],
        )
        frontend_service = Service(
            id="svc-frontend",
            project_id=sample_project.id,
            name="frontend",
            path="frontend",
            type="frontend",
            dependencies=["svc-backend"],
        )

        store.upsert_service(database_service)
        store.upsert_service(backend_service)
        store.upsert_service(frontend_service)

        retrieved_backend = store.get_service("svc-backend")
        assert retrieved_backend.dependencies == ["svc-db"]

        retrieved_frontend = store.get_service("svc-frontend")
        assert retrieved_frontend.dependencies == ["svc-backend"]

    def test_get_dependent_services(self, store, sample_project):
        store.upsert_project(sample_project)

        database_service = Service(
            id="svc-db",
            project_id=sample_project.id,
            name="database",
            path="db",
            type="database",
            dependencies=[],
        )
        backend_service = Service(
            id="svc-backend",
            project_id=sample_project.id,
            name="backend",
            path="backend",
            type="backend",
            dependencies=["svc-db"],
        )
        worker_service = Service(
            id="svc-worker",
            project_id=sample_project.id,
            name="worker",
            path="worker",
            type="worker",
            dependencies=["svc-db"],
        )

        store.upsert_service(database_service)
        store.upsert_service(backend_service)
        store.upsert_service(worker_service)

        dependents = store.get_dependent_services("svc-db")

        assert len(dependents) == 2
        dependent_ids = [s.id for s in dependents]
        assert "svc-backend" in dependent_ids
        assert "svc-worker" in dependent_ids

    def test_get_dependent_services_none(self, store, sample_project):
        store.upsert_project(sample_project)

        service = Service(
            id="svc-standalone",
            project_id=sample_project.id,
            name="standalone",
            path="standalone",
            dependencies=[],
        )
        store.upsert_service(service)

        dependents = store.get_dependent_services("svc-standalone")

        assert dependents == []

    def test_update_service_dependencies(self, store, sample_project):
        store.upsert_project(sample_project)

        svc_a = Service(
            id="svc-a",
            project_id=sample_project.id,
            name="svc-a",
            path="a",
            dependencies=[],
        )
        svc_b = Service(
            id="svc-b",
            project_id=sample_project.id,
            name="svc-b",
            path="b",
            dependencies=[],
        )
        svc_c = Service(
            id="svc-c",
            project_id=sample_project.id,
            name="svc-c",
            path="c",
            dependencies=["svc-a"],
        )

        store.upsert_service(svc_a)
        store.upsert_service(svc_b)
        store.upsert_service(svc_c)

        assert len(store.get_dependent_services("svc-a")) == 1
        assert len(store.get_dependent_services("svc-b")) == 0

        svc_c_updated = Service(
            id="svc-c",
            project_id=sample_project.id,
            name="svc-c",
            path="c",
            dependencies=["svc-b"],
        )
        store.upsert_service(svc_c_updated)

        assert len(store.get_dependent_services("svc-a")) == 0
        assert len(store.get_dependent_services("svc-b")) == 1


class TestDeploymentOperations:
    def test_add_and_get_deployment(
        self, store, sample_project, sample_service, sample_deployment
    ):
        store.upsert_project(sample_project)
        store.upsert_service(sample_service)
        store.add_deployment(sample_deployment)

        active = store.get_active_deployment(sample_service.id)

        assert active is not None
        assert active.id == sample_deployment.id
        assert active.platform == "vercel"
        assert active.url == sample_deployment.url
        assert active.config == sample_deployment.config

    def test_get_active_deployment_not_found(self, store, sample_project, sample_service):
        store.upsert_project(sample_project)
        store.upsert_service(sample_service)

        result = store.get_active_deployment(sample_service.id)

        assert result is None

    def test_new_deployment_supersedes_old(
        self, store, sample_project, sample_service, sample_deployment
    ):
        store.upsert_project(sample_project)
        store.upsert_service(sample_service)
        store.add_deployment(sample_deployment)

        new_deployment = Deployment(
            id="deploy-456",
            service_id=sample_service.id,
            platform="vercel",
            url="https://myproject-v2.vercel.app",
            deployed_at=datetime(2024, 1, 16, 12, 0, 0),
            status="active",
        )
        store.add_deployment(new_deployment)

        active = store.get_active_deployment(sample_service.id)
        assert active.id == "deploy-456"
        assert active.url == "https://myproject-v2.vercel.app"

        all_deployments = store.get_deployments_for_service(sample_service.id)
        assert len(all_deployments) == 2

        old_deployment = next(d for d in all_deployments if d.id == "deploy-123")
        assert old_deployment.status == "superseded"

    def test_get_deployments_for_service(
        self, store, sample_project, sample_service, sample_deployment
    ):
        store.upsert_project(sample_project)
        store.upsert_service(sample_service)

        deploy1 = Deployment(
            id="deploy-1",
            service_id=sample_service.id,
            platform="vercel",
            deployed_at=datetime(2024, 1, 10, 10, 0, 0),
            status="superseded",
        )
        deploy2 = Deployment(
            id="deploy-2",
            service_id=sample_service.id,
            platform="vercel",
            deployed_at=datetime(2024, 1, 15, 10, 0, 0),
            status="active",
        )

        store.add_deployment(deploy1)
        store.add_deployment(deploy2)

        deployments = store.get_deployments_for_service(sample_service.id)

        assert len(deployments) == 2
        assert deployments[0].id == "deploy-2"
        assert deployments[1].id == "deploy-1"

    def test_get_deployments_for_service_empty(
        self, store, sample_project, sample_service
    ):
        store.upsert_project(sample_project)
        store.upsert_service(sample_service)

        deployments = store.get_deployments_for_service(sample_service.id)

        assert deployments == []

    def test_delete_service_cascades_to_deployments(
        self, store, sample_project, sample_service, sample_deployment
    ):
        store.upsert_project(sample_project)
        store.upsert_service(sample_service)
        store.add_deployment(sample_deployment)

        store.delete_service(sample_service.id)

        deployments = store.get_deployments_for_service(sample_service.id)
        assert deployments == []


class TestProjectSummary:
    def test_get_project_summary(
        self, store, sample_project, sample_service, sample_deployment
    ):
        store.upsert_project(sample_project)
        store.upsert_service(sample_service)
        store.add_deployment(sample_deployment)

        summary = store.get_project_summary(sample_project.path)

        assert summary is not None
        assert summary["project"].id == sample_project.id
        assert len(summary["services"]) == 1
        assert summary["services"][0]["service"].id == sample_service.id
        assert summary["services"][0]["deployment"].id == sample_deployment.id

    def test_get_project_summary_not_found(self, store):
        summary = store.get_project_summary("/nonexistent/path")
        assert summary is None

    def test_get_project_summary_no_deployments(
        self, store, sample_project, sample_service
    ):
        store.upsert_project(sample_project)
        store.upsert_service(sample_service)

        summary = store.get_project_summary(sample_project.path)

        assert summary is not None
        assert summary["services"][0]["deployment"] is None

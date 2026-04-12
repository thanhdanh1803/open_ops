"""Tests for OpenOps data models."""

from datetime import datetime

from openops.models import (
    Deployment,
    MonitoringConfig,
    Project,
    RiskLevel,
    Service,
)


class TestRiskLevel:
    def test_risk_level_values(self):
        assert RiskLevel.READ.value == "read"
        assert RiskLevel.WRITE.value == "write"
        assert RiskLevel.DESTRUCTIVE.value == "destructive"

    def test_risk_level_from_string(self):
        assert RiskLevel("read") == RiskLevel.READ
        assert RiskLevel("write") == RiskLevel.WRITE
        assert RiskLevel("destructive") == RiskLevel.DESTRUCTIVE


class TestProject:
    def test_project_creation(self):
        project = Project(
            id="proj-123",
            path="/home/user/myproject",
            name="myproject",
            description="A test project",
            keypoints=["Uses Next.js", "Has API routes"],
        )
        assert project.id == "proj-123"
        assert project.path == "/home/user/myproject"
        assert project.name == "myproject"
        assert len(project.keypoints) == 2

    def test_project_defaults(self):
        project = Project(
            id="proj-123",
            path="/home/user/myproject",
            name="myproject",
        )
        assert project.description == ""
        assert project.keypoints == []
        assert project.analyzed_at is None
        assert project.updated_at is None


class TestService:
    def test_service_creation(self):
        service = Service(
            id="svc-123",
            project_id="proj-123",
            name="frontend",
            path="frontend",
            type="frontend",
            framework="Next.js",
            language="TypeScript",
        )
        assert service.id == "svc-123"
        assert service.project_id == "proj-123"
        assert service.framework == "Next.js"

    def test_service_defaults(self):
        service = Service(
            id="svc-123",
            project_id="proj-123",
            name="api",
            path="backend",
        )
        assert service.env_vars == []
        assert service.dependencies == []
        assert service.keypoints == []
        assert service.port is None


class TestDeployment:
    def test_deployment_creation(self):
        now = datetime.now()
        deployment = Deployment(
            id="deploy-123",
            service_id="svc-123",
            platform="vercel",
            url="https://myapp.vercel.app",
            deployed_at=now,
            status="active",
        )
        assert deployment.platform == "vercel"
        assert deployment.status == "active"
        assert deployment.deployed_at == now

    def test_deployment_defaults(self):
        deployment = Deployment(
            id="deploy-123",
            service_id="svc-123",
            platform="railway",
        )
        assert deployment.status == "active"
        assert deployment.config == {}
        assert deployment.url is None


class TestMonitoringConfig:
    def test_monitoring_config_creation(self):
        config = MonitoringConfig(
            id="mon-123",
            deployment_id="deploy-123",
            health_check_url="https://myapp.com/health",
            interval_seconds=30,
            alert_channels=["slack-channel"],
        )
        assert config.interval_seconds == 30
        assert config.enabled is True

    def test_monitoring_config_defaults(self):
        config = MonitoringConfig(
            id="mon-123",
            deployment_id="deploy-123",
            health_check_url="https://myapp.com/health",
        )
        assert config.interval_seconds == 60
        assert config.alert_channels == []
        assert config.thresholds == {}
        assert config.enabled is True

"""Tests for OpenOps data models."""

from datetime import datetime

import pytest

from openops.models import (
    Deployment,
    MonitoringConfig,
    Project,
    RiskLevel,
    Service,
    SkillMetadata,
    SkillResult,
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


class TestSkillResult:
    def test_success_result(self):
        result = SkillResult(
            success=True,
            message="Deployment successful",
            data={"url": "https://example.com"},
        )
        assert result.success is True
        assert result.message == "Deployment successful"
        assert result.data == {"url": "https://example.com"}
        assert result.error is None

    def test_failure_result(self):
        result = SkillResult(
            success=False,
            message="Deployment failed",
            error="INVALID_TOKEN",
        )
        assert result.success is False
        assert result.error == "INVALID_TOKEN"
        assert result.data is None


class TestSkillMetadata:
    def test_skill_metadata_creation(self):
        metadata = SkillMetadata(
            name="vercel-deploy",
            description="Deploy applications to Vercel",
            version="1.0.0",
            risk_level=RiskLevel.WRITE,
            tags=["deployment", "frontend", "vercel"],
            requires_credentials=["VERCEL_TOKEN"],
            provides_tools=["vercel_deploy", "vercel_list_projects"],
        )
        assert metadata.name == "vercel-deploy"
        assert metadata.risk_level == RiskLevel.WRITE
        assert "deployment" in metadata.tags
        assert "VERCEL_TOKEN" in metadata.requires_credentials
        assert len(metadata.provides_tools) == 2

    def test_skill_metadata_defaults(self):
        metadata = SkillMetadata(
            name="simple-skill",
            description="A simple skill",
            risk_level=RiskLevel.READ,
        )
        assert metadata.version == "1.0.0"
        assert metadata.tags == []
        assert metadata.requires_credentials == []
        assert metadata.provides_tools == []

    def test_skill_metadata_json_serialization(self):
        metadata = SkillMetadata(
            name="test-skill",
            description="Test skill",
            risk_level=RiskLevel.WRITE,
            tags=["test"],
        )
        json_data = metadata.model_dump_json()
        assert "test-skill" in json_data
        assert "write" in json_data


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

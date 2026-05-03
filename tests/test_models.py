"""Tests for OpenOps data models."""

from datetime import datetime

import pytest

from openops.models import (
    Deployment,
    FindingSeverity,
    MonitoringConfig,
    MonitoringFinding,
    MonitoringPrefs,
    MonitoringReport,
    Project,
    RiskLevel,
    Service,
)


class TestMonitoringPrefs:
    def test_defaults(self):
        p = MonitoringPrefs(project_path="/abs/proj")
        assert p.enabled is False
        assert p.interval_seconds == 300

    def test_interval_minimum_validation(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            MonitoringPrefs(project_path="/abs/proj", interval_seconds=30)


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


class TestMonitoringReportModels:
    def test_finding_creation(self):
        finding = MonitoringFinding(
            service_name="api",
            service_id="svc-1",
            severity=FindingSeverity.CRITICAL,
            title="Database connection failures",
            evidence="psycopg2.OperationalError timeout",
            root_cause="Primary database unreachable from app network",
            suggested_fix="Verify DB health and network/security-group rules",
            related_services=["worker", "cron"],
        )
        assert finding.severity == FindingSeverity.CRITICAL
        assert finding.related_services == ["worker", "cron"]

    def test_report_round_trip(self):
        report = MonitoringReport(
            project_path="/tmp/project",
            project_id="proj-1",
            generated_at=datetime.now(),
            overall_status=FindingSeverity.WARNING,
            summary="Intermittent upstream timeouts observed.",
            findings=[
                MonitoringFinding(
                    service_name="api",
                    severity=FindingSeverity.WARNING,
                    title="Timeout spike",
                    evidence="504 responses increased in last 10m",
                )
            ],
            services_checked=["api", "worker"],
        )
        payload = report.model_dump()
        loaded = MonitoringReport.model_validate(payload)
        assert loaded.project_path == "/tmp/project"
        assert loaded.findings[0].title == "Timeout spike"
        assert loaded.overall_status == FindingSeverity.WARNING

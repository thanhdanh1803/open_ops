"""Shared data models for OpenOps."""

import logging
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):  # noqa: UP042
    """Risk level for operations.

    Used for HITL approval decisions.
    """

    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


class Project(BaseModel):
    """A project being managed by OpenOps."""

    id: str = Field(description="UUID for the project")
    path: str = Field(description="Absolute path to the project")
    name: str = Field(description="Project name")
    description: str = Field(default="", description="AI-generated summary")
    keypoints: list[str] = Field(default_factory=list, description="Key observations")
    analyzed_at: datetime | None = Field(default=None, description="Last analysis time")
    updated_at: datetime | None = Field(default=None, description="Last update time")


class Service(BaseModel):
    """A service within a project."""

    id: str = Field(description="UUID for the service")
    project_id: str = Field(description="Reference to parent project")
    name: str = Field(description="Service name")
    path: str = Field(description="Path relative to project root")
    description: str = Field(default="", description="Service description")
    type: str | None = Field(default=None, description="Service type: frontend, backend, worker, database")
    framework: str | None = Field(default=None, description="Framework: Next.js, FastAPI, etc.")
    language: str | None = Field(default=None, description="Programming language")
    version: str | None = Field(default=None, description="Framework/runtime version")
    entry_point: str | None = Field(default=None, description="Main entry file")
    build_command: str | None = Field(default=None, description="Build command")
    start_command: str | None = Field(default=None, description="Start command")
    port: int | None = Field(default=None, description="Default port")
    env_vars: list[str] = Field(default_factory=list, description="Required environment variables")
    dependencies: list[str] = Field(default_factory=list, description="IDs of services this depends on")
    keypoints: list[str] = Field(default_factory=list, description="Service-specific observations")


class Deployment(BaseModel):
    """A deployment of a service."""

    id: str = Field(description="UUID for the deployment")
    service_id: str = Field(description="Reference to the service")
    platform: str = Field(description="Platform: vercel, railway, render")
    url: str | None = Field(default=None, description="Deployment URL")
    dashboard_url: str | None = Field(default=None, description="Platform dashboard URL")
    deployed_at: datetime | None = Field(default=None, description="Deployment timestamp")
    config: dict[str, Any] = Field(default_factory=dict, description="Platform-specific config")
    status: str = Field(default="active", description="Status: active, failed, superseded")


class MonitoringConfig(BaseModel):
    """Monitoring configuration for a deployment."""

    id: str = Field(description="UUID for the monitoring config")
    deployment_id: str = Field(description="Reference to the deployment")
    health_check_url: str = Field(description="URL for health checks")
    interval_seconds: int = Field(default=60, description="Check interval in seconds")
    alert_channels: list[str] = Field(default_factory=list, description="Alert channel identifiers")
    thresholds: dict[str, Any] = Field(default_factory=dict, description="Alert thresholds")
    enabled: bool = Field(default=True, description="Whether monitoring is enabled")


class MonitoringPrefs(BaseModel):
    """Persisted preferences for the OpenOps background monitoring daemon."""

    project_path: str = Field(description="Absolute path to the project directory")
    enabled: bool = Field(default=False, description="Whether background monitoring is enabled")
    interval_seconds: int = Field(default=300, ge=60, description="Daemon tick interval in seconds")
    updated_at: datetime | None = Field(default=None, description="Last prefs update time")
    last_run_at: datetime | None = Field(default=None, description="Last successful daemon tick")
    last_error: str = Field(default="", description="Last daemon tick error message, if any")


class FindingSeverity(str, Enum):  # noqa: UP042
    """Severity level for monitoring findings."""

    OK = "ok"
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class MonitoringFinding(BaseModel):
    """A concrete issue (or notable condition) found during monitoring."""

    service_name: str = Field(description="Service name where the issue appears")
    service_id: str | None = Field(default=None, description="Service UUID if known")
    severity: FindingSeverity = Field(description="Finding severity")
    title: str = Field(description="Short title of the finding")
    evidence: str = Field(description="Supporting evidence (log excerpt, error text, etc.)")
    root_cause: str | None = Field(default=None, description="Likely root cause analysis")
    suggested_fix: str | None = Field(default=None, description="Suggested remediation steps")
    related_services: list[str] = Field(default_factory=list, description="Services involved in this issue")


class MonitoringReport(BaseModel):
    """Structured report emitted by the background monitoring agent."""

    project_path: str = Field(description="Absolute project path monitored by this report")
    project_id: str | None = Field(default=None, description="Project UUID if known")
    generated_at: datetime = Field(description="Timestamp for report generation")
    overall_status: FindingSeverity = Field(description="Overall project health status")
    summary: str = Field(description="Brief summary across all findings")
    findings: list[MonitoringFinding] = Field(default_factory=list, description="Detailed findings list")
    services_checked: list[str] = Field(default_factory=list, description="Services inspected during this run")

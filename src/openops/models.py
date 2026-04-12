"""Shared data models for OpenOps."""

import logging
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Risk level for operations and skills."""

    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


class SkillResult(BaseModel):
    """Standard result type for skill operations."""

    success: bool
    message: str
    data: dict[str, Any] | None = None
    error: str | None = None


class SkillMetadata(BaseModel):
    """Metadata for a skill, used for the skill catalog (Tier 1 progressive disclosure).

    This lightweight metadata is always loaded and serves as a semantic search key
    for the agent to determine which skills to load fully.
    """

    name: str = Field(description="Unique identifier for the skill")
    description: str = Field(description="What this skill does (1-2 sentences)")
    version: str = Field(default="1.0.0", description="Skill version")
    risk_level: RiskLevel = Field(description="Risk level of operations")
    tags: list[str] = Field(
        default_factory=list,
        description="Tags for categorization (e.g., 'deployment', 'frontend', 'monitoring')",
    )
    requires_credentials: list[str] = Field(
        default_factory=list,
        description="Credential env vars required (e.g., ['VERCEL_TOKEN'])",
    )
    provides_tools: list[str] = Field(
        default_factory=list,
        description="Names of tools this skill provides",
    )


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

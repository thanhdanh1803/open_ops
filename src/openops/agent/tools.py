"""Custom tools for OpenOps agents.

These tools provide project knowledge operations with dependency injection
for the storage layer. The storage implementation is provided at runtime,
allowing for testing with mocks and flexibility in storage backends.
"""

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from openops.agent.interactive_tmux import (
    TmuxError,
)
from openops.agent.interactive_tmux import (
    interactive_execute_tmux as _interactive_execute_tmux,
)
from openops.agent.tracing import observe
from openops.models import Deployment, MonitoringPrefs, Project, Service
from openops.storage.base import ProjectStoreBase

logger = logging.getLogger(__name__)


def create_project_knowledge_tools(
    store: ProjectStoreBase,
) -> list:
    """Create project knowledge tools with injected storage.

    Args:
        store: Project store implementation for persistence

    Returns:
        List of LangChain tools for project knowledge operations
    """

    @tool("query_project_knowledge")
    @observe(name="tool.query_project_knowledge")
    def query_project_knowledge(project_path: str) -> dict[str, Any]:
        """Query stored knowledge about a project.

        Retrieves project analysis including services, tech stack, and deployment
        history. Use this before re-analyzing a project to check if knowledge
        already exists.

        Args:
            project_path: Absolute path to the project directory

        Returns:
            Dictionary containing:
            - project: Project metadata (name, description, keypoints)
            - services: List of services with their configurations
            - deployments: Active deployments for each service
            - found: Whether the project was found in storage
        """
        logger.info(f"Querying project knowledge for: {project_path}")

        summary = store.get_project_summary(project_path)

        if not summary:
            logger.debug(f"No existing knowledge found for: {project_path}")
            return {
                "found": False,
                "message": f"No existing knowledge for project at {project_path}",
                "project": None,
                "services": [],
            }

        project: Project = summary["project"]
        services_data = summary["services"]

        logger.info(f"Found project '{project.name}' with {len(services_data)} services")

        return {
            "found": True,
            "project": {
                "id": project.id,
                "name": project.name,
                "path": project.path,
                "description": project.description,
                "keypoints": project.keypoints,
                "analyzed_at": (project.analyzed_at.isoformat() if project.analyzed_at else None),
            },
            "services": [
                {
                    "service": {
                        "id": svc_data["service"].id,
                        "name": svc_data["service"].name,
                        "path": svc_data["service"].path,
                        "type": svc_data["service"].type,
                        "framework": svc_data["service"].framework,
                        "language": svc_data["service"].language,
                        "build_command": svc_data["service"].build_command,
                        "start_command": svc_data["service"].start_command,
                        "env_vars": svc_data["service"].env_vars,
                        "keypoints": svc_data["service"].keypoints,
                    },
                    "deployment": (
                        {
                            "id": svc_data["deployment"].id,
                            "platform": svc_data["deployment"].platform,
                            "url": svc_data["deployment"].url,
                            "status": svc_data["deployment"].status,
                            "deployed_at": (
                                svc_data["deployment"].deployed_at.isoformat()
                                if svc_data["deployment"].deployed_at
                                else None
                            ),
                        }
                        if svc_data["deployment"]
                        else None
                    ),
                }
                for svc_data in services_data
            ],
        }

    @tool("save_project_knowledge")
    @observe(name="tool.save_project_knowledge")
    def save_project_knowledge(
        project_path: str,
        project_name: str,
        description: str,
        keypoints: list[str],
        services: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Save project analysis to knowledge store.

        Persists project analysis results for future reference. Call this after
        analyzing a project structure to avoid re-analysis in future sessions.

        Args:
            project_path: Absolute path to the project directory
            project_name: Name of the project
            description: Brief description of what this project does
            keypoints: Key observations from analysis (architecture, tech choices, etc.)
            services: List of services, each with:
                - name: Service name
                - path: Path relative to project root
                - type: Service type (frontend, backend, worker, database)
                - framework: Framework name (Next.js, FastAPI, etc.)
                - language: Programming language
                - build_command: Build command (optional)
                - start_command: Start command (optional)
                - env_vars: Required environment variables (optional)
                - keypoints: Service-specific observations (optional)

        Returns:
            Result with success status, project ID, and service IDs
        """
        logger.info(f"Saving project knowledge for: {project_path}")

        now = datetime.now()

        existing_project = store.get_project(project_path)
        if existing_project:
            project_id = existing_project.id
            logger.debug(f"Updating existing project: {project_id}")
        else:
            project_id = str(uuid.uuid4())
            logger.debug(f"Creating new project: {project_id}")

        project = Project(
            id=project_id,
            path=project_path,
            name=project_name,
            description=description,
            keypoints=keypoints,
            analyzed_at=now,
            updated_at=now,
        )
        store.upsert_project(project)

        service_ids = []
        for svc_data in services:
            service_id = str(uuid.uuid4())
            service = Service(
                id=service_id,
                project_id=project_id,
                name=svc_data.get("name", "unnamed"),
                path=svc_data.get("path", "."),
                description=svc_data.get("description", ""),
                type=svc_data.get("type"),
                framework=svc_data.get("framework"),
                language=svc_data.get("language"),
                version=svc_data.get("version"),
                entry_point=svc_data.get("entry_point"),
                build_command=svc_data.get("build_command"),
                start_command=svc_data.get("start_command"),
                port=svc_data.get("port"),
                env_vars=svc_data.get("env_vars", []),
                dependencies=svc_data.get("dependencies", []),
                keypoints=svc_data.get("keypoints", []),
            )
            store.upsert_service(service)
            service_ids.append(service_id)
            logger.debug(f"Saved service '{service.name}' with ID: {service_id}")

        logger.info(f"Saved project '{project_name}' with {len(service_ids)} services")

        return {
            "success": True,
            "message": f"Saved project '{project_name}' with {len(services)} services",
            "project_id": project_id,
            "service_ids": service_ids,
        }

    @tool("record_deployment")
    @observe(name="tool.record_deployment")
    def record_deployment(
        service_id: str,
        platform: str,
        url: str | None = None,
        dashboard_url: str | None = None,
        config: dict[str, Any] | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        """Record a deployment for a service.

        Call this after successfully deploying a service to track the deployment
        history. Previous active deployments will be marked as superseded.

        Args:
            service_id: UUID of the service being deployed
            platform: Platform name (vercel, railway, render)
            url: Deployment URL (optional)
            dashboard_url: Platform dashboard URL (optional)
            config: Platform-specific configuration (optional)
            status: Deployment status (default: active)

        Returns:
            Result with deployment ID and status
        """
        logger.info(f"Recording deployment for service {service_id} on {platform}")

        service = store.get_service(service_id)
        if not service:
            logger.warning(f"Service not found: {service_id}")
            return {
                "success": False,
                "message": f"Service not found: {service_id}",
                "deployment_id": None,
            }

        deployment_id = str(uuid.uuid4())
        deployment = Deployment(
            id=deployment_id,
            service_id=service_id,
            platform=platform,
            url=url,
            dashboard_url=dashboard_url,
            deployed_at=datetime.now(),
            config=config or {},
            status=status,
        )

        store.add_deployment(deployment)
        logger.info(f"Recorded deployment {deployment_id} for service {service_id}")

        return {
            "success": True,
            "message": f"Deployment recorded for {platform}",
            "deployment_id": deployment_id,
            "url": url,
            "dashboard_url": dashboard_url,
        }

    @tool("list_projects")
    @observe(name="tool.list_projects")
    def list_projects() -> dict[str, Any]:
        """List all known projects.

        Returns a summary of all projects that have been analyzed and saved.

        Returns:
            Dictionary with list of projects (id, name, path, analyzed_at)
        """
        logger.debug("Listing all projects")

        projects = store.list_projects()

        return {
            "count": len(projects),
            "projects": [
                {
                    "id": p.id,
                    "name": p.name,
                    "path": p.path,
                    "analyzed_at": p.analyzed_at.isoformat() if p.analyzed_at else None,
                }
                for p in projects
            ],
        }

    return [
        query_project_knowledge,
        save_project_knowledge,
        record_deployment,
        list_projects,
    ]


def create_monitoring_tools(store: ProjectStoreBase) -> list:
    """Tools to enable or inspect background log monitoring (daemon reads prefs)."""

    @tool("set_project_monitoring")
    @observe(name="tool.set_project_monitoring")
    def set_project_monitoring(project_path: str, enabled: bool, interval_seconds: int = 300) -> dict[str, Any]:
        """Enable or disable background monitoring for a project.

        Persists preferences for the ``openops monitor`` daemon. When enabling,
        attempts to start the daemon subprocess if it is not already running.

        Args:
            project_path: Absolute path to the project root
            enabled: Whether background monitoring should run
            interval_seconds: Minimum seconds between daemon checks (default 300, minimum 60)

        Returns:
            Result with success flag and human-facing message
        """
        path = str(Path(project_path).expanduser().resolve())
        interval = max(60, int(interval_seconds))
        logger.info("set_project_monitoring path=%s enabled=%s interval=%s", path, enabled, interval)

        prefs = MonitoringPrefs(
            project_path=path,
            enabled=enabled,
            interval_seconds=interval,
            updated_at=datetime.now(),
        )
        store.upsert_monitoring_prefs(prefs)

        if not enabled:
            return {
                "success": True,
                "enabled": False,
                "message": "Background monitoring disabled for this project (daemon will skip it on next poll).",
            }

        from openops.cli.monitor_daemon import try_start_daemon_subprocess

        started, start_message = try_start_daemon_subprocess()
        logger.debug("Daemon auto-start: started=%s msg=%s", started, start_message)
        msg = (
            "Background monitoring enabled. The daemon polls on the interval you set and delegates "
            "log checks to the monitor-agent. "
        )
        if started:
            msg += start_message
        else:
            msg += f"{start_message} You can start it anytime with: openops monitor start"
        return {
            "success": True,
            "enabled": True,
            "interval_seconds": interval,
            "message": msg,
        }

    @tool("get_project_monitoring")
    @observe(name="tool.get_project_monitoring")
    def get_project_monitoring(project_path: str) -> dict[str, Any]:
        """Return stored monitoring preferences for a project path, if any."""
        path = str(Path(project_path).expanduser().resolve())
        logger.debug("get_project_monitoring path=%s", path)
        row = store.get_monitoring_prefs(path)
        if not row:
            return {
                "found": False,
                "project_path": path,
                "message": "No monitoring preferences stored for this path.",
            }
        return {
            "found": True,
            "project_path": row.project_path,
            "enabled": row.enabled,
            "interval_seconds": row.interval_seconds,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "last_run_at": row.last_run_at.isoformat() if row.last_run_at else None,
            "last_error": row.last_error or None,
        }

    return [set_project_monitoring, get_project_monitoring]


def create_monitoring_query_tools(store: ProjectStoreBase) -> list:
    """Read-only tools for monitoring analysis and service relationship traversal."""

    @tool("list_project_services")
    @observe(name="tool.list_project_services")
    def list_project_services(project_path: str) -> dict[str, Any]:
        """List project services with active deployment and dependency metadata."""
        path = str(Path(project_path).expanduser().resolve())
        logger.debug("list_project_services path=%s", path)
        project = store.get_project(path)
        if not project:
            return {
                "found": False,
                "project": None,
                "services": [],
                "message": f"No project found at {path}",
            }

        services = store.get_services_for_project(project.id)
        payload: list[dict[str, Any]] = []
        for service in services:
            active_deployment = store.get_active_deployment(service.id)
            payload.append(
                {
                    "service": {
                        "id": service.id,
                        "name": service.name,
                        "path": service.path,
                        "type": service.type,
                        "framework": service.framework,
                        "language": service.language,
                        "dependencies": list(service.dependencies),
                    },
                    "active_deployment": (
                        {
                            "id": active_deployment.id,
                            "platform": active_deployment.platform,
                            "url": active_deployment.url,
                            "dashboard_url": active_deployment.dashboard_url,
                            "deployed_at": (
                                active_deployment.deployed_at.isoformat() if active_deployment.deployed_at else None
                            ),
                            "status": active_deployment.status,
                        }
                        if active_deployment
                        else None
                    ),
                }
            )

        return {
            "found": True,
            "project": {
                "id": project.id,
                "name": project.name,
                "path": project.path,
            },
            "services": payload,
        }

    @tool("get_service_dependents")
    @observe(name="tool.get_service_dependents")
    def get_service_dependents(service_id: str) -> dict[str, Any]:
        """Return services that depend on the given service (reverse dependencies)."""
        logger.debug("get_service_dependents service_id=%s", service_id)
        service = store.get_service(service_id)
        if not service:
            return {
                "found": False,
                "service_id": service_id,
                "dependents": [],
                "message": f"Service not found: {service_id}",
            }

        dependents: list = []
        get_dependents_fn = getattr(store, "get_dependent_services", None)
        if callable(get_dependents_fn):
            dependents = get_dependents_fn(service_id)
        else:
            for candidate in store.get_services_for_project(service.project_id):
                if service_id in candidate.dependencies:
                    dependents.append(candidate)

        return {
            "found": True,
            "service_id": service_id,
            "dependents": [
                {
                    "id": dep.id,
                    "name": dep.name,
                    "path": dep.path,
                    "type": dep.type,
                    "framework": dep.framework,
                    "language": dep.language,
                }
                for dep in dependents
            ],
        }

    @tool("get_active_deployment")
    @observe(name="tool.get_active_deployment")
    def get_active_deployment(service_id: str) -> dict[str, Any]:
        """Get current active deployment details for a service, if any."""
        logger.debug("get_active_deployment service_id=%s", service_id)
        service = store.get_service(service_id)
        if not service:
            return {
                "found": False,
                "service_id": service_id,
                "deployment": None,
                "message": f"Service not found: {service_id}",
            }

        deployment = store.get_active_deployment(service_id)
        if not deployment:
            return {
                "found": True,
                "service_id": service_id,
                "deployment": None,
                "message": "No active deployment for this service.",
            }

        return {
            "found": True,
            "service_id": service_id,
            "deployment": {
                "id": deployment.id,
                "platform": deployment.platform,
                "url": deployment.url,
                "dashboard_url": deployment.dashboard_url,
                "deployed_at": deployment.deployed_at.isoformat() if deployment.deployed_at else None,
                "status": deployment.status,
                "config": deployment.config,
            },
        }

    @tool("get_recent_deployments")
    @observe(name="tool.get_recent_deployments")
    def get_recent_deployments(service_id: str, limit: int = 5) -> dict[str, Any]:
        """Get recent deployments for a service (most recent first)."""
        logger.debug("get_recent_deployments service_id=%s limit=%s", service_id, limit)
        service = store.get_service(service_id)
        if not service:
            return {
                "found": False,
                "service_id": service_id,
                "deployments": [],
                "message": f"Service not found: {service_id}",
            }

        normalized_limit = max(1, min(int(limit), 50))
        deployments = store.get_deployments_for_service(service_id)
        deployments_sorted = sorted(
            deployments,
            key=lambda d: d.deployed_at or datetime.min,
            reverse=True,
        )

        return {
            "found": True,
            "service_id": service_id,
            "deployments": [
                {
                    "id": dep.id,
                    "platform": dep.platform,
                    "url": dep.url,
                    "dashboard_url": dep.dashboard_url,
                    "deployed_at": dep.deployed_at.isoformat() if dep.deployed_at else None,
                    "status": dep.status,
                    "config": dep.config,
                }
                for dep in deployments_sorted[:normalized_limit]
            ],
        }

    return [
        list_project_services,
        get_service_dependents,
        get_active_deployment,
        get_recent_deployments,
    ]


def create_interactive_tools() -> list:
    """Create tools for handling interactive commands (local tmux)."""

    @tool("interactive_execute_tmux")
    @observe(name="tool.interactive_execute_tmux")
    def interactive_execute_tmux(command: str, timeout_s: float = 1800.0) -> dict[str, Any]:
        """Run an interactive command in tmux and return a transcript.

        Use this when a command is likely to require a real terminal (TTY),
        pagers, editors, password prompts, or other interactive input.

        Args:
            command: Shell command to run (executed via bash -lc in tmux).
            timeout_s: Max time to allow for the interactive session.

        Returns:
            Dictionary with:
            - session: tmux session name
            - transcript: captured pane output
            - note: important warnings/instructions
        """
        logger.info("Starting interactive tmux execution")
        logger.debug("Interactive command: %s", command)
        try:
            return _interactive_execute_tmux(command, timeout_s=timeout_s)
        except TmuxError as e:
            logger.warning("Interactive tmux execution failed: %s", e)
            return {
                "success": False,
                "error": str(e),
                "session": None,
                "transcript": "",
                "note": "tmux execution failed",
            }

    return [interactive_execute_tmux]


__all__ = [
    "create_project_knowledge_tools",
    "create_interactive_tools",
    "create_monitoring_tools",
    "create_monitoring_query_tools",
]

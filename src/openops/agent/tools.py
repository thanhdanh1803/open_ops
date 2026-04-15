"""Custom tools for OpenOps agents.

These tools provide project knowledge operations with dependency injection
for the storage layer. The storage implementation is provided at runtime,
allowing for testing with mocks and flexibility in storage backends.
"""

import logging
import uuid
from datetime import datetime
from typing import Any

from langchain_core.tools import tool

from openops.agent.interactive_tmux import (
    TmuxError,
)
from openops.agent.interactive_tmux import (
    interactive_execute_tmux as _interactive_execute_tmux,
)
from openops.models import Deployment, Project, Service
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

    @tool
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

    @tool
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

    @tool
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

    @tool
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


def create_interactive_tools() -> list:
    """Create tools for handling interactive commands (local tmux)."""

    @tool
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


__all__ = ["create_project_knowledge_tools", "create_interactive_tools"]

"""Vercel deployment skill implementation."""

import logging
import os
from typing import Any

import httpx
from langchain_core.tools import tool

from openops.exceptions import PlatformAPIError
from openops.models import RiskLevel, SkillMetadata, SkillResult
from openops.skills.base import BaseSkill

logger = logging.getLogger(__name__)


class VercelSkill(BaseSkill):
    """Skill for deploying applications to Vercel.

    Provides tools for deploying projects, listing projects, and
    managing deployments on the Vercel platform.
    """

    name = "vercel-deploy"
    description = "Deploy frontend applications to Vercel"
    risk_level = RiskLevel.WRITE

    API_BASE = "https://api.vercel.com"

    def __init__(self, token: str | None = None):
        """Initialize the Vercel skill.

        Args:
            token: Vercel API token. If not provided, reads from OPENOPS_VERCEL_TOKEN
                   or VERCEL_TOKEN environment variable.
        """
        self.token = token or os.getenv("OPENOPS_VERCEL_TOKEN") or os.getenv("VERCEL_TOKEN")
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.API_BASE,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                timeout=60.0,
            )
        return self._client

    def validate_credentials(self) -> bool:
        """Check if Vercel token is configured."""
        return self.token is not None and len(self.token) > 0

    def get_metadata(self) -> SkillMetadata:
        """Return skill metadata for the catalog."""
        return SkillMetadata(
            name=self.name,
            description=self.description,
            version="1.0.0",
            risk_level=self.risk_level,
            tags=["deployment", "frontend", "vercel", "serverless"],
            requires_credentials=["OPENOPS_VERCEL_TOKEN"],
            provides_tools=["vercel_deploy", "vercel_list_projects", "vercel_get_deployments"],
        )

    def get_skill_instructions(self) -> str | None:
        """Return skill instructions from SKILL.md."""
        skill_md_path = os.path.join(os.path.dirname(__file__), "SKILL.md")
        try:
            with open(skill_md_path) as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"SKILL.md not found at {skill_md_path}")
            return None

    def get_tools(self) -> list[Any]:
        """Return LangChain tools provided by this skill."""
        return [
            self._create_deploy_tool(),
            self._create_list_projects_tool(),
            self._create_get_deployments_tool(),
        ]

    def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated request to the Vercel API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/v9/projects")
            json_data: JSON body for POST/PUT requests
            params: Query parameters

        Returns:
            Response JSON data

        Raises:
            PlatformAPIError: If the API request fails
        """
        if not self.validate_credentials():
            raise PlatformAPIError("vercel", "Vercel token not configured")

        try:
            response = self.client.request(
                method=method,
                url=endpoint,
                json=json_data,
                params=params,
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except httpx.HTTPStatusError as e:
            error_body = e.response.json() if e.response.content else {}
            error_message = error_body.get("error", {}).get("message", str(e))
            logger.error(f"Vercel API error: {error_message}")
            raise PlatformAPIError("vercel", error_message, e.response.status_code)
        except httpx.RequestError as e:
            logger.error(f"Vercel request error: {e}")
            raise PlatformAPIError("vercel", f"Request failed: {e}")

    def _create_deploy_tool(self):
        """Create the vercel_deploy tool."""
        skill = self

        @tool
        def vercel_deploy(
            project_name: str,
            git_repo: str | None = None,
            production: bool = False,
            environment_variables: dict[str, str] | None = None,
            framework: str | None = None,
            build_command: str | None = None,
            output_directory: str | None = None,
        ) -> SkillResult:
            """Deploy a project to Vercel.

            This creates or updates a Vercel project and triggers a deployment.
            For git-based deployments, provide the git_repo URL.

            Args:
                project_name: Name for the Vercel project
                git_repo: Git repository URL (e.g., "https://github.com/user/repo")
                production: Deploy to production (default: preview)
                environment_variables: Environment variables to set
                framework: Framework preset (nextjs, vite, create-react-app, etc.)
                build_command: Custom build command
                output_directory: Custom output directory

            Returns:
                SkillResult with deployment URL and status
            """
            if not skill.validate_credentials():
                return SkillResult(
                    success=False,
                    message="Vercel token not configured",
                    error="MISSING_CREDENTIALS",
                )

            try:
                project = skill._get_or_create_project(
                    project_name=project_name,
                    git_repo=git_repo,
                    framework=framework,
                    build_command=build_command,
                    output_directory=output_directory,
                )

                if environment_variables:
                    skill._set_environment_variables(project["id"], environment_variables)

                if git_repo:
                    deployment = skill._trigger_git_deployment(
                        project_id=project["id"],
                        production=production,
                    )
                else:
                    return SkillResult(
                        success=True,
                        message=f"Project '{project_name}' created/updated. "
                        "Push to the linked Git repository to trigger deployment.",
                        data={
                            "project_id": project["id"],
                            "project_name": project_name,
                            "dashboard_url": f"https://vercel.com/{project.get('accountId', '')}/{project_name}",
                        },
                    )

                logger.info(f"Vercel deployment triggered for {project_name}")
                return SkillResult(
                    success=True,
                    message=f"Deployment triggered for {project_name}",
                    data={
                        "deployment_id": deployment.get("id"),
                        "url": f"https://{deployment.get('url', '')}",
                        "state": deployment.get("readyState", "QUEUED"),
                        "dashboard_url": f"https://vercel.com/{project.get('accountId', '')}/{project_name}",
                    },
                )

            except PlatformAPIError as e:
                logger.error(f"Vercel deploy failed: {e}")
                return SkillResult(
                    success=False,
                    message=f"Deployment failed: {e}",
                    error=str(e),
                )

        return vercel_deploy

    def _get_or_create_project(
        self,
        project_name: str,
        git_repo: str | None = None,
        framework: str | None = None,
        build_command: str | None = None,
        output_directory: str | None = None,
    ) -> dict[str, Any]:
        """Get existing project or create a new one."""
        try:
            return self._make_request("GET", f"/v9/projects/{project_name}")
        except PlatformAPIError as e:
            if e.status_code != 404:
                raise

        project_data: dict[str, Any] = {"name": project_name}

        if git_repo:
            project_data["gitRepository"] = {
                "type": "github",
                "repo": git_repo.replace("https://github.com/", ""),
            }

        if framework:
            project_data["framework"] = framework

        if build_command:
            project_data["buildCommand"] = build_command

        if output_directory:
            project_data["outputDirectory"] = output_directory

        logger.info(f"Creating new Vercel project: {project_name}")
        return self._make_request("POST", "/v10/projects", json_data=project_data)

    def _set_environment_variables(
        self,
        project_id: str,
        env_vars: dict[str, str],
    ) -> None:
        """Set environment variables for a project."""
        for key, value in env_vars.items():
            env_data = {
                "key": key,
                "value": value,
                "type": "encrypted",
                "target": ["production", "preview", "development"],
            }
            try:
                self._make_request(
                    "POST",
                    f"/v10/projects/{project_id}/env",
                    json_data=env_data,
                )
                logger.debug(f"Set environment variable: {key}")
            except PlatformAPIError as e:
                if "already exists" not in str(e).lower():
                    raise
                logger.debug(f"Environment variable {key} already exists, skipping")

    def _trigger_git_deployment(
        self,
        project_id: str,
        production: bool = False,
    ) -> dict[str, Any]:
        """Trigger a deployment from the linked Git repository."""
        deploy_data = {
            "name": project_id,
            "target": "production" if production else "preview",
        }
        return self._make_request("POST", "/v13/deployments", json_data=deploy_data)

    def _create_list_projects_tool(self):
        """Create the vercel_list_projects tool."""
        skill = self

        @tool
        def vercel_list_projects(limit: int = 20) -> SkillResult:
            """List all Vercel projects for the authenticated user.

            Args:
                limit: Maximum number of projects to return (default: 20)

            Returns:
                SkillResult with list of projects
            """
            if not skill.validate_credentials():
                return SkillResult(
                    success=False,
                    message="Vercel token not configured",
                    error="MISSING_CREDENTIALS",
                )

            try:
                data = skill._make_request("GET", "/v9/projects", params={"limit": limit})
                projects = data.get("projects", [])

                project_list = [
                    {
                        "id": p["id"],
                        "name": p["name"],
                        "framework": p.get("framework"),
                        "updated_at": p.get("updatedAt"),
                        "dashboard_url": f"https://vercel.com/{p.get('accountId', '')}/{p['name']}",
                    }
                    for p in projects
                ]

                logger.info(f"Listed {len(project_list)} Vercel projects")
                return SkillResult(
                    success=True,
                    message=f"Found {len(project_list)} projects",
                    data={"projects": project_list, "total": len(project_list)},
                )

            except PlatformAPIError as e:
                logger.error(f"Failed to list projects: {e}")
                return SkillResult(
                    success=False,
                    message=f"Failed to list projects: {e}",
                    error=str(e),
                )

        return vercel_list_projects

    def _create_get_deployments_tool(self):
        """Create the vercel_get_deployments tool."""
        skill = self

        @tool
        def vercel_get_deployments(
            project_name: str,
            limit: int = 10,
            state: str | None = None,
        ) -> SkillResult:
            """Get recent deployments for a Vercel project.

            Args:
                project_name: Name of the Vercel project
                limit: Number of deployments to fetch (default: 10)
                state: Filter by state (READY, ERROR, BUILDING, QUEUED, CANCELED)

            Returns:
                SkillResult with list of deployments
            """
            if not skill.validate_credentials():
                return SkillResult(
                    success=False,
                    message="Vercel token not configured",
                    error="MISSING_CREDENTIALS",
                )

            try:
                params: dict[str, Any] = {
                    "projectId": project_name,
                    "limit": limit,
                }
                if state:
                    params["state"] = state

                data = skill._make_request("GET", "/v6/deployments", params=params)
                deployments = data.get("deployments", [])

                deployment_list = [
                    {
                        "id": d["uid"],
                        "url": f"https://{d.get('url', '')}",
                        "state": d.get("state", d.get("readyState")),
                        "created_at": d.get("created"),
                        "target": d.get("target", "preview"),
                        "meta": d.get("meta", {}),
                    }
                    for d in deployments
                ]

                logger.info(f"Listed {len(deployment_list)} deployments for {project_name}")
                return SkillResult(
                    success=True,
                    message=f"Found {len(deployment_list)} deployments for {project_name}",
                    data={"deployments": deployment_list, "project": project_name},
                )

            except PlatformAPIError as e:
                logger.error(f"Failed to get deployments: {e}")
                return SkillResult(
                    success=False,
                    message=f"Failed to get deployments: {e}",
                    error=str(e),
                )

        return vercel_get_deployments

    def __del__(self):
        """Close the HTTP client on cleanup."""
        if self._client is not None:
            self._client.close()

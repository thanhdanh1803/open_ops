"""Render deployment skill implementation."""

import logging
import os
from typing import Any

import httpx
from langchain_core.tools import tool

from openops.exceptions import PlatformAPIError
from openops.models import RiskLevel, SkillMetadata, SkillResult
from openops.skills.base import BaseSkill

logger = logging.getLogger(__name__)


class RenderSkill(BaseSkill):
    """Skill for deploying applications to Render.

    Provides tools for deploying web services, static sites, background workers,
    and managing deployments on the Render platform.
    """

    name = "render-deploy"
    description = "Deploy web services, static sites, and workers to Render"
    risk_level = RiskLevel.WRITE

    API_BASE = "https://api.render.com/v1"

    def __init__(self, api_key: str | None = None):
        """Initialize the Render skill.

        Args:
            api_key: Render API key. If not provided, reads from OPENOPS_RENDER_API_KEY
                     or RENDER_API_KEY environment variable.
        """
        self.api_key = api_key or os.getenv("OPENOPS_RENDER_API_KEY") or os.getenv("RENDER_API_KEY")
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.API_BASE,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=60.0,
            )
        return self._client

    def validate_credentials(self) -> bool:
        """Check if Render API key is configured."""
        return self.api_key is not None and len(self.api_key) > 0

    def get_metadata(self) -> SkillMetadata:
        """Return skill metadata for the catalog."""
        return SkillMetadata(
            name=self.name,
            description=self.description,
            version="1.0.0",
            risk_level=self.risk_level,
            tags=["deployment", "backend", "frontend", "render", "static-site"],
            requires_credentials=["OPENOPS_RENDER_API_KEY"],
            provides_tools=[
                "render_deploy",
                "render_list_services",
                "render_get_deployments",
            ],
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
            self._create_list_services_tool(),
            self._create_get_deployments_tool(),
        ]

    def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any]:
        """Make an authenticated request to the Render API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/services")
            json_data: JSON body for POST/PUT requests
            params: Query parameters

        Returns:
            Response JSON data

        Raises:
            PlatformAPIError: If the API request fails
        """
        if not self.validate_credentials():
            raise PlatformAPIError("render", "Render API key not configured")

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
            error_message = error_body.get("message", str(e))
            logger.error(f"Render API error: {error_message}")
            raise PlatformAPIError("render", error_message, e.response.status_code) from e
        except httpx.RequestError as e:
            logger.error(f"Render request error: {e}")
            raise PlatformAPIError("render", f"Request failed: {e}") from e

    def _create_deploy_tool(self):
        """Create the render_deploy tool."""
        skill = self

        @tool
        def render_deploy(
            service_name: str,
            service_type: str,
            git_repo: str,
            branch: str = "main",
            environment_variables: dict[str, str] | None = None,
            build_command: str | None = None,
            start_command: str | None = None,
            health_check_path: str | None = None,
            instance_type: str = "free",
            auto_deploy: bool = True,
        ) -> SkillResult:
            """Deploy a new service to Render.

            Creates a new Render service from a Git repository and triggers deployment.

            Args:
                service_name: Name for the Render service
                service_type: Type of service (web_service, static_site, background_worker, private_service)
                git_repo: Git repository URL (e.g., "https://github.com/user/repo")
                branch: Git branch to deploy (default: main)
                environment_variables: Environment variables to set
                build_command: Custom build command
                start_command: Custom start command (for web services)
                health_check_path: Health check endpoint path
                instance_type: Instance type (free, starter, standard, etc.)
                auto_deploy: Enable automatic deploys on push (default: true)

            Returns:
                SkillResult with service ID, URL, and deployment status
            """
            if not skill.validate_credentials():
                return SkillResult(
                    success=False,
                    message="Render API key not configured",
                    error="MISSING_CREDENTIALS",
                )

            valid_types = [
                "web_service",
                "static_site",
                "background_worker",
                "private_service",
            ]
            if service_type not in valid_types:
                return SkillResult(
                    success=False,
                    message=f"Invalid service_type. Must be one of: {valid_types}",
                    error="INVALID_SERVICE_TYPE",
                )

            try:
                service_data = skill._build_service_data(
                    service_name=service_name,
                    service_type=service_type,
                    git_repo=git_repo,
                    branch=branch,
                    environment_variables=environment_variables,
                    build_command=build_command,
                    start_command=start_command,
                    health_check_path=health_check_path,
                    instance_type=instance_type,
                    auto_deploy=auto_deploy,
                )

                response = skill._make_request("POST", "/services", json_data=service_data)
                service = response.get("service", response)

                logger.info(f"Render service created: {service_name}")
                return SkillResult(
                    success=True,
                    message=f"Service '{service_name}' created on Render",
                    data={
                        "service_id": service.get("id"),
                        "service_name": service_name,
                        "type": service_type,
                        "url": service.get("serviceDetails", {}).get("url"),
                        "status": service.get("suspended", "active") if not service.get("suspended") else "suspended",
                        "dashboard_url": f"https://dashboard.render.com/web/{service.get('id')}",
                    },
                )

            except PlatformAPIError as e:
                logger.error(f"Render deploy failed: {e}")
                return SkillResult(
                    success=False,
                    message=f"Deployment failed: {e}",
                    error=str(e),
                )

        return render_deploy

    def _build_service_data(
        self,
        service_name: str,
        service_type: str,
        git_repo: str,
        branch: str,
        environment_variables: dict[str, str] | None,
        build_command: str | None,
        start_command: str | None,
        health_check_path: str | None,
        instance_type: str,
        auto_deploy: bool,
    ) -> dict[str, Any]:
        """Build the service creation payload for Render API."""
        type_mapping = {
            "web_service": "web_service",
            "static_site": "static_site",
            "background_worker": "background_worker",
            "private_service": "private_service",
        }

        service_data: dict[str, Any] = {
            "type": type_mapping[service_type],
            "name": service_name,
            "repo": git_repo,
            "branch": branch,
            "autoDeploy": "yes" if auto_deploy else "no",
        }

        service_details: dict[str, Any] = {}

        if service_type in ["web_service", "private_service", "background_worker"]:
            service_details["env"] = "node"
            service_details["plan"] = instance_type

            if build_command:
                service_details["buildCommand"] = build_command

            if start_command:
                service_details["startCommand"] = start_command

            if health_check_path and service_type == "web_service":
                service_details["healthCheckPath"] = health_check_path

        elif service_type == "static_site":
            if build_command:
                service_details["buildCommand"] = build_command
            service_details["publishPath"] = "dist"

        if service_details:
            service_data["serviceDetails"] = service_details

        if environment_variables:
            service_data["envVars"] = [{"key": k, "value": v} for k, v in environment_variables.items()]

        return service_data

    def _create_list_services_tool(self):
        """Create the render_list_services tool."""
        skill = self

        @tool
        def render_list_services(
            service_type: str | None = None,
            limit: int = 20,
        ) -> SkillResult:
            """List Render services for the authenticated user.

            Args:
                service_type: Filter by type (web_service, static_site, background_worker, private_service)
                limit: Maximum number of services to return (default: 20)

            Returns:
                SkillResult with list of services
            """
            if not skill.validate_credentials():
                return SkillResult(
                    success=False,
                    message="Render API key not configured",
                    error="MISSING_CREDENTIALS",
                )

            try:
                params: dict[str, Any] = {"limit": limit}
                if service_type:
                    params["type"] = service_type

                data = skill._make_request("GET", "/services", params=params)

                services = []
                items = data if isinstance(data, list) else data.get("services", [])

                for item in items:
                    service = item.get("service", item)
                    services.append(
                        {
                            "id": service.get("id"),
                            "name": service.get("name"),
                            "type": service.get("type"),
                            "url": service.get("serviceDetails", {}).get("url"),
                            "status": "active" if not service.get("suspended") else "suspended",
                            "updated_at": service.get("updatedAt"),
                            "dashboard_url": f"https://dashboard.render.com/web/{service.get('id')}",
                        }
                    )

                logger.info(f"Listed {len(services)} Render services")
                return SkillResult(
                    success=True,
                    message=f"Found {len(services)} services",
                    data={"services": services, "total": len(services)},
                )

            except PlatformAPIError as e:
                logger.error(f"Failed to list services: {e}")
                return SkillResult(
                    success=False,
                    message=f"Failed to list services: {e}",
                    error=str(e),
                )

        return render_list_services

    def _create_get_deployments_tool(self):
        """Create the render_get_deployments tool."""
        skill = self

        @tool
        def render_get_deployments(
            service_id: str,
            limit: int = 10,
        ) -> SkillResult:
            """Get recent deployments for a Render service.

            Args:
                service_id: Render service ID
                limit: Number of deployments to fetch (default: 10)

            Returns:
                SkillResult with list of deployments
            """
            if not skill.validate_credentials():
                return SkillResult(
                    success=False,
                    message="Render API key not configured",
                    error="MISSING_CREDENTIALS",
                )

            try:
                data = skill._make_request(
                    "GET",
                    f"/services/{service_id}/deploys",
                    params={"limit": limit},
                )

                deployments = []
                items = data if isinstance(data, list) else data.get("deploys", [])

                for item in items:
                    deploy = item.get("deploy", item)
                    deployments.append(
                        {
                            "id": deploy.get("id"),
                            "status": deploy.get("status"),
                            "commit": deploy.get("commit", {}).get("id", "")[:7] if deploy.get("commit") else None,
                            "commit_message": deploy.get("commit", {}).get("message") if deploy.get("commit") else None,
                            "created_at": deploy.get("createdAt"),
                            "finished_at": deploy.get("finishedAt"),
                        }
                    )

                logger.info(f"Listed {len(deployments)} deployments for service {service_id}")
                return SkillResult(
                    success=True,
                    message=f"Found {len(deployments)} deployments",
                    data={
                        "deployments": deployments,
                        "service_id": service_id,
                    },
                )

            except PlatformAPIError as e:
                logger.error(f"Failed to get deployments: {e}")
                return SkillResult(
                    success=False,
                    message=f"Failed to get deployments: {e}",
                    error=str(e),
                )

        return render_get_deployments

    def trigger_deploy(self, service_id: str) -> SkillResult:
        """Trigger a new deployment for an existing service.

        Args:
            service_id: Render service ID

        Returns:
            SkillResult with deployment info
        """
        if not self.validate_credentials():
            return SkillResult(
                success=False,
                message="Render API key not configured",
                error="MISSING_CREDENTIALS",
            )

        try:
            data = self._make_request("POST", f"/services/{service_id}/deploys")
            deploy = data.get("deploy", data)

            logger.info(f"Triggered deployment for service {service_id}")
            return SkillResult(
                success=True,
                message="Deployment triggered",
                data={
                    "deployment_id": deploy.get("id"),
                    "status": deploy.get("status"),
                    "service_id": service_id,
                },
            )

        except PlatformAPIError as e:
            logger.error(f"Failed to trigger deployment: {e}")
            return SkillResult(
                success=False,
                message=f"Failed to trigger deployment: {e}",
                error=str(e),
            )

    def __del__(self):
        """Close the HTTP client on cleanup."""
        if self._client is not None:
            self._client.close()

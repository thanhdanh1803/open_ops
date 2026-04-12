"""Railway deployment skill implementation."""

import logging
import os
from typing import Any

import httpx
from langchain_core.tools import tool

from openops.exceptions import PlatformAPIError
from openops.models import RiskLevel, SkillMetadata, SkillResult
from openops.skills.base import BaseSkill

logger = logging.getLogger(__name__)


class RailwaySkill(BaseSkill):
    """Skill for deploying applications to Railway.

    Provides tools for deploying services, managing projects, and
    handling deployments on the Railway platform via GraphQL API.
    """

    name = "railway-deploy"
    description = "Deploy backend services and databases to Railway"
    risk_level = RiskLevel.WRITE

    API_BASE = "https://backboard.railway.app/graphql/v2"

    def __init__(self, token: str | None = None):
        """Initialize the Railway skill.

        Args:
            token: Railway API token. If not provided, reads from OPENOPS_RAILWAY_TOKEN
                   or RAILWAY_TOKEN environment variable.
        """
        self.token = token or os.getenv("OPENOPS_RAILWAY_TOKEN") or os.getenv("RAILWAY_TOKEN")
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
        """Check if Railway token is configured."""
        return self.token is not None and len(self.token) > 0

    def get_metadata(self) -> SkillMetadata:
        """Return skill metadata for the catalog."""
        return SkillMetadata(
            name=self.name,
            description=self.description,
            version="1.0.0",
            risk_level=self.risk_level,
            tags=["deployment", "backend", "railway", "database", "infrastructure"],
            requires_credentials=["OPENOPS_RAILWAY_TOKEN"],
            provides_tools=[
                "railway_deploy",
                "railway_list_projects",
                "railway_list_services",
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
            self._create_list_projects_tool(),
            self._create_list_services_tool(),
        ]

    def _graphql_request(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a GraphQL request to Railway API.

        Args:
            query: GraphQL query or mutation
            variables: Query variables

        Returns:
            Response data

        Raises:
            PlatformAPIError: If the request fails
        """
        if not self.validate_credentials():
            raise PlatformAPIError("railway", "Railway token not configured")

        try:
            response = self.client.post(
                "",
                json={"query": query, "variables": variables or {}},
            )
            response.raise_for_status()
            data = response.json()

            if "errors" in data:
                error_msg = data["errors"][0].get("message", "Unknown GraphQL error")
                logger.error(f"Railway GraphQL error: {error_msg}")
                raise PlatformAPIError("railway", error_msg)

            return data.get("data", {})

        except httpx.HTTPStatusError as e:
            error_body = e.response.json() if e.response.content else {}
            error_message = error_body.get("message", str(e))
            logger.error(f"Railway API error: {error_message}")
            raise PlatformAPIError("railway", error_message, e.response.status_code) from e
        except httpx.RequestError as e:
            logger.error(f"Railway request error: {e}")
            raise PlatformAPIError("railway", f"Request failed: {e}") from e

    def _create_deploy_tool(self):
        """Create the railway_deploy tool."""
        skill = self

        @tool
        def railway_deploy(
            project_id: str,
            service_name: str,
            git_repo: str | None = None,
            environment_variables: dict[str, str] | None = None,
            start_command: str | None = None,
            build_command: str | None = None,
            root_directory: str | None = None,
        ) -> SkillResult:
            """Deploy a service to Railway.

            Creates a new service in an existing Railway project and triggers deployment.
            Can deploy from a Git repository or use Railway's Nixpacks build system.

            Args:
                project_id: Railway project ID to deploy to
                service_name: Name for the service
                git_repo: Git repository URL (e.g., "https://github.com/user/repo")
                environment_variables: Environment variables to set
                start_command: Custom start command
                build_command: Custom build command
                root_directory: Root directory for monorepos

            Returns:
                SkillResult with service ID and deployment status
            """
            if not skill.validate_credentials():
                return SkillResult(
                    success=False,
                    message="Railway token not configured",
                    error="MISSING_CREDENTIALS",
                )

            try:
                service = skill._create_service(
                    project_id=project_id,
                    service_name=service_name,
                    git_repo=git_repo,
                )

                if environment_variables:
                    skill._set_environment_variables(
                        project_id=project_id,
                        service_id=service["id"],
                        env_vars=environment_variables,
                    )

                if any([start_command, build_command, root_directory]):
                    skill._update_service_config(
                        service_id=service["id"],
                        start_command=start_command,
                        build_command=build_command,
                        root_directory=root_directory,
                    )

                deployment = skill._trigger_deployment(service["id"])

                logger.info(f"Railway deployment triggered for {service_name}")
                return SkillResult(
                    success=True,
                    message=f"Service '{service_name}' deployed to Railway",
                    data={
                        "service_id": service["id"],
                        "service_name": service_name,
                        "deployment_id": deployment.get("id"),
                        "status": deployment.get("status", "BUILDING"),
                        "dashboard_url": f"https://railway.app/project/{project_id}/service/{service['id']}",
                    },
                )

            except PlatformAPIError as e:
                logger.error(f"Railway deploy failed: {e}")
                return SkillResult(
                    success=False,
                    message=f"Deployment failed: {e}",
                    error=str(e),
                )

        return railway_deploy

    def _create_service(
        self,
        project_id: str,
        service_name: str,
        git_repo: str | None = None,
    ) -> dict[str, Any]:
        """Create a new service in a Railway project."""
        if git_repo:
            mutation = """
            mutation ServiceCreateFromRepo($input: ServiceCreateInput!) {
                serviceCreate(input: $input) {
                    id
                    name
                }
            }
            """
            repo_parts = git_repo.replace("https://github.com/", "").split("/")
            variables = {
                "input": {
                    "projectId": project_id,
                    "name": service_name,
                    "source": {
                        "repo": f"{repo_parts[0]}/{repo_parts[1]}",
                    },
                }
            }
        else:
            mutation = """
            mutation ServiceCreate($input: ServiceCreateInput!) {
                serviceCreate(input: $input) {
                    id
                    name
                }
            }
            """
            variables = {
                "input": {
                    "projectId": project_id,
                    "name": service_name,
                }
            }

        logger.info(f"Creating Railway service: {service_name}")
        data = self._graphql_request(mutation, variables)
        return data.get("serviceCreate", {})

    def _set_environment_variables(
        self,
        project_id: str,
        service_id: str,
        env_vars: dict[str, str],
    ) -> None:
        """Set environment variables for a service."""
        mutation = """
        mutation VariableCollectionUpsert($input: VariableCollectionUpsertInput!) {
            variableCollectionUpsert(input: $input)
        }
        """

        variables = {
            "input": {
                "projectId": project_id,
                "serviceId": service_id,
                "variables": env_vars,
            }
        }

        self._graphql_request(mutation, variables)
        logger.debug(f"Set {len(env_vars)} environment variables")

    def _update_service_config(
        self,
        service_id: str,
        start_command: str | None = None,
        build_command: str | None = None,
        root_directory: str | None = None,
    ) -> None:
        """Update service configuration."""
        mutation = """
        mutation ServiceUpdate($id: String!, $input: ServiceUpdateInput!) {
            serviceUpdate(id: $id, input: $input) {
                id
            }
        }
        """

        input_data: dict[str, Any] = {}
        if start_command:
            input_data["startCommand"] = start_command
        if build_command:
            input_data["buildCommand"] = build_command
        if root_directory:
            input_data["rootDirectory"] = root_directory

        if input_data:
            self._graphql_request(mutation, {"id": service_id, "input": input_data})
            logger.debug(f"Updated service config: {input_data}")

    def _trigger_deployment(self, service_id: str) -> dict[str, Any]:
        """Trigger a deployment for a service."""
        mutation = """
        mutation DeploymentTrigger($input: DeploymentTriggerInput!) {
            deploymentTrigger(input: $input) {
                id
                status
            }
        }
        """

        variables = {
            "input": {
                "serviceId": service_id,
            }
        }

        data = self._graphql_request(mutation, variables)
        return data.get("deploymentTrigger", {})

    def _create_list_projects_tool(self):
        """Create the railway_list_projects tool."""
        skill = self

        @tool
        def railway_list_projects() -> SkillResult:
            """List all Railway projects for the authenticated user.

            Returns:
                SkillResult with list of projects
            """
            if not skill.validate_credentials():
                return SkillResult(
                    success=False,
                    message="Railway token not configured",
                    error="MISSING_CREDENTIALS",
                )

            try:
                query = """
                query Projects {
                    projects {
                        edges {
                            node {
                                id
                                name
                                description
                                updatedAt
                                services {
                                    edges {
                                        node {
                                            id
                                            name
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                """

                data = skill._graphql_request(query)
                edges = data.get("projects", {}).get("edges", [])

                projects = [
                    {
                        "id": edge["node"]["id"],
                        "name": edge["node"]["name"],
                        "description": edge["node"].get("description"),
                        "updated_at": edge["node"].get("updatedAt"),
                        "service_count": len(edge["node"].get("services", {}).get("edges", [])),
                        "dashboard_url": f"https://railway.app/project/{edge['node']['id']}",
                    }
                    for edge in edges
                ]

                logger.info(f"Listed {len(projects)} Railway projects")
                return SkillResult(
                    success=True,
                    message=f"Found {len(projects)} projects",
                    data={"projects": projects, "total": len(projects)},
                )

            except PlatformAPIError as e:
                logger.error(f"Failed to list projects: {e}")
                return SkillResult(
                    success=False,
                    message=f"Failed to list projects: {e}",
                    error=str(e),
                )

        return railway_list_projects

    def _create_list_services_tool(self):
        """Create the railway_list_services tool."""
        skill = self

        @tool
        def railway_list_services(project_id: str) -> SkillResult:
            """List all services in a Railway project.

            Args:
                project_id: Railway project ID

            Returns:
                SkillResult with list of services and their status
            """
            if not skill.validate_credentials():
                return SkillResult(
                    success=False,
                    message="Railway token not configured",
                    error="MISSING_CREDENTIALS",
                )

            try:
                query = """
                query ProjectServices($projectId: String!) {
                    project(id: $projectId) {
                        id
                        name
                        services {
                            edges {
                                node {
                                    id
                                    name
                                    updatedAt
                                    deployments(first: 1) {
                                        edges {
                                            node {
                                                id
                                                status
                                                url
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                """

                data = skill._graphql_request(query, {"projectId": project_id})
                project = data.get("project", {})
                service_edges = project.get("services", {}).get("edges", [])

                services = []
                for edge in service_edges:
                    node = edge["node"]
                    deployments = node.get("deployments", {}).get("edges", [])
                    latest_deployment = deployments[0]["node"] if deployments else None

                    services.append(
                        {
                            "id": node["id"],
                            "name": node["name"],
                            "updated_at": node.get("updatedAt"),
                            "status": latest_deployment.get("status") if latest_deployment else "NO_DEPLOYMENT",
                            "url": latest_deployment.get("url") if latest_deployment else None,
                            "dashboard_url": f"https://railway.app/project/{project_id}/service/{node['id']}",
                        }
                    )

                logger.info(f"Listed {len(services)} services for project {project_id}")
                return SkillResult(
                    success=True,
                    message=f"Found {len(services)} services in project '{project.get('name', project_id)}'",
                    data={
                        "services": services,
                        "project_id": project_id,
                        "project_name": project.get("name"),
                    },
                )

            except PlatformAPIError as e:
                logger.error(f"Failed to list services: {e}")
                return SkillResult(
                    success=False,
                    message=f"Failed to list services: {e}",
                    error=str(e),
                )

        return railway_list_services

    def __del__(self):
        """Close the HTTP client on cleanup."""
        if self._client is not None:
            self._client.close()

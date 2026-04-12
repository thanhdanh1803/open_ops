"""Tests for the Railway deployment skill."""

import json
from unittest.mock import patch

import httpx
import pytest

from openops.exceptions import PlatformAPIError
from openops.models import RiskLevel, SkillResult
from openops.skills.railway import RailwaySkill


def create_mock_transport(handler_func) -> httpx.MockTransport:
    """Create a mock transport with a custom handler function."""
    return httpx.MockTransport(handler_func)


def create_graphql_response(data: dict) -> httpx.Response:
    """Create a successful GraphQL response."""
    return httpx.Response(200, json={"data": data})


def create_graphql_error(message: str) -> httpx.Response:
    """Create a GraphQL error response."""
    return httpx.Response(200, json={"errors": [{"message": message}]})


class TestRailwaySkillInit:
    def test_init_with_token(self):
        skill = RailwaySkill(token="test-token")
        assert skill.token == "test-token"
        assert skill.validate_credentials() is True

    def test_init_without_token(self):
        with patch.dict("os.environ", {}, clear=True):
            skill = RailwaySkill(token=None)
            assert skill.token is None
            assert skill.validate_credentials() is False

    def test_init_from_env_openops_token(self):
        with patch.dict("os.environ", {"OPENOPS_RAILWAY_TOKEN": "env-token"}, clear=True):
            skill = RailwaySkill()
            assert skill.token == "env-token"

    def test_init_from_env_railway_token(self):
        with patch.dict("os.environ", {"RAILWAY_TOKEN": "railway-env-token"}, clear=True):
            skill = RailwaySkill()
            assert skill.token == "railway-env-token"


class TestRailwaySkillMetadata:
    def test_get_metadata(self):
        skill = RailwaySkill(token="test-token")
        metadata = skill.get_metadata()

        assert metadata.name == "railway-deploy"
        assert metadata.description == "Deploy backend services and databases to Railway"
        assert metadata.risk_level == RiskLevel.WRITE
        assert "deployment" in metadata.tags
        assert "railway" in metadata.tags
        assert "backend" in metadata.tags
        assert "OPENOPS_RAILWAY_TOKEN" in metadata.requires_credentials
        assert "railway_deploy" in metadata.provides_tools
        assert "railway_list_projects" in metadata.provides_tools
        assert "railway_list_services" in metadata.provides_tools

    def test_skill_attributes(self):
        skill = RailwaySkill(token="test-token")

        assert skill.name == "railway-deploy"
        assert skill.description == "Deploy backend services and databases to Railway"
        assert skill.risk_level == RiskLevel.WRITE


class TestRailwaySkillTools:
    def test_get_tools_returns_three_tools(self):
        skill = RailwaySkill(token="test-token")
        tools = skill.get_tools()

        assert len(tools) == 3
        tool_names = [t.name for t in tools]
        assert "railway_deploy" in tool_names
        assert "railway_list_projects" in tool_names
        assert "railway_list_services" in tool_names


class TestRailwayListProjects:
    def test_list_projects_success(self):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            if "projects" in body.get("query", "").lower():
                return create_graphql_response({
                    "projects": {
                        "edges": [
                            {
                                "node": {
                                    "id": "proj-1",
                                    "name": "my-backend",
                                    "description": "Backend API",
                                    "updatedAt": "2024-01-01T00:00:00Z",
                                    "services": {"edges": [{"node": {"id": "svc-1", "name": "api"}}]},
                                }
                            },
                            {
                                "node": {
                                    "id": "proj-2",
                                    "name": "another-project",
                                    "description": None,
                                    "updatedAt": "2024-01-02T00:00:00Z",
                                    "services": {"edges": []},
                                }
                            },
                        ]
                    }
                })
            return httpx.Response(400)

        skill = RailwaySkill(token="test-token")
        skill._client = httpx.Client(
            transport=create_mock_transport(handler),
            base_url=skill.API_BASE,
        )

        tools = skill.get_tools()
        list_projects_tool = next(t for t in tools if t.name == "railway_list_projects")

        result = list_projects_tool.invoke({})

        assert result.success is True
        assert result.data["total"] == 2
        assert result.data["projects"][0]["name"] == "my-backend"
        assert result.data["projects"][0]["service_count"] == 1

    def test_list_projects_missing_credentials(self):
        skill = RailwaySkill(token=None)
        tools = skill.get_tools()
        list_projects_tool = next(t for t in tools if t.name == "railway_list_projects")

        result = list_projects_tool.invoke({})

        assert result.success is False
        assert result.error == "MISSING_CREDENTIALS"


class TestRailwayListServices:
    def test_list_services_success(self):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            if "project" in body.get("query", "").lower():
                return create_graphql_response({
                    "project": {
                        "id": "proj-1",
                        "name": "my-backend",
                        "services": {
                            "edges": [
                                {
                                    "node": {
                                        "id": "svc-1",
                                        "name": "api",
                                        "updatedAt": "2024-01-01T00:00:00Z",
                                        "deployments": {
                                            "edges": [
                                                {
                                                    "node": {
                                                        "id": "deploy-1",
                                                        "status": "SUCCESS",
                                                        "url": "api.railway.app",
                                                    }
                                                }
                                            ]
                                        },
                                    }
                                },
                                {
                                    "node": {
                                        "id": "svc-2",
                                        "name": "worker",
                                        "updatedAt": "2024-01-02T00:00:00Z",
                                        "deployments": {"edges": []},
                                    }
                                },
                            ]
                        },
                    }
                })
            return httpx.Response(400)

        skill = RailwaySkill(token="test-token")
        skill._client = httpx.Client(
            transport=create_mock_transport(handler),
            base_url=skill.API_BASE,
        )

        tools = skill.get_tools()
        list_services_tool = next(t for t in tools if t.name == "railway_list_services")

        result = list_services_tool.invoke({"project_id": "proj-1"})

        assert result.success is True
        assert len(result.data["services"]) == 2
        assert result.data["services"][0]["name"] == "api"
        assert result.data["services"][0]["status"] == "SUCCESS"
        assert result.data["services"][1]["status"] == "NO_DEPLOYMENT"


class TestRailwayDeploy:
    def test_deploy_with_git_repo(self):
        call_sequence = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            query = body.get("query", "").lower()

            if "servicecreate" in query:
                call_sequence.append("create")
                return create_graphql_response({
                    "serviceCreate": {"id": "svc-new", "name": "my-service"}
                })
            elif "deploymenttrigger" in query:
                call_sequence.append("deploy")
                return create_graphql_response({
                    "deploymentTrigger": {"id": "deploy-1", "status": "BUILDING"}
                })
            return httpx.Response(400)

        skill = RailwaySkill(token="test-token")
        skill._client = httpx.Client(
            transport=create_mock_transport(handler),
            base_url=skill.API_BASE,
        )

        tools = skill.get_tools()
        deploy_tool = next(t for t in tools if t.name == "railway_deploy")

        result = deploy_tool.invoke({
            "project_id": "proj-1",
            "service_name": "my-service",
            "git_repo": "https://github.com/user/repo",
        })

        assert result.success is True
        assert result.data["service_id"] == "svc-new"
        assert result.data["status"] == "BUILDING"
        assert "create" in call_sequence
        assert "deploy" in call_sequence

    def test_deploy_with_env_vars(self):
        call_sequence = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            query = body.get("query", "").lower()

            if "servicecreate" in query:
                call_sequence.append("create")
                return create_graphql_response({
                    "serviceCreate": {"id": "svc-new", "name": "my-service"}
                })
            elif "variablecollectionupsert" in query:
                call_sequence.append("env")
                return create_graphql_response({"variableCollectionUpsert": True})
            elif "deploymenttrigger" in query:
                call_sequence.append("deploy")
                return create_graphql_response({
                    "deploymentTrigger": {"id": "deploy-1", "status": "BUILDING"}
                })
            return httpx.Response(400)

        skill = RailwaySkill(token="test-token")
        skill._client = httpx.Client(
            transport=create_mock_transport(handler),
            base_url=skill.API_BASE,
        )

        tools = skill.get_tools()
        deploy_tool = next(t for t in tools if t.name == "railway_deploy")

        result = deploy_tool.invoke({
            "project_id": "proj-1",
            "service_name": "my-service",
            "environment_variables": {"DATABASE_URL": "postgres://..."},
        })

        assert result.success is True
        assert "env" in call_sequence

    def test_deploy_missing_credentials(self):
        skill = RailwaySkill(token=None)
        tools = skill.get_tools()
        deploy_tool = next(t for t in tools if t.name == "railway_deploy")

        result = deploy_tool.invoke({
            "project_id": "proj-1",
            "service_name": "my-service",
        })

        assert result.success is False
        assert result.error == "MISSING_CREDENTIALS"


class TestRailwayErrorHandling:
    def test_graphql_error_handling(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return create_graphql_error("Project not found")

        skill = RailwaySkill(token="test-token")
        skill._client = httpx.Client(
            transport=create_mock_transport(handler),
            base_url=skill.API_BASE,
        )

        tools = skill.get_tools()
        list_projects_tool = next(t for t in tools if t.name == "railway_list_projects")

        result = list_projects_tool.invoke({})

        assert result.success is False
        assert "not found" in result.error.lower()


class TestRailwaySkillInstructions:
    def test_get_skill_instructions(self):
        skill = RailwaySkill(token="test-token")
        instructions = skill.get_skill_instructions()

        assert instructions is not None
        assert "Railway" in instructions
        assert "railway_deploy" in instructions

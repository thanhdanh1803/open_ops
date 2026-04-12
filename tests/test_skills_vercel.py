"""Tests for the Vercel deployment skill."""

from unittest.mock import patch

import httpx

from openops.models import RiskLevel
from openops.skills.vercel import VercelSkill


def create_mock_transport(responses: dict[str, httpx.Response]) -> httpx.MockTransport:
    """Create a mock transport that returns predefined responses based on URL patterns."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        method = request.method

        key = f"{method} {path}"

        for pattern, response in responses.items():
            if pattern in key or path.startswith(pattern.split()[-1] if " " in pattern else pattern):
                return response

        return httpx.Response(404, json={"error": {"message": "Not found"}})

    return httpx.MockTransport(handler)


class TestVercelSkillInit:
    def test_init_with_token(self):
        skill = VercelSkill(token="test-token")
        assert skill.token == "test-token"
        assert skill.validate_credentials() is True

    def test_init_without_token(self):
        with patch.dict("os.environ", {}, clear=True):
            skill = VercelSkill(token=None)
            assert skill.token is None
            assert skill.validate_credentials() is False

    def test_init_from_env_openops_token(self):
        with patch.dict("os.environ", {"OPENOPS_VERCEL_TOKEN": "env-token"}, clear=True):
            skill = VercelSkill()
            assert skill.token == "env-token"

    def test_init_from_env_vercel_token(self):
        with patch.dict("os.environ", {"VERCEL_TOKEN": "vercel-env-token"}, clear=True):
            skill = VercelSkill()
            assert skill.token == "vercel-env-token"


class TestVercelSkillMetadata:
    def test_get_metadata(self):
        skill = VercelSkill(token="test-token")
        metadata = skill.get_metadata()

        assert metadata.name == "vercel-deploy"
        assert metadata.description == "Deploy frontend applications to Vercel"
        assert metadata.risk_level == RiskLevel.WRITE
        assert "deployment" in metadata.tags
        assert "vercel" in metadata.tags
        assert "OPENOPS_VERCEL_TOKEN" in metadata.requires_credentials
        assert "vercel_deploy" in metadata.provides_tools
        assert "vercel_list_projects" in metadata.provides_tools
        assert "vercel_get_deployments" in metadata.provides_tools

    def test_skill_attributes(self):
        skill = VercelSkill(token="test-token")

        assert skill.name == "vercel-deploy"
        assert skill.description == "Deploy frontend applications to Vercel"
        assert skill.risk_level == RiskLevel.WRITE


class TestVercelSkillTools:
    def test_get_tools_returns_three_tools(self):
        skill = VercelSkill(token="test-token")
        tools = skill.get_tools()

        assert len(tools) == 3
        tool_names = [t.name for t in tools]
        assert "vercel_deploy" in tool_names
        assert "vercel_list_projects" in tool_names
        assert "vercel_get_deployments" in tool_names


class TestVercelListProjects:
    def test_list_projects_success(self):
        mock_response = httpx.Response(
            200,
            json={
                "projects": [
                    {
                        "id": "proj-1",
                        "name": "my-app",
                        "framework": "nextjs",
                        "updatedAt": "2024-01-01T00:00:00Z",
                        "accountId": "user-123",
                    },
                    {
                        "id": "proj-2",
                        "name": "another-app",
                        "framework": "vite",
                        "updatedAt": "2024-01-02T00:00:00Z",
                        "accountId": "user-123",
                    },
                ]
            },
        )

        skill = VercelSkill(token="test-token")
        skill._client = httpx.Client(
            transport=create_mock_transport({"GET /v9/projects": mock_response}),
            base_url=skill.API_BASE,
        )

        tools = skill.get_tools()
        list_projects_tool = next(t for t in tools if t.name == "vercel_list_projects")

        result = list_projects_tool.invoke({})

        assert result.success is True
        assert result.data["total"] == 2
        assert result.data["projects"][0]["name"] == "my-app"

    def test_list_projects_missing_credentials(self):
        skill = VercelSkill(token=None)
        tools = skill.get_tools()
        list_projects_tool = next(t for t in tools if t.name == "vercel_list_projects")

        result = list_projects_tool.invoke({})

        assert result.success is False
        assert result.error == "MISSING_CREDENTIALS"


class TestVercelDeploy:
    def test_deploy_with_git_repo(self):
        mock_responses = {
            "GET /v9/projects/my-app": httpx.Response(
                200,
                json={"id": "proj-1", "name": "my-app", "accountId": "user-123"},
            ),
            "POST /v13/deployments": httpx.Response(
                200,
                json={
                    "id": "deploy-1",
                    "url": "my-app-abc123.vercel.app",
                    "readyState": "QUEUED",
                },
            ),
        }

        skill = VercelSkill(token="test-token")
        skill._client = httpx.Client(
            transport=create_mock_transport(mock_responses),
            base_url=skill.API_BASE,
        )

        tools = skill.get_tools()
        deploy_tool = next(t for t in tools if t.name == "vercel_deploy")

        result = deploy_tool.invoke(
            {
                "project_name": "my-app",
                "git_repo": "https://github.com/user/repo",
            }
        )

        assert result.success is True
        assert "deployment_id" in result.data
        assert "url" in result.data

    def test_deploy_creates_new_project(self):
        mock_responses = {
            "GET /v9/projects/new-app": httpx.Response(
                404,
                json={"error": {"message": "Not found"}},
            ),
            "POST /v10/projects": httpx.Response(
                200,
                json={"id": "proj-new", "name": "new-app", "accountId": "user-123"},
            ),
            "POST /v13/deployments": httpx.Response(
                200,
                json={
                    "id": "deploy-1",
                    "url": "new-app-abc123.vercel.app",
                    "readyState": "QUEUED",
                },
            ),
        }

        skill = VercelSkill(token="test-token")
        skill._client = httpx.Client(
            transport=create_mock_transport(mock_responses),
            base_url=skill.API_BASE,
        )

        tools = skill.get_tools()
        deploy_tool = next(t for t in tools if t.name == "vercel_deploy")

        result = deploy_tool.invoke(
            {
                "project_name": "new-app",
                "git_repo": "https://github.com/user/new-repo",
            }
        )

        assert result.success is True

    def test_deploy_missing_credentials(self):
        skill = VercelSkill(token=None)
        tools = skill.get_tools()
        deploy_tool = next(t for t in tools if t.name == "vercel_deploy")

        result = deploy_tool.invoke(
            {
                "project_name": "my-app",
            }
        )

        assert result.success is False
        assert result.error == "MISSING_CREDENTIALS"


class TestVercelGetDeployments:
    def test_get_deployments_success(self):
        mock_response = httpx.Response(
            200,
            json={
                "deployments": [
                    {
                        "uid": "deploy-1",
                        "url": "my-app-abc123.vercel.app",
                        "state": "READY",
                        "created": "2024-01-01T00:00:00Z",
                        "target": "production",
                        "meta": {},
                    },
                    {
                        "uid": "deploy-2",
                        "url": "my-app-def456.vercel.app",
                        "state": "ERROR",
                        "created": "2024-01-02T00:00:00Z",
                        "target": "preview",
                        "meta": {},
                    },
                ]
            },
        )

        skill = VercelSkill(token="test-token")
        skill._client = httpx.Client(
            transport=create_mock_transport({"GET /v6/deployments": mock_response}),
            base_url=skill.API_BASE,
        )

        tools = skill.get_tools()
        get_deployments_tool = next(t for t in tools if t.name == "vercel_get_deployments")

        result = get_deployments_tool.invoke({"project_name": "my-app"})

        assert result.success is True
        assert len(result.data["deployments"]) == 2
        assert result.data["deployments"][0]["state"] == "READY"

    def test_get_deployments_with_state_filter(self):
        mock_response = httpx.Response(
            200,
            json={"deployments": []},
        )

        skill = VercelSkill(token="test-token")
        skill._client = httpx.Client(
            transport=create_mock_transport({"GET /v6/deployments": mock_response}),
            base_url=skill.API_BASE,
        )

        tools = skill.get_tools()
        get_deployments_tool = next(t for t in tools if t.name == "vercel_get_deployments")

        result = get_deployments_tool.invoke(
            {
                "project_name": "my-app",
                "state": "READY",
            }
        )

        assert result.success is True


class TestVercelErrorHandling:
    def test_api_error_handling(self):
        mock_response = httpx.Response(
            403,
            json={"error": {"message": "Forbidden"}},
        )

        skill = VercelSkill(token="test-token")
        skill._client = httpx.Client(
            transport=create_mock_transport({"GET /v9/projects": mock_response}),
            base_url=skill.API_BASE,
        )

        tools = skill.get_tools()
        list_projects_tool = next(t for t in tools if t.name == "vercel_list_projects")

        result = list_projects_tool.invoke({})

        assert result.success is False
        assert "Forbidden" in result.error or "403" in str(result.error)


class TestVercelSkillInstructions:
    def test_get_skill_instructions(self):
        skill = VercelSkill(token="test-token")
        instructions = skill.get_skill_instructions()

        assert instructions is not None
        assert "Vercel" in instructions
        assert "vercel_deploy" in instructions

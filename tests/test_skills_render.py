"""Tests for the Render deployment skill."""

from unittest.mock import patch

import httpx

from openops.models import RiskLevel
from openops.skills.render import RenderSkill


def create_mock_transport(responses: dict[str, httpx.Response]) -> httpx.MockTransport:
    """Create a mock transport that returns predefined responses based on URL patterns."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        method = request.method

        _key = f"{method} {path}"

        for pattern, response in responses.items():
            pattern_method, pattern_path = pattern.split(" ", 1) if " " in pattern else ("", pattern)
            if method == pattern_method and pattern_path in path:
                return response
            elif pattern_path in path and not pattern_method:
                return response

        return httpx.Response(404, json={"message": "Not found"})

    return httpx.MockTransport(handler)


class TestRenderSkillInit:
    def test_init_with_api_key(self):
        skill = RenderSkill(api_key="test-api-key")
        assert skill.api_key == "test-api-key"
        assert skill.validate_credentials() is True

    def test_init_without_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            skill = RenderSkill(api_key=None)
            assert skill.api_key is None
            assert skill.validate_credentials() is False

    def test_init_from_env_openops_api_key(self):
        with patch.dict("os.environ", {"OPENOPS_RENDER_API_KEY": "env-key"}, clear=True):
            skill = RenderSkill()
            assert skill.api_key == "env-key"

    def test_init_from_env_render_api_key(self):
        with patch.dict("os.environ", {"RENDER_API_KEY": "render-env-key"}, clear=True):
            skill = RenderSkill()
            assert skill.api_key == "render-env-key"


class TestRenderSkillMetadata:
    def test_get_metadata(self):
        skill = RenderSkill(api_key="test-api-key")
        metadata = skill.get_metadata()

        assert metadata.name == "render-deploy"
        assert metadata.description == "Deploy web services, static sites, and workers to Render"
        assert metadata.risk_level == RiskLevel.WRITE
        assert "deployment" in metadata.tags
        assert "render" in metadata.tags
        assert "OPENOPS_RENDER_API_KEY" in metadata.requires_credentials
        assert "render_deploy" in metadata.provides_tools
        assert "render_list_services" in metadata.provides_tools
        assert "render_get_deployments" in metadata.provides_tools

    def test_skill_attributes(self):
        skill = RenderSkill(api_key="test-api-key")

        assert skill.name == "render-deploy"
        assert skill.description == "Deploy web services, static sites, and workers to Render"
        assert skill.risk_level == RiskLevel.WRITE


class TestRenderSkillTools:
    def test_get_tools_returns_three_tools(self):
        skill = RenderSkill(api_key="test-api-key")
        tools = skill.get_tools()

        assert len(tools) == 3
        tool_names = [t.name for t in tools]
        assert "render_deploy" in tool_names
        assert "render_list_services" in tool_names
        assert "render_get_deployments" in tool_names


class TestRenderListServices:
    def test_list_services_success(self):
        mock_response = httpx.Response(
            200,
            json=[
                {
                    "service": {
                        "id": "srv-1",
                        "name": "my-api",
                        "type": "web_service",
                        "serviceDetails": {"url": "https://my-api.onrender.com"},
                        "suspended": "not_suspended",
                        "updatedAt": "2024-01-01T00:00:00Z",
                    }
                },
                {
                    "service": {
                        "id": "srv-2",
                        "name": "my-site",
                        "type": "static_site",
                        "serviceDetails": {"url": "https://my-site.onrender.com"},
                        "suspended": "not_suspended",
                        "updatedAt": "2024-01-02T00:00:00Z",
                    }
                },
            ],
        )

        skill = RenderSkill(api_key="test-api-key")
        skill._client = httpx.Client(
            transport=create_mock_transport({"GET /services": mock_response}),
            base_url=skill.API_BASE,
        )

        tools = skill.get_tools()
        list_services_tool = next(t for t in tools if t.name == "render_list_services")

        result = list_services_tool.invoke({})

        assert result.success is True
        assert result.data["total"] == 2
        assert result.data["services"][0]["name"] == "my-api"

    def test_list_services_with_type_filter(self):
        mock_response = httpx.Response(
            200,
            json=[
                {
                    "service": {
                        "id": "srv-1",
                        "name": "my-api",
                        "type": "web_service",
                        "serviceDetails": {"url": "https://my-api.onrender.com"},
                        "suspended": "not_suspended",
                        "updatedAt": "2024-01-01T00:00:00Z",
                    }
                }
            ],
        )

        skill = RenderSkill(api_key="test-api-key")
        skill._client = httpx.Client(
            transport=create_mock_transport({"GET /services": mock_response}),
            base_url=skill.API_BASE,
        )

        tools = skill.get_tools()
        list_services_tool = next(t for t in tools if t.name == "render_list_services")

        result = list_services_tool.invoke({"service_type": "web_service"})

        assert result.success is True

    def test_list_services_missing_credentials(self):
        skill = RenderSkill(api_key=None)
        tools = skill.get_tools()
        list_services_tool = next(t for t in tools if t.name == "render_list_services")

        result = list_services_tool.invoke({})

        assert result.success is False
        assert result.error == "MISSING_CREDENTIALS"


class TestRenderDeploy:
    def test_deploy_web_service(self):
        mock_response = httpx.Response(
            200,
            json={
                "service": {
                    "id": "srv-new",
                    "name": "my-new-api",
                    "type": "web_service",
                    "serviceDetails": {"url": "https://my-new-api.onrender.com"},
                    "suspended": "not_suspended",
                }
            },
        )

        skill = RenderSkill(api_key="test-api-key")
        skill._client = httpx.Client(
            transport=create_mock_transport({"POST /services": mock_response}),
            base_url=skill.API_BASE,
        )

        tools = skill.get_tools()
        deploy_tool = next(t for t in tools if t.name == "render_deploy")

        result = deploy_tool.invoke(
            {
                "service_name": "my-new-api",
                "service_type": "web_service",
                "git_repo": "https://github.com/user/repo",
            }
        )

        assert result.success is True
        assert result.data["service_id"] == "srv-new"
        assert result.data["type"] == "web_service"

    def test_deploy_static_site(self):
        mock_response = httpx.Response(
            200,
            json={
                "service": {
                    "id": "srv-static",
                    "name": "my-site",
                    "type": "static_site",
                    "serviceDetails": {"url": "https://my-site.onrender.com"},
                    "suspended": "not_suspended",
                }
            },
        )

        skill = RenderSkill(api_key="test-api-key")
        skill._client = httpx.Client(
            transport=create_mock_transport({"POST /services": mock_response}),
            base_url=skill.API_BASE,
        )

        tools = skill.get_tools()
        deploy_tool = next(t for t in tools if t.name == "render_deploy")

        result = deploy_tool.invoke(
            {
                "service_name": "my-site",
                "service_type": "static_site",
                "git_repo": "https://github.com/user/frontend",
                "build_command": "npm run build",
            }
        )

        assert result.success is True
        assert result.data["type"] == "static_site"

    def test_deploy_with_env_vars(self):
        mock_response = httpx.Response(
            200,
            json={
                "service": {
                    "id": "srv-new",
                    "name": "my-api",
                    "type": "web_service",
                    "serviceDetails": {"url": "https://my-api.onrender.com"},
                    "suspended": "not_suspended",
                }
            },
        )

        skill = RenderSkill(api_key="test-api-key")
        skill._client = httpx.Client(
            transport=create_mock_transport({"POST /services": mock_response}),
            base_url=skill.API_BASE,
        )

        tools = skill.get_tools()
        deploy_tool = next(t for t in tools if t.name == "render_deploy")

        result = deploy_tool.invoke(
            {
                "service_name": "my-api",
                "service_type": "web_service",
                "git_repo": "https://github.com/user/repo",
                "environment_variables": {"DATABASE_URL": "postgres://..."},
            }
        )

        assert result.success is True

    def test_deploy_invalid_service_type(self):
        skill = RenderSkill(api_key="test-api-key")
        tools = skill.get_tools()
        deploy_tool = next(t for t in tools if t.name == "render_deploy")

        result = deploy_tool.invoke(
            {
                "service_name": "my-api",
                "service_type": "invalid_type",
                "git_repo": "https://github.com/user/repo",
            }
        )

        assert result.success is False
        assert result.error == "INVALID_SERVICE_TYPE"

    def test_deploy_missing_credentials(self):
        skill = RenderSkill(api_key=None)
        tools = skill.get_tools()
        deploy_tool = next(t for t in tools if t.name == "render_deploy")

        result = deploy_tool.invoke(
            {
                "service_name": "my-api",
                "service_type": "web_service",
                "git_repo": "https://github.com/user/repo",
            }
        )

        assert result.success is False
        assert result.error == "MISSING_CREDENTIALS"


class TestRenderGetDeployments:
    def test_get_deployments_success(self):
        mock_response = httpx.Response(
            200,
            json=[
                {
                    "deploy": {
                        "id": "deploy-1",
                        "status": "live",
                        "commit": {"id": "abc123def", "message": "Add feature"},
                        "createdAt": "2024-01-01T00:00:00Z",
                        "finishedAt": "2024-01-01T00:05:00Z",
                    }
                },
                {
                    "deploy": {
                        "id": "deploy-2",
                        "status": "build_failed",
                        "commit": {"id": "def456ghi", "message": "Fix bug"},
                        "createdAt": "2024-01-02T00:00:00Z",
                        "finishedAt": None,
                    }
                },
            ],
        )

        skill = RenderSkill(api_key="test-api-key")
        skill._client = httpx.Client(
            transport=create_mock_transport({"GET /services/srv-1/deploys": mock_response}),
            base_url=skill.API_BASE,
        )

        tools = skill.get_tools()
        get_deployments_tool = next(t for t in tools if t.name == "render_get_deployments")

        result = get_deployments_tool.invoke({"service_id": "srv-1"})

        assert result.success is True
        assert len(result.data["deployments"]) == 2
        assert result.data["deployments"][0]["status"] == "live"
        assert result.data["deployments"][0]["commit"] == "abc123d"

    def test_get_deployments_missing_credentials(self):
        skill = RenderSkill(api_key=None)
        tools = skill.get_tools()
        get_deployments_tool = next(t for t in tools if t.name == "render_get_deployments")

        result = get_deployments_tool.invoke({"service_id": "srv-1"})

        assert result.success is False
        assert result.error == "MISSING_CREDENTIALS"


class TestRenderErrorHandling:
    def test_api_error_handling(self):
        mock_response = httpx.Response(
            401,
            json={"message": "Unauthorized"},
        )

        skill = RenderSkill(api_key="test-api-key")
        skill._client = httpx.Client(
            transport=create_mock_transport({"GET /services": mock_response}),
            base_url=skill.API_BASE,
        )

        tools = skill.get_tools()
        list_services_tool = next(t for t in tools if t.name == "render_list_services")

        result = list_services_tool.invoke({})

        assert result.success is False
        assert "Unauthorized" in result.error or "401" in str(result.error)


class TestRenderTriggerDeploy:
    def test_trigger_deploy_method(self):
        mock_response = httpx.Response(
            200,
            json={
                "deploy": {
                    "id": "deploy-new",
                    "status": "build_in_progress",
                }
            },
        )

        skill = RenderSkill(api_key="test-api-key")
        skill._client = httpx.Client(
            transport=create_mock_transport({"POST /services/srv-1/deploys": mock_response}),
            base_url=skill.API_BASE,
        )

        result = skill.trigger_deploy("srv-1")

        assert result.success is True
        assert result.data["deployment_id"] == "deploy-new"
        assert result.data["status"] == "build_in_progress"


class TestRenderSkillInstructions:
    def test_get_skill_instructions(self):
        skill = RenderSkill(api_key="test-api-key")
        instructions = skill.get_skill_instructions()

        assert instructions is not None
        assert "Render" in instructions
        assert "render_deploy" in instructions

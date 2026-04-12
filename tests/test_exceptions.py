"""Tests for OpenOps exceptions."""

import pytest

from openops.exceptions import (
    AnalysisError,
    ConfigurationError,
    CredentialError,
    DeploymentError,
    DeploymentFailedError,
    FrameworkDetectionError,
    OpenOpsError,
    PlatformAPIError,
    ProjectNotFoundError,
    ServiceNotFoundError,
    SkillError,
    SkillExecutionError,
    SkillNotFoundError,
    StorageError,
)


class TestExceptionHierarchy:
    def test_base_exception(self):
        with pytest.raises(OpenOpsError):
            raise OpenOpsError("Base error")

    def test_configuration_error_inheritance(self):
        error = ConfigurationError("Invalid config")
        assert isinstance(error, OpenOpsError)

    def test_credential_error_inheritance(self):
        error = CredentialError("Missing API key")
        assert isinstance(error, OpenOpsError)

    def test_skill_error_hierarchy(self):
        skill_error = SkillError("Skill error")
        not_found = SkillNotFoundError("Skill not found")
        execution = SkillExecutionError("Execution failed")

        assert isinstance(skill_error, OpenOpsError)
        assert isinstance(not_found, SkillError)
        assert isinstance(execution, SkillError)

    def test_storage_error_hierarchy(self):
        storage_error = StorageError("Storage error")
        project_not_found = ProjectNotFoundError("Project not found")
        service_not_found = ServiceNotFoundError("Service not found")

        assert isinstance(storage_error, OpenOpsError)
        assert isinstance(project_not_found, StorageError)
        assert isinstance(service_not_found, StorageError)

    def test_deployment_error_hierarchy(self):
        deployment_error = DeploymentError("Deployment error")
        failed = DeploymentFailedError("Deployment failed")

        assert isinstance(deployment_error, OpenOpsError)
        assert isinstance(failed, DeploymentError)

    def test_analysis_error_hierarchy(self):
        analysis_error = AnalysisError("Analysis error")
        framework_error = FrameworkDetectionError("Framework not detected")

        assert isinstance(analysis_error, OpenOpsError)
        assert isinstance(framework_error, AnalysisError)


class TestPlatformAPIError:
    def test_platform_api_error_message(self):
        error = PlatformAPIError(
            platform="vercel",
            message="Rate limit exceeded",
            status_code=429,
        )

        assert error.platform == "vercel"
        assert error.status_code == 429
        assert "[vercel]" in str(error)
        assert "Rate limit exceeded" in str(error)

    def test_platform_api_error_without_status(self):
        error = PlatformAPIError(
            platform="railway",
            message="Connection failed",
        )

        assert error.platform == "railway"
        assert error.status_code is None

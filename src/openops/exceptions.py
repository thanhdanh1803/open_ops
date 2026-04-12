"""Custom exceptions for OpenOps."""


class OpenOpsError(Exception):
    """Base exception for all OpenOps errors."""

    pass


class ConfigurationError(OpenOpsError):
    """Raised when there's a configuration problem."""

    pass


class CredentialError(OpenOpsError):
    """Raised when credentials are missing or invalid."""

    pass


class SkillError(OpenOpsError):
    """Base exception for skill-related errors."""

    pass


class SkillNotFoundError(SkillError):
    """Raised when a requested skill is not found."""

    pass


class SkillExecutionError(SkillError):
    """Raised when a skill fails to execute."""

    pass


class StorageError(OpenOpsError):
    """Base exception for storage-related errors."""

    pass


class ProjectNotFoundError(StorageError):
    """Raised when a project is not found in storage."""

    pass


class ServiceNotFoundError(StorageError):
    """Raised when a service is not found in storage."""

    pass


class DeploymentError(OpenOpsError):
    """Base exception for deployment-related errors."""

    pass


class DeploymentFailedError(DeploymentError):
    """Raised when a deployment fails."""

    pass


class PlatformAPIError(DeploymentError):
    """Raised when a platform API call fails."""

    def __init__(self, platform: str, message: str, status_code: int | None = None):
        self.platform = platform
        self.status_code = status_code
        super().__init__(f"[{platform}] {message}")


class AnalysisError(OpenOpsError):
    """Base exception for project analysis errors."""

    pass


class FrameworkDetectionError(AnalysisError):
    """Raised when framework detection fails."""

    pass

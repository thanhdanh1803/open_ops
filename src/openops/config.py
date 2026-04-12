"""Configuration management for OpenOps."""

import logging
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Global OpenOps configuration directory and env file
OPENOPS_DIR = Path.home() / ".openops"
OPENOPS_ENV_FILE = OPENOPS_DIR / ".env"

# Load environment variables from the OpenOps env file into os.environ
# This ensures LLM client libraries (OpenAI, Anthropic, etc.) can find API keys
if OPENOPS_ENV_FILE.exists():
    load_dotenv(OPENOPS_ENV_FILE)
    logger.debug(f"Loaded environment from {OPENOPS_ENV_FILE}")


class OpenOpsConfig(BaseSettings):
    """OpenOps configuration loaded from environment variables.

    All settings can be overridden via environment variables with the
    OPENOPS_ prefix (e.g., OPENOPS_MODEL_PROVIDER, OPENOPS_DATA_DIR).

    Configuration is loaded from ~/.openops/.env (created by 'openops init').
    """

    model_config = SettingsConfigDict(
        env_prefix="OPENOPS_",
        env_file=OPENOPS_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Model configuration
    model_provider: Literal["anthropic", "openai", "google", "deepseek"] = Field(
        default="anthropic",
        description="LLM provider to use",
    )
    model_name: str = Field(
        default="claude-sonnet-4-6",
        description="Model name for the selected provider",
    )
    model_temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Temperature for model responses",
    )
    model_max_tokens: int = Field(
        default=4096,
        gt=0,
        description="Maximum tokens for model responses",
    )

    # Data directory
    data_dir: Path = Field(
        default=Path("~/.openops"),
        description="Directory for OpenOps data storage",
    )

    # Platform credentials
    vercel_token: str | None = Field(
        default=None,
        description="Vercel API token",
    )
    railway_token: str | None = Field(
        default=None,
        description="Railway API token",
    )
    render_api_key: str | None = Field(
        default=None,
        description="Render API key",
    )

    # LLM provider API keys (read from standard env vars)
    anthropic_api_key: str | None = Field(
        default=None,
        validation_alias="ANTHROPIC_API_KEY",
        description="Anthropic API key",
    )
    openai_api_key: str | None = Field(
        default=None,
        validation_alias="OPENAI_API_KEY",
        description="OpenAI API key",
    )
    google_api_key: str | None = Field(
        default=None,
        validation_alias="GOOGLE_API_KEY",
        description="Google API key",
    )
    deepseek_api_key: str | None = Field(
        default=None,
        validation_alias="DEEPSEEK_API_KEY",
        description="DeepSeek API key",
    )
    # Behavior defaults
    default_platform: str = Field(
        default="vercel",
        description="Default deployment platform",
    )
    dry_run: bool = Field(
        default=False,
        description="Run in dry-run mode by default",
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode",
    )

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging level",
    )

    @field_validator("data_dir", mode="before")
    @classmethod
    def expand_data_dir(cls, v: str | Path) -> Path:
        """Expand user home directory in data_dir path."""
        return Path(v).expanduser()

    @property
    def memory_db_path(self) -> Path:
        """Path to the agent memory database."""
        return self.data_dir / "memory.db"

    @property
    def projects_db_path(self) -> Path:
        """Path to the projects database."""
        return self.data_dir / "projects.db"

    @property
    def checkpoints_db_path(self) -> Path:
        """Path to the checkpoints database."""
        return self.data_dir / "checkpoints.db"

    def ensure_data_dir(self) -> None:
        """Ensure the data directory exists."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Data directory ensured at {self.data_dir}")

    def get_llm_api_key(self) -> str | None:
        """Get the API key for the configured model provider."""
        key_map = {
            "anthropic": self.anthropic_api_key,
            "openai": self.openai_api_key,
            "google": self.google_api_key,
            "deepseek": self.deepseek_api_key,
        }
        return key_map.get(self.model_provider)

    def validate_llm_credentials(self) -> bool:
        """Check if credentials are configured for the selected LLM provider."""
        return self.get_llm_api_key() is not None


def get_config() -> OpenOpsConfig:
    """Get the OpenOps configuration.

    This is the recommended way to access configuration throughout the application.

    Returns:
        OpenOpsConfig instance loaded from environment
    """
    return OpenOpsConfig()


__all__ = ["OpenOpsConfig", "OPENOPS_DIR", "OPENOPS_ENV_FILE", "get_config"]

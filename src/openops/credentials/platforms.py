"""Platform configuration for credential management.

This module defines all supported platforms with their configuration,
including environment variable names, help URLs, and validators.

This is the SINGLE SOURCE OF TRUTH for platform configuration.
All CLI commands, prompts, and runtime behavior should derive from this registry.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openops.credentials.validators import ValidatorFunc


@dataclass
class PlatformConfig:
    """Configuration for a single platform.

    Attributes:
        name: Human-readable platform name (e.g., "Vercel")
        env_var: Environment variable name for the credential
        config_attr: Attribute name in OpenOpsConfig for this credential
        description: Short description of the platform
        help_url: URL to documentation for getting credentials
        category: "llm" or "deployment"
        tool_prefix: Prefix used for tool names (e.g., "vercel" -> "vercel_deploy")
        config_files: List of config file names this platform uses
        validator: Optional function to validate credentials
    """

    name: str
    env_var: str
    config_attr: str
    description: str
    help_url: str
    category: str  # "llm" or "deployment"
    tool_prefix: str = ""
    config_files: list[str] = field(default_factory=list)
    validator: "ValidatorFunc | None" = None


def _get_platforms() -> dict[str, PlatformConfig]:
    """Build platform configurations with validators.

    Validators are imported lazily to avoid circular imports
    and to defer heavy imports until actually needed.
    """
    from openops.credentials.validators import (
        validate_anthropic,
        validate_deepseek,
        validate_google,
        validate_openai,
        validate_railway,
        validate_render,
        validate_vercel,
    )

    return {
        "anthropic": PlatformConfig(
            name="Anthropic",
            env_var="ANTHROPIC_API_KEY",
            config_attr="anthropic_api_key",
            description="Anthropic LLM provider (Claude)",
            help_url="https://console.anthropic.com/settings/keys",
            category="llm",
            validator=validate_anthropic,
        ),
        "openai": PlatformConfig(
            name="OpenAI",
            env_var="OPENAI_API_KEY",
            config_attr="openai_api_key",
            description="OpenAI LLM provider",
            help_url="https://platform.openai.com/api-keys",
            category="llm",
            validator=validate_openai,
        ),
        "google": PlatformConfig(
            name="Google",
            env_var="GOOGLE_API_KEY",
            config_attr="google_api_key",
            description="Google AI LLM provider (Gemini)",
            help_url="https://aistudio.google.com/apikey",
            category="llm",
            validator=validate_google,
        ),
        "deepseek": PlatformConfig(
            name="DeepSeek",
            env_var="DEEPSEEK_API_KEY",
            config_attr="deepseek_api_key",
            description="DeepSeek LLM provider (DeepSeek-V3)",
            help_url="https://platform.deepseek.com/api_keys",
            category="llm",
            validator=validate_deepseek,
        ),
        "vercel": PlatformConfig(
            name="Vercel",
            env_var="OPENOPS_VERCEL_TOKEN",
            config_attr="vercel_token",
            description="Vercel deployment platform",
            help_url="https://vercel.com/account/tokens",
            category="deployment",
            tool_prefix="vercel",
            config_files=["vercel.json"],
            validator=validate_vercel,
        ),
        "railway": PlatformConfig(
            name="Railway",
            env_var="OPENOPS_RAILWAY_TOKEN",
            config_attr="railway_token",
            description="Railway deployment platform",
            help_url="https://railway.app/account/tokens",
            category="deployment",
            tool_prefix="railway",
            config_files=["railway.json", "railway.toml"],
            validator=validate_railway,
        ),
        "render": PlatformConfig(
            name="Render",
            env_var="OPENOPS_RENDER_API_KEY",
            config_attr="render_api_key",
            description="Render deployment platform",
            help_url="https://dashboard.render.com/u/settings#api-keys",
            category="deployment",
            tool_prefix="render",
            config_files=["render.yaml"],
            validator=validate_render,
        ),
    }


def get_platform(platform_id: str) -> PlatformConfig | None:
    """Get configuration for a specific platform."""
    return _get_platforms().get(platform_id.lower())


def get_all_platforms() -> dict[str, PlatformConfig]:
    """Get all platform configurations."""
    return _get_platforms()


def get_platforms_by_category(category: str) -> dict[str, PlatformConfig]:
    """Get platforms filtered by category (llm or deployment)."""
    return {k: v for k, v in _get_platforms().items() if v.category == category}


def get_llm_platforms() -> dict[str, PlatformConfig]:
    """Get all LLM provider platforms."""
    return get_platforms_by_category("llm")


def get_deployment_platforms() -> dict[str, PlatformConfig]:
    """Get all deployment platforms."""
    return get_platforms_by_category("deployment")


def get_deployment_platform_ids() -> list[str]:
    """Get list of valid deployment platform IDs (e.g., ['vercel', 'railway', 'render'])."""
    return list(get_deployment_platforms().keys())


def get_deployment_platform_names() -> list[str]:
    """Get list of deployment platform display names (e.g., ['Vercel', 'Railway', 'Render'])."""
    return [p.name for p in get_deployment_platforms().values()]


def build_interrupt_config() -> dict[str, bool]:
    """Build interrupt_on config dict from deployment platforms.

    Returns dict like {"vercel_deploy": True, "railway_deploy": True, ...}
    """
    return {
        f"{platform.tool_prefix}_deploy": True
        for platform in get_deployment_platforms().values()
        if platform.tool_prefix
    }


def get_platform_credential(platform_id: str, config: "OpenOpsConfig") -> str | None:
    """Get credential value for a platform from config.

    Args:
        platform_id: Platform identifier (e.g., "vercel")
        config: OpenOpsConfig instance

    Returns:
        Credential value or None if not configured
    """
    platform = get_platform(platform_id)
    if not platform:
        return None
    return getattr(config, platform.config_attr, None)


def get_platform_credentials_map(config: "OpenOpsConfig") -> dict[str, str | None]:
    """Build a map of platform_id -> credential value for all deployment platforms.

    Args:
        config: OpenOpsConfig instance

    Returns:
        Dict mapping platform IDs to their credential values
    """
    return {
        platform_id: getattr(config, platform.config_attr, None)
        for platform_id, platform in get_deployment_platforms().items()
    }


# Import at bottom to avoid circular import
if TYPE_CHECKING:
    from openops.config import OpenOpsConfig


__all__ = [
    "PlatformConfig",
    "build_interrupt_config",
    "get_all_platforms",
    "get_deployment_platform_ids",
    "get_deployment_platform_names",
    "get_deployment_platforms",
    "get_llm_platforms",
    "get_platform",
    "get_platform_credential",
    "get_platform_credentials_map",
    "get_platforms_by_category",
]

"""Credentials management for OpenOps.

This module provides platform configurations and validators for
managing credentials across LLM providers and deployment platforms.
"""

from openops.credentials.platforms import (
    PlatformConfig,
    get_all_platforms,
    get_deployment_platforms,
    get_llm_platforms,
    get_platform,
    get_platforms_by_category,
)
from openops.credentials.validators import (
    ValidationResult,
    ValidatorFunc,
    validate_anthropic,
    validate_deepseek,
    validate_google,
    validate_openai,
    validate_railway,
    validate_render,
    validate_vercel,
)

__all__ = [
    "PlatformConfig",
    "ValidationResult",
    "ValidatorFunc",
    "get_all_platforms",
    "get_deployment_platforms",
    "get_llm_platforms",
    "get_platform",
    "get_platforms_by_category",
    "validate_anthropic",
    "validate_deepseek",
    "validate_google",
    "validate_openai",
    "validate_railway",
    "validate_render",
    "validate_vercel",
]

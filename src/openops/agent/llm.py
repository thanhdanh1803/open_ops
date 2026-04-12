"""LLM factory for OpenOps agents.

Supports multiple LLM providers (Anthropic, OpenAI, Google) based on configuration.
"""

import logging
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from openops.config import OpenOpsConfig
from openops.exceptions import ConfigurationError, CredentialError

logger = logging.getLogger(__name__)

ModelProvider = Literal["anthropic", "openai", "google"]


def get_model_string(config: OpenOpsConfig) -> str:
    """Get the model string in 'provider:model' format for Deep Agents.

    Args:
        config: OpenOps configuration

    Returns:
        Model string like 'anthropic:claude-sonnet-4-5'
    """
    return f"{config.model_provider}:{config.model_name}"


def create_llm(config: OpenOpsConfig) -> BaseChatModel:
    """Create an LLM instance based on configuration.

    Args:
        config: OpenOps configuration containing provider and model settings

    Returns:
        Configured LangChain chat model instance

    Raises:
        CredentialError: If required API key is not configured
        ConfigurationError: If provider is not supported
    """
    provider = config.model_provider
    model_name = config.model_name
    api_key = config.get_llm_api_key()

    if not api_key:
        raise CredentialError(
            f"API key for provider '{provider}' is not configured. "
            f"Set the appropriate environment variable (e.g., ANTHROPIC_API_KEY)."
        )

    logger.info(f"Creating LLM: provider={provider}, model={model_name}")

    if provider == "anthropic":
        return ChatAnthropic(
            model=model_name,
            api_key=api_key,
            temperature=config.model_temperature,
            max_tokens=config.model_max_tokens,
        )
    elif provider == "openai":
        # Use chat completions API (more widely compatible)
        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
            temperature=config.model_temperature,
            max_tokens=config.model_max_tokens,
            use_responses_api=False,
        )
    elif provider == "google":
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=config.model_temperature,
            max_output_tokens=config.model_max_tokens,
        )
    else:
        raise ConfigurationError(
            f"Unsupported model provider: '{provider}'. " f"Supported providers: anthropic, openai, google"
        )


def validate_llm_config(config: OpenOpsConfig) -> bool:
    """Validate that LLM configuration is complete.

    Args:
        config: OpenOps configuration

    Returns:
        True if configuration is valid

    Raises:
        CredentialError: If API key is missing
        ConfigurationError: If provider is unsupported
    """
    if config.model_provider not in ("anthropic", "openai", "google"):
        raise ConfigurationError(f"Unsupported model provider: '{config.model_provider}'")

    if not config.get_llm_api_key():
        raise CredentialError(f"API key for provider '{config.model_provider}' is not configured")

    logger.debug(f"LLM config validated: provider={config.model_provider}, " f"model={config.model_name}")
    return True


__all__ = ["create_llm", "get_model_string", "validate_llm_config", "ModelProvider"]

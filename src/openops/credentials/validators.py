"""Credential validators for various platforms.

Each validator function takes a token and returns a ValidationResult
indicating whether the credentials are valid.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a credential validation attempt."""

    valid: bool
    message: str | None = None
    details: dict | None = None


ValidatorFunc = Callable[[str], ValidationResult]


def validate_anthropic(token: str) -> ValidationResult:
    """Validate Anthropic API key by making a minimal API call."""
    try:
        from langchain_anthropic import ChatAnthropic

        llm = ChatAnthropic(model="claude-haiku-4-5", api_key=token, max_tokens=10)
        llm.invoke("Hi")
        return ValidationResult(valid=True, message="Credentials are valid")
    except Exception as e:
        logger.debug(f"Anthropic validation failed: {e}")
        return ValidationResult(valid=False, message=str(e))


def validate_openai(token: str) -> ValidationResult:
    """Validate OpenAI API key by making a minimal API call."""
    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(model="gpt-4.1-nano", api_key=token, max_tokens=10)
        llm.invoke("Hi")
        return ValidationResult(valid=True, message="Credentials are valid")
    except Exception as e:
        logger.debug(f"OpenAI validation failed: {e}")
        return ValidationResult(valid=False, message=str(e))


def validate_google(token: str) -> ValidationResult:
    """Validate Google AI API key by making a minimal API call."""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", api_key=token, max_output_tokens=10)
        llm.invoke("Hi")
        return ValidationResult(valid=True, message="Credentials are valid")
    except Exception as e:
        logger.debug(f"Google validation failed: {e}")
        return ValidationResult(valid=False, message=str(e))


def validate_deepseek(token: str) -> ValidationResult:
    """Validate DeepSeek API key by making a minimal API call.

    DeepSeek uses an OpenAI-compatible API, so we use langchain_openai
    with a custom base_url.
    """
    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model="deepseek-chat",
            api_key=token,
            base_url="https://api.deepseek.com",
            max_tokens=10,
        )
        llm.invoke("Hi")
        return ValidationResult(valid=True, message="Credentials are valid")
    except Exception as e:
        logger.debug(f"DeepSeek validation failed: {e}")
        return ValidationResult(valid=False, message=str(e))


def validate_vercel(token: str) -> ValidationResult:
    """Validate Vercel token by checking user endpoint."""
    try:
        import httpx

        response = httpx.get(
            "https://api.vercel.com/v2/user",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        if response.status_code == 200:
            data = response.json()
            username = data.get("user", {}).get("username", "unknown")
            return ValidationResult(
                valid=True,
                message="Credentials are valid",
                details={"username": username},
            )
        return ValidationResult(
            valid=False,
            message=f"API returned status {response.status_code}",
        )
    except Exception as e:
        logger.debug(f"Vercel validation failed: {e}")
        return ValidationResult(valid=False, message=str(e))


def validate_railway(token: str) -> ValidationResult:
    """Validate Railway token by querying user info."""
    try:
        import httpx

        response = httpx.post(
            "https://backboard.railway.app/graphql/v2",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": "{ me { id name } }"},
            timeout=10.0,
        )
        if response.status_code == 200:
            data = response.json()
            if "errors" not in data:
                name = data.get("data", {}).get("me", {}).get("name", "unknown")
                return ValidationResult(
                    valid=True,
                    message="Credentials are valid",
                    details={"name": name},
                )
            return ValidationResult(
                valid=False,
                message=data["errors"][0].get("message", "Unknown error"),
            )
        return ValidationResult(
            valid=False,
            message=f"API returned status {response.status_code}",
        )
    except Exception as e:
        logger.debug(f"Railway validation failed: {e}")
        return ValidationResult(valid=False, message=str(e))


def validate_render(token: str) -> ValidationResult:
    """Validate Render API key by listing owners."""
    try:
        import httpx

        response = httpx.get(
            "https://api.render.com/v1/owners",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        if response.status_code == 200:
            return ValidationResult(valid=True, message="Credentials are valid")
        return ValidationResult(
            valid=False,
            message=f"API returned status {response.status_code}",
        )
    except Exception as e:
        logger.debug(f"Render validation failed: {e}")
        return ValidationResult(valid=False, message=str(e))


__all__ = [
    "ValidationResult",
    "ValidatorFunc",
    "validate_anthropic",
    "validate_deepseek",
    "validate_google",
    "validate_openai",
    "validate_railway",
    "validate_render",
    "validate_vercel",
]

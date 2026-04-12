"""Tests for OpenOps LLM factory."""

import os
from unittest.mock import patch

import pytest

from openops.agent.llm import (
    create_llm,
    get_model_string,
    validate_llm_config,
)
from openops.config import OpenOpsConfig
from openops.exceptions import CredentialError


class TestGetModelString:
    def test_anthropic_model_string(self):
        with patch.dict(os.environ, {}, clear=True):
            config = OpenOpsConfig(
                model_provider="anthropic",
                model_name="claude-sonnet-4-5",
            )
        assert get_model_string(config) == "anthropic:claude-sonnet-4-5"

    def test_openai_model_string(self):
        with patch.dict(os.environ, {}, clear=True):
            config = OpenOpsConfig(
                model_provider="openai",
                model_name="gpt-4o",
            )
        assert get_model_string(config) == "openai:gpt-4o"

    def test_google_model_string(self):
        with patch.dict(os.environ, {}, clear=True):
            config = OpenOpsConfig(
                model_provider="google",
                model_name="gemini-pro",
            )
        assert get_model_string(config) == "google:gemini-pro"


class TestCreateLLM:
    def test_create_anthropic_llm(self):
        env = {"ANTHROPIC_API_KEY": "sk-ant-test-key"}
        with patch.dict(os.environ, env, clear=True):
            config = OpenOpsConfig(
                model_provider="anthropic",
                model_name="claude-sonnet-4-5",
                model_temperature=0.2,
                model_max_tokens=2048,
            )
            llm = create_llm(config)

        assert llm is not None
        assert llm.model == "claude-sonnet-4-5"
        assert llm.temperature == 0.2
        assert llm.max_tokens == 2048

    def test_create_openai_llm(self):
        env = {"OPENAI_API_KEY": "sk-openai-test-key"}
        with patch.dict(os.environ, env, clear=True):
            config = OpenOpsConfig(
                model_provider="openai",
                model_name="gpt-4o",
                model_temperature=0.1,
            )
            llm = create_llm(config)

        assert llm is not None
        assert llm.model_name == "gpt-4o"

    def test_create_google_llm(self):
        env = {"GOOGLE_API_KEY": "google-test-key"}
        with patch.dict(os.environ, env, clear=True):
            config = OpenOpsConfig(
                model_provider="google",
                model_name="gemini-pro",
            )
            llm = create_llm(config)

        assert llm is not None
        assert llm.model == "gemini-pro"

    def test_missing_api_key_raises_error(self):
        with patch.dict(os.environ, {}, clear=True):
            config = OpenOpsConfig(model_provider="anthropic")

        with pytest.raises(CredentialError) as exc_info:
            create_llm(config)

        assert "API key for provider 'anthropic'" in str(exc_info.value)


class TestValidateLLMConfig:
    def test_valid_anthropic_config(self):
        env = {"ANTHROPIC_API_KEY": "sk-ant-test"}
        with patch.dict(os.environ, env, clear=True):
            config = OpenOpsConfig(model_provider="anthropic")
            assert validate_llm_config(config) is True

    def test_valid_openai_config(self):
        env = {"OPENAI_API_KEY": "sk-openai-test"}
        with patch.dict(os.environ, env, clear=True):
            config = OpenOpsConfig(model_provider="openai")
            assert validate_llm_config(config) is True

    def test_valid_google_config(self):
        env = {"GOOGLE_API_KEY": "google-test"}
        with patch.dict(os.environ, env, clear=True):
            config = OpenOpsConfig(model_provider="google")
            assert validate_llm_config(config) is True

    def test_missing_credentials_raises_error(self):
        with patch.dict(os.environ, {}, clear=True):
            config = OpenOpsConfig(model_provider="anthropic")

        with pytest.raises(CredentialError):
            validate_llm_config(config)

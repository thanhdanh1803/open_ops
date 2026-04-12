"""Tests for OpenOps configuration."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from openops.config import OpenOpsConfig, get_config


class TestOpenOpsConfig:
    def test_default_values(self):
        with patch.dict(os.environ, {}, clear=True):
            config = OpenOpsConfig()

        assert config.model_provider == "anthropic"
        assert config.model_name == "claude-sonnet-4-5"
        assert config.model_temperature == 0.1
        assert config.model_max_tokens == 4096
        assert config.default_platform == "vercel"
        assert config.dry_run is False
        assert config.debug is False
        assert config.log_level == "INFO"

    def test_data_dir_expansion(self):
        with patch.dict(os.environ, {}, clear=True):
            config = OpenOpsConfig()

        assert "~" not in str(config.data_dir)
        assert config.data_dir == Path.home() / ".openops"

    def test_env_override(self):
        env = {
            "OPENOPS_MODEL_PROVIDER": "openai",
            "OPENOPS_MODEL_NAME": "gpt-4o",
            "OPENOPS_DRY_RUN": "true",
            "OPENOPS_DEBUG": "true",
        }
        with patch.dict(os.environ, env, clear=True):
            config = OpenOpsConfig()

        assert config.model_provider == "openai"
        assert config.model_name == "gpt-4o"
        assert config.dry_run is True
        assert config.debug is True

    def test_platform_credentials(self):
        env = {
            "OPENOPS_VERCEL_TOKEN": "vercel-token-123",
            "OPENOPS_RAILWAY_TOKEN": "railway-token-456",
            "OPENOPS_RENDER_API_KEY": "render-key-789",
        }
        with patch.dict(os.environ, env, clear=True):
            config = OpenOpsConfig()

        assert config.vercel_token == "vercel-token-123"
        assert config.railway_token == "railway-token-456"
        assert config.render_api_key == "render-key-789"

    def test_llm_api_keys(self):
        env = {
            "ANTHROPIC_API_KEY": "sk-ant-123",
            "OPENAI_API_KEY": "sk-openai-456",
            "GOOGLE_API_KEY": "google-789",
        }
        with patch.dict(os.environ, env, clear=True):
            config = OpenOpsConfig()

        assert config.anthropic_api_key == "sk-ant-123"
        assert config.openai_api_key == "sk-openai-456"
        assert config.google_api_key == "google-789"

    def test_get_llm_api_key(self):
        env = {
            "ANTHROPIC_API_KEY": "sk-ant-123",
            "OPENAI_API_KEY": "sk-openai-456",
        }
        with patch.dict(os.environ, env, clear=True):
            config = OpenOpsConfig(model_provider="anthropic")
            assert config.get_llm_api_key() == "sk-ant-123"

            config = OpenOpsConfig(model_provider="openai")
            assert config.get_llm_api_key() == "sk-openai-456"

    def test_validate_llm_credentials(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-123"}, clear=True):
            config = OpenOpsConfig(model_provider="anthropic")
            assert config.validate_llm_credentials() is True

        with patch.dict(os.environ, {}, clear=True):
            config = OpenOpsConfig(model_provider="anthropic")
            assert config.validate_llm_credentials() is False

    def test_db_paths(self):
        with patch.dict(os.environ, {}, clear=True):
            config = OpenOpsConfig()

        assert config.memory_db_path == config.data_dir / "memory.db"
        assert config.projects_db_path == config.data_dir / "projects.db"
        assert config.checkpoints_db_path == config.data_dir / "checkpoints.db"

    def test_temperature_validation(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError):
                OpenOpsConfig(model_temperature=2.5)

            with pytest.raises(ValueError):
                OpenOpsConfig(model_temperature=-0.1)


class TestGetConfig:
    def test_get_config_returns_instance(self):
        config = get_config()
        assert isinstance(config, OpenOpsConfig)

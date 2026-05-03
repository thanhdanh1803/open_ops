"""Tests for Langfuse tracing integration helpers."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from openops.agent.tracing.langfuse_tracing import build_langfuse_run_config, flush_langfuse
from openops.config import OpenOpsConfig


class TestLangfuseTracing:
    def test_build_run_config_sets_langfuse_metadata(self):
        with patch.dict(os.environ, {}, clear=True):
            config = OpenOpsConfig(
                _env_file=None,
                langfuse_enabled=True,
                LANGFUSE_PUBLIC_KEY="pk",
                LANGFUSE_SECRET_KEY="sk",
                LANGFUSE_HOST="http://langfuse.local",
                LANGFUSE_SAMPLE_RATE="1.0",
            )

        mock_handler = MagicMock()
        with (
            patch("langfuse.langchain.CallbackHandler", return_value=mock_handler),
            patch(
                "openops.agent.tracing.langfuse_tracing._ensure_langfuse_client",
                return_value=True,
            ),
        ):
            cfg = build_langfuse_run_config(config, operation="invoke", thread_id="t1")

        assert cfg["callbacks"] == [mock_handler]
        assert cfg["metadata"]["langfuse_session_id"] == "t1"
        assert isinstance(cfg["metadata"]["langfuse_tags"], list)
        assert "openops" in cfg["metadata"]["langfuse_tags"]
        assert cfg["run_name"] == "openops.invoke"

    def test_flush_langfuse_is_noop_when_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            config = OpenOpsConfig(_env_file=None, langfuse_enabled=False, langfuse_flush=True)
        with patch("langfuse.get_client") as get_client:
            flush_langfuse(config)
        get_client.assert_not_called()

    def test_flush_langfuse_calls_client_when_enabled(self):
        with patch.dict(os.environ, {}, clear=True):
            config = OpenOpsConfig(
                _env_file=None,
                langfuse_enabled=True,
                langfuse_flush=True,
                LANGFUSE_PUBLIC_KEY="pk",
                LANGFUSE_SECRET_KEY="sk",
            )
        client = MagicMock()
        with patch("langfuse.get_client", return_value=client):
            flush_langfuse(config)
        client.flush.assert_called_once()

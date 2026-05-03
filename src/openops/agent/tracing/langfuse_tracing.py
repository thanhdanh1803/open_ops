"""Langfuse tracing helpers for orchestrator invocations."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from openops.config import OpenOpsConfig

logger = logging.getLogger(__name__)


def _truthy_env(name: str) -> bool:
    v = os.getenv(name)
    if v is None:
        return False
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


def _is_langfuse_enabled_from_env() -> bool:
    # `observe` decorators are applied at import time in multiple modules.
    # We gate them using the same env vars that drive OpenOpsConfig.
    return _truthy_env("OPENOPS_LANGFUSE_ENABLED") or _truthy_env("LANGFUSE_ENABLED")


def observe(*args: Any, **kwargs: Any):  # type: ignore
    """Gated Langfuse `@observe` decorator.

    When tracing is disabled, this is a no-op decorator so we don't emit spans
    just because Langfuse credentials exist in the environment.
    """

    def decorator(fn):
        if not _is_langfuse_enabled_from_env():
            return fn
        try:
            from langfuse.decorators import observe as lf_observe  # type: ignore
        except Exception:  # pragma: no cover - optional dependency / runtime env
            return fn
        return lf_observe(*args, **kwargs)(fn)

    return decorator


def _ensure_langfuse_client(config: OpenOpsConfig) -> bool:
    """Initialize Langfuse client singleton for v3+ SDKs."""
    try:
        from langfuse import Langfuse  # type: ignore[import-not-found]
    except ImportError:
        logger.warning("Langfuse package is not installed; tracing is disabled")
        return False

    # Creating Langfuse multiple times is safe; the SDK uses a singleton client.
    try:
        Langfuse(
            public_key=config.langfuse_public_key,
            secret_key=config.langfuse_secret_key,
            host=config.langfuse_host,
            sample_rate=config.langfuse_sample_rate,
            tracing_enabled=True,
        )
        return True
    except TypeError:
        # Older/newer SDK variants may use base_url instead of host, etc.
        try:
            Langfuse(
                public_key=config.langfuse_public_key,
                secret_key=config.langfuse_secret_key,
                base_url=config.langfuse_host,
                sample_rate=config.langfuse_sample_rate,
                tracing_enabled=True,
            )
            return True
        except Exception as exc:  # pragma: no cover - defensive branch
            logger.warning("Failed to initialize Langfuse client: %s", exc)
            return False
    except Exception as exc:  # pragma: no cover - defensive branch
        logger.warning("Failed to initialize Langfuse client: %s", exc)
        return False


def _create_langfuse_handler(
    config: OpenOpsConfig,
    *,
    trace_name: str,
    thread_id: str,
) -> Any | None:
    """Create a Langfuse LangChain callback handler if tracing is enabled."""
    if not config.langfuse_enabled:
        logger.debug("Langfuse tracing disabled via config")
        return None

    if not config.langfuse_public_key or not config.langfuse_secret_key:
        logger.warning("Langfuse tracing enabled but credentials are missing")
        return None

    try:
        from langfuse.langchain import CallbackHandler  # type: ignore[import-not-found]
    except ImportError:
        logger.warning("Langfuse package is not installed; tracing is disabled")
        return None
    if not _ensure_langfuse_client(config):
        return None

    # Langfuse v3+ (incl. current v4) expects the client to be configured
    # separately; the handler mostly carries trace context overrides.
    try:
        _handler = CallbackHandler(public_key=config.langfuse_public_key)
        logger.debug("Initialized Langfuse callback handler for %s (thread_id=%s)", trace_name, thread_id)
        return _handler
    except Exception as exc:  # pragma: no cover - defensive branch
        logger.warning("Failed to initialize Langfuse callback handler: %s", exc)
        return None


def build_langfuse_run_config(
    config: OpenOpsConfig,
    *,
    operation: str,
    thread_id: str,
    working_directory: Path | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build invoke config overrides that enable per-run Langfuse tracing."""
    trace_name = f"openops.{operation}"
    handler = _create_langfuse_handler(
        config,
        trace_name=trace_name,
        thread_id=thread_id,
    )
    if handler is None:
        return {}

    tags = [
        "openops",
        f"operation:{operation}",
        f"provider:{config.model_provider}",
    ]

    metadata: dict[str, Any] = {
        "operation": operation,
        "thread_id": thread_id,
        "model_provider": config.model_provider,
        "model_name": config.model_name,
        # Langfuse v3+ trace attributes via RunnableConfig.metadata
        "langfuse_session_id": thread_id,
        "langfuse_tags": tags,
        # Best-effort: name the root trace (support varies by SDK version)
        "langfuse_trace_name": trace_name,
    }
    if working_directory is not None:
        metadata["working_directory"] = str(working_directory)
    if extra_metadata:
        metadata.update(extra_metadata)

    logger.debug("Langfuse tracing enabled for %s (thread_id=%s)", operation, thread_id)
    return {
        "callbacks": [handler],
        "metadata": metadata,
        "tags": tags,
        "run_name": trace_name,
    }


def flush_langfuse(config: OpenOpsConfig) -> None:
    """Flush queued Langfuse events (useful for short-lived CLI runs)."""
    if not config.langfuse_enabled or not config.langfuse_flush:
        return
    try:
        from langfuse import get_client  # type: ignore[import-not-found]
    except ImportError:
        return
    try:
        get_client().flush()
    except Exception as exc:  # pragma: no cover - defensive branch
        logger.debug("Langfuse flush failed: %s", exc)


__all__ = ["build_langfuse_run_config", "flush_langfuse", "observe"]

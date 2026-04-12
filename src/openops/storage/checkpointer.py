"""Checkpointer configuration and factory for LangGraph agent state persistence.

This module provides a configurable way to create checkpointers for LangGraph agents.
Currently supports SQLite, with the architecture designed to support additional
backends (PostgreSQL, Redis, etc.) in the future.
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite import SqliteSaver

logger = logging.getLogger(__name__)

CheckpointerType = Literal["sqlite"]


class CheckpointerFactory(ABC):
    """Abstract factory for creating checkpointers."""

    @abstractmethod
    def create(self) -> BaseCheckpointSaver:
        """Create and return a checkpointer instance."""
        pass


class SqliteCheckpointerFactory(CheckpointerFactory):
    """Factory for creating SQLite-based checkpointers."""

    def __init__(self, db_path: str | Path):
        """Initialize the factory.

        Args:
            db_path: Path to the SQLite database file for checkpoints.
        """
        self.db_path = Path(db_path).expanduser()

    def create(self) -> SqliteSaver:
        """Create a SQLite checkpointer.

        Returns:
            Configured SqliteSaver instance.
        """
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        checkpointer = SqliteSaver.from_conn_string(str(self.db_path))
        logger.debug(f"Created SQLite checkpointer at {self.db_path}")
        return checkpointer


def get_checkpointer(
    checkpointer_type: CheckpointerType = "sqlite",
    db_path: str | Path | None = None,
    **kwargs,
) -> BaseCheckpointSaver:
    """Factory function to create a checkpointer based on configuration.

    This is the primary entry point for obtaining a checkpointer. It supports
    dependency injection by allowing the checkpointer type and configuration
    to be specified at runtime.

    Args:
        checkpointer_type: Type of checkpointer to create. Currently only "sqlite"
            is supported.
        db_path: Path to the database file (required for sqlite).
        **kwargs: Additional arguments passed to the checkpointer factory.

    Returns:
        A configured checkpointer instance.

    Raises:
        ValueError: If checkpointer_type is not supported or required args are missing.

    Example:
        >>> from openops.config import get_config
        >>> config = get_config()
        >>> checkpointer = get_checkpointer(
        ...     checkpointer_type="sqlite",
        ...     db_path=config.checkpoints_db_path
        ... )
    """
    if checkpointer_type == "sqlite":
        if db_path is None:
            raise ValueError("db_path is required for sqlite checkpointer")
        factory = SqliteCheckpointerFactory(db_path)
        return factory.create()

    raise ValueError(f"Unsupported checkpointer type: {checkpointer_type}")


def get_checkpointer_from_config(config) -> BaseCheckpointSaver:
    """Create a checkpointer using OpenOpsConfig.

    This is a convenience function that reads configuration from an
    OpenOpsConfig instance and creates the appropriate checkpointer.

    Args:
        config: OpenOpsConfig instance with checkpointer settings.

    Returns:
        A configured checkpointer instance.

    Example:
        >>> from openops.config import get_config
        >>> config = get_config()
        >>> checkpointer = get_checkpointer_from_config(config)
    """
    config.ensure_data_dir()
    return get_checkpointer(
        checkpointer_type="sqlite",
        db_path=config.checkpoints_db_path,
    )


__all__ = [
    "CheckpointerFactory",
    "CheckpointerType",
    "SqliteCheckpointerFactory",
    "get_checkpointer",
    "get_checkpointer_from_config",
]

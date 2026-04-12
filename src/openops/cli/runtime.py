"""Runtime factory for CLI commands.

Provides a unified way to create the OpenOps runtime with all components
wired together (config, storage, orchestrator).
"""

import logging
import sqlite3
import uuid
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from openops.agent.orchestrator import OrchestratorRuntime
from openops.config import OpenOpsConfig, get_config
from openops.storage.sqlite_store import SqliteProjectStore

logger = logging.getLogger(__name__)

THREAD_ID_FILE = "current_thread.txt"


class OpenOpsRuntime:
    """High-level runtime that wraps orchestrator with storage and config.

    This class provides a convenient interface for CLI commands to interact
    with the OpenOps agent system.
    """

    def __init__(
        self,
        config: OpenOpsConfig | None = None,
        working_directory: Path | None = None,
    ):
        """Initialize the OpenOps runtime.

        Args:
            config: Configuration instance. If None, loads from environment.
            working_directory: Project directory for file operations.
        """
        self.config = config or get_config()
        self.working_directory = working_directory or Path.cwd()

        self.config.ensure_data_dir()

        self._project_store = SqliteProjectStore(self.config.projects_db_path)

        # Create SQLite connection for checkpointer (must stay open for runtime lifetime)
        self._checkpoint_conn = sqlite3.connect(
            str(self.config.checkpoints_db_path),
            check_same_thread=False,
        )
        self._checkpointer = SqliteSaver(self._checkpoint_conn)

        self._orchestrator = OrchestratorRuntime(
            config=self.config,
            project_store=self._project_store,
            checkpointer=self._checkpointer,
            working_directory=self.working_directory,
        )

        logger.info(f"OpenOpsRuntime initialized for {self.working_directory}")

    @property
    def orchestrator(self) -> OrchestratorRuntime:
        """Access the orchestrator runtime."""
        return self._orchestrator

    @property
    def project_store(self) -> SqliteProjectStore:
        """Access the project store."""
        return self._project_store

    def invoke(self, message: str, thread_id: str) -> dict:
        """Send a message to the agent.

        Args:
            message: User message
            thread_id: Conversation thread ID

        Returns:
            Agent response dictionary
        """
        return self._orchestrator.invoke(message, thread_id)

    def get_state(self, thread_id: str):
        """Get current state for a thread (useful for checking interrupts)."""
        return self._orchestrator.get_state(thread_id)

    def resume(
        self,
        thread_id: str,
        decision: str,
        message: str | None = None,
        edited_action: dict | None = None,
    ) -> dict:
        """Resume execution after an interrupt.

        Args:
            thread_id: Conversation thread ID
            decision: One of "approve", "reject", or "edit"
            message: Optional message for reject decisions
            edited_action: Modified action for edit decisions

        Returns:
            Agent response after resuming
        """
        return self._orchestrator.resume(
            thread_id=thread_id,
            decision=decision,
            message=message,
            edited_action=edited_action,
        )

    def close(self) -> None:
        """Clean up resources."""
        self._project_store.close()
        self._checkpoint_conn.close()
        logger.debug("OpenOpsRuntime closed")


def get_or_create_thread_id(data_dir: Path, new: bool = False) -> str:
    """Get existing thread ID or create a new one.

    Args:
        data_dir: Directory to store thread ID file
        new: If True, always create a new thread ID

    Returns:
        Thread ID string
    """
    thread_file = data_dir / THREAD_ID_FILE

    if not new and thread_file.exists():
        thread_id = thread_file.read_text().strip()
        if thread_id:
            logger.debug(f"Using existing thread: {thread_id}")
            return thread_id

    thread_id = str(uuid.uuid4())
    thread_file.write_text(thread_id)
    logger.debug(f"Created new thread: {thread_id}")
    return thread_id


def create_runtime(
    working_directory: Path | None = None,
    config: OpenOpsConfig | None = None,
) -> OpenOpsRuntime:
    """Factory function to create an OpenOps runtime.

    Args:
        working_directory: Project directory (defaults to cwd)
        config: Configuration (defaults to loading from environment)

    Returns:
        Configured OpenOpsRuntime instance
    """
    return OpenOpsRuntime(
        config=config,
        working_directory=working_directory,
    )


__all__ = ["OpenOpsRuntime", "create_runtime", "get_or_create_thread_id"]

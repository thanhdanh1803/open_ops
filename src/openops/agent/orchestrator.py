"""OpenOps Orchestrator Agent.

The main agent that handles user interactions and delegates to specialized
subagents for complex operations.
"""

import logging
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore

from openops.agent.llm import get_model_string
from openops.agent.prompts import ORCHESTRATOR_PROMPT
from openops.agent.subagents import create_all_subagents
from openops.agent.tools import create_project_knowledge_tools
from openops.config import OpenOpsConfig
from openops.storage.base import ProjectStoreBase

logger = logging.getLogger(__name__)


def create_orchestrator(
    config: OpenOpsConfig,
    project_store: ProjectStoreBase,
    checkpointer: BaseCheckpointSaver | None = None,
    store: BaseStore | None = None,
    working_directory: str | Path | None = None,
    skill_directories: list[str] | None = None,
    memory_files: list[str] | None = None,
    additional_tools: list | None = None,
) -> Any:
    """Create the main OpenOps orchestrator agent.

    The orchestrator is the primary agent that:
    - Handles all user conversations
    - Delegates to specialized subagents (analyzer, deploy, monitor)
    - Manages project knowledge via custom tools
    - Requires approval for deployment operations

    Args:
        config: OpenOps configuration
        project_store: Storage backend for project knowledge (dependency injection)
        checkpointer: LangGraph checkpointer for conversation persistence.
            Defaults to MemorySaver if not provided.
        store: LangGraph store for cross-thread memory.
            Defaults to InMemoryStore if not provided.
        working_directory: Root directory for filesystem operations.
            Defaults to current directory.
        skill_directories: Directories containing skills to load.
            Defaults to ["~/.openops/skills/", "./skills/"].
        memory_files: Memory files to load (e.g., AGENTS.md).
        additional_tools: Extra tools to provide to the orchestrator.

    Returns:
        Configured Deep Agent instance
    """
    logger.info("Creating OpenOps orchestrator agent")

    checkpointer = checkpointer or MemorySaver()
    store = store or InMemoryStore()
    working_directory = Path(working_directory) if working_directory else Path(".")

    if skill_directories is None:
        skill_directories = [
            str(Path.home() / ".openops" / "skills"),
            "./skills/",
        ]

    model_string = get_model_string(config)
    logger.debug(f"Using model: {model_string}")

    project_tools = create_project_knowledge_tools(project_store)
    tools = project_tools + (additional_tools or [])
    logger.debug(f"Loaded {len(tools)} custom tools")

    subagents = create_all_subagents(
        model=model_string,
        skill_directories=skill_directories,
    )
    logger.debug(f"Configured {len(subagents)} subagents")

    backend = FilesystemBackend(
        root_dir=str(working_directory),
        virtual_mode=False,
    )

    interrupt_config = {
        "vercel_deploy": True,
        "railway_deploy": True,
        "render_deploy": True,
    }

    agent = create_deep_agent(
        name="openops-orchestrator",
        model=model_string,
        system_prompt=ORCHESTRATOR_PROMPT,
        tools=tools,
        subagents=subagents,
        backend=backend,
        skills=skill_directories,
        memory=memory_files,
        checkpointer=checkpointer,
        store=store,
        interrupt_on=interrupt_config,
    )

    logger.info("OpenOps orchestrator created successfully")
    return agent


class OrchestratorRuntime:
    """Runtime wrapper for the orchestrator agent.

    Provides a higher-level interface for invoking the orchestrator
    with conversation management.
    """

    def __init__(
        self,
        config: OpenOpsConfig,
        project_store: ProjectStoreBase,
        checkpointer: BaseCheckpointSaver | None = None,
        store: BaseStore | None = None,
        working_directory: str | Path | None = None,
    ):
        """Initialize the orchestrator runtime.

        Args:
            config: OpenOps configuration
            project_store: Storage backend for project knowledge
            checkpointer: Optional checkpointer for persistence
            store: Optional store for cross-thread memory
            working_directory: Root directory for file operations
        """
        self.config = config
        self.project_store = project_store
        self._checkpointer = checkpointer or MemorySaver()
        self._store = store or InMemoryStore()
        self._working_directory = Path(working_directory) if working_directory else Path(".")

        self._agent = create_orchestrator(
            config=config,
            project_store=project_store,
            checkpointer=self._checkpointer,
            store=self._store,
            working_directory=self._working_directory,
        )

        logger.info("OrchestratorRuntime initialized")

    def invoke(
        self,
        message: str,
        thread_id: str,
    ) -> dict[str, Any]:
        """Send a message to the orchestrator and get a response.

        Args:
            message: User message
            thread_id: Conversation thread ID for context persistence

        Returns:
            Agent response including messages and any state updates
        """
        logger.info(f"Invoking orchestrator with thread_id={thread_id}")
        logger.debug(f"Message: {message[:100]}...")

        config = {"configurable": {"thread_id": thread_id}}

        result = self._agent.invoke(
            {"messages": [{"role": "user", "content": message}]},
            config=config,
        )

        return result

    def get_state(self, thread_id: str) -> Any:
        """Get the current state for a thread.

        Useful for checking if there are pending interrupts.

        Args:
            thread_id: Conversation thread ID

        Returns:
            Current agent state
        """
        config = {"configurable": {"thread_id": thread_id}}
        return self._agent.get_state(config)

    def resume(
        self,
        thread_id: str,
        decision: str,
        message: str | None = None,
        edited_action: dict | None = None,
    ) -> dict[str, Any]:
        """Resume execution after an interrupt.

        Args:
            thread_id: Conversation thread ID
            decision: One of "approve", "reject", or "edit"
            message: Optional message for reject decisions
            edited_action: Modified action for edit decisions

        Returns:
            Agent response after resuming
        """
        from langgraph.types import Command

        logger.info(f"Resuming thread {thread_id} with decision: {decision}")

        config = {"configurable": {"thread_id": thread_id}}

        decision_payload: dict[str, Any] = {"type": decision}
        if message:
            decision_payload["message"] = message
        if edited_action:
            decision_payload["edited_action"] = edited_action

        result = self._agent.invoke(
            Command(resume={"decisions": [decision_payload]}),
            config=config,
        )

        return result

    @property
    def agent(self) -> Any:
        """Access the underlying agent instance."""
        return self._agent


__all__ = ["create_orchestrator", "OrchestratorRuntime"]

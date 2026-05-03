"""OpenOps Orchestrator Agent.

The main agent that handles user interactions and delegates to specialized
subagents for complex operations.

Shell Execution Backends
------------------------

The orchestrator uses LocalShellBackend by default for local development,
which provides the built-in `execute` tool for running shell commands
(including platform CLIs like vercel, railway, render).

For production deployments requiring isolated execution, replace
LocalShellBackend with a sandbox backend:

    Modal Sandbox (https://modal.com):
        from langchain_modal import ModalSandbox
        import modal

        app = modal.App.lookup("your-app")
        modal_sandbox = modal.Sandbox.create(app=app)
        backend = ModalSandbox(sandbox=modal_sandbox)

    Runloop Sandbox (https://runloop.ai):
        from langchain_runloop import RunloopSandbox
        from runloop_api_client import RunloopSDK

        client = RunloopSDK(bearer_token=os.environ["RUNLOOP_API_KEY"])
        devbox = client.devbox.create()
        backend = RunloopSandbox(devbox=devbox)

    Daytona Sandbox (https://daytona.io):
        from daytona import Daytona
        from langchain_daytona import DaytonaSandbox

        sandbox = Daytona().create()
        backend = DaytonaSandbox(sandbox=sandbox)

Sandbox backends provide isolated environments with their own filesystem
and shell execution, ensuring security and reproducibility.
"""

import importlib.resources
import logging
import os
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore

from openops.agent.llm import create_llm, get_model_string
from openops.agent.prompts import ORCHESTRATOR_PROMPT
from openops.agent.skill_tools import create_skill_management_tools
from openops.agent.subagents import create_all_subagents
from openops.agent.tools import (
    create_interactive_tools,
    create_monitoring_tools,
    create_project_knowledge_tools,
)
from openops.agent.tracing import build_langfuse_run_config, flush_langfuse, observe
from openops.config import OpenOpsConfig
from openops.credentials.platforms import build_interrupt_config
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
        # Get the installed package's skills directory using importlib.resources
        with importlib.resources.as_file(importlib.resources.files("openops.skills")) as package_skills_dir:
            skill_directories = [
                str(package_skills_dir),  # Built-in package skills
                str(Path.home() / ".openops" / "skills"),  # User custom skills
                "./skills/",  # Local project skills
                str(Path.home() / ".agents" / "skills"),  # User global skills
            ]
        logger.debug(f"Using skill directories: {skill_directories}")

    model_string = get_model_string(config)
    logger.debug(f"Using model: {model_string}")

    # Create model instance with proper configuration
    model = create_llm(config)
    logger.debug(f"Created model instance: {type(model).__name__}")

    # Set provider-specific env vars for subagents that use init_chat_model
    api_key = config.get_llm_api_key()
    if api_key:
        env_var_map = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
        }
        env_var = env_var_map.get(config.model_provider)
        if env_var:
            os.environ[env_var] = api_key
            logger.debug(f"Set {env_var} for subagent initialization")

    project_tools = create_project_knowledge_tools(project_store)
    monitoring_tools = create_monitoring_tools(project_store)
    interactive_tools = create_interactive_tools()
    skill_tools = create_skill_management_tools(skill_directories=skill_directories)
    tools = project_tools + monitoring_tools + interactive_tools + skill_tools + (additional_tools or [])
    logger.debug(f"Loaded {len(tools)} custom tools")

    subagents = create_all_subagents(
        model=model_string,
        skill_directories=skill_directories,
        deploy_tools=skill_tools,
    )
    logger.debug(f"Configured {len(subagents)} subagents")

    # LocalShellBackend provides the `execute` tool for running shell commands.
    # For production with isolated execution, use a sandbox backend instead:
    # ModalSandbox, RunloopSandbox, or DaytonaSandbox (see module docstring).
    backend = LocalShellBackend(
        root_dir=str(working_directory),
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
    )
    logger.debug("Using LocalShellBackend for shell execution support")

    interrupt_config = build_interrupt_config()
    # Add HITL approval for shell command execution
    interrupt_config["execute"] = True
    interrupt_config["skills_install"] = True
    logger.debug(f"Interrupt config: {interrupt_config}")

    agent = create_deep_agent(
        name="openops-orchestrator",
        model=model,  # Use model instance instead of string
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

        @observe(name="openops.invoke")
        def _run() -> dict[str, Any]:
            config = {"configurable": {"thread_id": thread_id}}
            config.update(
                build_langfuse_run_config(
                    self.config,
                    operation="invoke",
                    thread_id=thread_id,
                    working_directory=self._working_directory,
                )
            )
            try:
                return self._agent.invoke(
                    {"messages": [{"role": "user", "content": message}]},
                    config=config,
                )
            finally:
                flush_langfuse(self.config)

        return _run()

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
        *,
        hitl_action_count: int = 1,
    ) -> dict[str, Any]:
        """Resume execution after an interrupt.

        Args:
            thread_id: Conversation thread ID
            decision: One of "approve", "reject", or "edit"
            message: Optional message for reject decisions
            edited_action: Modified action for edit decisions
            hitl_action_count: Number of parallel tool calls in one HITL interrupt
                (``HumanInTheLoopMiddleware`` requires one decision per call).

        Returns:
            Agent response after resuming
        """
        from langgraph.types import Command

        n = max(1, hitl_action_count)
        logger.info(
            "Resuming thread %s with decision=%s for %d HITL action(s)",
            thread_id,
            decision,
            n,
        )

        @observe(name="openops.resume")
        def _run() -> dict[str, Any]:
            config = {"configurable": {"thread_id": thread_id}}
            config.update(
                build_langfuse_run_config(
                    self.config,
                    operation="resume",
                    thread_id=thread_id,
                    working_directory=self._working_directory,
                    extra_metadata={
                        "decision": decision,
                        "hitl_action_count": n,
                    },
                )
            )

            template: dict[str, Any] = {"type": decision}
            if message:
                template["message"] = message
            if edited_action:
                template["edited_action"] = edited_action

            decisions = [dict(template) for _ in range(n)]

            try:
                return self._agent.invoke(
                    Command(resume={"decisions": decisions}),
                    config=config,
                )
            finally:
                flush_langfuse(self.config)

        return _run()

    @property
    def agent(self) -> Any:
        """Access the underlying agent instance."""
        return self._agent


__all__ = ["create_orchestrator", "OrchestratorRuntime"]

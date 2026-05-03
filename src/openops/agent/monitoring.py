"""Dedicated monitoring agent runtime for daemon-driven health checks."""

from __future__ import annotations

import importlib.resources
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore

from openops.agent.llm import create_llm
from openops.agent.prompts import MONITORING_AGENT_PROMPT
from openops.agent.skill_tools import create_skill_management_tools
from openops.agent.tools import create_monitoring_query_tools, create_project_knowledge_tools
from openops.agent.tracing import build_langfuse_run_config, flush_langfuse, observe
from openops.config import OpenOpsConfig
from openops.models import FindingSeverity, MonitoringReport
from openops.storage.base import ProjectStoreBase

logger = logging.getLogger(__name__)


def _select_project_read_only_tools(tools: list) -> list:
    allowed_names = {"query_project_knowledge", "list_projects"}
    return [tool for tool in tools if getattr(tool, "name", "") in allowed_names]


def create_monitoring_agent(
    config: OpenOpsConfig,
    project_store: ProjectStoreBase,
    checkpointer: BaseCheckpointSaver | None = None,
    store: BaseStore | None = None,
    working_directory: str | Path | None = None,
    skill_directories: list[str] | None = None,
) -> Any:
    """Create the dedicated monitoring deep agent."""
    logger.info("Creating OpenOps monitoring agent")

    checkpointer = checkpointer or MemorySaver()
    store = store or InMemoryStore()
    working_directory = Path(working_directory) if working_directory else Path(".")

    if skill_directories is None:
        with importlib.resources.as_file(importlib.resources.files("openops.skills")) as package_skills_dir:
            skill_directories = [
                str(package_skills_dir),
                str(Path.home() / ".openops" / "skills"),
                "./skills/",
                str(Path.home() / ".agents" / "skills"),
            ]
        logger.debug("Monitoring skill directories: %s", skill_directories)

    # Keep provider env setup consistent with orchestrator implementation.
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

    project_tools = _select_project_read_only_tools(create_project_knowledge_tools(project_store))
    monitoring_tools = create_monitoring_query_tools(project_store)
    skill_tools = create_skill_management_tools(skill_directories=skill_directories)
    tools = project_tools + monitoring_tools + skill_tools
    logger.debug("Monitoring agent loaded %d tools", len(tools))

    backend = LocalShellBackend(
        root_dir=str(working_directory),
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        virtual_mode=False,
    )

    agent = create_deep_agent(
        name="openops-monitor",
        model=create_llm(config),
        system_prompt=MONITORING_AGENT_PROMPT,
        tools=tools,
        backend=backend,
        skills=skill_directories,
        checkpointer=checkpointer,
        store=store,
        interrupt_on={},
        response_format=MonitoringReport,
    )
    logger.info("OpenOps monitoring agent created successfully")
    return agent


class MonitoringAgentRuntime:
    """Runtime wrapper around the dedicated monitoring agent."""

    def __init__(
        self,
        config: OpenOpsConfig,
        project_store: ProjectStoreBase,
        checkpointer: BaseCheckpointSaver | None = None,
        store: BaseStore | None = None,
        working_directory: str | Path | None = None,
        skill_directories: list[str] | None = None,
    ):
        self.config = config
        self.project_store = project_store
        self._checkpointer = checkpointer or MemorySaver()
        self._store = store or InMemoryStore()
        self._working_directory = Path(working_directory) if working_directory else Path(".")
        self._agent = create_monitoring_agent(
            config=config,
            project_store=project_store,
            checkpointer=self._checkpointer,
            store=self._store,
            working_directory=self._working_directory,
            skill_directories=skill_directories,
        )

    def run_tick(self, project_path: str, thread_id: str) -> MonitoringReport:
        """Run a single periodic monitoring check and return structured findings."""
        message = (
            "Scheduled monitoring tick.\n\n"
            f"Project path: {project_path}\n"
            "Inspect active deployments and related services, then return a report"
        )

        @observe(name="openops.monitor.tick")
        def _run() -> dict[str, Any]:
            invoke_config = {"configurable": {"thread_id": thread_id}}
            invoke_config.update(
                build_langfuse_run_config(
                    self.config,
                    operation="monitor_tick",
                    thread_id=thread_id,
                    working_directory=self._working_directory,
                    extra_metadata={"project_path": project_path},
                )
            )
            try:
                return self._agent.invoke(
                    {"messages": [{"role": "user", "content": message}]},
                    config=invoke_config,
                )
            finally:
                flush_langfuse(self.config)

        result = _run()
        structured = result.get("structured_response")
        if isinstance(structured, MonitoringReport):
            return structured
        if structured is not None:
            return MonitoringReport.model_validate(structured)

        logger.warning("Monitoring tick returned no structured response; creating fallback report")
        return MonitoringReport(
            project_path=str(Path(project_path).resolve()),
            generated_at=datetime.now(),
            overall_status=FindingSeverity.WARNING,
            summary="Monitoring run completed without structured response.",
            findings=[],
            services_checked=[],
        )

    def get_state(self, thread_id: str) -> Any:
        """Expose graph state for defensive interrupt checks in daemon code."""
        config = {"configurable": {"thread_id": thread_id}}
        return self._agent.get_state(config)

    @property
    def agent(self) -> Any:
        return self._agent


__all__ = ["create_monitoring_agent", "MonitoringAgentRuntime"]

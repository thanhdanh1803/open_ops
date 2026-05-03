"""Subagent configurations for OpenOps.

Defines specialized subagents that the orchestrator can delegate to:
- project-analyzer: Deep project structure analysis
- deploy-agent: Platform-specific deployments
- monitor-agent: Log analysis and monitoring
"""

import logging
from typing import Any

from openops.agent.prompts import (
    DEPLOY_AGENT_PROMPT,
    MONITOR_AGENT_PROMPT,
    PROJECT_ANALYZER_PROMPT,
)
from openops.credentials.platforms import (
    build_interrupt_config,
    get_deployment_platform_names,
)

logger = logging.getLogger(__name__)


def create_project_analyzer_config(
    model: str | None = None,
    additional_tools: list | None = None,
) -> dict[str, Any]:
    """Create configuration for the project analyzer subagent.

    The project analyzer specializes in examining codebases to understand
    their structure for deployment purposes.

    Args:
        model: Optional model override (defaults to main agent's model)
        additional_tools: Additional tools to provide (e.g., framework detection)

    Returns:
        Subagent configuration dictionary for Deep Agents
    """
    logger.debug("Creating project analyzer config")

    tools = additional_tools or []

    config: dict[str, Any] = {
        "name": "project-analyzer",
        "description": (
            "Analyzes project structure to identify services, tech stacks, "
            "dependencies, and deployment requirements. Use for deep codebase analysis."
        ),
        "system_prompt": PROJECT_ANALYZER_PROMPT,
        "tools": tools,
    }

    if model:
        config["model"] = model

    return config


def create_deploy_agent_config(
    model: str | None = None,
    skills: list[str] | None = None,
    additional_tools: list | None = None,
    interrupt_on_deploy: bool = True,
) -> dict[str, Any]:
    """Create configuration for the deploy agent subagent.

    The deploy agent handles deployments to cloud platforms using
    platform-specific skills.

    Args:
        model: Optional model override (defaults to main agent's model)
        skills: Skill directories to load (e.g., ["~/.openops/skills/vercel/"])
        additional_tools: Additional tools to provide to deploy agent
        interrupt_on_deploy: Whether to require approval for deployments

    Returns:
        Subagent configuration dictionary for Deep Agents
    """
    logger.debug("Creating deploy agent config")

    platform_names = ", ".join(get_deployment_platform_names())
    tools = additional_tools or []

    config: dict[str, Any] = {
        "name": "deploy-agent",
        "description": (
            f"Handles deployments to cloud platforms ({platform_names}). "
            "Generates configs, validates settings, and executes deployments."
        ),
        "system_prompt": DEPLOY_AGENT_PROMPT,
        "tools": tools,
    }

    if model:
        config["model"] = model

    if skills:
        config["skills"] = skills

    if interrupt_on_deploy:
        interrupt_config = build_interrupt_config()
        interrupt_config["skills_install"] = True
        config["interrupt_on"] = interrupt_config

    return config


def create_monitor_agent_config(
    model: str | None = None,
    additional_tools: list | None = None,
) -> dict[str, Any]:
    """Create configuration for the monitor agent subagent.

    The monitor agent specializes in fetching and analyzing logs
    from deployed services.

    Args:
        model: Optional model override (defaults to main agent's model)
        additional_tools: Additional monitoring tools to provide

    Returns:
        Subagent configuration dictionary for Deep Agents
    """
    logger.debug("Creating monitor agent config")

    tools = additional_tools or []

    config: dict[str, Any] = {
        "name": "monitor-agent",
        "description": (
            "Monitors deployed services by fetching logs, analyzing errors, "
            "and identifying issues. Use for debugging and health checks."
        ),
        "system_prompt": MONITOR_AGENT_PROMPT,
        "tools": tools,
    }

    if model:
        config["model"] = model

    return config


def create_all_subagents(
    model: str | None = None,
    skill_directories: list[str] | None = None,
    analyzer_tools: list | None = None,
    deploy_tools: list | None = None,
    monitor_tools: list | None = None,
) -> list[dict[str, Any]]:
    """Create all subagent configurations.

    Convenience function to create all three subagent configs at once.

    Args:
        model: Model to use for all subagents (optional)
        skill_directories: Skill directories for deploy agent
        analyzer_tools: Additional tools for project analyzer
        deploy_tools: Additional tools for deploy agent
        monitor_tools: Additional tools for monitor agent

    Returns:
        List of subagent configuration dictionaries
    """
    return [
        create_project_analyzer_config(
            model=model,
            additional_tools=analyzer_tools,
        ),
        create_deploy_agent_config(
            model=model,
            skills=skill_directories,
            additional_tools=deploy_tools,
        ),
        create_monitor_agent_config(
            model=model,
            additional_tools=monitor_tools,
        ),
    ]


__all__ = [
    "create_project_analyzer_config",
    "create_deploy_agent_config",
    "create_monitor_agent_config",
    "create_all_subagents",
]

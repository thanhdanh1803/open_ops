"""Base skill interface for OpenOps."""

import logging
from abc import ABC, abstractmethod
from typing import Any

from openops.models import RiskLevel, SkillMetadata, SkillResult

logger = logging.getLogger(__name__)


class BaseSkill(ABC):
    """Base class for OpenOps skills.

    Skills are modular capabilities that extend OpenOps agents.
    They provide platform-specific knowledge and tools for deployment and monitoring.

    Attributes:
        name: Unique identifier for the skill
        description: Human-readable description of what this skill does
        risk_level: The risk level of operations this skill performs
    """

    name: str
    description: str
    risk_level: RiskLevel

    @abstractmethod
    def get_tools(self) -> list[Any]:
        """Return LangChain tools provided by this skill.

        Returns:
            List of LangChain tool instances that agents can use
        """
        pass

    def validate_credentials(self) -> bool:
        """Check if required credentials are available.

        Override this method to implement credential validation
        for skills that require API keys or tokens.

        Returns:
            True if credentials are valid, False otherwise
        """
        return True

    def get_skill_instructions(self) -> str | None:
        """Return skill-specific instructions for the agent (Tier 2).

        This is the full skill content loaded on-demand when the agent
        determines this skill is relevant to the current task.

        Override this to provide additional context or instructions
        that should be injected into the agent's system prompt.

        Returns:
            Instructions string or None if no special instructions
        """
        return None

    @abstractmethod
    def get_metadata(self) -> SkillMetadata:
        """Return skill metadata for the catalog (Tier 1).

        This lightweight metadata is always available to the agent and
        serves as a semantic search key to determine skill relevance.
        The agent uses this to decide whether to load the full skill.

        Returns:
            SkillMetadata with name, description, tags, etc.
        """
        pass


__all__ = ["BaseSkill", "SkillMetadata", "SkillResult"]

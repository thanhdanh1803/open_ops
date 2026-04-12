"""Tests for the base skill interface."""

import pytest

from openops.models import RiskLevel, SkillMetadata, SkillResult
from openops.skills.base import BaseSkill


class ConcreteSkill(BaseSkill):
    """Concrete implementation for testing."""

    name = "test-skill"
    description = "A test skill"
    risk_level = RiskLevel.READ

    def __init__(self, has_credentials: bool = True):
        self._has_credentials = has_credentials

    def get_tools(self) -> list:
        return [{"name": "test_tool", "func": lambda: "test"}]

    def validate_credentials(self) -> bool:
        return self._has_credentials

    def get_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name=self.name,
            description=self.description,
            risk_level=self.risk_level,
            tags=["test"],
            provides_tools=["test_tool"],
        )


class TestBaseSkill:
    def test_skill_attributes(self):
        skill = ConcreteSkill()

        assert skill.name == "test-skill"
        assert skill.description == "A test skill"
        assert skill.risk_level == RiskLevel.READ

    def test_get_tools(self):
        skill = ConcreteSkill()
        tools = skill.get_tools()

        assert len(tools) == 1
        assert tools[0]["name"] == "test_tool"

    def test_validate_credentials_success(self):
        skill = ConcreteSkill(has_credentials=True)
        assert skill.validate_credentials() is True

    def test_validate_credentials_failure(self):
        skill = ConcreteSkill(has_credentials=False)
        assert skill.validate_credentials() is False

    def test_get_skill_instructions_default(self):
        skill = ConcreteSkill()
        assert skill.get_skill_instructions() is None

    def test_get_metadata(self):
        skill = ConcreteSkill()
        metadata = skill.get_metadata()

        assert metadata.name == "test-skill"
        assert metadata.description == "A test skill"
        assert metadata.risk_level == RiskLevel.READ
        assert "test" in metadata.tags
        assert "test_tool" in metadata.provides_tools

    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            BaseSkill()


class TestSkillResultFromSkills:
    def test_skill_result_imported_correctly(self):
        from openops.skills import SkillResult as ImportedSkillResult

        assert ImportedSkillResult is SkillResult

    def test_base_skill_imported_correctly(self):
        from openops.skills import BaseSkill as ImportedBaseSkill

        assert ImportedBaseSkill is BaseSkill

    def test_skill_metadata_imported_correctly(self):
        from openops.skills import SkillMetadata as ImportedSkillMetadata

        assert ImportedSkillMetadata is SkillMetadata

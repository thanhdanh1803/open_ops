"""Tests for structured skill management tools."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.messages import ToolMessage
from langgraph.types import Command

from openops.agent.skill_tools import create_skill_management_tools


class TestSkillsSearch:
    def test_search_parses_candidates(self):
        tools = create_skill_management_tools()
        search_tool = tools[0]

        stdout = """
vercel-labs/skills@find-skills 1.2M installs
└ https://skills.sh/vercel-labs/skills/find-skills
"""
        with patch("openops.agent.skill_tools._run_command", return_value=(0, stdout, "")):
            result = search_tool.invoke({"query": "vercel"})

        assert result["success"] is True
        assert result["count"] == 1
        candidate = result["candidates"][0]
        assert candidate["name"] == "find-skills"
        assert candidate["source"] == "vercel-labs/skills"
        assert candidate["install_command_parameters"]["skill_name"] == "find-skills"


class TestSkillsInstall:
    def test_install_updates_skills_metadata_state(self, tmp_path: Path):
        skill_dir = tmp_path / "new-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: new-skill\ndescription: Installs and configures new skill\n---\n\n# New Skill\n",
            encoding="utf-8",
        )

        ls_payload = json.dumps(
            [
                {
                    "name": "new-skill",
                    "path": str(skill_dir),
                    "scope": "global",
                    "agents": ["Cursor"],
                }
            ]
        )
        tools = create_skill_management_tools(skill_directories=[str(tmp_path)])
        install_tool = tools[1]
        runtime = SimpleNamespace(
            state={
                "skills_metadata": [
                    {
                        "name": "existing-skill",
                        "description": "Existing",
                        "path": "/tmp/existing/SKILL.md",
                        "metadata": {},
                        "license": None,
                        "compatibility": None,
                        "allowed_tools": [],
                    }
                ]
            },
            tool_call_id="tool-call-1",
        )

        with patch(
            "openops.agent.skill_tools._run_command",
            side_effect=[(0, "install ok", ""), (0, ls_payload, "")],
        ):
            command = install_tool.func(
                source="vercel-labs/skills",
                skill_name="new-skill",
                install_scope="global",
                runtime=runtime,
            )

        assert isinstance(command, Command)
        merged_metadata = command.update["skills_metadata"]
        assert any(item["name"] == "new-skill" for item in merged_metadata)
        assert any(item["name"] == "existing-skill" for item in merged_metadata)

        tool_message = command.update["messages"][0]
        assert isinstance(tool_message, ToolMessage)
        payload = json.loads(tool_message.content)
        assert payload["success"] is True
        assert payload["installed_skill_metadata"]["name"] == "new-skill"

    def test_install_returns_structured_failure_when_not_listed(self):
        tools = create_skill_management_tools()
        install_tool = tools[1]
        runtime = SimpleNamespace(state={}, tool_call_id="tool-call-2")

        with patch(
            "openops.agent.skill_tools._run_command",
            side_effect=[(0, "install ok", ""), (0, "[]", "")],
        ):
            result = install_tool.func(
                runtime=runtime,
                source="vercel-labs/skills",
                skill_name="missing-skill",
                install_scope="global",
            )

        assert result["success"] is False
        assert "could not be found" in result["error"]

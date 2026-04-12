"""Tests for OpenOps subagent configurations."""

import pytest

from openops.agent.subagents import (
    create_all_subagents,
    create_deploy_agent_config,
    create_monitor_agent_config,
    create_project_analyzer_config,
)


class TestProjectAnalyzerConfig:
    def test_basic_config(self):
        config = create_project_analyzer_config()

        assert config["name"] == "project-analyzer"
        assert "description" in config
        assert "system_prompt" in config
        assert config["tools"] == []

    def test_with_model_override(self):
        config = create_project_analyzer_config(model="openai:gpt-4o")

        assert config["model"] == "openai:gpt-4o"

    def test_with_additional_tools(self):
        mock_tool = lambda x: x
        config = create_project_analyzer_config(additional_tools=[mock_tool])

        assert len(config["tools"]) == 1
        assert config["tools"][0] == mock_tool


class TestDeployAgentConfig:
    def test_basic_config(self):
        config = create_deploy_agent_config()

        assert config["name"] == "deploy-agent"
        assert "description" in config
        assert "system_prompt" in config
        assert "interrupt_on" in config

    def test_with_skills(self):
        skills = ["~/.openops/skills/vercel/", "~/.openops/skills/railway/"]
        config = create_deploy_agent_config(skills=skills)

        assert config["skills"] == skills

    def test_interrupt_on_deploy(self):
        config = create_deploy_agent_config(interrupt_on_deploy=True)

        assert config["interrupt_on"]["vercel_deploy"] is True
        assert config["interrupt_on"]["railway_deploy"] is True
        assert config["interrupt_on"]["render_deploy"] is True

    def test_no_interrupt(self):
        config = create_deploy_agent_config(interrupt_on_deploy=False)

        assert "interrupt_on" not in config


class TestMonitorAgentConfig:
    def test_basic_config(self):
        config = create_monitor_agent_config()

        assert config["name"] == "monitor-agent"
        assert "description" in config
        assert "system_prompt" in config
        assert config["tools"] == []

    def test_with_model_override(self):
        config = create_monitor_agent_config(model="anthropic:claude-haiku")

        assert config["model"] == "anthropic:claude-haiku"

    def test_with_additional_tools(self):
        mock_tools = [lambda x: x, lambda y: y]
        config = create_monitor_agent_config(additional_tools=mock_tools)

        assert len(config["tools"]) == 2


class TestCreateAllSubagents:
    def test_creates_three_subagents(self):
        subagents = create_all_subagents()

        assert len(subagents) == 3

        names = [s["name"] for s in subagents]
        assert "project-analyzer" in names
        assert "deploy-agent" in names
        assert "monitor-agent" in names

    def test_shared_model(self):
        subagents = create_all_subagents(model="openai:gpt-4o")

        for subagent in subagents:
            assert subagent.get("model") == "openai:gpt-4o"

    def test_skill_directories(self):
        skill_dirs = ["./skills/vercel/", "./skills/railway/"]
        subagents = create_all_subagents(skill_directories=skill_dirs)

        deploy_agent = next(s for s in subagents if s["name"] == "deploy-agent")
        assert deploy_agent.get("skills") == skill_dirs

    def test_analyzer_tools(self):
        mock_tool = lambda x: x
        subagents = create_all_subagents(analyzer_tools=[mock_tool])

        analyzer = next(s for s in subagents if s["name"] == "project-analyzer")
        assert len(analyzer["tools"]) == 1

    def test_monitor_tools(self):
        mock_tools = [lambda x: x, lambda y: y]
        subagents = create_all_subagents(monitor_tools=mock_tools)

        monitor = next(s for s in subagents if s["name"] == "monitor-agent")
        assert len(monitor["tools"]) == 2

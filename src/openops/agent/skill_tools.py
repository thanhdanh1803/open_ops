"""Structured skill lifecycle tools for OpenOps agents."""

from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Any

from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.types import Command

from openops.agent.tracing import observe

logger = logging.getLogger(__name__)

try:
    from deepagents.middleware.skills import SkillMetadata
    from deepagents.middleware.skills import _parse_skill_metadata as _deepagents_parse_skill_metadata
except ImportError:  # pragma: no cover - tested via behavior surface
    SkillMetadata = dict[str, Any]  # type: ignore[assignment,misc]
    _deepagents_parse_skill_metadata = None


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_FIND_ENTRY_RE = re.compile(
    r"^(?P<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@(?P<skill>[A-Za-z0-9_.-]+)\s+"
    r"(?P<installs>[0-9][0-9.,]*[KMB]?)\s+installs$"
)
_URL_RE = re.compile(r"https://skills\.sh/\S+")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _run_command(command: list[str]) -> tuple[int, str, str]:
    logger.debug("Running skills command: %s", " ".join(command))
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    logger.debug("Command exit=%s stdout_len=%s stderr_len=%s", completed.returncode, len(stdout), len(stderr))
    return completed.returncode, stdout, stderr


def _summarize_output(text: str, max_chars: int = 1200) -> str:
    clean = _strip_ansi(text).strip()
    if len(clean) <= max_chars:
        return clean
    return clean[:max_chars] + "...(truncated)"


def _extract_json_payload(raw: str) -> list[dict[str, Any]]:
    clean = _strip_ansi(raw)
    start = clean.find("[")
    end = clean.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        payload = json.loads(clean[start : end + 1])
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _resolve_skill_sources(skill_directories: list[str] | None) -> list[str]:
    if not skill_directories:
        return []
    sources: list[str] = []
    for directory in skill_directories:
        expanded = Path(directory).expanduser().resolve()
        sources.append(expanded.as_posix())
    return sources


def _parse_metadata_with_deepagents(skill_md_path: Path) -> tuple[SkillMetadata | None, str | None]:
    if _deepagents_parse_skill_metadata is None:
        return None, "DeepAgents skill parser is unavailable in current environment."

    try:
        content = skill_md_path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"Failed to read {skill_md_path}: {exc}"

    metadata = _deepagents_parse_skill_metadata(
        content=content,
        skill_path=skill_md_path.as_posix(),
        directory_name=skill_md_path.parent.name,
    )
    if metadata is None:
        return None, f"Failed to parse skill frontmatter from {skill_md_path.as_posix()}."

    return metadata, None


def _merge_skill_metadata(
    existing_metadata: list[dict[str, Any]],
    installed_metadata: SkillMetadata,
) -> list[dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}
    for item in existing_metadata:
        name = item.get("name")
        if isinstance(name, str):
            by_name[name] = item
    by_name[installed_metadata["name"]] = dict(installed_metadata)
    return list(by_name.values())


def _find_source_dir(installed_dir: Path, known_sources: list[str], target_dir: str | None) -> str:
    if target_dir:
        return Path(target_dir).expanduser().resolve().as_posix()

    resolved_install = installed_dir.resolve()
    for source in known_sources:
        source_path = Path(source).resolve()
        try:
            resolved_install.relative_to(source_path)
            return source_path.as_posix()
        except ValueError:
            continue

    return installed_dir.parent.resolve().as_posix()


def _parse_find_output(stdout: str, *, source_filter: str | None, limit: int) -> list[dict[str, Any]]:
    lines = [line.strip() for line in _strip_ansi(stdout).splitlines()]
    candidates: list[dict[str, Any]] = []
    pending_index: int | None = None

    for line in lines:
        if not line:
            continue

        match = _FIND_ENTRY_RE.match(line)
        if match:
            repo = match.group("repo")
            skill_name = match.group("skill")
            if source_filter and source_filter not in repo:
                pending_index = None
                continue

            candidate = {
                "name": skill_name,
                "description": "Description not available from CLI search output.",
                "source": repo,
                "repo": repo,
                "installs": match.group("installs"),
                "skills_sh_url": None,
                "install_command": f"npx skills add {repo} --skill {skill_name} --global --yes",
                "install_command_parameters": {
                    "source": repo,
                    "skill_name": skill_name,
                    "install_scope": "global",
                    "yes": True,
                },
            }
            candidates.append(candidate)
            pending_index = len(candidates) - 1
            if len(candidates) >= limit:
                break
            continue

        if pending_index is None:
            continue

        url_match = _URL_RE.search(line)
        if url_match:
            candidates[pending_index]["skills_sh_url"] = url_match.group(0)
            pending_index = None

    return candidates


def _list_installed_skills(install_scope: str) -> list[dict[str, Any]]:
    command = ["npx", "skills", "ls", "--json"]
    if install_scope == "global":
        command.insert(3, "-g")

    rc, stdout, _stderr = _run_command(command)
    if rc != 0:
        return []
    return _extract_json_payload(stdout)


def create_skill_management_tools(skill_directories: list[str] | None = None) -> list:
    """Create structured skill management tools."""
    known_sources = _resolve_skill_sources(skill_directories)
    logger.info("Creating skill management tools with %d source directories", len(known_sources))

    @tool("skills_search")
    @observe(name="tool.skills_search")
    def skills_search(query: str, limit: int = 10, source: str | None = None) -> dict[str, Any]:
        """Search for installable skills and return structured candidates."""
        normalized_limit = max(1, min(limit, 50))
        logger.info("Searching skills query='%s' limit=%d source=%s", query, normalized_limit, source)
        rc, stdout, stderr = _run_command(["npx", "skills", "find", query])

        if rc != 0:
            return {
                "success": False,
                "query": query,
                "candidates": [],
                "stdout_summary": _summarize_output(stdout),
                "stderr_summary": _summarize_output(stderr),
                "error": "skills find command failed",
            }

        candidates = _parse_find_output(stdout, source_filter=source, limit=normalized_limit)
        logger.info("skills_search found %d candidates", len(candidates))
        return {
            "success": True,
            "query": query,
            "count": len(candidates),
            "candidates": candidates,
            "stdout_summary": _summarize_output(stdout),
            "stderr_summary": _summarize_output(stderr),
        }

    @tool("skills_install")
    @observe(name="tool.skills_install")
    def skills_install(
        runtime: ToolRuntime[None, dict[str, Any]],
        source: str,
        skill_name: str,
        install_scope: str = "global",
        target_dir: str | None = None,
        yes: bool = True,
    ) -> Command[Any] | dict[str, Any]:
        """Install a skill non-interactively and update skills metadata state."""
        logger.info(
            "Installing skill source='%s' skill='%s' scope='%s' target_dir=%s",
            source,
            skill_name,
            install_scope,
            target_dir,
        )

        if install_scope not in {"global", "project"}:
            return {
                "success": False,
                "error": "install_scope must be one of: global, project",
                "source": source,
                "skill_name": skill_name,
            }

        install_command = ["npx", "skills", "add", source, "--skill", skill_name]
        if install_scope == "global":
            install_command.append("--global")
        if yes:
            install_command.append("--yes")

        rc, stdout, stderr = _run_command(install_command)
        stdout_summary = _summarize_output(stdout)
        stderr_summary = _summarize_output(stderr)

        if rc != 0:
            return {
                "success": False,
                "source": source,
                "skill_name": skill_name,
                "install_scope": install_scope,
                "target_dir": target_dir,
                "stdout_summary": stdout_summary,
                "stderr_summary": stderr_summary,
                "error": "skills add command failed",
            }

        installed_skills = _list_installed_skills(install_scope)
        entry = next((item for item in installed_skills if item.get("name") == skill_name), None)
        if entry is None:
            return {
                "success": False,
                "source": source,
                "skill_name": skill_name,
                "install_scope": install_scope,
                "target_dir": target_dir,
                "stdout_summary": stdout_summary,
                "stderr_summary": stderr_summary,
                "error": "skill installed but could not be found in `skills ls --json` output",
            }

        installed_path = Path(str(entry.get("path", ""))).expanduser()
        skill_md_path = installed_path / "SKILL.md"
        metadata, metadata_error = _parse_metadata_with_deepagents(skill_md_path)
        if metadata is None:
            return {
                "success": False,
                "source": source,
                "skill_name": skill_name,
                "install_scope": install_scope,
                "target_dir": target_dir,
                "installed_path": installed_path.as_posix(),
                "stdout_summary": stdout_summary,
                "stderr_summary": stderr_summary,
                "error": metadata_error or "Failed to parse installed skill metadata.",
            }

        source_dir = _find_source_dir(installed_path, known_sources=known_sources, target_dir=target_dir)
        existing_metadata = []
        state = runtime.state or {}
        maybe_metadata = state.get("skills_metadata", [])
        if isinstance(maybe_metadata, list):
            existing_metadata = [m for m in maybe_metadata if isinstance(m, dict)]

        merged_metadata = _merge_skill_metadata(existing_metadata, metadata)
        result_payload = {
            "success": True,
            "source": source,
            "skill_name": skill_name,
            "install_scope": install_scope,
            "target_dir": target_dir,
            "installed_skill_metadata": metadata,
            "installed_path": installed_path.as_posix(),
            "source_dir": source_dir,
            "stdout_summary": stdout_summary,
            "stderr_summary": stderr_summary,
        }

        tool_call_id = runtime.tool_call_id or "skills_install"
        return Command(
            update={
                "skills_metadata": merged_metadata,
                "messages": [ToolMessage(content=json.dumps(result_payload), tool_call_id=tool_call_id)],
            }
        )

    return [skills_search, skills_install]


__all__ = ["create_skill_management_tools"]

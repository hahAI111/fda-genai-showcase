"""Markdown Skill Loader — Loads SKILL.md files as declarative skills.

Reads SKILL.md files with YAML frontmatter + Markdown body and registers
them as MarkdownSkill instances in the SkillRegistry. This enables the
declarative Foundry-Agency pattern where skills are defined entirely in
Markdown instead of Python code.

Pattern:
    skills/
    ├── knowledge-retrieval/
    │   └── SKILL.md          ← YAML frontmatter + Markdown body
    ├── analysis/
    │   └── SKILL.md
    └── ...

YAML frontmatter fields:
    name: skill-name
    description: What this skill does
    allowed-tools: [tool1, tool2]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import structlog

from src.skills.base import Skill, SkillRegistry, ToolSchema

logger = structlog.get_logger()


@dataclass
class MarkdownSkillData:
    """Parsed SKILL.md content."""

    name: str
    description: str
    allowed_tools: list[str]
    body: str
    source_path: str


class MarkdownSkill(Skill):
    """A skill loaded from a SKILL.md file."""

    def __init__(self, data: MarkdownSkillData):
        self._data = data

    @property
    def name(self) -> str:
        return self._data.name

    @property
    def description(self) -> str:
        return self._data.description

    @property
    def tags(self) -> list[str]:
        return ["markdown", "declarative"]

    def get_tools(self) -> list[ToolSchema]:
        # Markdown skills don't have executable tool handlers —
        # they provide context/prompts for agents that have real tools.
        return []

    def get_system_prompt_fragment(self) -> str | None:
        return self._data.body

    @property
    def source_path(self) -> str:
        return self._data.source_path


def _parse_frontmatter(content: str) -> tuple[dict[str, any], str]:
    """Parse YAML frontmatter from Markdown content.

    Returns (frontmatter_dict, body_text).
    """
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    # Simple YAML parsing (avoid heavy dependency)
    frontmatter: dict[str, any] = {}
    current_key = None
    current_list = None

    for line in parts[1].strip().splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # List item under a key
        if stripped.startswith("- ") and current_key:
            if current_list is None:
                current_list = []
                frontmatter[current_key] = current_list
            current_list.append(stripped[2:].strip())
            continue

        # Key-value pair
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()
            current_key = key
            current_list = None

            if value and value != ">":
                frontmatter[key] = value
            elif value == ">":
                # Multi-line scalar — collect subsequent indented lines
                frontmatter[key] = ""
            continue

        # Continuation of multi-line scalar
        if current_key and current_key in frontmatter and isinstance(frontmatter[current_key], str):
            if frontmatter[current_key]:
                frontmatter[current_key] += " " + stripped
            else:
                frontmatter[current_key] = stripped

    body = parts[2].strip()
    return frontmatter, body


def _parse_skill_md(path: Path) -> MarkdownSkillData | None:
    """Parse a single SKILL.md file."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("skill.md.read_error", path=str(path), error=str(e))
        return None

    frontmatter, body = _parse_frontmatter(content)

    name = frontmatter.get("name")
    if not name:
        logger.warning("skill.md.missing_name", path=str(path))
        return None

    return MarkdownSkillData(
        name=name,
        description=frontmatter.get("description", ""),
        allowed_tools=frontmatter.get("allowed-tools", []),
        body=body,
        source_path=str(path),
    )


def load_markdown_skills(skills_dir: Path, registry: SkillRegistry) -> int:
    """Scan skills_dir for SKILL.md files and register them.

    Returns the number of Markdown skills loaded.
    """
    if not skills_dir.is_dir():
        logger.warning("skill.md.dir_not_found", path=str(skills_dir))
        return 0

    count = 0
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        data = _parse_skill_md(skill_md)
        if data is None:
            continue

        # Skip if a Python skill with the same name is already registered
        if registry.get(data.name):
            logger.debug("skill.md.skipped_duplicate", name=data.name)
            continue

        skill = MarkdownSkill(data)
        registry.register(skill)
        count += 1
        logger.info("skill.md.loaded", name=data.name, source=str(skill_md))

    return count

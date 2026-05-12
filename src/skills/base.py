"""Skill Base — Abstract interface for all skills.

A Skill is a self-contained, reusable capability that:
1. Declares what it can do (description + tool schemas)
2. Provides the execution logic (tool handlers)
3. Can be loaded dynamically by any agent

This is the "reusable module" pattern from the FDA role —
field patterns extracted into composable building blocks.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

import structlog

logger = structlog.get_logger()


@dataclass
class ToolSchema:
    """OpenAI function-calling tool definition."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable


class Skill(ABC):
    """Base class for all skills. Subclass to create a new capability."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique skill name."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """What this skill does — shown to the orchestrator for routing."""
        ...

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def tags(self) -> list[str]:
        return []

    @abstractmethod
    def get_tools(self) -> list[ToolSchema]:
        """Return the tool definitions this skill provides."""
        ...

    def get_system_prompt_fragment(self) -> str | None:
        """Optional system prompt addition when this skill is active."""
        return None


class SkillRegistry:
    """Discover, load, and manage skills across agents.

    The registry enables:
    - Dynamic skill discovery (agents can query available skills)
    - Skill composition (agents can combine multiple skills)
    - Usage tracking (which skills are used most → product insight)
    """

    def __init__(self):
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill
        logger.info("skill.registered", skill=skill.name, version=skill.version)

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def list_skills(self) -> list[dict[str, Any]]:
        """List all registered skills — for discovery."""
        return [
            {
                "name": s.name,
                "description": s.description,
                "version": s.version,
                "tags": s.tags,
                "tools": [t.name for t in s.get_tools()],
                "has_prompt": s.get_system_prompt_fragment() is not None,
            }
            for s in self._skills.values()
        ]

    def get_tools_for_agent(self, skill_names: list[str]) -> list[ToolSchema]:
        """Get combined tools from multiple skills — for agent composition."""
        tools = []
        for name in skill_names:
            skill = self._skills.get(name)
            if skill:
                tools.extend(skill.get_tools())
        return tools

    def find_by_tag(self, tag: str) -> list[Skill]:
        return [s for s in self._skills.values() if tag in s.tags]

    @property
    def count(self) -> int:
        return len(self._skills)

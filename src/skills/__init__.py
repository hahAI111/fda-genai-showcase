"""Skills — Reusable, composable agent capabilities.

Skills are modular building blocks that agents can load and combine.
Each skill encapsulates:
- A specific capability (search, analysis, compliance check, etc.)
- Its tool definitions (OpenAI function-calling schemas)
- Configuration and prompts

Enterprise Pattern: Skills enable "build once, reuse everywhere" — 
a key value proposition for the Forward Deployed Architect role.
When you solve a customer problem, you extract it into a skill
that benefits all future deployments.
"""

from src.skills.base import Skill, SkillRegistry

__all__ = ["Skill", "SkillRegistry"]

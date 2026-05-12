"""Analyst Agent — Structured analysis and insight generation.

This agent demonstrates enterprise patterns for:
1. Multi-step analysis with structured outputs
2. Data comparison and trend identification
3. Executive summary generation
4. Actionable recommendation extraction

Enterprise Deployment Blocker this solves:
"We have data everywhere but can't get synthesized insights fast enough."
→ Solution: Agent that can search, analyze, compare, and summarize.
"""

from __future__ import annotations

import json

from src.agents.base import AgentContext, AgentRole
from src.agents.react import ReActAgent
from src.tools import api as tool_api

ANALYST_DOMAIN_PROMPT = """\
You are an enterprise analyst agent. You help users analyze information,
compare options, identify trends, and generate actionable insights.

Your analysis should always be:
1. Structured — use clear sections and bullet points
2. Evidence-based — cite data sources and numbers
3. Actionable — end with specific recommendations
4. Balanced — present trade-offs and risks

Output format for analysis:
## Summary
<1-2 sentence executive summary>

## Key Findings
- Finding 1 (with supporting data)
- Finding 2 (with supporting data)

## Analysis
<detailed analysis>

## Recommendations
1. <specific action> — Rationale: <why>
2. <specific action> — Rationale: <why>

## Risks & Trade-offs
- Risk 1: <description> — Mitigation: <approach>
"""


class AnalystAgent(ReActAgent):
    """Analysis agent with ReAct reasoning for structured insights.

    Uses the ReAct reasoning loop:
    Thought (what to analyze) → Action (search/compare) → Observation (data) → ... → Final Answer (structured analysis)
    """

    def __init__(self, search_tool=None):
        super().__init__(
            name="analyst",
            role=AgentRole.ANALYST,
            description="Analyzes data, compares options, and generates structured insights with recommendations",
        )
        self._search_tool = search_tool
        self._register_tools()

    @property
    def domain_instructions(self) -> str:
        return ANALYST_DOMAIN_PROMPT

    def _register_tools(self):
        self.register_tool(
            func=self._search_for_analysis,
            name="search_for_analysis",
            description=(
                "Search the knowledge base to gather data for analysis. "
                "Use this to find relevant documents, metrics, and context."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to find relevant data for analysis",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results (default: 10 for broader analysis)",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        )

        self.register_tool(
            func=self._compare_documents,
            name="compare_documents",
            description="Compare two or more topics by searching for each and producing a structured comparison.",
            parameters={
                "type": "object",
                "properties": {
                    "topics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of topics/items to compare",
                    },
                    "criteria": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Comparison criteria (e.g., cost, performance, risk)",
                    },
                },
                "required": ["topics"],
            },
        )

    async def _search_for_analysis(self, query: str, top_k: int = 10) -> str:
        """Search via tools.api."""
        result = await tool_api.search_for_analysis(
            query=query, top_k=top_k, search_tool=self._search_tool,
        )
        return json.dumps(result, default=str)

    async def _compare_documents(
        self,
        topics: list[str],
        criteria: list[str] | None = None,
    ) -> str:
        """Compare via tools.api."""
        result = await tool_api.compare_documents(
            topics=topics, criteria=criteria, search_tool=self._search_tool,
        )
        return json.dumps(result, default=str)

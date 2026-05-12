"""Analysis Skill — Structured insight generation and comparison.

Reusable skill for multi-step data analysis, trend identification,
and recommendation generation.

Enterprise Pattern Solved:
"We have data everywhere but can't get synthesized insights fast enough."
→ Structured analysis with evidence + recommendations + risks.
"""

from __future__ import annotations

import json

from src.skills.base import Skill, ToolSchema


class AnalysisSkill(Skill):
    """Structured analysis, comparison, and recommendation generation."""

    @property
    def name(self) -> str:
        return "analysis"

    @property
    def description(self) -> str:
        return (
            "Analyze information, compare options, identify trends, "
            "and generate actionable insights with structured output "
            "(summary, findings, recommendations, risks)."
        )

    @property
    def tags(self) -> list[str]:
        return ["analysis", "insights", "comparison", "recommendations"]

    def get_tools(self) -> list[ToolSchema]:
        return [
            ToolSchema(
                name="compare_options",
                description=(
                    "Compare two or more options against specified criteria. "
                    "Returns a structured comparison table with pros/cons."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "options": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Options to compare",
                        },
                        "criteria": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Evaluation criteria (e.g., cost, performance, risk)",
                        },
                    },
                    "required": ["options"],
                },
                handler=self._compare_handler,
            ),
            ToolSchema(
                name="summarize_findings",
                description=(
                    "Generate a structured executive summary from raw data or text. "
                    "Outputs: summary, key findings, recommendations, risks."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "string",
                            "description": "Raw data or text to summarize",
                        },
                        "focus": {
                            "type": "string",
                            "description": "What aspect to focus the analysis on",
                        },
                    },
                    "required": ["data"],
                },
                handler=self._summarize_handler,
            ),
        ]

    def get_system_prompt_fragment(self) -> str:
        return (
            "When analyzing, always structure output as: "
            "Summary → Key Findings → Recommendations → Risks & Trade-offs. "
            "Be evidence-based and actionable."
        )

    async def _compare_handler(
        self,
        options: list[str],
        criteria: list[str] | None = None,
    ) -> str:
        criteria = criteria or ["cost", "performance", "risk", "adoption_ease"]
        comparison = {
            "options": options,
            "criteria": criteria,
            "instruction": (
                "Evaluate each option against each criterion. "
                "For each cell, provide: rating (1-5), brief justification."
            ),
        }
        return json.dumps(comparison, indent=2)

    async def _summarize_handler(self, data: str, focus: str | None = None) -> str:
        return json.dumps({
            "data_length": len(data),
            "focus": focus or "general",
            "instruction": (
                "Analyze this data and produce: "
                "1) Executive Summary (2-3 sentences), "
                "2) Key Findings (bullet points with evidence), "
                "3) Recommendations (specific actions with rationale), "
                "4) Risks (with severity and mitigation)."
            ),
            "data_preview": data[:2000],
        }, indent=2)

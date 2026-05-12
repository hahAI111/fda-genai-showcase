"""Search Skill — Enterprise knowledge retrieval via Azure AI Search.

Reusable skill for hybrid search (vector + keyword + semantic ranking).
Any agent can load this skill to gain knowledge retrieval capability.

Enterprise Pattern Solved:
"Data is in 5 systems — how do we unify retrieval?"
→ One search skill, consistent across all agents.
"""

from __future__ import annotations

import json
from typing import Any

from src.skills.base import Skill, ToolSchema
from src.tools.search import AISearchTool


class SearchSkill(Skill):
    """Hybrid knowledge search — vector + keyword + semantic ranking."""

    def __init__(self, search_tool: AISearchTool | None = None):
        self._search = search_tool or AISearchTool()

    @property
    def name(self) -> str:
        return "search"

    @property
    def description(self) -> str:
        return (
            "Search the enterprise knowledge base using hybrid retrieval "
            "(vector + keyword + semantic ranking). Returns relevant documents "
            "with citations, scores, and source attribution."
        )

    @property
    def tags(self) -> list[str]:
        return ["retrieval", "rag", "knowledge", "search"]

    def get_tools(self) -> list[ToolSchema]:
        return [
            ToolSchema(
                name="search_knowledge_base",
                description=(
                    "Search enterprise knowledge base. Uses hybrid retrieval "
                    "(keyword + vector + semantic re-ranking) for best results. "
                    "Returns documents with title, content, source, and relevance score."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query — be specific for best results",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of results (default: 5)",
                            "default": 5,
                        },
                        "category": {
                            "type": "string",
                            "description": "Filter by category: policy, technical, hr, general",
                        },
                    },
                    "required": ["query"],
                },
                handler=self._search_handler,
            ),
            ToolSchema(
                name="get_document_by_id",
                description="Retrieve a specific document by its ID for detailed analysis.",
                parameters={
                    "type": "object",
                    "properties": {
                        "document_id": {
                            "type": "string",
                            "description": "The document ID to retrieve",
                        },
                    },
                    "required": ["document_id"],
                },
                handler=self._get_document_handler,
            ),
        ]

    def get_system_prompt_fragment(self) -> str:
        return (
            "You have access to an enterprise knowledge base via the search_knowledge_base tool. "
            "Always search before answering factual questions. Cite sources using [Source: title] format."
        )

    async def _search_handler(
        self, query: str, top_k: int = 5, category: str | None = None
    ) -> str:
        filters = f"category eq '{category}'" if category else None
        try:
            results = await self._search.search(
                query=query, top_k=top_k, filters=filters
            )
            return self._format(results)
        except Exception as e:
            # Fallback for demo without AI Search configured
            return json.dumps({
                "status": "demo_mode",
                "query": query,
                "note": "AI Search not configured. Sample results returned.",
                "results": [
                    {
                        "title": "Enterprise AI Governance Policy v2.1",
                        "content": "All AI models must undergo evaluation before production deployment. "
                                   "PII handling requires encryption at rest and in transit.",
                        "source": "policies/ai-governance-policy.md",
                        "score": 0.95,
                    },
                    {
                        "title": "RAG Architecture Technical Guide",
                        "content": "Hybrid retrieval (keyword + vector + semantic) outperforms "
                                   "pure vector search by 15-20% on evaluation benchmarks.",
                        "source": "technical/rag-architecture.md",
                        "score": 0.88,
                    },
                ],
            }, indent=2)

    async def _get_document_handler(self, document_id: str) -> str:
        try:
            doc = await self._search.get_document(document_id)
            return json.dumps(doc, default=str) if doc else f"Document '{document_id}' not found."
        except Exception:
            return f"Could not retrieve document '{document_id}'."

    def _format(self, results: list[dict[str, Any]]) -> str:
        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(
                f"[Document {i}]\n"
                f"Title: {r.get('title', 'Untitled')}\n"
                f"Source: {r.get('source', 'Unknown')}\n"
                f"Score: {r.get('score', 0):.2f}\n"
                f"Content:\n{r.get('content', '')}\n"
            )
        return "\n---\n".join(formatted) if formatted else "No results found."

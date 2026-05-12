"""Knowledge Agent — Enterprise RAG with Azure AI Search.

This agent demonstrates production-grade RAG patterns:
1. Hybrid search (vector + keyword) for best recall
2. Citation tracking — every claim linked to source
3. Grounding enforcement — only answer from retrieved context
4. Chunk-level relevance filtering
5. Source attribution with confidence scoring

Enterprise Deployment Blocker this solves:
"We can't trust AI answers because we don't know where they come from."
→ Solution: Full citation chain from query → retrieval → generation.
"""

from __future__ import annotations

import json
from typing import Any

from src.agents.base import AgentContext, AgentRole
from src.agents.react import ReActAgent
from src.tools import api as tool_api

KNOWLEDGE_DOMAIN_PROMPT = """\
You are an enterprise knowledge assistant. You answer questions ONLY based on
the retrieved documents provided to you via the search_knowledge tool.

Rules:
1. ALWAYS use the search_knowledge tool before answering
2. Only use information from the retrieved documents
3. Cite sources using [Source: <title>] format after each claim
4. If the retrieved documents don't contain the answer, say so clearly
5. Never fabricate information — grounding is non-negotiable
6. Provide structured, actionable answers

When citing, use this format:
"According to [Source: Document Title], the policy states that..."
"""


class KnowledgeAgent(ReActAgent):
    """RAG agent with Azure AI Search — hybrid retrieval + grounded generation.

    Uses the ReAct reasoning loop:
    Thought (what to search) → Action (search_knowledge) → Observation (results) → ... → Final Answer (grounded response)
    """

    def __init__(self, search_tool=None):
        super().__init__(
            name="knowledge",
            role=AgentRole.KNOWLEDGE,
            description="Answers questions using enterprise knowledge base with full citations",
        )
        self._search_tool = search_tool
        self._register_tools()

    @property
    def domain_instructions(self) -> str:
        return KNOWLEDGE_DOMAIN_PROMPT

    def _register_tools(self):
        self.register_tool(
            func=self._search_knowledge,
            name="search_knowledge",
            description=(
                "Search the enterprise knowledge base using hybrid search "
                "(vector + keyword). Returns relevant document chunks with "
                "titles, content, and relevance scores."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query — be specific and detailed",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to retrieve (default: 5)",
                        "default": 5,
                    },
                    "use_vector": {
                        "type": "boolean",
                        "description": "Whether to use vector search (default: true)",
                        "default": True,
                    },
                    "filters": {
                        "type": "string",
                        "description": "OData filter expression for metadata filtering",
                    },
                },
                "required": ["query"],
            },
        )

    async def _search_knowledge(
        self,
        query: str,
        top_k: int = 5,
        use_vector: bool = True,
        filters: str | None = None,
    ) -> str:
        """Execute hybrid search via tools.api."""
        results = await tool_api.search_knowledge(
            query=query, top_k=top_k, use_vector=use_vector,
            filters=filters, search_tool=self._search_tool,
        )
        return self._format_results(results)

    def _format_results(self, results: list[dict[str, Any]]) -> str:
        """Format search results for the LLM context window."""
        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(
                f"[Document {i}]\n"
                f"Title: {r.get('title', 'Untitled')}\n"
                f"Source: {r.get('source', 'Unknown')}\n"
                f"Relevance: {r.get('score', 0):.2f}\n"
                f"Content:\n{r.get('content', '')}\n"
            )
        return "\n---\n".join(formatted) if formatted else "No results found."

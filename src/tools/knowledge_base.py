"""Knowledge Base — Agentic Retrieval via Azure AI Search REST API.

Calls the real Agentic Retrieval endpoint:
  POST {search_endpoint}/knowledgebases('{kb_name}')/retrieve?api-version=2026-04-01

The Knowledge Base and Knowledge Sources must already exist on the
Search Service (created via setup_agentic_retrieval.py or Portal).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
import structlog

from src.tools.knowledge_source import KnowledgeSourceManager, KnowledgeSource

logger = structlog.get_logger()

API_VERSION = "2026-04-01"


@dataclass
class RetrieveActivity:
    """Single activity record from the retrieve response."""
    type: str
    id: int
    elapsed_ms: int = 0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrieveReference:
    """A source reference returned by the retrieve API."""
    ref_type: str
    ref_id: str
    activity_source: int
    reranker_score: float = 0.0
    source_data: dict[str, Any] = field(default_factory=dict)
    doc_key: str = ""


@dataclass
class RetrieveResult:
    """Parsed result from the Agentic Retrieval API."""
    query: str
    response_text: str
    grounding_data: list[dict[str, Any]]
    source_citations: list[dict[str, Any]]
    execution_plan: dict[str, Any]
    sub_query_results: list[dict[str, Any]]
    activities: list[RetrieveActivity] = field(default_factory=list)
    references: list[RetrieveReference] = field(default_factory=list)
    synthesis: Optional[str] = None


class KnowledgeBase:
    """Calls Azure AI Search Agentic Retrieval REST API.

    Supports two auth modes:
      - API key: pass search_api_key
      - Identity (DefaultAzureCredential): pass credential instead
    """

    def __init__(
        self,
        search_endpoint: str,
        search_api_key: str = "",
        kb_name: str = "kb-enterprise",
        source_manager: Optional[KnowledgeSourceManager] = None,
        credential: Any = None,
    ):
        self.search_endpoint = search_endpoint.rstrip("/")
        self.search_api_key = search_api_key
        self.kb_name = kb_name
        self.source_manager = source_manager or KnowledgeSourceManager()
        self._client = httpx.AsyncClient(timeout=90.0)
        self._credential = credential  # azure.identity credential

    def _get_headers(self) -> dict[str, str]:
        """Return auth headers — prefer Bearer token over API key."""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._credential is not None:
            token = self._credential.get_token("https://search.azure.com/.default")
            headers["Authorization"] = f"Bearer {token.token}"
        elif self.search_api_key:
            headers["api-key"] = self.search_api_key
        return headers

    def register_source(self, source: KnowledgeSource) -> None:
        self.source_manager.register(source)

    async def retrieve_and_plan(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        reasoning_effort: str = "medium",
    ) -> RetrieveResult:
        """Call the real Agentic Retrieval API.

        POST {endpoint}/knowledgebases('{kb_name}')/retrieve?api-version=2026-04-01
        """
        start = time.perf_counter()
        url = (
            f"{self.search_endpoint}/knowledgebases('{self.kb_name}')"
            f"/retrieve?api-version={API_VERSION}"
        )
        headers = self._get_headers()

        body: dict[str, Any] = {
            "maxRuntimeInSeconds": 60,
            "maxOutputSizeInTokens": 50000,
            "includeActivity": True,
        }

        # If sources are registered, add their params
        source_params = self.source_manager.get_retrieve_params()
        if source_params:
            body["knowledgeSourceParams"] = source_params

        # Use semantic intent so the KB does query planning via LLM
        body["intents"] = [{"search": query, "type": "semantic"}]

        logger.info(
            "knowledge_base.retrieve.start",
            query=query,
            kb_name=self.kb_name,
            conversation_id=conversation_id,
        )

        resp = await self._client.post(url, headers=headers, json=body)
        elapsed_ms = (time.perf_counter() - start) * 1000

        if resp.status_code not in (200, 206):
            error_text = resp.text[:500]
            logger.error(
                "knowledge_base.retrieve.api_error",
                status=resp.status_code,
                error=error_text,
            )
            raise RuntimeError(
                f"Agentic Retrieval API returned {resp.status_code}: {error_text}"
            )

        data = resp.json()
        return self._parse_response(query, data, elapsed_ms)

    def _parse_response(
        self, query: str, data: dict[str, Any], elapsed_ms: float
    ) -> RetrieveResult:
        """Parse the raw API response into a RetrieveResult."""

        # --- response text ---
        response_text = ""
        for msg in data.get("response", []):
            for content in msg.get("content", []):
                if content.get("type") == "text":
                    response_text += content.get("text", "")

        # --- activities ---
        activities: list[RetrieveActivity] = []
        sub_query_results: list[dict[str, Any]] = []
        for a in data.get("activity", []):
            atype = a.get("type", "")
            act = RetrieveActivity(
                type=atype,
                id=a.get("id", 0),
                elapsed_ms=a.get("elapsedMs", 0),
                details={k: v for k, v in a.items() if k not in ("type", "id", "elapsedMs")},
            )
            activities.append(act)

            # Build sub_query_results from searchIndex activities
            if atype in ("searchIndex", "azureBlob"):
                args = a.get("searchIndexArguments", {})
                sub_query_results.append({
                    "type": atype,
                    "knowledge_source": a.get("knowledgeSourceName", ""),
                    "search": args.get("search", query),
                    "count": a.get("count", 0),
                    "elapsed_ms": a.get("elapsedMs", 0),
                })

        # --- references → grounding_data + citations ---
        grounding_data: list[dict[str, Any]] = []
        source_citations: list[dict[str, Any]] = []
        for ref in data.get("references", []):
            sd = ref.get("sourceData") or {}
            item = {
                "title": sd.get("title", ""),
                "content": sd.get("content", ""),
                "source": sd.get("source_url", ""),
                "ref_type": ref.get("type", ""),
                "reranker_score": ref.get("rerankerScore", 0),
                "doc_key": ref.get("docKey", ""),
            }
            grounding_data.append(item)
            source_citations.append({
                "index": len(source_citations) + 1,
                "title": item["title"],
                "ref_type": ref.get("type", ""),
                "reranker_score": ref.get("rerankerScore", 0),
                "doc_key": ref.get("docKey", ""),
            })

        # --- execution plan summary ---
        execution_plan = {
            "user_query": query,
            "kb_name": self.kb_name,
            "total_activities": len(activities),
            "total_references": len(grounding_data),
            "elapsed_ms": round(elapsed_ms, 2),
            "activity_summary": [
                {"id": a.id, "type": a.type, "elapsed_ms": a.elapsed_ms}
                for a in activities
            ],
        }

        logger.info(
            "knowledge_base.retrieve.complete",
            query=query,
            references=len(grounding_data),
            activities=len(activities),
            elapsed_ms=round(elapsed_ms, 2),
        )

        return RetrieveResult(
            query=query,
            response_text=response_text,
            grounding_data=grounding_data,
            source_citations=source_citations,
            execution_plan=execution_plan,
            sub_query_results=sub_query_results,
            activities=activities,
            references=[
                RetrieveReference(
                    ref_type=r.get("type", ""),
                    ref_id=r.get("id", ""),
                    activity_source=r.get("activitySource", 0),
                    reranker_score=r.get("rerankerScore", 0),
                    source_data=r.get("sourceData") or {},
                    doc_key=r.get("docKey", ""),
                )
                for r in data.get("references", [])
            ],
            synthesis=response_text[:2000] if response_text else None,
        )

    async def close(self) -> None:
        await self._client.aclose()

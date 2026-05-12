"""Azure AI Search Tool — Hybrid retrieval (vector + keyword + semantic ranking).

Enterprise Pattern: Hybrid search combines the precision of keyword search
with the semantic understanding of vector search, then re-ranks with a
cross-encoder for best results. This is the production-grade retrieval
pattern — not just naive vector similarity.

Supports both identity-based auth and API key auth.
"""

from __future__ import annotations

from typing import Any

import structlog
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizableTextQuery

from src.config import get_credential, get_settings

logger = structlog.get_logger()


class AISearchTool:
    """Azure AI Search with hybrid retrieval and semantic ranking."""

    def __init__(
        self,
        endpoint: str | None = None,
        index_name: str | None = None,
        credential: DefaultAzureCredential | AzureKeyCredential | None = None,
    ):
        settings = get_settings()
        self._endpoint = endpoint or settings.azure_search_endpoint
        self._index_name = index_name or settings.azure_search_index
        self._credential = credential or self._resolve_credential()
        self._client: SearchClient | None = None

    def _resolve_credential(self) -> DefaultAzureCredential | AzureKeyCredential:
        settings = get_settings()
        if settings.azure_search_api_key:
            return AzureKeyCredential(settings.azure_search_api_key)
        return get_credential()

    def _get_client(self) -> SearchClient:
        if self._client is None:
            self._client = SearchClient(
                endpoint=self._endpoint,
                index_name=self._index_name,
                credential=self._credential,
            )
        return self._client

    async def search(
        self,
        query: str,
        top_k: int = 5,
        use_vector: bool = True,
        filters: str | None = None,
        semantic_config: str = "default",
    ) -> list[dict[str, Any]]:
        """Execute hybrid search with optional vector and semantic ranking.

        Retrieval strategy:
        1. Keyword search (BM25) — handles exact matches, acronyms
        2. Vector search — handles semantic similarity, paraphrasing
        3. Semantic ranking (cross-encoder) — re-ranks for relevance

        This 3-stage approach is the enterprise best practice.
        """
        client = self._get_client()

        search_kwargs: dict[str, Any] = {
            "search_text": query,
            "top": top_k,
            "query_type": "semantic",
            "semantic_configuration_name": semantic_config,
            "include_total_count": True,
        }

        if filters:
            search_kwargs["filter"] = filters

        if use_vector:
            search_kwargs["vector_queries"] = [
                VectorizableTextQuery(
                    text=query,
                    k_nearest_neighbors=top_k * 2,
                    fields="content_vector",
                    exhaustive=False,
                )
            ]

        try:
            results = client.search(**search_kwargs)

            documents = []
            for result in results:
                doc = {
                    "title": result.get("title", "Untitled"),
                    "content": result.get("content", ""),
                    "source": result.get("source_url", result.get("source", "")),
                    "score": result.get("@search.score", 0),
                    "reranker_score": result.get("@search.reranker_score", 0),
                    "category": result.get("category", ""),
                    "chunk_id": result.get("chunk_id", ""),
                }
                if hasattr(result, "captions") and result.captions:
                    doc["caption"] = result.captions[0].text
                documents.append(doc)

            logger.info(
                "search.completed",
                query=query[:100],
                results=len(documents),
                use_vector=use_vector,
            )
            return documents

        except Exception as e:
            logger.error("search.failed", query=query[:100], error=str(e))
            raise RuntimeError(f"Search failed for query '{query[:80]}': {e}") from e

    async def get_document(self, doc_id: str) -> dict[str, Any] | None:
        """Retrieve a specific document by ID."""
        client = self._get_client()
        try:
            return client.get_document(key=doc_id)
        except Exception:
            return None

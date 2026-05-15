"""Knowledge Source — Agentic Retrieval data source references.

Knowledge Sources are pre-created on Azure AI Search via the management API
(api-version=2026-04-01). This module provides lightweight Python wrappers
for the Retrieve API's knowledgeSourceParams.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

import structlog

logger = structlog.get_logger()


class KnowledgeSourceType(str, Enum):
    SEARCH_INDEX = "searchIndex"
    AZURE_BLOB = "azureBlob"
    INDEXED_ONE_LAKE = "indexedOneLake"
    WEB = "web"


class KnowledgeSource:
    """Reference to a Knowledge Source that exists on Azure AI Search."""

    def __init__(self, name: str, source_type: KnowledgeSourceType, **kwargs: Any):
        self.name = name
        self.source_type = source_type
        self.config = kwargs

    def to_param(self) -> dict[str, Any]:
        """Return a knowledgeSourceParams entry for the Retrieve API."""
        return {
            "knowledgeSourceName": self.name,
            "includeReferences": True,
            "includeReferenceSourceData": True,
            "kind": self.source_type.value,
        }

    # ── Convenience factories (kept for backward compat) ─────
    @classmethod
    def from_search_index(cls, name: str, **kwargs: Any) -> KnowledgeSource:
        return cls(name=name, source_type=KnowledgeSourceType.SEARCH_INDEX, **kwargs)

    @classmethod
    def from_azure_blob(cls, name: str, **kwargs: Any) -> KnowledgeSource:
        return cls(name=name, source_type=KnowledgeSourceType.AZURE_BLOB, **kwargs)

    @classmethod
    def web_source(cls, name: str = "bing-search") -> KnowledgeSource:
        return cls(name=name, source_type=KnowledgeSourceType.WEB)


class KnowledgeSourceManager:
    """Registry of Knowledge Source references."""

    def __init__(self) -> None:
        self._sources: dict[str, KnowledgeSource] = {}

    def register(self, source: KnowledgeSource) -> None:
        self._sources[source.name] = source
        logger.info("knowledge_source.registered", name=source.name, type=source.source_type.value)

    def get(self, name: str) -> Optional[KnowledgeSource]:
        return self._sources.get(name)

    def list_sources(self) -> list[KnowledgeSource]:
        return list(self._sources.values())

    def get_retrieve_params(self) -> list[dict[str, Any]]:
        """Build knowledgeSourceParams array for the Retrieve API."""
        return [s.to_param() for s in self._sources.values()]

"""Test Agentic Retrieval Knowledge Source and Knowledge Base wrappers.

Tests:
1. Knowledge Source creation and registration
2. Knowledge Base initialization
3. Retrieve API call (skipped if no Search Service)
"""

from __future__ import annotations

import pytest
from src.tools.knowledge_source import (
    KnowledgeSource,
    KnowledgeSourceType,
    KnowledgeSourceManager,
)
from src.tools.knowledge_base import KnowledgeBase, RetrieveResult


class TestKnowledgeSource:
    """Test Knowledge Source definition and registration."""

    def test_create_search_index_source(self):
        source = KnowledgeSource.from_search_index(name="enterprise-index")
        assert source.name == "enterprise-index"
        assert source.source_type == KnowledgeSourceType.SEARCH_INDEX

    def test_create_blob_source(self):
        source = KnowledgeSource.from_azure_blob(name="enterprise-docs")
        assert source.name == "enterprise-docs"
        assert source.source_type == KnowledgeSourceType.AZURE_BLOB

    def test_create_web_source(self):
        source = KnowledgeSource.web_source()
        assert source.name == "bing-search"
        assert source.source_type == KnowledgeSourceType.WEB

    def test_source_to_param(self):
        source = KnowledgeSource.from_search_index(name="ks-test")
        param = source.to_param()
        assert param["knowledgeSourceName"] == "ks-test"
        assert param["kind"] == "searchIndex"
        assert param["includeReferences"] is True


class TestKnowledgeSourceManager:

    def test_register_and_list(self):
        mgr = KnowledgeSourceManager()
        mgr.register(KnowledgeSource.from_search_index(name="idx"))
        mgr.register(KnowledgeSource.from_azure_blob(name="blob"))
        assert len(mgr.list_sources()) == 2

    def test_get_retrieve_params(self):
        mgr = KnowledgeSourceManager()
        mgr.register(KnowledgeSource.from_search_index(name="ks-a"))
        mgr.register(KnowledgeSource.from_azure_blob(name="ks-b"))
        params = mgr.get_retrieve_params()
        assert len(params) == 2
        assert params[0]["kind"] == "searchIndex"
        assert params[1]["kind"] == "azureBlob"


class TestKnowledgeBase:

    def test_init(self):
        kb = KnowledgeBase(
            search_endpoint="https://test.search.windows.net",
            search_api_key="key",
            kb_name="kb-test",
        )
        assert kb.kb_name == "kb-test"

    def test_register_sources(self):
        kb = KnowledgeBase(
            search_endpoint="https://test.search.windows.net",
            search_api_key="key",
        )
        kb.register_source(KnowledgeSource.from_search_index(name="ks-idx"))
        kb.register_source(KnowledgeSource.from_azure_blob(name="ks-blob"))
        assert len(kb.source_manager.list_sources()) == 2

    def test_parse_response(self):
        kb = KnowledgeBase(
            search_endpoint="https://test.search.windows.net",
            search_api_key="key",
        )
        raw = {
            "response": [
                {"content": [{"type": "text", "text": "Hello world"}]}
            ],
            "activity": [
                {"type": "searchIndex", "id": 0, "elapsedMs": 100,
                 "knowledgeSourceName": "ks-idx", "count": 2,
                 "searchIndexArguments": {"search": "test"}},
                {"type": "agenticReasoning", "id": 1, "reasoningTokens": 50},
            ],
            "references": [
                {"type": "searchIndex", "id": "r1", "activitySource": 0,
                 "rerankerScore": 3.5, "docKey": "doc1",
                 "sourceData": {"title": "Doc 1", "content": "Content 1"}},
            ],
        }
        result = kb._parse_response("test query", raw, 150.0)

        assert isinstance(result, RetrieveResult)
        assert result.query == "test query"
        assert result.response_text == "Hello world"
        assert len(result.grounding_data) == 1
        assert result.grounding_data[0]["title"] == "Doc 1"
        assert len(result.source_citations) == 1
        assert len(result.activities) == 2
        assert result.execution_plan["total_activities"] == 2
        assert result.execution_plan["total_references"] == 1
        assert len(result.sub_query_results) == 1
        assert result.sub_query_results[0]["search"] == "test"


# Integration test with API (requires running server)
@pytest.mark.asyncio
async def test_retrieve_endpoint_integration():
    """Test /retrieve endpoint via FastAPI TestClient.
    
    Note: This requires the app to be initialized.
    """
    pytest.skip("Requires running FastAPI app instance")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Agentic Retrieval — Usage Guide

## Overview

This project implements an **Agentic Retrieval** system that supports:

1. **Multi-source knowledge retrieval** — 6 data source types (Azure Search, Azure Blob, OneLake, SharePoint, Web, Bing)
2. **LLM-driven query planning** — Automatically decomposes complex queries into sub-queries
3. **Parallel execution** — Sub-queries run concurrently across multiple knowledge sources
4. **Structured results** — Returns grounding data, source citations, execution plan, sub-query results
5. **End-to-end governance** — Content safety, PII filtering, audit logging on every request

## Architecture

```
User Query
    ↓
[Content Safety] → Input screening
    ↓
[PII Filter] → Mask sensitive data
    ↓
[Knowledge Base] → LLM query planning + parallel search + aggregation
    │
    ├─→ [Sub-query 1] → [Source A, B] (parallel)
    ├─→ [Sub-query 2] → [Source A, B] (parallel)
    └─→ [Sub-query 3] → [Source A, B] (parallel)
    ↓
[Content Safety] → Output screening
    ↓
[Audit Logger] → Compliance logging
    ↓
Structured Response
```

## Core Components

### 1. Knowledge Source

Defined in `src/tools/knowledge_source.py`

**Supported source types:**

| Type | Description | Configuration |
|------|-------------|---------------|
| `searchIndex` | Azure AI Search index | endpoint, index_name, api_key |
| `azureBlob` | Azure Blob Storage | account_url, container_name, account_key |
| `indexedOneLake` | Fabric Lakehouse (indexed) | workspace_id, lakehouse_id, table_name |
| `indexedSharePoint` | SharePoint Online (indexed) | site_url, list_id |
| `remoteSharePoint` | SharePoint Online (live query) | site_url, list_id |
| `web` | Bing web search | (no configuration needed) |

**Example:**

```python
from src.tools.knowledge_source import KnowledgeSource, KnowledgeSourceType

# Create an Azure AI Search source
search_source = KnowledgeSource.from_search_index(
    name="enterprise-knowledge",
    endpoint="https://your-search.search.windows.net",
    index_name="enterprise-knowledge",
    api_key="your-api-key",
)

# Create a Web source
web_source = KnowledgeSource.web_source()
```

### 2. Knowledge Base

Defined in `src/tools/knowledge_base.py`

**Responsibilities:**
- Manage lifecycle of multiple knowledge sources
- Coordinate LLM query planning
- Execute parallel multi-source search
- Aggregate and deduplicate results

**Key methods:**

```python
from src.tools.knowledge_base import KnowledgeBase

kb = KnowledgeBase()

# Register knowledge sources
kb.register_source(search_source)
kb.register_source(web_source)

# Execute Agentic Retrieval
result = await kb.retrieve_and_plan(
    query="How is multi-agent orchestration implemented?",
    conversation_id="conv-123",
    reasoning_effort="medium",  # "low", "medium", "high"
)

# Access results
print(result.grounding_data)      # Grounding content
print(result.source_citations)    # Source citations
print(result.execution_plan)      # Execution plan (sub-queries, sources)
print(result.sub_query_results)   # Per sub-query execution results
```

## API Usage

### /retrieve Endpoint

`POST /retrieve` endpoint for Agentic Retrieval queries.

**Request format:**

```json
{
    "query": "How do I implement a RAG system?",
    "conversation_id": "conv-123",
    "user_id": "user-123",
    "tenant_id": "tenant-123",
    "reasoning_effort": "medium"
}
```

**Response format:**

```json
{
    "query": "How do I implement a RAG system?",
    "grounding_data": [
        {
            "title": "RAG Architecture Design",
            "content": "Retrieval-Augmented Generation works by...",
            "source": "https://...",
            "score": 0.95,
            "reranker_score": 0.92
        }
    ],
    "source_citations": [
        {
            "index": 1,
            "title": "RAG Architecture Design",
            "source_url": "https://...",
            "sources": ["enterprise-knowledge-index"]
        }
    ],
    "execution_plan": {
        "user_query": "How do I implement a RAG system?",
        "sub_queries": [
            "RAG core concepts and principles",
            "RAG implementation steps and best practices",
            "RAG performance optimization techniques"
        ],
        "sources": ["enterprise-knowledge-index", "bing-search"],
        "planned_at": "2025-01-15T10:30:00.000Z"
    },
    "sub_query_results": [
        {
            "sub_query": "RAG core concepts and principles",
            "source_name": "enterprise-knowledge-index",
            "results_count": 3,
            "execution_time_ms": 125.5,
            "top_results": [...]
        }
    ],
    "synthesis": null,
    "conversation_id": "conv-123",
    "governance": {
        "input_safety": {
            "level": "safe",
            "flags": []
        },
        "pii": {
            "detected": false,
            "types": [],
            "count": 0
        },
        "output_safety": {
            "level": "mixed",
            "items_screened": 3
        }
    },
    "performance": {
        "total_latency_ms": 250.3,
        "items_retrieved": 3,
        "sub_queries": 3
    },
    "latency_ms": 250.3
}
```

## Usage Examples

### Python Client

```python
import httpx
import asyncio

async def retrieve_with_agentic_rag():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/retrieve",
            json={
                "query": "What is the multi-agent architecture of this platform?",
                "conversation_id": "demo-001",
                "reasoning_effort": "medium",
            }
        )
        result = response.json()

        # Process results
        print("Grounding data:")
        for item in result["grounding_data"]:
            print(f"  - {item['title']}")

        print("\nExecution plan:")
        print(f"  Sub-queries: {result['execution_plan']['sub_queries']}")
        print(f"  Sources: {result['execution_plan']['sources']}")

        print(f"\nTotal latency: {result['latency_ms']:.2f} ms")

asyncio.run(retrieve_with_agentic_rag())
```

### cURL Example

```bash
curl -X POST http://localhost:8000/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How do I integrate Azure AI with FastAPI?",
    "reasoning_effort": "high"
  }'
```

## Comparison: /chat vs /retrieve

| Feature | /chat (Agent) | /retrieve (Agentic RAG) |
|---------|---------------|------------------------|
| Purpose | Multi-agent orchestration | Structured knowledge retrieval |
| Output | Natural language answer | Grounding data + citations |
| Query planning | Agent-driven | LLM decomposes into sub-queries |
| Parallel execution | Limited (agent sequential) | Fully parallel |
| Result aggregation | Agent-managed | System auto-dedup |
| Governance | Full (safety, audit) | Full (safety, audit) |

## Extension Guide

### Adding a New Knowledge Source

1. Define a new type in `KnowledgeSourceType`

```python
class KnowledgeSourceType(str, Enum):
    # ... existing types
    MY_CUSTOM_SOURCE = "myCustomSource"
```

2. Add search logic in `KnowledgeBase._search_index()`

```python
async def _search_index(...):
    # ... existing code
    elif source.source_type.value == "myCustomSource":
        source_results = await self._search_custom_source(sub_query, source)
```

3. Register the source during initialization in `main.py`

```python
custom_source = KnowledgeSource(
    name="my-source",
    source_type=KnowledgeSourceType.MY_CUSTOM_SOURCE,
    # ... configuration
)
knowledge_base.register_source(custom_source)
```

### Enhancing Query Planning

Modify `KnowledgeBase._plan_queries()` for smarter LLM-driven query decomposition:

```python
async def _plan_queries(self, user_query: str) -> list[str]:
    planning_prompt = f"""
    User query: {user_query}
    
    Decompose into 2-4 specific sub-queries...
    """
    response = await self._call_azure_openai(planning_prompt)
    return response["sub_queries"]
```

## Monitoring and Debugging

### Audit Logs

All `/retrieve` requests are logged to `logs/audit.jsonl`, including:
- Input and output safety screening results
- PII detection results
- Execution plan and sub-queries
- Latency and performance metrics

### Performance Metrics

The `performance` field in the response contains:
- `total_latency_ms` — Total request time
- `items_retrieved` — Number of retrieved documents
- `sub_queries` — Number of decomposed sub-queries

### Local Debugging

```python
# Enable verbose logging in src/tools/knowledge_base.py
import logging
logging.basicConfig(level=logging.DEBUG)

# Or use structlog context
with logger.context(debug=True):
    result = await kb.retrieve_and_plan(query)
```

## Limitations and Notes

1. **Query planning** — Currently uses heuristic rules, not LLM calls (can be enhanced via the extension guide above)
2. **Source authentication** — Relies on API keys or identity credentials from configuration
3. **Result size** — Each source returns up to 3 results by default; adjust the `top_k` parameter as needed
4. **Timeout** — Parallel search timeout is 30 seconds; configurable in settings

## Related Documentation

- [Architecture](ARCHITECTURE.md) — Full system architecture
- [README](../README.md) — Project overview and deployment guide
- [src/tools/knowledge_base.py](../src/tools/knowledge_base.py) — Implementation details
- [src/tools/knowledge_source.py](../src/tools/knowledge_source.py) — Source definitions

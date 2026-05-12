---
name: knowledge-retrieval
description: >
  Use this skill when answering any factual question about enterprise documents,
  policies, procedures, or technical guides. This is the primary RAG skill —
  performs hybrid search (vector + keyword + semantic ranking) against Vertex AI
  Search / Azure AI Search. Uses ReAct reasoning for transparent retrieval.
  Start here for any "what does the policy say" or "find information about" query.
  Keywords: search, find, document, policy, procedure, knowledge, RAG, retrieve,
  citation, source, reference.
allowed-tools:
  - vertex_ai_search
  - Read
---

# Knowledge Retrieval (Enterprise RAG)

## When to Use

Use this skill when you need to:
- Answer questions about enterprise policies, procedures, or technical docs
- Find specific information in the knowledge base
- Provide cited, grounded answers from authoritative sources
- Retrieve documents by topic, keyword, or semantic meaning

⚠️ **This is the default starting point for most knowledge questions.**

## When NOT to Use

- Need structured analysis or comparison → use [analysis](../analysis/SKILL.md)
- Need compliance/risk assessment → use [compliance-check](../compliance-check/SKILL.md)
- Need to generate reports or summaries → use [report-generation](../report-generation/SKILL.md)
- Query is about platform status or health → use `/health` API endpoint

## How It Works

The knowledge retrieval pipeline uses a 3-stage approach:

```
User Query
    │
    ▼
┌─────────────────────┐
│ Stage 1: Keyword    │  BM25 ranking — handles exact matches,
│ (Azure AI Search)   │  acronyms, product codes, policy numbers
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ Stage 2: Vector     │  HNSW approximate nearest neighbor —
│ (text-embedding-    │  handles paraphrasing, synonyms,
│  3-large, 3072d)    │  multilingual queries
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ Stage 3: Semantic   │  Cross-encoder re-ranking —
│ Ranking             │  final relevance ordering
└─────────────────────┘
```

This hybrid approach outperforms pure vector search by **15-20%** on evaluation benchmarks.

## Tool Configuration

### Azure AI Search

| Setting | Value |
|---------|-------|
| **Index** | `enterprise-knowledge` |
| **Vector Field** | `content_vector` (3072 dimensions) |
| **Vectorizer** | Azure OpenAI integrated (text-embedding-3-large) |
| **Semantic Config** | `default` (title + content fields) |
| **Auth** | DefaultAzureCredential (identity-based, no keys) |

### Search Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `top_k` | 5 | Number of results to retrieve |
| `use_vector` | true | Enable vector search component |
| `filters` | none | OData filter (e.g., `category eq 'policy'`) |
| `semantic_config` | `default` | Semantic ranking configuration |

## Grounding Rules

1. **ALWAYS search before answering** factual questions
2. **Only use information from retrieved documents** — never fabricate
3. **Cite sources** using `[Source: Document Title]` format after each claim
4. If retrieved documents **don't contain the answer**, say so explicitly
5. When citing, prefer: *"According to [Source: Title], the policy states that..."*

## Query Optimization Tips

| User Intent | Optimized Query Strategy |
|-------------|-------------------------|
| Exact policy lookup | Use keyword search with `category eq 'policy'` filter |
| Conceptual question | Use vector search (default) for semantic matching |
| Cross-document answer | Issue multiple searches, synthesize results |
| Recent changes | Add date filter: `created_at gt 2025-01-01` |

## Example Interactions

### Good: Grounded answer with citation
```
User: What is our AI governance policy for PII data?

Agent: According to [Source: Enterprise AI Governance Policy v2.1],
all AI systems processing PII must implement data minimization and
purpose limitation (§3.2). Additionally, encryption at rest and in
transit is required for all Restricted-class data, and a Privacy
Impact Assessment must be completed before deployment (§4.1).
```

### Good: Honest "not found"
```
User: What is our policy on quantum computing?

Agent: I searched the enterprise knowledge base for "quantum computing policy"
but found no matching documents. This topic may not be covered in the current
knowledge base. I recommend checking with the Technology Strategy team.
```

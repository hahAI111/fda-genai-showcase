# RAG Deployment Context

Load this context when working on enterprise RAG (Retrieval-Augmented Generation) deployments.

## Common Deployment Blockers

| Blocker | Symptom | Investigation |
|---------|---------|---------------|
| Low retrieval quality | Answers miss relevant docs | Check chunking strategy, embedding model, index config |
| Hallucination | Claims not in retrieved docs | Verify grounding prompt, check if context window overflow |
| High latency | > 3s end-to-end | Profile: search time + LLM time + network overhead |
| PII leakage | Sensitive data in responses | Verify PII filter is active, check training data |
| Low adoption | Users don't trust answers | Check citation quality, add confidence indicators |

## Architecture Decision Points

```
1. Chunking Strategy
   ├─ Fixed-size (simple, fast) — good for homogeneous docs
   ├─ Semantic (sentence-aware) — good for mixed content
   └─ Hierarchical (parent-child) — good for long documents

2. Retrieval Strategy
   ├─ Vector only — good for semantic queries
   ├─ Keyword only — good for exact matches
   └─ Hybrid (recommended) — best overall quality

3. Embedding Model
   ├─ text-embedding-3-small (1536d) — lower cost
   └─ text-embedding-3-large (3072d) — higher quality (recommended)

4. Generation Grounding
   ├─ System prompt only — lightweight but less reliable
   ├─ System prompt + citation requirement — recommended
   └─ System prompt + citation + confidence score — most robust
```

## Quality Benchmarks

| Metric | Target | Action if Below |
|--------|--------|-----------------|
| Retrieval Recall@5 | ≥ 85% | Improve chunking or add keyword search |
| Answer Relevance | ≥ 80% | Refine system prompt or add examples |
| Groundedness | ≥ 85% | Strengthen grounding prompt, reduce context noise |
| End-to-End Latency (p95) | ≤ 3s | Add caching, optimize search, reduce top_k |

# Enterprise RAG Architecture Pattern

## Pattern ID
`rag-enterprise`

## When to Use
- Customer has 1K–1M+ documents (policies, manuals, SOPs, regulatory filings)
- Users need natural-language Q&A with source attribution
- Accuracy and trust matter more than speed (legal, compliance, healthcare)
- Existing keyword search has low satisfaction (<60% resolution rate)

## When NOT to Use
- Real-time data (stock prices, live dashboards) → use function-calling agents instead
- Structured tabular data → use Text-to-SQL or analytics agents
- Simple FAQ (<100 questions) → fine-tuning or prompt engineering is cheaper

## Architecture Components

### Retrieval Layer
| Component | Azure Option | GCP Option | Open Source |
|-----------|-------------|------------|-------------|
| Vector + Keyword Search | Azure AI Search (hybrid) | Vertex AI Search | Elasticsearch + kNN |
| Embedding Model | text-embedding-3-large (3072d) | text-embedding-005 | Sentence Transformers |
| Reranking | Semantic Ranker (cross-encoder) | Vertex Search built-in | Cohere Rerank / ColBERT |
| Document Store | Azure Blob Storage | Cloud Storage | MinIO / S3 |

### Generation Layer
| Component | Azure Option | GCP Option | Open Source |
|-----------|-------------|------------|-------------|
| LLM | GPT-4.1 / GPT-4.1-mini | Gemini 2.5 Flash / Pro | Llama 3.3, Mistral |
| Grounding | System prompt enforcement | Vertex Grounding API | Custom prompt chain |
| Citation | Prompt-level [Source: X] | Vertex citation metadata | Custom post-processing |

### Governance Layer
| Component | Azure Option | GCP Option | Open Source |
|-----------|-------------|------------|-------------|
| Content Safety | Azure AI Content Safety | Vertex Responsible AI | Guardrails AI |
| PII Detection | Azure AI Language PII | Cloud DLP | Presidio |
| Audit | Azure Monitor + JSONL | Cloud Logging | ELK Stack |

## 3-Stage Retrieval (Best Practice)
1. **BM25 Keyword Search** — handles exact matches, acronyms, proper nouns
2. **Vector Search (HNSW)** — handles semantic similarity, paraphrasing, multilingual
3. **Semantic Reranking (Cross-Encoder)** — re-ranks combined results for final relevance

Over-retrieve 2x at stage 1-2, then rerank down to top-k at stage 3.

## Cost Model (Monthly Estimates)

### Small (10K docs, 5K queries/month)
| Component | Azure | GCP |
|-----------|-------|-----|
| Search Service | $250 (Basic) | $0 (Agent Builder free tier) |
| Embedding | $50 | $30 |
| LLM (generation) | $200 | $150 (Flash) |
| Storage | $5 | $5 |
| **Total** | **~$505** | **~$185** |

### Medium (100K docs, 50K queries/month)
| Component | Azure | GCP |
|-----------|-------|-----|
| Search Service | $750 (Standard S1) | $500 (Enterprise Search) |
| Embedding | $500 | $300 |
| LLM (generation) | $2,000 | $1,200 (Flash) |
| Storage | $50 | $50 |
| **Total** | **~$3,300** | **~$2,050** |

### Large (1M docs, 500K queries/month)
| Component | Azure | GCP |
|-----------|-------|-----|
| Search Service | $2,500 (Standard S3) | $2,000 |
| Embedding | $3,000 | $2,000 |
| LLM (generation) | $15,000 | $8,000 (Flash) |
| Storage | $200 | $200 |
| **Total** | **~$20,700** | **~$12,200** |

## Common Pitfalls
1. **Not chunking properly** — too large (>2000 tokens) loses precision, too small (<200 tokens) loses context
2. **Skipping reranking** — vector-only retrieval has 15-20% lower relevance than hybrid+rerank
3. **No citation enforcement** — users won't trust answers without source attribution
4. **Ignoring latency** — p95 should be <5s; if slower, use async streaming
5. **Not evaluating** — deploy without eval → silent quality degradation → user abandonment

## Evaluation Benchmarks
| Metric | Minimum | Target | Method |
|--------|---------|--------|--------|
| Relevance | ≥75% | ≥85% | LLM-as-judge (GPT-4 evaluator) |
| Groundedness | ≥80% | ≥90% | Citation verification |
| Coherence | ≥70% | ≥85% | LLM-as-judge |
| Answer Rate | ≥60% | ≥80% | Non-"I don't know" responses |
| Latency (p95) | <8s | <4s | End-to-end measurement |

## Reference Implementation
This platform's Knowledge Agent (`src/agents/knowledge.py`) + AI Search Tool (`src/tools/search.py`) implements this pattern with:
- Azure AI Search hybrid retrieval (BM25 + HNSW + Semantic Ranking)
- text-embedding-3-large (3072d) via integrated vectorization
- Grounding enforcement via system prompt
- Full citation chain (query → retrieval → generation → source attribution)

# GenAI Cost Optimization Pattern

## Pattern ID
`cost-optimization`

## Why This Pattern Exists
Customer #1 question after PoC: "How much will this cost in production?"
If you can't answer with a model, you lose credibility.

## The 4 Cost Levers

### 1. Model Selection (Biggest Impact — 5-20x difference)
| Model | Input $/1M tokens | Output $/1M tokens | Speed | Quality |
|-------|-------------------|---------------------|-------|---------|
| GPT-4.1 | $2.00 | $8.00 | Medium | Highest |
| GPT-4.1-mini | $0.40 | $1.60 | Fast | High |
| GPT-4.1-nano | $0.10 | $0.40 | Fastest | Good |
| Gemini 2.5 Flash | $0.15 | $0.60 | Fast | High |
| Gemini 2.5 Pro | $1.25 | $10.00 | Medium | Highest |
| Claude Sonnet 4 | $3.00 | $15.00 | Medium | Highest |

**Strategy**:
- **Routing/classification** → Cheapest model (nano/Flash)
- **RAG Q&A** → Mid-tier (mini/Flash)
- **Complex analysis** → High-end (GPT-4.1/Pro) only when needed
- **Evaluation (judge)** → High-end (needed for accuracy)

### 2. Retrieval Optimization
| Strategy | Impact | Implementation |
|----------|--------|---------------|
| Reduce top_k | -30-50% token cost | Tune from 10 → 5 results |
| Better chunking | -20% (fewer irrelevant chunks) | Sentence-aware, 500-1000 tokens |
| Semantic caching | -30-60% for repeated queries | Redis/Momento with embedding similarity |
| Reranking before generation | -40% tokens (fewer low-quality chunks) | Cross-encoder rerank, keep top 3-5 |

### 3. Token Management
| Strategy | Impact | Implementation |
|----------|--------|---------------|
| Prompt compression | -20-40% input tokens | LLMLingua, gzip-style prompt compression |
| Response length control | -30% output tokens | "Answer in 2-3 sentences" in system prompt |
| Context window management | -50% | Only send relevant conversation history, not all |
| Streaming with early stop | -10-20% | Stream and stop when answer is complete |

### 4. Infrastructure
| Strategy | Azure Cost | GCP Cost |
|----------|-----------|---------|
| Provisioned throughput | GPT-4 PTU: $2/hr per unit | Gemini provisioned: varies |
| Spot/preemptible for batch | N/A (API-based) | N/A (API-based) |
| Regional pricing | Same globally | Same globally |
| Commitment discount | Reserved capacity (6-12mo) | CUD (1-3yr) |

## Cost Estimation Template

### Per-Query Cost Breakdown
```
1 user query:
  → Routing (GPT-4.1-nano): ~100 tokens in, 50 out = $0.00003
  → Embedding (query): 1 API call = $0.00002
  → Search (Azure AI Search): 1 query = $0.00005
  → Generation (GPT-4.1-mini): ~2000 tokens in, 500 out = $0.0016
  → Content Safety: 2 checks = $0.002
  → Evaluation (10% sample): $0.016 × 0.1 = $0.0016
  ─────────────────────────
  Total per query: ~$0.005 ($5 per 1,000 queries)
```

### Monthly Cost Model
| Volume | Per Query | Monthly LLM | Monthly Infra | Total |
|--------|-----------|-------------|---------------|-------|
| 1K queries/month | $0.005 | $5 | $300 | $305 |
| 10K queries/month | $0.005 | $50 | $500 | $550 |
| 100K queries/month | $0.004 | $400 | $1,500 | $1,900 |
| 1M queries/month | $0.003 | $3,000 | $5,000 | $8,000 |

Costs decrease per-query at scale due to infrastructure amortization.

## Customer Conversation Framework
1. **Start with query volume estimate** — "How many queries per month?"
2. **Assess quality requirements** — "What accuracy is acceptable?" (determines model tier)
3. **Check compliance requirements** — "Any regulatory requirements?" (adds governance cost)
4. **Present 3 tiers** — Good/Better/Best with cost ranges
5. **Include optimization roadmap** — "Start with Better, optimize to Good cost with Better quality"

## Common Pitfalls
1. **Using GPT-4 for everything** — 90% of queries can use mini/Flash at 10x lower cost
2. **No caching** — 30-40% of enterprise queries are repeated/similar
3. **Over-retrieving** — Sending 20 chunks to LLM when 5 would suffice
4. **Not tracking per-query cost** — Can't optimize what you can't measure
5. **Ignoring infrastructure costs** — Search service, compute, storage add up

## Reference Implementation
This platform uses cost-optimized defaults:
- GPT-4.1-mini for routing AND generation (single mid-tier model)
- Integrated vectorization (no separate embedding API calls at query time)
- 10% evaluation sampling (not 100%)
- Hybrid search with reranking (better precision = fewer wasted tokens)

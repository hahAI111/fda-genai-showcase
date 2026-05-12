# Financial Compliance Scenario — Reference Architecture

## Recommended Architecture

```
Compliance Officers (Web UI / Teams Bot)
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  API Gateway (Azure APIM / GCP API Gateway)         │
│  VNet-isolated, WAF, rate limiting                  │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│  Governance Pipeline                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────────┐ │
│  │Content   │→│PII       │→│Audit Logger          │ │
│  │Safety    │ │Filter    │ │(FINRA 17a-4, 7yr)    │ │
│  └──────────┘ └──────────┘ └──────────────────────┘ │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│  Knowledge Agent (RAG)                               │
│  ┌─────────────────┐  ┌──────────────────────────┐  │
│  │Hybrid Search    │  │LLM Generation            │  │
│  │BM25 + Vector +  │→ │GPT-4.1-mini              │  │
│  │Semantic Rerank  │  │Grounded + Citations      │  │
│  └─────────────────┘  └──────────────────────────┘  │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│  Data Layer                                          │
│  ┌─────────────┐  ┌────────────────────────────────┐│
│  │Azure Blob   │  │Azure AI Search (Standard S1)   ││
│  │12K docs     │  │Hybrid index, integrated vectors││
│  └─────────────┘  └────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

## Why This Architecture

### Why RAG, not Fine-Tuning?
- 12K docs change frequently (new regulations monthly) → fine-tuning can't keep up
- Citation is required → RAG naturally provides source attribution
- Fine-tuning doesn't prevent hallucination → RAG with grounding does

### Why Hybrid Search, not Vector-Only?
- Regulatory documents have exact terminology (§240.10b-5, FINRA Rule 2111)
- Vector search misses exact acronyms and section numbers
- Hybrid catches both semantic meaning AND exact matches

### Why GPT-4.1-mini, not GPT-4.1?
- 5x cheaper per token
- Sufficient quality for extraction/summarization from retrieved docs
- Faster (better for <5s p95 requirement)
- For complex multi-hop analysis, could route to GPT-4.1 selectively

## Cost Breakdown ($3,200/month estimated)

| Component | Monthly Cost | Notes |
|-----------|-------------|-------|
| Azure AI Search (S1) | $750 | 12K docs, ~60K chunks |
| GPT-4.1-mini | $800 | ~50K queries, ~2K tokens/query |
| Azure Blob Storage | $50 | 12K documents |
| Content Safety | $100 | 50K queries × 2 checks |
| Compute (App Service B2) | $55 | Single instance |
| PII Detection (Azure AI Language) | $50 | 50K queries |
| Monitoring (Log Analytics) | $100 | 7-year retention for FINRA |
| **Total** | **$1,905** | Well under $5K budget |

**Note**: Actual costs may be lower. This leaves $3,095/month buffer for scaling.

## Compliance Checklist

- [x] SOC2: Audit logging with 7-year retention
- [x] FINRA 17a-4: All electronic communications logged
- [x] PII: Masked before LLM processing
- [x] VNet: Private endpoints for all Azure services
- [x] Encryption: TLS 1.2+ in transit, AES-256 at rest
- [x] Access Control: Entra ID + RBAC
- [x] Incident Response: 4-hour notification SLA

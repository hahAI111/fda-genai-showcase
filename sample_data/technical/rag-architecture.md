# Enterprise RAG Architecture — Technical Guide

## Overview
This document describes the Retrieval-Augmented Generation (RAG) architecture
deployed for the Enterprise Knowledge Platform. It covers design decisions,
trade-offs, and operational considerations.

## Architecture Components

### 1. Document Processing Pipeline
- **Ingestion**: Documents are processed from multiple sources (SharePoint, Confluence, S3)
- **Chunking**: Sentence-aware chunking with 1000-token chunks and 200-token overlap
- **Embedding**: text-embedding-3-large (3072 dimensions) via Azure OpenAI
- **Indexing**: Azure AI Search with HNSW algorithm for approximate nearest neighbor

### 2. Retrieval Strategy
We use a 3-stage retrieval approach:
1. **Keyword Search (BM25)**: Handles exact matches, acronyms, proper nouns
2. **Vector Search (HNSW)**: Handles semantic similarity, paraphrasing, multilingual
3. **Semantic Ranking (Cross-Encoder)**: Re-ranks combined results for final relevance

This hybrid approach consistently outperforms pure vector search by 15-20% on
our evaluation benchmarks.

### 3. Generation with Grounding
- **Grounding enforcement**: System prompt instructs the model to only use retrieved context
- **Citation requirement**: Every claim must reference a source document
- **Confidence thresholds**: Low-confidence answers include explicit uncertainty markers

## Performance Benchmarks

| Metric | Target | Actual |
|--------|--------|--------|
| Retrieval Recall@5 | 85% | 89% |
| Answer Relevance | 80% | 83% |
| Groundedness | 85% | 91% |
| End-to-End Latency (p95) | 3s | 2.1s |
| Cost per Query | $0.05 | $0.03 |

## Known Limitations
1. Table and chart data in PDFs are not well chunked
2. Cross-document reasoning requires explicit multi-query
3. Real-time data (< 15 min old) not yet indexed

## Operational Runbook
- **Index refresh**: Every 6 hours via scheduled pipeline
- **Evaluation**: 10% sampling rate, daily quality reports
- **Alerting**: PagerDuty integration for relevance < 70%
- **Capacity**: Auto-scale search replicas at > 80% query latency p95

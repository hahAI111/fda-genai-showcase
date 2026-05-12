# Vector Search Optimization Guide

## Overview
This guide covers optimization strategies for vector search in enterprise RAG systems,
focusing on Azure AI Search with HNSW indexing.

## Embedding Model Selection

### Comparison Table
| Model | Dimensions | Quality (MTEB) | Cost/1M tokens | Recommended For |
|-------|-----------|----------------|-----------------|-----------------|
| text-embedding-3-small | 1536 | 62.3 | $0.02 | Cost-sensitive, high volume |
| text-embedding-3-large | 3072 | 64.6 | $0.13 | Quality-sensitive, enterprise |
| text-embedding-ada-002 | 1536 | 61.0 | $0.10 | Legacy systems |

### Dimension Reduction
- text-embedding-3-large supports dimension reduction via `dimensions` parameter
- Reducing from 3072 → 1536 retains ~98% quality at 50% storage cost
- Reducing from 3072 → 256 retains ~90% quality at 8% storage cost
- Recommendation: Use 3072 for enterprise, 1536 for cost optimization

## HNSW Tuning

### Key Parameters
| Parameter | Default | Recommended | Impact |
|-----------|---------|-------------|--------|
| m (connections) | 4 | 8-16 | Higher = better recall, more memory |
| efConstruction | 400 | 500-800 | Higher = better index quality, slower build |
| efSearch | 500 | 500-1000 | Higher = better query recall, slower search |
| metric | cosine | cosine | Best for normalized embeddings |

### Index Size Planning
- 1M documents × 3072 dimensions × 4 bytes = ~12 GB vector storage
- HNSW graph overhead: ~2x vector storage = ~24 GB total
- Azure AI Search Standard tier: 50 GB per partition, up to 12 partitions

## Chunking Strategy Impact on Search Quality

### Chunk Size Comparison
| Chunk Size | Overlap | Recall@5 | Precision@5 | Notes |
|-----------|---------|----------|-------------|-------|
| 256 tokens | 50 | 92% | 71% | High recall, low precision (too many fragments) |
| 512 tokens | 100 | 89% | 78% | Good balance for short documents |
| 1000 tokens | 200 | 85% | 84% | Best balance for enterprise docs (recommended) |
| 2000 tokens | 400 | 78% | 88% | High precision but misses details |

### Hierarchical Chunking
For long documents (>10 pages), consider hierarchical chunking:
1. **Parent chunks**: 2000 tokens (full context for generation)
2. **Child chunks**: 256 tokens (precise retrieval)
3. **Strategy**: Search child chunks → retrieve parent chunks for generation

## Query Optimization

### Query Expansion
- Rephrase user query into 2-3 alternative formulations
- Search each formulation separately
- Merge and deduplicate results
- Benefit: +10-15% recall for ambiguous queries

### Hybrid Search Weights
| Scenario | Keyword Weight | Vector Weight | Notes |
|---------|---------------|---------------|-------|
| Technical docs (acronyms) | 0.6 | 0.4 | Keywords catch exact terms |
| Policy docs (concepts) | 0.3 | 0.7 | Vectors catch meaning |
| Mixed corpus (default) | 0.5 | 0.5 | Balanced (recommended) |

## Performance Benchmarks
- Cold search latency: 150-300ms
- Warm search latency: 50-100ms
- Vectorization latency: 20-50ms per query
- Total end-to-end (search + generation): 1.5-3.0s

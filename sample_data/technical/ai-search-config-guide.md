# Azure AI Search Configuration Guide

## Overview
This guide covers the setup and configuration of Azure AI Search for enterprise
RAG (Retrieval-Augmented Generation) workloads, including index design, vectorization,
and semantic ranking.

## Index Schema Design

### Core Fields
| Field | Type | Purpose | Searchable | Filterable |
|-------|------|---------|-----------|-----------|
| id | String (key) | Unique document identifier | No | Yes |
| title | String | Document title | Yes | Yes |
| content | String | Main document content | Yes | No |
| content_vector | Collection(Single) | 3072-dim embedding vector | Vector search | No |
| source | String | Original file path | No | Yes |
| source_url | String | URL to original document | No | No |
| category | String | Document category | No | Yes (facetable) |
| chunk_id | String | Chunk identifier within doc | No | No |
| created_at | DateTimeOffset | Ingestion timestamp | No | Yes (sortable) |

### Vector Search Configuration
```json
{
  "vectorSearch": {
    "algorithms": [
      {
        "name": "hnsw-config",
        "kind": "hnsw",
        "parameters": {
          "m": 4,
          "efConstruction": 400,
          "efSearch": 500,
          "metric": "cosine"
        }
      }
    ],
    "profiles": [
      {
        "name": "vector-profile",
        "algorithm": "hnsw-config",
        "vectorizer": "azure-openai-vectorizer"
      }
    ],
    "vectorizers": [
      {
        "name": "azure-openai-vectorizer",
        "kind": "azureOpenAI",
        "parameters": {
          "resourceUri": "https://gpt522222.services.ai.azure.com",
          "deploymentId": "text-embedding-3-large",
          "modelName": "text-embedding-3-large"
        }
      }
    ]
  }
}
```

### Semantic Ranking
Semantic ranking uses a cross-encoder model to re-rank results after initial
retrieval. This adds 50-100ms latency but improves precision significantly.

Configuration:
```json
{
  "semantic": {
    "configurations": [
      {
        "name": "default",
        "prioritizedFields": {
          "titleField": {"fieldName": "title"},
          "contentFields": [{"fieldName": "content"}]
        }
      }
    ]
  }
}
```

## Integrated Vectorization
Azure AI Search can handle vectorization automatically using an integrated
vectorizer. This means:
1. Upload text documents without pre-computing embeddings
2. The search service calls Azure OpenAI to generate embeddings
3. Vectors are stored alongside text in the index
4. Query-time vectorization is also handled automatically

**Benefits**: Simpler pipeline, no embedding code needed.
**Trade-off**: Dependency on Azure OpenAI availability during indexing.

## Access Control
- Use `DefaultAzureCredential` for all access (no API keys)
- Required RBAC roles:
  - `Search Service Contributor`: Create/manage indexes
  - `Search Index Data Contributor`: Read/write documents
  - `Search Index Data Reader`: Query-only access

## Performance Tuning
| Setting | Impact | Recommendation |
|---------|--------|---------------|
| Replicas | Query throughput | 2+ for production |
| Partitions | Index storage | Scale when > 80% capacity |
| Scoring profiles | Result ordering | Custom boost on title matches |
| Caching | Repeat query speed | Enable for FAQ-style workloads |

## Cost Estimation
| Tier | Price/month | Storage | Partitions | Replicas |
|------|------------|---------|-----------|---------|
| Free | $0 | 50 MB | 1 | 1 |
| Basic | $75 | 2 GB | 1 | 3 |
| Standard | $250 | 50 GB/partition | 12 | 12 |
| Standard S2 | $1,000 | 200 GB/partition | 12 | 12 |

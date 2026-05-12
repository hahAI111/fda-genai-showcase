# Enterprise AI Deployment Cost Analysis

## Overview
This document provides cost modeling for enterprise AI deployments on Azure,
covering compute, storage, AI services, and operational overhead.

## Cost Components

### 1. Azure OpenAI Service
| Model | Input (per 1M tokens) | Output (per 1M tokens) | Use Case |
|-------|----------------------|------------------------|----------|
| GPT-4o | $2.50 | $10.00 | Primary chat, analysis, governance |
| GPT-4o-mini | $0.15 | $0.60 | Intent classification, evaluation |
| text-embedding-3-large | $0.13 | — | Document embedding |
| text-embedding-3-small | $0.02 | — | Cost-optimized embedding |

### 2. Azure AI Search
| Tier | Monthly Cost | Storage | Best For |
|------|-------------|---------|----------|
| Free | $0 | 50 MB | Development/testing |
| Basic | $75 | 2 GB | Small deployments |
| Standard S1 | $250 | 50 GB | Production (recommended) |
| Standard S2 | $1,000 | 200 GB | Large enterprise |

### 3. Azure Blob Storage
| Component | Cost | Notes |
|-----------|------|-------|
| Storage (Hot) | $0.018/GB/month | Source documents |
| Read operations | $0.004/10K ops | Document retrieval |
| Write operations | $0.05/10K ops | Document upload |
| Data transfer | Free (same region) | Within Azure |

### 4. Compute (Azure App Service)
| Tier | Monthly Cost | Specs | Workers |
|------|-------------|-------|---------|
| B1 | $13 | 1 core, 1.75 GB | 1 |
| P1v3 | $115 | 2 cores, 8 GB | 2-3 |
| P2v3 | $230 | 4 cores, 16 GB | 4-8 |
| P3v3 | $460 | 8 cores, 32 GB | 8-16 |

## Cost Modeling Scenarios

### Scenario 1: Small Team (10 users, 100 queries/day)
| Component | Monthly Cost |
|-----------|-------------|
| GPT-4o (100 queries × 2K tokens avg) | $5 |
| AI Search Basic | $75 |
| Blob Storage (1 GB) | $0.02 |
| App Service B1 | $13 |
| Evaluation (10% sampling) | $6 |
| **Total** | **~$100/month** |

### Scenario 2: Department (100 users, 2,000 queries/day)
| Component | Monthly Cost |
|-----------|-------------|
| GPT-4o (2K queries × 3K tokens avg) | $150 |
| AI Search Standard S1 | $250 |
| Blob Storage (10 GB) | $0.18 |
| App Service P1v3 | $115 |
| Evaluation (10% sampling) | $120 |
| **Total** | **~$635/month** |

### Scenario 3: Enterprise (1,000+ users, 20,000 queries/day)
| Component | Monthly Cost |
|-----------|-------------|
| GPT-4o (20K queries × 3K tokens avg) | $1,500 |
| AI Search Standard S2 (2 replicas) | $2,000 |
| Blob Storage (100 GB) | $1.80 |
| App Service P2v3 (2 instances) | $460 |
| Evaluation (10% sampling) | $1,200 |
| Monitoring & alerting | $100 |
| **Total** | **~$5,260/month** |

## Cost Optimization Strategies

### 1. Model Tiering
- Use GPT-4o-mini for intent classification (90% cost reduction)
- Use GPT-4o for generation only
- Use text-embedding-3-small for non-critical indexes

### 2. Caching
- Cache frequent queries with Redis ($50-100/month)
- 30% cache hit rate → 30% reduction in AI costs
- TTL: 1 hour for dynamic content, 24 hours for static docs

### 3. Smart Evaluation
- 10% sampling rate (not 100%)
- Skip evaluation for cached responses
- Use cheaper model (GPT-4o-mini) for evaluation judges

### 4. Right-Sizing
- Start with Basic/B1 tier
- Monitor actual usage before scaling
- Use autoscaling rules based on request volume

## ROI Calculation Template
| Metric | Value |
|--------|-------|
| Monthly AI platform cost | $X |
| Hours saved per employee per month | Y hours |
| Number of employees | Z |
| Average hourly cost (fully loaded) | $W |
| **Monthly savings** | **Y × Z × $W** |
| **ROI** | **(Savings - Cost) / Cost × 100%** |

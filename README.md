# Enterprise GenAI Platform

Production-grade multi-agent AI platform with RAG, Agentic Retrieval, media generation, and enterprise governance.

**Live demo**: Run locally → `http://localhost:8000`

## Architecture Overview

```
User Request
    → Input Guardrails (PII masking + content safety screening)
    → Orchestrator (LLM-based intent classification)
        → Knowledge Agent (RAG + citations via Azure AI Search)
        → Analyst Agent (structured analysis + comparison)
        → Governance Agent (compliance check + risk assessment)
        → Architect Agent (architecture design + cost estimation)
    → Output Guardrails (safety + PII screening)
    → Metrics + Evaluation + Audit + Feedback
    → Response

Media Pipeline (parallel, independent):
    → Image Generation (gpt-image-2)
    → Video Generation (sora-2)
    → Presentation Builder (GPT → python-pptx)
```

### Component Map

| Layer | Components | Purpose |
|-------|-----------|---------|
| **Agents** | Orchestrator, Knowledge, Analyst, Governance, Architect | ReAct reasoning + tool-calling loops |
| **Retrieval** | Azure AI Search (hybrid), Agentic Retrieval (KB + multi-source) | RAG with vector + semantic ranking |
| **Media** | gpt-image-2, sora-2, python-pptx | Image/video/presentation generation |
| **Governance** | PII filter, content safety, guardrails, audit logger | Dual-layer input/output screening |
| **Evaluation** | LLM-as-judge (10% sampling) | Relevance, grounding, safety scoring |
| **Metrics** | Token/cost/latency tracking, SLO enforcement | Production observability |
| **Feedback** | Friction detection, feature request generation | Product improvement loop |
| **Persistence** | Cosmos DB, Redis, PostgreSQL, Blob Storage | Chat records, cache, telemetry, documents |

## Quick Start

### 1. Prerequisites

- Python 3.11+
- Azure AI Services endpoint (Azure AI Foundry or Azure OpenAI)
- Azure AI Search service (Basic tier or higher)
- Azure Blob Storage account

### 2. Install

```bash
git clone https://github.com/hahAI111/fda-genai-showcase.git
cd fda-genai-showcase
pip install -e .
```

### 3. Configure Environment

Copy and fill in your credentials:

```bash
cp .env.example .env
# Edit .env with your Azure resource details
```

**Required variables** (minimum to run):

| Variable | Purpose | Example |
|----------|---------|---------|
| `AZURE_AI_ENDPOINT` | Azure AI Services endpoint | `https://your-resource.cognitiveservices.azure.com` |
| `AZURE_OPENAI_API_KEY` | API key for Azure OpenAI | (from Azure Portal → Keys) |
| `AZURE_AI_CHAT_DEPLOYMENT` | Chat model deployment name | `gpt-5.2` |
| `AZURE_AI_EMBEDDING_DEPLOYMENT` | Embedding model deployment | `text-embedding-3-large` |
| `AZURE_SEARCH_ENDPOINT` | Azure AI Search endpoint | `https://your-search.search.windows.net` |
| `AZURE_SEARCH_API_KEY` | Search service admin key | (from Azure Portal → Keys) |
| `AZURE_STORAGE_ACCOUNT_URL` | Blob Storage URL | `https://your-storage.blob.core.windows.net` |
| `AZURE_STORAGE_ACCOUNT_KEY` | Blob Storage key | (from Azure Portal → Access Keys) |

**Optional variables** (features degrade gracefully without these):

| Variable | Feature | Default |
|----------|---------|---------|
| `AZURE_AI_IMAGE_DEPLOYMENT` | Image generation | `gpt-image-2` |
| `AZURE_AI_VIDEO_DEPLOYMENT` | Video generation | `sora-2` |
| `AZURE_COSMOS_ENDPOINT` / `AZURE_COSMOS_KEY` | Chat/media persistence | Disabled |
| `AZURE_REDIS_HOST` / `AZURE_REDIS_KEY` | Response caching | Disabled |
| `POSTGRES_DSN` | Telemetry logging | Disabled |

### 4. Run

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Open in browser:
- **Customer UI**: http://localhost:8000/
- **Internal Console**: http://localhost:8000/internal
- **API Docs**: http://localhost:8000/docs

## End-to-End Deployment: Agent + RAG Pipeline

### Step 1: Provision Azure Resources

| Resource | SKU | Purpose |
|----------|-----|---------|
| Azure AI Services | S0 | LLM inference (chat, embedding, image, video) |
| Azure AI Search | Basic | Hybrid search index + Agentic Retrieval |
| Azure Blob Storage | Standard | Document storage (source of truth) |

Create via Azure Portal or CLI:

```bash
# Resource group
az group create --name rg-genai --location eastus

# AI Services (hosts model deployments)
az cognitiveservices account create \
  --name my-ai-services --resource-group rg-genai \
  --kind AIServices --sku S0 --location eastus

# Search service
az search service create \
  --name my-search --resource-group rg-genai \
  --sku basic --location eastus

# Storage account
az storage account create \
  --name mygenaistorage --resource-group rg-genai \
  --sku Standard_LRS --location eastus
```

### Step 2: Deploy Models

In Azure AI Foundry or Azure Portal, create these deployments:

| Deployment Name | Model | Purpose |
|----------------|-------|---------|
| `gpt-5.2` | gpt-5.2 | Chat, reasoning, query planning |
| `text-embedding-3-large` | text-embedding-3-large | Vector embeddings (3072 dims) |
| `gpt-image-2` | gpt-image-2 | Image generation |
| `sora-2` | sora-2 | Video generation |

### Step 3: Create Search Index

Upload sample documents and create the vector index:

```bash
# Set environment variables first (or use .env)
export AZURE_SEARCH_API_KEY=your-key
export AZURE_OPENAI_API_KEY=your-key

# Create index schema + ingest sample documents
python scripts/ingest_documents.py
```

This creates the `enterprise-knowledge` index with 68 chunks from 14 policy/technical documents, including:
- AI governance policy
- Data security policy
- GDPR compliance framework
- Responsible AI framework
- RAG architecture patterns
- Multi-agent orchestration patterns

### Step 4: Setup Agentic Retrieval (Knowledge Base)

Agentic Retrieval adds LLM-powered query planning on top of search. The LLM decomposes complex questions into sub-queries, searches multiple sources in parallel, and synthesizes answers.

```bash
# Set environment variables
export AZURE_SEARCH_API_KEY=your-key
export AZURE_OPENAI_API_KEY=your-key
export AZURE_STORAGE_CONN_STR="DefaultEndpointsProtocol=https;AccountName=...;EndpointSuffix=core.windows.net"

# Create Knowledge Sources + Knowledge Base
python scripts/setup_agentic_retrieval.py
```

This creates:

| Resource | Type | Description |
|----------|------|-------------|
| `ks-enterprise-index` | searchIndex | Points to `enterprise-knowledge` index (68 docs) |
| `ks-enterprise-docs` | azureBlob | Auto-indexes `enterprise-docs` blob container (creates its own index, indexer, skillset) |
| `kb-enterprise` | Knowledge Base | Uses gpt-5.2 for query planning, searches both sources |

**How Agentic Retrieval works:**

```
User Question: "Compare RAG vs fine-tuning for regulatory compliance"
    ↓
1. Query Planning (gpt-5.2)
   → Sub-query 1: "RAG architecture benefits for compliance"
   → Sub-query 2: "Fine-tuning approach for regulatory documents"
    ↓
2. Parallel Search (both knowledge sources)
   → ks-enterprise-index: hybrid vector + semantic search
   → ks-enterprise-docs: blob-ingested document search
    ↓
3. Agentic Reasoning (gpt-5.2)
   → Synthesize findings, resolve conflicts, cite sources
    ↓
4. Structured Response
   → Grounding data + source citations + execution plan
```

### Step 5: Upload Documents to Blob Storage

```bash
# Create container
az storage container create \
  --name enterprise-docs \
  --account-name mygenaistorage

# Upload documents
az storage blob upload-batch \
  --destination enterprise-docs \
  --source sample_data/ \
  --account-name mygenaistorage
```

### Step 6: Verify the Pipeline

```bash
# Start the server
uvicorn src.main:app --host 0.0.0.0 --port 8000

# Test health
curl http://localhost:8000/health

# Test RAG search
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "data retention policy", "top_k": 5}'

# Test Agentic Retrieval
curl -X POST http://localhost:8000/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "What is our GDPR compliance framework?"}'

# Test multi-agent chat
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is our data retention policy?", "mode": "orchestrated"}'
```

Expected flow for `/chat`:
1. Orchestrator classifies intent → routes to Knowledge Agent
2. Knowledge Agent thinks (ReAct) → calls `search_knowledge` tool
3. Azure AI Search returns ranked documents
4. Agent synthesizes answer with citations
5. Governance screens output → metrics recorded → audit logged

## UI Features

### Customer Home (`/`)

| Section | Features | API Endpoints |
|---------|----------|---------------|
| **Video Generation** | Prompt, duration (4-12s), resolution, reference image upload/URL, progress polling | `POST /media/video`, `GET /media/video/{id}` |
| **Image Generation** | Prompt, size/quality/format/background, multi-reference image upload | `POST /media/image` |
| **Presentation Builder** | Topic, audience, style, slide count → PPTX download | `POST /media/ppt` |
| **Knowledge Search** | Hybrid RAG search with scope toggle (Internal/General), vector toggle, category filter | `POST /search`, `POST /chat` |
| **Agentic Retrieval** | Multi-source query planning with reasoning trace display | `POST /retrieve` |
| **Customer Metrics** | Service availability, content delivery, SLO compliance, trust signals | `GET /health`, `GET /metrics/slos` |
| **Asset History** | Media table with download/delete, bulk ZIP download | `GET /media/history`, `DELETE /media/history` |
| **Governance** | PII/safety/audit/GDPR status, interactive safety testing | `GET /health`, `POST /chat` |

### Internal Console (`/internal`)

| Section | Features | API Endpoints |
|---------|----------|---------------|
| **Chat** | Raw chat testing with JSON output | `POST /chat` |
| **Search** | Direct search testing | `POST /search` |
| **Media Check** | Quick image/video/PPT generation | `POST /media/*` |
| **Observability** | 6-endpoint dashboard, configurable thresholds, auto-refresh | `GET /metrics/*`, `GET /eval/stats`, `GET /feedback/*` |

## Multi-Agent Architecture

### Agent Routing

```
POST /chat {message, mode}
    ↓
Orchestrator (LLM intent classification)
    ├── "policy, procedure, find info" → Knowledge Agent
    ├── "compare, analyze, summarize"  → Analyst Agent
    ├── "compliance, risk, audit"      → Governance Agent
    └── "architecture, design, cost"   → Architect Agent
```

### ReAct Reasoning Loop

Each agent runs a Thought → Action → Observation loop:

```
Iteration 0: Thought → "I need to find the data retention policy"
Iteration 1: Action  → search_knowledge("data retention policy GDPR")
             Observation → [8 search results]
Iteration 2: Thought → "Results don't have an explicit retention schedule"
Iteration 3: Action  → search_knowledge("records management retention period")
             Observation → [10 search results]
Iteration 4: Thought → "Found GDPR references but no standalone policy"
Iteration 5: Final Answer → structured response with citations
```

### Agent Tools

| Agent | Tools | Description |
|-------|-------|-------------|
| Knowledge | `search_knowledge` | Hybrid vector + semantic search with filters |
| Analyst | `search_for_analysis`, `compare_documents` | Broad search + multi-topic comparison |
| Governance | `check_policy`, `assess_risk` | Policy search + risk scoring (GDPR/HIPAA/SOX/PCI) |
| Architect | `search_patterns`, `load_scenario`, `estimate_cost`, `generate_diagram` | Pattern search + scenario loading + cost calculator |

## Governance Pipeline

Every request passes through dual-layer guardrails:

```
Input  → ContentSafety (5 injection patterns) → PIIFilter (6 PII types) → Agent
Output → ContentSafety (toxic/harmful check)  → PIIFilter (leak prevention) → Response
```

PII types detected: email, phone, SSN, credit card, IP address, date of birth.

All interactions are logged to `logs/audit.jsonl` with:
- Conversation ID, timestamp, user query (masked), agent response
- Governance report (safety level, PII detections, flags)
- Token usage, latency, model name

## API Reference

### Core

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Customer UI |
| GET | `/internal` | Internal console |
| GET | `/health` | Service health + agent status |
| GET | `/db/health` | Database connectivity |
| POST | `/wake` | Resume from idle stop |

### Knowledge & Chat

| Method | Path | Description |
|--------|------|-------------|
| POST | `/chat` | Multi-agent chat (orchestrated or hierarchical mode) |
| POST | `/search` | Direct Azure AI Search (hybrid + semantic) |
| POST | `/retrieve` | Agentic Retrieval (query planning + multi-source) |
| POST | `/rag/ingest` | Ingest document into search index |
| GET | `/skills` | List registered skills |

### Media

| Method | Path | Description |
|--------|------|-------------|
| POST | `/media/image` | Generate image (gpt-image-2) |
| POST | `/media/video` | Generate video (sora-2) |
| GET | `/media/video/{job_id}` | Check video generation status |
| GET | `/media/video/{job_id}/stream` | Stream video content |
| POST | `/media/ppt` | Generate PowerPoint presentation |
| GET | `/media/history` | List generated media |
| DELETE | `/media/history` | Clear media history |
| GET | `/media/download-all` | Download all media as ZIP |

### Observability

| Method | Path | Description |
|--------|------|-------------|
| GET | `/metrics` | LLM metrics (tokens/sec, cost, latency) |
| GET | `/metrics/slos` | SLO compliance check |
| GET | `/metrics/models` | Model pricing table |
| GET | `/eval/stats` | Evaluation pipeline statistics |
| GET | `/delegation/stats` | Agent delegation history |
| POST | `/feedback/report` | Submit friction report |
| GET | `/feedback/friction` | Friction points |
| GET | `/feedback/feature-requests` | Generated feature requests |

### Operations

| Method | Path | Description |
|--------|------|-------------|
| GET | `/architecture/status` | Component connection status |
| POST | `/cache/refresh` | Warm cache |
| POST | `/cache/clear` | Clear all caches |
| GET | `/storage/documents` | List blob documents |
| GET | `/analytics/summary` | Aggregate analytics |

## Testing

```bash
# Run all tests (28 tests)
pytest -v

# Smoke tests only
pytest tests/test_api_smoke.py tests/test_governance_basics.py -v

# Agentic Retrieval tests
pytest tests/test_agentic_retrieval.py -v
```

## Project Structure

```
src/
├── main.py                 # FastAPI app, routes, middleware
├── config.py               # Settings (env vars), client factories
├── agents/
│   ├── base.py             # BaseAgent with LLM call + tool-calling
│   ├── react.py            # ReActAgent (Thought→Action→Observation loop)
│   ├── orchestrator.py     # Intent classification → agent routing
│   ├── hierarchy.py        # Task decomposition → parallel delegation
│   ├── media.py            # Media dispatch (image/video/ppt)
│   └── specialist.py       # Knowledge, Analyst, Governance, Architect
├── tools/
│   ├── api.py              # All agent tool functions
│   ├── search.py           # Azure AI Search SDK wrapper
│   ├── storage.py          # Azure Blob Storage SDK
│   ├── knowledge_base.py   # Agentic Retrieval REST API client
│   ├── knowledge_source.py # Knowledge Source definitions
│   ├── media.py            # Image/video generation (OpenAI SDK)
│   ├── ppt.py              # PowerPoint generation (python-pptx)
│   ├── cosmos_store.py     # Cosmos DB persistence
│   ├── redis_cache.py      # Redis caching
│   └── postgres_store.py   # PostgreSQL telemetry
├── governance/
│   ├── content_safety.py   # Prompt injection + toxic content detection
│   ├── pii_filter.py       # PII masking (regex-based)
│   ├── guardrails.py       # Dual-layer input/output guardrails
│   └── audit.py            # JSONL audit logger
├── evaluation/
│   ├── metrics.py          # LLM-as-judge (relevance, grounding, safety)
│   └── pipeline.py         # Evaluation sampling pipeline
├── metrics/
│   └── collector.py        # Token/cost/latency/SLO tracking
├── feedback/
│   └── collector.py        # Friction detection + feature requests
├── web/
│   ├── customer_home.html  # Customer-facing UI
│   └── internal_console.html # Engineering debug console
└── routers/
    └── media.py            # Media API routes

scripts/
├── ingest_documents.py     # Chunk + embed + index documents
├── setup_search_index.py   # Create search index schema
├── setup_agentic_retrieval.py # Create KB + KS for Agentic Retrieval
├── test_retrieve.py        # Test Agentic Retrieval API
└── check_search_resources.py # Inspect search service resources

tests/                      # 28 tests (smoke, regression, unit)
sample_data/                # Policy docs, case studies, technical docs
scenarios/                  # Industry scenarios (financial, healthcare, etc.)
skills/                     # Markdown skill definitions
```

## Deployment

### Docker

```bash
docker build -t genai-platform .
docker run -p 8000:8000 --env-file .env genai-platform
```

### GitHub Actions → Azure Container Apps

Configure repository secrets:

| Secret | Value |
|--------|-------|
| `ACR_NAME` | Azure Container Registry name |
| `AZURE_CLIENT_ID` | Service principal client ID |
| `AZURE_TENANT_ID` | Azure AD tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Subscription ID |
| `WEBAPP_RESOURCE_GROUP` | Resource group for the web app |
| `WEBAPP_NAME` | Azure Web App name |

Deploy:

```bash
# Via GitHub CLI
gh workflow run container-deploy.yml --repo hahAI111/fda-genai-showcase --ref master

# Or via GitHub UI: Actions → Container Build and Deploy → Run workflow
```

## Current Status (May 2026)

- ✅ Multi-agent orchestration (flat + hierarchical) with real LLM calls
- ✅ RAG pipeline (Azure AI Search hybrid + semantic ranking)
- ✅ Agentic Retrieval (gpt-5.2 query planning, 2 knowledge sources)
- ✅ Media generation (image, video, PPT)
- ✅ Governance pipeline (PII, content safety, audit)
- ✅ Evaluation pipeline (LLM-as-judge, 10% sampling)
- ✅ Metrics + SLO enforcement
- ✅ Feedback loop (friction detection → feature requests)
- ✅ 28 tests passing
- ⚠️ Optional backends (Cosmos, Redis, PostgreSQL) degrade gracefully when unconfigured

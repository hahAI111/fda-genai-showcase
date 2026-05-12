# Enterprise GenAI Content Studio

Production-grade FastAPI platform for enterprise GenAI workflows:
- Multi-agent orchestration (flat + hierarchical)
- Dual-layer guardrails (input and output)
- RAG ingestion and retrieval
- Media generation (image, video, PPT)
- Multi-store runtime (Cosmos, Redis, Blob, Azure AI Search, PostgreSQL)
- Metrics, evaluation, audit, and feedback loops

## 1. What This Project Is

This repository is a hybrid system:
- Knowledge modules in Markdown: skills, rules, contexts, scenarios
- Runtime backend in Python/FastAPI under src
- Customer-facing and internal web pages served by the API

Verified runtime today:
- Azure-first execution path for AI, search, storage, and media features
- Multi-cloud hooks remain in config/auth layers, but they are not the primary validated runtime path in current local and deployment checks

Primary runtime entry:
- `python -m uvicorn src.main:app --host 0.0.0.0 --port 8000`

## 2. Current Architecture (Verified Against Code)

Request path (high level):
1. HTTP request enters FastAPI app
2. Input guardrails run (content safety + PII masking)
3. Orchestrator routes to agent(s)
4. Optional tool calls (search/storage/media)
5. Output guardrails run
6. Response + audit + metrics + optional evaluation
7. Persistence/cache hooks run where configured

Core runtime components:
- Orchestration: OrchestratorAgent, HierarchicalOrchestrator
- Agents: Knowledge, Analyst, Governance, Architect, Media
- Governance: ContentSafety, PIIFilter, GuardrailPipeline, AuditLogger
- Evaluation and metrics: EvaluationPipeline, MetricsCollector, FeedbackCollector
- Data/services:
  - CosmosStore (chat/media/eval/auth records)
  - RedisCache (hot chat cache)
  - BlobStorageTool (document source + outputs)
  - AISearchTool (hybrid/vector retrieval)
  - PostgresStore (RAG/search/media/app telemetry)

## 3. Code Architecture Check Summary

### 3.1 Strengths

- Clear service initialization in lifespan startup
- Optional dependency pattern avoids full startup crashes and now emits clearer startup warnings when a dependency is unavailable
- Public health and architecture status endpoints exist
- RAG ingest and search are wired end-to-end
- Storage/cache/database checks are observable from API

### 3.2 Risks and Debt (Important)

1. Monolithic app module
- src/main.py currently mixes:
  - API routing
  - HTML/CSS/JS templates
  - business workflow and orchestration glue
- Impact: harder maintenance, testing, and review.

2. Inline frontend templates in backend file
- Customer and internal pages are large inline strings.
- Impact: frontend iteration is risky and easy to break with escaping mistakes.

3. Sync I/O in async request handlers
- Some data adapters are synchronous (Cosmos/Redis/PostgreSQL wrappers) while endpoints are async.
- Impact: potential event-loop blocking under high concurrency.

4. Global runtime singletons
- Many mutable globals are set during startup.
- Impact: hidden coupling; can complicate tests and future scaling patterns.

### 3.3 Recommended Refactor Order

1. Split src/main.py by responsibility
- routers: chat, media, rag, ops
- services: orchestration, governance, persistence adapters
- web templates/static assets

2. Move customer/internal frontend to dedicated template/static files
- keep backend focused on API and orchestration.

3. Introduce non-blocking persistence strategy for heavy writes
- async drivers or threadpool isolation for sync clients.

4. Add architecture regression tests
- startup wiring checks
- endpoint-contract checks
- persistence hook checks

## 4. Runtime Prerequisites

Python:
- 3.11+ (project supports >=3.11)

Install dependencies:

```bash
pip install -r requirements.txt
```

or

```bash
pip install -e .
```

## 5. Environment Variables

Minimum commonly required variables:
- Azure-first runtime / AI Foundry
  - AZURE_AI_ENDPOINT
  - AZURE_AI_CHAT_DEPLOYMENT
  - AZURE_AI_EMBEDDING_DEPLOYMENT
  - AZURE_AI_IMAGE_DEPLOYMENT
  - AZURE_AI_VIDEO_DEPLOYMENT

- Storage / search
  - AZURE_STORAGE_ACCOUNT_URL
  - AZURE_STORAGE_CONTAINER
  - AZURE_SEARCH_ENDPOINT
  - AZURE_SEARCH_INDEX

- Cosmos
  - AZURE_COSMOS_ENDPOINT
  - AZURE_COSMOS_KEY

- Redis
  - AZURE_REDIS_HOST
  - AZURE_REDIS_KEY

- PostgreSQL
  - POSTGRES_DSN

Note:
- See src/config.py for full settings map and defaults.
- .env.example includes reference placeholders.
- Google Cloud settings remain available in config for future or alternate deployments, but they are not required for the currently validated Azure-first runtime path.

## 6. Run Locally

```bash
uvicorn src.main:app --reload
```

Open:
- Customer page: http://localhost:8000/
- Internal console: http://localhost:8000/internal
- OpenAPI: http://localhost:8000/docs

## 7. API Surface (Current)

Core pages:
- GET /
- GET /internal

Health and platform status:
- GET /health
- GET /db/health
- GET /architecture/status
- POST /wake

Chat and knowledge:
- POST /chat
- POST /search
- POST /rag/ingest
- GET /skills

Media:
- POST /media/image
- POST /media/video
- GET /media/video/{job_id}
- GET /media/video/{job_id}/stream
- POST /media/ppt
- GET /media/history
- GET /media/download-all

Ops and telemetry:
- GET /metrics
- GET /metrics/slos
- GET /metrics/models
- GET /eval/stats
- GET /delegation/stats
- GET /feedback/friction
- GET /feedback/feature-requests
- POST /feedback/report
- POST /cache/refresh
- POST /cache/clear
- GET /storage/documents

## 8. Quick Verification Flow

1) Health checks

```bash
curl http://localhost:8000/health
curl http://localhost:8000/db/health
curl http://localhost:8000/architecture/status
```

2) RAG ingest + retrieval

```bash
curl -X POST http://localhost:8000/rag/ingest \
  -H "Content-Type: application/json" \
  -d '{"title":"Policy A","content":"All AI workloads must include audit logging.","category":"policy"}'

curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query":"audit logging requirement","top_k":5,"use_vector":true}'
```

3) Media generation

```bash
curl -X POST http://localhost:8000/media/image \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Enterprise AI architecture diagram"}'
```

## 9. Testing

Run all tests:

```bash
pytest -q
```

Focused smoke/regression examples:

```bash
pytest -q tests/test_api_smoke.py tests/test_chat_regression.py
```

## 10. MCP and CLI

CLI:

```bash
python -m src.cli
```

MCP server implementation:
- src/mcp/server.py

## 10.1 GitHub Actions Deployment Secrets

For .github/workflows/container-deploy.yml, configure these repository secrets:

- ACR_NAME
- AZURE_CLIENT_ID
- AZURE_TENANT_ID
- AZURE_SUBSCRIPTION_ID
- WEBAPP_RESOURCE_GROUP
- WEBAPP_NAME

Notes:
- The workflow now validates required secrets before Azure login/deploy steps.
- If any secret is missing, the run fails early with a clear missing-secret list.

## 10.2 GitHub Deployment Quick Start

After secrets are configured, deploy from GitHub in two ways:

1. GitHub UI
- Go to Actions → Container Build and Deploy
- Click Run workflow
- Optional input: imageTag (default: latest)

2. GitHub CLI

```bash
gh workflow run container-deploy.yml --repo hahAI111/fda-genai-showcase --ref master
gh run list --repo hahAI111/fda-genai-showcase --limit 5
```

Expected deploy flow:
- Build and push container image to ACR
- Configure Web App container image
- Restart Web App and print app state

Common failure checks:
- Missing secret names (workflow now fails early and shows missing keys)
- Wrong subscription/tenant/client for Azure login
- ACR name mismatch or insufficient ACR/WebApp permissions

## 11. Current Status (May 2026)

- Core API is running and testable
- Customer page and media flows are wired
- RAG ingest/search path is implemented
- PostgreSQL telemetry path is integrated (requires valid POSTGRES_DSN)
- Architecture is functional but needs modularization refactor for long-term maintainability

## 12. Suggested Next Milestones

1. Break main module into routers/services/templates.
2. Move frontend templates to static/template files with linted JS.
3. Add concurrency/load tests for mixed chat+media traffic.
4. Add CI gate for architecture status contract and endpoint schema stability.

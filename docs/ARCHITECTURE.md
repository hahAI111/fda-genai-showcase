# Enterprise GenAI Platform Architecture

## 1. Document Goal

This document defines the project architecture baseline for implementation, interview discussion, and demo storytelling.

It is intentionally aligned to the prior project requirements and recruiter expectations:
- production-grade multi-agent engineering, not a prompt wrapper
- ReAct reasoning transparency
- hierarchical delegation for complex tasks
- governance and security as default middleware
- GDPR controls on operational paths
- LLM-native metrics and feedback loop in production
- reusable skills and BMAD planning discipline

## 2. System Objective

Build an enterprise GenAI platform that can:
1. answer business questions with grounded retrieval
2. perform structured analysis and governance checks
3. generate media artifacts (image, video, PPT)
4. enforce safety and compliance controls by default
5. expose measurable operational quality and cost signals

## 3. High-Level Architecture

```text
Client (Web UI / API / CLI)
  -> FastAPI entrypoint
    -> Auth + request middleware
    -> Governance input guardrails
    -> Orchestration (flat or hierarchical)
      -> Specialist agents
      -> Tools (search, storage, db, media)
    -> Governance output guardrails
    -> Metrics + evaluation + audit + feedback
  -> Response (answer + citations + traces + controls)
```

## 4. Service Map

### 4.1 API and Orchestration Services

| Service | Responsibility | Module |
|---|---|---|
| API Gateway | endpoint hosting, lifecycle bootstrapping, middleware | `src/main.py` |
| Flat Orchestrator | intent routing for low-complexity requests | `src/agents/orchestrator.py` |
| Hierarchical Orchestrator | plan, delegate, synthesize for complex work | `src/agents/hierarchy.py` |
| ReAct Runtime | explicit Thought -> Action -> Observation loop | `src/agents/react.py` |

### 4.2 Specialist Agent Services

| Agent | Responsibility | Module |
|---|---|---|
| Knowledge | RAG retrieval and grounded answer generation | `src/agents/knowledge.py` |
| Analyst | comparison, trend, structured recommendations | `src/agents/analyst.py` |
| Governance | policy check and risk assessment | `src/agents/governance_agent.py` |
| Architect | architecture recommendation and tradeoff analysis | `src/agents/architect.py` |
| Media | image, video, PPT generation flows | `src/agents/media_agent.py` |

### 4.3 Data and Tool Services

| Service | Responsibility | Module |
|---|---|---|
| AI Search | hybrid retrieval, vector search, semantic rerank | `src/tools/search.py` |
| Knowledge Base | Agentic Retrieval: LLM query planning + multi-source parallel search | `src/tools/knowledge_base.py` |
| Knowledge Source | knowledge source definitions (searchIndex, azureBlob, OneLake, SharePoint, Web) | `src/tools/knowledge_source.py` |
| Blob Storage | document and artifact persistence | `src/tools/storage.py` |
| Cosmos Store | conversation/media/evaluation persistence | `src/tools/cosmos_store.py` |
| Redis Cache | hot-path cache and app key management | `src/tools/redis_cache.py` |
| PostgreSQL Store | telemetry, event, search/feedback logging | `src/tools/postgres_store.py` |
| Media Tooling | image/video transport integration | `src/tools/media.py` |
| PPT Tooling | presentation generation pipeline | `src/tools/ppt.py` |

## 5. Functional Capability Catalog

1. Chat and knowledge workflows
- grounded retrieval with citations
- ReAct traces for explainable reasoning
- hierarchical delegation for multi-step objectives
- Agentic Retrieval: LLM-driven query planning, parallel multi-source search, structured results with citations

2. Media workflows
- image generation with multi-reference support, format/quality/background controls
- async video lifecycle (create, status, stream) with reference image support
- PPT generation with audience/style/slide controls

3. Governance workflows
- content safety scanning
- PII masking before model invocation
- audit trail persistence
- GDPR data access and deletion endpoints

4. Operations and diagnostics
- architecture health status
- runtime readiness endpoints
- LLM-native metrics and SLO checks
- friction detection to feature request pipeline
- customer service snapshot (4 business-level metric tiles with trend tracking)
- interactive safety testing (PII/injection live screening via `/governance/test-safety`)
- media asset history with bulk download (ZIP) and clear operations
- observability dashboard (6-endpoint summary cards, configurable thresholds, auto-refresh)

5. Web UI features
- Customer Home (`/`): 8-section single-page app
  - Video Generation (sora-2, reference image, progress polling)
  - Image Generation (gpt-image-2, multi-reference, format/quality/background)
  - Presentation Builder (GPT → python-pptx, audience/style selection)
  - Internal Knowledge Search (hybrid RAG, scope toggle Internal/General, vector toggle)
  - Agentic Retrieval (LLM query planning, reasoning effort, execution plan display)
  - Customer Service Snapshot (availability, delivery, SLO, trust tiles)
  - Asset History (table, download/delete, bulk ZIP)
  - Governance & Compliance (5 sub-panels + interactive safety test)
- Internal Console (`/internal`): 4-card debug dashboard
  - Chat, Search, Media Check, Observability (6 endpoints, auto-refresh, thresholds)
- Info Overlays: Health, Architecture, API Console (12 endpoint quick links)

## 6. Security Architecture

### 6.1 Identity and Access

- preferred mode: identity-based auth (ADC, OAuth 2.0, managed identity)
- API key compatibility exists but is not the architecture target
- credential leakage prevention in code and deployment artifacts is mandatory

### 6.2 Data Protection

- pre-LLM PII masking pipeline
- audit logs with event-oriented traceability
- controlled file path and output directory boundaries

### 6.3 Safety Guardrails

- input guardrails: injection and unsafe intent screening
- output guardrails: harmful or policy-violating response checks
- structured decisions: allow, warn, block with explanations

## 7. GDPR Controls

Core GDPR-aligned controls in platform behavior:
1. right to access user data
2. right to erasure user data
3. retention configuration and policy enforcement
4. auditability of access and deletion operations

Representative endpoints:
- `/governance/status`
- `/gdpr/user-data` (read and delete flows)

## 8. ReAct and Delegation Design Choices

### ReAct

- each reasoning step is explicit and inspectable
- supports self-correction behavior
- supports token budget limits to avoid runaway loops

### Hierarchical Delegation

- decomposes complex requests into specialist tasks
- supports parallel and sequential execution
- synthesizes partial outputs with failure isolation

## 9. LLM-Native Metrics and SLO Baseline

| Metric | Target | Why it matters |
|---|---|---|
| TTFT | < 500 ms | perceived responsiveness |
| Tokens/sec | > 30 | model throughput |
| p99 latency | < 5 s | worst-case user experience |
| Cost per request | < $0.05 | business viability |
| Grounding score | >= 0.85 | factual reliability |

## 10. Skills and BMAD in This Architecture

### Skills

Platform capabilities are split into reusable skill modules:
- `skills/knowledge-retrieval`
- `skills/analysis`
- `skills/compliance-check`
- `skills/evaluation`
- `skills/discovery`
- `skills/report-generation`

Skill design principle:
- reusable, composable, and explicitly scoped by intent

### BMAD

Planning and delivery workflow is structured through BMAD phases:
1. analysis
2. planning
3. solutioning
4. implementation

Outputs are captured under `_bmad-output/` for traceable architecture and delivery artifacts.

## 11. Interview and Demo Positioning

When presenting this architecture, anchor the narrative in three proof points:
1. engineering depth: ReAct + delegation + modular services
2. governance readiness: security controls + GDPR + audit
3. production accountability: metrics + SLO + feedback loop

## 12. Current State and Next Increment

Current state includes domain router extraction for media and production-oriented governance/metrics endpoints.

Recommended next increment:
1. split remaining monolithic routes into domain routers
2. consolidate runtime dependencies into explicit service container
3. strengthen integration tests for RAG answer + citation behavior
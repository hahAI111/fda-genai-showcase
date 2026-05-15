# Production Architecture

## 1. Production Intent

This document defines the runtime-ready architecture posture of the platform, including service topology, security controls, GDPR controls, and operational SLO governance.

It is designed to answer recruiter and stakeholder questions about real production readiness, not only feature completeness.

## 2. Production Topology

```text
Ingress (Web/API/CLI)
  -> FastAPI runtime
    -> Auth and middleware
    -> Governance input checks
    -> Agent orchestration and tool execution
    -> Governance output checks
    -> Metrics/eval/audit/feedback sinks
  -> Persistence and retrieval services
```

Core backend dependencies:
- Azure AI Search (hybrid retrieval, rerank)
- Blob Storage (source docs and outputs)
- Cosmos DB (session/media/eval records)
- Redis (cache)
- PostgreSQL (telemetry/events)

## 3. Service Responsibilities in Production

### 3.1 Runtime API Service

Responsibilities:
- host all HTTP endpoints
- initialize runtime dependencies in lifespan
- expose health and architecture status
- enforce stop-mode and wake behavior

### 3.2 Agent Service Layer

Responsibilities:
- route by intent and complexity
- execute ReAct for explainability
- perform hierarchical delegation for composite tasks

### 3.3 Governance Service Layer

Responsibilities:
- content safety checks
- PII masking before LLM requests
- audit event persistence
- GDPR data operation support

### 3.4 Data Service Layer

Responsibilities:
- retrieval and rerank (hybrid search via Azure AI Search)
- Agentic Retrieval: LLM query planning + parallel multi-source search (`POST /retrieve`)
- persistent history and event records
- cache acceleration and controlled invalidation

## 4. Security Architecture in Production

### 4.1 Identity and Credential Strategy

Preferred production strategy:
- identity-based auth (OAuth 2.0, ADC, managed identity)
- secret-free runtime where platform identity is supported

Rules:
1. never commit plaintext credentials
2. avoid shared static credentials for production services
3. rotate and scope credentials where API keys are unavoidable

### 4.2 Defense-in-Depth Controls

1. Input controls
- prompt injection checks
- harmful content screening

2. Data controls
- PII detection and masking
- bounded file output paths

3. Output controls
- safety screening before response emission

4. Logging and audit
- governance decisions recorded
- critical data operations traceable

## 5. GDPR Controls in Production

### 5.1 Implemented Capability Set

- right to access data
- right to erasure
- retention policy exposure
- auditable GDPR operations

### 5.2 GDPR Control Matrix

| Control | Mechanism | Evidence Source |
|---|---|---|
| Data access request | dedicated endpoint and store read path | API response + audit log |
| Data deletion request | delete workflow across relevant stores | deletion response + audit log |
| Retention policy | configuration and status endpoint | governance status payload |
| Processing transparency | governance metadata in API responses | response fields + logs |

### 5.3 Operational GDPR Checklist

1. verify subject identifier normalization
2. verify complete store deletion path
3. verify audit entry for access/erase action
4. verify retention configuration is documented

## 6. Reliability and Failure Handling

### 6.1 Health and Readiness

Key endpoints:
- `/health`
- `/db/health`
- `/architecture/status`

### 6.2 Failure Isolation

- delegation subtasks are isolated
- partial success is preserved
- synthesis explicitly reports missing or failed segments

### 6.3 Service Idle Stop and Resume

- protected routes can return stop-mode status
- wake endpoint resumes execution path

## 7. LLM-Native Operations

### 7.1 Metrics Required for Production

- TTFT
- tokens/sec
- total latency
- cost/request
- grounding quality

### 7.2 SLO Baseline

| Metric | Target |
|---|---|
| TTFT | < 500 ms |
| tokens/sec | > 30 |
| p99 latency | < 5 s |
| cost/request | < $0.05 |
| grounding score | >= 0.85 |

### 7.3 Incident Triggers

Trigger alert when:
1. p99 latency violates threshold over sustained windows
2. cost/request drifts above budget envelope
3. grounding quality regresses below threshold
4. safety/GDPR control checks fail

## 8. Deployment and Change Management

### 8.1 Deployment Principles

- local validation first
- incremental non-breaking changes
- no direct infra/auth mutation without explicit approval

### 8.2 Release Checklist

1. run targeted regression tests
2. verify endpoints and critical flows
3. verify governance status and GDPR controls
4. verify metrics and audit paths
5. publish release notes with risk and rollback notes

## 9. Skills and BMAD in Production Delivery

### 9.1 Skills

Use skills to maintain reusable behavior patterns across customers and scenarios:
- retrieval
- analysis
- compliance
- evaluation
- discovery
- reporting

### 9.2 BMAD

Use BMAD phases to reduce delivery risk:
1. analysis
2. planning
3. solutioning
4. implementation and review

Artifacts should remain in `_bmad-output/` for review and reuse.

## 10. Demo-Ready Production Story

Use this sequence in demos:
1. architecture status and service readiness
2. internal knowledge RAG query with citations
3. governance and GDPR status evidence
4. metrics and SLO view
5. friction-to-feature feedback view

This demonstrates production engineering depth and architectural governance maturity end to end.

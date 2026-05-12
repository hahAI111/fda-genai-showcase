# Technical Discovery Template (Architecture, Security, GDPR, Skills, BMAD)

## 1. Objective

Use this template to convert a vague customer ask into a structured architecture and delivery plan.

This template is designed for enterprise discovery conversations and directly supports:
- service/function mapping
- security and GDPR readiness
- reusable skill extraction
- BMAD-driven planning

## 2. Business and Outcome Framing

### 2.1 Problem Statement
- [ ] What business problem is being solved?
- [ ] Who are target users?
- [ ] What decision latency is acceptable?

### 2.2 Success Criteria
- [ ] Business KPI targets
- [ ] User KPI targets
- [ ] Reliability and compliance targets

## 3. Service Inventory and Integration Scope

### 3.1 Existing Services

| Service | Type | Current Owner | Current Pain |
|---|---|---|---|
| | | | |

### 3.2 Required Platform Services

| Capability | Required Service | New/Existing | Notes |
|---|---|---|---|
| API hosting | FastAPI/API gateway | | |
| Retrieval | AI Search | | |
| Object store | Blob/Cloud Storage | | |
| Session history | NoSQL store | | |
| Cache | Redis | | |
| Telemetry/events | PostgreSQL or equivalent | | |

### 3.3 Integration Contracts
- [ ] auth strategy decided (OAuth2/ADC/managed identity)
- [ ] API contract style decided (REST/MCP/event)
- [ ] network and private connectivity constraints captured

## 4. Functional Requirements Matrix

| Function | Priority | User Impact | Technical Dependencies |
|---|---|---|---|
| Internal knowledge RAG | | | |
| Analysis and recommendations | | | |
| Governance checks | | | |
| Media generation | | | |
| Metrics and SLO reporting | | | |
| Feedback loop outputs | | | |

## 5. Security Discovery

### 5.1 Identity and Access
- [ ] enterprise IdP model confirmed
- [ ] least-privilege access model defined
- [ ] service-to-service auth model defined

### 5.2 Data Protection
- [ ] PII categories enumerated
- [ ] masking/redaction policy defined
- [ ] encryption at rest/in transit confirmed

### 5.3 Runtime Guardrails
- [ ] input safety checks required
- [ ] output safety checks required
- [ ] audit event schema defined

## 6. GDPR Discovery

### 6.1 Regulatory Fit
- [ ] right to access required
- [ ] right to erasure required
- [ ] retention policy requirements captured
- [ ] legal/compliance stakeholder identified

### 6.2 GDPR Implementation Checklist
- [ ] subject identity normalization approach
- [ ] cross-store deletion path
- [ ] audit evidence requirements
- [ ] policy communication to end users

### 6.3 GDPR Evidence Matrix

| GDPR Requirement | Planned Control | Evidence Artifact |
|---|---|---|
| Access request | | |
| Erasure request | | |
| Retention visibility | | |
| Processing transparency | | |

## 7. RAG Technical Discovery

### 7.1 Index and Data Readiness
- [ ] document schema and metadata quality
- [ ] source and chunk traceability fields
- [ ] category taxonomy quality

### 7.2 Retrieval Design
- [ ] semantic search config
- [ ] vector retrieval strategy
- [ ] reranker behavior and thresholds
- [ ] citation rendering requirements

### 7.3 Evaluation for RAG
- [ ] no-result behavior defined
- [ ] citation completeness acceptance criteria
- [ ] grounding quality target

## 8. LLM-Native SLO Discovery

| Metric | Target | Owner | Alert Rule |
|---|---|---|---|
| TTFT | | | |
| tokens/sec | | | |
| p99 latency | | | |
| cost/request | | | |
| grounding score | | | |

## 9. Skills and Reuse Discovery

### 9.1 Skill Opportunities

| Candidate Skill | Trigger Pattern | Reuse Potential | Owner |
|---|---|---|---|
| | | | |

### 9.2 Skill Quality Criteria
- [ ] clear scope and boundaries
- [ ] reproducible workflow steps
- [ ] examples and anti-patterns

## 10. BMAD Planning Output

Use BMAD phases to structure delivery output:

1. Analysis phase output
- business framing
- constraints
- feasibility and risk snapshot

2. Planning phase output
- product requirements
- UX flow for core scenarios

3. Solutioning phase output
- architecture design
- epics and stories

4. Implementation phase output
- story-level execution
- test and review evidence

## 11. Risk Register

| Risk | Probability | Impact | Mitigation | Owner |
|---|---|---|---|---|
| | | | | |

## 12. Discovery Exit Criteria

Discovery is complete when:
1. service map is approved
2. function matrix is prioritized
3. security and GDPR controls are agreed
4. RAG design decisions are explicit
5. SLO targets and ownership are defined
6. skill extraction opportunities are captured
7. BMAD phase outputs are assigned

---
name: discovery
description: >
  Use this skill when conducting a technical discovery session with an
  enterprise customer evaluating GenAI deployment. Provides structured
  frameworks for requirements gathering, architecture decision-making,
  and deployment planning. Triggers when discussing customer engagement,
  requirements, architecture design, or deployment strategy.
  Keywords: discovery, requirements, customer, architecture, deployment,
  planning, use case, stakeholder, roadmap, POC, pilot.
allowed-tools:
  - Read
---

# Technical Discovery — Customer Engagement Framework

## When to Use

Use this skill when you need to:
- Conduct initial technical discovery with a customer
- Gather requirements for a GenAI deployment
- Translate vague "we want AI" into concrete architecture decisions
- Create deployment roadmaps with phased rollout
- Produce Architecture Decision Records (ADRs)

## When NOT to Use

- Executing technical investigation → use specific technical skills
- Answering knowledge questions → use [knowledge-retrieval](../knowledge-retrieval/SKILL.md)
- Checking compliance → use [compliance-check](../compliance-check/SKILL.md)

## Discovery Session Framework

### Phase 1: Business Context (30 min)

```
1. Business Objective
   ├─ What problem are we solving?
   ├─ Success metric? (cost ↓, time ↓, accuracy ↑, satisfaction ↑)
   ├─ Who are the end users?
   └─ Expected usage volume?

2. Current State
   ├─ What tools/processes exist today?
   ├─ What has been tried? What failed?
   └─ Existing AI/ML initiatives?

3. Constraints
   ├─ Timeline (POC → production)
   ├─ Budget (one-time vs. ongoing)
   └─ Team capability (AI expertise level)
```

### Phase 2: Data Readiness (30 min)

```
1. Data Sources
   ├─ Where is the data? (SharePoint, DBs, APIs, file shares)
   ├─ Volume and update frequency?
   └─ Access methods?

2. Data Quality
   ├─ Clean and structured?
   ├─ Quality issues? (duplicates, gaps)
   └─ Format? (PDF, HTML, DB, API)

3. Data Sensitivity
   ├─ PII present?
   ├─ Data classification levels?
   ├─ Residency requirements?
   └─ Encryption requirements?
```

### Phase 3: Technical Requirements (30 min)

```
1. Performance
   ├─ Latency target (p95)?
   ├─ Throughput (QPS)?
   └─ Availability SLA?

2. Integration
   ├─ Systems to integrate with?
   ├─ Auth mechanism? (SSO, OAuth, SAML)
   └─ API format? (REST, gRPC)

3. Infrastructure
   ├─ Cloud provider?
   ├─ Network topology? (VNet, private endpoints)
   └─ Existing container infrastructure?
```

### Phase 4: Governance (20 min)

```
1. Regulatory
   ├─ Which regulations? (GDPR, HIPAA, SOC2)
   ├─ Existing AI governance framework?
   └─ Model risk management?

2. Security
   ├─ Security review process?
   ├─ Content safety requirements?
   └─ Prompt injection concerns?

3. Audit
   ├─ Audit trail requirements?
   ├─ Monitoring infrastructure?
   └─ Incident response plan?
```

### Phase 5: Adoption Planning (10 min)

```
1. Rollout Strategy
   ├─ Phased? (pilot → department → enterprise)
   ├─ Success criteria per phase?
   └─ Change management plan?

2. User Experience
   ├─ Interaction mode? (chat, API, embedded)
   ├─ Training plan?
   └─ Feedback mechanism?
```

## Discovery Output — Architecture Decision Record

After discovery, produce:

### 1. Architecture Recommendation
- Proposed architecture diagram
- Component selection with justification
- Integration approach
- Security architecture

### 2. Implementation Roadmap

| Phase | Scope | Duration | Success Criteria |
|-------|-------|----------|-----------------|
| POC | Core use case, limited data | 4 weeks | Accuracy > 80%, stakeholder demo |
| Pilot | Full data, limited users | 8 weeks | User satisfaction > 4/5, latency < 3s |
| Production | Full rollout | 4 weeks | SLA met, compliance approved |

### 3. Risk Register

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| Data not ready | Medium | High | Parallel data cleaning workstream |
| Compliance delay | Low | High | Engage legal early, use compliance-check skill |
| Low adoption | Medium | Medium | User testing in pilot, feedback loop |

### 4. Reusable Patterns Identified
- Patterns that could benefit other customers
- Product feature requests
- Documentation gaps

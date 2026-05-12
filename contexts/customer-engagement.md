# Customer Engagement Context

Load this context when conducting customer discovery or deployment planning.

## Engagement Phases

```
Phase 1: Discovery (1-2 weeks)
    │  Business context + data readiness + technical requirements
    │  Output: Architecture Decision Record
    │
    ▼
Phase 2: Reference Solution (2-4 weeks)
    │  Build reference architecture on customer data
    │  Output: Working prototype + evaluation results
    │
    ▼
Phase 3: Production Hardening (2-4 weeks)
    │  Governance + evaluation + observability + integration
    │  Output: Production-ready system
    │
    ▼
Phase 4: Adoption (ongoing)
    │  User training + feedback loop + quality monitoring
    │  Output: Adoption metrics + reusable patterns
```

## Customer Conversation Patterns

### Don't say → Say instead

| ❌ Don't | ✅ Do |
|----------|-------|
| "I investigated" | "I identified the deployment blocker" |
| "I optimized the code" | "I defined requirements for production readiness" |
| "I fixed the bug" | "I translated customer friction into a repeatable solution" |
| "I built a RAG pipeline" | "I designed a retrieval architecture aligned with the latency and governance requirements" |

### Business-First Questions

Always ask before designing:
1. What business problem are we solving?
2. What does success look like? (metric)
3. Who are the end users?
4. What has been tried before? What failed?
5. What are the constraints? (compliance, timeline, budget)

## Reusable Pattern Extraction

After every engagement, ask:
1. What deployment blocker did we overcome?
2. Is this blocker common across customers?
3. Can the solution be extracted into a reusable skill?
4. Is there a product gap that should be reported as feedback?

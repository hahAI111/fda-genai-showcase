# Model Deployment Checklist

## Overview
This checklist must be completed before any AI model is promoted to production.
All items require sign-off from the designated reviewer.

## Pre-Deployment Checklist

### 1. Model Quality
- [ ] Evaluation benchmarks pass minimum thresholds:
  - Relevance: ≥ 80%
  - Groundedness: ≥ 85%
  - Coherence: ≥ 75%
  - Safety: 100% (zero tolerance)
- [ ] Edge case testing completed (empty inputs, adversarial prompts, multilingual)
- [ ] Regression testing against previous model version
- [ ] Load testing at 2x expected peak traffic

### 2. Security Review
- [ ] Threat model documented and reviewed
- [ ] Prompt injection mitigations implemented and tested
- [ ] Content safety guardrails configured (input + output)
- [ ] PII filter active with all 6 detection patterns
- [ ] No API keys in code, config, or environment variables
- [ ] Network isolation verified (Private Endpoints / VNet)

### 3. Governance
- [ ] Data classification completed for all input sources
- [ ] Privacy Impact Assessment (PIA) filed and approved
- [ ] Audit logging verified (JSONL format, all events captured)
- [ ] Data retention policy configured
- [ ] Incident response plan documented

### 4. Observability
- [ ] Structured logging configured (JSON format)
- [ ] Distributed tracing enabled (OpenTelemetry)
- [ ] Health check endpoint returning correct status
- [ ] Alerting configured for:
  - Error rate > 5%
  - Latency p95 > 3 seconds
  - Evaluation score drop > 10%
  - PII detection spike

### 5. Operations
- [ ] Rollback procedure documented and tested
- [ ] Scaling configuration verified (auto-scale rules)
- [ ] Backup and recovery tested
- [ ] On-call rotation assigned
- [ ] Runbook updated with new model-specific procedures

## Sign-Off

| Reviewer | Role | Date | Status |
|----------|------|------|--------|
| | Engineering Lead | | |
| | Security Reviewer | | |
| | Compliance Officer | | |
| | Product Owner | | |

## Post-Deployment Verification
- [ ] Smoke test passed in production
- [ ] Evaluation pipeline running (10% sampling)
- [ ] Audit trail generating correctly
- [ ] No error spikes in first 24 hours
- [ ] User feedback mechanism active

# Governance Review Context

Load this context when conducting governance reviews for AI deployments.

## Governance Review Framework

### Pre-Deployment Checklist

```
0. 🎯 Risk Classification (mandatory first step)
   └─ Data types involved → Risk level (LOW/MEDIUM/HIGH/CRITICAL)
   └─ Deployment scope → Adjust risk level

1. 📋 Policy Compliance
   └─ AI Governance Policy v2.1 — all sections
   └─ Data classification completed?
   └─ PIA filed?

2. 🔒 Security Review
   └─ Threat model documented?
   └─ Prompt injection mitigations?
   └─ Content safety enabled?
   └─ PII filter configured?

3. 📊 Evaluation Readiness
   └─ Benchmarks defined and met?
   └─ Production evaluation pipeline configured?
   └─ Alerting thresholds set?

4. 📝 Audit Readiness
   └─ Audit logging active?
   └─ Data retention policy defined?
   └─ Incident response plan documented?

5. ✅ Sign-off
   └─ Engineering lead
   └─ Security review
   └─ Compliance officer
```

### Common Governance Failures

| Failure | Root Cause | Prevention |
|---------|-----------|-----------|
| PII in LLM context | No pre-processing filter | Mandatory PII filter middleware |
| No audit trail | Logging not configured | Governance-always rule |
| Quality drift | No production evaluation | Evaluation sampling pipeline |
| Prompt injection | No input screening | Content safety middleware |
| Key leakage | API keys in config | Identity-based auth only |

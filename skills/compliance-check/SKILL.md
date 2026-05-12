---
name: compliance-check
description: >
  Use this skill for any compliance, governance, risk assessment, or policy
  validation question. Checks AI use cases against enterprise policies (GDPR,
  HIPAA, SOC2, PCI-DSS), assesses data classification risks, and generates
  audit-ready compliance reports. Triggers when user mentions: compliance,
  risk, audit, regulation, governance, policy check, data privacy, PII handling,
  or deployment approval.
  Keywords: compliance, governance, risk, audit, GDPR, HIPAA, SOC2, PCI-DSS,
  PII, data privacy, policy, regulation, approval, security review.
allowed-tools:
  - vertex_ai_search
  - Read
---

# Compliance Check — Governance & Risk Assessment

## When to Use

Use this skill when you need to:
- Assess compliance for an AI use case or deployment
- Check requirements for specific regulations (GDPR, HIPAA, SOC2)
- Generate risk assessments with severity and mitigation
- Validate data handling practices against enterprise policy
- Produce audit-ready compliance documentation

⚠️ **Always err on the side of caution. Flag potential issues rather than miss them.**

## When NOT to Use

- Searching for policy documents → use [knowledge-retrieval](../knowledge-retrieval/SKILL.md)
- Comparing governance approaches → use [analysis](../analysis/SKILL.md)
- Generating formatted reports → use [report-generation](../report-generation/SKILL.md)

## Compliance Assessment Output Format

```markdown
## Compliance Assessment

### Risk Level: [LOW | MEDIUM | HIGH | CRITICAL]

### Policy Compliance
- ✅ / ❌ Policy 1: <status and details>
- ✅ / ❌ Policy 2: <status and details>

### Identified Risks
1. <risk> — Severity: <level> — Mitigation: <action>

### Regulatory Considerations
- <regulation>: <applicable requirements>

### Required Actions
1. <action item> — Owner: <team> — Timeline: <when>

### Audit Trail
- Assessment Date: <date>
- Assessor: Governance Agent
- Scope: <what was assessed>
```

## Policy Reference Table

| Policy | Section | Key Requirement |
|--------|---------|-----------------|
| AI Governance Policy v2.1 | §3.2 | Data minimization for PII |
| AI Governance Policy v2.1 | §4.1 | Pre-deployment: bias test + security review + eval benchmarks |
| AI Governance Policy v2.1 | §4.2 | Production: continuous eval ≥ 10% sampling |
| SOC 2 | — | Access controls + audit logging |
| GDPR Art. 5 | — | Lawful basis + purpose limitation |
| GDPR Art. 17 | — | Right to erasure (including from vector stores) |
| HIPAA | — | PHI encryption + access logging + BAA |
| PCI-DSS | — | Tokenization of financial data before AI processing |

## Data Classification → Risk Level Mapping

| Data Type | Classification | Default Risk Level | Regulations |
|-----------|---------------|-------------------|-------------|
| PII (names, emails) | Restricted | HIGH | GDPR, CCPA |
| Health data (PHI) | Restricted | CRITICAL | HIPAA |
| Financial data | Restricted | HIGH | SOX, PCI-DSS |
| Internal docs | Confidential | MEDIUM | SOC 2 |
| Public content | Public | LOW | — |

## Risk Assessment Flow

```
AI Use Case Description
    │
    ▼
┌─────────────────────────────┐
│ 1. Data Classification      │  What data types are involved?
│    PII? Health? Financial?   │  → Sets baseline risk level
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ 2. Deployment Scope         │  Internal only? Customer-facing?
│    Who sees the AI output?  │  → Customer-facing = higher risk
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ 3. Regulatory Mapping       │  Which regulations apply?
│    GDPR? HIPAA? SOC2?       │  → Each adds specific requirements
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ 4. Control Verification     │  Are required controls in place?
│    PII filter? Eval? Audit? │  → Gap = required action
└──────────┬──────────────────┘
           │
           ▼
  Compliance Report
  (risk level + requirements + actions)
```

## Deployment Approval Checklist

Before any AI system enters production, verify:

- [ ] Data classification completed
- [ ] Privacy Impact Assessment (PIA) filed
- [ ] Bias and fairness testing passed
- [ ] Security review and threat modeling done
- [ ] Evaluation benchmarks met (Relevance ≥ 80%, Groundedness ≥ 85%, Safety = 100%)
- [ ] Content safety guardrails enabled
- [ ] PII filtering configured and tested
- [ ] Audit logging active
- [ ] Incident response plan documented
- [ ] Compliance stakeholder sign-off obtained

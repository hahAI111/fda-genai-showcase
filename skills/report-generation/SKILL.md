---
name: report-generation
description: >
  Use this skill when the user needs formatted output — executive summaries,
  compliance reports, architecture documents, or customer-facing deliverables.
  Structures raw analysis and investigation results into professional documents.
  Keywords: report, document, summary, deliverable, format, executive,
  presentation, customer communication.
allowed-tools:
  - Read
  - Write
---

# Report Generation — Structured Deliverables

## When to Use

Use this skill when you need to:
- Format investigation results into executive summaries
- Create compliance reports for audit review
- Generate architecture recommendation documents
- Produce customer-facing communications
- Structure findings into presentation-ready format

## When NOT to Use

- Searching for information → use [knowledge-retrieval](../knowledge-retrieval/SKILL.md)
- Running analysis → use [analysis](../analysis/SKILL.md)
- Checking compliance → use [compliance-check](../compliance-check/SKILL.md)

## Report Templates

### Executive Summary

```markdown
# Executive Summary: [Topic]

**Date**: [date]  |  **Author**: [name]  |  **Status**: [Draft/Final]

## TL;DR
<2-3 sentences capturing the key finding and recommended action>

## Background
<Why this investigation/analysis was needed>

## Key Findings
1. <Finding with evidence>
2. <Finding with evidence>

## Recommendation
<Specific recommended action with justification>

## Next Steps
- [ ] <action> — Owner: <team> — By: <date>
```

### Architecture Decision Record (ADR)

```markdown
# ADR-NNN: [Decision Title]

**Status**: Proposed | Accepted | Deprecated
**Date**: [date]
**Deciders**: [stakeholders]

## Context
<What is the issue that we're seeing that requires a decision?>

## Decision
<What is the change that we're proposing and/or doing?>

## Consequences
### Positive
- <benefit>

### Negative
- <trade-off>

### Risks
- <risk> — Mitigation: <approach>
```

### Compliance Assessment Report

```markdown
# Compliance Assessment: [System Name]

**Assessment Date**: [date]
**Risk Level**: [LOW | MEDIUM | HIGH | CRITICAL]
**Assessor**: Governance Agent

## Scope
<What was assessed>

## Compliance Status

| Requirement | Status | Notes |
|-------------|--------|-------|
| PII Handling | ✅ / ❌ | <details> |
| Audit Logging | ✅ / ❌ | <details> |
| Evaluation | ✅ / ❌ | <details> |

## Required Actions
1. <action> — Priority: <HIGH/MED/LOW> — Timeline: <when>

## Sign-off
- [ ] Engineering Lead
- [ ] Security Review
- [ ] Compliance Officer
```

## Quality Standards

Every report must:
- [ ] Start with a TL;DR (≤ 3 sentences)
- [ ] Include data-backed findings (no unsupported claims)
- [ ] End with specific, actionable next steps
- [ ] Include owner and timeline for each action item
- [ ] Be readable by a non-technical stakeholder

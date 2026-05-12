---
name: analysis
description: >
  Use this skill when the user needs structured analysis, comparison,
  trend identification, or recommendation generation. Produces executive
  summaries with evidence-based findings and actionable recommendations.
  NOT for simple factual lookups (use knowledge-retrieval) or compliance
  checks (use compliance-check).
  Keywords: analyze, compare, trend, insight, recommendation, summary,
  report, data, evaluate, trade-off, pros cons.
allowed-tools:
  - vertex_ai_search
  - Read
---

# Analysis — Structured Insight Generation

## When to Use

Use this skill when you need to:
- Compare two or more options with structured criteria
- Generate executive summaries from raw data or documents
- Identify trends or patterns across multiple data points
- Produce actionable recommendations with supporting evidence
- Assess trade-offs between competing approaches

## When NOT to Use

- Simple factual lookup → use [knowledge-retrieval](../knowledge-retrieval/SKILL.md)
- Compliance or risk assessment → use [compliance-check](../compliance-check/SKILL.md)
- Report formatting (PPT/PDF) → use [report-generation](../report-generation/SKILL.md)
- Platform health inquiry → use `/health` API endpoint

## Output Format

All analysis output must follow this structure:

```markdown
## Summary
<1-2 sentence executive summary>

## Key Findings
- Finding 1 (with supporting evidence)
- Finding 2 (with supporting evidence)

## Analysis
<detailed analysis with data references>

## Recommendations
1. <specific action> — Rationale: <why>
2. <specific action> — Rationale: <why>

## Risks & Trade-offs
- Risk 1: <description> — Mitigation: <approach>
- Risk 2: <description> — Mitigation: <approach>
```

## Comparison Template

When comparing options, produce a structured table:

| Criterion | Option A | Option B | Winner |
|-----------|----------|----------|--------|
| Cost | <assessment> | <assessment> | A/B |
| Performance | <assessment> | <assessment> | A/B |
| Risk | <assessment> | <assessment> | A/B |
| Adoption Ease | <assessment> | <assessment> | A/B |

**Overall Recommendation**: <which option and why>

## Analysis Methodology

```
1. Define the question clearly
   └─ What decision does this analysis support?

2. Gather data
   └─ Search knowledge base for relevant documents
   └─ Identify quantitative and qualitative data points

3. Analyze
   └─ Apply criteria-based evaluation
   └─ Identify patterns, outliers, and trends
   └─ Consider both benefits and risks

4. Synthesize
   └─ Structured output (Summary → Findings → Recs → Risks)
   └─ Every recommendation must have evidence + rationale
   └─ Every risk must have severity + mitigation
```

## Quality Checklist

- [ ] Summary is 1-2 sentences (executive-readable)
- [ ] Every finding cites a data source
- [ ] Recommendations are specific and actionable (not vague)
- [ ] Risks include severity level and mitigation
- [ ] Trade-offs are explicitly acknowledged
- [ ] Analysis directly answers the question asked

## Code and UI Consistency Audit (Strict Mode)

When the user asks to audit or align implementation style, apply this workflow before proposing any change.

### Audit Scope

- Backend code quality and behavioral safety
- Frontend usability, visual consistency, and interaction logic
- API contract consistency between frontend calls and backend handlers
- Runtime robustness (timeouts, retries, error states, and graceful degradation)

### Required Audit Steps

1. Build a baseline inventory
   - List target files and responsibilities
   - Mark each as `core`, `supporting`, or `legacy`

2. Check code-style consistency
   - Naming consistency across models, handlers, and payload fields
   - Duplicate logic and dead branches
   - Error handling and user-facing messages
   - Backward compatibility for public API behavior

3. Check UI and interaction consistency
   - Single source of truth for button states (`idle`, `loading`, `success`, `error`)
   - Loading and failure feedback for every async operation
   - Visual hierarchy consistency (spacing, typography, primary vs secondary actions)
   - Mobile and desktop rendering parity for primary user journeys

4. Check design logic
   - Every user action maps to a clear API intent and visible outcome
   - Destructive actions require explicit confirmation or safe guardrails
   - Generated artifacts must be previewable and downloadable with stable links

5. Validate fixes
   - Run available tests/checks relevant to modified modules
   - Provide before/after findings and residual risk

### Output Requirements for Strict Mode

Use this exact structure in audit responses:

```markdown
## Audit Findings
1. [Severity] <issue>
2. [Severity] <issue>

## Fixes Applied
1. <change>
2. <change>

## Verification
- <test/check> — <result>

## Residual Risks
- <risk or "none">
```

### Acceptance Criteria (Pass/Fail)

- [ ] No broken primary buttons/actions in main user flows
- [ ] No silent failures for async actions
- [ ] No duplicate UI bindings for the same element
- [ ] API errors are surfaced with actionable messages
- [ ] Generated output has direct preview or download path

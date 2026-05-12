# Enterprise AI Evaluation Framework

## Overview
This document defines the evaluation methodology for all AI systems deployed
within the enterprise. Evaluation is not a one-time gate — it's a continuous
production practice.

## Evaluation Dimensions

### 1. Relevance (Is it answering the right question?)
**Definition**: The degree to which the response addresses the user's query.
**Measurement**: LLM-as-judge with calibrated rubric.
**Threshold**: ≥ 80% (pre-production), ≥ 75% (production alert)

**Rubric**:
| Score | Criteria |
|-------|----------|
| 1.0 | Directly and completely answers the query |
| 0.8 | Answers the query but misses minor details |
| 0.6 | Partially answers — addresses the topic but not the specific question |
| 0.4 | Tangentially related but doesn't answer the query |
| 0.2 | Mostly irrelevant |
| 0.0 | Completely unrelated or empty |

### 2. Groundedness (Are claims supported by evidence?)
**Definition**: The degree to which response claims are supported by retrieved context.
**Measurement**: LLM-as-judge comparing response against retrieved documents.
**Threshold**: ≥ 85% (pre-production), ≥ 80% (production alert)

**Common failures**:
- Hallucinated statistics (numbers not in source docs)
- Fabricated policy details (policy names that don't exist)
- Over-generalization (claiming something applies to "all cases" when source says "some")

### 3. Coherence (Is it well-structured and clear?)
**Definition**: The quality of the response's structure, flow, and clarity.
**Measurement**: LLM-as-judge evaluating organization and readability.
**Threshold**: ≥ 75% (pre-production), ≥ 70% (production alert)

### 4. Safety (Does it follow content policies?)
**Definition**: Compliance with content safety policies.
**Measurement**: Automated classifiers + LLM-as-judge.
**Threshold**: 100% (zero tolerance, both pre-production and production)

**Checked categories**:
- Harmful content (violence, self-harm, hate speech)
- Personal data leakage
- Prompt injection success
- Off-topic or unauthorized content generation

## Production Evaluation Pipeline

### Sampling Strategy
```
Total Requests → 10% Random Sample → 4-Dimension Evaluation → Log + Alert
```

**Why 10%?**
- Lower rate misses drift (detected too late)
- Higher rate is cost-prohibitive ($0.02 per evaluation × 4 dimensions)
- 10% at 10K requests/day = 1,000 evaluations = $20/day

### Alert Thresholds
| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| Relevance | < 75% | < 65% | Review system prompt |
| Groundedness | < 80% | < 70% | Check search quality |
| Coherence | < 70% | < 60% | Review output format instructions |
| Safety | < 99% | < 95% | Immediate investigation |

### Drift Detection
- 7-day rolling average compared to baseline
- Statistical significance test (p < 0.05)
- Automatic PagerDuty alert on critical drift
- Monthly trend reports to governance board

## Evaluation Dataset Management

### Test Set Requirements
- Minimum 200 test cases per use case
- 20% adversarial inputs (prompt injection, edge cases)
- 10% multilingual inputs
- Quarterly refresh to reflect evolving use patterns

### Golden Dataset
- Curated set of 50 questions with expert-annotated answers
- Used as regression test for prompt changes
- Version-controlled alongside the system prompt
- Updated annually with new question types

## Cost Analysis
| Component | Cost per Eval | At 10% of 10K/day |
|-----------|--------------|-------------------|
| Relevance judge | $0.005 | $5/day |
| Groundedness judge | $0.005 | $5/day |
| Coherence judge | $0.005 | $5/day |
| Safety judge | $0.005 | $5/day |
| **Total** | **$0.02** | **$20/day = $600/month** |

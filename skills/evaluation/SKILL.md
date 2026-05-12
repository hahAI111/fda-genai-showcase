---
name: evaluation
description: >
  Use this skill when assessing AI system quality, running evaluations,
  or monitoring production performance. Covers LLM-as-judge metrics
  (relevance, groundedness, coherence, safety), evaluation pipeline
  configuration, quality alerting, and drift detection. Triggers when
  user asks about AI quality, accuracy, hallucination rate, or evaluation.
  Keywords: evaluation, quality, metrics, relevance, groundedness,
  coherence, safety, hallucination, drift, monitoring, benchmark.
allowed-tools:
  - Read
---

# Evaluation — AI Quality Monitoring

## When to Use

Use this skill when you need to:
- Evaluate response quality (relevance, groundedness, coherence, safety)
- Configure production evaluation pipeline
- Investigate quality degradation or drift
- Set up alerting thresholds for quality metrics
- Run benchmark evaluation against test datasets

## When NOT to Use

- Searching for information → use [knowledge-retrieval](../knowledge-retrieval/SKILL.md)
- Compliance assessment → use [compliance-check](../compliance-check/SKILL.md)
- One-off question answering → not needed, evaluation runs automatically

## Evaluation Metrics

| Metric | What It Measures | Pass Threshold | Method |
|--------|-----------------|----------------|--------|
| **Relevance** | Does the response answer the query? | ≥ 80% (4/5) | LLM-as-judge |
| **Groundedness** | Is every claim supported by retrieved context? | ≥ 85% (4.25/5) | LLM-as-judge |
| **Coherence** | Is the response well-structured and clear? | ≥ 80% (4/5) | LLM-as-judge |
| **Safety** | Is the response free from harmful content? | 100% (pass/fail) | LLM-as-judge |

## Production Evaluation Pipeline

```
Every Request
    │
    ├── 90% → No evaluation (pass through)
    │
    └── 10% → Sampled for evaluation
                │
                ▼
          ┌─────────────────┐
          │ LLM-as-Judge    │
          │ (4 metrics)     │
          └────────┬────────┘
                   │
            ┌──────┴──────┐
            │             │
        All Pass      Any Fail
            │             │
        Log metrics   ⚠️ Alert
        (dashboard)   (PagerDuty)
```

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `EVAL_ENABLED` | `true` | Enable/disable evaluation |
| `EVAL_SAMPLE_RATE` | `0.1` | Fraction of requests to evaluate (10%) |

## Quality Degradation Investigation

When evaluation scores drop:

```
1. Check recent changes
   └─ Model version update?
   └─ Prompt changes?
   └─ Index refresh issues?

2. Analyze failure patterns
   └─ Which metric is failing?
   └─ Specific query types affected?
   └─ Time-correlated with a deployment?

3. Root cause categories
   ├─ Relevance drop → Retrieval issues (index, chunking, embedding)
   ├─ Groundedness drop → Prompt drift (model generating beyond context)
   ├─ Coherence drop → Context overload (too many/conflicting documents)
   └─ Safety failure → New attack pattern or model regression
```

## Evaluation vs. Testing

| Aspect | Testing (Pre-Deploy) | Evaluation (Production) |
|--------|---------------------|------------------------|
| When | Before deployment | Continuously in production |
| Coverage | 100% of test set | Sampled (default 10%) |
| Cost | One-time | Ongoing (~$0.02/eval) |
| Purpose | Gate deployment | Detect drift and regression |
| Action | Block deploy if fail | Alert and investigate |

# AI Evaluation Framework Pattern

## Pattern ID
`evaluation-framework`

## When to Use
- Before ANY production deployment of GenAI
- Continuous monitoring of production quality
- Comparing model/prompt/retrieval changes (A/B testing)
- Customer asks "how do we know it's working?"

## When NOT to Use
- Never. Every production GenAI system needs evaluation. No exceptions.

## The 5 Metrics That Matter

### 1. Relevance — "Did it answer the question?"
- **What**: Does the response address the user's actual intent?
- **How to measure**: LLM-as-judge with rubric (1-5 scale)
- **Target**: ≥80% scoring 4-5
- **Red flag**: <60% → retrieval or routing problem

### 2. Groundedness — "Is it making things up?"
- **What**: Is every claim in the response supported by retrieved documents?
- **How to measure**: LLM-as-judge comparing response against source chunks
- **Target**: ≥85% (≥95% for regulated industries)
- **Red flag**: <70% → hallucination problem, tighten grounding prompt

### 3. Coherence — "Does it make sense?"
- **What**: Is the response well-structured, logical, and readable?
- **How to measure**: LLM-as-judge on structure and clarity
- **Target**: ≥80%
- **Red flag**: <60% → prompt engineering issue

### 4. Safety — "Is it harmful?"
- **What**: Does the response contain harmful, biased, or inappropriate content?
- **How to measure**: Content safety API + LLM-as-judge
- **Target**: 100% safe (zero tolerance)
- **Red flag**: Any safety failure → immediate investigation

### 5. Latency — "Is it fast enough?"
- **What**: End-to-end response time
- **How to measure**: Application metrics (p50, p95, p99)
- **Target**: p95 < 5s for interactive, < 30s for analysis
- **Red flag**: p95 > 10s → users will leave

## Evaluation Architecture
```
Production Traffic
  → [10% sample] → Evaluation Queue (async)
                      → LLM-as-Judge (GPT-4 evaluator)
                      → Score Aggregation
                      → Dashboard / Alerts
                      → Weekly Report

Pre-Deployment (CI/CD)
  → Test Dataset (golden set, 100-500 examples)
  → Run all 5 metrics
  → Gate: Pass minimum thresholds → deploy
  → Fail → block deployment, alert team
```

## Component Selection

### Evaluation Frameworks
| Framework | Azure | GCP | Open Source |
|-----------|-------|-----|-------------|
| Managed Eval | Azure AI Evaluation SDK | Vertex AI Eval | — |
| Custom Eval | Azure OpenAI + code | Gemini + code | RAGAS, DeepEval, TruLens |
| Dashboard | Azure AI Studio | Vertex AI Studio | Weights & Biases, MLflow |

### LLM-as-Judge Setup
| Aspect | Recommendation |
|--------|---------------|
| Judge Model | GPT-4.1 or Gemini 2.5 Pro (stronger than the model being evaluated) |
| Rubric | Specific, with examples per score level |
| Samples | Minimum 100 per metric for statistical significance |
| Frequency | Pre-deploy: full test set. Production: 10% continuous sampling |

## Cost of Evaluation
| Component | Cost per 1K Evaluated Queries |
|-----------|------------------------------|
| LLM-as-Judge (5 metrics × GPT-4) | $15 |
| Content Safety API | $1 |
| Compute/Pipeline | ~$0 (async) |
| **Total** | **~$16 per 1K queries** |

At 10% sampling rate with 50K queries/month → 5K evaluated → **$80/month**.

## Golden Test Dataset Structure
```json
{
  "id": "test-001",
  "query": "What is our data retention policy for customer PII?",
  "expected_answer": "Customer PII must be retained for no more than 3 years...",
  "expected_sources": ["policies/data-security-policy.md"],
  "category": "compliance",
  "difficulty": "medium"
}
```

Minimum 100 examples, covering:
- Easy factual questions (30%)
- Multi-hop reasoning (20%)
- Edge cases / adversarial (20%)
- "I don't know" cases (15%)
- Cross-document synthesis (15%)

## Common Pitfalls
1. **No baseline** — Measure before making changes so you can quantify improvement
2. **Evaluating with the same model** — Don't use GPT-4 mini to judge GPT-4 mini. Use a stronger model.
3. **Too few test examples** — <50 examples → statistically meaningless
4. **Only evaluating accuracy** — Safety and latency are equally important
5. **Evaluating once, not continuously** — Quality degrades over time (data drift, prompt drift)

## Reference Implementation
This platform's evaluation pipeline (`src/evaluation/pipeline.py`) implements:
- Probabilistic 10% sampling in production
- Metric tracking (relevance, groundedness, coherence, safety)
- Audit-ready logging of evaluation results

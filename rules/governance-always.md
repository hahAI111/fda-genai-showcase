# Governance-Always Rule

## Rule

**Every AI interaction must pass through governance checks. No exceptions, no shortcuts.**

## Governance Pipeline (mandatory)

```
Input → Content Safety → PII Filter → Agent → Content Safety → Evaluation → Audit
```

Every step is mandatory. The pipeline is:
1. **Input screening** — Prompt injection detection, blocked topics
2. **PII masking** — Detect and mask PII before it reaches any model
3. **Agent processing** — The actual work
4. **Output screening** — Safety check on generated response
5. **Evaluation sampling** — Quality monitoring (10% of requests)
6. **Audit logging** — Every interaction logged for compliance

## Why This Matters

- Enterprise compliance requires provable governance
- PII leakage in LLM context windows is a real risk
- Audit trails are required by SOC 2, GDPR, HIPAA
- Governance that's optional will be skipped under pressure
- **If governance is middleware, it's invisible and reliable**

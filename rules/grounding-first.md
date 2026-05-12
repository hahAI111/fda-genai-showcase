# Grounding-First Rule

## Rule

**Never answer a factual question without first searching the knowledge base. Every claim must be traceable to a source document.**

## Correct ✅

```
User: What is our AI governance policy for PII data?

Agent: [searches knowledge base first]
According to [Source: AI Governance Policy v2.1, §3.2], all AI systems
processing PII must implement data minimization and purpose limitation.
```

## Incorrect ❌

```
User: What is our AI governance policy for PII data?

Agent: Generally, AI governance policies require data minimization
and encryption for PII data.
[No search performed, no specific source cited]
```

## Why This Matters

- Hallucination is the #1 blocker for enterprise AI adoption
- Ungrounded answers erode trust faster than "I don't know"
- Citations enable verification and audit
- This is a non-negotiable for production deployment

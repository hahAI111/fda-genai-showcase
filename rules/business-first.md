# Business-First Rule

## Rule

**Always start from the business objective, not the technology. Ask "what problem are we solving?" before "what tools should we use?"**

## Correct ✅

```
Customer: We want to use RAG for our internal docs.

You: Before we design the architecture, let me understand:
1. What business problem is this solving? (time-to-answer, accuracy, cost?)
2. Who are the end users? (legal team, engineers, customer support?)
3. What does success look like? (metric: resolution time ↓ 50%?)

[Then design the architecture based on answers]
```

## Incorrect ❌

```
Customer: We want to use RAG for our internal docs.

You: Great! Let me set up a vector database, configure embedding
models, and build a retrieval pipeline.
[Jumped to technology without understanding the business need]
```

## Why This Matters

- Same technology can serve completely different business goals
- Architecture decisions depend on success metrics (speed vs. accuracy vs. cost)
- Enterprise stakeholders evaluate solutions on business impact, not tech elegance
- This is what separates a Forward Deployed Architect from a developer

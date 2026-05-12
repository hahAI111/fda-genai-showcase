# Multi-Agent Architecture Patterns

## Overview
This document describes architectural patterns for multi-agent AI systems in
enterprise environments, including routing strategies, agent coordination,
and failure handling.

## Pattern 1: Orchestrator-Specialist

```
User → Orchestrator → [Knowledge | Analyst | Governance] → Response
```

**When to use**: Distinct task categories with specialized tools per agent.

**Pros**: Clean separation of concerns, independent agent evolution, per-agent evaluation.
**Cons**: +200ms routing latency, orchestrator is a single point of failure.

**Mitigation**: Fallback to default agent (knowledge) if orchestrator fails. Cache routing
decisions for repeated query patterns.

## Pattern 2: Pipeline (Sequential)

```
User → Agent A → Agent B → Agent C → Response
```

**When to use**: Tasks that require sequential processing stages.

**Example**: Query → Retrieval Agent → Analysis Agent → Review Agent → Response.

**Pros**: Each agent focuses on one transformation.
**Cons**: Total latency = sum of all agents. Failure in any stage blocks the pipeline.

## Pattern 3: Parallel Fan-Out

```
User → Orchestrator → [Agent A, Agent B, Agent C] (parallel) → Merge → Response
```

**When to use**: Independent subtasks that can run concurrently.

**Example**: "Compare our RAG approach vs competitors" →
- Agent A: Search our docs
- Agent B: Search competitor analysis
- Agent C: Search benchmarks
→ Merge: Combined comparison table

**Pros**: Lower latency for complex queries.
**Cons**: Higher cost (multiple LLM calls), merge logic can be complex.

## Agent Communication Patterns

### Context Propagation
Every agent call must propagate:
- `conversation_id`: Correlates all steps in one conversation
- `turn_id`: Identifies a single user turn
- `parent_agent`: Enables trace trees
- `user_id` / `tenant_id`: For audit and access control

### Tool-Calling Loop
```python
while iterations < max_iterations:
    response = llm.call(messages, tools)
    if response.has_tool_calls:
        results = execute_tools(response.tool_calls)
        messages.append(tool_results)
    else:
        return response.content  # Final answer
```

Key safeguards:
- **Max iterations**: Prevent infinite loops (default: 10)
- **Token budget**: Track cumulative tokens across iterations
- **Timeout**: Hard timeout per agent execution (default: 30s)

## Error Handling Strategies

### Retry with Backoff
```
1st failure → retry after 1s
2nd failure → retry after 2s
3rd failure → fallback response
```

### Graceful Degradation
| Failure | Fallback |
|---------|----------|
| Search tool fails | Answer with caveat "based on general knowledge" |
| Specialist agent fails | Orchestrator handles directly |
| Evaluation fails | Skip evaluation, log the failure |
| PII filter fails | Block the request (fail-safe) |

### Circuit Breaker
- After 5 consecutive failures in 60 seconds → open circuit
- Return fallback response immediately
- After 30 seconds → half-open (try one request)
- If success → close circuit; if failure → re-open

## Scaling Considerations
| Component | Scaling Strategy | Bottleneck |
|-----------|-----------------|-----------|
| Orchestrator | Horizontal (stateless) | LLM API rate limits |
| Knowledge Agent | Horizontal + AI Search replicas | Search latency |
| Analyst Agent | Horizontal | LLM token throughput |
| Governance Agent | Horizontal | Policy lookup latency |
| Evaluation Pipeline | Background queue | Cost (4 LLM calls/eval) |

# Multi-Agent Orchestration Pattern

## Pattern ID
`multi-agent-orchestration`

## When to Use
- Customer needs to handle 3+ distinct task types (Q&A, analysis, compliance, coding)
- Single-prompt approach leads to confused/inaccurate responses
- Different tasks need different tools (search, SQL, API calls)
- Enterprise requires per-task governance (e.g., compliance checks only on regulated queries)

## When NOT to Use
- Single-purpose bot (just Q&A, just summarization) → single agent is simpler
- Low query volume (<100/day) → overhead of multi-agent routing not justified
- All tasks use the same tools → agent specialization adds complexity without benefit

## Architecture Patterns

### Pattern 1: Router/Orchestrator (Recommended for Most Cases)
```
User → Orchestrator (LLM-based intent) → Agent A / Agent B / Agent C → Response
```
- **Pros**: Clean separation, each agent has focused system prompt, easy to add new agents
- **Cons**: +200-500ms routing latency, routing errors on ambiguous queries
- **Best for**: 3-10 specialized agents, enterprise workloads

### Pattern 2: Pipeline / Sequential
```
User → Agent A → Agent B → Agent C → Response
```
- **Pros**: Deterministic flow, easy to debug
- **Cons**: Latency = sum of all agents, can't skip unnecessary steps
- **Best for**: Fixed workflows (e.g., Extract → Validate → Summarize)

### Pattern 3: Parallel Fan-Out
```
User → Orchestrator → [Agent A, Agent B, Agent C] → Merge → Response
```
- **Pros**: Fastest for independent subtasks
- **Cons**: Merge logic is complex, wasted compute if some branches irrelevant
- **Best for**: Multi-perspective analysis, consensus-based decisions

### Pattern 4: Hierarchical (Agents calling Agents)
```
User → Manager Agent → [Worker A → Sub-Worker A1, Worker B] → Response
```
- **Pros**: Handles complex, multi-step tasks
- **Cons**: Hard to debug, runaway cost risk, deep call chains
- **Best for**: Research agents, coding agents, complex reasoning

## Component Selection

### Orchestration Layer
| Approach | Azure | GCP | Open Source |
|----------|-------|-----|-------------|
| Managed Agent Builder | Azure AI Agent Service | Vertex AI Agent Builder | — |
| Custom Orchestrator | Azure OpenAI + code | Vertex AI + code | LangGraph, CrewAI, AutoGen |
| Workflow Engine | Azure Durable Functions | Cloud Workflows | Temporal, Prefect |

### When to Use Managed vs Custom
| Factor | Managed (Agent Builder) | Custom Orchestrator |
|--------|------------------------|---------------------|
| Time to deploy | Hours | Days-Weeks |
| Customization | Limited | Full control |
| Governance hooks | Platform-provided | Must build yourself |
| Multi-agent routing | Built-in | Must implement |
| Cost control | Platform-managed | Must implement max_iterations, token budgets |
| Debugging | Dashboard-based | Full code traceability |
| **Choose when** | PoC, simple flows, <3 agents | Production, custom governance, >3 agents |

## Routing Strategy Comparison
| Strategy | Accuracy | Latency | Cost |
|----------|----------|---------|------|
| LLM-based intent classification | High (85-95%) | +200-500ms | $0.001-0.01/query |
| Embedding similarity to agent descriptions | Medium (70-85%) | +50ms | $0.0001/query |
| Keyword/regex rules | Low-Medium (60-75%) | +1ms | Free |
| Hybrid (rules first, LLM fallback) | High (90-95%) | +10-200ms | ~$0.003/query |

## Cost Model — Multi-Agent Overhead
| Scenario | Single Agent | 3-Agent + Router | Overhead |
|----------|-------------|-------------------|----------|
| Simple Q&A | 1 LLM call | 2 LLM calls (route + answer) | +100% |
| Analysis | 1-2 LLM calls | 2-3 LLM calls | +50% |
| Complex (tools + reasoning) | 3-5 LLM calls | 4-6 LLM calls | +20-30% |

**Rule of thumb**: Multi-agent adds 20-100% LLM cost. Justified when accuracy improvement > cost increase.

## Common Pitfalls
1. **Over-engineering** — Don't use multi-agent for a single-purpose chatbot
2. **No routing fallback** — If intent classification fails, default to knowledge agent
3. **Unbounded execution** — Set max_iterations (10) and token budgets per agent
4. **No cross-agent context** — Pass conversation_id and context between agents
5. **Testing individual agents but not the system** — Integration test the full routing flow

## Reference Implementation
This platform's Orchestrator (`src/agents/orchestrator.py`) implements Pattern 1 with:
- LLM-based intent classification (GPT-4.1-mini)
- 4 specialized agents (knowledge, analyst, governance, architect)
- Bounded execution (max 10 iterations per agent)
- Full execution trace propagation
- Context passing via AgentContext dataclass

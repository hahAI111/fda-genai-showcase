# Knowledge Base Index

Quick lookup for finding the right skill, agent, or reference for any topic.

---

## By Keyword

| Keyword | Skill | Agent | Context |
|---------|-------|-------|---------|
| search, find, retrieve, document, policy | [knowledge-retrieval](skills/knowledge-retrieval/SKILL.md) | knowledge | — |
| RAG, hybrid search, vector, embedding | [knowledge-retrieval](skills/knowledge-retrieval/SKILL.md) | knowledge | [rag-deployment](contexts/rag-deployment.md) |
| citation, source, grounding, hallucination | [knowledge-retrieval](skills/knowledge-retrieval/SKILL.md) | knowledge | — |
| compare, analyze, trend, insight | [analysis](skills/analysis/SKILL.md) | analyst | — |
| recommendation, trade-off, pros cons | [analysis](skills/analysis/SKILL.md) | analyst | — |
| executive summary, report | [report-generation](skills/report-generation/SKILL.md) | analyst | — |
| compliance, audit, regulation | [compliance-check](skills/compliance-check/SKILL.md) | governance | [governance-review](contexts/governance-review.md) |
| GDPR, HIPAA, SOC2, PCI-DSS | [compliance-check](skills/compliance-check/SKILL.md) | governance | [governance-review](contexts/governance-review.md) |
| PII, data privacy, sensitive data | [compliance-check](skills/compliance-check/SKILL.md) | governance | — |
| risk assessment, security review | [compliance-check](skills/compliance-check/SKILL.md) | governance | [governance-review](contexts/governance-review.md) |
| evaluation, quality, metrics, drift | [evaluation](skills/evaluation/SKILL.md) | quality-gate | — |
| relevance, groundedness, coherence, safety | [evaluation](skills/evaluation/SKILL.md) | quality-gate | — |
| benchmark, testing, production monitoring | [evaluation](skills/evaluation/SKILL.md) | quality-gate | — |
| discovery, requirements, customer | [discovery](skills/discovery/SKILL.md) | orchestrator | [customer-engagement](contexts/customer-engagement.md) |
| architecture, deployment, roadmap | [discovery](skills/discovery/SKILL.md) | orchestrator | [customer-engagement](contexts/customer-engagement.md) |
| ADR, decision record | [report-generation](skills/report-generation/SKILL.md) | analyst | — |
| ReAct, reasoning, thought, observation | — | react (any agent) | — |
| delegation, decompose, supervisor, worker | — | hierarchical orchestrator | — |
| tokens/sec, TTFT, cost, SLO, metrics | — | — (metrics module) | — |
| friction, feedback, feature request | — | — (feedback module) | — |
| OAuth, ADC, auth, identity, credentials | — | — (auth module) | — |

---

## By Enterprise Deployment Blocker

| Blocker | Relevant Module | Context |
|---------|----------------|---------|
| "Data is in 5 systems — how to unify?" | knowledge-retrieval skill, AI Search tool | rag-deployment |
| "Legal won't approve until we prove governance" | compliance-check skill, governance pipeline | governance-review |
| "How do we know it's still accurate after 3 months?" | evaluation skill, eval pipeline | — |
| "When something goes wrong, how do we debug?" | ReAct traces, observability | — |
| "Can other teams integrate without code changes?" | MCP server | — |
| "Zero-trust — no API keys" | auth module (ADC + OAuth 2.0) | — |
| "How much does this cost per request?" | metrics module, SLO enforcement | — |
| "How do we report product issues?" | feedback module, friction detection | — |
| "Can it reason, not just retrieve?" | ReAct agent, hierarchical delegation | — |

---

## Project Structure Quick Reference

```
skills/                          ← Declarative capability modules (6 Markdown)
├── knowledge-retrieval/         ← RAG + hybrid search
├── analysis/                    ← Structured insights
├── compliance-check/            ← Governance + risk
├── evaluation/                  ← Quality monitoring
├── discovery/                   ← Customer engagement
└── report-generation/           ← Formatted deliverables

.github/agents/                  ← Agent persona definitions (5 agents)
├── orchestrator.md              ← Intent routing
├── knowledge.md                 ← RAG specialist
├── analyst.md                   ← Analysis specialist
├── governance.md                ← Compliance specialist
└── quality-gate.md              ← Output reviewer

src/agents/                      ← Python agent implementations (8 agents)
├── base.py                      ← BaseAgent with tool-calling loop
├── orchestrator.py              ← Intent classification → route
├── react.py                     ← ReAct reasoning (Thought → Action → Observation)
├── hierarchy.py                 ← Hierarchical delegation (Supervisor → Worker)
├── knowledge.py                 ← RAG + citations
├── analyst.py                   ← Structured analysis
├── architect.py                 ← Architecture advisor
└── governance_agent.py          ← Compliance + risk

src/auth/                        ← Authentication (Google ADC + OAuth 2.0 + Azure)
src/metrics/                     ← LLM-Native Metrics (TPS, TTFT, cost, SLO)
src/feedback/                    ← Product Feedback Loop (friction → feature requests)
src/governance/                  ← Compliance pipeline (PII, safety, audit)
src/evaluation/                  ← Quality monitoring (LLM-as-judge, 10% sampling)
src/tools/                       ← AI Search + Storage + Registry
src/mcp/                         ← MCP server (streamable-http)
src/skills/                      ← Python skills (3 executable + base + loader)

rules/                           ← Behavioral constraints
contexts/                        ← Scenario-specific guides
docs/                            ← Architecture docs
```

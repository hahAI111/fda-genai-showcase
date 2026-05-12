# Copilot Instructions — Enterprise GenAI Platform

You are an enterprise GenAI platform assistant. This project is a **production-grade multi-agent AI system** with ReAct patterns, hierarchical delegation, LLM-native metrics, and Google Cloud architectural governance.

## Project Structure

This is a **hybrid project** — declarative Markdown knowledge modules + Python FastAPI backend:
- `skills/` — Reusable capability modules (Markdown SKILL.md files)
- `.github/agents/` — Agent persona definitions (Markdown files)
- `rules/` — Behavioral constraints
- `contexts/` — Scenario-specific investigation frameworks
- `src/` — Python backend (FastAPI, agents, tools, governance, evaluation)

## Skills

Skills are in `skills/*/SKILL.md`. Each skill has YAML frontmatter (name, description, allowed-tools) and a Markdown body with instructions, workflows, and examples.

| Skill | Purpose | Keywords |
|-------|---------|----------|
| [knowledge-retrieval](../../skills/knowledge-retrieval/SKILL.md) | RAG with hybrid search + citations | search, find, policy, document |
| [analysis](../../skills/analysis/SKILL.md) | Structured insights + recommendations | compare, trend, analyze, summary |
| [compliance-check](../../skills/compliance-check/SKILL.md) | Governance + risk assessment | compliance, risk, audit, GDPR, HIPAA |
| [evaluation](../../skills/evaluation/SKILL.md) | AI quality monitoring | quality, metrics, drift, benchmark |
| [discovery](../../skills/discovery/SKILL.md) | Customer engagement framework | requirements, architecture, deployment |
| [report-generation](../../skills/report-generation/SKILL.md) | Structured deliverables | report, executive summary, ADR |

## Agents

Agent definitions in `.github/agents/`:

| Agent | Role |
|-------|------|
| `orchestrator` | Intent classification → route to specialist |
| `knowledge` | RAG + citations (grounded answers only) |
| `analyst` | Structured analysis + recommendations |
| `governance` | Compliance checks + risk assessments |
| `quality-gate` | Review output for completeness + accuracy |

## BMAD Method (v6.3.0)

Installed at `_bmad/`. Use BMAD for structured planning before writing code.

| Phase | Key Skills | Purpose |
|-------|-----------|---------|
| Analysis | `bmad-product-brief`, `bmad-prfaq`, `bmad-brainstorming` | Ideation, research, product definition |
| Planning | `bmad-create-prd`, `bmad-create-ux-design` | Requirements, UX specifications |
| Solutioning | `bmad-create-architecture`, `bmad-create-epics-and-stories` | Architecture, work breakdown |
| Implementation | `bmad-dev-story`, `bmad-code-review`, `bmad-sprint-planning` | Build, review, iterate |

Quick start: invoke `bmad-help` to see recommended next steps.
Planning artifacts go to `_bmad-output/`.

## MCP Servers

Configured in `.vscode/mcp.json`:

| MCP | Purpose | Tools |
|-----|---------|-------|
| `enterprise-genai` | This platform's own capabilities | search, analyze, compliance check |

## Key Architecture Principles

1. **Identity-based auth only** — Google ADC + OAuth 2.0 / Azure DefaultAzureCredential, no API keys
2. **Governance as middleware** — PII filter + content safety + audit on every request
3. **Evaluation in production** — LLM-as-judge with 10% sampling
4. **ReAct patterns** — Agents reason explicitly (Thought → Action → Observation)
5. **Hierarchical delegation** — Supervisor → Planner → Worker agent chains
6. **LLM-native metrics** — tokens/sec, TTFT, cost-per-request, SLO enforcement
7. **Product feedback loop** — Auto-detect friction → feature requests
8. **Skills are reusable** — Extract field patterns into SKILL.md modules
9. **Agents have boundaries** — Each agent has clear "when to use / when NOT to use"
10. **BMAD for planning** — Business → Model → Architecture → Delivery before writing code

## Cloud Resources

### Google Cloud (Primary)

| Resource | Purpose | Auth |
|----------|---------|------|
| Vertex AI (Gemini 2.5 Flash) | LLM inference + reasoning | ADC / OAuth 2.0 |
| Vertex AI Search | Hybrid retrieval | ADC |
| Cloud Storage | Document source of truth | ADC |
| Cloud Trace | Distributed tracing | ADC |

### Azure (Multi-Cloud Support)

| Resource | Purpose | Auth |
|----------|---------|------|
| Azure AI Foundry | gpt-4.1-mini (chat) + text-embedding-3-large (vectors) | DefaultAzureCredential |
| Azure AI Search | Hybrid retrieval index (`enterprise-knowledge`, 67 chunks) | DefaultAzureCredential |
| Azure Blob Storage | Document source of truth (`enterprise-docs`, 13 docs) | DefaultAzureCredential |

Endpoint: `https://gpt522222.services.ai.azure.com`
Project: `proj-default`

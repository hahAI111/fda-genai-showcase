# Architecture Deep-Dive — Component-Level Technical Reference

> This document explains **how** each component works internally and **why** it
> was designed this way. For high-level overview see README.md; for file-by-file
> reference see FILE-REFERENCE.md.

---

## Table of Contents

1. [Multi-Agent System](#1-multi-agent-system)
2. [ReAct Reasoning Engine](#2-react-reasoning-engine)
3. [Hierarchical Delegation](#3-hierarchical-delegation)
4. [Tool System](#4-tool-system)
5. [Skill System (Dual Architecture)](#5-skill-system-dual-architecture)
6. [Governance Pipeline](#6-governance-pipeline)
7. [LLM-Native Metrics](#7-llm-native-metrics)
8. [Product Feedback Loop](#8-product-feedback-loop)
9. [Evaluation System](#9-evaluation-system)
10. [Authentication & Security](#10-authentication--security)
11. [MCP Integration](#11-mcp-integration)
12. [Observability](#12-observability)
13. [Data Flow: End-to-End Request](#13-data-flow-end-to-end-request)
14. [Declarative Architecture](#14-declarative-architecture)

---

## 1. Multi-Agent System

### Architecture Pattern: Two-Tier Orchestration

```
                    ┌───────────────────────────┐
                    │     Flat Orchestrator      │  ← Simple queries
                    │    (intent → route)        │
                    └────────────┬──────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                  │
     ┌────────▼───┐     ┌──────▼─────┐    ┌──────▼────────┐
     │  Knowledge  │     │  Analyst    │    │  Governance    │
     │  (ReAct +   │     │  (ReAct +   │    │  (ReAct +      │
     │   RAG)      │     │   Insight)  │    │   Compliance)  │
     └────────────┘     └────────────┘    └───────────────┘

                    ┌───────────────────────────┐
                    │  Hierarchical Orchestrator │  ← Complex queries
                    │  (decompose → delegate     │
                    │   → synthesize)            │
                    └────────────┬──────────────┘
                                │
                    ┌───────────▼──────────┐
                    │    Delegation Plan    │
                    │  ┌─────┬─────┬─────┐ │
                    │  │Sub-1│Sub-2│Sub-3│ │  ← Parallel/Sequential/DAG
                    │  └──┬──┴──┬──┴──┬──┘ │
                    │     ▼     ▼     ▼    │
                    │   Agent Agent Agent  │
                    └──────────┬───────────┘
                               ▼
                         Synthesized Result
```

### Why Two-Tier?

- **Simple queries** (80% of traffic): flat routing is faster (~200ms overhead)
- **Complex queries** (20%): hierarchical delegation decomposes into subtasks
- Customer chooses via API parameter or the orchestrator auto-detects complexity

### BaseAgent: The Tool-Calling Loop

```
┌─────────────────────────────────────────────────┐
│  BaseAgent.run(query, context)                   │
│                                                   │
│  1. governance_pre_hook(query)    ← overridable   │
│  2. LLM call with system prompt + tools           │
│  3. WHILE response has tool_calls:                │
│     a. Parse tool calls                           │
│     b. Execute each tool handler                  │
│     c. Append tool results to conversation         │
│     d. LLM call again (with tool results)          │
│     e. IF iterations > max_iterations → BREAK      │
│  4. governance_post_hook(response) ← overridable   │
│  5. Return AgentResponse                           │
│                                                    │
│  Tracking: steps[], total_tokens, latency_ms       │
│  Tracing: OpenTelemetry span per execution         │
└────────────────────────────────────────────────────┘
```

### Orchestrator: Intent Classification

Uses structured JSON output for routing:
```json
{
  "intent": "knowledge_query | analysis_request | compliance_check",
  "agent": "knowledge | analyst | governance",
  "reasoning": "Why this agent is the best fit",
  "refined_query": "Optimized version of the user's query"
}
```

**Why LLM-based routing?** Rule-based routing fails on ambiguous queries.
"Is our PII handling compliant with GDPR?" could be knowledge (find the policy)
or governance (assess compliance). The LLM understands intent, not just keywords.

---

## 2. ReAct Reasoning Engine

### Pattern: Thought → Action → Observation → Self-Critique

```
┌───────────────────────────────────────────────────┐
│  ReActAgent.run(query, context)                    │
│                                                     │
│  FOR each iteration (max_iterations=10):            │
│    1. LLM call → structured JSON output:            │
│       {                                             │
│         "thought": "I need to find PII policies",   │
│         "action": "search_knowledge",               │
│         "action_input": {"query": "PII policy"},    │
│         "self_critique": "Am I being thorough?"     │
│       }                                             │
│    2. Execute action → Observation                  │
│    3. Append [Thought, Action, Observation] to trace│
│    4. IF "final_answer" in response → BREAK         │
│                                                     │
│  Token Budget: max_tokens_budget = 50,000           │
│  Output: AgentResponse + react_traces in metadata   │
│                                                     │
│  Multi-Cloud:                                       │
│    Google → _gemini_call() with wrapper classes      │
│    Azure  → _azure_call() with OpenAI SDK           │
└───────────────────────────────────────────────────┘
```

### Why ReAct?

| Dimension | Standard Agent | ReAct Agent |
|-----------|---------------|-------------|
| Reasoning | Hidden in prompt | Explicit Thought → Action → Observation |
| Debugging | "Why did it do that?" | Full trace: each step documented |
| Auditing | Black box | Every reasoning step logged |
| Self-correction | None | Self-critique catches errors mid-execution |
| Cost control | None | Token budget enforcement |

### Gemini Compatibility

ReAct wraps Gemini responses in OpenAI-compatible wrapper classes:
- `_GeminiResponseWrapper` → mimics `ChatCompletion`
- `_GeminiChoice` → mimics `Choice`
- `_GeminiMessage` → mimics `ChatCompletionMessage`
- `_GeminiUsage` → mimics `CompletionUsage`

This allows the same ReAct loop to work with both Gemini and Azure OpenAI.

---

## 3. Hierarchical Delegation

### Pattern: Supervisor → Planner → Worker

```
Complex Query
    │
    ▼
┌─────────────────────────┐
│  HierarchicalOrchestrator│
│  1. _create_plan()       │  ← LLM decomposes into subtasks
│     → DelegationPlan     │
│       ├── Task 1 → knowledge agent
│       ├── Task 2 → analyst agent
│       └── Task 3 → governance agent
│                          │
│  2. Execute strategy:    │
│     • parallel           │  ← asyncio.gather (independent tasks)
│     • sequential         │  ← ordered pipeline
│     • dag                │  ← dependency graph
│                          │
│  3. _synthesize()        │  ← LLM merges all results
│     → Final response     │
└─────────────────────────┘
```

### Execution Strategies

| Strategy | When | Example |
|----------|------|---------|
| **Parallel** | Tasks are independent | "Compare RAG approaches AND check compliance" |
| **Sequential** | Tasks depend on prior results | "Find data → Analyze → Report" |
| **DAG** | Mixed dependencies | "Search + Analyze in parallel → Synthesize" |

### Failure Isolation

Each sub-agent runs independently. If one fails:
- Error is captured in `DelegationTask.result`
- Other agents continue execution
- Synthesizer incorporates partial results with failure context

---

## 4. Tool System

### Tool Registry Pattern

```
┌──────────────┐        ┌──────────────┐
│ ToolRegistry │───────►│ToolDefinition│ × N
│              │        │  name         │
│ register()   │        │  description  │
│ get()        │        │  parameters   │
│ to_openai()  │        │  handler()    │
│ by_category()│        │  category     │
└──────────────┘        └──────────────┘
```

### Agent → Tool Mapping

| Agent | Tools | Underlying Implementation |
|-------|-------|--------------------------|
| KnowledgeAgent | `search_knowledge` | AI Search hybrid retrieval |
| AnalystAgent | `search_for_analysis`, `compare_documents` | AI Search |
| GovernanceAgent | `check_policy`, `assess_risk` | AI Search + risk rules |
| ArchitectAgent | `search_patterns`, `load_scenario`, `estimate_cost`, `generate_diagram` | AI Search + YAML + cost tables |

### Hybrid Retrieval Pipeline

```
Query: "What is our PII handling policy?"
    │
    ├── Vector Search (semantic similarity)
    │   └── Embedding → cosine similarity → ranked results
    │
    ├── Keyword Search (exact matching)
    │   └── BM25 full-text → "PII" exact match
    │
    └── Semantic Ranking (re-ranking)
        └── Cross-encoder re-ranks combined results
            │
            ▼
        Top-K results (default: 5)
```

### Agentic Retrieval Pipeline

Agentic Retrieval (`POST /retrieve`) adds LLM-driven query planning on top of hybrid search.
Compared to basic `/search`, it decomposes complex questions, searches multiple sources in parallel, and returns structured results.

```
User Query: "Compare RAG vs fine-tuning for regulatory compliance"
    │
    ├── 1. Content Safety → screen input
    ├── 2. PII Filter → mask sensitive data
    │
    ├── 3. Knowledge Base (gpt-5.2 query planning)
    │   ├── Sub-query 1: "RAG architecture benefits compliance" → [ks-enterprise-index, ks-enterprise-docs]
    │   ├── Sub-query 2: "Fine-tuning regulatory documents"     → [ks-enterprise-index, ks-enterprise-docs]
    │   └── Sub-query 3: "Compliance requirements AI systems"   → [ks-enterprise-index, ks-enterprise-docs]
    │                                       (all parallel)
    ├── 4. Aggregation + deduplication
    ├── 5. Content Safety → screen outputs
    ├── 6. Audit Logger → compliance logging
    │
    ▼
    RetrieveResponse {
      grounding_data: [{title, content, source, score, reranker_score}],
      source_citations: [{index, title, source_url, sources}],
      execution_plan: {user_query, sub_queries, sources, planned_at},
      sub_query_results: [{sub_query, source_name, results_count, execution_time_ms}],
      governance: {input_safety, pii, output_safety},
      performance: {total_latency_ms, items_retrieved, activities}
    }
```

**Key differences from `/search`:**

| Aspect | `/search` (Basic RAG) | `/retrieve` (Agentic) |
|--------|----------------------|----------------------|
| Query handling | Direct single query | LLM decomposes into sub-queries |
| Data sources | 1 index | 2+ sources in parallel |
| Scoring | 0.01-0.02 range | 1.9-2.4 range (reranker) |
| Latency | ~200ms | ~2000ms |
| Best for | Simple, direct questions | Complex, multi-faceted questions |

**Knowledge Sources (current):**

| Source | Type | Description |
|--------|------|-------------|
| `ks-enterprise-index` | searchIndex | Points to `enterprise-knowledge` index (68 docs) |
| `ks-enterprise-docs` | azureBlob | Auto-indexes `enterprise-docs` blob container (28 docs) |

---

## 5. Skill System (Dual Architecture)

### Two Types of Skills

| Aspect | Python Skills | Markdown Skills |
|--------|--------------|----------------|
| **Location** | `src/skills/*.py` | `skills/*/SKILL.md` |
| **Has tools** | Yes — executable handlers | No — context/prompts only |
| **Has prompt** | Optional | Always (the Markdown body) |
| **Created by** | Engineers | Engineers or FDA field staff |
| **Count** | 5 (base, loader, search, analysis, compliance) | 6 (knowledge-retrieval, analysis, compliance-check, discovery, evaluation, report-generation) |

### Why Both?

**Python skills** handle execution — tool schemas + handler functions.
**Markdown skills** capture domain knowledge — when to use, how to approach, quality criteria.

Together: capability (tool) + expertise (when/how to use it).

### SKILL.md Format

```yaml
---
name: knowledge-retrieval
description: >
  Use this skill when answering factual questions...
allowed-tools:
  - vertex_ai_search
  - Read
---

# Knowledge Retrieval (Enterprise RAG)
## When to Use
## When NOT to Use
## Workflow
## Quality Checklist

### 5.1 Skill Loading Lifecycle (Startup)

**When**: During FastAPI `lifespan()` context manager startup (lines 370–378)

```python
# Initialize skill registry
skill_registry = SkillRegistry()

# Register Python-coded skills
skill_registry.register(SearchSkill())           # RAG retrieval
skill_registry.register(AnalysisSkill())         # Structured analysis
skill_registry.register(ComplianceSkill())       # Compliance checks

# Load declarative Markdown skills
project_root = Path(__file__).resolve().parent.parent
md_count = load_markdown_skills(project_root / "skills", skill_registry)
# Loads: knowledge-retrieval, analysis, compliance-check, discovery, evaluation, report-generation
```

### 5.2 Runtime: Skill Injection into Agent System Prompt

When an agent executes, it dynamically loads the skill instructions:

```python
# In GovernanceAgent.system_prompt()
skill = self.skill_registry.get("compliance-check")
# skill.body contains the Markdown content from SKILL.md
system_prompt = f"""
You are a compliance expert. Your role is to assess regulatory risks.

Use this guidance:
{skill.body}  # ← Markdown document injected directly into prompt

When answering:
- Reference the specific policy requirement
- Rate risk as Low / Medium / High
- Suggest remediation steps
"""
```

### 5.3 Example Flow: GDPR Compliance Check Request

```
User: "Is our data processing GDPR-compliant?"
  │
  ▼
1. Orchestrator detects "compliance + assessment" → routes to GovernanceAgent
  │
  ▼
2. GovernanceAgent.run():
   - Loads skill: skill_registry.get("compliance-check")
   - Injects skill.body into system prompt
   - Executes ReAct loop:
   Thought: "Need to find GDPR data protection requirements"
   Action: search_knowledge("GDPR data protection Article 5")
   Observation: [Results from knowledge index]
   Action: assess_risk("data processing", policies=["GDPR"])
   Observation: [Risk assessment from tool]
   Final Answer: "Based on GDPR Article 5 requirements... Risk: MEDIUM..."
  │
  ▼
3. Governance output safety check
  │
  ▼
4. Return response + react_traces + citations + governance_report
```

### 5.4 Tool Allowlist in SKILL.md

Each skill defines which tools it can invoke via `allowed-tools`:

```yaml
---
name: compliance-check
allowed-tools:
  - knowledge_retrieval      # ← Can call search
  - risk_assessment          # ← Can call risk scorer
---
```

The SkillRegistry enforces this—if an agent tries to call a tool not in `allowed-tools`,
the registry returns an error. This prevents privilege escalation: a "read-only" skill
cannot invoke expensive operations.
```

---

## 6. Governance Pipeline

### Pipeline Architecture

```
Request ──► INPUT GUARD ──► AGENT ──► OUTPUT GUARD ──► Response
               │                          │
          ┌────▼────┐              ┌─────▼──────┐
          │ContentSafety│           │ContentSafety│
          │.screen_input│           │.screen_output│
          └────┬────┘              └─────┬──────┘
          ┌────▼────┐              ┌─────▼──────┐
          │PIIFilter │              │ LLM Metrics │
          │.mask()   │              │ .record()   │
          └────┬────┘              └─────┬──────┘
          ┌────▼────┐              ┌─────▼──────┐
          │AuditLog  │              │ Feedback    │
          │.log_query│              │ .analyze()  │
          └─────────┘              └─────┬──────┘
                                   ┌─────▼──────┐
                                   │EvalPipeline │
                                   │.evaluate()  │
                                   └─────┬──────┘
                                   ┌─────▼──────┐
                                   │AuditLog     │
                                   │.log_response│
                                   └────────────┘
```

### Why Governance as Middleware?

Agents don't know they're being monitored. You can't bypass governance without
modifying `main.py`. Same pattern as web middleware (authentication, rate limiting).

### Content Safety: Defense in Depth

- Prompt injection detection (role hijacking, instruction override, system prompt extraction)
- Blocked topics (configurable deny list)
- Result: SAFE → continue | WARNING → log + continue | BLOCKED → 400 error

### PII Filter: Mask Before LLM

6 PII types detected: Email, Phone, SSN, Credit Card, IP Address, Date of Birth.
Masking happens before the LLM call — PII never enters the context window.

### Audit Trail: JSONL

Append-only, one JSON object per line. Ingestible by SIEM systems (Splunk, Sentinel, Chronicle).

---

## 7. LLM-Native Metrics

### Why LLM-Native?

| HTTP Metric | LLM-Native Metric | Why It Matters |
|------------|-------------------|----------------|
| Response time (p99) | **TTFT** (Time to First Token) | User-perceived responsiveness |
| Requests/sec | **Tokens/sec (TPS)** | Actual model throughput |
| Error rate | **Cost-per-request** | Business accountability |
| — | **Context utilization** | Prompt efficiency (% of window used) |
| — | **Token efficiency** | Output quality per token spent |
| — | **ReAct iterations** | Reasoning complexity |

### SLO Definitions

| Metric | Target | Breach Action |
|--------|--------|--------------|
| TTFT | < 500ms | Alert + friction point |
| TPS | > 30 tokens/sec | Alert + model comparison |
| p99 Latency | < 5,000ms | Alert |
| Cost/request | < $0.05 | Alert + cost optimization |

### Model Comparison

MetricsCollector supports comparing performance across models:
- Gemini 2.5 Flash vs. GPT-4.1-mini vs. Llama
- Cost, speed, and quality dimensions
- Data-driven model selection per use case

---

## 8. Product Feedback Loop

### Friction Detection Pipeline

```
LLM Metrics (every request)
    │
    ├── TTFT > 500ms?         → FrictionPoint(category=performance)
    ├── TPS < 30?             → FrictionPoint(category=performance)
    ├── Cost > $0.05?         → FrictionPoint(category=cost)
    ├── Context > 80%?        → FrictionPoint(category=api)
    ├── Grounding < 0.7?      → FrictionPoint(category=quality)
    └── Auth failures?        → FrictionPoint(category=integration)
         │
         ▼
    FrictionPoint.to_feature_request()
         │
         ▼
    Structured Feature Request
    {
      title: "Optimize TTFT for Gemini 2.5 Flash",
      priority: "high",
      category: "performance",
      evidence: {ttft_p95: 680, threshold: 500, sample_size: 100},
      suggested_action: "Enable response streaming..."
    }
```

### Why Automated?

Field friction rarely reaches engineering through traditional channels.
Auto-detection creates a data-driven product improvement pipeline:
1. Detect friction in production metrics
2. Generate structured feature requests with evidence
3. Export report for product team review
4. Track resolution over time

---

## 9. Evaluation System

### LLM-as-Judge: 4 Dimensions

| Metric | What It Measures | Pass Threshold |
|--------|-----------------|---------------|
| Relevance | Does it answer the right question? | ≥ 0.7 |
| Groundedness | Are claims supported by evidence? | ≥ 0.7 |
| Coherence | Is it well-structured and clear? | ≥ 0.7 |
| Safety | Does it follow content policies? | ≥ 0.9 |

### Production Sampling

10% of requests are evaluated (configurable). Each evaluation costs ~$0.02.
Drift detection: 7-day rolling average triggers alerts on quality regression.

---

## 10. Authentication & Security

### Zero-Trust Auth Model

```
Azure (Current Verified Runtime):
  App → DefaultAzureCredential / API key mode → Entra ID / Azure OpenAI → AI Foundry / Search / Blob
         │
         ├── In development: az login or local API-key-based demo setup
         ├── In App Service: Managed Identity
         └── In AKS: Workload Identity

Google Cloud (Optional Design Path):
  App → ADC → Google IAM → Token → Vertex AI / Search / Storage
         │
         ├── In development: gcloud auth application-default login
         ├── In GKE: Workload Identity (k8s-federated)
         └── In Cloud Run: Service Account (auto-provisioned)

Cross-Cloud:
  App → WorkloadIdentityBridge → Azure token → GCP token
```

### OAuth 2.0 for User Flows

```
User → /auth/login → Google OAuth consent → /auth/callback → Session token
```

Scopes are minimal per service. In the currently validated runtime, Azure identity and service-specific permissions are the main operational path.
Tokens are never logged. Sessions are tracked via `AuthSession` dataclass.

---

## 11. MCP Integration

### Server Architecture

```
FastAPI App (port 8000)
    │
    ├── REST API: /health, /chat, /skills, /metrics, /feedback, /auth
    │
    └── MCP Server: /mcp/ (streamable-http)
         ├── search_knowledge
         ├── analyze_document
         ├── check_compliance
         └── get_platform_status
```

MCP operates as a **parallel interface** — shares `AISearchTool` with agents but
bypasses the orchestrator and governance pipeline. External MCP clients (VS Code,
Claude Desktop) connect directly to tools.

---

## 12. Observability

### Two-Layer Stack

```
Layer 1: Structured Logging (structlog)
├── JSON format (machine-parseable)
├── Correlation IDs (conversation_id in every log)
└── Output: stdout → log aggregator

Layer 2: Distributed Tracing (OpenTelemetry)
├── Spans per: request, agent, tool call, governance check
├── Parent-child relationships
├── Export: OTLP → Cloud Trace / Jaeger / Zipkin
└── FastAPI auto-instrumentation
```

---

## 13. Data Flow: End-to-End Request

### Chat Flow

`POST /chat {"message": "What is our AI governance policy for PII?"}`

```
 1. FastAPI receives request
 2. OAuth / ADC authentication check
 3. ContentSafety.screen_input() → SAFE
 4. PIIFilter.mask() → no PII detected
 5. AuditLogger.log_query()
 6. Orchestrator.route() → {agent: "knowledge"}
 7. KnowledgeAgent.run() (ReAct loop):
    Thought: "I need to find the PII governance policy"
    Action: search_knowledge("AI governance policy PII")
    Observation: [{title: "AI Governance Policy v2.1", score: 0.94}]
    Final Answer: "According to the Enterprise AI Governance Policy v2.1..."
 8. ContentSafety.screen_output() → SAFE
 9. MetricsCollector.record() → {tps: 45, ttft: 320ms, cost: $0.012}
10. FeedbackCollector.analyze() → no friction detected
11. EvaluationPipeline.maybe_evaluate() → 10% chance
12. AuditLogger.log_response()
13. Return ChatResponse with citations, governance, metrics, react_traces
```

### Agentic Retrieval Flow

`POST /retrieve {"query": "How does GDPR compliance relate to data retention?", "reasoning_effort": "medium"}`

```
 1. FastAPI receives request
 2. ContentSafety.screen_input() → SAFE
 3. PIIFilter.mask() → no PII detected
 4. AuditLogger.log_query()
 5. KnowledgeBase.retrieve_and_plan():
    a. POST to Azure AI Search Agentic Retrieval API
    b. LLM (gpt-5.2) plans sub-queries
    c. Parallel search across ks-enterprise-index + ks-enterprise-docs
    d. 3 activities, 7 grounding results returned
 6. ContentSafety.screen_output() for each grounding item
 7. AuditLogger.log_response()
 8. Return RetrieveResponse with grounding_data, citations, execution_plan, governance
```

---

## 14. Declarative Architecture

### Foundry-Agency Pattern

```
DECLARATIVE (Markdown)               IMPERATIVE (Python)
┌──────────────────────┐             ┌──────────────────────┐
│ WHAT the system does │  ◄─ loads ─ │ HOW it executes      │
│ WHEN to use skills   │             │ Tool handlers         │
│ Rules for behavior   │             │ API endpoints         │
│ Investigation guides │             │ Governance pipeline   │
└──────────────────────┘             └──────────────────────┘

skills/*/SKILL.md                    src/skills/*.py
.github/agents/*.md                  src/agents/*.py
rules/*.md                           src/governance/*.py
contexts/*.md                        src/evaluation/*.py
INDEX.md                             src/main.py
```

**Why?** Domain experts write skills (Markdown). Engineers write execution (Python).
Git diff shows how field knowledge evolves. The Markdown is literally what gets
injected into agent system prompts — optimized for LLM consumption.

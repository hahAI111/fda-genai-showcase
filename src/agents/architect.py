"""Architect Agent — AI Architecture Advisor for Customer Engagements.

This is the core FDA tool: given a customer scenario (industry, requirements,
constraints, budget), the architect agent recommends an architecture by:
1. Searching architecture patterns knowledge base
2. Matching customer constraints to component options
3. Estimating costs
4. Identifying risks and trade-offs

This agent turns the platform from "demo project" into "the tool I'd use on Day 1."
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.agents.base import AgentContext, AgentRole
from src.agents.react import ReActAgent
from src.tools import api as tool_api

ARCHITECT_DOMAIN_PROMPT = """\
You are an AI Architecture Advisor, the core agent of the **FDA Architecture Toolkit**.
This toolkit is built for Field Development Architects (FDAs) to interactively design
production-ready GenAI architectures for customer engagements.

When someone asks "what can you do" or "what is this toolkit", respond with:

**FDA Architecture Toolkit** — An interactive architecture advisor for GenAI customer engagements.

**What I can do:**
1. **Load Industry Scenarios** — Pre-built customer scenarios (financial compliance, healthcare, manufacturing, retail) with real constraints, budgets, and requirements. Use `/scenarios` to list them, `/scenario <id>` to load one.
2. **Generate Architecture Recommendations** — Given a scenario or freeform requirements, I recommend specific components (search, LLM, governance, compute), provide cost breakdowns, identify risks, and create implementation roadmaps.
3. **What-If Analysis** — Ask follow-up questions like "What if budget is only $2K?", "What if we use GCP instead?", "Add multi-language support?" and I'll adjust the architecture accordingly.
4. **Search Architecture Patterns** — I have a knowledge base of 6 proven patterns: RAG Enterprise, Multi-Agent Orchestration, Governance Pipeline, Build-vs-Buy (Agent Builder), Evaluation Framework, and Cost Optimization.
5. **Cost Estimation** — Detailed per-component monthly cost breakdowns with model pricing, search tier pricing, and governance cost multipliers.

**This platform itself is the reference implementation** — it uses RAG with hybrid search, 4-agent orchestration, governance pipeline, and evaluation framework, all on Azure.

---

When advising on architecture (not describing yourself), you MUST:
1. Start by understanding the customer's industry, scale, and constraints
2. Search the patterns knowledge base for relevant architecture templates
3. Recommend specific components with justification (why X over Y)
4. Provide cost estimates (monthly, broken down by component)
5. Identify risks and trade-offs
6. Reference this platform's implementation as a working example where relevant

Output format for architecture recommendations:

## Recommended Architecture
<Architecture name and 1-sentence summary>

## Components
| Layer | Component | Recommendation | Why |
<table of component choices with reasoning>

## Cost Estimate
| Component | Monthly Cost | Notes |
<cost breakdown>
**Total: $X/month**

## Trade-offs & Alternatives
- <what was considered but not recommended, and why>

## Risks
- <identified risks with mitigation strategies>

## Implementation Roadmap
1. Week 1-2: <first milestone>
2. Week 3-4: <second milestone>
3. Month 2: <third milestone>

## Technical Deep Dive
For each domain below, provide a **graduate-level technical analysis** — the kind of depth
you would present in a systems design review at Google, a PhD qualifying exam, or a principal
engineer architecture review. Do NOT write generic bullet points. Write as a senior architect
who has built and debugged these systems in production.

### 1. GenAI Architecture and System Design
- Formally classify the system (RAG, ReAct agent, Plan-and-Execute, etc.) and cite the foundational paper or design pattern.
- Explain the orchestration topology: is it a DAG, tree, or flat dispatch? Why?
- Analyze context window budget allocation: how many tokens for system prompt, retrieved chunks, conversation history, and generation?
- Describe the grounding mechanism: how does retrieval-augmented generation reduce P(hallucination)? What confidence thresholds or calibration methods are used?
- If multi-agent: what is the inter-agent communication protocol (shared memory, message passing, tool-call chaining)? What are the failure modes?

### 2. Cloud Infrastructure and Distributed Systems
- Map every service to its specific SKU/tier and explain the capacity planning rationale.
- Network topology: VPC/subnet design, private endpoints, DNS resolution, egress costs.
- Scaling model: stateless vs stateful components, auto-scaling trigger metrics (CPU? queue depth? request latency?), cold start mitigation.
- Failure domains and blast radius: what happens when a single AZ goes down? What is the RTO/RPO?
- IaC approach: Terraform modules, resource naming conventions, environment promotion strategy.

### 3. Information Retrieval and Data Architecture
- Chunking: analyze the trade-off between chunk size and retrieval precision. What is the optimal chunk size for this domain and why? Overlapping windows vs semantic boundaries.
- Embedding space: model architecture (transformer encoder? dual encoder?), dimensionality vs recall trade-off, quantization (PQ/SQ) impact on recall@k.
- Retrieval pipeline: multi-stage — BM25 candidate generation → dense retrieval → cross-encoder reranking. Explain the precision/recall trade-off at each stage.
- Index architecture: HNSW parameters (M, efConstruction, efSearch), sharding strategy, incremental vs full rebuild, staleness guarantees.
- Query understanding: query expansion, intent classification, or HyDE? What preprocessing improves retrieval quality?

### 4. Large Language Model Engineering
- Model selection decision matrix: benchmark scores (MMLU, HumanEval, medical QA), latency profiling (TTFT, TPS), cost per million tokens, context window utilization.
- Prompt engineering: structured output (JSON mode, function calling), chain-of-thought, few-shot exemplars. How are prompts versioned and regression-tested?
- Token optimization: KV-cache reuse, prompt caching, semantic compression, context distillation. Quantify the cost/latency savings.
- Inference architecture: streaming (SSE/WebSocket), batching strategy, speculative decoding, model routing (fast model for simple queries, powerful model for complex ones).

### 5. Security Architecture and Compliance
- Threat model: enumerate attack surfaces (prompt injection, data exfiltration, model inversion, training data extraction).
- PII/PHI pipeline: detection → classification → de-identification → audit trail. What regex/NER/ML models are used? False positive/negative rates?
- Encryption: at-rest (AES-256, CMEK/BYOK), in-transit (TLS 1.3, mTLS between services), in-use (confidential computing if applicable).
- Access control: RBAC/ABAC model, service account least-privilege, network policies, WAF rules.
- Compliance mapping: specific controls mapped to framework requirements (e.g., HIPAA §164.312(a)(1) → encryption, SOC2 CC6.1 → access control).

### 6. ML Evaluation and Production Observability
- Offline evaluation: groundedness (citation verification), relevance (NDCG@k), coherence, faithfulness. What evaluation datasets and how are they maintained?
- Online evaluation: A/B testing framework, canary deployments with automatic rollback triggers, interleaving experiments.
- Observability stack: distributed tracing (OpenTelemetry), custom metrics (token usage, retrieval recall, safety filter trigger rate), latency percentiles (p50/p95/p99).
- Feedback loop: user thumbs-up/down → fine-tuning dataset, retrieval quality signals → re-indexing triggers, drift detection.
- SLOs: define specific SLIs and error budgets (e.g., p99 latency < 3s, groundedness > 0.85, availability > 99.9%).

### 7. Cost Engineering and FinOps
- Build a per-query unit economics model: input tokens + output tokens + embedding + search + compute + storage = cost/query.
- Optimization levers with quantified impact: prompt caching (X% reduction), model tiering (Y% savings on simple queries), batch inference for non-real-time workloads.
- TCO comparison: managed services vs self-hosted (e.g., managed vector DB vs self-hosted Qdrant on GKE). Include ops cost.
- Capacity planning: project cost at 2x, 5x, 10x current load. Where are the cost cliffs (tier boundaries, reserved capacity thresholds)?

### 8. Multilingual and Cross-lingual Systems (if applicable)
- Embedding model multilingual capability: was it trained on parallel corpora? What is recall@10 for cross-lingual queries?
- Language detection: what classifier (fastText, CLD3)? How does it handle code-switching within a single query?
- Cross-lingual retrieval: do you retrieve in the query language or all languages? How does translation affect semantic similarity scores?
- Localization beyond language: date/number formats, cultural context in prompts, domain-specific terminology (e.g., medical terms differ between regions).

Write with the precision of a technical paper and the practicality of a production postmortem.
Every claim must reference a specific component, configuration, or metric from the architecture above.

Rules:
- ALWAYS cite architecture patterns using [Pattern: <name>]
- NEVER recommend without searching the knowledge base first
- Be specific with component names and pricing (not vague)
- If you don't have enough info, ASK — don't guess
- When comparing Azure vs GCP vs open-source, present all options fairly
- Always consider the customer's existing cloud and team size
- After generating an architecture recommendation, ALWAYS call the generate_diagram tool with:
  1. A Mermaid diagram (flowchart TD/LR, simple labels, no & < > inside brackets, use 'and' not '&')
  2. A `dashboard_data` JSON string containing ALL of these fields:
     - "summary": {"name", "description", "total_cost" (string like "$2,500/mo"), "timeline" (like "8 weeks"), "component_count" (int)}
     - "components": array of {"name", "layer", "service", "tier", "cost" (string), "justification", "icon" (emoji)}
     - "costs": array of {"component", "monthly" (number, not string!), "notes"}
     - "risks": array of {"risk", "severity" ("high"/"medium"/"low"), "mitigation"}
     - "roadmap": array of {"phase", "timeline", "tasks" (array of strings)}
     - "tradeoffs": array of {"option", "chosen", "reason"}
     - "skills": array of {"category" (one of the 8 Technical Deep Dive categories), "details" (graduate-level technical analysis, NOT generic bullet points — write like a principal engineer's design review)}
  This data drives an interactive visual dashboard — component cards, cost bar charts, risk matrix, timeline, trade-off table, and technical deep-dive cards. Make each field detailed and specific, not generic.
"""


class ArchitectAgent(ReActAgent):
    """Architecture advisor agent with ReAct reasoning.

    Uses the ReAct reasoning loop:
    Thought (understand requirements) → Action (search_patterns/load_scenario/estimate_cost) → Observation (data) → ... → Final Answer (architecture + dashboard)
    """

    def __init__(self, search_tool=None):
        super().__init__(
            name="architect",
            role=AgentRole.ARCHITECT,
            description=(
                "Designs AI agent architectures for customer scenarios. "
                "Recommends components, estimates costs, identifies risks. "
                "Searches architecture patterns knowledge base for proven solutions."
            ),
        )
        self._search_tool = search_tool
        self._register_tools()

    @property
    def domain_instructions(self) -> str:
        return ARCHITECT_DOMAIN_PROMPT

    def _register_tools(self):
        self.register_tool(
            func=self._search_patterns,
            name="search_patterns",
            description=(
                "Search the architecture patterns knowledge base. Contains proven "
                "patterns for RAG, multi-agent orchestration, governance pipelines, "
                "agent builder (build vs buy), evaluation frameworks, and cost optimization. "
                "Each pattern includes component comparisons (Azure vs GCP vs open-source), "
                "cost models, common pitfalls, and decision frameworks."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Search query — be specific about what pattern or comparison you need. "
                            "Examples: 'RAG architecture cost model', 'managed vs custom agent builder', "
                            "'governance pipeline HIPAA requirements'"
                        ),
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results (default: 8 for broader context)",
                        "default": 8,
                    },
                },
                "required": ["query"],
            },
        )

        self.register_tool(
            func=self._load_scenario,
            name="load_scenario",
            description=(
                "Load a pre-built customer scenario with full context: industry profile, "
                "requirements, constraints, budget, and expected architecture. "
                "Available scenarios: financial-compliance, healthcare-knowledge, "
                "manufacturing-qa, retail-customer-service."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "scenario_id": {
                        "type": "string",
                        "description": "Scenario ID to load",
                        "enum": [
                            "financial-compliance",
                            "healthcare-knowledge",
                            "manufacturing-qa",
                            "retail-customer-service",
                        ],
                    },
                },
                "required": ["scenario_id"],
            },
        )

        self.register_tool(
            func=self._estimate_cost,
            name="estimate_cost",
            description=(
                "Estimate monthly costs for a GenAI architecture based on components and query volume."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "monthly_queries": {
                        "type": "integer",
                        "description": "Expected monthly query volume",
                    },
                    "document_count": {
                        "type": "integer",
                        "description": "Number of documents in the knowledge base",
                    },
                    "model": {
                        "type": "string",
                        "description": "LLM model choice (e.g., gpt-4.1-mini, gemini-2.5-flash)",
                        "default": "gpt-4.1-mini",
                    },
                    "search_tier": {
                        "type": "string",
                        "description": "Search service tier (basic, standard, premium)",
                        "default": "standard",
                    },
                    "governance_level": {
                        "type": "string",
                        "description": "Governance level (minimal, standard, enterprise)",
                        "default": "standard",
                    },
                },
                "required": ["monthly_queries"],
            },
        )

        self.register_tool(
            func=self._generate_diagram,
            name="generate_diagram",
            description=(
                "Generate an interactive architecture dashboard with diagram, component cards, "
                "cost charts, risk matrix, roadmap timeline, and technical deep-dive analysis. "
                "Call this AFTER making an architecture recommendation."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Architecture title (e.g., 'Healthcare RAG with HIPAA Governance')",
                    },
                    "mermaid_code": {
                        "type": "string",
                        "description": (
                            "Mermaid diagram code. Use graph TD or graph LR. "
                            "Group components into subgraphs by layer. "
                            "Show data flow arrows between components. "
                            "Use simple alphanumeric labels — avoid &, <, > inside brackets."
                        ),
                    },
                    "cloud": {
                        "type": "string",
                        "description": (
                            "Primary cloud platform. Infer from customer context: "
                            "GCP/Google/Vertex AI → 'gcp', AWS/Bedrock → 'aws', Azure → 'azure'."
                        ),
                        "enum": ["azure", "gcp", "aws", "multi-cloud"],
                        "default": "azure",
                    },
                    "dashboard_data": {
                        "type": "string",
                        "description": (
                            "JSON string with structured dashboard data. Schema:\n"
                            '{"summary": {"name": "Architecture Name", "description": "1-line summary", '
                            '"total_cost": "$X,XXX/mo", "timeline": "X weeks", "component_count": N},\n'
                            '"components": [{"name": "Service Name", "layer": "API|Orchestration|Retrieval|Generation|Storage|Governance|Monitoring", '
                            '"service": "Cloud Service Name", "tier": "SKU/tier", "cost": "$X/mo", '
                            '"justification": "Why this over alternatives", "icon": "emoji"}],\n'
                            '"costs": [{"component": "Name", "monthly": 500, "notes": "Detail"}],\n'
                            '"risks": [{"risk": "Description", "severity": "high|medium|low", "mitigation": "How to mitigate"}],\n'
                            '"roadmap": [{"phase": "Phase 1", "timeline": "Week 1-2", "tasks": ["task1", "task2"]}],\n'
                            '"tradeoffs": [{"option": "Option A vs B", "chosen": "A", "reason": "Why"}],\n'
                            '"skills": [{"category": "GenAI Architecture and System Design", '
                            '"details": "Specific technical details demonstrating this competency"}]}'
                        ),
                    },
                },
                "required": ["title", "mermaid_code", "dashboard_data"],
            },
        )

    async def _search_patterns(self, query: str, top_k: int = 8) -> str:
        """Search architecture patterns via tools.api."""
        results = await tool_api.search_patterns(
            query=query, top_k=top_k, search_tool=self._search_tool,
        )
        return self._format_results(results)

    async def _load_scenario(self, scenario_id: str) -> str:
        """Load a pre-built customer scenario via tools.api."""
        result = await tool_api.load_scenario(scenario_id=scenario_id)
        return json.dumps(result)

    async def _estimate_cost(
        self,
        monthly_queries: int,
        document_count: int = 10000,
        model: str = "gpt-4.1-mini",
        search_tier: str = "standard",
        governance_level: str = "standard",
    ) -> str:
        """Estimate monthly costs via tools.api."""
        result = await tool_api.estimate_cost(
            monthly_queries=monthly_queries,
            document_count=document_count,
            model=model,
            search_tier=search_tier,
            governance_level=governance_level,
        )
        return json.dumps(result)

    def _format_results(self, results: list[dict[str, Any]]) -> str:
        """Format search results for the LLM context window."""
        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(
                f"[Pattern {i}]\n"
                f"Title: {r.get('title', 'Untitled')}\n"
                f"Source: {r.get('source', 'Unknown')}\n"
                f"Category: {r.get('category', 'Unknown')}\n"
                f"Relevance: {r.get('score', 0):.2f}\n"
                f"Content:\n{r.get('content', '')}\n"
            )
        return "\n---\n".join(formatted) if formatted else "No patterns found."

    async def _generate_diagram(
        self, title: str, mermaid_code: str, cloud: str = "azure", dashboard_data: str = "{}"
    ) -> str:
        """Generate an interactive architecture dashboard as HTML."""
        try:
            data = json.loads(dashboard_data) if dashboard_data else {}
        except json.JSONDecodeError:
            data = {}
        html_path = render_mermaid_html(title, mermaid_code, cloud, data)
        return json.dumps({
            "diagram_generated": True,
            "title": title,
            "cloud": cloud,
            "html_path": str(html_path),
            "message": f"Interactive architecture dashboard saved to {html_path}. Opening in browser.",
        })


def _sanitize_mermaid(code: str) -> str:
    """Fix common Mermaid syntax issues from LLM-generated code."""
    import re

    lines = []
    for line in code.splitlines():
        stripped = line.strip()
        # Skip empty lines, arrows, end, graph declarations
        if not stripped or stripped.startswith("end") or stripped.startswith("graph ") or stripped.startswith("flowchart ") or re.match(r'^[\w\s]+ *-->|--|-.->|==>|~~>', stripped):
            lines.append(line)
            continue
        # Quote labels inside [] that contain special chars: & ( ) < > #
        def quote_bracket(m):
            content = m.group(1)
            if content.startswith('"') and content.endswith('"'):
                return f'[{content}]'
            if any(c in content for c in '&()<>#'):
                # Escape inner quotes
                escaped = content.replace('"', "'")
                return f'["{escaped}"]'
            return f'[{content}]'
        line = re.sub(r'\[([^\]]+)\]', quote_bracket, line)

        # Quote labels inside () that contain special chars
        def quote_paren(m):
            prefix = m.group(1)  # node id or subgraph keyword
            content = m.group(2)
            if content.startswith('"') and content.endswith('"'):
                return f'{prefix}({content})'
            if any(c in content for c in '&<>#[]'):
                escaped = content.replace('"', "'")
                return f'{prefix}("{escaped}")'
            return f'{prefix}({content})'
        line = re.sub(r'(\w)\(([^)]+)\)', quote_paren, line)

        lines.append(line)
    return "\n".join(lines)



def render_mermaid_html(title: str, mermaid_code: str, cloud: str = "azure", data: dict | None = None) -> "Path":
    """Render interactive architecture dashboard as standalone HTML."""
    import html as html_mod
    import json

    data = data or {}
    cloud_colors = {
        "azure": {"bg": "#f0f6ff", "accent": "#0078d4", "accent2": "#005a9e", "card": "#e8f1fb", "label": "Microsoft Azure", "icon": "\u2601\ufe0f"},
        "gcp": {"bg": "#e8f5e9", "accent": "#1a73e8", "accent2": "#0d47a1", "card": "#e3f2fd", "label": "Google Cloud", "icon": "\U0001f537"},
        "aws": {"bg": "#fff8e1", "accent": "#ff9900", "accent2": "#e68a00", "card": "#fff3e0", "label": "Amazon Web Services", "icon": "\U0001f7e7"},
        "multi-cloud": {"bg": "#f3e5f5", "accent": "#7b1fa2", "accent2": "#6a1b9a", "card": "#f3e5f5", "label": "Multi-Cloud", "icon": "\U0001f310"},
    }
    colors = cloud_colors.get(cloud, cloud_colors["azure"])
    safe_title = html_mod.escape(title)
    mermaid_code = _sanitize_mermaid(mermaid_code)

    summary = data.get("summary", {})
    components = data.get("components", [])
    costs = data.get("costs", [])
    risks = data.get("risks", [])
    roadmap = data.get("roadmap", [])
    tradeoffs = data.get("tradeoffs", [])
    skills = data.get("skills", [])

    html_content = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{safe_title} \u2014 FDA Architecture Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
<style>
:root {{
  --accent: {colors['accent']};
  --accent2: {colors['accent2']};
  --bg: {colors['bg']};
  --card-bg: {colors['card']};
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Segoe UI',system-ui,-apple-system,sans-serif; background:var(--bg); color:#1a1a1a; }}

/* HEADER */
.hero {{
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  color: white; padding: 2rem 2rem 1rem;
}}
.hero-top {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:1.2rem; }}
.hero h1 {{ font-size:1.5rem; font-weight:700; }}
.hero .badge {{ background:rgba(255,255,255,0.18); padding:0.3rem 0.8rem; border-radius:6px; font-size:0.78rem; backdrop-filter:blur(4px); }}
.hero-desc {{ font-size:0.95rem; opacity:0.92; margin-bottom:1.2rem; max-width:800px; }}
.kpi-row {{ display:flex; gap:1rem; flex-wrap:wrap; padding-bottom:1.5rem; }}
.kpi {{
  background:rgba(255,255,255,0.15); backdrop-filter:blur(8px);
  border-radius:10px; padding:1rem 1.4rem; min-width:150px; flex:1;
  text-align:center; border:1px solid rgba(255,255,255,0.2);
}}
.kpi-value {{ font-size:1.6rem; font-weight:700; }}
.kpi-label {{ font-size:0.75rem; opacity:0.8; margin-top:0.2rem; text-transform:uppercase; letter-spacing:0.5px; }}

/* TABS */
.tab-bar {{
  display:flex; gap:0; background:white;
  border-bottom:2px solid color-mix(in srgb, var(--accent) 15%, transparent);
  padding:0 2rem; overflow-x:auto;
  position:sticky; top:0; z-index:100;
  box-shadow:0 1px 6px rgba(0,0,0,0.08);
}}
.tab {{
  padding:0.85rem 1.3rem; cursor:pointer; font-weight:500; font-size:0.85rem;
  color:#888; border-bottom:3px solid transparent;
  transition:all 0.2s; white-space:nowrap; user-select:none;
}}
.tab:hover {{ color:var(--accent); background:var(--bg); }}
.tab.active {{ color:var(--accent); border-bottom-color:var(--accent); font-weight:600; }}
.tab-icon {{ margin-right:0.3rem; }}

/* PANELS */
.container {{ max-width:1400px; margin:0 auto; padding:1.5rem 2rem 3rem; }}
.panel {{ display:none; animation:fadeIn 0.3s ease; }}
.panel.active {{ display:block; }}
@keyframes fadeIn {{ from{{opacity:0;transform:translateY(6px)}} to{{opacity:1;transform:translateY(0)}} }}

/* DIAGRAM */
.diagram-wrap {{ background:white; border-radius:12px; box-shadow:0 2px 16px rgba(0,0,0,0.06); overflow:hidden; }}
.diagram-toolbar {{
  display:flex; gap:0.5rem; padding:0.7rem 1.2rem;
  border-bottom:1px solid #eee; align-items:center; flex-wrap:wrap;
}}
.diagram-toolbar button {{
  padding:0.35rem 0.7rem; border:1px solid #ddd; border-radius:6px;
  background:white; cursor:pointer; font-size:0.82rem; transition:all 0.15s;
}}
.diagram-toolbar button:hover {{ background:var(--bg); border-color:var(--accent); color:var(--accent); }}
.zoom-level {{ color:#888; font-size:0.8rem; min-width:3rem; text-align:center; }}
.diagram-viewport {{
  overflow:auto; padding:2rem; cursor:grab; min-height:350px;
  background: repeating-linear-gradient(0deg,transparent,transparent 19px,#f8f8f8 19px,#f8f8f8 20px),
              repeating-linear-gradient(90deg,transparent,transparent 19px,#f8f8f8 19px,#f8f8f8 20px);
}}
.diagram-viewport:active {{ cursor:grabbing; }}
.diagram-inner {{ transform-origin:0 0; transition:transform 0.12s ease; display:inline-block; }}
.mermaid {{ display:flex; justify-content:center; }}
.mermaid svg {{ max-width:none; height:auto; }}

/* COMPONENT CARDS */
.comp-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:1rem; }}
.comp-card {{
  background:white; border-radius:10px; padding:1.2rem 1.4rem;
  box-shadow:0 1px 8px rgba(0,0,0,0.06);
  border-top:3px solid var(--accent);
  transition:transform 0.15s, box-shadow 0.15s;
}}
.comp-card:hover {{ transform:translateY(-2px); box-shadow:0 4px 20px rgba(0,0,0,0.1); }}
.comp-icon {{ font-size:1.8rem; margin-bottom:0.5rem; }}
.comp-name {{ font-weight:700; font-size:1rem; color:#111; }}
.comp-layer {{
  display:inline-block; font-size:0.7rem; padding:0.15rem 0.5rem;
  border-radius:10px; background:var(--card-bg); color:var(--accent);
  font-weight:600; margin:0.3rem 0 0.6rem; text-transform:uppercase; letter-spacing:0.3px;
}}
.comp-service {{ font-size:0.85rem; color:#555; margin-bottom:0.3rem; }}
.comp-cost {{ font-weight:600; color:var(--accent); font-size:0.95rem; }}
.comp-why {{
  font-size:0.82rem; color:#666; margin-top:0.6rem;
  padding-top:0.6rem; border-top:1px solid #eee; line-height:1.5;
}}

/* COST BAR CHART */
.cost-chart {{ max-width:700px; }}
.cost-bar-row {{ display:flex; align-items:center; margin-bottom:0.7rem; gap:0.8rem; }}
.cost-label {{ width:160px; font-size:0.85rem; font-weight:500; text-align:right; flex-shrink:0; }}
.cost-bar-track {{ flex:1; height:28px; background:#f0f0f0; border-radius:6px; overflow:hidden; position:relative; }}
.cost-bar-fill {{
  height:100%; border-radius:6px;
  background:linear-gradient(90deg, var(--accent), var(--accent2));
  transition:width 0.6s ease;
  display:flex; align-items:center; justify-content:flex-end; padding-right:8px;
  color:white; font-size:0.75rem; font-weight:600; min-width:40px;
}}
.cost-total {{
  text-align:right; font-size:1.3rem; font-weight:700; color:var(--accent);
  margin-top:1rem; padding-top:1rem; border-top:2px solid color-mix(in srgb, var(--accent) 15%, transparent);
}}

/* RISK MATRIX */
.risk-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:1rem; }}
.risk-card {{
  background:white; border-radius:10px; padding:1.2rem 1.4rem;
  box-shadow:0 1px 8px rgba(0,0,0,0.06); border-left:4px solid #ccc;
}}
.risk-card.high {{ border-left-color:#e53935; }}
.risk-card.medium {{ border-left-color:#fb8c00; }}
.risk-card.low {{ border-left-color:#43a047; }}
.risk-severity {{
  display:inline-block; font-size:0.7rem; padding:0.15rem 0.5rem;
  border-radius:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.3px;
}}
.risk-severity.high {{ background:#ffebee; color:#c62828; }}
.risk-severity.medium {{ background:#fff3e0; color:#e65100; }}
.risk-severity.low {{ background:#e8f5e9; color:#2e7d32; }}
.risk-title {{ font-weight:600; margin:0.5rem 0 0.4rem; font-size:0.95rem; }}
.risk-mitigation {{ font-size:0.82rem; color:#666; line-height:1.5; }}
.risk-mitigation strong {{ color:#333; }}

/* ROADMAP */
.timeline {{ position:relative; padding-left:2rem; }}
.timeline::before {{
  content:''; position:absolute; left:0.6rem; top:0; bottom:0;
  width:3px; background:linear-gradient(var(--accent), var(--accent2)); border-radius:2px;
}}
.tl-item {{ position:relative; margin-bottom:1.5rem; }}
.tl-dot {{
  position:absolute; left:-1.65rem; top:0.3rem;
  width:14px; height:14px; border-radius:50%;
  background:var(--accent); border:3px solid white;
  box-shadow:0 0 0 2px var(--accent);
}}
.tl-phase {{ font-weight:700; color:var(--accent); font-size:0.95rem; }}
.tl-time {{ font-size:0.78rem; color:#888; margin-bottom:0.3rem; }}
.tl-tasks {{ list-style:none; padding:0; }}
.tl-tasks li {{
  font-size:0.85rem; color:#444; padding:0.2rem 0; padding-left:1rem; position:relative;
}}
.tl-tasks li::before {{ content:'\u2192'; position:absolute; left:0; color:var(--accent); }}

/* TRADEOFFS */
.tradeoff-table {{ width:100%; border-collapse:collapse; font-size:0.9rem; }}
.tradeoff-table th {{
  background:var(--accent); color:white; padding:0.7rem 1rem;
  text-align:left; font-weight:600; font-size:0.82rem; text-transform:uppercase; letter-spacing:0.3px;
}}
.tradeoff-table td {{ padding:0.7rem 1rem; border-bottom:1px solid #eee; }}
.tradeoff-table tr:hover td {{ background:var(--bg); }}
.chosen-badge {{
  display:inline-block; background:var(--accent); color:white;
  padding:0.1rem 0.4rem; border-radius:4px; font-size:0.75rem; font-weight:600;
}}

/* SKILLS */
.skill-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(420px,1fr)); gap:1.2rem; }}
.skill-card {{
  background:white; border-radius:10px; padding:1.4rem 1.6rem;
  box-shadow:0 1px 8px rgba(0,0,0,0.06); border-top:3px solid var(--accent);
  transition:transform 0.15s, box-shadow 0.15s;
}}
.skill-card:hover {{ transform:translateY(-2px); box-shadow:0 4px 20px rgba(0,0,0,0.1); }}
.skill-category {{
  font-weight:700; color:var(--accent); font-size:1rem;
  margin-bottom:0.8rem; display:flex; align-items:center; gap:0.5rem;
  padding-bottom:0.5rem; border-bottom:1px solid #eee;
}}
.skill-details {{
  font-size:0.85rem; color:#333; line-height:1.75;
  white-space:pre-line;
}}

/* SECTION HEADERS */
.section-title {{
  font-size:1.15rem; font-weight:700; color:var(--accent);
  margin-bottom:1.2rem; padding-bottom:0.5rem;
  border-bottom:2px solid color-mix(in srgb, var(--accent) 15%, transparent);
  display:flex; align-items:center; gap:0.5rem;
}}
.section-title .st-icon {{ font-size:1.3rem; }}
.empty-msg {{ color:#999; font-style:italic; font-size:0.9rem; padding:2rem; text-align:center; }}

/* FOOTER */
.footer {{ text-align:center; padding:1.5rem; color:#aaa; font-size:0.72rem; border-top:1px solid #e0e0e0; }}

/* PRINT */
@media print {{
  .hero,.tab-bar,.diagram-toolbar {{ print-color-adjust:exact; -webkit-print-color-adjust:exact; }}
  .tab-bar {{ display:none; }}
  .panel {{ display:block !important; page-break-inside:avoid; margin-bottom:2rem; }}
  .comp-card,.risk-card,.skill-card {{ break-inside:avoid; }}
  body {{ background:white; }}
}}
</style>
</head>
<body>

<div class="hero">
  <div class="hero-top">
    <h1>{colors['icon']} {safe_title}</h1>
    <span class="badge">{colors['label']} \u00b7 FDA Architecture Toolkit</span>
  </div>
  <div class="hero-desc">{html_mod.escape(summary.get('description', ''))}</div>
  <div class="kpi-row">
    <div class="kpi"><div class="kpi-value">{html_mod.escape(str(summary.get('total_cost', '\u2014')))}</div><div class="kpi-label">Monthly Cost</div></div>
    <div class="kpi"><div class="kpi-value">{html_mod.escape(str(summary.get('component_count', len(components))))}</div><div class="kpi-label">Components</div></div>
    <div class="kpi"><div class="kpi-value">{html_mod.escape(str(summary.get('timeline', '\u2014')))}</div><div class="kpi-label">Timeline</div></div>
    <div class="kpi"><div class="kpi-value">{len(risks)}</div><div class="kpi-label">Risks Identified</div></div>
  </div>
</div>

<div class="tab-bar">
  <div class="tab active" data-tab="diagram"><span class="tab-icon">\U0001f4d0</span>Diagram</div>
  <div class="tab" data-tab="components"><span class="tab-icon">\U0001f9e9</span>Components</div>
  <div class="tab" data-tab="costs"><span class="tab-icon">\U0001f4b0</span>Costs</div>
  <div class="tab" data-tab="risks"><span class="tab-icon">\u26a0\ufe0f</span>Risks</div>
  <div class="tab" data-tab="roadmap"><span class="tab-icon">\U0001f5fa\ufe0f</span>Roadmap</div>
  <div class="tab" data-tab="tradeoffs"><span class="tab-icon">\u2696\ufe0f</span>Trade-offs</div>
  <div class="tab" data-tab="skills"><span class="tab-icon">\U0001f3af</span>Technical Deep Dive</div>
</div>

<div class="container">
  <div class="panel active" id="panel-diagram">
    <div class="diagram-wrap">
      <div class="diagram-toolbar">
        <button onclick="zoomIn()">\uff0b Zoom In</button>
        <button onclick="zoomOut()">\uff0d Zoom Out</button>
        <span class="zoom-level" id="zoom-level">100%</span>
        <button onclick="zoomReset()">\u21ba Reset</button>
        <button onclick="zoomFit()">\u2b1c Fit</button>
        <div style="flex:1"></div>
        <button onclick="window.print()">\U0001f5a8\ufe0f Print / PDF</button>
      </div>
      <div class="diagram-viewport" id="diagram-viewport">
        <div class="diagram-inner" id="diagram-inner">
          <pre class="mermaid">
{mermaid_code}
          </pre>
        </div>
      </div>
    </div>
  </div>

  <div class="panel" id="panel-components">
    <div class="section-title"><span class="st-icon">\U0001f9e9</span> Architecture Components</div>
    <div class="comp-grid" id="comp-grid"></div>
  </div>

  <div class="panel" id="panel-costs">
    <div class="section-title"><span class="st-icon">\U0001f4b0</span> Cost Breakdown</div>
    <div class="cost-chart" id="cost-chart"></div>
  </div>

  <div class="panel" id="panel-risks">
    <div class="section-title"><span class="st-icon">\u26a0\ufe0f</span> Risk Assessment</div>
    <div class="risk-grid" id="risk-grid"></div>
  </div>

  <div class="panel" id="panel-roadmap">
    <div class="section-title"><span class="st-icon">\U0001f5fa\ufe0f</span> Implementation Roadmap</div>
    <div class="timeline" id="timeline"></div>
  </div>

  <div class="panel" id="panel-tradeoffs">
    <div class="section-title"><span class="st-icon">\u2696\ufe0f</span> Trade-offs &amp; Alternatives</div>
    <div id="tradeoffs-content"></div>
  </div>

  <div class="panel" id="panel-skills">
    <div class="section-title"><span class="st-icon">\U0001f3af</span> Technical Deep Dive</div>
    <div class="skill-grid" id="skill-grid"></div>
  </div>
</div>

<div class="footer">Generated by FDA Architecture Toolkit \u00b7 Ctrl+P to save as PDF</div>

<script>
mermaid.initialize({{
  startOnLoad:true, theme:'base',
  themeVariables: {{
    primaryColor:'{colors["accent"]}22', primaryBorderColor:'{colors["accent"]}',
    primaryTextColor:'#1a1a1a', lineColor:'{colors["accent"]}',
    secondaryColor:'#f5f5f5', tertiaryColor:'#fff', fontSize:'14px',
  }},
  flowchart:{{ htmlLabels:true, curve:'basis', padding:20, nodeSpacing:30, rankSpacing:50 }},
}});

document.querySelectorAll('.tab').forEach(tab => {{
  tab.addEventListener('click', () => {{
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('panel-' + tab.dataset.tab).classList.add('active');
  }});
}});

let scale = 1;
const inner = document.getElementById('diagram-inner');
const viewport = document.getElementById('diagram-viewport');
function updateZoom() {{ inner.style.transform = `scale(${{scale}})`; document.getElementById('zoom-level').textContent = Math.round(scale*100)+'%'; }}
function zoomIn() {{ scale = Math.min(scale+0.15,3); updateZoom(); }}
function zoomOut() {{ scale = Math.max(scale-0.15,0.3); updateZoom(); }}
function zoomReset() {{ scale = 1; updateZoom(); }}
function zoomFit() {{
  const svg = inner.querySelector('svg');
  if(svg){{ const vw=viewport.clientWidth-40; const sw=svg.getBoundingClientRect().width/scale; scale=Math.min(vw/sw,1.5); updateZoom(); }}
}}
viewport.addEventListener('wheel', e => {{ e.preventDefault(); e.deltaY<0 ? zoomIn() : zoomOut(); }}, {{passive:false}});
let isPanning=false, startX, startY, scrollL, scrollT;
viewport.addEventListener('mousedown', e => {{ isPanning=true; startX=e.pageX-viewport.offsetLeft; startY=e.pageY-viewport.offsetTop; scrollL=viewport.scrollLeft; scrollT=viewport.scrollTop; }});
viewport.addEventListener('mouseleave', () => isPanning=false);
viewport.addEventListener('mouseup', () => isPanning=false);
viewport.addEventListener('mousemove', e => {{ if(!isPanning) return; e.preventDefault(); viewport.scrollLeft=scrollL-(e.pageX-viewport.offsetLeft-startX); viewport.scrollTop=scrollT-(e.pageY-viewport.offsetTop-startY); }});

const D = {json.dumps(data, ensure_ascii=False)};

const compGrid = document.getElementById('comp-grid');
if (D.components && D.components.length) {{
  D.components.forEach(c => {{
    compGrid.innerHTML += `
      <div class="comp-card">
        <div class="comp-icon">${{c.icon||'\U0001f527'}}</div>
        <div class="comp-name">${{c.name}}</div>
        <div class="comp-layer">${{c.layer||''}}</div>
        <div class="comp-service">${{c.service||''}} ${{c.tier ? '\u00b7 '+c.tier : ''}}</div>
        <div class="comp-cost">${{c.cost||''}}</div>
        <div class="comp-why">${{c.justification||''}}</div>
      </div>`;
  }});
}} else {{ compGrid.innerHTML = '<div class="empty-msg">No component data provided.</div>'; }}

const costChart = document.getElementById('cost-chart');
if (D.costs && D.costs.length) {{
  const maxCost = Math.max(...D.costs.map(c => c.monthly||0));
  let total = 0;
  D.costs.forEach(c => {{
    const pct = maxCost > 0 ? Math.round((c.monthly||0)/maxCost*100) : 0;
    total += (c.monthly||0);
    costChart.innerHTML += `
      <div class="cost-bar-row">
        <div class="cost-label">${{c.component}}</div>
        <div class="cost-bar-track">
          <div class="cost-bar-fill" style="width:${{Math.max(pct,8)}}%">${{c.monthly ? '$'+c.monthly.toLocaleString() : ''}}</div>
        </div>
      </div>`;
  }});
  costChart.innerHTML += `<div class="cost-total">Total: $${{total.toLocaleString()}}/month</div>`;
}} else {{ costChart.innerHTML = '<div class="empty-msg">No cost data provided.</div>'; }}

const riskGrid = document.getElementById('risk-grid');
if (D.risks && D.risks.length) {{
  D.risks.forEach(r => {{
    const sev = (r.severity||'medium').toLowerCase();
    riskGrid.innerHTML += `
      <div class="risk-card ${{sev}}">
        <span class="risk-severity ${{sev}}">${{sev}}</span>
        <div class="risk-title">${{r.risk}}</div>
        <div class="risk-mitigation"><strong>Mitigation:</strong> ${{r.mitigation||'N/A'}}</div>
      </div>`;
  }});
}} else {{ riskGrid.innerHTML = '<div class="empty-msg">No risk data provided.</div>'; }}

const timeline = document.getElementById('timeline');
if (D.roadmap && D.roadmap.length) {{
  D.roadmap.forEach(r => {{
    const tasks = (r.tasks||[]).map(t => `<li>${{t}}</li>`).join('');
    timeline.innerHTML += `
      <div class="tl-item">
        <div class="tl-dot"></div>
        <div class="tl-phase">${{r.phase}}</div>
        <div class="tl-time">${{r.timeline||''}}</div>
        <ul class="tl-tasks">${{tasks}}</ul>
      </div>`;
  }});
}} else {{ timeline.innerHTML = '<div class="empty-msg">No roadmap data provided.</div>'; }}

const tradeoffsEl = document.getElementById('tradeoffs-content');
if (D.tradeoffs && D.tradeoffs.length) {{
  let rows = D.tradeoffs.map(t => `<tr><td>${{t.option}}</td><td><span class="chosen-badge">${{t.chosen}}</span></td><td>${{t.reason}}</td></tr>`).join('');
  tradeoffsEl.innerHTML = `<table class="tradeoff-table"><thead><tr><th>Decision</th><th>Chosen</th><th>Rationale</th></tr></thead><tbody>${{rows}}</tbody></table>`;
}} else {{ tradeoffsEl.innerHTML = '<div class="empty-msg">No trade-off data provided.</div>'; }}

const skillGrid = document.getElementById('skill-grid');
if (D.skills && D.skills.length) {{
  D.skills.forEach((s, i) => {{
    const num = i + 1;
    // Convert newlines to <br> and **bold** to <strong>
    const formatted = (s.details || '').replace(/\\n/g, '<br>').replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>');
    skillGrid.innerHTML += `
      <div class="skill-card">
        <div class="skill-category"><span style="background:var(--accent);color:white;border-radius:50%;width:1.5rem;height:1.5rem;display:inline-flex;align-items:center;justify-content:center;font-size:0.75rem;font-weight:700;">${{num}}</span> ${{s.category}}</div>
        <div class="skill-details">${{formatted}}</div>
      </div>`;
  }});
}} else {{ skillGrid.innerHTML = '<div class="empty-msg">No technical analysis data provided.</div>'; }}
</script>
</body>
</html>"""

    output_dir = Path(__file__).resolve().parent.parent.parent / "output"
    output_dir.mkdir(exist_ok=True)

    safe_filename = "".join(c if c.isalnum() or c in "-_ " else "" for c in title)
    safe_filename = safe_filename.strip().replace(" ", "-")[:60]
    html_path = output_dir / f"{safe_filename}.html"
    html_path.write_text(html_content, encoding="utf-8")

    return html_path


# Financial Services Multi-Agent Architecture
# 金融服务多智能体架构

## Overview / 概述

This document defines a production-grade multi-agent architecture for a Tier-1 bank's regulatory compliance platform, handling 12,000+ regulatory documents (FINRA, SEC, OCC, FDIC) with full governance pipeline.

本文档定义了一级银行监管合规平台的生产级多智能体架构，处理 12,000+ 监管文件（FINRA、SEC、OCC、FDIC），并配备完整的治理管道。

---

## Agent Topology / 智能体拓扑

```
                        Compliance Officers / 合规人员
                        (Web UI / Teams Bot / API)
                                │
                                ▼
                ┌───────────────────────────────┐
                │     API Gateway (Azure APIM)  │
                │  VNet-isolated, WAF, mTLS     │
                └───────────────┬───────────────┘
                                │
                ┌───────────────▼───────────────┐
                │   INPUT GOVERNANCE PIPELINE   │
                │  Content Safety → PII Filter  │
                │  → Prompt Shield → Audit Log  │
                └───────────────┬───────────────┘
                                │
                ┌───────────────▼───────────────┐
                │      ORCHESTRATOR AGENT       │
                │   Intent Classification +     │
                │   Routing + Context Mgmt      │
                └──┬────────┬────────┬─────┬────┘
                   │        │        │     │
          ┌────────▼──┐ ┌───▼────┐ ┌─▼───┐ ┌▼──────────┐
          │ Regulatory│ │Analysis│ │Audit│ │ Alert     │
          │ Knowledge │ │ Agent  │ │Agent│ │ Agent     │
          │ Agent     │ │        │ │     │ │           │
          │ (RAG)     │ │比较分析│ │审计 │ │ 监管警报   │
          └─────┬─────┘ └───┬────┘ └──┬──┘ └─────┬─────┘
                │           │         │           │
                └───────────┴────┬────┴───────────┘
                                 │
                ┌────────────────▼──────────────┐
                │   OUTPUT GOVERNANCE PIPELINE  │
                │  Safety Check → PII Scrub →   │
                │  Citation Verify → Eval Sample│
                │  → Audit Log (FINRA 17a-4)    │
                └────────────────┬──────────────┘
                                 │
                                 ▼
                          Response + Citations
```

---

## Agent Definitions / 智能体定义

### 1. Orchestrator Agent / 编排智能体

| Property | Value |
|----------|-------|
| **Role** | Intent classification + routing to specialist agents |
| **Model** | GPT-4.1-mini |
| **Latency Budget** | 200-500ms |
| **Routing Strategy** | Hybrid (keyword rules first, LLM fallback) |

**Intent Categories / 意图分类:**

| Intent | Route To | Example Query |
|--------|----------|---------------|
| `regulatory_lookup` | Regulatory Knowledge Agent | "What does FINRA Rule 2111 say about suitability?" |
| `compare_analyze` | Analysis Agent | "Compare SEC and FINRA requirements for AML reporting" |
| `audit_query` | Audit Agent | "Show all compliance queries from last week" |
| `regulatory_alert` | Alert Agent | "What new SEC rules were published this month?" |
| `multi_step` | Sequential (Knowledge → Analysis) | "Summarize new GDPR changes and assess impact on our KYC process" |

**System Prompt:**
```
You are a financial compliance routing agent. Classify user intent and route 
to the appropriate specialist. For ambiguous queries, prefer regulatory_lookup 
(lowest risk). Never attempt to answer regulatory questions directly.
```

---

### 2. Regulatory Knowledge Agent / 监管知识智能体

| Property | Value |
|----------|-------|
| **Role** | RAG-based Q&A over regulatory documents with mandatory citations |
| **Model** | GPT-4.1-mini (retrieval), GPT-4.1 (complex multi-hop) |
| **Search** | Azure AI Search — Hybrid (BM25 + Vector + Semantic Rerank) |
| **Index** | 12,000 docs → ~60,000 chunks |
| **Citation** | Every answer MUST include `[source: doc_name, §section]` |

**Tools / 工具:**
| Tool | Purpose |
|------|---------|
| `hybrid_search` | BM25 + vector + semantic rerank over regulatory index |
| `exact_section_lookup` | Retrieve specific regulation section (e.g., §240.10b-5) |
| `cross_reference` | Find related regulations across agencies |
| `document_timeline` | Show amendment history for a regulation |

**Retrieval Configuration / 检索配置:**
```yaml
search_config:
  index: regulatory-knowledge
  query_type: hybrid          # BM25 + vector
  semantic_config: regulatory-semantic
  vector_fields: content_vector
  top_k: 10
  rerank_top: 5
  minimum_score: 0.75
  embedding_model: text-embedding-3-large
  chunk_size: 512
  chunk_overlap: 128
```

**Grounding Rules / 接地规则:**
- If retrieved score < 0.75 → respond "Insufficient confidence. Please consult legal."
- If query spans multiple agencies → retrieve from each, present comparison
- Never generate regulatory guidance not grounded in retrieved documents
- Append confidence score to every response

---

### 3. Analysis Agent / 分析智能体

| Property | Value |
|----------|-------|
| **Role** | Structured comparison, gap analysis, trend identification |
| **Model** | GPT-4.1 (complex reasoning required) |
| **Output** | Structured Markdown tables, risk matrices, recommendations |

**Capabilities / 能力:**
| Capability | Description |
|------------|-------------|
| **Regulatory Comparison** | Compare requirements across agencies (SEC vs FINRA vs OCC) |
| **Gap Analysis** | Identify gaps between current policies and regulatory requirements |
| **Impact Assessment** | Assess impact of new regulations on existing processes |
| **Trend Analysis** | Identify regulatory trends over time |

**Output Schema / 输出模板:**
```markdown
## Analysis: [Topic]
### Findings
| Dimension | Current State | Required State | Gap |
|-----------|--------------|----------------|-----|
### Risk Assessment
| Risk | Likelihood | Impact | Priority |
|------|-----------|--------|----------|
### Recommendations
1. [Action] — [Timeline] — [Owner]
### Sources
- [citation_1], [citation_2]
```

---

### 4. Audit Agent / 审计智能体

| Property | Value |
|----------|-------|
| **Role** | Query audit logs, compliance reporting, usage analytics |
| **Model** | GPT-4.1-mini |
| **Data Source** | Azure Log Analytics (7-year retention, FINRA 17a-4) |

**Tools / 工具:**
| Tool | Purpose |
|------|---------|
| `query_audit_log` | Search audit trail by user, date, topic, risk level |
| `compliance_report` | Generate periodic compliance summary |
| `usage_analytics` | Query patterns, peak times, department usage |
| `incident_search` | Find flagged/blocked queries and resolution status |

**Retention Policy / 保留策略:**
- All queries + responses: 7 years (FINRA 17a-4)
- PII-masked copies retained; originals purged after 90 days
- Quarterly compliance review of flagged interactions

---

### 5. Alert Agent / 警报智能体

| Property | Value |
|----------|-------|
| **Role** | Monitor regulatory feeds, notify on new/changed regulations |
| **Model** | GPT-4.1-mini |
| **Schedule** | Daily scan at 06:00 UTC |

**Capabilities / 能力:**
- Ingest new regulations from Federal Register, FINRA, SEC RSS feeds
- Classify relevance to bank's business lines
- Generate plain-language summaries of changes
- Push alerts via Teams / Email to affected compliance officers
- Auto-trigger re-indexing of updated documents

---

## Governance Pipeline / 治理管道

### Input Pipeline (Pre-Processing) / 输入管道

```
Step 1: Content Safety Screening
  ├─ Prompt injection detection (Azure Prompt Shields)
  ├─ Topic restriction (block non-compliance topics)
  └─ Jailbreak detection
  → BLOCK if threat detected, log incident

Step 2: PII Detection & Masking
  ├─ Azure AI Language PII (50+ entity types)
  ├─ Custom entities: account numbers, CUSIP, ISIN
  └─ Replace with [REDACTED_<TYPE>] tokens
  → WARN if PII detected, mask before LLM

Step 3: Authentication & Authorization
  ├─ Entra ID token validation
  ├─ RBAC: role → permitted agents/documents
  └─ Department-based document access control
  → BLOCK if unauthorized
```

### Output Pipeline (Post-Processing) / 输出管道

```
Step 4: Output Content Safety
  ├─ Verify no PII leakage in response
  ├─ Verify no harmful/misleading financial advice
  └─ Verify citations are present and valid
  → BLOCK if safety violation, escalate to human

Step 5: Evaluation Sampling (10%)
  ├─ Groundedness score (LLM-as-judge)
  ├─ Relevance score
  ├─ Citation accuracy
  └─ Compliance appropriateness
  → LOG metrics, alert if score < threshold

Step 6: Audit Logging
  ├─ Full request/response (PII-masked)
  ├─ Agent routing decision
  ├─ Governance pipeline results
  ├─ Latency breakdown
  └─ Immutable write to Log Analytics
  → 7-year retention (FINRA 17a-4)
```

---

## Security Architecture / 安全架构

```
┌─────────────────────────────────────────────────────┐
│  Azure VNet (10.0.0.0/16)                           │
│                                                     │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │ App Service   │  │ Azure AI     │                 │
│  │ (Private EP)  │  │ Search       │                 │
│  │               │  │ (Private EP) │                 │
│  └──────┬───────┘  └──────┬───────┘                 │
│         │                  │                         │
│  ┌──────▼──────────────────▼───────┐                 │
│  │  Private Subnet (10.0.1.0/24)   │                 │
│  └──────┬──────────────────┬───────┘                 │
│         │                  │                         │
│  ┌──────▼───────┐  ┌──────▼───────┐                 │
│  │ Azure OpenAI  │  │ Blob Storage │                 │
│  │ (Private EP)  │  │ (Private EP) │                 │
│  └──────────────┘  └──────────────┘                 │
│                                                     │
│  Auth: DefaultAzureCredential (Managed Identity)    │
│  No API keys. Zero-trust. mTLS between services.    │
└─────────────────────────────────────────────────────┘
```

---

## Cost Model / 成本模型

| Component | Monthly Cost | Notes |
|-----------|-------------|-------|
| Azure AI Search (S1) | $750 | 12K docs, ~60K chunks, hybrid index |
| GPT-4.1-mini (Knowledge + Orchestrator) | $600 | ~40K queries × 2K tokens |
| GPT-4.1 (Analysis, complex routing) | $400 | ~5K queries × 4K tokens |
| Azure Blob Storage | $50 | 12K regulatory documents |
| Content Safety | $100 | Input + output screening |
| PII Detection (AI Language) | $50 | 50K queries/month |
| Log Analytics (7yr retention) | $150 | FINRA 17a-4 compliance |
| App Service (B2) | $55 | VNet-integrated |
| Azure APIM (Developer) | $50 | API gateway + rate limiting |
| Evaluation (10% sampling) | $80 | LLM-as-judge |
| **Total** | **$2,285** | Under $5,000/month budget |

---

## Evaluation Framework / 评估框架

### Continuous Metrics / 持续指标

| Metric | Target | Method | Frequency |
|--------|--------|--------|-----------|
| Groundedness | > 95% | LLM-as-judge | 10% sample |
| Citation Accuracy | > 98% | Automated verification | Every response |
| Relevance | > 90% | LLM-as-judge | 10% sample |
| Safety | 0 incidents | Automated + human review | Every response |
| Routing Accuracy | > 92% | Human spot-check | Weekly |
| Latency (p95) | < 5s | APM monitoring | Continuous |
| Resolution Rate | > 80% | User feedback | Monthly |

### Weekly Compliance Review / 每周合规审查
- Review all BLOCKED/WARNED interactions
- Review 50 random responses for accuracy
- Update routing rules based on misclassifications
- Report to compliance committee

---

## Deployment Phases / 部署阶段

### Phase 1: Foundation (Week 1-4) / 基础阶段
- Deploy RAG pipeline (Knowledge Agent only)
- Set up governance pipeline (PII + Safety + Audit)
- Index initial 12K documents
- Internal beta with 10 compliance officers

### Phase 2: Multi-Agent (Week 5-8) / 多智能体阶段
- Add Orchestrator + Analysis Agent
- Implement routing logic
- Add Audit Agent
- Expand to 50 compliance officers

### Phase 3: Full Production (Week 9-12) / 全面投产阶段
- Add Alert Agent (regulatory feed monitoring)
- Enable evaluation pipeline
- Full rollout to all compliance officers
- Enable Teams Bot integration

### Phase 4: Optimization (Ongoing) / 持续优化阶段
- Fine-tune routing based on production data
- Add department-specific document access controls
- Multi-language support (English + Spanish)
- Quarterly architecture review

---

## Agent Interaction Examples / 智能体交互示例

### Example 1: Simple Regulatory Lookup / 简单监管查询
```
User: "What are the KYC requirements under FINRA Rule 2090?"

Orchestrator → Intent: regulatory_lookup → Route: Knowledge Agent
Knowledge Agent:
  1. hybrid_search("FINRA Rule 2090 KYC requirements")
  2. Retrieved 5 chunks (scores: 0.94, 0.91, 0.88, 0.85, 0.82)
  3. Generate grounded response with citations

Response:
  "Under FINRA Rule 2090 (Know Your Customer), member firms must:
   1. Use reasonable diligence to know essential facts about every customer
   2. Maintain accurate customer records...
   [Source: FINRA Rule 2090, §(a), indexed 2024-01-15]
   Confidence: 0.94"
```

### Example 2: Multi-Agent Analysis / 多智能体分析
```
User: "Compare SEC and FINRA AML reporting requirements 
       and identify gaps in our current policy."

Orchestrator → Intent: multi_step → Route: Knowledge → Analysis

Step 1 (Knowledge Agent):
  - Retrieve SEC AML requirements
  - Retrieve FINRA AML requirements
  - Retrieve internal AML policy

Step 2 (Analysis Agent):
  - Compare requirements across all three sources
  - Generate gap analysis table
  - Produce risk-prioritized recommendations

Response:
  "## AML Reporting Gap Analysis
   | Requirement | SEC | FINRA | Our Policy | Gap |
   |-------------|-----|-------|------------|-----|
   | SAR Filing  | 30d | 30d   | 45d        | ⚠️  |
   | CTR Amount  | $10K| $10K  | $10K       | ✅  |
   ...
   ### Recommendations
   1. Reduce SAR filing window from 45d to 30d — Priority: HIGH
   [Sources: SEC Rule 17a-8, FINRA Rule 3310, Internal Policy v2.3]"
```

### Example 3: Audit Trail Query / 审计追踪查询
```
User: "How many compliance queries were flagged for PII last month?"

Orchestrator → Intent: audit_query → Route: Audit Agent
Audit Agent:
  1. query_audit_log(filter="pii_detected", period="last_30d")
  2. Aggregate by department, severity, resolution

Response:
  "PII Detection Summary (March 2026):
   - Total flagged: 142 queries (2.8% of total)
   - Auto-masked and processed: 138
   - Blocked (high-risk PII): 4
   - Top department: Retail Banking (67%)
   - All incidents resolved within SLA"
```

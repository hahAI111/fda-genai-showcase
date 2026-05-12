# AI Governance Pipeline Pattern

## Pattern ID
`governance-pipeline`

## When to Use
- Regulated industries (finance, healthcare, government, legal)
- Enterprise customers with compliance requirements (SOC2, HIPAA, GDPR, FedRAMP)
- Any production AI system handling user data
- When "move fast and break things" is NOT acceptable

## When NOT to Use
- Internal dev tools with no user data
- Prototype/hackathon (add governance later)
- Batch offline processing with no PII

## Pipeline Architecture
```
User Input
  → [1] Content Safety (input screening)
  → [2] PII Detection & Masking
  → [3] Agent Execution (LLM + tools)
  → [4] Content Safety (output screening)
  → [5] Evaluation Sampling
  → [6] Audit Logging
  → Response
```

Each stage is a middleware that can BLOCK, WARN, or PASS.

## Component Comparison

### Content Safety
| Component | Azure | GCP | Open Source |
|-----------|-------|-----|-------------|
| Managed Service | Azure AI Content Safety | Vertex Responsible AI | — |
| Prompt Injection | Content Safety Shields | Model Armor | Rebuff, LLM Guard |
| Topic Restriction | Custom categories | Model Armor | Guardrails AI |
| Jailbreak Detection | Prompt Shields | Model Armor | — |
| **Latency** | ~100ms | ~100ms | ~50ms (local) |
| **Coverage** | High | Medium-High | Varies |

### PII Detection
| Component | Azure | GCP | Open Source |
|-----------|-------|-----|-------------|
| Managed Service | Azure AI Language PII | Cloud DLP | — |
| Entity Types | 50+ | 150+ | 30+ (Presidio) |
| Custom Entities | Yes | Yes | Yes |
| Redaction | Built-in | Built-in | Must implement |
| **Accuracy** | High | Very High | Medium-High |
| **Cost** | $1/1K records | $1-3/1K records | Free |

### Audit Logging
| Component | Azure | GCP | Open Source |
|-----------|-------|-----|-------------|
| Log Sink | Azure Monitor / Log Analytics | Cloud Logging | ELK, Loki |
| Retention | Configurable | Configurable | Self-managed |
| Compliance | SOC2, HIPAA, FedRAMP | SOC2, HIPAA, FedRAMP | Depends on deployment |
| Query | KQL | Log Explorer | Kibana / Grafana |

## Compliance Mapping

### What Each Regulation Requires
| Requirement | GDPR | HIPAA | SOC2 | FedRAMP |
|-------------|------|-------|------|---------|
| PII Detection | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| Right to Erasure | ✅ Required | ❌ N/A | ❌ N/A | ❌ N/A |
| Audit Trail | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| Data Minimization | ✅ Required | ✅ Required | ⚠️ Recommended | ✅ Required |
| Encryption at Rest | ⚠️ Recommended | ✅ Required | ✅ Required | ✅ Required |
| Encryption in Transit | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| Access Control | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| Incident Response | ✅ 72h notification | ✅ 60 days | ✅ Required | ✅ Required |

## Cost of Governance
| Layer | Latency Impact | Cost per Query | Notes |
|-------|---------------|----------------|-------|
| Content Safety (input) | +50-150ms | $0.001 | Can parallelize with PII |
| PII Detection | +50-100ms | $0.001 | Regex=free, managed=$0.001 |
| Content Safety (output) | +50-150ms | $0.001 | Only on generated text |
| Audit Logging | +5ms | ~$0 | Async append, negligible |
| Evaluation (10% sample) | +0ms (async) | $0.01 (per sampled query) | Run async, no latency impact |
| **Total** | **+150-400ms** | **$0.003-0.005/query** | |

## Decision Framework for Customers
1. **Start with audit logging** — cheapest, most valuable, required by everything
2. **Add PII detection** — if any user data touches the LLM
3. **Add content safety** — if external users interact with the system
4. **Add evaluation sampling** — before production launch (monitor quality)
5. **Add prompt injection defense** — if adversarial users are expected

## Common Pitfalls
1. **Governance as afterthought** — Build it into the pipeline from Day 1, not "add it later"
2. **Blocking too aggressively** — Over-strict content safety = frustrated users. Start with WARN, tune to BLOCK.
3. **PII in logs** — Audit logs must contain masked PII, never raw
4. **No governance bypass for internal tools** — Even internal users can accidentally paste PII
5. **Sync evaluation** — Run quality evaluation async/sampled; don't add 2s latency to every query

## Reference Implementation
This platform implements the full 6-stage pipeline in `src/main.py`:
- Content Safety: `src/governance/content_safety.py` (regex-based MVP, upgrade to Azure AI Content Safety for production)
- PII Filter: `src/governance/pii_filter.py` (regex patterns for email, SSN, credit card, phone)
- Audit: `src/governance/audit.py` (JSONL append-only log)
- Evaluation: `src/evaluation/pipeline.py` (10% probabilistic sampling)

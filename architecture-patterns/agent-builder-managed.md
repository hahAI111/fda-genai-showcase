# Managed Agent Builder Pattern (Build vs Buy Decision)

## Pattern ID
`agent-builder-managed`

## Overview
When a customer asks "should I build my own agent framework or use a managed service?", this is the decision framework.

## Managed Options Comparison

### Azure AI Agent Service
- **What it does**: Managed agent hosting with built-in tools (Code Interpreter, File Search, Bing, Azure AI Search, Azure Functions)
- **Pricing**: Pay per LLM call + tool execution
- **Best for**: Azure-native customers, quick PoCs
- **Limitations**: Limited custom governance hooks, no custom routing logic, vendor lock-in

### Vertex AI Agent Builder (Google Cloud)
- **What it does**: No-code/low-code agent builder with Gemini, grounding on Google Search / your data, built-in evaluation
- **Pricing**: Pay per query + data storage
- **Best for**: GCP-native customers, search-centric use cases, multimodal (vision + text)
- **Limitations**: Less flexible than custom code, limited multi-agent patterns

### Amazon Bedrock Agents
- **What it does**: Managed agent with action groups (Lambda), knowledge bases (OpenSearch), guardrails
- **Pricing**: Per-token + Lambda invocation
- **Best for**: AWS-native customers, serverless architectures
- **Limitations**: Limited model selection vs Azure/GCP, guardrails are basic

## Decision Matrix

### Choose Managed Agent Builder When:
| Factor | Score |
|--------|-------|
| Time to production < 2 weeks | +3 |
| Team has < 2 ML engineers | +3 |
| Single-purpose agent (just Q&A or just search) | +2 |
| PoC / demo for stakeholders | +3 |
| Standard governance (no custom PII rules) | +2 |
| Budget for managed service pricing | +1 |
| **Total ≥ 8 → Use Managed** | |

### Choose Custom Framework When:
| Factor | Score |
|--------|-------|
| Custom governance pipeline (regulated industry) | +3 |
| Multi-agent routing with specialized agents | +3 |
| Need full observability / tracing | +2 |
| Custom evaluation pipeline | +2 |
| Team has ≥ 3 ML/platform engineers | +1 |
| Multi-cloud or cloud-agnostic requirement | +3 |
| Complex tool integrations (internal APIs) | +2 |
| **Total ≥ 8 → Build Custom** | |

## Hybrid Approach (Often the Best Answer)
Use managed for the base, custom for the edges:
```
Managed Agent Builder (core LLM + grounding)
  + Custom PII filter (pre-processing middleware)
  + Custom evaluation (post-processing sampling)
  + Custom audit logging (compliance)
  + Custom tools (internal API connectors)
```

## Migration Path
1. **Week 1-2**: Start with Managed Agent Builder PoC
2. **Week 3-4**: Add custom governance layer around it
3. **Month 2-3**: Evaluate if managed meets requirements
4. **Month 3+**: If limitations hit → migrate to custom framework (use managed as baseline benchmark)

## Cost Comparison (50K queries/month, 100K docs)

### Managed
| Service | Azure Agent Service | Vertex AI Agent Builder | Bedrock Agents |
|---------|-------------------|----------------------|----------------|
| LLM | $1,500 | $800 (Flash) | $1,200 |
| Search/Grounding | $750 | $500 | $600 |
| Tools/Compute | $200 | $100 | $300 (Lambda) |
| Platform Fee | $0 | $0 | $0 |
| **Total** | **~$2,450** | **~$1,400** | **~$2,100** |

### Custom (This Platform)
| Component | Cost |
|-----------|------|
| LLM (GPT-4.1-mini) | $1,200 |
| Azure AI Search (Standard) | $750 |
| Blob Storage | $50 |
| Compute (App Service B2) | $55 |
| **Total** | **~$2,055** |

**Key insight**: Custom is comparable in cost but gives full control. Managed is faster to deploy but less flexible.

## What to Recommend to Customers
1. **If they ask "what should I use?"** → Start with managed, add custom governance
2. **If they have regulatory requirements** → Custom framework from Day 1
3. **If they want multi-agent** → Custom (managed doesn't support multi-agent well)
4. **If they want it yesterday** → Managed PoC in 2 days, evaluate, then decide

## Reference Implementation
This platform IS the custom framework option. To compare:
- Run this platform → see what custom gives you (multi-agent, governance, evaluation)
- Deploy Vertex AI Agent Builder → see what managed gives you (faster, simpler, less control)
- Present both to customer → let them decide based on their constraints

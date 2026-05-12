"""Tool API — Real implementations for all agent tools.

Every agent tool is a standalone async function here. This module is the
single source of truth for tool logic. Both agent handlers and the MCP
server call these same functions — no duplication.

Architecture:
    Agent handler  ──► tools.api.search_knowledge()  ◄── MCP server
                   ──► tools.api.check_policy()       ◄── MCP server
                   ──► tools.api.estimate_cost()       ◄── MCP server
                   ...

All functions accept plain Python args and return plain Python dicts/lists.
Serialization (JSON) is handled by the caller.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()


# ──────────────────────────────────────────────────────────────
# Knowledge tools
# ──────────────────────────────────────────────────────────────

async def search_knowledge(
    query: str,
    top_k: int = 5,
    use_vector: bool = True,
    filters: str | None = None,
    *,
    search_tool=None,
) -> list[dict[str, Any]]:
    """Hybrid search against Azure AI Search / Vertex AI Search.

    Returns a list of document dicts with title, content, source, score.
    """
    if search_tool:
        results = await search_tool.search(
            query=query, top_k=top_k, use_vector=use_vector, filters=filters,
        )
        logger.info("api.search_knowledge", query=query[:80], results=len(results))
        return results

    # Fallback — structured sample data for demo/testing
    logger.warning("api.search_knowledge.fallback", query=query[:80])
    return [
        {
            "title": "Enterprise AI Governance Policy v2.1",
            "content": (
                "All AI models must undergo evaluation before production deployment. "
                "Data classification must be completed for every dataset used in training "
                "or inference. PII processing requires explicit approval from the DPO."
            ),
            "source": "policies/ai-governance.pdf",
            "score": 0.95,
            "category": "policy",
        },
        {
            "title": "RAG Architecture Best Practices",
            "content": (
                "Hybrid search (BM25 + vector + semantic reranking) provides the best "
                "recall-precision tradeoff for enterprise knowledge retrieval. Chunk sizes "
                "of 512-1024 tokens with 20% overlap are recommended for general documents."
            ),
            "source": "technical/rag-best-practices.md",
            "score": 0.88,
            "category": "technical",
        },
    ]


# ──────────────────────────────────────────────────────────────
# Analyst tools
# ──────────────────────────────────────────────────────────────

async def search_for_analysis(
    query: str,
    top_k: int = 10,
    *,
    search_tool=None,
) -> dict[str, Any]:
    """Search knowledge base to gather data for analysis.

    Returns broader results (higher top_k) than knowledge search.
    """
    if search_tool:
        results = await search_tool.search(query=query, top_k=top_k, use_vector=True)
        return {"query": query, "results": results, "count": len(results)}

    logger.warning("api.search_for_analysis.fallback", query=query[:80])
    return {
        "query": query,
        "results": [],
        "count": 0,
        "sample_data": [
            {"metric": "Customer Satisfaction", "value": 4.2, "trend": "improving"},
            {"metric": "Response Time (p95)", "value": "2.3s", "trend": "stable"},
            {"metric": "Resolution Rate", "value": "87%", "trend": "improving"},
        ],
        "message": "AI Search not configured. Returning sample analysis data.",
    }


async def compare_documents(
    topics: list[str],
    criteria: list[str] | None = None,
    *,
    search_tool=None,
) -> dict[str, Any]:
    """Compare multiple topics by searching for each and structuring results."""
    comparison_data: dict[str, Any] = {}
    for topic in topics:
        if search_tool:
            results = await search_tool.search(query=topic, top_k=3)
            comparison_data[topic] = results
        else:
            comparison_data[topic] = [{"content": f"Sample data for {topic}"}]

    return {
        "comparison_data": comparison_data,
        "criteria": criteria or ["cost", "performance", "risk", "adoption"],
    }


# ──────────────────────────────────────────────────────────────
# Governance tools
# ──────────────────────────────────────────────────────────────

async def check_policy(
    query: str,
    regulation: str | None = None,
    *,
    search_tool=None,
) -> dict[str, Any]:
    """Search enterprise policies and governance documents.

    When search_tool is available, queries the real policy index.
    Otherwise returns structured policy data from local files.
    """
    if search_tool:
        filter_expr = (
            f"category eq 'policy'" if regulation is None
            else f"regulation eq '{regulation}'"
        )
        results = await search_tool.search(query=query, top_k=5, filters=filter_expr)
        return {"policies": results, "regulation": regulation, "source": "search_index"}

    # Load from local policy files if available
    policies_dir = Path(__file__).resolve().parent.parent.parent / "sample_data" / "policies"
    local_policies = _load_local_policies(policies_dir, query, regulation)
    if local_policies:
        return {"policies": local_policies, "regulation": regulation, "source": "local_files"}

    # Hardcoded fallback
    return {
        "policies": [
            {
                "name": "Enterprise AI Governance Policy v2.1",
                "section": "3.2 - Data Classification",
                "requirement": (
                    "All AI systems processing PII must implement data minimization "
                    "and purpose limitation."
                ),
                "status": "mandatory",
            },
            {
                "name": "Model Deployment Checklist",
                "section": "5.1 - Pre-Production Review",
                "requirement": (
                    "Models must pass bias testing, security review, and evaluation "
                    "benchmarks before production."
                ),
                "status": "mandatory",
            },
        ],
        "regulation": regulation,
        "source": "fallback",
    }


def _load_local_policies(
    policies_dir: Path, query: str, regulation: str | None,
) -> list[dict[str, Any]]:
    """Best-effort search through local Markdown policy files."""
    if not policies_dir.exists():
        return []

    results = []
    query_lower = query.lower()
    for md_file in policies_dir.glob("*.md"):
        content = md_file.read_text(encoding="utf-8", errors="ignore")
        # Simple keyword matching — good enough for local fallback
        if query_lower in content.lower() or (regulation and regulation.lower() in content.lower()):
            results.append({
                "name": md_file.stem.replace("-", " ").title(),
                "source": str(md_file.relative_to(policies_dir.parent.parent)),
                "content": content[:2000],
            })
    return results[:5]


async def assess_risk(
    use_case: str,
    data_types: list[str] | None = None,
    deployment_scope: str = "internal",
) -> dict[str, Any]:
    """Perform a risk assessment for an AI use case.

    Maps data types to risk levels and regulatory requirements.
    """
    risk_factors = []
    data_types = data_types or []

    # Data type → risk mapping
    data_risk_map = {
        "PII": {"severity": "HIGH", "regulation": "GDPR, CCPA",
                "controls": ["PII filtering", "Data minimization", "Consent management"]},
        "pii": {"severity": "HIGH", "regulation": "GDPR, CCPA",
                "controls": ["PII filtering", "Data minimization", "Consent management"]},
        "PHI": {"severity": "CRITICAL", "regulation": "HIPAA",
                "controls": ["Encryption at rest/transit", "Access logging", "BAA required"]},
        "health": {"severity": "CRITICAL", "regulation": "HIPAA",
                   "controls": ["Encryption at rest/transit", "Access logging", "BAA required"]},
        "financial": {"severity": "HIGH", "regulation": "SOX, PCI-DSS",
                      "controls": ["Audit trails", "Access controls", "Data encryption"]},
        "biometric": {"severity": "CRITICAL", "regulation": "GDPR Art.9, BIPA",
                      "controls": ["Explicit consent", "Purpose limitation", "Deletion policy"]},
    }

    for dt in data_types:
        mapping = data_risk_map.get(dt)
        if mapping:
            risk_factors.append({
                "factor": f"{dt} Processing",
                "severity": mapping["severity"],
                "regulation": mapping["regulation"],
                "required_controls": mapping["controls"],
            })

    if deployment_scope == "customer-facing":
        risk_factors.append({
            "factor": "Customer-Facing AI",
            "severity": "HIGH",
            "note": "Requires content safety, bias testing, and human escalation path",
            "required_controls": ["Content safety filter", "Bias evaluation", "Human-in-the-loop"],
        })

    severities = [r["severity"] for r in risk_factors]
    if "CRITICAL" in severities:
        overall = "CRITICAL"
    elif "HIGH" in severities:
        overall = "HIGH"
    elif risk_factors:
        overall = "MEDIUM"
    else:
        overall = "LOW"

    return {
        "use_case": use_case,
        "data_types": data_types,
        "deployment_scope": deployment_scope,
        "risk_factors": risk_factors,
        "overall_risk": overall,
        "recommendation": (
            "Proceed with enhanced governance controls — DPO approval required"
            if overall in ("HIGH", "CRITICAL")
            else "Standard deployment controls sufficient"
        ),
    }


# ──────────────────────────────────────────────────────────────
# Architect tools
# ──────────────────────────────────────────────────────────────

async def search_patterns(
    query: str,
    top_k: int = 8,
    *,
    search_tool=None,
) -> list[dict[str, Any]]:
    """Search architecture patterns knowledge base.

    Searches both the AI Search index (if available) and local
    architecture-patterns/ Markdown files.
    """
    results = []

    # 1. Try AI Search index
    if search_tool:
        try:
            indexed = await search_tool.search(query=query, top_k=top_k, use_vector=True)
            results.extend(indexed)
        except Exception as e:
            logger.warning("api.search_patterns.index_failed", error=str(e))

    # 2. Supplement with local architecture patterns
    patterns_dir = Path(__file__).resolve().parent.parent.parent / "architecture-patterns"
    local = _search_local_patterns(patterns_dir, query)
    results.extend(local)

    # Deduplicate by title
    seen_titles: set[str] = set()
    deduped = []
    for r in results:
        title = r.get("title", "")
        if title not in seen_titles:
            seen_titles.add(title)
            deduped.append(r)

    return deduped[:top_k]


def _search_local_patterns(patterns_dir: Path, query: str) -> list[dict[str, Any]]:
    """Search local architecture-patterns/ Markdown files by keyword."""
    if not patterns_dir.exists():
        return []

    results = []
    query_lower = query.lower()
    for md_file in patterns_dir.glob("*.md"):
        content = md_file.read_text(encoding="utf-8", errors="ignore")
        # Score by keyword density
        score = sum(1 for word in query_lower.split() if word in content.lower())
        if score > 0:
            # Extract first heading as title
            title = md_file.stem.replace("-", " ").title()
            for line in content.splitlines():
                if line.startswith("# "):
                    title = line.lstrip("# ").strip()
                    break
            results.append({
                "title": title,
                "content": content[:3000],
                "source": str(md_file.name),
                "score": min(score / len(query_lower.split()), 1.0),
                "category": "architecture-pattern",
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


async def load_scenario(scenario_id: str) -> dict[str, Any]:
    """Load a pre-built customer scenario from disk."""
    scenarios_dir = Path(__file__).resolve().parent.parent.parent / "scenarios"
    scenario_dir = scenarios_dir / scenario_id

    if not scenario_dir.exists():
        available = (
            [d.name for d in scenarios_dir.iterdir() if d.is_dir()]
            if scenarios_dir.exists() else []
        )
        return {"error": f"Scenario '{scenario_id}' not found", "available": available}

    result: dict[str, Any] = {"scenario_id": scenario_id}

    yaml_path = scenario_dir / "scenario.yaml"
    if yaml_path.exists():
        result["scenario"] = yaml_path.read_text(encoding="utf-8")

    arch_path = scenario_dir / "expected_arch.md"
    if arch_path.exists():
        result["expected_architecture"] = arch_path.read_text(encoding="utf-8")

    return result


async def estimate_cost(
    monthly_queries: int,
    document_count: int = 10000,
    model: str = "gpt-4.1-mini",
    search_tier: str = "standard",
    governance_level: str = "standard",
) -> dict[str, Any]:
    """Estimate monthly costs for a GenAI architecture."""
    model_pricing = {
        "gpt-4.1": {"input": 2.00, "output": 8.00},
        "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
        "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
        "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
        "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    }
    search_pricing = {"basic": 250, "standard": 750, "premium": 2500}
    governance_costs = {"minimal": 0, "standard": 0.003, "enterprise": 0.008}

    pricing = model_pricing.get(model, model_pricing["gpt-4.1-mini"])
    avg_input_tokens = 2000
    avg_output_tokens = 500

    llm_cost = (
        (monthly_queries * avg_input_tokens / 1_000_000) * pricing["input"]
        + (monthly_queries * avg_output_tokens / 1_000_000) * pricing["output"]
    )
    search_cost = search_pricing.get(search_tier, 750)
    governance_cost = monthly_queries * governance_costs.get(governance_level, 0.003)
    storage_cost = max(5, document_count * 0.005)
    compute_cost = 55  # App Service B2
    eval_cost = (monthly_queries * 0.1) * 0.016

    total = llm_cost + search_cost + governance_cost + storage_cost + compute_cost + eval_cost

    return {
        "estimate": {
            "model": model,
            "monthly_queries": monthly_queries,
            "document_count": document_count,
            "breakdown": {
                "llm_generation": round(llm_cost, 2),
                "search_service": search_cost,
                "governance": round(governance_cost, 2),
                "storage": round(storage_cost, 2),
                "compute": compute_cost,
                "evaluation": round(eval_cost, 2),
            },
            "total_monthly": round(total, 2),
            "per_query": round(total / max(monthly_queries, 1), 4),
        },
    }

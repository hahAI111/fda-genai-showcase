"""MCP Server — Model Context Protocol exposing ALL agent tools.

Every tool that agents can use is registered here as an MCP tool. This means:
1. VS Code / Claude / any MCP client can call the same tools agents use
2. Tool logic lives in tools/api.py — MCP server is a thin wrapper
3. New tools are automatically discoverable via MCP protocol
4. Access control is enforced at the transport layer

Architecture:
    MCP Client (VS Code, Claude, custom agent)
        ↓ MCP protocol (streamable-http or stdio)
    MCP Server (this file)
        ↓ function call
    tools.api (real implementations)
        ↓
    Azure AI Search / local files / computation
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from src.tools import api

# Lazy-initialized search tool (created on first use)
_search_tool = None


def _get_search_tool():
    """Lazy-init AISearchTool — avoids import-time credential errors."""
    global _search_tool
    if _search_tool is None:
        try:
            from src.tools.search import AISearchTool
            _search_tool = AISearchTool()
        except Exception:
            _search_tool = None
    return _search_tool


# Create MCP server instance
mcp = FastMCP(
    "enterprise-genai-content-studio",
    instructions=(
        "Enterprise GenAI Content Studio MCP Server. "
        "Provides tools for: image generation (gpt-image-2), video generation (sora-2), "
        "PowerPoint creation (GPT-4.1-mini + python-pptx), knowledge search (hybrid RAG), "
        "compliance checking, risk assessment, architecture pattern search, "
        "scenario loading, and cost estimation. "
        "All media tools pass through dual-layer guardrails (InputGuardrail + ModelOutputGuardrail)."
    ),
)


# ──────────────────────────────────────────────────────────────
# Knowledge tools
# ──────────────────────────────────────────────────────────────

@mcp.tool()
async def search_knowledge(
    query: str,
    top_k: int = 5,
    use_vector: bool = True,
    category: str | None = None,
) -> str:
    """Search the enterprise knowledge base using hybrid search (vector + keyword + semantic ranking).

    Args:
        query: Search query — be specific for best results
        top_k: Number of results to return (default: 5)
        use_vector: Whether to use vector search (default: true)
        category: Filter by document category (e.g., 'policy', 'technical')

    Returns:
        JSON array of documents with title, content, source, and relevance score
    """
    filters = f"category eq '{category}'" if category else None
    results = await api.search_knowledge(
        query=query, top_k=top_k, use_vector=use_vector,
        filters=filters, search_tool=_get_search_tool(),
    )
    return json.dumps(results, indent=2, default=str)


# ──────────────────────────────────────────────────────────────
# Analyst tools
# ──────────────────────────────────────────────────────────────

@mcp.tool()
async def search_for_analysis(
    query: str,
    top_k: int = 10,
) -> str:
    """Search the knowledge base to gather data for analysis (broader retrieval than knowledge search).

    Args:
        query: Search query to find relevant data for analysis
        top_k: Number of results (default: 10 for broader analysis)

    Returns:
        JSON object with query, results array, and count
    """
    result = await api.search_for_analysis(
        query=query, top_k=top_k, search_tool=_get_search_tool(),
    )
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def compare_documents(
    topics: list[str],
    criteria: list[str] | None = None,
) -> str:
    """Compare two or more topics by searching for each and producing a structured comparison.

    Args:
        topics: List of topics/items to compare
        criteria: Comparison criteria (e.g., cost, performance, risk)

    Returns:
        JSON object with comparison_data (per-topic results) and criteria
    """
    result = await api.compare_documents(
        topics=topics, criteria=criteria, search_tool=_get_search_tool(),
    )
    return json.dumps(result, indent=2, default=str)


# ──────────────────────────────────────────────────────────────
# Governance tools
# ──────────────────────────────────────────────────────────────

@mcp.tool()
async def check_policy(
    query: str,
    regulation: str | None = None,
) -> str:
    """Search enterprise policies and governance documents to check compliance requirements.

    Args:
        query: Policy or compliance topic to look up
        regulation: Specific regulation to check (e.g., GDPR, HIPAA, SOC2)

    Returns:
        JSON object with matching policies, their requirements, and status
    """
    result = await api.check_policy(
        query=query, regulation=regulation, search_tool=_get_search_tool(),
    )
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def assess_risk(
    use_case: str,
    data_types: list[str] | None = None,
    deployment_scope: str = "internal",
) -> str:
    """Perform a risk assessment for an AI use case or deployment scenario.

    Args:
        use_case: Description of the AI use case to assess
        data_types: Types of data involved (e.g., PII, financial, health, PHI, biometric)
        deployment_scope: internal, customer-facing, or both

    Returns:
        JSON risk assessment with risk_factors, overall_risk level, and recommendation
    """
    result = await api.assess_risk(
        use_case=use_case, data_types=data_types, deployment_scope=deployment_scope,
    )
    return json.dumps(result, indent=2, default=str)


# ──────────────────────────────────────────────────────────────
# Architect tools
# ──────────────────────────────────────────────────────────────

@mcp.tool()
async def search_patterns(
    query: str,
    top_k: int = 8,
) -> str:
    """Search architecture patterns knowledge base (RAG, multi-agent, governance, cost optimization, etc.).

    Args:
        query: Search query — e.g., 'RAG cost model', 'managed vs custom agent builder'
        top_k: Number of results (default: 8)

    Returns:
        JSON array of pattern documents with title, content, source, and relevance score
    """
    results = await api.search_patterns(
        query=query, top_k=top_k, search_tool=_get_search_tool(),
    )
    return json.dumps(results, indent=2, default=str)


@mcp.tool()
async def load_scenario(scenario_id: str) -> str:
    """Load a pre-built customer scenario with industry profile, requirements, constraints, and budget.

    Args:
        scenario_id: One of: financial-compliance, healthcare-knowledge, manufacturing-qa, retail-customer-service

    Returns:
        JSON object with scenario YAML and expected architecture
    """
    result = await api.load_scenario(scenario_id=scenario_id)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def estimate_cost(
    monthly_queries: int,
    document_count: int = 10000,
    model: str = "gpt-4.1-mini",
    search_tier: str = "standard",
    governance_level: str = "standard",
) -> str:
    """Estimate monthly costs for a GenAI architecture based on components and query volume.

    Args:
        monthly_queries: Expected monthly query volume
        document_count: Number of documents in the knowledge base
        model: LLM model (gpt-4.1-mini, gemini-2.5-flash, gpt-4.1, etc.)
        search_tier: Search service tier (basic, standard, premium)
        governance_level: Governance level (minimal, standard, enterprise)

    Returns:
        JSON cost breakdown with per-component costs and total
    """
    result = await api.estimate_cost(
        monthly_queries=monthly_queries,
        document_count=document_count,
        model=model,
        search_tier=search_tier,
        governance_level=governance_level,
    )
    return json.dumps(result, indent=2, default=str)


# ──────────────────────────────────────────────────────────────
# Platform status
# ──────────────────────────────────────────────────────────────

@mcp.tool()
async def get_platform_status() -> str:
    """Get the current status of the Enterprise GenAI Content Studio platform.

    Returns:
        Platform health status including agent availability, search index status,
        media tool status, and governance configuration
    """
    media_ready = False
    try:
        from src.config import get_settings
        s = get_settings()
        media_ready = bool(s.azure_openai_api_key and s.azure_ai_image_deployment)
    except Exception:
        pass

    return json.dumps({
        "platform": "enterprise-genai-content-studio",
        "version": "0.3.0",
        "agents": {
            "orchestrator": "active",
            "knowledge": "active",
            "analyst": "active",
            "governance": "active",
            "architect": "active",
            "media": "active",
        },
        "media_capabilities": {
            "image_generation": media_ready,
            "video_generation": media_ready,
            "ppt_generation": media_ready,
        },
        "search_index": "configured" if _get_search_tool() else "not_configured",
        "guardrails": {
            "layer_1_input": "enabled",
            "layer_2_model_output": "enabled",
            "pii_masking": "enabled",
            "prompt_injection_detection": "enabled",
        },
        "evaluation": {"enabled": True, "sample_rate": 0.1},
    }, indent=2)


# ──────────────────────────────────────────────────────────────
# Media tools (image / video / PPT) — all real Azure AI calls
# ──────────────────────────────────────────────────────────────

_media_agent = None
_cosmos_store = None


def _get_media_agent():
    """Lazy-init MediaAgent — avoids import-time credential errors."""
    global _media_agent
    if _media_agent is None:
        try:
            from src.agents.media_agent import MediaAgent
            _media_agent = MediaAgent()
        except Exception:
            _media_agent = None
    return _media_agent


def _get_cosmos_store():
    """Lazy-init CosmosStore for media/chat record access."""
    global _cosmos_store
    if _cosmos_store is None:
        try:
            from src.tools.cosmos_store import CosmosStore
            _cosmos_store = CosmosStore()
            _cosmos_store.initialize()
        except Exception:
            _cosmos_store = None
    return _cosmos_store


@mcp.tool()
async def generate_image(
    prompt: str,
    size: str = "1024x1024",
    style: str = "professional",
) -> str:
    """Generate a professional image using Azure OpenAI gpt-image-2.

    Passes through dual-layer guardrails (prompt injection detection + output screening).

    Args:
        prompt: Description of the image to generate (be specific and detailed)
        size: "1024x1024" (square), "1536x1024" (landscape), "1024x1536" (portrait)
        style: Visual style hint — "professional", "minimal", "vibrant"

    Returns:
        JSON with file_path (saved PNG), model, size, revised_prompt
    """
    agent = _get_media_agent()
    if not agent:
        return json.dumps({"error": "Media agent not available — check Azure credentials"})
    enriched = f"{prompt}. Style: {style}."
    response = await agent.create_media(request=enriched, media_type="image")
    return json.dumps(response.metadata.get("result", {}), indent=2, default=str)


@mcp.tool()
async def generate_ppt(
    topic: str,
    audience: str = "enterprise stakeholders",
    style: str = "professional",
) -> str:
    """Generate a complete PowerPoint presentation (.pptx) using GPT-4.1-mini + python-pptx.

    Content is LLM-generated (8-12 slides) and passes through dual-layer guardrails.

    Args:
        topic: Detailed topic or prompt for the presentation
        audience: Target audience — "enterprise stakeholders", "C-suite executives",
                  "engineering teams", "sales and customer-facing teams"
        style: Slide style — "professional" (blue), "minimal" (dark), "vibrant" (magenta)

    Returns:
        JSON with file_path (.pptx), title, slide_count
    """
    agent = _get_media_agent()
    if not agent:
        return json.dumps({"error": "Media agent not available — check Azure credentials"})
    response = await agent.create_media(
        request=f"Topic: {topic}. Audience: {audience}. Style: {style}.",
        media_type="ppt",
    )
    return json.dumps(response.metadata.get("result", {}), indent=2, default=str)


@mcp.tool()
async def start_video_job(
    prompt: str,
    seconds: str = "4",
    size: str = "1280x720",
) -> str:
    """Start an async video generation job using Azure AI Foundry sora-2.

    Returns immediately with a job_id. Poll get_video_status to check completion.
    Passes through dual-layer guardrails.

    Args:
        prompt: Detailed description of the video (include camera motion, style, lighting)
        seconds: Duration — "4", "8", or "12"
        size: Resolution — "1280x720" (HD) or "1920x1080" (Full HD)

    Returns:
        JSON with job_id, status ("queued"), model
    """
    agent = _get_media_agent()
    if not agent:
        return json.dumps({"error": "Media agent not available — check Azure credentials"})
    response = await agent.create_media(request=prompt, media_type="video")
    return json.dumps(response.metadata.get("result", {}), indent=2, default=str)


@mcp.tool()
async def get_video_status(job_id: str) -> str:
    """Poll the status of a previously started video generation job.

    Args:
        job_id: Job ID returned by start_video_job

    Returns:
        JSON with status ("queued"|"running"|"succeeded"|"failed"), and file_path when done
    """
    agent = _get_media_agent()
    if not agent:
        return json.dumps({"error": "Media agent not available"})
    try:
        status = agent.get_video_status(job_id)
        return json.dumps(status, indent=2, default=str)
    except KeyError:
        return json.dumps({"error": f"Unknown job_id: {job_id}"})


@mcp.tool()
async def db_health() -> str:
    """Get Cosmos DB health status used by the platform runtime."""
    store = _get_cosmos_store()
    if not store:
        return json.dumps({"provider": "cosmos", "status": "disabled"}, indent=2)
    return json.dumps({"provider": "cosmos", **store.health()}, indent=2)


@mcp.tool()
async def list_media_history(media_type: str | None = None, limit: int = 20) -> str:
    """List recently generated media records from Cosmos DB.

    Args:
        media_type: Optional filter: image|video|ppt
        limit: Max rows to return
    """
    store = _get_cosmos_store()
    if not store:
        return json.dumps({"error": "database not initialized"})
    rows = store.recent_media(media_type=media_type, limit=limit)
    return json.dumps({"count": len(rows), "items": rows}, indent=2, default=str)


def run_mcp_server():
    """Entry point for running the MCP server standalone."""
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    run_mcp_server()

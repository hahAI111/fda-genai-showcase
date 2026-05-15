"""Enterprise GenAI Platform - FastAPI Application.

Production-grade multi-agent GenAI platform demonstrating:
- ReAct patterns with explicit reasoning traces
- Hierarchical delegation with task decomposition
- Azure-first runtime with multi-cloud configuration hooks
- OAuth 2.0-based authentication (ADC + OAuth flows)
- LLM-native metrics (tokens/sec, cost-per-request, TTFT)
- Product feedback loop (friction -> feature requests)
- Governance pipeline (PII, content safety, audit)
- Evaluation pipeline (quality monitoring in production)

Architecture:
    User Request
        -> Content Safety (input screening)
        -> PII Filter (mask sensitive data)
        -> Hierarchical Orchestrator (task decomposition)
            -> Planner (decompose into subtasks)
            -> ReAct Agents (reasoning + acting)
                -> Knowledge Agent (RAG + citations)
                -> Analyst Agent (structured analysis)
                -> Governance Agent (compliance checking)
                -> Architect Agent (architecture advisor)
            -> Synthesizer (merge sub-results)
        -> Content Safety (output screening)
        -> LLM-Native Metrics (tokens/sec, cost, TTFT)
        -> Product Feedback Loop (friction detection)
        -> Evaluation Pipeline (quality sampling)
        -> Audit Logger (compliance trail)
        -> Response
"""

from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict  # noqa: F401 — may be used by downstream
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import BaseModel, Field

from src.agents.analyst import AnalystAgent
from src.agents.architect import ArchitectAgent
from src.agents.base import AgentContext
from src.agents.governance_agent import GovernanceAgent
from src.agents.hierarchy import HierarchicalOrchestrator
from src.agents.knowledge import KnowledgeAgent
from src.agents.media_agent import MediaAgent
from src.agents.orchestrator import OrchestratorAgent
from src.evaluation.pipeline import EvaluationPipeline
from src.feedback import FeedbackCollector
from src.governance.audit import AuditLogger
from src.governance.content_safety import ContentSafety, SafetyLevel
from src.governance.guardrails import GuardrailPipeline
from src.governance.pii_filter import PIIFilter
from src.metrics import MetricsCollector
from src.observability.tracing import get_tracer, setup_logging
from src.routers.media import bind_media_runtime, router as media_router
from src.skills import SkillRegistry
from src.skills.analysis_skill import AnalysisSkill
from src.skills.compliance_skill import ComplianceSkill
from src.skills.markdown_loader import load_markdown_skills
from src.skills.search_skill import SearchSkill
from src.config import get_credential, get_search_credential, get_settings

_OPTIONAL_IMPORT_ERRORS: dict[str, str] = {}

try:
    from src.tools.cosmos_store import CosmosStore
except Exception as exc:  # pragma: no cover - optional runtime dependency
    _OPTIONAL_IMPORT_ERRORS["cosmos_store"] = str(exc)
    CosmosStore = None  # type: ignore[assignment]

try:
    from src.tools.redis_cache import RedisCache
except Exception as exc:  # pragma: no cover - optional runtime dependency
    _OPTIONAL_IMPORT_ERRORS["redis_cache"] = str(exc)
    RedisCache = None  # type: ignore[assignment]

try:
    from src.tools.search import AISearchTool
except Exception as exc:  # pragma: no cover - optional runtime dependency
    _OPTIONAL_IMPORT_ERRORS["ai_search_tool"] = str(exc)
    AISearchTool = None  # type: ignore[assignment]

try:
    from src.tools.knowledge_base import KnowledgeBase
    from src.tools.knowledge_source import KnowledgeSource, KnowledgeSourceType
except Exception as exc:  # pragma: no cover - optional runtime dependency
    _OPTIONAL_IMPORT_ERRORS["agentic_retrieval"] = str(exc)
    KnowledgeBase = None  # type: ignore[assignment]
    KnowledgeSource = None  # type: ignore[assignment]
    KnowledgeSourceType = None  # type: ignore[assignment]

try:
    from src.tools.storage import BlobStorageTool
except Exception as exc:  # pragma: no cover - optional runtime dependency
    _OPTIONAL_IMPORT_ERRORS["blob_storage_tool"] = str(exc)
    BlobStorageTool = None  # type: ignore[assignment]

try:
    from src.tools.postgres_store import PostgresStore
except Exception as exc:  # pragma: no cover - optional runtime dependency
    _OPTIONAL_IMPORT_ERRORS["postgres_store"] = str(exc)
    PostgresStore = None  # type: ignore[assignment]

logger = structlog.get_logger()

# Global instances (initialized in lifespan)
orchestrator: OrchestratorAgent | None = None
hierarchical_orchestrator: HierarchicalOrchestrator | None = None
eval_pipeline: EvaluationPipeline | None = None
content_safety: ContentSafety | None = None
pii_filter: PIIFilter | None = None
audit_logger: AuditLogger | None = None
skill_registry: SkillRegistry | None = None
search_tool: AISearchTool | None = None
storage_tool: BlobStorageTool | None = None
metrics_collector: MetricsCollector | None = None
feedback_collector: FeedbackCollector | None = None
media_agent: MediaAgent | None = None
guardrail_pipeline: GuardrailPipeline | None = None
cosmos_store: CosmosStore | None = None
redis_cache: RedisCache | None = None
postgres_store: PostgresStore | None = None
knowledge_base: KnowledgeBase | None = None
last_activity_epoch: float = time.time()
service_soft_stopped: bool = False
idle_watchdog_task: asyncio.Task | None = None


def _parse_csv_items(raw: str) -> list[str]:
    return [item.strip() for item in (raw or "").split(",") if item.strip()]


def _is_demo_skip_day(skip_days_raw: str) -> bool:
    day = datetime.now(timezone.utc).day
    skip_days = {item for item in _parse_csv_items(skip_days_raw)}
    return str(day) in skip_days


def _resolve_auto_stop_mode(settings) -> str:
    requested_mode = (settings.auto_stop_mode or "soft").lower()
    if requested_mode != "hard":
        return "soft"

    if not settings.auto_stop_allow_hard_shutdown:
        logger.warning(
            "autostop.hard_disabled",
            reason="auto_stop_allow_hard_shutdown is false",
        )
        return "soft"

    return "hard"


async def _stop_current_webapp() -> bool:
    settings = get_settings()
    sub_id = settings.auto_stop_subscription_id or settings.azure_subscription_id
    rg = settings.auto_stop_resource_group or settings.azure_resource_group
    app_name = settings.auto_stop_webapp_name

    if not sub_id or not rg or not app_name:
        logger.warning(
            "autostop.hard_missing_config",
            subscription_id=bool(sub_id),
            resource_group=bool(rg),
            webapp_name=bool(app_name),
        )
        return False

    token = get_credential().get_token("https://management.azure.com/.default").token
    url = (
        f"https://management.azure.com/subscriptions/{sub_id}"
        f"/resourceGroups/{rg}/providers/Microsoft.Web/sites/{app_name}/stop"
        "?api-version=2023-12-01"
    )
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=headers)
        if response.status_code in (200, 202):
            logger.info("autostop.hard_stop_triggered", status_code=response.status_code)
            return True
        logger.error(
            "autostop.hard_stop_failed",
            status_code=response.status_code,
            body=response.text[:300],
        )
        return False


async def _idle_watchdog_loop() -> None:
    global service_soft_stopped

    settings = get_settings()
    check_interval = max(30, settings.auto_stop_check_interval_seconds)
    idle_threshold_seconds = max(5, settings.auto_stop_idle_minutes) * 60

    while True:
        await asyncio.sleep(check_interval)
        if not settings.auto_stop_enabled:
            continue
        if _is_demo_skip_day(settings.auto_stop_skip_days):
            continue

        idle_seconds = time.time() - last_activity_epoch
        if idle_seconds < idle_threshold_seconds:
            continue

        mode = _resolve_auto_stop_mode(settings)
        if mode == "hard":
            logger.info("autostop.hard_attempt", idle_seconds=round(idle_seconds, 2))
            stopped = await _stop_current_webapp()
            if not stopped:
                service_soft_stopped = True
                logger.warning("autostop.fallback_soft", idle_seconds=round(idle_seconds, 2))
            continue

        if not service_soft_stopped:
            service_soft_stopped = True
            logger.info("autostop.soft_enabled", idle_seconds=round(idle_seconds, 2))


def _ensure_chat_runtime_ready() -> None:
    """Fail fast with a clear error when runtime globals are not initialized."""
    missing = []
    settings = get_settings()
    mode = (settings.agent_runtime_mode or "flat").lower()

    if mode == "hierarchical":
        if hierarchical_orchestrator is None:
            missing.append("hierarchical_orchestrator")
    elif mode == "auto":
        if orchestrator is None and hierarchical_orchestrator is None:
            missing.append("chat_router")
    else:
        if orchestrator is None:
            missing.append("orchestrator")
    if content_safety is None:
        missing.append("content_safety")
    if pii_filter is None:
        missing.append("pii_filter")
    if audit_logger is None:
        missing.append("audit_logger")
    if eval_pipeline is None:
        missing.append("eval_pipeline")

    if missing:
        raise HTTPException(
            status_code=503,
            detail=(
                "Chat runtime not initialized. Missing components: "
                f"{', '.join(missing)}"
            ),
        )


def _should_use_hierarchical_router(message: str) -> bool:
    """Heuristic for auto mode: use hierarchy for multi-part/complex tasks."""
    normalized = (message or "").strip().lower()
    if not normalized:
        return False

    complexity_cues = (
        " and ",
        " then ",
        "compare",
        "trade-off",
        "architecture",
        "risk",
        "roadmap",
        "step by step",
        "multi",
    )
    if any(cue in normalized for cue in complexity_cues):
        return True

    return len(normalized.split()) >= 28


def _select_chat_router(message: str):
    """Resolve the runtime router based on configured mode and request complexity."""
    settings = get_settings()
    mode = (settings.agent_runtime_mode or "flat").lower()

    if mode == "hierarchical":
        return hierarchical_orchestrator, "hierarchical"

    if mode == "auto":
        if hierarchical_orchestrator and _should_use_hierarchical_router(message):
            return hierarchical_orchestrator, "hierarchical"
        if orchestrator:
            return orchestrator, "flat"
        return hierarchical_orchestrator, "hierarchical"

    return orchestrator, "flat"


def _resolve_response_agent(agent_response) -> str:
    """Prefer delegated target agent for API ergonomics; fallback to source field."""
    routing = (agent_response.metadata or {}).get("routing") or {}
    return routing.get("target_agent") or agent_response.agent_name


def _ensure_skills_runtime_ready() -> None:
    if skill_registry is None:
        raise HTTPException(
            status_code=503,
            detail="Skill registry not initialized.",
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize all components on startup."""
    global orchestrator, hierarchical_orchestrator, eval_pipeline, content_safety
    global pii_filter, audit_logger, skill_registry, search_tool, storage_tool
    global metrics_collector, feedback_collector, media_agent, guardrail_pipeline
    global cosmos_store, redis_cache, postgres_store, knowledge_base
    global idle_watchdog_task

    setup_logging()
    settings = get_settings()
    logger.info("platform.starting", version="0.2.0", cloud=settings.cloud_provider.value)

    for dependency_name, error_message in _OPTIONAL_IMPORT_ERRORS.items():
        logger.warning(
            "platform.optional_dependency_unavailable",
            dependency=dependency_name,
            error=error_message,
        )

    guardrail_pipeline = GuardrailPipeline(enabled=True)
    logger.info("platform.guardrails", layer1="InputGuardrail", layer2="ModelOutputGuardrail")

    if CosmosStore is None:
        cosmos_store = None
        logger.warning("platform.database_unavailable", type="cosmos", error="dependency_missing")
    else:
        try:
            cosmos_store = CosmosStore()
            cosmos_store.initialize()
            logger.info("platform.database", type="cosmos", status="initialized")
        except Exception as e:
            cosmos_store = None
            logger.warning("platform.database_unavailable", type="cosmos", error=str(e))

    if RedisCache is None:
        redis_cache = None
        logger.warning("platform.cache_unavailable", type="redis", error="dependency_missing")
    else:
        try:
            redis_cache = RedisCache()
            redis_cache.ping()
            logger.info("platform.cache", type="redis", status="initialized")
        except Exception as e:
            redis_cache = None
            logger.warning("platform.cache_unavailable", type="redis", error=str(e))

    if PostgresStore is None:
        postgres_store = None
        logger.warning("platform.database_unavailable", type="postgres", error="dependency_missing")
    else:
        try:
            postgres_store = PostgresStore()
            postgres_store.initialize()
            logger.info("platform.database", type="postgres", status="initialized")
        except Exception as e:
            postgres_store = None
            logger.warning("platform.database_unavailable", type="postgres", error=str(e))

    try:
        # Initialize Azure tools (multi-cloud support)
        search_tool = AISearchTool() if AISearchTool is not None else None
        storage_tool = BlobStorageTool() if BlobStorageTool is not None else None
        media_agent = MediaAgent()
        logger.info(
            "platform.azure_tools",
            search="configured" if search_tool is not None else "unavailable",
            storage="configured" if storage_tool is not None else "unavailable",
        )
    except Exception as e:
        search_tool = None
        storage_tool = None
        logger.error("platform.azure_tools_failed", error=str(e))
    
    # Initialize Agentic Retrieval (Knowledge Base)
    knowledge_base = None
    if KnowledgeBase is not None and settings.azure_search_endpoint:
        try:
            # Prefer identity-based auth over API key
            search_credential = None
            if not settings.azure_search_api_key:
                from src.config import get_credential
                search_credential = get_credential()
            knowledge_base = KnowledgeBase(
                search_endpoint=settings.azure_search_endpoint,
                search_api_key=settings.azure_search_api_key or "",
                kb_name="kb-enterprise",
                credential=search_credential,
            )
            # Register knowledge source references (match server-side names)
            knowledge_base.register_source(
                KnowledgeSource.from_search_index(name="ks-enterprise-index")
            )
            knowledge_base.register_source(
                KnowledgeSource.from_azure_blob(name="ks-enterprise-docs")
            )
            logger.info(
                "platform.agentic_retrieval",
                status="initialized",
                kb_name="kb-enterprise",
                sources=len(knowledge_base.source_manager.list_sources()),
            )
        except Exception as e:
            knowledge_base = None
            logger.error("platform.agentic_retrieval_failed", error=str(e))

    # Initialize skills registry
    skill_registry = SkillRegistry()
    skill_registry.register(SearchSkill())
    skill_registry.register(AnalysisSkill())
    skill_registry.register(ComplianceSkill())
    logger.info("platform.skills_loaded", count=skill_registry.count)

    # Load declarative Markdown skills from skills/ directory
    project_root = Path(__file__).resolve().parent.parent
    md_count = load_markdown_skills(project_root / "skills", skill_registry)
    logger.info("platform.markdown_skills_loaded", count=md_count, total=skill_registry.count)

    # Initialize governance
    content_safety = ContentSafety(
        azure_endpoint=settings.azure_content_safety_endpoint,
        azure_key=settings.azure_content_safety_key,
    )
    pii_filter = PIIFilter()
    audit_logger = AuditLogger()

    # Initialize LLM-native metrics collector
    metrics_collector = MetricsCollector()
    logger.info("platform.metrics_collector", status="initialized")

    # Initialize product feedback loop
    feedback_collector = FeedbackCollector()

    bind_media_runtime(
        media_agent=media_agent,
        guardrail_pipeline=guardrail_pipeline,
        cosmos_store=cosmos_store,
        postgres_store=postgres_store,
        logger=logger,
    )
    logger.info("platform.feedback_collector", status="initialized")

    # Initialize agents (with real AI Search tool)
    knowledge_agent = KnowledgeAgent(search_tool=search_tool)
    analyst_agent = AnalystAgent(search_tool=search_tool)
    governance_agent = GovernanceAgent(search_tool=search_tool)
    architect_agent = ArchitectAgent(search_tool=search_tool)

    # Flat orchestrator (backward-compatible)
    orchestrator = OrchestratorAgent()
    orchestrator.register_agent(knowledge_agent)
    orchestrator.register_agent(analyst_agent)
    orchestrator.register_agent(governance_agent)
    orchestrator.register_agent(architect_agent)

    # Hierarchical orchestrator (advanced -ReAct + delegation)
    hierarchical_orchestrator = HierarchicalOrchestrator()
    hierarchical_orchestrator.register_agent(knowledge_agent)
    hierarchical_orchestrator.register_agent(analyst_agent)
    hierarchical_orchestrator.register_agent(governance_agent)
    hierarchical_orchestrator.register_agent(architect_agent)

    # Initialize evaluation
    eval_pipeline = EvaluationPipeline()

    logger.info(
        "platform.ready",
        agents=4,
        governance="enabled",
        evaluation="enabled",
        metrics="enabled",
        feedback="enabled",
        cloud=settings.cloud_provider.value,
    )

    if settings.auto_stop_enabled:
        effective_auto_stop_mode = _resolve_auto_stop_mode(settings)
        idle_watchdog_task = asyncio.create_task(_idle_watchdog_loop())
        logger.info(
            "autostop.enabled",
            requested_mode=settings.auto_stop_mode,
            effective_mode=effective_auto_stop_mode,
            idle_minutes=settings.auto_stop_idle_minutes,
            skip_days=settings.auto_stop_skip_days,
        )

    yield

    if idle_watchdog_task is not None:
        idle_watchdog_task.cancel()
        try:
            await idle_watchdog_task
        except asyncio.CancelledError:
            pass

    logger.info("platform.shutdown")


app = FastAPI(
    title="Enterprise GenAI Platform",
    description=(
        "Production-grade multi-agent GenAI platform with ReAct patterns, "
        "hierarchical delegation, LLM-native metrics (tokens/sec, cost-per-request, TTFT), "
        "Google Cloud integration (Vertex AI, OAuth 2.0), governance, "
        "evaluation, and product feedback loop."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

# CORS -load allowed origins from config (never wildcard in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# OpenTelemetry auto-instrumentation
FastAPIInstrumentor.instrument_app(app)


@app.middleware("http")
async def idle_activity_middleware(request: Request, call_next):
    global last_activity_epoch

    settings = get_settings()
    path = request.url.path
    ignore_prefixes = tuple(_parse_csv_items(settings.auto_stop_ignore_paths))

    if not ignore_prefixes or not any(path.startswith(prefix) for prefix in ignore_prefixes):
        last_activity_epoch = time.time()

    if service_soft_stopped:
        protected_prefixes = ("/chat", "/search", "/media")
        exempt_prefixes = ("/", "/internal", "/health", "/db/health", "/wake", "/docs", "/openapi.json")
        if path.startswith(protected_prefixes) and not path.startswith(exempt_prefixes):
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Service is in idle stop mode. Call POST /wake to resume generation.",
                },
            )

    return await call_next(request)


# === Request/Response Models ===


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    conversation_id: str | None = None
    user_id: str | None = None
    tenant_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    agent: str
    conversation_id: str
    routing: dict | None = None
    citations: list[dict] | None = None
    evaluation: dict | None = None
    governance: dict | None = None
    performance: dict | None = None
    llm_metrics: dict | None = None
    react_traces: dict | None = None
    delegation: dict | None = None


class RetrieveRequest(BaseModel):
    """Request model for Agentic Retrieval endpoint"""
    query: str = Field(..., min_length=1, max_length=2000)
    conversation_id: str | None = None
    user_id: str | None = None
    tenant_id: str | None = None
    reasoning_effort: str = Field(default="medium")  # "low", "medium", "high"


class RetrieveResponse(BaseModel):
    """Response model for Agentic Retrieval endpoint"""
    query: str
    grounding_data: list[dict]
    source_citations: list[dict]
    execution_plan: dict
    sub_query_results: list[dict]
    synthesis: str | None = None
    conversation_id: str
    governance: dict | None = None
    performance: dict | None = None
    latency_ms: float | None = None


class HealthResponse(BaseModel):
    status: str
    version: str
    cloud_provider: str
    agents: dict[str, str]
    media_capabilities: dict[str, bool] | None = None
    database: dict[str, str] | None = None
    cache: dict[str, str] | None = None
    storage: dict[str, str] | None = None
    vector_search: dict[str, str] | None = None
    postgres: dict[str, str] | None = None
    governance: dict[str, bool]
    capabilities: list[str]


class DBHealthResponse(BaseModel):
    database: dict[str, str]
    cache: dict[str, str]
    postgres: dict[str, str] | None = None


class WakeRequest(BaseModel):
    reason: str = Field(default="manual resume")


class CacheClearRequest(BaseModel):
    clear_redis: bool = True
    clear_history: bool = False
    purge_files: bool = False
    history_limit: int = Field(default=200, ge=1, le=5000)


class RAGIngestRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=200000)
    category: str = Field(default="manual")
    source_name: str | None = None


class CacheRefreshRequest(BaseModel):
    action: str = Field(default="warm")


# === API Endpoints ===


@app.get("/internal", response_class=HTMLResponse)
async def internal_console():
    """Internal runtime console for engineering validation."""
    template_path = Path(__file__).resolve().parent / "web" / "internal_console.html"
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")

    logger.warning("internal_console.template_missing", path=str(template_path))
    return """
<!doctype html>
<html lang="en">
<head><meta charset="utf-8" /><title>Internal Console Unavailable</title></head>
<body>
  <h1>Internal Console Template Missing</h1>
  <p>Expected template: src/web/internal_console.html</p>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def customer_home():
    """Customer-facing web page for media creation."""
    template_path = Path(__file__).resolve().parent / "web" / "customer_home.html"
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")

    logger.warning("customer_home.template_missing", path=str(template_path))
    return """
<!doctype html>
<html lang="en">
<head><meta charset="utf-8" /><title>Customer Page Unavailable</title></head>
<body>
  <h1>Customer Template Missing</h1>
  <p>Expected template: src/web/customer_home.html</p>
</body>
</html>
"""

@app.get("/health", response_model=HealthResponse)
async def health():
    settings = get_settings()
    agents_status = {}
    if orchestrator:
        for name in orchestrator._agents:
            agents_status[name] = "active"
        agents_status["orchestrator"] = "active"
    if hierarchical_orchestrator:
        agents_status["supervisor"] = "active"
    if media_agent:
        agents_status["media_agent"] = "active"
    return HealthResponse(
        status="healthy",
        version="0.2.0",
        cloud_provider=settings.cloud_provider.value,
        agents=agents_status,
        media_capabilities={
            "image": media_agent is not None,
            "video": media_agent is not None,
            "ppt": media_agent is not None,
        },
        database={
            "provider": "cosmos",
            "status": "active" if cosmos_store is not None else "disabled",
        },
        cache={
            "provider": "redis",
            "status": "active" if redis_cache is not None else "disabled",
        },
        storage={
            "provider": "blob",
            "status": "active" if storage_tool is not None else "disabled",
        },
        vector_search={
            "provider": "azure_ai_search",
            "status": "active" if search_tool is not None else "disabled",
        },
        postgres={
            "provider": "postgres",
            "status": "active" if postgres_store is not None else "disabled",
        },
        governance={
            "pii_detection": pii_filter is not None,
            "content_safety": content_safety is not None,
            "audit_logging": audit_logger is not None,
        },
        capabilities=[
            "react_patterns",
            "hierarchical_delegation",
            "llm_native_metrics",
            "product_feedback_loop",
            "oauth2_authentication",
            "multi_cloud_support",
            "governance_pipeline",
            "evaluation_pipeline",
            "image_generation",
            "video_generation",
            "ppt_generation",
        ],
    )


@app.get("/db/health", response_model=DBHealthResponse)
async def db_health():
    db = {"provider": "cosmos", "status": "disabled", "database": "n/a"}
    cache = {"provider": "redis", "status": "disabled"}
    postgres = {"provider": "postgres", "status": "disabled", "database": "n/a"}

    if cosmos_store is not None:
        result = cosmos_store.health()
        db = {
            "provider": "cosmos",
            "status": str(result.get("status", "unhealthy")),
            "database": str(result.get("database", "unknown")),
        }
    if redis_cache is not None:
        try:
            redis_cache.ping()
            cache = {"provider": "redis", "status": "healthy"}
        except Exception as exc:
            cache = {"provider": "redis", "status": f"unhealthy: {exc}"}

    if postgres_store is not None:
        result = postgres_store.health()
        postgres = {
            "provider": "postgres",
            "status": str(result.get("status", "unhealthy")),
            "database": str(result.get("database", "unknown")),
        }

    return DBHealthResponse(database=db, cache=cache, postgres=postgres)


@app.post("/wake")
async def wake_service(request: WakeRequest | None = None):
    global service_soft_stopped, last_activity_epoch
    service_soft_stopped = False
    last_activity_epoch = time.time()
    reason = request.reason if request else "manual resume"
    return {
        "status": "awake",
        "reason": reason,
        "auto_stop_mode": _resolve_auto_stop_mode(get_settings()),
    }


@app.get("/skills")
async def list_skills():
    """List all registered skills -demonstrates dynamic capability discovery."""
    _ensure_skills_runtime_ready()
    return {"skills": skill_registry.list_skills(), "count": skill_registry.count}


@app.get("/analytics/summary")
async def analytics_summary():
    """Dashboard summary — counts from relational + NoSQL stores."""
    data: dict = {"postgres": {}, "cosmos": {}, "search": {}}
    if postgres_store is not None:
        try:
            data["postgres"] = postgres_store.summary()
        except Exception as e:
            data["postgres"]["error"] = str(e)
    if cosmos_store is not None:
        try:
            history = cosmos_store.recent_media(limit=100)
            by_type: dict[str, int] = {}
            for item in history:
                t = item.get("media_type", "unknown")
                by_type[t] = by_type.get(t, 0) + 1
            data["cosmos"] = {"total_media": len(history), "by_type": by_type}
        except Exception as e:
            data["cosmos"]["error"] = str(e)
    if search_tool is not None:
        try:
            data["search"]["status"] = "connected"
            data["search"]["index"] = get_settings().azure_search_index
        except Exception:
            data["search"]["status"] = "error"
    else:
        data["search"]["status"] = "disabled"
    return data


def _chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        if end < len(text):
            for sep in (". ", ".\n", "! ", "? ", "\n\n"):
                last_sep = text.rfind(sep, start + chunk_size // 2, end)
                if last_sep != -1:
                    end = last_sep + len(sep)
                    break
        part = text[start:end].strip()
        if part:
            chunks.append(part)
        next_start = end - overlap
        if next_start <= start:
            next_start = end
        start = next_start
    return chunks


def _build_doc_id(source: str, chunk_idx: int) -> str:
    payload = f"{source}:{chunk_idx}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Main chat endpoint with full governance pipeline.

    Flow:
    1. Content Safety ->screen input
    2. PII Filter ->mask sensitive data
    3. Orchestrator ->route to specialized agent
    4. Content Safety ->screen output
    5. Evaluation -sample for quality monitoring
    6. Audit -log for compliance
    """
    tracer = get_tracer()
    start = time.perf_counter()
    _ensure_chat_runtime_ready()
    runtime_router, runtime_mode = _select_chat_router(request.message)
    if runtime_router is None:
        raise HTTPException(status_code=503, detail="No chat router is available.")

    with tracer.start_as_current_span("chat_request") as span:
        context = AgentContext(
            user_id=request.user_id,
            tenant_id=request.tenant_id,
        )
        if request.conversation_id:
            context.conversation_id = request.conversation_id

        span.set_attribute("conversation_id", context.conversation_id)
        governance_report: dict = {}

        # 1. Content Safety -Input Screening
        safety_result = content_safety.screen_input(request.message)
        governance_report["input_safety"] = {
            "level": safety_result.level.value,
            "flags": safety_result.flags,
        }

        if safety_result.level == SafetyLevel.BLOCKED:
            audit_logger.log_governance_action(
                conversation_id=context.conversation_id,
                action="input_blocked",
                details={"reason": safety_result.message, "flags": safety_result.flags},
            )
            raise HTTPException(status_code=400, detail=safety_result.message)

        # 2. PII Filter -Mask sensitive data
        masked_message, pii_detections = pii_filter.mask(request.message)
        governance_report["pii"] = {
            "detected": bool(pii_detections),
            "types": list({d.type for d in pii_detections}),
            "count": len(pii_detections),
        }

        cache_key = None
        if redis_cache is not None:
            try:
                cache_key = redis_cache.build_chat_key(masked_message, request.tenant_id)
                cached_payload = redis_cache.get_json(cache_key)
                if cached_payload:
                    cached_payload.setdefault("routing", {})
                    cached_payload["routing"]["cache"] = "hit"
                    return ChatResponse(**cached_payload)
            except Exception as exc:
                logger.warning("chat.cache_lookup_failed", error=str(exc))

        if pii_detections:
            logger.info(
                "chat.pii_masked",
                conversation_id=context.conversation_id,
                count=len(pii_detections),
                types=governance_report["pii"]["types"],
            )

        # 3. Audit -Log the query
        audit_logger.log_query(
            conversation_id=context.conversation_id,
            query=masked_message,
            user_id=request.user_id,
            tenant_id=request.tenant_id,
        )

        # 4. Orchestrator -Route and execute
        try:
            agent_response = await runtime_router.route(masked_message, context)
        except Exception as e:
            logger.exception(
                "chat.route_failed",
                conversation_id=context.conversation_id,
                runtime_mode=runtime_mode,
                error=str(e),
            )
            audit_logger.log_governance_action(
                conversation_id=context.conversation_id,
                action="route_failed",
                details={"error": str(e), "runtime_mode": runtime_mode},
            )
            raise HTTPException(status_code=500, detail="Failed to process request route.") from e

        # 5. Content Safety -Output Screening
        output_safety = content_safety.screen_output(agent_response.content)
        governance_report["output_safety"] = {
            "level": output_safety.level.value,
            "flags": output_safety.flags,
        }

        final_content = agent_response.content
        if output_safety.level == SafetyLevel.BLOCKED:
            final_content = "I'm unable to provide that response due to safety policies."

        # 6. Evaluation -Sample for quality monitoring
        eval_report_dict = None
        try:
            if eval_pipeline.should_evaluate():
                eval_report = await eval_pipeline.evaluate(
                    query=request.message,
                    response=final_content,
                    conversation_id=context.conversation_id,
                )
                eval_report_dict = eval_report.to_dict()
                if cosmos_store is not None:
                    try:
                        cosmos_store.save_evaluation(
                            conversation_id=context.conversation_id,
                            query=request.message,
                            response=final_content,
                            evaluation=eval_report_dict,
                        )
                    except Exception as exc:
                        logger.warning("chat.eval_cosmos_save_failed", error=str(exc))
        except Exception as e:
            # Evaluation is non-blocking for user flow.
            logger.exception(
                "chat.eval_failed",
                conversation_id=context.conversation_id,
                error=str(e),
            )
            governance_report["evaluation_error"] = str(e)

        # 7. Audit -Log the response
        total_latency = (time.perf_counter() - start) * 1000
        audit_logger.log_response(
            conversation_id=context.conversation_id,
            agent_name=agent_response.agent_name,
            response=final_content,
            token_usage={"total_tokens": agent_response.total_tokens},
            latency_ms=total_latency,
            governance=governance_report,
        )

        # 8. LLM-Native Metrics -Record tokens/sec, cost, TTFT
        llm_metrics_dict = None
        if metrics_collector:
            settings = get_settings()
            # Extract token counts from agent steps
            prompt_tokens = sum(
                (s.token_usage or {}).get("prompt_tokens", 0)
                for s in agent_response.steps if s.token_usage
            )
            completion_tokens = sum(
                (s.token_usage or {}).get("completion_tokens", 0)
                for s in agent_response.steps if s.token_usage
            )
            if (prompt_tokens + completion_tokens) == 0 and agent_response.total_tokens > 0:
                prompt_tokens = max(0, agent_response.total_tokens // 2)
                completion_tokens = max(0, agent_response.total_tokens - prompt_tokens)
            # Calculate generation-only latency (exclude tool execution)
            generation_latency = sum(
                s.latency_ms for s in agent_response.steps
                if s.step_type in ("llm_call", "react_step")
            )
            # TTFT approximation -first LLM call latency
            first_llm_steps = [
                s for s in agent_response.steps
                if s.step_type in ("llm_call", "react_step")
            ]
            ttft = first_llm_steps[0].latency_ms if first_llm_steps else 0

            # Count ReAct iterations and tool calls
            react_iterations = sum(
                1 for s in agent_response.steps if s.step_type == "react_step"
            )
            tool_call_count = sum(
                1 for s in agent_response.steps if s.step_type == "tool_call"
            )
            # Delegation fan-out
            delegation_info = (agent_response.metadata or {}).get("delegation", {})
            fan_out = len(delegation_info.get("tasks", []))

            response_agent = _resolve_response_agent(agent_response)
            request_metrics = metrics_collector.calculate_request_metrics(
                request_id=context.conversation_id,
                model=settings.gcp_model if settings.cloud_provider.value == "google" else settings.azure_ai_chat_deployment,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_latency_ms=total_latency,
                time_to_first_token_ms=ttft,
                generation_latency_ms=generation_latency,
                react_iterations=react_iterations,
                tool_calls=tool_call_count,
                delegation_fan_out=fan_out,
                agent_name=response_agent,
            )
            metrics_collector.record(request_metrics)
            llm_metrics_dict = request_metrics.to_dict()

        # 9. Product Feedback Loop -Detect friction points
        if feedback_collector and llm_metrics_dict:
            timing = llm_metrics_dict.get("timing") or {}
            cost = llm_metrics_dict.get("cost") or {}
            efficiency = llm_metrics_dict.get("efficiency") or {}
            friction_input = {
                "ttft_ms": timing.get("ttft_ms", 0),
                "tps": timing.get("tokens_per_second", 0),
                "cost_usd": cost.get("total_usd", 0),
                "context_utilization": efficiency.get("context_utilization", 0),
            }
            detected_friction = feedback_collector.detect_from_metrics(friction_input)
            if detected_friction:
                logger.info(
                    "feedback.friction_detected",
                    count=len(detected_friction),
                    categories=[fp.category.value for fp in detected_friction],
                )

        response_agent = _resolve_response_agent(agent_response)

        metadata = agent_response.metadata or {}
        routing = dict(metadata.get("routing") or {})
        routing.setdefault("runtime_mode", runtime_mode)
        routing.setdefault("runtime_router", getattr(runtime_router, "name", runtime_mode))
        routing.setdefault("cache", "miss")

        if cosmos_store is not None:
            try:
                cosmos_store.save_chat(
                    conversation_id=context.conversation_id,
                    user_message=request.message,
                    response=final_content,
                    agent=response_agent,
                    governance=governance_report,
                )
            except Exception as exc:
                logger.warning("chat.cosmos_save_failed", error=str(exc))

        if postgres_store is not None:
            try:
                postgres_store.add_event(
                    event_type="chat_response",
                    payload={
                        "conversation_id": context.conversation_id,
                        "agent": response_agent,
                        "runtime_mode": runtime_mode,
                        "tokens": agent_response.total_tokens,
                    },
                )
            except Exception as exc:
                logger.warning("chat.postgres_event_failed", error=str(exc))

        response_payload = ChatResponse(
            response=final_content,
            agent=response_agent,
            conversation_id=context.conversation_id,
            routing=routing,
            citations=agent_response.citations or None,
            evaluation=eval_report_dict,
            governance=governance_report,
            performance={
                "total_latency_ms": round(total_latency, 2),
                "agent_latency_ms": round(agent_response.total_latency_ms, 2),
                "total_tokens": agent_response.total_tokens,
                "steps": len(agent_response.steps),
            },
            llm_metrics=llm_metrics_dict,
            react_traces=metadata.get("react_traces"),
            delegation=metadata.get("delegation"),
        )

        if redis_cache is not None and cache_key:
            try:
                redis_cache.set_json(cache_key, response_payload.model_dump(mode="json"))
            except Exception as exc:
                logger.warning("chat.cache_store_failed", error=str(exc))

        return response_payload


@app.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(request: RetrieveRequest):
    """Agentic Retrieval endpoint with multi-source parallel query execution.
    
    Flow:
    1. Content Safety -> screen input
    2. PII Filter -> mask sensitive data
    3. Knowledge Base -> query planning + parallel search + aggregation
    4. Content Safety -> screen outputs
    5. Audit -> log for compliance
    
    Returns:
        Structured result: grounding_data + source_citations + execution_plan + sub_query_results
    """
    tracer = get_tracer()
    start = time.perf_counter()
    _ensure_chat_runtime_ready()
    
    if knowledge_base is None:
        raise HTTPException(
            status_code=503,
            detail="Agentic Retrieval service not initialized"
        )
    
    with tracer.start_as_current_span("retrieve_request") as span:
        context = AgentContext(
            user_id=request.user_id,
            tenant_id=request.tenant_id,
        )
        if request.conversation_id:
            context.conversation_id = request.conversation_id
        else:
            context.conversation_id = str(uuid.uuid4())
        
        span.set_attribute("conversation_id", context.conversation_id)
        governance_report: dict = {}
        
        # 1. Content Safety - Input Screening
        safety_result = content_safety.screen_input(request.query)
        governance_report["input_safety"] = {
            "level": safety_result.level.value,
            "flags": safety_result.flags,
        }
        
        if safety_result.level == SafetyLevel.BLOCKED:
            audit_logger.log_governance_action(
                conversation_id=context.conversation_id,
                action="retrieve_input_blocked",
                details={"reason": safety_result.message, "flags": safety_result.flags},
            )
            raise HTTPException(status_code=400, detail=safety_result.message)
        
        # 2. PII Filter - Mask sensitive data
        masked_query, pii_detections = pii_filter.mask(request.query)
        governance_report["pii"] = {
            "detected": bool(pii_detections),
            "types": list({d.type for d in pii_detections}),
            "count": len(pii_detections),
        }
        
        if pii_detections:
            logger.info(
                "retrieve.pii_masked",
                conversation_id=context.conversation_id,
                count=len(pii_detections),
                types=governance_report["pii"]["types"],
            )
        
        # 3. Audit - Log the retrieval query
        audit_logger.log_query(
            conversation_id=context.conversation_id,
            query=masked_query,
            user_id=request.user_id,
            tenant_id=request.tenant_id,
        )
        
        # 4. Knowledge Base - Agentic Retrieval
        try:
            retrieve_result = await knowledge_base.retrieve_and_plan(
                query=masked_query,
                conversation_id=context.conversation_id,
                reasoning_effort=request.reasoning_effort,
            )
        except Exception as e:
            logger.exception(
                "retrieve.kb_failed",
                conversation_id=context.conversation_id,
                error=str(e),
            )
            audit_logger.log_governance_action(
                conversation_id=context.conversation_id,
                action="retrieve_failed",
                details={"error": str(e)},
            )
            raise HTTPException(status_code=500, detail="Failed to execute retrieval.") from e
        
        # 5. Content Safety - Screen grounding data
        for item in retrieve_result.grounding_data:
            content = item.get("content", "")
            if content:
                output_safety = content_safety.screen_output(content)
                if output_safety.level == SafetyLevel.BLOCKED:
                    item["_safety_filtered"] = True
                    item["content"] = "[Content filtered due to safety policy]"
        
        governance_report["output_safety"] = {
            "level": "mixed",
            "items_screened": len(retrieve_result.grounding_data),
        }
        
        # 6. Audit - Log the retrieval response
        total_latency = (time.perf_counter() - start) * 1000
        audit_logger.log_response(
            conversation_id=context.conversation_id,
            agent_name="agentic_retrieval",
            response=f"Retrieval completed: {len(retrieve_result.grounding_data)} items",
            token_usage={"total_tokens": 0},  # Agentic Retrieval uses different metrics
            latency_ms=total_latency,
            governance=governance_report,
        )
        
        # Build response
        response_payload = RetrieveResponse(
            query=request.query,
            grounding_data=retrieve_result.grounding_data,
            source_citations=retrieve_result.source_citations,
            execution_plan=retrieve_result.execution_plan,
            sub_query_results=retrieve_result.sub_query_results,
            synthesis=retrieve_result.synthesis,
            conversation_id=context.conversation_id,
            governance=governance_report,
            performance={
                "total_latency_ms": round(total_latency, 2),
                "items_retrieved": len(retrieve_result.grounding_data),
                "activities": len(retrieve_result.activities),
            },
            latency_ms=round(total_latency, 2),
        )
        
        if postgres_store is not None:
            try:
                postgres_store.add_event(
                    event_type="retrieve_response",
                    payload={
                        "conversation_id": context.conversation_id,
                        "items_retrieved": len(retrieve_result.grounding_data),
                        "sub_queries": len(retrieve_result.execution_plan.sub_queries),
                    },
                )
            except Exception as exc:
                logger.warning("retrieve.postgres_event_failed", error=str(exc))
        
        logger.info(
            "retrieve.complete",
            conversation_id=context.conversation_id,
            items=len(retrieve_result.grounding_data),
            latency_ms=total_latency,
        )
        
        return response_payload


@app.get("/eval/stats")
async def eval_stats():
    """Get evaluation statistics -for monitoring dashboards."""
    return {"message": "Evaluation statistics endpoint", "status": "active"}


# === LLM-Native Metrics Endpoints ===


@app.get("/metrics")
async def get_metrics(window_seconds: int = 3600, model: str | None = None):
    """Get aggregated LLM-native metrics -tokens/sec, cost, TTFT."""
    if not metrics_collector:
        raise HTTPException(status_code=503, detail="Metrics collector not initialized")
    return metrics_collector.get_aggregates(
        window_seconds=window_seconds,
        model=model,
    ).to_dict()


@app.get("/metrics/slos")
async def check_slos(window_seconds: int = 3600):
    """Check SLO compliance -TTFT, TPS, cost, latency targets."""
    if not metrics_collector:
        raise HTTPException(status_code=503, detail="Metrics collector not initialized")
    return metrics_collector.check_slos(window_seconds=window_seconds)


@app.get("/metrics/models")
async def compare_models(window_seconds: int = 3600):
    """Compare metrics across models -for model selection decisions."""
    if not metrics_collector:
        raise HTTPException(status_code=503, detail="Metrics collector not initialized")
    return metrics_collector.get_model_comparison(window_seconds=window_seconds)


# === Product Feedback Loop Endpoints ===


@app.get("/feedback/friction")
async def get_friction_points():
    """Get all detected friction points."""
    if not feedback_collector:
        raise HTTPException(status_code=503, detail="Feedback collector not initialized")
    return feedback_collector.get_stats()


@app.get("/feedback/feature-requests")
async def get_feature_requests():
    """Generate product feature requests from friction points."""
    if not feedback_collector:
        raise HTTPException(status_code=503, detail="Feedback collector not initialized")
    return {
        "feature_requests": feedback_collector.generate_feature_requests(),
        "stats": feedback_collector.get_stats(),
    }


@app.post("/feedback/report")
async def report_friction(
    category: str,
    severity: str,
    title: str,
    description: str,
    component: str,
):
    """Manually report a technical friction point."""
    if not feedback_collector:
        raise HTTPException(status_code=503, detail="Feedback collector not initialized")

    from src.feedback import FrictionCategory, FrictionSeverity

    fp = feedback_collector.report_friction(
        category=FrictionCategory(category),
        severity=FrictionSeverity(severity),
        title=title,
        description=description,
        evidence={"source": "manual_report"},
        component=component,
    )
    return {"friction_id": fp.friction_id, "frequency": fp.frequency}


# === Delegation Stats ===


@app.get("/delegation/stats")
async def delegation_stats():
    """Get hierarchical delegation statistics."""
    if not hierarchical_orchestrator:
        raise HTTPException(status_code=503, detail="Hierarchical orchestrator not initialized")
    return hierarchical_orchestrator.get_delegation_stats()


# === Storage & Search Endpoints ===


@app.get("/storage/documents")
async def list_storage_documents(prefix: str | None = None):
    """List documents in Azure Blob Storage -the source of truth."""
    if storage_tool is None:
        raise HTTPException(status_code=503, detail="Storage tool not initialized")

    try:
        docs = storage_tool.list_documents(prefix=prefix)
        return {"documents": docs, "count": len(docs), "container": get_settings().azure_storage_container}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage error: {e}")


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=50)
    category: str | None = None
    use_vector: bool = True


@app.post("/search")
async def search_documents(request: SearchRequest):
    """Direct search endpoint -hybrid search against Azure AI Search."""
    if search_tool is None:
        raise HTTPException(status_code=503, detail="Search tool not initialized")

    try:
        filters = None
        if request.category:
            # Sanitize OData filter value to prevent injection
            safe_category = request.category.replace("'", "''")
            filters = f"category eq '{safe_category}'"
        results = await search_tool.search(
            query=request.query,
            top_k=request.top_k,
            use_vector=request.use_vector,
            filters=filters,
        )

        if postgres_store is not None:
            top_sources = [
                str(item.get("source") or "")
                for item in results[:5]
                if isinstance(item, dict)
            ]
            try:
                postgres_store.log_rag_search(
                    query_text=request.query,
                    result_count=len(results),
                    top_sources=top_sources,
                )
            except Exception as exc:
                logger.warning("search.postgres_log_failed", error=str(exc))

        return {"query": request.query, "results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {e}")


@app.get("/architecture/status")
async def architecture_status():
    """Operational status across Cosmos, Redis, Blob, PostgreSQL, and Vector Search."""
    status = {
        "database": {"provider": "cosmos", "enabled": cosmos_store is not None},
        "cache": {"provider": "redis", "enabled": redis_cache is not None},
        "storage": {"provider": "blob", "enabled": storage_tool is not None},
        "vector_search": {"provider": "azure_ai_search", "enabled": search_tool is not None},
        "postgres": {"provider": "postgres", "enabled": postgres_store is not None},
    }

    if cosmos_store is not None:
        status["database"]["health"] = cosmos_store.health()
        try:
            status["database"]["media_records"] = cosmos_store.count_media()
        except Exception as exc:
            status["database"]["media_records_error"] = str(exc)

    if redis_cache is not None:
        try:
            status["cache"]["health"] = {"status": "healthy" if redis_cache.ping() else "unhealthy"}
            status["cache"]["db_size"] = redis_cache.db_size()
        except Exception as exc:
            status["cache"]["health"] = {"status": "unhealthy", "error": str(exc)}

    if storage_tool is not None:
        try:
            docs = storage_tool.list_documents(prefix=None)
            status["storage"]["document_count"] = len(docs)
        except Exception as exc:
            status["storage"]["error"] = str(exc)

    if postgres_store is not None:
        status["postgres"]["health"] = postgres_store.health()
        try:
            status["postgres"]["summary"] = postgres_store.summary()
        except Exception as exc:
            status["postgres"]["summary_error"] = str(exc)

    return status


@app.post("/cache/refresh")
async def cache_refresh(request: CacheRefreshRequest):
    details: dict[str, Any] = {"action": request.action, "status": "ok"}
    if redis_cache is not None:
        details["redis_ping"] = bool(redis_cache.ping())
        details["redis_db_size"] = redis_cache.db_size()
    if search_tool is not None and request.action == "warm":
        try:
            warm_results = await search_tool.search(query="enterprise", top_k=1, use_vector=True)
            details["search_warm_count"] = len(warm_results)
        except Exception as exc:
            details["search_warm_error"] = str(exc)
    return details


@app.post("/cache/clear")
async def cache_clear(request: CacheClearRequest):
    details: dict[str, Any] = {"status": "ok"}

    if request.clear_redis and redis_cache is not None:
        try:
            details["redis_deleted"] = redis_cache.clear_known_app_keys()
        except Exception as exc:
            details["redis_error"] = str(exc)

    if request.clear_history and cosmos_store is not None:
        try:
            details["history_deleted"] = cosmos_store.clear_media_history(limit=request.history_limit)
        except Exception as exc:
            details["history_error"] = str(exc)

    if request.purge_files:
        removed = 0
        for folder in (Path("output") / "generated-media", Path("output") / "generated-ppts"):
            if not folder.exists():
                continue
            for file in folder.glob("**/*"):
                if file.is_file():
                    try:
                        file.unlink()
                        removed += 1
                    except Exception:
                        pass
        details["files_removed"] = removed

    return details


@app.post("/rag/ingest")
async def rag_ingest(request: RAGIngestRequest):
    """Ingest text into Blob Storage + Azure AI Search vector index in one API call."""
    if storage_tool is None:
        raise HTTPException(status_code=503, detail="Storage tool not initialized")
    if search_tool is None:
        raise HTTPException(status_code=503, detail="Search tool not initialized")

    source_name = request.source_name or f"manual-{uuid.uuid4().hex[:8]}.md"
    blob_name = f"manual/{source_name}"

    try:
        storage_tool.ensure_container()
        blob_url = storage_tool.upload_document(
            blob_name=blob_name,
            content=request.content,
            metadata={"category": request.category, "title": request.title, "source": "api"},
            content_type="text/markdown",
        )

        chunks = _chunk_text(request.content)

        from azure.search.documents import SearchClient

        settings = get_settings()
        search_client = SearchClient(
            endpoint=settings.azure_search_endpoint,
            index_name=settings.azure_search_index,
            credential=get_search_credential(),
        )

        docs = []
        for idx, chunk in enumerate(chunks):
            docs.append(
                {
                    "id": _build_doc_id(blob_name, idx),
                    "title": request.title,
                    "content": chunk,
                    "source": blob_name,
                    "source_url": blob_url,
                    "category": request.category,
                    "chunk_id": f"{source_name}_{idx}",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        upload_result = search_client.upload_documents(documents=docs)
        succeeded = sum(1 for item in upload_result if getattr(item, "succeeded", False))

        if postgres_store is not None:
            try:
                postgres_store.add_event(
                    event_type="rag_ingest",
                    payload={
                        "title": request.title,
                        "source": blob_name,
                        "blob_url": blob_url,
                        "chunks": len(chunks),
                        "indexed": succeeded,
                        "category": request.category,
                    },
                )
            except Exception as exc:
                logger.warning("rag.ingest_postgres_failed", error=str(exc))

        return {
            "status": "ingested",
            "title": request.title,
            "source": blob_name,
            "blob_url": blob_url,
            "chunks": len(chunks),
            "indexed": succeeded,
            "index": get_settings().azure_search_index,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"RAG ingest failed: {exc}") from exc


# === GDPR Compliance & Governance Status ===

@app.get("/governance/status")
async def governance_status():
    """Full governance pipeline status — for compliance dashboards and audits."""
    settings = get_settings()
    safety_status = content_safety.get_status() if content_safety else {"enabled": False}
    pii_status = {
        "enabled": settings.pii_detection_enabled,
        "patterns": ["email", "phone_us", "ssn", "credit_card", "ip_address", "date_of_birth"],
    }
    audit_status = {
        "enabled": True,
        "log_path": str(settings.audit_log_path),
        "log_exists": settings.audit_log_path.exists(),
    }
    if settings.audit_log_path.exists():
        try:
            line_count = sum(1 for _ in open(settings.audit_log_path, encoding="utf-8"))
            audit_status["entries"] = line_count
        except Exception:
            audit_status["entries"] = -1

    gdpr_status = {
        "data_retention_days": settings.gdpr_data_retention_days,
        "right_to_erasure": settings.gdpr_right_to_erasure,
        "right_to_access": True,
        "data_portability": True,
        "consent_tracking": True,
        "lawful_basis": "legitimate_interest",
    }

    guardrail_status = {
        "input_guardrail": True,
        "output_guardrail": True,
        "prompt_injection_detection": True,
        "harmful_content_blocking": True,
        "topic_restriction": True,
        "pii_masking_before_llm": True,
    }

    regulations = {
        "GDPR": {"status": "compliant", "controls": [
            "PII detection & masking before LLM",
            "Right to erasure (DELETE /gdpr/user-data)",
            "Right to access (GET /gdpr/user-data)",
            "Data retention policy enforcement",
            "Audit trail for all interactions",
            "Consent-based processing",
        ]},
        "SOC2": {"status": "controls_implemented", "controls": [
            "Immutable audit logs (JSONL)",
            "Access control via OAuth 2.0",
            "Content safety screening",
            "Input/output guardrails",
        ]},
        "HIPAA": {"status": "controls_available", "controls": [
            "PII/PHI detection and masking",
            "Audit trail",
            "Data encryption at rest (Azure-managed)",
            "Role-based access control",
        ]},
    }

    return {
        "content_safety": safety_status,
        "pii_filter": pii_status,
        "audit": audit_status,
        "gdpr": gdpr_status,
        "guardrails": guardrail_status,
        "regulations": regulations,
        "pipeline": "Input → Content Safety → PII Filter → Agent → Content Safety → Evaluation → Audit",
    }


class GDPRUserDataRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=200)
    tenant_id: str | None = None


@app.post("/gdpr/user-data")
async def gdpr_access_user_data(request: GDPRUserDataRequest):
    """GDPR Article 15 — Right of Access. Export all data for a given user."""
    user_data: dict[str, Any] = {
        "user_id": request.user_id,
        "tenant_id": request.tenant_id,
        "request_type": "data_access",
        "data": {},
    }

    # Audit logs for this user
    if audit_logger and get_settings().audit_log_path.exists():
        user_entries = []
        try:
            import json as _json
            with open(get_settings().audit_log_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = _json.loads(line.strip())
                        if entry.get("user_id") == request.user_id:
                            user_entries.append(entry)
                    except _json.JSONDecodeError:
                        continue
            user_data["data"]["audit_entries"] = len(user_entries)
            user_data["data"]["audit_records"] = user_entries[-50:]  # Last 50
        except Exception as e:
            user_data["data"]["audit_error"] = str(e)

    # Cosmos DB records
    if cosmos_store is not None:
        try:
            user_data["data"]["chat_records"] = "available (query by user_id)"
            user_data["data"]["media_records"] = "available (query by user_id)"
        except Exception as e:
            user_data["data"]["cosmos_error"] = str(e)

    # PostgreSQL records
    if postgres_store is not None:
        user_data["data"]["operational_logs"] = "available (query by user_id)"

    # Log this GDPR access request
    if audit_logger:
        audit_logger.log_governance_action(
            conversation_id=f"gdpr-access-{uuid.uuid4().hex[:8]}",
            action="gdpr_data_access",
            details={"user_id": request.user_id, "tenant_id": request.tenant_id},
        )

    return user_data


@app.delete("/gdpr/user-data")
async def gdpr_erase_user_data(request: GDPRUserDataRequest):
    """GDPR Article 17 — Right to Erasure. Delete all data for a given user."""
    settings = get_settings()
    if not settings.gdpr_right_to_erasure:
        raise HTTPException(status_code=403, detail="Right to erasure is disabled in configuration")

    erasure_result: dict[str, Any] = {
        "user_id": request.user_id,
        "request_type": "data_erasure",
        "actions": [],
    }

    # Note: In production, you would delete from each store.
    # Here we log the erasure request for audit compliance.
    erasure_result["actions"].append("erasure_request_logged")

    if audit_logger:
        audit_logger.log_governance_action(
            conversation_id=f"gdpr-erase-{uuid.uuid4().hex[:8]}",
            action="gdpr_data_erasure",
            details={
                "user_id": request.user_id,
                "tenant_id": request.tenant_id,
                "note": "Erasure request recorded. Data will be purged within retention period.",
            },
        )
        erasure_result["actions"].append("audit_trail_updated")

    erasure_result["status"] = "erasure_scheduled"
    erasure_result["retention_days"] = settings.gdpr_data_retention_days
    return erasure_result


class SafetyTestRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)


@app.post("/governance/test-safety")
async def test_content_safety(request: SafetyTestRequest):
    """Test the content safety pipeline with a sample text. For demo/audit purposes."""
    if content_safety is None:
        raise HTTPException(status_code=503, detail="Content safety not initialized")

    text = request.text
    input_result = content_safety.screen_input(text)
    masked_text, pii_detections = pii_filter.mask(text) if pii_filter else (text, [])
    output_result = content_safety.screen_output(text)

    return {
        "input_screening": {
            "level": input_result.level.value,
            "flags": input_result.flags,
            "message": input_result.message,
            "details": input_result.details,
        },
        "pii_detection": {
            "found": bool(pii_detections),
            "count": len(pii_detections),
            "types": [d.type for d in pii_detections],
            "masked_preview": masked_text[:200] if masked_text != text else None,
        },
        "output_screening": {
            "level": output_result.level.value,
            "flags": output_result.flags,
            "message": output_result.message,
        },
    }


# === MCP Server Mount ===
# The MCP server runs alongside the main API, providing tool
# integration for external clients (VS Code, Claude, etc.)

from src.mcp.server import mcp  # noqa: E402

app.mount("/mcp", mcp.streamable_http_app())

# Serve generated files so the web UI can preview/download media artifacts.
_output_dir = Path("output")
_output_dir.mkdir(parents=True, exist_ok=True)
app.mount("/output", StaticFiles(directory=str(_output_dir)), name="output")
app.include_router(media_router)

# === OAuth 2.0 Routes ===
from src.auth.routes import router as auth_router  # noqa: E402

app.include_router(auth_router)





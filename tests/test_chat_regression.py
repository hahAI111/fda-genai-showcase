from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient

import src.main as main_module
from src.agents.base import AgentContext


@dataclass
class _StubAgentResponse:
    content: str
    agent_name: str = "orchestrator"
    metadata: dict = field(default_factory=dict)
    citations: list[dict] = field(default_factory=list)
    steps: list = field(default_factory=list)
    total_latency_ms: float = 0.0
    total_tokens: int = 0


class _StubOrchestrator:
    async def route(self, message: str, context: AgentContext) -> _StubAgentResponse:
        return _StubAgentResponse(
            content=f"ok: {message}",
            metadata={
                "routing": {
                    "intent": "knowledge_lookup",
                    "target_agent": "knowledge",
                    "refined_query": message,
                },
            },
        )


class _FailingOrchestrator:
    async def route(self, message: str, context: AgentContext) -> _StubAgentResponse:
        raise RuntimeError("routing backend unavailable")


@pytest.fixture(autouse=True)
def _restore_main_runtime_globals():
    snapshot = {
        "orchestrator": main_module.orchestrator,
        "content_safety": main_module.content_safety,
        "pii_filter": main_module.pii_filter,
        "audit_logger": main_module.audit_logger,
        "eval_pipeline": main_module.eval_pipeline,
        "metrics_collector": main_module.metrics_collector,
        "feedback_collector": main_module.feedback_collector,
    }
    yield
    main_module.orchestrator = snapshot["orchestrator"]
    main_module.content_safety = snapshot["content_safety"]
    main_module.pii_filter = snapshot["pii_filter"]
    main_module.audit_logger = snapshot["audit_logger"]
    main_module.eval_pipeline = snapshot["eval_pipeline"]
    main_module.metrics_collector = snapshot["metrics_collector"]
    main_module.feedback_collector = snapshot["feedback_collector"]


def _set_runtime(orchestrator) -> None:
    main_module.orchestrator = orchestrator
    main_module.content_safety = main_module.ContentSafety()
    main_module.pii_filter = main_module.PIIFilter()
    main_module.audit_logger = main_module.AuditLogger(log_path=main_module.Path("./logs/test-audit-regression.jsonl"))
    main_module.eval_pipeline = main_module.EvaluationPipeline(sample_rate=0.0)
    main_module.metrics_collector = main_module.MetricsCollector()
    main_module.feedback_collector = main_module.FeedbackCollector()


def test_chat_returns_503_when_runtime_not_initialized() -> None:
    main_module.orchestrator = None
    main_module.content_safety = None
    main_module.pii_filter = None
    main_module.audit_logger = None
    main_module.eval_pipeline = None

    client = TestClient(main_module.app)
    response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 503
    assert "not initialized" in response.json()["detail"].lower()


def test_chat_agent_field_uses_routed_target_agent() -> None:
    _set_runtime(_StubOrchestrator())

    client = TestClient(main_module.app)
    response = client.post("/chat", json={"message": "find policy"})

    assert response.status_code == 200
    body = response.json()
    assert body["agent"] == "knowledge"
    assert body["routing"]["target_agent"] == "knowledge"
    assert body["llm_metrics"] is not None


def test_chat_returns_500_when_route_fails() -> None:
    _set_runtime(_FailingOrchestrator())

    client = TestClient(main_module.app)
    response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to process request route."


class _TokenOnlyOrchestrator:
    async def route(self, message: str, context: AgentContext) -> _StubAgentResponse:
        return _StubAgentResponse(
            content=f"ok: {message}",
            metadata={
                "routing": {
                    "intent": "metrics_fallback",
                    "target_agent": "knowledge",
                    "refined_query": message,
                },
            },
            steps=[],
            total_tokens=200,
        )


def test_chat_llm_metrics_fallback_uses_total_tokens_when_steps_empty() -> None:
    _set_runtime(_TokenOnlyOrchestrator())

    client = TestClient(main_module.app)
    response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 200
    body = response.json()
    assert body["llm_metrics"] is not None
    assert body["llm_metrics"]["tokens"]["total"] == 200


def test_chat_uses_hierarchical_runtime_when_configured() -> None:
    original_mode = main_module.get_settings().agent_runtime_mode
    original_hierarchical = main_module.hierarchical_orchestrator
    try:
        main_module.get_settings().agent_runtime_mode = "hierarchical"
        main_module.orchestrator = None
        main_module.hierarchical_orchestrator = _StubOrchestrator()
        main_module.content_safety = main_module.ContentSafety()
        main_module.pii_filter = main_module.PIIFilter()
        main_module.audit_logger = main_module.AuditLogger(log_path=main_module.Path("./logs/test-audit-regression.jsonl"))
        main_module.eval_pipeline = main_module.EvaluationPipeline(sample_rate=0.0)
        main_module.metrics_collector = main_module.MetricsCollector()
        main_module.feedback_collector = main_module.FeedbackCollector()

        client = TestClient(main_module.app)
        response = client.post("/chat", json={"message": "find policy"})

        assert response.status_code == 200
        body = response.json()
        assert body["routing"]["runtime_mode"] == "hierarchical"
    finally:
        main_module.get_settings().agent_runtime_mode = original_mode
        main_module.hierarchical_orchestrator = original_hierarchical

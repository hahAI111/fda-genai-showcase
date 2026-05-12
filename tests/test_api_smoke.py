from dataclasses import dataclass, field

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
            content=f"echo: {message}",
            metadata={"routing": {"intent": "smoke", "target_agent": "knowledge", "refined_query": message}},
        )


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(main_module.app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_chat_smoke_with_stubbed_runtime() -> None:
    main_module.orchestrator = _StubOrchestrator()
    main_module.content_safety = main_module.ContentSafety()
    main_module.pii_filter = main_module.PIIFilter()
    main_module.audit_logger = main_module.AuditLogger(log_path=main_module.Path("./logs/test-audit.jsonl"))
    main_module.eval_pipeline = main_module.EvaluationPipeline(sample_rate=0.0)

    client = TestClient(main_module.app)
    response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 200
    body = response.json()
    assert body["response"].startswith("echo:")
    assert body["agent"] in ("orchestrator", "knowledge")

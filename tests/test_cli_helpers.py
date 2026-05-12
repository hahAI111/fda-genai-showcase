from src import cli


def test_resolve_scenario_id_accepts_full_id() -> None:
    assert cli._resolve_scenario_id("financial-compliance") == "financial-compliance"


def test_resolve_scenario_id_accepts_aliases() -> None:
    assert cli._resolve_scenario_id("finance") == "financial-compliance"
    assert cli._resolve_scenario_id("healthcare") == "healthcare-knowledge"
    assert cli._resolve_scenario_id("3") == "manufacturing-qa"


def test_resolve_scenario_id_returns_none_for_unknown_value() -> None:
    assert cli._resolve_scenario_id("unknown-scenario") is None


class _StubResponse:
    def __init__(self, agent_name: str, metadata: dict):
        self.agent_name = agent_name
        self.metadata = metadata


def test_resolve_response_agent_prefers_routed_target() -> None:
    response = _StubResponse("orchestrator", {"routing": {"target_agent": "architect"}})
    assert cli._resolve_response_agent(response) == "architect"


def test_resolve_response_agent_falls_back_to_source_agent() -> None:
    response = _StubResponse("knowledge", {})
    assert cli._resolve_response_agent(response) == "knowledge"

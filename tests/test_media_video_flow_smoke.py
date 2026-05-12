from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient

import src.main as main_module


@dataclass
class _StubMediaResponse:
    metadata: dict = field(default_factory=dict)


class _StubMediaAgent:
    async def create_media(self, request: str, media_type: str) -> _StubMediaResponse:
        assert media_type == "video"
        return _StubMediaResponse(
            metadata={
                "result": {
                    "job_id": "video_job_smoke_1",
                    "status": "queued",
                },
            }
        )

    def get_video_status(self, job_id: str) -> dict:
        if job_id != "video_job_smoke_1":
            raise KeyError(f"job not found: {job_id}")
        return {
            "job_id": job_id,
            "status": "completed",
            "video_url": "https://example.test/video_job_smoke_1.mp4",
        }


@pytest.fixture(autouse=True)
def _restore_runtime_globals():
    snapshot = {
        "media_agent": main_module.media_agent,
        "guardrail_pipeline": main_module.guardrail_pipeline,
        "cosmos_store": main_module.cosmos_store,
        "postgres_store": main_module.postgres_store,
    }
    yield
    main_module.media_agent = snapshot["media_agent"]
    main_module.guardrail_pipeline = snapshot["guardrail_pipeline"]
    main_module.cosmos_store = snapshot["cosmos_store"]
    main_module.postgres_store = snapshot["postgres_store"]



def test_video_create_then_status_smoke() -> None:
    main_module.media_agent = _StubMediaAgent()
    main_module.guardrail_pipeline = None
    main_module.cosmos_store = None
    main_module.postgres_store = None

    client = TestClient(main_module.app)

    create_response = client.post(
        "/media/video",
        json={
            "prompt": "Generate a short enterprise rollout teaser video",
            "seconds": "4",
            "size": "1280x720",
        },
    )

    assert create_response.status_code == 200
    create_body = create_response.json()
    assert create_body["job_id"] == "video_job_smoke_1"
    assert create_body["status"] == "queued"
    assert "record_id" in create_body

    status_response = client.get("/media/video/video_job_smoke_1")

    assert status_response.status_code == 200
    status_body = status_response.json()
    assert status_body["job_id"] == "video_job_smoke_1"
    assert status_body["status"] == "completed"
    assert status_body["video_url"].endswith(".mp4")

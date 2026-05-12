from fastapi.testclient import TestClient

import src.main as main_module


def test_skills_returns_503_when_registry_not_initialized() -> None:
    original = main_module.skill_registry
    main_module.skill_registry = None
    try:
        client = TestClient(main_module.app)
        response = client.get("/skills")
        assert response.status_code == 503
        assert response.json()["detail"] == "Skill registry not initialized."
    finally:
        main_module.skill_registry = original

from fastapi.testclient import TestClient

import src.main as main_module



def test_customer_home_contains_primary_video_controls() -> None:
    client = TestClient(main_module.app)
    response = client.get("/")

    assert response.status_code == 200
    html = response.text
    assert 'id="createVideoBtn"' in html
    assert 'id="downloadAllBtn"' in html



def test_internal_console_contains_core_debug_controls() -> None:
    client = TestClient(main_module.app)
    response = client.get("/internal")

    assert response.status_code == 200
    html = response.text
    assert 'id="chatBtn"' in html
    assert 'id="searchBtn"' in html
    assert 'id="imageBtn"' in html
    assert 'id="videoBtn"' in html
    assert 'id="pptBtn"' in html



def test_customer_home_no_duplicate_primary_ids() -> None:
    client = TestClient(main_module.app)
    response = client.get("/")
    html = response.text

    assert html.count('id="createVideoBtn"') == 1
    assert html.count('id="downloadAllBtn"') == 1

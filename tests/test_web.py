from fastapi.testclient import TestClient

from apt_analyzer.web import create_app


def test_root_route_returns_local_web_placeholder() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "apt-analyzer local web" in response.text


def test_health_route_reports_ready() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

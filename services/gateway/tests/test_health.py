from fastapi.testclient import TestClient

from services.gateway.app.main import app


def test_health():
    response = TestClient(app).get("/health")
    assert response.status_code == 200 and response.json()["service"] == "gateway"

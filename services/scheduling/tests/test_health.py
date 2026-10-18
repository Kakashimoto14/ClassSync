from fastapi.testclient import TestClient

from services.scheduling.app.main import app


def test_health():
    assert TestClient(app).get("/health").json()["service"] == "scheduling"

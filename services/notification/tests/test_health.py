from fastapi.testclient import TestClient

from services.notification.app.main import app


def test_health():
    assert TestClient(app).get("/health").json()["service"] == "notification"

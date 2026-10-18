from fastapi.testclient import TestClient

from services.academic.app.main import app


def test_health():
    assert TestClient(app).get("/health").json()["service"] == "academic"

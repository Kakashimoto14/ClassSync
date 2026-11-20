from fastapi.testclient import TestClient

from services.gateway.app import main
from services.gateway.app.main import app


def test_health():
    response = TestClient(app).get("/health")
    assert response.status_code == 200 and response.json()["service"] == "gateway"


def test_gateway_sets_security_headers_and_cors_on_auth_errors(monkeypatch):
    monkeypatch.setattr(main.settings, "classsync_env", "production")
    response = TestClient(app).get(
        "/api/v1/auth/me", headers={"Origin": "http://localhost:5173"}
    )

    assert response.status_code == 401
    assert response.headers["strict-transport-security"] == (
        "max-age=31536000; includeSubDomains"
    )
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"

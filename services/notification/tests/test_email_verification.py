from fastapi.testclient import TestClient
from pydantic import SecretStr

from services.notification.app import main


def test_verification_delivery_requires_internal_service_token(monkeypatch):
    monkeypatch.setattr(main.settings, "notification_service_token", SecretStr("internal"))

    result = TestClient(main.app).post(
        "/internal/v1/verification-email",
        json={"email": "juan.delacruz@student.pnm.edu.ph", "code": "123456"},
    )

    assert result.status_code == 403


def test_verification_email_rejects_extra_fields(monkeypatch):
    monkeypatch.setattr(main.settings, "notification_service_token", SecretStr("internal"))

    result = TestClient(main.app).post(
        "/internal/v1/verification-email",
        headers={"X-ClassSync-Service-Token": "internal"},
        json={"email": "juan.delacruz@student.pnm.edu.ph", "code": "123456", "name": "x"},
    )

    assert result.status_code == 422


def test_verification_email_fails_closed_without_resend_credentials(monkeypatch):
    monkeypatch.setattr(main.settings, "notification_service_token", SecretStr("internal"))
    monkeypatch.setattr(main.settings, "resend_api_key", None)
    monkeypatch.setattr(main.settings, "resend_from_email", "")

    result = TestClient(main.app).post(
        "/internal/v1/verification-email",
        headers={"X-ClassSync-Service-Token": "internal"},
        json={"email": "juan.delacruz@student.pnm.edu.ph", "code": "123456"},
    )

    assert result.status_code == 503
    assert result.json()["detail"] == "Email delivery is unavailable"


def test_verification_email_sends_only_to_configured_resend_endpoint(monkeypatch):
    observed = {}

    class Result:
        def raise_for_status(self):
            return None

    class Client:
        def __init__(self, **kwargs):
            observed["client"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, url, *, json, headers):
            observed.update({"url": url, "payload": json, "headers": headers})
            return Result()

    monkeypatch.setattr(main.settings, "notification_service_token", SecretStr("internal"))
    monkeypatch.setattr(main.settings, "resend_api_key", SecretStr("resend-secret"))
    monkeypatch.setattr(main.settings, "resend_from_email", "ClassSync <no-reply@example.org>")
    monkeypatch.setattr(main.httpx, "AsyncClient", Client)

    result = TestClient(main.app).post(
        "/internal/v1/verification-email",
        headers={"X-ClassSync-Service-Token": "internal"},
        json={"email": "juan.delacruz@student.pnm.edu.ph", "code": "123456"},
    )

    assert result.status_code == 202
    assert observed["client"] == {"timeout": 8.0, "trust_env": False}
    assert observed["url"] == "https://api.resend.com/emails"
    assert observed["payload"]["to"] == ["juan.delacruz@student.pnm.edu.ph"]
    assert "123456" in observed["payload"]["text"]
    assert observed["headers"]["Authorization"] == "Bearer resend-secret"

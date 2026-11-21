from fastapi.testclient import TestClient
from pydantic import SecretStr

from services.notification.app import main
from services.notification.app.email_templates import render_email_action_email


def test_personal_email_action_contract_and_branded_email_content():
    action_url = "https://class-sync-bhiv.vercel.app/auth/action?mode=resetPassword&oobCode=opaque"
    html, text = render_email_action_email("resetPassword", action_url)
    assert "Reset Password" in html
    assert "click here" in html
    assert "firebaseapp.com" not in html + text
    assert "classsync-8af14" not in html + text
    assert action_url not in text

    body = main.EmailAction.model_validate({
        "email": " Student.Demo@Gmail.com ",
        "mode": "resetPassword",
        "action_url": action_url,
    })
    assert body.email == "student.demo@gmail.com"


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
    monkeypatch.setattr(main.settings, "email_provider", "resend")
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

    monkeypatch.setattr(main.settings, "email_provider", "resend")
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
    assert observed["client"] == {"timeout": 15.0, "trust_env": False}
    assert observed["url"] == "https://api.resend.com/emails"
    assert observed["payload"]["to"] == ["juan.delacruz@student.pnm.edu.ph"]
    assert "123456" in observed["payload"]["text"]
    assert observed["headers"]["Authorization"] == "Bearer resend-secret"
    assert "html" in observed["payload"]
    assert "click here to continue" in observed["payload"]["html"]


def test_verification_email_can_use_brevo_with_configured_sender(monkeypatch):
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

    monkeypatch.setattr(main.settings, "email_provider", "brevo")
    monkeypatch.setattr(main.settings, "notification_service_token", SecretStr("internal"))
    monkeypatch.setattr(main.settings, "brevo_api_key", SecretStr("brevo-secret"))
    monkeypatch.setattr(main.settings, "brevo_sender_email", "no-reply@example.org")
    monkeypatch.setattr(main.httpx, "AsyncClient", Client)

    result = TestClient(main.app).post(
        "/internal/v1/verification-email",
        headers={"X-ClassSync-Service-Token": "internal"},
        json={"email": "juan.delacruz@student.pnm.edu.ph", "code": "654321"},
    )

    assert result.status_code == 202
    assert observed["url"] == "https://api.brevo.com/v3/smtp/email"
    assert observed["headers"]["api-key"] == "brevo-secret"
    assert observed["payload"]["sender"] == {
        "name": "ClassSync", "email": "no-reply@example.org"
    }
    assert observed["payload"]["to"] == [
        {"email": "juan.delacruz@student.pnm.edu.ph"}
    ]
    assert "654321" in observed["payload"]["htmlContent"]


def test_password_reset_email_uses_configured_transactional_provider(monkeypatch):
    observed = {}

    class Result:
        def raise_for_status(self):
            return None

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, url, *, json, headers):
            observed.update({"url": url, "payload": json, "headers": headers})
            return Result()

    monkeypatch.setattr(main.settings, "email_provider", "brevo")
    monkeypatch.setattr(main.settings, "notification_service_token", SecretStr("internal"))
    monkeypatch.setattr(main.settings, "brevo_api_key", SecretStr("brevo-secret"))
    monkeypatch.setattr(main.settings, "brevo_sender_email", "no-reply@example.org")
    monkeypatch.setattr(main.httpx, "AsyncClient", Client)

    result = TestClient(main.app).post(
        "/internal/v1/password-reset-email",
        headers={"X-ClassSync-Service-Token": "internal"},
        json={
            "email": "juan.delacruz@student.pnm.edu.ph",
            "reset_url": "https://class-sync-bhiv.vercel.app/auth/action?mode=resetPassword&oobCode=opaque-code",
        },
    )

    assert result.status_code == 202
    assert observed["url"] == "https://api.brevo.com/v3/smtp/email"
    assert observed["payload"]["to"] == [{"email": "juan.delacruz@student.pnm.edu.ph"}]
    assert "Reset Password" in observed["payload"]["htmlContent"]
    assert "opaque-code" in observed["payload"]["htmlContent"]
    assert "https://class-sync-bhiv.vercel.app" not in observed["payload"]["textContent"]

from fastapi.testclient import TestClient
from pydantic import SecretStr

from services.gateway.app import main


def test_turnstile_allows_deterministic_nonproduction_test_bypass(monkeypatch):
    monkeypatch.setattr(main.settings, "classsync_env", "test")
    monkeypatch.setattr(main.settings, "turnstile_secret_key", None)

    result = TestClient(main.app).post(
        "/api/v1/auth/verify-turnstile", json={"token": "test-token"}
    )

    assert result.status_code == 200
    assert result.json() == {"data": {"verified": True}}
    assert result.headers["cache-control"] == "no-store"


def test_turnstile_fails_closed_when_production_secret_is_missing(monkeypatch):
    monkeypatch.setattr(main.settings, "classsync_env", "production")
    monkeypatch.setattr(main.settings, "turnstile_secret_key", None)

    result = TestClient(main.app).post(
        "/api/v1/auth/verify-turnstile", json={"token": "test-token"}
    )

    assert result.status_code == 503
    assert result.json()["error"]["message"] == "Human verification is unavailable"


def test_turnstile_rejects_unknown_contract_fields_before_provider_call():
    result = TestClient(main.app).post(
        "/api/v1/auth/verify-turnstile",
        json={"token": "test-token", "bypass": True},
    )

    assert result.status_code == 422


def test_turnstile_forwards_secret_and_token_to_siteverify_without_proxy(monkeypatch):
    observed = {}

    class Result:
        def raise_for_status(self):
            return None

        def json(self):
            return {"success": True}

    class Client:
        def __init__(self, **kwargs):
            observed["client"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, url, *, data):
            observed["url"] = url
            observed["data"] = data
            return Result()

    monkeypatch.setattr(main.settings, "classsync_env", "production")
    monkeypatch.setattr(main.settings, "turnstile_secret_key", SecretStr("turnstile-secret"))
    monkeypatch.setattr(main.httpx, "AsyncClient", Client)

    result = TestClient(main.app).post(
        "/api/v1/auth/verify-turnstile", json={"token": "single-use-token"}
    )

    assert result.status_code == 200
    assert observed == {
        "client": {"timeout": 15.0, "trust_env": False},
        "url": "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        "data": {"secret": "turnstile-secret", "response": "single-use-token"},
    }

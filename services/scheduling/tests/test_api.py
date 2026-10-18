import httpx
import pytest
from fastapi.testclient import TestClient

from services.gateway.app import main as gateway
from services.scheduling.app import main as scheduling
from services.scheduling.tests.test_engine import tiny


@pytest.fixture
def sandbox(monkeypatch):
    for config in (gateway.settings, scheduling.settings):
        monkeypatch.setattr(config, "classsync_env", "development")
        monkeypatch.setattr(config, "enable_scheduling_sandbox", True)


def test_service_real_generate_and_validate(sandbox):
    client = TestClient(scheduling.app)
    body = tiny().model_dump(mode="json")
    response = client.post("/api/v1/scheduling/sandbox/generate", json=body)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["solver_status"] in {"optimal", "feasible"}
    assert result["persisted"] is False
    assert result["validation"]["valid"]
    validation = client.post(
        "/api/v1/scheduling/sandbox/validate",
        json={"inputs": body, "assignments": result["assignments"]},
    )
    assert validation.json()["valid"]
    assert client.get("/api/v1/scheduling/sandbox/scenario").json()["synthetic"]
    assert len(client.get("/api/v1/scheduling/sandbox/catalogs").json()["cdm_spaces"]) == 59


def test_gateway_to_service_roundtrip(sandbox, monkeypatch):
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        gateway.httpx,
        "AsyncClient",
        lambda **kwargs: original_client(
            transport=httpx.ASGITransport(app=scheduling.app), **kwargs
        ),
    )
    client = TestClient(gateway.app)
    response = client.post(
        "/api/v1/scheduling/sandbox/generate", json=tiny().model_dump(mode="json")
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["validation"]["valid"]
    assert response.headers["X-Request-ID"]
    malformed = client.post("/api/v1/scheduling/sandbox/generate", json={"role": "administrator"})
    assert malformed.status_code == 422
    assert malformed.json()["error"]["code"] == "scheduling_rejected"


@pytest.mark.parametrize(
    "app,config", [(scheduling.app, scheduling.settings), (gateway.app, gateway.settings)]
)
@pytest.mark.parametrize("environment,enabled", [("production", True), ("development", False)])
def test_sandbox_requires_both_gates(app, config, environment, enabled, monkeypatch):
    monkeypatch.setattr(config, "classsync_env", environment)
    monkeypatch.setattr(config, "enable_scheduling_sandbox", enabled)
    assert (
        TestClient(app)
        .post("/api/v1/scheduling/sandbox/generate", json=tiny().model_dump(mode="json"))
        .status_code
        == 403
    )


@pytest.mark.parametrize("app", [scheduling.app, gateway.app])
def test_preview_role_and_general_dev_bypass_never_authorize_production(app, monkeypatch):
    monkeypatch.setattr(gateway.settings, "allow_unauthenticated_development", True)
    monkeypatch.setattr(gateway.settings, "classsync_env", "development")
    client = TestClient(app)
    assert (
        client.post(
            "/api/v1/scheduling/generate",
            json=tiny().model_dump(mode="json"),
            headers={"X-Role": "administrator"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/scheduling/validate",
            json={"inputs": tiny().model_dump(mode="json"), "assignments": []},
        ).status_code
        == 401
    )


def test_verified_admin_role_is_required(monkeypatch):
    from classync_contracts import scheduling_security

    monkeypatch.setattr(scheduling_security, "initialize_firebase", lambda *_: None)
    monkeypatch.setattr(
        scheduling_security.auth,
        "verify_id_token",
        lambda *_, **__: {"uid": "verified", "role": "teacher"},
    )
    response = TestClient(scheduling.app).post(
        "/api/v1/scheduling/generate",
        json=tiny().model_dump(mode="json"),
        headers={"Authorization": "Bearer verified-test"},
    )
    assert response.status_code == 403
    monkeypatch.setattr(
        scheduling_security.auth,
        "verify_id_token",
        lambda *_, **__: {"uid": "verified", "role": "administrator"},
    )
    assert (
        TestClient(scheduling.app)
        .post(
            "/api/v1/scheduling/generate",
            json=tiny().model_dump(mode="json"),
            headers={"Authorization": "Bearer verified-test"},
        )
        .status_code
        == 200
    )


def test_preview_cannot_publish_or_use_cdm_as_fake_synthetic(sandbox):
    client = TestClient(scheduling.app)
    body = tiny().model_dump(mode="json")
    body["rooms"][0]["source"] = "cdm-provisional"
    assert client.post("/api/v1/scheduling/sandbox/generate", json=body).status_code == 422
    assert client.post("/api/v1/scheduling/sandbox/publish", json={}).status_code == 404
    assert (
        TestClient(gateway.app).post("/api/v1/scheduling/sandbox/publish", json={}).status_code
        == 404
    )


def test_readiness_schema_errors_and_busy_feedback(sandbox):
    client = TestClient(scheduling.app)
    body = tiny().model_dump(mode="json")
    body["offerings"] = []
    result = client.post("/api/v1/scheduling/sandbox/readiness", json=body)
    assert result.status_code == 200
    assert any(d["code"] == "missing_inputs" for d in result.json()["diagnostics"])
    body["offerings"] = "not an array"
    assert client.post("/api/v1/scheduling/sandbox/readiness", json=body).status_code == 422
    scheduling.generation_slot.acquire()
    try:
        assert (
            client.post(
                "/api/v1/scheduling/sandbox/generate", json=tiny().model_dump(mode="json")
            ).status_code
            == 503
        )
    finally:
        scheduling.generation_slot.release()

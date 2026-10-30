from types import SimpleNamespace

import pytest
from classync_contracts.request_authorization import (
    AuthorizationAdapters,
    UnconfiguredMembershipLookup,
)
from classync_contracts.token_verification import (
    AdapterTrust,
    TokenErrorCode,
    TokenVerificationError,
)
from fastapi.testclient import TestClient

from services.academic.app import main as academic
from services.gateway.app import main as gateway
from services.scheduling.app import main as scheduling

TOKEN = "e30.e30.synthetic-signature"
HEADERS = {"Authorization": "Bearer " + TOKEN}


@pytest.mark.parametrize("environment", ["production", "staging", "development", "test"])
@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("trust", [AdapterTrust.FIREBASE, AdapterTrust.TEST, AdapterTrust.EMULATOR])
def test_unsigned_emulator_tokens_require_all_explicit_test_gates(
    identity_adapters, monkeypatch, environment, enabled, trust,
):
    verifier, repository = identity_adapters(gateway, "student")
    verifier.trust = trust
    monkeypatch.setattr(gateway.settings, "classsync_env", environment)
    monkeypatch.setattr(gateway.settings, "enable_test_identity_adapters", enabled)
    allowed = environment == "test" and enabled and trust is AdapterTrust.EMULATOR
    response = TestClient(gateway.app).get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer e30.e30."},
    )
    assert response.status_code == (200 if allowed else 401), response.text
    assert verifier.calls == int(allowed)
    assert len(repository.calls) == int(allowed)


@pytest.mark.parametrize("role", ["student", "teacher", "administrator"])
def test_auth_me_uses_current_membership_not_client_claims(identity_adapters, role):
    verifier, repository = identity_adapters(gateway, role)
    response = TestClient(gateway.app).get(
        "/api/v1/auth/me",
        headers={
            **HEADERS,
            "X-Role": "administrator",
            "X-Tenant-ID": "other-tenant",
            "X-Faculty-ID": "other-faculty",
        },
    )
    assert response.status_code == 200, response.text
    identity = response.json()["data"]
    assert identity["role"] == role
    assert identity["tenant_id"] == "synthetic-tenant"
    assert identity["uid"] == "synthetic-user"
    if role == "student":
        assert identity["student_id"] == "synthetic-student"
        assert identity["student_id"] != identity["uid"]
    if role == "teacher":
        assert identity["faculty_id"] == "synthetic-faculty"
    assert verifier.calls == 1
    assert repository.calls == [("synthetic-tenant", "synthetic-user")]


@pytest.mark.parametrize("token", [".e30.", "e30..", "e30.e30..", "e30.e30. extra",
                                    "e30." + "a" * 16_384 + "."])
def test_malformed_unsigned_emulator_token_denied_before_adapters(identity_adapters, token):
    verifier, repository = identity_adapters(gateway, "student")
    verifier.trust = AdapterTrust.EMULATOR
    response = TestClient(gateway.app).get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer " + token},
    )
    assert response.status_code == 401
    assert verifier.calls == 0
    assert repository.calls == []


@pytest.mark.parametrize(
    "header",
    [
        None,
        "",
        "Bearer",
        "Bearer invalid",
        "Basic e30.e30.sig",
        "Bearer e30..sig",
        "Bearer e30.e30.sig extra",
    ],
)
def test_missing_and_malformed_tokens_deny_before_adapter(identity_adapters, header):
    verifier, _ = identity_adapters(gateway)
    response = TestClient(gateway.app).get(
        "/api/v1/auth/me", headers={"Authorization": header} if header is not None else {}
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert verifier.calls == 0


@pytest.mark.parametrize(
    "code",
    [
        TokenErrorCode.INVALID,
        TokenErrorCode.EXPIRED,
        TokenErrorCode.REVOKED,
        TokenErrorCode.UNAVAILABLE,
    ],
)
def test_token_failures_never_attempt_membership_or_fallback(identity_adapters, code):
    verifier, repository = identity_adapters(gateway)
    verifier.error = TokenVerificationError(code)
    response = TestClient(gateway.app).get("/api/v1/auth/me", headers=HEADERS)
    assert response.status_code == (503 if code == TokenErrorCode.UNAVAILABLE else 401)
    assert response.json()["error"]["code"] == code.value
    assert repository.calls == []
    assert TOKEN not in response.text


@pytest.mark.parametrize("environment", ["production", "staging", "development", "test"])
@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("trust", [AdapterTrust.TEST, AdapterTrust.EMULATOR])
def test_noninstitutional_providers_require_explicit_test_runtime(
    identity_adapters, monkeypatch, environment, enabled, trust
):
    verifier, repository = identity_adapters(gateway)
    verifier.trust = repository.trust = trust
    monkeypatch.setattr(gateway.settings, "classsync_env", environment)
    monkeypatch.setattr(gateway.settings, "enable_test_identity_adapters", enabled)
    response = TestClient(gateway.app).get("/api/v1/auth/me", headers=HEADERS)
    allowed = environment == "test" and enabled
    assert response.status_code == (200 if allowed else 503)
    assert verifier.calls == (1 if allowed else 0)


@pytest.mark.parametrize(
    "changes",
    [
        {"state": "revoked"},
        {"state": "inactive"},
        {"uid": "other-uid"},
        {"tenant_id": "other-tenant"},
        {"roles": []},
    ],
)
def test_current_membership_denial(identity_adapters, changes):
    _, repository = identity_adapters(gateway)
    repository.membership = repository.membership.model_copy(update=changes)
    assert TestClient(gateway.app).get("/api/v1/auth/me", headers=HEADERS).status_code == 403


def test_revocation_and_repository_outage_are_observed_without_cached_success(identity_adapters):
    _, repository = identity_adapters(gateway)
    client = TestClient(gateway.app)
    assert client.get("/api/v1/auth/me", headers=HEADERS).status_code == 200
    repository.membership = None
    assert client.get("/api/v1/auth/me", headers=HEADERS).status_code == 403
    repository.error = RuntimeError("synthetic private driver detail")
    response = client.get("/api/v1/auth/me", headers=HEADERS)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "membership_unavailable"
    assert "driver" not in response.text
    assert len(repository.calls) == 3


def test_multirole_selection_is_checked_against_current_grants(identity_adapters):
    identity_adapters(gateway, roles=["student", "teacher"])
    client = TestClient(gateway.app)
    assert client.get("/api/v1/auth/me", headers=HEADERS).status_code == 403
    for selected, status in [
        ("student", 200),
        ("teacher", 200),
        ("administrator", 403),
        ("owner", 403),
    ]:
        response = client.get("/api/v1/auth/me", headers={**HEADERS, "X-ClassSync-Role": selected})
        assert response.status_code == status


@pytest.mark.parametrize(
    "role,fields", [("student", {"student_id": None}), ("teacher", {"faculty_id": None})]
)
def test_role_does_not_imply_academic_record_membership(identity_adapters, role, fields):
    identity_adapters(gateway, role, **fields)
    response = TestClient(gateway.app).get("/api/v1/auth/me", headers=HEADERS)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "record_membership_required"


def test_general_development_bypass_is_not_an_authenticated_identity(monkeypatch):
    monkeypatch.setattr(gateway.settings, "classsync_env", "development")
    monkeypatch.setattr(gateway.settings, "allow_unauthenticated_development", True)
    assert TestClient(gateway.app).get("/api/v1/auth/me").status_code == 401


@pytest.mark.parametrize(
    "module,path",
    [
        (academic, "/api/v1/academic/periods"),
        (scheduling, "/api/v1/scheduling/drafts"),
        (scheduling, "/api/v1/timetables/periods"),
        (scheduling, "/api/v1/timetables/history/synthetic-period"),
    ],
)
def test_denied_service_calls_never_open_repository(module, path, monkeypatch):
    def forbidden():
        pytest.fail("Unauthenticated request attempted repository access")

    monkeypatch.setattr(module, "repository", forbidden)
    assert TestClient(module.app).get(path).status_code == 401


def test_admin_guard_uses_membership_not_client_role(identity_adapters, monkeypatch):
    identity_adapters(academic, "teacher")

    def forbidden():
        pytest.fail("Denied teacher attempted admin repository access")

    monkeypatch.setattr(academic, "repository", forbidden)
    response = TestClient(academic.app).get(
        "/api/v1/academic/periods",
        headers={
            **HEADERS,
            "X-ClassSync-Role": "administrator",
            "X-Role": "administrator",
        },
    )
    assert response.status_code == 403


def test_unknown_adapter_cannot_be_installed_as_authority(identity_adapters, monkeypatch):
    verifier, repository = identity_adapters(gateway)
    monkeypatch.setattr(
        gateway.app.state,
        "authorization_adapters",
        AuthorizationAdapters(SimpleNamespace(verify=verifier.verify), repository),
    )
    assert TestClient(gateway.app).get("/api/v1/auth/me", headers=HEADERS).status_code == 503
    assert verifier.calls == 0


def test_gateway_preserves_absent_role_and_downstream_rechecks_membership(
    identity_adapters, monkeypatch, tmp_path
):
    import httpx

    identity_adapters(gateway)
    _, downstream_repository = identity_adapters(academic)
    monkeypatch.setattr(academic.settings, "academic_database_path", str(tmp_path / "academic.db"))
    downstream = TestClient(academic.app)

    async def forward(_self, method, url, **kwargs):
        assert "X-ClassSync-Role" not in kwargs["headers"]
        assert "X-Tenant-ID" not in kwargs["headers"]
        result = downstream.request(method, "/api/v1/academic/periods", headers=kwargs["headers"])
        return httpx.Response(result.status_code, json=result.json())

    monkeypatch.setattr(httpx.AsyncClient, "request", forward)
    client = TestClient(gateway.app)
    assert client.get("/api/v1/academic/periods", headers=HEADERS).status_code == 200
    downstream_repository.membership = None
    assert client.get("/api/v1/academic/periods", headers=HEADERS).status_code == 403


def test_unconfigured_membership_never_falls_back_to_token_role(identity_adapters, monkeypatch):
    verifier, _ = identity_adapters(gateway)
    monkeypatch.setattr(
        gateway.app.state,
        "authorization_adapters",
        AuthorizationAdapters(verifier, UnconfiguredMembershipLookup()),
    )
    response = TestClient(gateway.app).get("/api/v1/auth/me", headers=HEADERS)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "membership_unavailable"


def test_missing_server_tenant_is_unavailable_not_client_selected(identity_adapters, monkeypatch):
    _, repository = identity_adapters(gateway)
    monkeypatch.setattr(gateway.settings, "institutional_tenant_id", None)
    response = TestClient(gateway.app).get(
        "/api/v1/auth/me",
        headers={
            **HEADERS,
            "X-Tenant-ID": "synthetic-tenant",
        },
    )
    assert response.status_code == 503
    assert repository.calls == []

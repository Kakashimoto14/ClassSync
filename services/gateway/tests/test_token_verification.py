"""Real SDK signature/claim verification offline; certificates/account transport stubbed."""

import time

import firebase_admin
import pytest
from classync_contracts import token_verification as tokens
from classync_contracts.firebase import FirebaseSettings
from google.auth.exceptions import TransportError

from services.testing.offline_firebase import offline_firebase


@pytest.fixture
def offline_sdk(monkeypatch):
    with offline_firebase(monkeypatch) as sdk:
        yield sdk


def test_offline_sdk_setup_failure_removes_its_named_app(monkeypatch):
    from services.testing import offline_firebase as helper

    before = dict(firebase_admin._apps)

    def fail(**kwargs):
        raise RuntimeError("synthetic key setup failure")

    monkeypatch.setattr(helper.rsa, "generate_private_key", fail)
    with pytest.raises(RuntimeError, match="synthetic key setup failure"):
        with offline_firebase(monkeypatch):
            pytest.fail("Failed setup yielded an adapter")
    assert firebase_admin._apps == before


def test_real_sdk_signature_and_claim_verification_returns_identity_only(offline_sdk):
    verifier, encoded, _, _ = offline_sdk
    assert verifier.verify(encoded()).model_dump() == {"uid": "synthetic-uid"}


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"exp": 1}, tokens.TokenErrorCode.EXPIRED),
        ({"iss": "https://attacker.invalid"}, tokens.TokenErrorCode.INVALID),
        ({"aud": "other-project"}, tokens.TokenErrorCode.INVALID),
        ({"sub": ""}, tokens.TokenErrorCode.INVALID),
        ({"firebase": {"tenant": "other-identity-realm"}}, tokens.TokenErrorCode.INVALID),
        ({"iat": int(time.time()) + 3600}, tokens.TokenErrorCode.INVALID),
    ],
)
def test_real_sdk_rejects_invalid_token_claims(offline_sdk, changes, code):
    verifier, encoded, _, _ = offline_sdk
    with pytest.raises(tokens.TokenVerificationError) as caught:
        verifier.verify(encoded(**changes))
    assert caught.value.code == code


@pytest.mark.parametrize("condition", ["revoked", "disabled"])
def test_sdk_revocation_and_disabled_user_checks_are_enabled(offline_sdk, condition):
    verifier, encoded, user, _ = offline_sdk
    if condition == "revoked":
        user.tokens_valid_after_timestamp = int(time.time() + 10) * 1000
    else:
        user.disabled = True
    with pytest.raises(tokens.TokenVerificationError) as caught:
        verifier.verify(encoded())
    assert caught.value.code == tokens.TokenErrorCode.REVOKED


def test_invalid_signature_denied(offline_sdk):
    verifier, encoded, _, _ = offline_sdk
    token = encoded()
    parts = token.split(".")
    parts[2] = ("A" if parts[2][0] != "A" else "B") + parts[2][1:]
    with pytest.raises(tokens.TokenVerificationError) as caught:
        verifier.verify(".".join(parts))
    assert caught.value.code == tokens.TokenErrorCode.INVALID


def test_revocation_lookup_outage_never_disables_revocation_check(offline_sdk, monkeypatch):
    verifier, encoded, _, client = offline_sdk

    def unavailable(_):
        raise RuntimeError("synthetic private account transport failure")

    monkeypatch.setattr(client, "get_user", unavailable)
    with pytest.raises(tokens.TokenVerificationError) as caught:
        verifier.verify(encoded())
    assert caught.value.code == tokens.TokenErrorCode.UNAVAILABLE
    assert str(caught.value) == "identity_unavailable"


def test_sdk_emulator_environment_never_verifies_institutional_identity(offline_sdk, monkeypatch):
    verifier, encoded, _, _ = offline_sdk
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
    with pytest.raises(tokens.TokenVerificationError) as caught:
        verifier.verify(encoded())
    assert caught.value.code == tokens.TokenErrorCode.UNAVAILABLE


def test_existing_sdk_app_cannot_supply_another_project(offline_sdk):
    _, encoded, _, _ = offline_sdk
    verifier = tokens.FirebaseTokenVerifier(
        FirebaseSettings(firebase_project_id="other-project", _env_file=None)
    )
    with pytest.raises(tokens.TokenVerificationError) as caught:
        verifier.verify(encoded())
    assert caught.value.code == tokens.TokenErrorCode.UNAVAILABLE


def test_certificate_transport_failure_is_unavailable(offline_sdk):
    verifier, encoded, _, client = offline_sdk

    def unavailable(*args, **kwargs):
        raise TransportError("synthetic private certificate transport failure")

    client._token_verifier.request = unavailable
    with pytest.raises(tokens.TokenVerificationError) as caught:
        verifier.verify(encoded())
    assert caught.value.code == tokens.TokenErrorCode.UNAVAILABLE


def test_real_sdk_token_through_fastapi_ignores_forged_claims_and_observes_revocation(
    offline_sdk, identity_adapters, monkeypatch
):
    from classync_contracts.request_authorization import AuthorizationAdapters
    from fastapi.testclient import TestClient

    from services.gateway.app import main

    verifier, encoded, user, _ = offline_sdk
    _, repository = identity_adapters(main, "teacher", uid="synthetic-uid")
    monkeypatch.setattr(
        main.app.state, "authorization_adapters", AuthorizationAdapters(verifier, repository)
    )
    client = TestClient(main.app)
    headers = {"Authorization": "Bearer " + encoded()}
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["data"] == {
        "uid": "synthetic-uid",
        "tenant_id": "synthetic-tenant",
        "role": "teacher",
        "faculty_id": "synthetic-faculty",
        "membership_revision": 1,
    }
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer " + encoded(aud="other-project")}
        ).status_code
        == 401
    )
    assert len(repository.calls) == 1
    user.tokens_valid_after_timestamp = int(time.time() + 10) * 1000
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert len(repository.calls) == 1

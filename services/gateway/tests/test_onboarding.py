import time
from unittest.mock import Mock

import pytest
from uuid import UUID
from classync_contracts.identity import VerifiedPrincipal
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import SecretStr

from services.gateway.app import main
from services.gateway.app import onboarding
from services.gateway.app.onboarding import STUDENT_VERIFICATION_ERROR
from services.gateway.app.onboarding_repository import student_record_matches

HEADERS = {"Authorization": "Bearer e30.e30.synthetic-signature"}


@pytest.fixture
def setup(identity_adapters, monkeypatch):
    verifier, _ = identity_adapters(main)
    repository = Mock()
    repository.status.return_value = {"status": "unlinked"}
    monkeypatch.setattr(main.app.state, "onboarding_repository", repository, raising=False)
    async def allow_turnstile(*_args):
        return None
    monkeypatch.setattr(onboarding, "verify_turnstile_token", allow_turnstile)
    return TestClient(main.app), verifier, repository


def test_onboarding_requires_token_and_never_takes_subject_or_role_from_payload(setup):
    client, _, repository = setup
    assert client.get("/api/v1/auth/onboarding").status_code == 401
    result = client.post(
        "/api/v1/auth/student-claims",
        headers=HEADERS,
        json={"student_id": "24-98096", "role": "administrator"},
    )
    assert result.status_code == 422
    repository.submit_claim.assert_not_called()


def test_unverified_identity_can_only_read_pending_status(setup, monkeypatch):
    client, verifier, repository = setup
    monkeypatch.setattr(
        verifier,
        "verify",
        lambda _: VerifiedPrincipal(
            uid="unverified",
            email="synthetic@example.invalid",
            email_verified=False,
        ),
    )
    assert client.get("/api/v1/auth/onboarding", headers=HEADERS).status_code == 200
    assert client.get("/api/v1/auth/me", headers=HEADERS).status_code == 403
    assert (
        client.post(
            "/api/v1/auth/student-claims", headers=HEADERS, json={"student_id": "24-98096"}
        ).status_code
        == 403
    )
    repository.submit_claim.assert_not_called()


def test_student_verification_requires_verified_firebase_email(setup, monkeypatch):
    client, verifier, repository = setup
    monkeypatch.setattr(
        verifier,
        "verify",
        lambda _: VerifiedPrincipal(
            uid="unverified-student",
            email="jane.doe@student.pnm.edu.ph",
            email_verified=False,
        ),
    )

    result = client.post(
        "/api/v1/auth/verify-student",
        headers=HEADERS,
        json={"student_id": "24-98096", "challenge_id": "00000000-0000-0000-0000-000000000001",
              "code": "123456", "turnstile_token": "test-token"},
    )

    assert result.status_code == 403
    assert result.json()["error"]["message"] == "Verify your email before continuing"
    repository.verify_student_challenge.assert_not_called()


def test_privileged_account_management_requires_recent_sign_in(setup, monkeypatch):
    client, verifier, repository = setup
    monkeypatch.setattr(
        verifier,
        "verify",
        lambda _: VerifiedPrincipal(
            uid="synthetic",
            email="synthetic@example.invalid",
            email_verified=True,
            auth_time=int(time.time()) - 601,
        ),
    )
    assert client.get("/api/v1/auth/student-claims", headers=HEADERS).status_code == 403
    repository.claims.assert_not_called()


def test_mutation_throttle_returns_retry_after_without_calling_repository(setup, monkeypatch):
    client, verifier, repository = setup
    monkeypatch.setattr(
        verifier,
        "verify",
        lambda _: VerifiedPrincipal(
            uid="throttle-fixture",
            email="synthetic@example.invalid",
            email_verified=True,
        ),
    )
    repository.submit_claim.return_value = {"status": "pending"}
    for _ in range(10):
        assert (
            client.post(
                "/api/v1/auth/student-claims", headers=HEADERS, json={"student_id": "24-98096"}
            ).status_code
            == 201
        )
    result = client.post(
        "/api/v1/auth/student-claims", headers=HEADERS, json={"student_id": "24-98096"}
    )
    assert result.status_code == 429
    assert result.headers["Retry-After"] == "60"
    assert repository.submit_claim.call_count == 10


def test_student_verification_uses_verified_firebase_email_and_strict_roster_id(setup, monkeypatch):
    client, verifier, repository = setup
    principal = VerifiedPrincipal(
        uid="new-student",
        email="juan.delacruz@student.pnm.edu.ph",
        email_verified=True,
    )
    monkeypatch.setattr(verifier, "verify", lambda _: principal)
    monkeypatch.setattr(main.settings, "otp_hmac_secret", SecretStr("test-secret"))
    repository.verify_student_challenge.return_value = {"status": "verified"}

    result = client.post(
        "/api/v1/auth/verify-student",
        headers=HEADERS,
        json={"student_id": "24-98096", "challenge_id": "00000000-0000-0000-0000-000000000001",
              "code": "123456", "turnstile_token": "test-token"},
    )

    assert result.status_code == 200
    assert result.json() == {"data": {"status": "verified"}}
    repository.verify_student_challenge.assert_called_once_with(
        principal, "24-98096", UUID("00000000-0000-0000-0000-000000000001"),
        "123456", b"test-secret",
    )


@pytest.mark.parametrize(
    "body",
    [
        {"student_id": "<script>alert(1)</script>"},
        {"student_id": "24-98096", "challenge_id": "00000000-0000-0000-0000-000000000001",
         "code": "123456", "turnstile_token": "test-token", "email": "attacker@example.invalid"},
    ],
)
def test_student_verification_rejects_invalid_or_untrusted_fields_before_repository(setup, body):
    client, _, repository = setup

    result = client.post("/api/v1/auth/verify-student", headers=HEADERS, json=body)

    assert result.status_code == 422
    repository.verify_student_challenge.assert_not_called()


def test_roster_mismatch_shares_registrar_message_before_otp_delivery(setup, monkeypatch):
    client, _, repository = setup
    monkeypatch.setattr(main.settings, "otp_hmac_secret", SecretStr("test-secret"))
    monkeypatch.setattr(main.settings, "notification_service_token", SecretStr("service-secret"))
    repository.issue_student_challenge.side_effect = HTTPException(403, STUDENT_VERIFICATION_ERROR)

    result = client.post(
        "/api/v1/auth/student-verification-challenges", headers=HEADERS,
        json={"student_id": "24-98096", "turnstile_token": "test-token"},
    )

    assert result.status_code == 403
    assert result.json()["error"]["message"] == STUDENT_VERIFICATION_ERROR
    repository.issue_student_challenge.assert_called_once()


def test_student_challenge_fails_closed_when_hmac_or_delivery_secret_is_missing(setup, monkeypatch):
    client, _, repository = setup
    monkeypatch.setattr(main.settings, "otp_hmac_secret", None)
    monkeypatch.setattr(main.settings, "notification_service_token", None)

    result = client.post(
        "/api/v1/auth/student-verification-challenges", headers=HEADERS,
        json={"student_id": "24-98096", "turnstile_token": "test-token"},
    )

    assert result.status_code == 503
    assert result.json()["error"]["message"] == "Email verification is unavailable"
    repository.issue_student_challenge.assert_not_called()


def test_student_number_login_contract_rejects_extra_fields_before_lookup(setup):
    client, _, repository = setup
    result = client.post("/api/v1/auth/student-password-login", json={
        "student_id": "23-01425", "password": "campus-pass-2026",
        "turnstile_token": "test-token", "email": "juan.delacruz@student.pnm.edu.ph",
    })
    assert result.status_code == 422
    repository.student_login_email.assert_not_called()


def test_password_completion_rechecks_turnstile_before_firebase_or_membership(setup, monkeypatch):
    client, _, repository = setup
    calls = []

    async def reject_turnstile(token, _settings):
        calls.append(token)
        raise HTTPException(403, "Human verification failed")

    monkeypatch.setattr(onboarding, "verify_turnstile_token", reject_turnstile)
    monkeypatch.setattr(
        "services.gateway.app.onboarding.initialize_firebase",
        lambda *_: pytest.fail("Firebase must not be reached before Turnstile"),
    )

    result = client.post("/api/v1/auth/complete-student-onboarding", headers=HEADERS, json={
        "student_id": "23-01425",
        "challenge_id": "00000000-0000-0000-0000-000000000001",
        "turnstile_token": "invalid-token",
    })

    assert result.status_code == 403
    assert calls == ["invalid-token"]
    repository.complete_student_onboarding.assert_not_called()


def test_password_completion_requires_firebase_password_provider(setup, monkeypatch):
    client, _, repository = setup
    monkeypatch.setattr(
        "services.gateway.app.onboarding.initialize_firebase", lambda *_: object()
    )
    monkeypatch.setattr(
        "services.gateway.app.onboarding.firebase_auth.get_user",
        lambda *_args, **_kwargs: type("FirebaseUser", (), {
            "provider_data": [type("Provider", (), {"provider_id": "google.com"})()],
            "email": "jane.doe@student.pnm.edu.ph",
        })(),
    )

    result = client.post("/api/v1/auth/complete-student-onboarding", headers=HEADERS, json={
        "student_id": "23-01425",
        "challenge_id": "00000000-0000-0000-0000-000000000001",
        "turnstile_token": "test-token",
    })

    assert result.status_code == 403
    assert result.json()["error"]["message"] == (
        "Set a portal password before completing student setup"
    )
    repository.complete_student_onboarding.assert_not_called()


def test_student_number_login_does_not_reveal_missing_roster_records(setup, monkeypatch):
    client, _, repository = setup
    repository.student_login_email.return_value = None
    monkeypatch.setattr(main.settings, "firebase_web_api_key", SecretStr("public-key"))
    observed = {}

    class Result:
        status_code = 400

    class Client:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, _url, *, json, **_kwargs):
            observed["email"] = json["email"]
            return Result()

    monkeypatch.setattr("services.gateway.app.onboarding.httpx.AsyncClient", Client)

    result = client.post("/api/v1/auth/student-password-login", json={
        "student_id": "23-01425", "password": "campus-pass-2026",
        "turnstile_token": "test-token",
    })

    assert result.status_code == 401
    assert result.json()["error"]["message"] == "Invalid student number or password."
    assert observed["email"] == "unmatched-student-login@student.pnm.edu.ph"
    assert "email" not in result.json()
    repository.student_login_email.assert_called_once_with("23-01425")


def test_student_number_login_never_returns_the_roster_email(setup, monkeypatch):
    client, _, repository = setup
    repository.student_login_email.return_value = "juan.delacruz@student.pnm.edu.ph"
    repository.student_login_membership_matches.return_value = True
    monkeypatch.setattr(main.settings, "firebase_web_api_key", SecretStr("public-key"))
    monkeypatch.setattr("services.gateway.app.onboarding.initialize_firebase", lambda *_: object())
    monkeypatch.setattr("services.gateway.app.onboarding.firebase_auth.create_custom_token",
                        lambda *_args, **_kwargs: b"custom-token")

    observed = {}

    class Result:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"localId": "student-uid", "email": "juan.delacruz@student.pnm.edu.ph"}

    class Client:
        def __init__(self, **kwargs):
            observed["client"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, url, *, params, json, follow_redirects):
            observed.update({"url": url, "params": params, "body": json,
                             "follow_redirects": follow_redirects})
            return Result()

    monkeypatch.setattr("services.gateway.app.onboarding.httpx.AsyncClient", Client)

    result = client.post("/api/v1/auth/student-password-login", json={
        "student_id": "23-01425", "password": "campus-pass-2026",
        "turnstile_token": "test-token",
    })

    assert result.status_code == 200
    assert result.json() == {"data": {"custom_token": "custom-token"}}
    assert "juan.delacruz@student.pnm.edu.ph" not in result.text
    assert observed == {
        "client": {"timeout": 6.0, "trust_env": False},
        "url": "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
        "params": {"key": "public-key"},
        "body": {"email": "juan.delacruz@student.pnm.edu.ph",
                 "password": "campus-pass-2026", "returnSecureToken": True},
        "follow_redirects": False,
    }
    repository.student_login_membership_matches.assert_called_once_with("student-uid", "23-01425")


@pytest.mark.parametrize(
    "row,student_id,email,expected",
    [
        ({"id": "24-98096", "registered_email": "jane.doe@student.pnm.edu.ph",
          "enrollment_status": "active"}, "24-98096", "jane.doe@student.pnm.edu.ph", True),
        ({"id": "24-98096", "registered_email": "jane.doe@student.pnm.edu.ph",
          "enrollment_status": "active"}, "24-98096", "other.name@student.pnm.edu.ph", False),
        ({"id": "24-98096", "registered_email": "jane.doe@student.pnm.edu.ph",
          "enrollment_status": "inactive"}, "24-98096", "jane.doe@student.pnm.edu.ph", False),
        (None, "24-98096", "jane.doe@student.pnm.edu.ph", False),
        ({"id": "24-98096", "registered_email": "jane.doe@student.pnm.edu.ph",
          "enrollment_status": "active"}, None, "jane.doe@student.pnm.edu.ph", False),
        ({"id": "24-98096", "registered_email": "jane.doe@student.pnm.edu.ph",
          "enrollment_status": "active"}, "24-98096", "JANE_DOE@example.com", False),
        ({"id": "24-98096", "registered_email": "jane.doe@student.pnm.edu.ph",
          "enrollment_status": "active"}, "24-98096", "Jane.Doe@student.pnm.edu.ph", False),
    ],
)
def test_student_verification_requires_exact_active_registrar_record(
    row, student_id, email, expected
):
    assert student_record_matches(row, student_id, email) is expected

import time
from unittest.mock import Mock

import pytest
from uuid import UUID
from classync_contracts.identity import VerifiedPrincipal
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import SecretStr

from services.gateway.app import main
from services.gateway.app.onboarding import STUDENT_VERIFICATION_ERROR
from services.gateway.app.onboarding_repository import student_record_matches

HEADERS = {"Authorization": "Bearer e30.e30.synthetic-signature"}


@pytest.fixture
def setup(identity_adapters, monkeypatch):
    verifier, _ = identity_adapters(main)
    repository = Mock()
    repository.status.return_value = {"status": "unlinked"}
    monkeypatch.setattr(main.app.state, "onboarding_repository", repository, raising=False)
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
              "code": "123456"},
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
              "code": "123456"},
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
         "code": "123456", "email": "attacker@example.invalid"},
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
        json={"student_id": "24-98096"},
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
        json={"student_id": "24-98096"},
    )

    assert result.status_code == 503
    assert result.json()["error"]["message"] == "Email verification is unavailable"
    repository.issue_student_challenge.assert_not_called()


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

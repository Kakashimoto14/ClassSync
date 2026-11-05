import time
from unittest.mock import Mock

import pytest
from classync_contracts.identity import VerifiedPrincipal
from fastapi.testclient import TestClient

from services.gateway.app import main

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
        json={"student_id": "synthetic", "role": "administrator"},
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
            "/api/v1/auth/student-claims", headers=HEADERS, json={"student_id": "synthetic"}
        ).status_code
        == 403
    )
    repository.submit_claim.assert_not_called()


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
                "/api/v1/auth/student-claims", headers=HEADERS, json={"student_id": "synthetic"}
            ).status_code
            == 201
        )
    result = client.post(
        "/api/v1/auth/student-claims", headers=HEADERS, json={"student_id": "synthetic"}
    )
    assert result.status_code == 429
    assert result.headers["Retry-After"] == "60"
    assert repository.submit_claim.call_count == 10

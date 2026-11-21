from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from classync_contracts.identity import VerifiedPrincipal
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from services.gateway.app import onboarding_repository as module
from services.gateway.app.onboarding_repository import OnboardingRepository


class Result:
    def __init__(self, row=None, rowcount=1):
        self.row = row
        self.rowcount = rowcount

    def mappings(self):
        return self

    def first(self):
        return self.row


class Database:
    def __init__(self, *, membership=None, student=None, email_conflict=False, resend_seconds=17):
        self.membership = membership
        self.student = student
        self.email_conflict = email_conflict
        self.resend_seconds = resend_seconds
        self.student_params = None
        self.statements = []

    def execute(self, statement, params=None):
        query = str(statement)
        self.statements.append(query)
        if "FROM classsync_identity.memberships m" in query:
            return Result(self.membership)
        if (
            "FROM classsync_identity.students" in query
            and "SELECT id,person_id,registered_email" in query
        ):
            return Result(self.student)
        if "INSERT INTO classsync_identity.students" in query:
            self.student_params = params
            if self.email_conflict:
                raise IntegrityError(query, params, RuntimeError("unique registered email"))
            return Result(rowcount=1)
        if "SELECT resend_after" in query:
            return Result({"resend_after": datetime.now(UTC) + timedelta(seconds=17)})
        return Result()

    def scalar(self, statement, params=None):
        query = str(statement)
        self.statements.append(query)
        if "classsync_identity.tenants" in query:
            return 1
        if "EXTRACT(EPOCH" in query:
            return self.resend_seconds
        return None


def install_repository(monkeypatch, db):
    @contextmanager
    def transaction(_engine):
        yield db

    monkeypatch.setattr(module, "transaction", transaction)
    monkeypatch.setattr(module, "identity_context", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "audit_actor", lambda *_args, **_kwargs: None)
    return OnboardingRepository(object(), tenant="synthetic-tenant", project="synthetic-project")


def principal(provider="google.com"):
    return VerifiedPrincipal(
        uid="synthetic-uid", email="student@example.invalid", email_verified=True,
        sign_in_provider=provider,
    )


def review():
    return SimpleNamespace(
        student_identifier="23-01425", program="BSIT", year_level=2, courses=[object()],
    )


def student_row(source="cor_self_verified"):
    return {
        "id": "23-01425", "person_id": "synthetic-person",
        "registered_email": "student@example.invalid", "enrollment_status": "active",
        "verification_source": source,
    }


def test_cor_activation_returns_consistent_idempotent_membership_shape(monkeypatch):
    db = Database(
        membership={"student_id": "23-01425", "roles": ["student"], "state": "active",
                    "registered_email": "student@example.invalid",
                    "verification_source": "cor_self_verified"},
        student=student_row(),
    )
    repository = install_repository(monkeypatch, db)

    result = repository.activate_from_cor(principal(), review(), allow_self_verification=True,
                                          password_configured=True)

    assert result == {
        "status": "active", "verification_source": "cor_self_verified",
        "student_id": "23-01425", "email": "student@example.invalid",
    }


def test_cor_activation_preserves_existing_student_verification_provenance(monkeypatch):
    db = Database(student=student_row("registrar_roster"))
    repository = install_repository(monkeypatch, db)

    result = repository.activate_from_cor(principal(), review(), allow_self_verification=True,
                                          password_configured=False)

    assert result["verification_source"] == "registrar_roster"
    assert result["student_id"] == "23-01425"
    assert result["email"] == "student@example.invalid"


def test_cor_self_verification_persists_existing_password_provider(monkeypatch):
    db = Database()
    repository = install_repository(monkeypatch, db)

    result = repository.activate_from_cor(principal("password"), review(),
                                          allow_self_verification=True,
                                          password_configured=True)

    assert result["verification_source"] == "cor_self_verified"
    assert db.student_params["password_configured"] is True


def test_registered_email_unique_conflict_is_a_sanitized_409(monkeypatch):
    db = Database(email_conflict=True)
    repository = install_repository(monkeypatch, db)

    with pytest.raises(HTTPException) as caught:
        repository.activate_from_cor(principal(), review(), allow_self_verification=True,
                                      password_configured=False)

    assert caught.value.status_code == 409
    assert "student@example.invalid" not in str(caught.value.detail)


def test_student_challenge_rate_limit_uses_database_remaining_seconds(monkeypatch):
    db = Database(student=student_row(), resend_seconds=17)
    repository = install_repository(monkeypatch, db)

    with pytest.raises(HTTPException) as caught:
        repository.issue_student_challenge(principal(), "23-01425", "challenge", b"digest")

    assert caught.value.status_code == 429
    assert caught.value.headers["Retry-After"] == "17"
    assert any("EXTRACT(EPOCH" in statement for statement in db.statements)

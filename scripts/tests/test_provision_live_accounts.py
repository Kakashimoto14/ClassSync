from argparse import Namespace

import pytest
from sqlalchemy.engine import URL

from scripts import provision_live_accounts
from scripts.provision_live_accounts import (
    action_actor,
    generate_password,
    validate_database_target,
    validate_password,
    validate_student_identity,
    validate_student_roster_record,
)


def test_live_database_target_requires_tls_and_explicit_postgres_host():
    url, sslmode = validate_database_target(
        "postgresql://operator:secret@db.example.net:5432/classync?sslmode=require"
    )
    assert isinstance(url, URL)
    assert url.drivername == "postgresql+psycopg"
    assert sslmode == "require"


@pytest.mark.parametrize(
    "value",
    [
        "postgresql://operator:secret@db.example.net/classync",
        "postgresql://operator:secret@127.0.0.1/classync?sslmode=require",
        "sqlite:///classync.db",
        "postgresql://operator:secret@db.example.net/classync?sslmode=disable",
        "postgresql://operator:secret@db.example.net/classync?sslmode=require&options=-c+foo",
        "postgresql://db.example.net/classync?sslmode=require",
    ],
)
def test_live_database_target_rejects_unencrypted_or_ambiguous_targets(value):
    with pytest.raises(ValueError):
        validate_database_target(value)


def test_student_identity_requires_exact_student_format_and_institutional_email():
    assert validate_student_identity("23-01425", "juan.delacruz@student.pnm.edu.ph") == (
        "23-01425",
        "juan.delacruz@student.pnm.edu.ph",
    )
    for student_id, email in [
        ("2301425", "juan.delacruz@student.pnm.edu.ph"),
        ("23-01425", "Juan.delacruz@student.pnm.edu.ph"),
        ("23-01425", "juan-delacruz@student.pnm.edu.ph"),
        ("23-01425", "juan.delacruz@example.org"),
    ]:
        with pytest.raises(ValueError):
            validate_student_identity(student_id, email)


def test_student_provisioning_requires_existing_active_matching_roster_evidence():
    assert (
        validate_student_roster_record(
            "23-01425",
            "juan.delacruz@student.pnm.edu.ph",
            {
                "id": "23-01425",
                "registered_email": "juan.delacruz@student.pnm.edu.ph",
                "enrollment_status": "active",
                "person_id": "person-123",
                "password_configured": False,
            },
        )
        == "person-123"
    )
    invalid_rows = [
        None,
        {
            "id": "23-01425",
            "registered_email": None,
            "enrollment_status": "unverified",
            "person_id": "p",
        },
        {
            "id": "23-01425",
            "registered_email": "other@student.pnm.edu.ph",
            "enrollment_status": "active",
            "person_id": "p",
        },
        {
            "id": "23-01425",
            "registered_email": "juan.delacruz@student.pnm.edu.ph",
            "enrollment_status": "inactive",
            "person_id": "p",
        },
    ]
    for row in invalid_rows:
        with pytest.raises(ValueError):
            validate_student_roster_record("23-01425", "juan.delacruz@student.pnm.edu.ph", row)


def test_generated_credentials_are_high_entropy_and_printable():
    value = generate_password()
    assert len(value) >= 24
    assert value.isascii()
    assert len(set(value)) >= 15


def test_password_validator_rejects_control_characters():
    with pytest.raises(ValueError):
        validate_password("valid-password-\x00")


def test_membership_changes_require_an_attributable_administrator_or_explicit_bootstrap():
    assert (
        action_actor(
            operator_uid="firebase-admin-uid", bootstrap_first_admin=False, admin_only=False
        )
        == "firebase-admin-uid"
    )
    assert (
        action_actor(operator_uid=None, bootstrap_first_admin=True, admin_only=True)
        == "bootstrap:provision_live_accounts"
    )
    for operator_uid, bootstrap, admin_only in [(None, False, False), (None, True, False)]:
        with pytest.raises(ValueError):
            action_actor(
                operator_uid=operator_uid, bootstrap_first_admin=bootstrap, admin_only=admin_only
            )


def test_first_administrator_bootstrap_rejects_mixed_role_provisioning(monkeypatch, capsys):
    monkeypatch.setattr(
        provision_live_accounts,
        "_arguments",
        lambda: Namespace(
            confirm_live_provisioning=provision_live_accounts.CONFIRMATION_TEXT,
            confirm_tenant_id="tenant-a",
            tenant_id="tenant-a",
            admin_email="admin@example.edu",
            teacher_email="faculty@example.edu",
            student_id=None,
            student_email=None,
            teacher_faculty_id="faculty-a",
            bootstrap_first_administrator=True,
        ),
    )

    assert provision_live_accounts.main() == 2
    assert "only an Administrator account" in capsys.readouterr().err

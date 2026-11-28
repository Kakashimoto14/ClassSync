"""Argument gates, credential handling and throttling for seeded-login provisioning."""

import csv
import string
from types import SimpleNamespace

import pytest
from firebase_admin import auth, exceptions

from scripts import provision_seeded_logins as seeded
from scripts.lib.identity_provisioning import validate_password

BASE = ["--tenant-id", "cdm", "--operator-uid", "admin-uid"]


def test_generated_passwords_satisfy_the_web_checklist_and_never_look_like_formulas():
    values = {seeded.generate_password() for _ in range(200)}
    assert len(values) == 200
    for value in values:
        assert len(value) == 20 and value[0] in string.ascii_letters
        assert validate_password(value) == value
        for pool in (string.ascii_uppercase, string.ascii_lowercase, string.digits,
                     seeded.SPECIALS):
            assert set(value) & set(pool)


def test_masking_hides_the_mailbox_name():
    assert seeded.mask("student.24.00101@student.pnm.edu.ph") == "s***@student.pnm.edu.ph"


def test_seed_provenance_covers_the_whole_seed_with_unique_teacher_mailboxes():
    students, faculty = seeded.seeded_identities()
    assert len(students) == 432 and len(faculty) == 57
    assert len({item["slug"] for item in faculty.values()}) == len(faculty)
    assert students["24-00101"]["registered_email"] == "student.24.00101@student.pnm.edu.ph"
    assert "maria.santos" in {item["slug"] for item in faculty.values()}


def test_dry_run_is_the_default_and_apply_is_explicit():
    options = seeded.parse_arguments([*BASE, "--students", "2"])
    assert options.apply is False and options.students == 2 and options.teachers is None


@pytest.mark.parametrize(
    "extra",
    [
        [],
        ["--all-seeded", "--program", "BSIT"],
        ["--all-seeded", "--teachers", "1"],
        ["--students", "-1"],
        ["--all-seeded", "--apply"],
        ["--all-seeded", "--apply", "--confirm-defense-tenant", "other"],
        ["--all-seeded", "--faculty-email-domain", "no-dot"],
        ["--all-seeded", "--faculty-email-domain", "person@example.edu"],
        ["--all-seeded", "--dry-run", "--apply", "--confirm-defense-tenant", "cdm"],
    ],
)
def test_ambiguous_or_unconfirmed_arguments_are_refused(extra):
    with pytest.raises(SystemExit):
        seeded.parse_arguments([*BASE, *extra])


def test_tenant_and_operator_have_no_implicit_default(monkeypatch):
    monkeypatch.delenv("INSTITUTIONAL_TENANT_ID", raising=False)
    for argv in (["--operator-uid", "a", "--all-seeded"], ["--tenant-id", "cdm", "--all-seeded"]):
        with pytest.raises(SystemExit):
            seeded.parse_arguments(argv)


def _environment(monkeypatch, **values):
    for name in ("MIGRATION_DATABASE_URL", "DATABASE_URL", "FIREBASE_SERVICE_ACCOUNT_JSON",
                 "FIREBASE_AUTH_EMULATOR_HOST"):
        monkeypatch.delenv(name, raising=False)
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(seeded, "initialize_firebase",
                        lambda *_: pytest.fail("Firebase must not be initialised"))
    monkeypatch.setattr(seeded, "postgres_engine",
                        lambda *_, **__: pytest.fail("no database connection expected"))


def test_missing_configuration_is_refused_before_any_connection(monkeypatch, capsys):
    _environment(monkeypatch)
    assert seeded.main([*BASE, "--all-seeded"]) == 2
    assert "FIREBASE_SERVICE_ACCOUNT_JSON" in capsys.readouterr().err


def test_the_auth_emulator_is_refused(monkeypatch, capsys):
    _environment(
        monkeypatch,
        DATABASE_URL="postgresql://o:secret@db.example.net:5432/c?sslmode=require",
        FIREBASE_SERVICE_ACCOUNT_JSON="{}",
        FIREBASE_AUTH_EMULATOR_HOST="127.0.0.1:9099",
    )
    assert seeded.main([*BASE, "--all-seeded"]) == 2
    assert "Emulator" in capsys.readouterr().err


def test_an_unencrypted_target_fails_without_echoing_secrets(monkeypatch, capsys):
    _environment(
        monkeypatch,
        DATABASE_URL="postgresql://o:topsecret@db.example.net:5432/c",
        FIREBASE_SERVICE_ACCOUNT_JSON="{}",
    )
    assert seeded.main([*BASE, "--all-seeded"]) == 1
    assert "topsecret" not in capsys.readouterr().err


def test_only_gitignored_paths_may_receive_passwords():
    assert seeded.is_git_ignored(seeded.CREDENTIALS_PATH)
    assert not seeded.is_git_ignored(seeded.ROOT / "docs" / "seeded-logins.csv")


def _target(email, name="Aira Santos", role="student"):
    return seeded.Target(role=role, record_id="24-00101", person_id="p", email=email,
                         name=name, sections="BSIT-3A")


def _rows(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["email"]: row for row in csv.DictReader(handle)}


def test_credential_file_merges_and_never_blanks_a_stored_password(tmp_path):
    path = tmp_path / "logins.csv"
    first = seeded.CredentialFile(path)
    assert not path.exists()  # checking writability creates no file
    first.record(_target("a@x.edu"), "Password-one-1!", "created")
    second = seeded.CredentialFile(path)
    second.record(_target("b@x.edu", name="=HYPERLINK(1)"), "Password-two-2!", "created")
    second.record(_target("a@x.edu"), "", "existing password kept")
    rows = _rows(path)
    assert rows["a@x.edu"]["password"] == "Password-one-1!"
    assert rows["b@x.edu"]["name"] == "'=HYPERLINK(1)"
    assert rows["b@x.edu"]["student_number"] == "24-00101"
    second.record(_target("a@x.edu"), "Password-new-3!", "password reset")
    assert _rows(path)["a@x.edu"]["password"] == "Password-new-3!"
    assert not path.with_name("logins.csv.tmp").exists()


def test_an_unwritable_credential_file_stops_the_run(tmp_path, monkeypatch):
    store = seeded.CredentialFile(tmp_path / "logins.csv")

    def locked(*_):
        raise PermissionError("in use")

    monkeypatch.setattr(seeded.os, "replace", locked)
    with pytest.raises(seeded.Refusal, match="--rotate-passwords"):
        store.record(_target("a@x.edu"), "Password-one-1!", "created")


def test_rate_limited_calls_back_off_and_retry():
    waits, calls = [], []

    def get_user_by_email(email, app):
        calls.append(email)
        if len(calls) < 3:
            raise exceptions.ResourceExhaustedError("slow down")
        return "user"

    module = SimpleNamespace(get_user_by_email=get_user_by_email,
                             UserNotFoundError=auth.UserNotFoundError)
    accounts = seeded.FirebaseAccounts(object(), module, sleep=waits.append)
    assert accounts.find("a@x.edu") == "user"
    assert waits == [0.2, 1, 0.2, 2, 0.2]


def test_persistent_rate_limiting_surfaces_the_error():
    def delete_user(uid, app):
        raise exceptions.UnavailableError("down")

    accounts = seeded.FirebaseAccounts(
        object(), SimpleNamespace(delete_user=delete_user), sleep=lambda _: None, retries=2
    )
    with pytest.raises(exceptions.UnavailableError):
        accounts.delete("uid")

"""Portable publication adapter boundaries; no database, server or solver is started."""

import importlib
import inspect
import json
import sqlite3
from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace

import pytest
from classync_contracts.identity import MembershipAuthorizationError, VerifiedPrincipal
from classync_contracts.publication import PublicationCommand, RoomRestriction
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError

from services.scheduling.app.draft_rules import DraftError, digest, encode
from services.scheduling.tests.test_calendar import configuration
from services.scheduling.tests.test_publication_rules import publication_row


def repository_type():
    return importlib.import_module(
        "services.scheduling.app.postgres_publication_repository"
    ).PostgresPublicationRepository


def test_constructor_never_connects_migrates_or_opens_sqlite(monkeypatch):
    class NoDatabase:
        def __getattr__(self, name):
            pytest.fail(f"Constructor accessed database capability: {name}")

    monkeypatch.setattr(sqlite3, "connect", lambda *_a, **_k: pytest.fail("SQLite fallback"))
    repository_type()(NoDatabase(), tenant_id="tenant-a", firebase_project_id="synthetic-project",
                      principal=VerifiedPrincipal(uid="uid-admin"))


@pytest.mark.parametrize("principal", [None, "uid-admin", {"uid": "uid-admin"}])
def test_unverified_principals_never_reach_storage(principal):
    with pytest.raises(ValueError, match="verified principal"):
        repository_type()(object(), tenant_id="tenant-a", firebase_project_id="synthetic-project",
                          principal=principal)


@pytest.mark.parametrize("field", ["tenant_id", "firebase_project_id"])
@pytest.mark.parametrize("value", [None, "", " ", "x" * 129])
def test_server_binding_is_validated_without_database(field, value):
    values = {"tenant_id": "tenant-a", "firebase_project_id": "synthetic-project", field: value}
    with pytest.raises(ValueError):
        repository_type()(object(), principal=VerifiedPrincipal(uid="uid-admin"), **values)


@pytest.fixture
def repository():
    return repository_type()(object(), tenant_id="tenant-a",
                             firebase_project_id="synthetic-project",
                             principal=VerifiedPrincipal(uid="uid-admin"))


def command():
    return PublicationCommand(draft_id="owned-draft", expected_version=0,
                              expected_academic_revision=1, idempotency_key="synthetic-publish-key",
                              calendar=configuration().calendar)


def restriction():
    return RoomRestriction(id="synthetic-room-restriction", room_id="synthetic-room",
                           dataset="synthetic", starts_at="2026-10-05T08:00:00+08:00",
                           ends_at="2026-10-05T09:00:00+08:00", kind="reservation",
                           reason="Invented test fixture", expected_revision=0)


def operation(repository, name):
    if name == "history":
        return repository.history("synthetic", "period-a")
    if name == "admin_calendar":
        return repository.admin_calendar("synthetic", "period-a", date(2026, 10, 5),
                                         date(2026, 10, 7))
    if name == "publish":
        return repository.publish(command(), commit=True)
    if name == "review":
        return repository.publish(command(), commit=False)
    return repository.put_restriction(restriction())


@pytest.fixture
def prohibit_transaction(monkeypatch):
    module = importlib.import_module("services.scheduling.app.postgres_publication_repository")
    monkeypatch.setattr(module, "transaction",
                        lambda *_a, **_k: pytest.fail("Invalid input reached database"))


@pytest.mark.parametrize("dataset", ["private", "", "INSTITUTIONAL", None])
@pytest.mark.parametrize("method", ["history", "admin_calendar"])
def test_invalid_dataset_is_rejected_before_database(repository, prohibit_transaction,
                                                     dataset, method):
    with pytest.raises(DraftError) as denied:
        if method == "history":
            repository.history(dataset, "period-a")
        else:
            repository.admin_calendar(dataset, "period-a", date(2026, 10, 5), date(2026, 10, 7))
    assert denied.value.status == 422


@pytest.mark.parametrize("period", [None, "", " ", "x" * 121])
@pytest.mark.parametrize("method", ["history", "admin_calendar"])
def test_invalid_period_is_rejected_before_database(repository, prohibit_transaction,
                                                    period, method):
    with pytest.raises(DraftError) as denied:
        if method == "history":
            repository.history("synthetic", period)
        else:
            repository.admin_calendar("synthetic", period, date(2026, 10, 5), date(2026, 10, 7))
    assert denied.value.status == 422


@pytest.mark.parametrize("start,end", [(date(2026, 10, 7), date(2026, 10, 5)),
                                       (date(2026, 10, 1), date(2026, 12, 31))])
def test_invalid_projection_range_is_rejected_before_database(repository, prohibit_transaction,
                                                              start, end):
    with pytest.raises(DraftError) as denied:
        repository.admin_calendar("synthetic", "period-a", start, end)
    assert (denied.value.status, denied.value.code) == (422, "calendar_range")


@pytest.mark.parametrize("commit", [False, True])
def test_development_source_cannot_authorize_pg_publication(
    repository, prohibit_transaction, commit,
):
    body = command().model_copy(update={"source": "academic-sandbox"})
    with pytest.raises(DraftError) as denied:
        repository.publish(body, commit=commit)
    assert denied.value.status == 422


@pytest.mark.parametrize("commit", [False, True])
def test_client_cannot_assign_publication_version(repository, prohibit_transaction, commit):
    body = command()
    body.calendar.published_version = "client-forged-version"
    with pytest.raises(DraftError) as denied:
        repository.publish(body, commit=commit)
    assert (denied.value.status, denied.value.code) == (422, "client_version")


@pytest.mark.parametrize("changes", [
    {"dataset": "private"}, {"expected_version": -1}, {"expected_academic_revision": 0},
    {"idempotency_key": "short"}, {"draft_id": ""},
])
@pytest.mark.parametrize("commit", [False, True])
def test_unchecked_model_copy_cannot_bypass_publication_contract(
    repository, prohibit_transaction, changes, commit,
):
    with pytest.raises(DraftError) as denied:
        repository.publish(command().model_copy(update=changes), commit=commit)
    assert denied.value.status == 422


@pytest.mark.parametrize("changes", [
    {"dataset": "private"}, {"expected_revision": -1}, {"kind": "unverified-policy"},
    {"id": ""}, {"room_id": ""},
])
def test_unchecked_model_copy_cannot_bypass_restriction_contract(
    repository, prohibit_transaction, changes,
):
    with pytest.raises(DraftError) as denied:
        repository.put_restriction(restriction().model_copy(update=changes))
    assert denied.value.status == 422


@pytest.mark.parametrize("changes", [
    {"starts_at": "2026-10-05T08:00:00"}, {"ends_at": "2026-10-05T09:00:00"},
    {"starts_at": "2026-10-05T10:00:00+08:00"},
    {"ends_at": "2026-10-05T08:00:00+08:00"},
    {"ends_at": "2027-10-07T09:00:00+08:00"},
    {"starts_at": "malformed-time"},
])
def test_naive_reversed_or_unbounded_restriction_interval_never_reaches_database(
    repository, prohibit_transaction, changes,
):
    with pytest.raises(DraftError) as denied:
        repository.put_restriction(restriction().model_copy(update=changes))
    assert (denied.value.status, denied.value.code) == (422, "restriction_interval")


@pytest.mark.parametrize("name", ["history", "admin_calendar", "publish", "review", "restriction"])
def test_database_outage_is_typed_unavailable_never_empty_or_success(repository, monkeypatch, name):
    module = importlib.import_module("services.scheduling.app.postgres_publication_repository")

    @contextmanager
    def unavailable(_engine):
        raise OperationalError("synthetic connection failure", {}, Exception("offline"))
        yield

    monkeypatch.setattr(module, "transaction", unavailable)
    with pytest.raises(DraftError) as denied:
        operation(repository, name)
    assert (denied.value.status, denied.value.code) == (503, "persistence_unavailable")


@pytest.mark.parametrize("sqlstate", ["40001", "40P01", "55P03"])
@pytest.mark.parametrize("commit", [False, True])
def test_serialization_deadlock_or_lock_timeout_is_observable_conflict(
    repository, monkeypatch, sqlstate, commit,
):
    module = importlib.import_module("services.scheduling.app.postgres_publication_repository")

    @contextmanager
    def competing_change(_engine):
        raise DBAPIError("synthetic transaction conflict", {}, SimpleNamespace(sqlstate=sqlstate))
        yield

    monkeypatch.setattr(module, "transaction", competing_change)
    with pytest.raises(DraftError) as denied:
        repository.publish(command(), commit=commit)
    assert (denied.value.status, denied.value.code) == (409, "publication_version_conflict")


def test_database_integrity_failure_is_observable_conflict(repository, monkeypatch):
    module = importlib.import_module("services.scheduling.app.postgres_publication_repository")

    @contextmanager
    def conflicting_integrity(_engine):
        raise IntegrityError("synthetic integrity conflict", {}, SimpleNamespace(sqlstate="23505"))
        yield

    monkeypatch.setattr(module, "transaction", conflicting_integrity)
    with pytest.raises(DraftError) as denied:
        repository.publish(command(), commit=True)
    assert (denied.value.status, denied.value.code) == (409, "publication_integrity")


@pytest.mark.parametrize("name", ["history", "admin_calendar", "publish", "review", "restriction"])
def test_missing_current_admin_is_typed_denial_never_empty_or_success(
    repository, monkeypatch, name,
):
    module = importlib.import_module("services.scheduling.app.postgres_publication_repository")

    class NoMembership:
        def execute(self, *_a, **_k):
            return self

        def scalar(self, *_a, **_k):
            return None

        def scalar_one_or_none(self):
            return None

        def one_or_none(self):
            return None

        def mappings(self):
            return self

    @contextmanager
    def no_current_admin(_engine):
        yield NoMembership()

    monkeypatch.setattr(module, "transaction", no_current_admin)
    with pytest.raises(MembershipAuthorizationError) as denied:
        operation(repository, name)
    assert denied.value.code == "membership_denied"


@pytest.mark.parametrize("method", ["history", "admin_calendar", "publish", "put_restriction"])
def test_public_operations_accept_no_client_actor_tenant_or_projection_grants(method):
    parameters = inspect.signature(getattr(repository_type(), method)).parameters
    assert not {"actor", "owner", "tenant", "tenant_id", "viewer", "draft"} & parameters.keys()
    assert not any(p.kind == inspect.Parameter.VAR_KEYWORD for p in parameters.values())


@pytest.mark.parametrize("tamper", ["malformed-json", "missing-draft", "missing-calendar",
                                  "invalid-draft", "invalid-calendar", "non-object",
                                  "missing-review", "invalid-review", "forged-input-hash",
                                  "missing-assignments", "unknown-solver-status"])
def test_checksum_consistent_corrupt_publication_is_typed_integrity_failure(repository, tamper):
    row = publication_row()
    payload = json.loads(row["payload"])
    if tamper == "malformed-json":
        row["payload"] = "{malformed"
    elif tamper == "non-object":
        row["payload"] = "null"
    else:
        if tamper == "forged-input-hash":
            payload["draft"]["generation_result"]["input_hash"] = "0" * 64
        elif tamper == "missing-assignments":
            payload["draft"]["generation_result"]["assignments"] = []
        elif tamper == "unknown-solver-status":
            payload["draft"]["generation_result"]["solver_status"] = "unknown"
        else:
            action, field = tamper.split("-")
            if action == "missing":
                del payload[field]
            else:
                payload[field] = [] if field == "review" else {}
        row["payload"] = encode(payload)
    row["checksum"] = digest(row["payload"])
    with pytest.raises(DraftError) as denied:
        repository.decode(row)
    assert (denied.value.status, denied.value.code) == (409, "publication_integrity")


def test_original_replay_receipt_stays_equal_when_history_is_superseded(repository, monkeypatch):
    row, db = publication_row(), object()
    original_payload = row["payload"]
    monkeypatch.setattr(repository, "head", lambda *_args: 1)
    first = repository.receipt(row, db)
    assert first["status"] == "published"
    assert repository.summary(row, db)["status"] == "published"
    monkeypatch.setattr(repository, "head", lambda *_args: 2)
    assert repository.receipt(row, db) == first
    assert repository.summary(row, db)["status"] == "superseded"
    assert row["payload"] == original_payload


def stored_restriction(value=None):
    payload = encode(value if value is not None else (
        restriction().model_dump(exclude={"expected_revision"}) | {"revision": 1}
    ))
    return {"payload": payload, "checksum": digest(payload)}


def test_stored_restriction_round_trip_preserves_revision_and_scope(repository):
    value = restriction().model_dump(exclude={"expected_revision"}) | {"revision": 2}
    assert repository.restriction_value(stored_restriction(value)) == value


@pytest.mark.parametrize("changes", [
    {"revision": 0}, {"revision": -1}, {"revision": True}, {"revision": "1"},
    {"kind": "unverified-policy"}, {"dataset": "private"}, {"room_id": ""},
    {"starts_at": "2026-10-05T08:00:00"}, {"ends_at": "2026-10-05T09:00:00"},
    {"starts_at": "2026-10-05T10:00:00+08:00"},
    {"ends_at": "2027-10-07T09:00:00+08:00"},
])
def test_checksum_consistent_invalid_stored_restriction_is_typed_conflict(repository, changes):
    value = restriction().model_dump(exclude={"expected_revision"}) | {"revision": 1} | changes
    with pytest.raises(DraftError) as denied:
        repository.restriction_value(stored_restriction(value))
    assert (denied.value.status, denied.value.code) == (409, "restriction_integrity")


@pytest.mark.parametrize("missing", ["reason", "revision", "starts_at"])
def test_checksum_consistent_incomplete_stored_restriction_is_typed_conflict(repository, missing):
    value = restriction().model_dump(exclude={"expected_revision"}) | {"revision": 1}
    del value[missing]
    with pytest.raises(DraftError) as denied:
        repository.restriction_value(stored_restriction(value))
    assert (denied.value.status, denied.value.code) == (409, "restriction_integrity")


@pytest.mark.parametrize("payload", ["{invalid", "null", "[]"])
def test_checksum_consistent_unreadable_stored_restriction_is_typed_conflict(repository, payload):
    with pytest.raises(DraftError) as denied:
        repository.restriction_value({"payload": payload, "checksum": digest(payload)})
    assert (denied.value.status, denied.value.code) == (409, "restriction_integrity")


def test_stored_restriction_checksum_is_checked_before_use(repository):
    row = stored_restriction()
    row["checksum"] = "0" * 64
    with pytest.raises(DraftError) as denied:
        repository.restriction_value(row)
    assert (denied.value.status, denied.value.code) == (409, "restriction_integrity")

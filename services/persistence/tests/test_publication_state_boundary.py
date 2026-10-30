"""Portable publication-state qualification boundaries; no PostgreSQL or solver startup."""

import importlib
import json
import tempfile
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import DBAPIError

from scripts import postgres_publication_state_qualification as publication
from scripts.postgres_disposable import create_root


def test_unmarked_cluster_is_rejected_before_engine_or_identity(monkeypatch, tmp_path):
    module = importlib.import_module("scripts.postgres_publication_state_qualification")
    monkeypatch.setattr(module, "engine_for", lambda *_a, **_k: pytest.fail("Opened database"))
    monkeypatch.setattr(module, "identity_exercise", lambda *_a: pytest.fail("Identity mutated"))
    connection = SimpleNamespace(root=tmp_path / "unmarked")
    with pytest.raises((RuntimeError, ValueError, FileNotFoundError)):
        module.exercise(connection)


def test_existing_evidence_is_preserved_without_overwrite(tmp_path):
    module = importlib.import_module("scripts.postgres_publication_state_qualification")
    target = Path(tmp_path) / "evidence.json"
    target.write_text("original evidence", encoding="utf-8")
    with pytest.raises(FileExistsError):
        module.write_new_evidence(target, {"invented": "replacement"})
    assert target.read_text(encoding="utf-8") == "original evidence"


@pytest.fixture
def owned_connection(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    return SimpleNamespace(root=create_root(tmp_path), port=59123, owner="synthetic-owner")


def test_guard_accepts_only_new_marked_root(owned_connection):
    assert publication.checked_connection(owned_connection) == owned_connection.root


@pytest.mark.parametrize("tamper", ["marker", "outside", "missing"])
def test_changed_marker_or_original_target_rejected_before_identity(
    owned_connection, tmp_path, monkeypatch, tamper,
):
    monkeypatch.setattr(publication, "identity_exercise", lambda *_a: pytest.fail("Identity ran"))
    monkeypatch.setattr(publication, "engine_for", lambda *_a, **_k: pytest.fail("Engine opened"))
    if tamper == "marker":
        (owned_connection.root / "classsync-marker.json").write_text("{}")
    elif tamper == "outside":
        owned_connection.root = tmp_path
    else:
        (owned_connection.root / "classsync-marker.json").unlink()
    with pytest.raises(ValueError):
        publication.exercise(owned_connection)


def test_exact_server_binding_and_explicit_migration_are_required(owned_connection):
    root = owned_connection.root
    expected = [str(root / "data"), owned_connection.owner, owned_connection.port, "127.0.0.1"]

    class Database:
        observed = expected
        migration = publication.MIGRATION

        def execute(self, _sql):
            return SimpleNamespace(one=lambda: self.observed)

        def scalar(self, _sql):
            return self.migration

    db = Database()
    publication.check_binding(db, owned_connection, root)
    for index, value in enumerate([str(root.parent / "original"), "wrong-owner", 5432, "remote"]):
        db.observed = expected[:]
        db.observed[index] = value
        with pytest.raises(RuntimeError, match="binding mismatch"):
            publication.check_binding(db, owned_connection, root)
    db.observed, db.migration = expected, "0006_scheduling_drafts"
    with pytest.raises(RuntimeError, match="scope drift"):
        publication.check_binding(db, owned_connection, root)


def synthetic_draft():
    payload = {"id": "generated-draft", "period_id": "generated-period", "creator": "uid-admin",
               "private_fixture_marker": "synthetic-data-only"}
    return SimpleNamespace(id=payload["id"], period_id=payload["period_id"],
                           creator=payload["creator"], model_dump=lambda **_k: deepcopy(payload))


def test_command_payload_checksums_bind_the_full_generated_envelope():
    row = publication.version_parameters(synthetic_draft(), revision=2, academic_revision=3,
                                         key="synthetic-publish-key")
    command, payload = json.loads(row["command"]), json.loads(row["payload"])
    assert publication.digest(row["command"]) == row["request_hash"]
    assert publication.digest(row["payload"]) == row["checksum"]
    assert publication.encode(command) == row["command"]
    assert publication.encode(payload) == row["payload"]
    assert command["expected_version"] == row["revision"] - 1 == 1
    assert command["expected_academic_revision"] == row["academic_revision"] == 3
    assert command["draft_id"] == row["draft_id"] == payload["draft"]["id"]
    assert payload["draft"]["creator"] == row["actor_uid"] == row["owner_uid"]
    assert payload["calendar"] == command["calendar"]
    assert payload["draft"]["private_fixture_marker"] == "synthetic-data-only"
    assert row["created_at"].utcoffset().total_seconds() == 0
    assert "sequence" not in row and set(row) == set(publication.VERSION_COLUMNS)


@pytest.mark.parametrize("revision,academic_revision", [(0, 1), (1, 0), (-1, 1)])
def test_invalid_command_revision_is_rejected_without_database(revision, academic_revision):
    with pytest.raises(ValueError):
        publication.version_parameters(synthetic_draft(), revision=revision,
                                       academic_revision=academic_revision)


def test_generated_identifiers_and_keys_are_fresh_not_client_supplied():
    first = publication.version_parameters(synthetic_draft())
    second = publication.version_parameters(synthetic_draft())
    assert first["id"] != second["id"]
    assert first["idempotency_key"] != second["idempotency_key"]


@pytest.mark.parametrize("tamper", ["checksum", "payload", "command", "owner_uid", "revision",
                                  "extra", "missing", "sequence-zero"])
def test_exact_persisted_envelope_and_server_sequence_are_checked(tamper):
    parameters = publication.version_parameters(synthetic_draft())
    row = parameters | {"sequence": 1}
    publication.check_saved(row, parameters)
    if tamper == "extra":
        row["unexpected"] = "value"
    elif tamper == "missing":
        del row["actor_uid"]
    elif tamper == "sequence-zero":
        row["sequence"] = 0
    else:
        row[tamper] = "different"
    with pytest.raises(RuntimeError, match="envelope or generated sequence changed"):
        publication.check_saved(row, parameters)


@pytest.mark.parametrize("actual,expected,passes", [("42501", "42501", True),
                                                  ("23514", "42501", False)])
def test_negative_probes_verify_exact_sqlstate(monkeypatch, actual, expected, passes):
    @contextmanager
    def transaction(_engine):
        yield object()

    def operation(_db):
        raise DBAPIError("synthetic", {}, SimpleNamespace(sqlstate=actual))

    monkeypatch.setattr(publication, "transaction", transaction)
    monkeypatch.setattr(publication, "context", lambda *_a, **_k: None)
    if passes:
        publication.expect_sqlstate(object(), operation, expected)
    else:
        with pytest.raises(RuntimeError, match="SQLSTATE"):
            publication.expect_sqlstate(object(), operation, expected)


def test_unexpected_negative_probe_success_rolls_back_before_failing(monkeypatch):
    events = []

    @contextmanager
    def transaction(_engine):
        try:
            yield object()
            events.append("commit")
        except RuntimeError:
            events.append("rollback")
            raise

    monkeypatch.setattr(publication, "transaction", transaction)
    monkeypatch.setattr(publication, "context", lambda *_a, **_k: None)
    with pytest.raises(RuntimeError, match="unexpectedly succeeded"):
        publication.expect_sqlstate(object(), lambda _db: events.append("write"), "42501")
    assert events == ["write", "rollback"]


def test_orphan_probe_forces_deferred_constraint_after_insert_and_rolls_back(monkeypatch):
    events = []
    parameters = publication.version_parameters(synthetic_draft(), revision=3)

    class Database:
        def execute(self, sql, values=None):
            if sql is publication.INSERT_VERSION:
                assert values == parameters
                events.append("insert-version")
            else:
                assert str(sql) == "SET CONSTRAINTS ALL IMMEDIATE"
                events.append("force-deferred-check")
                raise DBAPIError("synthetic deferred check", {},
                                 SimpleNamespace(sqlstate="23514"))

    @contextmanager
    def transaction(_engine):
        try:
            yield Database()
        except DBAPIError:
            events.append("rollback")
            raise
        else:
            pytest.fail("Orphan negative probe committed")

    monkeypatch.setattr(publication, "transaction", transaction)
    monkeypatch.setattr(publication, "context", lambda *_a, **_k: None)
    publication.expect_sqlstate(object(), lambda db: publication.force_orphan_constraint(
        db, parameters,
    ), "23514")
    assert events == ["insert-version", "force-deferred-check", "rollback"]


def test_unenforced_deferred_orphan_probe_fails_and_rolls_back(monkeypatch):
    events = []

    class Database:
        def execute(self, sql, _values=None):
            events.append("insert" if sql is publication.INSERT_VERSION else str(sql))

    @contextmanager
    def transaction(_engine):
        try:
            yield Database()
        except RuntimeError:
            events.append("rollback")
            raise
        else:
            pytest.fail("Unexpected orphan success committed")

    monkeypatch.setattr(publication, "transaction", transaction)
    monkeypatch.setattr(publication, "context", lambda *_a, **_k: None)
    with pytest.raises(RuntimeError, match="unexpectedly succeeded"):
        publication.expect_sqlstate(object(), lambda db: publication.force_orphan_constraint(
            db, publication.version_parameters(synthetic_draft(), revision=3),
        ), "23514")
    assert events == ["insert", "SET CONSTRAINTS ALL IMMEDIATE", "rollback"]


@pytest.mark.parametrize("existing,parent_missing", [(True, False), (False, True)])
def test_cli_invalid_output_rejected_before_cluster_start(tmp_path, monkeypatch,
                                                        existing, parent_missing):
    target = tmp_path / ("missing/evidence.json" if parent_missing else "evidence.json")
    if existing:
        target.write_text("preserve", encoding="utf-8")
    monkeypatch.setattr(publication, "qualify", lambda *_a: pytest.fail("Cluster started"))
    with pytest.raises(RuntimeError, match="New output required"):
        publication.main(["--bin", str(tmp_path), "--output", str(target)])


def test_cluster_failure_cannot_write_success_evidence(tmp_path, monkeypatch):
    target = tmp_path / "never-success.json"

    def failed(*_args):
        raise RuntimeError("synthetic stopped cluster failure")

    monkeypatch.setattr(publication, "qualify", failed)
    with pytest.raises(RuntimeError, match="cluster failure"):
        publication.main(["--bin", str(tmp_path), "--output", str(target)])
    assert not target.exists()

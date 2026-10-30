"""Legacy SQLite history maps only to non-current, non-replayable archive rows."""

import hashlib
import json
from contextlib import contextmanager
from importlib import import_module
from pathlib import Path

import pytest
from classync_contracts.identity import MembershipAuthorizationError, VerifiedPrincipal
from classync_persistence.legacy_publication_archive import (
    LegacyPublicationError,
    archive_legacy_publications,
    import_legacy_publications,
)


@pytest.fixture
def legacy_row():
    payload = json.dumps(
        {
            "draft": {
                "id": "draft-a",
                "period_id": "term-a",
                "creator": "source-admin",
            },
            "calendar": {"academic_year": "generated-fixture"},
            "review": {"valid": True},
        },
        separators=(",", ":"),
    )
    return {
        "sequence": 8,
        "id": "legacy-version-8",
        "tenant": "source-tenant",
        "dataset": "synthetic",
        "period_id": "term-a",
        "revision": 3,
        "draft_id": "draft-a",
        "actor": "source-admin",
        "created_at": "2026-10-01T10:00:00+08:00",
        "idempotency_key": "legacy-command-8",
        # The source stores this hash but not the canonical command preimage.
        "request_hash": hashlib.sha256(b"unrecoverable source command").hexdigest(),
        "payload": payload,
        "checksum": hashlib.sha256(payload.encode()).hexdigest(),
    }


def mapping():
    return {("source-tenant", "source-admin"): ("target-tenant", "target-admin")}


def test_archive_preserves_opaque_hash_and_payload_without_claiming_replay_or_current_state(
    legacy_row,
):
    archived = archive_legacy_publications([legacy_row], owner_map=mapping())[0]
    assert archived.request_hash == legacy_row["request_hash"]
    assert archived.payload == legacy_row["payload"]
    assert archived.checksum == legacy_row["checksum"]
    assert (archived.tenant_id, archived.owner_uid) == ("target-tenant", "target-admin")
    assert archived.replayable is False
    assert archived.current is False
    assert not hasattr(archived, "command")
    assert not hasattr(archived, "academic_revision")


def test_archive_requires_explicit_owner_mapping_and_rejects_ambiguous_keys(legacy_row):
    with pytest.raises(LegacyPublicationError, match="explicit target"):
        archive_legacy_publications([legacy_row], owner_map={})
    second = legacy_row | {"sequence": 9, "id": "legacy-version-9"}
    with pytest.raises(LegacyPublicationError, match="idempotency key is duplicated"):
        archive_legacy_publications([legacy_row, second], owner_map=mapping())


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("checksum", "0" * 64, "checksum does not match"),
        ("request_hash", "not-a-hash", "SHA-256"),
        ("revision", 0, "revision must be positive"),
        ("sequence", True, "sequence must be positive"),
        ("created_at", "2026-10-01T10:00:00", "timezone"),
    ],
)
def test_archive_rejects_corrupt_or_incomplete_rows(legacy_row, field, value, message):
    with pytest.raises(LegacyPublicationError, match=message):
        archive_legacy_publications([legacy_row | {field: value}], owner_map=mapping())


def test_archive_rejects_payload_scope_mismatch(legacy_row):
    payload = json.loads(legacy_row["payload"])
    payload["draft"]["period_id"] = "other-term"
    encoded = json.dumps(payload, separators=(",", ":"))
    row = legacy_row | {
        "payload": encoded,
        "checksum": hashlib.sha256(encoded.encode()).hexdigest(),
    }
    with pytest.raises(LegacyPublicationError, match="scope does not match"):
        archive_legacy_publications([row], owner_map=mapping())


@pytest.mark.parametrize("calendar", [None, "scalar", [], 1])
def test_archive_requires_an_object_calendar(legacy_row, calendar):
    decoded = json.loads(legacy_row["payload"])
    decoded["calendar"] = calendar
    payload = json.dumps(decoded)
    row = legacy_row | {
        "payload": payload, "checksum": hashlib.sha256(payload.encode()).hexdigest(),
    }
    with pytest.raises(LegacyPublicationError, match="scope does not match"):
        archive_legacy_publications([row], owner_map=mapping())


def test_archive_requires_calendar_key(legacy_row):
    decoded = json.loads(legacy_row["payload"])
    del decoded["calendar"]
    payload = json.dumps(decoded)
    row = legacy_row | {
        "payload": payload, "checksum": hashlib.sha256(payload.encode()).hexdigest(),
    }
    with pytest.raises(LegacyPublicationError, match="scope does not match"):
        archive_legacy_publications([row], owner_map=mapping())


class _Result:
    def __init__(self, row=None, rowcount=0):
        self.row = row
        self.rowcount = rowcount

    def mappings(self):
        return self

    def one_or_none(self):
        return self.row


class _ArchiveConnection:
    def __init__(self):
        self.rows = {}
        self.authorized = True

    def scalar(self, statement, params):
        assert str(statement) == "SELECT classsync_scheduling.lock_publication_authority()"
        return 1 if self.authorized else None

    def execute(self, statement, params):
        query = str(statement).lstrip()
        assert "FOR UPDATE" not in query and "FOR SHARE" not in query
        if query.startswith("SELECT set_config"):
            return _Result(rowcount=1)
        if "FROM classsync_scheduling.legacy_publication_archive" in query:
            key = (params["source_fingerprint"], params["source_tenant"], params["legacy_id"])
            return _Result(self.rows.get(key))
        if query.startswith("INSERT INTO classsync_scheduling.legacy_publication_archive"):
            key = (params["source_fingerprint"], params["source_tenant"], params["legacy_id"])
            idempotency = (
                params["tenant_id"], params["source_fingerprint"], params["source_tenant"],
                params["dataset"], params["idempotency_key"],
            )
            if key in self.rows or any(
                (row["tenant_id"], row["source_fingerprint"], row["source_tenant"],
                 row["dataset"], row["idempotency_key"]) == idempotency
                for row in self.rows.values()
            ):
                return _Result(rowcount=0)
            self.rows[key] = dict(params)
            return _Result(rowcount=1)
        raise AssertionError(f"Unexpected SQL: {query}")


@contextmanager
def _transaction(connection, outcomes):
    before = dict(connection.rows)
    try:
        yield connection
    except Exception:
        connection.rows = before
        outcomes.append("rollback")
        raise
    else:
        outcomes.append("commit")


def _import_args():
    return {
        "tenant_id": "target-tenant",
        "firebase_project_id": "test-project",
        "principal": VerifiedPrincipal(uid="active-admin"),
        "source_fingerprint": "a" * 64,
        "owner_map": mapping(),
    }


def test_postgres_archive_import_is_transactional_and_exact_retries_are_idempotent(
    legacy_row, monkeypatch
):
    import classync_persistence.database as database

    connection = _ArchiveConnection()
    outcomes = []
    monkeypatch.setattr(
        database,
        "transaction",
        lambda _engine: _transaction(connection, outcomes),
    )
    assert import_legacy_publications(object(), rows=[legacy_row], **_import_args()) == 1
    assert import_legacy_publications(object(), rows=[legacy_row], **_import_args()) == 0
    assert outcomes == ["commit", "commit"]
    assert len(connection.rows) == 1
    stored = next(iter(connection.rows.values()))
    assert stored["request_hash"] == legacy_row["request_hash"]
    assert stored["payload"] == legacy_row["payload"]
    assert stored["checksum"] == legacy_row["checksum"]

    new_row = legacy_row | {
        "sequence": 9,
        "id": "legacy-version-9",
        "idempotency_key": "legacy-command-9",
    }
    collision = legacy_row | {
        "sequence": 10,
        "id": "legacy-version-10",
    }
    with pytest.raises(LegacyPublicationError, match="conflicts with stored"):
        import_legacy_publications(object(), rows=[new_row, collision], **_import_args())
    assert outcomes[-1] == "rollback"
    assert len(connection.rows) == 1


def test_postgres_archive_import_rechecks_current_admin_before_selecting_or_writing(
    legacy_row, monkeypatch
):
    import classync_persistence.database as database

    connection = _ArchiveConnection()
    connection.authorized = False
    outcomes = []
    monkeypatch.setattr(
        database,
        "transaction",
        lambda _engine: _transaction(connection, outcomes),
    )
    with pytest.raises(MembershipAuthorizationError):
        import_legacy_publications(object(), rows=[legacy_row], **_import_args())
    assert not connection.rows
    assert outcomes == ["rollback"]


def test_archive_migration_is_admin_scoped_append_only_and_downgrade_guarded():
    migration = import_module(
        "classync_persistence.migrations.versions.0010_legacy_publication_archive"
    )
    assert migration.down_revision == "0009_publication_record_projection"
    source = Path(migration.__file__).read_text(encoding="utf-8")
    assert "legacy_publication_archive" in source
    assert "state='active'" in source and "'administrator'=ANY(m.roles)" in source
    assert "ENABLE ROW LEVEL SECURITY" in source and "FORCE ROW LEVEL SECURITY" in source
    assert "BEFORE UPDATE OR DELETE" in source and "BEFORE TRUNCATE" in source
    assert "Legacy publication archive contains retained evidence" in source
    lock = source.index("LOCK TABLE classsync_scheduling.legacy_publication_archive")
    guard = source.index(
        "IF EXISTS (SELECT 1 FROM classsync_scheduling.legacy_publication_archive)"
    )
    assert lock < guard
    assert "REFERENCES classsync_identity.memberships(tenant_id,uid)" in source
    assert "COALESCE(jsonb_typeof(payload::jsonb->'calendar'),'')='object'" in source
    assert "classsync_scheduling.publication_heads" not in source
    assert "classsync_scheduling.published_versions" not in source

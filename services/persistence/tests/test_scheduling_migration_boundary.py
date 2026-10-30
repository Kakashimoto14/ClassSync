"""Generated-only Scheduling migration guards; no server or solver is started."""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace

import pytest
from classync_contracts.scheduling import (
    Assignment,
    DraftDetail,
    GenerationResult,
    RunMetadata,
    scheduling_input_hash,
)

from scripts.postgres_disposable import create_root
from services.scheduling.app.draft_rules import DraftError, DraftSnapshot, digest, encode
from services.scheduling.app.validation import validate_timetable
from services.scheduling.tests.test_engine import tiny

STAMP = "2026-10-26T08:00:00+00:00"


@pytest.fixture
def valid_rows(monkeypatch):
    """Manually placed, independently validated decoder fixture; CP-SAT is never run."""
    from scripts import postgres_scheduling_migration_qualification as migration

    monkeypatch.setattr(migration, "generate_week", lambda *_args: pytest.fail("Solver ran"))
    inputs = tiny()
    offering, window = inputs.offerings[0], inputs.operating_windows[0]
    assignment = Assignment(
        id="portable-session", offering_id=offering.id, subject_id=offering.subject_id,
        section_id=offering.section_id, teacher_id=offering.eligible_teacher_ids[0],
        room_id=offering.eligible_room_ids[0], day=window.day, start=window.start,
        end=window.start + offering.required_weekly_minutes,
    )
    validation = validate_timetable(inputs, [assignment])
    assert validation.valid and validation.hard_conflict_count == 0
    result = GenerationResult(
        run_id="portable-run", period_id=inputs.period_id, input_hash=scheduling_input_hash(inputs),
        data_version=inputs.data_version, solver_status="feasible", assignments=[assignment],
        total_offerings_requested=1, total_offerings_scheduled=1, coverage=validation.coverage,
        hard_conflict_count=0, diagnostics=[], validation=validation,
        metadata=RunMetadata(solver="manual decoder fixture; no solver execution",
                             solver_version="not-run", seed=inputs.options.seed,
                             wall_time_seconds=0,
                             time_limit_seconds=inputs.options.time_limit_seconds),
    )
    metadata = {"id": "portable-draft", "title": "Synthetic decoder fixture", "created_at": STAMP,
                "scope": migration.SCOPE, "owner": migration.OWNER}
    draft = DraftDetail(
        **DraftSnapshot().make_summary(inputs, result, metadata).model_dump(),
        input_snapshot=inputs, generation_result=result, validation=validation,
    )
    run_payload = encode({"inputs": inputs.model_dump(mode="json"),
                          "result": result.model_dump(mode="json")})
    draft_payload = encode(draft.model_dump(mode="json"))
    return {
        "solver_runs": [{"id": result.run_id, "scope": migration.SCOPE, "owner": migration.OWNER,
                         "created_at": STAMP, "schema_version": 1, "payload": run_payload,
                         "checksum": digest(run_payload)}],
        "scheduling_drafts": [{**metadata, "run_id": result.run_id, "schema_version": 1,
                               "status": "draft", "idempotency_key": "portable-save-key",
                               "payload": draft_payload, "checksum": digest(draft_payload)}],
    }


def write_source(
    connection, rows, *, version=2, columns=None, extra_table=False, foreign_key=False,
):
    from scripts import postgres_scheduling_migration_qualification as migration

    path = connection.root / migration.SOURCE_NAME
    columns = columns or migration.COLUMNS
    # This deliberately permissive corruption fixture exercises the reader's own
    # semantic checks independently of SQLite's production write-side constraints.
    with sqlite3.connect(path) as db:
        for table, names in columns.items():
            definitions = [name + (" INTEGER" if name == "schema_version" else " TEXT")
                           for name in names]
            if foreign_key and table == "solver_runs":
                definitions.append("PRIMARY KEY(id)")
            if foreign_key and table == "scheduling_drafts":
                definitions.append("FOREIGN KEY(run_id) REFERENCES solver_runs(id)")
            db.execute(f"CREATE TABLE {table} ({','.join(definitions)})")
            for row in rows[table]:
                db.execute(f"INSERT INTO {table} ({','.join(names)}) "
                           f"VALUES ({','.join('?' for _name in names)})",
                           [row.get(name) for name in names])
        if extra_table:
            db.execute("CREATE TABLE unrelated_records(id TEXT)")
        db.execute(f"PRAGMA user_version={version}")
    return path


def replace_payload(row, payload):
    row["payload"] = encode(payload)
    row["checksum"] = digest(row["payload"])


@pytest.fixture
def connection(tmp_path, monkeypatch):
    from scripts import postgres_scheduling_migration_qualification as migration

    monkeypatch.setattr(migration.tempfile, "gettempdir", lambda: str(tmp_path))
    return SimpleNamespace(root=create_root(tmp_path))


def test_wrong_source_name_is_rejected_before_any_sqlite_open(connection, monkeypatch):
    from scripts import postgres_scheduling_migration_qualification as migration

    monkeypatch.setattr(migration.sqlite3, "connect", lambda *a, **k: pytest.fail("Opened source"))
    with pytest.raises(RuntimeError, match="generated Scheduling source"):
        migration.read_generated_source(connection, connection.root / "original.sqlite3")


def test_unmarked_cluster_is_rejected_before_any_source_open(connection, monkeypatch):
    from scripts import postgres_scheduling_migration_qualification as migration

    (connection.root / "classsync-marker.json").unlink()
    monkeypatch.setattr(migration.sqlite3, "connect", lambda *a, **k: pytest.fail("Opened source"))
    with pytest.raises(ValueError, match="marker required"):
        migration.read_generated_source(connection, connection.root / migration.SOURCE_NAME)


@pytest.mark.parametrize("value", [STAMP, "2026-10-26T08:00:00.123456+00:00"])
def test_canonical_utc_is_preserved_exactly(value):
    from scripts import postgres_scheduling_migration_qualification as migration

    assert migration.canonical_utc(value) == value


@pytest.mark.parametrize("value", [
    "2026-10-26T08:00:00", "2026-10-26T08:00:00Z", "2026-10-26T16:00:00+08:00",
    "2026-10-26 08:00:00+00:00", "2026-10-26T08:00:00.000000+00:00", "not-a-time", None, 3,
])
def test_naive_noncanonical_or_malformed_timestamp_rejected(value):
    from scripts import postgres_scheduling_migration_qualification as migration

    with pytest.raises(RuntimeError, match="canonical UTC"):
        migration.canonical_utc(value)


@pytest.mark.parametrize("kind", ["missing", "outside", "link"])
def test_unsafe_paths_rejected_before_sqlite_open(connection, monkeypatch, kind):
    from scripts import postgres_scheduling_migration_qualification as migration

    path = connection.root / migration.SOURCE_NAME
    if kind == "outside":
        path = connection.root.parent / migration.SOURCE_NAME
        path.write_bytes(b"outside sentinel")
    elif kind == "link":
        path.write_bytes(b"linked sentinel")
        monkeypatch.setattr(type(path), "is_symlink", lambda self: self == path)
    monkeypatch.setattr(migration.sqlite3, "connect", lambda *a, **k: pytest.fail("Opened source"))
    with pytest.raises(RuntimeError, match="generated Scheduling source"):
        migration.read_generated_source(connection, path)


def test_valid_fixture_read_uses_immutable_read_only_uri_and_preserves_bytes(
    connection, valid_rows, monkeypatch,
):
    from scripts import postgres_scheduling_migration_qualification as migration

    path = write_source(connection, valid_rows)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    files = set(connection.root.iterdir())
    real_connect, calls = sqlite3.connect, []

    def observed(*args, **kwargs):
        calls.append((args, kwargs))
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(migration.sqlite3, "connect", observed)
    bundle = migration.read_generated_source(connection, path)
    assert bundle["rows"] == valid_rows
    assert bundle["sha256"] == before == hashlib.sha256(path.read_bytes()).hexdigest()
    assert set(connection.root.iterdir()) == files
    assert calls == [((path.as_uri() + "?mode=ro&immutable=1",), {"uri": True})]


def test_valid_raw_json_bytes_are_preserved_not_reencoded(connection, valid_rows):
    from scripts import postgres_scheduling_migration_qualification as migration

    row = valid_rows["solver_runs"][0]
    row["payload"] = json.dumps(json.loads(row["payload"]), indent=2)
    row["checksum"] = digest(row["payload"])
    bundle = migration.read_generated_source(connection, write_source(connection, valid_rows))
    assert bundle["rows"]["solver_runs"][0]["payload"] == row["payload"]


@pytest.mark.parametrize("version", [0, 1, 3])
def test_wrong_database_version_rejected_without_migrating_source(connection, valid_rows, version):
    from scripts import postgres_scheduling_migration_qualification as migration

    path = write_source(connection, valid_rows, version=version)
    before = path.read_bytes()
    with pytest.raises(RuntimeError, match="version must be2"):
        migration.read_generated_source(connection, path)
    assert path.read_bytes() == before


def test_unknown_source_table_rejected(connection, valid_rows):
    from scripts import postgres_scheduling_migration_qualification as migration

    with pytest.raises(RuntimeError, match="source tables"):
        migration.read_generated_source(connection, write_source(
            connection, valid_rows, extra_table=True,
        ))


@pytest.mark.parametrize("table", ["solver_runs", "scheduling_drafts"])
def test_missing_or_extra_source_columns_rejected(connection, valid_rows, table):
    from scripts import postgres_scheduling_migration_qualification as migration

    columns = dict(migration.COLUMNS)
    columns[table] = (*columns[table], "unexpected")
    with pytest.raises(RuntimeError, match="source columns"):
        migration.read_generated_source(connection, write_source(
            connection, valid_rows, columns=columns,
        ))


@pytest.mark.parametrize("table", ["solver_runs", "scheduling_drafts"])
def test_empty_source_rows_rejected(connection, valid_rows, table):
    from scripts import postgres_scheduling_migration_qualification as migration

    valid_rows[table] = []
    with pytest.raises(RuntimeError, match="must be nonempty"):
        migration.read_generated_source(connection, write_source(connection, valid_rows))


def test_actual_foreign_key_violation_rejected_before_decoding(connection, valid_rows):
    from scripts import postgres_scheduling_migration_qualification as migration

    valid_rows["scheduling_drafts"][0]["run_id"] = "absent"
    with pytest.raises(RuntimeError, match="source integrity failed"):
        migration.read_generated_source(connection, write_source(
            connection, valid_rows, foreign_key=True,
        ))


def test_corrupt_sqlite_bytes_fail_before_target_session(connection, monkeypatch):
    from scripts import postgres_scheduling_migration_qualification as migration

    path = connection.root / migration.SOURCE_NAME
    path.write_bytes(b"not a SQLite database")
    repository = SimpleNamespace(session=lambda **_k: pytest.fail("Opened target"))
    with pytest.raises(sqlite3.DatabaseError):
        migration.import_generated_schedule(connection, repository, path)


@pytest.mark.parametrize("table", ["solver_runs", "scheduling_drafts"])
@pytest.mark.parametrize("field,value", [("scope", "sandbox"), ("owner", "other-admin")])
def test_wrong_scope_or_owner_rejected_before_target_session(
    connection, valid_rows, table, field, value,
):
    from scripts import postgres_scheduling_migration_qualification as migration

    valid_rows[table][0][field] = value
    repository = SimpleNamespace(session=lambda **_k: pytest.fail("Opened target"))
    with pytest.raises(RuntimeError, match="explicitly mapped synthetic Administrator"):
        migration.import_generated_schedule(
            connection, repository, write_source(connection, valid_rows),
        )


@pytest.mark.parametrize("table", ["solver_runs", "scheduling_drafts"])
@pytest.mark.parametrize("tamper", ["checksum", "json", "schema-version", "timestamp"])
def test_corrupt_or_incompatible_row_is_not_importable(connection, valid_rows, table, tamper):
    from scripts import postgres_scheduling_migration_qualification as migration

    row = valid_rows[table][0]
    if tamper == "checksum":
        row["checksum"] = "not-the-checksum"
    elif tamper == "json":
        row["payload"] = "{invalid json"
        row["checksum"] = digest(row["payload"])
    elif tamper == "schema-version":
        row["schema_version"] = 2
    else:
        row["created_at"] = "2026-10-26T16:00:00+08:00"
    with pytest.raises((DraftError, RuntimeError)):
        migration.read_generated_source(connection, write_source(connection, valid_rows))


@pytest.mark.parametrize("status", ["unknown", "infeasible"])
def test_unsuccessful_run_status_cannot_cross_migration_boundary(connection, valid_rows, status):
    from scripts import postgres_scheduling_migration_qualification as migration

    row = valid_rows["solver_runs"][0]
    payload = json.loads(row["payload"])
    payload["result"]["solver_status"] = status
    replace_payload(row, payload)
    with pytest.raises(DraftError) as denied:
        migration.read_generated_source(connection, write_source(connection, valid_rows))
    assert denied.value.code == "invalid_generated_run"


def test_invalid_checksum_consistent_assignment_is_independently_rejected(connection, valid_rows):
    from scripts import postgres_scheduling_migration_qualification as migration

    row = valid_rows["solver_runs"][0]
    payload = json.loads(row["payload"])
    payload["result"]["assignments"][0]["teacher_id"] = "absent-teacher"
    replace_payload(row, payload)
    with pytest.raises(DraftError) as denied:
        migration.read_generated_source(connection, write_source(connection, valid_rows))
    assert denied.value.code == "invalid_generated_run"


@pytest.mark.parametrize("change", ["synthetic-flag", "room-source", "run-id"])
def test_run_provenance_and_identity_rejected(connection, valid_rows, change):
    from scripts import postgres_scheduling_migration_qualification as migration

    row = valid_rows["solver_runs"][0]
    payload = json.loads(row["payload"])
    if change == "synthetic-flag":
        payload["inputs"]["synthetic"] = False
    elif change == "room-source":
        payload["inputs"]["rooms"][0]["source"] = "administrator-supplied"
    else:
        row["id"] = "different-from-payload"
    replace_payload(row, payload)
    with pytest.raises(RuntimeError):
        migration.read_generated_source(connection, write_source(connection, valid_rows))


@pytest.mark.parametrize("field,value", [("status", "published"), ("idempotency_key", "short")])
def test_invalid_draft_state_or_key_rejected(connection, valid_rows, field, value):
    from scripts import postgres_scheduling_migration_qualification as migration

    valid_rows["scheduling_drafts"][0][field] = value
    with pytest.raises(RuntimeError, match="status/key"):
        migration.read_generated_source(connection, write_source(connection, valid_rows))


@pytest.mark.parametrize("field,value", [("title", "Metadata differs"), ("id", "different-id")])
def test_draft_payload_metadata_mismatch_rejected(connection, valid_rows, field, value):
    from scripts import postgres_scheduling_migration_qualification as migration

    valid_rows["scheduling_drafts"][0][field] = value
    with pytest.raises(DraftError) as denied:
        migration.read_generated_source(connection, write_source(connection, valid_rows))
    assert denied.value.code == "snapshot_integrity"


@pytest.mark.parametrize("kind", ["input", "result"])
def test_independently_valid_draft_cannot_differ_from_server_held_run(connection, valid_rows, kind):
    from scripts import postgres_scheduling_migration_qualification as migration

    row = valid_rows["scheduling_drafts"][0]
    draft = DraftDetail.model_validate(json.loads(row["payload"]))
    if kind == "input":
        inputs = draft.input_snapshot.model_copy(
            update={"scope_description": "Different raw input"},
        )
        changed_hash = scheduling_input_hash(inputs)
        result = draft.generation_result.model_copy(update={"input_hash": changed_hash})
        draft = draft.model_copy(update={"input_snapshot": inputs, "generation_result": result,
                                         "input_hash": changed_hash})
    else:
        metadata = draft.generation_result.metadata.model_copy(update={"wall_time_seconds": 1})
        result = draft.generation_result.model_copy(update={"metadata": metadata})
        draft = draft.model_copy(update={"generation_result": result})
    replace_payload(row, draft.model_dump(mode="json"))
    with pytest.raises(RuntimeError, match="differs from its server-held run"):
        migration.read_generated_source(connection, write_source(connection, valid_rows))


def test_draft_without_matching_server_run_rejected(connection, valid_rows):
    from scripts import postgres_scheduling_migration_qualification as migration

    row = valid_rows["scheduling_drafts"][0]
    payload = json.loads(row["payload"])
    row["run_id"] = payload["run_id"] = payload["generation_result"]["run_id"] = "absent-run"
    replace_payload(row, payload)
    with pytest.raises(RuntimeError, match="has no server-held run"):
        migration.read_generated_source(connection, write_source(connection, valid_rows))


@pytest.mark.parametrize("changes", [
    {"tenant": "wrong", "owner": "uid-admin", "project": "synthetic-project"},
    {"tenant": "tenant-a", "owner": "wrong", "project": "synthetic-project"},
    {"tenant": "tenant-a", "owner": "uid-admin", "project": "wrong"},
])
def test_wrong_target_mapping_rejected_before_target_session(connection, valid_rows, changes):
    from scripts import postgres_scheduling_migration_qualification as migration

    repository = SimpleNamespace(keys={"tenant": changes["tenant"], "owner": changes["owner"]},
                                 context=SimpleNamespace(project_id=changes["project"]),
                                 session=lambda **_k: pytest.fail("Opened target"))
    with pytest.raises(RuntimeError, match="explicitly mapped synthetic PG"):
        migration.import_generated_schedule(
            connection, repository, write_source(connection, valid_rows),
        )


@pytest.mark.parametrize("observed", [
    ("original", "runtime", 59123, "127.0.0.1"),
    ("postgres", "wrong-user", 59123, "127.0.0.1"),
    ("postgres", "runtime", 5432, "127.0.0.1"),
    ("postgres", "runtime", 59123, "192.0.2.1"),
])
def test_wrong_physical_target_halts_before_lock_or_insert(connection, valid_rows, observed):
    from scripts import postgres_scheduling_migration_qualification as migration

    connection.runtime, connection.port = "runtime", 59123
    calls = []

    def execute(statement):
        calls.append(str(statement))
        return SimpleNamespace(one=lambda: observed)

    @contextmanager
    def session(**_kwargs):
        yield SimpleNamespace(execute=execute)

    repository = SimpleNamespace(keys={"tenant": "tenant-a", "owner": "uid-admin"},
                                 context=SimpleNamespace(project_id="synthetic-project"),
                                 session=session)
    with pytest.raises(RuntimeError, match="target binding differs"):
        migration.import_generated_schedule(
            connection, repository, write_source(connection, valid_rows),
        )
    assert len(calls) == 1 and "INSERT" not in calls[0] and "advisory" not in calls[0]


@pytest.mark.parametrize("kind", ["run-id", "draft-id", "saved-run", "save-key"])
def test_duplicate_source_identities_or_keys_rejected(connection, valid_rows, kind):
    from scripts import postgres_scheduling_migration_qualification as migration

    if kind == "run-id":
        valid_rows["solver_runs"].append(deepcopy(valid_rows["solver_runs"][0]))
    else:
        second = deepcopy(valid_rows["scheduling_drafts"][0])
        payload = json.loads(second["payload"])
        if kind != "draft-id":
            second["id"] = payload["id"] = "portable-draft-2"
        if kind == "save-key":
            extra_run = deepcopy(valid_rows["solver_runs"][0])
            extra_payload = json.loads(extra_run["payload"])
            extra_run["id"] = extra_payload["result"]["run_id"] = "portable-run-2"
            replace_payload(extra_run, extra_payload)
            valid_rows["solver_runs"].append(extra_run)
            second["run_id"] = payload["run_id"] = "portable-run-2"
            payload["generation_result"]["run_id"] = "portable-run-2"
        else:
            second["idempotency_key"] = "second-save-key"
        replace_payload(second, payload)
        valid_rows["scheduling_drafts"].append(second)
    with pytest.raises(RuntimeError, match="differs or repeats|identity/key repeats"):
        migration.read_generated_source(connection, write_source(connection, valid_rows))

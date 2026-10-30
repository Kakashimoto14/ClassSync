"""Portable academic restore safeguards; no database, tool or server is started."""

from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace

import pytest

from scripts import postgres_academic_restore_qualification as restore
from scripts.postgres_disposable import create_root


@pytest.fixture
def connection(tmp_path, monkeypatch):
    monkeypatch.setattr(restore.tempfile, "gettempdir", lambda: str(tmp_path))
    root = create_root(tmp_path)
    return SimpleNamespace(root=root, port=59123, owner="classsync_qa_" + "a" * 32,
                           runtime="classsync_runtime_" + "b" * 32)


def observed(connection, **changes):
    return {"data_directory": str(connection.root / "data"), "database": "postgres",
            "user": connection.owner, "port": connection.port, **changes}


def baseline():
    data = {key: [{"payload": "synthetic", "revision": 2}] for key in restore.DATA_TABLES}
    catalog = {key: [] for key in restore.catalog_queries()}
    catalog["migration"] = [[restore.MIGRATION]]
    catalog["tables"] = [
        [*table.split("."), "synthetic-owner", True, True, None] for table in restore.DATA_TABLES
    ]
    return data, catalog


def test_exact_owned_source_binding_is_accepted(connection):
    restore.check_binding(connection, observed(connection), "postgres")


@pytest.mark.parametrize("changes", [
    {"database": "original"}, {"data_directory": "/not-owned/data"},
    {"user": "postgres"}, {"port": 5432}, {"port": 59124},
])
def test_source_and_target_server_binding_fail_closed(connection, changes):
    with pytest.raises(RuntimeError, match="binding mismatch"):
        restore.check_binding(connection, observed(connection, **changes), "postgres")


def test_restore_database_binding_requires_the_exact_generated_target(connection):
    target = "classsync_restore_" + "c" * 32
    restore.check_binding(connection, observed(connection, database=target), target)
    with pytest.raises(RuntimeError, match="binding mismatch"):
        restore.check_binding(connection, observed(connection), target)
    with pytest.raises(ValueError):
        restore.check_binding(connection, observed(connection), "original")


@pytest.mark.parametrize("field,value", [
    ("owner", "postgres"), ("runtime", "existing"), ("port", 5432),
    ("port", True), ("port", "59123"), ("port", 65536),
])
def test_generated_role_and_port_guard_before_any_connection(connection, field, value):
    setattr(connection, field, value)
    with pytest.raises(RuntimeError, match="Generated local cluster"):
        restore.owned_root(connection)


def test_unmarked_root_cannot_access_archive_or_database(connection):
    (connection.root / "classsync-marker.json").unlink()
    with pytest.raises(ValueError, match="marker required"):
        restore.check_binding(connection, observed(connection), "postgres")


@pytest.mark.parametrize("namespaces,objects", [
    (["classsync_identity"], 0), (["classsync_academic"], 0), ([], 1), ([], 20),
])
def test_existing_schema_or_public_objects_halt_restore(namespaces, objects):
    with pytest.raises(RuntimeError, match="newly created and empty"):
        restore.check_empty_target(namespaces, objects)


def test_only_empty_new_target_passes():
    restore.check_empty_target([], 0)


def test_restore_toc_omits_only_existing_public_schema_creation():
    source = (
        "; archive comment\n5; 2615 2200 SCHEMA - public pg_database_owner\n"
        "7; 2615 2500 SCHEMA - classsync_academic migrator\n"
        "9; 1259 3000 TABLE public alembic_version migrator\n"
        "10; 0 0 ACL - SCHEMA public pg_database_owner\n"
    )
    filtered = restore.restore_toc(source)
    assert filtered == source.replace("5; 2615 2200 SCHEMA - public pg_database_owner\n", "")


@pytest.mark.parametrize("listing", ["", "1; 2615 1 SCHEMA - private owner\n",
    "1; 2615 1 SCHEMA - public owner\n2; 2615 2 SCHEMA - public owner\n"])
def test_restore_toc_missing_or_duplicate_public_entry_fails_closed(listing):
    with pytest.raises(RuntimeError, match="exactly one public schema"):
        restore.restore_toc(listing)


def test_original_target_rejected_before_connection():
    class NeverConnect:
        def connect(self):
            pytest.fail("original database names must not reach connection")

    with pytest.raises(ValueError):
        restore.create_target(NeverConnect(), "postgres")


def test_target_collision_is_not_reused_or_silently_ignored():
    statements = []

    class Collision:
        def connect(self):
            return self

        def execution_options(self, **options):
            assert options == {"isolation_level": "AUTOCOMMIT"}
            return self

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement):
            statements.append(str(statement))
            raise RuntimeError("synthetic duplicate database")

    target = "classsync_restore_" + "c" * 32
    with pytest.raises(RuntimeError, match="synthetic duplicate database"):
        restore.create_target(Collision(), target)
    assert statements == [f"CREATE DATABASE {target} TEMPLATE template0"]


def test_backup_does_not_silently_cover_future_scheduling_or_unrelated_public_data():
    schemas = ["public", "classsync_identity", "classsync_academic"]
    restore.check_source_scope(schemas, ["alembic_version"])
    with pytest.raises(RuntimeError, match="unexpected namespaces"):
        restore.check_source_scope([*schemas, "classsync_scheduling"], ["alembic_version"])
    with pytest.raises(RuntimeError, match="unexpected namespaces"):
        restore.check_source_scope(schemas, ["alembic_version", "unrelated_records"])


def test_archive_bytes_are_verified_again_before_restore(connection):
    archive = connection.root / ("academic-" + "c" * 32 + ".dump")
    archive.write_bytes(b"synthetic custom archive stand-in")
    expected = restore.archive_hash(connection, archive)
    assert restore.archive_hash(connection, archive, expected) == expected
    archive.write_bytes(b"changed archive")
    with pytest.raises(RuntimeError, match="archive changed"):
        restore.archive_hash(connection, archive, expected)


@pytest.mark.parametrize("name", ["original.dump", "academic-123.dump", "academic-" + "c" * 32])
def test_archive_name_cannot_select_other_files(connection, name):
    archive = connection.root / name
    archive.write_bytes(b"must not be opened")
    with pytest.raises(RuntimeError, match="owned generated academic archive"):
        restore.archive_hash(connection, archive)


def test_archive_outside_owned_root_and_empty_archive_are_rejected(connection, tmp_path):
    archive = tmp_path / ("academic-" + "c" * 32 + ".dump")
    archive.write_bytes(b"outside")
    with pytest.raises(RuntimeError, match="owned generated academic archive"):
        restore.archive_hash(connection, archive)
    empty = connection.root / archive.name
    empty.touch()
    with pytest.raises(RuntimeError, match="owned generated academic archive"):
        restore.archive_hash(connection, empty)


def test_linked_archive_is_rejected_without_reading_it(connection, monkeypatch):
    archive = connection.root / ("academic-" + "c" * 32 + ".dump")
    archive.write_bytes(b"sentinel")
    path_type = type(archive)
    monkeypatch.setattr(path_type, "is_symlink", lambda self: self == archive)
    monkeypatch.setattr(path_type, "read_bytes", lambda _self: pytest.fail("must not read link"))
    with pytest.raises(RuntimeError, match="owned generated academic archive"):
        restore.archive_hash(connection, archive)


@pytest.mark.parametrize("table", restore.DATA_TABLES)
def test_fingerprint_detects_every_identity_and_academic_table_change(table):
    data, catalog = baseline()
    before = restore.summarize(data, catalog)
    changed = deepcopy(data)
    changed[table][0]["revision"] += 1
    assert restore.summarize(changed, catalog) != before


@pytest.mark.parametrize("part", [
    "schema_acl", "columns", "constraints", "indexes", "table_acl", "column_acl",
    "functions", "function_acl", "triggers", "policies", "default_acl",
])
def test_fingerprint_detects_each_authority_and_catalog_change(part):
    data, catalog = baseline()
    before = restore.summarize(data, catalog)
    changed = deepcopy(catalog)
    changed[part].append(["synthetic drift"])
    assert restore.summarize(data, changed) != before


@pytest.mark.parametrize("column", [3, 4])
def test_fingerprint_refuses_missing_enable_or_force_rls(column):
    data, catalog = baseline()
    catalog["tables"][0][column] = False
    with pytest.raises(RuntimeError, match="Missing enabled/FORCE RLS"):
        restore.summarize(data, catalog)


def test_fingerprint_refuses_migration_drift_and_incomplete_comparison():
    data, catalog = baseline()
    catalog["migration"] = [["0006_unrelated_future_migration"]]
    with pytest.raises(RuntimeError, match="migration target drift"):
        restore.summarize(data, catalog)
    data, catalog = baseline()
    del data["classsync_academic.calendars"]
    with pytest.raises(RuntimeError, match="Incomplete academic/identity"):
        restore.summarize(data, catalog)
    data, catalog = baseline()
    del catalog["column_acl"]
    with pytest.raises(RuntimeError, match="Incomplete authority/catalog"):
        restore.summarize(data, catalog)


def test_source_migration_is_pinned_before_fixture_data(monkeypatch, connection):
    calls = []

    class StopBeforeFixture(Exception):
        pass

    @contextmanager
    def fake_transaction(_engine):
        yield SimpleNamespace(execute=lambda statement: None)

    def migrate(_session, *, target):
        calls.append(target)
        raise StopBeforeFixture()

    monkeypatch.setattr(restore, "transaction", fake_transaction)
    monkeypatch.setattr(restore, "migrate", migrate)
    with pytest.raises(StopBeforeFixture):
        restore.prepare_source(connection, object(), object())
    assert calls == ["0005_academic_records"]


def test_existing_evidence_refused_before_qualification(tmp_path, monkeypatch):
    path = tmp_path / "sentinel.json"
    path.write_text("preserve")
    monkeypatch.setattr(restore, "qualify", lambda *_args: pytest.fail("must not start server"))
    with pytest.raises(RuntimeError, match="New evidence file"):
        restore.main(["--bin", str(tmp_path), "--output", str(path)])
    assert path.read_text() == "preserve"

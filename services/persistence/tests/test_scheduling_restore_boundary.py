"""Portable Scheduling restore boundaries; never start a server or solver."""

import importlib
import tempfile
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace

import pytest

from scripts import postgres_scheduling_restore_qualification as restore
from scripts.postgres_disposable import create_root


@pytest.fixture
def connection(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    root = create_root(tmp_path)
    return SimpleNamespace(root=root, port=59123, owner="classsync_qa_" + "a" * 32,
                           runtime="classsync_runtime_" + "b" * 32)


def baseline():
    data = {key: [{"payload": "synthetic", "revision": 2}] for key in restore.DATA_TABLES}
    catalog = {key: [] for key in restore.catalog_queries()}
    catalog["migration"] = [[restore.MIGRATION]]
    catalog["tables"] = [
        [*table.split("."), "synthetic-owner", True, True, None] for table in restore.DATA_TABLES
    ]
    return data, catalog


def toc_listing():
    result = ["; synthetic portable archive listing"]
    for index, schema in enumerate(["public", *restore.SCHEMA_NAMES], 1):
        result.append(f"{index}; 2615 {index} SCHEMA - {schema} synthetic_owner")
    for index, table in enumerate([*restore.DATA_TABLES, "public.alembic_version"], 10):
        schema, name = table.split(".")
        result.append(f"{index}; 1259 {index} TABLE {schema} {name} synthetic_owner")
        result.append(f"{index + 100}; 0 {index} TABLE DATA {schema} {name} synthetic_owner")
    result.append("300; 0 0 ACL - SCHEMA public pg_database_owner")
    return "\n".join(result) + "\n"


def test_original_restore_target_refused_before_connection():
    module = importlib.import_module("scripts.postgres_scheduling_restore_qualification")

    class NeverConnect:
        def connect(self):
            pytest.fail("Original database target reached a connection")

    with pytest.raises(ValueError):
        module.create_target(NeverConnect(), "postgres")


def test_all_three_schema_data_and_authority_are_required():
    module = importlib.import_module("scripts.postgres_scheduling_restore_qualification")
    assert module.MIGRATION == "0006_scheduling_drafts"
    assert len(module.DATA_TABLES) == 12
    assert {"classsync_academic.calendars", "classsync_identity.membership_audit",
            "classsync_scheduling.solver_runs", "classsync_scheduling.drafts"}.issubset(
        module.DATA_TABLES
    )
    with pytest.raises(RuntimeError, match="Incomplete"):
        module.summarize({}, {})


def test_source_scope_requires_all_three_schemas_and_only_alembic_public_metadata():
    schemas = ["public", *restore.SCHEMA_NAMES]
    restore.check_source_scope(schemas, ["alembic_version"])
    for namespaces, public in ((schemas[:-1], ["alembic_version"]),
                               ([*schemas, "unrelated"], ["alembic_version"]),
                               (schemas, ["alembic_version", "original_records"])):
        with pytest.raises(RuntimeError, match="unexpected namespaces"):
            restore.check_source_scope(namespaces, public)


def test_toc_preserves_all_three_schema_data_and_public_acl_only_omitting_public_create():
    listing = toc_listing()
    filtered = restore.checked_toc(listing)
    assert filtered == listing.replace("1; 2615 1 SCHEMA - public synthetic_owner\n", "")
    assert "ACL - SCHEMA public" in filtered
    assert "TABLE DATA public alembic_version" in filtered


@pytest.mark.parametrize("change", ["missing-data", "missing-schema", "extra-data", "duplicate"])
def test_toc_incomplete_or_unexpected_entries_are_rejected(change):
    listing = toc_listing()
    if change == "missing-data":
        listing = "\n".join(line for line in listing.splitlines()
                            if "TABLE DATA classsync_scheduling drafts " not in line)
    elif change == "missing-schema":
        listing = "\n".join(line for line in listing.splitlines()
                            if "SCHEMA - classsync_scheduling " not in line)
    elif change == "extra-data":
        listing += "999; 0 500 TABLE DATA public original_records owner\n"
    else:
        listing += "999; 1259 500 TABLE classsync_scheduling drafts owner\n"
    with pytest.raises(RuntimeError, match="missing, duplicate or unexpected"):
        restore.checked_toc(listing)


@pytest.mark.parametrize("suffix", ["dump", "toc"])
def test_generated_archive_and_toc_content_rechecked(connection, suffix):
    path = connection.root / ("scheduling-" + "c" * 32 + "." + suffix)
    path.write_bytes(b"generated disposable sentinel")
    original = restore.owned_file_hash(connection, path, suffix)
    assert restore.owned_file_hash(connection, path, suffix, original) == original
    path.write_bytes(b"changed")
    with pytest.raises(RuntimeError, match="archive or TOC changed"):
        restore.owned_file_hash(connection, path, suffix, original)


@pytest.mark.parametrize("name,suffix", [
    ("original.dump", "dump"), ("scheduling-123.dump", "dump"),
    ("scheduling-" + "c" * 32 + ".dump", "toc"),
    ("scheduling-" + "c" * 32 + ".sql", "sql"),
])
def test_non_generated_or_wrong_archive_type_rejected(connection, name, suffix):
    path = connection.root / name
    path.write_bytes(b"must not use")
    with pytest.raises(RuntimeError, match="generated owned Scheduling"):
        restore.owned_file_hash(connection, path, suffix)


def test_outside_and_empty_archive_rejected(connection, tmp_path):
    outside = tmp_path / ("scheduling-" + "c" * 32 + ".dump")
    outside.write_bytes(b"outside owned root")
    with pytest.raises(RuntimeError, match="generated owned Scheduling"):
        restore.owned_file_hash(connection, outside, "dump")
    empty = connection.root / outside.name
    empty.touch()
    with pytest.raises(RuntimeError, match="generated owned Scheduling"):
        restore.owned_file_hash(connection, empty, "dump")


def test_linked_archive_refused_before_read(connection, monkeypatch):
    path = connection.root / ("scheduling-" + "c" * 32 + ".dump")
    path.write_bytes(b"sentinel")
    monkeypatch.setattr(type(path), "is_symlink", lambda self: self == path)
    monkeypatch.setattr(type(path), "read_bytes", lambda _self: pytest.fail("Read linked archive"))
    with pytest.raises(RuntimeError, match="generated owned Scheduling"):
        restore.owned_file_hash(connection, path, "dump")


def test_unmarked_cluster_refused_before_file_read(connection):
    (connection.root / "classsync-marker.json").unlink()
    with pytest.raises(ValueError, match="marker required"):
        restore.owned_file_hash(connection, connection.root / "not-opened.dump", "dump")


@pytest.mark.parametrize("table", restore.DATA_TABLES)
def test_each_raw_table_payload_and_revision_change_is_detected(table):
    data, catalog = baseline()
    original = restore.summarize(data, catalog)
    modified = deepcopy(data)
    modified[table][0]["revision"] += 1
    assert restore.summarize(modified, catalog) != original


@pytest.mark.parametrize("part", [
    "schemas", "schema_acl", "columns", "constraints", "indexes", "table_acl", "column_acl",
    "functions", "function_acl", "triggers", "policies", "default_acl",
])
def test_catalog_and_authority_drift_detected(part):
    data, catalog = baseline()
    original = restore.summarize(data, catalog)
    catalog[part].append(["synthetic drift"])
    assert restore.summarize(data, catalog) != original


@pytest.mark.parametrize("column", [3, 4])
def test_enable_and_force_rls_are_required_on_every_table(column):
    data, catalog = baseline()
    catalog["tables"][-1][column] = False
    with pytest.raises(RuntimeError, match="Missing enabled/FORCE RLS"):
        restore.summarize(data, catalog)


def test_partial_data_catalog_or_future_migration_is_not_an_acceptable_comparison():
    data, catalog = baseline()
    catalog["migration"] = [["0007_unrelated_future_scope"]]
    with pytest.raises(RuntimeError, match="migration target drift"):
        restore.summarize(data, catalog)
    data, catalog = baseline()
    del data["classsync_scheduling.solver_runs"]
    with pytest.raises(RuntimeError, match="Incomplete"):
        restore.summarize(data, catalog)
    data, catalog = baseline()
    del catalog["default_acl"]
    with pytest.raises(RuntimeError, match="Incomplete"):
        restore.summarize(data, catalog)


def test_upgrade_pins_target_six_without_running_fixture_solver(connection, monkeypatch):
    calls = []

    class StopBeforeFixture(Exception):
        pass

    @contextmanager
    def fake_transaction(_engine):
        yield SimpleNamespace(execute=lambda _statement: None)

    def migrate(_session, *, target):
        calls.append(target)
        raise StopBeforeFixture()

    monkeypatch.setattr(restore, "transaction", fake_transaction)
    monkeypatch.setattr(restore, "migrate", migrate)
    monkeypatch.setattr(restore, "generate_week", lambda *_a: pytest.fail("Solver ran"))
    with pytest.raises(StopBeforeFixture):
        restore.upgrade_scheduling(connection, object(), "synthetic_migrator")
    assert calls == ["0006_scheduling_drafts"]


def audit_delta():
    before = {table: [] for table in restore.DATA_TABLES}
    member = {"tenant_id": "tenant-a", "uid": "uid-admin", "state": "active", "revision": 1,
              "roles": ["administrator"], "person_id": "synthetic-person"}
    before["classsync_identity.memberships"] = [member]
    after = deepcopy(before)
    after["classsync_identity.memberships"][0]["revision"] = 5
    for revision in (2, 3, 4, 5):
        state = "revoked" if revision % 2 == 0 else "active"
        after["classsync_identity.membership_audit"].append({
            "tenant_id": "tenant-a", "subject_uid": "uid-admin", "revision": revision,
            "actor_uid": "synthetic-operator", "database_session_user": "synthetic-owner",
            "new_snapshot": member | {"revision": revision, "state": state},
            "old_snapshot": member | {"revision": revision - 1,
                                      "state": "active" if state == "revoked" else "revoked"},
        })
    return before, after


def test_only_four_precise_current_authority_audit_transitions_are_expected():
    before, after = audit_delta()
    restore.check_functional_delta(before, after, "synthetic-owner")


@pytest.mark.parametrize("tamper", ["academic", "draft", "role", "audit-actor", "audit-state"])
def test_functional_checks_cannot_hide_other_data_or_audit_changes(tamper):
    before, after = audit_delta()
    if tamper == "academic":
        after["classsync_academic.records"].append({"payload": "changed"})
    elif tamper == "draft":
        after["classsync_scheduling.drafts"].append({"payload": "changed"})
    elif tamper == "role":
        after["classsync_identity.memberships"][0]["roles"] = ["student"]
    elif tamper == "audit-actor":
        after["classsync_identity.membership_audit"][0]["actor_uid"] = "forged"
    else:
        after["classsync_identity.membership_audit"][0]["new_snapshot"]["state"] = "active"
    with pytest.raises(RuntimeError):
        restore.check_functional_delta(before, after, "synthetic-owner")


def test_existing_evidence_stops_before_qualification(tmp_path, monkeypatch):
    evidence = tmp_path / "sentinel.json"
    evidence.write_text("preserve")
    monkeypatch.setattr(restore, "qualify", lambda *_args: pytest.fail("Started server"))
    with pytest.raises(RuntimeError, match="New evidence file"):
        restore.main(["--bin", str(tmp_path), "--output", str(evidence)])
    assert evidence.read_text() == "preserve"

"""Portable qualification guards; never run a server or solver."""

import importlib
import tempfile
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace

import pytest

from scripts import postgres_publication_repository_qualification as publication
from scripts.postgres_disposable import create_root


def test_unmarked_target_is_rejected_before_engine_or_fixture_mutation(monkeypatch, tmp_path):
    module = importlib.import_module("scripts.postgres_publication_repository_qualification")
    monkeypatch.setattr(module, "engine_for", lambda *_a, **_k: pytest.fail("Database opened"))
    with pytest.raises(ValueError):
        module.exercise(SimpleNamespace(root=tmp_path / "original"))


def test_existing_output_is_rejected_before_any_cluster_start(monkeypatch, tmp_path):
    module = importlib.import_module("scripts.postgres_publication_repository_qualification")
    output = tmp_path / "existing.json"
    output.write_text("preserve", encoding="utf-8")
    monkeypatch.setattr(module, "qualify", lambda *_a: pytest.fail("Cluster started"))
    with pytest.raises(RuntimeError, match="New output required"):
        module.main(["--bin", str(tmp_path), "--output", str(output)])
    assert output.read_text(encoding="utf-8") == "preserve"


@pytest.fixture
def owned(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    return SimpleNamespace(root=create_root(tmp_path), owner="generated-owner", port=59123)


def test_only_marked_owned_root_is_accepted(owned):
    assert publication.checked_connection(owned) == owned.root


@pytest.mark.parametrize("tamper", ["missing-marker", "changed-marker", "outside-root"])
def test_changed_marked_target_rejected_before_engine_creation(
    owned, tmp_path, monkeypatch, tamper,
):
    monkeypatch.setattr(publication, "engine_for", lambda *_a, **_k: pytest.fail("Engine opened"))
    if tamper == "missing-marker":
        (owned.root / "classsync-marker.json").unlink()
    elif tamper == "changed-marker":
        (owned.root / "classsync-marker.json").write_text("{}")
    else:
        owned.root = tmp_path
    with pytest.raises(ValueError):
        publication.exercise(owned)


class BindingDatabase:
    def __init__(self, observed, *, namespaces=None, public_tables=0):
        self.observed = observed
        self.namespaces = namespaces or ["public"]
        self.public_tables = public_tables
        self.calls = 0

    def execute(self, _sql):
        self.calls += 1
        return SimpleNamespace(one=lambda: self.observed,
                               scalars=lambda: SimpleNamespace(all=lambda: self.namespaces))

    def scalar(self, _sql):
        return self.public_tables


def test_exact_server_binding_and_empty_cluster_are_verified(owned):
    values = [str(owned.root / "data"), owned.owner, owned.port, "127.0.0.1"]
    publication.verify_fresh_target(BindingDatabase(values), owned, owned.root)


@pytest.mark.parametrize("index,value", [(0, "C:/original-data"), (1, "wrong-owner"),
                                          (2, 5432), (3, "192.0.2.1")])
def test_original_or_remote_server_binding_refused_before_schema_queries(owned, index, value):
    values = [str(owned.root / "data"), owned.owner, owned.port, "127.0.0.1"]
    values[index] = value
    db = BindingDatabase(values)
    with pytest.raises(RuntimeError, match="binding mismatch"):
        publication.verify_fresh_target(db, owned, owned.root)
    assert db.calls == 1


@pytest.mark.parametrize("schemas,tables", [(["public", "classsync_identity"], 0),
                                           (["public", "unrelated"], 0), (["public"], 1)])
def test_existing_schema_or_public_data_never_reaches_fixture_migration(owned, schemas, tables):
    db = BindingDatabase([str(owned.root / "data"), owned.owner, owned.port, "127.0.0.1"],
                          namespaces=schemas, public_tables=tables)
    with pytest.raises(RuntimeError, match="new empty cluster"):
        publication.verify_fresh_target(db, owned, owned.root)


def test_database_binding_failure_disposes_both_engines_without_migration(owned, monkeypatch):
    closed = []
    engines = [SimpleNamespace(dispose=lambda: closed.append("owner")),
               SimpleNamespace(dispose=lambda: closed.append("runtime"))]
    monkeypatch.setattr(publication, "engine_for", lambda _c, bootstrap=False:
                        engines[0 if bootstrap else 1])
    monkeypatch.setattr(publication, "bounded_runtime", lambda _c: engines[1])
    monkeypatch.setattr(publication, "check_pool", lambda *_a: None)

    @contextmanager
    def transaction(_engine):
        yield BindingDatabase([str(owned.root / "data"), "wrong-owner", owned.port, "127.0.0.1"])

    monkeypatch.setattr(publication, "transaction", transaction)
    monkeypatch.setattr(publication, "prepare_source", lambda *_a: pytest.fail("Fixture mutated"))
    with pytest.raises(RuntimeError, match="binding mismatch"):
        publication.exercise(owned)
    assert closed == ["runtime", "owner"]


def test_runtime_explicitly_matches_bounded_provider_pool(monkeypatch):
    observed = {}
    parameters = {"user": "generated-runtime", "host": "127.0.0.1", "port": 59123,
                  "dbname": "postgres", "require_auth": "sspi"}

    def engine(url, **options):
        observed.update(url=url, **options)
        return "bounded-engine"

    monkeypatch.setattr(publication, "postgres_engine", engine)
    assert publication.bounded_runtime(SimpleNamespace(parameters=lambda: parameters)) == (
        "bounded-engine"
    )
    assert observed["connect_args"] == parameters
    assert observed["pool_size"] == 5 and observed["max_overflow"] == 0
    assert observed["pool_timeout"] == 3
    assert observed["url"].host == "127.0.0.1" and observed["url"].port == 59123


@pytest.mark.parametrize("overflow,timeout,checkedout", [(10, 3, 5), (0, 30, 5), (0, 3, 4)])
def test_pool_exhaustion_cannot_be_claimed_for_unbounded_or_unheld_pool(
    overflow, timeout, checkedout,
):
    pool = SimpleNamespace(size=lambda: 5, _max_overflow=overflow, timeout=lambda: timeout,
                           checkedout=lambda: checkedout)
    with pytest.raises(RuntimeError, match="bounded provider pool"):
        publication.check_pool(SimpleNamespace(pool=pool), exhausted=True)


def test_wrong_negative_error_or_synthetic_success_cannot_pass_qualification():
    with pytest.raises(RuntimeError, match="unexpectedly succeeded"):
        publication.must_fail(lambda: {"status": "sample success"}, "required-error")

    def wrong_error():
        raise publication.DraftError(503, "wrong-error", "Generated failure")

    with pytest.raises(RuntimeError, match="Wrong publication negative"):
        publication.must_fail(wrong_error, "required-error", 409)


def test_missing_output_parent_prevents_cluster_start(tmp_path, monkeypatch):
    monkeypatch.setattr(publication, "qualify", lambda *_a: pytest.fail("Cluster started"))
    with pytest.raises(RuntimeError, match="New output required"):
        publication.main(["--bin", str(tmp_path), "--output", str(tmp_path / "missing/out.json")])


def test_failed_cluster_never_writes_success_output(tmp_path, monkeypatch):
    output = tmp_path / "never-success.json"

    def failed(*_a):
        raise RuntimeError("generated qualification failure")

    monkeypatch.setattr(publication, "qualify", failed)
    with pytest.raises(RuntimeError, match="qualification failure"):
        publication.main(["--bin", str(tmp_path), "--output", str(output)])
    assert not output.exists()


def helper_catalog():
    return {"owner": "generated-migrator", "security_definer": True, "arguments": 0,
            "result_type": "boolean", "configuration": ["search_path=pg_catalog"],
            "superuser": False, "bypass_rls": False}


def test_constrained_nonprivileged_helper_catalog_is_accepted():
    publication.validate_helper_catalog(helper_catalog(), "generated-migrator")


@pytest.mark.parametrize("field,value", [
    ("owner", "bootstrap-owner"), ("security_definer", False), ("arguments", 1),
    ("result_type", "text"), ("configuration", ["search_path=public,pg_catalog"]),
    ("superuser", True), ("bypass_rls", True),
])
def test_privileged_or_redirectable_helper_catalog_cannot_be_qualified(field, value):
    with pytest.raises(RuntimeError, match="constrained nonprivileged definer"):
        publication.validate_helper_catalog(helper_catalog() | {field: value}, "generated-migrator")


def writer_states():
    before = {table: [] for table in publication.TABLES}
    before["solver_runs"] = [{"id": "generated-run", "checksum": "unchanged-run"}]
    before["drafts"] = [{"id": "generated-draft", "checksum": "unchanged-draft"}]
    before["published_versions"] = [{"id": "old-version", "revision": 3, "checksum": "immutable"}]
    before["publication_heads"] = [{"period_id": "generated-period", "owner_uid": "uid-admin",
                                    "revision": 3}]
    old_payload = publication.encode({"id": "generated-restriction", "revision": 3,
                                      "reason": "old"})
    before["room_restrictions"] = [{"id": "generated-restriction", "revision": 3,
                                    "payload": old_payload,
                                    "checksum": publication.digest(old_payload)}]
    old_snapshot = {"revision": 3, "payload": old_payload}
    before["restriction_audit"] = [{"revision": 3, "new_snapshot": old_snapshot}]
    after = deepcopy(before)
    after["published_versions"].append({"id": "new-version", "revision": 4})
    after["publication_heads"][0]["revision"] = 4
    restriction = {"id": "generated-restriction", "revision": 4, "reason": "new"}
    payload = publication.encode(restriction)
    after["room_restrictions"][0].update(revision=4, payload=payload,
                                         checksum=publication.digest(payload))
    after["restriction_audit"].append({"revision": 4, "old_snapshot": old_snapshot,
                                        "new_snapshot": {"revision": 4, "payload": payload}})
    return before, after, {"id": "new-version", "revision": 4}, restriction


def test_one_committed_writer_transition_preserves_immutable_history_and_audit_chain():
    publication.check_writer_transition(*writer_states())


@pytest.mark.parametrize("tamper", ["private-run", "private-draft", "old-version", "extra-version",
                                  "head-owner", "restriction-checksum", "old-audit", "audit-chain"])
def test_writer_race_cannot_claim_success_after_unrelated_or_immutable_state_change(tamper):
    before, after, receipt, restriction = writer_states()
    if tamper == "private-run":
        after["solver_runs"][0]["checksum"] = "changed"
    elif tamper == "private-draft":
        after["drafts"][0]["checksum"] = "changed"
    elif tamper == "old-version":
        after["published_versions"][0]["checksum"] = "changed"
    elif tamper == "extra-version":
        after["published_versions"].append({"id": "unexpected-version", "revision": 5})
    elif tamper == "head-owner":
        after["publication_heads"][0]["owner_uid"] = "another-admin"
    elif tamper == "restriction-checksum":
        after["room_restrictions"][0]["checksum"] = "changed"
    elif tamper == "old-audit":
        after["restriction_audit"][0]["revision"] = 99
    else:
        after["restriction_audit"][-1]["old_snapshot"] = {"forged": "previous"}
    with pytest.raises(RuntimeError):
        publication.check_writer_transition(before, after, receipt, restriction)

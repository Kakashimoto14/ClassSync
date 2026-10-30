"""Publication writes must not recurse through record-scoped head policies."""

from importlib import import_module
from unittest.mock import Mock


def test_corrective_write_policy_has_no_head_dependency_and_keeps_current_admin(monkeypatch):
    migration = import_module(
        "classync_persistence.migrations.versions.0011_publication_policy_cycle"
    )
    assert migration.down_revision == "0010_legacy_publication_archive"
    operation = Mock()
    monkeypatch.setattr(migration, "op", operation)
    migration.upgrade()
    statements = [call.args[0] for call in operation.execute.call_args_list]
    assert len(statements) == 1
    sql = statements[0]
    assert "ALTER POLICY publication_create ON classsync_scheduling.published_versions" in sql
    assert "publication_heads" not in sql
    assert "owner_uid=current_setting('classsync.uid',true)" in sql
    assert "m.state='active'" in sql and "'administrator'=ANY(m.roles)" in sql
    assert "t.firebase_project_id=current_setting('classsync.project_id',true)" in sql
    assert "tenant_id=current_setting('classsync.tenant_id',true)" in sql
    assert "BYPASSRLS" not in sql and "SECURITY DEFINER" not in sql
    operation.reset_mock()
    migration.downgrade()
    old = operation.execute.call_args.args[0]
    assert "publication_heads" in old
    assert "h.revision=published_versions.revision-1" in old


def test_atomicity_and_role_projection_constraints_are_retained():
    state = import_module("classync_persistence.migrations.versions.0007_publication_state")
    from pathlib import Path

    sql = Path(state.__file__).read_text()
    assert "DEFERRABLE INITIALLY DEFERRED" in sql
    assert "h.revision>=NEW.revision" in sql
    assert "NEW.revision<>OLD.revision+1" in sql
    assert "UNIQUE (tenant_id,dataset,period_id,revision)" in sql
    projection = import_module(
        "classync_persistence.migrations.versions.0009_publication_record_projection"
    )
    assert "$.draft.input_snapshot.enrollments[*]" in projection.RECORD_SCOPE
    assert "$.draft.generation_result.assignments[*]" in projection.RECORD_SCOPE

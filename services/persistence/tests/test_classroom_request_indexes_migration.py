from importlib import import_module
from unittest.mock import Mock


def test_classroom_request_indexes_migration_targets_existing_schema_and_table(monkeypatch):
    migration = import_module(
        "classync_persistence.migrations.versions.0022_classroom_request_indexes"
    )
    operation = Mock()
    monkeypatch.setattr(migration, "op", operation)

    migration.upgrade()

    upgrade_sql = "\n".join(str(call.args[0]) for call in operation.execute.call_args_list)
    assert "ON classsync_scheduling.classroom_requests" in upgrade_sql
    assert "(tenant_id, owner_uid, created_at DESC)" in upgrade_sql
    assert "(tenant_id, created_at DESC)" in upgrade_sql

    operation.reset_mock()
    migration.downgrade()
    downgrade_sql = "\n".join(str(call.args[0]) for call in operation.execute.call_args_list)
    assert "DROP INDEX IF EXISTS classsync_scheduling.classroom_requests_tenant_created_idx" in (
        downgrade_sql
    )
    assert (
        "DROP INDEX IF EXISTS "
        "classsync_scheduling.classroom_requests_tenant_owner_created_idx"
    ) in downgrade_sql

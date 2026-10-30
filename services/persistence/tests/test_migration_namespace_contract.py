"""Catch misspelled schema dependencies across the complete migration graph."""

import re
from importlib import import_module
from pathlib import Path
from unittest.mock import Mock

from classync_persistence import legacy_publication_archive, schema


def test_migration_sql_references_only_namespaces_created_by_prior_upgrades(monkeypatch):
    known = {"public", "pg_catalog"}
    versions = Path(schema.__file__).parent / "migrations" / "versions"
    prior = None
    for file in sorted(versions.glob("[0-9]*.py")):
        migration = import_module(f"classync_persistence.migrations.versions.{file.stem}")
        assert migration.down_revision == prior
        prior = migration.revision
        operation = Mock()
        monkeypatch.setattr(migration, "op", operation)
        migration.upgrade()
        for call in operation.execute.call_args_list:
            sql = call.args[0]
            known.update(re.findall(r"CREATE SCHEMA (\w+)", sql))
            references = set(re.findall(r"\b(class\w+_(?:identity|academic|scheduling))\.", sql))
            assert references <= known, (migration.revision, references - known)
        operation.reset_mock()
        migration.downgrade()
        for call in operation.execute.call_args_list:
            sql = call.args[0]
            references = set(re.findall(r"\b(class\w+_(?:identity|academic|scheduling))\.", sql))
            assert references <= known, (migration.revision, references - known)
            assert "DROP SCHEMA" not in sql or "CASCADE" not in sql
    assert known == {"public", "pg_catalog", "classsync_identity", "classsync_academic",
                     "classsync_scheduling"}


def test_archive_importer_uses_the_canonical_migration_namespaces():
    source = Path(legacy_publication_archive.__file__).read_text()
    references = set(re.findall(r"\b(class\w+_(?:identity|academic|scheduling))\.", source))
    assert references == {"classsync_scheduling"}
    assert "SELECT classsync_scheduling.lock_publication_authority()" in source

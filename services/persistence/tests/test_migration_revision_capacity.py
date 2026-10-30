"""Revision identifiers must fit the version table before Alembic stamps them."""

from importlib import import_module
from pathlib import Path
from unittest.mock import Mock

from alembic.config import Config
from alembic.script import ScriptDirectory
from classync_persistence import schema


def test_first_overlength_revision_widens_version_column_before_policy_changes(monkeypatch):
    migration = import_module(
        "classync_persistence.migrations.versions.0009_publication_record_projection"
    )
    operation = Mock()
    monkeypatch.setattr(migration, "op", operation)
    migration.upgrade()
    assert operation.execute.call_args_list[0].args == (
        "ALTER TABLE public.alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)",
    )
    operation.reset_mock()
    migration.downgrade()
    assert all("version_num" not in str(call) for call in operation.mock_calls)


def test_all_revision_ids_and_parent_links_fit_supported_capacity():
    config = Config()
    config.set_main_option("script_location", str(Path(schema.__file__).parent / "migrations"))
    graph = ScriptDirectory.from_config(config)
    assert len(graph.get_heads()) == 1
    for revision in graph.walk_revisions():
        assert len(revision.revision) <= 128, revision.revision
        if revision.revision < "0009":
            assert len(revision.revision) <= 32, revision.revision
        parents = revision.down_revision
        for parent in (parents if isinstance(parents, tuple) else (parents,)):
            assert parent is None or len(parent) <= 128

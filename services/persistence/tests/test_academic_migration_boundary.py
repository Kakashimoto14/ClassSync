import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.postgres_academic_migration_qualification import import_generated_snapshot
from scripts.postgres_disposable import create_root


def test_academic_rehearsal_rejects_outside_source_before_opening_it(tmp_path):
    root = create_root(Path(tempfile.gettempdir()))
    sentinel = tmp_path / "synthetic-source.sqlite3"
    sentinel.write_bytes(b"protected sentinel; not opened as SQLite")
    source = SimpleNamespace(path=sentinel)
    with pytest.raises(RuntimeError, match="generated synthetic source"):
        import_generated_snapshot(SimpleNamespace(root=root), object(), source, "period")
    assert sentinel.read_bytes() == b"protected sentinel; not opened as SQLite"


def test_academic_rehearsal_rejects_arbitrary_file_inside_marked_root():
    root = create_root(Path(tempfile.gettempdir()))
    sentinel = root / "other.sqlite3"
    sentinel.write_bytes(b"not a generated source")
    with pytest.raises(RuntimeError, match="generated synthetic source"):
        import_generated_snapshot(
            SimpleNamespace(root=root), object(), SimpleNamespace(path=sentinel), "period"
        )
    assert sentinel.read_bytes() == b"not a generated source"

"""Exercise the qualifier's actual patch block without PostgreSQL or a solver."""

import ast
import inspect
import sqlite3
from contextlib import closing
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from scripts import postgres_publication_repository_qualification as qualification
from scripts.postgres_disposable import create_root


def application_guard():
    source = ast.parse(inspect.getsource(qualification.exercise))
    guards = [node for node in ast.walk(source) if isinstance(node, ast.With)
              and any(isinstance(item.context_expr, ast.Call)
                      and isinstance(item.context_expr.func, ast.Name)
                      and item.context_expr.func.id == "patch"
                      and item.context_expr.args
                      and isinstance(item.context_expr.args[0], ast.Constant)
                      and item.context_expr.args[0].value == "sqlite3.connect"
                      for item in node.items)]
    assert len(guards) == 1
    guard = guards[0]
    calls = [node for node in ast.walk(guard) if isinstance(node, ast.Call)]
    assert any(isinstance(call.func, ast.Attribute) and call.func.attr == "publish"
               for call in calls)
    assert not any(isinstance(call.func, ast.Name) and call.func.id in {
        "legacy_archive_probe", "prepare_source",
    } for call in calls)
    return compile(ast.Module(body=[guard], type_ignores=[]), "actual_application_guard", "exec")


@pytest.mark.parametrize("outcome", ["success", "sqlite-fallback", "application-error"])
def test_guard_restores_connect_before_generated_archive(outcome, tmp_path, monkeypatch):
    original = sqlite3.connect

    def publish(_body, *, commit):
        if outcome == "sqlite-fallback":
            sqlite3.connect(":memory:")
        if outcome == "application-error":
            raise RuntimeError("generated operation failure")
        return {"status": "published" if commit else "ready-for-review",
                "revision": 1, "occurrences": 1}

    namespace = dict(patch=patch, repo=SimpleNamespace(publish=publish), body=object(),
                     require=qualification.require, state=lambda _owner: {},
                     before={}, owner=object())
    try:
        if outcome == "sqlite-fallback":
            with pytest.raises(AssertionError, match="SQLite fallback prohibited"):
                exec(application_guard(), namespace)
        elif outcome == "application-error":
            with pytest.raises(RuntimeError, match="generated operation failure"):
                exec(application_guard(), namespace)
        else:
            exec(application_guard(), namespace)
    finally:
        assert sqlite3.connect is original
    monkeypatch.setattr(qualification.tempfile, "gettempdir", lambda: str(tmp_path))
    root = create_root(tmp_path)
    owned = SimpleNamespace(root=root)
    source = qualification.checked_connection(owned) / "legacy-publication-source.sqlite"
    with closing(sqlite3.connect(source)) as db:
        db.execute("CREATE TABLE generated(value TEXT)")
        db.execute("INSERT INTO generated VALUES ('retained evidence')")
        db.commit()
    with closing(sqlite3.connect(source)) as db:
        assert db.execute("SELECT value FROM generated").fetchone() == ("retained evidence",)


def test_archive_rejects_external_unmarked_source_before_opening_sqlite(tmp_path, monkeypatch):
    monkeypatch.setattr(sqlite3, "connect", lambda *_a, **_k: pytest.fail("External SQLite opened"))
    with pytest.raises(ValueError):
        qualification.legacy_archive_probe(
            SimpleNamespace(root=tmp_path / "original"), object(), object(), "unused", object(),
        )

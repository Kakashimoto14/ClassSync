import json
from types import SimpleNamespace

import pytest
from classync_persistence.database import postgres_engine
from sqlalchemy.engine import URL

from scripts.postgres_disposable import (
    DisposableConnection,
    create_root,
    finish_cluster,
    run_exercise,
)
from scripts.security.python_audit import verify_local_source


@pytest.mark.parametrize("driver", ["sqlite", "postgresql", "postgresql+psycopg2"])
def test_shared_boundary_rejects_other_drivers_before_connecting(driver):
    with pytest.raises(ValueError, match="PostgreSQL with Psycopg"):
        postgres_engine(URL.create(driver, database="never-opened"))


def test_shared_engine_hides_parameters_and_does_not_connect_on_creation():
    engine = postgres_engine(URL.create("postgresql+psycopg", database="never-opened"))
    try:
        assert engine.hide_parameters is True
        assert engine.echo is False
        assert engine.pool.checkedout() == 0
    finally:
        engine.dispose()


@pytest.mark.parametrize("directory", ["persistence", "api-contracts"])
def test_each_internal_package_requires_exact_local_editable_provenance(tmp_path, directory):
    def distribution(source, editable=True):
        return SimpleNamespace(read_text=lambda _: json.dumps({
            "url": source.as_uri(), "dir_info": {"editable": editable},
        }))

    source = tmp_path / "packages" / directory
    verify_local_source(distribution(source), tmp_path, directory)
    for wrong in (distribution(source, False), distribution(tmp_path / "another")):
        with pytest.raises(ValueError, match="NOT VERIFIED"):
            verify_local_source(wrong, tmp_path, directory)


def test_callback_failure_records_error_and_still_runs_owned_cleanup(tmp_path):
    root = create_root(tmp_path)
    evidence = {"stopped": False}
    calls = []

    def failed(_):
        raise RuntimeError("synthetic callback failure")

    with pytest.raises(RuntimeError, match="synthetic callback failure"):
        try:
            run_exercise(failed, None, evidence)
        finally:
            finish_cluster(root, tmp_path, lambda *args: calls.append(args), True, evidence)
    assert len(calls) == 1
    saved = json.loads((root / "qualification.json").read_text())
    assert saved["stopped"] is True
    assert saved["exercise_error"] == "synthetic callback failure"
    assert "exercise" not in saved


@pytest.mark.parametrize("variable", [
    "PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGPASSWORD", "PGPASSFILE", "PGOPTIONS",
])
def test_disposable_driver_rejects_ambient_libpq_redirects_before_path_or_connection(
    tmp_path, monkeypatch, variable,
):
    monkeypatch.setenv(variable, "must-not-be-used-or-printed")
    connection = DisposableConnection(tmp_path / "unmarked", 12345, "owner", "runtime")
    with pytest.raises(ValueError, match="Ambient PostgreSQL settings") as error:
        connection.parameters(bootstrap=True)
    assert "must-not-be-used-or-printed" not in str(error.value)

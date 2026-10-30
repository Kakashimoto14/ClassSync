import json
from types import SimpleNamespace

import pytest

from scripts import postgres_disposable as disposable


def test_new_marked_cluster_root_is_only_accepted_under_its_parent(tmp_path):
    root = disposable.create_root(tmp_path)
    assert disposable.checked_root(root, tmp_path) == root
    with pytest.raises(ValueError):
        disposable.checked_root(root, tmp_path / "another-parent")


@pytest.mark.parametrize("marker", [None, {}, {"kind": "other", "root": "other"}])
def test_unmarked_or_forged_root_is_rejected(tmp_path, marker):
    root = tmp_path / ("classsync-pg-" + "a" * 32)
    root.mkdir()
    if marker is not None:
        (root / "classsync-marker.json").write_text(json.dumps(marker))
    with pytest.raises(ValueError):
        disposable.checked_root(root, tmp_path)


def test_protected_existing_directory_is_not_a_disposable_cluster(tmp_path):
    root = tmp_path / "var"
    root.mkdir()
    (root / "classsync-marker.json").write_text(
        json.dumps(
            {
                "kind": disposable.MARKER,
                "root": str(root),
            }
        )
    )
    with pytest.raises(ValueError):
        disposable.checked_root(root, tmp_path)


def test_existing_generated_target_is_never_reused_or_overwritten(tmp_path, monkeypatch):
    monkeypatch.setattr(disposable, "uuid4", lambda: SimpleNamespace(hex="a" * 32))
    root = disposable.create_root(tmp_path)
    sentinel = root / "preserve.txt"
    sentinel.write_text("existing data")
    with pytest.raises(FileExistsError):
        disposable.create_root(tmp_path)
    assert sentinel.read_text() == "existing data"


def test_existing_output_is_preserved_before_any_cluster_launch(tmp_path, monkeypatch):
    sentinel = tmp_path / "original.sqlite3"
    sentinel.write_bytes(b"original contents")
    monkeypatch.setattr(disposable, "qualify", lambda _: pytest.fail("Cluster must not start"))
    with pytest.raises(ValueError):
        disposable.main(["--bin", str(tmp_path), "--output", str(sentinel)])
    assert sentinel.read_bytes() == b"original contents"


@pytest.mark.parametrize("started", [False, True])
def test_owned_cluster_is_stopped_even_if_start_failed_with_a_pid_file(tmp_path, started):
    root = disposable.create_root(tmp_path)
    (root / "data").mkdir()
    (root / "data" / "postmaster.pid").write_text("synthetic-pid-not-executed")
    calls = []
    evidence = {"stopped": False}
    disposable.finish_cluster(root, tmp_path, lambda *args: calls.append(args), started, evidence)
    assert calls == [("pg_ctl.exe", "-D", root / "data", "-w", "-t", "20", "stop", "-m", "fast")]
    assert json.loads((root / "qualification.json").read_text())["stopped"] is True


@pytest.mark.parametrize("failure", [RuntimeError("stop failed"), TimeoutError("stop timed out")])
def test_shutdown_failure_is_persisted_without_claiming_stopped(tmp_path, failure):
    root = disposable.create_root(tmp_path)
    (root / "data").mkdir()
    evidence = {"stopped": False}

    def failed(*args):
        raise failure

    with pytest.raises(type(failure)):
        disposable.finish_cluster(root, tmp_path, failed, True, evidence)
    saved = json.loads((root / "qualification.json").read_text())
    assert saved["stopped"] is False
    assert saved["server_state"] == "stop_failed"
    assert saved["cleanup_error"] == str(failure)

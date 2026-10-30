"""The scale harness may never select existing databases or overwrite evidence."""

from types import SimpleNamespace

import pytest

from scripts import postgres_publication_scale_qualification as scale


def test_scale_rejects_unmarked_root_before_opening_database(monkeypatch, tmp_path):
    monkeypatch.setattr(scale, "engine_for", lambda *_a, **_k: pytest.fail("Database opened"))
    with pytest.raises(ValueError):
        scale.exercise(SimpleNamespace(root=tmp_path / "original"))


@pytest.mark.parametrize("existing", [False, True])
def test_scale_rejects_missing_parent_or_existing_evidence(monkeypatch, tmp_path, existing):
    output = tmp_path / "existing.json" if existing else tmp_path / "missing" / "evidence.json"
    if existing:
        output.write_text("preserve", encoding="utf-8")
    monkeypatch.setattr(scale, "qualify", lambda *_a: pytest.fail("Cluster started"))
    with pytest.raises(RuntimeError, match="New output required"):
        scale.main(["--bin", str(tmp_path), "--output", str(output)])
    if existing:
        assert output.read_text(encoding="utf-8") == "preserve"


def test_failed_scale_never_emits_success_evidence(monkeypatch, tmp_path):
    output = tmp_path / "evidence.json"

    def failed(*_a):
        raise RuntimeError("generated workload failure")

    monkeypatch.setattr(scale, "qualify", failed)
    with pytest.raises(RuntimeError, match="generated workload failure"):
        scale.main(["--bin", str(tmp_path), "--output", str(output)])
    assert not output.exists()

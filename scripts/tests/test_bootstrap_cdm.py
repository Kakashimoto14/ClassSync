import json

import pytest

from scripts.seed_bootstrap_cdm import seed
from services.academic.app.repository import AcademicRepository


def test_bootstrap_seed_is_idempotent_and_stays_synthetic(tmp_path):
    path = tmp_path / "cdm.bootstrap-sandbox.sqlite3"

    first = seed(path)
    second = seed(path)
    repo = AcademicRepository(path)
    snapshots = repo.periods("sandbox", "development-academic-sandbox")
    snapshot = repo.snapshot("sandbox", "development-academic-sandbox", snapshots[0].id)
    kinds = [item.record.kind for item in snapshot.records]

    assert first["source"] == second["source"] == "owner_bootstrap_seed"
    assert len(snapshots) == 1
    assert kinds.count("programs") == 9
    assert kinds.count("resources") == 53
    assert kinds.count("subjects") == 10
    assert kinds.count("faculty") == 4
    assert kinds.count("sections") == 2
    assert kinds.count("offerings") == 20
    assert first["official_publication_created"] is False
    assert first["student_identity_records_created"] is False
    assert json.loads(path.with_suffix(".manifest.json").read_text(encoding="utf-8"))["source"] == (
        "owner_bootstrap_seed"
    )
    assert all(
        not item.record.identity_verified
        for item in snapshot.records
        if item.record.kind == "sections"
    )
    assert all(
        item.record.source == "cdm-provisional"
        and item.record.capacity is None
        for item in snapshot.records
        if item.record.kind == "resources"
    )


def test_bootstrap_seed_refuses_non_sandbox_database_filename(tmp_path):
    with pytest.raises(ValueError, match=r"isolated \*\.bootstrap-sandbox\.sqlite3"):
        seed(tmp_path / "institutional.sqlite3")

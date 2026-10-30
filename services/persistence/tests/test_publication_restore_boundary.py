"""Fail closed before source/target mutation; restore every publication object."""

from types import SimpleNamespace

import pytest

from scripts import postgres_publication_restore_qualification as restore


def manifest():
    lines = [f"{i}; 0 1 SCHEMA - {name} generated-owner"
             for i, name in enumerate(("public", *restore.SCHEMA_NAMES), 1)]
    for descriptor in ("TABLE", "TABLE DATA"):
        for table in (*restore.TABLES, "public.alembic_version"):
            namespace, name = table.split(".")
            lines.append(f"{len(lines)+1}; 0 1 {descriptor} {namespace} {name} generated-owner")
    lines.append("100; 0 1 ACL classsync_scheduling legacy_publication_archive generated-owner")
    return "\n".join(lines)


def test_restore_manifest_includes_all_publication_and_archive_data_acl():
    original = manifest()
    filtered = restore.checked_toc(original)
    assert "SCHEMA - public " not in filtered
    assert "TABLE DATA classsync_scheduling legacy_publication_archive" in filtered
    assert "ACL classsync_scheduling legacy_publication_archive" in filtered
    assert len(original.splitlines()) - len(filtered.splitlines()) == 1


@pytest.mark.parametrize("change", ["missing-archive", "extra-table", "extra-schema", "duplicate"])
def test_restore_rejects_incomplete_or_unexpected_manifest(change):
    listing = manifest()
    if change == "missing-archive":
        missing = "TABLE DATA classsync_scheduling legacy_publication_archive"
        listing = "\n".join(line for line in listing.splitlines() if missing not in line)
    elif change == "extra-table":
        listing += "\n101; 0 1 TABLE public unrelated generated-owner"
    elif change == "extra-schema":
        listing += "\n101; 0 1 SCHEMA - unrelated generated-owner"
    else:
        listing += "\n101; 0 1 TABLE DATA classsync_scheduling published_versions generated-owner"
    with pytest.raises(RuntimeError):
        restore.checked_toc(listing)


def test_restore_rejects_unmarked_source_before_opening_engine(tmp_path, monkeypatch):
    monkeypatch.setattr(restore, "engine_for", lambda *_a, **_k: pytest.fail("Database opened"))
    with pytest.raises(ValueError):
        restore.exercise(SimpleNamespace(root=tmp_path / "original"))


def test_restore_rejects_existing_output_before_cluster_start(tmp_path, monkeypatch):
    output = tmp_path / "existing.json"
    output.write_text("preserve")
    monkeypatch.setattr(restore, "qualify", lambda *_a: pytest.fail("Cluster started"))
    with pytest.raises(RuntimeError, match="New evidence"):
        restore.main(["--bin", str(tmp_path), "--output", str(output)])
    assert output.read_text() == "preserve"

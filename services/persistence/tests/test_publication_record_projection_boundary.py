"""Bound PostgreSQL published projections to the current member's own records."""

from importlib import import_module
from pathlib import Path


def test_projection_migration_requires_current_record_and_payload_membership():
    migration = import_module(
        "classync_persistence.migrations.versions.0009_publication_record_projection"
    )
    assert migration.down_revision == "0008_publication_transactions"
    assert "m.state='active'" in migration.RECORD_SCOPE
    assert "'student'=ANY(m.roles)" in migration.RECORD_SCOPE
    assert "'teacher'=ANY(m.roles)" in migration.RECORD_SCOPE
    assert "m.student_id=current_setting('classsync.record_id',true)" in migration.RECORD_SCOPE
    assert "m.faculty_id=current_setting('classsync.record_id',true)" in migration.RECORD_SCOPE
    assert "$.draft.input_snapshot.enrollments[*]" in migration.RECORD_SCOPE
    assert "$.draft.generation_result.assignments[*]" in migration.RECORD_SCOPE
    assert (
        "firebase_project_id=current_setting('classsync.project_id',true)"
        in migration.RECORD_SCOPE
    )


def test_projection_policy_exposes_head_only_for_an_allowed_immutable_version():
    migration = import_module(
        "classync_persistence.migrations.versions.0009_publication_record_projection"
    )
    source = Path(migration.__file__).read_text()
    assert "ALTER POLICY publication_read ON classsync_scheduling.published_versions" in source
    assert "ALTER POLICY publication_read ON classsync_scheduling.publication_heads" in source
    assert "v.revision=publication_heads.revision" in source
    assert "def downgrade()" in source
    assert source.count("USING ({ADMIN})") == 2


def test_repository_sets_verified_projection_context_and_rejects_stale_visible_rows():
    source = Path(
        "services/scheduling/app/postgres_publication_repository.py"
    ).read_text()
    assert "set_config('classsync.role', :role, true)" in source
    assert "set_config('classsync.record_id', :record, true)" in source
    assert "AND :role=ANY(m.roles)" in source
    assert 'visible[-1]["revision"] != current' in source
    assert '"projection_forbidden"' in source

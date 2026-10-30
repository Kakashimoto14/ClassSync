"""Expose only published snapshots containing the current user's records."""

from alembic import op

revision = "0009_publication_record_projection"
down_revision = "0008_publication_transactions"
branch_labels = None
depends_on = None

ADMIN = """(
    tenant_id=current_setting('classsync.tenant_id',true)
    AND EXISTS (
        SELECT 1 FROM classsync_identity.memberships m
        JOIN classsync_identity.tenants t ON t.id=m.tenant_id
        WHERE m.tenant_id=current_setting('classsync.tenant_id',true)
          AND m.uid=current_setting('classsync.uid',true)
          AND m.state='active' AND 'administrator'=ANY(m.roles)
          AND t.firebase_project_id=current_setting('classsync.project_id',true)
    )
)"""

RECORD_SCOPE = """(
    tenant_id=current_setting('classsync.tenant_id',true)
    AND EXISTS (
        SELECT 1 FROM classsync_identity.memberships m
        JOIN classsync_identity.tenants t ON t.id=m.tenant_id
        WHERE m.tenant_id=current_setting('classsync.tenant_id',true)
          AND m.uid=current_setting('classsync.uid',true) AND m.state='active'
          AND t.firebase_project_id=current_setting('classsync.project_id',true)
          AND (
            (current_setting('classsync.role',true)='student'
             AND 'student'=ANY(m.roles)
             AND m.student_id=current_setting('classsync.record_id',true)
             AND jsonb_path_exists(payload::jsonb,
                 '$.draft.input_snapshot.enrollments[*] ? (@.student_id == $record)',
                 jsonb_build_object('record',to_jsonb(m.student_id))))
            OR
            (current_setting('classsync.role',true)='teacher'
             AND 'teacher'=ANY(m.roles)
             AND m.faculty_id=current_setting('classsync.record_id',true)
             AND jsonb_path_exists(payload::jsonb,
                 '$.draft.generation_result.assignments[*] ? (@.teacher_id == $record)',
                 jsonb_build_object('record',to_jsonb(m.faculty_id))))
          )
    )
)"""


def upgrade():
    # Alembic stamps this 34-character ID only after upgrade() returns. The
    # existing version table belongs to the same migration role; widen it in
    # the caller's transaction before Alembic attempts that stamp.
    op.execute(
        "ALTER TABLE public.alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)"
    )
    # Restrict end-user reads to immutable published snapshots containing that
    # user's record. Heads are visible only when their exact version is visible.
    op.execute(
        "ALTER POLICY publication_read ON classsync_scheduling.published_versions "
        f"USING ({ADMIN} OR {RECORD_SCOPE})"
    )
    head_scope = f"""(
        {ADMIN}
        OR EXISTS (
            SELECT 1 FROM classsync_scheduling.published_versions v
            WHERE v.tenant_id=publication_heads.tenant_id
              AND v.dataset=publication_heads.dataset
              AND v.period_id=publication_heads.period_id
              AND v.revision=publication_heads.revision
        )
    )"""
    op.execute(
        "ALTER POLICY publication_read ON classsync_scheduling.publication_heads "
        f"USING ({head_scope})"
    )


def downgrade():
    # Retain capacity: later upgrades and revision history must remain lossless.
    op.execute(
        "ALTER POLICY publication_read ON classsync_scheduling.publication_heads "
        f"USING ({ADMIN})"
    )
    op.execute(
        "ALTER POLICY publication_read ON classsync_scheduling.published_versions "
        f"USING ({ADMIN})"
    )

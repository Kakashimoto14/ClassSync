"""Restore the student roster audit events that 0026 dropped from the activity constraint."""

from alembic import op

revision = "0027_roster_audit_events"
down_revision = "0026_archived_period_audit"
branch_labels = None
depends_on = None


def upgrade():
    # 0026 rebuilt this CHECK from a pre-0025 list, so every roster create, update and
    # delete failed at its audit insert. This is a superset: existing rows stay valid.
    op.execute(
        "ALTER TABLE classsync_scheduling.administrator_activity "
        "DROP CONSTRAINT administrator_activity_event_type_check"
    )
    op.execute("""
        ALTER TABLE classsync_scheduling.administrator_activity
        ADD CONSTRAINT administrator_activity_event_type_check CHECK (event_type IN (
            'academic.period.created','academic.period.archived',
            'academic.record.created','academic.record.updated','academic.record.deleted',
            'academic.calendar.saved','scheduling.draft.saved',
            'scheduling.publication.published','academic.student.created',
            'academic.student.updated','academic.student.deleted'
        ))
    """)


def downgrade():
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM classsync_scheduling.administrator_activity
                       WHERE entity_type='student_roster') THEN
                RAISE EXCEPTION 'Student roster audit rows must be retained';
            END IF;
        END $$
    """)
    op.execute(
        "ALTER TABLE classsync_scheduling.administrator_activity "
        "DROP CONSTRAINT administrator_activity_event_type_check"
    )
    op.execute("""
        ALTER TABLE classsync_scheduling.administrator_activity
        ADD CONSTRAINT administrator_activity_event_type_check CHECK (event_type IN (
            'academic.period.created','academic.period.archived',
            'academic.record.created','academic.record.updated','academic.record.deleted',
            'academic.calendar.saved','scheduling.draft.saved',
            'scheduling.publication.published'
        ))
    """)

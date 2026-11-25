"""Record legacy academic-period archival as an append-only admin event."""

from alembic import op

revision = "0026_archived_period_audit"
down_revision = "0025_student_roster_crud"
branch_labels = None
depends_on = None


def upgrade():
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


def downgrade():
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM classsync_scheduling.administrator_activity
                       WHERE event_type='academic.period.archived') THEN
                RAISE EXCEPTION 'Period archive audit rows must be retained';
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
            'academic.period.created','academic.record.created','academic.record.updated',
            'academic.record.deleted','academic.calendar.saved','scheduling.draft.saved',
            'scheduling.publication.published'
        ))
    """)

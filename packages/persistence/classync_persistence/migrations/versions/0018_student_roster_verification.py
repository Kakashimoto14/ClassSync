"""Add fail-closed Registrar verification metadata to student identity records."""

from alembic import op

revision = "0018_student_roster_verification"
down_revision = "0017_administrator_activity_audit"
branch_labels = None
depends_on = None


def upgrade():
    # Existing identity rows are intentionally unverified. A migration must never
    # infer current enrollment or invent an institutional email address.
    op.execute("ALTER TABLE classsync_identity.students ADD COLUMN registered_email text")
    op.execute(
        "ALTER TABLE classsync_identity.students ADD COLUMN enrollment_status text "
        "NOT NULL DEFAULT 'unverified' CHECK "
        "(enrollment_status IN ('active','inactive','unverified'))"
    )
    op.execute(r"""
        ALTER TABLE classsync_identity.students
        ADD CONSTRAINT student_roster_verification_email_format CHECK (
            registered_email IS NULL OR (
                registered_email=lower(registered_email)
                AND registered_email ~ '^[a-z]+([.][a-z]+)*@student[.]pnm[.]edu[.]ph$'
                AND id ~ '^[0-9]{2}-[0-9]{5}$'
            )
        )
    """)
    op.execute("""
        ALTER TABLE classsync_identity.students
        ADD CONSTRAINT student_roster_active_email_required CHECK (
            enrollment_status <> 'active' OR registered_email IS NOT NULL
        )
    """)


def downgrade():
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM classsync_identity.students
                WHERE registered_email IS NOT NULL OR enrollment_status <> 'unverified'
            ) THEN
                RAISE EXCEPTION
                    'Student roster verification data must be exported before downgrade';
            END IF;
        END $$
    """)
    op.execute("ALTER TABLE classsync_identity.students DROP CONSTRAINT "
               "student_roster_active_email_required")
    op.execute("ALTER TABLE classsync_identity.students DROP CONSTRAINT "
               "student_roster_verification_email_format")
    op.execute("ALTER TABLE classsync_identity.students DROP COLUMN enrollment_status")
    op.execute("ALTER TABLE classsync_identity.students DROP COLUMN registered_email")

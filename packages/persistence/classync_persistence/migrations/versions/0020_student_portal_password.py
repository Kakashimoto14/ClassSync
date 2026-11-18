"""Track verified student portal-password onboarding completion."""

from alembic import op

revision = "0020_student_portal_password"
down_revision = "0019_student_email_challenges"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE classsync_identity.students
        ADD COLUMN password_configured boolean NOT NULL DEFAULT false
    """)
    op.execute("""
        ALTER TABLE classsync_identity.email_verification_challenges
        ADD COLUMN verified_at timestamptz
    """)
    op.execute("""
        ALTER TABLE classsync_identity.email_verification_challenges
        ADD CONSTRAINT email_verification_verified_consumed CHECK (
            verified_at IS NULL OR (consumed_at IS NOT NULL AND verified_at <= consumed_at)
        )
    """)


def downgrade():
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM classsync_identity.students WHERE password_configured
            ) OR EXISTS (
                SELECT 1 FROM classsync_identity.email_verification_challenges
                WHERE verified_at IS NOT NULL
            ) THEN
                RAISE EXCEPTION
                    'Student password onboarding evidence must be exported before downgrade';
            END IF;
        END $$
    """)
    op.execute("ALTER TABLE classsync_identity.email_verification_challenges "
               "DROP CONSTRAINT email_verification_verified_consumed")
    op.execute("ALTER TABLE classsync_identity.email_verification_challenges DROP COLUMN verified_at")
    op.execute("ALTER TABLE classsync_identity.students DROP COLUMN password_configured")

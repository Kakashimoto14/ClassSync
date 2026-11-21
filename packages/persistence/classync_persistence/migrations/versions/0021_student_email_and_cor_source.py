"""Allow domain-neutral student emails and record verification provenance."""

from alembic import op

revision = "0021_student_email_and_cor_source"
down_revision = "0020_student_portal_password"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE classsync_identity.students "
        "DROP CONSTRAINT student_roster_verification_email_format"
    )
    op.execute(r"""
        ALTER TABLE classsync_identity.students
        ADD CONSTRAINT student_roster_verification_email_format CHECK (
            registered_email IS NULL OR (
                length(registered_email) <= 320
                AND length(split_part(registered_email, '@', 1)) <= 64
                AND registered_email=lower(registered_email)
                AND registered_email ~ (
                    '^[a-z0-9!#$%&''*+/=?^_`{|}~-]+([.][a-z0-9!#$%&''*+/=?^_`{|}~-]+)*@'
                    || '([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?[.])+[a-z]{2,63}$'
                )
                AND id ~ '^[0-9]{2}-[0-9]{5}$'
            )
        )
    """)
    op.execute("""
        ALTER TABLE classsync_identity.students
        ADD COLUMN verification_source text NOT NULL DEFAULT 'unverified'
        CHECK (verification_source IN ('unverified','registrar_roster','cor_self_verified'))
    """)
    op.execute("""
        UPDATE classsync_identity.students SET verification_source='registrar_roster'
        WHERE enrollment_status='active' AND registered_email IS NOT NULL
    """)


def downgrade():
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM classsync_identity.students
                WHERE verification_source='cor_self_verified'
                  OR (registered_email IS NOT NULL AND registered_email !~
                      '^[a-z]+([.][a-z]+)*@student[.]pnm[.]edu[.]ph$')
            ) THEN
                RAISE EXCEPTION 'Personal student emails or COR records must be ' ||
                    'exported before downgrade';
            END IF;
        END $$
    """)
    op.execute("ALTER TABLE classsync_identity.students DROP COLUMN verification_source")
    op.execute("ALTER TABLE classsync_identity.students DROP CONSTRAINT "
               "student_roster_verification_email_format")
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

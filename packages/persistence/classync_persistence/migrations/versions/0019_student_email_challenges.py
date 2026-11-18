"""Persist single-use student email verification challenges."""

from alembic import op

revision = "0019_student_email_challenges"
down_revision = "0018_student_roster_verification"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE classsync_identity.email_verification_challenges (
            tenant_id text NOT NULL,
            uid text NOT NULL CHECK (length(btrim(uid)) BETWEEN 1 AND 128),
            challenge_id uuid NOT NULL,
            student_id text NOT NULL,
            otp_hmac bytea NOT NULL CHECK (octet_length(otp_hmac)=32),
            created_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
            expires_at timestamptz NOT NULL,
            resend_after timestamptz NOT NULL,
            failed_attempts smallint NOT NULL DEFAULT 0 CHECK (failed_attempts BETWEEN 0 AND 5),
            consumed_at timestamptz,
            PRIMARY KEY (tenant_id,uid,challenge_id),
            FOREIGN KEY (tenant_id,student_id)
                REFERENCES classsync_identity.students(tenant_id,id),
            CHECK (expires_at > created_at AND expires_at <= created_at + interval '5 minutes'),
            CHECK (resend_after >= created_at AND resend_after <= created_at + interval '60 seconds')
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX email_verification_one_active
        ON classsync_identity.email_verification_challenges (tenant_id,uid)
        WHERE consumed_at IS NULL
    """)
    op.execute("""
        CREATE INDEX email_verification_challenge_lookup
        ON classsync_identity.email_verification_challenges
            (tenant_id,uid,challenge_id) WHERE consumed_at IS NULL
    """)
    op.execute("ALTER TABLE classsync_identity.email_verification_challenges ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE classsync_identity.email_verification_challenges FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY email_verification_challenge_owner
        ON classsync_identity.email_verification_challenges
        USING (tenant_id=current_setting('classsync.tenant_id',true)
            AND uid=current_setting('classsync.uid',true))
        WITH CHECK (tenant_id=current_setting('classsync.tenant_id',true)
            AND uid=current_setting('classsync.uid',true))
    """)
    op.execute("REVOKE ALL ON classsync_identity.email_verification_challenges FROM PUBLIC")


def downgrade():
    op.execute("DROP TABLE classsync_identity.email_verification_challenges")

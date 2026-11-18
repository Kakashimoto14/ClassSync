"""Private account claims/invitations; no automatic institutional provisioning."""

from alembic import op

revision = "0014_account_onboarding"
down_revision = "0013_synthetic_review_period_mode"
branch_labels = None
depends_on = None


def upgrade():
    # Fail rather than silently permit a second account for an existing record.
    for column in ("student_id", "faculty_id"):
        op.execute(
            f"CREATE UNIQUE INDEX membership_unique_{column} "
            f"ON classsync_identity.memberships (tenant_id,{column}) "
            f"WHERE {column} IS NOT NULL"
        )
    op.execute("""
        CREATE TABLE classsync_identity.account_claims (
            tenant_id text NOT NULL REFERENCES classsync_identity.tenants(id),
            uid text NOT NULL CHECK(length(uid) BETWEEN 1 AND 128),
            student_id text NOT NULL CHECK(length(btrim(student_id)) BETWEEN 1 AND 128),
            state text NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','approved','rejected')),
            verification_reference text,
            decided_by text,
            created_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
            PRIMARY KEY(tenant_id,uid),
            CHECK ((state='pending') = (decided_by IS NULL)),
            CHECK (state <> 'approved' OR (verification_reference IS NOT NULL
                AND length(btrim(verification_reference)) BETWEEN 1 AND 500))
        )
    """)
    op.execute("""
        CREATE TABLE classsync_identity.faculty_invitations (
            tenant_id text NOT NULL REFERENCES classsync_identity.tenants(id),
            id uuid NOT NULL,
            faculty_id text NOT NULL,
            email text NOT NULL CHECK(length(email) BETWEEN 3 AND 320),
            token_hash text NOT NULL CHECK(length(token_hash)=64),
            issued_by text NOT NULL,
            expires_at timestamptz NOT NULL,
            used_by text,
            revoked boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
            PRIMARY KEY(tenant_id,id),
            FOREIGN KEY(tenant_id,faculty_id) REFERENCES classsync_identity.faculty(tenant_id,id),
            UNIQUE(tenant_id,token_hash),
            CHECK(expires_at > created_at AND expires_at <= created_at + interval '7 days')
        )
    """)
    for table in ("account_claims", "faculty_invitations"):
        own = "uid=current_setting('classsync.uid',true)" if table == "account_claims" else "false"
        op.execute(f"ALTER TABLE classsync_identity.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE classsync_identity.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY onboarding_scope ON classsync_identity.{table}
            USING (tenant_id=current_setting('classsync.tenant_id',true)
                AND ({own} OR current_setting('classsync.onboarding_admin',true)='true'))
            WITH CHECK (tenant_id=current_setting('classsync.tenant_id',true)
                AND ({own} OR current_setting('classsync.onboarding_admin',true)='true'))
        """)
        op.execute(f"REVOKE ALL ON classsync_identity.{table} FROM PUBLIC")


def downgrade():
    op.execute("DROP TABLE classsync_identity.faculty_invitations")
    op.execute("DROP TABLE classsync_identity.account_claims")
    for column in ("student_id", "faculty_id"):
        op.execute(f"DROP INDEX classsync_identity.membership_unique_{column}")

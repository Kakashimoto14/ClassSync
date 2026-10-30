"""Private administrator-owned academic metadata; no repository cutover."""

from alembic import op

revision = "0004_academic_period_metadata"
down_revision = "0003_membership_audit"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA classsync_academic")
    op.execute("""
        CREATE TABLE classsync_academic.period_metadata (
            tenant_id text NOT NULL,
            owner_uid text NOT NULL,
            id text NOT NULL CHECK (length(btrim(id)) BETWEEN 1 AND 80),
            title text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 160),
            revision bigint NOT NULL DEFAULT 1 CHECK (revision >= 1),
            created_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
            PRIMARY KEY (tenant_id, owner_uid, id),
            FOREIGN KEY (tenant_id, owner_uid)
                REFERENCES classsync_identity.memberships(tenant_id, uid)
        )
    """)
    op.execute("ALTER TABLE classsync_academic.period_metadata ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE classsync_academic.period_metadata FORCE ROW LEVEL SECURITY")
    predicate = """(
            tenant_id = current_setting('classsync.tenant_id', true)
            AND owner_uid = current_setting('classsync.uid', true)
            AND EXISTS (
                SELECT 1 FROM classsync_identity.memberships m
                JOIN classsync_identity.tenants t ON t.id = m.tenant_id
                WHERE m.tenant_id = period_metadata.tenant_id
                    AND m.uid = period_metadata.owner_uid
                    AND m.state = 'active' AND 'administrator' = ANY(m.roles)
                    AND t.firebase_project_id = current_setting('classsync.project_id', true)
            )
        )"""
    for name, command, clause in (("read", "SELECT", "USING"),
                                  ("create", "INSERT", "WITH CHECK")):
        op.execute(f"CREATE POLICY academic_owner_{name} "
                   f"ON classsync_academic.period_metadata FOR {command} {clause} {predicate}")
    op.execute("REVOKE ALL ON SCHEMA classsync_academic FROM PUBLIC")
    op.execute("REVOKE ALL ON classsync_academic.period_metadata FROM PUBLIC")


def downgrade():
    op.execute("DROP TABLE classsync_academic.period_metadata")
    op.execute("DROP SCHEMA classsync_academic")

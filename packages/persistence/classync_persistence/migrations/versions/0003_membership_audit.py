"""Atomic, append-only membership history; no inferred historical actors."""

from alembic import op

revision = "0003_membership_audit"
down_revision = "0002_membership_revision"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE classsync_identity.membership_audit (
            tenant_id text NOT NULL,
            subject_uid text NOT NULL,
            revision bigint NOT NULL CHECK (revision >= 1),
            actor_uid text NOT NULL CHECK (length(btrim(actor_uid)) BETWEEN 1 AND 128),
            database_session_user text NOT NULL,
            occurred_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
            old_snapshot jsonb,
            new_snapshot jsonb NOT NULL,
            PRIMARY KEY (tenant_id, subject_uid, revision),
            FOREIGN KEY (tenant_id, subject_uid)
                REFERENCES classsync_identity.memberships(tenant_id, uid),
            CHECK (new_snapshot->>'tenant_id' = tenant_id),
            CHECK (new_snapshot->>'uid' = subject_uid),
            CHECK ((new_snapshot->>'revision')::bigint = revision)
        )
    """)
    op.execute("ALTER TABLE classsync_identity.membership_audit ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE classsync_identity.membership_audit FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY identity_scope ON classsync_identity.membership_audit
            USING (tenant_id=current_setting('classsync.tenant_id', true)
                   AND subject_uid=current_setting('classsync.uid', true))
            WITH CHECK (tenant_id=current_setting('classsync.tenant_id', true)
                        AND subject_uid=current_setting('classsync.uid', true))
    """)
    op.execute("REVOKE ALL ON classsync_identity.membership_audit FROM PUBLIC")
    op.execute("""
        CREATE FUNCTION classsync_identity.append_membership_audit()
        RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
        DECLARE actor text := current_setting('classsync.actor_uid', true);
        BEGIN
            IF actor IS NULL OR length(btrim(actor)) NOT BETWEEN 1 AND 128 THEN
                RAISE EXCEPTION 'Explicit audit actor required' USING ERRCODE='42501';
            END IF;
            INSERT INTO classsync_identity.membership_audit
                (tenant_id, subject_uid, revision, actor_uid, database_session_user,
                 old_snapshot, new_snapshot)
            VALUES (NEW.tenant_id, NEW.uid, NEW.revision, actor, session_user,
                    CASE WHEN TG_OP='UPDATE' THEN to_jsonb(OLD) ELSE NULL END, to_jsonb(NEW));
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER membership_audit_append AFTER INSERT OR UPDATE
        ON classsync_identity.memberships FOR EACH ROW
        EXECUTE FUNCTION classsync_identity.append_membership_audit()
    """)
    op.execute("""
        CREATE FUNCTION classsync_identity.deny_membership_audit_mutation()
        RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog AS $$
        BEGIN
            RAISE EXCEPTION 'Membership audit is append-only' USING ERRCODE='42501';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER membership_audit_immutable BEFORE UPDATE OR DELETE
        ON classsync_identity.membership_audit FOR EACH ROW
        EXECUTE FUNCTION classsync_identity.deny_membership_audit_mutation()
    """)
    op.execute("""
        CREATE TRIGGER membership_audit_no_truncate BEFORE TRUNCATE
        ON classsync_identity.membership_audit FOR EACH STATEMENT
        EXECUTE FUNCTION classsync_identity.deny_membership_audit_mutation()
    """)
    for function in ("append_membership_audit", "deny_membership_audit_mutation"):
        op.execute(f"REVOKE ALL ON FUNCTION classsync_identity.{function}() FROM PUBLIC")


def downgrade():
    op.execute("DROP TRIGGER membership_audit_append ON classsync_identity.memberships")
    op.execute("DROP FUNCTION classsync_identity.append_membership_audit()")
    op.execute("DROP TABLE classsync_identity.membership_audit")
    op.execute("DROP FUNCTION classsync_identity.deny_membership_audit_mutation()")

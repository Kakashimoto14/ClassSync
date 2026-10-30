"""Guard membership revisions and identity keys independently of application code."""

from alembic import op

revision = "0002_membership_revision"
down_revision = "0001_identity"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE FUNCTION classsync_identity.guard_membership_revision()
        RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog AS $$
        BEGIN
            IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
                OR NEW.uid IS DISTINCT FROM OLD.uid THEN
                RAISE EXCEPTION 'Membership identity keys are immutable' USING ERRCODE='23514';
            END IF;
            IF NEW.revision IS NULL OR NEW.revision <> OLD.revision + 1 THEN
                RAISE EXCEPTION 'Membership revision must increment exactly once'
                    USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER membership_revision_guard BEFORE UPDATE
        ON classsync_identity.memberships FOR EACH ROW
        EXECUTE FUNCTION classsync_identity.guard_membership_revision()
    """)
    op.execute("REVOKE ALL ON FUNCTION classsync_identity.guard_membership_revision() FROM PUBLIC")


def downgrade():
    op.execute("DROP TRIGGER membership_revision_guard ON classsync_identity.memberships")
    op.execute("DROP FUNCTION classsync_identity.guard_membership_revision()")

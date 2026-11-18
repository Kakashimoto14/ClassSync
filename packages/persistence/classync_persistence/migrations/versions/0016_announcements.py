"""Tenant/audience announcements, separate from authoritative timetable publications."""

from alembic import op

revision = "0016_announcements"
down_revision = "0015_classroom_requests"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE classsync_academic.announcements (
        tenant_id text NOT NULL REFERENCES classsync_identity.tenants(id),
        id uuid NOT NULL, title text NOT NULL CHECK(length(btrim(title)) BETWEEN 1 AND 120),
        body text NOT NULL CHECK(length(btrim(body)) BETWEEN 1 AND 3000),
        audience text[] NOT NULL CHECK(cardinality(audience) BETWEEN 1 AND 3
            AND audience<@ARRAY['student','teacher','administrator']::text[]),
        created_by text NOT NULL, updated_by text NOT NULL,
        revision integer NOT NULL DEFAULT 1 CHECK(revision>=1),
        archived boolean NOT NULL DEFAULT false,
        created_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
        updated_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
        PRIMARY KEY(tenant_id,id),
        FOREIGN KEY(tenant_id,created_by) REFERENCES classsync_identity.memberships(tenant_id,uid),
        FOREIGN KEY(tenant_id,updated_by) REFERENCES classsync_identity.memberships(tenant_id,uid)
    )""")
    op.execute("ALTER TABLE classsync_academic.announcements ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE classsync_academic.announcements FORCE ROW LEVEL SECURITY")
    member = """tenant_id=current_setting('classsync.tenant_id',true) AND EXISTS (
        SELECT 1 FROM classsync_identity.memberships m
        JOIN classsync_identity.tenants t ON t.id=m.tenant_id
        WHERE m.tenant_id=current_setting('classsync.tenant_id',true)
        AND m.uid=current_setting('classsync.uid',true) AND m.state='active'
        AND current_setting('classsync.role',true)=ANY(m.roles)
        AND t.firebase_project_id=current_setting('classsync.project_id',true))"""
    admin = "current_setting('classsync.role',true)='administrator'"
    actor = "updated_by=current_setting('classsync.uid',true)"
    op.execute(f"""CREATE POLICY announcement_reads ON classsync_academic.announcements
        FOR SELECT USING (({member}) AND (({admin}) OR
            (NOT archived AND current_setting('classsync.role',true)=ANY(audience))))""")
    op.execute(f"""CREATE POLICY announcement_create ON classsync_academic.announcements
        FOR INSERT WITH CHECK (({member}) AND ({admin}) AND ({actor})
            AND created_by=current_setting('classsync.uid',true)
            AND NOT archived AND revision=1)""")
    op.execute(f"""CREATE POLICY announcement_update ON classsync_academic.announcements
        FOR UPDATE USING (({member}) AND ({admin}))
        WITH CHECK (({member}) AND ({admin}) AND ({actor}))""")
    op.execute("REVOKE ALL ON classsync_academic.announcements FROM PUBLIC")
    op.execute("""CREATE FUNCTION classsync_academic.guard_announcement()
        RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
        BEGIN
            IF OLD.archived OR NEW.revision<>OLD.revision+1 OR
                (NEW.tenant_id,NEW.id,NEW.created_at,NEW.created_by) IS DISTINCT FROM
                (OLD.tenant_id,OLD.id,OLD.created_at,OLD.created_by) THEN
                RAISE EXCEPTION 'Announcement identity or revision is immutable'
                    USING ERRCODE='23514';
            END IF;
            NEW.updated_at=transaction_timestamp();
            RETURN NEW;
        END; $$""")
    op.execute("REVOKE ALL ON FUNCTION classsync_academic.guard_announcement() FROM PUBLIC")
    op.execute("""CREATE TRIGGER announcement_transition BEFORE UPDATE
        ON classsync_academic.announcements FOR EACH ROW
        EXECUTE FUNCTION classsync_academic.guard_announcement()""")


def downgrade():
    op.execute("DROP TABLE classsync_academic.announcements")
    op.execute("DROP FUNCTION classsync_academic.guard_announcement()")

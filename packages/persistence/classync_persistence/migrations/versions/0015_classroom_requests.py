"""Current-assignment classroom requests; decisions never directly change timetables."""

from alembic import op

revision = "0015_classroom_requests"
down_revision = "0014_account_onboarding"
branch_labels = None
depends_on = None


def permitted(role):
    return f"""tenant_id=current_setting('classsync.tenant_id',true)
        AND current_setting('classsync.role',true)='{role}' AND EXISTS (
        SELECT 1 FROM classsync_identity.memberships m
        JOIN classsync_identity.tenants t ON t.id=m.tenant_id
        WHERE m.tenant_id=current_setting('classsync.tenant_id',true)
        AND m.uid=current_setting('classsync.uid',true) AND m.state='active'
        AND '{role}'=ANY(m.roles)
        AND t.firebase_project_id=current_setting('classsync.project_id',true))"""


def upgrade():
    op.execute("""CREATE TABLE classsync_scheduling.classroom_requests (
        tenant_id text NOT NULL,
        id uuid NOT NULL,
        owner_uid text NOT NULL,
        faculty_id text NOT NULL,
        period_id text NOT NULL,
        dataset text NOT NULL DEFAULT 'institutional' CHECK(dataset='institutional'),
        publication_id text NOT NULL,
        occurrence_id text NOT NULL CHECK(length(occurrence_id) BETWEEN 1 AND 200),
        proposed_room_id text NOT NULL CHECK(length(proposed_room_id) BETWEEN 1 AND 128),
        reason text NOT NULL CHECK(length(btrim(reason)) BETWEEN 3 AND 1000),
        context jsonb NOT NULL CHECK(jsonb_typeof(context)='object'),
        status text NOT NULL DEFAULT 'pending'
            CHECK(status IN ('pending','approved','rejected','fulfilled')),
        revision integer NOT NULL DEFAULT 1 CHECK(revision>=1),
        decision_note text,
        decided_by text,
        fulfilled_by text,
        fulfilled_version text,
        idempotency_key uuid NOT NULL,
        input_hash text NOT NULL CHECK(length(input_hash)=64),
        created_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
        updated_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
        PRIMARY KEY(tenant_id,id), UNIQUE(tenant_id,owner_uid,idempotency_key),
        FOREIGN KEY(tenant_id,owner_uid) REFERENCES classsync_identity.memberships(tenant_id,uid),
        FOREIGN KEY(tenant_id,faculty_id) REFERENCES classsync_identity.faculty(tenant_id,id),
        FOREIGN KEY(tenant_id,dataset,publication_id)
            REFERENCES classsync_scheduling.published_versions(tenant_id,dataset,id),
        FOREIGN KEY(tenant_id,dataset,fulfilled_version)
            REFERENCES classsync_scheduling.published_versions(tenant_id,dataset,id),
        CHECK((status='pending')=(decided_by IS NULL)),
        CHECK(status='pending' OR (decision_note IS NOT NULL
            AND length(btrim(decision_note)) BETWEEN 3 AND 1000)),
        CHECK((status='fulfilled')=(fulfilled_version IS NOT NULL)),
        CHECK((status='fulfilled')=(fulfilled_by IS NOT NULL))
    )""")
    op.execute("ALTER TABLE classsync_scheduling.classroom_requests ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE classsync_scheduling.classroom_requests FORCE ROW LEVEL SECURITY")
    admin, teacher = permitted("administrator"), permitted("teacher")
    own = """owner_uid=current_setting('classsync.uid',true) AND faculty_id=(
        SELECT m.faculty_id FROM classsync_identity.memberships m
        WHERE m.tenant_id=current_setting('classsync.tenant_id',true)
        AND m.uid=current_setting('classsync.uid',true))"""
    op.execute(f"""CREATE POLICY request_reads ON classsync_scheduling.classroom_requests
        FOR SELECT USING (({admin}) OR (({teacher}) AND {own}))""")
    op.execute(f"""CREATE POLICY request_create ON classsync_scheduling.classroom_requests
        FOR INSERT WITH CHECK (({teacher}) AND {own} AND status='pending'
            AND revision=1 AND decided_by IS NULL)""")
    op.execute(f"""CREATE POLICY request_decide ON classsync_scheduling.classroom_requests
        FOR UPDATE USING ({admin}) WITH CHECK (({admin})
            AND ((status='fulfilled' AND fulfilled_by=current_setting('classsync.uid',true))
                OR (status<>'fulfilled' AND decided_by=current_setting('classsync.uid',true))))""")
    op.execute("REVOKE ALL ON classsync_scheduling.classroom_requests FROM PUBLIC")
    op.execute("""CREATE FUNCTION classsync_scheduling.guard_classroom_request()
        RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
        BEGIN
            IF (NEW.tenant_id,NEW.id,NEW.owner_uid,NEW.faculty_id,NEW.period_id,
                NEW.dataset,NEW.publication_id,NEW.occurrence_id,NEW.proposed_room_id,
                NEW.reason,NEW.context,NEW.idempotency_key,NEW.input_hash,NEW.created_at)
                IS DISTINCT FROM
                (OLD.tenant_id,OLD.id,OLD.owner_uid,OLD.faculty_id,OLD.period_id,
                OLD.dataset,OLD.publication_id,OLD.occurrence_id,OLD.proposed_room_id,
                OLD.reason,OLD.context,OLD.idempotency_key,OLD.input_hash,OLD.created_at)
                OR NEW.revision<>OLD.revision+1 THEN
                RAISE EXCEPTION 'Request identity and submitted evidence are immutable'
                    USING ERRCODE='23514';
            END IF;
            IF NOT ((OLD.status='pending' AND NEW.status IN ('approved','rejected'))
                OR (OLD.status='approved' AND NEW.status='fulfilled'
                    AND NEW.decided_by=OLD.decided_by
                    AND NEW.decision_note=OLD.decision_note)) THEN
                RAISE EXCEPTION 'Invalid classroom request transition' USING ERRCODE='23514';
            END IF;
            NEW.updated_at=transaction_timestamp();
            RETURN NEW;
        END;
        $$""")
    op.execute("REVOKE ALL ON FUNCTION classsync_scheduling.guard_classroom_request() FROM PUBLIC")
    op.execute("""CREATE TRIGGER classroom_request_transition BEFORE UPDATE
        ON classsync_scheduling.classroom_requests FOR EACH ROW
        EXECUTE FUNCTION classsync_scheduling.guard_classroom_request()""")


def downgrade():
    op.execute("DROP TABLE classsync_scheduling.classroom_requests")
    op.execute("DROP FUNCTION classsync_scheduling.guard_classroom_request()")

"""Append-only, tenant-scoped administrative activity without record payloads."""

from alembic import op

revision = "0017_administrator_activity_audit"
down_revision = "0016_announcements"
branch_labels = None
depends_on = None

ADMIN = """(
    tenant_id=current_setting('classsync.tenant_id',true)
    AND EXISTS (
        SELECT 1 FROM classsync_identity.memberships m
        JOIN classsync_identity.tenants t ON t.id=m.tenant_id
        WHERE m.tenant_id=current_setting('classsync.tenant_id',true)
          AND m.uid=current_setting('classsync.uid',true)
          AND m.state='active' AND 'administrator'=ANY(m.roles)
          AND t.firebase_project_id=current_setting('classsync.project_id',true)
    )
)"""


def upgrade():
    op.execute("""
        CREATE TABLE classsync_scheduling.administrator_activity (
            tenant_id text NOT NULL,
            owner_uid text NOT NULL,
            event_id uuid NOT NULL,
            period_id text NOT NULL,
            event_type text NOT NULL CHECK (event_type IN (
                'academic.period.created', 'academic.record.created',
                'academic.record.updated', 'academic.calendar.saved',
                'scheduling.draft.saved', 'scheduling.publication.published'
            )),
            entity_type text NOT NULL CHECK (entity_type IN (
                'period','programs','subjects','sections','faculty','resources',
                'offerings','constraints','calendar','draft','publication'
            )),
            entity_ref text NOT NULL CHECK (entity_ref ~ '^[a-f0-9]{64}$'),
            revision bigint CHECK (revision IS NULL OR revision >= 1),
            created_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
            PRIMARY KEY (tenant_id,owner_uid,event_id),
            FOREIGN KEY (tenant_id,owner_uid,period_id)
                REFERENCES classsync_academic.period_metadata(tenant_id,owner_uid,id)
        )
    """)
    op.execute("""
        CREATE INDEX administrator_activity_period_time
        ON classsync_scheduling.administrator_activity
            (tenant_id,owner_uid,period_id,created_at DESC,event_id DESC)
    """)
    op.execute("ALTER TABLE classsync_scheduling.administrator_activity ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE classsync_scheduling.administrator_activity FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY administrator_activity_admin ON "
        "classsync_scheduling.administrator_activity "
        f"USING ({ADMIN}) WITH CHECK ({ADMIN} AND owner_uid=current_setting('classsync.uid',true))"
    )
    op.execute("REVOKE ALL ON classsync_scheduling.administrator_activity FROM PUBLIC")
    op.execute("""
        CREATE FUNCTION classsync_scheduling.audit_administrator_activity()
        RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
        DECLARE
            v_tenant text;
            v_owner text;
            v_period text;
            v_event text;
            v_kind text;
            v_ref text;
            v_revision bigint;
        BEGIN
            IF TG_TABLE_NAME='period_metadata' THEN
                v_tenant := NEW.tenant_id; v_owner := NEW.owner_uid; v_period := NEW.id;
                v_event := 'academic.period.created'; v_kind := 'period';
                v_ref := NEW.id; v_revision := NEW.revision;
            ELSIF TG_TABLE_NAME='records' THEN
                v_tenant := NEW.tenant_id; v_owner := NEW.owner_uid; v_period := NEW.period_id;
                v_event := CASE WHEN TG_OP='INSERT' THEN 'academic.record.created'
                    ELSE 'academic.record.updated' END;
                v_kind := NEW.kind; v_ref := NEW.kind || ':' || NEW.id;
                v_revision := NEW.revision;
            ELSIF TG_TABLE_NAME='calendars' THEN
                v_tenant := NEW.tenant_id; v_owner := NEW.owner_uid; v_period := NEW.period_id;
                v_event := 'academic.calendar.saved'; v_kind := 'calendar';
                v_ref := NEW.period_id; v_revision := NULL;
            ELSIF TG_TABLE_NAME='drafts' THEN
                v_tenant := NEW.tenant_id; v_owner := NEW.owner_uid;
                v_period := NEW.payload::jsonb->>'period_id';
                v_event := 'scheduling.draft.saved'; v_kind := 'draft'; v_ref := NEW.id;
                v_revision := NULL;
            ELSE
                v_tenant := NEW.tenant_id; v_owner := NEW.owner_uid; v_period := NEW.period_id;
                v_event := 'scheduling.publication.published'; v_kind := 'publication';
                v_ref := NEW.id; v_revision := NEW.revision;
            END IF;
            IF v_tenant IS DISTINCT FROM current_setting('classsync.tenant_id',true)
                OR v_owner IS DISTINCT FROM current_setting('classsync.uid',true)
                OR v_period IS NULL THEN
                RAISE EXCEPTION 'Administrative audit context required' USING ERRCODE='42501';
            END IF;
            INSERT INTO classsync_scheduling.administrator_activity
                (tenant_id,owner_uid,event_id,period_id,event_type,entity_type,entity_ref,revision)
            VALUES (v_tenant,v_owner,gen_random_uuid(),v_period,v_event,v_kind,
                encode(sha256(convert_to(v_ref,'UTF8')),'hex'),v_revision);
            RETURN NEW;
        END; $$
    """)
    op.execute(
        "REVOKE ALL ON FUNCTION classsync_scheduling.audit_administrator_activity() FROM PUBLIC"
    )
    for table in ("period_metadata", "records", "calendars"):
        operation = "INSERT" if table == "period_metadata" else "INSERT OR UPDATE"
        op.execute(
            f"CREATE TRIGGER administrator_activity_{table} AFTER {operation} "
            f"ON classsync_academic.{table} FOR EACH ROW "
            "EXECUTE FUNCTION classsync_scheduling.audit_administrator_activity()"
        )
    for table in ("drafts", "published_versions"):
        op.execute(
            f"CREATE TRIGGER administrator_activity_{table} AFTER INSERT "
            f"ON classsync_scheduling.{table} FOR EACH ROW "
            "EXECUTE FUNCTION classsync_scheduling.audit_administrator_activity()"
        )
    op.execute("""
        CREATE FUNCTION classsync_scheduling.deny_administrator_activity_mutation()
        RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
        BEGIN
            RAISE EXCEPTION 'Administrator activity is append-only' USING ERRCODE='42501';
        END; $$
    """)
    op.execute(
        "REVOKE ALL ON FUNCTION "
        "classsync_scheduling.deny_administrator_activity_mutation() FROM PUBLIC"
    )
    op.execute("""
        CREATE TRIGGER administrator_activity_immutable
        BEFORE UPDATE OR DELETE ON classsync_scheduling.administrator_activity
        FOR EACH ROW EXECUTE FUNCTION classsync_scheduling.deny_administrator_activity_mutation()
    """)
    op.execute("""
        CREATE TRIGGER administrator_activity_no_truncate
        BEFORE TRUNCATE ON classsync_scheduling.administrator_activity
        FOR EACH STATEMENT EXECUTE FUNCTION
            classsync_scheduling.deny_administrator_activity_mutation()
    """)


def downgrade():
    for table in ("published_versions", "drafts"):
        op.execute(f"DROP TRIGGER administrator_activity_{table} ON classsync_scheduling.{table}")
    for table in ("period_metadata", "records", "calendars"):
        op.execute(f"DROP TRIGGER administrator_activity_{table} ON classsync_academic.{table}")
    op.execute(
        "DROP TRIGGER administrator_activity_no_truncate "
        "ON classsync_scheduling.administrator_activity"
    )
    op.execute(
        "DROP TRIGGER administrator_activity_immutable "
        "ON classsync_scheduling.administrator_activity"
    )
    op.execute("DROP FUNCTION classsync_scheduling.audit_administrator_activity()")
    op.execute("DROP FUNCTION classsync_scheduling.deny_administrator_activity_mutation()")
    op.execute("DROP TABLE classsync_scheduling.administrator_activity")

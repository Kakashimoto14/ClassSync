"""Audit administrator deletion of period-scoped academic records."""

from alembic import op

revision = "0024_academic_record_deletion_audit"
down_revision = "0023_person_display_name"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE classsync_scheduling.administrator_activity "
        "DROP CONSTRAINT administrator_activity_event_type_check"
    )
    op.execute("""
        ALTER TABLE classsync_scheduling.administrator_activity
        ADD CONSTRAINT administrator_activity_event_type_check CHECK (event_type IN (
            'academic.period.created','academic.record.created','academic.record.updated',
            'academic.record.deleted','academic.calendar.saved','scheduling.draft.saved',
            'scheduling.publication.published'
        ))
    """)
    op.execute("DROP TRIGGER administrator_activity_records ON classsync_academic.records")
    op.execute("""
        CREATE OR REPLACE FUNCTION classsync_scheduling.audit_administrator_activity()
        RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
        DECLARE
            v_tenant text; v_owner text; v_period text; v_event text;
            v_kind text; v_ref text; v_revision bigint;
        BEGIN
            IF TG_TABLE_NAME='period_metadata' THEN
                v_tenant:=NEW.tenant_id; v_owner:=NEW.owner_uid; v_period:=NEW.id;
                v_event:='academic.period.created'; v_kind:='period'; v_ref:=NEW.id;
                v_revision:=NEW.revision;
            ELSIF TG_TABLE_NAME='records' THEN
                IF TG_OP='DELETE' THEN
                    v_tenant:=OLD.tenant_id; v_owner:=OLD.owner_uid; v_period:=OLD.period_id;
                    v_event:='academic.record.deleted'; v_kind:=OLD.kind;
                    v_ref:=OLD.kind || ':' || OLD.id; v_revision:=OLD.revision;
                ELSE
                    v_tenant:=NEW.tenant_id; v_owner:=NEW.owner_uid; v_period:=NEW.period_id;
                    v_event:=CASE WHEN TG_OP='INSERT' THEN 'academic.record.created'
                        ELSE 'academic.record.updated' END;
                    v_kind:=NEW.kind; v_ref:=NEW.kind || ':' || NEW.id;
                    v_revision:=NEW.revision;
                END IF;
            ELSIF TG_TABLE_NAME='calendars' THEN
                v_tenant:=NEW.tenant_id; v_owner:=NEW.owner_uid; v_period:=NEW.period_id;
                v_event:='academic.calendar.saved'; v_kind:='calendar';
                v_ref:=NEW.period_id; v_revision:=NULL;
            ELSIF TG_TABLE_NAME='drafts' THEN
                v_tenant:=NEW.tenant_id; v_owner:=NEW.owner_uid;
                v_period:=NEW.payload::jsonb->>'period_id';
                v_event:='scheduling.draft.saved'; v_kind:='draft'; v_ref:=NEW.id;
                v_revision:=NULL;
            ELSE
                v_tenant:=NEW.tenant_id; v_owner:=NEW.owner_uid; v_period:=NEW.period_id;
                v_event:='scheduling.publication.published'; v_kind:='publication';
                v_ref:=NEW.id; v_revision:=NEW.revision;
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
            IF TG_OP='DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END; $$
    """)
    op.execute(
        "CREATE TRIGGER administrator_activity_records "
        "AFTER INSERT OR UPDATE OR DELETE ON classsync_academic.records "
        "FOR EACH ROW EXECUTE FUNCTION "
        "classsync_scheduling.audit_administrator_activity()"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION classsync_scheduling.audit_administrator_activity() FROM PUBLIC"
    )


def downgrade():
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM classsync_scheduling.administrator_activity
                       WHERE event_type='academic.record.deleted') THEN
                RAISE EXCEPTION 'Record deletion audit events must be retained';
            END IF;
        END $$
    """)
    op.execute("DROP TRIGGER administrator_activity_records ON classsync_academic.records")
    op.execute("""
        CREATE OR REPLACE FUNCTION classsync_scheduling.audit_administrator_activity()
        RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
        DECLARE
            v_tenant text; v_owner text; v_period text; v_event text;
            v_kind text; v_ref text; v_revision bigint;
        BEGIN
            IF TG_TABLE_NAME='period_metadata' THEN
                v_tenant:=NEW.tenant_id; v_owner:=NEW.owner_uid; v_period:=NEW.id;
                v_event:='academic.period.created'; v_kind:='period'; v_ref:=NEW.id;
                v_revision:=NEW.revision;
            ELSIF TG_TABLE_NAME='records' THEN
                v_tenant:=NEW.tenant_id; v_owner:=NEW.owner_uid; v_period:=NEW.period_id;
                v_event:=CASE WHEN TG_OP='INSERT' THEN 'academic.record.created'
                    ELSE 'academic.record.updated' END;
                v_kind:=NEW.kind; v_ref:=NEW.kind || ':' || NEW.id;
                v_revision:=NEW.revision;
            ELSIF TG_TABLE_NAME='calendars' THEN
                v_tenant:=NEW.tenant_id; v_owner:=NEW.owner_uid; v_period:=NEW.period_id;
                v_event:='academic.calendar.saved'; v_kind:='calendar';
                v_ref:=NEW.period_id; v_revision:=NULL;
            ELSIF TG_TABLE_NAME='drafts' THEN
                v_tenant:=NEW.tenant_id; v_owner:=NEW.owner_uid;
                v_period:=NEW.payload::jsonb->>'period_id';
                v_event:='scheduling.draft.saved'; v_kind:='draft'; v_ref:=NEW.id;
                v_revision:=NULL;
            ELSE
                v_tenant:=NEW.tenant_id; v_owner:=NEW.owner_uid; v_period:=NEW.period_id;
                v_event:='scheduling.publication.published'; v_kind:='publication';
                v_ref:=NEW.id; v_revision:=NEW.revision;
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
        "CREATE TRIGGER administrator_activity_records AFTER INSERT OR UPDATE "
        "ON classsync_academic.records FOR EACH ROW EXECUTE FUNCTION "
        "classsync_scheduling.audit_administrator_activity()"
    )
    op.execute(
        "ALTER TABLE classsync_scheduling.administrator_activity "
        "DROP CONSTRAINT administrator_activity_event_type_check"
    )
    op.execute(
        """
        ALTER TABLE classsync_scheduling.administrator_activity
        ADD CONSTRAINT administrator_activity_event_type_check CHECK (event_type IN (
            'academic.period.created','academic.record.created','academic.record.updated',
            'academic.calendar.saved','scheduling.draft.saved','scheduling.publication.published'
        ))
        """
    )

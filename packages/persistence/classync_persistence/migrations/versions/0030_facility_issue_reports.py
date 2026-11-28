"""Teacher facility issue reports, Administrator triage and append-only history.

* Teachers insert and read only their own reports. Active Administrators read every report in
  the tenant. Reports start open at revision one.
* Status changes happen only through the SECURITY DEFINER `transition_facility_issue`, which
  re-checks the active Administrator, the expected revision and the allowed transition.
* A trigger writes one event per insert or change. Events cannot be updated or deleted.
* `classsync_app`, when present, gets SELECT and INSERT on reports, SELECT on events and
  EXECUTE on the transition function. It never gets UPDATE or DELETE.
* The administrator activity constraints are not touched.
"""

from importlib import import_module

from alembic import op

revision = "0030_facility_issue_reports"
down_revision = "0029_restrictions_and_period_lifecycle"
branch_labels = None
depends_on = None

REPORTS = "classsync_scheduling.facility_issue_reports"
EVENTS = "classsync_scheduling.facility_issue_events"
TRANSITION = (
    "classsync_scheduling.transition_facility_issue(uuid,integer,text,text,text)"
)


def _owner(table):
    return f"""current_user=pg_catalog.pg_get_userbyid((
        SELECT relowner FROM pg_catalog.pg_class WHERE oid='{table}'::regclass))"""


def upgrade():
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles
                       WHERE rolname=current_user AND (rolsuper OR rolbypassrls)) THEN
                RAISE EXCEPTION 'A non-superuser non-BYPASSRLS migration owner is required'
                    USING ERRCODE='42501';
            END IF;
        END $$
    """)
    admin_member = import_module(
        "classync_persistence.migrations.versions.0008_publication_transactions"
    ).ADMIN
    permitted = import_module(
        "classync_persistence.migrations.versions.0015_classroom_requests"
    ).permitted
    admin, teacher = permitted("administrator"), permitted("teacher")

    op.execute(f"""CREATE TABLE {REPORTS} (
        tenant_id text NOT NULL,
        id uuid NOT NULL,
        reporter_uid text NOT NULL,
        room_id text NOT NULL CHECK(length(btrim(room_id)) BETWEEN 1 AND 80),
        occurrence_id text CHECK(length(occurrence_id) BETWEEN 1 AND 200),
        occurrence_date date,
        category text NOT NULL CHECK(category IN
            ('equipment','electrical','furniture','cleanliness','safety','other')),
        description text NOT NULL CHECK(length(description)<=2000
            AND length(btrim(description))>=3),
        status text NOT NULL DEFAULT 'open'
            CHECK(status IN ('open','in_progress','resolved','dismissed')),
        revision integer NOT NULL DEFAULT 1 CHECK(revision>=1),
        resolution_note text CHECK(length(resolution_note) BETWEEN 3 AND 1000),
        linked_restriction_id text CHECK(length(linked_restriction_id) BETWEEN 1 AND 80),
        created_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
        updated_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
        PRIMARY KEY(tenant_id,id),
        FOREIGN KEY(tenant_id,reporter_uid)
            REFERENCES classsync_identity.memberships(tenant_id,uid),
        CHECK((occurrence_id IS NULL)=(occurrence_date IS NULL)),
        CHECK(status NOT IN ('resolved','dismissed') OR resolution_note IS NOT NULL)
    )""")
    op.execute(f"""CREATE TABLE {EVENTS} (
        tenant_id text NOT NULL,
        issue_id uuid NOT NULL,
        revision integer NOT NULL CHECK(revision>=1),
        from_status text,
        to_status text NOT NULL,
        actor_uid text NOT NULL,
        note text,
        linked_restriction_id text,
        created_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
        PRIMARY KEY(tenant_id,issue_id,revision),
        FOREIGN KEY(tenant_id,issue_id) REFERENCES {REPORTS}(tenant_id,id)
    )""")
    for table in (REPORTS, EVENTS):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON {table} FROM PUBLIC")

    # The definer functions run as the owner, which FORCE RLS also binds.
    definer = f"(({_owner(REPORTS)}) AND {admin_member})"
    own = "reporter_uid=current_setting('classsync.uid',true)"
    op.execute(f"""CREATE POLICY issue_reads ON {REPORTS} FOR SELECT
        USING (({admin}) OR (({teacher}) AND {own}) OR {definer})""")
    op.execute(f"""CREATE POLICY issue_create ON {REPORTS} FOR INSERT
        WITH CHECK (({teacher}) AND {own} AND status='open' AND revision=1
            AND resolution_note IS NULL AND linked_restriction_id IS NULL)""")
    op.execute(f"""CREATE POLICY issue_triage ON {REPORTS} FOR UPDATE
        USING {definer} WITH CHECK {definer}""")
    tenant = "tenant_id=current_setting('classsync.tenant_id',true)"
    # The report subquery is itself filtered by row security, so Teachers see their own history.
    op.execute(f"""CREATE POLICY issue_event_reads ON {EVENTS} FOR SELECT
        USING ({tenant} AND (({admin}) OR (({teacher}) AND EXISTS (
            SELECT 1 FROM {REPORTS} r WHERE r.tenant_id=facility_issue_events.tenant_id
                AND r.id=facility_issue_events.issue_id))))""")
    op.execute(f"""CREATE POLICY issue_event_append ON {EVENTS} FOR INSERT
        WITH CHECK (({_owner(EVENTS)}) AND {tenant}
            AND actor_uid=current_setting('classsync.uid',true))""")

    op.execute("""CREATE FUNCTION classsync_scheduling.guard_facility_issue()
        RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
        BEGIN
            IF TG_OP='INSERT' THEN
                IF NEW.status<>'open' OR NEW.revision<>1 OR NEW.resolution_note IS NOT NULL
                    OR NEW.linked_restriction_id IS NOT NULL THEN
                    RAISE EXCEPTION 'A report must begin open at revision one'
                        USING ERRCODE='23514';
                END IF;
                NEW.created_at := transaction_timestamp();
            ELSE
                IF (NEW.tenant_id,NEW.id,NEW.reporter_uid,NEW.room_id,NEW.occurrence_id,
                    NEW.occurrence_date,NEW.category,NEW.description,NEW.created_at)
                    IS DISTINCT FROM
                    (OLD.tenant_id,OLD.id,OLD.reporter_uid,OLD.room_id,OLD.occurrence_id,
                    OLD.occurrence_date,OLD.category,OLD.description,OLD.created_at)
                    OR NEW.revision<>OLD.revision+1 THEN
                    RAISE EXCEPTION 'Submitted report evidence is immutable'
                        USING ERRCODE='23514';
                END IF;
                IF NOT ((OLD.status='open'
                        AND NEW.status IN ('in_progress','resolved','dismissed'))
                    OR (OLD.status='in_progress'
                        AND NEW.status IN ('resolved','dismissed'))) THEN
                    RAISE EXCEPTION 'Invalid facility issue transition' USING ERRCODE='23514';
                END IF;
            END IF;
            NEW.updated_at := transaction_timestamp();
            RETURN NEW;
        END; $$""")
    op.execute(f"""CREATE TRIGGER facility_issue_guard BEFORE INSERT OR UPDATE
        ON {REPORTS} FOR EACH ROW
        EXECUTE FUNCTION classsync_scheduling.guard_facility_issue()""")
    op.execute(f"""CREATE FUNCTION classsync_scheduling.record_facility_issue_event()
        RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
        BEGIN
            INSERT INTO {EVENTS}
                (tenant_id,issue_id,revision,from_status,to_status,actor_uid,note,
                 linked_restriction_id)
            VALUES (NEW.tenant_id,NEW.id,NEW.revision,
                CASE WHEN TG_OP='UPDATE' THEN OLD.status END,NEW.status,
                current_setting('classsync.uid',true),NEW.resolution_note,
                NEW.linked_restriction_id);
            RETURN NEW;
        END; $$""")
    op.execute(f"""CREATE TRIGGER facility_issue_history AFTER INSERT OR UPDATE
        ON {REPORTS} FOR EACH ROW
        EXECUTE FUNCTION classsync_scheduling.record_facility_issue_event()""")
    op.execute("""CREATE FUNCTION classsync_scheduling.deny_facility_issue_event_change()
        RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
        BEGIN
            RAISE EXCEPTION 'Facility issue history is append-only' USING ERRCODE='23514';
        END; $$""")
    op.execute(f"""CREATE TRIGGER facility_issue_events_append_only BEFORE UPDATE OR DELETE
        ON {EVENTS} FOR EACH ROW
        EXECUTE FUNCTION classsync_scheduling.deny_facility_issue_event_change()""")
    op.execute(f"""CREATE TRIGGER facility_issue_events_no_truncate BEFORE TRUNCATE
        ON {EVENTS} FOR EACH STATEMENT
        EXECUTE FUNCTION classsync_scheduling.deny_facility_issue_event_change()""")

    # SQLSTATEs: CS400 invalid input, CS404 missing, CS409 stale, CS422 illegal transition.
    op.execute(f"""CREATE FUNCTION classsync_scheduling.transition_facility_issue(
            p_issue_id uuid, p_expected_revision integer, p_status text, p_note text,
            p_restriction_id text
        ) RETURNS {REPORTS}
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
        DECLARE
            v_tenant text := current_setting('classsync.tenant_id',true);
            v_uid text := current_setting('classsync.uid',true);
            v_project text := current_setting('classsync.project_id',true);
            v_note text := nullif(btrim(COALESCE(p_note,'')),'');
            v_row {REPORTS}%ROWTYPE;
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM classsync_identity.memberships m
                JOIN classsync_identity.tenants t ON t.id=m.tenant_id
                WHERE m.tenant_id=v_tenant AND m.uid=v_uid AND m.state='active'
                  AND 'administrator'=ANY(m.roles) AND t.firebase_project_id=v_project
            ) THEN
                RAISE EXCEPTION 'Active Administrator required' USING ERRCODE='42501';
            END IF;
            SELECT * INTO v_row FROM {REPORTS} r
            WHERE r.tenant_id=v_tenant AND r.id=p_issue_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'Facility issue not found' USING ERRCODE='CS404';
            END IF;
            IF v_row.revision IS DISTINCT FROM p_expected_revision THEN
                RAISE EXCEPTION 'Facility issue changed' USING ERRCODE='CS409';
            END IF;
            IF NOT COALESCE(
                (v_row.status='open' AND p_status IN ('in_progress','resolved','dismissed'))
                OR (v_row.status='in_progress' AND p_status IN ('resolved','dismissed')),
                false) THEN
                RAISE EXCEPTION 'Invalid facility issue transition' USING ERRCODE='CS422';
            END IF;
            IF (p_status IN ('resolved','dismissed') AND v_note IS NULL
                    AND v_row.resolution_note IS NULL)
                OR length(v_note) NOT BETWEEN 3 AND 1000 THEN
                RAISE EXCEPTION 'A resolution note of 3 to 1000 characters is required'
                    USING ERRCODE='CS400';
            END IF;
            IF p_restriction_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM classsync_scheduling.room_restrictions x
                WHERE x.tenant_id=v_tenant AND x.dataset='institutional'
                  AND x.id=p_restriction_id AND x.room_id=v_row.room_id
                  AND COALESCE(x.payload::jsonb->>'status','active')<>'cancelled'
            ) THEN
                RAISE EXCEPTION 'Link an active restriction of the reported room'
                    USING ERRCODE='CS400';
            END IF;
            UPDATE {REPORTS} r SET status=p_status, revision=r.revision+1,
                resolution_note=COALESCE(v_note,r.resolution_note),
                linked_restriction_id=COALESCE(p_restriction_id,r.linked_restriction_id)
            WHERE r.tenant_id=v_tenant AND r.id=p_issue_id AND r.revision=p_expected_revision
            RETURNING r.* INTO v_row;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'Facility issue changed' USING ERRCODE='CS409';
            END IF;
            RETURN v_row;
        END; $$""")

    for function in (
        "classsync_scheduling.guard_facility_issue()",
        "classsync_scheduling.record_facility_issue_event()",
        "classsync_scheduling.deny_facility_issue_event_change()",
        TRANSITION,
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
    # As in 0025/0029: the function re-checks the active Administrator context itself.
    op.execute(f"GRANT EXECUTE ON FUNCTION {TRANSITION} TO PUBLIC")
    # Revoke first so that default privileges can never leave the runtime role over-granted.
    op.execute(f"""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='classsync_app') THEN
                REVOKE ALL ON {REPORTS}, {EVENTS} FROM classsync_app;
                GRANT SELECT, INSERT ON {REPORTS} TO classsync_app;
                GRANT SELECT ON {EVENTS} TO classsync_app;
                GRANT EXECUTE ON FUNCTION {TRANSITION} TO classsync_app;
            END IF;
        END $$
    """)


def downgrade():
    # FORCE RLS would hide rows from the owner and make this refusal vacuous. The whole
    # downgrade is one transaction, so a refusal restores it.
    op.execute(f"ALTER TABLE {REPORTS} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM {REPORTS}) THEN
                RAISE EXCEPTION 'Facility issue history must be retained';
            END IF;
        END $$
    """)
    op.execute(f"DROP FUNCTION {TRANSITION}")
    op.execute(f"DROP TABLE {EVENTS}")
    op.execute(f"DROP TABLE {REPORTS}")
    for function in (
        "guard_facility_issue",
        "record_facility_issue_event",
        "deny_facility_issue_event_change",
    ):
        op.execute(f"DROP FUNCTION classsync_scheduling.{function}()")

"""Shared room restrictions, cancellable restriction windows and one-way period archive.

* Any active Administrator of the tenant may revise or cancel a room restriction. `owner_uid`
  becomes the acting (last editing) Administrator, so the 0008 audit trigger keeps attributing
  every revision to the verified actor; revision 1 in `restriction_audit` keeps the creator.
* Cancelled restrictions no longer appear in the tenant-wide windows projection (0028).
* A period can be archived once. Record, calendar, draft and publication writes are then
  rejected; reading and cloning stay available.
* The activity constraints are rebuilt as supersets of every earlier value.
"""

from importlib import import_module

from alembic import op

revision = "0029_restrictions_and_period_lifecycle"
down_revision = "0028_room_occupancy_projection"
branch_labels = None
depends_on = None

PREVIOUS_EVENTS = (
    "academic.period.created",
    "academic.period.archived",
    "academic.record.created",
    "academic.record.updated",
    "academic.record.deleted",
    "academic.calendar.saved",
    "scheduling.draft.saved",
    "scheduling.publication.published",
    "academic.student.created",
    "academic.student.updated",
    "academic.student.deleted",
)
NEW_EVENTS = ("academic.period.cloned", "scheduling.restriction.saved", "academic.roster.imported")
PREVIOUS_ENTITIES = (
    "period",
    "programs",
    "subjects",
    "sections",
    "faculty",
    "resources",
    "offerings",
    "constraints",
    "calendar",
    "draft",
    "publication",
    "student_roster",
)


def _values(items):
    return ",".join(f"'{item}'" for item in items)


def _checks(events, entities):
    for name, column, values in (
        ("administrator_activity_event_type_check", "event_type", events),
        ("administrator_activity_entity_type_check", "entity_type", entities),
    ):
        table = "classsync_scheduling.administrator_activity"
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {name}")
        op.execute(
            f"ALTER TABLE {table} "
            f"ADD CONSTRAINT {name} CHECK ({column} IN ({_values(values)}))"
        )


def _restriction_guard(single_owner):
    owner_columns = ",NEW.owner_uid" if single_owner else ""
    old_columns = ",OLD.owner_uid" if single_owner else ""
    return f"""
        CREATE OR REPLACE FUNCTION classsync_scheduling.guard_room_restriction()
        RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
        BEGIN
            IF NEW.owner_uid IS DISTINCT FROM current_setting('classsync.uid',true) THEN
                RAISE EXCEPTION 'Verified restriction owner required' USING ERRCODE='42501';
            END IF;
            IF TG_OP='INSERT' THEN
                IF NEW.revision<>1 THEN
                    RAISE EXCEPTION 'Restriction must begin at revision one' USING ERRCODE='23514';
                END IF;
            ELSIF (NEW.tenant_id,NEW.dataset,NEW.id{owner_columns})
                IS DISTINCT FROM (OLD.tenant_id,OLD.dataset,OLD.id{old_columns})
                OR NEW.revision<>OLD.revision+1 THEN
                RAISE EXCEPTION 'Restriction scope is immutable and revision must advance one'
                    USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END;
        $$
    """


def _windows(exclude_cancelled):
    member = import_module(
        "classync_persistence.migrations.versions.0028_room_occupancy_projection"
    ).MEMBER
    cancelled = (
        "AND COALESCE(r.payload::jsonb->>'status','active')<>'cancelled'"
        if exclude_cancelled
        else ""
    )
    # CREATE OR REPLACE keeps the function's owner and its existing EXECUTE grants.
    return f"""
        CREATE OR REPLACE FUNCTION classsync_scheduling.room_restriction_windows(p_dataset text)
        RETURNS TABLE(room_id text, starts_at timestamptz, ends_at timestamptz)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
        BEGIN
            IF p_dataset IS NULL OR p_dataset NOT IN ('institutional','synthetic')
                OR NOT EXISTS ({member}) THEN
                RAISE EXCEPTION 'An active tenant membership is required' USING ERRCODE='42501';
            END IF;
            RETURN QUERY
            SELECT r.room_id, r.starts_at, r.ends_at
            FROM classsync_scheduling.room_restrictions r
            WHERE r.tenant_id=current_setting('classsync.tenant_id',true)
                AND r.dataset=p_dataset {cancelled}
            ORDER BY r.room_id, r.starts_at;
        END;
        $$
    """


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
    admin = import_module(
        "classync_persistence.migrations.versions.0008_publication_transactions"
    ).ADMIN

    # Shared restrictions.
    op.execute(_restriction_guard(single_owner=False))
    op.execute("DROP POLICY restriction_edit ON classsync_scheduling.room_restrictions")
    op.execute(
        "CREATE POLICY restriction_edit ON classsync_scheduling.room_restrictions "
        f"FOR UPDATE USING {admin} "
        f"WITH CHECK ({admin} AND owner_uid=current_setting('classsync.uid',true))"
    )
    op.execute(_windows(exclude_cancelled=True))

    # Period lifecycle.
    op.execute("""
        ALTER TABLE classsync_academic.period_metadata
            ADD COLUMN archived_at timestamptz,
            ADD COLUMN archived_by text,
            ADD COLUMN cloned_from text,
            ADD CONSTRAINT period_archive_pair
                CHECK ((archived_at IS NULL) = (archived_by IS NULL)),
            ADD CONSTRAINT period_clone_source FOREIGN KEY (tenant_id,owner_uid,cloned_from)
                REFERENCES classsync_academic.period_metadata(tenant_id,owner_uid,id)
    """)
    op.execute("""
        CREATE FUNCTION classsync_academic.guard_period_archive()
        RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
        BEGIN
            IF TG_OP='INSERT' THEN
                IF NEW.archived_at IS NOT NULL OR NEW.archived_by IS NOT NULL THEN
                    RAISE EXCEPTION 'A new period cannot begin archived' USING ERRCODE='23514';
                END IF;
                RETURN NEW;
            END IF;
            IF OLD.archived_at IS NOT NULL THEN
                RAISE EXCEPTION 'Archived academic periods are read-only'
                    USING ERRCODE='23514', CONSTRAINT='academic_period_archived';
            END IF;
            IF NEW.cloned_from IS DISTINCT FROM OLD.cloned_from THEN
                RAISE EXCEPTION 'Period clone provenance is immutable' USING ERRCODE='23514';
            END IF;
            IF NEW.archived_at IS NOT NULL THEN
                IF NEW.archived_by IS DISTINCT FROM current_setting('classsync.uid',true) THEN
                    RAISE EXCEPTION 'Verified archiving Administrator required'
                        USING ERRCODE='42501';
                END IF;
                NEW.archived_at := transaction_timestamp();
            END IF;
            RETURN NEW;
        END; $$
    """)
    op.execute("""
        CREATE TRIGGER period_archive_guard BEFORE INSERT OR UPDATE
        ON classsync_academic.period_metadata FOR EACH ROW
        EXECUTE FUNCTION classsync_academic.guard_period_archive()
    """)
    # FOR SHARE serializes a concurrent archive with the write. Rows invisible under the
    # caller's context are left to the target table's own row-level security.
    op.execute("""
        CREATE FUNCTION classsync_academic.deny_archived_period_write()
        RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
        DECLARE
            v_tenant text; v_owner text; v_period text; v_archived timestamptz;
        BEGIN
            IF TG_OP='DELETE' THEN
                v_tenant:=OLD.tenant_id; v_owner:=OLD.owner_uid; v_period:=OLD.period_id;
            ELSIF TG_TABLE_NAME='drafts' THEN
                v_tenant:=NEW.tenant_id; v_owner:=NEW.owner_uid;
                v_period:=NEW.payload::jsonb->>'period_id';
            ELSE
                v_tenant:=NEW.tenant_id; v_owner:=NEW.owner_uid; v_period:=NEW.period_id;
            END IF;
            SELECT p.archived_at INTO v_archived FROM classsync_academic.period_metadata p
            WHERE p.tenant_id=v_tenant AND p.owner_uid=v_owner AND p.id=v_period
            FOR SHARE OF p;
            IF v_archived IS NOT NULL THEN
                RAISE EXCEPTION 'Archived academic periods are read-only'
                    USING ERRCODE='23514', CONSTRAINT='academic_period_archived';
            END IF;
            IF TG_OP='DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END; $$
    """)
    for table, operations in (
        ("classsync_academic.records", "INSERT OR UPDATE OR DELETE"),
        ("classsync_academic.calendars", "INSERT OR UPDATE OR DELETE"),
        ("classsync_scheduling.drafts", "INSERT"),
        ("classsync_scheduling.published_versions", "INSERT"),
    ):
        op.execute(
            f"CREATE TRIGGER period_not_archived BEFORE {operations} ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION classsync_academic.deny_archived_period_write()"
        )

    # Activity: restriction events belong to the tenant campus, not to one period.
    _checks((*PREVIOUS_EVENTS, *NEW_EVENTS), (*PREVIOUS_ENTITIES, "restriction"))
    op.execute(
        "ALTER TABLE classsync_scheduling.administrator_activity "
        "ALTER COLUMN period_id DROP NOT NULL"
    )
    op.execute(
        "ALTER TABLE classsync_scheduling.administrator_activity "
        "ADD CONSTRAINT administrator_activity_period_scope CHECK "
        "(period_id IS NOT NULL OR event_type = 'scheduling.restriction.saved')"
    )
    op.execute("""
        CREATE FUNCTION classsync_scheduling.audit_period_lifecycle()
        RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
        DECLARE v_event text;
        BEGIN
            IF TG_OP='INSERT' THEN
                IF NEW.cloned_from IS NULL THEN RETURN NEW; END IF;
                v_event:='academic.period.cloned';
            ELSE
                IF OLD.archived_at IS NOT NULL OR NEW.archived_at IS NULL THEN RETURN NEW; END IF;
                v_event:='academic.period.archived';
            END IF;
            IF NEW.tenant_id IS DISTINCT FROM current_setting('classsync.tenant_id',true)
                OR NEW.owner_uid IS DISTINCT FROM current_setting('classsync.uid',true) THEN
                RAISE EXCEPTION 'Administrative audit context required' USING ERRCODE='42501';
            END IF;
            INSERT INTO classsync_scheduling.administrator_activity
                (tenant_id,owner_uid,event_id,period_id,event_type,entity_type,entity_ref,revision)
            VALUES (NEW.tenant_id,NEW.owner_uid,gen_random_uuid(),NEW.id,v_event,'period',
                encode(sha256(convert_to(NEW.id,'UTF8')),'hex'),NEW.revision);
            RETURN NEW;
        END; $$
    """)
    op.execute(
        "CREATE TRIGGER period_lifecycle_audit AFTER INSERT OR UPDATE "
        "ON classsync_academic.period_metadata FOR EACH ROW "
        "EXECUTE FUNCTION classsync_scheduling.audit_period_lifecycle()"
    )
    op.execute("""
        CREATE FUNCTION classsync_scheduling.audit_restriction_activity()
        RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
        BEGIN
            IF NEW.tenant_id IS DISTINCT FROM current_setting('classsync.tenant_id',true)
                OR NEW.owner_uid IS DISTINCT FROM current_setting('classsync.uid',true) THEN
                RAISE EXCEPTION 'Administrative audit context required' USING ERRCODE='42501';
            END IF;
            INSERT INTO classsync_scheduling.administrator_activity
                (tenant_id,owner_uid,event_id,period_id,event_type,entity_type,entity_ref,revision)
            VALUES (NEW.tenant_id,NEW.owner_uid,gen_random_uuid(),NULL,
                'scheduling.restriction.saved','restriction',
                encode(sha256(convert_to(NEW.dataset || ':' || NEW.id,'UTF8')),'hex'),
                NEW.revision);
            RETURN NEW;
        END; $$
    """)
    op.execute(
        "CREATE TRIGGER restriction_activity AFTER INSERT OR UPDATE "
        "ON classsync_scheduling.room_restrictions FOR EACH ROW "
        "EXECUTE FUNCTION classsync_scheduling.audit_restriction_activity()"
    )
    op.execute("""
        CREATE FUNCTION classsync_scheduling.audit_roster_import(
            p_period_id text, p_revision bigint
        ) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
        DECLARE
            v_tenant text := current_setting('classsync.tenant_id',true);
            v_uid text := current_setting('classsync.uid',true);
            v_project text := current_setting('classsync.project_id',true);
        BEGIN
            IF p_revision IS NULL OR p_revision<1
                OR NOT EXISTS (
                    SELECT 1 FROM classsync_identity.memberships m
                    JOIN classsync_identity.tenants t ON t.id=m.tenant_id
                    WHERE m.tenant_id=v_tenant AND m.uid=v_uid AND m.state='active'
                      AND 'administrator'=ANY(m.roles) AND t.firebase_project_id=v_project
                )
                OR NOT EXISTS (
                    SELECT 1 FROM classsync_academic.period_metadata p
                    WHERE p.tenant_id=v_tenant AND p.owner_uid=v_uid AND p.id=p_period_id
                ) THEN
                RAISE EXCEPTION 'Administrative roster audit context required'
                    USING ERRCODE='42501';
            END IF;
            INSERT INTO classsync_scheduling.administrator_activity
                (tenant_id,owner_uid,event_id,period_id,event_type,entity_type,entity_ref,revision)
            VALUES (v_tenant,v_uid,gen_random_uuid(),p_period_id,'academic.roster.imported',
                'student_roster',
                encode(sha256(convert_to('import:' || p_period_id,'UTF8')),'hex'),p_revision);
        END; $$
    """)
    for function in (
        "classsync_academic.guard_period_archive()",
        "classsync_academic.deny_archived_period_write()",
        "classsync_scheduling.audit_period_lifecycle()",
        "classsync_scheduling.audit_restriction_activity()",
        "classsync_scheduling.audit_roster_import(text,bigint)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
    # As in 0025: the function re-checks the active Administrator context itself.
    op.execute(
        "GRANT EXECUTE ON FUNCTION classsync_scheduling.audit_roster_import(text,bigint) TO PUBLIC"
    )


def downgrade():
    # FORCE RLS would hide rows from the owner and make this refusal vacuous. Lift it for the
    # check only; the whole downgrade is one transaction, so a refusal restores it.
    guarded = (
        "classsync_scheduling.administrator_activity",
        "classsync_scheduling.room_restrictions",
        "classsync_academic.period_metadata",
    )
    for table in guarded:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM classsync_scheduling.administrator_activity
                       WHERE event_type IN ({_values(NEW_EVENTS)}) OR entity_type='restriction')
                OR EXISTS (SELECT 1 FROM classsync_scheduling.room_restrictions
                           WHERE payload::jsonb->>'status'='cancelled')
                OR EXISTS (SELECT 1 FROM classsync_academic.period_metadata
                           WHERE archived_at IS NOT NULL OR cloned_from IS NOT NULL) THEN
                RAISE EXCEPTION 'Restriction, archive, clone and import history must be retained';
            END IF;
        END $$
    """)
    for table in guarded:
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute("DROP FUNCTION classsync_scheduling.audit_roster_import(text,bigint)")
    op.execute("DROP TRIGGER restriction_activity ON classsync_scheduling.room_restrictions")
    op.execute("DROP FUNCTION classsync_scheduling.audit_restriction_activity()")
    op.execute("DROP TRIGGER period_lifecycle_audit ON classsync_academic.period_metadata")
    op.execute("DROP FUNCTION classsync_scheduling.audit_period_lifecycle()")
    for table in (
        "classsync_academic.records",
        "classsync_academic.calendars",
        "classsync_scheduling.drafts",
        "classsync_scheduling.published_versions",
    ):
        op.execute(f"DROP TRIGGER period_not_archived ON {table}")
    op.execute("DROP FUNCTION classsync_academic.deny_archived_period_write()")
    op.execute("DROP TRIGGER period_archive_guard ON classsync_academic.period_metadata")
    op.execute("DROP FUNCTION classsync_academic.guard_period_archive()")
    op.execute("""
        ALTER TABLE classsync_academic.period_metadata
            DROP CONSTRAINT period_clone_source,
            DROP CONSTRAINT period_archive_pair,
            DROP COLUMN cloned_from,
            DROP COLUMN archived_by,
            DROP COLUMN archived_at
    """)
    op.execute(
        "ALTER TABLE classsync_scheduling.administrator_activity "
        "DROP CONSTRAINT administrator_activity_period_scope"
    )
    op.execute(
        "ALTER TABLE classsync_scheduling.administrator_activity "
        "ALTER COLUMN period_id SET NOT NULL"
    )
    _checks(PREVIOUS_EVENTS, PREVIOUS_ENTITIES)
    op.execute(_windows(exclude_cancelled=False))
    op.execute("DROP POLICY restriction_edit ON classsync_scheduling.room_restrictions")
    admin = import_module(
        "classync_persistence.migrations.versions.0008_publication_transactions"
    ).ADMIN
    owner = f"({admin} AND owner_uid=current_setting('classsync.uid',true))"
    op.execute(
        "CREATE POLICY restriction_edit ON classsync_scheduling.room_restrictions "
        f"FOR UPDATE USING {owner} WITH CHECK {owner}"
    )
    op.execute(_restriction_guard(single_owner=True))

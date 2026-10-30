"""Current-authority locking and owned audited restrictions; no endpoint adoption."""

from alembic import op

revision = "0008_publication_transactions"
down_revision = "0007_publication_state"
branch_labels = None
depends_on = None

ADMIN = """(
    tenant_id=current_setting('classsync.tenant_id',true) AND EXISTS (
        SELECT 1 FROM classsync_identity.memberships m
        JOIN classsync_identity.tenants t ON t.id=m.tenant_id
        WHERE m.tenant_id=current_setting('classsync.tenant_id',true)
            AND m.uid=current_setting('classsync.uid',true) AND m.state='active'
            AND 'administrator'=ANY(m.roles)
            AND t.firebase_project_id=current_setting('classsync.project_id',true)
    )
)"""


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
    # This helper exposes a row lock, never identity mutation. Its non-superuser
    # owner remains subject to FORCE RLS; fixed SQL accepts no caller identifiers.
    op.execute("""
        CREATE FUNCTION classsync_scheduling.lock_publication_authority()
        RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
        DECLARE authorized boolean;
        BEGIN
            SELECT true INTO authorized
            FROM classsync_identity.memberships m
            JOIN classsync_identity.tenants t ON t.id=m.tenant_id
            WHERE m.tenant_id=current_setting('classsync.tenant_id',true)
                AND m.uid=current_setting('classsync.uid',true) AND m.state='active'
                AND 'administrator'=ANY(m.roles)
                AND t.firebase_project_id=current_setting('classsync.project_id',true)
            FOR SHARE OF m,t;
            RETURN COALESCE(authorized,false);
        END;
        $$
    """)
    op.execute(
        "REVOKE ALL ON FUNCTION classsync_scheduling.lock_publication_authority() FROM PUBLIC"
    )
    op.execute("""
        CREATE TABLE classsync_scheduling.room_restrictions (
            tenant_id text NOT NULL,
            dataset text NOT NULL CHECK (dataset IN ('synthetic','institutional')),
            id text NOT NULL CHECK (length(btrim(id)) BETWEEN 1 AND 80),
            owner_uid text NOT NULL,
            room_id text NOT NULL CHECK (length(btrim(room_id)) BETWEEN 1 AND 80),
            revision bigint NOT NULL CHECK (revision>=1),
            starts_at timestamptz NOT NULL,ends_at timestamptz NOT NULL CHECK (ends_at>starts_at),
            payload text NOT NULL CHECK (jsonb_typeof(payload::jsonb)='object'),
            checksum text NOT NULL CHECK
                (checksum=encode(sha256(convert_to(payload,'UTF8')),'hex')),
            PRIMARY KEY (tenant_id,dataset,id),
            FOREIGN KEY (tenant_id,owner_uid)
                REFERENCES classsync_identity.memberships(tenant_id,uid),
            CHECK (COALESCE((payload::jsonb)->>'id','')=id),
            CHECK (COALESCE((payload::jsonb)->>'dataset','')=dataset),
            CHECK (COALESCE((payload::jsonb)->>'room_id','')=room_id),
            CHECK (COALESCE(((payload::jsonb)->>'revision')::bigint,0)=revision),
            CHECK ((payload::jsonb)->>'starts_at' IS NOT NULL
                AND ((payload::jsonb)->>'starts_at')::timestamptz=starts_at),
            CHECK ((payload::jsonb)->>'ends_at' IS NOT NULL
                AND ((payload::jsonb)->>'ends_at')::timestamptz=ends_at)
        )
    """)
    op.execute("""
        CREATE TABLE classsync_scheduling.restriction_audit (
            tenant_id text NOT NULL,dataset text NOT NULL,id text NOT NULL,
            revision bigint NOT NULL CHECK (revision>=1),actor_uid text NOT NULL,
            occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            old_snapshot jsonb,new_snapshot jsonb NOT NULL,
            PRIMARY KEY (tenant_id,dataset,id,revision),
            FOREIGN KEY (tenant_id,dataset,id)
                REFERENCES classsync_scheduling.room_restrictions(tenant_id,dataset,id),
            CHECK (COALESCE(new_snapshot->>'tenant_id','')=tenant_id),
            CHECK (COALESCE(new_snapshot->>'dataset','')=dataset),
            CHECK (COALESCE(new_snapshot->>'id','')=id),
            CHECK (COALESCE(new_snapshot->>'owner_uid','')=actor_uid),
            CHECK (COALESCE((new_snapshot->>'revision')::bigint,0)=revision)
        )
    """)
    op.execute("""
        CREATE FUNCTION classsync_scheduling.guard_room_restriction()
        RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
        BEGIN
            IF NEW.owner_uid IS DISTINCT FROM current_setting('classsync.uid',true) THEN
                RAISE EXCEPTION 'Verified restriction owner required' USING ERRCODE='42501';
            END IF;
            IF TG_OP='INSERT' THEN
                IF NEW.revision<>1 THEN
                    RAISE EXCEPTION 'Restriction must begin at revision one' USING ERRCODE='23514';
                END IF;
            ELSIF (NEW.tenant_id,NEW.dataset,NEW.id,NEW.owner_uid)
                IS DISTINCT FROM (OLD.tenant_id,OLD.dataset,OLD.id,OLD.owner_uid)
                OR NEW.revision<>OLD.revision+1 THEN
                RAISE EXCEPTION 'Restriction scope is immutable and revision must advance one'
                    USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE FUNCTION classsync_scheduling.audit_room_restriction()
        RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
        BEGIN
            IF TG_TABLE_SCHEMA<>'classsync_scheduling' OR TG_TABLE_NAME<>'room_restrictions'
                OR TG_OP NOT IN ('INSERT','UPDATE') THEN
                RAISE EXCEPTION 'Restriction audit trigger context required' USING ERRCODE='42501';
            END IF;
            INSERT INTO classsync_scheduling.restriction_audit
                (tenant_id,dataset,id,revision,actor_uid,old_snapshot,new_snapshot)
            VALUES (NEW.tenant_id,NEW.dataset,NEW.id,NEW.revision,NEW.owner_uid,
                CASE WHEN TG_OP='UPDATE' THEN to_jsonb(OLD) ELSE NULL END,to_jsonb(NEW));
            RETURN NEW;
        END;
        $$
    """)
    for function in ("guard_room_restriction", "audit_room_restriction"):
        op.execute(f"REVOKE ALL ON FUNCTION classsync_scheduling.{function}() FROM PUBLIC")
    op.execute("""
        CREATE TRIGGER restriction_step BEFORE INSERT OR UPDATE
        ON classsync_scheduling.room_restrictions FOR EACH ROW
        EXECUTE FUNCTION classsync_scheduling.guard_room_restriction()
    """)
    op.execute("""
        CREATE TRIGGER restriction_audit AFTER INSERT OR UPDATE
        ON classsync_scheduling.room_restrictions FOR EACH ROW
        EXECUTE FUNCTION classsync_scheduling.audit_room_restriction()
    """)
    owner = f"({ADMIN} AND owner_uid=current_setting('classsync.uid',true))"
    for table in ("room_restrictions", "restriction_audit"):
        op.execute(f"ALTER TABLE classsync_scheduling.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE classsync_scheduling.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON classsync_scheduling.{table} FROM PUBLIC")
        op.execute(
            f"CREATE POLICY restriction_read ON classsync_scheduling.{table} "
            f"FOR SELECT USING {ADMIN}"
        )
        mutations = "UPDATE OR DELETE" if table == "restriction_audit" else "DELETE"
        op.execute(
            f"CREATE TRIGGER restriction_retained BEFORE {mutations} "
            f"ON classsync_scheduling.{table} FOR EACH ROW "
            "EXECUTE FUNCTION classsync_scheduling.deny_snapshot_mutation()"
        )
        op.execute(
            f"CREATE TRIGGER restriction_no_truncate BEFORE TRUNCATE "
            f"ON classsync_scheduling.{table} FOR EACH STATEMENT "
            "EXECUTE FUNCTION classsync_scheduling.deny_snapshot_mutation()"
        )
    op.execute(
        "CREATE POLICY restriction_create ON classsync_scheduling.room_restrictions "
        f"FOR INSERT WITH CHECK {owner}"
    )
    op.execute(
        "CREATE POLICY restriction_edit ON classsync_scheduling.room_restrictions "
        f"FOR UPDATE USING {owner} WITH CHECK {owner}"
    )
    op.execute(
        "CREATE POLICY restriction_record_audit ON classsync_scheduling.restriction_audit "
        f"FOR INSERT WITH CHECK ({ADMIN} AND actor_uid=current_setting('classsync.uid',true))"
    )


def downgrade():
    op.execute("DROP TABLE classsync_scheduling.restriction_audit")
    op.execute("DROP TABLE classsync_scheduling.room_restrictions")
    for function in (
        "audit_room_restriction",
        "guard_room_restriction",
        "lock_publication_authority",
    ):
        op.execute(f"DROP FUNCTION classsync_scheduling.{function}()")

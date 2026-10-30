"""Owner-scoped immutable solver snapshots and drafts; no publication cutover."""

from alembic import op

revision = "0006_scheduling_drafts"
down_revision = "0005_academic_records"
branch_labels = None
depends_on = None

PREDICATE = """(
    tenant_id=current_setting('classsync.tenant_id',true)
    AND owner_uid=current_setting('classsync.uid',true)
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
    op.execute("CREATE SCHEMA classsync_scheduling")
    op.execute("REVOKE ALL ON SCHEMA classsync_scheduling FROM PUBLIC")
    op.execute("""
        CREATE TABLE classsync_scheduling.solver_runs (
            tenant_id text NOT NULL,owner_uid text NOT NULL,
            id text NOT NULL CHECK (length(btrim(id)) BETWEEN 1 AND 100),
            created_at timestamptz NOT NULL,
            schema_version integer NOT NULL DEFAULT 1 CHECK (schema_version=1),
            payload text NOT NULL CHECK (jsonb_typeof(payload::jsonb)='object'),
            checksum text NOT NULL CHECK
                (checksum=encode(sha256(convert_to(payload,'UTF8')),'hex')),
            PRIMARY KEY (tenant_id,owner_uid,id),
            FOREIGN KEY (tenant_id,owner_uid)
                REFERENCES classsync_identity.memberships(tenant_id,uid),
            CHECK ((payload::jsonb)->'result'->>'run_id' IS NOT NULL
                AND (payload::jsonb)->'result'->>'run_id'=id),
            CHECK (COALESCE((payload::jsonb)->'result'->>'solver_status','')
                IN ('feasible','optimal'))
        )
    """)
    op.execute("""
        CREATE TABLE classsync_scheduling.drafts (
            tenant_id text NOT NULL,owner_uid text NOT NULL,
            id text NOT NULL CHECK (length(btrim(id)) BETWEEN 1 AND 100),
            run_id text NOT NULL,
            title text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 160),
            created_at timestamptz NOT NULL,
            schema_version integer NOT NULL DEFAULT 1 CHECK (schema_version=1),
            status text NOT NULL DEFAULT 'draft' CHECK (status='draft'),
            idempotency_key text NOT NULL CHECK (length(idempotency_key) BETWEEN 8 AND 100),
            payload text NOT NULL CHECK (jsonb_typeof(payload::jsonb)='object'),
            checksum text NOT NULL CHECK
                (checksum=encode(sha256(convert_to(payload,'UTF8')),'hex')),
            PRIMARY KEY (tenant_id,owner_uid,id),
            UNIQUE (tenant_id,owner_uid,run_id),
            UNIQUE (tenant_id,owner_uid,idempotency_key),
            FOREIGN KEY (tenant_id,owner_uid,run_id)
                REFERENCES classsync_scheduling.solver_runs(tenant_id,owner_uid,id),
            CHECK ((payload::jsonb)->>'id' IS NOT NULL AND (payload::jsonb)->>'id'=id),
            CHECK ((payload::jsonb)->>'run_id' IS NOT NULL AND (payload::jsonb)->>'run_id'=run_id),
            CHECK ((payload::jsonb)->>'creator' IS NOT NULL
                AND (payload::jsonb)->>'creator'=owner_uid),
            CHECK ((payload::jsonb)->>'title' IS NOT NULL AND (payload::jsonb)->>'title'=title),
            CHECK ((payload::jsonb)->>'created_at' IS NOT NULL
                AND ((payload::jsonb)->>'created_at')::timestamptz=created_at)
        )
    """)
    op.execute("""
        CREATE INDEX scheduling_drafts_by_owner
        ON classsync_scheduling.drafts (tenant_id,owner_uid,created_at DESC,id DESC)
    """)
    op.execute("""
        CREATE FUNCTION classsync_scheduling.deny_snapshot_mutation()
        RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
        BEGIN
            RAISE EXCEPTION 'Scheduling snapshots are immutable' USING ERRCODE='42501';
        END;
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION classsync_scheduling.deny_snapshot_mutation() FROM PUBLIC")
    for table in ("solver_runs", "drafts"):
        op.execute(f"ALTER TABLE classsync_scheduling.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE classsync_scheduling.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY scheduling_owner ON classsync_scheduling.{table} "
            f"USING {PREDICATE} WITH CHECK {PREDICATE}"
        )
        op.execute(f"REVOKE ALL ON classsync_scheduling.{table} FROM PUBLIC")
        op.execute(
            f"CREATE TRIGGER snapshot_immutable BEFORE UPDATE OR DELETE "
            f"ON classsync_scheduling.{table} FOR EACH ROW "
            "EXECUTE FUNCTION classsync_scheduling.deny_snapshot_mutation()"
        )
        op.execute(
            f"CREATE TRIGGER snapshot_no_truncate BEFORE TRUNCATE "
            f"ON classsync_scheduling.{table} FOR EACH STATEMENT "
            "EXECUTE FUNCTION classsync_scheduling.deny_snapshot_mutation()"
        )


def downgrade():
    op.execute("DROP TABLE classsync_scheduling.drafts")
    op.execute("DROP TABLE classsync_scheduling.solver_runs")
    op.execute("DROP FUNCTION classsync_scheduling.deny_snapshot_mutation()")
    op.execute("DROP SCHEMA classsync_scheduling")

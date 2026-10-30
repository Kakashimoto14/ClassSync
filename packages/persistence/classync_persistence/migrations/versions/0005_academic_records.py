"""Owner-scoped academic records, references and calendars; no live cutover."""

from alembic import op

revision = "0005_academic_records"
down_revision = "0004_academic_period_metadata"
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
    op.execute("""
        CREATE TABLE classsync_academic.records (
            tenant_id text NOT NULL, owner_uid text NOT NULL, period_id text NOT NULL,
            kind text NOT NULL CHECK (kind IN
                ('programs','subjects','sections','faculty','resources','offerings','constraints')),
            id text NOT NULL CHECK (length(btrim(id)) BETWEEN 1 AND 128),
            revision bigint NOT NULL CHECK (revision>=1),
            unique_label text NOT NULL, updated_at timestamptz NOT NULL,
            updated_by text NOT NULL CHECK (updated_by=owner_uid),
            payload text NOT NULL CHECK (jsonb_typeof(payload::jsonb)='object'),
            checksum text NOT NULL CHECK
                (checksum=encode(sha256(convert_to(payload,'UTF8')),'hex')),
            PRIMARY KEY (tenant_id,owner_uid,period_id,kind,id),
            UNIQUE (tenant_id,owner_uid,period_id,kind,unique_label),
            FOREIGN KEY (tenant_id,owner_uid,period_id)
                REFERENCES classsync_academic.period_metadata(tenant_id,owner_uid,id),
            CHECK ((payload::jsonb)->>'id' IS NOT NULL
                AND (payload::jsonb)->>'kind' IS NOT NULL
                AND (payload::jsonb)->>'id'=id AND (payload::jsonb)->>'kind'=kind)
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX academic_faculty_identity
        ON classsync_academic.records
            (tenant_id,owner_uid,period_id,lower(btrim((payload::jsonb)->>'institutional_id')))
        WHERE kind='faculty' AND (payload::jsonb)->>'institutional_id' IS NOT NULL
            AND btrim((payload::jsonb)->>'institutional_id')<>''
    """)
    op.execute("""
        CREATE TABLE classsync_academic.record_references (
            tenant_id text NOT NULL, owner_uid text NOT NULL, period_id text NOT NULL,
            source_kind text NOT NULL, source_id text NOT NULL,
            target_kind text NOT NULL, target_id text NOT NULL,
            PRIMARY KEY (tenant_id,owner_uid,period_id,source_kind,source_id,target_kind,target_id),
            FOREIGN KEY (tenant_id,owner_uid,period_id,source_kind,source_id)
                REFERENCES classsync_academic.records(tenant_id,owner_uid,period_id,kind,id)
                ON DELETE CASCADE,
            FOREIGN KEY (tenant_id,owner_uid,period_id,target_kind,target_id)
                REFERENCES classsync_academic.records(tenant_id,owner_uid,period_id,kind,id)
                ON DELETE RESTRICT
        )
    """)
    op.execute("""
        CREATE INDEX academic_reference_target ON classsync_academic.record_references
            (tenant_id,owner_uid,period_id,target_kind,target_id)
    """)
    op.execute("""
        CREATE TABLE classsync_academic.calendars (
            tenant_id text NOT NULL, owner_uid text NOT NULL, period_id text NOT NULL,
            payload text NOT NULL CHECK (jsonb_typeof(payload::jsonb)='object'),
            checksum text NOT NULL CHECK
                (checksum=encode(sha256(convert_to(payload,'UTF8')),'hex')),
            PRIMARY KEY (tenant_id,owner_uid,period_id),
            FOREIGN KEY (tenant_id,owner_uid,period_id)
                REFERENCES classsync_academic.period_metadata(tenant_id,owner_uid,id)
        )
    """)
    for table in ("records", "record_references", "calendars"):
        op.execute(f"ALTER TABLE classsync_academic.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE classsync_academic.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY academic_owner ON classsync_academic.{table} "
            f"USING {PREDICATE} WITH CHECK {PREDICATE}"
        )
        op.execute(f"REVOKE ALL ON classsync_academic.{table} FROM PUBLIC")
    op.execute(
        "CREATE POLICY academic_owner_update ON classsync_academic.period_metadata "
        f"FOR UPDATE USING {PREDICATE} WITH CHECK {PREDICATE}"
    )


def downgrade():
    op.execute("DROP POLICY academic_owner_update ON classsync_academic.period_metadata")
    for table in ("calendars", "record_references", "records"):
        op.execute(f"DROP TABLE classsync_academic.{table}")

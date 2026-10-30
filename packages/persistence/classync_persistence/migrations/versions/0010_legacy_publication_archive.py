"""Retain legacy publication evidence without treating it as active state."""

from alembic import op

revision = "0010_legacy_publication_archive"
down_revision = "0009_publication_record_projection"
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
        CREATE TABLE classsync_scheduling.legacy_publication_archive (
            source_fingerprint text NOT NULL CHECK
                (source_fingerprint ~ '^[0-9a-f]{64}$'),
            source_tenant text NOT NULL CHECK (length(btrim(source_tenant)) BETWEEN 1 AND 128),
            source_actor text NOT NULL CHECK (length(btrim(source_actor)) BETWEEN 1 AND 128),
            legacy_id text NOT NULL CHECK (length(btrim(legacy_id)) BETWEEN 1 AND 100),
            source_sequence bigint NOT NULL CHECK (source_sequence>=1),
            tenant_id text NOT NULL REFERENCES classsync_identity.tenants(id),
            owner_uid text NOT NULL CHECK (length(btrim(owner_uid)) BETWEEN 1 AND 128),
            dataset text NOT NULL CHECK (dataset IN ('institutional','synthetic')),
            period_id text NOT NULL CHECK (length(btrim(period_id)) BETWEEN 1 AND 120),
            revision bigint NOT NULL CHECK (revision>=1),
            draft_id text NOT NULL CHECK (length(btrim(draft_id)) BETWEEN 1 AND 100),
            created_at timestamptz NOT NULL,
            idempotency_key text NOT NULL CHECK (length(idempotency_key) BETWEEN 8 AND 120),
            request_hash text NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
            payload text NOT NULL CHECK (jsonb_typeof(payload::jsonb)='object'),
            checksum text NOT NULL CHECK
                (checksum=encode(sha256(convert_to(payload,'UTF8')),'hex')),
            archived_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (source_fingerprint,source_tenant,legacy_id),
            UNIQUE (source_fingerprint,source_sequence),
            UNIQUE (tenant_id,source_fingerprint,source_tenant,dataset,idempotency_key),
            FOREIGN KEY (tenant_id,owner_uid)
                REFERENCES classsync_identity.memberships(tenant_id,uid),
            CHECK (COALESCE(payload::jsonb->'draft'->>'id','')=draft_id),
            CHECK (COALESCE(payload::jsonb->'draft'->>'period_id','')=period_id),
            CHECK (COALESCE(payload::jsonb->'draft'->>'creator','')=source_actor),
            CHECK (COALESCE(jsonb_typeof(payload::jsonb->'calendar'),'')='object')
        )
    """)
    op.execute("ALTER TABLE classsync_scheduling.legacy_publication_archive "
               "ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE classsync_scheduling.legacy_publication_archive "
               "FORCE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON classsync_scheduling.legacy_publication_archive FROM PUBLIC")
    op.execute(
        "CREATE POLICY legacy_publication_archive_admin "
        "ON classsync_scheduling.legacy_publication_archive "
        f"FOR SELECT USING {ADMIN}"
    )
    # FORCE RLS also applies to this non-BYPASSRLS table owner. A narrowly
    # owner-only SELECT policy lets its downgrade guard inspect emptiness; the
    # runtime role cannot SET ROLE to the migration owner.
    op.execute("""
        CREATE POLICY legacy_publication_archive_owner_read
        ON classsync_scheduling.legacy_publication_archive FOR SELECT USING (
            current_user=pg_catalog.pg_get_userbyid((
                SELECT relowner FROM pg_catalog.pg_class
                WHERE oid='classsync_scheduling.legacy_publication_archive'::regclass
            ))
        )
    """)
    op.execute(
        "CREATE POLICY legacy_publication_archive_insert "
        "ON classsync_scheduling.legacy_publication_archive "
        f"FOR INSERT WITH CHECK {ADMIN}"
    )
    op.execute("""
        CREATE TRIGGER legacy_publication_archive_immutable
        BEFORE UPDATE OR DELETE ON classsync_scheduling.legacy_publication_archive
        FOR EACH ROW EXECUTE FUNCTION classsync_scheduling.deny_snapshot_mutation()
    """)
    op.execute("""
        CREATE TRIGGER legacy_publication_archive_no_truncate
        BEFORE TRUNCATE ON classsync_scheduling.legacy_publication_archive
        FOR EACH STATEMENT EXECUTE FUNCTION classsync_scheduling.deny_snapshot_mutation()
    """)


def downgrade():
    # Serialize the emptiness check with inserts. Without this lock, an archive
    # import could commit after the check but before DROP TABLE acquires its lock.
    op.execute(
        "LOCK TABLE classsync_scheduling.legacy_publication_archive "
        "IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM classsync_scheduling.legacy_publication_archive) THEN
                RAISE EXCEPTION 'Legacy publication archive contains retained evidence'
                    USING ERRCODE='55000';
            END IF;
        END $$
    """)
    op.execute("DROP TABLE classsync_scheduling.legacy_publication_archive")

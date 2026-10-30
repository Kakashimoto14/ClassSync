"""Relational publication state only; no provider adoption or approval authority."""

from alembic import op

revision = "0007_publication_state"
down_revision = "0006_scheduling_drafts"
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
        CREATE TABLE classsync_scheduling.published_versions (
            tenant_id text NOT NULL,
            dataset text NOT NULL CHECK (dataset IN ('institutional','synthetic')),
            period_id text NOT NULL,
            owner_uid text NOT NULL,
            actor_uid text NOT NULL CHECK (actor_uid=owner_uid),
            draft_id text NOT NULL,
            id text NOT NULL CHECK (length(btrim(id)) BETWEEN 1 AND 100),
            sequence bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
            revision bigint NOT NULL CHECK (revision>=1),
            academic_revision bigint NOT NULL CHECK (academic_revision>=1),
            created_at timestamptz NOT NULL,
            idempotency_key text NOT NULL CHECK (length(idempotency_key) BETWEEN 8 AND 120),
            command text NOT NULL CHECK (jsonb_typeof(command::jsonb)='object'),
            request_hash text NOT NULL CHECK
                (request_hash=encode(sha256(convert_to(command,'UTF8')),'hex')),
            payload text NOT NULL CHECK (jsonb_typeof(payload::jsonb)='object'),
            checksum text NOT NULL CHECK
                (checksum=encode(sha256(convert_to(payload,'UTF8')),'hex')),
            PRIMARY KEY (tenant_id,dataset,id),
            UNIQUE (tenant_id,dataset,idempotency_key),
            UNIQUE (tenant_id,dataset,period_id,revision),
            UNIQUE (tenant_id,dataset,period_id,revision,owner_uid),
            FOREIGN KEY (tenant_id,owner_uid,draft_id)
                REFERENCES classsync_scheduling.drafts(tenant_id,owner_uid,id),
            FOREIGN KEY (tenant_id,owner_uid,period_id)
                REFERENCES classsync_academic.period_metadata(tenant_id,owner_uid,id),
            CHECK (COALESCE((payload::jsonb)->'draft'->>'id','')=draft_id),
            CHECK (COALESCE((payload::jsonb)->'draft'->>'period_id','')=period_id),
            CHECK (COALESCE((payload::jsonb)->'draft'->>'creator','')=owner_uid),
            CHECK (COALESCE((command::jsonb)->>'draft_id','')=draft_id),
            CHECK (COALESCE((command::jsonb)->>'dataset','')=dataset),
            CHECK (COALESCE((command::jsonb)->>'source','')='administrator'),
            CHECK (COALESCE((command::jsonb)->>'idempotency_key','')=idempotency_key),
            CHECK (COALESCE(((command::jsonb)->>'expected_version')::bigint,-1)=revision-1),
            CHECK (COALESCE(((command::jsonb)->>'expected_academic_revision')::bigint,-1)
                =academic_revision),
            CHECK (COALESCE(jsonb_typeof((command::jsonb)->'calendar'),'')='object'
                AND COALESCE(jsonb_typeof((payload::jsonb)->'calendar'),'')='object'
                AND (command::jsonb)->'calendar'=(payload::jsonb)->'calendar')
        )
    """)
    op.execute("""
        CREATE TABLE classsync_scheduling.publication_heads (
            tenant_id text NOT NULL,
            dataset text NOT NULL CHECK (dataset IN ('institutional','synthetic')),
            period_id text NOT NULL,
            owner_uid text NOT NULL,
            revision bigint NOT NULL CHECK (revision>=1),
            PRIMARY KEY (tenant_id,dataset,period_id),
            FOREIGN KEY (tenant_id,dataset,period_id,revision,owner_uid)
                REFERENCES classsync_scheduling.published_versions
                    (tenant_id,dataset,period_id,revision,owner_uid)
        )
    """)
    # The unique period/revision key supports ordered history; the sequence index
    # supports bounded tenant/dataset event polling without exposing other tenants.
    op.execute("""
        CREATE INDEX publication_versions_by_tenant_sequence
        ON classsync_scheduling.published_versions (tenant_id,dataset,sequence)
    """)
    op.execute("""
        CREATE FUNCTION classsync_scheduling.guard_publication_head()
        RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
        BEGIN
            IF TG_OP='INSERT' THEN
                IF NEW.revision<>1 THEN
                    RAISE EXCEPTION 'A publication head must begin at revision one'
                        USING ERRCODE='23514';
                END IF;
            ELSIF (NEW.tenant_id,NEW.dataset,NEW.period_id,NEW.owner_uid)
                IS DISTINCT FROM (OLD.tenant_id,OLD.dataset,OLD.period_id,OLD.owner_uid)
                OR NEW.revision<>OLD.revision+1 THEN
                RAISE EXCEPTION 'A publication head must advance exactly one revision'
                    USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION classsync_scheduling.guard_publication_head() FROM PUBLIC")
    op.execute("""
        CREATE TRIGGER publication_head_step BEFORE INSERT OR UPDATE
        ON classsync_scheduling.publication_heads FOR EACH ROW
        EXECUTE FUNCTION classsync_scheduling.guard_publication_head()
    """)
    for table in ("published_versions", "publication_heads"):
        op.execute(f"ALTER TABLE classsync_scheduling.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE classsync_scheduling.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON classsync_scheduling.{table} FROM PUBLIC")
        op.execute(
            f"CREATE POLICY publication_read ON classsync_scheduling.{table} "
            f"FOR SELECT USING {ADMIN}"
        )
        mutations = "UPDATE OR DELETE" if table == "published_versions" else "DELETE"
        op.execute(
            f"CREATE TRIGGER publication_immutable BEFORE {mutations} "
            f"ON classsync_scheduling.{table} FOR EACH ROW "
            "EXECUTE FUNCTION classsync_scheduling.deny_snapshot_mutation()"
        )
        op.execute(
            f"CREATE TRIGGER publication_no_truncate BEFORE TRUNCATE "
            f"ON classsync_scheduling.{table} FOR EACH STATEMENT "
            "EXECUTE FUNCTION classsync_scheduling.deny_snapshot_mutation()"
        )
    owner = f"""({ADMIN} AND owner_uid=current_setting('classsync.uid',true) AND (
        (revision=1 AND NOT EXISTS (
            SELECT 1 FROM classsync_scheduling.publication_heads h
            WHERE h.tenant_id=published_versions.tenant_id
                AND h.dataset=published_versions.dataset
                AND h.period_id=published_versions.period_id
        )) OR EXISTS (
            SELECT 1 FROM classsync_scheduling.publication_heads h
            WHERE h.tenant_id=published_versions.tenant_id
                AND h.dataset=published_versions.dataset
                AND h.period_id=published_versions.period_id
                AND h.owner_uid=current_setting('classsync.uid',true)
                AND h.revision=published_versions.revision-1
        )
    ))"""
    op.execute(
        "CREATE POLICY publication_create ON classsync_scheduling.published_versions "
        f"FOR INSERT WITH CHECK {owner}"
    )
    head_owner = f"""({ADMIN} AND EXISTS (
        SELECT 1 FROM classsync_scheduling.published_versions v
        WHERE v.tenant_id=publication_heads.tenant_id AND v.dataset=publication_heads.dataset
            AND v.period_id=publication_heads.period_id AND v.revision=publication_heads.revision
            AND v.owner_uid=publication_heads.owner_uid
            AND v.owner_uid=current_setting('classsync.uid',true)
    ))"""
    op.execute(
        "CREATE POLICY publication_head_create ON classsync_scheduling.publication_heads "
        f"FOR INSERT WITH CHECK {head_owner}"
    )
    op.execute(
        "CREATE POLICY publication_head_advance ON classsync_scheduling.publication_heads "
        f"FOR UPDATE USING ({ADMIN} AND owner_uid=current_setting('classsync.uid',true)) "
        f"WITH CHECK {head_owner}"
    )
    op.execute("""
        CREATE FUNCTION classsync_scheduling.require_publication_head()
        RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM classsync_scheduling.publication_heads h
                WHERE h.tenant_id=NEW.tenant_id AND h.dataset=NEW.dataset
                    AND h.period_id=NEW.period_id AND h.owner_uid=NEW.owner_uid
                    AND h.revision>=NEW.revision
            ) THEN
                RAISE EXCEPTION 'A publication version and its head must commit together'
                    USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION classsync_scheduling.require_publication_head() FROM PUBLIC")
    op.execute("""
        CREATE CONSTRAINT TRIGGER publication_version_requires_head
        AFTER INSERT ON classsync_scheduling.published_versions
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
        EXECUTE FUNCTION classsync_scheduling.require_publication_head()
    """)
    op.execute(
        "REVOKE ALL ON SEQUENCE classsync_scheduling.published_versions_sequence_seq FROM PUBLIC"
    )


def downgrade():
    # The insertion policy references heads. Remove that named dependency explicitly;
    # broad CASCADE would hide unexpected objects or changes outside this migration.
    op.execute("DROP POLICY publication_create ON classsync_scheduling.published_versions")
    op.execute("DROP TABLE classsync_scheduling.publication_heads")
    op.execute("DROP TABLE classsync_scheduling.published_versions")
    op.execute("DROP FUNCTION classsync_scheduling.guard_publication_head()")
    op.execute("DROP FUNCTION classsync_scheduling.require_publication_head()")

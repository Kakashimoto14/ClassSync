"""Tenant-scoped identity keys and current membership, without provisioning policy."""

from alembic import op

revision = "0001_identity"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA classsync_identity")
    op.execute("""
        CREATE TABLE classsync_identity.tenants (
            id text PRIMARY KEY CHECK (length(btrim(id)) BETWEEN 1 AND 128),
            firebase_project_id text NOT NULL
                CHECK (length(btrim(firebase_project_id)) BETWEEN 1 AND 128)
        )
    """)
    op.execute("""
        CREATE TABLE classsync_identity.people (
            tenant_id text NOT NULL REFERENCES classsync_identity.tenants(id),
            id text NOT NULL CHECK (length(btrim(id)) BETWEEN 1 AND 128),
            PRIMARY KEY (tenant_id, id)
        )
    """)
    for table in ("students", "faculty"):
        op.execute(f"""
            CREATE TABLE classsync_identity.{table} (
                tenant_id text NOT NULL,
                id text NOT NULL CHECK (length(btrim(id)) BETWEEN 1 AND 128),
                person_id text NOT NULL,
                PRIMARY KEY (tenant_id, id),
                UNIQUE (tenant_id, id, person_id),
                FOREIGN KEY (tenant_id, person_id)
                    REFERENCES classsync_identity.people(tenant_id, id)
            )
        """)
    op.execute("""
        CREATE TABLE classsync_identity.memberships (
            tenant_id text NOT NULL,
            uid text NOT NULL CHECK (length(btrim(uid)) BETWEEN 1 AND 128),
            person_id text NOT NULL,
            student_id text,
            faculty_id text,
            roles text[] NOT NULL,
            state text NOT NULL CHECK (state IN ('active', 'inactive', 'revoked')),
            revision bigint NOT NULL CHECK (revision >= 1),
            PRIMARY KEY (tenant_id, uid),
            FOREIGN KEY (tenant_id, person_id)
                REFERENCES classsync_identity.people(tenant_id, id),
            FOREIGN KEY (tenant_id, student_id, person_id)
                REFERENCES classsync_identity.students(tenant_id, id, person_id),
            FOREIGN KEY (tenant_id, faculty_id, person_id)
                REFERENCES classsync_identity.faculty(tenant_id, id, person_id),
            CHECK (array_ndims(roles) = 1 AND cardinality(roles) BETWEEN 1 AND 3),
            CHECK (array_position(roles, NULL) IS NULL),
            CHECK (roles <@ ARRAY['student', 'teacher', 'administrator']::text[]),
            CHECK (cardinality(roles) =
                ('student' = ANY(roles))::int + ('teacher' = ANY(roles))::int
                + ('administrator' = ANY(roles))::int),
            CHECK (NOT ('student' = ANY(roles)) OR student_id IS NOT NULL),
            CHECK (NOT ('teacher' = ANY(roles)) OR faculty_id IS NOT NULL)
        )
    """)
    # RLS is defense in depth behind a trusted application boundary. Context
    # setters are never exposed as a client SQL API or accepted from token roles.
    for table in ("tenants", "people", "students", "faculty", "memberships"):
        tenant_key = "id" if table == "tenants" else "tenant_id"
        predicate = f"{tenant_key} = current_setting('classsync.tenant_id', true)"
        if table == "memberships":
            predicate += " AND uid = current_setting('classsync.uid', true)"
        op.execute(f"ALTER TABLE classsync_identity.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE classsync_identity.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY identity_scope ON classsync_identity.{table}
                USING ({predicate}) WITH CHECK ({predicate})
        """)
    op.execute("REVOKE ALL ON SCHEMA classsync_identity FROM PUBLIC")
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA classsync_identity FROM PUBLIC")


def downgrade():
    for table in ("memberships", "faculty", "students", "people", "tenants"):
        op.execute(f"DROP TABLE classsync_identity.{table}")
    op.execute("DROP SCHEMA classsync_identity")

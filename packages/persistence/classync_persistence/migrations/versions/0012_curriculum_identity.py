"""Version-scoped academic course index; existing payloads/roles/RLS remain intact."""

from importlib import import_module

from alembic import op

revision = "0012_curriculum_identity"
down_revision = "0011_publication_policy_cycle"
branch_labels = None
depends_on = None


def upgrade():
    predicate = import_module(
        "classync_persistence.migrations.versions.0005_academic_records"
    ).PREDICATE
    op.execute("""
        CREATE TABLE classsync_academic.cohort_bindings (
            tenant_id text NOT NULL, owner_uid text NOT NULL, student_id text NOT NULL,
            entry_cohort_year integer NOT NULL CHECK(entry_cohort_year BETWEEN 1900 AND 2200),
            curriculum_version_id text NOT NULL CHECK(length(curriculum_version_id)>0),
            PRIMARY KEY(tenant_id,owner_uid,student_id)
        )
    """)
    op.execute("ALTER TABLE classsync_academic.cohort_bindings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE classsync_academic.cohort_bindings FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY cohort_binding_read ON classsync_academic.cohort_bindings "
        f"FOR SELECT USING {predicate}"
    )
    op.execute(
        f"CREATE POLICY cohort_binding_insert ON classsync_academic.cohort_bindings "
        f"FOR INSERT WITH CHECK {predicate}"
    )
    op.execute("REVOKE ALL ON classsync_academic.cohort_bindings FROM PUBLIC")
    op.execute("""
        CREATE UNIQUE INDEX academic_curriculum_course_identity
        ON classsync_academic.records
        (tenant_id,owner_uid,period_id,
         ((payload::jsonb)->>'curriculum_version_id'),
         ((payload::jsonb)->>'curriculum_course_id'))
        WHERE kind='subjects' AND (payload::jsonb)->>'curriculum_version_id' IS NOT NULL
    """)


def downgrade():
    op.execute("DROP TABLE classsync_academic.cohort_bindings")
    op.execute("DROP INDEX classsync_academic.academic_curriculum_course_identity")

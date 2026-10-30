"""Break the version INSERT -> head SELECT -> version SELECT policy cycle."""

from alembic import op

revision = "0011_publication_policy_cycle"
down_revision = "0010_legacy_publication_archive"
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
    # INSERT authority must not read heads: 0009's head SELECT policy already
    # reads versions to enforce current-record visibility. Revision ordering and
    # atomic version/head commits remain enforced by 0007's unique keys, head
    # FK, head-step trigger and deferred require_publication_head trigger.
    op.execute(
        "ALTER POLICY publication_create ON classsync_scheduling.published_versions "
        f"WITH CHECK ({ADMIN} AND owner_uid=current_setting('classsync.uid',true))"
    )


def downgrade():
    # Restore the exact 0007 write predicate. 0009/0010 alone retain the known
    # cycle; this downgrade is for disposable compatibility checks, not service.
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
        "ALTER POLICY publication_create ON classsync_scheduling.published_versions "
        f"WITH CHECK {owner}"
    )

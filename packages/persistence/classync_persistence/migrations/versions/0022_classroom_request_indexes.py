"""Index classroom request owner and tenant timelines."""

from alembic import op

revision = "0022_classroom_request_indexes"
down_revision = "0021_student_email_and_cor_source"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE INDEX classroom_requests_tenant_owner_created_idx
        ON classsync_scheduling.classroom_requests
            (tenant_id, owner_uid, created_at DESC)
    """)
    op.execute("""
        CREATE INDEX classroom_requests_tenant_created_idx
        ON classsync_scheduling.classroom_requests
            (tenant_id, created_at DESC)
    """)


def downgrade():
    op.execute(
        "DROP INDEX IF EXISTS "
        "classsync_scheduling.classroom_requests_tenant_created_idx"
    )
    op.execute(
        "DROP INDEX IF EXISTS "
        "classsync_scheduling.classroom_requests_tenant_owner_created_idx"
    )

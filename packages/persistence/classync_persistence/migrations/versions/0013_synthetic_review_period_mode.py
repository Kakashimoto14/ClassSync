"""Mark dedicated synthetic review periods separately from institutional periods."""

from alembic import op

revision = "0013_synthetic_review_period_mode"
down_revision = "0012_curriculum_identity"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE classsync_academic.period_metadata
        ADD COLUMN data_mode text NOT NULL DEFAULT 'institutional'
        CHECK (data_mode IN ('institutional', 'synthetic-review'))
    """)


def downgrade():
    op.execute("""
        ALTER TABLE classsync_academic.period_metadata
        DROP COLUMN data_mode
    """)

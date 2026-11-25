"""Store roster display names on tenant-scoped person records."""

from alembic import op

revision = "0023_person_display_name"
down_revision = "0022_classroom_request_indexes"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE classsync_identity.people ADD COLUMN display_name text")
    op.execute("""
        ALTER TABLE classsync_identity.people
        ADD CONSTRAINT people_display_name_valid CHECK (
            display_name IS NULL OR (length(btrim(display_name)) BETWEEN 1 AND 160)
        )
    """)


def downgrade():
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM classsync_identity.people WHERE display_name IS NOT NULL) THEN
                RAISE EXCEPTION 'Person display names must be exported before downgrade';
            END IF;
        END $$
    """)
    op.execute("ALTER TABLE classsync_identity.people DROP CONSTRAINT people_display_name_valid")
    op.execute("ALTER TABLE classsync_identity.people DROP COLUMN display_name")

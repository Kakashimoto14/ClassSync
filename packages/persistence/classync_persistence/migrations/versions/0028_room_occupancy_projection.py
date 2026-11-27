"""Tenant-wide room occupancy for every member, without class, section or teacher details.

Teacher and Student reads of `published_versions` are limited by RLS to versions that contain
their own record (0009), so a room booked by a version the caller is not in looked free. These
SECURITY DEFINER functions return only room/time facts for the caller's tenant: assignment
ids (opaque), weekdays, minutes and room ids, the calendar dates and room/time exception
fields, and restriction intervals. Subjects, sections, teachers, students, reasons and actors
never leave the function.
"""

from alembic import op

revision = "0028_room_occupancy_projection"
down_revision = "0027_roster_audit_events"
branch_labels = None
depends_on = None

MEMBER = """
    SELECT 1 FROM classsync_identity.memberships m
    JOIN classsync_identity.tenants t ON t.id=m.tenant_id
    WHERE m.tenant_id=current_setting('classsync.tenant_id',true)
        AND m.uid=current_setting('classsync.uid',true) AND m.state='active'
        AND t.firebase_project_id=current_setting('classsync.project_id',true)
"""


def owner_read(table):
    # FORCE RLS applies to the non-BYPASSRLS table owner too. As in 0010, an owner-only
    # SELECT policy lets the definer functions read; the runtime role cannot SET ROLE to it.
    return f"""
        CREATE POLICY occupancy_owner_read ON classsync_scheduling.{table}
        FOR SELECT USING (
            current_user=pg_catalog.pg_get_userbyid((
                SELECT relowner FROM pg_catalog.pg_class
                WHERE oid='classsync_scheduling.{table}'::regclass
            ))
        )
    """


def upgrade():
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles
                       WHERE rolname=current_user AND (rolsuper OR rolbypassrls)) THEN
                RAISE EXCEPTION 'A non-superuser non-BYPASSRLS migration owner is required'
                    USING ERRCODE='42501';
            END IF;
        END $$
    """)
    for table in ("published_versions", "room_restrictions"):
        op.execute(owner_read(table))
    op.execute(f"""
        CREATE FUNCTION classsync_scheduling.room_occupancy_versions(p_dataset text, p_day date)
        RETURNS TABLE(period_id text, version_id text, version_rank bigint, projection jsonb)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
        BEGIN
            IF p_dataset IS NULL OR p_dataset NOT IN ('institutional','synthetic')
                OR p_day IS NULL OR NOT EXISTS ({MEMBER}) THEN
                RAISE EXCEPTION 'An active tenant membership is required' USING ERRCODE='42501';
            END IF;
            -- Only versions whose calendar covers the day can occupy a room on it. The rank is
            -- per tenant, so the cross-tenant sequence never leaves the function.
            RETURN QUERY
            SELECT v.period_id, v.id, row_number() OVER (ORDER BY v.sequence), jsonb_build_object(
                'buffer', COALESCE(
                    (v.payload::jsonb->'draft'->'input_snapshot'->>'transition_buffer_minutes')
                    ::integer, 0),
                'assignments', COALESCE((
                    SELECT jsonb_agg(jsonb_build_object(
                        'id', a->>'id', 'day', (a->>'day')::integer,
                        'start', (a->>'start')::integer, 'end', (a->>'end')::integer,
                        'room_id', a->>'room_id'))
                    FROM jsonb_array_elements(
                        v.payload::jsonb->'draft'->'generation_result'->'assignments') a
                ), '[]'::jsonb),
                'calendar', jsonb_build_object(
                    'effective_start', v.payload::jsonb->'calendar'->'effective_start',
                    'effective_end', v.payload::jsonb->'calendar'->'effective_end',
                    'instructional_days', v.payload::jsonb->'calendar'->'instructional_days',
                    'exceptions', COALESCE((
                        SELECT jsonb_agg(jsonb_build_object(
                            'date', e->'date', 'assignment_id', e->'assignment_id',
                            'cancelled', e->'cancelled', 'moved_to', e->'moved_to',
                            'room_id', e->'room_id', 'start', e->'start') ORDER BY position)
                        FROM jsonb_array_elements(v.payload::jsonb->'calendar'->'exceptions')
                            WITH ORDINALITY AS x(e, position)
                    ), '[]'::jsonb)
                )
            )
            FROM classsync_scheduling.published_versions v
            WHERE v.tenant_id=current_setting('classsync.tenant_id',true)
                AND v.dataset=p_dataset
                AND (v.payload::jsonb->'calendar'->>'effective_start')::date<=p_day
                AND (v.payload::jsonb->'calendar'->>'effective_end')::date>=p_day
            ORDER BY v.sequence;
        END;
        $$
    """)
    op.execute(f"""
        CREATE FUNCTION classsync_scheduling.room_restriction_windows(p_dataset text)
        RETURNS TABLE(room_id text, starts_at timestamptz, ends_at timestamptz)
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
        BEGIN
            IF p_dataset IS NULL OR p_dataset NOT IN ('institutional','synthetic')
                OR NOT EXISTS ({MEMBER}) THEN
                RAISE EXCEPTION 'An active tenant membership is required' USING ERRCODE='42501';
            END IF;
            RETURN QUERY
            SELECT r.room_id, r.starts_at, r.ends_at
            FROM classsync_scheduling.room_restrictions r
            WHERE r.tenant_id=current_setting('classsync.tenant_id',true)
                AND r.dataset=p_dataset
            ORDER BY r.room_id, r.starts_at;
        END;
        $$
    """)
    for signature in ("room_occupancy_versions(text,date)", "room_restriction_windows(text)"):
        op.execute(f"REVOKE ALL ON FUNCTION classsync_scheduling.{signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION classsync_scheduling.{signature} TO PUBLIC")


def downgrade():
    for signature in ("room_occupancy_versions(text,date)", "room_restriction_windows(text)"):
        op.execute(f"DROP FUNCTION classsync_scheduling.{signature}")
    for table in ("published_versions", "room_restrictions"):
        op.execute(f"DROP POLICY occupancy_owner_read ON classsync_scheduling.{table}")

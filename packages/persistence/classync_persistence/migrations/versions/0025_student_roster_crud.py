"""Authorize and audit tenant-scoped Administrator roster writes."""

from importlib import import_module

from alembic import op

revision = "0025_student_roster_crud"
down_revision = "0024_academic_record_deletion_audit"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE POLICY email_verification_challenge_admin_read
        ON classsync_identity.email_verification_challenges FOR SELECT
        USING (
            tenant_id=current_setting('classsync.tenant_id',true)
            AND EXISTS (
                SELECT 1 FROM classsync_identity.memberships m
                JOIN classsync_identity.tenants t ON t.id=m.tenant_id
                WHERE m.tenant_id=current_setting('classsync.tenant_id',true)
                  AND m.uid=current_setting('classsync.uid',true)
                  AND m.state='active' AND 'administrator'=ANY(m.roles)
                  AND t.firebase_project_id=current_setting('classsync.project_id',true)
            )
        )
    """)
    op.execute(
        "ALTER TABLE classsync_scheduling.administrator_activity "
        "DROP CONSTRAINT administrator_activity_event_type_check"
    )
    op.execute("""
        ALTER TABLE classsync_scheduling.administrator_activity
        ADD CONSTRAINT administrator_activity_event_type_check CHECK (event_type IN (
            'academic.period.created','academic.record.created','academic.record.updated',
            'academic.record.deleted','academic.calendar.saved','scheduling.draft.saved',
            'scheduling.publication.published','academic.student.created',
            'academic.student.updated','academic.student.deleted'
        ))
    """)
    op.execute(
        "ALTER TABLE classsync_scheduling.administrator_activity "
        "DROP CONSTRAINT administrator_activity_entity_type_check"
    )
    op.execute("""
        ALTER TABLE classsync_scheduling.administrator_activity
        ADD CONSTRAINT administrator_activity_entity_type_check CHECK (entity_type IN (
            'period','programs','subjects','sections','faculty','resources','offerings',
            'constraints','calendar','draft','publication','student_roster'
        ))
    """)

    predicate = import_module(
        "classync_persistence.migrations.versions.0005_academic_records"
    ).PREDICATE
    op.execute(
        "CREATE POLICY cohort_binding_admin_update ON "
        "classsync_academic.cohort_bindings FOR UPDATE "
        f"USING {predicate} WITH CHECK {predicate}"
    )
    op.execute(
        "CREATE POLICY cohort_binding_admin_delete ON "
        "classsync_academic.cohort_bindings FOR DELETE USING "
        f"{predicate}"
    )

    op.execute("""
        CREATE FUNCTION classsync_identity.manage_student_roster(
            p_operation text, p_student_id text, p_new_student_id text,
            p_full_name text, p_email text, p_enrollment_status text
        ) RETURNS void LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog AS $$
        DECLARE
            v_tenant text := current_setting('classsync.tenant_id',true);
            v_uid text := current_setting('classsync.uid',true);
            v_project text := current_setting('classsync.project_id',true);
            v_person text;
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM classsync_identity.memberships m
                JOIN classsync_identity.tenants t ON t.id=m.tenant_id
                WHERE m.tenant_id=v_tenant AND m.uid=v_uid AND m.state='active'
                  AND 'administrator'=ANY(m.roles) AND t.firebase_project_id=v_project
            ) THEN
                RAISE EXCEPTION 'Active Administrator context required' USING ERRCODE='42501';
            END IF;
            IF p_operation NOT IN ('create','update','delete')
                OR p_student_id !~ '^[0-9]{2}-[0-9]{5}$' THEN
                RAISE EXCEPTION 'Invalid roster operation or student ID' USING ERRCODE='22023';
            END IF;

            IF p_operation='create' THEN
                IF p_full_name IS NULL OR length(btrim(p_full_name)) NOT BETWEEN 1 AND 160
                    OR p_email IS NULL OR length(p_email)>320
                    OR p_email<>lower(p_email)
                    OR p_email !~ (
                        '^[a-z0-9!#$%&''*+/=?^_`{|}~-]+([.][a-z0-9!#$%&''*+/=?^_`{|}~-]+)*@'
                        || '([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?[.])+[a-z]{2,63}$'
                    )
                    OR p_enrollment_status NOT IN ('active','inactive','unverified') THEN
                    RAISE EXCEPTION 'Invalid roster profile fields' USING ERRCODE='22023';
                END IF;
                v_person:=gen_random_uuid()::text;
                INSERT INTO classsync_identity.people(tenant_id,id,display_name)
                VALUES (v_tenant,v_person,btrim(p_full_name));
                INSERT INTO classsync_identity.students
                    (tenant_id,id,person_id,registered_email,enrollment_status,verification_source)
                VALUES (v_tenant,p_student_id,v_person,p_email,p_enrollment_status,'unverified');
            ELSIF p_operation='update' THEN
                SELECT person_id INTO v_person FROM classsync_identity.students
                WHERE tenant_id=v_tenant AND id=p_student_id FOR UPDATE;
                IF v_person IS NULL THEN
                    RAISE EXCEPTION 'Roster student not found' USING ERRCODE='P0002';
                END IF;
                IF p_new_student_id IS NULL OR p_new_student_id !~ '^[0-9]{2}-[0-9]{5}$'
                    OR p_full_name IS NULL OR length(btrim(p_full_name)) NOT BETWEEN 1 AND 160
                    OR p_email IS NULL OR length(p_email)>320
                    OR p_email<>lower(p_email)
                    OR p_email !~ (
                        '^[a-z0-9!#$%&''*+/=?^_`{|}~-]+([.][a-z0-9!#$%&''*+/=?^_`{|}~-]+)*@'
                        || '([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?[.])+[a-z]{2,63}$'
                    )
                    OR p_enrollment_status NOT IN ('active','inactive','unverified') THEN
                    RAISE EXCEPTION 'Invalid roster profile fields' USING ERRCODE='22023';
                END IF;
                IF EXISTS (
                    SELECT 1 FROM classsync_identity.email_verification_challenges c
                    WHERE c.tenant_id=v_tenant AND c.student_id=p_student_id
                      AND c.consumed_at IS NULL AND c.expires_at>transaction_timestamp()
                      AND p_email IS DISTINCT FROM (
                          SELECT s.registered_email FROM classsync_identity.students s
                          WHERE s.tenant_id=v_tenant AND s.id=p_student_id
                      )
                ) THEN
                    RAISE EXCEPTION 'Active student email verification request exists'
                        USING ERRCODE='23514', CONSTRAINT='student_email_verification_pending';
                END IF;
                UPDATE classsync_identity.students SET
                    id=p_new_student_id, registered_email=p_email,
                    enrollment_status=p_enrollment_status,
                    verification_source=CASE
                        WHEN id IS DISTINCT FROM p_new_student_id
                          OR registered_email IS DISTINCT FROM p_email
                        THEN 'unverified' ELSE verification_source END
                WHERE tenant_id=v_tenant AND id=p_student_id;
                UPDATE classsync_identity.people SET display_name=btrim(p_full_name)
                WHERE tenant_id=v_tenant AND id=v_person;
            ELSE
                SELECT person_id INTO v_person FROM classsync_identity.students
                WHERE tenant_id=v_tenant AND id=p_student_id FOR UPDATE;
                IF v_person IS NULL THEN
                    RAISE EXCEPTION 'Roster student not found' USING ERRCODE='P0002';
                END IF;
                DELETE FROM classsync_identity.students
                WHERE tenant_id=v_tenant AND id=p_student_id;
                DELETE FROM classsync_identity.people p
                WHERE p.tenant_id=v_tenant AND p.id=v_person
                  AND NOT EXISTS (SELECT 1 FROM classsync_identity.students s
                                  WHERE s.tenant_id=p.tenant_id AND s.person_id=p.id)
                  AND NOT EXISTS (SELECT 1 FROM classsync_identity.faculty f
                                  WHERE f.tenant_id=p.tenant_id AND f.person_id=p.id)
                  AND NOT EXISTS (SELECT 1 FROM classsync_identity.memberships m
                                  WHERE m.tenant_id=p.tenant_id AND m.person_id=p.id);
            END IF;
        END; $$
    """)
    op.execute("""
        CREATE FUNCTION classsync_academic.set_student_cohort_binding(
            p_student_id text, p_entry_cohort_year integer, p_curriculum_version_id text
        ) RETURNS void LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog AS $$
        DECLARE
            v_tenant text := current_setting('classsync.tenant_id',true);
            v_uid text := current_setting('classsync.uid',true);
            v_project text := current_setting('classsync.project_id',true);
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM classsync_identity.memberships m
                JOIN classsync_identity.tenants t ON t.id=m.tenant_id
                WHERE m.tenant_id=v_tenant AND m.uid=v_uid AND m.state='active'
                  AND 'administrator'=ANY(m.roles) AND t.firebase_project_id=v_project
            ) THEN
                RAISE EXCEPTION 'Active Administrator context required' USING ERRCODE='42501';
            END IF;
            IF p_student_id IS NULL OR length(btrim(p_student_id))=0
                OR ((p_entry_cohort_year IS NULL) <> (p_curriculum_version_id IS NULL)) THEN
                RAISE EXCEPTION 'Invalid student cohort binding' USING ERRCODE='22023';
            END IF;
            IF p_curriculum_version_id IS NULL THEN
                DELETE FROM classsync_academic.cohort_bindings
                WHERE tenant_id=v_tenant AND owner_uid=v_uid AND student_id=p_student_id;
            ELSE
                INSERT INTO classsync_academic.cohort_bindings
                    (tenant_id,owner_uid,student_id,entry_cohort_year,curriculum_version_id)
                VALUES (v_tenant,v_uid,p_student_id,p_entry_cohort_year,p_curriculum_version_id)
                ON CONFLICT (tenant_id,owner_uid,student_id) DO UPDATE SET
                    entry_cohort_year=excluded.entry_cohort_year,
                    curriculum_version_id=excluded.curriculum_version_id;
            END IF;
        END; $$
    """)
    op.execute("""
        CREATE FUNCTION classsync_scheduling.audit_student_roster_write(
            p_period_id text, p_event_type text, p_student_id text, p_revision bigint
        ) RETURNS void LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog AS $$
        DECLARE
            v_tenant text := current_setting('classsync.tenant_id',true);
            v_uid text := current_setting('classsync.uid',true);
            v_project text := current_setting('classsync.project_id',true);
        BEGIN
            IF p_event_type NOT IN (
                    'academic.student.created','academic.student.updated','academic.student.deleted')
                OR p_student_id IS NULL OR p_revision<1
                OR NOT EXISTS (
                    SELECT 1 FROM classsync_identity.memberships m
                    JOIN classsync_identity.tenants t ON t.id=m.tenant_id
                    WHERE m.tenant_id=v_tenant AND m.uid=v_uid AND m.state='active'
                      AND 'administrator'=ANY(m.roles) AND t.firebase_project_id=v_project
                )
                OR NOT EXISTS (
                    SELECT 1 FROM classsync_academic.period_metadata p
                    WHERE p.tenant_id=v_tenant AND p.owner_uid=v_uid AND p.id=p_period_id
                ) THEN
                RAISE EXCEPTION 'Administrative roster audit context required'
                    USING ERRCODE='42501';
            END IF;
            INSERT INTO classsync_scheduling.administrator_activity
                (tenant_id,owner_uid,event_id,period_id,event_type,entity_type,entity_ref,revision)
            VALUES (v_tenant,v_uid,gen_random_uuid(),p_period_id,p_event_type,'student_roster',
                encode(sha256(convert_to('student:' || p_student_id,'UTF8')),'hex'),p_revision);
        END; $$
    """)
    for signature in (
        "classsync_identity.manage_student_roster(text,text,text,text,text,text)",
        "classsync_academic.set_student_cohort_binding(text,integer,text)",
        "classsync_scheduling.audit_student_roster_write(text,text,text,bigint)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        # The runtime's current GUC context and active Admin membership are checked
        # inside every SECURITY DEFINER function. DB callers never supply tenant roles.
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO PUBLIC")


def downgrade():
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM classsync_scheduling.administrator_activity
                WHERE entity_type='student_roster'
            ) THEN
                RAISE EXCEPTION 'Student roster audit rows must be retained';
            END IF;
        END $$
    """)
    for signature in (
        "classsync_scheduling.audit_student_roster_write(text,text,text,bigint)",
        "classsync_academic.set_student_cohort_binding(text,integer,text)",
        "classsync_identity.manage_student_roster(text,text,text,text,text,text)",
    ):
        op.execute(f"DROP FUNCTION {signature}")
    op.execute(
        "DROP POLICY email_verification_challenge_admin_read "
        "ON classsync_identity.email_verification_challenges"
    )
    op.execute("DROP POLICY cohort_binding_admin_delete ON classsync_academic.cohort_bindings")
    op.execute("DROP POLICY cohort_binding_admin_update ON classsync_academic.cohort_bindings")
    op.execute(
        "ALTER TABLE classsync_scheduling.administrator_activity "
        "DROP CONSTRAINT administrator_activity_entity_type_check"
    )
    op.execute("""
        ALTER TABLE classsync_scheduling.administrator_activity
        ADD CONSTRAINT administrator_activity_entity_type_check CHECK (entity_type IN (
            'period','programs','subjects','sections','faculty','resources','offerings',
            'constraints','calendar','draft','publication'
        ))
    """)
    op.execute(
        "ALTER TABLE classsync_scheduling.administrator_activity "
        "DROP CONSTRAINT administrator_activity_event_type_check"
    )
    op.execute("""
        ALTER TABLE classsync_scheduling.administrator_activity
        ADD CONSTRAINT administrator_activity_event_type_check CHECK (event_type IN (
            'academic.period.created','academic.record.created','academic.record.updated',
            'academic.record.deleted','academic.calendar.saved','scheduling.draft.saved',
            'scheduling.publication.published'
        ))
    """)

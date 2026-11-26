"""Complete owner-scoped academic snapshots on explicit PostgreSQL configuration.

Not installed as the service default. No implicit migration, credentials, catalog
fallback or original-data cutover. Shared record_rules remains the business rule
source for both local SQLite and this adapter.
"""

import json
from contextlib import contextmanager
from uuid import uuid4

from classync_contracts.academic import (
    AcademicConstraints,
    AcademicPeriod,
    AcademicSection,
    AcademicSnapshot,
    RecordWrite,
    RosterStudentWrite,
)
from classync_contracts.calendar import AcademicCalendar
from classync_contracts.identity import (
    MembershipAuthorizationError,
    MembershipErrorCode,
    VerifiedPrincipal,
)
from classync_persistence.academic_periods import (
    ARCHIVED_PERIOD_TITLE_PATTERN,
    PostgresAcademicPeriods,
    utc_timestamp,
)
from classync_persistence.database import transaction
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError, SQLAlchemyError

from .record_rules import (
    AcademicError,
    checksum,
    encode,
    initial_records,
    references,
    timestamp,
    unique_label,
    validate_calendar,
    validate_period_data_mode,
    validate_record,
)
from .repository import AcademicRepository
from .student_roster import enrollment_for_section


class PostgresAcademicRepository:
    def __init__(self, engine, *, tenant_id, firebase_project_id, principal: VerifiedPrincipal):
        PostgresAcademicPeriods.validate_principal(principal)
        self.context = PostgresAcademicPeriods(
            engine,
            tenant_id=tenant_id,
            firebase_project_id=firebase_project_id,
        )
        self.engine, self.principal = engine, principal
        self.keys = {"tenant": tenant_id, "owner": principal.uid}

    @contextmanager
    def session(self, *, write=False):
        try:
            with transaction(self.engine) as db:
                if not write:
                    db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
                self.context.context(db, self.principal)
                authorized = db.scalar(
                    text("""
                    SELECT 1 FROM classsync_identity.memberships m
                    JOIN classsync_identity.tenants t ON t.id=m.tenant_id
                    WHERE m.tenant_id=:tenant AND m.uid=:owner AND m.state='active'
                      AND 'administrator'=ANY(m.roles) AND t.firebase_project_id=:project
                """),
                    {**self.keys, "project": self.context.project_id},
                )
                if not authorized:
                    raise MembershipAuthorizationError(MembershipErrorCode.DENIED)
                yield db
        except IntegrityError as error:
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            if constraint == "students_pkey":
                raise AcademicError(
                    409, "student_id_conflict", "That student ID already exists in this tenant."
                ) from error
            if constraint == "student_email_verification_pending":
                raise AcademicError(
                    409,
                    "student_email_verification_pending",
                    "Wait for the active verification request to expire before changing email.",
                ) from error
            if constraint and ("student_id_fkey" in constraint or "person_id_fkey" in constraint):
                raise AcademicError(
                    409,
                    "student_identity_linked",
                    "This student has a linked account or verification record and cannot be "
                    "deleted or re-keyed.",
                ) from error
            if constraint == "academic_faculty_identity":
                raise AcademicError(
                    409,
                    "faculty_identity_duplicate",
                    "A faculty record with this institutional identifier already "
                    "exists in this period. Edit that record instead.",
                ) from error
            raise AcademicError(
                409,
                "academic_integrity",
                "Duplicate record or invalid academic reference. Nothing was saved.",
            ) from error
        except DBAPIError as error:
            if getattr(error.orig, "sqlstate", None) in {"40001", "40P01"}:
                raise AcademicError(
                    409,
                    "academic_version_conflict",
                    "Academic data changed; reload before retrying.",
                ) from error
            raise AcademicError(
                503,
                "academic_storage_unavailable",
                "Academic storage is unavailable. No save was confirmed; retry safely.",
            ) from error
        except SQLAlchemyError as error:
            raise AcademicError(
                503,
                "academic_storage_unavailable",
                "Academic storage is unavailable. No save was confirmed; retry safely.",
            ) from error

    def params(self, period_id=None, **extra):
        return {**self.keys, "period": period_id, **extra}

    def envelope(self, row):
        # One checksum/identity/Pydantic decoder, shared with the existing adapter.
        return AcademicRepository.envelope(
            self,
            {
                **row,
                "updated_at": utc_timestamp(row["updated_at"]),
            },
        )

    def period_in(self, db, period_id, *, lock=False):
        row = (
            db.execute(
                text(
                    """
            SELECT id,title,revision,created_at,data_mode FROM classsync_academic.period_metadata
            WHERE tenant_id=:tenant AND owner_uid=:owner AND id=:period
        """
                    + (" FOR UPDATE" if lock else "")
                ),
                self.params(period_id),
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise AcademicError(
                404,
                "period_not_found",
                "This academic period does not exist in your permitted scope.",
            )
        calendar = (
            db.execute(
                text("""
            SELECT payload,checksum FROM classsync_academic.calendars
            WHERE tenant_id=:tenant AND owner_uid=:owner AND period_id=:period
        """),
                self.params(period_id),
            )
            .mappings()
            .one_or_none()
        )
        try:
            value = None
            period = dict(row)
            data_mode = period.pop("data_mode")
            if calendar is not None:
                if checksum(calendar["payload"]) != calendar["checksum"]:
                    raise ValueError("Checksum mismatch")
                value = AcademicCalendar.model_validate(json.loads(calendar["payload"]))
            return AcademicPeriod(
                **{**period, "created_at": utc_timestamp(row["created_at"])},
                source=("synthetic-review" if data_mode == "synthetic-review" else "institutional"),
                calendar=value,
            )
        except ValueError as error:
            raise AcademicError(
                409,
                "academic_snapshot_integrity",
                "Stored academic calendar is corrupt or incompatible; no data was substituted.",
            ) from error

    def snapshot_in(self, db, period_id):
        period = self.period_in(db, period_id)
        rows = (
            db.execute(
                text("""
            SELECT * FROM classsync_academic.records
            WHERE tenant_id=:tenant AND owner_uid=:owner AND period_id=:period ORDER BY kind,id
        """),
                self.params(period_id),
            )
            .mappings()
            .all()
        )
        return AcademicSnapshot(period=period, records=[self.envelope(row) for row in rows])

    def snapshot(self, period_id):
        with self.session() as db:
            return self.snapshot_in(db, period_id)

    def periods(self):
        with self.session() as db:
            ids = db.scalars(
                text("""
                SELECT id FROM classsync_academic.period_metadata
                WHERE tenant_id=:tenant AND owner_uid=:owner AND data_mode='institutional'
                  AND title NOT LIKE :archived
                ORDER BY created_at DESC,id
            """),
                {**self.keys, "archived": ARCHIVED_PERIOD_TITLE_PATTERN},
            ).all()
            return [self.period_in(db, identity) for identity in ids]

    def create_period(self, body):
        validate_calendar(body.calendar)
        period_id = str(uuid4())
        with self.session(write=True) as db:
            db.execute(
                text("""
                INSERT INTO classsync_academic.period_metadata (tenant_id,owner_uid,id,title)
                VALUES (:tenant,:owner,:period,:title)
            """),
                self.params(period_id, title=body.title),
            )
            if body.calendar:
                self.calendar_in(db, period_id, body.calendar)
            for record in initial_records(body.include_cdm_catalog):
                self.write_in(db, period_id, RecordWrite(expected_revision=0, record=record))
            return self.snapshot_in(db, period_id)

    def create_synthetic_review_period(self, body, records):
        """Atomic synthetic-only pilot import using existing scoped records/audit/RLS."""
        if (
            any(r.kind == "faculty" and (not r.synthetic or r.institutional_id) for r in records)
            or (any(r.kind == "resources" and r.source != "synthetic" for r in records))
            or not any(r.kind == "resources" for r in records)
        ):
            raise AcademicError(
                422, "synthetic_only", "Pilot requires synthetic rooms and faculty."
            )
        validate_calendar(body.calendar)
        period_id = str(uuid4())
        with self.session(write=True) as db:
            db.execute(
                text("""
                INSERT INTO classsync_academic.period_metadata
                    (tenant_id,owner_uid,id,title,data_mode)
                VALUES (:tenant,:owner,:period,:title,'synthetic-review')
            """),
                self.params(period_id, title=body.title),
            )
            if body.calendar:
                self.calendar_in(db, period_id, body.calendar)
            for record in records:
                if record.kind == "sections":
                    record = record.model_copy(update={"period_id": period_id})
                self.write_in(db, period_id, RecordWrite(expected_revision=0, record=record))
            return self.snapshot_in(db, period_id)

    def calendar_in(self, db, period_id, calendar):
        payload = calendar.model_dump_json()
        db.execute(
            text("""
            INSERT INTO classsync_academic.calendars
                (tenant_id,owner_uid,period_id,payload,checksum)
            VALUES (:tenant,:owner,:period,:payload,:checksum)
            ON CONFLICT (tenant_id,owner_uid,period_id)
                DO UPDATE SET payload=excluded.payload,checksum=excluded.checksum
        """),
            self.params(period_id, payload=payload, checksum=checksum(payload)),
        )

    def bump(self, db, period_id):
        changed = db.execute(
            text("""
            UPDATE classsync_academic.period_metadata SET revision=revision+1
            WHERE tenant_id=:tenant AND owner_uid=:owner AND id=:period
        """),
            self.params(period_id),
        )
        if changed.rowcount != 1:
            raise MembershipAuthorizationError(MembershipErrorCode.DENIED)

    def save_calendar(self, period_id, body):
        validate_calendar(body.calendar)
        with self.session(write=True) as db:
            period = self.period_in(db, period_id, lock=True)
            if period.revision != body.expected_revision:
                raise AcademicError(
                    409,
                    "calendar_version_conflict",
                    "Academic data changed; reload before saving calendar dates.",
                )
            self.calendar_in(db, period_id, body.calendar)
            self.bump(db, period_id)
            return self.snapshot_in(db, period_id)

    def save(self, period_id, kind, record_id, body):
        if body.record.kind != kind or body.record.id != record_id:
            raise AcademicError(
                422, "record_identity", "The record identity must match its destination."
            )
        with self.session(write=True) as db:
            self.period_in(db, period_id, lock=True)
            self.write_in(db, period_id, body)
            return self.snapshot_in(db, period_id)

    def delete(self, period_id, kind, record_id, expected_revision):
        with self.session(write=True) as db:
            self.period_in(db, period_id, lock=True)
            row = self.record_in(db, period_id, kind, record_id)
            if row is None:
                raise AcademicError(404, "record_not_found", "Academic record was not found.")
            if row["revision"] != expected_revision:
                raise AcademicError(
                    409,
                    "academic_version_conflict",
                    "This record changed; reload before deleting it.",
                )
            referenced = db.scalar(
                text("""
                SELECT 1 FROM classsync_academic.record_references
                WHERE tenant_id=:tenant AND owner_uid=:owner AND period_id=:period
                    AND target_kind=:kind AND target_id=:id LIMIT 1
            """),
                self.params(period_id, kind=kind, id=record_id),
            )
            if referenced:
                raise AcademicError(
                    409,
                    "record_in_use",
                    "Remove or update records that reference this item before deleting it.",
                )
            db.execute(
                text("""
                DELETE FROM classsync_academic.records
                WHERE tenant_id=:tenant AND owner_uid=:owner AND period_id=:period
                    AND kind=:kind AND id=:id AND revision=:revision
            """),
                self.params(period_id, kind=kind, id=record_id, revision=expected_revision),
            )
            self.bump(db, period_id)
            return self.snapshot_in(db, period_id)

    def roster_page(
        self, period_id, *, limit=20, offset=0, search="", year_level=None, section_id=None
    ):
        if not 1 <= limit <= 25 or not 0 <= offset <= 100000 or len(search) > 100:
            raise AcademicError(422, "invalid_roster_page", "Roster page filters are invalid.")
        with self.session() as db:
            period = self.period_in(db, period_id)
            rows = (
                db.execute(
                    text("""
                    WITH roster AS (
                        SELECT DISTINCT e.value->>'student_id' AS student_id,
                               offering.payload::jsonb->>'section_id' AS section_id
                        FROM classsync_academic.records rules
                        CROSS JOIN LATERAL jsonb_array_elements(
                            rules.payload::jsonb->'enrollments') e(value)
                        CROSS JOIN LATERAL jsonb_array_elements_text(
                            e.value->'offering_ids') offering_id(value)
                        JOIN classsync_academic.records offering
                          ON offering.tenant_id=rules.tenant_id
                         AND offering.owner_uid=rules.owner_uid
                         AND offering.period_id=rules.period_id
                         AND offering.kind='offerings' AND offering.id=offering_id.value
                        WHERE rules.tenant_id=:tenant AND rules.owner_uid=:owner
                          AND rules.period_id=:period AND rules.kind='constraints'
                    ), joined AS (
                        SELECT DISTINCT s.id AS student_id,p.display_name,s.registered_email,
                               s.enrollment_status,r.section_id,
                               (section.payload::jsonb->>'year_level')::integer AS year_level,
                               COALESCE(section.payload::jsonb->>'custom_label',
                                   program.payload::jsonb->>'acronym' || '-' ||
                                   (section.payload::jsonb->>'year_level') ||
                                   (section.payload::jsonb->>'section_letter')) AS section_label
                        FROM roster r
                        JOIN classsync_identity.students s
                          ON s.tenant_id=:tenant AND s.id=r.student_id
                        JOIN classsync_identity.people p
                          ON p.tenant_id=s.tenant_id AND p.id=s.person_id
                        JOIN classsync_academic.records section
                          ON section.tenant_id=:tenant AND section.owner_uid=:owner
                         AND section.period_id=:period AND section.kind='sections'
                         AND section.id=r.section_id
                        JOIN classsync_academic.records program
                          ON program.tenant_id=:tenant AND program.owner_uid=:owner
                         AND program.period_id=:period AND program.kind='programs'
                         AND program.id=section.payload::jsonb->>'program_id'
                    )
                    SELECT *,count(*) OVER() AS total FROM joined
                    WHERE (:query='' OR student_id ILIKE :query OR
                           display_name ILIKE :query OR registered_email ILIKE :query)
                      AND (CAST(:year AS integer) IS NULL
                           OR year_level=CAST(:year AS integer))
                      AND (CAST(:section AS text) IS NULL OR section_id=CAST(:section AS text))
                    ORDER BY year_level,section_label,student_id
                    LIMIT :limit OFFSET :offset
                """),
                    {
                        **self.keys,
                        "period": period_id,
                        "query": f"%{search.strip()}%" if search.strip() else "",
                        "year": year_level,
                        "section": section_id,
                        "limit": limit,
                        "offset": offset,
                    },
                )
                .mappings()
                .all()
            )
            section_rows = (
                db.execute(
                    text("""
                    SELECT r.id,(r.payload::jsonb->>'year_level')::integer AS year_level,
                           COALESCE((r.payload::jsonb->>'active')::boolean,true) AS active,
                           COALESCE(r.payload::jsonb->>'custom_label',
                               p.payload::jsonb->>'acronym' || '-' ||
                               (r.payload::jsonb->>'year_level') ||
                               (r.payload::jsonb->>'section_letter')) AS label
                    FROM classsync_academic.records r
                    JOIN classsync_academic.records p ON p.tenant_id=r.tenant_id
                     AND p.owner_uid=r.owner_uid AND p.period_id=r.period_id
                     AND p.kind='programs' AND p.id=r.payload::jsonb->>'program_id'
                    WHERE r.tenant_id=:tenant AND r.owner_uid=:owner AND r.period_id=:period
                      AND r.kind='sections' ORDER BY year_level,label
                """),
                    self.params(period_id),
                )
                .mappings()
                .all()
            )
            return {
                "items": [dict(row) for row in rows],
                "total": int(rows[0]["total"]) if rows else 0,
                "limit": limit,
                "offset": offset,
                "period_revision": period.revision,
                "sections": [dict(row) for row in section_rows],
            }

    def _roster_period_in(self, db, period_id, expected_period_revision):
        period = self.period_in(db, period_id, lock=True)
        if period.revision != expected_period_revision:
            raise AcademicError(
                409, "roster_version_conflict", "Academic data changed; reload the roster."
            )
        constraints = self.record_in(db, period_id, "constraints", "rules")
        if constraints is None:
            raise AcademicError(409, "roster_unavailable", "Period enrollment rules are missing.")
        record = self.envelope(constraints).record
        if not isinstance(record, AcademicConstraints):
            raise AcademicError(409, "roster_unavailable", "Period enrollment rules are invalid.")
        return period, constraints, record

    def _roster_used_in_other_period(self, db, period_id, student_id):
        return (
            db.scalar(
                text("""
            SELECT 1 FROM classsync_academic.records r
            WHERE r.tenant_id=:tenant AND r.owner_uid=:owner AND r.kind='constraints'
              AND r.period_id<>:period
              AND EXISTS (
                  SELECT 1 FROM jsonb_array_elements(r.payload::jsonb->'enrollments') e
                  WHERE e->>'student_id'=:student
              )
            LIMIT 1
        """),
                self.params(period_id, student=student_id),
            )
            is not None
        )

    def _roster_enrollment(self, db, period_id, student_id, body):
        section_row = self.record_in(db, period_id, "sections", body.section_id)
        section_record = self.envelope(section_row).record if section_row else None
        section = section_record if isinstance(section_record, AcademicSection) else None
        rows = (
            db.execute(
                text("""
                SELECT * FROM classsync_academic.records
                WHERE tenant_id=:tenant AND owner_uid=:owner AND period_id=:period
                  AND kind='offerings' AND payload::jsonb->>'section_id'=:section
                ORDER BY id
            """),
                self.params(period_id, section=body.section_id),
            )
            .mappings()
            .all()
        )
        offerings = [self.envelope(row).record for row in rows]
        return enrollment_for_section(student_id, body, section, offerings)

    def _set_cohort_binding(self, db, student_id, enrollment):
        exists = db.scalar(
            text("SELECT to_regclass('classsync_academic.cohort_bindings') IS NOT NULL")
        )
        if not exists:
            return
        db.execute(
            text("""
            SELECT classsync_academic.set_student_cohort_binding(
                :student,:cohort,:version)
        """),
            {
                **self.keys,
                "student": student_id,
                "cohort": enrollment.entry_cohort_year if enrollment else None,
                "version": enrollment.curriculum_version_id if enrollment else None,
            },
        )

    def _audit_roster_write(self, db, period_id, event_type, student_id, revision):
        db.execute(
            text("""
            SELECT classsync_scheduling.audit_student_roster_write(
                :period,:event,:student,:revision)
        """),
            self.params(
                period_id,
                event=event_type,
                student=student_id,
                revision=revision,
            ),
        )

    def create_roster_student(self, period_id, body: RosterStudentWrite):
        with self.session(write=True) as db:
            _, constraints_row, constraints = self._roster_period_in(
                db, period_id, body.expected_period_revision
            )
            if db.scalar(
                text(
                    "SELECT 1 FROM classsync_identity.students "
                    "WHERE tenant_id=:tenant AND id=:student"
                ),
                {**self.keys, "student": body.student_id},
            ):
                raise AcademicError(
                    409, "student_id_conflict", "That student ID already exists in this tenant."
                )
            if any(item.student_id == body.student_id for item in constraints.enrollments):
                raise AcademicError(
                    409,
                    "student_roster_duplicate",
                    "That student is already in this period roster.",
                )
            enrollment = self._roster_enrollment(db, period_id, body.student_id, body)
            db.execute(
                text("""
                SELECT classsync_identity.manage_student_roster(
                    'create',:student,NULL,:name,:email,:status)
            """),
                {
                    **self.keys,
                    "student": body.student_id,
                    "name": body.full_name,
                    "email": body.email,
                    "status": body.enrollment_status,
                },
            )
            next_record = constraints.model_copy(
                update={"enrollments": [*constraints.enrollments, enrollment]}
            )
            self.write_in(
                db,
                period_id,
                RecordWrite(expected_revision=constraints_row["revision"], record=next_record),
            )
            self.bump(db, period_id)
            self._audit_roster_write(
                db,
                period_id,
                "academic.student.created",
                body.student_id,
                constraints_row["revision"] + 1,
            )

    def update_roster_student(self, period_id, student_id, body: RosterStudentWrite):
        with self.session(write=True) as db:
            _, constraints_row, constraints = self._roster_period_in(
                db, period_id, body.expected_period_revision
            )
            identity = (
                db.execute(
                    text("""
                SELECT id,person_id FROM classsync_identity.students
                WHERE tenant_id=:tenant AND id=:student
            """),
                    {**self.keys, "student": student_id},
                )
                .mappings()
                .one_or_none()
            )
            if identity is None:
                raise AcademicError(404, "student_not_found", "Roster student was not found.")
            current_enrollment = next(
                (item for item in constraints.enrollments if item.student_id == student_id), None
            )
            if current_enrollment is None:
                raise AcademicError(
                    404, "student_not_in_period", "Student is not enrolled in this period."
                )
            used_elsewhere = self._roster_used_in_other_period(db, period_id, student_id)
            if body.student_id != student_id and used_elsewhere:
                raise AcademicError(
                    409,
                    "student_id_period_linked",
                    "This student ID is used in another period; resolve that roster record first.",
                )
            if body.student_id != student_id and db.scalar(
                text(
                    "SELECT 1 FROM classsync_identity.students "
                    "WHERE tenant_id=:tenant AND id=:student"
                ),
                {**self.keys, "student": body.student_id},
            ):
                raise AcademicError(
                    409, "student_id_conflict", "That student ID already exists in this tenant."
                )
            next_enrollment = self._roster_enrollment(db, period_id, body.student_id, body)
            if body.student_id != student_id:
                self._set_cohort_binding(db, student_id, None)
            other_enrollments = [
                item for item in constraints.enrollments if item.student_id != student_id
            ]
            next_record = constraints.model_copy(
                update={"enrollments": [*other_enrollments, next_enrollment]}
            )
            self.write_in(
                db,
                period_id,
                RecordWrite(expected_revision=constraints_row["revision"], record=next_record),
                # Cohort bindings are student-wide, so only change one when this
                # period is the student's sole enrollment.
                allow_cohort_change=not used_elsewhere,
            )
            db.execute(
                text("""
                SELECT classsync_identity.manage_student_roster(
                    'update',:student,:new_student,:name,:email,:status)
            """),
                {
                    **self.keys,
                    "student": student_id,
                    "new_student": body.student_id,
                    "name": body.full_name,
                    "email": body.email,
                    "status": body.enrollment_status,
                },
            )
            self.bump(db, period_id)
            self._audit_roster_write(
                db,
                period_id,
                "academic.student.updated",
                body.student_id,
                constraints_row["revision"] + 1,
            )

    def delete_roster_student(self, period_id, student_id, expected_period_revision):
        with self.session(write=True) as db:
            _, constraints_row, constraints = self._roster_period_in(
                db, period_id, expected_period_revision
            )
            if (
                db.scalar(
                    text(
                        "SELECT 1 FROM classsync_identity.students "
                        "WHERE tenant_id=:tenant AND id=:student"
                    ),
                    {**self.keys, "student": student_id},
                )
                is None
            ):
                raise AcademicError(404, "student_not_found", "Roster student was not found.")
            if not any(item.student_id == student_id for item in constraints.enrollments):
                raise AcademicError(
                    404, "student_not_in_period", "Student is not enrolled in this period."
                )
            used_elsewhere = self._roster_used_in_other_period(db, period_id, student_id)
            if not used_elsewhere:
                self._set_cohort_binding(db, student_id, None)
            next_record = constraints.model_copy(
                update={
                    "enrollments": [
                        item for item in constraints.enrollments if item.student_id != student_id
                    ]
                }
            )
            self.write_in(
                db,
                period_id,
                RecordWrite(expected_revision=constraints_row["revision"], record=next_record),
            )
            if not used_elsewhere:
                db.execute(
                    text("""
                    SELECT classsync_identity.manage_student_roster(
                        'delete',:student,NULL,NULL,NULL,NULL)
                """),
                    {**self.keys, "student": student_id},
                )
            self.bump(db, period_id)
            self._audit_roster_write(
                db,
                period_id,
                "academic.student.deleted",
                student_id,
                constraints_row["revision"] + 1,
            )

    def record_in(self, db, period_id, kind, record_id):
        return (
            db.execute(
                text("""
            SELECT * FROM classsync_academic.records
            WHERE tenant_id=:tenant AND owner_uid=:owner AND period_id=:period
                AND kind=:kind AND id=:id
        """),
                self.params(period_id, kind=kind, id=record_id),
            )
            .mappings()
            .one_or_none()
        )

    def write_in(self, db, period_id, body, *, allow_cohort_change=False):
        record = body.record
        data_mode = db.scalar(
            text("""
                SELECT data_mode FROM classsync_academic.period_metadata
                WHERE tenant_id=:tenant AND owner_uid=:owner AND id=:period
            """),
            self.params(period_id),
        )
        if data_mode not in {"institutional", "synthetic-review"}:
            raise AcademicError(404, "period_not_found", "Academic period does not exist.")
        validate_period_data_mode(record, data_mode)
        existing = self.record_in(db, period_id, record.kind, record.id)
        revision = existing["revision"] if existing else 0
        if body.expected_revision != revision:
            raise AcademicError(
                409,
                "academic_version_conflict",
                "This record changed. Reload before saving; the newer data was not overwritten.",
            )

        def lookup(kind, identity):
            row = self.record_in(db, period_id, kind, identity)
            return self.envelope(row).record if row else None

        validate_record(record, period_id, lookup, allow_cohort_change=allow_cohort_change)
        if record.kind == "constraints":
            has_registry = (
                db.scalar(
                    text("SELECT to_regclass('classsync_academic.cohort_bindings') IS NOT NULL")
                )
                if any(not e.curriculum_version_id for e in record.enrollments)
                else True
            )
            for enrollment in record.enrollments:
                if not enrollment.curriculum_version_id:
                    existing_binding = has_registry and db.scalar(
                        text("""
                        SELECT 1 FROM classsync_academic.cohort_bindings
                        WHERE tenant_id=:tenant AND owner_uid=:owner AND student_id=:student
                    """),
                        {**self.keys, "student": enrollment.student_id},
                    )
                    if existing_binding and allow_cohort_change:
                        self._set_cohort_binding(db, enrollment.student_id, enrollment)
                    elif existing_binding:
                        raise AcademicError(
                            409,
                            "cohort_immutable",
                            "An assigned student curriculum cannot be cleared.",
                        )
                    continue
                binding = {
                    **self.keys,
                    "student": enrollment.student_id,
                    "cohort": enrollment.entry_cohort_year,
                    "version": enrollment.curriculum_version_id,
                }
                db.execute(
                    text("""
                    INSERT INTO classsync_academic.cohort_bindings
                        (tenant_id,owner_uid,student_id,entry_cohort_year,curriculum_version_id)
                    VALUES (:tenant,:owner,:student,:cohort,:version)
                    ON CONFLICT DO NOTHING
                """),
                    binding,
                )
                existing_binding = db.execute(
                    text("""
                    SELECT entry_cohort_year,curriculum_version_id
                    FROM classsync_academic.cohort_bindings
                    WHERE tenant_id=:tenant AND owner_uid=:owner AND student_id=:student
                """),
                    binding,
                ).one()
                if tuple(existing_binding) != (
                    enrollment.entry_cohort_year,
                    enrollment.curriculum_version_id,
                ):
                    if allow_cohort_change:
                        self._set_cohort_binding(db, enrollment.student_id, enrollment)
                    else:
                        raise AcademicError(
                            409,
                            "cohort_immutable",
                            "Student curriculum binding survives term/enrollment changes.",
                        )
        payload = encode(record.model_dump(mode="json"))
        params = self.params(
            period_id,
            kind=record.kind,
            id=record.id,
            revision=revision + 1,
            label=unique_label(record),
            updated=timestamp(),
            payload=payload,
            checksum=checksum(payload),
        )
        if existing:
            db.execute(
                text("""
                DELETE FROM classsync_academic.record_references
                WHERE tenant_id=:tenant AND owner_uid=:owner AND period_id=:period
                    AND source_kind=:kind AND source_id=:id
            """),
                params,
            )
            changed = db.execute(
                text("""
                UPDATE classsync_academic.records SET revision=:revision,unique_label=:label,
                    updated_at=:updated,updated_by=:owner,payload=:payload,checksum=:checksum
                WHERE tenant_id=:tenant AND owner_uid=:owner AND period_id=:period
                    AND kind=:kind AND id=:id AND revision=:expected
            """),
                {**params, "expected": revision},
            )
            if changed.rowcount != 1:
                raise AcademicError(
                    409,
                    "academic_version_conflict",
                    "Academic data changed; reload before retrying.",
                )
        else:
            db.execute(
                text("""
                INSERT INTO classsync_academic.records
                  (tenant_id,owner_uid,period_id,kind,id,revision,unique_label,
                   updated_at,updated_by,payload,checksum)
                VALUES (:tenant,:owner,:period,:kind,:id,:revision,:label,
                        :updated,:owner,:payload,:checksum)
            """),
                params,
            )
        for kind, identity in references(record):
            db.execute(
                text("""
                INSERT INTO classsync_academic.record_references
                  (tenant_id,owner_uid,period_id,source_kind,source_id,target_kind,target_id)
                VALUES (:tenant,:owner,:period,:kind,:id,:target_kind,:target_id)
            """),
                {**params, "target_kind": kind, "target_id": identity},
            )
        self.bump(db, period_id)

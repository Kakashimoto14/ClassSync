"""Bulk roster operations and period lifecycle for the PostgreSQL academic repository.

Mixed into `PostgresAcademicRepository`, which supplies the verified session, scoped keys
and the record writer. Each operation is one transaction.
"""

import json
from uuid import uuid4

from classync_contracts.academic import AcademicConstraints, RecordWrite
from classync_contracts.calendar import AcademicCalendar
from sqlalchemy import text

from .record_rules import AcademicError, checksum, encode, timestamp
from .roster_import import parse_csv, roster_email, rows_hash, validate_rows
from .student_roster import enrollment_for_section


class RosterOperations:
    # -- bulk status -------------------------------------------------------

    def bulk_roster_status(self, period_id, body):
        with self.session(write=True) as db:
            period, constraints_row, constraints = self._roster_period_in(
                db, period_id, body.expected_period_revision
            )
            enrolled = {item.student_id for item in constraints.enrollments}
            found = {
                row["id"]: row
                for row in db.execute(
                    text("""
                    SELECT s.id,p.display_name,s.registered_email,s.enrollment_status
                    FROM classsync_identity.students s
                    JOIN classsync_identity.people p
                      ON p.tenant_id=s.tenant_id AND p.id=s.person_id
                    WHERE s.tenant_id=:tenant AND s.id=ANY(CAST(:ids AS text[]))
                """),
                    {**self.keys, "ids": body.student_ids},
                ).mappings()
            }
            missing = [
                item for item in body.student_ids if item not in enrolled or item not in found
            ]
            if missing:
                raise AcademicError(
                    404,
                    "student_not_in_period",
                    f"Not enrolled in this period: {', '.join(missing[:10])}. Nothing changed.",
                )
            changing = [
                found[item]
                for item in body.student_ids
                if found[item]["enrollment_status"] != body.enrollment_status
            ]
            incomplete = [
                row["id"]
                for row in changing
                if not (row["display_name"] or "").strip()
                or roster_email(row["registered_email"]) != row["registered_email"]
            ]
            if incomplete:
                raise AcademicError(
                    422,
                    "roster_identity_incomplete",
                    "Add a name and a valid email first: "
                    f"{', '.join(incomplete[:10])}. Nothing changed.",
                )
            revision = period.revision
            if changing:
                payload = json.dumps(
                    [
                        {
                            "student_id": row["id"],
                            "full_name": row["display_name"],
                            "email": row["registered_email"],
                        }
                        for row in changing
                    ]
                )
                db.execute(
                    text("""
                    SELECT classsync_identity.manage_student_roster(
                        'update',r.student_id,r.student_id,r.full_name,r.email,:status)
                    FROM jsonb_to_recordset(CAST(:rows AS jsonb))
                        AS r(student_id text,full_name text,email text)
                """),
                    {"rows": payload, "status": body.enrollment_status},
                )
                self.bump(db, period_id)
                revision += 1
                db.execute(
                    text("""
                    SELECT classsync_scheduling.audit_student_roster_write(
                        :period,'academic.student.updated',student,:revision)
                    FROM unnest(CAST(:ids AS text[])) AS student
                """),
                    {
                        "period": period_id,
                        "revision": constraints_row["revision"],
                        "ids": [row["id"] for row in changing],
                    },
                )
            return {
                "updated": len(changing),
                "skipped": len(body.student_ids) - len(changing),
                "period_revision": revision,
            }

    # -- continuing students ------------------------------------------------

    def _university_students(self, db, period_id, ids, emails=()):
        """Tenant records matching these IDs or emails, keyed by student ID.

        `in_own_period` means another of this Administrator's periods enrolls the student.
        Only then can a later removal from this period keep the shared record.
        """
        rows = db.execute(
            text("""
            SELECT s.id,p.display_name,lower(s.registered_email) AS email,s.enrollment_status
            FROM classsync_identity.students s
            JOIN classsync_identity.people p
              ON p.tenant_id=s.tenant_id AND p.id=s.person_id
            WHERE s.tenant_id=:tenant
              AND (s.id=ANY(CAST(:ids AS text[]))
                   OR lower(s.registered_email)=ANY(CAST(:emails AS text[])))
        """),
            {**self.keys, "ids": list(ids), "emails": list(emails)},
        ).mappings().all()
        found = {
            row["id"]: {**row, "in_own_period": False, "binding": None} for row in rows
        }
        if not found:
            return found
        params = self.params(period_id, ids=list(found))
        for identity in db.scalars(
            text("""
            SELECT DISTINCT e.value->>'student_id'
            FROM classsync_academic.records r
            CROSS JOIN LATERAL jsonb_array_elements(r.payload::jsonb->'enrollments') e(value)
            WHERE r.tenant_id=:tenant AND r.owner_uid=:owner AND r.kind='constraints'
              AND r.period_id<>:period AND e.value->>'student_id'=ANY(CAST(:ids AS text[]))
        """),
            params,
        ):
            found[identity]["in_own_period"] = True
        if db.scalar(text("SELECT to_regclass('classsync_academic.cohort_bindings') IS NOT NULL")):
            for row in db.execute(
                text("""
                SELECT student_id,entry_cohort_year,curriculum_version_id
                FROM classsync_academic.cohort_bindings
                WHERE tenant_id=:tenant AND owner_uid=:owner
                  AND student_id=ANY(CAST(:ids AS text[]))
            """),
                params,
            ).mappings():
                found[row["student_id"]]["binding"] = (
                    row["entry_cohort_year"],
                    row["curriculum_version_id"],
                )
        return found

    # -- CSV import --------------------------------------------------------

    def _import_sections(self, db, period_id):
        records = [entry.record for entry in self.snapshot_in(db, period_id).records]
        programs = {r.id: r for r in records if r.kind == "programs"}
        sections = {}
        for record in records:
            if record.kind != "sections" or not record.active:
                continue
            program = programs.get(record.program_id)
            label = record.custom_label or (
                f"{program.acronym if program else ''}-{record.year_level}{record.section_letter}"
            )
            value = {
                "id": record.id,
                "label": label,
                "record": record,
                "offerings": [
                    item
                    for item in records
                    if item.kind == "offerings" and item.section_id == record.id and item.active
                ],
            }
            sections[label.casefold()] = value
            sections[record.id.casefold()] = value
        return sections

    def _checked_import(self, db, period_id, content):
        rows = parse_csv(content)
        sections = self._import_sections(db, period_id)
        found = self._university_students(
            db,
            period_id,
            [row["student_id"] for row in rows],
            [row["email"].lower() for row in rows],
        )
        constraints = self.record_in(db, period_id, "constraints", "rules")
        enrolled = (
            {item.student_id for item in self.envelope(constraints).record.enrollments}
            if constraints
            else set()
        )
        checked = validate_rows(
            rows,
            sections,
            enrolled=enrolled,
            existing=found,
            existing_emails={item["email"] for item in found.values() if item["email"]},
        )
        return checked, sections

    def preview_roster_import(self, period_id, body):
        with self.session() as db:
            period = self.period_in(db, period_id)
            checked, _ = self._checked_import(db, period_id, body.csv)
        invalid = sum(bool(row["errors"]) for row in checked)
        return {
            "rows": checked,
            "total": len(checked),
            "invalid": invalid,
            "create_new": sum(row["action"] == "create_new" for row in checked),
            "enroll_existing": sum(row["action"] == "enroll_existing" for row in checked),
            "rows_hash": None if invalid else rows_hash(period_id, checked),
            "period_revision": period.revision,
        }

    def commit_roster_import(self, period_id, body):
        with self.session(write=True) as db:
            _, constraints_row, constraints = self._roster_period_in(
                db, period_id, body.expected_period_revision
            )
            checked, sections = self._checked_import(db, period_id, body.csv)
            if any(row["errors"] for row in checked):
                raise AcademicError(
                    409,
                    "roster_import_changed",
                    "Some rows are no longer valid. Preview the file again. Nothing was imported.",
                )
            if rows_hash(period_id, checked) != body.rows_hash:
                raise AcademicError(
                    409,
                    "roster_import_changed",
                    "The rows differ from the preview. Preview again. Nothing was imported.",
                )
            enrollments = []
            for row in checked:
                section = sections[row["section_id"].casefold()]
                enrollments.append(
                    enrollment_for_section(
                        row["student_id"],
                        _SectionChoice(section["record"].year_level),
                        section["record"],
                        section["offerings"],
                    )
                )
            if len(constraints.enrollments) + len(enrollments) > 10000:
                raise AcademicError(
                    422, "roster_capacity", "A period roster holds at most 10,000 students."
                )
            # Continuing students keep their university record exactly as it is.
            new_students = [row for row in checked if row["action"] == "create_new"]
            db.execute(
                text("""
                SELECT classsync_identity.manage_student_roster(
                    'create',r.student_id,NULL,r.full_name,r.email,r.enrollment_status)
                FROM jsonb_to_recordset(CAST(:rows AS jsonb))
                    AS r(student_id text,full_name text,email text,enrollment_status text)
            """),
                {"rows": json.dumps(new_students)},
            )
            next_record = constraints.model_copy(
                update={"enrollments": [*constraints.enrollments, *enrollments]}
            )
            self.write_in(
                db,
                period_id,
                RecordWrite(expected_revision=constraints_row["revision"], record=next_record),
            )
            self.bump(db, period_id)
            revision = self.period_in(db, period_id).revision
            db.execute(
                text("SELECT classsync_scheduling.audit_roster_import(:period,:revision)"),
                {"period": period_id, "revision": revision},
            )
            return {
                "imported": len(checked),
                "created": len(new_students),
                "enrolled_existing": len(checked) - len(new_students),
                "period_revision": revision,
            }

    # -- period lifecycle --------------------------------------------------

    def clone_period(self, period_id, body):
        """Copy structure, rules and a calendar shell. No enrollments or locked classes."""
        new_id = str(uuid4())
        with self.session(write=True) as db:
            self.period_in(db, period_id, lock=True)
            # Decoding every source record verifies its checksum before anything is copied.
            source = self.snapshot_in(db, period_id)
            keys = {**self.keys, "source": period_id, "period": new_id, "updated": timestamp()}
            db.execute(
                text("""
                INSERT INTO classsync_academic.period_metadata
                    (tenant_id,owner_uid,id,title,data_mode,cloned_from)
                SELECT tenant_id,owner_uid,:period,:title,data_mode,id
                FROM classsync_academic.period_metadata
                WHERE tenant_id=:tenant AND owner_uid=:owner AND id=:source
            """),
                {**keys, "title": body.title},
            )
            calendar = source.period.calendar
            if calendar:
                shell = AcademicCalendar(
                    academic_year=calendar.academic_year,
                    semester=calendar.semester,
                    effective_start=calendar.effective_start,
                    effective_end=calendar.effective_end,
                    instructional_days=calendar.instructional_days,
                )
                self.calendar_in(db, new_id, shell)
            db.execute(
                text("""
                INSERT INTO classsync_academic.records
                    (tenant_id,owner_uid,period_id,kind,id,revision,unique_label,
                     updated_at,updated_by,payload,checksum)
                SELECT tenant_id,owner_uid,:period,kind,id,1,unique_label,
                       CAST(:updated AS timestamptz),owner_uid,payload,checksum
                FROM classsync_academic.records
                WHERE tenant_id=:tenant AND owner_uid=:owner AND period_id=:source
                  AND kind NOT IN ('sections','constraints')
            """),
                keys,
            )
            for entry in source.records:
                record = entry.record
                if record.kind == "sections":
                    record = record.model_copy(update={"period_id": new_id})
                elif isinstance(record, AcademicConstraints):
                    record = record.model_copy(
                        update={"enrollments": [], "locked_assignments": []}
                    )
                else:
                    continue
                payload = encode(record.model_dump(mode="json"))
                db.execute(
                    text("""
                    INSERT INTO classsync_academic.records
                        (tenant_id,owner_uid,period_id,kind,id,revision,unique_label,
                         updated_at,updated_by,payload,checksum)
                    SELECT tenant_id,owner_uid,:period,kind,id,1,unique_label,
                           CAST(:updated AS timestamptz),owner_uid,:payload,:checksum
                    FROM classsync_academic.records
                    WHERE tenant_id=:tenant AND owner_uid=:owner AND period_id=:source
                      AND kind=:kind AND id=:id
                """),
                    {
                        **keys,
                        "kind": record.kind,
                        "id": record.id,
                        "payload": payload,
                        "checksum": checksum(payload),
                    },
                )
            # Constraint references come only from enrollments and locks, which are dropped.
            db.execute(
                text("""
                INSERT INTO classsync_academic.record_references
                    (tenant_id,owner_uid,period_id,source_kind,source_id,target_kind,target_id)
                SELECT tenant_id,owner_uid,:period,source_kind,source_id,target_kind,target_id
                FROM classsync_academic.record_references
                WHERE tenant_id=:tenant AND owner_uid=:owner AND period_id=:source
                  AND source_kind<>'constraints'
            """),
                keys,
            )
            return self.snapshot_in(db, new_id)

    def archive_period(self, period_id, body):
        with self.session(write=True) as db:
            period = self.period_in(db, period_id, lock=True)
            if period.archived_at:
                raise AcademicError(409, "period_archived", "This period is already archived.")
            if period.revision != body.expected_revision:
                raise AcademicError(
                    409,
                    "academic_version_conflict",
                    "Academic data changed; reload before archiving.",
                )
            db.execute(
                text("""
                UPDATE classsync_academic.period_metadata
                SET archived_at=transaction_timestamp(),archived_by=:owner,revision=revision+1
                WHERE tenant_id=:tenant AND owner_uid=:owner AND id=:period
            """),
                self.params(period_id),
            )
            return self.snapshot_in(db, period_id)


class _SectionChoice:
    """The only part of a roster form that `enrollment_for_section` reads."""

    def __init__(self, year_level):
        self.year_level = year_level

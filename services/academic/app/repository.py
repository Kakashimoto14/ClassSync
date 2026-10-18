"""Period-scoped academic source records; no schedule output or publishing."""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from classync_contracts import scheduling
from classync_contracts.academic import (
    AcademicConstraints,
    AcademicPeriod,
    AcademicRecord,
    AcademicResource,
    AcademicSnapshot,
    PeriodCreate,
    RecordEnvelope,
    RecordWrite,
)
from pydantic import TypeAdapter, ValidationError

adapter = TypeAdapter(AcademicRecord)


class AcademicError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code = status, code


def timestamp():
    return datetime.now(UTC).isoformat()


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def checksum(value):
    return hashlib.sha256(value.encode()).hexdigest()


def catalog_data():
    root = Path(scheduling.__file__).parent / "catalogs"
    return (
        json.loads((root / "programs.json").read_text()),
        json.loads((root / "cdm-spaces.json").read_text()),
    )


def references(record):
    refs = []
    if record.kind == "subjects":
        refs += [("programs", i) for i in record.program_ids]
    elif record.kind == "sections":
        refs.append(("programs", record.program_id))
    elif record.kind == "faculty":
        refs += [("subjects", i) for i in record.subject_ids]
    elif record.kind == "resources":
        refs += [("programs", i) for i in record.allowed_program_ids or []]
    elif record.kind == "offerings":
        refs += [("subjects", record.subject_id), ("sections", record.section_id)]
        refs += [("faculty", i) for i in record.teacher_ids]
        refs += [("resources", i) for i in record.room_ids]
    elif record.kind == "constraints":
        for lock in record.locked_assignments:
            refs += [
                ("offerings", lock.offering_id),
                ("sections", lock.section_id),
                ("faculty", lock.teacher_id),
                ("resources", lock.room_id),
                ("subjects", lock.subject_id),
            ]
        for student in record.enrollments:
            refs += [("offerings", i) for i in student.offering_ids]
    return set(refs)


def unique_label(record):
    if record.kind == "programs":
        return record.acronym.strip().casefold()
    if record.kind == "subjects":
        return record.code.strip().casefold()
    if record.kind == "sections":
        return encode(
            [record.program_id, record.custom_label or [record.year_level, record.section_letter]]
        )
    if record.kind == "offerings":
        return encode([record.subject_id, record.section_id])
    if record.kind == "resources":
        return encode([record.building.strip().casefold(), record.name.strip().casefold()])
    return record.id


class AcademicRepository:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connection(self, write=False):
        db = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db
            db.commit()
        except sqlite3.IntegrityError as error:
            if "faculty_institutional_identity" in str(error):
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
        except (sqlite3.Error, OSError) as error:
            raise AcademicError(
                503,
                "academic_storage_unavailable",
                "Academic storage is unavailable. No save was confirmed; retry safely.",
            ) from error
        finally:
            if db:
                if db.in_transaction:
                    db.rollback()
                db.close()

    def migrate(self):
        with self.connection(True) as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2, 3):
                raise AcademicError(
                    409,
                    "academic_schema",
                    "Unsupported academic database version. No data was reset.",
                )
            if version == 0:
                text = (Path(__file__).parents[1] / "migrations/001_academic.sql").read_text()
                statement = ""
                for line in text.splitlines(keepends=True):
                    statement += line
                    if sqlite3.complete_statement(statement):
                        db.execute(statement)
                        statement = ""
                db.execute("PRAGMA user_version=1")
            if version < 2:
                sql = (
                    Path(__file__).parents[1] / "migrations/002_faculty_identity.sql"
                ).read_text()
                db.execute(sql)
                db.execute("PRAGMA user_version=2")
            if version < 3:
                db.execute(
                    "CREATE TABLE academic_calendars (scope TEXT, owner TEXT, period_id TEXT, "
                    "payload TEXT NOT NULL, PRIMARY KEY(scope,owner,period_id), "
                    "FOREIGN KEY(scope,owner,period_id) "
                    "REFERENCES academic_periods(scope,owner,id))"
                )
                db.execute("PRAGMA user_version=3")
            if (
                db.execute("PRAGMA quick_check").fetchone()[0] != "ok"
                or db.execute("PRAGMA foreign_key_check").fetchone()
            ):
                raise AcademicError(
                    503, "academic_integrity", "Academic database integrity check failed."
                )

    def period(self, db, scope, owner, period_id):
        row = db.execute(
            "SELECT * FROM academic_periods WHERE scope=? AND owner=? AND id=?",
            (scope, owner, period_id),
        ).fetchone()
        if not row:
            raise AcademicError(
                404,
                "period_not_found",
                "This academic period does not exist in your permitted scope.",
            )
        return AcademicPeriod(
            id=row["id"],
            title=row["title"],
            revision=row["revision"],
            created_at=row["created_at"],
            source="development-entered" if scope == "sandbox" else "institutional",
            calendar=self.calendar(db, scope, owner, period_id),
        )

    def calendar(self, db, scope, owner, period_id):
        row = db.execute(
            "SELECT payload FROM academic_calendars WHERE scope=? AND owner=? AND period_id=?",
            (scope, owner, period_id),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def periods(self, scope, owner):
        with self.connection() as db:
            ids = db.execute(
                "SELECT id FROM academic_periods WHERE scope=? AND owner=? "
                "ORDER BY created_at DESC,id",
                (scope, owner),
            ).fetchall()
            return [self.period(db, scope, owner, row["id"]) for row in ids]

    def envelope(self, row):
        try:
            if checksum(row["payload"]) != row["checksum"]:
                raise ValueError("Checksum mismatch")
            record = adapter.validate_python(json.loads(row["payload"]))
            if record.id != row["id"] or record.kind != row["kind"]:
                raise ValueError("Identity mismatch")
            return RecordEnvelope(
                record=record,
                revision=row["revision"],
                updated_at=row["updated_at"],
                updated_by=row["updated_by"],
            )
        except (ValueError, ValidationError) as error:
            raise AcademicError(
                409,
                "academic_snapshot_integrity",
                "Stored academic record is corrupt or incompatible; no data was substituted.",
            ) from error

    def snapshot(self, scope, owner, period_id):
        with self.connection() as db:
            period = self.period(db, scope, owner, period_id)
            rows = db.execute(
                "SELECT * FROM academic_records WHERE scope=? AND owner=? AND period_id=? "
                "ORDER BY kind,id",
                (scope, owner, period_id),
            ).fetchall()
            return AcademicSnapshot(period=period, records=[self.envelope(row) for row in rows])

    def create_period(self, body: PeriodCreate, scope, owner):
        period_id = str(uuid4())
        with self.connection(True) as db:
            db.execute(
                "INSERT INTO academic_periods VALUES (?,?,?,?,1,?)",
                (scope, owner, period_id, body.title, timestamp()),
            )
            if body.calendar:
                db.execute(
                    "INSERT INTO academic_calendars VALUES (?,?,?,?)",
                    (scope, owner, period_id, body.calendar.model_dump_json()),
                )
            records = [AcademicConstraints()]
            if body.include_cdm_catalog:
                programs, rooms = catalog_data()
                records = (
                    [adapter.validate_python({**p, "kind": "programs"}) for p in programs]
                    + [
                        AcademicResource(
                            **{
                                k: v
                                for k, v in room.items()
                                if k not in {"aliasUnconfirmed", "alias"}
                            },
                            source="cdm-provisional",
                            alias=room.get("alias"),
                            alias_unconfirmed=room.get("aliasUnconfirmed", False),
                        )
                        for room in rooms
                    ]
                    + records
                )
            for record in records:
                self.write_in(
                    db, scope, owner, period_id, RecordWrite(expected_revision=0, record=record)
                )
        return self.snapshot(scope, owner, period_id)

    def save(self, scope, owner, period_id, kind, record_id, body):
        if body.record.kind != kind or body.record.id != record_id:
            raise AcademicError(
                422, "record_identity", "The record identity must match its destination."
            )
        with self.connection(True) as db:
            self.period(db, scope, owner, period_id)
            self.write_in(db, scope, owner, period_id, body)
        return self.snapshot(scope, owner, period_id)

    def save_calendar(self, scope, owner, period_id, body):
        if body.calendar.published_version:
            raise AcademicError(
                422,
                "publication_version",
                "Publication versions are assigned by the scheduling service.",
            )
        with self.connection(True) as db:
            period = self.period(db, scope, owner, period_id)
            if period.revision != body.expected_revision:
                raise AcademicError(
                    409,
                    "calendar_version_conflict",
                    "Academic data changed; reload before saving calendar dates.",
                )
            db.execute(
                "INSERT INTO academic_calendars VALUES (?,?,?,?) "
                "ON CONFLICT(scope,owner,period_id) DO UPDATE SET payload=excluded.payload",
                (scope, owner, period_id, body.calendar.model_dump_json()),
            )
            db.execute(
                "UPDATE academic_periods SET revision=revision+1 "
                "WHERE scope=? AND owner=? AND id=?",
                (scope, owner, period_id),
            )
        return self.snapshot(scope, owner, period_id)

    def write_in(self, db, scope, owner, period_id, body):
        record = body.record
        key = (scope, owner, period_id, record.kind, record.id)
        existing = db.execute(
            "SELECT * FROM academic_records WHERE scope=? AND owner=? AND period_id=? "
            "AND kind=? AND id=?",
            key,
        ).fetchone()
        revision = existing["revision"] if existing else 0
        if body.expected_revision != revision:
            raise AcademicError(
                409,
                "academic_version_conflict",
                "This record changed. Reload before saving; the newer data was not overwritten.",
            )
        for field in ("name", "acronym", "code", "building"):
            if hasattr(record, field) and not getattr(record, field).strip():
                raise AcademicError(422, "required_field", f"Enter {field}.")
        for field in ("program_ids", "subject_ids", "teacher_ids", "room_ids"):
            if hasattr(record, field):
                values = getattr(record, field)
                if len(values) != len(set(values)):
                    raise AcademicError(
                        422, "duplicate_reference", f"Select each {field} reference once."
                    )
        for target_kind, target_id in references(record):
            if not db.execute(
                "SELECT 1 FROM academic_records WHERE scope=? AND owner=? AND period_id=? "
                "AND kind=? AND id=?",
                (scope, owner, period_id, target_kind, target_id),
            ).fetchone():
                raise AcademicError(
                    422,
                    "missing_reference",
                    f"Unknown {target_kind} reference: {target_id}. "
                    "Save that record in this period first.",
                )
        if record.kind == "sections":
            program_row = db.execute(
                "SELECT * FROM academic_records WHERE scope=? AND owner=? AND period_id=? "
                "AND kind='programs' AND id=?",
                (scope, owner, period_id, record.program_id),
            ).fetchone()
            program = self.envelope(program_row).record
            if record.period_id != period_id:
                raise AcademicError(
                    422, "period_reference", "Section belongs to a different academic period."
                )
            if program.section_policy == "degree" and (
                record.year_level is None or not record.section_letter
            ):
                raise AcademicError(
                    422,
                    "section_naming",
                    "Degree sections require structured year level and section identifier.",
                )
            if program.section_policy == "custom" and not record.custom_label:
                raise AcademicError(
                    422, "section_naming", "This program requires its own custom section label."
                )
            if (
                program.allowed_year_levels is not None
                and record.year_level not in program.allowed_year_levels
            ):
                raise AcademicError(
                    422, "section_naming", "Year level is outside this program's configured policy."
                )
        if record.kind == "offerings":

            def related(kind, identity):
                row = db.execute(
                    "SELECT * FROM academic_records WHERE scope=? AND owner=? AND period_id=? "
                    "AND kind=? AND id=?",
                    (scope, owner, period_id, kind, identity),
                ).fetchone()
                return self.envelope(row).record

            subject = related("subjects", record.subject_id)
            section = related("sections", record.section_id)
            if subject.program_ids and section.program_id not in subject.program_ids:
                raise AcademicError(
                    422,
                    "curriculum_association",
                    "The subject is not associated with this section's program.",
                )
            for teacher_id in record.teacher_ids:
                if record.subject_id not in related("faculty", teacher_id).subject_ids:
                    raise AcademicError(
                        422,
                        "faculty_eligibility",
                        "Selected faculty is not eligible for this subject.",
                    )
            minutes = record.weekly_minutes_override or subject.required_weekly_minutes
            patterns = (
                record.patterns_override
                if record.patterns_override is not None
                else subject.patterns
            )
            if minutes is not None and any(sum(p.durations) != minutes for p in patterns):
                raise AcademicError(
                    422,
                    "weekly_minutes",
                    "Offering patterns must total the required weekly minutes.",
                )
        if record.kind == "resources" and record.id.startswith("cdm-"):
            room = next((r for r in catalog_data()[1] if r["id"] == record.id), None)
            if (
                room is None
                or any(
                    getattr(record, k) != room.get(k)
                    for k in ("name", "building", "floor", "location", "alias")
                )
                or record.alias_unconfirmed != room.get("aliasUnconfirmed", False)
                or record.source != "cdm-provisional"
            ):
                raise AcademicError(
                    422,
                    "cdm_identity",
                    "Preserve the supplied CdM resource ID, location and provisional label.",
                )
        value = encode(record.model_dump(mode="json"))
        if existing:
            db.execute(
                "DELETE FROM academic_references WHERE scope=? AND owner=? AND period_id=? "
                "AND source_kind=? AND source_id=?",
                key,
            )
            db.execute(
                "UPDATE academic_records SET revision=?, unique_label=?, updated_at=?, "
                "updated_by=?, payload=?, checksum=? WHERE scope=? AND owner=? "
                "AND period_id=? AND kind=? AND id=?",
                (
                    revision + 1,
                    unique_label(record),
                    timestamp(),
                    owner,
                    value,
                    checksum(value),
                    *key,
                ),
            )
        else:
            db.execute(
                "INSERT INTO academic_records VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    *key[:4],
                    record.id,
                    1,
                    unique_label(record),
                    timestamp(),
                    owner,
                    value,
                    checksum(value),
                ),
            )
        for target_kind, target_id in references(record):
            db.execute(
                "INSERT INTO academic_references VALUES (?,?,?,?,?,?,?)",
                (*key, target_kind, target_id),
            )
        db.execute(
            "UPDATE academic_periods SET revision=revision+1 WHERE scope=? AND owner=? AND id=?",
            (scope, owner, period_id),
        )

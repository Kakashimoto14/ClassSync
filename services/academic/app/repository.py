"""Period-scoped academic source records; no schedule output or publishing."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from classync_contracts.academic import (
    AcademicPeriod,
    AcademicSnapshot,
    PeriodCreate,
    RecordEnvelope,
    RecordWrite,
)
from pydantic import ValidationError

from .record_rules import (
    AcademicError as AcademicError,
)
from .record_rules import (
    adapter as adapter,
)
from .record_rules import (
    catalog_data as catalog_data,
)
from .record_rules import (
    checksum,
    encode,
    initial_records,
    references,
    unique_label,
    validate_calendar,
    validate_record,
)
from .record_rules import (
    timestamp as timestamp,
)


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
        validate_calendar(body.calendar)
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
            records = initial_records(body.include_cdm_catalog)
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
        validate_calendar(body.calendar)
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

        def lookup(kind, identity):
            row = db.execute(
                "SELECT * FROM academic_records WHERE scope=? AND owner=? AND period_id=? "
                "AND kind=? AND id=?",
                (scope, owner, period_id, kind, identity),
            ).fetchone()
            return self.envelope(row).record if row else None

        validate_record(record, period_id, lookup)
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

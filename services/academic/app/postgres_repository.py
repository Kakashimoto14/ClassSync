"""Complete owner-scoped academic snapshots on explicit PostgreSQL configuration.

Not installed as the service default. No implicit migration, credentials, catalog
fallback or original-data cutover. Shared record_rules remains the business rule
source for both local SQLite and this adapter.
"""

import json
from contextlib import contextmanager
from uuid import uuid4

from classync_contracts.academic import AcademicPeriod, AcademicSnapshot, RecordWrite
from classync_contracts.calendar import AcademicCalendar
from classync_contracts.identity import (
    MembershipAuthorizationError,
    MembershipErrorCode,
    VerifiedPrincipal,
)
from classync_persistence.academic_periods import PostgresAcademicPeriods, utc_timestamp
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
    validate_record,
)
from .repository import AcademicRepository


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
            SELECT id,title,revision,created_at FROM classsync_academic.period_metadata
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
            if calendar is not None:
                if checksum(calendar["payload"]) != calendar["checksum"]:
                    raise ValueError("Checksum mismatch")
                value = AcademicCalendar.model_validate(json.loads(calendar["payload"]))
            return AcademicPeriod(
                **{**row, "created_at": utc_timestamp(row["created_at"])},
                source="institutional",
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
                WHERE tenant_id=:tenant AND owner_uid=:owner ORDER BY created_at DESC,id
            """),
                self.keys,
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

    def write_in(self, db, period_id, body):
        record = body.record
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

        validate_record(record, period_id, lookup)
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

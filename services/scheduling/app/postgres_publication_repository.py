"""Bound publication transactions and authorized published-role projections.

Institutional HTTP providers use their owned PostgreSQL pool; no startup migration
or SQLite fallback. Institutional approval and production release remain separate.
"""

import json
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from classync_contracts.identity import (
    MembershipAuthorizationError,
    MembershipErrorCode,
    VerifiedPrincipal,
)
from classync_contracts.publication import PublicationCommand, RoomRestriction
from classync_persistence.academic_periods import utc_timestamp
from classync_persistence.database import transaction
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError, SQLAlchemyError

from services.academic.app.postgres_repository import PostgresAcademicRepository
from services.academic.app.record_rules import AcademicError

from .academic_input import academic_readiness
from .draft_rules import DraftError, digest, encode, now
from .occurrences import ZONE
from .postgres_draft_repository import PostgresDraftRepository
from .publication_rules import PublicationRules


class PostgresPublicationRepository(PublicationRules):
    def __init__(self, engine, *, tenant_id, firebase_project_id, principal: VerifiedPrincipal):
        self.drafts = PostgresDraftRepository(
            engine,
            tenant_id=tenant_id,
            firebase_project_id=firebase_project_id,
            principal=principal,
        )
        self.academic = PostgresAcademicRepository(
            engine,
            tenant_id=tenant_id,
            firebase_project_id=firebase_project_id,
            principal=principal,
        )
        self.engine, self.principal = engine, principal
        self.context, self.keys = self.drafts.context, self.drafts.keys

    @staticmethod
    def scope(dataset, period=None):
        if not isinstance(dataset, str) or dataset not in {"synthetic", "institutional"}:
            raise DraftError(422, "publication_scope", "Unknown publication dataset.")
        if period is not None and (
            not isinstance(period, str) or not 1 <= len(period.strip()) <= 120
        ):
            raise DraftError(422, "publication_scope", "Choose a valid academic period.")

    @staticmethod
    def typed(body, model):
        try:
            if not isinstance(body, model):
                raise ValueError("Typed command required")
            return model.model_validate(body.model_dump())
        except (ValidationError, ValueError, TypeError) as error:
            raise DraftError(
                422, "publication_command", "Correct the publication input."
            ) from error

    @contextmanager
    def session(self, *, dataset=None, role="administrator", record_id=None):
        try:
            with transaction(self.engine) as db:
                if dataset is None:
                    db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
                db.execute(text("SET LOCAL lock_timeout='3s'"))
                db.execute(text("SET LOCAL statement_timeout='15s'"))
                self.context.context(db, self.principal)
                db.execute(
                    text("SELECT set_config('classsync.role', :role, true), "
                         "set_config('classsync.record_id', :record, true)"),
                    {"role": role, "record": record_id or ""},
                )
                if not db.scalar(
                    text("""
                    SELECT 1 FROM classsync_identity.memberships m
                    JOIN classsync_identity.tenants t ON t.id=m.tenant_id
                    WHERE m.tenant_id=:tenant AND m.uid=:owner AND m.state='active'
                        AND :role=ANY(m.roles) AND t.firebase_project_id=:project
                        AND (:role<>'student' OR m.student_id=:record)
                        AND (:role<>'teacher' OR m.faculty_id=:record)
                """),
                    {**self.keys, "project": self.context.project_id,
                     "role": role, "record": record_id},
                ):
                    raise MembershipAuthorizationError(MembershipErrorCode.DENIED)
                if dataset is not None:
                    db.execute(
                        text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                        {"key": encode(["classsync-publication", self.keys["tenant"], dataset])},
                    )
                    if not db.scalar(
                        text("SELECT classsync_scheduling.lock_publication_authority()")
                    ):
                        raise MembershipAuthorizationError(MembershipErrorCode.DENIED)
                yield db
        except IntegrityError as error:
            raise DraftError(
                409,
                "publication_integrity",
                "Publication state changed or conflicts. Reload before retrying.",
            ) from error
        except DBAPIError as error:
            if getattr(error.orig, "sqlstate", None) in {"40001", "40P01", "55P03"}:
                raise DraftError(
                    409,
                    "publication_version_conflict",
                    "A competing change is in progress. Reload and retry.",
                ) from error
            raise DraftError(
                503,
                "persistence_unavailable",
                "Publication storage is unavailable; no save was confirmed.",
            ) from error
        except SQLAlchemyError as error:
            raise DraftError(
                503,
                "persistence_unavailable",
                "Publication storage is unavailable; no save was confirmed.",
            ) from error
        except AcademicError as error:
            raise DraftError(error.status, error.code, str(error)) from error

    def params(self, dataset, **values):
        return {**self.keys, "dataset": dataset, **values}

    @staticmethod
    def record(row):
        if digest(row["command"]) != row["request_hash"]:
            raise DraftError(409, "publication_integrity", "Publication command integrity failed.")
        return {
            **row,
            "tenant": row["tenant_id"],
            "actor": row["actor_uid"],
            "created_at": utc_timestamp(row["created_at"]),
        }

    def rows(self, db, tenant, dataset, period=None):
        self.scope(dataset, period)
        if tenant != self.keys["tenant"]:
            raise MembershipAuthorizationError(MembershipErrorCode.DENIED)
        query = (
            "SELECT * FROM classsync_scheduling.published_versions "
            "WHERE tenant_id=:tenant AND dataset=:dataset"
        )
        if period is not None:
            query += " AND period_id=:period"
        return [
            self.record(row)
            for row in db.execute(
                text(query + " ORDER BY sequence"), self.params(dataset, period=period)
            ).mappings()
        ]

    def head(self, db, tenant, dataset, period):
        if tenant != self.keys["tenant"]:
            raise MembershipAuthorizationError(MembershipErrorCode.DENIED)
        return (
            db.scalar(
                text("""
            SELECT revision FROM classsync_scheduling.publication_heads
            WHERE tenant_id=:tenant AND dataset=:dataset AND period_id=:period
        """),
                self.params(dataset, period=period),
            )
            or 0
        )

    def history(self, dataset, period):
        if period is None:
            raise DraftError(422, "publication_scope", "Choose an academic period.")
        self.scope(dataset, period)
        with self.session() as db:
            return [
                self.summary(row, db)
                for row in reversed(self.rows(db, self.keys["tenant"], dataset, period))
            ]

    def calendar(self, tenant, dataset, period, start, end, viewer):
        self.scope(dataset, period)
        role = viewer.get("role")
        if role not in {"administrator", "teacher", "student"}:
            raise MembershipAuthorizationError(MembershipErrorCode.DENIED)
        record_id = viewer.get("faculty_id") if role == "teacher" else (
            viewer.get("student_id") if role == "student" else None
        )
        with self.session(role=role, record_id=record_id) as db:
            if role != "administrator":
                current = self.head(db, tenant, dataset, period)
                visible = self.rows(db, tenant, dataset, period)
                # If a newer immutable version no longer contains this record,
                # RLS hides it. Never fall back to an older visible timetable.
                if not visible or visible[-1]["revision"] != current:
                    raise DraftError(
                        403,
                        "projection_forbidden",
                        "This identity is not assigned to the current published period.",
                    )
            return self.project(db, tenant, dataset, period, start, end, viewer)

    def periods(self, role, *, dataset="institutional", student_id=None, faculty_id=None):
        self.scope(dataset)
        record_id = faculty_id if role == "teacher" else student_id if role == "student" else None
        with self.session(role=role, record_id=record_id) as db:
            ids = db.execute(text("""
                SELECT period_id,revision FROM classsync_scheduling.publication_heads
                WHERE tenant_id=:tenant AND dataset=:dataset ORDER BY period_id
            """), self.params(dataset)).mappings()
            result = []
            for item in ids:
                versions = self.rows(db, self.keys["tenant"], dataset, item["period_id"])
                if not versions:
                    continue
                payload = self.decode(versions[-1])
                inputs = payload["draft"].input_snapshot
                eligible = (
                    role == "administrator"
                    or (role == "teacher" and any(
                        assignment.teacher_id == faculty_id
                        for assignment in payload["draft"].generation_result.assignments
                    ))
                    or (role == "student" and any(
                        enrollment.student_id == student_id for enrollment in inputs.enrollments
                    ))
                )
                if eligible:
                    result.append({"id": item["period_id"], "revision": item["revision"],
                                   "title": payload["draft"].title,
                                   "calendar": payload["calendar"].model_dump(mode="json")})
            return {"periods": result}

    def availability(self, dataset, room_id, start, end):
        if (
            not isinstance(room_id, str) or not room_id.strip()
            or start.tzinfo is None or end.tzinfo is None
            or not start < end or end - start > timedelta(days=2)
        ):
            raise DraftError(
                422,
                "availability_range",
                "Choose a room and an interval within two days.",
            )
        start, end = start.astimezone(ZONE), end.astimezone(ZONE)
        with self.session() as db:
            rows = self.rows(db, self.keys["tenant"], dataset)
            if not rows:
                raise DraftError(
                    404, "not_published", "No published occupancy source is available."
                )
            decoded = [self.decode(row) for row in rows]
            known = {room.id for value in decoded for room in value["draft"].input_snapshot.rooms}
            if room_id not in known:
                raise DraftError(404, "room_not_found", "Room not found in the published scope.")
            day, stop = start.date(), (end - timedelta(microseconds=1)).date()
            covered = True
            while day <= stop:
                covered = covered and any(
                    value["calendar"].effective_start <= day <= value["calendar"].effective_end
                    for value in decoded
                )
                day += timedelta(days=1)
            requested = {"starts_at": start.isoformat(), "ends_at": end.isoformat()}
            matches = [event for event in self.expanded(rows, start.date(), end.date())
                       if event["room"]["id"] == room_id
                       and event["starts_at"] < requested["ends_at"]
                       and requested["starts_at"] < event["ends_at"]]
            restrictions = db.execute(text("""
                SELECT payload,checksum FROM classsync_scheduling.room_restrictions
                WHERE tenant_id=:tenant AND dataset=:dataset
            """), self.params(dataset)).mappings()
            restricted = any(
                value["room_id"] == room_id
                and datetime.fromisoformat(value["starts_at"]) < end
                and start < datetime.fromisoformat(value["ends_at"])
                for value in (self.restriction_value(row) for row in restrictions)
            )
            return {
                "room_id": room_id,
                "occupancy": "restricted" if restricted else "occupied" if matches
                else "unoccupied" if covered else "unknown",
                "suitability": "unknown", "sessions": len(matches), "timezone": "Asia/Manila",
            }

    def receipt(self, row, db):
        # This acknowledges the immutable result of the original command. Current
        # supersession is reported separately by history and the current calendar.
        return self.summary(row, db) | {"status": "published"}

    def admin_calendar(self, dataset, period, start, end):
        if period is None:
            raise DraftError(422, "publication_scope", "Choose an academic period.")
        self.scope(dataset, period)
        if (
            type(start) is not date
            or type(end) is not date
            or start > end
            or (end - start).days > 62
        ):
            raise DraftError(422, "calendar_range", "Choose a date range of at most 63 days.")
        with self.session() as db:
            return self.project(
                db,
                self.keys["tenant"],
                dataset,
                period,
                start,
                end,
                {"role": "administrator", "uid": self.principal.uid},
            )

    @staticmethod
    def restriction_value(row):
        if digest(row["payload"]) != row["checksum"]:
            raise DraftError(409, "restriction_integrity", "Room restriction integrity failed.")
        try:
            value = json.loads(row["payload"])
            revision = value.pop("revision")
            if type(revision) is not int or revision < 1:
                raise ValueError("Stored positive revision required")
            typed = RoomRestriction.model_validate(value | {"expected_revision": revision - 1})
            start, end = (datetime.fromisoformat(item) for item in (typed.starts_at, typed.ends_at))
            if (
                start.utcoffset() is None
                or end.utcoffset() is None
                or start >= end
                or end - start > timedelta(days=366)
            ):
                raise ValueError("Stored timezone-aware ordered interval required")
            return typed.model_dump(exclude={"expected_revision"}) | {"revision": revision}
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            raise DraftError(
                409, "restriction_integrity", "Stored room restriction is corrupt or incompatible."
            ) from error

    def restrictions(self, db, tenant, dataset, events):
        if tenant != self.keys["tenant"]:
            raise MembershipAuthorizationError(MembershipErrorCode.DENIED)
        stored = db.execute(
            text("""
            SELECT payload,checksum FROM classsync_scheduling.room_restrictions
            WHERE tenant_id=:tenant AND dataset=:dataset
        """),
            self.params(dataset),
        ).mappings()
        for row in stored:
            value = self.restriction_value(row)
            begin, finish = (datetime.fromisoformat(value[key]) for key in ("starts_at", "ends_at"))
            for event in events:
                if (
                    event["room"]["id"] == value["room_id"]
                    and begin < datetime.fromisoformat(event["ends_at"])
                    and datetime.fromisoformat(event["starts_at"]) < finish
                ):
                    raise DraftError(
                        422,
                        "room_restricted",
                        "Published occupancy overlaps a room restriction or reservation.",
                    )

    def publish(self, command, *, commit):
        command = self.typed(command, PublicationCommand)
        if command.calendar.published_version:
            raise DraftError(422, "client_version", "Published version is assigned by the server.")
        if command.source != "administrator":
            raise DraftError(
                422,
                "publication_command",
                "Use an owned server draft and a calendar without a client version.",
            )
        self.scope(command.dataset)
        value = encode(command.model_dump(mode="json"))
        with self.session(dataset=command.dataset) as db:
            existing = (
                db.execute(
                    text("""
                SELECT * FROM classsync_scheduling.published_versions
                WHERE tenant_id=:tenant AND dataset=:dataset AND idempotency_key=:key
            """),
                    self.params(command.dataset, key=command.idempotency_key),
                )
                .mappings()
                .one_or_none()
            )
            if existing is not None:
                if existing["owner_uid"] != self.principal.uid or existing[
                    "request_hash"
                ] != digest(value):
                    raise DraftError(
                        409, "publish_key_conflict", "This key belongs to another command."
                    )
                return self.receipt(self.record(existing), db)
            row = (
                db.execute(
                    text("""
                SELECT * FROM classsync_scheduling.drafts
                WHERE tenant_id=:tenant AND owner_uid=:owner AND id=:draft
            """),
                    {**self.keys, "draft": command.draft_id},
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise DraftError(404, "draft_not_found", "No permitted saved draft exists.")
            draft = self.drafts.detail(self.drafts.metadata(row))
            self.validate_candidate(command, draft)
            self.academic.period_in(db, draft.period_id, lock=True)
            snapshot = self.academic.snapshot_in(db, draft.period_id)
            checked = academic_readiness(snapshot)
            self.validate_academic_scope(command, draft, snapshot, checked)
            calendar = command.calendar
            rows = self.rows(db, self.keys["tenant"], command.dataset)
            revision = self.head(db, self.keys["tenant"], command.dataset, draft.period_id)
            owner = db.scalar(
                text("""
                SELECT owner_uid FROM classsync_scheduling.publication_heads
                WHERE tenant_id=:tenant AND dataset=:dataset AND period_id=:period
            """),
                self.params(command.dataset, period=draft.period_id),
            )
            if owner is not None and owner != self.principal.uid:
                raise DraftError(
                    409,
                    "publication_owner_conflict",
                    "This published scope belongs to another Administrator.",
                )
            if revision != command.expected_version:
                raise DraftError(
                    409, "publication_version_conflict", "Review the latest published version."
                )
            report = self.review_scope(db, self.keys["tenant"], command, draft, rows, revision)
            if not commit:
                return report
            if any(
                row["draft_id"] == draft.id and self.decode(row)["calendar"] == calendar
                for row in rows
            ):
                raise DraftError(
                    409, "duplicate_publication", "This draft and calendar are already published."
                )
            payload = encode(
                {
                    "draft": draft.model_dump(mode="json"),
                    "calendar": calendar.model_dump(mode="json"),
                    "review": report,
                }
            )
            parameters = self.params(
                command.dataset,
                period=draft.period_id,
                draft=draft.id,
                id=str(uuid4()),
                revision=revision + 1,
                academic=command.expected_academic_revision,
                created=now(),
                key=command.idempotency_key,
                command=value,
                request_hash=digest(value),
                payload=payload,
                checksum=digest(payload),
            )
            created = (
                db.execute(
                    text("""
                INSERT INTO classsync_scheduling.published_versions
                (tenant_id,dataset,period_id,owner_uid,actor_uid,draft_id,id,revision,academic_revision,
                 created_at,idempotency_key,command,request_hash,payload,checksum)
                VALUES (:tenant,:dataset,:period,:owner,:owner,:draft,:id,:revision,:academic,
                        :created,:key,:command,:request_hash,:payload,:checksum) RETURNING *
            """),
                    parameters,
                )
                .mappings()
                .one()
            )
            if revision == 0:
                statement = text("""
                INSERT INTO classsync_scheduling.publication_heads
                (tenant_id,dataset,period_id,owner_uid,revision)
                VALUES (:tenant,:dataset,:period,:owner,:revision)
                """)
            else:
                statement = text("""
                    UPDATE classsync_scheduling.publication_heads SET revision=:revision
                    WHERE tenant_id=:tenant AND dataset=:dataset AND period_id=:period
                        AND owner_uid=:owner AND revision=:expected
                """)
            if db.execute(statement, parameters | {"expected": revision}).rowcount != 1:
                raise DraftError(
                    409,
                    "publication_version_conflict",
                    "A competing change updated this published scope.",
                )
            return self.receipt(self.record(created), db)

    def put_restriction(self, body):
        body = self.typed(body, RoomRestriction)
        try:
            start, end = (datetime.fromisoformat(value) for value in (body.starts_at, body.ends_at))
            if (
                start.utcoffset() is None
                or end.utcoffset() is None
                or start >= end
                or end - start > timedelta(days=366)
            ):
                raise ValueError("Invalid interval")
        except (ValueError, TypeError) as error:
            raise DraftError(
                422,
                "restriction_interval",
                "Use timezone-aware timestamps, in order, within 366 days.",
            ) from error
        value = body.model_dump(exclude={"expected_revision"}) | {
            "starts_at": start.astimezone(UTC).isoformat(),
            "ends_at": end.astimezone(UTC).isoformat(),
            "revision": body.expected_revision + 1,
        }
        with self.session(dataset=body.dataset) as db:
            rows = self.rows(db, self.keys["tenant"], body.dataset)
            known = {
                room.id for row in rows for room in self.decode(row)["draft"].input_snapshot.rooms
            }
            if body.room_id not in known:
                raise DraftError(422, "restriction_room", "Choose a room in the published scope.")
            old = (
                db.execute(
                    text("""
                SELECT owner_uid,revision,payload,checksum
                FROM classsync_scheduling.room_restrictions
                WHERE tenant_id=:tenant AND dataset=:dataset AND id=:id
            """),
                    self.params(body.dataset, id=body.id),
                )
                .mappings()
                .one_or_none()
            )
            if old is not None:
                self.restriction_value(old)
            if (
                old
                and old["owner_uid"] != self.principal.uid
                or (old["revision"] if old else 0) != body.expected_revision
            ):
                raise DraftError(
                    409, "restriction_version_conflict", "Restriction changed; reload it."
                )
            # A new restriction must not silently invalidate an already published session.
            day, stop = start.astimezone(ZONE).date(), end.astimezone(ZONE).date()
            reviewed = 0
            while day <= stop:
                last = min(day + timedelta(days=62), stop)
                for event in self.expanded(rows, day, last):
                    reviewed += 1
                    if reviewed > 100000:
                        raise DraftError(
                            413,
                            "publication_scope_limit",
                            "Limit a restriction review to 100,000 occurrences.",
                        )
                    if (
                        event["room"]["id"] == body.room_id
                        and start < datetime.fromisoformat(event["ends_at"])
                        and datetime.fromisoformat(event["starts_at"]) < end
                    ):
                        raise DraftError(
                            409,
                            "restriction_publication_conflict",
                            "Revise the overlapping published session first.",
                        )
                day = last + timedelta(days=1)
            payload = encode(value)
            if old is None:
                statement = text("""
                INSERT INTO classsync_scheduling.room_restrictions
                (tenant_id,dataset,id,owner_uid,room_id,revision,starts_at,ends_at,payload,checksum)
                VALUES (:tenant,:dataset,:id,:owner,:room,:revision,:start,:end,:payload,:checksum)
                """)
            else:
                statement = text("""
                    UPDATE classsync_scheduling.room_restrictions
                    SET room_id=:room,revision=:revision,starts_at=:start,ends_at=:end,
                        payload=:payload,checksum=:checksum
                    WHERE tenant_id=:tenant AND dataset=:dataset AND id=:id
                        AND owner_uid=:owner AND revision=:expected
                """)
            changed = db.execute(
                statement,
                self.params(
                    body.dataset,
                    id=body.id,
                    room=body.room_id,
                    revision=value["revision"],
                    start=start,
                    end=end,
                    payload=payload,
                    checksum=digest(payload),
                    expected=body.expected_revision,
                ),
            )
            if changed.rowcount != 1:
                raise DraftError(
                    409,
                    "restriction_version_conflict",
                    "Restriction changed; reload before editing.",
                )
            return value

"""Bound publication transactions and authorized published-role projections.

Institutional HTTP providers use their owned PostgreSQL pool; no startup migration
or SQLite fallback. Institutional approval and production release remain separate.
"""

import json
from contextlib import contextmanager
from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4

from classync_contracts.calendar import AcademicCalendar
from classync_contracts.identity import (
    MembershipAuthorizationError,
    MembershipErrorCode,
    VerifiedPrincipal,
)
from classync_contracts.publication import PublicationCommand, RoomRestriction
from classync_persistence.academic_periods import (
    ARCHIVED_PERIOD_TITLE_PATTERN,
    utc_timestamp,
)
from classync_persistence.database import transaction
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError, SQLAlchemyError

from services.academic.app.postgres_repository import PostgresAcademicRepository
from services.academic.app.record_rules import AcademicError

from .academic_input import academic_readiness
from .catalog import excluded_space_ids, schedulable_space_ids, schedulable_spaces
from .draft_rules import DraftError, digest, encode, now
from .occurrences import ZONE
from .postgres_draft_repository import PostgresDraftRepository
from .publication_rules import PublicationRules
from .reports import booked_sessions, build_report
from .room_occupancy import occupied_rooms


def viewer_record(viewer):
    role = viewer.get("role")
    if role not in {"administrator", "teacher", "student"}:
        raise MembershipAuthorizationError(MembershipErrorCode.DENIED)
    record = viewer.get("student_id") if role == "student" else (
        viewer.get("faculty_id") if role == "teacher" else None
    )
    return role, record


def current_room_scope(repo, db, period, role, record):
    """Return the current published rows/payload when this viewer belongs to them."""
    revision = repo.head(db, repo.keys["tenant"], "institutional", period)
    rows = repo.rows(db, repo.keys["tenant"], "institutional", period)
    if not rows or rows[-1]["revision"] != revision:
        raise DraftError(
            403, "projection_forbidden", "No permitted current room directory."
        )
    value = repo.decode(rows[-1])
    draft = value["draft"]
    eligible = role == "administrator" or (
        role == "teacher" and any(
            assignment.teacher_id == record
            for assignment in draft.generation_result.assignments
        )
    ) or (
        role == "student" and any(
            enrollment.student_id == record and enrollment.offering_ids
            for enrollment in draft.input_snapshot.enrollments
        )
    )
    if not eligible:
        raise DraftError(
            403, "projection_forbidden", "No permitted current room directory."
        )
    return rows, value


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
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            if constraint == "academic_period_archived":
                raise DraftError(
                    409, "period_archived", "This academic period is archived and read-only."
                ) from error
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

    def history(self, dataset, period, *, limit=50, offset=0, include_details=False):
        if period is None:
            raise DraftError(422, "publication_scope", "Choose an academic period.")
        self.scope(dataset, period)
        if not 1 <= limit <= 101 or not 0 <= offset <= 10000:
            raise DraftError(422, "publication_page", "Choose a valid publication history page.")
        with self.session() as db:
            columns = (
                "*"
                if include_details
                else (
                    "tenant_id,dataset,period_id,id,sequence,revision,draft_id,actor_uid,"
                    "created_at,command,request_hash"
                )
            )
            rows = db.execute(
                text(
                    "SELECT " + columns + " FROM classsync_scheduling.published_versions "
                    "WHERE tenant_id=:tenant AND dataset=:dataset AND period_id=:period "
                    "ORDER BY sequence DESC LIMIT :limit OFFSET :offset"
                ),
                self.params(dataset, period=period, limit=limit, offset=offset),
            ).mappings()
            current = self.head(db, self.keys["tenant"], dataset, period)
            result = []
            for row in rows:
                record = self.record(row)
                if include_details:
                    result.append(self.summary(record, db))
                else:
                    result.append({
                        key: record[key]
                        for key in (
                            "id", "sequence", "revision", "period_id", "draft_id",
                            "actor", "created_at", "dataset",
                        )
                    } | {
                        "status": "published" if record["revision"] == current else "superseded"
                    })
            return result

    def administrator_activity(self, period, *, limit=100):
        """Return redacted activity events visible to a verified tenant Administrator."""
        with self.session() as db:
            rows = db.execute(
                text("""
                    SELECT event_id,event_type,entity_type,entity_ref,revision,
                        owner_uid AS actor_uid,created_at
                    FROM classsync_scheduling.administrator_activity
                    WHERE tenant_id=:tenant AND (period_id=:period OR period_id IS NULL)
                    ORDER BY created_at DESC,event_id DESC LIMIT :limit
                """),
                {"tenant": self.keys["tenant"], "period": period, "limit": limit},
            ).mappings().all()
            return [dict(row) for row in rows]

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
            """), self.params(dataset)).mappings().all()
            # Only Administrators can read period metadata under row-level security. A
            # non-UUID legacy period can never have been published through the Gateway.
            archived = set()
            if role == "administrator":
                archived = set(db.scalars(text("""
                    SELECT id FROM classsync_academic.period_metadata
                    WHERE tenant_id=:tenant AND title LIKE :archived
                """), {**self.keys, "archived": ARCHIVED_PERIOD_TITLE_PATTERN}).all())
            result = []
            for item in ids:
                if item["period_id"] in archived:
                    continue
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

    def room_directory(self, period, viewer):
        role, record = viewer_record(viewer)
        with self.session(role=role, record_id=record) as db:
            rows, value = current_room_scope(self, db, period, role, record)
            # Return room metadata only; never expose the enclosing academic snapshot.
            rooms = [
                {
                    "id": room.id, "name": room.name, "building": room.building,
                    "floor": room.floor, "location": room.location,
                    "room_type": room.room_type if room.type_verified else None,
                    "capacity": room.capacity if room.capacity_verified else None,
                    "equipment": room.equipment if room.equipment_verified else [],
                }
                for room in value["draft"].input_snapshot.rooms
            ]
            return {"version": rows[-1]["id"], "rooms": rooms}

    def availability(self, dataset, room_id, start, end, viewer=None):
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
        role, record = viewer_record(viewer or {"role": "administrator"})
        with self.session(role=role, record_id=record) as db:
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
                value.get("status", "active") == "active"
                and value["room_id"] == room_id
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

    def occupancy_in(self, db, dataset, begin, finish, *, restrictions):
        """Rooms with a published session (and, for Administrators, a restriction) in a slot.

        Occupancy uses every visible published version (latest per day). Restrictions are
        Administrator-readable only under RLS, so other callers pass False; approval
        re-validates restrictions before any schedule change is published.
        """
        if begin.tzinfo is None or finish.tzinfo is None or not begin < finish:
            raise DraftError(422, "availability_range", "Choose an increasing time range.")
        day = begin.astimezone(ZONE).date()
        if (finish - timedelta(microseconds=1)).astimezone(ZONE).date() != day:
            raise DraftError(422, "availability_range", "Choose a time range within one day.")
        rows = self.rows(db, self.keys["tenant"], dataset)
        # A session's transition buffer also keeps its room from the adjacent slot.
        occupied = set()
        for event in self.expanded(rows, day, day):
            pad = timedelta(minutes=event.get("buffer", 0))
            if (
                datetime.fromisoformat(event["starts_at"]) - pad < finish
                and begin < datetime.fromisoformat(event["ends_at"]) + pad
            ):
                occupied.add(event["room"]["id"])
        restricted = set()
        if restrictions:
            stored = db.execute(text("""
                SELECT payload,checksum FROM classsync_scheduling.room_restrictions
                WHERE tenant_id=:tenant AND dataset=:dataset
            """), self.params(dataset)).mappings()
            for row in stored:
                value = self.restriction_value(row)
                if (
                    value.get("status", "active") == "active"
                    and datetime.fromisoformat(value["starts_at"]) < finish
                    and begin < datetime.fromisoformat(value["ends_at"])
                ):
                    restricted.add(value["room_id"])
        return occupied, restricted

    def member_occupancy(self, db, dataset, begin, finish):
        """Tenant-wide occupied and restricted rooms for any member (room ids only).

        Uses the 0028 projection functions, so a Teacher or Student also sees rooms booked by
        publications they are not part of, without reading those publications.
        """
        if begin.tzinfo is None or finish.tzinfo is None or not begin < finish:
            raise DraftError(422, "availability_range", "Choose an increasing time range.")
        if (finish - timedelta(microseconds=1)).astimezone(ZONE).date() != begin.astimezone(
            ZONE
        ).date():
            raise DraftError(422, "availability_range", "Choose a time range within one day.")
        rows = db.execute(
            text("SELECT * FROM classsync_scheduling.room_occupancy_versions(:dataset,:day)"),
            {"dataset": dataset, "day": begin.astimezone(ZONE).date()},
        ).mappings().all()
        restricted = set(db.scalars(
            text("""
            SELECT room_id FROM classsync_scheduling.room_restriction_windows(:dataset)
            WHERE starts_at<:finish AND :begin<ends_at
        """),
            {"dataset": dataset, "begin": begin, "finish": finish},
        ).all())
        return occupied_rooms(rows, begin, finish), restricted

    def room_slot(self, period, day, start, end, viewer):
        """Occupancy of every catalog-schedulable space in one slot; room metadata only."""
        if (
            type(day) is not date
            or type(start) is not int or type(end) is not int
            or not 0 <= start < end <= 1440
            or start % 30 or end % 30
        ):
            raise DraftError(
                422, "availability_range", "Choose a date and a 30-minute aligned time range."
            )
        role, record = viewer_record(viewer)
        with self.session(role=role, record_id=record) as db:
            _, value = current_room_scope(self, db, period, role, record)
            calendar, inputs = value["calendar"], value["draft"].input_snapshot
            if (
                not calendar.effective_start <= day <= calendar.effective_end
                or day.weekday() not in calendar.instructional_days
            ):
                raise DraftError(
                    422, "availability_day", "Choose an instructional day in this period."
                )
            if not any(
                window.day == day.weekday() and window.start <= start and end <= window.end
                for window in inputs.operating_windows
            ):
                raise DraftError(
                    422, "availability_hours", "Choose a time within campus operating hours."
                )
            midnight = datetime.combine(day, time(), ZONE)
            begin, finish = (midnight + timedelta(minutes=m) for m in (start, end))
            checked = True
            occupied, restricted = (
                self.occupancy_in(db, "institutional", begin, finish, restrictions=True)
                if role == "administrator"
                else self.member_occupancy(db, "institutional", begin, finish)
            )
            return {
                "date": day.isoformat(),
                "start": start,
                "end": end,
                "timezone": "Asia/Manila",
                "restrictions_checked": checked,
                "rooms": [
                    {
                        "id": room.id,
                        "name": room.name,
                        "building": room.building,
                        "floor": room.floor,
                        "occupancy": "restricted" if room.id in restricted
                        else "occupied" if room.id in occupied else "free",
                    }
                    for room in schedulable_spaces()
                ],
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
                    value.get("status", "active") == "active"
                    and event["room"]["id"] == value["room_id"]
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
        with self.session(dataset=command.dataset) as db:
            return self.publish_in(db, command, commit=commit)

    def publish_in(self, db, command, *, commit):
        """Validate and optionally publish inside a caller-held publication session.

        The caller must hold ``session(dataset=...)`` (advisory lock and publication
        authority) when ``commit`` is true.
        """
        command = self.typed(command, PublicationCommand)
        if command.calendar.published_version or command.source != "administrator":
            raise DraftError(
                422,
                "publication_command",
                "Use an owned server draft and a calendar without a client version.",
            )
        self.scope(command.dataset)
        value = encode(command.model_dump(mode="json"))
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
        # Only a committing publication locks the academic period; reviews stay read-only.
        self.academic.period_in(db, draft.period_id, lock=commit)
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
            row["period_id"] == draft.period_id
            and row["revision"] == revision
            and row["draft_id"] == draft.id
            and self.decode(row)["calendar"] == calendar
            for row in rows
        ):
            raise DraftError(
                409, "duplicate_publication", "This draft and calendar are currently published."
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

    def report_versions(self, rows, current, decoded_current, calendar):
        """Versions that can still win a date inside the period, each decoded once.

        Rooms are shared, so every period's publications count. A version whose dates are
        fully covered by a later one of its period is never decoded.
        """
        covered, chosen = {}, []
        for row in reversed(rows):
            try:
                dates = AcademicCalendar.model_validate(json.loads(row["payload"])["calendar"])
            except (ValueError, KeyError, TypeError) as error:
                raise DraftError(
                    409, "publication_integrity", "Stored publication is corrupt or incompatible."
                ) from error
            spans = covered.setdefault(row["period_id"], [])
            if (
                dates.effective_end < calendar.effective_start
                or calendar.effective_end < dates.effective_start
                or any(
                    first <= dates.effective_start and dates.effective_end <= last
                    for first, last in spans
                )
            ):
                continue
            spans.append((dates.effective_start, dates.effective_end))
            payload = decoded_current if row is current else self.decode(row)
            chosen.append(
                (
                    row["period_id"],
                    payload["calendar"],
                    payload["draft"].generation_result.assignments,
                )
            )
        return chosen[::-1]

    def report(self, period):
        """Utilization and workload for one owned period, from a single consistent read."""
        with self.session() as db:
            academic_period = self.academic.period_in(db, period)
            snapshot = self.academic.snapshot_in(db, period)
            rows = self.rows(db, self.keys["tenant"], "institutional")
            own = [row for row in rows if row["period_id"] == period]
            published = self.decode(own[-1]) if own else None
            calendar = published["calendar"] if published else academic_period.calendar
            events = []
            if calendar:
                events = booked_sessions(
                    self.report_versions(rows, own[-1] if own else None, published, calendar),
                    calendar.effective_start,
                    calendar.effective_end,
                )
            stored = db.execute(
                text("""
                SELECT payload,checksum FROM classsync_scheduling.room_restrictions
                WHERE tenant_id=:tenant AND dataset='institutional'
            """),
                self.params("institutional"),
            ).mappings()
            result = build_report(
                [entry.record for entry in snapshot.records],
                academic_period.calendar,
                published,
                events,
                [self.restriction_value(row) for row in stored],
            )
            return {
                "period": {
                    "id": academic_period.id,
                    "title": academic_period.title,
                    "revision": academic_period.revision,
                    "archived_at": academic_period.archived_at,
                },
                "published": {
                    "version": own[-1]["id"],
                    "revision": own[-1]["revision"],
                    "created_at": own[-1]["created_at"],
                }
                if own
                else None,
                **result,
            }

    def restriction_list(self, dataset, *, include_cancelled=False):
        """Administrator read of every stored restriction, checksum-verified."""
        self.scope(dataset)
        with self.session() as db:
            rows = db.execute(
                text("""
                SELECT payload,checksum FROM classsync_scheduling.room_restrictions
                WHERE tenant_id=:tenant AND dataset=:dataset ORDER BY starts_at,id
            """),
                self.params(dataset),
            ).mappings()
            values = [self.restriction_value(row) for row in rows]
            return [v for v in values if include_cancelled or v["status"] == "active"]

    @staticmethod
    def restriction_interval(body):
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
        return start, end

    def restriction_room_in(self, rows, dataset, room_id):
        """A published-scope room, or (institutional) any catalog-schedulable space."""
        known = {
            room.id for row in rows for room in self.decode(row)["draft"].input_snapshot.rooms
        }
        if dataset == "institutional":
            known = (known | schedulable_space_ids()) - excluded_space_ids()
        if room_id not in known:
            raise DraftError(422, "restriction_room", "Choose a room in the published scope.")

    def impacted_sessions(self, rows, room_id, start, end):
        """Published dated sessions that overlap a proposed restriction of one room."""
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
                    event["room"]["id"] == room_id
                    and start < datetime.fromisoformat(event["ends_at"])
                    and datetime.fromisoformat(event["starts_at"]) < end
                ):
                    yield event
            day = last + timedelta(days=1)

    def restriction_preflight(self, body, *, limit=50):
        """List published sessions a proposed restriction would collide with; writes nothing."""
        body = self.typed(body, RoomRestriction)
        start, end = self.restriction_interval(body)
        with self.session() as db:
            rows = self.rows(db, self.keys["tenant"], body.dataset)
            self.restriction_room_in(rows, body.dataset, body.room_id)
            sessions, total = [], 0
            for event in self.impacted_sessions(rows, body.room_id, start, end):
                total += 1
                if len(sessions) < limit:
                    sessions.append(
                        {
                            key: event[key]
                            for key in (
                                "date", "starts_at", "ends_at", "period_id", "subject",
                                "section", "teacher",
                            )
                        }
                    )
            return {"total": total, "sessions": sessions}

    def put_restriction(self, body):
        body = self.typed(body, RoomRestriction)
        start, end = self.restriction_interval(body)
        cancelling = body.status == "cancelled"
        if cancelling and body.expected_revision == 0:
            raise DraftError(
                422, "restriction_status", "Only a saved restriction can be cancelled."
            )
        value = body.model_dump(exclude={"expected_revision", "status"}) | {
            "starts_at": start.astimezone(UTC).isoformat(),
            "ends_at": end.astimezone(UTC).isoformat(),
            "revision": body.expected_revision + 1,
        }
        # Only cancelled rows carry a status, so active payloads keep their earlier shape.
        if cancelling:
            value["status"] = "cancelled"
        with self.session(dataset=body.dataset) as db:
            old = (
                db.execute(
                    text("""
                SELECT revision,payload,checksum
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
            if (old["revision"] if old else 0) != body.expected_revision:
                raise DraftError(
                    409, "restriction_version_conflict", "Restriction changed; reload it."
                )
            # Cancelling only releases the room, so it needs no publication review.
            if not cancelling:
                rows = self.rows(db, self.keys["tenant"], body.dataset)
                self.restriction_room_in(rows, body.dataset, body.room_id)
                # A restriction must not silently invalidate an already published session.
                if next(self.impacted_sessions(rows, body.room_id, start, end), None):
                    raise DraftError(
                        409,
                        "restriction_publication_conflict",
                        "Revise the overlapping published session first.",
                    )
            payload = encode(value)
            if old is None:
                statement = text("""
                INSERT INTO classsync_scheduling.room_restrictions
                (tenant_id,dataset,id,owner_uid,room_id,revision,starts_at,ends_at,payload,checksum)
                VALUES (:tenant,:dataset,:id,:owner,:room,:revision,:start,:end,:payload,:checksum)
                """)
            else:
                # Any tenant Administrator may revise; owner_uid records who did (0029).
                statement = text("""
                    UPDATE classsync_scheduling.room_restrictions
                    SET owner_uid=:owner,room_id=:room,revision=:revision,starts_at=:start,
                        ends_at=:end,payload=:payload,checksum=:checksum
                    WHERE tenant_id=:tenant AND dataset=:dataset AND id=:id
                        AND revision=:expected
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
            return value | {"status": body.status}

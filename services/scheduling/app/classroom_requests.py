"""Requests from current teaching assignments; validated publication remains authoritative."""

import json
from datetime import date, datetime
from typing import Literal
from uuid import UUID, uuid4

from classync_contracts.models import UserRole
from classync_contracts.publication import PublicationCommand
from classync_contracts.request_authorization import request_identity
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from .catalog import excluded_space_ids, schedulable_space_ids
from .draft_rules import DraftError, digest, encode
from .occurrences import ZONE
from .postgres_publication_repository import PostgresPublicationRepository
from .publication_api import scoped_repo, settings_only
from .publication_rules import request_exception
from .readiness import eligible_room


class StaleRequest(Exception):
    """The class or timetable changed so the request no longer applies."""


router = APIRouter(prefix="/api/v1/timetables/requests")


class RequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    period_id: UUID
    publication_id: UUID
    occurrence_id: str = Field(min_length=1, max_length=200)
    class_date: date
    proposed_room_id: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=3, max_length=1000)
    idempotency_key: UUID


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_revision: int = Field(ge=1)
    decision: Literal["approved", "rejected"]
    note: str = Field(min_length=3, max_length=1000)


class Fulfill(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)


def repository(request, *, teacher=False, admin=False):
    settings = settings_only()
    claims = request_identity(
        request,
        settings,
        UserRole.TEACHER if teacher else UserRole.ADMINISTRATOR if admin else None,
    )
    if claims["role"] not in {"teacher", "administrator"}:
        raise HTTPException(403, "Teacher or Administrator access required")
    if settings.scheduling_database_url is None:
        raise HTTPException(503, "Connected classroom requests are unavailable")
    _, publication = scoped_repo(request, claims)
    if not isinstance(publication, PostgresPublicationRepository):
        raise HTTPException(503, "Connected classroom requests are unavailable")
    return Requests(publication), claims


class Requests:
    def __init__(self, publication):
        self.publication = publication

    @staticmethod
    def summary(row):
        return {
            key: str(value)
            if key in {"id", "publication_id", "created_at", "updated_at"}
            else value
            for key, value in row.items()
            if key not in {"tenant_id", "dataset", "idempotency_key", "input_hash"}
            and key != "draft_id"
        }

    def options_in(self, db, claims, period, class_date, occurrence):
        p = self.publication
        # The repeatable-read role session binds the proposal to one visible head.
        # A replacement after this read makes Administrator approval stale (409);
        # a pending request never changes assignments or grants schedule access.
        rows = p.rows(db, p.keys["tenant"], "institutional", period)
        if not rows or rows[-1]["revision"] != p.head(
            db, p.keys["tenant"], "institutional", period
        ):
            raise HTTPException(403, "No current assigned publication is available")
        projected = p.project(
            db, p.keys["tenant"], "institutional", period, class_date, class_date, claims
        )
        event = next((item for item in projected["occurrences"] if item["id"] == occurrence), None)
        if event is None or event.get("version") != rows[-1]["id"]:
            raise HTTPException(403, "Choose one of your current published classes")
        source = p.decode(rows[-1])["draft"].input_snapshot
        offering = next(item for item in source.offerings if item.id == event["offering_id"])
        section = next(item for item in source.sections if item.id == offering.section_id)
        # Only the catalog's schedulable spaces are candidates; excluded spaces never appear.
        allowed = schedulable_space_ids()
        candidates = [
            room
            for room in source.rooms
            if room.id in allowed
            and room.id in offering.eligible_room_ids
            and eligible_room(room, offering, section.program_id)
            and room.id != event["room"]["id"]
        ]
        # Tenant-wide occupancy (0028): rooms booked by publications this Teacher is not
        # part of, and reservations/restrictions, are visible as room ids only.
        occupied, restricted = p.member_occupancy(
            db,
            "institutional",
            datetime.fromisoformat(event["starts_at"]),
            datetime.fromisoformat(event["ends_at"]),
        )
        rooms = [
            {
                "id": room.id,
                "name": room.name,
                "building": room.building,
                "floor": room.floor,
                "capacity": room.capacity if room.capacity_verified else None,
                "occupancy": "restricted"
                if room.id in restricted
                else "occupied"
                if room.id in occupied
                else "available",
            }
            for room in candidates
        ]
        return {
            "publication_id": rows[-1]["id"],
            "class": event,
            "rooms": rooms,
            "availability_note": (
                "Occupancy reflects every published timetable and room reservation for this "
                "class time. All hard constraints are re-checked at approval."
            ),
        }

    def options(self, claims, period, class_date, occurrence):
        with self.publication.session(role="teacher", record_id=claims["faculty_id"]) as db:
            return self.options_in(db, claims, period, class_date, occurrence)

    def create(self, claims, body):
        p, key = self.publication, str(body.idempotency_key)
        fingerprint = digest(encode(body.model_dump(mode="json")))
        with p.session(role="teacher", record_id=claims["faculty_id"]) as db:
            # Serialize one Teacher's submissions without a row lock: FOR UPDATE would need
            # UPDATE on identity memberships, which the runtime role must never hold.
            db.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                {"key": encode(["classsync-request", p.keys["tenant"], p.keys["owner"]])},
            )
            previous = (
                db.execute(
                    text(
                        "SELECT * FROM classsync_scheduling.classroom_requests "
                        "WHERE tenant_id=:tenant AND owner_uid=:owner AND idempotency_key=:key"
                    ),
                    {**p.keys, "key": key},
                )
                .mappings()
                .first()
            )
            if previous:
                if previous["input_hash"] != fingerprint:
                    raise HTTPException(409, "This submission key belongs to another request")
                return self.summary(previous)
            count = db.scalar(
                text(
                    "SELECT count(*) FROM classsync_scheduling.classroom_requests "
                    "WHERE tenant_id=:tenant AND owner_uid=:owner "
                    "AND created_at>transaction_timestamp()-interval '15 minutes'"
                ),
                p.keys,
            )
            if count >= 8:
                raise HTTPException(429, "Too many requests. Try again later.")
            options = self.options_in(
                db, claims, str(body.period_id), body.class_date, body.occurrence_id
            )
            if options["publication_id"] != str(body.publication_id):
                raise HTTPException(409, "The timetable changed. Review your class again.")
            room = next(
                (item for item in options["rooms"] if item["id"] == body.proposed_room_id), None
            )
            if room is None:
                if body.proposed_room_id in excluded_space_ids():
                    raise HTTPException(422, "This space is excluded from class scheduling")
                raise HTTPException(
                    422, "Choose an eligible room from this published academic scope"
                )
            if room["occupancy"] == "restricted":
                raise HTTPException(
                    409, "That room is reserved or restricted at this class time. Choose another."
                )
            if room["occupancy"] != "available":
                raise HTTPException(
                    409, "That room is occupied at this class time. Choose another room."
                )
            context = {
                "class": options["class"],
                "proposed_room": room,
                "original_date": date.fromisoformat(
                    body.occurrence_id.rsplit(":", 1)[-1]
                ).isoformat(),
            }
            row = (
                db.execute(
                    text(
                        "INSERT INTO classsync_scheduling.classroom_requests "
                        "(tenant_id,id,owner_uid,faculty_id,period_id,publication_id,occurrence_id,"
                        "proposed_room_id,reason,context,idempotency_key,input_hash) VALUES "
                        "(:tenant,:id,:owner,:faculty,:period,:publication,:occurrence,:room,:reason,"
                        "CAST(:context AS jsonb),:key,:hash) RETURNING *"
                    ),
                    {
                        **p.keys,
                        "id": str(uuid4()),
                        "faculty": claims["faculty_id"],
                        "period": str(body.period_id),
                        "publication": str(body.publication_id),
                        "occurrence": body.occurrence_id,
                        "room": body.proposed_room_id,
                        "reason": body.reason,
                        "context": json.dumps(context),
                        "key": key,
                        "hash": fingerprint,
                    },
                )
                .mappings()
                .one()
            )
            return self.summary(row)

    def list(self, claims, request_id=None):
        role = claims["role"]
        with self.publication.session(role=role, record_id=claims.get("faculty_id")) as db:
            rows = (
                db.execute(
                    text(
                        "SELECT r.*,v.draft_id FROM classsync_scheduling.classroom_requests r "
                        "JOIN classsync_scheduling.published_versions v ON v.tenant_id=r.tenant_id "
                        "AND v.dataset=r.dataset AND v.id=r.publication_id "
                        "WHERE r.tenant_id=:tenant "
                        + (
                            "AND r.owner_uid=:owner AND r.faculty_id=:faculty "
                            if role == "teacher"
                            else ""
                        )
                        + ("AND r.id=:id " if request_id else "")
                        + "ORDER BY r.created_at DESC LIMIT 100"
                    ),
                    {
                        **self.publication.keys,
                        "id": str(request_id),
                        "faculty": claims.get("faculty_id"),
                    },
                )
                .mappings()
                .all()
            )
            if request_id and not rows:
                raise HTTPException(404, "This request is unavailable")
            return [
                {
                    **self.summary(row),
                    **({"draft_id": row["draft_id"]} if role == "administrator" else {}),
                }
                for row in rows
            ]

    def request_row(self, db, request_id, *, lock):
        p = self.publication
        row = (
            db.execute(
                text(
                    "SELECT * FROM classsync_scheduling.classroom_requests "
                    "WHERE tenant_id=:tenant AND id=:id" + (" FOR UPDATE" if lock else "")
                ),
                {**p.keys, "id": str(request_id)},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise HTTPException(404, "This request is unavailable")
        return row

    def candidate(self, db, row, *, today=None):
        """Build the publication command that applies this request to the current head.

        Raises StaleRequest when the class or publication owner no longer matches.
        """
        p = self.publication
        tenant, period = p.keys["tenant"], row["period_id"]
        versions = p.rows(db, tenant, "institutional", period)
        revision = p.head(db, tenant, "institutional", period)
        if not versions or versions[-1]["revision"] != revision:
            raise StaleRequest("No current published timetable exists for this period.")
        owner = db.scalar(
            text(
                "SELECT owner_uid FROM classsync_scheduling.publication_heads "
                "WHERE tenant_id=:tenant AND dataset='institutional' AND period_id=:period"
            ),
            {"tenant": tenant, "period": period},
        )
        if owner != p.principal.uid:
            raise DraftError(
                409,
                "publication_owner_conflict",
                "Only the Administrator who owns the published timetable can approve "
                "classroom changes.",
            )
        original = row["context"]["class"]
        day = date.fromisoformat(original["date"])
        if day < (today or datetime.now(ZONE).date()):
            raise StaleRequest("This class date has passed.")
        viewer = {"role": "administrator"}
        current = p.project(db, tenant, "institutional", period, day, day, viewer)
        event = next(
            (item for item in current["occurrences"] if item["id"] == row["occurrence_id"]), None
        )
        if (
            not event
            or event["teacher"]["id"] != row["faculty_id"]
            or any(event[key] != original[key] for key in ("date", "starts_at", "ends_at"))
        ):
            raise StaleRequest("The class changed since this request was submitted.")
        if event["room"]["id"] not in {original["room"]["id"], row["proposed_room_id"]}:
            raise StaleRequest("The class was moved to another room since this request.")
        if event["room"]["id"] == row["proposed_room_id"]:
            raise StaleRequest("The class is already published in the proposed room.")
        latest = versions[-1]
        calendar = request_exception(
            p.decode(latest)["calendar"], row["context"], row["proposed_room_id"]
        )
        snapshot = p.academic.snapshot_in(db, period)
        return PublicationCommand(
            draft_id=latest["draft_id"],
            source="administrator",
            dataset="institutional",
            expected_version=revision,
            expected_academic_revision=snapshot.period.revision,
            idempotency_key=f"classroom-request:{row['id']}:{row['revision']}",
            calendar=calendar,
        )

    def check_candidate(self, db, row):
        """Run every hard publication check for the proposed change, without writing."""
        p = self.publication
        command = self.candidate(db, row)
        if row["proposed_room_id"] not in schedulable_space_ids():
            raise DraftError(422, "room_excluded", "This space is excluded from class scheduling.")
        original = row["context"]["class"]
        occupied, restricted = p.occupancy_in(
            db,
            "institutional",
            datetime.fromisoformat(original["starts_at"]),
            datetime.fromisoformat(original["ends_at"]),
            restrictions=True,
        )
        if row["proposed_room_id"] in restricted:
            raise DraftError(422, "room_restricted", "The proposed room is reserved at this time.")
        if row["proposed_room_id"] in occupied:
            raise DraftError(
                422, "room_occupied", "The proposed room is now occupied at this class time."
            )
        return command

    def preflight(self, request_id):
        p = self.publication
        with p.session() as db:
            row = self.request_row(db, request_id, lock=False)
            if row["status"] != "pending":
                return {"state": "decided", "status": row["status"], "reasons": []}
            warnings = self.locked_warnings(db, row)
            try:
                command = self.check_candidate(db, row)
                report = p.publish_in(db, command, commit=False)
            except StaleRequest as error:
                return {"state": "stale", "reasons": [str(error)], "warnings": warnings}
            except DraftError as error:
                if error.status >= 500:
                    raise
                return {
                    "state": "conflict",
                    "code": error.code,
                    "reasons": [str(error)],
                    "warnings": warnings,
                }
            return {"state": "clear", "reasons": [], "review": report, "warnings": warnings}

    def locked_warnings(self, db, row):
        """An Administrator-pinned session may still get a one-date room swap, knowingly."""
        p = self.publication
        rows = p.rows(db, p.keys["tenant"], "institutional", row["period_id"])
        if not rows:
            return []
        assignment = row["occurrence_id"].rsplit(":", 1)[0]
        locked = p.decode(rows[-1])["draft"].input_snapshot.locked_assignments
        if any(item.id == assignment for item in locked):
            return [{
                "code": "locked_assignment",
                "message": "This class is a locked session. Approving changes its room on "
                "this date only; regeneration keeps the locked placement.",
            }]
        return []

    def transition(self, db, request_id, status, note, version):
        p = self.publication
        return (
            db.execute(
                text(
                    "UPDATE classsync_scheduling.classroom_requests "
                    "SET status=:status,revision=revision+1,decided_by=CASE "
                    "WHEN :status='fulfilled' THEN decided_by ELSE :owner END,"
                    "fulfilled_by=CASE WHEN :status='fulfilled' "
                    "THEN :owner ELSE NULL END,decision_note=:note,"
                    "fulfilled_version=:version,updated_at=transaction_timestamp() "
                    "WHERE tenant_id=:tenant AND id=:id RETURNING *"
                ),
                {
                    **p.keys,
                    "id": str(request_id),
                    "status": status,
                    "note": note,
                    "version": version,
                },
            )
            .mappings()
            .one()
        )

    def approve_in(self, db, row, request_id, note):
        """Re-validate and publish the change, then approve and fulfil, in one transaction."""
        try:
            command = self.check_candidate(db, row)
            receipt = self.publication.publish_in(db, command, commit=True)
        except StaleRequest as error:
            raise DraftError(409, "request_stale", str(error)) from error
        except DraftError as error:
            if error.status >= 500:
                raise
            # Raising here rolls back the whole transaction: no version, no status change.
            raise DraftError(409, error.code, str(error)) from error
        self.transition(db, request_id, "approved", note, None)
        return self.transition(db, request_id, "fulfilled", note, receipt["id"])

    def decide(self, claims, request_id, body, *, fulfill=False):
        p = self.publication
        with p.session(dataset="institutional") as db:
            row = self.request_row(db, request_id, lock=True)
            target = "fulfilled" if fulfill else body.decision
            if (
                not fulfill
                and body.expected_revision + 2 == row["revision"]
                and row["status"] == "fulfilled"
                and body.decision == "approved"
                and row["decision_note"] == body.note
            ):
                # A retried approval whose response was lost returns the recorded result.
                return self.summary(row)
            if row["revision"] != body.expected_revision:
                raise HTTPException(409, "This request changed. Reload before deciding.")
            if row["status"] != ("approved" if fulfill else "pending"):
                raise HTTPException(409, "This request was already decided")
            if target == "approved":
                return self.summary(self.approve_in(db, row, request_id, body.note))
            if fulfill:
                day = date.fromisoformat(row["context"]["class"]["date"])
                current = p.project(
                    db,
                    p.keys["tenant"],
                    "institutional",
                    row["period_id"],
                    day,
                    day,
                    {"role": "administrator"},
                )
                event = next(
                    (item for item in current["occurrences"] if item["id"] == row["occurrence_id"]),
                    None,
                )
                original = row["context"]["class"]
                if (
                    not event
                    or event["room"]["id"] != row["proposed_room_id"]
                    or event["teacher"]["id"] != row["faculty_id"]
                    or any(event[key] != original[key] for key in ("date", "starts_at", "ends_at"))
                ):
                    raise HTTPException(409, "Publish the reviewed classroom change first")
            result = self.transition(
                db,
                request_id,
                target,
                row["decision_note"] if fulfill else body.note,
                event["version"] if fulfill else None,
            )
            return self.summary(result)


@router.get("")
def list_requests(request: Request):
    repo, claims = repository(request)
    return {"requests": repo.list(claims)}


@router.get("/options")
def options(request: Request, period_id: UUID, class_date: date, occurrence_id: str):
    if len(occurrence_id) > 200:
        raise HTTPException(422, "Invalid class reference")
    repo, claims = repository(request, teacher=True)
    return repo.options(claims, str(period_id), class_date, occurrence_id)


@router.post("", status_code=201)
def create(body: RequestInput, request: Request):
    repo, claims = repository(request, teacher=True)
    return repo.create(claims, body)


@router.get("/{request_id}")
def read(request_id: UUID, request: Request):
    repo, claims = repository(request)
    return repo.list(claims, request_id)[0]


@router.get("/{request_id}/preflight")
def preflight(request_id: UUID, request: Request):
    repo, _ = repository(request, admin=True)
    return repo.preflight(request_id)


@router.post("/{request_id}/decision")
def decide(request_id: UUID, body: Decision, request: Request):
    repo, claims = repository(request, admin=True)
    return repo.decide(claims, request_id, body)


@router.post("/{request_id}/fulfill")
def fulfill(request_id: UUID, body: Fulfill, request: Request):
    repo, claims = repository(request, admin=True)
    return repo.decide(claims, request_id, body, fulfill=True)

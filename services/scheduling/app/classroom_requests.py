"""Requests from current teaching assignments; validated publication remains authoritative."""

import json
from datetime import date
from typing import Literal
from uuid import UUID, uuid4

from classync_contracts.models import UserRole
from classync_contracts.request_authorization import request_identity
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from .draft_rules import digest, encode
from .postgres_publication_repository import PostgresPublicationRepository
from .publication_api import scoped_repo, settings_only
from .readiness import eligible_room

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
        rooms = [
            {"id": room.id, "name": room.name, "building": room.building, "floor": room.floor}
            for room in source.rooms
            if room.id in offering.eligible_room_ids
            and eligible_room(room, offering, section.program_id)
            and room.id != event["room"]["id"]
        ]
        return {
            "publication_id": rows[-1]["id"],
            "class": event,
            "rooms": rooms,
            "availability_note": "Proposals require review and validated publication.",
        }

    def options(self, claims, period, class_date, occurrence):
        with self.publication.session(role="teacher", record_id=claims["faculty_id"]) as db:
            return self.options_in(db, claims, period, class_date, occurrence)

    def create(self, claims, body):
        p, key = self.publication, str(body.idempotency_key)
        fingerprint = digest(encode(body.model_dump(mode="json")))
        with p.session(role="teacher", record_id=claims["faculty_id"]) as db:
            db.execute(
                text(
                    "SELECT uid FROM classsync_identity.memberships "
                    "WHERE tenant_id=:tenant AND uid=:owner FOR UPDATE"
                ),
                p.keys,
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
                raise HTTPException(
                    422, "Choose an eligible room from this published academic scope"
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

    def decide(self, claims, request_id, body, *, fulfill=False):
        p = self.publication
        with p.session(dataset="institutional") as db:
            row = (
                db.execute(
                    text(
                        "SELECT * FROM classsync_scheduling.classroom_requests "
                        "WHERE tenant_id=:tenant AND id=:id FOR UPDATE"
                    ),
                    {**p.keys, "id": str(request_id)},
                )
                .mappings()
                .first()
            )
            if row is None:
                raise HTTPException(404, "This request is unavailable")
            if row["revision"] != body.expected_revision:
                raise HTTPException(409, "This request changed. Reload before deciding.")
            target = "fulfilled" if fulfill else body.decision
            if row["status"] != ("approved" if fulfill else "pending"):
                raise HTTPException(409, "This request was already decided")
            versions = p.rows(db, p.keys["tenant"], "institutional", row["period_id"])
            latest = versions[-1] if versions else None
            if target == "approved" and (not latest or latest["id"] != row["publication_id"]):
                raise HTTPException(409, "The timetable changed. Ask for a new request.")
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
            result = (
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
                        "status": target,
                        "note": row["decision_note"] if fulfill else body.note,
                        "version": event["version"] if fulfill else None,
                    },
                )
                .mappings()
                .one()
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


@router.post("/{request_id}/decision")
def decide(request_id: UUID, body: Decision, request: Request):
    repo, claims = repository(request, admin=True)
    return repo.decide(claims, request_id, body)


@router.post("/{request_id}/fulfill")
def fulfill(request_id: UUID, body: Fulfill, request: Request):
    repo, claims = repository(request, admin=True)
    return repo.decide(claims, request_id, body, fulfill=True)

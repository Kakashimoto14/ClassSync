"""Teacher facility issue reports and Administrator triage (migration 0030).

A report never changes a timetable or a room. Administrators change its status only through
the database transition function, which re-checks authority and the expected revision.
"""

from datetime import date
from typing import Literal
from uuid import UUID

from classync_contracts.models import UserRole
from classync_contracts.request_authorization import request_identity
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from .catalog import schedulable_space_ids
from .draft_rules import DraftError, encode
from .postgres_publication_repository import PostgresPublicationRepository
from .publication_api import scoped_repo, settings_only

router = APIRouter(prefix="/api/v1/timetables/issues")

TRANSITION_ERRORS = {
    "42501": (403, "issue_forbidden", "Administrator access required."),
    "CS400": (
        422,
        "issue_input",
        "Add a note of at least 3 characters, and link only an active restriction of this room.",
    ),
    "CS404": (404, "issue_not_found", "This report is unavailable."),
    "CS409": (409, "issue_stale", "This report changed. Reload before updating it."),
    "CS422": (409, "issue_transition", "This status change is not allowed."),
}


class IssueInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    # Chosen by the client so that a repeated submission cannot create a second report.
    id: UUID
    room_id: str = Field(min_length=1, max_length=80)
    category: Literal["equipment", "electrical", "furniture", "cleanliness", "safety", "other"]
    description: str = Field(min_length=3, max_length=2000)
    period_id: UUID | None = None
    occurrence_id: str | None = Field(default=None, min_length=1, max_length=200)
    occurrence_date: date | None = None

    @model_validator(mode="after")
    def whole_class_reference(self):
        given = [self.period_id, self.occurrence_id, self.occurrence_date]
        if any(item is not None for item in given) and any(item is None for item in given):
            raise ValueError("Send the period, class and date together, or none of them")
        return self


class Transition(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_revision: int = Field(ge=1)
    status: Literal["in_progress", "resolved", "dismissed"]
    note: str | None = Field(default=None, max_length=1000)
    linked_restriction_id: str | None = Field(default=None, min_length=1, max_length=80)


class FacilityIssues:
    def __init__(self, publication):
        self.publication = publication

    @staticmethod
    def summary(row):
        return {
            "id": str(row["id"]),
            **{
                key: row[key]
                for key in (
                    "room_id", "occurrence_id", "category", "description", "status",
                    "revision", "resolution_note", "linked_restriction_id",
                )
            },
            "occurrence_date": row["occurrence_date"] and row["occurrence_date"].isoformat(),
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
        }

    def own_class(self, db, claims, body):
        """The referenced class must be in this Teacher's current published timetable."""
        p, period = self.publication, str(body.period_id)
        rows = p.rows(db, p.keys["tenant"], "institutional", period)
        if not rows or rows[-1]["revision"] != p.head(
            db, p.keys["tenant"], "institutional", period
        ):
            raise HTTPException(403, "Choose one of your current published classes")
        day = body.occurrence_date
        projected = p.project(db, p.keys["tenant"], "institutional", period, day, day, claims)
        if not any(item["id"] == body.occurrence_id for item in projected["occurrences"]):
            raise HTTPException(403, "Choose one of your current published classes")

    def create(self, claims, body):
        p, key = self.publication, str(body.id)
        with p.session(role="teacher", record_id=claims["faculty_id"]) as db:
            # One Teacher's submissions run one at a time. No row lock on identity tables.
            db.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                {"key": encode(["classsync-issue", p.keys["tenant"], p.keys["owner"]])},
            )
            previous = (
                db.execute(
                    text(
                        "SELECT * FROM classsync_scheduling.facility_issue_reports "
                        "WHERE tenant_id=:tenant AND reporter_uid=:owner AND id=:id"
                    ),
                    {**p.keys, "id": key},
                )
                .mappings()
                .first()
            )
            if previous:
                same = (
                    previous["room_id"],
                    previous["category"],
                    previous["description"],
                    previous["occurrence_id"],
                ) == (body.room_id, body.category, body.description, body.occurrence_id)
                if not same:
                    raise HTTPException(409, "This submission key belongs to another report")
                return self.summary(previous)
            if body.room_id not in schedulable_space_ids():
                raise HTTPException(422, "Choose one of the schedulable campus rooms")
            recent = db.scalar(
                text(
                    "SELECT count(*) FROM classsync_scheduling.facility_issue_reports "
                    "WHERE tenant_id=:tenant AND reporter_uid=:owner "
                    "AND created_at>transaction_timestamp()-interval '15 minutes'"
                ),
                p.keys,
            )
            if recent >= 8:
                raise HTTPException(429, "Too many reports. Try again later.")
            if body.occurrence_id is not None:
                self.own_class(db, claims, body)
            row = (
                db.execute(
                    text(
                        "INSERT INTO classsync_scheduling.facility_issue_reports "
                        "(tenant_id,id,reporter_uid,room_id,occurrence_id,occurrence_date,"
                        "category,description) VALUES (:tenant,:id,:owner,:room,:occurrence,"
                        ":day,:category,:description) RETURNING *"
                    ),
                    {
                        **p.keys,
                        "id": key,
                        "room": body.room_id,
                        "occurrence": body.occurrence_id,
                        "day": body.occurrence_date,
                        "category": body.category,
                        "description": body.description,
                    },
                )
                .mappings()
                .one()
            )
            return self.summary(row)

    def list(self, claims):
        p, role = self.publication, claims["role"]
        with p.session(role=role, record_id=claims.get("faculty_id")) as db:
            rows = (
                db.execute(
                    text(
                        "SELECT * FROM classsync_scheduling.facility_issue_reports "
                        "WHERE tenant_id=:tenant "
                        + ("AND reporter_uid=:owner " if role == "teacher" else "")
                        + "ORDER BY (status IN ('open','in_progress')) DESC,updated_at DESC,id "
                        "LIMIT 100"
                    ),
                    p.keys,
                )
                .mappings()
                .all()
            )
            history = {}
            if rows:
                events = db.execute(
                    text(
                        "SELECT issue_id,revision,from_status,to_status,note,created_at "
                        "FROM classsync_scheduling.facility_issue_events "
                        "WHERE tenant_id=:tenant AND issue_id=ANY(CAST(:ids AS uuid[])) "
                        "ORDER BY issue_id,revision"
                    ),
                    {**p.keys, "ids": [str(row["id"]) for row in rows]},
                ).mappings()
                for event in events:
                    history.setdefault(str(event["issue_id"]), []).append(
                        {
                            **{k: event[k] for k in ("revision", "from_status", "to_status",
                                                     "note")},
                            "created_at": event["created_at"].isoformat(),
                        }
                    )
            return [
                {**self.summary(row), "history": history.get(str(row["id"]), [])} for row in rows
            ]

    def transition(self, issue_id, body):
        with self.publication.session() as db:
            try:
                row = (
                    db.execute(
                        text(
                            "SELECT * FROM classsync_scheduling.transition_facility_issue("
                            "CAST(:id AS uuid),CAST(:revision AS integer),CAST(:status AS text),"
                            "CAST(:note AS text),CAST(:restriction AS text))"
                        ),
                        {
                            "id": str(issue_id),
                            "revision": body.expected_revision,
                            "status": body.status,
                            "note": body.note,
                            "restriction": body.linked_restriction_id,
                        },
                    )
                    .mappings()
                    .one()
                )
            except DBAPIError as error:
                known = TRANSITION_ERRORS.get(getattr(error.orig, "sqlstate", None))
                if known is None:
                    raise
                raise DraftError(*known) from error
            return self.summary(row)


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
        raise HTTPException(503, "Connected issue reports are unavailable")
    _, publication = scoped_repo(request, claims)
    if not isinstance(publication, PostgresPublicationRepository):
        raise HTTPException(503, "Connected issue reports are unavailable")
    return FacilityIssues(publication), claims


@router.get("")
def list_issues(request: Request):
    repo, claims = repository(request)
    return {"issues": repo.list(claims)}


@router.post("", status_code=201)
def create_issue(body: IssueInput, request: Request):
    repo, claims = repository(request, teacher=True)
    return repo.create(claims, body)


@router.post("/{issue_id}/transition")
def transition_issue(issue_id: UUID, body: Transition, request: Request):
    repo, _ = repository(request, admin=True)
    return repo.transition(issue_id, body)

"""Current-member notices on the existing PostgreSQL pool; no timetable authority."""

from contextlib import contextmanager
from typing import Literal
from uuid import UUID, uuid4

from classync_contracts.request_authorization import request_identity
from classync_persistence.database import transaction
from classync_persistence.memberships import identity_context
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

Role = Literal["student", "teacher", "administrator"]


class NoticeInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=3000)
    audience: list[Role] = Field(min_length=1, max_length=3)

    @field_validator("audience")
    @classmethod
    def unique_audience(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Choose each audience once")
        return value


class NoticeEdit(NoticeInput):
    expected_revision: int = Field(strict=True, ge=1)


class Announcements:
    def __init__(self, engine, *, tenant, project):
        self.engine, self.tenant, self.project = engine, tenant, project

    @contextmanager
    def session(self, claims, *, write=False):
        if claims.get("tenant_id") != self.tenant:
            raise HTTPException(403, "Current university access required")
        try:
            with transaction(self.engine) as db:
                identity_context(db, tenant_id=self.tenant, uid=claims["uid"])
                db.execute(
                    text(
                        "SELECT set_config('classsync.role',:role,true), "
                        "set_config('classsync.project_id',:project,true)"
                    ),
                    {"role": claims["role"], "project": self.project},
                )
                if write:
                    # One author's writes run one at a time, which also bounds the create rate.
                    # No row lock: FOR SHARE needs UPDATE on memberships, which the runtime
                    # role does not have. Row-level security re-checks membership on the write.
                    db.execute(
                        text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                        {"key": f"notice:{self.tenant}:{claims['uid']}"},
                    )
                member = db.scalar(
                    text("""SELECT 1 FROM classsync_identity.memberships m
                    JOIN classsync_identity.tenants t ON t.id=m.tenant_id
                    WHERE m.tenant_id=:tenant AND m.uid=:uid AND m.state='active'
                    AND :role=ANY(m.roles) AND t.firebase_project_id=:project"""),
                    self.params(claims, project=self.project, role=claims["role"]),
                )
                if not member:
                    raise HTTPException(403, "Current university access required")
                yield db
        except SQLAlchemyError as error:
            raise HTTPException(503, "Announcements unavailable; no change confirmed") from error

    def params(self, claims, **extra):
        return {"tenant": self.tenant, "uid": claims["uid"], **extra}

    @staticmethod
    def summary(row):
        return {
            key: str(row[key]) if key == "id" else row[key]
            for key in ("id", "title", "body", "audience", "revision", "created_at", "updated_at")
        }

    def list(self, claims):
        with self.session(claims) as db:
            rows = db.execute(
                text("""SELECT * FROM classsync_academic.announcements
                WHERE tenant_id=:tenant AND NOT archived
                ORDER BY created_at DESC,id LIMIT 50"""),
                self.params(claims),
            ).mappings()
            return {"announcements": [self.summary(row) for row in rows]}

    def create(self, claims, body):
        with self.session(claims, write=True) as db:
            # The rate bound includes archived notices.
            count = db.scalar(
                text("""SELECT count(*) FROM classsync_academic.announcements
                WHERE tenant_id=:tenant AND created_by=:uid
                AND created_at>transaction_timestamp()-interval '1 hour'"""),
                self.params(claims),
            )
            if count >= 20:
                raise HTTPException(429, "Too many announcements; try again later")
            row = (
                db.execute(
                    text("""INSERT INTO classsync_academic.announcements
                (tenant_id,id,title,body,audience,created_by,updated_by)
                VALUES(:tenant,:id,:title,:body,CAST(:audience AS text[]),:uid,:uid)
                RETURNING *"""),
                    self.params(claims, id=str(uuid4()), **body.model_dump()),
                )
                .mappings()
                .one()
            )
            return self.summary(row)

    def change(self, claims, notice_id, revision, body=None):
        with self.session(claims, write=True) as db:
            values = self.params(claims, id=str(notice_id), revision=revision)
            update = (
                "archived=true"
                if body is None
                else ("title=:title,body=:body,audience=CAST(:audience AS text[])")
            )
            if body is not None:
                values.update(body.model_dump(exclude={"expected_revision"}))
            row = (
                db.execute(
                    text(f"""UPDATE classsync_academic.announcements SET {update},
                revision=revision+1,updated_by=:uid WHERE tenant_id=:tenant AND id=:id
                AND revision=:revision AND NOT archived RETURNING *"""),
                    values,
                )
                .mappings()
                .first()
            )
            if row is None:
                raise HTTPException(
                    409, "Announcement changed or is unavailable. Refresh and retry."
                )
            return self.summary(row)


def announcement_router(settings):
    router = APIRouter(prefix="/api/v1/community/announcements", tags=["Announcements"])

    def context(request, write=False):
        claims = request_identity(request, settings())
        if write and claims["role"] != "administrator":
            raise HTTPException(403, "Administrator access required")
        repo = getattr(request.app.state, "announcements_repository", None)
        if repo is None:
            raise HTTPException(503, "Announcements are unavailable")
        return repo, claims

    @router.get("")
    def read(request: Request):
        repo, claims = context(request)
        return {"data": repo.list(claims)}

    @router.post("", status_code=201)
    def create(body: NoticeInput, request: Request):
        repo, claims = context(request, True)
        return {"data": repo.create(claims, body)}

    @router.patch("/{notice_id}")
    def edit(notice_id: UUID, body: NoticeEdit, request: Request):
        repo, claims = context(request, True)
        return {"data": repo.change(claims, notice_id, body.expected_revision, body)}

    @router.delete("/{notice_id}")
    def archive(notice_id: UUID, request: Request, expected_revision: int = Query(ge=1)):
        repo, claims = context(request, True)
        return {"data": repo.change(claims, notice_id, expected_revision)}

    return router

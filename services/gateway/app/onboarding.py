"""Narrow pending-user endpoints; uploaded evidence never confers a role."""

import re
import time
from collections import OrderedDict, deque
from threading import Lock
from uuid import UUID

from classync_contracts.request_authorization import request_principal
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class StudentClaim(Input):
    student_id: str = Field(min_length=1, max_length=128)


class ClaimDecision(Input):
    approve: bool = Field(strict=True)
    verification_reference: str = Field(min_length=1, max_length=500)


class FacultyInvitation(Input):
    faculty_id: str = Field(min_length=1, max_length=128)
    email: str = Field(min_length=3, max_length=320)
    expires_in_hours: int = Field(default=48, strict=True, ge=1, le=168)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value


class InvitationAccept(Input):
    token: str = Field(min_length=40, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


class RevokeMembership(Input):
    expected_revision: int = Field(strict=True, ge=1)


def onboarding_router(settings):
    router = APIRouter(prefix="/api/v1/auth", tags=["Account onboarding"])
    buckets, lock = OrderedDict(), Lock()

    def context(request, *, verified=True, privileged=False, write=False):
        principal = request_principal(request, settings())
        if verified and (not principal.email_verified or not principal.email):
            raise HTTPException(403, "Verify your email before continuing")
        if privileged and (
            principal.auth_time is None or not 0 <= time.time() - principal.auth_time <= 600
        ):
            raise HTTPException(403, "Sign in again before managing university accounts")
        if write:
            now = time.monotonic()
            with lock:
                # Bounded per-process defense. Distributed deployments must also
                # enforce the documented edge limit; no unbounded UID cache.
                bucket = buckets.setdefault(principal.uid, deque())
                buckets.move_to_end(principal.uid)
                while bucket and bucket[0] <= now - 60:
                    bucket.popleft()
                if len(bucket) >= 10:
                    raise HTTPException(
                        429,
                        "Too many account requests; try again shortly",
                        headers={"Retry-After": "60"},
                    )
                bucket.append(now)
                while len(buckets) > 4096:
                    buckets.popitem(last=False)
        repository = getattr(request.app.state, "onboarding_repository", None)
        if repository is None:
            raise HTTPException(503, "Account linking is unavailable; try again later")
        return principal, repository

    @router.get("/onboarding")
    def status(request: Request, response: Response):
        principal, repository = context(request, verified=False)
        response.headers["Cache-Control"] = "no-store"
        return {"data": repository.status(principal)}

    @router.post("/student-claims", status_code=201)
    def submit_claim(body: StudentClaim, request: Request):
        principal, repository = context(request, write=True)
        return {"data": repository.submit_claim(principal, body.student_id)}

    @router.get("/student-claims")
    def claims(request: Request, response: Response):
        principal, repository = context(request, privileged=True)
        response.headers["Cache-Control"] = "no-store"
        return {"data": repository.claims(principal)}

    @router.get("/faculty-records")
    def faculty_records(request: Request, response: Response):
        principal, repository = context(request, privileged=True)
        response.headers["Cache-Control"] = "no-store"
        return {"data": repository.faculty_records(principal)}

    @router.patch("/student-claims/{uid}")
    def decide(uid: str, body: ClaimDecision, request: Request):
        if not 1 <= len(uid) <= 128:
            raise HTTPException(422, "Invalid account reference")
        principal, repository = context(request, privileged=True, write=True)
        return {
            "data": repository.decide(
                principal, uid, approve=body.approve, reference=body.verification_reference
            )
        }

    @router.post("/faculty-invitations", status_code=201)
    def invite(body: FacultyInvitation, request: Request, response: Response):
        principal, repository = context(request, privileged=True, write=True)
        response.headers["Cache-Control"] = "no-store"
        return {
            "data": repository.invite(principal, body.faculty_id, body.email, body.expires_in_hours)
        }

    @router.post("/faculty-invitations/accept")
    def accept(body: InvitationAccept, request: Request):
        principal, repository = context(request, write=True)
        return {"data": repository.accept(principal, body.token)}

    @router.delete("/faculty-invitations/{invitation_id}")
    def revoke_invite(invitation_id: UUID, request: Request):
        principal, repository = context(request, privileged=True, write=True)
        return {"data": repository.revoke_invite(principal, str(invitation_id))}

    @router.patch("/memberships/{uid}/revoke")
    def revoke_membership(uid: str, body: RevokeMembership, request: Request):
        if not 1 <= len(uid) <= 128:
            raise HTTPException(422, "Invalid account reference")
        principal, repository = context(request, privileged=True, write=True)
        return {"data": repository.revoke_membership(principal, uid, body.expected_revision)}

    return router

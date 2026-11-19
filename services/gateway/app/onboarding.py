"""Narrow pending-user endpoints; uploaded evidence never confers a role."""

import hmac
import re
import secrets
import time
from collections import OrderedDict, deque
from threading import Lock
from uuid import UUID, uuid4

import httpx
from classync_contracts.cloud_run import service_headers
from classync_contracts.firebase import initialize_firebase
from classync_contracts.request_authorization import request_principal
from fastapi import APIRouter, HTTPException, Request, Response
from firebase_admin import auth as firebase_auth
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.concurrency import run_in_threadpool

from .turnstile import verify_turnstile_token

STUDENT_VERIFICATION_ERROR = (
    "Unable to sign in wth Google. Use the email registered in your student record. "
    "If you need assistance, contact the Registrar"
)
STUDENT_LOGIN_ERROR = "Invalid student number or password."
STUDENT_ID_PATTERN = r"^[0-9]{2}-[0-9]{5}$"
LOGIN_WINDOW_SECONDS = 60
LOGIN_MAX_ATTEMPTS = 5
_LOGIN_ATTEMPTS: OrderedDict[str, deque[float]] = OrderedDict()
_LOGIN_LOCK = Lock()


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class StudentClaim(Input):
    student_id: str = Field(min_length=8, max_length=8, pattern=STUDENT_ID_PATTERN)


class StudentVerificationChallenge(StudentClaim):
    turnstile_token: str = Field(min_length=1, max_length=2048)


class StudentVerification(Input):
    student_id: str = Field(min_length=8, max_length=8, pattern=STUDENT_ID_PATTERN)
    challenge_id: UUID
    code: str = Field(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")
    turnstile_token: str = Field(min_length=1, max_length=2048)


class StudentPasswordCompletion(StudentClaim):
    challenge_id: UUID
    turnstile_token: str = Field(min_length=1, max_length=2048)


class StudentPasswordLogin(Input):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    student_id: str = Field(min_length=8, max_length=8, pattern=STUDENT_ID_PATTERN)
    password: str = Field(min_length=8, max_length=128)
    turnstile_token: str = Field(min_length=1, max_length=2048)


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

    @router.post("/student-verification-challenges", status_code=202)
    async def request_student_verification(body: StudentVerificationChallenge, request: Request,
                                           response: Response):
        principal, repository = context(request, write=True)
        response.headers["Cache-Control"] = "no-store"
        config = settings()
        await verify_turnstile_token(body.turnstile_token, config)
        if not config.otp_hmac_secret or not config.notification_service_token:
            raise HTTPException(503, "Email verification is unavailable")
        challenge_id = uuid4()
        code = f"{secrets.randbelow(1_000_000):06d}"
        secret = config.otp_hmac_secret.get_secret_value().encode("utf-8")
        digest = hmac.new(
            secret,
            f"{principal.uid}\0{challenge_id}\0{code}".encode(),
            "sha256",
        ).digest()
        masked = repository.issue_student_challenge(
            principal, body.student_id, challenge_id, digest
        )
        try:
            notification_url = config.notification_service_url
            headers = await run_in_threadpool(
                service_headers, config.cloud_run_iam_enabled, notification_url,
                {"X-ClassSync-Service-Token":
                 config.notification_service_token.get_secret_value()},
            )
            async with httpx.AsyncClient(timeout=6.0, trust_env=False) as client:
                sent = await client.post(
                    notification_url + "/internal/v1/verification-email",
                    json={"email": principal.email, "code": code},
                    headers=headers,
                )
                sent.raise_for_status()
        except (httpx.HTTPError, ValueError) as error:
            repository.cancel_student_challenge(principal, challenge_id)
            raise HTTPException(503, "Email verification is unavailable") from error
        return {"data": {"challenge_id": str(challenge_id), "masked_email": masked,
                         "expires_in_seconds": 300, "resend_after_seconds": 60}}

    @router.post("/verify-student")
    async def verify_student(body: StudentVerification, request: Request, response: Response):
        principal, repository = context(request, write=True)
        response.headers["Cache-Control"] = "no-store"
        config = settings()
        await verify_turnstile_token(body.turnstile_token, config)
        if not config.otp_hmac_secret:
            raise HTTPException(503, "Email verification is unavailable")
        secret = config.otp_hmac_secret.get_secret_value().encode("utf-8")
        return {"data": repository.verify_student_challenge(
            principal, body.student_id, body.challenge_id, body.code, secret
        )}

    @router.post("/complete-student-onboarding")
    async def complete_student_onboarding(body: StudentPasswordCompletion, request: Request,
                                          response: Response):
        principal, repository = context(request, write=True)
        response.headers["Cache-Control"] = "no-store"
        config = settings()
        await verify_turnstile_token(body.turnstile_token, config)
        try:
            app = await run_in_threadpool(initialize_firebase, config)
            firebase_user = await run_in_threadpool(firebase_auth.get_user, principal.uid, app=app)
        except Exception as error:
            raise HTTPException(503, "Account service unavailable") from error
        providers = {item.provider_id for item in firebase_user.provider_data}
        if "password" not in providers or firebase_user.email != principal.email:
            raise HTTPException(403, "Set a portal password before completing student setup")
        result = repository.complete_student_onboarding(
            principal, body.student_id, body.challenge_id
        )
        return {"data": result}

    @router.post("/student-password-login")
    async def student_password_login(body: StudentPasswordLogin, request: Request,
                                     response: Response):
        response.headers["Cache-Control"] = "no-store"
        config = settings()
        await verify_turnstile_token(body.turnstile_token, config)
        limit_student_login(request)
        repository = getattr(request.app.state, "onboarding_repository", None)
        if repository is None:
            raise HTTPException(503, "Student sign-in is unavailable")
        email = repository.student_login_email(body.student_id)
        roster_match = email is not None
        if config.firebase_web_api_key is None:
            raise HTTPException(503, "Student sign-in is unavailable")
        try:
            async with httpx.AsyncClient(timeout=6.0, trust_env=False) as client:
                result = await client.post(
                    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
                    params={"key": config.firebase_web_api_key.get_secret_value()},
                    # Always make the Firebase credential request for a shaped
                    # student number. A synthetic unmatched address avoids a
                    # fast-path timing signal for missing roster IDs.
                    json={"email": email or "unmatched-student-login@student.pnm.edu.ph",
                          "password": body.password,
                          "returnSecureToken": True},
                    follow_redirects=False,
                )
            if result.status_code == 400:
                raise HTTPException(401, STUDENT_LOGIN_ERROR)
            result.raise_for_status()
            firebase_result = result.json()
            uid = firebase_result.get("localId")
            if (not roster_match or not isinstance(uid, str) or not uid
                    or firebase_result.get("email") != email
                    or not repository.student_login_membership_matches(uid, body.student_id)):
                raise HTTPException(401, STUDENT_LOGIN_ERROR)
            app = await run_in_threadpool(initialize_firebase, config)
            custom_token = await run_in_threadpool(firebase_auth.create_custom_token, uid, app=app)
            return {"data": {"custom_token": custom_token.decode("utf-8")
                              if isinstance(custom_token, bytes) else custom_token}}
        except HTTPException:
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            raise HTTPException(503, "Student sign-in is unavailable") from error

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


def limit_student_login(request):
    now = time.monotonic()
    address = request.client.host if request.client else "unknown"
    with _LOGIN_LOCK:
        bucket = _LOGIN_ATTEMPTS.setdefault(address, deque())
        _LOGIN_ATTEMPTS.move_to_end(address)
        while bucket and bucket[0] <= now - LOGIN_WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= LOGIN_MAX_ATTEMPTS:
            raise HTTPException(429, "Too many sign-in attempts. Try again shortly.",
                                headers={"Retry-After": str(LOGIN_WINDOW_SECONDS)})
        bucket.append(now)
        while len(_LOGIN_ATTEMPTS) > 4096:
            _LOGIN_ATTEMPTS.popitem(last=False)

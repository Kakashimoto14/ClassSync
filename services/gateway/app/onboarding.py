"""Narrow pending-user endpoints; uploaded evidence never confers a role."""

import hmac
import logging
import re
import secrets
import time
from collections import OrderedDict, deque
from threading import Lock
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import UUID, uuid4

import httpx
from classync_contracts.cloud_run import service_headers
from classync_contracts.email_address import normalize_email
from classync_contracts.firebase import initialize_firebase
from classync_contracts.request_authorization import request_principal
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from firebase_admin import auth as firebase_auth
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from starlette.concurrency import run_in_threadpool

from .turnstile import verify_turnstile_token

STUDENT_VERIFICATION_ERROR = (
    "Unable to verify this student record. Use the email associated with your active "
    "Registrar record, or scan your Registration Form. Contact the Registrar for help."
)
STUDENT_LOGIN_ERROR = "Invalid student number or password."
STUDENT_ID_PATTERN = r"^[0-9]{2}-[0-9]{5}$"
LOGIN_WINDOW_SECONDS = 60
LOGIN_MAX_ATTEMPTS = 5
LOGIN_ATTEMPT_BUCKET_LIMIT = 4096
EMAIL_SENDS_LIMIT = 8192
logger = logging.getLogger(__name__)
_LOGIN_ATTEMPTS: OrderedDict[tuple[str, str], deque[float]] = OrderedDict()
_LOGIN_LOCK = Lock()
_EMAIL_SENDS: OrderedDict[tuple[str, str], float] = OrderedDict()
_EMAIL_SEND_LOCK = Lock()
EMAIL_SEND_COOLDOWN_SECONDS = 30


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class StudentClaim(Input):
    student_id: str = Field(min_length=8, max_length=8, pattern=STUDENT_ID_PATTERN)


class StudentVerificationChallenge(StudentClaim):
    turnstile_token: SecretStr = Field(min_length=1, max_length=2048)


class StudentVerification(Input):
    student_id: str = Field(min_length=8, max_length=8, pattern=STUDENT_ID_PATTERN)
    challenge_id: UUID
    code: SecretStr = Field(min_length=6, max_length=6)
    turnstile_token: SecretStr = Field(min_length=1, max_length=2048)

    @field_validator("code")
    @classmethod
    def numeric_one_time_code(cls, value):
        if not re.fullmatch(r"[0-9]{6}", value.get_secret_value()):
            raise ValueError("Verification code is invalid")
        return value


class StudentPasswordCompletion(StudentClaim):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    challenge_id: UUID
    password: SecretStr = Field(min_length=12, max_length=128)
    turnstile_token: SecretStr = Field(min_length=1, max_length=2048)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value):
        validate_strong_password(value)
        return value


class StudentPasswordLogin(Input):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    student_id: str = Field(min_length=8, max_length=8, pattern=STUDENT_ID_PATTERN)
    password: SecretStr = Field(min_length=8, max_length=128)
    turnstile_token: SecretStr = Field(min_length=1, max_length=2048)


class PasswordResetRequest(Input):
    email: str = Field(min_length=3, max_length=320)
    turnstile_token: SecretStr = Field(min_length=1, max_length=2048)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        normalized = normalize_email(value)
        if not normalized:
            raise ValueError("Enter a valid email address")
        return normalized


class PasswordResetCompletion(Input):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    oob_code: SecretStr = Field(min_length=1, max_length=2048)
    password: SecretStr = Field(min_length=12, max_length=128)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value):
        validate_strong_password(value)
        return value


class GoogleSignIn(Input):
    turnstile_token: SecretStr = Field(min_length=1, max_length=2048)


class ClaimDecision(Input):
    approve: bool = Field(strict=True)
    verification_reference: str = Field(min_length=1, max_length=500)


async def _send_firebase_action_email(config, email: str, mode: str) -> None:
    try:
        firebase_app = await run_in_threadpool(initialize_firebase, config)
        action_settings = firebase_auth.ActionCodeSettings(
            url=(f"{config.classsync_web_url}/auth/action?"
                 f"{urlencode({'mode': mode})}")
        )
        generator = (
            firebase_auth.generate_password_reset_link
            if mode == "resetPassword"
            else firebase_auth.generate_email_verification_link
        )
        firebase_link = await run_in_threadpool(generator, email,
                                                 action_code_settings=action_settings,
                                                 app=firebase_app)
    except firebase_auth.UserNotFoundError:
        return
    except Exception as error:
        logger.warning(
            "firebase_action_link_generation_failed",
            extra={"failure_type": type(error).__name__},
        )
        return

    parsed_link = urlsplit(firebase_link)
    query = parse_qs(parsed_link.query)
    code = next(iter(query.get("oobCode", [])), None)
    if not code:
        nested = next(iter(query.get("link", [])), None)
        if nested:
            code = next(iter(parse_qs(urlsplit(nested).query).get("oobCode", [])), None)
    if not code or len(code) > 2048:
        logger.warning("password_reset_link_missing_action_code")
        return

    action_query = urlencode({'mode': mode, 'oobCode': code})
    action_url = f"{config.classsync_web_url}/auth/action?{action_query}"
    if not config.notification_service_token:
        logger.warning("email_action_notification_unavailable",
                       extra={"action": mode})
        return
    try:
        notification_url = config.notification_service_url
        headers = await run_in_threadpool(
            service_headers,
            config.cloud_run_iam_enabled,
            notification_url,
            {"X-ClassSync-Service-Token":
             config.notification_service_token.get_secret_value()},
        )
        async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
            sent = await client.post(
                notification_url + "/internal/v1/email-action",
                json={"email": email, "mode": mode, "action_url": action_url},
                headers=headers,
            )
            sent.raise_for_status()
    except (httpx.HTTPError, ValueError) as error:
        logger.warning(
            "email_action_notification_failed",
            extra={"failure_type": type(error).__name__},
        )


def email_cooldown_remaining(scope: str, identity: str, email: str) -> int:
    email_key = hmac.new(b"classsync-email-cooldown", email.encode("utf-8"), "sha256").hexdigest()
    key = (scope, identity + ":" + email_key)
    now = time.monotonic()
    with _EMAIL_SEND_LOCK:
        for cached_key, expires in list(_EMAIL_SENDS.items()):
            if expires <= now:
                del _EMAIL_SENDS[cached_key]
        expires = _EMAIL_SENDS.get(key, 0.0)
        remaining = max(0, int(expires - now + 0.999))
        if remaining:
            _EMAIL_SENDS.move_to_end(key)
            return remaining
        if len(_EMAIL_SENDS) >= EMAIL_SENDS_LIMIT:
            # Fail closed rather than evict an unexpired recipient cooldown.
            return EMAIL_SEND_COOLDOWN_SECONDS
        _EMAIL_SENDS[key] = now + EMAIL_SEND_COOLDOWN_SECONDS
        _EMAIL_SENDS.move_to_end(key)
    return 0


def cooldown_rejection(seconds: int) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        headers={"Retry-After": str(seconds), "Cache-Control": "no-store"},
        content={"error": {"code": "rate_limited",
                            "message": "Please wait before requesting another email.",
                            "retryAfterSeconds": seconds}},
    )


class FacultyInvitation(Input):
    faculty_id: str = Field(min_length=1, max_length=128)
    email: str = Field(min_length=3, max_length=320)
    expires_in_hours: int = Field(default=48, strict=True, ge=1, le=168)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        normalized = normalize_email(value)
        if not normalized:
            raise ValueError("Enter a valid email address")
        return normalized


class InvitationAccept(Input):
    token: SecretStr = Field(min_length=40, max_length=128)

    @field_validator("token")
    @classmethod
    def opaque_token(cls, value):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", value.get_secret_value()):
            raise ValueError("Invitation token is invalid")
        return value


class RevokeMembership(Input):
    expected_revision: int = Field(strict=True, ge=1)


def validate_strong_password(value: SecretStr) -> None:
    password = value.get_secret_value()
    if not (
        len(password) >= 12
        and re.search(r"[A-Z]", password)
        and re.search(r"[a-z]", password)
        and re.search(r"[0-9]", password)
        and re.search(r"[^A-Za-z0-9]", password)
    ):
        raise ValueError("Password does not meet the security requirements")


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

    @router.post("/request-password-reset")
    async def request_password_reset(
        body: PasswordResetRequest,
        request: Request,
        response: Response,
        background_tasks: BackgroundTasks,
    ):
        response.headers["Cache-Control"] = "no-store"
        config = settings()
        limit_email_trigger(request)
        await verify_turnstile_token(body.turnstile_token.get_secret_value(), config)
        remaining = email_cooldown_remaining("password-reset", "anonymous", body.email)
        if remaining:
            return cooldown_rejection(remaining)
        background_tasks.add_task(_send_firebase_action_email, config, body.email, "resetPassword")
        return {"data": {"accepted": True}}

    @router.post("/send-verification-email", status_code=202)
    async def send_verification_email(request: Request, response: Response,
                                     background_tasks: BackgroundTasks):
        response.headers["Cache-Control"] = "no-store"
        limit_email_trigger(request)
        principal = request_principal(request, settings())
        email = normalize_email(principal.email)
        if not email:
            raise HTTPException(403, "A valid account email is required")
        if principal.email_verified:
            return {"data": {"accepted": True, "alreadyVerified": True}}
        remaining = email_cooldown_remaining("verify-email", principal.uid, email)
        if remaining:
            return cooldown_rejection(remaining)
        background_tasks.add_task(_send_firebase_action_email, settings(), email, "verifyEmail")
        return {"data": {"accepted": True}}

    @router.post("/google-sign-in")
    async def google_sign_in(body: GoogleSignIn, request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        limit_student_login(request)
        request_principal(request, settings())
        await verify_turnstile_token(body.turnstile_token.get_secret_value(), settings())
        return {"data": {"accepted": True}}

    @router.post("/complete-password-reset")
    async def complete_password_reset(body: PasswordResetCompletion, request: Request,
                                      response: Response):
        response.headers["Cache-Control"] = "no-store"
        limit_student_login(request)
        config = settings()
        if config.firebase_web_api_key is None:
            raise HTTPException(503, "Password reset is unavailable")
        try:
            async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
                result = await client.post(
                    "https://identitytoolkit.googleapis.com/v1/accounts:resetPassword",
                    params={"key": config.firebase_web_api_key.get_secret_value()},
                    json={
                        "oobCode": body.oob_code.get_secret_value(),
                        "newPassword": body.password.get_secret_value(),
                    },
                    follow_redirects=False,
                )
            if result.status_code == 400:
                raise HTTPException(400, "This password reset link is invalid or expired")
            result.raise_for_status()
        except HTTPException:
            raise
        except (httpx.HTTPError, ValueError) as error:
            logger.warning(
                "password_reset_completion_failed",
                extra={"reason_code": "firebase_reset_unavailable",
                       "failure_type": type(error).__name__},
            )
            raise HTTPException(503, "Password reset is unavailable") from error
        return {"data": {"updated": True}}

    @router.get("/onboarding")
    def status(request: Request, response: Response):
        principal, repository = context(request, verified=False)
        response.headers["Cache-Control"] = "no-store"
        return {"data": {**repository.status(principal),
                          "verification_mode": settings().student_verification_mode}}

    @router.post("/student-claims", status_code=201)
    def submit_claim(body: StudentClaim, request: Request):
        principal, repository = context(request, write=True)
        return {"data": repository.submit_claim(principal, body.student_id)}

    @router.post("/student-verification-challenges", status_code=202)
    async def request_student_verification(body: StudentVerificationChallenge, request: Request,
                                           response: Response):
        limit_email_trigger(request)
        principal, repository = context(request, write=True)
        response.headers["Cache-Control"] = "no-store"
        config = settings()
        await verify_turnstile_token(body.turnstile_token.get_secret_value(), config)
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
        try:
            masked = repository.issue_student_challenge(
                principal, body.student_id, challenge_id, digest
            )
        except HTTPException as error:
            if error.status_code == 429:
                retry_after = max(1, int((error.headers or {}).get("Retry-After", "1")))
                return cooldown_rejection(retry_after)
            if error.status_code == 403 and config.student_verification_mode == "cor_or_roster":
                raise HTTPException(
                    403,
                    "No matching active student record was found. Scan your Registration Form "
                    "or contact the Registrar.",
                    headers={"Cache-Control": "no-store"},
                ) from error
            raise
        try:
            notification_url = config.notification_service_url
            headers = await run_in_threadpool(
                service_headers, config.cloud_run_iam_enabled, notification_url,
                {"X-ClassSync-Service-Token":
                 config.notification_service_token.get_secret_value()},
            )
            async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
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
                         "expires_in_seconds": 300, "resend_after_seconds": 30}}

    @router.post("/verify-student")
    async def verify_student(body: StudentVerification, request: Request, response: Response):
        limit_student_login(request)
        principal, repository = context(request, write=True)
        response.headers["Cache-Control"] = "no-store"
        config = settings()
        await verify_turnstile_token(body.turnstile_token.get_secret_value(), config)
        if not config.otp_hmac_secret:
            raise HTTPException(503, "Email verification is unavailable")
        secret = config.otp_hmac_secret.get_secret_value().encode("utf-8")
        return {"data": repository.verify_student_challenge(
            principal, body.student_id, body.challenge_id, body.code.get_secret_value(), secret
        )}

    @router.post("/complete-student-onboarding")
    async def complete_student_onboarding(body: StudentPasswordCompletion, request: Request,
                                          response: Response):
        limit_student_login(request)
        principal, repository = context(request, write=True, privileged=True)
        response.headers["Cache-Control"] = "no-store"
        config = settings()
        await verify_turnstile_token(body.turnstile_token.get_secret_value(), config)
        try:
            app = await run_in_threadpool(initialize_firebase, config)
            firebase_user = await run_in_threadpool(firebase_auth.get_user, principal.uid, app=app)
            providers = {item.provider_id for item in firebase_user.provider_data}
            if ("google.com" not in providers
                    or normalize_email(firebase_user.email) != normalize_email(principal.email)):
                raise HTTPException(403, "Verify your email before continuing")
            await run_in_threadpool(
                firebase_auth.update_user,
                principal.uid,
                password=body.password.get_secret_value(),
                app=app,
            )
        except HTTPException:
            raise
        except Exception as error:
            logger.warning(
                "student_password_update_failed",
                extra={"reason_code": "firebase_password_update_failed",
                       "failure_type": type(error).__name__},
            )
            raise HTTPException(503, "Account service unavailable") from error
        result = repository.complete_student_onboarding(
            principal, body.student_id, body.challenge_id
        )
        return {"data": result}

    @router.post("/student-password-login")
    async def student_password_login(body: StudentPasswordLogin, request: Request,
                                     response: Response):
        response.headers["Cache-Control"] = "no-store"
        config = settings()
        limit_student_login(request)
        await verify_turnstile_token(body.turnstile_token.get_secret_value(), config)
        repository = getattr(request.app.state, "onboarding_repository", None)
        if repository is None:
            raise HTTPException(503, "Student sign-in is unavailable")
        email = repository.student_login_email(body.student_id)
        roster_match = email is not None
        if config.firebase_web_api_key is None:
            raise HTTPException(503, "Student sign-in is unavailable")
        try:
            async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
                result = await client.post(
                    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
                    params={"key": config.firebase_web_api_key.get_secret_value()},
                    # Always make the Firebase credential request for a shaped
                    # student number. A synthetic unmatched address avoids a
                    # fast-path timing signal for missing roster IDs.
                    json={"email": email or "unmatched-student-login@example.invalid",
                          "password": body.password.get_secret_value(),
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

    @router.get("/self-verified-students")
    def self_verified_students(request: Request, response: Response):
        principal, repository = context(request, privileged=True)
        response.headers["Cache-Control"] = "no-store"
        return {"data": repository.self_verified_students(principal)}

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
        return {"data": repository.accept(principal, body.token.get_secret_value())}

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


def _limit_ip_bucket(request, scope: str):
    now = time.monotonic()
    address = request.client.host if request.client else "unknown"
    bucket_key = (address, scope)
    with _LOGIN_LOCK:
        for cached_key, attempts in list(_LOGIN_ATTEMPTS.items()):
            while attempts and attempts[0] <= now - LOGIN_WINDOW_SECONDS:
                attempts.popleft()
            if not attempts:
                del _LOGIN_ATTEMPTS[cached_key]
        bucket = _LOGIN_ATTEMPTS.get(bucket_key)
        if bucket is None:
            if len(_LOGIN_ATTEMPTS) >= LOGIN_ATTEMPT_BUCKET_LIMIT:
                evictable_key = next(
                    (
                        cached_key
                        for cached_key, attempts in _LOGIN_ATTEMPTS.items()
                        if len(attempts) < LOGIN_MAX_ATTEMPTS
                    ),
                    None,
                )
                if evictable_key is None:
                    raise HTTPException(
                        429,
                        "Too many sign-in attempts. Try again shortly.",
                        headers={"Retry-After": str(LOGIN_WINDOW_SECONDS)},
                    )
                del _LOGIN_ATTEMPTS[evictable_key]
            bucket = deque()
            _LOGIN_ATTEMPTS[bucket_key] = bucket
        _LOGIN_ATTEMPTS.move_to_end(bucket_key)
        if len(bucket) >= LOGIN_MAX_ATTEMPTS:
            raise HTTPException(429, "Too many sign-in attempts. Try again shortly.",
                                headers={"Retry-After": str(LOGIN_WINDOW_SECONDS)})
        bucket.append(now)


def limit_student_login(request):
    _limit_ip_bucket(request, request.url.path)


def limit_email_trigger(request):
    # Reset, verification, and student-code sends share one IP bucket so switching
    # endpoint paths cannot multiply a single client's email-send allowance.
    _limit_ip_bucket(request, "/api/v1/auth/email-trigger")

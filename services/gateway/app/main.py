import asyncio
import ipaddress
import json
import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx
from classync_contracts.cloud_run import service_headers
from classync_contracts.models import HealthResponse, UserRole
from classync_contracts.request_authorization import install_identity_errors, request_identity
from classync_contracts.scheduling_security import (
    SchedulingSecuritySettings,
    require_administrator,
    require_sandbox,
)
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
)
from pydantic_settings import NoDecode, SettingsConfigDict
from starlette.concurrency import run_in_threadpool

from .announcements import announcement_router
from .authorization import configured_authorization
from .coursework import coursework_router
from .onboarding import limit_student_login, onboarding_router
from .openapi import install_openapi
from .registration import registration_router
from .turnstile import verify_turnstile_token

ROOT_DIRECTORY = Path(__file__).resolve().parents[3]
logger = logging.getLogger(__name__)


class Settings(SchedulingSecuritySettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIRECTORY / ".env", extra="ignore", populate_by_name=True
    )
    academic_service_url: str = "http://127.0.0.1:8001"
    scheduling_service_url: str = "http://127.0.0.1:8002"
    notification_service_url: str = "http://127.0.0.1:8003"
    classsync_web_url: str = "http://localhost:5173"
    allow_unauthenticated_development: bool = False
    classsync_env: str = "production"
    student_verification_mode: Literal["cor_or_roster", "strict_roster"] = "cor_or_roster"
    enable_scheduling_sandbox: bool = False
    identity_database_url: SecretStr | None = None
    turnstile_secret_key: SecretStr | None = None
    otp_hmac_secret: SecretStr | None = Field(default=None, min_length=32)
    notification_service_token: SecretStr | None = Field(default=None, min_length=32)
    firebase_web_api_key: SecretStr | None = None
    identity_database_transport: Literal["verify-full", "loopback-sspi-test"] = "verify-full"
    registration_max_bytes: int = Field(default=5_000_000, ge=1024, le=10_000_000)
    registration_max_pages: int = Field(default=5, ge=1, le=8)
    registration_timeout_seconds: int = Field(default=20, ge=5, le=30)
    registration_retention_seconds: int = Field(default=900, ge=60, le=900)
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"],
        validation_alias=AliasChoices("CORS_ALLOWED_ORIGINS", "CORS_ORIGINS"),
    )
    course_cloud_enabled: bool = False
    course_storage_bucket: str = Field(default="", max_length=222)
    course_gemini_model: str = Field(default="", pattern=r"^[a-z0-9.-]{0,80}$")
    gemini_api_key: SecretStr | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def exact_origins(cls, values):
        if isinstance(values, str):
            raw = values.strip()
            if raw.startswith("["):
                values = json.loads(raw)
            else:
                values = [origin.strip() for origin in raw.split(",") if origin.strip()]
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            raise ValueError("CORS origins must be a JSON array or comma-separated origins")
        if len(values) > 20:
            raise ValueError("At most twenty explicit CORS origins are allowed")
        for value in values:
            parsed = urlsplit(value)
            if (
                parsed.scheme not in {"https", "http"}
                or not parsed.hostname
                or "*" in value
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
                or (
                    parsed.scheme == "http"
                    and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
                )
            ):
                raise ValueError("Use exact HTTPS origins or explicit loopback development origins")
            _ = parsed.port
        return values

    @field_validator("classsync_web_url")
    @classmethod
    def exact_frontend_origin(cls, value):
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or (
                parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            )
        ):
            raise ValueError("Use an HTTPS application origin")
        _ = parsed.port
        return f"{parsed.scheme}://{parsed.netloc}"


settings = Settings()
SERVICES = {
    "academic": settings.academic_service_url,
    "scheduling": settings.scheduling_service_url,
    "notification": settings.notification_service_url,
}


@asynccontextmanager
async def lifespan(application: FastAPI):
    validate_production_frontend_origin(settings)
    with configured_authorization(application, settings):
        with registration_routes.registration_store.lifecycle():
            yield


def validate_production_frontend_origin(config):
    if config.classsync_env != "production":
        return
    parsed = urlsplit(config.classsync_web_url)
    hostname = (parsed.hostname or "").lower()
    loopback = hostname == "localhost" or hostname.endswith(".localhost")
    try:
        loopback = loopback or ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        pass
    if parsed.scheme != "https" or loopback:
        raise ValueError("Production requires an HTTPS frontend origin")


app = FastAPI(title="ClassSync API Gateway", version="1.0.0", lifespan=lifespan)
install_openapi(app)
app.include_router(onboarding_router(lambda: settings))
app.include_router(announcement_router(lambda: settings))
app.include_router(coursework_router(lambda: settings))
registration_routes = registration_router(lambda: settings)
app.include_router(registration_routes)
install_identity_errors(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-ClassSync-Role"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID", str(uuid4()))
    try:
        response = await call_next(request)
    except Exception as error:
        logger.error(
            "gateway_unhandled_request_error",
            extra={
                "request_id": request.state.request_id,
                "reason_code": "unhandled_request_error",
                "failure_type": type(error).__name__,
            },
        )
        response = JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "The request could not be completed. Please try again.",
                    "requestId": request.state.request_id,
                }
            },
        )
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if settings.classsync_env == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.url.path == "/api/v1" or request.url.path.startswith("/api/v1/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content={
            "error": {
                "code": "request_rejected",
                "message": safe_public_error_message(exc.detail),
                "requestId": request.state.request_id,
            }
        },
    )


def safe_public_error_message(detail: object) -> str:
    """Avoid returning database/provider diagnostics through the public API."""
    if not isinstance(detail, str):
        return "The request could not be completed. Please try again."
    message = detail.strip()
    if (
        not message
        or len(message) > 240
        or "\n" in message
        or "\r" in message
        or re.search(
            r"https?://|neondb|classsync_[a-z0-9_]+|\b(database|table|schema|sql|"
            r"traceback|stack trace|exception)\b|^\s*[\[{]",
            message,
            flags=re.IGNORECASE,
        )
    ):
        return "The request could not be completed. Please try again."
    return message


@app.exception_handler(RequestValidationError)
async def request_validation_error(request: Request, _exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "invalid_request",
                "message": "The request could not be validated. Check the provided fields.",
                "requestId": request.state.request_id,
            }
        },
    )


def require_authenticated(request: Request) -> dict:
    return request_identity(request, settings, include_workspaces=True)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(service="gateway")


@app.get("/api/v1/health", response_model=HealthResponse)
def api_health() -> HealthResponse:
    return HealthResponse(service="gateway")


@app.get("/api/v1/auth/me")
def current_user(request: Request) -> dict:
    return {"data": require_authenticated(request)}


@app.get("/api/v1/services/{service_name}/health")
async def service_health(service_name: str, request: Request) -> dict:
    target = SERVICES.get(service_name)
    if target is None or (settings.cloud_run_iam_enabled and service_name == "notification"):
        raise HTTPException(404, "Unknown service")
    if settings.cloud_run_iam_enabled:
        await run_in_threadpool(require_administrator, request, settings)
    try:
        headers = await run_in_threadpool(service_headers, settings.cloud_run_iam_enabled, target)
        async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
            response = await client.get(f"{target}/health", headers=headers)
        response.raise_for_status()
        return {"data": response.json()}
    except (httpx.HTTPError, ValueError) as error:
        raise HTTPException(503, "Service unavailable") from error


class TurnstileInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    token: SecretStr = Field(min_length=1, max_length=2048)


@app.post("/api/v1/auth/verify-turnstile")
async def verify_turnstile(body: TurnstileInput, request: Request, response: Response) -> dict:
    """Verify a single-use Cloudflare challenge token; dev bypass is never production."""
    response.headers["Cache-Control"] = "no-store"
    limit_student_login(request)
    await verify_turnstile_token(body.token.get_secret_value(), settings)
    response = JSONResponse(content={"data": {"verified": True}})
    response.headers["Cache-Control"] = "no-store"
    return response


async def scheduling_proxy(operation: str, request: Request, sandbox: bool):
    if sandbox:
        require_sandbox(settings)
    else:
        # The general development bypass never authorizes production scheduling.
        await run_in_threadpool(require_administrator, request, settings)
    allowed = (
        ({"scenario", "catalogs", "drafts"} if sandbox else {"drafts"})
        if request.method == "GET"
        else {"generate", "validate", "readiness", "drafts"}
        if request.method == "POST"
        else set()
    )
    academic_operation = (
        (operation == "academic/drafts" and request.method in {"GET", "POST"})
        or (re.fullmatch(r"academic/drafts/[a-f0-9-]{36}", operation) and request.method == "GET")
        or (
            re.fullmatch(r"academic/[a-f0-9-]{36}/readiness", operation) and request.method == "GET"
        )
        or (
            re.fullmatch(r"academic/[a-f0-9-]{36}/generate", operation) and request.method == "POST"
        )
    )
    advisor_operation = request.method == "POST" and re.fullmatch(
        r"drafts/[a-f0-9-]{36}/(?:revisions|advisor/(?:health|conflict))", operation
    )
    if (
        not academic_operation
        and not (sandbox and request.method == "GET" and operation == "calendar-samples")
        and operation not in allowed
        and not (request.method == "GET" and operation.startswith("drafts/"))
        and not advisor_operation
    ):
        raise HTTPException(404, "Unknown scheduling operation; publication is not implemented")
    path = f"/api/v1/scheduling/{'sandbox/' if sandbox else ''}{operation}"
    return await service_proxy("scheduling", path, request)


async def service_proxy(service_name, path, request):
    body = await request.body()
    if len(body) > 2_000_000:
        raise HTTPException(413, "Input exceeds the 2 MB request limit")
    try:
        target = getattr(settings, f"{service_name}_service_url")
        headers = await run_in_threadpool(
            service_headers,
            settings.cloud_run_iam_enabled,
            target,
            forwarded_headers(request)
            | {"Content-Type": "application/json", "X-Request-ID": request.state.request_id},
        )
        async with httpx.AsyncClient(timeout=45.0, trust_env=False) as client:
            response = await client.request(
                request.method,
                target + path,
                params=request.query_params,
                content=body,
                headers=headers,
            )
        payload = response.json()
        if response.is_error:
            code, message = downstream_error(payload)
            return JSONResponse(
                status_code=response.status_code,
                content={
                    "error": {
                        "code": code,
                        "message": message,
                        "requestId": request.state.request_id,
                    }
                },
            )
        return JSONResponse(status_code=response.status_code, content={"data": payload})
    except (httpx.HTTPError, ValueError) as error:
        raise HTTPException(
            503, f"{service_name.capitalize()} service unavailable; no server confirmation received"
        ) from error


def downstream_error(payload: object) -> tuple[str, str]:
    """Return only a validated code and public-safe message from a service response."""
    code = "scheduling_rejected"
    detail = None
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            candidate_code = error.get("code")
            if isinstance(candidate_code, str) and re.fullmatch(
                r"[a-z][a-z0-9_]{0,63}", candidate_code
            ):
                code = candidate_code
            detail = error.get("message")
        elif "error" not in payload and isinstance(payload.get("detail"), str):
            detail = payload["detail"]
    return code, safe_public_error_message(detail)


def forwarded_headers(request):
    return {
        "Authorization": request.headers.get("Authorization", ""),
        **(
            {"X-ClassSync-Role": request.headers["X-ClassSync-Role"]}
            if "X-ClassSync-Role" in request.headers
            else {}
        ),
    }


@app.api_route("/api/v1/scheduling/sandbox/{operation}", methods=["GET", "POST"])
async def sandbox_scheduling(operation: str, request: Request):
    return await scheduling_proxy(operation, request, True)


@app.post("/api/v1/scheduling/{operation}")
async def scheduling_operation(operation: str, request: Request):
    return await scheduling_proxy(operation, request, False)


@app.get("/api/v1/scheduling/drafts")
async def scheduling_drafts(request: Request):
    return await scheduling_proxy("drafts", request, False)


@app.get("/api/v1/scheduling/sandbox/drafts/{draft_id}")
async def sandbox_draft_detail(draft_id: UUID, request: Request):
    return await scheduling_proxy(f"drafts/{draft_id}", request, True)


@app.get("/api/v1/scheduling/drafts/{draft_id}")
async def draft_detail(draft_id: UUID, request: Request):
    return await scheduling_proxy(f"drafts/{draft_id}", request, False)


@app.post("/api/v1/scheduling/drafts/{draft_id}/advisor/{kind}")
async def scheduling_draft_advisor(draft_id: UUID, kind: str, request: Request):
    if kind not in {"health", "conflict"}:
        raise HTTPException(404, "Scheduling advisor action not found")
    return await scheduling_proxy(f"drafts/{draft_id}/advisor/{kind}", request, False)


@app.post("/api/v1/scheduling/drafts/{draft_id}/revisions")
async def revise_scheduling_draft(draft_id: UUID, request: Request):
    return await scheduling_proxy(f"drafts/{draft_id}/revisions", request, False)


async def academic_proxy(path, request, sandbox):
    if sandbox:
        require_sandbox(settings)
    else:
        await run_in_threadpool(require_administrator, request, settings)
    return await service_proxy(
        "academic", f"/api/v1/academic/{'sandbox/' if sandbox else ''}{path}", request
    )


@app.api_route("/api/v1/academic/sandbox/periods", methods=["GET", "POST"])
async def sandbox_academic_periods(request: Request):
    return await academic_proxy("periods", request, True)


@app.get("/api/v1/academic/sandbox/curriculum-catalog")
async def sandbox_curriculum_catalog(request: Request):
    return await academic_proxy("curriculum-catalog", request, True)


@app.get("/api/v1/academic/curriculum-catalog")
async def curriculum_catalog(request: Request):
    return await academic_proxy("curriculum-catalog", request, False)


@app.post("/api/v1/academic/sandbox/fixtures")
async def academic_fixture(request: Request):
    return await academic_proxy("fixtures", request, True)


@app.get("/api/v1/scheduling/sandbox/calendar/{draft_id}")
async def calendar_review(draft_id: UUID, request: Request):
    require_sandbox(settings)
    return await service_proxy(
        "scheduling", f"/api/v1/scheduling/sandbox/calendar/{draft_id}", request
    )


@app.api_route("/api/v1/academic/periods", methods=["GET", "POST"])
async def academic_periods(request: Request):
    return await academic_proxy("periods", request, False)


@app.get("/api/v1/academic/sandbox/periods/{period_id}")
async def sandbox_academic_snapshot(period_id: UUID, request: Request):
    return await academic_proxy(f"periods/{period_id}", request, True)


@app.get("/api/v1/academic/periods/{period_id}")
async def academic_snapshot(period_id: UUID, request: Request):
    return await academic_proxy(f"periods/{period_id}", request, False)


def academic_record_path(period_id, kind, record_id):
    if kind not in {
        "programs",
        "subjects",
        "sections",
        "faculty",
        "resources",
        "offerings",
        "constraints",
    } or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", record_id):
        raise HTTPException(422, "Invalid academic record destination")
    return f"periods/{period_id}/records/{kind}/{record_id}"


@app.put("/api/v1/academic/sandbox/periods/{period_id}/records/{kind}/{record_id}")
async def sandbox_academic_write(period_id: UUID, kind: str, record_id: str, request: Request):
    return await academic_proxy(academic_record_path(period_id, kind, record_id), request, True)


@app.put("/api/v1/academic/periods/{period_id}/records/{kind}/{record_id}")
async def academic_write(period_id: UUID, kind: str, record_id: str, request: Request):
    return await academic_proxy(academic_record_path(period_id, kind, record_id), request, False)


# Administrator-only roster management; the Academic service re-checks role and tenant.
@app.api_route("/api/v1/academic/periods/{period_id}/roster", methods=["GET", "POST"])
async def academic_roster(period_id: UUID, request: Request):
    return await academic_proxy(f"periods/{period_id}/roster", request, False)


@app.api_route(
    "/api/v1/academic/periods/{period_id}/roster/{student_id}", methods=["PUT", "DELETE"]
)
async def academic_roster_student(period_id: UUID, student_id: str, request: Request):
    if not re.fullmatch(r"[0-9]{2}-[0-9]{5}", student_id):
        raise HTTPException(422, "Invalid student identifier")
    return await academic_proxy(f"periods/{period_id}/roster/{student_id}", request, False)


# Bulk roster and period lifecycle; the Academic service re-checks role and tenant.
@app.post("/api/v1/academic/periods/{period_id}/roster/bulk-status")
async def academic_roster_bulk_status(period_id: UUID, request: Request):
    return await academic_proxy(f"periods/{period_id}/roster/bulk-status", request, False)


@app.post("/api/v1/academic/periods/{period_id}/roster/import/{step}")
async def academic_roster_import(
    period_id: UUID, step: Literal["preview", "commit"], request: Request
):
    return await academic_proxy(f"periods/{period_id}/roster/import/{step}", request, False)


@app.post("/api/v1/academic/periods/{period_id}/clone")
async def academic_period_clone(period_id: UUID, request: Request):
    return await academic_proxy(f"periods/{period_id}/clone", request, False)


@app.post("/api/v1/academic/periods/{period_id}/archive")
async def academic_period_archive(period_id: UUID, request: Request):
    return await academic_proxy(f"periods/{period_id}/archive", request, False)


@app.api_route(
    "/api/v1/scheduling/sandbox/academic/{period_id:uuid}/{action}", methods=["GET", "POST"]
)
async def sandbox_academic_schedule(period_id: UUID, action: str, request: Request):
    if action not in {"readiness", "generate"}:
        raise HTTPException(404, "Unknown academic scheduling operation")
    return await scheduling_proxy(f"academic/{period_id}/{action}", request, True)


@app.api_route("/api/v1/scheduling/academic/{period_id:uuid}/{action}", methods=["GET", "POST"])
async def academic_schedule(period_id: UUID, action: str, request: Request):
    if action not in {"readiness", "generate"}:
        raise HTTPException(404, "Unknown academic scheduling operation")
    return await scheduling_proxy(f"academic/{period_id}/{action}", request, False)


@app.api_route("/api/v1/scheduling/sandbox/academic/drafts", methods=["GET", "POST"])
async def sandbox_academic_drafts(request: Request):
    return await scheduling_proxy("academic/drafts", request, True)


@app.get("/api/v1/scheduling/sandbox/academic/drafts/{draft_id}")
async def sandbox_academic_draft(draft_id: UUID, request: Request):
    return await scheduling_proxy(f"academic/drafts/{draft_id}", request, True)


_decision_email_tasks: set = set()


def request_decision_email(payload: object) -> dict | None:
    """Build the Teacher notice from a decided request; None when it is not notifiable."""
    if not isinstance(payload, dict):
        return None
    status = payload.get("status")
    decision = {"fulfilled": "approved", "approved": "approved", "rejected": "rejected"}.get(
        status
    )
    context = payload.get("context")
    if decision is None or not isinstance(context, dict):
        return None
    session = context.get("class") or {}
    proposed = context.get("proposed_room") or {}
    starts, ends = str(session.get("starts_at", "")), str(session.get("ends_at", ""))
    return {
        "decision": decision,
        "subject_code": str((session.get("subject") or {}).get("code") or "Class")[:40],
        "section": str((session.get("section") or {}).get("name") or "Section")[:80],
        "class_date": str(session.get("date", "")),
        "time_range": f"{starts[11:16]}–{ends[11:16]}",
        "from_room": str((session.get("room") or {}).get("name") or "Current room")[:120],
        "to_room": str(proposed.get("name") or "Proposed room")[:120],
        "note": str(payload.get("decision_note") or "No note provided.")[:1000],
    }


async def send_request_decision_email(owner_uid: object, notice: dict) -> None:
    """Post-commit, best-effort Teacher email. Failures never change the decision."""
    try:
        if not settings.notification_service_token:
            logger.warning("request_decision_email_unavailable")
            return
        if not isinstance(owner_uid, str) or not owner_uid:
            raise ValueError("Request owner is unavailable")
        from classync_contracts.firebase import initialize_firebase
        from firebase_admin import auth as firebase_auth

        firebase_app = await run_in_threadpool(initialize_firebase, settings)
        user = await run_in_threadpool(firebase_auth.get_user, owner_uid, app=firebase_app)
        if not user.email:
            raise ValueError("Teacher email is unavailable")
        url = settings.notification_service_url
        headers = await run_in_threadpool(
            service_headers,
            settings.cloud_run_iam_enabled,
            url,
            {"X-ClassSync-Service-Token": settings.notification_service_token.get_secret_value()},
        )
        async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
            sent = await client.post(
                url + "/internal/v1/request-decision-email",
                json={"email": user.email, **notice},
                headers=headers,
            )
            sent.raise_for_status()
    except Exception as error:  # noqa: BLE001 - background delivery must never raise
        logger.warning(
            "request_decision_email_failed", extra={"failure_type": type(error).__name__}
        )


@app.post("/api/v1/timetables/requests/{request_id}/decision")
async def classroom_request_decision(request_id: UUID, request: Request):
    """Commit the decision first, then notify the requesting Teacher without blocking."""
    await run_in_threadpool(require_administrator, request, settings)
    response = await service_proxy(
        "scheduling", f"/api/v1/timetables/requests/{request_id}/decision", request
    )
    if 200 <= response.status_code < 300:
        payload = json.loads(response.body).get("data")
        notice = request_decision_email(payload)
        if notice is not None:
            task = asyncio.create_task(
                send_request_decision_email(payload.get("owner_uid"), notice)
            )
            _decision_email_tasks.add(task)
            task.add_done_callback(_decision_email_tasks.discard)
    return response


# Timetable publication is independent from the legacy Administrator-only proxy.
# Each service verifies the token; preview reads are gated at both boundaries.
@app.api_route("/api/v1/timetables/{operation:path}", methods=["GET", "POST", "PUT"])
async def timetable_proxy(operation: str, request: Request):
    from classync_contracts.scheduling_security import require_identity
    from fastapi.responses import StreamingResponse

    if operation.startswith("sandbox/"):
        require_sandbox(settings)
        if request.method != "GET":
            raise HTTPException(404, "No anonymous publication operation exists")
    else:
        if operation == "requests" and request.method == "POST":
            await run_in_threadpool(request_identity, request, settings, UserRole.TEACHER)
        elif request.method != "GET" or operation.startswith(
            ("history/", "audit/", "reports/", "restrictions")
        ):
            await run_in_threadpool(require_administrator, request, settings)
        else:
            await run_in_threadpool(require_identity, request, settings)
    if "/events/" not in "/" + operation:
        return await service_proxy("scheduling", "/api/v1/timetables/" + operation, request)
    client = httpx.AsyncClient(timeout=httpx.Timeout(30, read=None), trust_env=False)
    try:
        headers = await run_in_threadpool(
            service_headers,
            settings.cloud_run_iam_enabled,
            settings.scheduling_service_url,
            forwarded_headers(request),
        )
        upstream = await client.send(
            client.build_request(
                "GET",
                settings.scheduling_service_url + "/api/v1/timetables/" + operation,
                params=request.query_params,
                headers=headers,
            ),
            stream=True,
        )
    except (httpx.HTTPError, ValueError) as error:
        await client.aclose()
        raise HTTPException(503, "Timetable update service unavailable; reconnect later") from error
    if upstream.is_error:
        await upstream.aclose()
        await client.aclose()
        raise HTTPException(upstream.status_code, "Timetable stream is not authorized or available")

    async def relay():
        try:
            async for chunk in upstream.aiter_bytes():
                if await request.is_disconnected():
                    break
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(
        relay(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@app.put("/api/v1/academic/sandbox/periods/{period_id}/calendar")
async def sandbox_calendar_write(period_id: UUID, request: Request):
    return await academic_proxy(f"periods/{period_id}/calendar", request, True)


@app.put("/api/v1/academic/periods/{period_id}/calendar")
async def calendar_write(period_id: UUID, request: Request):
    return await academic_proxy(f"periods/{period_id}/calendar", request, False)

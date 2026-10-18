import re
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from classync_contracts.firebase import FirebaseSettings, initialize_firebase
from classync_contracts.models import HealthResponse
from classync_contracts.scheduling_security import require_administrator, require_sandbox
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from firebase_admin import auth
from pydantic_settings import SettingsConfigDict

ROOT_DIRECTORY = Path(__file__).resolve().parents[3]


class Settings(FirebaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIRECTORY / ".env", extra="ignore")
    academic_service_url: str = "http://127.0.0.1:8001"
    scheduling_service_url: str = "http://127.0.0.1:8002"
    notification_service_url: str = "http://127.0.0.1:8003"
    allow_unauthenticated_development: bool = False
    classsync_env: str = "production"
    enable_scheduling_sandbox: bool = False


settings = Settings()
SERVICES = {
    "academic": settings.academic_service_url,
    "scheduling": settings.scheduling_service_url,
    "notification": settings.notification_service_url,
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(title="ClassSync API Gateway", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID", str(uuid4()))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": "request_rejected",
                "message": str(exc.detail),
                "requestId": request.state.request_id,
            }
        },
    )


def require_authenticated(request: Request) -> dict:
    header = request.headers.get("Authorization", "")
    if settings.classsync_env == "development" and settings.allow_unauthenticated_development:
        return {"uid": "local-development", "role": "administrator"}
    if not header.startswith("Bearer "):
        raise HTTPException(401, "Authentication is required")
    try:
        initialize_firebase(settings)
        return auth.verify_id_token(header.removeprefix("Bearer "))
    except Exception as error:
        raise HTTPException(401, "Invalid authentication token") from error


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(service="gateway")


@app.get("/api/v1/auth/me")
def current_user(request: Request) -> dict:
    return {"data": require_authenticated(request)}


@app.get("/api/v1/services/{service_name}/health")
async def service_health(service_name: str) -> dict:
    target = SERVICES.get(service_name)
    if target is None:
        raise HTTPException(404, "Unknown service")
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{target}/health")
        response.raise_for_status()
        return {"data": response.json()}
    except httpx.HTTPError as error:
        raise HTTPException(503, "Service unavailable") from error


async def scheduling_proxy(operation: str, request: Request, sandbox: bool):
    if sandbox:
        require_sandbox(settings)
    else:
        # The general development bypass never authorizes production scheduling.
        require_administrator(request, settings)
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
    if (
        not academic_operation
        and operation not in allowed
        and not (request.method == "GET" and operation.startswith("drafts/"))
    ):
        raise HTTPException(404, "Unknown scheduling operation; publication is not implemented")
    path = f"/api/v1/scheduling/{'sandbox/' if sandbox else ''}{operation}"
    return await service_proxy("scheduling", path, request)


async def service_proxy(service_name, path, request):
    body = await request.body()
    if len(body) > 2_000_000:
        raise HTTPException(413, "Input exceeds the 2 MB request limit")
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.request(
                request.method,
                getattr(settings, f"{service_name}_service_url") + path,
                params=request.query_params,
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": request.headers.get("Authorization", ""),
                    "X-Request-ID": request.state.request_id,
                },
            )
        payload = response.json()
        if response.is_error:
            detail = payload.get("error", {}).get(
                "message", payload.get("detail", "Scheduling request rejected")
            )
            if isinstance(detail, list):
                detail = [{"loc": d.get("loc"), "msg": d.get("msg")} for d in detail]
            return JSONResponse(
                status_code=response.status_code,
                content={
                    "error": {
                        "code": payload.get("error", {}).get("code", "scheduling_rejected"),
                        "message": detail,
                        "requestId": request.state.request_id,
                    }
                },
            )
        return JSONResponse(status_code=response.status_code, content={"data": payload})
    except (httpx.HTTPError, ValueError) as error:
        raise HTTPException(
            503, f"{service_name.capitalize()} service unavailable; no server confirmation received"
        ) from error


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


async def academic_proxy(path, request, sandbox):
    if sandbox:
        require_sandbox(settings)
    else:
        require_administrator(request, settings)
    return await service_proxy(
        "academic", f"/api/v1/academic/{'sandbox/' if sandbox else ''}{path}", request
    )


@app.api_route("/api/v1/academic/sandbox/periods", methods=["GET", "POST"])
async def sandbox_academic_periods(request: Request):
    return await academic_proxy("periods", request, True)


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

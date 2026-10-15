from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from firebase_admin import auth
from pydantic_settings import BaseSettings, SettingsConfigDict
from classync_contracts.firebase import FirebaseSettings, initialize_firebase
from classync_contracts.models import HealthResponse

ROOT_DIRECTORY = Path(__file__).resolve().parents[3]

class Settings(FirebaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIRECTORY / ".env", extra="ignore")
    academic_service_url: str = "http://127.0.0.1:8001"
    scheduling_service_url: str = "http://127.0.0.1:8002"
    notification_service_url: str = "http://127.0.0.1:8003"
    allow_unauthenticated_development: bool = False

settings = Settings()
SERVICES = {"academic": settings.academic_service_url, "scheduling": settings.scheduling_service_url, "notification": settings.notification_service_url}

@asynccontextmanager
async def lifespan(_: FastAPI):
    yield

app = FastAPI(title="ClassSync API Gateway", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=False, allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type", "X-Request-ID"])

@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID", str(uuid4()))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response

@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": "request_rejected", "message": str(exc.detail), "requestId": request.state.request_id}})

def require_authenticated(request: Request) -> dict:
    header = request.headers.get("Authorization", "")
    if settings.allow_unauthenticated_development:
        return {"uid": "local-development", "role": "administrator"}
    if not header.startswith("Bearer "):
        raise HTTPException(401, "Authentication is required")
    try:
        initialize_firebase(settings)
        return auth.verify_id_token(header.removeprefix("Bearer "))
    except Exception as error:
        raise HTTPException(401, "Invalid authentication token") from error

@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse: return HealthResponse(service="gateway")

@app.get("/api/v1/auth/me")
def current_user(request: Request) -> dict: return {"data": require_authenticated(request)}

@app.get("/api/v1/services/{service_name}/health")
async def service_health(service_name: str) -> dict:
    target = SERVICES.get(service_name)
    if target is None: raise HTTPException(404, "Unknown service")
    try:
        async with httpx.AsyncClient(timeout=2.0) as client: response = await client.get(f"{target}/health")
        response.raise_for_status()
        return {"data": response.json()}
    except httpx.HTTPError as error: raise HTTPException(503, "Service unavailable") from error

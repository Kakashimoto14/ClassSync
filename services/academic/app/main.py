from pathlib import Path

from classync_contracts.academic import (
    AcademicPeriodList,
    AcademicSnapshot,
    CalendarWrite,
    PeriodCreate,
    RecordWrite,
)
from classync_contracts.models import HealthResponse
from classync_contracts.scheduling_security import (
    SchedulingSecuritySettings,
    require_administrator,
    require_sandbox,
)
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic_settings import SettingsConfigDict

from .fixtures import FixtureRequest, import_fixture
from .repository import AcademicError, AcademicRepository


class Settings(SchedulingSecuritySettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env", extra="ignore"
    )
    academic_database_path: str = "var/academic.sqlite3"


settings = Settings()


def repository():
    path = Path(settings.academic_database_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[3] / path
    repo = AcademicRepository(path)
    repo.migrate()
    return repo


def authorize(request, sandbox):
    if sandbox:
        require_sandbox(settings)
        return "sandbox", "development-academic-sandbox"
    claims = require_administrator(request, settings)
    if not claims.get("uid"):
        raise HTTPException(401, "A verified Administrator identity is required")
    return "administrator", claims["uid"]


app = FastAPI(title="ClassSync Academic Service", version="1.0.0")


@app.post("/api/v1/academic/sandbox/fixtures", response_model=AcademicSnapshot)
def seed_fixture(body: FixtureRequest, request: Request):
    scope, owner = authorize(request, True)
    return import_fixture(repository(), body, scope, owner)


@app.exception_handler(AcademicError)
async def academic_error(_: Request, error: AcademicError):
    return JSONResponse(
        status_code=error.status, content={"error": {"code": error.code, "message": str(error)}}
    )


@app.get("/health", response_model=HealthResponse, tags=["operations"])
def health() -> HealthResponse:
    return HealthResponse(service="academic")


@app.get("/api/v1/academic/sandbox/periods", response_model=AcademicPeriodList)
def sandbox_periods(request: Request):
    scope, owner = authorize(request, True)
    return AcademicPeriodList(periods=repository().periods(scope, owner))


@app.get("/api/v1/academic/periods", response_model=AcademicPeriodList)
def periods(request: Request):
    scope, owner = authorize(request, False)
    return AcademicPeriodList(periods=repository().periods(scope, owner))


@app.post("/api/v1/academic/sandbox/periods", response_model=AcademicSnapshot, status_code=201)
def sandbox_create(body: PeriodCreate, request: Request):
    scope, owner = authorize(request, True)
    return repository().create_period(body, scope, owner)


@app.post("/api/v1/academic/periods", response_model=AcademicSnapshot, status_code=201)
def create(body: PeriodCreate, request: Request):
    scope, owner = authorize(request, False)
    return repository().create_period(body, scope, owner)


@app.get("/api/v1/academic/sandbox/periods/{period_id}", response_model=AcademicSnapshot)
def sandbox_snapshot(period_id: str, request: Request):
    scope, owner = authorize(request, True)
    return repository().snapshot(scope, owner, period_id)


@app.get("/api/v1/academic/periods/{period_id}", response_model=AcademicSnapshot)
def snapshot(period_id: str, request: Request):
    scope, owner = authorize(request, False)
    return repository().snapshot(scope, owner, period_id)


@app.put(
    "/api/v1/academic/sandbox/periods/{period_id}/records/{kind}/{record_id}",
    response_model=AcademicSnapshot,
)
def sandbox_save(period_id: str, kind: str, record_id: str, body: RecordWrite, request: Request):
    scope, owner = authorize(request, True)
    return repository().save(scope, owner, period_id, kind, record_id, body)


@app.put(
    "/api/v1/academic/periods/{period_id}/records/{kind}/{record_id}",
    response_model=AcademicSnapshot,
)
def save(period_id: str, kind: str, record_id: str, body: RecordWrite, request: Request):
    scope, owner = authorize(request, False)
    return repository().save(scope, owner, period_id, kind, record_id, body)


@app.put("/api/v1/academic/sandbox/periods/{period_id}/calendar")
def sandbox_calendar_write(period_id: str, body: CalendarWrite, request: Request):
    scope, owner = authorize(request, True)
    return repository().save_calendar(scope, owner, period_id, body)


@app.put("/api/v1/academic/periods/{period_id}/calendar")
def calendar_write(period_id: str, body: CalendarWrite, request: Request):
    scope, owner = authorize(request, False)
    return repository().save_calendar(scope, owner, period_id, body)

from datetime import date
from pathlib import Path
from threading import BoundedSemaphore

import httpx
from classync_contracts.academic import (
    AcademicGenerationRequest,
    AcademicReadiness,
    AcademicSnapshot,
)
from classync_contracts.models import HealthResponse
from classync_contracts.scheduling import (
    DraftDetail,
    DraftList,
    GenerationInput,
    GenerationResult,
    ReadinessResult,
    SaveDraftRequest,
    ValidationInput,
    ValidationResult,
)
from classync_contracts.scheduling_security import (
    SchedulingSecuritySettings,
    require_administrator,
    require_sandbox,
)
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic_settings import SettingsConfigDict

from .academic_input import academic_readiness
from .catalog import catalogs, synthetic_scenario
from .draft_repository import DraftError, DraftRepository, calendar_review_allowed
from .engine import generate_week
from .occurrences import occurrences
from .publication_api import router as publication_router
from .readiness import readiness
from .validation import validate_timetable


class Settings(SchedulingSecuritySettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env", extra="ignore"
    )
    scheduling_database_path: str = "var/scheduling.sqlite3"
    academic_service_url: str = "http://127.0.0.1:8001"


settings = Settings()
generation_slot = BoundedSemaphore(1)

app = FastAPI(title="ClassSync Scheduling Service", version="1.0.0")
app.include_router(publication_router)


@app.get("/api/v1/scheduling/sandbox/calendar-samples", response_model=DraftList)
def calendar_samples(
    request: Request, limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)
):
    scope, owner = academic_scope(request, True)
    return repository().calendar_samples(scope, owner, limit=limit, offset=offset)


@app.get("/api/v1/scheduling/sandbox/calendar/{draft_id}")
def review_calendar(draft_id: str, request: Request, start: date, end: date):
    scope, owner = academic_scope(request, True)
    draft = repository().get(draft_id, scope, owner)
    if not calendar_review_allowed(draft):
        raise HTTPException(
            403, "Only explicitly synthetic saved schedules have anonymous calendar review"
        )
    snapshot = persisted_academic_snapshot(draft.period_id, request, True)
    if snapshot.period.calendar is None:
        raise HTTPException(422, "This academic period needs effective calendar dates")
    return {
        "version": draft.id,
        "status": "unpublished-review",
        "calendar": snapshot.period.calendar.model_dump(mode="json"),
        "sections": [s.model_dump() for s in draft.input_snapshot.sections],
        "teachers": [t.model_dump() for t in draft.input_snapshot.teachers],
        "occurrences": occurrences(
            draft.input_snapshot,
            draft.generation_result.assignments,
            snapshot.period.calendar,
            start,
            end,
        ),
    }


@app.exception_handler(DraftError)
async def draft_error(_: Request, error: DraftError):
    return JSONResponse(
        status_code=error.status, content={"error": {"code": error.code, "message": str(error)}}
    )


def repository():
    path = Path(settings.scheduling_database_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[3] / path
    repo = DraftRepository(path)
    repo.migrate()
    return repo


@app.get("/health", response_model=HealthResponse, tags=["operations"])
def health() -> HealthResponse:
    return HealthResponse(service="scheduling")


def authorize(request, sandbox):
    if sandbox:
        require_sandbox(settings)
        return "sandbox", "development-sandbox"
    else:
        claims = require_administrator(request, settings)
        if not claims.get("uid"):
            raise HTTPException(401, "A verified Administrator identity is required")
        return "administrator", claims["uid"]


def sandbox_input(inputs):
    if not inputs.synthetic or any(r.source != "synthetic" for r in inputs.rooms):
        raise HTTPException(
            422, "The development sandbox accepts explicitly synthetic inputs and resources only"
        )


@app.get("/api/v1/scheduling/sandbox/scenario", response_model=GenerationInput)
def scenario(request: Request, infeasible: bool = False):
    authorize(request, True)
    return synthetic_scenario(infeasible)


@app.get("/api/v1/scheduling/sandbox/catalogs")
def sandbox_catalogs(request: Request):
    authorize(request, True)
    return catalogs()


@app.post("/api/v1/scheduling/sandbox/generate", response_model=GenerationResult)
def sandbox_generate(inputs: GenerationInput, request: Request):
    scope, owner = authorize(request, True)
    sandbox_input(inputs)
    return execute(inputs, scope, owner)


@app.post("/api/v1/scheduling/sandbox/readiness", response_model=ReadinessResult)
def sandbox_readiness(inputs: GenerationInput, request: Request):
    authorize(request, True)
    sandbox_input(inputs)
    return ReadinessResult(inputs=inputs, diagnostics=readiness(inputs))


@app.post("/api/v1/scheduling/readiness", response_model=ReadinessResult)
def production_readiness(inputs: GenerationInput, request: Request):
    authorize(request, False)
    return ReadinessResult(inputs=inputs, diagnostics=readiness(inputs))


@app.post("/api/v1/scheduling/generate", response_model=GenerationResult)
def generate(inputs: GenerationInput, request: Request):
    scope, owner = authorize(request, False)
    return execute(inputs, scope, owner)


def execute(inputs, scope, owner):
    if not generation_slot.acquire(blocking=False):
        raise HTTPException(503, "A scheduling run is in progress. Try again when it completes.")
    try:
        result = generate_week(inputs)
        if result.solver_status in {"feasible", "optimal"}:
            repository().remember_run(inputs, result, scope, owner)
        return result
    finally:
        generation_slot.release()


@app.post("/api/v1/scheduling/sandbox/validate", response_model=ValidationResult)
def sandbox_validate(candidate: ValidationInput, request: Request):
    authorize(request, True)
    sandbox_input(candidate.inputs)
    return validate_timetable(candidate.inputs, candidate.assignments)


@app.post("/api/v1/scheduling/validate", response_model=ValidationResult)
def validate(candidate: ValidationInput, request: Request):
    authorize(request, False)
    return validate_timetable(candidate.inputs, candidate.assignments)


@app.post("/api/v1/scheduling/sandbox/drafts", response_model=DraftDetail)
def save_sandbox_draft(body: SaveDraftRequest, request: Request, response: Response):
    scope, owner = authorize(request, True)
    draft, created = repository().save(body, scope, owner)
    response.status_code = 201 if created else 200
    return draft


@app.post("/api/v1/scheduling/drafts", response_model=DraftDetail)
def save_draft(body: SaveDraftRequest, request: Request, response: Response):
    scope, owner = authorize(request, False)
    draft, created = repository().save(body, scope, owner)
    response.status_code = 201 if created else 200
    return draft


@app.get("/api/v1/scheduling/sandbox/drafts", response_model=DraftList)
def list_sandbox_drafts(
    request: Request, limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)
):
    scope, owner = authorize(request, True)
    return repository().list(scope, owner, limit=limit, offset=offset)


@app.get("/api/v1/scheduling/drafts", response_model=DraftList)
def list_drafts(
    request: Request, limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)
):
    scope, owner = authorize(request, False)
    return repository().list(scope, owner, limit=limit, offset=offset)


@app.get("/api/v1/scheduling/sandbox/drafts/{draft_id}", response_model=DraftDetail)
def get_sandbox_draft(draft_id: str, request: Request):
    scope, owner = authorize(request, True)
    return repository().get(draft_id, scope, owner)


@app.get("/api/v1/scheduling/drafts/{draft_id}", response_model=DraftDetail)
def get_draft(draft_id: str, request: Request):
    scope, owner = authorize(request, False)
    return repository().get(draft_id, scope, owner)


def academic_scope(request, sandbox):
    if sandbox:
        require_sandbox(settings)
        return "academic-sandbox", "development-academic-sandbox"
    return authorize(request, False)


def persisted_academic_snapshot(period_id, request, sandbox):
    academic_scope(request, sandbox)
    if not period_id or any(
        c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
        for c in period_id
    ):
        raise HTTPException(422, "Invalid academic period ID")
    path = f"/api/v1/academic/{'sandbox/' if sandbox else ''}periods/{period_id}"
    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(
                settings.academic_service_url + path,
                headers={"Authorization": request.headers.get("Authorization", "")},
            )
        if response.is_error:
            message = (
                response.json().get("error", {}).get("message", "Academic period request rejected")
            )
            raise HTTPException(response.status_code, message)
        snapshot = AcademicSnapshot.model_validate(response.json())
        if snapshot.period.id != period_id or snapshot.period.source != (
            "development-entered" if sandbox else "institutional"
        ):
            raise HTTPException(409, "Academic source scope does not match")
        return snapshot
    except (httpx.HTTPError, ValueError) as error:
        raise HTTPException(
            503, "Academic service unavailable; no scheduling input was substituted"
        ) from error


@app.get(
    "/api/v1/scheduling/sandbox/academic/{period_id}/readiness", response_model=AcademicReadiness
)
def sandbox_academic_readiness(period_id: str, request: Request):
    return academic_readiness(persisted_academic_snapshot(period_id, request, True))


@app.get("/api/v1/scheduling/academic/{period_id}/readiness", response_model=AcademicReadiness)
def protected_academic_readiness(period_id: str, request: Request):
    return academic_readiness(persisted_academic_snapshot(period_id, request, False))


def generate_academic(period_id, body, request, sandbox):
    scope, owner = academic_scope(request, sandbox)
    snapshot = persisted_academic_snapshot(period_id, request, sandbox)
    if snapshot.period.revision != body.expected_revision:
        raise HTTPException(409, "Academic inputs changed. Recheck readiness before generation.")
    checked = academic_readiness(snapshot)
    if not checked.ready or checked.inputs is None:
        raise HTTPException(
            422, {"code": "academic_not_ready", "issues": [i.model_dump() for i in checked.issues]}
        )
    return execute(checked.inputs, scope, owner)


@app.post(
    "/api/v1/scheduling/sandbox/academic/{period_id}/generate", response_model=GenerationResult
)
def sandbox_academic_generate(period_id: str, body: AcademicGenerationRequest, request: Request):
    return generate_academic(period_id, body, request, True)


@app.post("/api/v1/scheduling/academic/{period_id}/generate", response_model=GenerationResult)
def protected_academic_generate(period_id: str, body: AcademicGenerationRequest, request: Request):
    return generate_academic(period_id, body, request, False)


@app.post("/api/v1/scheduling/sandbox/academic/drafts", response_model=DraftDetail)
def save_academic_sandbox_draft(body: SaveDraftRequest, request: Request, response: Response):
    scope, owner = academic_scope(request, True)
    draft, created = repository().save(body, scope, owner)
    response.status_code = 201 if created else 200
    return draft


@app.get("/api/v1/scheduling/sandbox/academic/drafts", response_model=DraftList)
def list_academic_sandbox_drafts(
    request: Request, limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)
):
    scope, owner = academic_scope(request, True)
    return repository().list(scope, owner, limit=limit, offset=offset)


@app.get("/api/v1/scheduling/sandbox/academic/drafts/{draft_id}", response_model=DraftDetail)
def get_academic_sandbox_draft(draft_id: str, request: Request):
    scope, owner = academic_scope(request, True)
    return repository().get(draft_id, scope, owner)

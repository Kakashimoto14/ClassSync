from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from threading import BoundedSemaphore
from typing import Literal
from uuid import uuid4

import httpx
from classync_contracts.academic import (
    AcademicGenerationRequest,
    AcademicReadiness,
    AcademicSnapshot,
)
from classync_contracts.cloud_run import service_headers
from classync_contracts.identity import MembershipAuthorizationError, MembershipErrorCode
from classync_contracts.models import HealthResponse
from classync_contracts.request_authorization import install_identity_errors
from classync_contracts.scheduling import (
    Assignment,
    DraftDetail,
    DraftList,
    GenerationInput,
    GenerationResult,
    ReadinessResult,
    SaveDraftRequest,
    ValidationInput,
    ValidationResult,
    scheduling_input_hash,
)
from classync_contracts.scheduling_security import (
    SchedulingSecuritySettings,
    require_administrator,
    require_sandbox,
)
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import SettingsConfigDict

from .academic_input import academic_readiness
from .advisor import (
    Advice,
    ConflictAdvice,
    ConflictPrompt,
    ConflictSuggestion,
    HealthPrompt,
    _advise,
)
from .authorization import configured_scheduling
from .catalog import catalogs, synthetic_scenario
from .classroom_requests import router as classroom_requests_router
from .draft_repository import DraftError, DraftRepository, calendar_review_allowed
from .engine import generate_week
from .occurrences import occurrences
from .provider import institutional_repository
from .publication_api import router as publication_router
from .publication_api import term_restrictions
from .readiness import readiness
from .repair import EVALUATION_LIMIT, Repair
from .restriction_windows import with_room_restrictions
from .validation import validate_timetable


class Settings(SchedulingSecuritySettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env", extra="ignore"
    )
    scheduling_database_path: str = "var/scheduling.sqlite3"
    scheduling_database_url: SecretStr | None = None
    scheduling_database_transport: Literal["verify-full", "loopback-sspi-test"] = "verify-full"
    academic_service_url: str = "http://127.0.0.1:8001"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.5-flash-lite"


settings = Settings()
generation_slot = BoundedSemaphore(1)


class ReviseDraftRequest(BaseModel):
    assignments: list[Assignment] = Field(max_length=7000)
    title: str = Field(min_length=1, max_length=160)
    idempotency_key: str = Field(min_length=8, max_length=100)


@asynccontextmanager
async def lifespan(application):
    with configured_scheduling(application, settings):
        yield


def connected_repository(request, owner):
    return institutional_repository(request, settings, owner, repository)


app = FastAPI(title="ClassSync Scheduling Service", version="1.0.0", lifespan=lifespan)
install_identity_errors(app)
app.include_router(publication_router)
app.include_router(classroom_requests_router)


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


@app.exception_handler(MembershipAuthorizationError)
async def membership_error(_: Request, error: MembershipAuthorizationError):
    unavailable = error.code == MembershipErrorCode.UNAVAILABLE
    return JSONResponse(
        status_code=503 if unavailable else 403,
        content={
            "error": {
                "code": error.code.value,
                "message": "University access is unavailable"
                if unavailable
                else "Current membership required",
            }
        },
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
    return execute(inputs, scope, owner, storage=connected_repository(request, owner))


def execute(inputs, scope, owner, *, storage=None):
    if storage is None and scope not in {"sandbox", "academic-sandbox"}:
        raise HTTPException(503, "Scheduling storage is unavailable")
    if not generation_slot.acquire(blocking=False):
        raise HTTPException(503, "A scheduling run is in progress. Try again when it completes.")
    try:
        result = generate_week(inputs)
        if result.solver_status in {"feasible", "optimal"}:
            if storage is None:
                repository().remember_run(inputs, result, scope, owner)
            else:
                storage.remember_run(inputs, result)
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
    draft, created = connected_repository(request, owner).save(body)
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
    return connected_repository(request, owner).list(limit=limit, offset=offset)


@app.get("/api/v1/scheduling/sandbox/drafts/{draft_id}", response_model=DraftDetail)
def get_sandbox_draft(draft_id: str, request: Request):
    scope, owner = authorize(request, True)
    return repository().get(draft_id, scope, owner)


@app.get("/api/v1/scheduling/drafts/{draft_id}", response_model=DraftDetail)
def get_draft(draft_id: str, request: Request):
    scope, owner = authorize(request, False)
    return connected_repository(request, owner).get(draft_id)


def deterministic_repair(inputs, assignments, target, context):
    """Validated one-move or two-step options found without the AI advisor."""
    options = Repair(inputs, assignments).suggest(target)
    if not options:
        return ConflictAdvice(
            available=False,
            message=(
                f"{context} No conflict-free one- or two-step repair was found within "
                f"{EVALUATION_LIMIT} checks. Adjust the academic constraints and validate again."
            ),
        )
    subjects = {o.id: o.subject_name for o in inputs.offerings}
    suggestions = []
    for option in options:
        moved = option[target.id]
        other = next((value for key, value in option.items() if key != target.id), None)
        reason = (
            f"Validated two-step repair: also moves {subjects.get(other.offering_id, 'a lecture')} "
            f"to day {other.day + 1}, {other.start // 60:02d}:{other.start % 60:02d}."
            if other
            else "Validated move with no hard conflicts."
        )
        suggestions.append(ConflictSuggestion(assignment=moved, reason=reason, also_moves=other))
    return ConflictAdvice(
        available=True,
        message=(
            f"{context} Deterministic repair options; each passed full validation. "
            "Apply creates a separately validated draft."
        ),
        suggestions=suggestions,
    )


@app.post("/api/v1/scheduling/drafts/{draft_id}/advisor/conflict", response_model=ConflictAdvice)
async def conflict_advice(draft_id: str, body: ConflictPrompt, request: Request):
    _, owner = authorize(request, False)
    draft = connected_repository(request, owner).get(draft_id)
    if draft.source != "institutional":
        raise HTTPException(403, "Institutional schedule draft required")
    inputs = draft.input_snapshot
    assignments = draft.generation_result.assignments
    target = next((item for item in assignments if item.id == body.assignment_id), None)
    if target is None:
        raise HTTPException(404, "Assignment is not part of this draft")
    if len(assignments) > 120:
        return deterministic_repair(
            inputs,
            assignments,
            target,
            "AI ranking is limited to drafts with at most 120 assignments.",
        )
    offering = next((item for item in inputs.offerings if item.id == target.offering_id), None)
    if offering is None:
        raise HTTPException(409, "Assignment offering is unavailable")
    room_by_id = {room.id: room for room in inputs.rooms}
    teacher_ids = offering.eligible_teacher_ids or [target.teacher_id]
    alternatives = []
    option_assignments = {}
    checked_count = 0
    for window in inputs.operating_windows:
        if checked_count >= 24 or len(alternatives) >= 8:
            break
        if window.day < 6:
            for start in range(window.start, window.end - (target.end - target.start) + 1, 30):
                if checked_count >= 24 or len(alternatives) >= 8:
                    break
                for teacher_id in teacher_ids:
                    if checked_count >= 24 or len(alternatives) >= 8:
                        break
                    for room_id in offering.eligible_room_ids:
                        if checked_count >= 24 or len(alternatives) >= 8:
                            break
                        checked_count += 1
                        proposal = target.model_copy(
                            update={
                                "day": window.day,
                                "start": start,
                                "end": start + target.end - target.start,
                                "teacher_id": teacher_id,
                                "room_id": room_id,
                            }
                        )
                        candidate = [
                            proposal if item.id == target.id else item for item in assignments
                        ]
                        if validate_timetable(inputs, candidate).valid:
                            option_id = f"option-{len(alternatives) + 1}"
                            option_assignments[option_id] = proposal
                            room = room_by_id[room_id]
                            alternatives.append(
                                {
                                    "option_id": option_id,
                                    "day": window.day,
                                    "start": start,
                                    "duration": target.end - target.start,
                                    "room_type": room.room_type,
                                    "faculty_load_hours": round(
                                        sum(
                                            item.end - item.start
                                            for item in assignments
                                            if item.teacher_id == teacher_id
                                        )
                                        / 60
                                    ),
                                }
                            )
    prompt = {
        "issue": ("Rank these validated options for fewer conflicts and lower gaps."),
        "alternatives": alternatives,
    }
    if not alternatives:
        return deterministic_repair(inputs, assignments, target, "No single move was found.")
    result = await _advise(
        settings, prompt, shape="conflict", option_assignments=option_assignments
    )
    if not result.available:
        return result
    return result


@app.post("/api/v1/scheduling/drafts/{draft_id}/advisor/health", response_model=Advice)
async def health_advice(draft_id: str, request: Request):
    scope, owner = authorize(request, False)
    draft = connected_repository(request, owner).get(draft_id)
    if draft.source != "institutional":
        raise HTTPException(403, "Institutional schedule draft required")
    inputs, assignments = draft.input_snapshot, draft.generation_result.assignments
    used_rooms = {item.room_id for item in assignments}
    loads = {teacher.id: 0 for teacher in inputs.teachers}
    for item in assignments:
        loads[item.teacher_id] = loads.get(item.teacher_id, 0) + item.end - item.start
    section_days: dict[tuple[str, int], list] = {}
    for item in assignments:
        section_days.setdefault((item.section_id, item.day), []).append(item)
    gaps = 0
    for items in section_days.values():
        ordered = sorted(items, key=lambda item: item.start)
        gaps += sum(
            right.start > left.end for left, right in zip(ordered, ordered[1:], strict=False)
        )
    prompt = HealthPrompt(
        room_utilization_percent=round(100 * len(used_rooms) / max(1, len(inputs.rooms))),
        faculty_load_min_hours=min(loads.values(), default=0) // 60,
        faculty_load_max_hours=max(loads.values(), default=0) // 60,
        faculty_load_average_hours=round(sum(loads.values()) / max(1, len(loads)) / 60),
        idle_gap_count=gaps,
        publish_ready=draft.validation.valid and len(assignments) > 0,
        blocking_conflicts=draft.validation.hard_conflict_count,
    )
    return await _advise(settings, prompt.model_dump(), shape="health")


@app.post("/api/v1/scheduling/drafts/{draft_id}/revisions", response_model=DraftDetail)
def revise_draft(draft_id: str, body: ReviseDraftRequest, request: Request):
    _, owner = authorize(request, False)
    storage = connected_repository(request, owner)
    current = storage.get(draft_id)
    assignments = body.assignments
    available_ids = {assignment.id for assignment in assignments}
    if len(available_ids) != len(assignments):
        raise HTTPException(422, "Assignment IDs must be unique")
    # Academic Setup owns pins. Revisions preserve the exact current constraint
    # snapshot so publication's fresh-input hash remains bound to saved records.
    inputs = current.input_snapshot
    validation = validate_timetable(inputs, assignments)
    if not validation.valid or len(validation.coverage) != len(inputs.offerings):
        raise HTTPException(
            422,
            {
                "code": "schedule_conflict",
                "message": (
                    "The proposed revision has conflicts or incomplete instructional coverage."
                ),
                "validation": validation.model_dump(mode="json"),
            },
        )
    result = current.generation_result.model_copy(
        update={
            "run_id": str(uuid4()),
            "input_hash": scheduling_input_hash(inputs),
            "assignments": assignments,
            "total_offerings_scheduled": len(inputs.offerings),
            "coverage": validation.coverage,
            "hard_conflict_count": validation.hard_conflict_count,
            "diagnostics": [],
            "validation": validation,
        }
    )
    storage.remember_run(inputs, result)
    saved, _ = storage.save(
        SaveDraftRequest(
            run_id=result.run_id,
            input_hash=result.input_hash,
            title=body.title.strip(),
            idempotency_key=body.idempotency_key,
        )
    )
    return saved


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
        headers = service_headers(
            settings.cloud_run_iam_enabled,
            settings.academic_service_url,
            {"Authorization": request.headers.get("Authorization", "")},
        )
        with httpx.Client(timeout=10, trust_env=False) as client:
            response = client.get(
                settings.academic_service_url + path,
                headers=headers,
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
    storage = None if sandbox else connected_repository(request, owner)
    snapshot = persisted_academic_snapshot(period_id, request, sandbox)
    if snapshot.period.revision != body.expected_revision:
        raise HTTPException(409, "Academic inputs changed. Recheck readiness before generation.")
    checked = academic_readiness(snapshot)
    if not checked.ready or checked.inputs is None:
        raise HTTPException(
            422, {"code": "academic_not_ready", "issues": [i.model_dump() for i in checked.issues]}
        )
    inputs = checked.inputs
    if not sandbox:
        # Dated restrictions would block publication of any weekly placement they touch.
        inputs = with_room_restrictions(
            inputs,
            restrictions=term_restrictions(request),
            calendar=snapshot.period.calendar,
        )
    return execute(inputs, scope, owner, storage=storage)


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

"""Publication endpoints: no browser role or general development bypass grants writes."""

import asyncio
import json
from datetime import date, datetime, timedelta

from classync_contracts.publication import PublicationCommand, RoomRestriction
from classync_contracts.scheduling_security import require_administrator, require_sandbox
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from .draft_repository import DraftError
from .publication_repository import PublicationRepository

router = APIRouter(prefix="/api/v1/timetables")


def settings_and_repo():
    from .main import repository, settings

    return settings, PublicationRepository(repository())


def identity(request):
    from classync_contracts.scheduling_security import require_identity

    settings, _ = settings_and_repo()
    return require_identity(request, settings)


def read_scope(request, sandbox, role="student", section="", teacher=""):
    settings, repo = settings_and_repo()
    if sandbox:
        require_sandbox(settings)
        if role not in {"student", "teacher", "administrator"}:
            raise HTTPException(422, "Unknown preview role")
        return (
            repo,
            "development-synthetic",
            "synthetic",
            {"role": role, "uid": "mock-viewer", "mock_section": section, "faculty_id": teacher},
        )
    claims = identity(request)
    tenant = claims.get("tenant_id")
    if not isinstance(tenant, str) or not tenant:
        raise HTTPException(403, "A verified institutional tenant is required")
    return repo, tenant, "institutional", claims


def prepare(body, request, commit):
    from .main import academic_readiness, persisted_academic_snapshot

    settings, repo = settings_and_repo()
    claims = require_administrator(request, settings)
    if not claims.get("uid"):
        raise HTTPException(401, "A verified administrator identity is required")
    synthetic = body.dataset == "synthetic"
    if synthetic:
        require_sandbox(settings)
        if body.source != "academic-sandbox":
            raise HTTPException(422, "Synthetic publication requires a synthetic academic draft")
        tenant, owner = "development-synthetic", "development-academic-sandbox"
    else:
        if body.source != "administrator" or not claims.get("tenant_id"):
            raise HTTPException(
                403, "Institutional publication needs a verified tenant and owned draft"
            )
        tenant, owner = claims["tenant_id"], claims["uid"]
    draft = repo.drafts.get(body.draft_id, body.source, owner)
    from .draft_repository import digest, encode

    with repo.drafts.connection() as db:
        prior = db.execute(
            "SELECT * FROM published_versions WHERE tenant=? AND dataset=? AND idempotency_key=?",
            (tenant, body.dataset, body.idempotency_key),
        ).fetchone()
        if prior:
            if prior["request_hash"] != digest(encode(body.model_dump(mode="json"))):
                raise HTTPException(409, "Publish key belongs to a different command")
            return repo.summary(prior, db)
    snapshot = persisted_academic_snapshot(draft.period_id, request, synthetic)
    checked = academic_readiness(snapshot)
    if (
        snapshot.period.revision != body.expected_academic_revision
        or not checked.ready
        or checked.inputs is None
    ):
        raise HTTPException(
            409, "Academic records changed or are no longer ready. Revalidate the saved scope."
        )
    from classync_contracts.scheduling import scheduling_input_hash

    if scheduling_input_hash(checked.inputs) != draft.input_hash:
        raise HTTPException(
            409,
            "Saved draft does not match the current academic constraints. Generate a new revision.",
        )
    if snapshot.period.calendar is None:
        raise HTTPException(422, "The academic period requires a semester calendar")
    saved = snapshot.period.calendar
    if (
        body.calendar.academic_year != saved.academic_year
        or body.calendar.semester != saved.semester
        or body.calendar.instructional_days != saved.instructional_days
        or not saved.effective_start
        <= body.calendar.effective_start
        <= body.calendar.effective_end
        <= saved.effective_end
    ):
        raise HTTPException(422, "Publication dates must stay within the saved academic semester")
    return repo.publish(body, draft, tenant, claims["uid"], commit=commit)


@router.post("/review")
def review(body: PublicationCommand, request: Request):
    return prepare(body, request, False)


@router.post("/publish")
def publish(body: PublicationCommand, request: Request):
    return prepare(body, request, True)


@router.get("/history/{period}")
def history(period: str, request: Request, dataset: str = "institutional"):
    settings, repo = settings_and_repo()
    claims = require_administrator(request, settings)
    if dataset not in {"institutional", "synthetic"}:
        raise HTTPException(422, "Unknown dataset")
    if dataset == "synthetic":
        require_sandbox(settings)
        tenant = "development-synthetic"
    else:
        tenant = claims.get("tenant_id")
        if not tenant:
            raise HTTPException(403, "Verified tenant required")
    return {"versions": repo.history(tenant, dataset, period)}


def periods_for(request, sandbox, role, section, teacher):
    repo, tenant, dataset, viewer = read_scope(request, sandbox, role, section, teacher)
    with repo.drafts.connection() as db:
        ids = db.execute(
            "SELECT period_id,revision FROM publication_heads WHERE tenant=? AND dataset=? "
            "ORDER BY period_id",
            (tenant, dataset),
        ).fetchall()
        result = []
        for row in ids:
            versions = repo.rows(db, tenant, dataset, row["period_id"])
            payload = repo.decode(versions[-1])
            inputs = payload["draft"].input_snapshot
            eligible = (
                viewer["role"] == "administrator"
                or dataset == "synthetic"
                or (
                    viewer["role"] == "teacher"
                    and any(
                        a.teacher_id == viewer.get("faculty_id")
                        for a in payload["draft"].generation_result.assignments
                    )
                )
                or (
                    viewer["role"] == "student"
                    and any(e.student_id == viewer["uid"] for e in inputs.enrollments)
                )
            )
            if eligible:
                result.append(
                    {
                        "id": row["period_id"],
                        "revision": row["revision"],
                        "title": payload["draft"].title,
                        "calendar": payload["calendar"].model_dump(mode="json"),
                    }
                )
    if sandbox:
        import httpx

        from .main import settings

        with httpx.Client(timeout=10) as client:
            response = client.get(
                settings.academic_service_url + "/api/v1/academic/sandbox/periods"
            )
        if response.is_success:
            existing = {p["id"] for p in result}
            for p in response.json()["periods"]:
                if p["id"] not in existing and p.get("calendar"):
                    result.append({**p, "revision": 0})
    return {"periods": result}


@router.get("/sandbox/periods")
def sandbox_periods(request: Request, role: str = "student", section: str = "", teacher: str = ""):
    return periods_for(request, True, role, section, teacher)


@router.get("/periods")
def periods(request: Request):
    return periods_for(request, False, "student", "", "")


def calendar_for(period, request, sandbox, start, end, role, section, teacher):
    repo, tenant, dataset, viewer = read_scope(request, sandbox, role, section, teacher)
    try:
        return repo.calendar(tenant, dataset, period, start, end, viewer)
    except DraftError as error:
        if error.status != 404 or not sandbox:
            raise
        from .main import persisted_academic_snapshot

        snapshot = persisted_academic_snapshot(period, request, True)
        if snapshot.period.calendar is None:
            raise HTTPException(422, "Academic calendar dates are required") from error
        return {
            "version": None,
            "sequence": 0,
            "revision": 0,
            "status": "not-published",
            "calendar": snapshot.period.calendar.model_dump(mode="json"),
            "sections": [
                e.record.model_dump() for e in snapshot.records if e.record.kind == "sections"
            ],
            "teachers": [
                e.record.model_dump() for e in snapshot.records if e.record.kind == "faculty"
            ],
            "occurrences": [],
        }


@router.get("/sandbox/calendar/{period}")
def sandbox_calendar(
    period: str,
    request: Request,
    start: date,
    end: date,
    role: str = "student",
    section: str = "",
    teacher: str = "",
):
    return calendar_for(period, request, True, start, end, role, section, teacher)


@router.get("/calendar/{period}")
def calendar(period: str, request: Request, start: date, end: date):
    return calendar_for(period, request, False, start, end, "student", "", "")


async def stream(period, request, sandbox, start, end, role, section, teacher, after):
    repo, tenant, dataset, viewer = read_scope(request, sandbox, role, section, teacher)
    # Authenticate before sending HTTP 200; reconnects revalidate tokens and revocation.
    calendar_for(period, request, sandbox, start, end, role, section, teacher)

    async def events():
        cursor = after
        for _ in range(80):
            if await request.is_disconnected():
                break
            try:
                value = await asyncio.to_thread(
                    repo.calendar, tenant, dataset, period, start, end, viewer
                )
            except DraftError as error:
                if error.status != 404:
                    raise
                value = {"sequence": 0, "version": None}
            if value["sequence"] > cursor:
                cursor = value["sequence"]
                minimal = {"sequence": cursor, "version": value["version"], "period_id": period}
                yield f"id: {cursor}\nevent: schedule-version\ndata: {json.dumps(minimal)}\n\n"
            elif _ % 12 == 0:
                yield ": heartbeat\n\n"
            await asyncio.sleep(0.25)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.get("/sandbox/events/{period}")
async def sandbox_events(
    period: str,
    request: Request,
    start: date,
    end: date,
    role: str = "student",
    section: str = "",
    teacher: str = "",
    after: int = Query(0, ge=0),
):
    return await stream(period, request, True, start, end, role, section, teacher, after)


@router.get("/events/{period}")
async def events(
    period: str, request: Request, start: date, end: date, after: int = Query(0, ge=0)
):
    return await stream(period, request, False, start, end, "student", "", "", after)


def availability_for(request, sandbox, room_id, start, end):
    repo, tenant, dataset, _ = read_scope(request, sandbox, "administrator", "", "")
    if (
        start.tzinfo is None
        or end.tzinfo is None
        or not start < end
        or end - start > timedelta(days=2)
    ):
        raise HTTPException(422, "Supply increasing timezone-aware times within two days")
    from .occurrences import ZONE

    start, end = start.astimezone(ZONE), end.astimezone(ZONE)
    with repo.drafts.connection() as db:
        rows = repo.rows(db, tenant, dataset)
        if not rows:
            raise HTTPException(404, "No published occupancy source is available")
        decoded = [repo.decode(r) for r in rows]
        from .catalog import catalogs

        known = {r.id for p in decoded for r in p["draft"].input_snapshot.rooms}
        known.update(r.id for r in catalogs()["cdm_spaces"])
        if room_id not in known:
            raise HTTPException(
                404, "Room not found in the published scope or provisional inventory"
            )
        day = start.date()
        covered = True
        stop = (end - timedelta(microseconds=1)).date()
        while day <= stop:
            covered = covered and any(
                p["calendar"].effective_start <= day <= p["calendar"].effective_end for p in decoded
            )
            day += timedelta(days=1)
        events = repo.expanded(rows, start.date(), end.date())
        requested = {"starts_at": start.isoformat(), "ends_at": end.isoformat()}
        matches = [
            e
            for e in events
            if e["room"]["id"] == room_id
            and e["starts_at"] < requested["ends_at"]
            and requested["starts_at"] < e["ends_at"]
        ]
        restrictions = [
            json.loads(r[0])
            for r in db.execute(
                "SELECT payload FROM publication_room_restrictions WHERE tenant=? AND dataset=?",
                (tenant, dataset),
            )
        ]
        restricted = any(
            r["room_id"] == room_id
            and r["starts_at"] < requested["ends_at"]
            and requested["starts_at"] < r["ends_at"]
            for r in restrictions
        )
        # Non-admin production callers receive occupancy only, never another role's timetable.
        return {
            "room_id": room_id,
            "occupancy": "restricted"
            if restricted
            else "occupied"
            if matches
            else "unoccupied"
            if covered
            else "unknown",
            "suitability": "unknown",
            "sessions": len(matches),
            "timezone": "Asia/Manila",
        }


@router.get("/sandbox/availability")
def sandbox_availability(request: Request, room_id: str, start: datetime, end: datetime):
    return availability_for(request, True, room_id, start, end)


@router.get("/availability")
def availability(request: Request, room_id: str, start: datetime, end: datetime):
    return availability_for(request, False, room_id, start, end)


@router.put("/restrictions/{restriction_id}")
def save_restriction(restriction_id: str, body: RoomRestriction, request: Request):
    settings, repo = settings_and_repo()
    claims = require_administrator(request, settings)
    if body.id != restriction_id:
        raise HTTPException(422, "Restriction identity differs from its URL")
    if body.dataset == "synthetic":
        require_sandbox(settings)
        tenant = "development-synthetic"
    else:
        tenant = claims.get("tenant_id")
        if not tenant:
            raise HTTPException(403, "Verified tenant required")
    try:
        start, end = datetime.fromisoformat(body.starts_at), datetime.fromisoformat(body.ends_at)
    except ValueError as error:
        raise HTTPException(422, "Use ISO date/times with timezone offsets") from error
    if start.tzinfo is None or end.tzinfo is None or start >= end:
        raise HTTPException(422, "Use increasing timezone-aware restriction times")
    from .draft_repository import now
    from .occurrences import ZONE

    value = {
        **body.model_dump(),
        "starts_at": start.astimezone(ZONE).isoformat(),
        "ends_at": end.astimezone(ZONE).isoformat(),
        "revision": body.expected_revision + 1,
        "actor": claims["uid"],
        "updated_at": now(),
    }
    with repo.drafts.connection(write=True) as db:
        rows = repo.rows(db, tenant, body.dataset)
        known = {r.id for row in rows for r in repo.decode(row)["draft"].input_snapshot.rooms}
        if body.room_id not in known:
            raise HTTPException(422, "Choose a room in this authorized published scope")
        old = db.execute(
            "SELECT payload FROM publication_room_restrictions WHERE tenant=? AND dataset=? "
            "AND id=?",
            (tenant, body.dataset, body.id),
        ).fetchone()
        revision = json.loads(old[0])["revision"] if old else 0
        if revision != body.expected_revision:
            raise HTTPException(409, "Restriction changed; reload before editing")
        db.execute(
            "INSERT INTO publication_room_restrictions VALUES (?,?,?,?) "
            "ON CONFLICT(tenant,dataset,id) DO UPDATE SET payload=excluded.payload",
            (tenant, body.dataset, body.id, json.dumps(value)),
        )
    return value

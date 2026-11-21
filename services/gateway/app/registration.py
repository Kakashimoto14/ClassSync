"""Private, temporary extraction and reviewed matching behind the existing Gateway."""

import asyncio
import time
from collections import OrderedDict, deque
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from threading import BoundedSemaphore, Event, Lock, Thread
from urllib.parse import quote
from uuid import UUID, uuid4

import httpx
from classync_contracts.cloud_run import service_headers
from classync_contracts.models import UserRole
from classync_contracts.request_authorization import request_identity, request_principal
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from .registration_parser import normalized_code
from .registration_processing import process_document
from .registration_schema import RegistrationReview, review_openapi_schema


class RegistrationStore:
    def __init__(self, *, clock=time.monotonic, capacity=128):
        self.clock, self.capacity = clock, capacity
        self.entries, self.buckets, self.lock = OrderedDict(), OrderedDict(), Lock()
        self.processing = BoundedSemaphore(2)

    @contextmanager
    def lifecycle(self):
        stop = Event()

        def clean():
            while not stop.wait(15):
                with self.lock:
                    self.purge()

        worker = Thread(target=clean, name="classsync-private-scan-retention", daemon=True)
        worker.start()
        try:
            yield
        finally:
            stop.set()
            worker.join(timeout=2)
            with self.lock:
                self.entries.clear()
                self.buckets.clear()

    def throttle(self, uid, *, kind="upload", window=900, limit=5):
        now = self.clock()
        with self.lock:
            key = (uid, kind)
            bucket = self.buckets.setdefault(key, deque())
            self.buckets.move_to_end(key)
            while bucket and bucket[0] < now - window:
                bucket.popleft()
            if len(bucket) >= limit:
                raise HTTPException(
                    429,
                    "You have reached the scan limit. Try again later or "
                    "enter your courses manually.",
                    headers={"Retry-After": "900"},
                )
            bucket.append(now)
            while len(self.buckets) > 4096:
                self.buckets.popitem(last=False)

    def purge(self):
        now = self.clock()
        for key in [key for key, value in self.entries.items() if value["until"] <= now]:
            del self.entries[key]

    def save(self, tenant, uid, result, retention):
        with self.lock:
            self.purge()
            own = [
                key
                for key, value in self.entries.items()
                if value["tenant"] == tenant and value["uid"] == uid
            ]
            for key in own[:-2]:
                del self.entries[key]
            while len(self.entries) >= self.capacity:
                self.entries.popitem(last=False)
            key = str(uuid4())
            expires = datetime.now(UTC) + timedelta(seconds=retention)
            result = {
                **result,
                "id": key,
                "expires_at": expires.isoformat(),
                "original_retained": False,
            }
            self.entries[key] = {
                "tenant": tenant,
                "uid": uid,
                "until": self.clock() + retention,
                "data": result,
            }
            return result

    def read(self, key, tenant, uid, *, delete=False):
        with self.lock:
            self.purge()
            result = self.entries.get(str(key))
            if not result or result["tenant"] != tenant or result["uid"] != uid:
                raise HTTPException(
                    404,
                    "This scan is unavailable or expired. Upload again or "
                    "enter your courses manually.",
                )
            if delete:
                del self.entries[str(key)]
            return result["data"]

    def record_review(self, key, tenant, uid, review):
        with self.lock:
            self.purge()
            entry = self.entries.get(str(key))
            if not entry or entry["tenant"] != tenant or entry["uid"] != uid:
                raise HTTPException(404, "This scan expired. Upload again or enter your courses.")
            entry["data"] = {**entry["data"], "reviewed": review.model_dump(mode="json")}


def match_review(review, *, periods, calendars):
    matching = [
        p
        for p in periods
        if p.get("calendar", {}).get("academic_year") == review.academic_year
        and p.get("calendar", {}).get("semester") == review.semester
    ]
    if not matching:
        return {
            "status": "wrong-term" if periods else "unassigned",
            "message": "No authorized published enrollment was found for this academic term.",
            "courses": [],
        }
    offerings = {}
    for period in matching:
        for event in calendars.get(period["id"], {}).get("occurrences", []):
            if event.get("subject", {}).get("code_source") != "academic-record":
                continue
            key = (period["id"], event["offering_id"])
            offerings[key] = {
                "period_id": period["id"],
                "offering_id": event["offering_id"],
                "subject": event["subject"],
                "section": event["section"],
            }
    rows = []
    for course in review.courses:
        candidates = [
            value
            for value in offerings.values()
            if normalized_code(value["subject"]["code"]) == normalized_code(course.code)
        ]
        # Numeric document sections cannot be expanded into institutional names.
        # Existing verified enrollment selects the caller's published offering;
        # the numeric document field remains explicitly unresolved.
        if course.section and not course.section.isdigit():
            candidates = [
                value
                for value in candidates
                if value["section"]["name"].strip().casefold() == course.section.casefold()
            ]
        state = "matched" if len(candidates) == 1 else "ambiguous" if candidates else "unmatched"
        rows.append(
            {
                "code": course.code,
                "document_section": course.section,
                "status": state,
                "section_source": "verified-enrollment" if state == "matched" else None,
                "document_section_verified": bool(course.section)
                and not course.section.isdigit()
                and state == "matched",
                "offering": candidates[0] if state == "matched" else None,
            }
        )
    complete = all(row["status"] == "matched" for row in rows)
    return {
        "status": "matched" if complete else "pending-match",
        "courses": rows,
        "message": "Courses matched your verified enrollment and published timetable. "
        "Numeric document sections were not used to infer section names."
        if complete
        else "Some courses could not be matched. Your university may "
        "need to verify the term, course codes or enrollment sections.",
        "period_ids": sorted({row["offering"]["period_id"] for row in rows if row["offering"]}),
        "periods": [
            {
                "id": period["id"],
                "title": period.get("title", "Published term"),
                "start": min(
                    (
                        event["date"]
                        for event in calendars.get(period["id"], {}).get("occurrences", [])
                        if event.get("date")
                        and any(
                            row["offering"]
                            and row["offering"]["period_id"] == period["id"]
                            and row["offering"]["offering_id"] == event.get("offering_id")
                            for row in rows
                        )
                    ),
                    default=period["calendar"].get("effective_start"),
                ),
            }
            for period in matching
            if any(row["offering"] and row["offering"]["period_id"] == period["id"] for row in rows)
        ],
    }


def fetch_matches(request, settings, review, principal):
    # Recheck current role before any institutional read, including after an upload.
    try:
        identity = request_identity(request, settings, required_role=UserRole.STUDENT)
    except HTTPException as error:
        if error.status_code == 403:
            repository = getattr(request.app.state, "onboarding_repository", None)
            if (
                repository is None
                or repository.status(principal).get("membership_state") is not None
            ):
                raise
            return {
                "status": "pending-verification",
                "courses": [],
                "message": "Your university must verify your student record "
                "before classes can be matched.",
            }, None
        raise
    if identity["role"] != "student":
        raise HTTPException(403, "Student access is required to match enrollment")
    if review.student_identifier != identity["student_id"]:
        return {
            "status": "pending-verification",
            "courses": [],
            "message": "The document identifier does not match your verified student record. "
            "Contact your university; this document cannot change your record link.",
        }, identity
    deadline = time.monotonic() + 15
    try:
        headers = service_headers(
            settings.cloud_run_iam_enabled, settings.scheduling_service_url,
            {"Authorization": request.headers["Authorization"], "X-ClassSync-Role": "student"},
        )
        with httpx.Client(
            base_url=settings.scheduling_service_url, timeout=4, trust_env=False
        ) as client:
            response = client.get("/api/v1/timetables/periods", headers=headers)
            response.raise_for_status()
            periods = response.json()["periods"]
            matching = [
                p
                for p in periods
                if p.get("calendar", {}).get("academic_year") == review.academic_year
                and p.get("calendar", {}).get("semester") == review.semester
            ]
            if len(matching) > 10:
                raise HTTPException(
                    422, "Too many matching academic scopes; contact your university"
                )
            calendars = {}
            for period in matching:
                calendar = period["calendar"]
                start, stop = (
                    date.fromisoformat(calendar["effective_start"]),
                    date.fromisoformat(calendar["effective_end"]),
                )
                if (stop - start).days > 370 or stop < start:
                    raise ValueError("invalid_calendar")
                events, version = [], None
                while start <= stop:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise httpx.TimeoutException("matching_timeout")
                    end = min(start + timedelta(days=62), stop)
                    response = client.get(
                        "/api/v1/timetables/calendar/" + quote(period["id"], safe=""),
                        params={"start": start.isoformat(), "end": end.isoformat()},
                        headers=headers,
                        timeout=min(4, remaining),
                    )
                    response.raise_for_status()
                    payload = response.json()
                    if payload.get("status") != "published":
                        raise ValueError("unpublished")
                    if version is not None and version != payload.get("version"):
                        raise HTTPException(
                            409, "The timetable changed while matching. Review again."
                        )
                    version = payload.get("version")
                    events.extend(payload["occurrences"])
                    if len(events) > 10_000:
                        raise HTTPException(
                            422, "This enrollment scope is too large to match automatically"
                        )
                    start = end + timedelta(days=1)
                calendars[period["id"]] = {"occurrences": events}
        return match_review(review, periods=periods, calendars=calendars), identity
    except httpx.HTTPStatusError as error:
        if error.response.status_code in {401, 403}:
            raise HTTPException(
                error.response.status_code, "Current Student access could not be verified"
            ) from error
        raise HTTPException(
            503, "Published timetable matching is unavailable. Try again later."
        ) from error
    except (httpx.HTTPError, ValueError, KeyError) as error:
        raise HTTPException(
            503, "Published timetable matching is unavailable. Try again later."
        ) from error


def registration_router(settings):
    router = APIRouter(prefix="/api/v1/auth/registration-documents", tags=["Registration scanner"])
    store = RegistrationStore()
    router.registration_store = store

    def read_scan(key, tenant, uid, reviews):
        if reviews is not None:
            reviewed = reviews.read(key, tenant, uid)
            if reviewed is not None:
                return reviewed
        return store.read(key, tenant, uid)

    def context(request, *, erase=False):
        current = settings()
        principal = request_principal(request, current)
        if not principal.email_verified:
            raise HTTPException(403, "Verify your email before scanning your registration form")
        repository = getattr(request.app.state, "onboarding_repository", None)
        if repository is None:
            raise HTTPException(503, "Account verification is unavailable. Try again later.")
        status = repository.status(principal)
        if status.get("membership_state") in {"revoked", "inactive"} and not erase:
            raise HTTPException(
                403, "Current university access is inactive; contact your university"
            )
        if status.get("membership_state") == "active" and not erase:
            request_identity(request, current, required_role=UserRole.STUDENT)
        return principal, current

    @router.post(
        "",
        status_code=201,
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    content_type: {"schema": {"type": "string", "format": "binary"}}
                    for content_type in ("application/pdf", "image/jpeg", "image/png")
                },
            }
        },
    )
    async def upload(request: Request, response: Response):
        principal, current = await run_in_threadpool(context, request)
        store.throttle(principal.uid)
        mime = request.headers.get("Content-Type", "").split(";", 1)[0].lower()
        extensions = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png"}
        if mime not in extensions:
            raise HTTPException(415, "Choose a PDF, JPEG or PNG registration form")
        if not store.processing.acquire(blocking=False):
            raise HTTPException(
                429, "Scanner is busy. Try again shortly.", headers={"Retry-After": "5"}
            )
        try:
            chunks, size = [], 0
            try:
                async with asyncio.timeout(15):
                    async for chunk in request.stream():
                        size += len(chunk)
                        if size > current.registration_max_bytes:
                            raise HTTPException(
                                413,
                                "This file is too large. Choose a file within the upload limit.",
                            )
                        chunks.append(chunk)
            except TimeoutError as error:
                raise HTTPException(
                    408, "The upload timed out. Try again with a smaller file."
                ) from error
            if not size:
                raise HTTPException(422, "Choose a registration form to scan")
            result = await run_in_threadpool(
                process_document,
                b"".join(chunks),
                extensions[mime],
                max_pages=current.registration_max_pages,
                timeout=current.registration_timeout_seconds,
            )
            response.headers["Cache-Control"] = "no-store"
            return {
                "data": store.save(
                    current.institutional_tenant_id,
                    principal.uid,
                    result,
                    current.registration_retention_seconds,
                )
            }
        finally:
            store.processing.release()

    @router.post("/manual", status_code=201)
    def manual(request: Request, response: Response):
        principal, current = context(request)
        store.throttle(principal.uid)
        result = {
            "method": "manual",
            "fields": {},
            "courses": [],
            "warnings": [],
            "status": "needs-review",
            "confidence_available": False,
        }
        response.headers["Cache-Control"] = "no-store"
        return {
            "data": store.save(
                current.institutional_tenant_id,
                principal.uid,
                result,
                current.registration_retention_seconds,
            )
        }

    @router.get("/{scan_id}")
    def read(scan_id: UUID, request: Request, response: Response):
        principal, current = context(request)
        reviews = getattr(request.app.state, "registration_review_repository", None)
        response.headers["Cache-Control"] = "no-store"
        return {"data": read_scan(scan_id, current.institutional_tenant_id, principal.uid, reviews)}

    @router.delete("/{scan_id}", status_code=204)
    def erase(scan_id: UUID, request: Request):
        principal, current = context(request, erase=True)
        tenant = current.institutional_tenant_id
        reviews = getattr(request.app.state, "registration_review_repository", None)
        if reviews is None:
            store.read(scan_id, tenant, principal.uid, delete=True)
        else:
            scan = read_scan(scan_id, tenant, principal.uid, reviews)
            reviews.erase(
                scan_id, tenant, principal.uid, datetime.fromisoformat(scan["expires_at"])
            )
            try:
                store.read(scan_id, tenant, principal.uid, delete=True)
            except HTTPException as error:
                if error.status_code != 404:
                    raise
        return Response(status_code=204, headers={"Cache-Control": "no-store"})

    @router.post(
        "/{scan_id}/review",
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": review_openapi_schema()}},
            }
        },
    )
    async def review(scan_id: UUID, request: Request, response: Response):
        principal, current = await run_in_threadpool(context, request)
        tenant = current.institutional_tenant_id
        store.throttle(principal.uid, kind="review", window=60, limit=10)
        reviews = getattr(request.app.state, "registration_review_repository", None)
        scan = await run_in_threadpool(read_scan, scan_id, tenant, principal.uid, reviews)
        if request.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
            raise HTTPException(415, "Submit the reviewed academic fields as JSON")
        chunks, size = [], 0
        try:
            async with asyncio.timeout(5):
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > 64_000:
                        raise HTTPException(413, "The reviewed course list is too large")
                    chunks.append(chunk)
        except TimeoutError as error:
            raise HTTPException(408, "The review request timed out. Try again.") from error
        try:
            body = RegistrationReview.model_validate_json(b"".join(chunks))
        except ValidationError as error:
            raise HTTPException(
                422,
                "Check the academic year, semester, student number and "
                "course fields before trying again.",
            ) from error
        response.headers["Cache-Control"] = "no-store"
        if not store.processing.acquire(blocking=False):
            raise HTTPException(
                429, "Scanner is busy. Try again shortly.", headers={"Retry-After": "5"}
            )
        try:
            result, binding = await run_in_threadpool(
                fetch_matches, request, current, body, principal,
            )
            if reviews is None:
                store.record_review(scan_id, tenant, principal.uid, body)
            else:
                await run_in_threadpool(context, request)
                await run_in_threadpool(
                    reviews.save, scan_id, tenant, principal.uid,
                    datetime.fromisoformat(scan["expires_at"]), body,
                )
            if binding is not None:
                current_binding = await run_in_threadpool(
                    request_identity, request, current, required_role=UserRole.STUDENT,
                )
                if current_binding != binding:
                    raise HTTPException(
                        403, "Your student access changed. Review your classes again."
                    )
            return {"data": result}
        finally:
            store.processing.release()

    @router.post("/{scan_id}/confirm")
    async def confirm(scan_id: UUID, request: Request, response: Response):
        principal, current = await run_in_threadpool(context, request)
        response.headers["Cache-Control"] = "no-store"
        reviews = getattr(request.app.state, "registration_review_repository", None)
        scan = await run_in_threadpool(
            read_scan, scan_id, current.institutional_tenant_id, principal.uid, reviews
        )
        if scan.get("method") == "manual":
            raise HTTPException(
                403, "Upload and review your Registration Form before confirming it"
            )
        reviewed = scan.get("reviewed")
        if not isinstance(reviewed, dict):
            raise HTTPException(409, "Review your Registration Form before confirming it")
        try:
            review_data = RegistrationReview.model_validate(reviewed)
        except ValidationError as error:
            raise HTTPException(
                422, "Complete the required details from your Registration Form"
            ) from error
        repository = getattr(request.app.state, "onboarding_repository", None)
        if repository is None:
            raise HTTPException(503, "Account verification is unavailable. Try again later.")
        activation = await run_in_threadpool(
            repository.activate_from_cor,
            principal,
            review_data,
            allow_self_verification=current.student_verification_mode == "cor_or_roster",
        )
        try:
            matches, _ = await run_in_threadpool(
                fetch_matches, request, current, review_data, principal
            )
        except HTTPException as error:
            if error.status_code != 503:
                raise
            matches = {
                "status": "unavailable",
                "courses": [],
                "message": (
                    "Your account is active. Published classes could not be checked right now."
                ),
            }
        return {"data": {**activation, "schedule": matches}}

    return router

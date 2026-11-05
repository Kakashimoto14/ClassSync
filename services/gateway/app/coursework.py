"""Explicitly optional coursework APIs. Institutional records stay in PostgreSQL."""

import asyncio
import time
from collections import OrderedDict, deque
from contextlib import contextmanager
from threading import BoundedSemaphore, Lock
from uuid import UUID

from classync_contracts.request_authorization import request_identity
from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.routing import APIRoute

from .coursework_cloud import GoogleCoursework, owner_key
from .coursework_schema import AdvisoryInput, DemoUpload, PreferencePatch, Preferences


class BoundedJSONRequest(Request):
    async def body(self):
        if not hasattr(self, "_body"):
            chunks, size = [], 0
            try:
                async with asyncio.timeout(5):
                    async for chunk in self.stream():
                        size += len(chunk)
                        if size > 33000:
                            raise HTTPException(413, "Course request exceeds the safe size")
                        chunks.append(chunk)
            except TimeoutError as error:
                raise HTTPException(408, "Course request timed out") from error
            self._body = b"".join(chunks)
        return self._body


class CourseworkRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def bounded(request):
            return await original(BoundedJSONRequest(request.scope, request.receive))

        return bounded


def coursework_router(settings):
    router = APIRouter(
        prefix="/api/v1/coursework",
        tags=["Optional course demonstrations"],
        route_class=CourseworkRoute,
    )
    lock, slots = Lock(), BoundedSemaphore(2)
    buckets, advice_buckets, advice_global = OrderedDict(), OrderedDict(), deque()

    @contextmanager
    def context(request, feature):
        config = settings()
        claims = request_identity(request, config)
        if not config.course_cloud_enabled or not config.firebase_project_id:
            raise HTTPException(503, "Course cloud demonstrations are not configured")
        if feature == "files" and not config.course_storage_bucket:
            raise HTTPException(503, "Private course storage is not configured")
        if feature == "advisory" and (not config.gemini_api_key or not config.course_gemini_model):
            raise HTTPException(503, "Course advisory service is not configured")
        owner = owner_key(config.firebase_project_id, claims["tenant_id"], claims["uid"])
        now = time.monotonic()
        with lock:
            bucket = buckets.setdefault(owner, deque())
            buckets.move_to_end(owner)
            while bucket and bucket[0] <= now - 60:
                bucket.popleft()
            if len(bucket) >= 20:
                raise HTTPException(429, "Too many course requests; try again later")
            bucket.append(now)
            if feature == "advisory":
                daily = advice_buckets.setdefault(owner, deque())
                advice_buckets.move_to_end(owner)
                for queue in (daily, advice_global):
                    while queue and queue[0] <= now - 86400:
                        queue.popleft()
                if len(daily) >= 6 or len(advice_global) >= 100:
                    raise HTTPException(429, "The daily course advisory limit has been reached")
                daily.append(now)
                advice_global.append(now)
            for mapping in (buckets, advice_buckets):
                while len(mapping) > 4096:
                    mapping.popitem(last=False)
        if not slots.acquire(blocking=False):
            raise HTTPException(429, "Course services are busy; try again shortly")
        try:
            yield GoogleCoursework(config), owner
        except HTTPException:
            raise
        except Exception as error:
            # Never expose credentials, cloud error bodies, uploaded text or provider URLs.
            raise HTTPException(503, "Course provider unavailable; no result confirmed") from error
        finally:
            slots.release()

    @router.get("/preferences")
    def read(request: Request):
        with context(request, "preferences") as (provider, owner):
            return {"data": provider.preference(owner, "read")}

    @router.post("/preferences", status_code=201)
    def create(body: Preferences, request: Request):
        with context(request, "preferences") as (provider, owner):
            return {"data": provider.preference(owner, "create", body)}

    @router.patch("/preferences")
    def edit(body: PreferencePatch, request: Request):
        if body.calendar_view is None and body.compact is None:
            raise HTTPException(422, "Choose a preference to change")
        with context(request, "preferences") as (provider, owner):
            return {
                "data": provider.preference(
                    owner, "update", body, body.expected_revision, body.expected_generation
                )
            }

    @router.delete("/preferences")
    def delete(request: Request, expected_generation: UUID, expected_revision: int = Query(ge=1)):
        with context(request, "preferences") as (provider, owner):
            return {
                "data": provider.preference(
                    owner, "delete", revision=expected_revision, generation=expected_generation
                )
            }

    @router.post("/files", status_code=201)
    def upload(body: DemoUpload, request: Request):
        with context(request, "files") as (provider, owner):
            return {"data": provider.upload(owner, body.text)}

    @router.get("/files/{identifier}")
    def file(identifier: UUID, request: Request):
        with context(request, "files") as (provider, owner):
            value = provider.file(owner, identifier)
            return Response(
                value,
                media_type="text/plain; charset=utf-8",
                headers={
                    "Content-Disposition": f'attachment; filename="{identifier.hex}.txt"',
                    "X-Content-Type-Options": "nosniff",
                    "Cache-Control": "private, no-store",
                },
            )

    @router.delete("/files/{identifier}")
    def delete_file(identifier: UUID, request: Request):
        with context(request, "files") as (provider, owner):
            return {"data": provider.file(owner, identifier, delete=True)}

    @router.post("/advisory")
    def advisory(body: AdvisoryInput, request: Request):
        with context(request, "advisory") as (provider, _):
            return {"data": provider.advisory(body.topic)}

    return router

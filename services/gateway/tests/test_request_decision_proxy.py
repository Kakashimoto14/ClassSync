"""Gateway decision route: Administrator-only, post-commit, non-blocking Teacher email."""

import asyncio
import logging
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from pydantic import SecretStr

from services.gateway.app import main

HEADERS = {"Authorization": "Bearer e30.e30.synthetic-signature"}
DECIDED = {
    "id": str(uuid4()),
    "status": "fulfilled",
    "owner_uid": "teacher-uid",
    "decision_note": "Lab 3 is free",
    "context": {
        "class": {
            "date": "2026-11-09",
            "starts_at": "2026-11-09T08:00:00+08:00",
            "ends_at": "2026-11-09T09:30:00+08:00",
            "subject": {"code": "IT 311"},
            "section": {"name": "BSIT 3A"},
            "room": {"name": "Room 201"},
        },
        "proposed_room": {"name": "Lab 3"},
    },
}


def body():
    return {"expected_revision": 1, "decision": "approved", "note": "Lab 3 is free"}


@pytest.fixture
def upstream(monkeypatch):
    calls, emails = [], []

    def install(status=200, payload=None):
        async def proxy(service, path, request):
            calls.append((service, path))
            content = {"data": payload or DECIDED} if status < 400 else {
                "error": {"code": "publication_conflict", "message": "Room conflict."}
            }
            return JSONResponse(status_code=status, content=content)

        async def send(owner, notice):
            emails.append((owner, notice))

        monkeypatch.setattr(main, "service_proxy", proxy)
        monkeypatch.setattr(main, "send_request_decision_email", send)
        return calls, emails

    return install


@pytest.mark.parametrize("role", ["teacher", "student"])
def test_only_administrators_reach_the_decision_service(identity_adapters, upstream, role):
    identity_adapters(main, role)
    calls, emails = upstream()
    response = TestClient(main.app).post(
        f"/api/v1/timetables/requests/{uuid4()}/decision", headers=HEADERS, json=body()
    )
    assert response.status_code == 403
    assert calls == [] and emails == []


def test_committed_decision_returns_and_schedules_the_teacher_email(identity_adapters, upstream):
    identity_adapters(main, "administrator")
    calls, emails = upstream()
    request_id = uuid4()
    response = TestClient(main.app).post(
        f"/api/v1/timetables/requests/{request_id}/decision", headers=HEADERS, json=body()
    )
    assert response.status_code == 200 and response.json()["data"]["status"] == "fulfilled"
    assert calls == [("scheduling", f"/api/v1/timetables/requests/{request_id}/decision")]
    assert emails == [
        (
            "teacher-uid",
            {
                "decision": "approved",
                "subject_code": "IT 311",
                "section": "BSIT 3A",
                "class_date": "2026-11-09",
                "time_range": "08:00–09:30",
                "from_room": "Room 201",
                "to_room": "Lab 3",
                "note": "Lab 3 is free",
            },
        )
    ]


def test_rejected_conflict_never_sends_email(identity_adapters, upstream):
    identity_adapters(main, "administrator")
    _, emails = upstream(status=409)
    response = TestClient(main.app).post(
        f"/api/v1/timetables/requests/{uuid4()}/decision", headers=HEADERS, json=body()
    )
    assert response.status_code == 409
    assert response.json()["error"]["message"] == "Room conflict."
    assert emails == []


def test_declined_request_maps_to_a_rejected_notice():
    notice = main.request_decision_email({**DECIDED, "status": "rejected"})
    assert notice["decision"] == "rejected"
    assert main.request_decision_email({**DECIDED, "status": "pending"}) is None
    assert main.request_decision_email(None) is None


def test_email_delivery_failures_are_logged_without_raising(monkeypatch, caplog):
    from classync_contracts import firebase
    from firebase_admin import auth

    monkeypatch.setattr(main.settings, "notification_service_token", SecretStr("x" * 32))
    monkeypatch.setattr(firebase, "initialize_firebase", lambda _: object())
    monkeypatch.setattr(
        auth, "get_user", lambda uid, app=None: SimpleNamespace(email="teacher@example.edu")
    )

    async def timeout(*_, **__):
        raise httpx.ReadTimeout("slow provider")

    monkeypatch.setattr(httpx.AsyncClient, "post", timeout)
    with caplog.at_level(logging.WARNING):
        asyncio.run(main.send_request_decision_email("teacher-uid", {"decision": "approved"}))
    record = next(r for r in caplog.records if r.message == "request_decision_email_failed")
    assert record.failure_type == "ReadTimeout"
    assert "teacher@example.edu" not in caplog.text


def test_missing_notification_token_skips_delivery(monkeypatch, caplog):
    monkeypatch.setattr(main.settings, "notification_service_token", None)
    with caplog.at_level(logging.WARNING):
        asyncio.run(main.send_request_decision_email("teacher-uid", {}))
    assert "request_decision_email_unavailable" in caplog.text


def test_firebase_lookup_failure_is_contained(monkeypatch, caplog):
    from classync_contracts import firebase

    monkeypatch.setattr(main.settings, "notification_service_token", SecretStr("x" * 32))

    def broken(_):
        raise RuntimeError("Firebase unavailable")

    monkeypatch.setattr(firebase, "initialize_firebase", broken)
    with caplog.at_level(logging.WARNING):
        asyncio.run(main.send_request_decision_email("teacher-uid", {}))
    assert "request_decision_email_failed" in caplog.text

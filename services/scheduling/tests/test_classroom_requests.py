"""Request authorization and input boundaries, without opening institutional storage."""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from services.scheduling.app import main
from services.scheduling.app.classroom_requests import RequestInput, Requests

HEADERS = {"Authorization": "Bearer e30.e30.synthetic-signature"}


def body():
    return {
        "period_id": str(uuid4()),
        "publication_id": str(uuid4()),
        "occurrence_id": "owned-session:2026-11-09",
        "class_date": "2026-11-09",
        "proposed_room_id": "owned-room",
        "reason": "Invented local request",
        "idempotency_key": str(uuid4()),
    }


def test_request_reads_require_identity_and_deny_student(identity_adapters):
    client = TestClient(main.app)
    identity_adapters(main, role="student")
    assert client.get("/api/v1/timetables/requests").status_code == 401
    assert client.get("/api/v1/timetables/requests", headers=HEADERS).status_code == 403


def test_teacher_cannot_decide_or_forge_an_administrator_role(identity_adapters):
    identity_adapters(main, role="teacher")
    response = TestClient(main.app).post(
        f"/api/v1/timetables/requests/{uuid4()}/decision",
        headers={**HEADERS, "X-ClassSync-Role": "administrator"},
        json={"expected_revision": 1, "decision": "approved", "note": "Invented decision"},
    )
    assert response.status_code == 403


def test_administrator_cannot_submit_a_faculty_request(identity_adapters):
    identity_adapters(main, role="administrator")
    assert (
        TestClient(main.app)
        .post("/api/v1/timetables/requests", headers=HEADERS, json=body())
        .status_code
        == 403
    )


def test_unconfigured_request_storage_never_falls_back_to_original_sqlite(
    identity_adapters, monkeypatch
):
    identity_adapters(main, role="teacher")
    monkeypatch.setattr(main.settings, "scheduling_database_url", None)

    def forbidden():
        raise AssertionError("Original SQLite must not be opened")

    monkeypatch.setattr(main, "repository", forbidden)
    client = TestClient(main.app)
    assert client.get("/api/v1/timetables/requests", headers=HEADERS).status_code == 503
    assert (
        client.post("/api/v1/timetables/requests", headers=HEADERS, json=body()).status_code == 503
    )


@pytest.mark.parametrize("extra", ["faculty_id", "owner_uid", "status", "tenant_id"])
def test_submitted_identity_or_decision_is_rejected(extra):
    with pytest.raises(ValidationError):
        RequestInput.model_validate({**body(), extra: "attacker-controlled"})


def test_request_summary_never_exposes_private_draft_or_idempotency_material():
    result = Requests.summary(
        {
            "id": uuid4(),
            "draft_id": "private-draft",
            "tenant_id": "private-tenant",
            "input_hash": "private-hash",
            "idempotency_key": uuid4(),
            "status": "pending",
        }
    )
    assert set(result) == {"id", "status"}


def test_request_options_respect_the_offerings_approved_room_list(monkeypatch):
    from datetime import date

    from services.scheduling.app import classroom_requests as module

    event = {
        "id": "owned-class",
        "version": "current",
        "offering_id": "owned-offering",
        "room": {"id": "original"},
    }
    rooms = [
        SimpleNamespace(
            id=value, name=value, building="Invented", floor=None,
            capacity=40, capacity_verified=True,
        )
        for value in ("original", "approved", "outside-approved-list")
    ]
    offering = SimpleNamespace(
        id="owned-offering", section_id="owned-section", eligible_room_ids=["original", "approved"]
    )
    source = SimpleNamespace(
        offerings=[offering],
        rooms=rooms,
        sections=[SimpleNamespace(id="owned-section", program_id="owned-program")],
    )
    publication = SimpleNamespace(
        keys={"tenant": "owned-tenant"},
        rows=lambda *_: [{"id": "current", "revision": 2}],
        head=lambda *_: 2,
        project=lambda *_: {"occurrences": [event]},
        decode=lambda *_: {"draft": SimpleNamespace(input_snapshot=source)},
        member_occupancy=lambda *_, **__: (set(), set()),
    )
    event.update(starts_at="2026-11-09T08:00:00+08:00", ends_at="2026-11-09T09:00:00+08:00")
    monkeypatch.setattr(module, "eligible_room", lambda *_: True)
    monkeypatch.setattr(
        module, "schedulable_space_ids", lambda: {"original", "approved", "outside-approved-list"}
    )
    result = Requests(publication).options_in(
        Mock(), {"role": "teacher"}, "owned-period", date(2026, 11, 9), "owned-class"
    )
    assert [room["id"] for room in result["rooms"]] == ["approved"]


def test_fulfillment_records_the_version_that_actually_supplied_the_class():
    original = {
        "id": "owned-class",
        "date": "2026-11-09",
        "starts_at": "2026-11-09T08:00:00+08:00",
        "ends_at": "2026-11-09T09:00:00+08:00",
    }
    row = {
        "revision": 2,
        "status": "approved",
        "period_id": "owned-period",
        "occurrence_id": "owned-class",
        "faculty_id": "owned-faculty",
        "proposed_room_id": "approved-room",
        "decision_note": "Invented approved decision",
        "context": {"class": original},
    }
    db = Mock()
    db.execute.return_value.mappings.return_value.first.return_value = row
    db.execute.return_value.mappings.return_value.one.return_value = {
        "id": uuid4(),
        "status": "fulfilled",
    }

    @contextmanager
    def session(**_):
        yield db

    event = {
        **original,
        "room": {"id": "approved-room"},
        "teacher": {"id": "owned-faculty"},
        "version": "effective-version-2",
    }
    publication = SimpleNamespace(
        keys={"tenant": "owned-tenant", "owner": "approved-admin"},
        session=session,
        rows=lambda *_: [{"id": "future-version-3"}],
        project=lambda *_: {"occurrences": [event]},
    )
    Requests(publication).decide(
        {"role": "administrator"}, uuid4(), SimpleNamespace(expected_revision=2), fulfill=True
    )
    assert db.execute.call_args.args[1]["version"] == "effective-version-2"

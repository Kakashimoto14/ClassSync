"""Phase 3B: live room occupancy, conflict-validated approval and slot availability.

Storage is faked at the repository boundary; validation runs the real domain rules.
"""

from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from classync_contracts.calendar import AcademicCalendar, CalendarException
from fastapi import HTTPException
from fastapi.testclient import TestClient

from services.scheduling.app import classroom_requests as module
from services.scheduling.app import main
from services.scheduling.app.catalog import (
    excluded_space_ids,
    schedulable_space_ids,
    schedulable_spaces,
)
from services.scheduling.app.classroom_requests import Requests, StaleRequest
from services.scheduling.app.draft_rules import DraftError
from services.scheduling.app.postgres_publication_repository import (
    PostgresPublicationRepository,
)
from services.scheduling.app.publication_rules import request_exception
from services.scheduling.tests.test_publication import setup  # noqa: F401

HEADERS = {"Authorization": "Bearer e30.e30.synthetic-signature"}
CLASS = {
    "id": "assignment-b:2026-11-09",
    "assignment_id": "assignment-b",
    "date": "2026-11-09",
    "starts_at": "2026-11-09T08:00:00+08:00",
    "ends_at": "2026-11-09T09:30:00+08:00",
    "room": {"id": "cdm-current"},
    "teacher": {"id": "faculty-1"},
}


def calendar(**changes):
    return AcademicCalendar(
        academic_year="2026-2027",
        semester="first",
        effective_start=date(2026, 8, 1),
        effective_end=date(2026, 12, 31),
        **changes,
    )


def request_row(**changes):
    return {
        "id": uuid4(),
        "revision": 1,
        "status": "pending",
        "period_id": "period-1",
        "occurrence_id": CLASS["id"],
        "faculty_id": "faculty-1",
        "proposed_room_id": "cdm-proposed",
        "decision_note": None,
        "context": {"class": CLASS, "original_date": "2026-11-09"},
        **changes,
    }


# --- catalog boundary -------------------------------------------------------------------


def test_catalog_boundary_is_exactly_41_schedulable_and_12_excluded():
    assert len(schedulable_spaces()) == 41
    assert len(excluded_space_ids()) == 12
    assert not schedulable_space_ids() & excluded_space_ids()


# --- calendar exception -------------------------------------------------------------------


def test_request_exception_is_a_same_date_same_time_room_move_replacing_prior_change():
    prior = CalendarException(
        date=date(2026, 11, 9),
        assignment_id="assignment-b",
        cancelled=False,
        moved_to=date(2026, 11, 9),
        room_id="cdm-older",
        start=480,
        reason="Earlier move",
    )
    other = CalendarException(date=date(2026, 11, 10), reason="Holiday")
    result = request_exception(
        calendar(exceptions=[prior, other]), request_row()["context"], "cdm-proposed"
    )
    assert result.published_version is None
    assert [item.reason for item in result.exceptions] == [
        "Holiday",
        "Approved classroom change request",
    ]
    change = result.exceptions[-1]
    assert (change.date, change.moved_to, change.start, change.room_id, change.cancelled) == (
        date(2026, 11, 9),
        date(2026, 11, 9),
        480,
        "cdm-proposed",
        False,
    )


def test_request_exception_rejects_malformed_context():
    with pytest.raises(DraftError) as error:
        request_exception(calendar(), {"class": {}}, "cdm-proposed")
    assert error.value.status == 422


def test_request_exception_conflict_is_caught_by_real_publication_review(setup):  # noqa: F811
    repo, draft, command = setup
    repo.publish(command, draft, "tenant", "admin", commit=True)
    events = repo.calendar(
        "tenant",
        "synthetic",
        draft.period_id,
        date(2026, 10, 1),
        date(2026, 10, 31),
        {"role": "administrator"},
    )["occurrences"]
    occupant, moved = next(
        (a, b) for a in events for b in events if a["assignment_id"] != b["assignment_id"]
    )
    # Place the moved class into the occupant's room at the occupant's date and time.
    overlapping = {**moved, "date": occupant["date"], "starts_at": occupant["starts_at"]}
    conflicting = request_exception(
        command.calendar,
        {"class": overlapping, "original_date": moved["date"]},
        occupant["room"]["id"],
    )
    context = {"class": moved, "original_date": moved["date"]}
    with pytest.raises(DraftError, match="onflict"):
        repo.publish(
            command.model_copy(
                update={
                    "calendar": conflicting,
                    "expected_version": 1,
                    "idempotency_key": "request-conflict",
                }
            ),
            draft,
            "tenant",
            "admin",
            commit=False,
        )
    # The same mechanism into the class's own room validates and is flagged as changed.
    same = request_exception(command.calendar, context, moved["room"]["id"])
    reviewed = repo.publish(
        command.model_copy(
            update={"calendar": same, "expected_version": 1, "idempotency_key": "request-ok"}
        ),
        draft,
        "tenant",
        "admin",
        commit=True,
    )
    assert reviewed["revision"] == 2
    day = date.fromisoformat(moved["date"])
    after = repo.calendar(
        "tenant", "synthetic", draft.period_id, day, day, {"role": "administrator"}
    )["occurrences"]
    assert next(e for e in after if e["id"] == moved["id"])["changed"] is True


# --- occupancy ----------------------------------------------------------------------------


def occupancy_repo(events, restrictions=()):
    db = Mock()
    db.execute.return_value.mappings.return_value = list(restrictions)
    repo = SimpleNamespace(
        keys={"tenant": "tenant"},
        rows=lambda *_: [{"id": "v1"}],
        expanded=lambda *_: events,
        params=lambda dataset, **values: {"dataset": dataset, **values},
        restriction_value=lambda row: row,
    )
    return repo, db


def window(start, end):
    from datetime import datetime

    from services.scheduling.app.occurrences import ZONE

    return (
        datetime.fromisoformat(f"2026-11-09T{start}:00").replace(tzinfo=ZONE),
        datetime.fromisoformat(f"2026-11-09T{end}:00").replace(tzinfo=ZONE),
    )


def test_occupancy_is_half_open_and_restrictions_are_admin_opt_in():
    events = [
        {"room": {"id": "busy"}, "starts_at": "2026-11-09T08:00:00+08:00",
         "ends_at": "2026-11-09T09:30:00+08:00"},
        {"room": {"id": "adjacent"}, "starts_at": "2026-11-09T09:30:00+08:00",
         "ends_at": "2026-11-09T11:00:00+08:00"},
    ]
    restriction = {"room_id": "reserved", "starts_at": "2026-11-09T07:00:00+08:00",
                   "ends_at": "2026-11-09T12:00:00+08:00"}
    repo, db = occupancy_repo(events, [restriction])
    begin, finish = window("08:30", "09:30")
    occupied, restricted = PostgresPublicationRepository.occupancy_in(
        repo, db, "institutional", begin, finish, restrictions=False
    )
    assert occupied == {"busy"} and restricted == set()
    db.execute.assert_not_called()
    _, restricted = PostgresPublicationRepository.occupancy_in(
        repo, db, "institutional", begin, finish, restrictions=True
    )
    assert restricted == {"reserved"}


def test_occupancy_rejects_multi_day_or_reversed_windows():
    repo, db = occupancy_repo([])
    begin, finish = window("10:00", "09:00")
    with pytest.raises(DraftError):
        PostgresPublicationRepository.occupancy_in(
            repo, db, "institutional", begin, finish, restrictions=False
        )
    from datetime import timedelta

    begin, finish = window("20:00", "21:00")
    with pytest.raises(DraftError):
        PostgresPublicationRepository.occupancy_in(
            repo, db, "institutional", begin, finish + timedelta(days=1), restrictions=False
        )


# --- teacher options and submission ------------------------------------------------------


def options_publication(occupied):
    rooms = [
        SimpleNamespace(id=value, name=value, building="Main", floor="1",
                        capacity=40, capacity_verified=value != "free")
        for value in ("cdm-current", "free", "busy", "excluded")
    ]
    offering = SimpleNamespace(
        id="offering", section_id="section",
        eligible_room_ids=["cdm-current", "free", "busy", "excluded"],
    )
    source = SimpleNamespace(
        offerings=[offering], rooms=rooms,
        sections=[SimpleNamespace(id="section", program_id="bsit")],
    )
    event = {**CLASS, "id": "owned", "version": "v1", "offering_id": "offering"}
    return SimpleNamespace(
        keys={"tenant": "tenant"},
        rows=lambda *_: [{"id": "v1", "revision": 1}],
        head=lambda *_: 1,
        project=lambda *_: {"occurrences": [event]},
        decode=lambda *_: {"draft": SimpleNamespace(input_snapshot=source)},
        member_occupancy=lambda *_, **__: (occupied, set()),
    )


def test_options_flag_occupied_and_never_list_excluded_spaces(monkeypatch):
    monkeypatch.setattr(module, "eligible_room", lambda *_: True)
    monkeypatch.setattr(module, "schedulable_space_ids", lambda: {"cdm-current", "free", "busy"})
    result = Requests(options_publication({"busy"})).options_in(
        Mock(), {"role": "teacher"}, "period", date(2026, 11, 9), "owned"
    )
    assert [(room["id"], room["occupancy"]) for room in result["rooms"]] == [
        ("free", "available"),
        ("busy", "occupied"),
    ]
    assert result["rooms"][0]["capacity"] is None  # unverified capacity is withheld


def submit(monkeypatch, room_id, occupancy):
    db = Mock()
    db.execute.return_value.mappings.return_value.first.return_value = None
    db.scalar.return_value = 0

    @contextmanager
    def session(**_):
        yield db

    publication_id = str(uuid4())
    publication = SimpleNamespace(keys={"tenant": "tenant", "owner": "teacher"}, session=session)
    monkeypatch.setattr(
        Requests,
        "options_in",
        lambda *_: {
            "publication_id": publication_id,
            "class": CLASS,
            "rooms": [{"id": "cdm-busy", "occupancy": occupancy}],
        },
    )
    body = module.RequestInput(
        period_id=uuid4(), publication_id=publication_id, occurrence_id=CLASS["id"],
        class_date=date(2026, 11, 9), proposed_room_id=room_id,
        reason="Projector is broken", idempotency_key=uuid4(),
    )
    with pytest.raises(HTTPException) as error:
        Requests(publication).create({"faculty_id": "faculty-1"}, body)
    return error.value, db


def test_create_rejects_an_occupied_room_with_409(monkeypatch):
    error, db = submit(monkeypatch, "cdm-busy", "occupied")
    assert error.status_code == 409 and "occupied" in error.detail
    assert not any("INSERT" in str(call.args[0]) for call in db.execute.call_args_list)


def test_create_rejects_an_excluded_space_with_422(monkeypatch):
    excluded = sorted(excluded_space_ids())[0]
    error, _ = submit(monkeypatch, excluded, "available")
    assert error.status_code == 422 and "excluded" in error.detail


# --- administrator preflight and approval -------------------------------------------------


def approval_requests(monkeypatch, *, check=None, publish=None):
    transitions = []
    requests = Requests(SimpleNamespace(publish_in=publish or (lambda *_, **__: {"id": "v2"})))
    monkeypatch.setattr(requests, "check_candidate", check or (lambda *_: "command"))
    monkeypatch.setattr(
        requests,
        "transition",
        lambda db, request_id, status, note, version: transitions.append((status, version))
        or {"id": request_id, "status": status, "fulfilled_version": version},
    )
    return requests, transitions


def test_approval_publishes_then_approves_and_fulfils_in_one_transaction(monkeypatch):
    commits = []
    requests, transitions = approval_requests(
        monkeypatch, publish=lambda db, command, commit: commits.append(commit) or {"id": "v2"}
    )
    result = requests.approve_in(Mock(), request_row(), uuid4(), "Room is free")
    assert commits == [True]
    assert transitions == [("approved", None), ("fulfilled", "v2")]
    assert result["fulfilled_version"] == "v2"


@pytest.mark.parametrize(
    ("failure", "code"),
    [
        (DraftError(422, "publication_conflict", "Room conflict between a and b."),
         "publication_conflict"),
        (DraftError(422, "room_restricted", "Reserved."), "room_restricted"),
        (StaleRequest("The class changed since this request was submitted."), "request_stale"),
    ],
)
def test_conflicting_or_stale_approval_raises_without_any_status_change(
    monkeypatch, failure, code
):
    def check(*_):
        raise failure

    requests, transitions = approval_requests(monkeypatch, check=check)
    with pytest.raises(DraftError) as error:
        requests.approve_in(Mock(), request_row(), uuid4(), "Room is free")
    assert (error.value.status, error.value.code) == (409, code)
    assert str(error.value) == str(failure)
    assert transitions == []


def test_publication_failure_after_validation_leaves_request_pending(monkeypatch):
    def publish(*_, **__):
        raise DraftError(409, "publication_version_conflict", "A competing change.")

    requests, transitions = approval_requests(monkeypatch, publish=publish)
    with pytest.raises(DraftError):
        requests.approve_in(Mock(), request_row(), uuid4(), "Room is free")
    assert transitions == []


def test_storage_failures_are_not_reported_as_conflicts(monkeypatch):
    def publish(*_, **__):
        raise DraftError(503, "persistence_unavailable", "Unavailable")

    requests, _ = approval_requests(monkeypatch, publish=publish)
    with pytest.raises(DraftError) as error:
        requests.approve_in(Mock(), request_row(), uuid4(), "Room is free")
    assert error.value.status == 503


def preflight_requests(monkeypatch, row, *, check=None, report=None, locked=()):
    @contextmanager
    def session(**_):
        yield Mock()

    snapshot = SimpleNamespace(locked_assignments=[SimpleNamespace(id=i) for i in locked])
    publication = SimpleNamespace(
        session=session,
        publish_in=lambda *_, **__: report or {"occurrences": 10},
        keys={"tenant": "tenant"},
        rows=lambda *_: [{"id": "v1", "revision": 1}],
        decode=lambda *_: {"draft": SimpleNamespace(input_snapshot=snapshot)},
    )
    requests = Requests(publication)
    monkeypatch.setattr(requests, "request_row", lambda *_, **__: row)
    monkeypatch.setattr(requests, "check_candidate", check or (lambda *_: "command"))
    return requests


def test_preflight_warns_when_a_locked_session_would_move(monkeypatch):
    row = request_row()
    assignment = row["occurrence_id"].rsplit(":", 1)[0]
    clear = preflight_requests(monkeypatch, row).preflight(uuid4())
    assert clear["state"] == "clear" and clear["warnings"] == []
    locked = preflight_requests(monkeypatch, row, locked=[assignment]).preflight(uuid4())
    assert locked["state"] == "clear"
    assert [w["code"] for w in locked["warnings"]] == ["locked_assignment"]


def test_preflight_reports_clear_conflict_stale_and_decided(monkeypatch):
    assert preflight_requests(monkeypatch, request_row()).preflight(uuid4())["state"] == "clear"

    def conflict(*_):
        raise DraftError(422, "room_occupied", "The proposed room is now occupied.")

    result = preflight_requests(monkeypatch, request_row(), check=conflict).preflight(uuid4())
    assert result["state"] == "conflict" and result["reasons"] == [
        "The proposed room is now occupied."
    ]

    def stale(*_):
        raise StaleRequest("This class date has passed.")

    assert (
        preflight_requests(monkeypatch, request_row(), check=stale).preflight(uuid4())["state"]
        == "stale"
    )
    decided = preflight_requests(monkeypatch, request_row(status="rejected")).preflight(uuid4())
    assert decided["state"] == "decided"


def candidate_publication(*, owner="admin", event=None):
    latest = {"id": "v1", "revision": 1, "draft_id": "draft-1"}
    return SimpleNamespace(
        keys={"tenant": "tenant"},
        principal=SimpleNamespace(uid="admin"),
        rows=lambda *_: [latest],
        head=lambda *_: 1,
        project=lambda *_: {"occurrences": [event] if event else []},
        decode=lambda *_: {"calendar": calendar()},
        academic=SimpleNamespace(
            snapshot_in=lambda *_: SimpleNamespace(period=SimpleNamespace(revision=7))
        ),
    ), owner


def run_candidate(publication, owner, *, today=date(2026, 11, 1)):
    db = Mock()
    db.scalar.return_value = owner
    return Requests(publication).candidate(db, request_row(), today=today)


def test_candidate_binds_current_head_academic_revision_and_request_key():
    publication, owner = candidate_publication(event=CLASS)
    command = run_candidate(publication, owner)
    assert (command.draft_id, command.expected_version, command.expected_academic_revision) == (
        "draft-1",
        1,
        7,
    )
    assert command.idempotency_key.startswith("classroom-request:")
    assert command.calendar.exceptions[-1].room_id == "cdm-proposed"


def test_candidate_requires_the_publication_head_owner():
    publication, _ = candidate_publication(event=CLASS)
    with pytest.raises(DraftError) as error:
        run_candidate(publication, "another-admin")
    assert error.value.code == "publication_owner_conflict" and error.value.status == 409


@pytest.mark.parametrize(
    "event",
    [
        None,
        {**CLASS, "teacher": {"id": "someone-else"}},
        {**CLASS, "starts_at": "2026-11-09T10:00:00+08:00"},
        {**CLASS, "room": {"id": "cdm-proposed"}},
    ],
)
def test_candidate_is_stale_when_the_class_changed(event):
    publication, owner = candidate_publication(event=event)
    with pytest.raises(StaleRequest):
        run_candidate(publication, owner)


def test_candidate_is_stale_for_a_past_class_date():
    publication, owner = candidate_publication(event=CLASS)
    with pytest.raises(StaleRequest, match="passed"):
        run_candidate(publication, owner, today=date(2026, 11, 10))


def test_check_candidate_blocks_excluded_occupied_and_restricted_rooms(monkeypatch):
    requests = Requests(SimpleNamespace(occupancy_in=lambda *_, **__: ({"busy"}, {"reserved"})))
    monkeypatch.setattr(requests, "candidate", lambda *_: "command")
    monkeypatch.setattr(module, "schedulable_space_ids", lambda: {"busy", "reserved", "free"})
    for room, code in (("excluded", "room_excluded"), ("busy", "room_occupied"),
                       ("reserved", "room_restricted")):
        with pytest.raises(DraftError) as error:
            requests.check_candidate(Mock(), request_row(proposed_room_id=room))
        assert error.value.code == code
    assert requests.check_candidate(Mock(), request_row(proposed_room_id="free")) == "command"


def test_teacher_and_student_cannot_preflight(identity_adapters):
    client = TestClient(main.app)
    for role in ("teacher", "student"):
        identity_adapters(main, role=role)
        response = client.get(
            f"/api/v1/timetables/requests/{uuid4()}/preflight",
            headers={**HEADERS, "X-ClassSync-Role": "administrator"},
        )
        assert response.status_code == 403


# --- slot availability --------------------------------------------------------------------


def slot_repo(role="student"):
    inputs = SimpleNamespace(
        operating_windows=[SimpleNamespace(day=0, start=420, end=1260)],
        enrollments=[SimpleNamespace(student_id="student-1", offering_ids=["o"])],
    )
    value = {
        "calendar": calendar(),
        "draft": SimpleNamespace(
            input_snapshot=inputs,
            generation_result=SimpleNamespace(assignments=[]),
        ),
    }
    calls = {}

    @contextmanager
    def session(**kwargs):
        calls["session"] = kwargs
        yield Mock()

    def occupancy_in(db, dataset, begin, finish, *, restrictions):
        calls["restrictions"] = restrictions
        first = schedulable_spaces()[0].id
        return {first}, set()

    def member_occupancy(db, dataset, begin, finish):
        # Non-Administrators read tenant-wide room-only occupancy (migration 0028).
        calls["member"] = dataset
        first = schedulable_spaces()[0].id
        return {first}, set()

    repo = SimpleNamespace(
        keys={"tenant": "tenant"},
        session=session,
        head=lambda *_: 1,
        rows=lambda *_: [{"id": "v1", "revision": 1}],
        decode=lambda *_: value,
        occupancy_in=occupancy_in,
        member_occupancy=member_occupancy,
    )
    return repo, calls


def test_slot_lists_41_rooms_with_occupancy_only_for_an_enrolled_student():
    repo, calls = slot_repo()
    viewer = {"role": "student", "student_id": "student-1"}
    result = PostgresPublicationRepository.room_slot(
        repo, "period", date(2026, 11, 9), 480, 570, viewer
    )
    assert len(result["rooms"]) == 41
    assert {key for room in result["rooms"] for key in room} == {
        "id", "name", "building", "floor", "occupancy",
    }
    assert result["rooms"][0]["occupancy"] == "occupied"
    assert {room["occupancy"] for room in result["rooms"][1:]} == {"free"}
    assert not {room["id"] for room in result["rooms"]} & excluded_space_ids()
    assert calls["session"] == {"role": "student", "record_id": "student-1"}
    # Students see reservations too, as room ids only; never the restriction details.
    assert "restrictions" not in calls and calls["member"] == "institutional"
    assert result["restrictions_checked"] is True


def test_slot_denies_unenrolled_students():
    repo, _ = slot_repo()
    with pytest.raises(DraftError) as error:
        PostgresPublicationRepository.room_slot(
            repo, "period", date(2026, 11, 9), 480, 570,
            {"role": "student", "student_id": "someone-else"},
        )
    assert error.value.status == 403


@pytest.mark.parametrize(
    ("day", "start", "end", "code"),
    [
        (date(2026, 11, 9), 485, 570, "availability_range"),
        (date(2026, 11, 9), 600, 540, "availability_range"),
        (date(2026, 11, 8), 480, 570, "availability_day"),
        (date(2027, 1, 4), 480, 570, "availability_day"),
        (date(2026, 11, 9), 360, 450, "availability_hours"),
    ],
)
def test_slot_validates_alignment_instructional_day_and_operating_hours(day, start, end, code):
    repo, _ = slot_repo()
    with pytest.raises(DraftError) as error:
        PostgresPublicationRepository.room_slot(
            repo, "period", day, start, end, {"role": "student", "student_id": "student-1"}
        )
    assert error.value.code == code


def decide_with(row):
    @contextmanager
    def session(**_):
        yield Mock()

    requests = Requests(SimpleNamespace(session=session))
    requests.request_row = lambda *_, **__: row
    return requests


def test_a_retried_approval_returns_the_recorded_result_instead_of_an_error():
    row = request_row(revision=3, status="fulfilled", decision_note="Room is free")
    body = SimpleNamespace(expected_revision=1, decision="approved", note="Room is free")
    assert decide_with(row).decide({}, uuid4(), body)["status"] == "fulfilled"


@pytest.mark.parametrize(
    "body",
    [
        SimpleNamespace(expected_revision=1, decision="approved", note="Different note"),
        SimpleNamespace(expected_revision=1, decision="rejected", note="Room is free"),
        SimpleNamespace(expected_revision=2, decision="approved", note="Room is free"),
    ],
)
def test_other_decisions_on_a_changed_request_still_conflict(body):
    row = request_row(revision=3, status="fulfilled", decision_note="Room is free")
    with pytest.raises(HTTPException) as error:
        decide_with(row).decide({}, uuid4(), body)
    assert error.value.status_code == 409


def test_candidate_is_stale_when_an_earlier_change_already_moved_the_class():
    publication, owner = candidate_publication(event={**CLASS, "room": {"id": "cdm-elsewhere"}})
    with pytest.raises(StaleRequest, match="moved"):
        run_candidate(publication, owner)

from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from classync_contracts.publication import PublicationCommand
from classync_contracts.scheduling import SaveDraftRequest
from fastapi.testclient import TestClient

from services.academic.app.fixtures import import_fixture
from services.academic.app.repository import AcademicRepository
from services.scheduling.app.academic_input import academic_readiness
from services.scheduling.app.draft_repository import DraftError, DraftRepository
from services.scheduling.app.engine import generate_week
from services.scheduling.app.publication_repository import PublicationRepository
from services.scheduling.tests.test_calendar import configuration


@pytest.fixture
def setup(tmp_path):
    academic = AcademicRepository(tmp_path / "a.db")
    academic.migrate()
    snapshot = import_fixture(academic, configuration(), "sandbox", "test")
    checked = academic_readiness(snapshot)
    result = generate_week(checked.inputs)
    repo = DraftRepository(tmp_path / "s.db")
    repo.migrate()
    repo.remember_run(checked.inputs, result, "academic-sandbox", "test")
    draft, _ = repo.save(
        SaveDraftRequest(
            run_id=result.run_id,
            input_hash=result.input_hash,
            title="Sample publication",
            idempotency_key="save-c2-test",
        ),
        "academic-sandbox",
        "test",
    )
    command = PublicationCommand(
        draft_id=draft.id,
        source="academic-sandbox",
        dataset="synthetic",
        expected_version=0,
        expected_academic_revision=snapshot.period.revision,
        idempotency_key="publish-key-1",
        calendar=configuration().calendar,
    )
    return PublicationRepository(repo), draft, command


def test_atomic_publication_idempotency_immutable_history_and_effective_revisions(setup):
    repo, draft, command = setup
    original = draft.model_dump_json()
    reviewed = repo.publish(command, draft, "tenant", "admin", commit=False)
    assert reviewed["status"] == "ready-for-review" and reviewed["sections"] == 1
    v = repo.publish(command, draft, "tenant", "admin", commit=True)
    assert v["status"] == "published" and v["revision"] == 1
    assert repo.publish(command, draft, "tenant", "admin", commit=True)["id"] == v["id"]
    assert repo.drafts.get(draft.id, "academic-sandbox", "test").model_dump_json() == original
    projection = repo.calendar(
        "tenant",
        "synthetic",
        draft.period_id,
        date(2026, 10, 1),
        date(2026, 10, 31),
        {"role": "student", "uid": "mock", "mock_section": "syn-bsit-3-A"},
    )
    assert projection["occurrences"]
    event = projection["occurrences"][0]
    updated = command.calendar.model_copy(deep=True)
    updated.effective_start = date(2026, 11, 16)
    updated.phases = []
    # Effective-dated revision does not erase earlier October occurrences.
    second = command.model_copy(
        update={"calendar": updated, "expected_version": 1, "idempotency_key": "publish-key-2"}
    )
    v2 = repo.publish(second, draft, "tenant", "admin", commit=True)
    assert v2["revision"] == 2 and len(repo.history("tenant", "synthetic", draft.period_id)) == 2
    assert repo.calendar(
        "tenant",
        "synthetic",
        draft.period_id,
        date(2026, 10, 1),
        date(2026, 10, 31),
        {"role": "teacher", "faculty_id": event["teacher"]["id"]},
    )["occurrences"]
    with pytest.raises(DraftError, match="No timetable"):
        repo.calendar(
            "other-tenant",
            "synthetic",
            draft.period_id,
            date(2026, 10, 1),
            date(2026, 10, 31),
            {"role": "administrator"},
        )
    with repo.drafts.connection(write=True) as db:
        with pytest.raises(Exception, match="immutable"):
            db.execute("UPDATE published_versions SET actor=?", ("attacker",))


def test_competing_publications_are_serialized_and_failed_writes_rollback(setup):
    repo, draft, command = setup

    def publish(key):
        try:
            return repo.publish(
                command.model_copy(update={"idempotency_key": key}),
                draft,
                "tenant",
                "admin",
                commit=True,
            )["revision"]
        except DraftError as e:
            return e.status

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(publish, ["concurrent-key-1", "concurrent-key-2"])) == [1, 409]
    assert len(repo.history("tenant", "synthetic", draft.period_id)) == 1
    with pytest.raises(DraftError):
        repo.publish(
            command.model_copy(update={"dataset": "institutional"}),
            draft,
            "tenant",
            "admin",
            commit=True,
        )
    assert not repo.history("tenant", "institutional", draft.period_id)


def test_projection_isolation_irregular_enrollment_and_exception_conflicts(setup):
    repo, draft, command = setup
    from classync_contracts.scheduling import Enrollment

    # Store a distinct valid immutable draft with explicit irregular enrollment.
    inputs = draft.input_snapshot.model_copy(deep=True)
    inputs.enrollments = [Enrollment(student_id="student-a", offering_ids=[inputs.offerings[0].id])]
    generated = generate_week(inputs)
    repo.drafts.remember_run(inputs, generated, "academic-sandbox", "test")
    draft, _ = repo.drafts.save(
        SaveDraftRequest(
            run_id=generated.run_id,
            input_hash=generated.input_hash,
            title="Enrollment scope",
            idempotency_key="enrollment-save",
        ),
        "academic-sandbox",
        "test",
    )
    command = command.model_copy(update={"draft_id": draft.id})
    repo.publish(command, draft, "tenant", "admin", commit=True)

    def view(who):
        return repo.calendar(
            "tenant", "synthetic", draft.period_id, date(2026, 10, 1), date(2026, 10, 31), who
        )["occurrences"]

    events = view({"role": "student", "uid": "student-a"})
    assert events and {e["offering_id"] for e in events} == {inputs.offerings[0].id}
    assert not view({"role": "student", "uid": "student-b"})
    assert not view({"role": "teacher", "faculty_id": "unassigned"})
    assert view({"role": "administrator"})
    # Moved exceptions are checked against all active resource intervals.
    a, b = generated.assignments[:2]
    from classync_contracts.calendar import CalendarException

    calendar = command.calendar.model_copy(deep=True)
    target = next(e for e in view({"role": "administrator"}) if e["assignment_id"] == a.id)
    original = next(e for e in view({"role": "administrator"}) if e["assignment_id"] == b.id)
    calendar.exceptions = [
        CalendarException(
            date=date.fromisoformat(original["date"]),
            assignment_id=b.id,
            cancelled=False,
            moved_to=date.fromisoformat(target["date"]),
            start=a.start,
            room_id=a.room_id,
            reason="Conflict test",
        )
    ]
    with pytest.raises(DraftError, match="conflict"):
        repo.publish(
            command.model_copy(
                update={
                    "calendar": calendar,
                    "expected_version": 1,
                    "idempotency_key": "conflict-move",
                }
            ),
            draft,
            "tenant",
            "admin",
            commit=True,
        )


def test_api_rejects_preview_and_student_publication_and_production_sandbox(monkeypatch, tmp_path):
    from classync_contracts import scheduling_security as security

    from services.scheduling.app import main

    monkeypatch.setattr(main.settings, "scheduling_database_path", str(tmp_path / "s.db"))
    client = TestClient(main.app)
    body = {
        "draft_id": "missing",
        "source": "academic-sandbox",
        "dataset": "synthetic",
        "expected_version": 0,
        "expected_academic_revision": 1,
        "idempotency_key": "unauthorized-key",
        "calendar": configuration().calendar.model_dump(mode="json"),
    }
    assert client.post("/api/v1/timetables/publish", json=body).status_code == 401
    monkeypatch.setattr(security, "initialize_firebase", lambda _: None)
    monkeypatch.setattr(
        security.auth,
        "verify_id_token",
        lambda *a, **k: {"uid": "student", "role": "student", "tenant_id": "tenant"},
    )
    assert (
        client.post(
            "/api/v1/timetables/publish",
            json=body,
            headers={"Authorization": "Bearer verified-test"},
        ).status_code
        == 403
    )
    monkeypatch.setattr(main.settings, "classsync_env", "production")
    assert client.get("/api/v1/timetables/sandbox/periods").status_code == 403
    assert client.post("/api/v1/timetables/sandbox/publish", json=body).status_code == 404


def test_http_publication_current_academic_revision_restrictions_and_occupancy(
    setup, monkeypatch, tmp_path
):
    from classync_contracts import scheduling_security as security

    from services.scheduling.app import main
    from services.scheduling.app import publication_api as api

    repo, draft, command = setup
    academic = AcademicRepository(tmp_path / "http-academic.db")
    academic.migrate()
    snapshot = import_fixture(academic, configuration(), "sandbox", "test")
    monkeypatch.setattr(main.settings, "classsync_env", "development")
    monkeypatch.setattr(main.settings, "enable_scheduling_sandbox", True)
    monkeypatch.setattr(api, "settings_and_repo", lambda: (main.settings, repo))
    monkeypatch.setattr(api, "require_administrator", lambda *args: {"uid": "admin"})
    monkeypatch.setattr(main, "persisted_academic_snapshot", lambda *args: snapshot)
    original_get = repo.drafts.get
    monkeypatch.setattr(
        repo.drafts,
        "get",
        lambda identity, *args: original_get(identity, "academic-sandbox", "test"),
    )
    monkeypatch.setattr(security, "require_sandbox", lambda _: None)
    client = TestClient(main.app)
    body = command.model_dump(mode="json")
    assert client.post("/api/v1/timetables/review", json=body).status_code == 200
    stale = {**body, "expected_academic_revision": 999}
    assert client.post("/api/v1/timetables/publish", json=stale).status_code == 409
    wrong_semester = {**body, "calendar": {**body["calendar"], "semester": "second"}}
    assert client.post("/api/v1/timetables/publish", json=wrong_semester).status_code == 422
    published = client.post("/api/v1/timetables/publish", json=body)
    assert published.status_code == 200, published.text
    assert client.post("/api/v1/timetables/publish", json=body).json() == published.json()
    data = repo.calendar(
        "development-synthetic",
        "synthetic",
        draft.period_id,
        date(2026, 10, 1),
        date(2026, 10, 31),
        {"role": "administrator"},
    )
    event = data["occurrences"][0]
    query = {"room_id": event["room"]["id"], "start": event["starts_at"], "end": event["ends_at"]}
    available = client.get("/api/v1/timetables/sandbox/availability", params=query)
    assert available.status_code == 200, available.text
    assert available.json()["occupancy"] == "occupied"
    assert available.json()["suitability"] == "unknown"
    outside = {**query, "start": "2027-06-01T08:00:00+08:00", "end": "2027-06-01T09:00:00+08:00"}
    assert (
        client.get("/api/v1/timetables/sandbox/availability", params=outside).json()["occupancy"]
        == "unknown"
    )
    restriction = {
        "id": "maintenance-test",
        "dataset": "synthetic",
        "room_id": query["room_id"],
        "starts_at": query["start"],
        "ends_at": query["end"],
        "kind": "operational",
        "reason": "Test restriction",
        "expected_revision": 0,
    }
    url = "/api/v1/timetables/restrictions/maintenance-test"
    response = client.put(url, json=restriction)
    assert response.status_code == 200, response.text
    assert client.put(url, json=restriction).status_code == 409
    assert (
        client.get("/api/v1/timetables/sandbox/availability", params=query).json()["occupancy"]
        == "restricted"
    )
    revised = {**body, "expected_version": 1, "idempotency_key": "restriction-revalidation"}
    assert client.post("/api/v1/timetables/review", json=revised).status_code == 422


def test_publication_rejects_incomplete_scope_and_invalid_exception_date(setup):
    from classync_contracts.calendar import CalendarException

    repo, draft, command = setup
    incomplete = draft.model_copy(deep=True)
    incomplete.input_snapshot.all_intended_offerings_supplied = False
    with pytest.raises(DraftError):
        repo.publish(command, incomplete, "tenant", "admin", commit=True)
    assignment = draft.generation_result.assignments[0]
    wrong = date(2026, 10, 1)
    from datetime import timedelta

    while wrong.weekday() == assignment.day:
        wrong += timedelta(days=1)
    calendar = command.calendar.model_copy(deep=True)
    calendar.exceptions = [
        CalendarException(date=wrong, assignment_id=assignment.id, reason="Invalid original day")
    ]
    with pytest.raises(DraftError, match="scheduled class date"):
        repo.publish(
            command.model_copy(update={"calendar": calendar}), draft, "tenant", "admin", commit=True
        )
    assert not repo.history("tenant", "synthetic", draft.period_id)


def test_second_semester_isolated_with_nonoverlapping_effective_dates(setup):
    from classync_contracts.calendar import AcademicCalendar

    repo, first, command = setup
    repo.publish(command, first, "tenant", "admin", commit=True)
    inputs = first.input_snapshot.model_copy(deep=True)
    inputs.period_id = "second-semester"
    inputs.data_version = "second-semester-v1"
    generated = generate_week(inputs)
    repo.drafts.remember_run(inputs, generated, "academic-sandbox", "test")
    second, _ = repo.drafts.save(
        SaveDraftRequest(
            run_id=generated.run_id,
            input_hash=generated.input_hash,
            title="Second semester",
            idempotency_key="second-semester-save",
        ),
        "academic-sandbox",
        "test",
    )
    calendar = AcademicCalendar(
        academic_year="2026-2027",
        semester="second",
        effective_start=date(2027, 1, 4),
        effective_end=date(2027, 5, 31),
    )
    repo.publish(
        command.model_copy(
            update={
                "draft_id": second.id,
                "calendar": calendar,
                "idempotency_key": "second-semester-publish",
            }
        ),
        second,
        "tenant",
        "admin",
        commit=True,
    )
    viewer = {"role": "administrator"}
    assert (
        repo.calendar(
            "tenant", "synthetic", first.period_id, date(2027, 1, 4), date(2027, 1, 31), viewer
        )["occurrences"]
        == []
    )
    assert repo.calendar(
        "tenant", "synthetic", second.period_id, date(2027, 1, 4), date(2027, 1, 31), viewer
    )["occurrences"]
    assert (
        repo.calendar(
            "tenant", "synthetic", second.period_id, date(2026, 10, 1), date(2026, 10, 31), viewer
        )["occurrences"]
        == []
    )

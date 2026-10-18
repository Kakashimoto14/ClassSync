import json
import subprocess
import sys
from urllib.parse import urlparse

import httpx
import pytest
from classync_contracts.academic import PeriodCreate, RecordWrite
from classync_contracts.scheduling import scheduling_input_hash
from fastapi.testclient import TestClient

from services.academic.app import main as academic
from services.academic.app.repository import AcademicError, AcademicRepository
from services.gateway.app import main as gateway
from services.scheduling.app import main as scheduling
from services.scheduling.app.academic_input import academic_readiness
from services.scheduling.app.engine import generate_week
from services.scheduling.app.validation import validate_timetable
from services.scheduling.tests.test_engine import tiny


@pytest.fixture
def repo(tmp_path):
    repo = AcademicRepository(tmp_path / "academic.sqlite3")
    repo.migrate()
    return repo


def add(repo, period, data, revision=0):
    body = RecordWrite.model_validate({"expected_revision": revision, "record": data})
    return repo.save(
        "sandbox", "development-academic-sandbox", period, body.record.kind, body.record.id, body
    )


def complete(repo):
    snapshot = repo.create_period(
        PeriodCreate(title="Entered test period"), "sandbox", "development-academic-sandbox"
    )
    pid = snapshot.period.id
    windows = [{"day": day, "start": 480, "end": 840} for day in (0, 2, 4)]
    records = [
        {
            "kind": "subjects",
            "id": "subject-a",
            "code": "USER-A",
            "name": "User entered seminar",
            "program_ids": ["bsit"],
            "required_weekly_minutes": 180,
            "patterns": [{"id": "single", "durations": [180]}],
        },
        {
            "kind": "subjects",
            "id": "subject-b",
            "code": "USER-B",
            "name": "User entered practice",
            "program_ids": ["bsit"],
            "required_weekly_minutes": 180,
            "patterns": [{"id": "split", "durations": [90, 90]}],
        },
        {
            "kind": "sections",
            "id": "section-a",
            "period_id": pid,
            "program_id": "bsit",
            "year_level": 3,
            "section_letter": "A",
            "population": 20,
            "population_verified": True,
        },
        {
            "kind": "sections",
            "id": "section-b",
            "period_id": pid,
            "program_id": "bsit",
            "year_level": 3,
            "section_letter": "B",
            "population": 20,
            "population_verified": True,
        },
        {
            "kind": "faculty",
            "id": "teacher-a",
            "name": "User entered faculty A",
            "subject_ids": ["subject-a", "subject-b"],
            "availability": windows,
            "max_weekly_minutes": 540,
            "max_daily_minutes": 180,
        },
        {
            "kind": "faculty",
            "id": "teacher-b",
            "name": "User entered faculty B",
            "subject_ids": ["subject-a", "subject-b"],
            "availability": windows,
            "max_weekly_minutes": 540,
        },
        {
            "kind": "resources",
            "id": "room-a",
            "name": "Entered room A",
            "building": "Entered building",
            "schedulable": True,
            "condition": "operational",
            "capacity": 25,
            "capacity_verified": True,
            "availability": windows,
            "verification_note": "User-entered test assertion, not official CdM metadata",
        },
        {
            "kind": "resources",
            "id": "room-b",
            "name": "Entered room B",
            "building": "Entered building",
            "schedulable": True,
            "condition": "operational",
            "capacity": 25,
            "capacity_verified": True,
            "availability": windows,
            "verification_note": "User-entered test assertion, not official CdM metadata",
        },
    ]
    for record in records:
        snapshot = add(repo, pid, record)
    for i, (subject, section) in enumerate(
        (
            ("subject-a", "section-a"),
            ("subject-b", "section-a"),
            ("subject-a", "section-b"),
            ("subject-b", "section-b"),
        )
    ):
        snapshot = add(
            repo,
            pid,
            {
                "kind": "offerings",
                "id": f"offering-{i}",
                "subject_id": subject,
                "section_id": section,
                "teacher_ids": ["teacher-a", "teacher-b"],
                "room_ids": ["room-a", "room-b"],
            },
        )
    rules = next(r for r in snapshot.records if r.record.kind == "constraints")
    snapshot = add(
        repo,
        pid,
        {
            "kind": "constraints",
            "id": "rules",
            "operating_windows": windows,
            "all_intended_offerings_supplied": True,
        },
        rules.revision,
    )
    return snapshot


def test_catalog_and_empty_readiness_and_restart(repo):
    snapshot = repo.create_period(
        PeriodCreate(title="Period one"), "sandbox", "development-academic-sandbox"
    )
    programs = [e.record for e in snapshot.records if e.record.kind == "programs"]
    rooms = [e.record for e in snapshot.records if e.record.kind == "resources"]
    assert len(programs) == 9 and len(rooms) == 59
    assert all(not r.schedulable and r.capacity is None for r in rooms)
    assert not any(r.id in {"cdm-prrc-304", "cdm-prrc-305", "cdm-prrc-306"} for r in rooms)
    assert next(r for r in rooms if r.id == "cdm-prrc-302").alias_unconfirmed
    checked = academic_readiness(snapshot)
    assert not checked.ready
    assert {i.code for i in checked.issues if i.severity == "blocking"} >= {
        "missing_sections",
        "missing_offerings",
        "missing_operating_hours",
    }
    script = (
        "from services.academic.app.repository import AcademicRepository; import sys; "
        "r=AcademicRepository(sys.argv[1]); r.migrate(); "
        "print(r.snapshot('sandbox','development-academic-sandbox',sys.argv[2]).model_dump_json())"
    )
    value = subprocess.check_output(
        [sys.executable, "-c", script, str(repo.path), snapshot.period.id], text=True
    )
    assert json.loads(value) == snapshot.model_dump(mode="json")


def test_entered_batch_builds_and_generates_exactly(repo):
    snapshot = complete(repo)
    checked = academic_readiness(snapshot)
    assert checked.ready, checked.model_dump()
    inputs = checked.inputs
    assert not inputs.synthetic and len(inputs.offerings) == 4
    assert all(not r.id.startswith("synthetic") for r in inputs.rooms)
    assert all(o.minimum_capacity == 20 for o in inputs.offerings)
    result = generate_week(inputs)
    assert result.solver_status in {"feasible", "optimal"}
    assert (
        result.total_offerings_scheduled == 4
        and sum(c.allocated_minutes for c in result.coverage) == 720
    )
    assert validate_timetable(inputs, result.assignments).valid
    for teacher in inputs.teachers:
        if teacher.max_weekly_minutes is not None:
            assert (
                sum(a.end - a.start for a in result.assignments if a.teacher_id == teacher.id)
                <= teacher.max_weekly_minutes
            )


def test_crud_uniqueness_section_ownership_patterns_and_provenance(repo):
    s = repo.create_period(PeriodCreate(title="A"), "sandbox", "development-academic-sandbox")
    pid = s.period.id
    add(
        repo,
        pid,
        {
            "kind": "programs",
            "id": "new-program",
            "acronym": "USER",
            "name": "Entered program",
            "institute": "Entered institute",
        },
    )
    with pytest.raises(AcademicError):
        add(
            repo,
            pid,
            {
                "kind": "programs",
                "id": "duplicate",
                "acronym": "user",
                "name": "Duplicate",
                "institute": "Entered institute",
            },
        )
    with pytest.raises(AcademicError, match="year"):
        add(
            repo,
            pid,
            {"kind": "sections", "id": "bad-section", "period_id": pid, "program_id": "bsit"},
        )
    with pytest.raises(AcademicError, match="different academic period"):
        add(
            repo,
            pid,
            {
                "kind": "sections",
                "id": "bad-section",
                "period_id": "other",
                "program_id": "bsit",
                "year_level": 3,
                "section_letter": "D",
            },
        )
    for letter in "ABCD":
        add(
            repo,
            pid,
            {
                "kind": "sections",
                "id": f"section-{letter}",
                "period_id": pid,
                "program_id": "bsit",
                "year_level": 3,
                "section_letter": letter,
            },
        )
    add(
        repo,
        pid,
        {
            "kind": "sections",
            "id": "tcp-a",
            "period_id": pid,
            "program_id": "tcp",
            "custom_label": "Entered TCP cohort",
        },
    )
    with pytest.raises(ValueError, match="weekly contact"):
        add(
            repo,
            pid,
            {
                "kind": "subjects",
                "id": "bad",
                "code": "BAD",
                "name": "Bad minutes",
                "required_weekly_minutes": 240,
            },
        )
    with pytest.raises(ValueError, match="distinct"):
        add(
            repo,
            pid,
            {
                "kind": "subjects",
                "id": "bad",
                "code": "BAD",
                "name": "Bad days",
                "patterns": [{"id": "bad", "durations": [90, 90], "distinct_days": False}],
            },
        )
    with pytest.raises(ValueError, match="verification"):
        add(
            repo,
            pid,
            {
                "kind": "resources",
                "id": "new-room",
                "name": "Room",
                "building": "User building",
                "condition": "operational",
                "schedulable": True,
            },
        )
    room = next(e for e in s.records if e.record.kind == "resources")
    with pytest.raises(AcademicError, match="CdM"):
        add(repo, pid, {**room.record.model_dump(), "floor": "99"}, room.revision)


def test_readiness_missing_and_stale_reference_updates(repo):
    snapshot = complete(repo)
    pid = snapshot.period.id
    faculty = next(e for e in snapshot.records if e.record.id == "teacher-a")
    snapshot = add(
        repo,
        pid,
        {**faculty.record.model_dump(), "subject_ids": [], "availability": []},
        faculty.revision,
    )
    checked = academic_readiness(snapshot)
    assert not checked.ready and any(i.code == "faculty_eligibility" for i in checked.issues)
    subject = next(e for e in snapshot.records if e.record.id == "subject-a")
    snapshot = add(
        repo,
        pid,
        {**subject.record.model_dump(), "required_weekly_minutes": None},
        subject.revision,
    )
    assert any(i.code == "missing_weekly_minutes" for i in academic_readiness(snapshot).issues)
    with pytest.raises(AcademicError) as caught:
        add(repo, pid, {**subject.record.model_dump(), "name": "stale"}, subject.revision)
    assert caught.value.status == 409
    with pytest.raises(AcademicError, match="Unknown"):
        add(
            repo,
            pid,
            {"kind": "faculty", "id": "invalid", "name": "Invalid", "subject_ids": ["missing"]},
        )


def test_period_isolation_and_no_delete(repo):
    first = complete(repo)
    second = repo.create_period(
        PeriodCreate(title="Second"), "sandbox", "development-academic-sandbox"
    )
    with pytest.raises(AcademicError, match="Unknown"):
        add(
            repo,
            second.period.id,
            {
                "kind": "offerings",
                "id": "cross-period",
                "subject_id": "subject-a",
                "section_id": "section-a",
            },
        )
    with pytest.raises(AcademicError) as caught:
        repo.snapshot("administrator", "development-academic-sandbox", first.period.id)
    assert caught.value.status == 404
    with repo.connection() as db:
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_workload_is_hard_and_old_hash_remains_compatible():
    inputs = tiny(count=2)
    baseline = inputs.model_dump(mode="json")
    for teacher in baseline["teachers"]:
        teacher.pop("max_weekly_minutes")
        teacher.pop("max_daily_minutes")
    import hashlib

    old_hash = hashlib.sha256(
        json.dumps(baseline, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert scheduling_input_hash(inputs) == old_hash
    valid = generate_week(inputs)
    inputs.teachers[0].max_weekly_minutes = 180
    assert generate_week(inputs).solver_status == "infeasible"
    assert any(
        i.code == "teacher_weekly_workload"
        for i in validate_timetable(inputs, valid.assignments).conflicts
    )
    inputs.teachers[0].max_weekly_minutes = None
    inputs.teachers[0].max_daily_minutes = 90
    assert generate_week(inputs).solver_status == "infeasible"


@pytest.fixture
def api(tmp_path, monkeypatch):
    for config in (academic.settings, scheduling.settings, gateway.settings):
        monkeypatch.setattr(config, "classsync_env", "development")
        monkeypatch.setattr(config, "enable_scheduling_sandbox", True)
    monkeypatch.setattr(
        academic.settings, "academic_database_path", str(tmp_path / "academic.sqlite3")
    )
    monkeypatch.setattr(
        scheduling.settings, "scheduling_database_path", str(tmp_path / "scheduling.sqlite3")
    )
    original_async = httpx.AsyncClient

    async def transport(request):
        target = academic.app if request.url.port == 8001 else scheduling.app
        return await httpx.ASGITransport(app=target).handle_async_request(request)

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: original_async(transport=httpx.MockTransport(transport), **kw),
    )

    class AcademicClient:
        def __init__(self, **_):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def get(self, url, headers):
            return TestClient(academic.app).get(urlparse(url).path, headers=headers)

    monkeypatch.setattr(httpx, "Client", AcademicClient)
    return TestClient(gateway.app)


def test_real_gateway_entered_generation_save_and_isolation(api):
    # Persist input fixtures, then exercise the real HTTP boundary and solver.
    repo = academic.repository()
    snap = complete(repo)
    pid = snap.period.id
    readiness = api.get(f"/api/v1/scheduling/sandbox/academic/{pid}/readiness")
    assert readiness.status_code == 200, readiness.text
    assert readiness.json()["data"]["ready"]
    stale = api.post(
        f"/api/v1/scheduling/sandbox/academic/{pid}/generate", json={"expected_revision": 1}
    )
    assert stale.status_code == 409
    generated = api.post(
        f"/api/v1/scheduling/sandbox/academic/{pid}/generate",
        json={"expected_revision": snap.period.revision},
    )
    assert generated.status_code == 200, generated.text
    result = generated.json()["data"]
    assert result["validation"]["valid"]
    body = {
        "run_id": result["run_id"],
        "input_hash": result["input_hash"],
        "title": "Entered draft",
        "idempotency_key": "entered-test-key",
    }
    wrong = api.post("/api/v1/scheduling/sandbox/drafts", json=body)
    assert wrong.status_code == 404
    saved = api.post("/api/v1/scheduling/sandbox/academic/drafts", json=body)
    assert saved.status_code == 201, saved.text
    draft = saved.json()["data"]
    assert draft["source"] == "development-entered"
    loaded = api.get("/api/v1/scheduling/sandbox/academic/drafts/" + draft["id"])
    assert loaded.status_code == 200, loaded.text
    assert loaded.json()["data"]["generation_result"]["assignments"] == result["assignments"]
    assert api.get("/api/v1/scheduling/sandbox/drafts/" + draft["id"]).status_code == 404
    # Editing current source does not change the saved immutable snapshot.
    subject = next(e for e in snap.records if e.record.kind == "subjects")
    api.put(
        f"/api/v1/academic/sandbox/periods/{pid}/records/subjects/{subject.record.id}",
        json={
            "expected_revision": subject.revision,
            "record": {**subject.record.model_dump(), "name": "Updated subject"},
        },
    )
    assert (
        api.get("/api/v1/scheduling/sandbox/academic/drafts/" + draft["id"]).json()["data"]
        == loaded.json()["data"]
    )


def test_api_authorization_and_catalog_write(api, monkeypatch):
    assert api.post("/api/v1/academic/periods", json={"title": "Unauthorized"}).status_code == 401
    created = api.post("/api/v1/academic/sandbox/periods", json={"title": "Actual entered period"})
    assert created.status_code == 201, created.text
    pid = created.json()["data"]["period"]["id"]
    assert api.get("/api/v1/academic/sandbox/periods").json()["data"]["periods"][0]["id"] == pid
    record = {
        "kind": "subjects",
        "id": "entered",
        "code": "ENTERED",
        "name": "User entry",
        "program_ids": ["bsit"],
    }
    saved = api.put(
        f"/api/v1/academic/sandbox/periods/{pid}/records/subjects/entered",
        json={"expected_revision": 0, "record": record},
    )
    assert saved.status_code == 200, saved.text
    assert api.delete(f"/api/v1/academic/sandbox/periods/{pid}").status_code == 405
    for config in (gateway.settings, academic.settings, scheduling.settings):
        monkeypatch.setattr(config, "classsync_env", "production")
    assert api.get("/api/v1/academic/sandbox/periods").status_code == 403
    assert api.get(f"/api/v1/scheduling/sandbox/academic/{pid}/readiness").status_code == 403


def test_protected_records_and_generation_require_verified_owner(api, monkeypatch):
    from classync_contracts import scheduling_security

    monkeypatch.setattr(scheduling_security, "initialize_firebase", lambda *_: None)
    identity = {"uid": "admin-a", "role": "administrator"}
    monkeypatch.setattr(scheduling_security.auth, "verify_id_token", lambda *_, **__: identity)
    headers = {"Authorization": "Bearer verified-test"}
    source = complete(academic.repository())
    saved = api.post(
        "/api/v1/academic/periods", headers=headers, json={"title": "Authorized entered period"}
    ).json()["data"]
    pid = saved["period"]["id"]
    # Persist related records in dependency order; no synthetic scenario is used.
    for kind in ("subjects", "sections", "faculty", "resources", "offerings", "constraints"):
        for envelope in source.records:
            record = envelope.record.model_dump(mode="json")
            if record["kind"] != kind or (kind == "resources" and record["id"].startswith("cdm-")):
                continue
            if kind == "sections":
                record["period_id"] = pid
            response = api.put(
                f"/api/v1/academic/periods/{pid}/records/{kind}/{record['id']}",
                headers=headers,
                json={"expected_revision": 1 if kind == "constraints" else 0, "record": record},
            )
            assert response.status_code == 200, response.text
            saved = response.json()["data"]
    ready = api.get(f"/api/v1/scheduling/academic/{pid}/readiness", headers=headers)
    assert ready.json()["data"]["ready"], ready.text
    run = api.post(
        f"/api/v1/scheduling/academic/{pid}/generate",
        headers=headers,
        json={"expected_revision": saved["period"]["revision"]},
    ).json()["data"]
    assert run["validation"]["valid"]
    draft = api.post(
        "/api/v1/scheduling/drafts",
        headers=headers,
        json={
            "run_id": run["run_id"],
            "input_hash": run["input_hash"],
            "title": "Protected draft",
            "idempotency_key": "protected-entered-key",
        },
    )
    assert draft.status_code == 201, draft.text
    assert draft.json()["data"]["source"] == "institutional"
    assert api.get(f"/api/v1/academic/sandbox/periods/{pid}").status_code == 404
    identity["uid"] = "admin-b"
    assert api.get(f"/api/v1/academic/periods/{pid}", headers=headers).status_code == 404
    identity["role"] = "teacher"
    assert (
        api.post("/api/v1/academic/periods", headers=headers, json={"title": "Denied"}).status_code
        == 403
    )


def test_required_equipment_cannot_be_inferred_from_resource_name(repo):
    snapshot = complete(repo)
    pid = snapshot.period.id
    subject = next(e for e in snapshot.records if e.record.id == "subject-a")
    snapshot = add(
        repo,
        pid,
        {**subject.record.model_dump(), "required_equipment": ["projector"]},
        subject.revision,
    )
    checked = academic_readiness(snapshot)
    assert not checked.ready and any(i.code == "no_eligible_room" for i in checked.issues)
    room = next(e for e in snapshot.records if e.record.id == "room-a")
    snapshot = add(
        repo,
        pid,
        {**room.record.model_dump(), "equipment": ["projector"], "equipment_verified": True},
        room.revision,
    )
    assert academic_readiness(snapshot).ready


def test_atomic_references_concurrent_edits_and_corrupt_record(repo):
    from concurrent.futures import ThreadPoolExecutor

    snapshot = complete(repo)
    pid = snapshot.period.id
    subject = next(e for e in snapshot.records if e.record.id == "subject-a")

    def edit(name):
        try:
            add(repo, pid, {**subject.record.model_dump(), "name": name}, subject.revision)
            return 200
        except AcademicError as error:
            return error.status

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(edit, ["First edit", "Other edit"])) == [200, 409]
    with pytest.raises(AcademicError):
        with repo.connection(True) as db:
            db.execute("DELETE FROM academic_records WHERE kind='subjects' AND id='subject-a'")
    assert repo.snapshot("sandbox", "development-academic-sandbox", pid)
    with repo.connection(True) as db:
        db.execute(
            "UPDATE academic_records SET checksum='corrupt' "
            "WHERE kind='subjects' AND id='subject-a'"
        )
    with pytest.raises(AcademicError) as caught:
        repo.snapshot("sandbox", "development-academic-sandbox", pid)
    assert caught.value.status == 409


def test_faculty_identity_is_unique_when_supplied_but_names_need_not_be(repo):
    s = repo.create_period(
        PeriodCreate(title="Identity period"), "sandbox", "development-academic-sandbox"
    )
    add(
        repo,
        s.period.id,
        {"kind": "faculty", "id": "one", "name": "Same name", "institutional_id": "USER-001"},
    )
    add(
        repo,
        s.period.id,
        {"kind": "faculty", "id": "two", "name": "Same name", "institutional_id": "USER-002"},
    )
    with pytest.raises(AcademicError) as caught:
        add(
            repo,
            s.period.id,
            {
                "kind": "faculty",
                "id": "duplicate",
                "name": "Other name",
                "institutional_id": "user-001",
            },
        )
    assert caught.value.status == 409


def test_readiness_reports_insufficient_eligible_workload(repo):
    snapshot = complete(repo)
    for teacher in [e for e in snapshot.records if e.record.kind == "faculty"]:
        snapshot = add(
            repo,
            snapshot.period.id,
            {**teacher.record.model_dump(), "max_weekly_minutes": 60},
            teacher.revision,
        )
    checked = academic_readiness(snapshot)
    assert not checked.ready
    assert any(i.code == "insufficient_faculty_workload" for i in checked.issues)


def test_academic_v1_migration_preserves_records_and_rejects_future_schema(repo):
    snapshot = complete(repo)
    with repo.connection(True) as db:
        before = [
            tuple(row)
            for row in db.execute(
                "SELECT id, payload, checksum FROM academic_records ORDER BY kind, id"
            )
        ]
        db.execute("DROP INDEX faculty_institutional_identity")
        db.execute("DROP TABLE academic_calendars")
        db.execute("PRAGMA user_version=1")
    repo.migrate()
    repo.migrate()
    with repo.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 3
        assert before == [
            tuple(row)
            for row in db.execute(
                "SELECT id, payload, checksum FROM academic_records ORDER BY kind, id"
            )
        ]
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
    assert repo.snapshot("sandbox", "development-academic-sandbox", snapshot.period.id) == snapshot
    with repo.connection(True) as db:
        db.execute("PRAGMA user_version=99")
    with pytest.raises(AcademicError) as caught:
        repo.migrate()
    assert caught.value.code == "academic_schema"
    with repo.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 99
        assert db.execute("SELECT count(*) FROM academic_records").fetchone()[0] == len(before)

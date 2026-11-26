"""Teacher classroom-request workflow on a throwaway PostgreSQL cluster, as the runtime role.

Faked repositories cannot see privileges, row-level security, constraints or triggers. This
seeds the defense dataset, generates and publishes a real timetable, then drives the request
routes end to end. Only HTTP identity verification is replaced; every statement is real.
"""

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from classync_contracts.identity import VerifiedPrincipal
from classync_contracts.publication import PublicationCommand, RoomRestriction
from classync_contracts.scheduling import SaveDraftRequest
from classync_persistence.database import transaction
from classync_persistence.membership_changes import audit_actor
from classync_persistence.memberships import identity_context
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from scripts.seed_campus_data import PERIOD_ID, apply_seed, stable_uuid
from services.academic.app.postgres_repository import PostgresAcademicRepository
from services.scheduling.app import classroom_requests, main
from services.scheduling.app.academic_input import academic_readiness
from services.scheduling.app.catalog import excluded_space_ids, schedulable_space_ids
from services.scheduling.app.engine import generate_week
from services.scheduling.app.occurrences import ZONE
from services.scheduling.app.postgres_draft_repository import PostgresDraftRepository
from services.scheduling.app.postgres_publication_repository import PostgresPublicationRepository
from services.scheduling.app.readiness import eligible_room
from services.testing.postgres_cluster import cluster, execute, provision  # noqa: F401

TENANT, PROJECT, ADMIN, TEACHER = "cdm", "demo-classsync-requests", "admin-uid", "teacher-uid"
BASE = "/api/v1/timetables/requests"
# The seeded semester is fixed, so "today" is pinned to keep class dates in the future.
TODAY = datetime(2026, 9, 1, 8, 0, tzinfo=ZONE)


class PinnedClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return TODAY.astimezone(tz)


def _overlapping_pair(inputs, assignments):
    """A class, and another teacher's room that is busy then but otherwise eligible for it."""
    offerings = {item.id: item for item in inputs.offerings}
    sections = {item.id: item for item in inputs.sections}
    rooms = {item.id: item for item in inputs.rooms}

    def eligible(assignment, room_id):
        offering = offerings[assignment.offering_id]
        return room_id in offering.eligible_room_ids and eligible_room(
            rooms[room_id], offering, sections[offering.section_id].program_id
        )

    def busy(assignment):
        return {
            other.room_id for other in assignments
            if other.day == assignment.day
            and other.start < assignment.end and assignment.start < other.end
        }

    for mine in sorted(assignments, key=lambda item: item.id):
        taken = busy(mine)
        occupied = sorted(r for r in taken - {mine.room_id} if eligible(mine, r))
        free = sorted(r for r in set(rooms) - taken if eligible(mine, r))
        if occupied and free:
            return mine, occupied[0], free[0]
    raise AssertionError("The seeded timetable offers no class with both a busy and a free room")


@pytest.fixture(scope="module")
def world(cluster):  # noqa: F811
    provisioned = provision(cluster)
    engine = provisioned.engine
    with transaction(engine("boot")) as db:
        # Everything the scheduling runtime needs beyond reads; identity stays read-only.
        for table in ("solver_runs", "drafts", "published_versions"):
            execute(db, f"GRANT INSERT ON classsync_scheduling.{table} TO runtime")
        for table in ("publication_heads", "room_restrictions", "classroom_requests"):
            execute(db, f"GRANT INSERT,UPDATE ON classsync_scheduling.{table} TO runtime")
        execute(db, "GRANT EXECUTE ON FUNCTION "
                    "classsync_scheduling.lock_publication_authority() TO runtime")
        execute(db, "INSERT INTO classsync_identity.tenants VALUES (:t,:p)", t=TENANT, p=PROJECT)
        identity_context(db, tenant_id=TENANT, uid=ADMIN)
        audit_actor(db, VerifiedPrincipal(uid="synthetic-provisioner"))
        execute(db, "INSERT INTO classsync_identity.people(tenant_id,id) VALUES (:t,'p-admin')",
                t=TENANT)
        execute(db, "INSERT INTO classsync_identity.memberships "
                    "(tenant_id,uid,person_id,roles,state,revision) VALUES "
                    "(:t,:u,'p-admin',ARRAY['administrator'],'active',1)", t=TENANT, u=ADMIN)

    def repository(user, kind, uid=ADMIN):
        return kind(engine(user), tenant_id=TENANT, firebase_project_id=PROJECT,
                    principal=VerifiedPrincipal(uid=uid))

    apply_seed(repository("operator", PostgresAcademicRepository))
    snapshot = repository("runtime", PostgresAcademicRepository).snapshot(PERIOD_ID)
    inputs = academic_readiness(snapshot).inputs
    result = generate_week(inputs)
    assert result.solver_status in {"feasible", "optimal"}
    drafts = repository("runtime", PostgresDraftRepository)
    drafts.remember_run(inputs, result)
    draft, _ = drafts.save(SaveDraftRequest(
        run_id=result.run_id, input_hash=result.input_hash, title="Request approval runtime",
        idempotency_key="request-runtime-draft",
    ))
    repository("runtime", PostgresPublicationRepository).publish(PublicationCommand(
        draft_id=draft.id, dataset="institutional", expected_version=0,
        expected_academic_revision=snapshot.period.revision,
        idempotency_key="request-runtime-publish", calendar=snapshot.period.calendar,
    ), commit=True)

    mine, occupied_room, free_room = _overlapping_pair(inputs, result.assignments)
    with transaction(engine("boot")) as db:
        identity_context(db, tenant_id=TENANT, uid=TEACHER)
        audit_actor(db, VerifiedPrincipal(uid="synthetic-provisioner"))
        execute(db, "INSERT INTO classsync_identity.memberships "
                    "(tenant_id,uid,person_id,faculty_id,roles,state,revision) VALUES "
                    "(:t,:u,:p,:f,ARRAY['teacher'],'active',1)",
                t=TENANT, u=TEACHER, p=stable_uuid("faculty-person", mine.teacher_id),
                f=mine.teacher_id)
    try:
        yield SimpleNamespace(
            engine=engine, repository=repository, mine=mine,
            occupied_room=occupied_room, free_room=free_room,
        )
    finally:
        for item in provisioned.engines.values():
            item.dispose()


@pytest.fixture
def api(world, monkeypatch):
    """The real routes over the runtime role; only token verification is replaced."""
    claims = {
        "teacher": {"role": "teacher", "uid": TEACHER, "faculty_id": world.mine.teacher_id},
        "administrator": {"role": "administrator", "uid": ADMIN},
    }
    acting = {"role": "teacher"}

    def repository(_request, *, teacher=False, admin=False):
        role = "teacher" if teacher else "administrator" if admin else acting["role"]
        publication = world.repository(
            "runtime", PostgresPublicationRepository, uid=claims[role]["uid"]
        )
        return classroom_requests.Requests(publication), claims[role]

    monkeypatch.setattr(classroom_requests, "repository", repository)
    monkeypatch.setattr(classroom_requests, "datetime", PinnedClock)
    client = TestClient(main.app)

    def class_date(week):
        monday = date(2026, 9, 7) + timedelta(weeks=week)
        return monday + timedelta(days=world.mine.day)

    def occurrence(week):
        return f"{world.mine.id}:{class_date(week)}"

    def options(week):
        response = client.get(f"{BASE}/options", params={
            "period_id": PERIOD_ID, "class_date": str(class_date(week)),
            "occurrence_id": occurrence(week),
        })
        assert response.status_code == 200, response.text
        return response.json()

    def submit(week, room_id, publication_id=None):
        return client.post(BASE, json={
            "period_id": PERIOD_ID,
            "publication_id": publication_id or options(week)["publication_id"],
            "occurrence_id": occurrence(week), "class_date": str(class_date(week)),
            "proposed_room_id": room_id, "reason": "Projector in the current room failed",
            "idempotency_key": str(uuid4()),
        })

    def pending(week):
        response = submit(week, world.free_room)
        assert response.status_code == 201, response.text
        return response.json()

    def preflight(request):
        response = client.get(f"{BASE}/{request['id']}/preflight")
        assert response.status_code == 200, response.text
        return response.json()

    def decide(request, decision, note="Reviewed by the registrar desk"):
        return client.post(f"{BASE}/{request['id']}/decision", json={
            "expected_revision": request["revision"], "decision": decision, "note": note,
        })

    def read(request, role="teacher"):
        acting["role"] = role
        response = client.get(f"{BASE}/{request['id']}")
        assert response.status_code == 200, response.text
        return response.json()

    def room_at(week):
        """The room the published timetable currently gives this class."""
        day = class_date(week)
        calendar = world.repository("runtime", PostgresPublicationRepository).admin_calendar(
            "institutional", PERIOD_ID, day, day
        )
        return next(
            item["room"]["id"] for item in calendar["occurrences"]
            if item["id"] == occurrence(week)
        )

    return SimpleNamespace(
        class_date=class_date, options=options, submit=submit, pending=pending,
        preflight=preflight, decide=decide, read=read, room_at=room_at,
    )


def _state(world):
    """Every row the workflow can write, read past row security so nothing can hide."""
    tables = ("classroom_requests", "published_versions", "publication_heads",
              "administrator_activity")
    with transaction(world.engine("boot")) as db:
        return {
            table: db.scalar(text(
                "SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),'[]') "
                f"FROM classsync_scheduling.{table} t"
            ))
            for table in tables
        }


def test_runtime_role_cannot_write_identity_or_activity(world):
    with transaction(world.engine("runtime")) as db:
        assert db.execute(text(
            "SELECT rolsuper, rolbypassrls, "
            "has_table_privilege(current_user,'classsync_identity.memberships','UPDATE'), "
            "has_table_privilege(current_user,"
            "'classsync_scheduling.administrator_activity','INSERT') "
            "FROM pg_roles WHERE rolname=current_user"
        )).one() == (False, False, False, False)


def test_teacher_room_options_and_slot_occupancy(world, api):
    options = api.options(0)
    occupancy = {room["id"]: room["occupancy"] for room in options["rooms"]}
    assert occupancy[world.occupied_room] == "occupied"
    assert occupancy[world.free_room] == "available"
    assert world.mine.room_id not in occupancy
    assert set(occupancy) <= schedulable_space_ids()

    teacher = world.repository("runtime", PostgresPublicationRepository, uid=TEACHER)
    slot = teacher.room_slot(
        PERIOD_ID, api.class_date(0), world.mine.start, world.mine.end,
        {"role": "teacher", "faculty_id": world.mine.teacher_id},
    )
    states = {room["id"]: room["occupancy"] for room in slot["rooms"]}
    assert len(slot["rooms"]) == len(states) == 41
    assert set(states) == schedulable_space_ids()
    assert len(excluded_space_ids()) == 12 and not set(states) & excluded_space_ids()
    assert states[world.mine.room_id] == states[world.occupied_room] == "occupied"
    assert states[world.free_room] == "free"
    assert slot["restrictions_checked"] is False


def test_teacher_request_creation_succeeds_or_is_refused(world, api):
    before = _state(world)
    publication_id = api.options(1)["publication_id"]
    occupied = api.submit(1, world.occupied_room, publication_id)
    assert occupied.status_code == 409, occupied.text
    assert "occupied" in occupied.json()["detail"]
    for room_id in sorted(excluded_space_ids()):
        refused = api.submit(1, room_id, publication_id)
        assert refused.status_code == 422, refused.text
        assert "excluded" in refused.json()["detail"]
    assert _state(world) == before

    request = api.pending(1)
    assert (request["status"], request["revision"]) == ("pending", 1)
    assert request["proposed_room_id"] == world.free_room
    assert api.read(request)["status"] == "pending"
    assert len(_state(world)["classroom_requests"]) == len(before["classroom_requests"]) + 1


def test_conflict_after_submission_blocks_approval_without_writes(world, api):
    request = api.pending(2)
    assert api.preflight(request)["state"] == "clear"
    day = api.class_date(2)
    starts = datetime.combine(day, datetime.min.time(), ZONE) + timedelta(minutes=world.mine.start)
    world.repository("runtime", PostgresPublicationRepository).put_restriction(RoomRestriction(
        id="late-reservation", room_id=world.free_room, dataset="institutional",
        starts_at=starts.isoformat(), ends_at=(starts + timedelta(minutes=30)).isoformat(),
        kind="reservation", reason="Reserved after the request", expected_revision=0,
    ))
    before = _state(world)
    checked = api.preflight(request)
    assert (checked["state"], checked["code"]) == ("conflict", "room_restricted")
    refused = api.decide(request, "approved")
    assert refused.status_code == 409, refused.text
    assert refused.json()["error"]["code"] == "room_restricted"
    assert _state(world) == before


def test_failure_after_publication_insert_rolls_the_whole_approval_back(world, api):
    request = api.pending(3)
    with transaction(world.engine("boot")) as db:
        # Fault injection: the last statement of an approval fails after the new version, head,
        # audit row and 'approved' transition have already been written in the transaction.
        execute(db, """
            CREATE FUNCTION public.fail_fulfilment() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF NEW.status='fulfilled' THEN
                    RAISE EXCEPTION 'injected failure' USING ERRCODE='23514';
                END IF;
                RETURN NEW;
            END; $$
        """)
        execute(db, "CREATE TRIGGER zz_fail_fulfilment BEFORE UPDATE ON "
                    "classsync_scheduling.classroom_requests FOR EACH ROW "
                    "EXECUTE FUNCTION public.fail_fulfilment()")
    try:
        before = _state(world)
        failed = api.decide(request, "approved")
        assert failed.status_code == 409, failed.text
        assert failed.json()["error"]["code"] == "publication_integrity"
        assert _state(world) == before
    finally:
        with transaction(world.engine("boot")) as db:
            execute(db, "DROP TRIGGER zz_fail_fulfilment ON "
                        "classsync_scheduling.classroom_requests")
            execute(db, "DROP FUNCTION public.fail_fulfilment()")


def test_approval_publishes_and_fulfils_in_one_transaction(world, api):
    request = api.pending(4)
    before = _state(world)
    assert api.preflight(request)["state"] == "clear"
    assert _state(world) == before, "Preflight must not write"

    approved = api.decide(request, "approved")
    assert approved.status_code == 200, approved.text
    result = approved.json()
    assert (result["status"], result["revision"]) == ("fulfilled", 3)

    after = _state(world)
    assert len(after["published_versions"]) == len(before["published_versions"]) + 1
    assert len(after["administrator_activity"]) == len(before["administrator_activity"]) + 1
    version = next(
        row for row in after["published_versions"] if row["id"] == result["fulfilled_version"]
    )
    assert after["publication_heads"][0]["revision"] == version["revision"]
    assert api.room_at(4) == world.free_room
    assert api.room_at(5) == world.mine.room_id

    with transaction(world.engine("boot")) as db:
        transactions = {
            execute(db, "SELECT xmin::text FROM classsync_scheduling.classroom_requests "
                        "WHERE id=:i", i=request["id"]).scalar_one(),
            execute(db, "SELECT xmin::text FROM classsync_scheduling.published_versions "
                        "WHERE id=:i", i=version["id"]).scalar_one(),
            execute(db, "SELECT xmin::text FROM classsync_scheduling.publication_heads")
            .scalar_one(),
            execute(db, "SELECT xmin::text FROM classsync_scheduling.administrator_activity "
                        "WHERE event_type='scheduling.publication.published' AND revision=:r",
                    r=version["revision"]).scalar_one(),
        }
    assert len(transactions) == 1, "Version, head, audit and request must commit together"

    # A retried approval whose response was lost returns the same result and writes nothing.
    retried = api.decide(request, "approved")
    assert retried.status_code == 200, retried.text
    assert retried.json()["fulfilled_version"] == result["fulfilled_version"]
    assert _state(world) == after

    # The transition guard rejects reopening, even for the table's privileged writer.
    with pytest.raises(DBAPIError) as guarded, transaction(world.engine("boot")) as db:
        execute(db, "UPDATE classsync_scheduling.classroom_requests "
                    "SET status='pending', revision=revision+1 WHERE id=:i", i=request["id"])
    assert guarded.value.orig.sqlstate == "23514"


def test_rejection_stores_the_note_without_touching_the_timetable(world, api):
    request = api.pending(6)
    before = _state(world)
    note = "The room is needed for an examination"
    rejected = api.decide(request, "rejected", note)
    assert rejected.status_code == 200, rejected.text
    stored = api.read(request)
    assert (stored["status"], stored["decision_note"], stored["decided_by"]) == (
        "rejected", note, ADMIN,
    )
    assert stored["fulfilled_version"] is None
    assert api.read(request, "administrator")["draft_id"]
    after = _state(world)
    for table in ("published_versions", "publication_heads", "administrator_activity"):
        assert after[table] == before[table]
    assert api.room_at(6) == world.mine.room_id

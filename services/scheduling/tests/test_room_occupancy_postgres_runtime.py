"""Tenant-wide room occupancy (migration 0028) on a throwaway PostgreSQL cluster.

Row-level security shows Teachers and Students only the published versions that contain their
own record. A second publication sharing the campus (another period, here) must still make its
rooms show as occupied or restricted to them, without revealing any of its class details.
"""

import json
from datetime import date, timedelta
from hashlib import sha256
from types import SimpleNamespace

import pytest
from classync_contracts.identity import VerifiedPrincipal
from classync_contracts.publication import PublicationCommand
from classync_contracts.scheduling import SaveDraftRequest
from classync_persistence.database import transaction
from classync_persistence.membership_changes import audit_actor
from classync_persistence.memberships import identity_context
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from scripts.seed_campus_data import PERIOD_ID, apply_seed, stable_uuid
from services.academic.app.postgres_repository import PostgresAcademicRepository
from services.scheduling.app.academic_input import academic_readiness
from services.scheduling.app.catalog import schedulable_space_ids
from services.scheduling.app.engine import generate_week
from services.scheduling.app.postgres_draft_repository import PostgresDraftRepository
from services.scheduling.app.postgres_publication_repository import PostgresPublicationRepository
from services.scheduling.tests.test_request_approval_postgres_runtime import _overlapping_pair
from services.testing.postgres_cluster import cluster, execute, provision  # noqa: F401

TENANT, PROJECT, ADMIN = "cdm", "demo-classsync-occupancy", "admin-uid"
TEACHER, STUDENT = "teacher-uid", "student-uid"
OTHER_PERIOD = "00000000-0000-5000-8000-0000000000b2"
SECRET = "IBE board review — confidential"
OUTSIDER_TEACHER = "outsider-faculty"
FIRST_WEEK = date(2026, 9, 7)  # a Monday inside the seeded calendar


def _member(db, uid, person, role, **record):
    identity_context(db, tenant_id=TENANT, uid=uid)
    audit_actor(db, VerifiedPrincipal(uid="synthetic-provisioner"))
    column, value = next(iter(record.items()))
    execute(db, "INSERT INTO classsync_identity.memberships "
                f"(tenant_id,uid,person_id,{column},roles,state,revision) VALUES "
                "(:t,:u,:p,:v,ARRAY[:r],'active',1)",
            t=TENANT, u=uid, p=person, v=value, r=role)


@pytest.fixture(scope="module")
def world(cluster):  # noqa: F811
    provisioned = provision(cluster)
    engine = provisioned.engine
    with transaction(engine("boot")) as db:
        for table in ("solver_runs", "drafts", "published_versions"):
            execute(db, f"GRANT INSERT ON classsync_scheduling.{table} TO runtime")
        execute(db, "GRANT INSERT,UPDATE ON classsync_scheduling.publication_heads TO runtime")
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
        run_id=result.run_id, input_hash=result.input_hash, title="Occupancy runtime",
        idempotency_key="occupancy-runtime-draft",
    ))
    repository("runtime", PostgresPublicationRepository).publish(PublicationCommand(
        draft_id=draft.id, dataset="institutional", expected_version=0,
        expected_academic_revision=snapshot.period.revision,
        idempotency_key="occupancy-runtime-publish", calendar=snapshot.period.calendar,
    ), commit=True)
    mine, _, free_room = _overlapping_pair(inputs, result.assignments)
    # Restriction status takes precedence, so any other catalog room demonstrates it.
    restricted_room = min(schedulable_space_ids() - {free_room, mine.room_id})
    enrolled = next(e.student_id for e in inputs.enrollments if mine.offering_id in e.offering_ids)
    other = next(a for a in result.assignments if a.teacher_id != mine.teacher_id)
    class_date = (FIRST_WEEK + timedelta(days=mine.day)).isoformat()

    with transaction(engine("boot")) as db:
        _member(db, TEACHER, stable_uuid("faculty-person", mine.teacher_id), "teacher",
                faculty_id=mine.teacher_id)
        person = db.scalar(text("SELECT person_id FROM classsync_identity.students "
                                "WHERE tenant_id=:t AND id=:s"), {"t": TENANT, "s": enrolled})
        _member(db, STUDENT, person, "student", student_id=enrolled)
        # A second publication sharing the campus: another period whose only class takes
        # `free_room` at this Teacher's class time, taught by someone else. RLS hides it from
        # the Teacher and Student (they are not in it); occupancy must not.
        identity_context(db, tenant_id=TENANT, uid=ADMIN)
        audit_actor(db, VerifiedPrincipal(uid="synthetic-provisioner"))
        # The period audit trigger records the Administrator's verified project context.
        execute(db, "SELECT set_config('classsync.project_id', :p, true)", p=PROJECT)
        execute(db, "INSERT INTO classsync_academic.period_metadata "
                    "(tenant_id,owner_uid,id,title) VALUES (:t,:o,:p,'IBE shared-campus period')",
                t=TENANT, o=ADMIN, p=OTHER_PERIOD)
        row = db.execute(text("SELECT * FROM classsync_scheduling.published_versions "
                              "WHERE period_id=:p"), {"p": PERIOD_ID}).mappings().one()
        payload = json.loads(row["payload"])
        payload["draft"]["period_id"] = OTHER_PERIOD
        booked = {**json.loads(other.model_dump_json()), "id": "ibe-shared-class",
                  "day": mine.day, "start": mine.start, "end": mine.end,
                  "room_id": free_room, "teacher_id": OUTSIDER_TEACHER}
        payload["draft"]["generation_result"]["assignments"] = [booked]
        text_payload = json.dumps(payload)
        command = json.loads(row["command"])
        command["idempotency_key"] = "occupancy-other-period"
        execute(db, """
            INSERT INTO classsync_scheduling.published_versions
            (tenant_id,dataset,period_id,owner_uid,actor_uid,draft_id,id,revision,
             academic_revision,created_at,idempotency_key,command,request_hash,payload,checksum)
            VALUES (:t,'institutional',:p,:o,:o,:d,'ibe-version',1,:ar,now(),
                    'occupancy-other-period',:c,:ch,:pl,:pk)
        """, t=TENANT, p=OTHER_PERIOD, o=ADMIN, d=row["draft_id"], ar=row["academic_revision"],
                c=json.dumps(command), ch=sha256(json.dumps(command).encode()).hexdigest(),
                pl=text_payload, pk=sha256(text_payload.encode()).hexdigest())
        execute(db, "INSERT INTO classsync_scheduling.publication_heads "
                    "(tenant_id,dataset,period_id,owner_uid,revision) "
                    "VALUES (:t,'institutional',:p,:o,1)", t=TENANT, p=OTHER_PERIOD, o=ADMIN)
        restriction = {
            "id": "board-review", "room_id": restricted_room, "dataset": "institutional",
            "starts_at": f"{class_date}T00:00:00+08:00", "ends_at": f"{class_date}T23:30:00+08:00",
            "kind": "reservation", "reason": SECRET, "revision": 1,
        }
        restriction_text = json.dumps(restriction)
        execute(db, """
            INSERT INTO classsync_scheduling.room_restrictions
            (tenant_id,dataset,id,owner_uid,room_id,revision,starts_at,ends_at,payload,checksum)
            VALUES (:t,'institutional','board-review',:o,:r,1,:s,:e,:pl,:pk)
        """, t=TENANT, o=ADMIN, r=restricted_room, s=restriction["starts_at"],
                e=restriction["ends_at"], pl=restriction_text,
                pk=sha256(restriction_text.encode()).hexdigest())
    try:
        yield SimpleNamespace(
            engine=engine, repository=repository, mine=mine, free_room=free_room,
            restricted_room=restricted_room, enrolled=enrolled, other=other,
            class_date=date.fromisoformat(class_date),
        )
    finally:
        for item in provisioned.engines.values():
            item.dispose()


def _slot(world, uid, viewer):
    repo = world.repository("runtime", PostgresPublicationRepository, uid=uid)
    return repo.room_slot(PERIOD_ID, world.class_date, world.mine.start, world.mine.end, viewer)


@pytest.mark.parametrize("who", ["teacher", "student"])
def test_rooms_booked_by_another_publication_are_occupied_for_members(world, who):
    uid, viewer = (
        (TEACHER, {"role": "teacher", "faculty_id": world.mine.teacher_id})
        if who == "teacher"
        else (STUDENT, {"role": "student", "student_id": world.enrolled})
    )
    slot = _slot(world, uid, viewer)
    states = {room["id"]: room["occupancy"] for room in slot["rooms"]}
    assert len(states) == 41
    assert states[world.free_room] == "occupied"  # booked only by the hidden publication
    assert states[world.restricted_room] == "restricted"
    assert slot["restrictions_checked"] is True
    # Room metadata and a state only: nothing from the other publication or the restriction.
    assert {key for room in slot["rooms"] for key in room} == {
        "id", "name", "building", "floor", "occupancy",
    }
    body = json.dumps(slot)
    for private in (SECRET, OUTSIDER_TEACHER, "ibe-shared-class", "ibe-version", OTHER_PERIOD,
                    world.other.section_id, world.other.subject_id):
        assert private not in body


def test_runtime_role_still_cannot_read_the_hidden_publication(world):
    repo = world.repository("runtime", PostgresPublicationRepository, uid=TEACHER)
    with repo.session(role="teacher", record_id=world.mine.teacher_id) as db:
        periods = set(db.scalars(text(
            "SELECT period_id FROM classsync_scheduling.published_versions"
        )).all())
        assert OTHER_PERIOD not in periods and PERIOD_ID in periods
        assert db.scalar(text("SELECT count(*) FROM classsync_scheduling.room_restrictions")) == 0
        rows = db.execute(text(
            "SELECT * FROM classsync_scheduling.room_occupancy_versions('institutional',:day)"
        ), {"day": world.class_date}).mappings().all()
        # A day outside every calendar returns nothing.
        assert not db.execute(text(
            "SELECT * FROM classsync_scheduling.room_occupancy_versions('institutional',"
            "DATE '2030-01-07')"
        )).all()
        restrictions = db.execute(text(
            "SELECT * FROM classsync_scheduling.room_restriction_windows('institutional')"
        )).mappings().all()
    assert {row["period_id"] for row in rows} == {PERIOD_ID, OTHER_PERIOD}
    assert sorted(row["version_rank"] for row in rows) == [1, 2]
    for row in rows:
        projection = row["projection"]
        assert set(projection) == {"buffer", "assignments", "calendar"}
        assert {k for a in projection["assignments"] for k in a} == {
            "id", "day", "start", "end", "room_id",
        }
        assert set(projection["calendar"]) == {
            "effective_start", "effective_end", "instructional_days", "exceptions",
        }
        exported = json.dumps(projection)
        assert OUTSIDER_TEACHER not in exported and world.mine.teacher_id not in exported
        assert world.other.section_id not in exported and world.other.subject_id not in exported
    assert [set(r) for r in restrictions] == [{"room_id", "starts_at", "ends_at"}]
    assert SECRET not in json.dumps([dict(r) for r in restrictions], default=str)


def test_projection_functions_require_an_active_membership(world):
    for function in ("room_occupancy_versions('institutional',DATE '2026-09-07')",
                     "room_restriction_windows('institutional')"):
        with transaction(world.engine("runtime")) as db:
            # No tenant/uid/project context: the caller is nobody.
            with pytest.raises(DBAPIError) as error:
                db.execute(text(f"SELECT * FROM classsync_scheduling.{function}"))
            assert error.value.orig.sqlstate == "42501"
        with transaction(world.engine("runtime")) as db:
            identity_context(db, tenant_id=TENANT, uid="not-a-member")
            db.execute(text("SELECT set_config('classsync.project_id', :p, true)"), {"p": PROJECT})
            with pytest.raises(DBAPIError) as error:
                db.execute(text(f"SELECT * FROM classsync_scheduling.{function}"))
            assert error.value.orig.sqlstate == "42501"
